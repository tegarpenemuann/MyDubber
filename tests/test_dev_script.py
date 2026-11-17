import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import dev


class DevScriptTests(unittest.TestCase):
    def test_read_env_file_handles_quotes_and_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# comment\n"
                "MYDUBBER_MAX_MEDIA_HOURS=6\n"
                "export MYDUBBER_OLLAMA_MODEL='llama3.2'\n"
                'MYDUBBER_CORS_ORIGINS=["http://localhost:3000"]\n',
                encoding="utf-8",
            )
            values = dev.read_env_file(path)
        self.assertEqual(values["MYDUBBER_MAX_MEDIA_HOURS"], "6")
        self.assertEqual(values["MYDUBBER_OLLAMA_MODEL"], "llama3.2")
        self.assertEqual(values["MYDUBBER_CORS_ORIGINS"], '["http://localhost:3000"]')

    def test_setting_prefers_process_environment(self):
        with (
            patch.dict("os.environ", {"MYDUBBER_OLLAMA_MODEL": "custom"}, clear=False),
            patch("scripts.dev.read_env_file", return_value={"MYDUBBER_OLLAMA_MODEL": "file"}),
        ):
            self.assertEqual(dev.setting("MYDUBBER_OLLAMA_MODEL", "default"), "custom")

    def test_storage_dir_resolves_relative_paths_from_project_root(self):
        with patch(
            "scripts.dev.setting",
            side_effect=lambda name, default: (
                "./local-storage" if name == "MYDUBBER_STORAGE_DIR" else default
            ),
        ):
            self.assertEqual(dev.storage_dir(), dev.PROJECT_ROOT / "local-storage")

    def test_pid_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.dev.run_dir", return_value=Path(directory)):
                dev.write_pid("api", 4321, ["python", "uvicorn"])
                payload = dev.read_pid("api")
                self.assertIsNotNone(payload)
                self.assertEqual(payload["pid"], 4321)
                self.assertEqual(payload["command"], ["python", "uvicorn"])
                dev.remove_pid("api")
                self.assertIsNone(dev.read_pid("api"))

    def test_stale_pid_is_removed_without_stopping_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            with (
                patch("scripts.dev.run_dir", return_value=run_dir),
                patch("scripts.dev.pid_alive", return_value=False),
                patch("scripts.dev.subprocess.run") as run,
                patch("builtins.print"),
            ):
                dev.write_pid("worker", 999999, ["python", "celery"])
                self.assertTrue(dev.stop_process("worker"))
                self.assertFalse(dev.pid_path("worker").exists())
            run.assert_not_called()

    def test_process_specs_use_the_platform_worker_pool(self):
        with (
            patch("scripts.dev.venv_python", return_value=Path("/venv/python")),
            patch("scripts.dev.os.name", "nt"),
        ):
            self.assertIn("--pool=solo", dev.process_specs(8000)["worker"])
        with (
            patch("scripts.dev.venv_python", return_value=Path("/venv/python")),
            patch("scripts.dev.os.name", "posix"),
        ):
            self.assertIn("--pool=prefork", dev.process_specs(8000)["worker"])

    def test_process_specs_require_a_virtual_environment(self):
        with patch("scripts.dev.venv_python", return_value=None):
            with self.assertRaisesRegex(dev.StartupError, "make setup"):
                dev.process_specs(8000)

    def test_process_port_reads_the_start_command(self):
        self.assertEqual(
            dev.process_port({"pid": 1, "command": ["python", "uvicorn", "--port", "8001"]}),
            8001,
        )
        self.assertIsNone(dev.process_port({"pid": 1, "command": ["python"]}))
        self.assertIsNone(dev.process_port(None))

    def test_read_last_lines_returns_the_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api.log"
            path.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
            self.assertEqual(dev.read_last_lines(path, 2), ["three", "four"])
            self.assertEqual(dev.read_last_lines(path, 0), [])
            self.assertEqual(dev.read_last_lines(path.with_name("missing.log"), 2), [])

    def test_request_stop_falls_back_when_windows_console_event_fails(self):
        with (
            patch("scripts.dev.os.name", "nt"),
            patch("scripts.dev.os.kill", side_effect=SystemError("boom")),
            patch("scripts.dev.subprocess.run") as run,
        ):
            dev.request_stop(4321)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][:3], ["taskkill", "/PID", "4321"])

    def test_model_available_accepts_a_tag(self):
        self.assertTrue(dev.model_available("llama3.2", {"llama3.2:latest"}))
        self.assertTrue(dev.model_available("llama3.2:latest", {"llama3.2"}))
        self.assertFalse(dev.model_available("llama3.1", {"llama3.2:latest"}))

    def test_redis_target_and_ollama_base_url_follow_settings(self):
        values = {
            "MYDUBBER_REDIS_URL": "redis://127.0.0.1:6380/0",
            "MYDUBBER_OLLAMA_URL": "http://localhost:11434/api/generate",
        }
        with patch(
            "scripts.dev.setting", side_effect=lambda name, default: values.get(name, default)
        ):
            self.assertEqual(dev.redis_target(), ("127.0.0.1", 6380))
            self.assertEqual(dev.ollama_base_url(), "http://localhost:11434")
