"""Tests for :mod:`cdt.models`."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from cdt.models import (
    UsageSession,
    human_duration,
    new_session_id,
    parse_iso,
    to_iso,
    utcnow,
)


def make_session(**overrides):
    now = utcnow().replace(microsecond=0)
    defaults = dict(
        session_id=new_session_id(),
        package_name="google-chrome",
        app_name="Google Chrome",
        start=now - timedelta(seconds=120),
        end=now,
        duration_seconds=120,
        created_at=now,
    )
    defaults.update(overrides)
    return UsageSession(**defaults)


class HumanDurationTest(unittest.TestCase):
    def test_compact_format(self):
        self.assertEqual(human_duration(45), "45s")
        self.assertEqual(human_duration(90), "1m 30s")
        self.assertEqual(human_duration(3661), "1h 1m 1s")
        self.assertEqual(human_duration(0), "0s")
        self.assertEqual(human_duration(None), "-")


class SessionIdTest(unittest.TestCase):
    def test_guid_length(self):
        # the backend column is varchar(36)
        self.assertEqual(len(new_session_id()), 36)

    def test_unique(self):
        self.assertNotEqual(new_session_id(), new_session_id())


class IsoTest(unittest.TestCase):
    def test_round_trip(self):
        moment = datetime(2026, 10, 19, 12, 30, 15, 123456, tzinfo=timezone.utc)
        text = to_iso(moment)
        self.assertTrue(text.endswith("Z"))
        self.assertEqual(parse_iso(text), moment)

    def test_naive_is_treated_as_utc(self):
        moment = datetime(2026, 10, 19, 12, 0, 0)
        self.assertEqual(to_iso(moment), "2026-10-19T12:00:00Z")


class UsageSessionTest(unittest.TestCase):
    def test_payload_matches_backend_contract(self):
        session = make_session()
        payload = session.to_payload(created_at=utcnow())
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
        self.assertEqual(payload["packageName"], "google-chrome")
        self.assertEqual(payload["appName"], "Google Chrome")
        self.assertEqual(payload["durationSeconds"], 120)
        self.assertTrue(payload["startTimeUtc"].endswith("Z"))
        self.assertTrue(payload["endTimeUtc"].endswith("Z"))

    def test_validate_accepts_a_good_session(self):
        self.assertIsNone(make_session().validate())

    def test_validate_rejects_zero_duration(self):
        self.assertIn("greater than zero", make_session(duration_seconds=0).validate())

    def test_validate_rejects_reversed_interval(self):
        session = make_session()
        session.start, session.end = session.end, session.start
        self.assertIn("EndTimeUtc", session.validate())

    def test_validate_rejects_mismatched_duration(self):
        self.assertIn("must match", make_session(duration_seconds=900).validate())

    def test_validate_rejects_missing_package(self):
        self.assertIn("PackageName", make_session(package_name="").validate())

    def test_validate_rejects_long_session_id(self):
        self.assertIn(
            "36 characters", make_session(session_id="x" * 40).validate()
        )

    def test_clamp_to_past_fixes_future_timestamps(self):
        session = make_session()
        session.start = utcnow() + timedelta(minutes=5)
        session.end = session.start + timedelta(seconds=30)
        self.assertTrue(session.clamp_to_past())
        self.assertIsNone(session.validate())
        self.assertLessEqual(session.end, utcnow())


if __name__ == "__main__":
    unittest.main()
