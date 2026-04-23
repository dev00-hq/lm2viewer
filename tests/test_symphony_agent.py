import os
import unittest
from unittest import mock

from symphony.agent import _app_server_command


class SymphonyAgentTests(unittest.TestCase):
    def test_app_server_command_uses_windows_split_without_bash_wrapper(self) -> None:
        with mock.patch("symphony.agent.os.name", "nt"):
            command = _app_server_command(
                'codex --config shell_environment_policy.inherit=all --model gpt-5.3-codex app-server'
            )

        self.assertEqual(
            command,
            [
                "codex",
                "--config",
                "shell_environment_policy.inherit=all",
                "--model",
                "gpt-5.3-codex",
                "app-server",
            ],
        )

    def test_app_server_command_uses_bash_wrapper_on_non_windows_when_available(self) -> None:
        with mock.patch("symphony.agent.os.name", "posix"):
            with mock.patch("symphony.agent.shutil.which", return_value="/bin/bash"):
                command = _app_server_command("codex app-server")

        self.assertEqual(command, ["bash", "-lc", "codex app-server"])


if __name__ == "__main__":
    unittest.main()
