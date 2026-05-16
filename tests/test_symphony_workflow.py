import os
import tempfile
import unittest
from pathlib import Path

from symphony.config import build_config, validate_dispatch_config
from symphony.errors import MissingWorkflowFile, TemplateRenderError
from symphony.models import Issue
from symphony.workflow import load_workflow, render_prompt, resolve_workflow_path


WORKFLOW = """---
tracker:
  kind: linear
  api_key: $TEST_LINEAR_KEY
  project_slug: CODEX
  active_states: [Todo, In Progress]
polling:
  interval_ms: 1234
workspace:
  root: $TEST_WORKSPACE_ROOT
hooks:
  before_run: |
    echo ready
  timeout_ms: 1000
agent:
  max_concurrent_agents: 2
  max_concurrent_agents_by_state:
    Todo: 1
  max_retry_backoff_ms: 20000
  max_turns: 3
codex:
  command: codex app-server
---
Work on {{ issue.identifier }}: {{ issue.title }}.
{% for label in issue.labels %}[{{ label }}]{% endfor %}
Attempt {{ attempt }}
"""


class SymphonyWorkflowTests(unittest.TestCase):
    def test_load_workflow_parses_front_matter_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_path = root / "WORKFLOW.md"
            workflow_path.write_text(WORKFLOW, encoding="utf-8")
            os.environ["TEST_LINEAR_KEY"] = "token"
            os.environ["TEST_WORKSPACE_ROOT"] = str(root / "workspaces")

            workflow = load_workflow(workflow_path)
            config = build_config(workflow)

            self.assertEqual(workflow.config["tracker"]["kind"], "linear")
            self.assertIn("Work on", workflow.prompt_template)
            self.assertEqual(config.tracker_api_key, "token")
            self.assertEqual(config.tracker_project_slug, "CODEX")
            self.assertEqual(config.polling_interval_ms, 1234)
            self.assertEqual(config.max_concurrent_agents, 2)
            self.assertEqual(config.max_concurrent_agents_by_state["todo"], 1)
            self.assertEqual(config.max_turns, 3)
            self.assertEqual(config.hooks.before_run, "echo ready")
            validate_dispatch_config(config)

    def test_default_workflow_path_is_cwd_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = root / "WORKFLOW.md"
            expected.write_text("hello", encoding="utf-8")
            self.assertEqual(resolve_workflow_path(None, root), expected.resolve())

    def test_missing_workflow_is_typed_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(MissingWorkflowFile):
                resolve_workflow_path(None, Path(temp_dir))

    def test_render_prompt_is_strict(self) -> None:
        issue = Issue(
            id="1",
            identifier="ABC-1",
            title="Fix it",
            description=None,
            priority=1,
            state="Todo",
            branch_name=None,
            url=None,
            labels=("bug",),
        )
        rendered = render_prompt("{{ issue.identifier }} {% for label in issue.labels %}{{ label }}{% endfor %}", issue, 2)
        self.assertEqual(rendered, "ABC-1 bug")

        with self.assertRaises(TemplateRenderError):
            render_prompt("{{ issue.nope }}", issue)

        with self.assertRaises(TemplateRenderError):
            render_prompt("{{ issue.title | upcase }}", issue)


if __name__ == "__main__":
    unittest.main()

