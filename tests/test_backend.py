import json
import logging
import os
import socket
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch
from uuid import uuid4

import httpx
import numpy as np
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import HealthCheckAccessFilter, app
from app.tasks import (
    SAMPLE_RATE,
    ProgressReporter,
    assert_media_limits,
    check_ollama_available,
    cleanup_stale_artifacts,
    decode_audio,
    dub_video,
    ffmpeg,
    load_partial_transcript,
    load_segments,
    media_duration,
    parse_numbered_translation,
    piper_voice,
    probe_media,
    render_speech,
    run_process,
    speech_regions,
    synthesize,
    timeline_sample_rate,
    transcribe,
    transcribe_chunks,
    translate_segments,
    trim_edge_silence,
    video_stream_duration,
    whisper_model,
    write_silence,
)
from scripts.prepare_local import download


def ollama_response(text: str, done_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={"response": text, "done_reason": done_reason},
        request=httpx.Request("POST", "http://localhost"),
    )


class FakeVoice:
    """Synthesize deterministic audio without loading the real Piper model."""

    def __init__(self, seconds: float = 1.0, sample_rate: int = 22050) -> None:
        self.config = SimpleNamespace(sample_rate=sample_rate)
        self.seconds = seconds
        self.length_scales: list[float] = []

    def synthesize(self, text: str, syn_config=None):
        scale = syn_config.length_scale if syn_config and syn_config.length_scale else 1.0
        self.length_scales.append(scale)
        frames = max(1, round(self.seconds * scale * self.config.sample_rate))
        yield SimpleNamespace(audio_int16_array=np.full(frames, 1000, dtype=np.int16))


class PrepareLocalTests(unittest.TestCase):
    @patch("scripts.prepare_local.sys.platform", "win32")
    @patch("scripts.prepare_local.subprocess.run")
    def test_windows_download_retries_connection_errors(self, run):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "model.bin"
            temporary = destination.with_name(destination.name + ".part")
            run.side_effect = lambda *args, **kwargs: temporary.write_bytes(b"model")

            download("https://example.com/model.bin", destination)

            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--retry") + 1], "3")
            self.assertIn("--retry-all-errors", command)
            self.assertEqual(command[command.index("--connect-timeout") + 1], "30")
            self.assertTrue(run.call_args.kwargs["check"])
            self.assertEqual(destination.read_bytes(), b"model")
            self.assertFalse(temporary.exists())


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(storage_dir=Path(self.directory.name), max_upload_mb=1)
        self.settings.ensure_directories()
        self.settings_patch = patch("app.main.settings", self.settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.store_patch = patch("app.task_store.settings", self.settings)
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        self.ollama_patch = patch("app.main.check_ollama_available", return_value=(True, ""))
        self.ollama_ready = self.ollama_patch.start()
        self.addCleanup(self.ollama_patch.stop)
        self.client = TestClient(app)

    @patch("app.main.dub_video.apply_async")
    def test_upload_enqueues_with_server_generated_path(self, enqueue):
        response = self.client.post(
            "/api/v1/dubbing/tasks", files={"file": ("../../video.mp4", b"video", "video/mp4")}
        )
        self.assertEqual(response.status_code, 202)
        task_id = response.json()["task_id"]
        self.assertEqual((self.settings.uploads_dir / f"{task_id}.mp4").read_bytes(), b"video")
        record = json.loads((self.settings.tasks_dir / f"{task_id}.json").read_text("utf-8"))
        self.assertEqual(record["filename"], "video.mp4")
        self.assertEqual(record["status"], "PENDING")
        enqueue.assert_called_once_with(args=[task_id], task_id=task_id, retry=False)

    @patch("app.main.dub_video.apply_async")
    def test_invalid_uploads_are_not_queued(self, enqueue):
        for name, data, expected in [
            ("video.txt", b"video", 415),
            ("video.mp4", b"", 400),
            ("video.mp4", b"a" * (1024 * 1024 + 1), 413),
        ]:
            with self.subTest(expected=expected):
                response = self.client.post("/api/v1/dubbing/tasks", files={"file": (name, data)})
                self.assertEqual(response.status_code, expected)
        enqueue.assert_not_called()
        self.assertEqual(list(self.settings.uploads_dir.iterdir()), [])

    @patch("app.main.dub_video.apply_async", side_effect=ConnectionError("offline"))
    def test_queue_failure_removes_upload(self, _enqueue):
        response = self.client.post(
            "/api/v1/dubbing/tasks", files={"file": ("video.mp4", b"video")}
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(list(self.settings.uploads_dir.iterdir()), [])
        self.assertEqual(list(self.settings.tasks_dir.iterdir()), [])

    @patch("app.main.dub_video.apply_async")
    def test_upload_rejected_when_ollama_is_unavailable(self, enqueue):
        self.ollama_ready.return_value = (False, "Ollama is not reachable. Start the Ollama app.")

        response = self.client.post(
            "/api/v1/dubbing/tasks", files={"file": ("video.mp4", b"video")}
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("Ollama", response.json()["detail"])
        enqueue.assert_not_called()
        self.assertEqual(list(self.settings.uploads_dir.iterdir()), [])

    def test_dashboard_and_upload_config_are_served(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("text/html", page.headers["content-type"])
        self.assertIn("MyDubber", page.text)
        self.assertIn("/assets/app.js", page.text)
        config = self.client.get("/api/v1/dubbing/config")
        self.assertEqual(config.status_code, 200)
        self.assertEqual(config.json()["max_upload_mb"], 1)
        self.assertEqual(config.json()["accepted_format"], ".mp4")

    @patch("app.main.dub_video.apply_async")
    def test_task_list_reads_persisted_metadata(self, _enqueue):
        created = self.client.post("/api/v1/dubbing/tasks", files={"file": ("clip.mp4", b"video")})
        self.assertEqual(created.status_code, 202)
        task_id = created.json()["task_id"]
        listing = self.client.get("/api/v1/dubbing/tasks?limit=10")
        self.assertEqual(listing.status_code, 200)
        payload = listing.json()
        self.assertEqual(payload["active"], 1)
        self.assertEqual(payload["tasks"][0]["task_id"], task_id)
        self.assertEqual(payload["tasks"][0]["filename"], "clip.mp4")
        self.assertEqual(payload["tasks"][0]["status"], "PENDING")

    @patch("app.main.dub_video.apply_async")
    def test_retry_requeues_failed_task_with_existing_upload(self, enqueue):
        missing = self.client.post(f"/api/v1/dubbing/tasks/{uuid4()}/retry")
        self.assertEqual(missing.status_code, 404)

        created = self.client.post("/api/v1/dubbing/tasks", files={"file": ("clip.mp4", b"video")})
        self.assertEqual(created.status_code, 202)
        task_id = created.json()["task_id"]
        enqueue.reset_mock()

        from app import task_store

        task_store.update_task(task_id, status="FAILURE", stage="failed", error="failed")
        response = self.client.post(f"/api/v1/dubbing/tasks/{task_id}/retry")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "PENDING")
        enqueue.assert_called_once_with(args=[task_id], task_id=ANY, retry=False)
        self.assertNotEqual(enqueue.call_args.kwargs["task_id"], task_id)
        record = task_store.get_task(task_id)
        self.assertEqual(record["celery_task_id"], enqueue.call_args.kwargs["task_id"])
        self.assertEqual(record["status"], "PENDING")
        self.assertEqual(record["stage"], "queued")
        self.assertIsNone(record["error"])

    @patch("app.main.celery_app.control.revoke")
    @patch("app.main.dub_video.apply_async")
    def test_pause_resume_and_delete_endpoints(self, enqueue, revoke):
        from app import task_store

        missing_id = str(uuid4())
        self.assertEqual(
            self.client.post(f"/api/v1/dubbing/tasks/{missing_id}/pause").status_code, 404
        )
        self.assertEqual(self.client.delete(f"/api/v1/dubbing/tasks/{missing_id}").status_code, 404)

        created = self.client.post("/api/v1/dubbing/tasks", files={"file": ("clip.mp4", b"video")})
        self.assertEqual(created.status_code, 202)
        task_id = created.json()["task_id"]
        enqueue.reset_mock()

        task_store.update_task(task_id, status="PROGRESS", progress=35, stage="translating")
        paused = self.client.post(f"/api/v1/dubbing/tasks/{task_id}/pause")
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["status"], "PAUSED")
        self.assertEqual(paused.json()["progress"], 35)
        self.assertEqual(paused.json()["stage"], "paused")
        revoke.assert_called_with(task_id)

        with patch(
            "app.main.celery_app.AsyncResult",
            return_value=SimpleNamespace(state="REVOKED", info=None),
        ):
            polled = self.client.get(f"/api/v1/dubbing/tasks/{task_id}")
        self.assertEqual(polled.status_code, 200)
        self.assertEqual(polled.json()["status"], "PAUSED")
        self.assertEqual(polled.json()["progress"], 35)

        resumed = self.client.post(f"/api/v1/dubbing/tasks/{task_id}/resume")
        self.assertEqual(resumed.status_code, 202)
        self.assertEqual(resumed.json()["status"], "PENDING")
        enqueue.assert_called_once_with(args=[task_id], task_id=ANY, retry=False)
        resumed_celery_id = enqueue.call_args.kwargs["task_id"]
        self.assertNotEqual(resumed_celery_id, task_id)
        self.assertEqual(task_store.get_task(task_id)["celery_task_id"], resumed_celery_id)

        work_dir = self.settings.temp_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "segments.json").write_text("{}", encoding="utf-8")
        output = self.settings.outputs_dir / f"{task_id}.mp4"
        output.write_bytes(b"done")
        self.assertEqual(
            self.client.post(f"/api/v1/dubbing/tasks/{task_id}/pause").status_code, 409
        )

        deleted = self.client.delete(f"/api/v1/dubbing/tasks/{task_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["deleted"])
        revoke.assert_called_with(resumed_celery_id)
        self.assertIsNone(task_store.get_task(task_id))
        self.assertFalse((self.settings.uploads_dir / f"{task_id}.mp4").exists())
        self.assertFalse(work_dir.exists())
        self.assertFalse(output.exists())

    @patch("app.main.celery_app.AsyncResult")
    def test_polling_states(self, async_result):
        cases = [
            ("PENDING", None, 0, "queued"),
            ("STARTED", {"pid": 1}, 0, "processing"),
            ("PROGRESS", {"progress": 60, "stage": "translated"}, 60, "translated"),
            ("SUCCESS", {"download_url": "/outputs/test.mp4"}, 100, "completed"),
            ("FAILURE", ValueError("private error"), 0, "failed"),
        ]
        for state, info, progress, stage in cases:
            with self.subTest(state=state):
                async_result.return_value = SimpleNamespace(state=state, info=info)
                task_id = str(uuid4())
                if state == "PENDING":
                    (self.settings.uploads_dir / f"{task_id}.mp4").touch()
                response = self.client.get(f"/api/v1/dubbing/tasks/{task_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual((payload["progress"], payload["stage"]), (progress, stage))
                self.assertNotIn("private error", response.text)
                if state == "SUCCESS":
                    self.assertEqual(payload["download_url"], "/outputs/test.mp4")

    @patch("app.main.celery_app.AsyncResult")
    def test_unknown_task_does_not_report_queued_progress(self, async_result):
        async_result.return_value = SimpleNamespace(state="PENDING", info=None)
        response = self.client.get("/api/v1/dubbing/tasks/c289faab-d38d-401f-9f22-9d028bbca925")
        self.assertEqual(response.status_code, 404)
        self.assertIn("actual upload response", response.json()["detail"])

    def test_only_missing_health_access_logs_are_hidden(self):
        access_filter = HealthCheckAccessFilter()
        for method, path, response_status, expected in (
            ("GET", "/health", 404, False),
            ("HEAD", "/health?probe=1", 404, False),
            ("GET", "/health", 500, True),
            ("GET", "/other", 404, True),
            ("POST", "/health", 404, True),
            ("GET", "/api/v1/dubbing/tasks/test", 200, True),
        ):
            with self.subTest(method=method, path=path, status=response_status):
                record = logging.LogRecord(
                    "uvicorn.access",
                    logging.INFO,
                    "",
                    0,
                    "%s %s %s %s %s",
                    ("127.0.0.1", method, path, "1.1", response_status),
                    None,
                )
                self.assertEqual(access_filter.filter(record), expected)

    @patch("app.main.celery_app.AsyncResult", side_effect=ConnectionError("offline"))
    def test_polling_backend_failure(self, _result):
        response = self.client.get(f"/api/v1/dubbing/tasks/{uuid4()}")
        self.assertEqual(response.status_code, 503)

    def test_invalid_task_id(self):
        self.assertEqual(self.client.get("/api/v1/dubbing/tasks/invalid").status_code, 422)

    def test_swagger_ui_is_available(self):
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SwaggerUIBundle", response.text)
        self.assertIn("/openapi.json", response.text)
        self.assertIn('src="/docs-assets/swagger-ui-bundle.js"', response.text)
        self.assertNotIn("cdn.jsdelivr.net", response.text)
        self.assertNotIn("fastapi.tiangolo.com", response.text)
        self.assertIn('"validatorUrl": null', response.text)

    def test_openapi_documents_upload_polling_and_errors(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertIn("Try It Directly in Swagger", schema["info"]["description"])
        upload = schema["paths"]["/api/v1/dubbing/tasks"]["post"]
        self.assertEqual(upload["tags"], ["Dubbing"])
        multipart = upload["requestBody"]["content"]["multipart/form-data"]["schema"]
        body = schema["components"]["schemas"][multipart["$ref"].split("/")[-1]]
        self.assertIn("file", body["required"])
        self.assertEqual(body["properties"]["file"]["format"], "binary")
        for code in ("202", "400", "413", "415", "422", "503"):
            self.assertIn(code, upload["responses"])
        polling = schema["paths"]["/api/v1/dubbing/tasks/{task_id}"]["get"]
        self.assertEqual(polling["parameters"][0]["schema"]["format"], "uuid")
        self.assertNotIn("examples", polling["parameters"][0]["schema"])
        self.assertIn("404", polling["responses"])
        examples = polling["responses"]["200"]["content"]["application/json"]["examples"]
        self.assertEqual(examples["success"]["value"]["status"], "SUCCESS")
        self.assertTrue(examples["success"]["value"]["download_url"].startswith("/outputs/"))
        self.assertIn("failure", examples)

    def test_cors_preflight(self):
        response = self.client.options(
            "/api/v1/dubbing/tasks",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_translation_uses_non_streaming_local_ollama(self):
        response = httpx.Response(
            200,
            json={"response": "Halo", "done_reason": "stop"},
            request=httpx.Request("POST", "http://localhost"),
        )
        client = Mock()
        client.post.return_value = response
        with patch("app.tasks.httpx.Client") as factory:
            factory.return_value.__enter__.return_value = client
            translated = translate_segments([{"start": 0, "end": 1, "text": "Hello"}])
        self.assertEqual(translated[0]["text"], "Halo")
        self.assertFalse(client.post.call_args.kwargs["json"]["stream"])
        self.assertEqual(client.post.call_args.kwargs["json"]["options"]["num_gpu"], 0)

    @patch("app.tasks.httpx.Client")
    def test_translation_system_carries_a_duration_based_character_budget(self, factory):
        client = Mock()
        client.post.return_value = ollama_response("Halo")
        factory.return_value.__enter__.return_value = client
        translated = translate_segments([{"start": 0, "end": 2, "text": "Hello"}])
        system = client.post.call_args.kwargs["json"]["system"]
        self.assertIn("at or below 28 characters", system)
        self.assertEqual(translated[0]["text"], "Halo")

    @patch("app.tasks.httpx.Client")
    def test_overlong_translation_is_shortened_before_synthesis(self, factory):
        client = Mock()
        client.post.side_effect = [
            ollama_response("Ini adalah terjemahan yang jauh terlalu panjang untuk durasinya"),
            ollama_response("Halo"),
        ]
        factory.return_value.__enter__.return_value = client
        translated = translate_segments([{"start": 0, "end": 1, "text": "Hello"}])
        self.assertEqual(translated[0]["text"], "Halo")
        self.assertEqual(client.post.call_count, 2)
        self.assertIn("Current translation:", client.post.call_args.kwargs["json"]["prompt"])

    @patch("app.tasks.run_process", return_value='{"streams": []}')
    def test_media_tools_only_allow_local_protocols(self, process):
        ffmpeg("-i", "source.mp4", "-i", "dubbing.mp3", "result.mp4")
        command = process.call_args.args[0]
        for index, argument in enumerate(command):
            if argument == "-i":
                self.assertEqual(command[index - 2 : index], ["-protocol_whitelist", "file,pipe"])
        probe_media(Path("source.mp4"))
        command = process.call_args.args[0]
        self.assertEqual(command[command.index("-protocol_whitelist") + 1], "file,pipe")

    @patch("app.tasks.subprocess.run")
    @patch("app.tasks.local_binary")
    def test_media_tools_resolve_bundled_binary_at_execution(self, resolve, process):
        process.return_value.stdout = "version"
        for name in ("ffmpeg", "ffprobe"):
            with self.subTest(name=name):
                bundled = str(Path(self.directory.name) / f"{name}.exe")
                resolve.return_value = bundled
                command = [name, "-version"]
                self.assertEqual(run_process(command), "version")
                resolve.assert_called_with(name)
                self.assertEqual(process.call_args.args[0], [bundled, "-version"])
                self.assertEqual(command, [name, "-version"])

    @patch("app.tasks.subprocess.run")
    @patch("app.tasks.local_binary")
    def test_media_tools_preserve_custom_binary_path(self, resolve, process):
        command = [str(Path(self.directory.name) / "custom-ffprobe.exe"), "-version"]
        run_process(command)
        resolve.assert_not_called()
        self.assertEqual(process.call_args.args[0], command)

    def test_whisper_requires_local_model_and_never_downloads(self):
        local_model = Path(self.directory.name) / "whisper-base"
        local_model.mkdir()
        local_settings = Settings(whisper_model_dir=local_model)
        whisper_model.cache_clear()
        self.addCleanup(whisper_model.cache_clear)
        with (
            patch("app.tasks.settings", local_settings),
            patch("faster_whisper.WhisperModel") as engine,
        ):
            with self.assertRaisesRegex(RuntimeError, "Local Whisper model is not available"):
                whisper_model()
            engine.assert_not_called()
            (local_model / "model.bin").touch()
            whisper_model()
            self.assertTrue(engine.call_args.kwargs["local_files_only"])
            self.assertEqual(engine.call_args.args[0], str(local_model))

    def test_only_loopback_services_are_allowed(self):
        for field in ("ollama_url", "redis_url", "redis_result_url"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                Settings(**{field: "http://example.com/service"})

    def test_external_network_is_blocked_before_connecting(self):
        with self.assertRaises(PermissionError):
            socket.getaddrinfo("example.com", 443)
        with socket.socket() as connection:
            with self.assertRaises(PermissionError):
                connection.connect(("1.1.1.1", 443))

    def test_piper_requires_local_indonesian_model(self):
        model = Path(self.directory.name) / "voice.onnx"
        local_settings = Settings(piper_model_path=model)
        piper_voice.cache_clear()
        self.addCleanup(piper_voice.cache_clear)
        with patch("app.tasks.settings", local_settings), patch("piper.PiperVoice.load") as engine:
            with self.assertRaisesRegex(
                RuntimeError, "Local Indonesian Piper model is not available"
            ):
                piper_voice()
            engine.assert_not_called()
            model.touch()
            Path(f"{model}.json").write_text(
                json.dumps(
                    {
                        "espeak": {"voice": "id"},
                        "phoneme_type": "espeak",
                    }
                ),
                encoding="utf-8",
            )
            piper_voice()
            engine.assert_called_once_with(str(model), use_cuda=False)

    def test_timeline_has_exact_duration_and_silence(self):
        voice = FakeVoice(seconds=2.0)
        work_dir = Path(self.directory.name)
        with (
            patch("app.tasks.piper_voice", return_value=voice),
            patch("app.tasks.ffmpeg") as media,
        ):
            output = synthesize([{"start": 1, "end": 2, "text": "Halo"}], 3, work_dir)
        media.assert_not_called()
        self.assertEqual(output, work_dir / "timeline.wav")
        self.assertFalse((work_dir / "timeline.wav.part").exists())
        with wave.open(str(output), "rb") as timeline:
            self.assertEqual(timeline.getframerate(), 22050)
            self.assertEqual(timeline.getnframes(), 3 * 22050)
            self.assertEqual(timeline.readframes(22050), b"\x00\x00" * 22050)
            self.assertEqual(timeline.readframes(1), (1000).to_bytes(2, "little", signed=True))
        # 2 seconds do not fit into a 1 second slot, so Piper resynthesizes at 0.5x.
        self.assertEqual(voice.length_scales[0], 1.0)
        self.assertAlmostEqual(voice.length_scales[1], 0.5)
        # No word is cut off: the whole sentence is still audible in the slot.
        with wave.open(str(output), "rb") as timeline:
            timeline.setpos(22050)
            frames = np.frombuffer(timeline.readframes(22050), dtype="<i2")
        self.assertTrue((frames == 1000).all())

    def test_short_speech_is_stretched_to_fill_the_slot(self):
        voice = FakeVoice(seconds=0.4)
        work_dir = Path(self.directory.name)
        with patch("app.tasks.piper_voice", return_value=voice):
            output = synthesize([{"start": 0, "end": 1, "text": "Halo"}], 1, work_dir)
        self.assertEqual(voice.length_scales, [1.0, 1.5])
        with wave.open(str(output), "rb") as timeline:
            self.assertEqual(timeline.getnframes(), 22050)
            frames = np.frombuffer(timeline.readframes(22050), dtype="<i2")
        self.assertTrue((frames[:10] == 1000).all())
        self.assertTrue((frames[-10:] == 0).all())

    def test_small_gap_between_segments_is_filled_with_speech(self):
        voice = FakeVoice(seconds=1.0)
        work_dir = Path(self.directory.name)
        segments = [
            {"start": 0, "end": 1, "text": "Satu"},
            {"start": 1.4, "end": 2, "text": "Dua"},
        ]
        with patch("app.tasks.piper_voice", return_value=voice):
            output = synthesize(segments, 2, work_dir)
        with wave.open(str(output), "rb") as timeline:
            frames = np.frombuffer(timeline.readframes(2 * 22050), dtype="<i2")
        self.assertEqual(frames[int(1.2 * 22050)], 1000)
        self.assertEqual(voice.length_scales, [1.0, 1.4, 1.0, 0.6])

    def test_edge_silence_from_synthesizer_is_trimmed(self):
        samples = np.concatenate(
            [
                np.zeros(441, dtype=np.int16),
                np.full(22050, 1000, dtype=np.int16),
                np.zeros(441, dtype=np.int16),
            ]
        )
        trimmed = trim_edge_silence(samples, 22050)
        self.assertEqual(len(trimmed), 22050)

    def test_render_speech_keeps_all_words_when_slot_is_very_short(self):
        voice = FakeVoice(seconds=1.0)
        with patch("app.tasks.settings.dub_min_length_scale", 0.2):
            samples = render_speech(voice, "Halo", 0.25, 22050)
        self.assertEqual(len(samples), round(0.25 * 22050))
        self.assertTrue((samples == 1000).all())

    def test_emergency_length_scale_fits_overlong_speech_without_trimming(self):
        voice = FakeVoice(seconds=4.0)
        with (
            patch("app.tasks.settings.dub_min_length_scale", 0.5),
            patch("app.tasks.settings.dub_emergency_min_length_scale", 0.25),
        ):
            samples = render_speech(voice, "Halo", 1.0, 22050)
        self.assertEqual(voice.length_scales, [1.0, 0.5, 0.25])
        self.assertEqual(len(samples), 22050)
        self.assertTrue((samples == 1000).all())

    def test_oversized_segment_slot_keeps_a_natural_speaking_rate(self):
        voice = FakeVoice(seconds=3.0)
        work_dir = Path(self.directory.name) / "long-slot"
        work_dir.mkdir()
        with patch("app.tasks.piper_voice", return_value=voice):
            output = synthesize([{"start": 0, "end": 22, "text": "Halo"}], 22, work_dir)
        self.assertEqual(voice.length_scales, [1.0])
        with wave.open(str(output), "rb") as timeline:
            self.assertEqual(timeline.getnframes(), 22 * 22050)

    def test_synthesis_reports_total_time_lost_to_trimming(self):
        voice = FakeVoice(seconds=10.0)
        stats = {"trimmed_seconds": 0.0}
        with (
            patch("app.tasks.settings.dub_min_length_scale", 0.5),
            patch("app.tasks.settings.dub_emergency_min_length_scale", 0.2),
            self.assertLogs("app.tasks", level="WARNING") as captured,
        ):
            render_speech(voice, "Halo", 1.0, 22050, stats)
        self.assertGreater(stats["trimmed_seconds"], 0)
        self.assertTrue(any("trimming" in message for message in captured.output))

    def test_timeline_can_span_hours_without_buffering(self):
        voice = FakeVoice(seconds=0.2, sample_rate=100)
        work_dir = Path(self.directory.name)
        segments = [
            {"start": float(minute * 60), "end": float(minute * 60 + 1), "text": "Halo"}
            for minute in range(0, 120, 2)
        ]
        with patch("app.tasks.piper_voice", return_value=voice):
            output = synthesize(segments, 7200, work_dir)
        with wave.open(str(output), "rb") as timeline:
            self.assertEqual(timeline.getframerate(), 100)
            self.assertEqual(timeline.getnframes(), 7200 * 100)

    def test_chunked_silence_uses_requested_sample_rate(self):
        audio = Mock()
        write_silence(audio, 32001)
        self.assertEqual(
            sum(len(call.args[0]) for call in audio.writeframesraw.call_args_list), 64002
        )
        audio = Mock()
        write_silence(audio, 22050 * 2 + 10, 22050)
        self.assertEqual(len(audio.writeframesraw.call_args_list), 3)

    def test_pipeline_progress_merge_and_cleanup(self):
        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.write_bytes(b"video")
        segments = [{"start": 0, "end": 1, "text": "Halo"}]

        def fake_ffmpeg(*arguments):
            Path(arguments[-1]).touch()

        with (
            patch("app.tasks.settings", self.settings),
            patch(
                "app.tasks.probe_media",
                return_value={
                    "format": {"duration": "2.0"},
                    "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                },
            ),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg) as media,
            patch("app.tasks.transcribe", return_value=segments),
            patch("app.tasks.translate_segments", return_value=segments),
            patch("app.tasks.synthesize", return_value=Path(self.directory.name) / "timeline.wav"),
            patch.object(dub_video, "update_state") as update,
        ):
            result = dub_video.run(task_id)
        self.assertEqual(
            [call.kwargs["meta"]["progress"] for call in update.call_args_list],
            [10, 30, 60, 80, 100],
        )
        self.assertEqual(result["download_url"], f"/outputs/{task_id}.mp4")
        self.assertTrue((self.settings.outputs_dir / f"{task_id}.mp4").exists())
        self.assertFalse(source.exists())
        self.assertFalse((self.settings.temp_dir / task_id).exists())
        merge = media.call_args_list[-1].args
        self.assertEqual(merge[merge.index("-c:v") + 1], "copy")

    def test_pipeline_failure_cleans_temp_files(self):
        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.touch()
        with (
            patch("app.tasks.settings", self.settings),
            patch("app.tasks.probe_media", side_effect=ValueError("invalid media")),
        ):
            with self.assertRaises(ValueError):
                dub_video.run(task_id)
        self.assertFalse(source.exists())
        self.assertFalse((self.settings.temp_dir / task_id).exists())

    def test_pipeline_failure_keeps_the_real_error_in_task_metadata(self):
        from app import task_store

        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.write_bytes(b"video")
        task_store.create_task(task_id, "clip.mp4", 5)

        with (
            patch("app.tasks.settings", self.settings),
            patch("app.tasks.probe_media", side_effect=RuntimeError("Ollama is not reachable")),
        ):
            with self.assertRaises(RuntimeError):
                dub_video.run(task_id)

        record = task_store.get_task(task_id)
        self.assertEqual(record["status"], "FAILURE")
        self.assertEqual(record["error"], "Ollama is not reachable")

    def test_pipeline_reuses_transcript_and_translation_checkpoints(self):
        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.write_bytes(b"video")
        work_dir = self.settings.temp_dir / task_id
        work_dir.mkdir(parents=True)
        segments = [{"start": 0.0, "end": 1.0, "text": "Halo"}]
        (work_dir / "segments.json").write_text(
            json.dumps({"duration": 2.0, "segments": segments}), encoding="utf-8"
        )
        (work_dir / "translations.json").write_text(
            json.dumps({"entries": [{"index": 0, "source": "Halo", "text": "Halo"}]}),
            encoding="utf-8",
        )
        (work_dir / "timeline.wav").write_bytes(b"timeline")

        def fake_ffmpeg(*arguments):
            Path(arguments[-1]).touch()

        with (
            patch("app.tasks.settings", self.settings),
            patch(
                "app.tasks.probe_media",
                return_value={
                    "format": {"duration": "2.0"},
                    "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                },
            ),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg),
            patch("app.tasks.transcribe") as transcribe_task,
            patch("app.tasks.translate_segments") as translate_task,
            patch("app.tasks.synthesize") as synthesize_task,
            patch.object(dub_video, "update_state"),
        ):
            result = dub_video.run(task_id)

        transcribe_task.assert_not_called()
        synthesize_task.assert_not_called()
        translate_task.assert_called_once()
        self.assertEqual(result["progress"], 100)
        self.assertFalse(source.exists())
        self.assertFalse(work_dir.exists())

    def test_pipeline_keeps_the_upload_when_a_checkpoint_can_be_resumed(self):
        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.write_bytes(b"video")
        work_dir = self.settings.temp_dir / task_id
        work_dir.mkdir(parents=True)
        (work_dir / "segments.json").write_text(
            json.dumps({"duration": 2.0, "segments": [{"start": 0, "end": 1, "text": "Halo"}]}),
            encoding="utf-8",
        )

        with (
            patch("app.tasks.settings", self.settings),
            patch(
                "app.tasks.probe_media",
                return_value={
                    "format": {"duration": "2.0"},
                    "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                },
            ),
            patch("app.tasks.translate_segments", side_effect=ValueError("ollama offline")),
        ):
            with self.assertRaises(ValueError):
                dub_video.run(task_id)

        self.assertTrue(source.exists())
        self.assertTrue((work_dir / "segments.json").exists())

    def test_rejects_videos_over_the_duration_limit(self):
        source = Path(self.directory.name) / "video.mp4"
        source.write_bytes(b"video")
        limited = Settings(storage_dir=Path(self.directory.name), max_media_hours=0.5)
        with patch("app.tasks.settings", limited):
            with self.assertRaisesRegex(ValueError, "configured limit"):
                assert_media_limits(source, 3600)

    def test_rejects_videos_without_enough_disk_space(self):
        source = Path(self.directory.name) / "video.mp4"
        source.write_bytes(b"video")
        usage = SimpleNamespace(total=1, used=1, free=0)
        with patch("app.tasks.shutil.disk_usage", return_value=usage):
            with self.assertRaisesRegex(RuntimeError, "disk space"):
                assert_media_limits(source, 60)

    def test_timeline_sample_rate_uses_the_voice_configuration(self):
        model = Path(self.directory.name) / "voice.onnx"
        model.touch()
        Path(f"{model}.json").write_text(
            json.dumps({"audio": {"sample_rate": 16000}}), encoding="utf-8"
        )
        with patch("app.tasks.settings", Settings(piper_model_path=model)):
            self.assertEqual(timeline_sample_rate(), 16000)
        with patch("app.tasks.settings", Settings(piper_model_path=Path("missing.onnx"))):
            self.assertEqual(timeline_sample_rate(), 22050)

    def test_stale_artifacts_are_removed(self):
        old_upload = self.settings.uploads_dir / f"{uuid4()}.mp4"
        old_upload.write_bytes(b"old")
        old_work = self.settings.temp_dir / str(uuid4())
        old_work.mkdir()
        (old_work / "segments.json").write_text("{}", encoding="utf-8")
        fresh_upload = self.settings.uploads_dir / f"{uuid4()}.mp4"
        fresh_upload.write_bytes(b"fresh")
        for path in (old_upload, old_work):
            os.utime(path, (0, 0))
        with patch("app.tasks.settings", self.settings):
            cleanup_stale_artifacts(max_age_seconds=60)
        self.assertFalse(old_upload.exists())
        self.assertFalse(old_work.exists())
        self.assertTrue(fresh_upload.exists())

    def test_progress_reporter_throttles_repeated_updates(self):
        update = Mock()
        reporter = ProgressReporter(update, minimum_interval=3600)
        reporter(10, "extracted")
        reporter(12, "transcribing")
        reporter(13, "transcribing")
        reporter(30, "transcribed")
        self.assertEqual(
            [call.kwargs["meta"]["progress"] for call in update.call_args_list],
            [10, 12, 30],
        )

    def test_transcription_avoids_long_audio_drift(self):
        segment = SimpleNamespace(
            start=0.0,
            end=1.0,
            text=" Hello ",
            avg_logprob=-0.2,
            no_speech_prob=0.1,
            compression_ratio=1.4,
        )
        engine = Mock()
        engine.transcribe.return_value = ([segment], None)
        updates = []
        with (
            patch("app.tasks.whisper_model", return_value=engine),
            patch("app.tasks.decode_audio", return_value=np.zeros(32000, dtype=np.float32)),
            patch("app.tasks.speech_regions", return_value=[(0, 16000)]),
        ):
            transcript = transcribe(
                Path("audio.wav"),
                duration=2.0,
                on_progress=lambda percent, stage: updates.append((percent, stage)),
            )
        self.assertEqual(transcript, [{"start": 0.0, "end": 1.0, "text": "Hello"}])
        options = engine.transcribe.call_args.kwargs
        self.assertFalse(options["condition_on_previous_text"])
        self.assertFalse(options["vad_filter"])
        self.assertEqual(updates, [(19, "transcribing")])

    def test_transcription_offsets_each_vad_region_and_keeps_gap_silent(self):
        def region_segments(region):
            if region == "first":
                return ([SimpleNamespace(start=0.0, end=2.0, text="Pertama")], None)
            return ([SimpleNamespace(start=0.0, end=1.0, text="Kedua")], None)

        engine = Mock()
        engine.transcribe.side_effect = lambda audio, **kwargs: region_segments(
            "first" if len(audio) == 16000 else "second"
        )
        with (
            patch("app.tasks.whisper_model", return_value=engine),
            patch("app.tasks.decode_audio", return_value=np.zeros(100000, dtype=np.float32)),
            patch("app.tasks.speech_regions", return_value=[(0, 16000), (60000, 80000)]),
        ):
            transcript = transcribe(Path("audio.wav"), duration=6.0)
        self.assertEqual(
            transcript,
            [
                {"start": 0.0, "end": 2.0, "text": "Pertama"},
                {"start": 3.75, "end": 4.75, "text": "Kedua"},
            ],
        )
        self.assertEqual(engine.transcribe.call_count, 2)
        for call in engine.transcribe.call_args_list:
            self.assertFalse(call.kwargs["vad_filter"])

    def test_unreliable_transcription_segments_are_dropped(self):
        from app.tasks import segment_is_reliable

        good = SimpleNamespace(avg_logprob=-0.2, no_speech_prob=0.1, compression_ratio=1.4)
        repetitive = SimpleNamespace(avg_logprob=-0.2, no_speech_prob=0.1, compression_ratio=3.0)
        noisy = SimpleNamespace(avg_logprob=-1.4, no_speech_prob=0.9, compression_ratio=1.4)
        self.assertTrue(segment_is_reliable(good))
        self.assertFalse(segment_is_reliable(repetitive))
        self.assertFalse(segment_is_reliable(noisy))

    @unittest.skipUnless(
        (
            Path(__file__).resolve().parent.parent
            / "Jensen-Huang-just-shrunk-a-supercomputer-into-a-laptop.mp4"
        ).is_file(),
        "Jensen sample video is not present in the project root.",
    )
    def test_jensen_video_keeps_the_applause_gap_silent(self):
        """Regression: Silero must not let Whisper bridge the 40.7-47.3 s applause."""
        video = (
            Path(__file__).resolve().parent.parent
            / "Jensen-Huang-just-shrunk-a-supercomputer-into-a-laptop.mp4"
        )
        audio = Path(self.directory.name) / "jensen.wav"
        ffmpeg(
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(audio),
        )
        samples = decode_audio(audio)
        regions = speech_regions(samples)
        self.assertTrue(regions)
        for start, end in regions:
            self.assertFalse(
                start < 44 * SAMPLE_RATE < end,
                f"VAD region {start / SAMPLE_RATE:.2f}-{end / SAMPLE_RATE:.2f} bridges applause",
            )
        segments = transcribe(audio, duration=len(samples) / SAMPLE_RATE)
        self.assertTrue(segments)
        for segment in segments:
            self.assertFalse(
                segment["start"] < 44.0 < segment["end"],
                f"Dubbed segment bridges the applause gap: {segment}",
            )

    def test_ollama_preflight_detects_missing_service_and_model(self):
        with patch("app.tasks.httpx.Client") as factory:
            client = factory.return_value.__enter__.return_value
            client.get.side_effect = httpx.ConnectError(
                "offline", request=httpx.Request("GET", "http://127.0.0.1")
            )
            ready, message = check_ollama_available()
            self.assertFalse(ready)
            self.assertIn("not reachable", message)

        with patch("app.tasks.httpx.Client") as factory:
            client = factory.return_value.__enter__.return_value
            client.get.return_value = httpx.Response(
                200,
                json={"models": [{"name": "other:latest"}]},
                request=httpx.Request("GET", "http://127.0.0.1"),
            )
            ready, message = check_ollama_available()
            self.assertFalse(ready)
            self.assertIn("not installed", message)

    def test_partial_transcript_checkpoint_is_not_treated_as_complete(self):
        work_dir = Path(self.directory.name) / "work"
        work_dir.mkdir()
        checkpoint = work_dir / "segments.json"
        checkpoint.write_text(
            json.dumps(
                {
                    "duration": 1200.0,
                    "processed_seconds": 600.0,
                    "segments": [{"start": 1.0, "end": 2.0, "text": "Halo"}],
                }
            ),
            encoding="utf-8",
        )
        self.assertIsNone(load_segments(checkpoint, 1200.0))
        segments, processed = load_partial_transcript(checkpoint, 1200.0)
        self.assertEqual(processed, 600.0)
        self.assertEqual(len(segments), 1)

    def test_chunked_transcription_resumes_and_drops_overlap_duplicates(self):
        work_dir = Path(self.directory.name) / "work"
        work_dir.mkdir()
        checkpoint = work_dir / "segments.json"
        checkpoint.write_text(
            json.dumps(
                {
                    "duration": 1300.0,
                    "processed_seconds": 600.0,
                    "segments": [{"start": 1.0, "end": 2.0, "text": "awal"}],
                }
            ),
            encoding="utf-8",
        )
        chunked = Settings(
            storage_dir=Path(self.directory.name),
            transcribe_chunk_seconds=600,
            transcribe_chunk_overlap_seconds=2,
        )
        responses = [
            [
                {"start": 1.0, "end": 2.0, "text": "duplikat"},
                {"start": 3.0, "end": 4.0, "text": "kedua"},
            ],
            [
                {"start": 0.5, "end": 1.5, "text": "duplikat2"},
                {"start": 4.0, "end": 5.0, "text": "ketiga"},
            ],
        ]

        def fake_transcribe(path, duration=None, on_progress=None):
            result = responses.pop(0)
            if on_progress is not None:
                on_progress(29, "transcribing")
            return result

        def fake_ffmpeg(*arguments):
            Path(arguments[-1]).touch()

        with (
            patch("app.tasks.settings", chunked),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg) as media,
            patch("app.tasks.transcribe", side_effect=fake_transcribe),
        ):
            segments = transcribe_chunks(
                Path("audio.wav"),
                duration=1300.0,
                checkpoint=checkpoint,
                on_progress=lambda percent, stage: None,
            )

        self.assertEqual([item["text"] for item in segments], ["awal", "kedua", "ketiga"])
        self.assertEqual([item["start"] for item in segments], [1.0, 601.0, 1202.0])
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(payload["processed_seconds"], 1300.0)
        self.assertEqual(len(payload["segments"]), 3)
        self.assertFalse((work_dir / "transcribe-chunk.wav").exists())
        seeks = [call.args[call.args.index("-ss") + 1] for call in media.call_args_list]
        self.assertEqual(seeks, ["598.000", "1198.000"])

    def test_long_video_uses_chunked_transcription(self):
        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.write_bytes(b"video")
        segments = [{"start": 0, "end": 1, "text": "Halo"}]
        long_settings = Settings(
            storage_dir=Path(self.directory.name),
            max_upload_mb=1,
            transcribe_chunk_seconds=60,
        )

        def fake_ffmpeg(*arguments):
            Path(arguments[-1]).touch()

        with (
            patch("app.tasks.settings", long_settings),
            patch(
                "app.tasks.probe_media",
                return_value={
                    "format": {"duration": "120.0"},
                    "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                },
            ),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg),
            patch("app.tasks.transcribe_chunks", return_value=segments) as chunked,
            patch("app.tasks.transcribe") as plain,
            patch("app.tasks.translate_segments", return_value=segments),
            patch("app.tasks.synthesize", return_value=Path(self.directory.name) / "timeline.wav"),
            patch.object(dub_video, "update_state"),
        ):
            result = dub_video.run(task_id)

        chunked.assert_called_once()
        plain.assert_not_called()
        self.assertEqual(result["progress"], 100)

    def test_media_duration_falls_back_to_stream_duration(self):
        with patch(
            "app.tasks.probe_media",
            return_value={"format": {"duration": "N/A"}, "streams": [{"duration": "120.5"}]},
        ):
            self.assertEqual(media_duration(Path("video.mp4")), 120.5)

    def test_video_stream_duration_is_preferred_for_the_timeline(self):
        media = {
            "format": {"duration": "53.568"},
            "streams": [
                {"codec_type": "video", "duration": "53.517"},
                {"codec_type": "audio", "duration": "53.568"},
            ],
        }
        self.assertEqual(video_stream_duration(media), 53.517)
        self.assertIsNone(
            video_stream_duration({"streams": [{"codec_type": "audio", "duration": "10"}]})
        )

    def test_media_timeout_follows_configuration(self):
        with (
            patch("app.tasks.subprocess.run") as process,
            patch("app.tasks.settings") as configured,
        ):
            process.return_value.stdout = ""
            configured.ffmpeg_timeout = 1234
            run_process(["custom-tool", "-version"])
        self.assertEqual(process.call_args.kwargs["timeout"], 1234)

    def test_numbered_translation_parser(self):
        self.assertEqual(parse_numbered_translation("[1] Satu\n[2] Dua", 2), ["Satu", "Dua"])
        self.assertEqual(
            parse_numbered_translation("[1] Satu\nlanjutan\n[2] Dua", 2),
            ["Satu lanjutan", "Dua"],
        )
        self.assertIsNone(parse_numbered_translation("[1] Satu", 2))
        self.assertIsNone(parse_numbered_translation("[1] \n[2] Dua", 2))
        self.assertIsNone(parse_numbered_translation("[1] Satu\n[3] Tiga", 2))

    @patch("app.tasks.httpx.Client")
    def test_translation_batches_numbered_segments(self, factory):
        client = Mock()
        client.post.return_value = ollama_response("[1] Satu\n[2] Dua\n[3] Tiga")
        factory.return_value.__enter__.return_value = client
        translated = translate_segments(
            [
                {"start": 0, "end": 1, "text": "One"},
                {"start": 1, "end": 2, "text": "Two"},
                {"start": 2, "end": 3, "text": "Three"},
            ]
        )
        self.assertEqual([item["text"] for item in translated], ["Satu", "Dua", "Tiga"])
        self.assertEqual(client.post.call_count, 1)
        self.assertEqual(
            client.post.call_args.kwargs["json"]["prompt"], "[1] One\n[2] Two\n[3] Three"
        )

    @patch("app.tasks.httpx.Client")
    def test_unusable_batch_falls_back_to_single_segments(self, factory):
        client = Mock()
        client.post.side_effect = [
            ollama_response("not numbered at all"),
            ollama_response("Satu"),
            ollama_response("Dua"),
        ]
        factory.return_value.__enter__.return_value = client
        translated = translate_segments(
            [
                {"start": 0, "end": 1, "text": "One"},
                {"start": 1, "end": 2, "text": "Two"},
            ]
        )
        self.assertEqual([item["text"] for item in translated], ["Satu", "Dua"])
        self.assertEqual(client.post.call_count, 3)

    @patch("app.tasks.httpx.Client")
    def test_truncated_batch_falls_back_to_single_segments(self, factory):
        client = Mock()
        client.post.side_effect = [
            ollama_response("[1] Satu", done_reason="length"),
            ollama_response("Satu"),
            ollama_response("Dua"),
        ]
        factory.return_value.__enter__.return_value = client
        translated = translate_segments(
            [
                {"start": 0, "end": 1, "text": "One"},
                {"start": 1, "end": 2, "text": "Two"},
            ]
        )
        self.assertEqual([item["text"] for item in translated], ["Satu", "Dua"])
        self.assertEqual(client.post.call_count, 3)

    @patch("app.tasks.httpx.Client")
    def test_translation_resumes_from_a_checkpoint(self, factory):
        checkpoint = Path(self.directory.name) / "translations.json"
        checkpoint.write_text(
            json.dumps({"entries": [{"index": 0, "source": "One", "text": "Satu"}]}),
            encoding="utf-8",
        )
        client = Mock()
        client.post.return_value = ollama_response("Dua")
        factory.return_value.__enter__.return_value = client
        translated = translate_segments(
            [
                {"start": 0, "end": 1, "text": "One"},
                {"start": 1, "end": 2, "text": "Two"},
            ],
            checkpoint=checkpoint,
        )
        self.assertEqual([item["text"] for item in translated], ["Satu", "Dua"])
        self.assertEqual(client.post.call_count, 1)
        self.assertEqual(client.post.call_args.kwargs["json"]["prompt"], "Two")
        entries = json.loads(checkpoint.read_text(encoding="utf-8"))["entries"]
        self.assertEqual([entry["text"] for entry in entries], ["Satu", "Dua"])

    @patch("app.tasks.httpx.Client")
    def test_repeated_lines_are_translated_once(self, factory):
        client = Mock()
        client.post.return_value = ollama_response("Terima kasih")
        factory.return_value.__enter__.return_value = client
        translated = translate_segments(
            [
                {"start": 0, "end": 1, "text": "Thank you"},
                {"start": 1, "end": 2, "text": "Thank you"},
            ]
        )
        self.assertEqual([item["text"] for item in translated], ["Terima kasih", "Terima kasih"])
        self.assertEqual(client.post.call_count, 1)

    @patch("app.tasks.time.sleep")
    @patch("app.tasks.httpx.Client")
    def test_translation_retries_transport_errors(self, factory, sleep):
        client = Mock()
        client.post.side_effect = [
            httpx.ConnectError("offline", request=httpx.Request("POST", "http://localhost")),
            ollama_response("Halo"),
        ]
        factory.return_value.__enter__.return_value = client
        translated = translate_segments([{"start": 0, "end": 1, "text": "Hello"}])
        self.assertEqual(translated[0]["text"], "Halo")
        self.assertEqual(client.post.call_count, 2)
        sleep.assert_called_once()

    @patch("app.tasks.time.sleep")
    @patch("app.tasks.httpx.Client")
    def test_translation_reports_retry_exhaustion(self, factory, _sleep):
        client = Mock()
        client.post.side_effect = httpx.ConnectError(
            "offline", request=httpx.Request("POST", "http://localhost")
        )
        factory.return_value.__enter__.return_value = client
        with self.assertRaisesRegex(RuntimeError, "Ollama is not reachable"):
            translate_segments([{"start": 0, "end": 1, "text": "Hello"}])
        self.assertEqual(client.post.call_count, 3)

    def test_celery_allows_long_running_tasks(self):
        from app.celery_utils import celery_app

        self.assertGreater(celery_app.conf.broker_transport_options["visibility_timeout"], 3600)
        self.assertFalse(celery_app.conf.task_acks_late)
        self.assertIsNone(celery_app.conf.task_time_limit)

    def test_pipeline_pause_preserves_checkpoints_and_delete_cleans_up(self):
        from app import task_store

        task_id = str(uuid4())
        source = self.settings.uploads_dir / f"{task_id}.mp4"
        source.write_bytes(b"video")
        task_store.create_task(task_id, "clip.mp4", 5)

        def fake_ffmpeg(*arguments):
            Path(arguments[-1]).touch()

        def pause_during_translate(segments, on_progress=None, checkpoint=None, duration=None):
            task_store.update_task(task_id, status="PAUSED", progress=30, stage="paused")
            if on_progress is not None:
                on_progress(35, "translating")
            return segments

        with (
            patch("app.tasks.settings", self.settings),
            patch(
                "app.tasks.probe_media",
                return_value={
                    "format": {"duration": "2.0"},
                    "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                },
            ),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg),
            patch(
                "app.tasks.transcribe",
                return_value=[{"start": 0, "end": 1, "text": "Halo"}],
            ),
            patch("app.tasks.translate_segments", side_effect=pause_during_translate),
            patch.object(dub_video, "update_state"),
        ):
            paused_result = dub_video.run(task_id)

        self.assertEqual(paused_result["status"], "PAUSED")
        self.assertTrue(source.exists())
        self.assertTrue((self.settings.temp_dir / task_id / "segments.json").exists())
        self.assertEqual(task_store.get_task(task_id)["status"], "PAUSED")

        def delete_during_translate(segments, on_progress=None, checkpoint=None, duration=None):
            task_store.delete_task(task_id)
            if on_progress is not None:
                on_progress(40, "translating")
            return segments

        task_store.update_task(task_id, status="PENDING", stage="queued")
        with (
            patch("app.tasks.settings", self.settings),
            patch(
                "app.tasks.probe_media",
                return_value={
                    "format": {"duration": "2.0"},
                    "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                },
            ),
            patch("app.tasks.translate_segments", side_effect=delete_during_translate),
            patch.object(dub_video, "update_state"),
        ):
            deleted_result = dub_video.run(task_id)

        self.assertEqual(deleted_result["status"], "REVOKED")
        self.assertFalse(source.exists())
        self.assertFalse((self.settings.temp_dir / task_id).exists())
        self.assertIsNone(task_store.get_task(task_id))


if __name__ == "__main__":
    unittest.main()
