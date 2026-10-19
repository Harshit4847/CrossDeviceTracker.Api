"""Tests for :mod:`cdt.service`."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from cdt import service


class PathsTest(unittest.TestCase):
    def test_paths_follow_xdg_config_home(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/cfg"}):
            self.assertEqual(
                service.systemd_unit_path(), Path("/tmp/cfg/systemd/user/crossdevicetracker.service")
            )
            self.assertEqual(
                service.autostart_path(), Path("/tmp/cfg/autostart/crossdevicetracker.desktop")
            )


class ExecResolutionTest(unittest.TestCase):
    def test_prefers_a_command_next_to_the_interpreter(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "cdt"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)
            with mock.patch.object(sys, "executable", str(Path(tmp) / "python3")):
                info = service.resolve_exec_command()
        self.assertEqual(info["argv"], [str(executable), "start"])

    def test_prefers_a_command_on_the_path(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "cdt"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)
            with mock.patch("shutil.which", return_value=str(executable)):
                info = service.resolve_exec_command()
        self.assertEqual(info["argv"], [str(executable), "start"])

    def test_falls_back_to_python_m(self):
        with mock.patch("shutil.which", return_value=None):
            info = service.resolve_exec_command()
        self.assertEqual(info["argv"][-3:], ["-m", "cdt", "start"])
        self.assertIn("PYTHONPATH", info["env"])


class UnitFileTest(unittest.TestCase):
    def test_unit_contents(self):
        text = service._unit_contents(
            ["/usr/local/bin/cdt", "start"], {"PYTHONUNBUFFERED": "1"}, "http://localhost:5148"
        )
        self.assertIn("[Unit]", text)
        self.assertIn("[Service]", text)
        self.assertIn("[Install]", text)
        self.assertIn("ExecStart=/usr/local/bin/cdt start", text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn("Environment=CDT_API_URL=http://localhost:5148", text)
        self.assertIn("ExecCondition=/bin/sh -c 'test -n \"${DISPLAY}${WAYLAND_DISPLAY}\"'", text)
        self.assertIn("WantedBy=default.target", text)

    def test_desktop_entry_contents(self):
        text = service._desktop_entry_contents(["/usr/local/bin/cdt", "start"], {"FOO": "bar"})
        self.assertIn("[Desktop Entry]", text)
        self.assertIn("Type=Application", text)
        self.assertIn("Exec=env FOO=bar /usr/local/bin/cdt start", text)
        self.assertIn("X-GNOME-Autostart-enabled=true", text)


class PidFileTest(unittest.TestCase):
    def test_round_trip(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "tracker.pid"
            service.write_pid_file(path)
            self.assertEqual(service.read_pid_file(path), os.getpid())
            self.assertTrue(service.process_alive(os.getpid()))
            service.remove_pid_file(path)
            self.assertIsNone(service.read_pid_file(path))

    def test_process_alive_handles_bogus_pids(self):
        self.assertFalse(service.process_alive(None))
        self.assertFalse(service.process_alive(0))


class SystemdDetectionTest(unittest.TestCase):
    def test_missing_systemctl_is_reported(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(service.systemd_available())

    def test_install_without_systemd_returns_an_error(self):
        with mock.patch.object(service, "systemd_available", return_value=False):
            result = service.install_systemd("http://localhost:5148")
        self.assertFalse(result["ok"])
        self.assertIn("systemd", result["error"])

    def test_install_writes_the_unit_and_enables_it(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "systemd" / "user"
            calls = []

            def fake_run(command, *args, **kwargs):
                calls.append(command)
                return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with mock.patch.object(service, "systemd_available", return_value=True), mock.patch(
                "subprocess.run", side_effect=fake_run
            ), mock.patch.object(
                service, "systemd_unit_dir", return_value=unit_dir
            ), mock.patch.object(
                service, "resolve_exec_command",
                return_value={"argv": ["/bin/cdt", "start"], "env": {}},
            ):
                result = service.install_systemd("http://localhost:5148")

            self.assertTrue(result["ok"])
            self.assertTrue((unit_dir / "crossdevicetracker.service").exists())
            self.assertIn(["systemctl", "--user", "enable", "crossdevicetracker.service"], calls)
            self.assertIn(["systemctl", "--user", "restart", "crossdevicetracker.service"], calls)

    def test_autostart_entry_is_written(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "autostart"
            with mock.patch.object(service, "autostart_dir", return_value=target), mock.patch.object(
                service, "resolve_exec_command",
                return_value={"argv": ["/bin/cdt", "start"], "env": {}},
            ):
                result = service.install_autostart()
            self.assertTrue((Path(result["path"])).exists())


if __name__ == "__main__":
    unittest.main()
