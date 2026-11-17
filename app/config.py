import sys
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def local_binary(name: str) -> str:
    filename = f"{name}.exe" if sys.platform == "win32" else name
    bundled = PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / filename
    return str(bundled) if bundled.is_file() else name


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYDUBBER_", env_file=PROJECT_ROOT / ".env", extra="ignore"
    )

    storage_dir: Path = PROJECT_ROOT / "storage"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_result_url: str = "redis://127.0.0.1:6379/1"
    ollama_url: str = "http://127.0.0.1:11434/api/generate"
    ollama_model: str = "llama3.2"
    whisper_model_dir: Path = PROJECT_ROOT / "models" / "whisper-base"
    piper_model_path: Path = PROJECT_ROOT / "models" / "piper" / "id_ID-news_tts-medium.onnx"
    cpu_threads: int = Field(default=4, ge=1, le=16)
    max_upload_mb: int = Field(default=4096, ge=1)
    max_media_hours: float = Field(default=6.0, gt=0)
    ollama_timeout: float = Field(default=300, gt=0)
    ffmpeg_timeout: float = Field(default=7200, gt=0)
    translation_batch_chars: int = Field(default=700, ge=0)
    translation_batch_segments: int = Field(default=8, ge=1)
    translation_retries: int = Field(default=3, ge=1)
    progress_min_interval: float = Field(default=5.0, ge=0)
    task_visibility_timeout: int = Field(default=43200, ge=60)
    result_expires: int = Field(default=86400, ge=60)
    ffmpeg_binary: str = Field(default_factory=lambda: local_binary("ffmpeg"))
    ffprobe_binary: str = Field(default_factory=lambda: local_binary("ffprobe"))
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("ollama_url", "redis_url", "redis_result_url")
    @classmethod
    def require_loopback(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Offline mode only allows services on a local loopback address.")
        if parsed.scheme not in {"http", "https", "redis", "rediss"}:
            raise ValueError("Unsupported service URL scheme.")
        return value

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def temp_dir(self) -> Path:
        return self.storage_dir / "temp"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_dir / "outputs"

    @property
    def tasks_dir(self) -> Path:
        return self.storage_dir / "tasks"

    def ensure_directories(self) -> None:
        for directory in (
            self.uploads_dir,
            self.temp_dir,
            self.outputs_dir,
            self.tasks_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
