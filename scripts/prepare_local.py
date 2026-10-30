import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
import redis

from app.config import PROJECT_ROOT, settings


def download(url: str, destination: Path) -> None:
    if destination.is_file():
        print(f"Already available: {destination.name}", flush=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    print(f"Downloading: {destination.name}", flush=True)
    try:
        if sys.platform == "win32":
            subprocess.run(
                [
                    "curl.exe",
                    "--fail",
                    "--location",
                    "--retry",
                    "3",
                    "--retry-all-errors",
                    "--connect-timeout",
                    "30",
                    "--max-time",
                    "600",
                    "--output",
                    str(temporary),
                    url,
                ],
                check=True,
            )
        else:
            with httpx.stream("GET", url, follow_redirects=True, timeout=300) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        output.write(chunk)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def download_assets(model_hub: str) -> None:
    print("Preparing Whisper base CPU model...", flush=True)
    model_hub = model_hub.rstrip("/")
    whisper = f"{model_hub}/Systran/faster-whisper-base/resolve/main"
    for filename in ("config.json", "tokenizer.json", "vocabulary.txt", "model.bin"):
        download(f"{whisper}/{filename}", settings.whisper_model_dir / filename)
    voice = f"{model_hub}/rhasspy/piper-voices/resolve/main/id/id_ID/news_tts/medium"
    download(f"{voice}/id_ID-news_tts-medium.onnx", settings.piper_model_path)
    download(f"{voice}/id_ID-news_tts-medium.onnx.json", Path(f"{settings.piper_model_path}.json"))
    download(f"{voice}/MODEL_CARD", settings.piper_model_path.parent / "MODEL_CARD")
    swagger = PROJECT_ROOT / "tools" / "swagger"
    for filename in ("swagger-ui-bundle.js", "swagger-ui.css", "favicon-32x32.png", "LICENSE"):
        download(
            f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/{filename}", swagger / filename
        )
    install_ffmpeg()


def install_ffmpeg() -> None:
    if sys.platform == "win32":
        binary_dir = PROJECT_ROOT / "tools" / "ffmpeg" / "bin"
        if not all((binary_dir / name).is_file() for name in ("ffmpeg.exe", "ffprobe.exe")):
            archive = PROJECT_ROOT / "tools" / "ffmpeg-essentials.zip"
            download("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", archive)
            binary_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as bundle:
                for filename in ("ffmpeg.exe", "ffprobe.exe"):
                    member = next(
                        name for name in bundle.namelist() if name.endswith(f"/bin/{filename}")
                    )
                    with (
                        bundle.open(member) as source,
                        (binary_dir / filename).open("wb") as output,
                    ):
                        shutil.copyfileobj(source, output)
                for member in bundle.namelist():
                    if Path(member).name.lower().startswith(
                        ("license", "readme")
                    ) and not member.endswith("/"):
                        target = binary_dir.parent / Path(member).name
                        with bundle.open(member) as source, target.open("wb") as output:
                            shutil.copyfileobj(source, output)
            archive.unlink()
    else:
        print(
            "Install FFmpeg/FFprobe through your OS package manager before going offline.",
            flush=True,
        )


def check_assets() -> None:
    from piper.phonemize_espeak import ESPEAK_DATA_DIR

    from app.config import local_binary

    required = [
        settings.whisper_model_dir / "model.bin",
        settings.whisper_model_dir / "config.json",
        settings.whisper_model_dir / "tokenizer.json",
        settings.whisper_model_dir / "vocabulary.txt",
        settings.piper_model_path,
        Path(f"{settings.piper_model_path}.json"),
        ESPEAK_DATA_DIR / "phontab",
        *[
            PROJECT_ROOT / "tools" / "swagger" / name
            for name in (
                "swagger-ui-bundle.js",
                "swagger-ui.css",
                "favicon-32x32.png",
            )
        ],
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Missing local assets:\n"
            + "\n".join(missing)
            + "\nInstall them while online with: "
            + f'"{sys.executable}" -m scripts.prepare_local --download --skip-services'
        )
    for name in ("ffmpeg", "ffprobe"):
        configured = getattr(settings, f"{name}_binary")
        binary = local_binary(name) if configured == name else configured
        subprocess.run([binary, "-version"], check=True, capture_output=True)
    print("All local assets ready. No downloads are performed by the application.", flush=True)


def ollama_tags_url() -> str:
    parsed = urlparse(settings.ollama_url)
    return f"{parsed.scheme}://{parsed.netloc}/api/tags"


def model_names(tags: dict) -> set[str]:
    names: set[str] = set()
    for model in tags.get("models", []):
        name = str(model.get("name") or model.get("model") or "")
        if name:
            names.add(name)
            names.add(name.split(":", 1)[0])
    return names


def check_redis() -> None:
    try:
        client = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=3, socket_timeout=3
        )
        client.ping()
    except Exception as exc:
        raise RuntimeError(
            f"Redis is not reachable at {settings.redis_url}. Start it with: docker compose up -d"
        ) from exc
    print("Redis ready.", flush=True)


def check_ollama() -> None:
    url = ollama_tags_url()
    try:
        response = httpx.get(url, timeout=5, trust_env=False)
        response.raise_for_status()
        tags = response.json()
    except Exception as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {url}. Start the Ollama app or run: ollama serve"
        ) from exc
    if settings.ollama_model not in model_names(tags):
        raise RuntimeError(
            f"Ollama model '{settings.ollama_model}' is not installed. "
            f"Run: ollama pull {settings.ollama_model}"
        )
    print(f"Ollama ready with model {settings.ollama_model}.", flush=True)


def check_services() -> None:
    check_redis()
    check_ollama()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or verify offline MyDubber assets.")
    parser.add_argument(
        "--download", action="store_true", help="Explicit one-time online asset installation."
    )
    parser.add_argument(
        "--model-hub-url",
        default="https://huggingface.co",
        help="Public model hub or explicit mirror for installation only.",
    )
    parser.add_argument(
        "--skip-services",
        action="store_true",
        help="Only check local files and binaries, without Redis or Ollama.",
    )
    arguments = parser.parse_args()
    if arguments.download:
        download_assets(arguments.model_hub_url)
    check_assets()
    if not arguments.skip_services:
        check_services()


if __name__ == "__main__":
    main()
