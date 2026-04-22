# LBA2 LM2 Viewer

Standalone LM2 model explorer for Little Big Adventure 2 assets.

This package does not include decoded models, animations, textures, or HQR data. It ships only the decoder, backend, and viewer. At runtime you select your own LBA2 asset folder, and the tool scans the HQR files locally.

## Requirements

- Python 3.10+
- A local copy of the LBA2 HQR files
- Node.js only if you want to rebuild the frontend

## Run

```powershell
py -3 .\viewer.py
```

Then use **Choose folder...** in the app and select the folder that contains files such as `BODY.HQR`, `ANIM.HQR`, `ANIM3DS.HQR`, and `RESS.HQR`.

You can also start with a known folder:

```powershell
py -3 .\viewer.py --asset-root "D:\Games\LBA2"
```

The server defaults to `http://127.0.0.1:8765`.

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

The Python backend serves `frontend/dist/`.

