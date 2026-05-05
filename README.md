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
- `OBJFIX.HQR` for fixed-object LM2 models used by inventory, extras, darts,
  and overlays
- `ANIM.HQR` for animation data
- `ANIM3DS.HQR` for 3D animation payload metadata
- `SPRITES.HQR` and `SPRIRAW.HQR` for projected runtime sprites
- `SCENE.HQR` for partial scene runtime reconnaissance and object render
  contract evidence
- `RESS.HQR` for palette and texture atlas data
- `VIDEO/VIDEO.HQR` for Smacker/ACF cinematic metadata

You can select a whole folder containing those files or select individual HQR files when you only want to catalog part of the data.
The current audited archive status is tracked in `docs/hqr-coverage.md`.

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

`TEXT.HQR` payload banks can also be exported as JSON bundles. The export pairs
each decoded text record with its order-table message id, `FlagDial` byte,
decoded CP850 text, raw bytes, and source hashes.

## Texture and UV Inspector

The browser viewer includes a read-only UV inspector for the loaded model. It
shows polygon material, render flags, UV group, sampled atlas region, sampled
colors, and currently unknown polygon flags. The atlas preview highlights the
selected texture region and UV outline when atlas data is available.

You can copy or download the selected polygon evidence as JSON. The viewer does
not edit UVs.

## Sprite View

Decoded projected sprite frames open in a separate **Sprite View** main area
tab. The catalog resolves all three runtime sprite backends:
`ANIM3DS.HQR` for `SPRITE_3D | ANIM_3DS`, `SPRITES.HQR` for normal
`SPRITE_3D` objects with `Sprite >= 100`, and `SPRIRAW.HQR` for normal
`SPRITE_3D` objects with `Sprite < 100`.

Sprite View uses its own 2D canvas with nearest-neighbor scaling, fit/zoom
controls, palette-index hover readout, runtime backend facts, hotspot/bounds
facts from `RESS.HQR`, direct code-reference provenance for known system/extra
sprite ids, and previous/play/next/scrub controls for decoded ANIM3DS frame
ranges. Playback uses catalog frame order for inspection;
original game timing is not currently decoded. The existing **Model View**
remains the Three.js BODY/LM2 model viewer.

The shared **Export** action also works for decoded sprite frames. Normal
runtime sprites export a PNG, sheet PNG, and manifest; ANIM3DS selections export
the whole decoded range as per-frame PNGs plus a fixed-cell sheet.

The **Runtime Sprite** inspector resolves an object-like state (`Flags`,
`Sprite`, optional `Obj.Body.Num`, object slot, and `LabelTrack`) through the
same backend model and can open the resolved catalog asset directly in Sprite
View. This is intended for live-run snapshots and port/editor debugging, not
for one-off evidence panels.

## Scene Render Contract

`SCENE.HQR` catalog detail exposes classic object draw and redraw evidence from
`AffScene`/`AffOneObject`: tree insertion, shadow handling, `DrawRecover` versus
`DrawRecover3`, z-buffer/water moving-box recovery, sprite clip recovery, and
`OBJ_BACKGROUND` copy behavior. It also names the scene-level frame order:
decor refresh, scene object insertion, runtime extras/darts/particle flows in
the sorted tree, rain, and incrust overlays. The frame contract keeps structured
dynamic-source records for each non-SCENE draw list so ports can model those
runtime phases without pretending they are archive records. Background previews still stop
before sorted object, extra, dart, flow, rain, and incrust overdraw. Zone detail
also shows `LoadScene` post-load state normalization for zone enable flags,
ladder/rail active state, giver state, hit-zone timers, change-cube transition
math, camera-zone application rules, message-zone camera plus facing-angle gates
from `GereZoneMessage`, and giver-zone bonus spawning rules from
`ZoneGiveExtraBonus`. Hit zones expose the
`HitObj` gate, force field, cooldown timer, and `LM_SET_HIT_ZONE` control.
Ladder, escalator, and rail zones expose their movement-side runtime pointers,
code-jeu writes, active fields, and script controls. GRM zones expose
`LM_SET_GRM` on/off transitions, fragment application/restoration, and redraw
flags. Scenario zones expose `ZoneSce` writes and `LF_ZONE`/`LF_ZONE_OBJ`
readback.
Large scene details use sampled per-object script lists with total counters so
the browser catalog stays usable on the full retail asset set.

## Sample Audio

`SAMPLES.HQR` entries are cataloged by zero-based runtime sample id. Decoded
RIFF/WAVE samples show format/rate/duration metadata, scene script and ambience
usage, and referenced missing ids classified by empty/undecoded slots versus
ids outside the archive table. Selecting a sample enables browser playback from
the decoded WAVE payload. Export writes the decoded `.wav` and a manifest
preserving the runtime id and HQR table slot.

`SCREEN.HQR` entries are cataloged by zero-based PCR id. Indexed 640x480 screen
images render in Sprite View with their paired palette. Named PCR entries include
classic menu/logo/slate call-site provenance, and export writes a PNG plus
manifest with the PCR image/palette pair.

`RESS.HQR` indexed image payloads and the texture atlas can also open in Sprite
View with `RESS.HQR:0` applied, and export as PNG evidence bundles.

`HOLOMAP.HQR` plan images render in Sprite View with `RESS.HQR:0` applied, and
export as PNG bundles that preserve the plan variant and paired parameter entry.

## Cinematic Video

`VIDEO/VIDEO.HQR` entries are cataloged by zero-based ACF index using movie
names from `RESS.HQR:48`. Decoded Smacker headers show dimensions, frame counts,
timing estimates, and reverse scene `PLAY_ACF` usage. Export writes the original
Smacker container with manifest provenance. The app does not decode or play
Smacker frames yet.

## Contract Probe

Write a versioned model contract JSON file for one catalog model asset:

```powershell
lba2-lm2-viewer contract --asset-root "C:\LBA2" --asset "BODY.HQR:1" --out out\body-001.contract.json
```

Contracts are typed with `msgspec.Struct` in the Python package and emitted as
plain JSON. They capture reusable facts for the future port: source identity,
geometry, render facts, animation compatibility placeholders, gameplay-facing
placeholders, evidence references, confidence, and unknown-field descriptors.

## Animation Evidence Probe

Write decoded ANIM records and one deterministic frame-step sample as JSON:

```powershell
lba2-lm2-viewer animation --asset-root "C:\LBA2" --asset "ANIM.HQR:1" --body-asset "BODY.HQR:1" --out out\anim-001.evidence.json --sample-frame 1 --previous-frame 0 --elapsed-ms 50
```

The evidence keeps raw keyframe and boneframe values, applies the recovered
12-bit wrapped rotation and signed-linear interpolation rules, and records
optional BODY bone-count compatibility. It does not write game assets into the
repository.

## Animation Frame Stepping

In the browser viewer, index the HQR folder, select a BODY model, then select a
decoded `ANIM.HQR` entry. The Animation panel poses the selected BODY at a
target keyframe and elapsed time, and provides previous/next frame stepping. The
backend applies the BODY + ANIM transform and returns regular viewer model JSON
with posed vertices.

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
- full ANIM record decode, CLI frame-step evidence, and viewer posed frame
  stepping from `ANIM.HQR`
- `ANIM3DS.HQR` frame-range metadata plus LSP sprite frame decode and Sprite
  View rendering for frame payloads, with raw/deferred evidence for failed
  decodes
- palette, texture atlas, File3D, sprite bounds, and named `RESS_FLOW`/`RESS_POF`/`RESS_IMPACT` runtime tables from `RESS.HQR`

Decoded payloads are kept in memory for viewing and are not written back into the project directory.
