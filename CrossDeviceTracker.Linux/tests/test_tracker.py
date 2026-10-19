"""Tests for :mod:`cdt.tracker` - the core usage tracking logic."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from cdt.idle import ScriptedIdleSource
from cdt.models import WindowInfo
from cdt.queue import PendingLogQueue
from cdt.tracker import TrackerOptions, UsageTracker
from cdt.window import ScriptedWindowSource

BASE = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)


def at(seconds: float) -> datetime:
    return BASE + timedelta(seconds=seconds)


class TrackerFixture(unittest.TestCase):
    def build(
        self,
        windows: Sequence[Optional[WindowInfo]],
        idle: Sequence[int] = (0,),
        **options,
    ) -> UsageTracker:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        queue = PendingLogQueue(Path(self.tmp.name) / "queue.db")
        self.addCleanup(queue.close)
        self.queue = queue
        tracker = UsageTracker(
            window_source=ScriptedWindowSource(windows),
            idle_source=ScriptedIdleSource(list(idle)),
            queue=queue,
            options=TrackerOptions(**options),
        )
        self.addCleanup(tracker.close)
        return tracker

    def entries(self):
        return self.queue.peek(limit=100)

    def durations(self) -> List[int]:
        return [entry.duration_seconds for entry in self.entries()]

    def app_names(self) -> List[str]:
        return [entry.app_name for entry in self.entries()]


CHROME = WindowInfo("google-chrome", "Google Chrome", "Gmail", 1001)
CODE = WindowInfo("code", "Visual Studio Code", "cli.py", 1002)
TERMINAL = WindowInfo("org.gnome.Terminal", "Terminal", "bash", 1003)


class AppSwitchTest(TrackerFixture):
    def test_a_session_is_queued_when_the_app_switches(self):
        tracker = self.build([CHROME] * 3 + [CODE], min_session_seconds=2)
        for second in (0, 1, 2, 3):
            tracker.tick(now=at(second))
        self.assertEqual(self.app_names(), ["Google Chrome"])
        self.assertEqual(self.durations(), [3])

    def test_short_sessions_are_discarded(self):
        tracker = self.build([CHROME, CODE], min_session_seconds=5)
        tracker.tick(now=at(0))
        tracker.tick(now=at(1))  # only 1s of Chrome
        self.assertEqual(self.entries(), [])

    def test_closing_flushes_the_running_session(self):
        tracker = self.build([CHROME] * 4, min_session_seconds=1)
        for second in (0, 1, 2, 3):
            tracker.tick(now=at(second))
        tracker.close()
        self.assertEqual(self.app_names(), ["Google Chrome"])
        # the tracker only records up to the last confirmed observation
        self.assertEqual(self.durations(), [3])

    def test_no_window_means_no_session(self):
        tracker = self.build([None, None], min_session_seconds=1)
        tracker.tick(now=at(0))
        tracker.tick(now=at(1))
        self.assertEqual(self.entries(), [])

    def test_switching_back_and_forth_creates_two_sessions(self):
        tracker = self.build([CHROME, CODE, CHROME] * 2, min_session_seconds=1)
        for second in (0, 10, 20):
            tracker.tick(now=at(second))
        tracker.close()
        self.assertEqual(self.app_names(), ["Google Chrome", "Visual Studio Code"])
        self.assertEqual(self.durations(), [10, 10])

    def test_package_name_is_the_machine_identifier(self):
        tracker = self.build([TERMINAL] * 2, min_session_seconds=1)
        tracker.tick(now=at(0))
        tracker.tick(now=at(5))
        tracker.close()
        entry = self.entries()[0]
        self.assertEqual(entry.package_name, "org.gnome.Terminal")
        self.assertEqual(entry.app_name, "Terminal")


class IdleTest(TrackerFixture):
    def test_idle_closes_the_session_at_the_last_input(self):
        tracker = self.build(
            [CHROME] * 4,
            idle=[0, 0, 0, 70_000],
            idle_threshold_seconds=60,
            min_session_seconds=1,
            poll_interval_seconds=60,
        )
        for second in (0, 60, 120):
            tracker.tick(now=at(second))
        tracker.tick(now=at(180))  # 70s idle -> session ended at 110s
        self.assertEqual(self.durations(), [110])

    def test_activity_resume_starts_a_new_session(self):
        tracker = self.build(
            [CHROME] * 6,
            idle=[0, 70_000, 0, 0, 0, 0],
            idle_threshold_seconds=60,
            min_session_seconds=1,
            poll_interval_seconds=60,
        )
        for second in (0, 60, 120, 180, 240, 300):
            tracker.tick(now=at(second))
        tracker.close()
        # first session: 0 -> 60-70 <0 -> dropped; second session: 120 -> 300
        self.assertEqual(self.durations(), [180])

    def test_idle_below_threshold_keeps_the_session_open(self):
        tracker = self.build(
            [CHROME] * 4,
            idle=[0, 30_000, 0],
            idle_threshold_seconds=60,
            min_session_seconds=1,
            poll_interval_seconds=30,
        )
        for second in (0, 30, 60, 90):
            tracker.tick(now=at(second))
        tracker.close()
        self.assertEqual(self.durations(), [90])


class LongSessionTest(TrackerFixture):
    def test_long_sessions_are_flushed_in_segments(self):
        tracker = self.build(
            [CHROME] * 13,
            max_session_seconds=30,
            min_session_seconds=1,
            poll_interval_seconds=10,
        )
        for step in range(13):
            tracker.tick(now=at(step * 10))
        tracker.close()
        self.assertEqual(self.durations(), [30, 30, 30, 30])

    def test_chunking_survives_a_minimum_above_the_maximum(self):
        # A nonsensical config (min > max) must hang the tracker, not loop.
        tracker = self.build(
            [CHROME] * 3,
            max_session_seconds=30,
            min_session_seconds=600,
            poll_interval_seconds=10,
        )
        for second in (0, 10, 20):
            tracker.tick(now=at(second))
        tracker.close()
        # every chunk is below the minimum, so nothing is recorded
        self.assertEqual(self.entries(), [])

    def test_each_segment_has_its_own_session_id(self):
        tracker = self.build(
            [CHROME] * 7,
            max_session_seconds=30,
            min_session_seconds=1,
            poll_interval_seconds=10,
        )
        for step in range(7):
            tracker.tick(now=at(step * 10))
        tracker.close()
        ids = {entry.client_session_id for entry in self.entries()}
        self.assertEqual(len(ids), len(self.entries()))
        for entry in self.entries():
            self.assertEqual(len(entry.client_session_id), 36)


class FilterTest(TrackerFixture):
    def test_include_list_only_tracks_listed_apps(self):
        tracker = self.build(
            [CHROME, CODE, CODE, CODE],
            include_apps=["code"],
            min_session_seconds=1,
            poll_interval_seconds=10,
        )
        tracker.tick(now=at(0))
        tracker.tick(now=at(10))
        tracker.tick(now=at(20))
        tracker.close()
        self.assertEqual(self.app_names(), ["Visual Studio Code"])

    def test_exclude_list_drops_apps(self):
        tracker = self.build(
            [CHROME, CODE, CODE, CODE],
            exclude_apps=["chrome"],
            min_session_seconds=1,
            poll_interval_seconds=10,
        )
        tracker.tick(now=at(0))
        tracker.tick(now=at(10))
        tracker.tick(now=at(20))
        tracker.close()
        self.assertEqual(self.app_names(), ["Visual Studio Code"])
        self.assertEqual(self.durations(), [10])

    def test_a_suspend_gap_is_not_recorded_as_usage(self):
        # A suspended laptop looks like a one hour jump between two polls.
        tracker = self.build([CHROME] * 2, min_session_seconds=1, poll_interval_seconds=1.0)
        tracker.tick(now=at(0))
        tracker.tick(now=at(3600))
        tracker.close()
        # only the single confirmed second before the suspend is kept
        self.assertEqual(self.durations(), [1])

    def test_polls_within_the_gap_threshold_are_recorded_normally(self):
        tracker = self.build(
            [CHROME] * 3,
            min_session_seconds=1,
            poll_interval_seconds=1.0,
            gap_threshold_seconds=3600,
            max_session_seconds=7200,
        )
        for second in (0, 1800, 3600):
            tracker.tick(now=at(second))
        tracker.close()
        self.assertEqual(self.durations(), [3600])

    def test_filtered_app_closes_the_previous_session(self):
        tracker = self.build(
            [CHROME, CODE, CHROME] * 2,
            include_apps=["code"],
            min_session_seconds=1,
            poll_interval_seconds=10,
        )
        tracker.tick(now=at(0))
        tracker.tick(now=at(10))  # code starts being tracked
        tracker.tick(now=at(20))  # chrome is not in the allow-list -> close
        tracker.close()
        self.assertEqual(self.app_names(), ["Visual Studio Code"])
        self.assertEqual(self.durations(), [10])


class DescribeTest(TrackerFixture):
    def test_describe_reports_state(self):
        tracker = self.build([CHROME] * 2, min_session_seconds=1, poll_interval_seconds=10)
        tracker.tick(now=at(0))
        tracker.tick(now=at(30))
        described = tracker.describe()
        self.assertEqual(described["currentApp"], "Google Chrome")
        self.assertEqual(described["windowSource"], "scripted")
        self.assertEqual(described["currentSessionSeconds"], 30)
        self.assertEqual(described["stats"]["polls"], 2)
        self.assertFalse(described["idle"])

    def test_tick_survives_a_broken_window_source(self):
        class Broken:
            name = "broken"

            def get_active_window(self):
                raise RuntimeError("display gone")

        tracker = self.build([CHROME], min_session_seconds=1)
        tracker.window_source = Broken()
        tracker.tick(now=at(0))
        self.assertIn("display gone", tracker.stats.last_error or "")


if __name__ == "__main__":
    unittest.main()
