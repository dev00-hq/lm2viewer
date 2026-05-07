#!/usr/bin/env python3
"""Script entrypoint for catalog graph validation probes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lba2_lm2_viewer.catalog_graph import catalog_graph_command


if __name__ == "__main__":
    raise SystemExit(catalog_graph_command(sys.argv[1:]))
