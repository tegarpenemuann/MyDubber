import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np

from app.celery_utils import celery_app
from app.config import settings
from app.offline import require_loopback
from app.tasks import probe_media, run_process


def video_hash(path: Path) -> str:
    return run_process(
        [
            settings.ffmpeg_binary,
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ]
    ).strip()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_video(video: Path, base_url: str, timeout: int) -> dict:
    require_loopback(urlparse(base_url).hostname)
    started = time.monotonic()
    with httpx.Client(base_url=base_url, timeout=120, trust_env=False) as client:
        for asset in ("/docs", "/docs-assets/swagger-ui-bundle.js", "/docs-assets/swagger-ui.css"):
            client.get(asset).raise_for_status()
        with video.open("rb") as source:
            response = client.post(
                "/api/v1/dubbing/tasks", files={"file": (video.name, source, "video/mp4")}
            )
        response.raise_for_status()
        if response.status_code != 202:
            raise RuntimeError(f"Unexpected upload status: {response.status_code}")
        task_id = response.json()["task_id"]
        print(f"Uploaded through API. Task: {task_id}", flush=True)

        def progress(message: dict) -> None:
            metadata = message.get("result", {})
            if isinstance(metadata, dict):
                print(
                    f"{message.get('status')}: {metadata.get('progress', 0)}% {metadata.get('stage', '')}",
                    flush=True,
                )

        celery_app.AsyncResult(task_id).get(timeout=timeout, on_message=progress)
        status_response = client.get(f"/api/v1/dubbing/tasks/{task_id}")
        status_response.raise_for_status()
        payload = status_response.json()
        if payload["status"] != "SUCCESS" or payload["progress"] != 100:
            raise RuntimeError(f"Task did not succeed: {payload}")
        output = settings.outputs_dir / f"{task_id}.mp4"
        source_info = probe_media(video)
        output_info = probe_media(output)
        duration_difference = abs(
            float(source_info["format"]["duration"]) - float(output_info["format"]["duration"])
        )
        if duration_difference > 0.25:
            raise RuntimeError(f"Video duration changed by {duration_difference:.3f}s")
        unchanged_video = video_hash(video) == video_hash(output)
        if not unchanged_video:
            raise RuntimeError("Video bitstream was unexpectedly changed.")
        run_process(
            [
                settings.ffmpeg_binary,
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(output),
                "-f",
                "null",
                "-",
            ]
        )
        decoded = subprocess.run(
            [
                settings.ffmpeg_binary,
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(output),
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                "-",
            ],
            check=True,
            capture_output=True,
            timeout=settings.ffmpeg_timeout,
        )
        samples = np.frombuffer(decoded.stdout, dtype="<i2").astype(np.float32)
        rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0
        if rms < 10:
            raise RuntimeError("Output audio is empty or silent.")
        downloaded = hashlib.sha256()
        with client.stream("GET", payload["download_url"]) as result:
            result.raise_for_status()
            for chunk in result.iter_bytes(1024 * 1024):
                downloaded.update(chunk)
        if downloaded.hexdigest() != file_hash(output):
            raise RuntimeError("Downloaded bytes differ from the rendered video.")
        partial = client.get(payload["download_url"], headers={"Range": "bytes=0-31"})
        if partial.status_code != 206 or len(partial.content) != 32:
            raise RuntimeError("Video range streaming failed.")
        if (settings.uploads_dir / f"{task_id}.mp4").exists() or (
            settings.temp_dir / task_id
        ).exists():
            raise RuntimeError("Temporary task files were not cleaned.")
    report = {
        "task_id": task_id,
        "status": payload["status"],
        "output": str(output),
        "download_url": f"{base_url.rstrip('/')}{payload['download_url']}",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "duration_seconds": float(output_info["format"]["duration"]),
        "duration_difference_seconds": round(duration_difference, 4),
        "video_bitstream_unchanged": unchanged_video,
        "audio_rms": round(rms, 2),
        "download_verified": True,
        "range_streaming_verified": True,
        "temporary_files_cleaned": True,
        "python_external_connections_blocked": True,
    }
    destination = settings.storage_dir / "e2e-report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload any test video and verify the full offline pipeline."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=1800)
    arguments = parser.parse_args()
    test_video(arguments.video, arguments.base_url, arguments.timeout)


if __name__ == "__main__":
    main()
