from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BlockerRef:
    id: str | None
    identifier: str | None
    state: str | None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "BlockerRef":
        return cls(
            id=_optional_str(value.get("id")),
            identifier=_optional_str(value.get("identifier")),
            state=_optional_str(value.get("state")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "identifier": self.identifier, "state": self.state}


@dataclass(frozen=True)
class Issue:
    id: str
    identifier: str
    title: str
    description: str | None
    priority: int | None
    state: str
    branch_name: str | None
    url: str | None
    team_id: str | None = None
    labels: tuple[str, ...] = ()
    blocked_by: tuple[BlockerRef, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Issue":
        blockers = tuple(
            BlockerRef.from_mapping(item)
            for item in value.get("blocked_by", ())
            if isinstance(item, dict)
        )
        labels = tuple(str(label).lower() for label in value.get("labels", ()) or ())
        return cls(
            id=str(value["id"]),
            identifier=str(value["identifier"]),
            title=str(value.get("title", "")),
            description=_optional_str(value.get("description")),
            priority=_optional_int(value.get("priority")),
            state=str(value.get("state", "")),
            branch_name=_optional_str(value.get("branch_name")),
            url=_optional_str(value.get("url")),
            team_id=_optional_str(value.get("team_id")),
            labels=labels,
            blocked_by=blockers,
            created_at=_optional_str(value.get("created_at")),
            updated_at=_optional_str(value.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "state": self.state,
            "branch_name": self.branch_name,
            "url": self.url,
            "team_id": self.team_id,
            "labels": list(self.labels),
            "blocked_by": [blocker.to_dict() for blocker in self.blocked_by],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class WorkflowDefinition:
    path: Path
    config: dict[str, Any]
    prompt_template: str
    loaded_mtime_ns: int


@dataclass(frozen=True)
class HooksConfig:
    after_create: str | None = None
    before_run: str | None = None
    after_run: str | None = None
    before_remove: str | None = None
    timeout_ms: int = 60000


@dataclass(frozen=True)
class ServiceConfig:
    workflow_path: Path
    tracker_kind: str
    tracker_endpoint: str
    tracker_api_key: str
    tracker_project_slug: str
    active_states: tuple[str, ...]
    terminal_states: tuple[str, ...]
    polling_interval_ms: int
    workspace_root: Path
    hooks: HooksConfig
    max_concurrent_agents: int
    max_concurrent_agents_by_state: dict[str, int]
    max_retry_backoff_ms: int
    max_turns: int
    codex_command: str
    codex_approval_policy: str | None
    codex_thread_sandbox: str | None
    codex_turn_sandbox_policy: dict[str, Any] | str | None
    codex_turn_timeout_ms: int
    codex_read_timeout_ms: int
    codex_stall_timeout_ms: int

    @property
    def active_state_keys(self) -> set[str]:
        return {state.lower() for state in self.active_states}

    @property
    def terminal_state_keys(self) -> set[str]:
        return {state.lower() for state in self.terminal_states}


@dataclass(frozen=True)
class Workspace:
    path: Path
    workspace_key: str
    created_now: bool


@dataclass
class RetryEntry:
    issue_id: str
    identifier: str
    attempt: int
    due_at_ms: float
    error: str | None = None
    action: str = "run"


@dataclass
class RunningEntry:
    issue: Issue
    identifier: str
    started_at: float
    retry_attempt: int | None
    thread_id: str | None = None
    turn_id: str | None = None
    session_id: str | None = None
    codex_app_server_pid: str | None = None
    last_codex_event: str | None = None
    last_codex_timestamp: str | None = None
    last_codex_message: str | None = None
    codex_input_tokens: int = 0
    codex_output_tokens: int = 0
    codex_total_tokens: int = 0
    turn_count: int = 0
    worker: Any = None
    cancel: Any = None


@dataclass
class RuntimeState:
    poll_interval_ms: int
    max_concurrent_agents: int
    running: dict[str, RunningEntry] = field(default_factory=dict)
    claimed: set[str] = field(default_factory=set)
    retry_attempts: dict[str, RetryEntry] = field(default_factory=dict)
    completed: set[str] = field(default_factory=set)
    codex_input_tokens: int = 0
    codex_output_tokens: int = 0
    codex_total_tokens: int = 0
    codex_seconds_running: float = 0.0
    codex_rate_limits: dict[str, Any] | None = None


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
