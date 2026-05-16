# Roadmap To Static

## Decision

Convert the viewer into a Cloudflare Pages deployable static app by moving the
viewer runtime into the browser. Do not keep the Python HTTP server as a second
runtime path for the hosted app, and do not preserve `/api/*` as a compatibility
facade.

Recommended path: Pyodide-first worker spike, then keep Pyodide only where it
proves fast and reliable. Port hot or brittle paths to TypeScript behind the
same browser service boundary.

This is not a Vite deployment task. The current frontend bundle is static, but
the product behavior is owned by Python session state and Python endpoints.

## Goals

- Deploy the app as static HTML, CSS, and JavaScript on Cloudflare Pages.
- Let users choose their own local LBA2 files in the browser.
- Keep game data local to the user's browser. Do not ship retail assets.
- Preserve the current evidence workbench workflows where technically viable:
  catalog, graph selection, model view, sprite/resource previews, animation
  posing/playback, audio playback, and evidence exports.
- Replace server-side filesystem writes with browser downloads.
- Optimize for one canonical current-state implementation.

## Non-Goals

- No Python backend for the Cloudflare-hosted app.
- No compatibility bridge that silently falls back from browser runtime to
  `/api/*`.
- No server path input, native Python file dialogs, or local server export
  directory picker in the hosted app.
- No full precomputed retail catalog shipped with the site.
- No JSON-only viewer as the primary product unless the goal explicitly changes
  to viewing previously exported evidence bundles.

## Evidence From Current Code

- `frontend/src/api.ts` is a live server API client. It calls `/api/upload`,
  `/api/path`, `/api/catalog/build`, `/api/catalog/search`,
  `/api/catalog/load`, `/api/catalog/export`, `/api/catalog-graph/*`,
  `/api/animation/*`, `/api/entity/*`, `/api/runtime/sprite-resolve`,
  `/api/catalog/audio`, `/catalog.json`, and `/model.json`.
- `frontend/vite.config.ts` proxies `/api`, `/catalog.json`, and `/model.json`
  to `http://127.0.0.1:8765`, which confirms the dev frontend assumes a local
  backend.
- `lba2_lm2_viewer/server.py` owns mutable session state: asset root, catalog,
  catalog graph, palette, texture atlas, scene preview cache, decode progress,
  and last model.
- `ViewerServer.set_asset_root()` and `set_asset_files()` call
  `build_catalog()`, build graph state, load palette and texture atlas, and
  return compact catalog responses.
- `lba2_lm2_viewer/viewer.py::build_catalog()` does much more than scan files:
  it decodes archives, classifies entries, enriches scene runtime/script/text,
  sample, video, background, GRM, and usage links, builds coverage, and compacts
  scene payloads.
- `ISSUES.md` records that a full retail `/catalog.json` response once reached
  about 2.15 GB. Static conversion must use compact and query-oriented data
  shapes, not one giant startup JSON.

## Architecture Target

Introduce a browser-owned runtime spine:

1. `frontend/src/runtime/assetSession.ts`
   Owns the current selected files, archive registry, catalog, graph indexes,
   palette, texture atlas, object URLs, and cache handles.

2. `frontend/src/runtime/viewerService.ts`
   Replaces `frontend/src/api.ts` as the canonical domain boundary. It exposes
   methods like `buildCatalogFromFiles`, `searchCatalog`, `loadCatalogAsset`,
   `poseAnimation`, `loadAnimationSequence`, `resolveRuntimeSprite`,
   `loadEntityWorkflow`, `exportCatalogAsset`, and `catalogAudioUrl`.

3. `frontend/src/runtime/decoder.worker.ts`
   Runs heavy decode/catalog/animation/export work off the main thread. Progress
   is delivered by worker messages, replacing `/api/decode/progress`.

4. Browser storage
   Use IndexedDB only as an optional acceleration cache. The source of truth is
   the user's selected local files for the current session.

5. Downloads and object URLs
   Use `Blob`, object URLs, and ZIP downloads for generated assets. Revoke object
   URLs when the active session changes.

## Strategy Comparison

| Strategy | Strength | Hard Objection | Decision |
| --- | --- | --- | --- |
| Pyodide-first | Reuses the mature Python decoder and reduces parity drift. | Browser runtime still needs new file, worker, export, and state boundaries. Pyodide startup, memory, and `msgspec` packaging must be proven. | Use as first spike with strict gates. |
| Pure TypeScript port | Clean long-term browser-native implementation. | Reimplements the evidence pipeline, including HQR indexing traps, catalog enrichment, graph/entity behavior, animation interpolation, and exports. | Do not start here unless Pyodide fails. Port narrow hot paths later. |
| Precomputed JSON-only | Fastest way to host static evidence snapshots. | Changes the product. Users cannot bring arbitrary local HQR files from anywhere without running Python elsewhere first. Full JSON can also be enormous. | Optional secondary evidence-gallery mode only. |

## Capability Matrix

| Current API surface | Current owner | Static replacement |
| --- | --- | --- |
| `fetchCatalog`, `/catalog.json` | Server compact catalog response | Browser session catalog with paged/query views |
| `fetchInitialModel`, `/model.json` | Server last-model state | Remove startup fetch; show empty state until user selects local files |
| `fetchDecodeProgress` | Python `DecodeProgress` | Worker progress messages |
| `uploadModel` | Multipart upload to Python parser | Direct `File.arrayBuffer()` decode in worker |
| `loadPath` | Server reads arbitrary local path | Remove UI and code path |
| `buildCatalog` | Server path scan | Browser folder/file selection and worker catalog build |
| `pickCatalogFolder`, `pickCatalogFiles` | Tk dialogs in Python | Browser file/folder input controls |
| `searchCatalog` | Server catalog search | Local indexed search over browser catalog |
| `loadCatalogAsset` | Server rereads HQR payloads on demand | Browser archive registry reads selected `File` blobs |
| `loadCatalogGraphSelection` | Python catalog graph | Browser graph index/projection |
| `loadCatalogGraphCompatible` | Python graph compatibility | Browser graph compatibility query |
| `resolveRuntimeSprite` | Python runtime resolver | Browser runtime resolver using catalog indexes |
| `load*EntityWorkflow` | Python entity builders | Browser entity workflow builders |
| `exportCatalogAsset` | Server writes files/directories | ZIP or direct `Blob` downloads |
| `catalogAudioUrl` | `/api/catalog/audio` stream | Object URL from decoded WAV bytes |
| `poseAnimation` | Python BODY/ANIM parse and pose | Worker pose call, Pyodide first |
| `loadAnimationSequence` | Python sequence builder | Worker sequence call, Pyodide first |
| `fetchPortPromotionPackets` | Reads sibling repo from disk | Bundle committed static data or remove from hosted app |

## Phased Plan

### Phase 0: Static Boundary Audit

Deliverables:

- Create the `runtime/viewerService` interface mirroring domain operations, not
  HTTP endpoints.
- Add a build check or test that fails when production static code imports
  `fetch('/api` paths.
- Decide whether port promotion packets are in scope for hosted static use.

Exit criteria:

- `frontend/src/api.ts` has a documented replacement plan by method.
- The app has one intended static runtime boundary, not a fake HTTP adapter.

### Phase 1: Pyodide Worker Spike

Deliverables:

- Build a throwaway worker that loads Pyodide and imports the current Python
  package.
- Run synthetic fixture operations:
  - HQR table parse through `lba_hqr.parse_table` and `parse_classic_table`.
  - LM2 decode through `load_lm2_bytes`.
  - ANIM parse plus one pose through `pose_lm2_model`.
  - Minimal catalog build over a tiny synthetic asset set.
- Measure startup time, memory, decode latency, payload size, and dependency
  failures, especially `msgspec`.

Exit criteria:

- If Pyodide imports and fixture parity pass within acceptable latency/memory,
  keep Pyodide as the first implementation bridge.
- If Pyodide fails import, packaging, or runtime-cost gates, port the narrow
  decoder spine to TypeScript first: HQR, LM2, palette/atlas, ANIM pose.

Phase 1 result:

- Passed on 2026-05-16 using `npm run spike:pyodide`.
- The spike mounted the current `lba2_lm2_viewer` Python package sources into a
  Pyodide worker-style runtime and ran synthetic HQR regular/classic table
  parsing, LM2 decode, ANIM parse plus pose, and minimal selected-file catalog
  build.
- Measured in the local Node worker harness: Pyodide startup about 883 ms,
  source package about 955 KB across 15 source/data files, fixture operation
  batch about 328 ms, and process RSS about 177 MB.
- `msgspec` installed and imported in Pyodide 0.29.4 as version 0.19.0.
- Recalibration: keep Pyodide as the first implementation bridge for browser
  worker runtime. Do not start the narrow TypeScript HQR/LM2/ANIM port unless
  later browser-memory, startup, or responsiveness gates fail on larger data.
  Keep the service boundary stable so hot-path TypeScript ports can replace
  individual worker operations later.

### Phase 2: Browser Asset Input

Deliverables:

- Replace `HQR Folder` Windows path input with browser-native file/folder
  selection.
- Remove `Server Path` UI and `loadPath` code.
- Support:
  - Single `.lm2`/`.ldc` file decode.
  - Multiple selected `.HQR` files.
  - Folder selection where supported by the browser.
- Build an archive registry keyed by normalized archive name and entry index.

Exit criteria:

- A selected local model file renders without any `/api/*`, `/catalog.json`, or
  `/model.json` request.
- Selected HQR files can be listed and indexed in browser session state.

Phase 2 result:

- Passed on 2026-05-16 against local static preview `http://127.0.0.1:4174/`.
- `viewerService.decodeModelFile` now transfers local model bytes to a
  Pyodide-backed `decoder.worker`, calls `viewer.load_lm2_bytes(...)`, and
  returns `to_viewer_json(...)` to the existing Three.js render path.
- `viewerService.buildCatalogFromFiles` filters selected browser files to HQR
  archives, writes them into the worker filesystem with relative paths
  preserved, and calls `viewer.build_catalog(..., selected_files=...)`.
- Static build prepares a generated Python source manifest plus local Pyodide
  runtime assets under `/pyodide/`; the generated files are ignored and rebuilt
  by `npm run prepare:static-runtime`.
- Validation used a synthetic triangle `.ldc` and synthetic `BODY.HQR`: model
  decode returned 3 vertices and 1 polygon, HQR catalog summary reported 1
  model across 1 HQR file, and the browser observed no retired server requests
  to `/api/*`, `/catalog.json`, or `/model.json`.
- Recalibration: Phase 3 can build on the same worker bridge, but must avoid
  returning a full retail catalog/graph payload. Add query-first catalog APIs
  before validating large roots.

### Phase 3: Catalog And Graph Runtime

Deliverables:

- Move catalog build into the worker.
- Keep startup catalog compact and query-first. Do not materialize a full graph
  projection into one startup payload.
- Move search, detail lookup, graph selection, graph compatibility, edge/usages
  queries, and runtime sprite resolution behind `viewerService`.
- Preserve known HQR indexing rules from `ISSUES.md`: classic zero-based
  archives, regular one-based archives, runtime sample ids, ANIM3DS frame table,
  TEXT pairing, and archive-specific classification order.

Exit criteria:

- Full retail roots do not require a multi-GB startup object.
- Explorer search, selection, graph compatibility, and basic entity trails work
  from browser-owned state.

Phase 3 result:

- Passed on 2026-05-16 against local static preview `http://127.0.0.1:4175/`
  with synthetic `BODY.HQR` and `ANIM.HQR`.
- Catalog search and detail lookup now operate locally over the current browser
  session catalog in `viewerService`, not through HTTP.
- Graph selection and compatibility queries run inside the Pyodide worker against
  the current catalog. The startup catalog is not expanded with the full graph
  projection; graph work is queried on demand.
- Explorer search found the selected synthetic BODY asset, clicking it loaded
  the model from the selected HQR through the worker, hydrated active selection
  evidence, and populated the compatible animation picker with the synthetic
  one-bone `ANIM.HQR:1` result.
- Validation observed no retired server requests to `/api/*`, `/catalog.json`,
  or `/model.json`.
- Recalibration: keep query-first graph APIs. Full retail validation still needs
  a memory/startup-payload measurement before treating Phase 3 as proven at
  production scale.

### Phase 4: Visual Asset Loading

Deliverables:

- Move on-demand model, sprite, resource, scene-background preview, palette,
  texture atlas, and audio payload loading into the worker/session.
- Convert audio playback to object URLs.
- Preserve resource and scene preview ownership semantics: previews may reuse
  sprite rendering internals, but active selection remains the owning resource
  or scene.

Exit criteria:

- Model, sprite, indexed image, resource, scene-background, and sample audio
  selections render without server calls.
- Object URLs are revoked on session reset.

Phase 4 result:

- Passed on 2026-05-16 against local static preview `http://127.0.0.1:4175/`
  with synthetic `BODY.HQR`, `ANIM.HQR`, `SPRITES.HQR`, `LBA_BKG.HQR`, and
  `RESS.HQR`.
- The worker now creates a browser-local visual session after catalog build,
  preserving the current Python server payload shapes for model palette/atlas
  context, sprite frames, scene background previews, and resource previews.
- Static e2e uploaded local HQR files and selected a model, an LSP sprite, a
  BRK `bkg_affgraph` resource, and a BKG grid preview without calls to
  `/api/*`, `/catalog.json`, or `/model.json`.
- Sample audio assets now return browser `Blob` object URLs, and those URLs are
  revoked/replaced on catalog rebuild. The static e2e confirmed the audio player
  receives a `blob:` URL and that a rebuild replaces the URL.
- Recalibration: keep the worker-local visual session for now because it
  avoids duplicating mature BKG and scene preview logic. Indexed image branches
  are wired but still need explicit e2e fixtures. Add a committed static e2e
  harness before expanding into larger phases.

Guardrail result:

- Passed on 2026-05-16 with `npm run test:e2e:static`.
- Removed the Vite dev proxy for `/api`, `/catalog.json`, and `/model.json`,
  and removed the frontend `dev:viewer` script that advertised the retired
  backend validation path.
- Added a committed Playwright static-runtime spec that builds synthetic HQR
  fixtures, serves the built static bundle with `vite preview`, verifies no
  retired HTTP routes are requested, and exercises model, sprite, resource,
  BKG grid, sample audio, and animation paths.

### Phase 5: Animation Runtime

Deliverables:

- Move `poseAnimation` and `loadAnimationSequence` behind worker calls.
- Preserve the current animation correctness traps from `ISSUES.md`:
  rounded 16.16 interpolation, loop segment behavior, sequence indexes, root
  motion, and File3D compatibility allow-lists.
- Cache sequence results per BODY/ANIM pair and step size inside the session.

Exit criteria:

- Manual pose and playback match Python fixture outputs for representative
  BODY/ANIM pairs.
- Playback does not freeze the Three.js UI.

Phase 5 result:

- Passed on 2026-05-16 with `npm run test:e2e:static`.
- `viewerService.poseAnimation` and `loadAnimationSequence` now call the
  Pyodide worker. The worker reuses the existing Python
  `ViewerServer.pose_catalog_animation*` methods so compatibility checks,
  loop segment indexing, sequence indexes, root motion, and pose payload shapes
  stay aligned with the current canonical implementation.
- The committed static e2e selects a compatible synthetic `BODY.HQR`/`ANIM.HQR`
  pair, applies a pose, loads a playback sequence, and confirms the animation
  sequence strip appears without `/api/*`, `/catalog.json`, or `/model.json`.
- Recalibration: Phase 6 exports can build on the same worker/session bridge.
  Runtime sprite and entity workflow stubs are still hidden workbench gaps and
  should be closed before deploy-readiness validation.

### Phase 6: Browser Exports

Deliverables:

- Convert server file exports into browser downloads.
- Prefer a single ZIP per export action for multi-file evidence bundles.
- Replace messages like `Wrote N files to exports/...` with download-focused
  status text.
- Preserve manifest provenance, but remove local filesystem paths that only
  make sense on the old server.

Exit criteria:

- Model OBJ/MTL/manifest, sprite PNG/sheet/manifest, sample WAV/manifest,
  indexed image PNG/manifest, text JSON, Smacker passthrough, and scene/BKG
  preview exports download in browser where supported.

Result:

- Added a Pyodide worker `exportCatalogAsset` request that reuses
  `ViewerServer.export_catalog_asset()` and zips the generated evidence files
  with Python `zipfile`, so browser exports keep the canonical Python manifest
  and exporter semantics without server directory writes.
- Replaced export UI copy with download-focused status text and kept evidence
  artifact selections tied to a `browser-download:<zip>` provenance string.
- Extended the committed static Playwright e2e to assert a model export ZIP is
  downloaded, has a ZIP header, and does not hit retired `/api/*`,
  `/catalog.json`, or `/model.json` routes.
- Recalibration: Phase 7 needs deploy-readiness validation plus static hosting
  documentation. Runtime sprite resolution and entity workflow stubs were found
  during review and moved into the worker before final deploy validation.

### Phase 7: Cloudflare Pages Deployment

Deliverables:

- Change Vite output to a frontend-owned static `dist` suitable for Cloudflare
  Pages.
- Remove Vite dev proxy assumptions for production.
- Add Cloudflare Pages build docs and a smoke test that serves static `dist`.
- Add browser validation for:
  - App loads from static server.
  - No network calls target `/api/*`, `/catalog.json`, or `/model.json`.
  - Single model file decode.
  - HQR catalog build from selected files.
  - One model selection render.
  - One export download.

Exit criteria:

- Static `dist` works from a local static server and from Cloudflare Pages.

Result:

- Changed Vite to emit the canonical hosted app at `frontend/dist` and added
  Cloudflare Pages `_redirects` and `_headers` static assets.
- Documented Cloudflare Pages settings in `README.md`: root directory is the
  repository root, build command is `cd frontend && npm ci && npm run build`,
  output directory is `frontend/dist`, and the hosted app has no backend routes.
- Tightened the Pyodide source packer so browser runtime sources exclude the
  HTTP handler route table and local picker/CLI entrypoints, while preserving
  the Python decoder/export runtime used by the worker.
- Added committed Playwright coverage for standalone model-file decode, HQR
  catalog build, model selection/render, animation pose/sequence, sprite and
  resource preview paths, sample audio object URLs, runtime sprite resolution,
  browser ZIP export, sanitized manifest provenance, and no retired route calls.
- Local validation: `npm run test:e2e:static` passed from `frontend/dist`, a
  Vite preview static server on `http://127.0.0.1:4179/` served the app with no
  console errors or retired network calls, the Pyodide spike passed, and the
  targeted compact-catalog Python unit test passed.
- Ready for the deploy step that needs a human to connect or trigger the
  Cloudflare Pages deployment. Remaining known risk: very large retail export
  bundles still pass through a base64 ZIP handoff, so full retail export memory
  should be observed after deployment or before broad public use.

## Validation Plan

- Add golden JSON fixtures from Python outputs before replacing each decoder
  path.
- Compare browser runtime outputs to Python fixture outputs for:
  - HQR table parsing.
  - LM2 model decode.
  - Palette and texture atlas decode.
  - Sprite frame decode.
  - Resource indexed image decode.
  - ANIM pose and sequence sampling.
  - Catalog compact projections and graph selection projections.
- Use agent-browser for UI validation after frontend changes.
- For full retail roots, measure catalog build time, peak browser memory where
  possible, startup payload size, and Explorer responsiveness.

## Risks And Gates

- Pyodide package gate: prove imports and `msgspec` availability before
  committing to Pyodide.
- Memory gate: full retail root cannot require loading every decoded payload and
  graph projection into one giant object.
- UI freeze gate: heavy decode/catalog/animation work must run in a worker.
- Export semantics gate: browser export is downloads, not directory writes.
- File access gate: browser sessions cannot use typed local paths.
- Parity gate: no TypeScript port lands without Python fixture comparison for
  the corresponding decoder behavior.

## Smallest Next Test

Move catalog search, detail lookup, and graph selection behind the browser
worker without materializing a full retail graph projection into the startup
catalog object. Validate with small synthetic HQR files first, then measure a
full retail root for catalog build time, startup payload size, and Explorer
responsiveness before expanding visual payload loading.
