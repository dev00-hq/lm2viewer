# LBA2 LM2 Viewer

A local LM2 model viewer for Little Big Adventure 2 assets.

The project ships the decoder, Python backend, and browser frontend. It does not ship game data, decoded models, animations, textures, palettes, or HQR files.
When the app starts, you choose a folder or one or more HQR files from your own local LBA2 installation, and decoding happens on your machine.

## Requirements

- Python 3.10 or newer
- Node.js and npm for source builds
- A local copy of the LBA2 asset files

Installable Python dependencies are listed in both `pyproject.toml` and
`requirements.txt`.

## Build From Source

From the repository root:

```powershell
py -3 .\scripts\build.py
```

This is the normal one-command setup for developers. It:

- installs frontend dependencies with `npm ci`
- builds the Vite frontend into `lba2_lm2_viewer/frontend/dist/`
- installs the Python package in editable mode with `pip install -e .`

The generated frontend bundle is ignored by Git. It is rebuilt locally and
included only when packaging a release.

## Run

After building, start the viewer with the console command:

```powershell
lba2-lm2-viewer
```

If your Python scripts directory is not on `PATH`, use the module entry point:

```powershell
py -3 -m lba2_lm2_viewer
```

The server listens on `http://127.0.0.1:8765` by default and opens the browser viewer. In the app, use **Choose folder...** for a full asset directory or **Choose HQR files...** to decode only selected files.

You can also start with a known asset folder:

```powershell
lba2-lm2-viewer --asset-root "C:\LBA2"
```

The legacy source entry point is kept for convenience:

```powershell
py -3 .\viewer.py
```

## Expected Asset Files

The viewer can use these LBA2 files when they are present:

- `BODY.HQR` for LM2 body models
- `ANIM.HQR` for animation data
- `ANIM3DS.HQR` for 3D animation payload metadata
- `RESS.HQR` for palette and texture atlas data

You can select a whole folder containing those files or select individual HQR files when you only want to catalog part of the data.

## Development

Python source lives in `lba2_lm2_viewer/`. Frontend source lives in `frontend/`.
Root-level `viewer.py` and `lba_hqr.py` are compatibility wrappers around the package modules.

Run the full local build:

```powershell
py -3 .\scripts\build.py
```

Run only the frontend build:

```powershell
py -3 .\scripts\build.py --no-editable
```

Run the Python tests:

```powershell
py -3 -m unittest discover -s tests -v
```

During frontend-only work, you can use the Vite dev server from `frontend/`:

```powershell
npm run dev
```

The Python backend serves the built files from
`lba2_lm2_viewer/frontend/dist/`, so run the project build before testing the integrated backend/frontend path.

## Export Probe

Export one catalog model asset as an evidence bundle:

```powershell
lba2-lm2-viewer export --asset-root "C:\LBA2" --asset "BODY.HQR:1" --out out\body-001
```

The bundle contains OBJ, MTL, `manifest.json`, and texture PNGs when palette and
atlas data are available.

The browser viewer also exposes **Export** for the selected catalog model and
uses a backend folder picker for the output location.

## Texture and UV Inspector

The browser viewer includes a read-only UV inspector for the loaded model. It
shows polygon material, render flags, UV group, sampled atlas region, sampled
colors, and currently unknown polygon flags. The atlas preview highlights the
selected texture region and UV outline when atlas data is available.

You can copy or download the selected polygon evidence as JSON. The viewer does
not edit UVs.

## Contract Probe

Write a versioned model contract JSON file for one catalog model asset:

```powershell
lba2-lm2-viewer contract --asset-root "C:\LBA2" --asset "BODY.HQR:1" --out out\body-001.contract.json
```

Contracts are typed with `msgspec.Struct` in the Python package and emitted as
plain JSON. They capture reusable facts for the future port: source identity,
geometry, render facts, animation compatibility placeholders, gameplay-facing
placeholders, evidence references, confidence, and unknown-field descriptors.

## Release Package

Create release artifacts with:

```powershell
py -3 .\scripts\package.py
```

The package script rebuilds the frontend, copies runtime files into
`build/lba2-lm2-viewer/`, writes `release/lba2-lm2-viewer.zip`, and builds a wheel in `release/`.

Release artifacts include the built frontend. Source checkouts do not.

## Current Decoder Coverage

- LM2 body models from HQR entries
- animation summaries from `ANIM.HQR`
- raw `ANIM3DS.HQR` payload metadata for entries not yet fully decoded
- palette and texture atlas data from `RESS.HQR`

Decoded payloads are kept in memory for viewing and are not written back into the project directory.
