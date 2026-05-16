from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(start: Path | None = None) -> Path | None:
    env_path = _find_dotenv(start or Path.cwd())
    if env_path is None:
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _parse_env_value(value.strip())
    return env_path


def _find_dotenv(start: Path) -> Path | None:
    current = start if start.is_dir() else start.parent
    current = current.resolve()
    for candidate_root in (current, *current.parents):
        candidate = candidate_root / ".env"
        if candidate.is_file():
            return candidate
    return None


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value
