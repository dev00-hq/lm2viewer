import os
import io
import tempfile
import time
import unittest
from pathlib import Path

from symphony.models import BlockerRef, Issue
from symphony.orchestrator import Orchestrator
from symphony.logging import StructuredLogger


class FakeTracker:
    def __init__(self, candidates):
        self.candidates = candidates
        self.completed = []

    def fetch_candidate_issues(self):
        return list(self.candidates)

    def fetch_terminal_issues(self):
        return []

    def fetch_issue_states_by_ids(self, ids):
        return [issue for issue in self.candidates if issue.id in ids]

    def complete_issue(self, issue):
        self.completed.append(issue.identifier)
        return Issue(
            id=issue.id,
            identifier=issue.identifier,
            title=issue.title,
            description=issue.description,
            priority=issue.priority,
            state="Done",
            branch_name=issue.branch_name,
            url=issue.url,
            team_id=issue.team_id,
            labels=issue.labels,
            blocked_by=issue.blocked_by,
        )


class FakeRunner:
    def __init__(self, *_args):
        self.runs = []

    def run_issue(self, issue, attempt=None):
        self.runs.append((issue, attempt))


class SymphonyOrchestratorTests(unittest.TestCase):
    def test_dispatch_skips_todo_with_non_terminal_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "WORKFLOW.md"
            workflow.write_text(
                """---
tracker:
  kind: linear
  api_key: token
  project_slug: CODEX
workspace:
  root: work
agent:
  max_concurrent_agents: 2
codex:
  command: echo ok
---
Do it
""",
                encoding="utf-8",
            )
            blocked = Issue(
                id="1",
                identifier="ABC-1",
                title="Blocked",
                description=None,
                priority=1,
                state="Todo",
                branch_name=None,
                url=None,
                blocked_by=(BlockerRef("0", "ABC-0", "In Progress"),),
            )
            ready = Issue(
                id="2",
                identifier="ABC-2",
                title="Ready",
                description=None,
                priority=2,
                state="Todo",
                branch_name=None,
                url=None,
                blocked_by=(BlockerRef("0", "ABC-0", "Done"),),
            )
            runner = FakeRunner()

            orchestrator = Orchestrator(
                workflow,
                tracker=FakeTracker([blocked, ready]),
                agent_runner_factory=lambda *_args: runner,
            )
            orchestrator.tick()
            time.sleep(0.05)

            self.assertNotIn("1", orchestrator.state.claimed)
            self.assertIn("ABC-2", orchestrator.tracker.completed)

    def test_due_retry_dispatches_candidate_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "WORKFLOW.md"
            workflow.write_text(
                """---
tracker:
  kind: linear
  api_key: token
  project_slug: CODEX
workspace:
  root: work
agent:
  max_concurrent_agents: 1
codex:
  command: echo ok
---
Do it
""",
                encoding="utf-8",
            )
            issue = Issue(
                id="1",
                identifier="ABC-1",
                title="Retry",
                description=None,
                priority=1,
                state="In Progress",
                branch_name=None,
                url=None,
            )
            runner = FakeRunner()
            orchestrator = Orchestrator(
                workflow,
                tracker=FakeTracker([issue]),
                agent_runner_factory=lambda *_args: runner,
            )
            orchestrator._schedule_retry(issue, attempt=2, error="previous failure")
            orchestrator.state.retry_attempts[issue.id].due_at_ms = 0

            orchestrator.tick()
            time.sleep(0.05)

            self.assertEqual([(run[0].id, run[1]) for run in runner.runs], [("1", 2)])
            self.assertIn("ABC-1", orchestrator.tracker.completed)

    def test_worker_success_marks_issue_complete_without_run_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "WORKFLOW.md"
            workflow.write_text(
                """---
tracker:
  kind: linear
  api_key: token
  project_slug: CODEX
workspace:
  root: work
agent:
  max_concurrent_agents: 1
codex:
  command: echo ok
---
Do it
""",
                encoding="utf-8",
            )
            issue = Issue(
                id="1",
                identifier="ABC-1",
                title="Complete",
                description=None,
                priority=1,
                state="In Progress",
                branch_name=None,
                url=None,
            )
            runner = FakeRunner()
            tracker = FakeTracker([issue])
            orchestrator = Orchestrator(
                workflow,
                tracker=tracker,
                agent_runner_factory=lambda *_args: runner,
            )

            orchestrator.tick()
            time.sleep(0.05)

            self.assertEqual(tracker.completed, ["ABC-1"])
            self.assertNotIn("1", orchestrator.state.retry_attempts)
            self.assertNotIn("1", orchestrator.state.claimed)

    def test_agent_event_named_event_does_not_collide_with_logger_event_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "WORKFLOW.md"
            workflow.write_text(
                """---
tracker:
  kind: linear
  api_key: token
  project_slug: CODEX
workspace:
  root: work
codex:
  command: echo ok
---
Do it
""",
                encoding="utf-8",
            )
            stream = io.StringIO()
            orchestrator = Orchestrator(
                workflow,
                tracker=FakeTracker([]),
                logger=StructuredLogger(stream),
            )

            orchestrator._on_agent_event({"event": "app_server_stderr", "message": "boom"})

            self.assertIn('"event": "codex_update"', stream.getvalue())
            self.assertIn('"source_event": "app_server_stderr"', stream.getvalue())

    def test_wait_for_idle_blocks_until_worker_exits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "WORKFLOW.md"
            workflow.write_text(
                """---
tracker:
  kind: linear
  api_key: token
  project_slug: CODEX
workspace:
  root: work
codex:
  command: echo ok
---
Do it
""",
                encoding="utf-8",
            )
            issue = Issue(
                id="1",
                identifier="ABC-1",
                title="Complete",
                description=None,
                priority=1,
                state="In Progress",
                branch_name=None,
                url=None,
            )
            runner = FakeRunner()
            tracker = FakeTracker([issue])
            orchestrator = Orchestrator(
                workflow,
                tracker=tracker,
                agent_runner_factory=lambda *_args: runner,
            )

            orchestrator.tick()
            orchestrator.wait_for_idle()

            self.assertEqual(tracker.completed, ["ABC-1"])
            self.assertEqual(orchestrator.state.running, {})


if __name__ == "__main__":
    unittest.main()
