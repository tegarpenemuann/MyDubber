import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi import Path as PathParameter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.celery_utils import celery_app
from app.config import PROJECT_ROOT, settings
from app.tasks import dub_video

logger = logging.getLogger(__name__)


class HealthCheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        arguments = record.args
        if isinstance(arguments, tuple) and len(arguments) == 5:
            _client, method, path, _version, response_status = arguments
            if method in {"GET", "HEAD"} and isinstance(path, str):
                return not (path.split("?", 1)[0] == "/health" and response_status == 404)
        return True


logging.getLogger("uvicorn.access").addFilter(HealthCheckAccessFilter())
settings.ensure_directories()
app = FastAPI(
    title="MyDubber API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    description=f"""
Backend for automatic MP4 dubbing into Bahasa Indonesia, processed asynchronously on the CPU.

## Try It Directly in Swagger

1. Make sure the local prerequisites are ready: Redis (`docker compose up -d`),
    Ollama with the `llama3.2` model (`ollama pull llama3.2`), the Celery worker,
    FFmpeg/FFprobe, the local Whisper base model, and the local Piper Indonesian
    voice. Verify everything at once with `python -m scripts.prepare_local`.
    All processing and Swagger assets run locally without internet.
2. Open **POST /api/v1/dubbing/tasks**, click **Try it out**, choose an MP4
    that contains speech, then click **Execute**. Current upload limit:
    **{settings.max_upload_mb} MiB**.
3. Copy the `task_id` from the **202** response. This means the task is queued,
    not that dubbing has finished.
4. Open **GET /api/v1/dubbing/tasks/{{task_id}}**, click **Try it out**, paste the
    `task_id`, then click **Execute**. Repeat every few seconds; Swagger does not
    poll automatically.
5. When `status` becomes **SUCCESS**, open `download_url` on the same API host,
    for example `/outputs/<task_id>.mp4`, to play or download the video.

## Status and Progress

| Status | Meaning |
| --- | --- |
| PENDING | An uploaded task is waiting for a worker |
| STARTED | A worker has started processing |
| PROGRESS | Milestone: 10 extract, 30 STT, 60 translate, 80 TTS, 100 merge |
| SUCCESS | The result is ready at `download_url` |
| FAILURE / REVOKED | Failed or cancelled; check the worker log |

Status metadata is kept for {settings.result_expires} seconds. If the task stays
PENDING, check the Celery worker. If it fails, check the worker log and the engine
prerequisites. The original audio is replaced, including background music.
Unknown or expired task IDs without local task files return HTTP 404. Always use
the task_id or status_url from your actual upload response, not an example ID.
This API is intended for local use and has no authentication.
""",
    openapi_tags=[
        {"name": "Dubbing", "description": "Upload a video and track the dubbing process."}
    ],
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "defaultModelsExpandDepth": -1,
        "validatorUrl": None,
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=str(settings.outputs_dir)), name="outputs")
app.mount(
    "/docs-assets",
    StaticFiles(directory=str(PROJECT_ROOT / "tools" / "swagger"), check_dir=False),
    name="docs-assets",
)


@app.get("/docs", include_in_schema=False)
def swagger_docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/docs-assets/swagger-ui-bundle.js",
        swagger_css_url="/docs-assets/swagger-ui.css",
        swagger_favicon_url="/docs-assets/favicon-32x32.png",
        swagger_ui_parameters=app.swagger_ui_parameters,
    )


class TaskCreated(BaseModel):
    task_id: str = Field(description="Task UUID. Copy it for polling.")
    status: str = Field(description="Initial queue status: PENDING.")
    status_url: str = Field(description="Relative path for checking task status.")


class TaskStatus(BaseModel):
    task_id: str = Field(description="The task UUID being checked.")
    status: str = Field(description="PENDING, STARTED, PROGRESS, SUCCESS, FAILURE, or REVOKED.")
    progress: int = Field(description="Milestone from 0 to 100, not a time estimate.")
    stage: str = Field(
        description=(
            "queued, processing, extracted, transcribed, translated, synthesized, "
            "completed, or failed."
        )
    )
    download_url: str | None = Field(
        default=None, description="Relative URL of the result video; available on SUCCESS."
    )
    error: str | None = Field(
        default=None, description="Generic failure message; details are in the worker log."
    )


class ErrorResponse(BaseModel):
    detail: str = Field(description="Explanation of the request or service error.")


@app.post(
    "/api/v1/dubbing/tasks",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Dubbing"],
    summary="Upload an MP4 and queue the dubbing job",
    description=(
        "Choose a .mp4 video in the file field. Video and audio stream validation "
        "happens inside the worker, so an invalid file can be accepted and then end "
        "in FAILURE. Use the task_id from the response for polling. Do not upload the "
        "file again just to check progress."
    ),
    responses={
        202: {
            "description": "The video was accepted and the task was queued.",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "c289faab-d38d-401f-9f22-9d028bbca925",
                        "status": "PENDING",
                        "status_url": "/api/v1/dubbing/tasks/c289faab-d38d-401f-9f22-9d028bbca925",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "The file is empty.",
            "content": {"application/json": {"example": {"detail": "The video file is empty."}}},
        },
        413: {"model": ErrorResponse, "description": "The file exceeds the upload limit."},
        415: {"model": ErrorResponse, "description": "The file extension is not .mp4."},
        503: {"model": ErrorResponse, "description": "The Redis queue is not available."},
    },
)
def create_dubbing_task(
    file: Annotated[
        UploadFile,
        File(
            description="MP4 video with speech to dub into Bahasa Indonesia.",
            json_schema_extra={"format": "binary"},
        ),
    ],
) -> TaskCreated:
    if Path(file.filename or "").suffix.lower() != ".mp4":
        file.file.close()
        raise HTTPException(status_code=415, detail="The upload must be an .mp4 video.")
    task_id = str(uuid4())
    destination = settings.uploads_dir / f"{task_id}.mp4"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        size = 0
        with destination.open("xb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413, detail="The video exceeds the upload limit."
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The video file is empty.")
        try:
            dub_video.apply_async(args=[task_id], task_id=task_id, retry=False)
        except Exception as exc:
            logger.exception("Could not enqueue task %s", task_id)
            raise HTTPException(
                status_code=503, detail="The Redis queue is not available."
            ) from exc
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()
    return TaskCreated(
        task_id=task_id, status="PENDING", status_url=f"/api/v1/dubbing/tasks/{task_id}"
    )


@app.get(
    "/api/v1/dubbing/tasks/{task_id}",
    tags=["Dubbing"],
    summary="Check task status and the result URL",
    description=(
        "Enter the task_id from POST. Click Execute again every few seconds until "
        "the status is SUCCESS or FAILURE. HTTP 200 means the status check worked, "
        "not that dubbing succeeded. An unknown UUID or expired metadata returns "
        "404 when no local task files remain. download_url is relative to the API host."
    ),
    responses={
        200: {
            "description": "The task status was read successfully.",
            "content": {
                "application/json": {
                    "examples": {
                        "pending": {
                            "summary": "Waiting for a worker",
                            "value": {
                                "task_id": "c289faab-d38d-401f-9f22-9d028bbca925",
                                "status": "PENDING",
                                "progress": 0,
                                "stage": "queued",
                                "download_url": None,
                                "error": None,
                            },
                        },
                        "progress": {
                            "summary": "Translation finished",
                            "value": {
                                "task_id": "c289faab-d38d-401f-9f22-9d028bbca925",
                                "status": "PROGRESS",
                                "progress": 60,
                                "stage": "translated",
                                "download_url": None,
                                "error": None,
                            },
                        },
                        "success": {
                            "summary": "Video is ready",
                            "value": {
                                "task_id": "c289faab-d38d-401f-9f22-9d028bbca925",
                                "status": "SUCCESS",
                                "progress": 100,
                                "stage": "completed",
                                "download_url": "/outputs/c289faab-d38d-401f-9f22-9d028bbca925.mp4",
                                "error": None,
                            },
                        },
                        "failure": {
                            "summary": "Dubbing failed",
                            "value": {
                                "task_id": "c289faab-d38d-401f-9f22-9d028bbca925",
                                "status": "FAILURE",
                                "progress": 0,
                                "stage": "failed",
                                "download_url": None,
                                "error": "Dubbing failed or was cancelled. Check the worker log for details.",
                            },
                        },
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "The task ID is unknown or has expired."},
        503: {"model": ErrorResponse, "description": "The Redis result backend is not available."},
    },
)
def get_dubbing_task(
    task_id: Annotated[
        UUID,
        PathParameter(
            description="Paste the task_id from your actual upload response, not an example ID.",
        ),
    ],
) -> TaskStatus:
    identifier = str(task_id)
    try:
        result = celery_app.AsyncResult(identifier)
        task_state = result.state
        info = result.info
    except Exception as exc:
        logger.exception("Could not poll task %s", identifier)
        raise HTTPException(
            status_code=503, detail="The Redis result backend is not available."
        ) from exc
    metadata = info if isinstance(info, dict) else {}
    if task_state == "PENDING" and not any(
        path.exists()
        for path in (
            settings.uploads_dir / f"{identifier}.mp4",
            settings.temp_dir / identifier,
            settings.outputs_dir / f"{identifier}.mp4",
        )
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Task not found or expired. Use the task_id or status_url from your "
                "actual upload response, not an example ID."
            ),
        )
    response = TaskStatus(task_id=identifier, status=task_state, progress=0, stage="queued")
    if task_state == "SUCCESS":
        response.progress = 100
        response.stage = "completed"
        response.download_url = metadata.get("download_url")
    elif task_state in {"FAILURE", "REVOKED"}:
        response.stage = "failed"
        response.error = "Dubbing failed or was cancelled. Check the worker log for details."
    elif task_state == "PROGRESS":
        response.progress = metadata.get("progress", 0)
        response.stage = metadata.get("stage", "processing")
    elif task_state == "STARTED":
        response.stage = "processing"
    return response
