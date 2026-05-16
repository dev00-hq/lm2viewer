import os
import tempfile
import unittest
from pathlib import Path

from symphony.env import load_dotenv


class SymphonyEnvTests(unittest.TestCase):
    def test_load_dotenv_reads_parent_file_without_overriding_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child = root / "nested"
            child.mkdir()
            env_file = root / ".env"
            env_file.write_text(
                """
# comment
LINEAR_API_KEY="from-file"
EXPORTED=value # comment
export EXTRA='quoted'
""",
                encoding="utf-8",
            )
            old_linear = os.environ.get("LINEAR_API_KEY")
            old_exported = os.environ.get("EXPORTED")
            old_extra = os.environ.get("EXTRA")
            try:
                os.environ["LINEAR_API_KEY"] = "already-set"
                os.environ.pop("EXPORTED", None)
                os.environ.pop("EXTRA", None)

                loaded = load_dotenv(child / "WORKFLOW.md")

                self.assertEqual(loaded, env_file)
                self.assertEqual(os.environ["LINEAR_API_KEY"], "already-set")
                self.assertEqual(os.environ["EXPORTED"], "value")
                self.assertEqual(os.environ["EXTRA"], "quoted")
            finally:
                _restore_env("LINEAR_API_KEY", old_linear)
                _restore_env("EXPORTED", old_exported)
                _restore_env("EXTRA", old_extra)

    def test_load_dotenv_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertIsNone(load_dotenv(Path(temp_dir)))


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
