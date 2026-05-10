# Final Task Validation - Agent Browser - 2026-05-10

## Context

- Checkout: `C:\Users\sebam\.codex\worktrees\e82a\lba2-lm2-viewer`
- URL: `http://127.0.0.1:8910/`
- Browser tool: Codex in-app `agent-browser`
- Screenshot: `docs/validation-task-final-agent-browser-2026-05-10.png`

## Scenario

1. Start a fresh viewer from this checkout.
2. Select graph-linked model asset `BODY.HQR:26`.
3. Open the UV inspector and select a model polygon so model UV/stats state is visible.
4. Search for `bkg_brick_graphic`.
5. Select `LBA_BKG.HQR:197`.

## Expected State

- Active selection is `LBA_BKG.HQR:197`.
- Active selection does not offer `Export evidence bundle`.
- Inspector tab returns to `Details`.
- UV panel is hidden.
- UV facts reset to `No model loaded.`
- Model stats are empty.
- Details inspector shows the background resource route and `bkg_brick_graphic` evidence.

## Observed State

- Active selection: `Background brick graphic 0 (LBA_BKG.HQR:197)`.
- Active selection had no `Export evidence bundle` action.
- `#inspectorDetailsTab[aria-selected="true"]`.
- `#inspectorUvPanel[hidden]`.
- `#uvFacts`: `No model loaded.`
- `#stats`: empty.
- Details inspector rendered 8 structured sections including background layout `bkg_brick_graphic`.

## Validation Commands

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities
uv run python -m unittest discover -s tests
Set-Location frontend; fnm use 24.15.0; npm run build; Set-Location ..
git diff --check
```
