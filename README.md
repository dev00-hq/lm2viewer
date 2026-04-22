# LBA2 LM2 Viewer

Standalone LM2 model explorer for Little Big Adventure 2 assets.

This package does not include decoded models, animations, textures, or HQR data. It ships only the decoder, backend, and viewer. At runtime you select your own LBA2 asset folder, and the tool scans the HQR files locally.

## Requirements

- Python 3.10+
- A local copy of the LBA2 HQR files
- Node.js for source checkouts, development, and release packaging

## Run

Source checkouts do not commit the built frontend. Build it once before running:

```powershell
cd frontend
npm install
npm run build
cd ..
```

Then start the backend:

```powershell
py -3 .\viewer.py
```

Then use **Choose folder...** in the app and select the folder that contains files such as `BODY.HQR`, `ANIM.HQR`, `ANIM3DS.HQR`, and `RESS.HQR`.

You can also start with a known folder:

```powershell
py -3 .\viewer.py --asset-root "D:\Games\LBA2"
```

The server defaults to `http://127.0.0.1:8765`.

Packaged releases already include `frontend/dist`, so they only need Python and your local LBA2 asset files.

## What Is Decoded

- LM2 body models from HQR entries
- LBA2 animation summaries from `ANIM.HQR`
- raw `ANIM3DS.HQR` payload metadata when the current animation decoder does not understand the entry
- palette and texture atlas data from `RESS.HQR`

Decoded model and animation payloads are kept in memory for viewing. They are not written to the package directory.

## Development

Frontend source lives in `frontend/`.

```powershell
cd frontend
npm install
npm run build
```

The Python backend serves `frontend/dist/`, but that generated folder is intentionally ignored by Git.

Run the Python tests from the repository root:

```powershell
py -3 -m unittest discover -s tests -v
```

Run the frontend build from `frontend/`:

```powershell
npm run build
```

## Release Package

Create a self-contained zip with the Python runtime files and built frontend:

```powershell
py -3 .\scripts\package.py
```

The script runs `npm ci`, builds the frontend, copies runtime files into `build/lba2-lm2-viewer/`, and writes `release/lba2-lm2-viewer.zip`.
