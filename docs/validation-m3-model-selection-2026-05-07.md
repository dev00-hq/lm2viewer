# M3 Model Selection Graph Projection Validation - 2026-05-07

## Setup

- URL: `http://127.0.0.1:8892`
- Server command: `python -m lba2_lm2_viewer.viewer --host 127.0.0.1 --port 8892 --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 --no-browser`
- Asset root: `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- Screenshot: `docs/validation-m3-model-selection-2026-05-07.png`

## Selection

- Selected id: `BODY.HQR:2`
- Selection path: Explorer model row for `Twinsen with tunic model`

## Expected State

- Active selection remains an `ASSET` selection for `BODY.HQR:2`.
- Workspace suggestion is `model`.
- Evidence status is `DECODED_ONLY`.
- Export action is available for the selected model.
- No scene/entity auto-promotion occurs for this no-known-usage model.

## Observed State

- Active selection showed `Twinsen with tunic model`.
- Kind showed `ASSET`.
- Stable ID showed `BODY.HQR:2`.
- Source showed `BODY.HQR[2]`.
- Status showed `DECODED_ONLY`.
- Workspace showed `model`.
- Actions included `Open model workspace` and `Export evidence bundle`.

Result: passed.
