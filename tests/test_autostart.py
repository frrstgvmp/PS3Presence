from subprocess import CompletedProcess
import unittest
from unittest.mock import patch

import autostart


class AutostartTests(unittest.TestCase):
    def test_frozen_application_registers_the_exe_not_a_development_python(self):
        with patch("autostart.is_autostart_enabled", return_value=False), \
             patch("autostart.sys.frozen", True, create=True), \
             patch("autostart._run_hidden", return_value=CompletedProcess([], 0, "", "")) as run:
            autostart.set_autostart_enabled(True)
        arguments = run.call_args.args[0]
        self.assertIn("-NoStart", arguments)
        self.assertIn("-ExecutablePath", arguments)
        self.assertNotIn("-StartNow:$false", arguments)

    def test_development_installation_uses_the_original_launcher(self):
        with patch("autostart.is_autostart_enabled", return_value=False), \
             patch("autostart.sys.frozen", False, create=True), \
             patch("autostart._run_hidden", return_value=CompletedProcess([], 0, "", "")) as run:
            autostart.set_autostart_enabled(True)
        arguments = run.call_args.args[0]
        self.assertIn("-NoStart", arguments)
        self.assertNotIn("-ExecutablePath", arguments)

    def test_existing_task_is_not_recreated(self):
        with patch("autostart.is_autostart_enabled", return_value=True), \
             patch("autostart._run_hidden") as run:
            autostart.set_autostart_enabled(True)
        run.assert_not_called()

    def test_scheduler_error_is_reported(self):
        with patch("autostart.is_autostart_enabled", return_value=False), \
             patch("autostart._run_hidden", return_value=CompletedProcess([], 1, "", "Rejected")):
            with self.assertRaisesRegex(RuntimeError, "Rejected"):
                autostart.set_autostart_enabled(True)
