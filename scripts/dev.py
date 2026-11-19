"""Developer helper for running the local MyDubber stack.

The API and worker run natively so they can reach the host Ollama instance
directly. Redis runs through Docker Compose. Ollama is always external and is
never started or stopped by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "storage"
DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_API_PORT = 8000
API_READY_TIMEOUT = 30.0
WORKER_READY_TIMEOUT = 45.0
REDIS_READY_TIMEOUT = 30.0
STOP_TIMEOUT = 15.0
WINDOWS_STOP_TIMEOUT = 2.0
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_POLL_SECONDS = 0.5
STILL_ACTIVE = 259

# Ignore proxy environment variables for local health checks, like the app does.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class StartupError(RuntimeError):
    """The stack could not be started."""


def read_env_file(path: Path | None = None) -> dict[str, str]:
    path = PROJECT_ROOT / ".env" if path is None else path
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def setting(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    return read_env_file().get(name, default)


def storage_dir() -> Path:
    path = Path(setting("MYDUBBER_STORAGE_DIR", str(DEFAULT_STORAGE_DIR))).expanduser()
    if not path.is_absolute():
        # The API and worker are started with the project root as their working
        # directory, so resolve relative storage paths the same way.
        path = PROJECT_ROOT / path
    return path


def run_dir() -> Path:
    return storage_dir() / "run"


def log_dir() -> Path:
    return storage_dir() / "logs"


def pid_path(name: str) -> Path:
    return run_dir() / f"{name}.pid"


def log_path(name: str) -> Path:
    return log_dir() / f"{name}.log"


def venv_python() -> Path | None:
    for candidate in (
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return candidate
    return None


def process_specs(port: int) -> dict[str, list[str]]:
    python = venv_python()
    if python is None:
        raise StartupError("The virtual environment is missing. Run: make setup")
    pool = "solo" if os.name == "nt" else "prefork"
    return {
        "api": [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        "worker": [
            str(python),
            "-m",
            "celery",
            "-A",
            "app.celery_utils:celery_app",
            "worker",
            "--loglevel=info",
            f"--pool={pool}",
            "--concurrency=1",
        ],
    }


def write_pid(name: str, pid: int, command: list[str]) -> None:
    path = pid_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid,
        "started": time.time(),
        "command": [str(part) for part in command],
    }
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def read_pid(name: str) -> dict | None:
    path = pid_path(name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(payload, int):
        payload = {"pid": payload}
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    return payload


def remove_pid(name: str) -> None:
    try:
        pid_path(name).unlink(missing_ok=True)
    except OSError:
        pass


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def looks_like_python(pid: int) -> bool:
    """Avoid stopping an unrelated process when a PID has been reused."""
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return True
        if result.returncode != 0:
            return True
        return "python" in result.stdout.casefold()
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return True
    return b"python" in command.casefold()


def process_payload(name: str) -> dict | None:
    payload = read_pid(name)
    if payload is None:
        return None
    pid = payload["pid"]
    if not pid_alive(pid) or not looks_like_python(pid):
        remove_pid(name)
        return None
    return payload


def process_port(payload: dict | None) -> int | None:
    if payload is None:
        return None
    command = payload.get("command")
    if not isinstance(command, list) or "--port" not in command:
        return None
    try:
        return int(command[command.index("--port") + 1])
    except (IndexError, TypeError, ValueError):
        return None


def rotate_log(path: Path, max_bytes: int = MAX_LOG_BYTES) -> None:
    try:
        if path.is_file() and path.stat().st_size > max_bytes:
            backup = path.with_name(f"{path.name}.1")
            backup.unlink(missing_ok=True)
            path.replace(backup)
    except OSError:
        pass


def start_process(name: str, command: list[str]) -> tuple[subprocess.Popen, int]:
    path = log_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(path)
    offset = path.stat().st_size if path.is_file() else 0
    environment = os.environ.copy()
    environment.setdefault("PYTHONUNBUFFERED", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    options: dict = {
        "cwd": str(PROJECT_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": path.open("ab"),
        "stderr": subprocess.STDOUT,
        "env": environment,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **options)
    finally:
        options["stdout"].close()
    write_pid(name, process.pid, command)
    return process, offset


def wait_for_http(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with OPENER.open(url, timeout=2) as response:
                if 200 <= response.status < 300:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(0.25)
    return False


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with OPENER.open(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def tcp_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if tcp_reachable(host, port):
            return True
        time.sleep(0.25)
    return False


def redis_target() -> tuple[str, int]:
    parsed = urlparse(setting("MYDUBBER_REDIS_URL", DEFAULT_REDIS_URL))
    return parsed.hostname or "127.0.0.1", parsed.port or 6379


def ollama_base_url() -> str:
    parsed = urlparse(setting("MYDUBBER_OLLAMA_URL", DEFAULT_OLLAMA_URL))
    if not parsed.scheme or not parsed.netloc:
        return "http://127.0.0.1:11434"
    return f"{parsed.scheme}://{parsed.netloc}"


def ollama_model() -> str:
    return setting("MYDUBBER_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


def ollama_models() -> tuple[bool, set[str]]:
    try:
        with OPENER.open(f"{ollama_base_url()}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, ValueError):
        return False, set()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return True, set()
    names = {
        str(item.get("name")) for item in models if isinstance(item, dict) and item.get("name")
    }
    return True, names


def model_available(model: str, names: set[str]) -> bool:
    wanted = model.split(":", 1)[0]
    return any(name.split(":", 1)[0] == wanted for name in names)


def resolve_binary(name: str) -> str | None:
    setting_name = f"MYDUBBER_{name.upper()}_BINARY"
    configured = setting(setting_name, "")
    if configured:
        return configured
    executable = f"{name}.exe" if os.name == "nt" else name
    bundled = PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / executable
    if bundled.is_file():
        return str(bundled)
    return shutil.which(name)


def command_result(
    command: list[str], timeout: float = 15.0
) -> tuple[subprocess.CompletedProcess | None, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    detail = (result.stderr or result.stdout or "").strip()
    return result, detail


def docker_available() -> tuple[bool, str]:
    result, detail = command_result(["docker", "info"])
    if result is None:
        return False, "The Docker CLI is not available."
    if result.returncode != 0:
        return False, detail or "The Docker daemon is not running."
    return True, ""


def compose(*arguments: str, timeout: float = 120.0) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["docker", "compose", *arguments],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def compose_detail(result: subprocess.CompletedProcess | None) -> str:
    if result is None:
        return "Docker Compose could not be executed."
    return (result.stderr or result.stdout or "").strip() or "Unknown Docker Compose error."


def ffmpeg_available() -> tuple[bool, str]:
    for name in ("ffmpeg", "ffprobe"):
        binary = resolve_binary(name)
        if binary is None:
            return False, f"{name} was not found on PATH or in tools/ffmpeg/bin."
        result, detail = command_result([binary, "-version"], timeout=10)
        if result is None or result.returncode != 0:
            return False, f"{name} could not run: {detail}"
    return True, ""


def required_assets() -> list[str]:
    missing: list[str] = []
    whisper = Path(
        setting("MYDUBBER_WHISPER_MODEL_DIR", str(PROJECT_ROOT / "models" / "whisper-base"))
    )
    if not (whisper / "model.bin").is_file():
        missing.append(f"Whisper model ({whisper})")
    piper = Path(
        setting(
            "MYDUBBER_PIPER_MODEL_PATH",
            str(PROJECT_ROOT / "models" / "piper" / "id_ID-news_tts-medium.onnx"),
        )
    )
    if not piper.is_file() or not Path(f"{piper}.json").is_file():
        missing.append(f"Piper voice ({piper})")
    return missing


def missing_swagger_assets() -> list[str]:
    swagger = PROJECT_ROOT / "tools" / "swagger"
    return [
        str(swagger / filename)
        for filename in ("swagger-ui-bundle.js", "swagger-ui.css")
        if not (swagger / filename).is_file()
    ]


def ensure_redis() -> bool:
    host, port = redis_target()
    if tcp_reachable(host, port):
        print(f"Redis is reachable at {host}:{port}.")
        return True
    available, detail = docker_available()
    if not available:
        print(f"Redis is not reachable at {host}:{port}.")
        print(f"Docker is not ready: {detail}")
        print("Start Docker Desktop and retry, or run Redis outside Docker.")
        return False
    print("Starting Redis...")
    result = compose("up", "-d", "redis")
    if result is None or result.returncode != 0:
        print(f"Could not start Redis: {compose_detail(result)}")
        return False
    if not wait_for_port(host, port, REDIS_READY_TIMEOUT):
        print(f"Redis did not become ready at {host}:{port} within {REDIS_READY_TIMEOUT:g}s.")
        return False
    print("Redis is ready.")
    return True


def read_last_lines(path: Path, count: int) -> list[str]:
    if count <= 0 or not path.is_file():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            data = b""
            block = 4096
            while size > 0 and data.count(b"\n") <= count:
                read_size = min(block, size)
                size -= read_size
                handle.seek(size)
                data = handle.read(read_size) + data
    except OSError:
        return []
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()[-count:]


def print_tail(name: str, count: int = 30) -> None:
    path = log_path(name)
    recent = read_last_lines(path, count)
    if not recent:
        return
    print(f"--- last {len(recent)} lines of {path} ---")
    for line in recent:
        print(line)


def wait_for_log_marker(
    path: Path,
    marker: str,
    offset: int,
    timeout: float,
    process: subprocess.Popen | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                content = handle.read()
        except OSError:
            content = ""
        if marker in content:
            return True
        time.sleep(0.25)
    return False


def warn_active_work() -> None:
    temp = storage_dir() / "temp"
    try:
        active = any(entry.is_dir() for entry in temp.iterdir())
    except OSError:
        active = False
    if active:
        print(
            "Warning: work directories exist. Stopping now interrupts a running dub; "
            "the upload and JSON checkpoints are kept for a requeue."
        )


def signal_process(pid: int, sig: int) -> None:
    if os.name == "nt":
        return
    try:
        group = os.getpgid(pid)
        if group == pid:
            os.killpg(group, sig)
        else:
            os.kill(pid, sig)
    except ProcessLookupError:
        pass


def request_stop(pid: int) -> None:
    if os.name == "nt":
        # CTRL_BREAK_EVENT gives Python processes a graceful shutdown; taskkill
        # without /F does not reach console processes. Force later if needed.
        try:
            os.kill(pid, signal.CTRL_BREAK_EVENT)
            return
        except (OSError, ValueError, SystemError):
            # Detached processes without a console cannot receive console
            # events; fall through to taskkill and the forced stop below.
            pass
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        return
    signal_process(pid, signal.SIGTERM)


def stop_process(name: str, timeout: float | None = None) -> bool:
    if timeout is None:
        timeout = WINDOWS_STOP_TIMEOUT if os.name == "nt" else STOP_TIMEOUT
    payload = process_payload(name)
    if payload is None:
        print(f"{name}: already stopped.")
        return True
    pid = payload["pid"]
    print(f"Stopping {name} (pid {pid})...")
    request_stop(pid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            break
        time.sleep(0.2)
    if pid_alive(pid):
        print(f"{name} did not stop; forcing.")
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                errors="replace",
            )
        else:
            signal_process(pid, signal.SIGKILL)
        for _ in range(10):
            if not pid_alive(pid):
                break
            time.sleep(0.2)
    remove_pid(name)
    if pid_alive(pid):
        print(f"{name}: process {pid} is still alive.")
        return False
    print(f"{name}: stopped.")
    return True


def stop_all() -> bool:
    running = any(process_payload(name) is not None for name in ("api", "worker"))
    if running:
        warn_active_work()
    results = [stop_process(name) for name in ("worker", "api")]
    return all(results)


def check_ollama() -> None:
    reachable, names = ollama_models()
    if not reachable:
        print(f"\nWarning: Ollama is not reachable at {ollama_base_url()}.")
        print("Start the Ollama app, or run: ollama serve")
        return
    model = ollama_model()
    if not model_available(model, names):
        print(f"\nWarning: the Ollama model '{model}' is not available.")
        print(f"Pull it with: ollama pull {model}")


def wait_for_ollama(timeout: float = 30.0) -> bool:
    """Give a starting Ollama app time to become reachable before uploads begin."""
    deadline = time.monotonic() + timeout
    while True:
        reachable, names = ollama_models()
        if reachable and model_available(ollama_model(), names):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(2.0)


def up(port: int) -> int:
    python = venv_python()
    if python is None:
        print("The virtual environment is missing. Run: make setup")
        return 1
    if not (PROJECT_ROOT / ".env").is_file():
        print("The .env file is missing. Run: make setup")
        return 1
    missing = required_assets()
    if missing:
        print("Local assets are missing:")
        for asset in missing:
            print(f"  - {asset}")
        print("Run: make setup")
        return 1
    swagger_missing = missing_swagger_assets()
    if swagger_missing:
        print("Warning: Swagger UI assets are missing; /docs may be blank.")
        for asset in swagger_missing:
            print(f"  - {asset}")
        print("Run: make setup to download them.")
    ffmpeg_ready, detail = ffmpeg_available()
    if not ffmpeg_ready:
        print(detail)
        return 1
    if not ensure_redis():
        return 1
    wait_for_ollama()

    specs = process_specs(port)
    started: list[str] = []
    try:
        api_payload = process_payload("api")
        if api_payload is not None:
            running_port = process_port(api_payload)
            if running_port not in {None, port}:
                print(
                    f"The API is already running on port {running_port}. "
                    "Run make stop first, or use make up PORT=..."
                )
                return 1
            print(f"API is already running (pid {api_payload['pid']}).")
        else:
            if tcp_reachable("127.0.0.1", port):
                print(
                    f"Port {port} is already in use by another process. "
                    "Stop it, or run make up PORT=8001."
                )
                return 1
            process, _offset = start_process("api", specs["api"])
            started.append("api")
            print(f"Starting API (pid {process.pid})...")
            if not wait_for_http(f"http://127.0.0.1:{port}/openapi.json", API_READY_TIMEOUT):
                raise StartupError(f"The API did not become ready within {API_READY_TIMEOUT:g}s.")

        worker_payload = process_payload("worker")
        if worker_payload is not None:
            print(f"Worker is already running (pid {worker_payload['pid']}).")
        else:
            process, offset = start_process("worker", specs["worker"])
            started.append("worker")
            print(f"Starting worker (pid {process.pid})...")
            if not wait_for_log_marker(
                log_path("worker"),
                "ready.",
                offset,
                WORKER_READY_TIMEOUT,
                process,
            ):
                raise StartupError(
                    f"The worker did not become ready within {WORKER_READY_TIMEOUT:g}s."
                )
    except StartupError as exc:
        print(f"\n{exc}")
        for name in reversed(started):
            print_tail(name)
        for name in reversed(started):
            stop_process(name)
        return 1

    check_ollama()
    print("\nMyDubber is running.")
    print(f"  Swagger: http://127.0.0.1:{port}/docs")
    print(f"  API:     http://127.0.0.1:{port}/openapi.json")
    print(f"  Logs:    {log_dir()} (make logs)")
    print("  Stop:    make down")
    return 0


def down() -> int:
    stopped = stop_all()
    result = compose("down")
    if result is None or result.returncode != 0:
        print(f"Warning: Redis was not stopped via Docker Compose: {compose_detail(result)}")
        print("If Redis runs outside Docker, stop it manually.")
    else:
        print("Redis stopped. The redis_data volume is preserved.")
    return 0 if stopped else 1


def restart(port: int) -> int:
    down()
    return up(port)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def describe_process(name: str) -> tuple[bool, str]:
    payload = process_payload(name)
    if payload is None:
        return False, "not running"
    started = payload.get("started")
    age = time.time() - started if isinstance(started, (int, float)) else 0.0
    return True, f"running (pid {payload['pid']}, up {format_duration(age)})"


def status(port: int) -> int:
    api_running, api_text = describe_process("api")
    worker_running, worker_text = describe_process("worker")
    api_http = http_ok(f"http://127.0.0.1:{port}/openapi.json")
    host, redis_port = redis_target()
    redis_ready = tcp_reachable(host, redis_port)
    ollama_ready, names = ollama_models()
    model = ollama_model()

    print(
        f"API      {api_text}; HTTP {'ready' if api_http else 'not ready'} at http://127.0.0.1:{port}"
    )
    print(f"Worker   {worker_text}")
    print(f"Redis    {'reachable' if redis_ready else 'not reachable'} at {host}:{redis_port}")
    if ollama_ready:
        availability = "available" if model_available(model, names) else "missing"
        print(f"Ollama   reachable at {ollama_base_url()}; model {model} {availability}")
    else:
        print(f"Ollama   not reachable at {ollama_base_url()}")
    if not (api_running and api_http and worker_running):
        print("\nThe stack is not fully running. Start it with: make up")
    return 0


def doctor(port: int) -> int:
    failures = 0
    warnings = 0

    def report(
        label: str, ok: bool, detail: str = "", fix: str = "", required: bool = True
    ) -> None:
        nonlocal failures, warnings
        if ok:
            print(f"[ OK ] {label}{': ' + detail if detail else ''}")
            return
        status_text = "FAIL" if required else "WARN"
        if required:
            failures += 1
        else:
            warnings += 1
        print(f"[{status_text}] {label}: {detail}")
        if fix:
            print(f"       {fix}")

    report(
        "Python",
        sys.version_info >= (3, 10),
        sys.version.split()[0],
        "Install Python 3.10 or newer.",
    )
    python = venv_python()
    report(
        "Virtual environment",
        python is not None,
        str(python) if python else "not found",
        "Run: make setup",
    )
    env_file = PROJECT_ROOT / ".env"
    report("Configuration", env_file.is_file(), str(env_file), "Run: make setup")

    if python is not None:
        result, detail = command_result(
            [
                str(python),
                "-c",
                "import fastapi, celery, faster_whisper, piper, httpx, numpy",
            ],
            timeout=60,
        )
        report(
            "Python dependencies",
            result is not None and result.returncode == 0,
            "" if result is not None and result.returncode == 0 else detail,
            "Run: make setup",
        )

    missing = required_assets()
    report(
        "Local assets",
        not missing,
        "" if not missing else ", ".join(missing),
        "Run: make setup",
    )
    ffmpeg_ready, ffmpeg_detail = ffmpeg_available()
    report(
        "FFmpeg and FFprobe",
        ffmpeg_ready,
        "" if ffmpeg_ready else ffmpeg_detail,
        "Install FFmpeg or run: make setup",
    )
    swagger_missing = missing_swagger_assets()
    report(
        "Swagger UI assets",
        not swagger_missing,
        "" if not swagger_missing else ", ".join(swagger_missing),
        "Run: make setup to download the local Swagger files.",
        required=False,
    )

    docker_ready, docker_detail = docker_available()
    report(
        "Docker",
        docker_ready,
        "" if docker_ready else docker_detail,
        "Start Docker Desktop. Redis is needed for the queue.",
        required=False,
    )
    host, redis_port = redis_target()
    redis_ready = tcp_reachable(host, redis_port)
    report(
        "Redis",
        redis_ready,
        f"reachable at {host}:{redis_port}"
        if redis_ready
        else f"not reachable at {host}:{redis_port}",
        "Run: make up (it starts Redis through Docker Compose).",
        required=False,
    )
    ollama_ready, names = ollama_models()
    report(
        "Ollama",
        ollama_ready,
        f"reachable at {ollama_base_url()}"
        if ollama_ready
        else f"not reachable at {ollama_base_url()}",
        "Start the Ollama app, or run: ollama serve",
        required=False,
    )
    model = ollama_model()
    report(
        f"Ollama model {model}",
        ollama_ready and model_available(model, names),
        "available" if ollama_ready and model_available(model, names) else "not found",
        f"Run: ollama pull {model}",
        required=False,
    )

    api_payload = process_payload("api")
    if api_payload is not None:
        report(
            "API port", True, f"managed API is running on port {process_port(api_payload) or port}"
        )
    elif tcp_reachable("127.0.0.1", port):
        report(
            "API port",
            False,
            f"port {port} is in use by another process",
            "Stop that process, or run make up PORT=8001.",
            required=False,
        )
    else:
        report("API port", True, f"port {port} is free")

    if failures:
        print(f"\n{failures} required check(s) failed. Fix the [FAIL] items, then retry.")
        return 1
    if warnings:
        print("\nLocal files are ready. Address the [WARN] items, then run: make up")
        return 0
    print("\nAll checks passed. Start the stack with: make up")
    return 0


def create_environment() -> None:
    venv = PROJECT_ROOT / ".venv"
    if venv_python() is None:
        print("Creating .venv...", flush=True)
        result = subprocess.run([sys.executable, "-m", "venv", str(venv)], cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            raise SystemExit("Could not create .venv.")
    python = venv_python()
    if python is None:
        raise SystemExit("The virtual environment is not usable.")
    requirements = (
        PROJECT_ROOT / "requirements-dev.txt"
        if (PROJECT_ROOT / "requirements-dev.txt").is_file()
        else PROJECT_ROOT / "requirements.txt"
    )
    print(f"Installing dependencies from {requirements.name}...", flush=True)
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(requirements)],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise SystemExit("Dependency installation failed.")
    env_file = PROJECT_ROOT / ".env"
    example = PROJECT_ROOT / ".env.example"
    if not env_file.is_file() and example.is_file():
        shutil.copyfile(example, env_file)
        print("Created .env from .env.example.", flush=True)
    print("Downloading local models and tools...", flush=True)
    result = subprocess.run(
        [
            str(python),
            "-m",
            "scripts.prepare_local",
            "--download",
            "--skip-services",
        ],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise SystemExit("Asset preparation failed.")
    print("\nSetup complete. Start the stack with: make up")


def tail_logs(component: str, lines: int, follow: bool) -> int:
    names = ["api", "worker"] if component == "all" else [component]
    paths = {name: log_path(name) for name in names}
    existing = {name: path for name, path in paths.items() if path.is_file()}
    if not existing:
        print("No log files yet. Start the stack with: make up")
        return 1
    handles: dict[str, object] = {}
    for name, path in existing.items():
        prefix = f"[{name}] " if len(paths) > 1 else ""
        for line in read_last_lines(path, lines):
            print(f"{prefix}{line}")
        handle = path.open("r", encoding="utf-8", errors="replace")
        handle.seek(0, os.SEEK_END)
        handles[name] = handle
    if not follow:
        for handle in handles.values():
            handle.close()
        return 0
    print(f"Following {', '.join(existing)}. Press Ctrl+C to stop following.")
    try:
        while True:
            for name, handle in handles.items():
                chunk = handle.read()
                if not chunk:
                    continue
                prefix = f"[{name}] " if len(paths) > 1 else ""
                for line in chunk.splitlines(keepends=True):
                    print(f"{prefix}{line}", end="")
            time.sleep(LOG_POLL_SECONDS)
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        for handle in handles.values():
            handle.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and inspect the local MyDubber stack. Ollama is always external."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("setup", help="Create the virtual environment, .env, and local assets")
    for name, help_text in (
        ("up", "Start Redis, the API, and the worker"),
        ("restart", "Restart the stack"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    subparsers.add_parser("stop", help="Stop the API and worker, keeping Redis running")
    subparsers.add_parser("down", help="Stop the API, the worker, and Redis")
    status_parser = subparsers.add_parser("status", help="Show stack status")
    status_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    doctor_parser = subparsers.add_parser("doctor", help="Check prerequisites and local assets")
    doctor_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    logs_parser = subparsers.add_parser("logs", help="Show and follow API and worker logs")
    logs_parser.add_argument(
        "component", nargs="?", choices=["all", "api", "worker"], default="all"
    )
    logs_parser.add_argument("--lines", type=int, default=50)
    logs_parser.add_argument("--no-follow", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "setup":
        create_environment()
        return 0
    if arguments.command == "up":
        return up(arguments.port)
    if arguments.command == "restart":
        return restart(arguments.port)
    if arguments.command == "stop":
        return 0 if stop_all() else 1
    if arguments.command == "down":
        return down()
    if arguments.command == "status":
        return status(arguments.port)
    if arguments.command == "doctor":
        return doctor(arguments.port)
    if arguments.command == "logs":
        return tail_logs(arguments.component, arguments.lines, not arguments.no_follow)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
