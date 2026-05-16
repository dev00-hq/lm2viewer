import tempfile
import unittest
from pathlib import Path

from symphony.models import HooksConfig
from symphony.workspace import WorkspaceManager, sanitize_workspace_key


class SymphonyWorkspaceTests(unittest.TestCase):
    def test_workspace_key_sanitizes_identifier(self) -> None:
        self.assertEqual(sanitize_workspace_key("ABC/123: fix"), "ABC_123_fix")

    def test_create_reuses_workspace_and_cleans_temp_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkspaceManager(Path(temp_dir), HooksConfig())
            workspace = manager.create_for_issue("ABC-1")
            (workspace.path / "tmp").mkdir()
            (workspace.path / ".elixir_ls").mkdir()

            reused = manager.create_for_issue("ABC-1")

            self.assertFalse(reused.created_now)
            self.assertFalse((workspace.path / "tmp").exists())
            self.assertFalse((workspace.path / ".elixir_ls").exists())

    def test_cleanup_removes_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkspaceManager(Path(temp_dir), HooksConfig())
            workspace = manager.create_for_issue("ABC-1")

            manager.cleanup_for_issue("ABC-1")

            self.assertFalse(workspace.path.exists())


if __name__ == "__main__":
    unittest.main()

