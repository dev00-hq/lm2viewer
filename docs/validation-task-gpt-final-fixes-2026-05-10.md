# TASK_GPT final gap validation - 2026-05-10

Validation target: `http://127.0.0.1:8904/`, served from this checkout with `uv run python -m lba2_lm2_viewer --host 127.0.0.1 --port 8904 --no-browser`.

## Code validation

- `uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities`
  - Result: 38 tests OK.
- `uv run python -m unittest discover -s tests`
  - Result: 152 tests OK.
- `fnm use 24.15.0; npm run build`
  - Result: TypeScript and Vite build passed. Vite reported the existing large chunk warning.
- `git diff --check`
  - Result: passed; only CRLF normalization warnings from Git.

## Browser validation

Used agent-browser against the local app.

- Explorer summary now says `Catalog relationship refs: 28128 refs across 2361 assets`; it no longer advertises the relationship count as graph-derived authority.
- `LBA_BKG.HQR:197` (`bkg_brick_graphic`) loads as an inspectable background resource, but its active selection does not include `Export evidence bundle`.
- `BODY.HQR:26` model surface selection from the UV inspector produces `BODY.HQR:26#polygon:1` and carries the parent graph export action (`Export evidence bundle`).
- After the stale-tab fix and rebuild, selecting `LBA_BKG.HQR:197` returns the inspector to Details and clears model UV/stats state before the resource route renders.

Screenshot artifact:

- `docs/validation-task-gpt-bkg-brick-no-export-2026-05-10.png`

Note: after the final rebuild, DOM validation confirmed the stale UV tab was cleared and the active brick selection remained non-exportable. The in-app screenshot capture then timed out on the refreshed tab, so the saved screenshot is from the pre-clear browser pass; the post-clear assertion is recorded from the rebuilt browser DOM.
