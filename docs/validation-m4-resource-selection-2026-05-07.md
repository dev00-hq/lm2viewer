# M4 Resource Selection Graph Projection Validation - 2026-05-07

## Setup

- URL: `http://127.0.0.1:8893`
- Server command: `python -m lba2_lm2_viewer.viewer --host 127.0.0.1 --port 8893 --asset-root <asset-root> --no-browser`
- Asset root: `<asset-root>`
- Screenshot: `docs/validation-m4-resource-selection-2026-05-07.png`

## Selection

- Selected id: `SAMPLES.HQR:0`
- Selection path: Explorer search for `SAMPLES.HQR:0`, then the sample resource row.

## Expected State

- Active selection remains an `ASSET` selection for `SAMPLES.HQR:0`.
- Workspace suggestion is `resource`.
- Evidence status is `SOURCE_BACKED`.
- Resource workspace shows the selected sample.
- Export action is available and the Export button is enabled.
- Scene/script references appear as links without auto-promoting selection to a scene object.

## Observed State

- Active selection showed `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`.
- Kind showed `ASSET`.
- Stable ID showed `SAMPLES.HQR:0`.
- Source showed `SAMPLES.HQR[0]`.
- Status showed `SOURCE_BACKED`.
- Workspace showed `resource`.
- Links listed script reference stable ids.
- Actions included `Open resource workspace` and `Export evidence bundle`.
- `#resourceTitle` showed `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`.
- `#exportAsset.disabled` was `false`.

Result: passed.
