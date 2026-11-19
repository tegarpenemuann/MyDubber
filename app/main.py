import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi import Path as PathParameter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import task_store
from app.celery_utils import celery_app
from app.config import PROJECT_ROOT, settings
from app.events import broker
from app.tasks import check_ollama_available, dub_video

logger = logging.getLogger(__name__)
WEB_DIR = PROJECT_ROOT / "app" / "web"


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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task_store.recover_stale_tasks()
    task_store.prune_tasks()
    yield
    await broker.stop()


app = FastAPI(
    title="MyDubber API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    description=f"""
Local web app and backend for automatic MP4 dubbing into Bahasa Indonesia, processed asynchronously on the CPU.

## Web Dashboard

Open `/` in a browser for the dashboard. It supports drag-and-drop uploads,
live progress over Server-Sent Events (`GET /api/v1/dubbing/events`), persistent
history, play/download, and Indonesian or English themes. No build step or CDN is
involved; assets are served from `/assets`.

## Try It Directly in Swagger

1. Make sure the local prerequisites are ready: Redis (`docker compose up -d`),
    Ollama with the `llama3.2` model (`ollama pull llama3.2`), the Celery worker,
    FFmpeg/FFprobe, the local Whisper base model, and the local Piper Indonesian
    voice. Verify everything at once with `python -m scripts.prepare_local`.
    With GNU Make installed, `make up` starts Redis, the API, and the worker while
    keeping Ollama external; `make doctor` checks the prerequisites.
    All processing and Swagger assets run locally without internet.
2. Open **POST /api/v1/dubbing/tasks**, click **Try it out**, choose an MP4
    that contains speech, then click **Execute**. Current upload limit:
    **{settings.max_upload_mb} MiB** and current duration limit:
    **{settings.max_media_hours:g} hours**. Long videos such as a two-hour
    recording are supported, but they take a long time to process and need
    free disk space for the original video, the temporary timeline, and the
    result.
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
| PROGRESS | Milestone: 10 extract, 10-29 transcribe, 30-59 translate, 60-79 synthesize, 80 merge |
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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=str(settings.outputs_dir)), name="outputs")
app.mount(
    "/docs-assets",
    StaticFiles(directory=str(PROJECT_ROOT / "tools" / "swagger"), check_dir=False),
    name="docs-assets",
)
app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(
        WEB_DIR / "index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
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
    status: str = Field(
        description="PENDING, STARTED, PROGRESS, PAUSED, SUCCESS, FAILURE, or REVOKED."
    )
    progress: int = Field(description="Milestone from 0 to 100, not a time estimate.")
    stage: str = Field(
        description=(
            "queued, processing, extracted, transcribing, transcribed, translating, "
            "translated, synthesizing, synthesized, paused, completed, or failed."
        )
    )
    download_url: str | None = Field(
        default=None, description="Relative URL of the result video; available on SUCCESS."
    )
    error: str | None = Field(
        default=None, description="Generic failure message; details are in the worker log."
    )


class TaskDeletedResponse(BaseModel):
    task_id: str
    deleted: bool = True


class ErrorResponse(BaseModel):
    detail: str = Field(description="Explanation of the request or service error.")


class TaskSummary(BaseModel):
    task_id: str
    filename: str
    size_bytes: int
    created_at: str
    updated_at: str
    status: str
    progress: int
    stage: str
    download_url: str | None = None
    error: str | None = None


class TaskList(BaseModel):
    tasks: list[TaskSummary]
    active: int
    server_time: str


class DubbingConfig(BaseModel):
    max_upload_mb: int
    max_media_hours: float
    accepted_format: str = ".mp4"


@app.get(
    "/api/v1/dubbing/config",
    tags=["Dubbing"],
    summary="Read the upload limits used by the dashboard",
)
def read_dubbing_config() -> DubbingConfig:
    return DubbingConfig(
        max_upload_mb=settings.max_upload_mb,
        max_media_hours=settings.max_media_hours,
    )


@app.get(
    "/api/v1/dubbing/tasks",
    tags=["Dubbing"],
    summary="List recent tasks for the dashboard",
    description=(
        "Returns persisted task metadata, active tasks first. The dashboard uses "
        "this for its initial render and to resynchronize after a reconnect."
    ),
)
def list_dubbing_tasks(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> TaskList:
    tasks = task_store.list_tasks(limit)
    return TaskList(
        tasks=[TaskSummary(**task) for task in tasks],
        active=sum(1 for task in tasks if task.get("status") in task_store.ACTIVE_STATUSES),
        server_time=task_store.iso_timestamp(),
    )


@app.get("/api/v1/dubbing/events", include_in_schema=False)
async def stream_dubbing_events(
    request: Request,
    interval: Annotated[float | None, Query(ge=1, le=3600)] = None,
) -> StreamingResponse:
    broker.start()
    return StreamingResponse(
        broker.stream(request, refresh_interval=interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
        503: {
            "model": ErrorResponse,
            "description": "Ollama or the Redis queue is not available.",
        },
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
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if file.size is not None:
        if file.size > max_bytes:
            file.file.close()
            raise HTTPException(status_code=413, detail="The video exceeds the upload limit.")
        if file.size == 0:
            file.file.close()
            raise HTTPException(status_code=400, detail="The video file is empty.")
    ready, message = check_ollama_available()
    if not ready:
        file.file.close()
        raise HTTPException(status_code=503, detail=message)
    task_id = str(uuid4())
    destination = settings.uploads_dir / f"{task_id}.mp4"
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
        task_store.create_task(task_id, file.filename, size)
        try:
            dub_video.apply_async(args=[task_id], task_id=task_id, retry=False)
        except Exception as exc:
            logger.exception("Could not enqueue task %s", task_id)
            task_store.delete_task(task_id)
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


def _requeue_task(identifier: str) -> TaskCreated:
    if (settings.outputs_dir / f"{identifier}.mp4").is_file():
        raise HTTPException(status_code=409, detail="The dubbing task has already completed.")
    source = settings.uploads_dir / f"{identifier}.mp4"
    if not source.is_file():
        raise HTTPException(
            status_code=404,
            detail="The uploaded video is no longer available to retry. Upload it again.",
        )
    ready, message = check_ollama_available()
    if not ready:
        raise HTTPException(status_code=503, detail=message)
    record = task_store.get_task(identifier)
    previous_status = record.get("status", "FAILURE") if record else "FAILURE"
    previous_stage = record.get("stage", "failed") if record else "failed"
    previous_error = record.get("error") if record else None
    previous_celery_id = (record or {}).get("celery_task_id", identifier)
    # Celery keeps revoked task ids in worker memory. Requeue under a fresh id so
    # a pause/delete followed by resume/retry is not silently discarded.
    celery_id = f"{identifier}-{uuid4().hex}"
    if record is None:
        created = task_store.create_task(identifier, source.name, source.stat().st_size)
        task_store.update_task(identifier, celery_task_id=celery_id)
        previous_celery_id = created.get("celery_task_id", identifier)
    else:
        task_store.update_task(
            identifier, status="PENDING", stage="queued", error=None, celery_task_id=celery_id
        )
    try:
        dub_video.apply_async(args=[identifier], task_id=celery_id, retry=False)
    except Exception as exc:
        logger.exception("Could not requeue task %s", identifier)
        task_store.update_task(
            identifier,
            status=previous_status,
            stage=previous_stage,
            error=previous_error,
            celery_task_id=previous_celery_id,
        )
        raise HTTPException(status_code=503, detail="The Redis queue is not available.") from exc
    return TaskCreated(
        task_id=identifier, status="PENDING", status_url=f"/api/v1/dubbing/tasks/{identifier}"
    )


@app.post(
    "/api/v1/dubbing/tasks/{task_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Dubbing"],
    summary="Requeue a failed or interrupted dubbing task from its checkpoints",
    responses={
        202: {"description": "The task was requeued."},
        404: {"model": ErrorResponse, "description": "The uploaded video is no longer available."},
        409: {"model": ErrorResponse, "description": "The task is already finished."},
        503: {"model": ErrorResponse, "description": "The Redis queue is not available."},
    },
)
def retry_dubbing_task(
    task_id: Annotated[
        UUID,
        PathParameter(description="The task_id to requeue."),
    ],
) -> TaskCreated:
    return _requeue_task(str(task_id))


@app.post(
    "/api/v1/dubbing/tasks/{task_id}/pause",
    tags=["Dubbing"],
    summary="Pause an active or queued dubbing task while keeping checkpoints",
    responses={
        200: {"description": "The task was paused."},
        404: {"model": ErrorResponse, "description": "The task was not found."},
        409: {"model": ErrorResponse, "description": "The task has already finished."},
    },
)
def pause_dubbing_task(
    task_id: Annotated[
        UUID,
        PathParameter(description="The task_id to pause."),
    ],
) -> TaskStatus:
    identifier = str(task_id)
    record = task_store.get_task(identifier)
    source = settings.uploads_dir / f"{identifier}.mp4"
    output = settings.outputs_dir / f"{identifier}.mp4"
    if output.is_file() or (
        record is not None and record.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}
    ):
        raise HTTPException(status_code=409, detail="The dubbing task has already finished.")
    if record is None and not source.is_file():
        raise HTTPException(status_code=404, detail="Task not found.")
    celery_id = (record or {}).get("celery_task_id", identifier)
    try:
        celery_app.control.revoke(celery_id)
    except Exception:
        logger.warning("Could not revoke queued task %s during pause", identifier, exc_info=True)
    if record is None:
        record = task_store.create_task(identifier, source.name, source.stat().st_size)
    updated = task_store.update_task(identifier, status="PAUSED", stage="paused", error=None)
    progress = int((updated or record).get("progress", 0))
    return TaskStatus(task_id=identifier, status="PAUSED", progress=progress, stage="paused")


@app.post(
    "/api/v1/dubbing/tasks/{task_id}/resume",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Dubbing"],
    summary="Resume a paused dubbing task from its saved checkpoints",
    responses={
        202: {"description": "The task was requeued to resume."},
        404: {"model": ErrorResponse, "description": "The uploaded video is no longer available."},
        409: {"model": ErrorResponse, "description": "The task is already finished."},
        503: {"model": ErrorResponse, "description": "The Redis queue is not available."},
    },
)
def resume_dubbing_task(
    task_id: Annotated[
        UUID,
        PathParameter(description="The task_id to resume."),
    ],
) -> TaskCreated:
    return _requeue_task(str(task_id))


@app.delete(
    "/api/v1/dubbing/tasks/{task_id}",
    tags=["Dubbing"],
    summary="Delete a dubbing task and all of its local files",
    responses={
        200: {"description": "The task and its files were deleted."},
        404: {"model": ErrorResponse, "description": "The task was not found."},
    },
)
def delete_dubbing_task(
    task_id: Annotated[
        UUID,
        PathParameter(description="The task_id to delete."),
    ],
) -> TaskDeletedResponse:
    identifier = str(task_id)
    record = task_store.get_task(identifier)
    source = settings.uploads_dir / f"{identifier}.mp4"
    work_dir = settings.temp_dir / identifier
    output = settings.outputs_dir / f"{identifier}.mp4"
    if record is None and not any(path.exists() for path in (source, work_dir, output)):
        raise HTTPException(status_code=404, detail="Task not found.")
    celery_id = (record or {}).get("celery_task_id", identifier)
    try:
        celery_app.control.revoke(celery_id)
    except Exception:
        logger.warning("Could not revoke task %s during delete", identifier, exc_info=True)
    task_store.delete_task(identifier)
    source.unlink(missing_ok=True)
    output.unlink(missing_ok=True)
    shutil.rmtree(work_dir, ignore_errors=True)
    return TaskDeletedResponse(task_id=identifier, deleted=True)


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
    record = task_store.get_task(identifier)
    celery_id = (record or {}).get("celery_task_id", identifier)
    try:
        result = celery_app.AsyncResult(celery_id)
        task_state = result.state
        info = result.info
    except Exception as exc:
        logger.exception("Could not poll task %s", identifier)
        raise HTTPException(
            status_code=503, detail="The Redis result backend is not available."
        ) from exc
    metadata = info if isinstance(info, dict) else {}
    if (record is not None and record.get("status") == "PAUSED") or task_state == "PAUSED":
        progress = int(record.get("progress", 0)) if record else int(metadata.get("progress", 0))
        return TaskStatus(task_id=identifier, status="PAUSED", progress=progress, stage="paused")
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
