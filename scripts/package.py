#!/usr/bin/env python3
"""Build a self-contained release package for the LM2 viewer."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BUILD_ROOT = ROOT / "build"
PACKAGE_ROOT = BUILD_ROOT / "lba2-lm2-viewer"
RELEASE_ROOT = ROOT / "release"
ARCHIVE_BASE = RELEASE_ROOT / "lba2-lm2-viewer"

RUNTIME_FILES = (
    "MANIFEST.in",
    "pyproject.toml",
    "README.md",
    "requirements.txt",
    "viewer.py",
    "lba_hqr.py",
)


def run(command: list[str], cwd: Path) -> None:
    executable = shutil.which(command[0]) or shutil.which(f"{command[0]}.cmd") or command[0]
    subprocess.run([executable, *command[1:]], cwd=cwd, check=True)


def copy_runtime() -> None:
    if PACKAGE_ROOT.exists():
        shutil.rmtree(PACKAGE_ROOT)
    PACKAGE_ROOT.mkdir(parents=True)

    for relative in RUNTIME_FILES:
        shutil.copy2(ROOT / relative, PACKAGE_ROOT / relative)

    shutil.copytree(
        ROOT / "lba2_lm2_viewer",
        PACKAGE_ROOT / "lba2_lm2_viewer",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    frontend_dist = ROOT / "lba2_lm2_viewer" / "frontend" / "dist"
    if not frontend_dist.exists():
        raise SystemExit(f"frontend build missing: {frontend_dist}")


def main() -> int:
    run([sys.executable, str(ROOT / "scripts" / "build.py"), "--no-editable"], ROOT)

    copy_runtime()
    RELEASE_ROOT.mkdir(exist_ok=True)
    archive_path = shutil.make_archive(str(ARCHIVE_BASE), "zip", BUILD_ROOT, PACKAGE_ROOT.name)
    print(f"Wrote {archive_path}")
    run([sys.executable, "-m", "pip", "wheel", ".", "-w", str(RELEASE_ROOT)], PACKAGE_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
