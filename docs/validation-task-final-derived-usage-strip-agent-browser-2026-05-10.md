# Final Derived Usage Strip Validation - Agent Browser - 2026-05-10

## Context

- Checkout: `C:\Users\sebam\.codex\worktrees\e82a\lba2-lm2-viewer`
- URL: `http://127.0.0.1:8915/`
- Server command: `uv run python -m lba2_lm2_viewer --host 127.0.0.1 --port 8915 --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 --no-browser`
- Asset root: `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- Browser tool: Codex in-app `agent-browser`
- Screenshot: `docs/validation-task-final-derived-usage-strip-agent-browser-2026-05-10.png`

## Scenario

1. Start a fresh viewer from this checkout after rebuilding the frontend bundle.
2. Load the canonical LBA2 asset root through the HQR Folder UI.
3. Select graph-linked model asset `BODY.HQR:26`.
4. Open the body model workspace from the selected entity.
5. Open the UV Inspector and select polygon `1`, creating `BODY.HQR:26#polygon:1`.

## Expected State

- Active selection is a derived `model_surface`.
- Scene usage strip still resolves parent graph usage from the model surface evidence.
- Scene usage strip shows graph-backed usage items for `BODY.HQR:26`.
- The usage strip does not fall back to `No selected usage strip.`
- The usage strip does not show `No graph usage evidence for selected asset.`
- The usage strip does not show `Graph usage links are missing usage records.`

## Observed State

- Active selection: `Nitro-meca-penguin model polygon 1`.
- Active selection kind: `model_surface`.
- Stable ID: `BODY.HQR:26#polygon:1`.
- Active selection links included parent graph usage links such as
  `SCENE.HQR:100#object:1`.
- Scene usage strip showed `Scene 99 (SCENE.HQR:100) object 1`.
- No missing-record or no-selection usage strip fallback text was visible.

## Selector Evidence

The browser run asserted:

```text
Active selection contains model_surface
Scene usage strip contains Scene 99 (SCENE.HQR:100) object 1
No selected usage strip. is absent
No graph usage evidence for selected asset. is absent
Graph usage links are missing usage records. is absent
```

## Validation Commands

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities
Set-Location frontend; fnm use 24.15.0; npm run build; Set-Location ..
git diff --check
```
