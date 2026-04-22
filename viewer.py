#!/usr/bin/env python3
"""Compatibility wrapper for source checkouts."""

from lba2_lm2_viewer.viewer import *  # noqa: F403
from lba2_lm2_viewer.viewer import main


if __name__ == "__main__":
    raise SystemExit(main())
