# LBA2 LM2 Viewer Documentation

## What This Repo Is

This repository contains a local LM2 model and animation inspection tool for
Little Big Adventure 2 assets. It is used for reverse engineering and for
producing evidence that can inform a future port.

The repo does not contain game data. Users select their own LBA2 asset folder or
HQR files at runtime.

## Current Status

- Installable Python package exists.
- Browser frontend exists and is served by the Python backend.
- Single developer build command exists.
- Release zip and wheel packaging exists.
- HQR, BODY/LM2, palette, texture atlas, and structured ANIM decode paths exist.
- CLI and frontend model export probes exist.
- CLI model contract probes exist.
- CLI animation evidence probes exist.
- Frontend texture/UV inspector exists.
- Frontend posed mesh frame stepping exists for selected BODY + ANIM pairs.
- ANIM3DS entries are cataloged as raw evidence with size, hash, header words,
  and unknown byte-range descriptors.

Milestone status is tracked in `docs/plans.md`.

## Requirements

- Python 3.10 or newer
- Node.js and npm for source builds
- Local user-owned LBA2 assets

Python runtime dependencies are listed in `pyproject.toml` and
`requirements.txt`.

## Build

Run the full developer build from the repository root:

```powershell
py -3 .\scripts\build.py
```

This runs:

- `npm ci`
- `npm run build`
- `pip install -e .`

The frontend bundle is generated into `lba2_lm2_viewer/frontend/dist/` and is
ignored by Git.

## Run

After building:

```powershell
lba2-lm2-viewer
```

If the Python scripts directory is not on `PATH`:

```powershell
py -3 -m lba2_lm2_viewer
```

With a known asset folder:

```powershell
lba2-lm2-viewer --asset-root "C:\LBA2"
```

The default server URL is `http://127.0.0.1:8765`.

## Test

Run Python tests:

```powershell
py -3 -m unittest discover -s tests -v
```

Run a frontend-only build without reinstalling the package:

```powershell
py -3 .\scripts\build.py --no-editable
```

## Export Probe

Export one catalog model asset for external inspection:

```powershell
lba2-lm2-viewer export --asset-root "C:\LBA2" --asset "BODY.HQR:1" --out out\body-001
```

The export writes an OBJ mesh, MTL file, JSON evidence manifest, and texture PNGs
when `RESS.HQR` palette/atlas data is available.

The frontend can export the selected catalog model with the **Export** button.
It asks the backend to open an output-folder picker, then writes the same bundle
as the CLI path.

Use triangulated faces when comparing against the Three.js render path:

```powershell
lba2-lm2-viewer export --asset-root "C:\LBA2" --asset "BODY.HQR:1" --out out\body-001-tri --polygon-mode triangulated
```

## Contract Probe

Write a versioned model contract JSON file for one catalog model:

```powershell
lba2-lm2-viewer contract --asset-root "C:\LBA2" --asset "BODY.HQR:1" --out out\body-001.contract.json
```

Contracts live under `lba2_lm2_viewer.contracts` as `msgspec.Struct` types and
emit plain JSON with schema version `lm2_model_contract.v0`. The current draft
includes source identity, geometry facts, render facts, animation placeholders,
gameplay placeholders, evidence references, confidence, and unknown-field
descriptors.

## Animation Evidence Probe

Write decoded ANIM records and one deterministic frame-step sample:

```powershell
lba2-lm2-viewer animation --asset-root "C:\LBA2" --asset "ANIM.HQR:1" --body-asset "BODY.HQR:1" --out out\anim-001.evidence.json --sample-frame 1 --previous-frame 0 --elapsed-ms 50
```

The JSON uses schema version `lm2_animation_evidence.v0`. It preserves raw
keyframe and boneframe values, records the decoded header and summary, applies
the recovered `0040ce90` wrapped 12-bit rotation and `0040cf10` signed-linear
interpolation rules, and can record BODY bone-count compatibility. It is an RE
evidence artifact, not a runtime asset.

## Animation Frame Stepping

After indexing HQR files, select a BODY model and a decoded `ANIM.HQR` entry in
the explorer. The Animation panel can pose the selected BODY at a target
keyframe and elapsed time, or step to the previous/next frame. The backend owns
the BODY + ANIM transform path and returns normal model JSON with posed
vertices plus pose metadata for inspection.

## ANIM3DS Cataloging

`ANIM3DS.HQR` entries are intentionally not semantically decoded yet. The
catalog records each non-empty entry as raw animation evidence with decoded
size, decoded SHA-256, header words, raw parse status, and unknown descriptors
for byte ranges. Descriptors include offset, length, SHA-256, confidence, and a
note instead of embedding raw game bytes.

## Texture And UV Inspector

The frontend includes a read-only UV inspector for the loaded model. It shows
per-polygon material, render flags, UV group, sampled atlas region, UV points,
sampled colors, and currently unknown polygon flags. The atlas preview highlights
the selected UV group and polygon UV outline when texture atlas data is loaded.

The inspector can copy the selected polygon evidence JSON or download it as a
small local JSON file. It does not edit UVs or write game assets.

## Package

Create release artifacts:

```powershell
py -3 .\scripts\package.py
```

The script writes:

- `release/lba2-lm2-viewer.zip`
- a wheel in `release/`

`build/` and `release/` are generated outputs and are ignored by Git.

## Important Files

| Path | Read first when... |
| --- | --- |
| `README.md` | You need quick setup and run commands |
| `docs/plans.md` | You need source-of-truth milestones and decisions |
| `docs/architecture.md` | You need subsystem boundaries and target module shape |
| `docs/implement.md` | You are about to make code changes |
| `frontend/PLAN.md` | You need older frontend-local planning context |
| `AGENTS.md` | You need project-specific agent rules |
| `ISSUES.md` | You need known confusion points and traps |

## Asset Selection

The app supports:

- `Choose folder...` for a full LBA2 asset directory.
- `Choose HQR files...` for selected archive decoding.

Expected asset files include:

- `BODY.HQR`
- `ANIM.HQR`
- `ANIM3DS.HQR`
- `RESS.HQR`

Other assets may be cataloged only when they support model, animation, render, or
contract evidence.

## Common Troubleshooting

### Frontend build missing

Run:

```powershell
py -3 .\scripts\build.py
```

The backend serves `lba2_lm2_viewer/frontend/dist/`, not `frontend/dist/`.

### Console command not found

Use:

```powershell
py -3 -m lba2_lm2_viewer
```

or ensure the Python scripts directory is on `PATH`.

### Vite chunk-size warning

The frontend bundle can exceed Vite's warning threshold because Three.js is in
the local app bundle. This is acceptable until startup latency becomes a measured
problem.

### Real asset output in Git

Do not commit generated exports from real game assets. Commit synthetic fixtures
and metadata only.
