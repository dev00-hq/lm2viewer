from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .errors import (
    MissingWorkflowFile,
    TemplateRenderError,
    WorkflowFrontMatterNotMap,
    WorkflowParseError,
)
from .models import Issue, WorkflowDefinition


DEFAULT_PROMPT = "You are working on an issue from Linear."
_VAR_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")
_FOR_RE = re.compile(
    r"{%\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z0-9_.]+)\s*%}(.*?){%\s*endfor\s*%}",
    re.DOTALL,
)


def resolve_workflow_path(path: Path | None, cwd: Path | None = None) -> Path:
    root = cwd or Path.cwd()
    selected = path if path is not None else root / "WORKFLOW.md"
    selected = selected.expanduser()
    if not selected.is_absolute():
        selected = (root / selected).resolve()
    if not selected.exists() or not selected.is_file():
        raise MissingWorkflowFile(f"workflow file not found: {selected}")
    return selected


def load_workflow(path: Path | None = None, cwd: Path | None = None) -> WorkflowDefinition:
    workflow_path = resolve_workflow_path(path, cwd)
    try:
        raw = workflow_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MissingWorkflowFile(f"workflow file cannot be read: {workflow_path}") from exc

    config: dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.splitlines(keepends=True)
        end_index = None
        for index, line in enumerate(parts[1:], start=1):
            if line.strip() == "---":
                end_index = index
                break
        if end_index is None:
            raise WorkflowParseError("workflow front matter is missing closing ---")
        front_matter = "".join(parts[1:end_index])
        body = "".join(parts[end_index + 1 :])
        parsed = parse_front_matter(front_matter)
        if not isinstance(parsed, dict):
            raise WorkflowFrontMatterNotMap("workflow front matter must be a map")
        config = parsed

    stat = workflow_path.stat()
    return WorkflowDefinition(
        path=workflow_path,
        config=config,
        prompt_template=body.strip(),
        loaded_mtime_ns=stat.st_mtime_ns,
    )


def parse_front_matter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    parser = _YamlSubsetParser(lines)
    try:
        value = parser.parse_block(0, 0)
    except Exception as exc:
        if isinstance(exc, WorkflowParseError):
            raise
        raise WorkflowParseError(str(exc)) from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise WorkflowFrontMatterNotMap("workflow front matter must be a map")
    return value


def render_prompt(template: str, issue: Issue, attempt: int | None = None) -> str:
    source = template.strip() or DEFAULT_PROMPT
    context = {"issue": issue.to_dict(), "attempt": attempt}
    source = _render_loops(source, context)

    def replace(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        if "|" in expr:
            raise TemplateRenderError(f"unknown filters are not supported: {expr}")
        value = _resolve_expr(expr, context)
        if isinstance(value, (dict, list, tuple)):
            raise TemplateRenderError(f"cannot render non-scalar value: {expr}")
        return "" if value is None else str(value)

    try:
        return _VAR_RE.sub(replace, source)
    except TemplateRenderError:
        raise
    except Exception as exc:
        raise TemplateRenderError(str(exc)) from exc


def _render_loops(template: str, context: dict[str, Any]) -> str:
    while True:
        match = _FOR_RE.search(template)
        if match is None:
            return template
        name, expr, body = match.groups()
        values = _resolve_expr(expr, context)
        if not isinstance(values, (list, tuple)):
            raise TemplateRenderError(f"loop target is not iterable: {expr}")
        rendered = []
        for value in values:
            nested = dict(context)
            nested[name] = value
            rendered.append(_VAR_RE.sub(lambda m: str(_resolve_expr(m.group(1).strip(), nested) or ""), body))
        template = template[: match.start()] + "".join(rendered) + template[match.end() :]


def _resolve_expr(expr: str, context: dict[str, Any]) -> Any:
    parts = expr.split(".")
    current: Any = context
    for part in parts:
        if not part:
            raise TemplateRenderError(f"invalid template expression: {expr}")
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise TemplateRenderError(f"unknown template variable: {expr}")
    return current


class _YamlSubsetParser:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def parse_block(self, start: int, indent: int) -> Any:
        result: dict[str, Any] = {}
        index = start
        while index < len(self.lines):
            raw = self.lines[index]
            if not raw.strip() or raw.lstrip().startswith("#"):
                index += 1
                continue
            current_indent = len(raw) - len(raw.lstrip(" "))
            if current_indent < indent:
                break
            if current_indent > indent:
                raise WorkflowParseError(f"unexpected indentation on line {index + 1}")
            stripped = raw.strip()
            if stripped.startswith("- "):
                return self._parse_list(index, indent)
            if ":" not in stripped:
                raise WorkflowParseError(f"expected key: value on line {index + 1}")
            key, rest = stripped.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            if not key:
                raise WorkflowParseError(f"empty key on line {index + 1}")
            if rest in {"|", ">"}:
                value, index = self._collect_block_scalar(index + 1, indent + 2)
                result[key] = value
                continue
            if rest:
                result[key] = _parse_scalar(rest)
                index += 1
                continue
            next_index = self._next_content_line(index + 1)
            if next_index is None:
                result[key] = {}
                index += 1
                continue
            next_indent = len(self.lines[next_index]) - len(self.lines[next_index].lstrip(" "))
            if next_indent <= indent:
                result[key] = {}
                index += 1
                continue
            value, consumed = self._parse_nested(next_index, next_indent)
            result[key] = value
            index = consumed
        return result

    def _parse_nested(self, start: int, indent: int) -> tuple[Any, int]:
        if self.lines[start].strip().startswith("- "):
            return self._parse_list(start, indent)
        parser = _YamlSubsetParser(self.lines)
        value = parser.parse_block(start, indent)
        return value, parser._find_end(start, indent)

    def _parse_list(self, start: int, indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        index = start
        while index < len(self.lines):
            raw = self.lines[index]
            if not raw.strip() or raw.lstrip().startswith("#"):
                index += 1
                continue
            current_indent = len(raw) - len(raw.lstrip(" "))
            if current_indent < indent:
                break
            if current_indent != indent or not raw.strip().startswith("- "):
                break
            items.append(_parse_scalar(raw.strip()[2:].strip()))
            index += 1
        return items, index

    def _collect_block_scalar(self, start: int, indent: int) -> tuple[str, int]:
        chunks: list[str] = []
        index = start
        while index < len(self.lines):
            raw = self.lines[index]
            current_indent = len(raw) - len(raw.lstrip(" "))
            if raw.strip() and current_indent < indent:
                break
            chunks.append(raw[indent:] if len(raw) >= indent else "")
            index += 1
        return "\n".join(chunks).rstrip("\n"), index

    def _find_end(self, start: int, indent: int) -> int:
        index = start
        while index < len(self.lines):
            raw = self.lines[index]
            if raw.strip():
                current_indent = len(raw) - len(raw.lstrip(" "))
                if current_indent < indent:
                    break
            index += 1
        return index

    def _next_content_line(self, start: int) -> int | None:
        for index in range(start, len(self.lines)):
            line = self.lines[index]
            if line.strip() and not line.lstrip().startswith("#"):
                return index
        return None


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        return os.path.expandvars(value)

