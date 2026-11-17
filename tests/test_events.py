import asyncio
import json
import unittest
from unittest.mock import patch

from app.events import TaskEventBroker, format_sse, snapshot_payload


class FormatTests(unittest.TestCase):
    def test_format_sse_has_retry_event_and_json_data(self):
        payload = format_sse("tasks", {"tasks": [], "active": 0}, retry=3000)
        self.assertTrue(payload.startswith("retry: 3000\n"))
        self.assertIn("event: tasks\n", payload)
        self.assertTrue(payload.endswith("\n\n"))
        data_line = next(line for line in payload.splitlines() if line.startswith("data: "))
        self.assertEqual(json.loads(data_line.removeprefix("data: "))["active"], 0)

    def test_snapshot_payload_adds_server_time(self):
        with patch("app.events.task_store.snapshot", return_value={"tasks": [], "active": 0}):
            payload = snapshot_payload()
        self.assertIn("server_time", payload)
        self.assertEqual(payload["tasks"], [])


class FakeRequest:
    def __init__(self, disconnect_after=0):
        self.disconnect_after = disconnect_after
        self.calls = 0

    async def is_disconnected(self):
        self.calls += 1
        return self.calls > self.disconnect_after


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_sends_an_initial_snapshot(self):
        with patch(
            "app.events.task_store.snapshot",
            return_value={"tasks": [{"task_id": "one"}], "active": 1},
        ):
            broker = TaskEventBroker(keepalive=5)
            stream = broker.stream(FakeRequest(disconnect_after=0))
            first = await anext(stream)
            await stream.aclose()
        self.assertIn("event: tasks", first)
        self.assertIn('"active":1', first)
        self.assertIn("retry: 3000", first)

    async def test_stream_emits_heartbeats_while_idle(self):
        with patch(
            "app.events.task_store.snapshot",
            return_value={"tasks": [], "active": 0},
        ):
            broker = TaskEventBroker(keepalive=0.01)
            stream = broker.stream(FakeRequest(disconnect_after=2))
            events = []
            async for event in stream:
                events.append(event)
        self.assertGreaterEqual(len(events), 3)
        self.assertIn("event: tasks", events[0])
        self.assertIn("event: ping", events[1])

    async def test_watcher_broadcasts_a_changed_snapshot(self):
        payload = {"tasks": [{"task_id": "one"}], "active": 1, "server_time": "now"}
        broker = TaskEventBroker(poll_interval=0.01, keepalive=5)
        queue = broker.subscribe()
        with patch("app.events.snapshot_payload", return_value=payload):
            broker.start()
            received = await asyncio.wait_for(queue.get(), timeout=1)
            await broker.stop()
        broker.unsubscribe(queue)
        self.assertEqual(received["tasks"][0]["task_id"], "one")

    async def test_watcher_stops_cleanly(self):
        broker = TaskEventBroker(poll_interval=0.01)
        with patch("app.events.snapshot_payload", return_value={"tasks": [], "active": 0}):
            broker.start()
            await asyncio.sleep(0.02)
            await broker.stop()
        self.assertIsNone(broker._watcher)
