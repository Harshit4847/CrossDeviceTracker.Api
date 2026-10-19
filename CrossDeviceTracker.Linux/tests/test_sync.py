"""Tests for :mod:`cdt.sync`."""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from cdt.api import ApiClient, ApiError
from cdt.models import UsageSession, new_session_id, utcnow
from cdt.queue import PendingLogQueue
from cdt.sync import AuthRequiredError, SyncEngine, SyncLoop


class FakeApi(ApiClient):
    """Scriptable stand-in for the real HTTP client."""

    def __init__(self, script: Optional[Sequence[str]] = None) -> None:
        super().__init__("http://stub")
        self.script: List[str] = list(script or [])
        self.batches: List[List[Dict[str, Any]]] = []
        self.singles: List[Dict[str, Any]] = []

    def _next(self) -> str:
        return self.script.pop(0) if self.script else "ok"

    def create_time_logs_batch(self, token: str, entries: Sequence[Dict[str, Any]]):
        self.batches.append([dict(entry) for entry in entries])
        outcome = self._next()
        if outcome == "ok":
            return [str(entry["clientSessionId"]) for entry in entries]
        if outcome == "auth":
            raise ApiError("invalid token", status=401)
        if outcome == "forbidden":
            raise ApiError("device revoked", status=403)
        if outcome == "validation":
            raise ApiError("DurationSeconds must be greater than zero", status=400)
        if outcome == "server":
            raise ApiError("An unexpected error occurred", status=500)
        raise ApiError("cannot reach the backend", status=0)

    def create_time_log(self, token: str, entry: Dict[str, Any]):
        self.singles.append(dict(entry))
        outcome = self._next()
        if outcome == "ok":
            return {"id": new_session_id()}
        if outcome == "auth":
            raise ApiError("invalid token", status=401)
        if outcome == "validation":
            raise ApiError("DurationSeconds must be greater than zero", status=400)
        if outcome == "server":
            raise ApiError("An unexpected error occurred", status=500)
        raise ApiError("cannot reach the backend", status=0)


def make_session(seconds: int = 60, **overrides) -> UsageSession:
    now = utcnow().replace(microsecond=0)
    defaults = dict(
        session_id=new_session_id(),
        package_name="firefox",
        app_name="Firefox",
        start=now - timedelta(seconds=seconds),
        end=now,
        duration_seconds=seconds,
        created_at=now,
    )
    defaults.update(overrides)
    return UsageSession(**defaults)


class SyncEngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = PendingLogQueue(Path(self.tmp.name) / "queue.db")
        self.addCleanup(self.queue.close)

    def engine(self, api: FakeApi) -> SyncEngine:
        return SyncEngine(
            api=api,
            queue=self.queue,
            token_provider=lambda: "device-jwt",
            batch_size=50,
            retry_base_seconds=15,
            retry_max_seconds=900,
        )

    def test_successful_batch_empties_the_queue(self):
        api = FakeApi(["ok"])
        sessions = [make_session(), make_session()]
        self.queue.add_many(sessions)

        result = self.engine(api).sync_once()

        self.assertEqual(result.accepted, 2)
        self.assertIsNone(result.error)
        self.assertEqual(self.queue.stats()["pending"], 0)
        self.assertEqual(len(api.batches), 1)
        self.assertEqual(len(api.batches[0]), 2)
        # the payload uses the backend's camelCase contract
        payload = api.batches[0][0]
        self.assertEqual(
            sorted(payload),
            sorted(
                [
                    "packageName",
                    "appName",
                    "startTimeUtc",
                    "endTimeUtc",
                    "durationSeconds",
                    "createdAtUtc",
                    "clientSessionId",
                ]
            ),
        )

    def test_nothing_to_do_is_a_noop(self):
        api = FakeApi()
        result = self.engine(api).sync_once()
        self.assertEqual(result.sent, 0)
        self.assertEqual(api.batches, [])

    def test_auth_error_keeps_the_queue_and_flags_it(self):
        api = FakeApi(["auth"])
        self.queue.add(make_session())
        result = self.engine(api).sync_once()
        self.assertTrue(result.auth_error)
        self.assertEqual(self.queue.stats()["pending"], 1)

    def test_validation_error_falls_back_to_single_uploads(self):
        good, bad = make_session(), make_session(duration_seconds=0)
        # the invalid one never even reaches the queue
        self.queue.add(good)
        self.assertFalse(self.queue.add(bad))

        api = FakeApi(["validation", "ok"])
        result = self.engine(api).sync_once()

        self.assertEqual(result.accepted, 1)
        self.assertEqual(self.queue.stats()["pending"], 0)
        self.assertEqual(len(api.batches), 1)
        self.assertEqual(len(api.singles), 1)

    def test_single_upload_validation_failure_is_quarantined(self):
        self.queue.add(make_session())
        api = FakeApi(["validation", "validation"])
        result = self.engine(api).sync_once()
        self.assertEqual(result.dropped, 1)
        self.assertEqual(self.queue.stats()["pending"], 0)
        self.assertEqual(self.queue.stats()["deadLetters"], 1)

    def test_server_error_retries_later(self):
        self.queue.add(make_session())
        api = FakeApi(["server"])
        result = self.engine(api).sync_once()
        self.assertEqual(result.retried, 1)
        self.assertEqual(self.queue.stats()["pending"], 1)
        self.assertEqual(self.queue.due(limit=10), [])  # not due yet
        self.assertEqual(
            len(self.queue.due(limit=10, now=utcnow() + timedelta(seconds=900))), 1
        )

    def test_network_error_retries_later(self):
        self.queue.add(make_session())
        api = FakeApi(["network"])
        result = self.engine(api).sync_once()
        self.assertEqual(result.retried, 1)
        self.assertIn("cannot reach", result.error or "")
        self.assertEqual(self.queue.stats()["pending"], 1)

    def test_missing_token_is_an_auth_error(self):
        self.queue.add(make_session())
        engine = SyncEngine(
            api=FakeApi(), queue=self.queue, token_provider=lambda: "", batch_size=10
        )
        result = engine.sync_once()
        self.assertTrue(result.auth_error)
        self.assertEqual(self.queue.stats()["pending"], 1)

    def test_token_provider_failure_is_reported(self):
        def boom() -> str:
            raise AuthRequiredError("not linked")

        self.queue.add(make_session())
        engine = SyncEngine(api=FakeApi(), queue=self.queue, token_provider=boom)
        result = engine.sync_once()
        self.assertTrue(result.auth_error)
        self.assertIn("not linked", result.error or "")

    def test_only_the_batch_size_is_sent(self):
        for _ in range(5):
            self.queue.add(make_session())
        api = FakeApi(["ok"])
        engine = SyncEngine(
            api=api, queue=self.queue, token_provider=lambda: "jwt", batch_size=2
        )
        engine.sync_once()
        self.assertEqual(len(api.batches[0]), 2)
        self.assertEqual(self.queue.stats()["pending"], 3)

    def test_future_timestamps_are_clamped_before_sending(self):
        session = make_session()
        session.start = utcnow() + timedelta(minutes=10)
        session.end = session.start + timedelta(seconds=60)
        self.queue.add(session)
        api = FakeApi(["ok"])
        self.engine(api).sync_once()
        sent = api.batches[0][0]
        self.assertTrue(sent["startTimeUtc"] < sent["endTimeUtc"])
        self.assertLessEqual(sent["endTimeUtc"], utcnow().isoformat().replace("+00:00", "Z"))


class SyncLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = PendingLogQueue(Path(self.tmp.name) / "queue.db")
        self.addCleanup(self.queue.close)

    def test_loop_uploads_periodically(self):
        self.queue.add(make_session())
        api = FakeApi(["ok", "ok", "ok", "ok"])
        engine = SyncEngine(
            api=api, queue=self.queue, token_provider=lambda: "jwt", batch_size=10
        )
        loop = SyncLoop(engine, interval_seconds=1)
        loop.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and self.queue.stats()["pending"]:
                time.sleep(0.1)
        finally:
            loop.stop(timeout=5)
        self.assertEqual(self.queue.stats()["pending"], 0)
        self.assertGreaterEqual(len(api.batches), 1)

    def test_sync_now_uploads_immediately(self):
        self.queue.add(make_session())
        api = FakeApi(["ok"])
        engine = SyncEngine(
            api=api, queue=self.queue, token_provider=lambda: "jwt", batch_size=10
        )
        loop = SyncLoop(engine, interval_seconds=3600)
        result = loop.sync_now()
        self.assertEqual(result.accepted, 1)
        loop.stop()


if __name__ == "__main__":
    unittest.main()
