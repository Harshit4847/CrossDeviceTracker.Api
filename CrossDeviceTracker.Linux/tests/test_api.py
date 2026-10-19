"""Tests for :mod:`cdt.api` against the in-process stub backend."""

from __future__ import annotations

import unittest
from datetime import timedelta

from cdt.api import ApiClient, ApiError
from cdt.models import new_session_id, to_iso, utcnow

from .stub_api import StubApiServer


class ApiClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = StubApiServer()
        cls.server.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def setUp(self):
        self.server.reset()
        self.api = ApiClient(self.server.base_url, timeout=10)

    # -- helpers ------------------------------------------------------------
    def entry(self, seconds: int = 30):
        now = utcnow().replace(microsecond=0)
        return {
            "packageName": "firefox",
            "appName": "Firefox",
            "startTimeUtc": to_iso(now - timedelta(seconds=seconds)),
            "endTimeUtc": to_iso(now),
            "durationSeconds": seconds,
            "createdAtUtc": to_iso(now),
            "clientSessionId": new_session_id(),
        }

    # -- auth ---------------------------------------------------------------
    def test_login_returns_the_access_token(self):
        payload = self.api.login("user@example.com", "secret")
        self.assertEqual(payload["accessToken"], "stub-user-jwt")

    def test_login_failure_raises_with_a_message(self):
        with self.assertRaises(ApiError) as caught:
            self.api.login("user@example.com", "wrong")
        self.assertEqual(caught.exception.status, 401)
        self.assertIn("Invalid", str(caught.exception))

    def test_register(self):
        payload = self.api.register("new@example.com", "secret")
        self.assertEqual(payload["email"], "new@example.com")

    # -- devices ------------------------------------------------------------
    def test_link_device(self):
        result = self.api.link_device("x" * 40, "my-laptop", "Linux")
        self.assertTrue(result.device_jwt)
        self.assertTrue(result.device_id)

    def test_link_device_rejects_a_short_token(self):
        with self.assertRaises(ApiError) as caught:
            self.api.link_device("short", "my-laptop", "Linux")
        self.assertEqual(caught.exception.status, 400)

    def test_link_token_generation(self):
        payload = self.api.create_link_token("stub-user-jwt")
        self.assertTrue(payload["token"])
        self.assertTrue(payload["expiresAt"])

    def test_list_devices(self):
        devices = self.api.list_devices("stub-user-jwt")
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].platform, "Linux")

    # -- time logs ----------------------------------------------------------
    def test_batch_upload_returns_accepted_ids(self):
        entries = [self.entry(), self.entry(seconds=45)]
        accepted = self.api.create_time_logs_batch("stub-device-jwt", entries)
        self.assertEqual(sorted(accepted), sorted(e["clientSessionId"] for e in entries))
        self.assertEqual(len(self.server.state.time_logs), 2)

    def test_batch_upload_requires_a_token(self):
        with self.assertRaises(ApiError) as caught:
            self.api.create_time_logs_batch("", [self.entry()])
        self.assertTrue(caught.exception.is_auth_error)

    def test_batch_upload_rejects_invalid_entries(self):
        entry = self.entry()
        entry["durationSeconds"] = 0
        with self.assertRaises(ApiError) as caught:
            self.api.create_time_logs_batch("stub-device-jwt", [entry])
        self.assertTrue(caught.exception.is_validation_error)

    def test_single_upload(self):
        entry = self.entry()
        self.api.create_time_log("stub-device-jwt", entry)
        self.assertEqual(len(self.server.state.time_logs), 1)

    def test_get_time_logs(self):
        payload = self.api.get_time_logs("stub-device-jwt", limit=10)
        self.assertEqual(payload["items"], [])
        self.assertFalse(payload["hasMore"])

    # -- dashboard ----------------------------------------------------------
    def test_dashboard_summary(self):
        summary = self.api.dashboard_summary("stub-user-jwt")
        self.assertEqual(summary["today"]["totalScreenTimeSeconds"], 7380)
        self.assertEqual(summary["mostUsedApp"]["appName"], "Google Chrome")

    def test_dashboard_apps(self):
        usage = self.api.dashboard_apps("stub-user-jwt")
        self.assertEqual(usage[0].app_name, "Google Chrome")
        self.assertEqual(usage[0].percentage, 62.5)

    def test_analytics(self):
        buckets = self.api.analytics("daily", "stub-user-jwt")
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0].duration_seconds, 7380)

    # -- error handling -----------------------------------------------------
    def test_unknown_endpoint_raises(self):
        with self.assertRaises(ApiError) as caught:
            self.api.request("GET", "/api/nope")
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(caught.exception.payload, b'{"error": "not found"}')

    def test_unreachable_backend_raises_a_retryable_error(self):
        api = ApiClient("http://127.0.0.1:1", timeout=2)
        with self.assertRaises(ApiError) as caught:
            api.ping()
        self.assertTrue(caught.exception.retryable)
        self.assertFalse(caught.exception.is_auth_error)

    def test_requests_carry_the_user_agent(self):
        self.api.dashboard_summary("stub-user-jwt")
        request = self.server.state.requests[-1]
        self.assertIn("CrossDeviceTracker.Linux/", request["userAgent"])
        self.assertEqual(request["authorization"], "Bearer stub-user-jwt")


if __name__ == "__main__":
    unittest.main()
