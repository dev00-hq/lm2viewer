# Final Usage Strip Validation - Agent Browser - 2026-05-10

## Context

- Checkout: `C:\Users\sebam\.codex\worktrees\e82a\lba2-lm2-viewer`
- URL: `http://127.0.0.1:8913/`
- Server command: `uv run python -m lba2_lm2_viewer --host 127.0.0.1 --port 8913 --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 --no-browser`
- Asset root: `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- Browser tool: Codex in-app `agent-browser`
- Screenshot: `docs/validation-task-final-usage-strip-agent-browser-2026-05-10.png`

## Scenario

1. Start a fresh viewer from this checkout after rebuilding the frontend bundle.
2. Load the canonical LBA2 asset root through the HQR Folder UI.
3. Select graph-linked model asset `BODY.HQR:26`.
4. Click the graph usage strip item `Scene 99 (SCENE.HQR:100) object 1`.

## Expected State

- Active selection is a `scene_usage`, not a fallback scene object.
- Stable ID is graph-derived from the selected asset and usage record.
- Inspector renders non-empty structured sections.
- Scene usage details include target asset, scene asset, object index, File3D, GenBody/GenAnim/Sprite, and flags.
- Graph Usage Evidence shows proof scope, evidence status, source rule, source field, and index rule from the catalog graph.
- The fail-closed missing-record message is not shown for this linked usage item.

## Observed State

- Active selection: `Scene 99 (SCENE.HQR:100) object 1`.
- Active selection kind: `scene_usage`.
- Stable ID: `BODY.HQR:26#usage:SCENE.HQR:100#object:1`.
- Inspector rendered 5 structured sections.
- Scene Usage section showed:
  - Target asset: `BODY.HQR:26`
  - Scene asset: `SCENE.HQR:100`
  - Scene index: `99`
  - Object index: `1`
  - File3D: `14`
  - Flags: `0x8847`
- Graph Usage Evidence showed:
  `scene_object_state | source_backed | matched scene GenBody to File3D body generic id | SceneObject.links.body.asset_id / SceneAssetUsage.target_asset_id | File3D body generic id resolves to BODY.HQR catalog entry index.`
- `Graph usage links are missing usage records.` was absent.

## Selector Evidence

The browser run asserted:

```text
Active selection contains scene_usage
Inspector contains Scene Usage
Inspector contains Graph Usage Evidence
Inspector contains BODY.HQR:26
Inspector contains SCENE.HQR:100
Inspector contains Object index 1
Inspector contains File3D
Inspector does not contain Graph usage links are missing usage records.
```

## Validation Commands

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities
Set-Location frontend; fnm use 24.15.0; npm run build; Set-Location ..
```
