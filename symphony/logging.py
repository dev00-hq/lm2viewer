from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogger:
    def __init__(self, stream: Any = None) -> None:
        self.stream = stream or sys.stderr

    def event(self, event: str, level: str = "info", **fields: Any) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
        }
        payload.update({key: value for key, value in fields.items() if value is not None})
        try:
            print(json.dumps(payload, sort_keys=True), file=self.stream, flush=True)
        except Exception:
            print(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "error",
                        "event": "logging_sink_failure",
                    }
                ),
                file=sys.stderr,
                flush=True,
            )

