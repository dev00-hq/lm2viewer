from __future__ import annotations

import json
import queue
import shlex
import shutil
import subprocess
import threading
import time
import os
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .errors import AgentError
from .models import Issue, ServiceConfig
from .workflow import render_prompt


EventCallback = Callable[[dict[str, Any]], None]


class AppServerClient:
    def __init__(self, config: ServiceConfig, workspace: Path, on_event: EventCallback | None = None) -> None:
        self.config = config
        self.workspace = workspace
        self.on_event = on_event or (lambda _event: None)
        self.process: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._responses: dict[int, dict[str, Any]] = {}
        self._events: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._reader: threading.Thread | None = None

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process is not None else None

    def start(self) -> str:
        command = _app_server_command(self.config.codex_command)
        self.process = subprocess.Popen(
            command,
            cwd=self.workspace,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self.request(
            "initialize",
            {
                "clientInfo": {"name": "symphony", "version": __version__},
                "capabilities": {},
            },
        )
        self.notify("initialized", {})
        thread = self.request(
            "thread/start",
            {
                "approvalPolicy": self.config.codex_approval_policy,
                "sandbox": self.config.codex_thread_sandbox,
                "cwd": str(self.workspace),
            },
        )
        thread_id = (
            thread.get("result", {}).get("thread", {}).get("id")
            or thread.get("result", {}).get("thread_id")
            or thread.get("thread_id")
        )
        if not thread_id:
            raise AgentError("thread/start response did not include thread id")
        return str(thread_id)

    def run_turn(self, thread_id: str, prompt: str, issue: Issue) -> str:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": str(self.workspace),
            "title": f"{issue.identifier}: {issue.title}",
        }
        if self.config.codex_approval_policy is not None:
            params["approvalPolicy"] = self.config.codex_approval_policy
        if self.config.codex_turn_sandbox_policy is not None:
            params["sandboxPolicy"] = self.config.codex_turn_sandbox_policy
        response = self.request("turn/start", params, timeout_ms=self.config.codex_turn_timeout_ms)
        turn_id = (
            response.get("result", {}).get("turn", {}).get("id")
            or response.get("result", {}).get("turn_id")
            or response.get("turn_id")
        )
        if not turn_id:
            raise AgentError("turn/start response did not include turn id")
        return str(turn_id)

    def request(self, method: str, params: dict[str, Any], timeout_ms: int | None = None) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None:
            raise AgentError("app-server process is not running")
        request_id = self._next_id
        self._next_id += 1
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + (timeout_ms or self.config.codex_read_timeout_ms) / 1000
        while time.monotonic() < deadline:
            if request_id in self._responses:
                response = self._responses.pop(request_id)
                if "error" in response:
                    raise AgentError(f"{method} failed: {response['error']}")
                return response
            if self.process.poll() is not None:
                raise AgentError(f"app-server exited with {self.process.returncode}")
            time.sleep(0.01)
        raise AgentError(f"{method} timed out")

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"method": method, "params": params})

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.process is not None and self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def _read_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in message and "method" in message:
                self._reject_server_request(message)
            elif "id" in message and isinstance(message["id"], int):
                self._responses[message["id"]] = message
            else:
                self.on_event(message)

    def _read_stderr(self) -> None:
        assert self.process is not None and self.process.stderr is not None
        for line in self.process.stderr:
            self.on_event({"event": "app_server_stderr", "message": line.rstrip()})

    def _reject_server_request(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        method = message.get("method")
        self.on_event(
            {
                "event": "unsupported_app_server_request",
                "method": method,
                "id": request_id,
            }
        )
        if self.process is None or self.process.stdin is None:
            return
        response = {
            "id": request_id,
            "error": {
                "code": "unsupported_request",
                "message": f"Symphony does not implement client-side request {method}",
            },
        }
        self.process.stdin.write(json.dumps(response) + "\n")
        self.process.stdin.flush()


class AgentRunner:
    def __init__(self, config: ServiceConfig, workflow_template: str, tracker: Any, workspace_manager: Any, on_event: EventCallback | None = None) -> None:
        self.config = config
        self.workflow_template = workflow_template
        self.tracker = tracker
        self.workspace_manager = workspace_manager
        self.on_event = on_event or (lambda _event: None)

    def run_issue(self, issue: Issue, attempt: int | None = None) -> None:
        workspace = self.workspace_manager.create_for_issue(issue.identifier)
        client: AppServerClient | None = None
        try:
            self.workspace_manager.run_before_run(workspace.path)
            client = AppServerClient(self.config, workspace.path, self.on_event)
            thread_id = client.start()
            turn_number = 1
            current_issue = issue
            while True:
                prompt = render_prompt(self.workflow_template, current_issue, attempt)
                turn_id = client.run_turn(thread_id, prompt, current_issue)
                self.on_event(
                    {
                        "event": "session_started",
                        "issue_id": issue.id,
                        "issue_identifier": issue.identifier,
                        "thread_id": thread_id,
                        "turn_id": turn_id,
                    }
                )
                refreshed = self.tracker.fetch_issue_states_by_ids([issue.id])
                if refreshed:
                    current_issue = refreshed[0]
                if current_issue.state.lower() not in self.config.active_state_keys:
                    break
                if turn_number >= self.config.max_turns:
                    break
                turn_number += 1
        finally:
            if client is not None:
                client.stop()
            self.workspace_manager.run_after_run(workspace.path)


def _app_server_command(command: str) -> list[str]:
    if os.name != "nt" and shutil.which("bash"):
        return ["bash", "-lc", command]
    parts = shlex.split(command, posix=(os.name != "nt"))
    if os.name == "nt" and parts:
        parts[0] = _resolve_windows_command(parts[0])
    return parts


def _resolve_windows_command(command: str) -> str:
    if Path(command).suffix:
        resolved = shutil.which(command)
        return resolved or command
    extensions = [".exe", ".cmd", ".bat", ".com", ".ps1"]
    for extension in extensions:
        resolved = shutil.which(command + extension)
        if resolved:
            if resolved.lower().endswith(".ps1"):
                pwsh = shutil.which("pwsh") or shutil.which("powershell")
                return pwsh or resolved
            return resolved
    resolved = shutil.which(command)
    return resolved or command
