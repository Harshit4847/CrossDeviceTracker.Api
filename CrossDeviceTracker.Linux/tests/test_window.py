"""Tests for :mod:`cdt.window` and :mod:`cdt.idle`."""

from __future__ import annotations

import os
import unittest
from unittest import mock

def fake_process(stdout: str = "", returncode: int = 0):
    """A stand-in for ``subprocess.CompletedProcess``."""
    return type("CompletedProcess", (), {"stdout": stdout, "returncode": returncode})()


from cdt.idle import (
    MutterIdleSource,
    NullIdleSource,
    ScriptedIdleSource,
    XPrintIdleSource,
    open_idle_source,
)
from cdt.models import WindowInfo
from cdt.window import (
    ExternalWindowSource,
    NullWindowSource,
    ScriptedWindowSource,
    WindowSource,
    describe_environment,
    open_window_source,
)


class ScriptedSourceTest(unittest.TestCase):
    def test_replays_and_repeats_the_last_entry(self):
        source = ScriptedWindowSource(
            [WindowInfo("a", "A"), WindowInfo("b", "B")]
        )
        self.assertEqual(source.get_active_window().app_id, "a")
        self.assertEqual(source.get_active_window().app_id, "b")
        self.assertEqual(source.get_active_window().app_id, "b")

    def test_empty_script_returns_none(self):
        self.assertIsNone(ScriptedWindowSource([]).get_active_window())

    def test_is_a_window_source(self):
        self.assertIsInstance(ScriptedWindowSource([]), WindowSource)


class NullSourceTest(unittest.TestCase):
    def test_returns_none(self):
        self.assertIsNone(NullWindowSource().get_active_window())
        self.assertTrue(NullWindowSource().is_available())


class FactoryTest(unittest.TestCase):
    def test_none_is_selectable(self):
        with open_window_source("none") as source:
            self.assertIsInstance(source, NullWindowSource)

    def test_unknown_source_raises_with_options(self):
        with self.assertRaises(OSError) as caught:
            open_window_source("bogus")
        self.assertIn("bogus", str(caught.exception))
        self.assertIn("external", str(caught.exception))

    def test_auto_falls_back_to_something_usable_or_explains_why(self):
        # In a headless sandbox there is no display, so the factory must either
        # return a source or raise an actionable error - never crash.
        try:
            with open_window_source("auto") as source:
                self.assertTrue(source.is_available())
        except OSError as error:
            self.assertIn("window", str(error))

    def test_external_requires_a_command(self):
        with self.assertRaises(OSError):
            open_window_source("external", external_command="")

    def test_external_reads_json(self):
        source = ExternalWindowSource(
            "echo '{\"app_id\": \"code\", \"app_name\": \"VS Code\", \"title\": \"x\", \"pid\": 42}'"
        )
        window = source.get_active_window()
        self.assertEqual(window.app_id, "code")
        self.assertEqual(window.app_name, "VS Code")
        self.assertEqual(window.pid, 42)

    def test_external_reads_pipe_separated_output(self):
        source = ExternalWindowSource("echo 'code|VS Code|main.py|42'")
        window = source.get_active_window()
        self.assertEqual(window.app_id, "code")
        self.assertEqual(window.app_name, "VS Code")
        self.assertEqual(window.pid, 42)

    def test_external_ignores_empty_output(self):
        source = ExternalWindowSource("true")
        self.assertIsNone(source.get_active_window())


class X11SourceTest(unittest.TestCase):
    """These only run when libX11 is actually installed."""

    def setUp(self):
        try:
            from cdt.window import X11WindowSource
        except Exception:  # pragma: no cover
            self.skipTest("libX11 not available")
        self.X11WindowSource = X11WindowSource

    def test_without_a_display_it_fails_cleanly(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            source = self.X11WindowSource.__new__(self.X11WindowSource)
            self.assertFalse(source.is_available())


class IdleSourceTest(unittest.TestCase):
    def test_scripted_sequence(self):
        source = ScriptedIdleSource([100, 200, 300])
        self.assertEqual(source.get_idle_ms(), 100)
        self.assertEqual(source.get_idle_ms(), 200)
        self.assertEqual(source.get_idle_ms(), 300)
        self.assertEqual(source.get_idle_ms(), 300)  # repeats the last value

    def test_null_source(self):
        self.assertEqual(NullIdleSource().get_idle_ms(), 0)

    def test_auto_never_fails(self):
        for preference in ("auto", "none", "xss", "mutter", "xprintidle"):
            with self.subTest(preference=preference):
                source = open_idle_source(preference)
                self.assertGreaterEqual(source.get_idle_ms(), 0)
                source.close()

    def test_unknown_idle_source_raises(self):
        with self.assertRaises(OSError):
            open_idle_source("bogus")

    def test_xprintidle_parses_milliseconds(self):
        source = XPrintIdleSource.__new__(XPrintIdleSource)
        with mock.patch("subprocess.run", return_value=fake_process(" 4200\n")):
            self.assertEqual(source.get_idle_ms(), 4200)

    def test_xprintidle_handles_failures(self):
        source = XPrintIdleSource.__new__(XPrintIdleSource)
        with mock.patch("subprocess.run", return_value=fake_process("", returncode=1)):
            self.assertEqual(source.get_idle_ms(), 0)

    def test_mutter_parses_gdbus_output(self):
        source = MutterIdleSource.__new__(MutterIdleSource)
        with mock.patch("subprocess.run", return_value=fake_process("(uint64 9876,)\n")):
            self.assertEqual(source.get_idle_ms(), 9876)


class EnvironmentDescriptionTest(unittest.TestCase):
    def test_describe_environment_returns_a_diagnostic_payload(self):
        described = describe_environment()
        for key in ("session", "display", "waylandDisplay", "availableSources", "tools", "notes"):
            self.assertIn(key, described)
        self.assertIsInstance(described["availableSources"], list)
        self.assertIn("systemctl", described["tools"])


if __name__ == "__main__":
    unittest.main()
