"""Server-Sent Events for the local task dashboard.

A single background watcher polls the shared JSON task registry. The worker and
the API are separate processes, so polling the registry is more reliable than an
in-process queue: a worker restart cannot lose events, and a late subscriber
always receives a complete snapshot.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from starlette.requests import Request

from app import task_store

logger = logging.getLogger(__name__)

EVENT_POLL_SECONDS = 0.75
KEEPALIVE_SECONDS = 15.0
RETRY_MILLISECONDS = 3000
QUEUE_SIZE = 4


def format_sse(event: str, payload: Any, retry: int | None = None) -> str:
    lines: list[str] = []
    if retry is not None:
        lines.append(f"retry: {retry}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def snapshot_payload() -> dict:
    payload = task_store.snapshot()
    payload["server_time"] = task_store.iso_timestamp()
    return payload


class TaskEventBroker:
    def __init__(
        self,
        poll_interval: float = EVENT_POLL_SECONDS,
        keepalive: float = KEEPALIVE_SECONDS,
    ) -> None:
        self._poll_interval = poll_interval
        self._keepalive = keepalive
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._watcher: asyncio.Task | None = None
        self._signature: str | None = None

    def start(self) -> None:
        if self._watcher is None or self._watcher.done():
            self._watcher = asyncio.create_task(self._watch(), name="mydubber-events")

    async def stop(self) -> None:
        watcher = self._watcher
        self._watcher = None
        if watcher is None:
            return
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

    def subscribe(self) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        self._subscribers.discard(queue)

    def _broadcast(self, payload: dict) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def _watch(self) -> None:
        while True:
            try:
                payload = await asyncio.to_thread(snapshot_payload)
                tasks = payload.get("tasks", [])
                signature = json.dumps(tasks, sort_keys=True, ensure_ascii=False)
                if signature != self._signature:
                    self._signature = signature
                    self._broadcast(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Could not read task metadata for SSE", exc_info=True)
            await asyncio.sleep(self._poll_interval)

    async def stream(
        self,
        request: Request | None = None,
        refresh_interval: float | None = None,
    ) -> AsyncIterator[str]:
        queue = self.subscribe()
        timeout = (
            self._keepalive if refresh_interval is None else max(0.01, float(refresh_interval))
        )
        try:
            payload = await asyncio.to_thread(snapshot_payload)
            yield format_sse("tasks", payload, retry=RETRY_MILLISECONDS)
            while True:
                if request is not None and await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    if refresh_interval is not None:
                        payload = await asyncio.to_thread(snapshot_payload)
                        yield format_sse("tasks", payload)
                    else:
                        yield format_sse("ping", {"server_time": task_store.iso_timestamp()})
                else:
                    yield format_sse("tasks", payload)
        finally:
            self.unsubscribe(queue)


broker = TaskEventBroker()
