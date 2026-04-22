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
- HQR, BODY/LM2, palette, texture atlas, and animation-summary paths exist.
- Export probes, contracts, full animation decode, frame stepping, and UV
  inspector are planned.

Milestone status is tracked in `docs/plans.md`.

## Requirements

- Python 3.10 or newer
- Node.js and npm for source builds
- Local user-owned LBA2 assets

Python runtime dependencies are currently stdlib-only. If `msgspec` is added for
contracts, update packaging docs and dependency files in the same change.

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
