import json
import logging
import socket
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import HealthCheckAccessFilter, app
from app.tasks import (
    dub_video,
    ffmpeg,
    piper_voice,
    probe_media,
    run_process,
    synthesize,
    tempo_filter,
    translate_segments,
    whisper_model,
    write_silence,
)
from scripts.prepare_local import download


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
        self.client = TestClient(app)

    @patch("app.main.dub_video.apply_async")
    def test_upload_enqueues_with_server_generated_path(self, enqueue):
        response = self.client.post(
            "/api/v1/dubbing/tasks", files={"file": ("../../video.mp4", b"video", "video/mp4")}
        )
        self.assertEqual(response.status_code, 202)
        task_id = response.json()["task_id"]
        self.assertEqual((self.settings.uploads_dir / f"{task_id}.mp4").read_bytes(), b"video")
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
        def fake_ffmpeg(*arguments):
            destination = Path(arguments[-1])
            if destination.suffix == ".wav":
                with wave.open(str(destination), "wb") as audio:
                    audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                    audio.writeframes(b"\x01\x00" * 8000)
            else:
                destination.write_bytes(b"mp3")

        with (
            patch("app.tasks.synthesize_speech") as speech,
            patch("app.tasks.media_duration", return_value=2),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg) as media,
        ):
            speech.side_effect = lambda text, path: path.touch()
            output = synthesize(
                [{"start": 1, "end": 2, "text": "Halo"}], 3, Path(self.directory.name)
            )
        self.assertTrue(output.exists())
        with wave.open(str(Path(self.directory.name) / "timeline.wav"), "rb") as timeline:
            self.assertEqual(timeline.getnframes(), 48000)
            self.assertEqual(timeline.readframes(16000), b"\x00\x00" * 16000)
            self.assertEqual(timeline.readframes(1), b"\x01\x00")
        self.assertIn("atempo=2.00000000", media.call_args_list[0].args[4])

    def test_tempo_and_chunked_silence(self):
        self.assertEqual(tempo_filter(8), "atempo=2,atempo=2,atempo=2.00000000")
        audio = Mock()
        write_silence(audio, 32001)
        self.assertEqual(
            sum(len(call.args[0]) for call in audio.writeframesraw.call_args_list), 64002
        )

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
                return_value={"streams": [{"codec_type": "video"}, {"codec_type": "audio"}]},
            ),
            patch("app.tasks.media_duration", return_value=2),
            patch("app.tasks.ffmpeg", side_effect=fake_ffmpeg) as media,
            patch("app.tasks.transcribe", return_value=segments),
            patch("app.tasks.translate_segments", return_value=segments),
            patch("app.tasks.synthesize", return_value=Path(self.directory.name) / "dubbing.mp3"),
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


if __name__ == "__main__":
    unittest.main()
