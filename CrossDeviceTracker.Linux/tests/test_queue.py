"""Tests for :mod:`cdt.queue`."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from cdt.models import UsageSession, new_session_id, utcnow
from cdt.queue import PendingLogQueue, backoff_delay


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


class BackoffTest(unittest.TestCase):
    def test_growth_and_cap(self):
        self.assertEqual(backoff_delay(0, 15, 900), 15)
        self.assertEqual(backoff_delay(1, 15, 900), 15)
        self.assertEqual(backoff_delay(2, 15, 900), 30)
        self.assertEqual(backoff_delay(3, 15, 900), 60)
        self.assertEqual(backoff_delay(50, 15, 900), 900)


class PendingLogQueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "queue.db"
        self.queue = PendingLogQueue(self.db_path)
        self.addCleanup(self.queue.close)

    def test_add_and_due(self):
        session = make_session()
        self.assertTrue(self.queue.add(session))
        due = self.queue.due(limit=10)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].client_session_id, session.session_id)
        self.assertEqual(due[0].app_name, "Firefox")
        self.assertEqual(due[0].duration_seconds, 60)

    def test_duplicate_session_id_is_ignored(self):
        session = make_session()
        self.assertTrue(self.queue.add(session))
        self.assertFalse(self.queue.add(session))
        self.assertEqual(self.queue.stats()["pending"], 1)

    def test_invalid_sessions_are_rejected(self):
        self.assertFalse(self.queue.add(make_session(duration_seconds=0)))
        self.assertFalse(self.queue.add(make_session(package_name="")))
        self.assertEqual(self.queue.stats()["pending"], 0)

    def test_mark_sent_removes_entries(self):
        first, second = make_session(), make_session()
        self.queue.add_many([first, second])
        self.assertEqual(self.queue.mark_sent([first.session_id]), 1)
        self.assertEqual(self.queue.stats()["pending"], 1)
        self.assertIsNotNone(self.queue.stats()["lastSyncAt"])

    def test_mark_failure_schedules_a_retry(self):
        session = make_session()
        self.queue.add(session)
        self.queue.mark_failure([session.session_id], "boom", delay_seconds=600)
        self.assertEqual(self.queue.due(limit=10), [])
        entry = self.queue.peek()[0]
        self.assertEqual(entry.attempts, 1)
        self.assertEqual(entry.last_error, "boom")
        # ... and it becomes due again later
        self.assertEqual(len(self.queue.due(limit=10, now=utcnow() + timedelta(seconds=601))), 1)

    def test_quarantine_moves_entries_to_dead_letters(self):
        good, bad = make_session(), make_session()
        self.queue.add_many([good, bad])
        self.assertEqual(self.queue.quarantine([bad.session_id], "invalid"), 1)
        self.assertEqual(self.queue.stats()["pending"], 1)
        self.assertEqual(self.queue.stats()["deadLetters"], 1)
        dead = self.queue.dead_letters()
        self.assertEqual(dead[0]["reason"], "invalid")

    def test_clear(self):
        self.queue.add_many([make_session(), make_session()])
        self.assertEqual(self.queue.clear(), 2)
        self.assertEqual(self.queue.stats()["pending"], 0)

    def test_purge_dead_letters(self):
        session = make_session()
        self.queue.add(session)
        self.queue.quarantine([session.session_id], "invalid")
        self.assertEqual(self.queue.purge_dead_letters(older_than_days=0), 1)
        self.assertEqual(self.queue.stats()["deadLetters"], 0)

    def test_pending_seconds_are_summed(self):
        self.queue.add_many([make_session(seconds=60), make_session(seconds=120)])
        self.assertEqual(self.queue.stats()["pendingSeconds"], 180)

    def test_reopening_the_database_keeps_entries(self):
        session = make_session()
        self.queue.add(session)
        self.queue.close()
        reopened = PendingLogQueue(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.stats()["pending"], 1)


if __name__ == "__main__":
    unittest.main()
