from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import ConfigValidationError
from .models import HooksConfig, ServiceConfig, WorkflowDefinition


DEFAULT_ACTIVE_STATES = ("Todo", "In Progress")
DEFAULT_TERMINAL_STATES = ("Closed", "Cancelled", "Canceled", "Duplicate", "Done")


def build_config(workflow: WorkflowDefinition) -> ServiceConfig:
    raw = workflow.config
    tracker = _mapping(raw.get("tracker"))
    polling = _mapping(raw.get("polling"))
    workspace = _mapping(raw.get("workspace"))
    hooks = _mapping(raw.get("hooks"))
    agent = _mapping(raw.get("agent"))
    codex = _mapping(raw.get("codex"))

    tracker_kind = str(tracker.get("kind", "") or "")
    tracker_endpoint = str(
        tracker.get("endpoint") or "https://api.linear.app/graphql"
    )
    tracker_api_key = _resolve_env(
        str(tracker.get("api_key") or os.environ.get("LINEAR_API_KEY", ""))
    )
    tracker_project_slug = str(tracker.get("project_slug", "") or "")

    return ServiceConfig(
        workflow_path=workflow.path,
        tracker_kind=tracker_kind,
        tracker_endpoint=tracker_endpoint,
        tracker_api_key=tracker_api_key,
        tracker_project_slug=tracker_project_slug,
        active_states=tuple(_string_list(tracker.get("active_states"), DEFAULT_ACTIVE_STATES)),
        terminal_states=tuple(
            _string_list(tracker.get("terminal_states"), DEFAULT_TERMINAL_STATES)
        ),
        polling_interval_ms=_positive_int(polling.get("interval_ms"), 30000),
        workspace_root=_resolve_path(
            workspace.get("root") or str(Path(tempfile.gettempdir()) / "symphony_workspaces")
        ),
        hooks=HooksConfig(
            after_create=_optional_str(hooks.get("after_create")),
            before_run=_optional_str(hooks.get("before_run")),
            after_run=_optional_str(hooks.get("after_run")),
            before_remove=_optional_str(hooks.get("before_remove")),
            timeout_ms=_positive_int(hooks.get("timeout_ms"), 60000),
        ),
        max_concurrent_agents=_positive_int(agent.get("max_concurrent_agents"), 10),
        max_concurrent_agents_by_state=_state_concurrency(
            agent.get("max_concurrent_agents_by_state")
        ),
        max_retry_backoff_ms=_positive_int(agent.get("max_retry_backoff_ms"), 300000),
        max_turns=_positive_int(agent.get("max_turns"), 20),
        codex_command=str(codex.get("command") or "codex app-server"),
        codex_approval_policy=_optional_str(codex.get("approval_policy")),
        codex_thread_sandbox=_optional_str(codex.get("thread_sandbox")),
        codex_turn_sandbox_policy=codex.get("turn_sandbox_policy"),
        codex_turn_timeout_ms=_positive_int(codex.get("turn_timeout_ms"), 3600000),
        codex_read_timeout_ms=_positive_int(codex.get("read_timeout_ms"), 5000),
        codex_stall_timeout_ms=_int(codex.get("stall_timeout_ms"), 300000),
    )


def validate_dispatch_config(config: ServiceConfig) -> None:
    errors: list[str] = []
    if config.tracker_kind != "linear":
        errors.append("tracker.kind must be linear")
    if not config.tracker_api_key:
        errors.append("tracker.api_key is required")
    if not config.tracker_project_slug:
        errors.append("tracker.project_slug is required")
    if not config.codex_command.strip():
        errors.append("codex.command is required")
    if errors:
        raise ConfigValidationError("invalid Symphony configuration", errors)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _string_list(value: Any, default: tuple[str, ...]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _state_concurrency(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw in value.items():
        parsed = _int(raw, 0)
        if parsed > 0:
            result[str(key).lower()] = parsed
    return result


def _resolve_env(value: str) -> str:
    if value.startswith("$") and len(value) > 1:
        return os.environ.get(value[1:], "")
    return value


def _resolve_path(value: Any) -> Path:
    text = _resolve_env(str(value))
    return Path(os.path.expandvars(os.path.expanduser(text))).resolve()


def _positive_int(value: Any, default: int) -> int:
    parsed = _int(value, default)
    return parsed if parsed > 0 else default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

