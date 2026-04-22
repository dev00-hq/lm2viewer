# LBA2 LM2 Viewer

Standalone LM2 model explorer for Little Big Adventure 2 assets.

This package does not include decoded models, animations, textures, or HQR data. It ships only the decoder, backend, and viewer. At runtime you select your own LBA2 asset folder, and the tool scans the HQR files locally.

## Requirements

- Python 3.10+
- A local copy of the LBA2 HQR files
- Node.js for source checkouts, development, and release packaging

## Install From Source

Python runtime dependencies are stdlib-only, so `requirements.txt` is intentionally empty except for a note. Install the project in editable mode:

```powershell
py -3 .\scripts\build.py
```

That single command runs `npm ci`, builds the frontend into `lba2_lm2_viewer/frontend/dist/`, and installs the Python package in editable mode. Then start the backend:

```powershell
lba2-lm2-viewer
```

If your Python scripts directory is not on `PATH`, use the module entry point instead:

```powershell
py -3 -m lba2_lm2_viewer
```

Then use **Choose folder...** in the app and select the folder that contains files such as `BODY.HQR`, `ANIM.HQR`, `ANIM3DS.HQR`, and `RESS.HQR`.

You can also start with a known folder:

```powershell
lba2-lm2-viewer --asset-root "D:\Games\LBA2"
```

The server defaults to `http://127.0.0.1:8765`.

Packaged releases already include `frontend/dist`, so they only need Python and your local LBA2 asset files.

The legacy source command still works:

```powershell
py -3 .\viewer.py
```

## What Is Decoded

- LM2 body models from HQR entries
- LBA2 animation summaries from `ANIM.HQR`
- raw `ANIM3DS.HQR` payload metadata when the current animation decoder does not understand the entry
- palette and texture atlas data from `RESS.HQR`

Decoded model and animation payloads are kept in memory for viewing. They are not written to the package directory.

## Development

Frontend source lives in `frontend/`, and Python code lives in `lba2_lm2_viewer/`.

```powershell
py -3 .\scripts\build.py
```

The Python backend serves `lba2_lm2_viewer/frontend/dist/`, but that generated folder is intentionally ignored by Git.

Run the Python tests from the repository root:

```powershell
py -3 -m unittest discover -s tests -v
```

Run only the frontend build without reinstalling the editable Python package:

```powershell
py -3 .\scripts\build.py --no-editable
```

## Release Package

Create a self-contained zip with the Python runtime files and built frontend:

```powershell
py -3 .\scripts\package.py
```

The script runs the project build, copies runtime files into `build/lba2-lm2-viewer/`, writes `release/lba2-lm2-viewer.zip`, and builds a wheel in `release/`.
