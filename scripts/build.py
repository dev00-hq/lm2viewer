#!/usr/bin/env python3
"""Build the frontend and install the Python project for local development."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path) -> None:
    executable = shutil.which(command[0]) or shutil.which(f"{command[0]}.cmd") or command[0]
    subprocess.run([executable, *command[1:]], cwd=cwd, check=True)


def build_frontend() -> None:
    run(["npm", "ci"], FRONTEND)
    run(["npm", "run", "build"], FRONTEND)


def install_editable() -> None:
    run([sys.executable, "-m", "pip", "install", "-e", "."], ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the LM2 viewer for local development.")
    parser.add_argument(
        "--no-editable",
        action="store_true",
        help="build the frontend but do not run pip install -e .",
    )
    args = parser.parse_args(argv)

    build_frontend()
    if not args.no_editable:
        install_editable()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
