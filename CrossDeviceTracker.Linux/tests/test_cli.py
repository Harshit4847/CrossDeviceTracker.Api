"""End-to-end tests for the command line interface.

These drive the real CLI against the in-process stub backend: link, track,
queue, sync, report.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from cdt.cli import main

from .stub_api import StubApiServer


class CliTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = StubApiServer()
        cls.server.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def setUp(self):
        self.server.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_dir = Path(self.tmp.name) / "config"
        self.data_dir = Path(self.tmp.name) / "data"
        self.state_dir = Path(self.tmp.name) / "state"
        for directory in (self.config_dir, self.data_dir, self.state_dir):
            directory.mkdir(parents=True)

    # -- helpers ------------------------------------------------------------
    def run_cli(self, *argv: str, api: bool = True) -> int:
        buffer = io.StringIO()
        prefix = ["--api-url", self.server.base_url] if api else []
        with redirect_stdout(buffer), redirect_stderr(buffer), mock.patch(
            "cdt.cli.configure_logging"
        ):
            code = main(
                [
                    *prefix,
                    "--config-dir",
                    str(self.config_dir),
                    "--data-dir",
                    str(self.data_dir),
                    *argv,
                ]
            )
        self.output = buffer.getvalue()
        return code

    @property
    def credentials(self) -> dict:
        path = self.config_dir / "crossdevicetracker" / "credentials.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def queue_db(self) -> Path:
        return self.data_dir / "crossdevicetracker" / "queue.db"


class VersionAndConfigTest(CliTestBase):
    def test_version(self):
        self.assertEqual(self.run_cli("version"), 0)
        self.assertIn("cdt 1.0.0", self.output)

    def test_version_json(self):
        self.assertEqual(self.run_cli("--json", "version"), 0)
        payload = json.loads(self.output)
        self.assertEqual(payload["version"], "1.0.0")

    def test_config_round_trip(self):
        self.assertEqual(
            self.run_cli("config", "--set", "api_url=http://example:1234", api=False), 0
        )
        self.assertEqual(self.run_cli("config", "--get", "api_url", api=False), 0)
        self.assertEqual(self.output.strip(), "http://example:1234")

    def test_config_rejects_unknown_keys(self):
        self.assertEqual(self.run_cli("config", "--set", "nope=1"), 1)

    def test_doctor_reports_the_environment(self):
        code = self.run_cli("doctor")
        self.assertIn(code, (0, 1))  # 1 when no window source exists (headless)
        self.assertIn("backend", self.output)


class LinkingTest(CliTestBase):
    def test_link_with_a_token(self):
        code = self.run_cli("link", "--token", "t" * 40, "--name", "test-laptop")
        self.assertEqual(code, 0)
        self.assertTrue(self.credentials["device_jwt"])
        self.assertEqual(self.credentials["device_name"], "test-laptop")
        self.assertTrue(self.credentials["linked_at"])
        # the credentials file must not be world readable
        mode = oct(
            (self.config_dir / "crossdevicetracker" / "credentials.json").stat().st_mode
        )[-3:]
        self.assertEqual(mode, "600")

    def test_link_with_account_credentials(self):
        code = self.run_cli(
            "link", "--email", "user@example.com", "--password", "secret", "--name", "box"
        )
        self.assertEqual(code, 0)
        self.assertIn("stub-link-token", str(self.server.state.link_tokens))

    def test_link_with_a_bad_token_fails(self):
        code = self.run_cli("link", "--token", "short")
        self.assertEqual(code, 1)
        self.assertFalse(self.credentials.get("device_jwt"))

    def test_commands_that_need_a_device_fail_cleanly(self):
        self.assertEqual(self.run_cli("sync"), 1)
        self.assertIn("not linked", self.output.lower())


class TrackingAndSyncTest(CliTestBase):
    def test_link_track_then_sync(self):
        self.assertEqual(self.run_cli("link", "--token", "t" * 40), 0)

        # a dry run tracks fake applications and queues them locally
        code = self.run_cli(
            "start",
            "--dry-run",
            "--no-sync",
            "--no-pid-file",
            "--duration",
            "4",
            "--poll",
            "0.5",
            "--min-session",
            "1",
        )
        self.assertEqual(code, 0)

        self.assertEqual(self.run_cli("--json", "queue"), 0)
        stats = json.loads(self.output)
        self.assertGreater(stats["pending"], 0)

        # ... and syncing uploads exactly those sessions
        code = self.run_cli("sync")
        self.assertEqual(code, 0)
        self.assertIn("Uploaded", self.output)
        self.assertEqual(len(self.server.state.batches), 1)
        self.assertGreater(len(self.server.state.time_logs), 0)

        # the queue is empty afterwards
        self.assertEqual(self.run_cli("--json", "queue"), 0)
        self.assertEqual(json.loads(self.output)["pending"], 0)

    def test_sync_retries_when_the_backend_is_down(self):
        self.assertEqual(self.run_cli("link", "--token", "t" * 40), 0)
        self.assertEqual(
            self.run_cli(
                "start", "--dry-run", "--no-sync", "--no-pid-file", "--duration", "3",
                "--poll", "0.5", "--min-session", "1",
            ),
            0,
        )

        # point at a dead backend: the sessions must stay queued
        code = main(
            [
                "--api-url", "http://127.0.0.1:1",
                "--config-dir", str(self.config_dir),
                "--data-dir", str(self.data_dir),
                "sync",
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(self.run_cli("--json", "queue"), 0)
        self.assertGreater(json.loads(self.output)["pending"], 0)

    def test_queue_clear(self):
        self.assertEqual(self.run_cli("link", "--token", "t" * 40), 0)
        self.run_cli(
            "start", "--dry-run", "--no-sync", "--no-pid-file", "--duration", "3",
            "--poll", "0.5", "--min-session", "1",
        )
        self.assertEqual(self.run_cli("queue", "--clear"), 0)
        self.assertEqual(self.run_cli("--json", "queue"), 0)
        self.assertEqual(json.loads(self.output)["pending"], 0)


class ReportingTest(CliTestBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_cli("link", "--token", "t" * 40), 0)
        self.assertEqual(
            self.run_cli("login", "--email", "user@example.com", "--password", "secret"), 0
        )

    def test_status(self):
        code = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("today", self.output)
        self.assertIn("2h 3m", self.output)  # 7380 seconds
        self.assertIn("Google Chrome", self.output)

    def test_status_local_only(self):
        self.assertEqual(self.run_cli("status", "--local"), 0)
        self.assertIn("tracker", self.output)
        self.assertNotIn("today", self.output)

    def test_apps(self):
        self.assertEqual(self.run_cli("apps", "--days", "7"), 0)
        self.assertIn("Google Chrome", self.output)
        self.assertIn("62.5%", self.output)

    def test_apps_json(self):
        self.assertEqual(self.run_cli("--json", "apps"), 0)
        payload = json.loads(self.output)
        self.assertEqual(payload[0]["app_name"], "Google Chrome")

    def test_devices(self):
        self.assertEqual(self.run_cli("devices", "--days", "7"), 0)
        self.assertIn("stub-laptop", self.output)

    def test_analytics(self):
        self.assertEqual(self.run_cli("analytics", "daily"), 0)
        self.assertIn("2026-10-19", self.output)

    def test_logs(self):
        self.assertEqual(self.run_cli("logs"), 0)
        self.assertIn("No time logs", self.output)

    def test_account(self):
        self.assertEqual(self.run_cli("account"), 0)
        self.assertIn("stub-laptop", self.output)

    def test_logout_keeps_the_device_link(self):
        self.assertEqual(self.run_cli("logout"), 0)
        self.assertFalse(self.credentials["user_jwt"])
        self.assertTrue(self.credentials["device_jwt"])


if __name__ == "__main__":
    unittest.main()
