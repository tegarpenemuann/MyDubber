import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app import task_store
from app.config import Settings


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(storage_dir=Path(self.directory.name))
        self.settings.ensure_directories()
        self.patch = patch("app.task_store.settings", self.settings)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def _record(self, status="PROGRESS", updated_at=None, task_id=None):
        identifier = task_id or str(uuid4())
        task_store.create_task(identifier, "clip.mp4", 2048)
        record = task_store.get_task(identifier)
        record["status"] = status
        record["updated_at"] = updated_at or task_store.iso_timestamp()
        task_store._write(record)
        return record

    def test_create_and_read_task(self):
        task_id = str(uuid4())
        task_store.create_task(task_id, "../../clip.mp4", 2048)
        record = task_store.get_task(task_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["filename"], "clip.mp4")
        self.assertEqual(record["size_bytes"], 2048)
        self.assertEqual(record["status"], "PENDING")
        self.assertEqual(record["stage"], "queued")

    def test_update_merges_progress_and_keeps_creation_time(self):
        task_id = str(uuid4())
        created = task_store.create_task(task_id, "clip.mp4", 10)
        updated = task_store.update_task(
            task_id,
            status="PROGRESS",
            progress=42,
            stage="translating",
        )
        self.assertEqual(updated["created_at"], created["created_at"])
        self.assertEqual(updated["progress"], 42)
        self.assertEqual(updated["stage"], "translating")
        self.assertEqual(task_store.get_task(task_id)["status"], "PROGRESS")

    def test_progress_is_clamped(self):
        task_id = str(uuid4())
        task_store.create_task(task_id, "clip.mp4", 10)
        task_store.update_task(task_id, progress=250)
        self.assertEqual(task_store.get_task(task_id)["progress"], 100)
        task_store.update_task(task_id, progress=-5)
        self.assertEqual(task_store.get_task(task_id)["progress"], 0)

    def test_invalid_json_and_unknown_fields_are_ignored(self):
        task_id = str(uuid4())
        task_store.create_task(task_id, "clip.mp4", 10)
        (self.settings.tasks_dir / "broken.json").write_text("{not json", encoding="utf-8")
        (self.settings.tasks_dir / "other.json").write_text(
            json.dumps({"task_id": "not-a-uuid"}), encoding="utf-8"
        )
        task_store.update_task(task_id, status="SUCCESS", ignored="value")
        tasks = task_store.all_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], task_id)
        self.assertNotIn("ignored", tasks[0])

    def test_list_orders_active_before_finished_and_newest_finished_first(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        new = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        active = self._record(status="PROGRESS", updated_at=new)
        finished_old = self._record(status="SUCCESS", updated_at=old)
        finished_new = self._record(status="FAILURE", updated_at=new)
        tasks = task_store.list_tasks()
        self.assertEqual(tasks[0]["task_id"], active["task_id"])
        self.assertEqual(tasks[1]["task_id"], finished_new["task_id"])
        self.assertEqual(tasks[2]["task_id"], finished_old["task_id"])

    def test_prune_removes_expired_failures_but_keeps_results(self):
        failed = self._record(
            status="FAILURE",
            updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        success = self._record(
            status="SUCCESS",
            updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        (self.settings.outputs_dir / f"{success['task_id']}.mp4").touch()
        task_store.prune_tasks(max_age_seconds=60)
        self.assertIsNone(task_store.get_task(failed["task_id"]))
        self.assertIsNotNone(task_store.get_task(success["task_id"]))

    def test_prune_removes_orphaned_active_tasks(self):
        orphan = self._record(
            status="PROGRESS",
            updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        resumable = self._record(
            status="PROGRESS",
            updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        (self.settings.uploads_dir / f"{resumable['task_id']}.mp4").touch()
        task_store.prune_tasks(max_age_seconds=60)
        self.assertIsNone(task_store.get_task(orphan["task_id"]))
        self.assertIsNotNone(task_store.get_task(resumable["task_id"]))

    def test_history_limit_keeps_the_newest_terminal_records(self):
        for _ in range(3):
            self._record(status="FAILURE")
        task_store.prune_tasks(max_age_seconds=86400, history_limit=2)
        self.assertEqual(len(task_store.all_tasks()), 2)

    def test_snapshot_reports_active_count(self):
        self._record(status="PROGRESS")
        self._record(status="SUCCESS")
        payload = task_store.snapshot()
        self.assertEqual(payload["active"], 1)
        self.assertEqual(len(payload["tasks"]), 2)

    def test_prune_keeps_paused_tasks_with_artifacts_and_drops_orphaned_ones(self):
        orphan = self._record(
            status="PAUSED",
            updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        resumable = self._record(
            status="PAUSED",
            updated_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        (self.settings.uploads_dir / f"{resumable['task_id']}.mp4").touch()
        task_store.prune_tasks(max_age_seconds=60)
        self.assertIsNone(task_store.get_task(orphan["task_id"]))
        self.assertIsNotNone(task_store.get_task(resumable["task_id"]))

    def test_recover_stale_tasks_fails_only_stalled_active_tasks(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        stalled = self._record(status="PROGRESS", updated_at=old)
        stalled_start = self._record(status="STARTED", updated_at=old)
        fresh = self._record(status="PROGRESS")
        queued = self._record(status="PENDING", updated_at=old)
        paused = self._record(status="PAUSED", updated_at=old)

        recovered = task_store.recover_stale_tasks(max_age_seconds=60)

        self.assertEqual(set(recovered), {stalled["task_id"], stalled_start["task_id"]})
        for identifier in recovered:
            record = task_store.get_task(identifier)
            self.assertEqual(record["status"], "FAILURE")
            self.assertEqual(record["stage"], "failed")
            self.assertIn("resume", record["error"])
        self.assertEqual(task_store.get_task(fresh["task_id"])["status"], "PROGRESS")
        self.assertEqual(task_store.get_task(queued["task_id"])["status"], "PENDING")
        self.assertEqual(task_store.get_task(paused["task_id"])["status"], "PAUSED")
