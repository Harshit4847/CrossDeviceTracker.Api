"""Tests for :mod:`cdt.config`."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cdt.config import AppPaths, ConfigStore, Credentials, Settings


class SettingsTest(unittest.TestCase):
    def test_defaults(self):
        settings = Settings()
        self.assertEqual(settings.api_url, "http://localhost:5148")
        self.assertEqual(settings.platform, "Linux")
        self.assertEqual(settings.window_source, "auto")
        self.assertEqual(settings.batch_size, 50)

    def test_from_dict_ignores_unknown_keys(self):
        settings = Settings.from_dict({"api_url": "http://x", "nope": 1})
        self.assertEqual(settings.api_url, "http://x")
        self.assertFalse(hasattr(settings, "nope"))

    def test_normalize_clamps_values(self):
        settings = Settings.from_dict(
            {
                "poll_interval_seconds": 0.01,
                "idle_threshold_seconds": 1,
                "batch_size": 5000,
                "min_session_seconds": 0,
                "api_url": "http://example.com/",
                "include_apps": ["a", "", " b "],
            }
        )
        self.assertEqual(settings.poll_interval_seconds, 0.25)
        self.assertEqual(settings.idle_threshold_seconds, 10)
        self.assertEqual(settings.batch_size, 200)
        self.assertEqual(settings.min_session_seconds, 1)
        self.assertEqual(settings.api_url, "http://example.com")
        self.assertEqual(settings.include_apps, ["a", "b"])

    def test_round_trip(self):
        settings = Settings(api_url="http://localhost:9999", batch_size=10)
        restored = Settings.from_dict(settings.to_dict())
        self.assertEqual(restored.api_url, "http://localhost:9999")
        self.assertEqual(restored.batch_size, 10)


class ConfigStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = AppPaths(
            config_dir=Path(self.tmp.name) / "config",
            data_dir=Path(self.tmp.name) / "data",
            state_dir=Path(self.tmp.name) / "state",
        )
        self.store = ConfigStore(self.paths)

    def test_settings_round_trip(self):
        self.store.save_settings(Settings(api_url="http://localhost:7000"))
        self.assertEqual(
            self.store.load_settings().api_url, "http://localhost:7000"
        )

    def test_credentials_are_written_privately(self):
        self.store.save_credentials(Credentials(device_id="abc", device_jwt="jwt"))
        mode = stat.S_IMODE(self.paths.credentials_file.stat().st_mode)
        self.assertEqual(mode, 0o600)
        restored = self.store.load_credentials()
        self.assertEqual(restored.device_id, "abc")
        self.assertTrue(restored.is_linked)

    def test_clear_credentials(self):
        self.store.save_credentials(Credentials(device_id="abc", device_jwt="jwt"))
        self.store.clear_credentials()
        self.assertFalse(self.store.load_credentials().is_linked)

    def test_missing_files_return_defaults(self):
        self.assertFalse(self.store.load_credentials().is_linked)
        self.assertEqual(self.store.load_settings().api_url, "http://localhost:5148")

    def test_environment_overrides_api_url(self):
        self.store.save_settings(Settings(api_url="http://file"))
        with mock.patch.dict(os.environ, {"CDT_API_URL": "http://env"}):
            self.assertEqual(self.store.load_settings().api_url, "http://env")

    def test_corrupt_files_do_not_crash(self):
        self.paths.ensure()
        self.paths.credentials_file.write_text("{not json", encoding="utf-8")
        self.assertFalse(self.store.load_credentials().is_linked)

    def test_paths_follow_xdg(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/xdg-config"}):
            paths = AppPaths()
        self.assertEqual(str(paths.config_file), "/tmp/xdg-config/crossdevicetracker/config.json")

    def test_json_is_valid(self):
        self.store.save_credentials(Credentials(device_id="abc", device_jwt="jwt"))
        payload = json.loads(self.paths.credentials_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["device_id"], "abc")


if __name__ == "__main__":
    unittest.main()
