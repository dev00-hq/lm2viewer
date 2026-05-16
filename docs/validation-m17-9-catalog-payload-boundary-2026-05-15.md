# M17.9 Catalog Payload Boundary Validation - 2026-05-15

## Environment

- Workspace: `D:\repos\reverse\lba2-lm2-viewer`
- Retail asset root: `D:\LBA2_cdrom\LBA2`
- Server: `py -3 -m lba2_lm2_viewer --asset-root D:\LBA2_cdrom\LBA2 --no-browser`
- Browser: Codex in-app browser at `http://127.0.0.1:8765/`

## Payload Checks

- `GET /catalog.json`
  - HTTP 200
  - 646,840 bytes
  - 0.682s
  - Previous observed payload before M17.9 was 2,156,373,462 bytes.
- `POST /api/catalog/search` with `q=twinsen`, `kind=model`, `limit=20`
  - HTTP 200
  - 12,889 bytes
- `POST /api/catalog-graph/selection` with `id=BODY.HQR:2`
  - HTTP 200
  - 1,160 bytes
- `POST /api/catalog-graph/compatible` with `model_id=BODY.HQR:2`
  - HTTP 200
  - 40,266 bytes
- `POST /api/catalog-graph/usages` with `id=BODY.HQR:2`, `limit=20`
  - HTTP 200
  - 165 bytes

## Browser Checks

- Startup renders the retail catalog summary:
  - 573 models
  - 2,082 decoded animations
  - 720 sprite assets
  - 222 scenes
  - 19,062 resources
  - 22,659 total catalog entries
- Explorer initially shows a bounded page of 260 entries and reports the full catalog total.
- Searching `saucer` finds `Piece of flying saucer model`.
- Selecting `Twinsen with tunic model` hydrates model detail and graph selection; Active Selection, Inspector geometry, compatible animations, and export action are present.
- Selecting `Piece of flying saucer model` follows backend graph/entity evidence to the linked scene object selection, showing graph-backed entity evidence instead of frontend inference.
- Browser console error log was empty.

## Automated Checks

```powershell
py -3 -m compileall lba2_lm2_viewer
py -3 -m unittest tests.test_catalog_graph -v
py -3 -m unittest tests.test_viewer_concurrency -v
py -3 -m unittest discover -s tests -v
npm run build
```

All commands passed. `npm run build` still reports the existing Vite chunk-size warning.
