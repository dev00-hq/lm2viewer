from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import WorkspaceError
from .logging import StructuredLogger
from .models import HooksConfig, Workspace


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_workspace_key(identifier: str) -> str:
    value = _SAFE_NAME_RE.sub("_", identifier).strip("._")
    return value or "issue"


class WorkspaceManager:
    def __init__(self, root: Path, hooks: HooksConfig, logger: StructuredLogger | None = None) -> None:
        self.root = root.expanduser().resolve()
        self.hooks = hooks
        self.logger = logger or StructuredLogger()

    def create_for_issue(self, identifier: str) -> Workspace:
        key = sanitize_workspace_key(identifier)
        path = (self.root / key).resolve()
        self._assert_inside_root(path)
        if path.exists() and not path.is_dir():
            raise WorkspaceError(f"workspace path exists and is not a directory: {path}")
        created_now = not path.exists()
        path.mkdir(parents=True, exist_ok=True)
        self._prepare(path)
        workspace = Workspace(path=path, workspace_key=key, created_now=created_now)
        if created_now and self.hooks.after_create:
            self.run_hook("after_create", path, fatal=True)
        return workspace

    def cleanup_for_issue(self, identifier: str) -> None:
        path = (self.root / sanitize_workspace_key(identifier)).resolve()
        self._assert_inside_root(path)
        if not path.exists():
            return
        if self.hooks.before_remove:
            self.run_hook("before_remove", path, fatal=False)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def run_before_run(self, path: Path) -> None:
        if self.hooks.before_run:
            self.run_hook("before_run", path, fatal=True)

    def run_after_run(self, path: Path) -> None:
        if self.hooks.after_run:
            self.run_hook("after_run", path, fatal=False)

    def run_hook(self, name: str, path: Path, *, fatal: bool) -> None:
        script = getattr(self.hooks, name)
        if not script:
            return
        self.logger.event("workspace_hook_start", hook=name, workspace=str(path))
        command = _shell_command(script)
        try:
            completed = subprocess.run(
                command,
                cwd=path,
                text=True,
                capture_output=True,
                timeout=self.hooks.timeout_ms / 1000,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self.logger.event("workspace_hook_timeout", "error", hook=name, workspace=str(path))
            if fatal:
                raise WorkspaceError(f"{name} hook timed out") from exc
            return
        if completed.returncode != 0:
            self.logger.event(
                "workspace_hook_failed",
                "error",
                hook=name,
                workspace=str(path),
                exit_code=completed.returncode,
                stderr=completed.stderr[-2000:],
            )
            if fatal:
                raise WorkspaceError(f"{name} hook failed with {completed.returncode}")

    def _prepare(self, path: Path) -> None:
        for name in ("tmp", ".elixir_ls"):
            target = path / name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

    def _assert_inside_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError(f"workspace path escapes root: {path}") from exc


def _shell_command(script: str) -> list[str]:
    if sys.platform == "win32":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    shell = os.environ.get("SHELL", "/bin/sh")
    return [shell, "-lc", script]

