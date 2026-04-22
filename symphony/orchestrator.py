from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .agent import AgentRunner
from .config import build_config, validate_dispatch_config
from .errors import SymphonyError
from .logging import StructuredLogger
from .models import Issue, RetryEntry, RunningEntry, RuntimeState, ServiceConfig, WorkflowDefinition
from .tracker import LinearClient
from .workflow import load_workflow
from .workspace import WorkspaceManager


class Orchestrator:
    def __init__(
        self,
        workflow_path: Path | None,
        *,
        logger: StructuredLogger | None = None,
        tracker: Any | None = None,
        agent_runner_factory: Any | None = None,
    ) -> None:
        self.workflow_path = workflow_path
        self.logger = logger or StructuredLogger()
        self.workflow = load_workflow(workflow_path)
        self.config = build_config(self.workflow)
        validate_dispatch_config(self.config)
        self.state = RuntimeState(
            poll_interval_ms=self.config.polling_interval_ms,
            max_concurrent_agents=self.config.max_concurrent_agents,
        )
        self.tracker = tracker or LinearClient(self.config)
        self.agent_runner_factory = agent_runner_factory
        self._stop = threading.Event()
        self._lock = threading.RLock()

    def run_forever(self) -> None:
        self.startup_terminal_workspace_cleanup()
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.state.poll_interval_ms / 1000)

    def stop(self) -> None:
        self._stop.set()

    def tick(self) -> None:
        with self._lock:
            self._reload_if_changed()
            self._reconcile_running_issues()
            try:
                validate_dispatch_config(self.config)
            except SymphonyError as exc:
                self.logger.event("validation_failed", "error", error=str(exc))
                return
            try:
                issues = self.tracker.fetch_candidate_issues()
            except Exception as exc:
                self.logger.event("tracker_fetch_failed", "error", error=str(exc))
                return
            self._process_due_retries(issues)
            for issue in sorted(issues, key=_dispatch_sort_key):
                if self.config.max_concurrent_agents - len(self.state.running) <= 0:
                    break
                if self._available_slots(issue.state) <= 0:
                    continue
                if self._should_dispatch(issue):
                    self._dispatch_issue(issue, attempt=None)

    def startup_terminal_workspace_cleanup(self) -> None:
        manager = WorkspaceManager(self.config.workspace_root, self.config.hooks, self.logger)
        try:
            terminal = self.tracker.fetch_terminal_issues()
        except Exception as exc:
            self.logger.event("startup_terminal_cleanup_failed", "error", error=str(exc))
            return
        for issue in terminal:
            try:
                manager.cleanup_for_issue(issue.identifier)
                self.logger.event(
                    "workspace_cleaned",
                    issue_id=issue.id,
                    issue_identifier=issue.identifier,
                )
            except Exception as exc:
                self.logger.event(
                    "workspace_cleanup_failed",
                    "error",
                    issue_id=issue.id,
                    issue_identifier=issue.identifier,
                    error=str(exc),
                )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": [
                    {
                        "issue_id": entry.issue.id,
                        "issue_identifier": entry.identifier,
                        "state": entry.issue.state,
                        "session_id": entry.session_id,
                        "started_at": entry.started_at,
                    }
                    for entry in self.state.running.values()
                ],
                "retry": [
                    {
                        "issue_id": retry.issue_id,
                        "identifier": retry.identifier,
                        "attempt": retry.attempt,
                        "due_at_ms": retry.due_at_ms,
                        "error": retry.error,
                        "action": retry.action,
                    }
                    for retry in self.state.retry_attempts.values()
                ],
                "totals": {
                    "input_tokens": self.state.codex_input_tokens,
                    "output_tokens": self.state.codex_output_tokens,
                    "total_tokens": self.state.codex_total_tokens,
                    "seconds_running": self.state.codex_seconds_running,
                },
                "rate_limits": self.state.codex_rate_limits,
            }

    def _dispatch_issue(self, issue: Issue, attempt: int | None) -> None:
        self.state.claimed.add(issue.id)
        entry = RunningEntry(
            issue=issue,
            identifier=issue.identifier,
            started_at=time.time(),
            retry_attempt=attempt,
        )
        self.state.running[issue.id] = entry
        runner = self._make_runner()

        def worker() -> None:
            reason = "normal"
            try:
                runner.run_issue(issue, attempt)
            except Exception as exc:
                reason = str(exc)
                self.logger.event(
                    "worker_failed",
                    "error",
                    issue_id=issue.id,
                    issue_identifier=issue.identifier,
                    error=reason,
                )
            finally:
                self._on_worker_exit(issue.id, reason)

        thread = threading.Thread(target=worker, daemon=True)
        entry.worker = thread
        thread.start()
        self.logger.event(
            "issue_dispatched",
            issue_id=issue.id,
            issue_identifier=issue.identifier,
            attempt=attempt,
        )

    def _make_runner(self) -> AgentRunner:
        manager = WorkspaceManager(self.config.workspace_root, self.config.hooks, self.logger)
        if self.agent_runner_factory is not None:
            return self.agent_runner_factory(
                self.config, self.workflow.prompt_template, self.tracker, manager
            )
        return AgentRunner(
            self.config,
            self.workflow.prompt_template,
            self.tracker,
            manager,
            self._on_agent_event,
        )

    def _on_worker_exit(self, issue_id: str, reason: str) -> None:
        with self._lock:
            entry = self.state.running.pop(issue_id, None)
            if entry is None:
                return
            self.state.codex_seconds_running += max(0.0, time.time() - entry.started_at)
            if reason == "normal":
                self.state.completed.add(issue_id)
                self._complete_issue(entry.issue, attempt=1)
            else:
                next_attempt = (entry.retry_attempt or 0) + 1
                self._schedule_retry(entry.issue, attempt=next_attempt, error=reason)

    def _complete_issue(self, issue: Issue, attempt: int) -> None:
        try:
            updated = self.tracker.complete_issue(issue)
        except Exception as exc:
            self._schedule_retry(
                issue,
                attempt=attempt,
                error=f"completion failed: {exc}",
                action="complete",
            )
            return
        self.state.retry_attempts.pop(issue.id, None)
        self.state.claimed.discard(issue.id)
        self.logger.event(
            "issue_completed",
            issue_id=issue.id,
            issue_identifier=issue.identifier,
            state=updated.state,
        )
        manager = WorkspaceManager(self.config.workspace_root, self.config.hooks, self.logger)
        try:
            manager.cleanup_for_issue(issue.identifier)
        except Exception as exc:
            self.logger.event(
                "workspace_cleanup_failed",
                "error",
                issue_id=issue.id,
                issue_identifier=issue.identifier,
                error=str(exc),
            )

    def _schedule_retry(self, issue: Issue, attempt: int, error: str | None, action: str = "run") -> None:
        delay = min(10000 * (2 ** max(0, attempt - 1)), self.config.max_retry_backoff_ms)
        if error is None:
            delay = 1000
        self.state.retry_attempts[issue.id] = RetryEntry(
            issue_id=issue.id,
            identifier=issue.identifier,
            attempt=attempt,
            due_at_ms=time.monotonic() * 1000 + delay,
            error=error,
            action=action,
        )
        self.logger.event(
            "retry_scheduled",
            issue_id=issue.id,
            issue_identifier=issue.identifier,
            attempt=attempt,
            delay_ms=delay,
            error=error,
            action=action,
        )

    def _process_due_retries(self, candidates: list[Issue]) -> None:
        now_ms = time.monotonic() * 1000
        by_id = {issue.id: issue for issue in candidates}
        for issue_id, retry in list(self.state.retry_attempts.items()):
            if retry.due_at_ms > now_ms:
                continue
            issue = by_id.get(issue_id)
            if issue is None:
                self.state.retry_attempts.pop(issue_id, None)
                self.state.claimed.discard(issue_id)
                self.logger.event(
                    "retry_released",
                    issue_id=issue_id,
                    issue_identifier=retry.identifier,
                    reason="issue_not_candidate",
                )
                continue
            if self.config.max_concurrent_agents - len(self.state.running) <= 0:
                self._schedule_retry(
                    issue,
                    retry.attempt + 1,
                    "no available orchestrator slots",
                    retry.action,
                )
                continue
            if self._available_slots(issue.state) <= 0:
                self._schedule_retry(
                    issue,
                    retry.attempt + 1,
                    f"no available slots for state {issue.state}",
                    retry.action,
                )
                continue
            self.state.retry_attempts.pop(issue_id, None)
            if retry.action == "complete":
                self._complete_issue(issue, attempt=retry.attempt + 1)
            else:
                self._dispatch_issue(issue, attempt=retry.attempt)

    def _on_agent_event(self, event: dict[str, Any]) -> None:
        issue_id = event.get("issue_id")
        with self._lock:
            if issue_id and issue_id in self.state.running:
                entry = self.state.running[issue_id]
                entry.last_codex_event = str(event.get("event") or event.get("method") or "codex_event")
                entry.last_codex_message = str(event)[:1000]
                entry.thread_id = event.get("thread_id") or entry.thread_id
                entry.turn_id = event.get("turn_id") or entry.turn_id
                if entry.thread_id and entry.turn_id:
                    entry.session_id = f"{entry.thread_id}-{entry.turn_id}"
        self.logger.event("codex_update", **event)

    def _should_dispatch(self, issue: Issue) -> bool:
        if issue.id in self.state.claimed:
            return False
        state = issue.state.lower()
        if state not in self.config.active_state_keys:
            return False
        if state == "todo":
            for blocker in issue.blocked_by:
                if blocker.state is None or blocker.state.lower() not in self.config.terminal_state_keys:
                    return False
        return True

    def _available_slots(self, state: str) -> int:
        global_remaining = self.config.max_concurrent_agents - len(self.state.running)
        state_cap = self.config.max_concurrent_agents_by_state.get(state.lower())
        if state_cap is None:
            return global_remaining
        running_in_state = sum(
            1 for entry in self.state.running.values() if entry.issue.state.lower() == state.lower()
        )
        return min(global_remaining, state_cap - running_in_state)

    def _reconcile_running_issues(self) -> None:
        ids = list(self.state.running)
        if not ids:
            return
        try:
            refreshed = {issue.id: issue for issue in self.tracker.fetch_issue_states_by_ids(ids)}
        except Exception as exc:
            self.logger.event("running_reconcile_failed", "debug", error=str(exc))
            return
        manager = WorkspaceManager(self.config.workspace_root, self.config.hooks, self.logger)
        for issue_id, entry in list(self.state.running.items()):
            issue = refreshed.get(issue_id)
            if issue is None:
                continue
            state = issue.state.lower()
            if state in self.config.terminal_state_keys:
                self.state.running.pop(issue_id, None)
                self.state.claimed.discard(issue_id)
                manager.cleanup_for_issue(issue.identifier)
            elif state in self.config.active_state_keys:
                entry.issue = issue
            else:
                self.state.running.pop(issue_id, None)
                self.state.claimed.discard(issue_id)

    def _reload_if_changed(self) -> None:
        try:
            if self.workflow.path.stat().st_mtime_ns == self.workflow.loaded_mtime_ns:
                return
            workflow = load_workflow(self.workflow.path)
            config = build_config(workflow)
            validate_dispatch_config(config)
        except Exception as exc:
            self.logger.event("workflow_reload_failed", "error", error=str(exc))
            return
        self.workflow = workflow
        self.config = config
        self.state.poll_interval_ms = config.polling_interval_ms
        self.state.max_concurrent_agents = config.max_concurrent_agents
        self.tracker = LinearClient(config)
        self.logger.event("workflow_reloaded", workflow=str(workflow.path))


def _dispatch_sort_key(issue: Issue) -> tuple[int, str]:
    priority = issue.priority if issue.priority is not None else 999999
    return (priority, issue.created_at or "")
