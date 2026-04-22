import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import viewer


class ViewerServerConcurrencyTests(unittest.TestCase):
    def test_catalog_build_operations_do_not_overlap(self) -> None:
        server = viewer.ViewerServer(None, None)
        events: list[tuple[str, str]] = []
        active = 0
        max_active = 0
        active_lock = threading.Lock()
        first_started = threading.Event()
        release_first = threading.Event()
        errors: list[BaseException] = []

        def fake_build_catalog(
            asset_root: Path,
            progress: viewer.DecodeProgress | None = None,
            selected_files: list[Path] | None = None,
        ) -> dict[str, object]:
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                events.append(("start", asset_root.name))
                if asset_root.name == "first":
                    first_started.set()
                    if not release_first.wait(2):
                        raise TimeoutError("test did not release first catalog build")
                events.append(("end", asset_root.name))
                return {"asset_root": str(asset_root), "summary": {}}
            finally:
                with active_lock:
                    active -= 1

        def run_build(path: str) -> None:
            try:
                server.set_asset_root(Path(path))
            except BaseException as exc:
                errors.append(exc)

        with (
            patch.object(viewer, "build_catalog", side_effect=fake_build_catalog),
            patch.object(viewer.ViewerServer, "load_visual_assets", return_value=None),
        ):
            first = threading.Thread(target=run_build, args=("first",))
            first.start()
            self.assertTrue(first_started.wait(2))

            second = threading.Thread(target=run_build, args=("second",))
            second.start()
            time.sleep(0.1)
            self.assertEqual(events, [("start", "first")])

            release_first.set()
            first.join(2)
            second.join(2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(max_active, 1)
        self.assertEqual(
            events,
            [("start", "first"), ("end", "first"), ("start", "second"), ("end", "second")],
        )


if __name__ == "__main__":
    unittest.main()
