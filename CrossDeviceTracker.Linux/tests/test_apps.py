"""Tests for :mod:`cdt.apps`."""

from __future__ import annotations

import unittest

from cdt.apps import prettify_app_name, should_track


class PrettifyTest(unittest.TestCase):
    def test_known_identifiers(self):
        self.assertEqual(prettify_app_name("google-chrome"), "Google Chrome")
        self.assertEqual(prettify_app_name("code"), "Visual Studio Code")
        self.assertEqual(prettify_app_name("org.gnome.nautilus"), "Files")
        self.assertEqual(prettify_app_name("vlc"), "VLC")

    def test_reverse_domain_identifiers(self):
        self.assertEqual(prettify_app_name("com.example.MyEditor"), "MyEditor")
        self.assertEqual(prettify_app_name("org.telegram.desktop"), "Telegram")

    def test_unknown_identifiers_are_humanised(self):
        self.assertEqual(prettify_app_name("my-cool-app"), "My Cool App")
        self.assertEqual(prettify_app_name("gimp"), "GIMP")

    def test_empty_falls_back(self):
        self.assertEqual(prettify_app_name("", fallback="Some Title"), "Some Title")
        self.assertEqual(prettify_app_name(None), "")


class ShouldTrackTest(unittest.TestCase):
    def test_empty_window_is_ignored(self):
        self.assertFalse(should_track("", "", ""))

    def test_tracks_by_default(self):
        self.assertTrue(should_track("firefox", "Firefox", "Mozilla Firefox"))

    def test_include_list_acts_as_allow_list(self):
        self.assertTrue(should_track("code", "Visual Studio Code", include=["code"]))
        self.assertFalse(should_track("firefox", "Firefox", include=["code"]))

    def test_exclude_wins_over_include(self):
        self.assertFalse(
            should_track("code", "Visual Studio Code", include=["code"], exclude=["code"])
        )

    def test_exclude_matches_app_id(self):
        self.assertFalse(should_track("notification-daemon", "", exclude=["notification"]))

    def test_exclude_matches_title(self):
        self.assertFalse(
            should_track("firefox", "Firefox", "YouTube", exclude=["youtube"])
        )


if __name__ == "__main__":
    unittest.main()
