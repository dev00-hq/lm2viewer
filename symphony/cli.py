from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import SymphonyError
from .logging import StructuredLogger
from .orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Symphony issue orchestration service.")
    parser.add_argument(
        "workflow",
        nargs="?",
        type=Path,
        help="path to WORKFLOW.md; defaults to ./WORKFLOW.md",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one poll/dispatch tick and exit",
    )
    args = parser.parse_args(argv)

    logger = StructuredLogger()
    try:
        orchestrator = Orchestrator(args.workflow, logger=logger)
        if args.once:
            orchestrator.startup_terminal_workspace_cleanup()
            orchestrator.tick()
        else:
            orchestrator.run_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except SymphonyError as exc:
        logger.event("startup_failed", "error", error=str(exc), code=getattr(exc, "code", None))
        return 2
    except Exception as exc:
        logger.event("startup_failed", "error", error=str(exc), code="unhandled")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
