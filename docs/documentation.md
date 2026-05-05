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
- ANIM3DS entries are cataloged as sprite assets with decoded LSP frame stats
  and a dedicated frontend Sprite View when possible.
- `VIDEO/VIDEO.HQR` entries are cataloged as Smacker/ACF movie resources and
  scene `PLAY_ACF` script refs are reverse-indexed where the runtime name list
  resolves them.
- `SCENE.HQR` object records expose classic draw, sort, shadow, mask recovery,
  z-buffer/moving-box, background-copy, and condition comparator evidence for
  port work.

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

Write decoded ANIM records, canonical playback transitions, and one deterministic
frame-step sample:

```powershell
lba2-lm2-viewer animation --asset-root "C:\LBA2" --asset "ANIM.HQR:1" --body-asset "BODY.HQR:1" --out out\anim-001.evidence.json --sample-frame 1 --previous-frame 0 --elapsed-ms 50
```

To sample the playback loop-start transition, use:

```powershell
lba2-lm2-viewer animation --asset-root "C:\LBA2" --asset "ANIM.HQR:1" --out out\anim-001.evidence.json --sample-loop-transition
```

The JSON uses schema version `lm2_animation_evidence.v0`. It preserves raw
keyframe and boneframe values, records the decoded header and summary, applies
the recovered `0040ce90` wrapped 12-bit rotation and `0040cf10` signed-linear
interpolation rules, records the intro/loop playback transition table, and can
record BODY bone-count compatibility. It is an RE evidence artifact, not a
runtime asset.

## Animation Frame Stepping

After indexing HQR files, select a BODY model and a decoded `ANIM.HQR` entry in
the explorer. The Animation panel can pose the selected BODY at a target
keyframe and elapsed time, or step to the previous/next frame. The backend owns
the BODY + ANIM transform path and returns normal model JSON with posed
vertices plus pose metadata for inspection.

The playback endpoint returns a sampled sequence with explicit `sequence_index`,
`segment`, `timeline_ms`, `loop_index`, `playback_end_index`, and
`loop_cycle_root_delta` fields. The frontend uses those fields for repeat-off
stopping, scrubbing/resume identity, and world-motion loops. Static OBJ/model
contract exports stay independent of playback state and reload decoded model
bytes from the selected catalog asset.

## ANIM3DS Cataloging

`ANIM3DS.HQR` uses classic zero-based HQR indexing. Entry 127 is decoded as the
classic `T_ANIM_3DS` frame-range table: four name bytes, signed start frame, and
signed end frame per record. The catalog exposes ANIM3DS entries as `sprite`
assets, with entry 127 classified as `anim3ds-info` metadata. Raw ANIM3DS
sprite frames are linked back to their owning range when the table is available.

The individual ANIM3DS frame payloads decode as LSP sprites with width, height,
offsets, palette indices, pixel counts, and a dedicated frontend Sprite View.
Normal runtime sprites from `SPRITES.HQR` decode as LSP frames, while raw runtime
sprites from `SPRIRAW.HQR` decode through the classic raw scaled-sprite layout
used by `ScaleSprite`. Both use the Sprite View path. The catalog stores the
classic `InitSprite` backend resolution model: `SPRITE_3D |
ANIM_3DS` resolves to `ANIM3DS.HQR`, `SPRITE_3D` with `Sprite >= 100` resolves
to `SPRITES.HQR`, and `SPRITE_3D` with `Sprite < 100` resolves to
`SPRIRAW.HQR`. Known direct system/extra sprite ids from `COMMON.H`,
`GAMEMENU.CPP`, and `INVENT.CPP` are attached to sprite catalog entries as
code-reference provenance. Failed sprite decodes remain explicit raw/deferred
evidence. Real `ANIM.HQR` parse failures remain separate raw animation evidence with
`decode_status: parse_failed` and `parse_error`.

Sprite View is a separate main-area tab with its own 2D canvas. It displays
decoded sprite pixels with nearest-neighbor scaling, fit/zoom controls, runtime
backend facts, hotspot/bounds facts from the corresponding `RESS.HQR` ZV table,
previous/play/next/scrub controls for the owning ANIM3DS frame range, and pixel
palette-index hover readout. Playback uses catalog frame order for inspection;
original game timing is not currently decoded. The existing Model View canvas
remains the Three.js BODY/LM2 viewer and is not reused for sprite payloads.
Decoded sprite frames are exportable through the shared Export action. Normal
`SPRITES.HQR` and `SPRIRAW.HQR` frames write a PNG, a one-cell sheet PNG, and a
manifest with runtime index/hotspot context. Selecting an `ANIM3DS.HQR` frame
exports every frame in its decoded range as individual PNGs plus a deterministic
fixed-cell sheet, preserving the frame offsets in the manifest.

## Fixed Objects

`OBJFIX.HQR` uses classic zero-based runtime ids through
`GivePtrObjFix(index)`. The catalog ids therefore match source constants and
inventory table values directly. Known inventory, extra, dart, and protection
object ids from `INVENT.CPP`, `COMMON.H`, `DART.H`, and `INVENT.H` are attached
to decoded OBJFIX model entries as direct code-reference provenance.

The Runtime Sprite inspector accepts runtime object fields (`Flags`, `Sprite`,
optional `Obj.Body.Num`, object slot, and `LabelTrack`) and resolves them through
the same server-side `InitSprite` model. When the resolved asset exists in the
loaded catalog, the inspector can open it directly in Sprite View. The
`Obj.Body.Num` value is treated as the runtime mirror of `Sprite` after
`InitSprite` applies a projected sprite; mismatches are reported instead of
hidden.

## Scene Object Render Contract

Scene catalog detail includes object render-pipeline and render-contract counts
derived from `OBJECT.CPP::AffScene` and `AffOneObject`. The parser distinguishes
flag presence from effective redraw behavior: `OBJ_ZBUFFER` and `OBJ_IN_WATER`
produce moving-box recovery only for visible BODY objects and non-clipped
projected sprites, while `SPRITE_CLIP` and `ANIM_3DS` projected sprites recover
through `DrawRecover3`. `OBJ_BACKGROUND` is exposed as both an object-only
presence probe and an all-scene `Log` to `Screen` copy after draw. The background
composition preview still intentionally stops before sorted object, extra, dart,
and incrust overdraw. Scene detail also aggregates redraw methods, so the
mask/z-buffer burden can be scanned as `DrawRecover`, `DrawRecover3`, and
`DrawOverBrickCage + BoxMovingAdd` counts before inspecting individual objects.

Scene detail also carries a frame-level render contract. It names the `AFF_ALL`
decor refresh and `CopyScreen(Log, Screen)` setup, scene object tree insertion,
runtime `ListExtra`/`ListDart`/`ListPartFlow` sorted-tree insertion, `BaseSort`
draw/restart behavior, exterior rain, and `ListIncrustDisp` overlays. Those
dynamic runtime lists are not SCENE.HQR records, so they are exposed as required
port-renderer phases rather than as decoded scene assets. Each dynamic source
also carries structured owner, insertion-stage, sorted-tree type, asset-backing,
and preview/export limitation fields.

Object runtime summaries aggregate collision participation, `SRot` conversion
paths, and combat/bonus initialization. This distinguishes
object/brick/zone/code-jeu/floor collision requirements, separates direct
sprite/wagon rotation fields from the non-sprite `51200 / SRot` divisor, and
shows how many objects start alive, armored, damaging, or bonus-bearing.

Zone detail separates authored scene bytes from the runtime state created by
`LoadScene`. The catalog shows post-load `Info7` zone flags for change-cube and
camera zones, post-load `Info1` active state for ladder and rail zones, reset
giver/hit timer fields, and the life-script opcodes that can toggle those zone
states. Change-cube zones expose `GereZoneChangeCube` transition gates and
`NewCube`/`NewPosX/Y/Z`/beta/readjust rules. GRM zones expose `LM_SET_GRM`
on/off transitions, `IncrustGrm`/`DesIncrustGrm`, `Info2` state, and redraw
flags. Camera zones also expose the `SetZoneCamera` state application rule for
interior and exterior cubes. Message zones link to their associated camera zone
when `Info1` matches a camera zone `Num`, and expose the `GereZoneMessage`
facing-angle gate: the `GetAngle2D` points selected by north/south/east/west,
the `Obj.Beta` condition, the south wrap-around case, and the `Dial(zone.Num,
TRUE)` call. Giver zones expose the `ZoneGiveExtraBonus` trigger gate,
`WhichBonus(Info0)` selection rule, zone-center spawn call, count/taken fields,
and successful-spawn state mutation. Hit zones expose the `HitObj` gate,
force/enabled field, cooldown timer math, timer clear rule, and
`LM_SET_HIT_ZONE` script control. Ladder, escalator, and rail zones expose
`PtrZoneClimb`, `CodeJeu`/`DONT_PICK_CODE_JEU`, `PtrZoneRail`, active fields,
and script controls where those mechanics are source-backed. Scenario zones
expose `ZoneSce` writes and `LF_ZONE`/`LF_ZONE_OBJ` readback. Scene detail
also summarizes these source-backed mechanics as zone contract counts, so a
scene can be scanned for represented runtime contracts without opening each
zone row.

Full parser output keeps complete script target/link evidence for backend
aggregation. The browser catalog response intentionally samples bulky per-object
script lists after aggregate counts and reverse links are computed: scene object
detail keeps representative link/instruction lists plus `*_total` counters, and
large scenes expose the first 24 object records while retaining the full
`sampled_object_count`.

Script detail also groups selected source-backed runtime opcodes into execution
contracts: object death, life/track pass control, animation and ANIM3DS waits,
body visibility, behavior save/restore, background incrust redraw toggles, ACF
playback with its post-cinematic `AFF_ALL` redraw request, terminal game-flow
actions, and sample parameter writes. These counts identify port obligations
without claiming full script execution or branch semantics.
Life-script condition operands are also aggregated by `LF_*` function, return
type, and `LT_*` comparator, which exposes scene dependencies on runtime
readers such as zones, variables, animation state, inventory, and object
geometry while preserving the boundary that branches are not executed offline.

## Sample Audio

`SAMPLES.HQR` catalog ids use the zero-based runtime sample id. The underlying
HQR table slot is `runtime id + 1`, matching the classic `HQF_Init`/`HQR_Get`
sample path. Decoded sample resources expose RIFF/WAVE format, rate, channel,
duration, data-size, and resource-header metadata. Scene script and ambience
references are reverse-indexed to sample assets when present; missing referenced
ids are listed with their expected HQR table slot and classified as unresolved
archive slots or ids outside the loaded table. The local extracted/reference
sample archives checked so far are byte-identical, and all scene-referenced
missing ids are empty HQR slots rather than decode failures. The shared Export
action writes the decoded RIFF/WAVE file
plus a manifest with runtime id, HQR table index, resource header, and audio
metadata. Selecting a decoded sample also enables an in-browser audio control
that streams the same decoded WAVE payload from the loaded catalog asset.

## Screen Images

`SCREEN.HQR` uses classic zero-based PCR ids. Even entries are 640x480 indexed
screen images and odd `PCR+1` entries are paired 256-color palettes. Selecting
an indexed screen image renders it in Sprite View with its paired palette.
Named PCR entries carry direct code-reference provenance for the classic menu,
logo, slate, CD-ROM wait, and publisher-logo call sites. Export writes a PNG
and manifest preserving the PCR id and palette pair.

## Indexed Resources

`RESS.HQR` indexed image payloads and the texture atlas can be opened in Sprite
View with `RESS.HQR:0` applied as the palette. Export writes a PNG and manifest
for the selected indexed payload while preserving source hashes and palette
provenance.

## Holomap Plans

`HOLOMAP.HQR` plan images are 640x480 indexed framebuffers selected by
`HOLOPLAN.CPP::InitHoloPlan`, with a paired parameter record carrying camera
and placement fields. Selecting a plan image renders it in Sprite View with
`RESS.HQR:0`; export writes a PNG plus variant and paired-parameter provenance.

## Text Bundles

`TEXT.HQR` payload banks export as JSON bundles for port use. Each record keeps
the paired order-table message id, `FlagDial` byte, decoded CP850 text, raw
record bytes, language/file metadata, and the `InitDial`/`FindText`/`GetText`
resolution rule used by the classic engine.

## Cinematic Video

`VIDEO/VIDEO.HQR` catalog ids use the zero-based runtime ACF index returned by
`PLAYACF.CPP::GetNumAcf`. Movie names come from `RESS.HQR:48`; the catalog
decodes each non-empty Smacker header with dimensions, frame count, timing
estimate, and HQR resource metadata. Scene `TM_PLAY_ACF` and `LM_PLAY_ACF`
references link back to movie assets when the name is present in the loaded
video archive. Export writes the original Smacker container plus a manifest with
ACF index/name, header metadata, scene usage, and source hashes. Codec frame and
audio decoding is intentionally not implemented yet.

## Scene Script Target Evidence

Scene script control-flow and cross-script target links report a target status,
not just found/missing. Resolved offsets are `instruction_start`. Unresolved
offsets retain their target byte evidence, including decoded-prefix length,
script byte length, and statuses such as `after_decoded_prefix`,
`inside_instruction_operand`, `outside_script`, or `missing_owner`. In the
current retail scene set, nested `LM_SWITCH` blocks are decoded with a stack,
and life scripts resume at later known branch/behavior targets when linear
layout crosses non-instruction byte islands. Same-script control-flow targets
all resolve. One cross-script target remains `outside_script` evidence, and the
only skipped byte islands are preserved with offset, length, hash, and reason.

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
| `lba2_lm2_viewer/server.py` | You need HTTP endpoints, static serving, or viewer session state |
| `frontend/src/ui/animationController.ts` | You need frontend animation pose, stepping, or playback state |
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

`RESS.HQR` catalog detail names the classic runtime identities for the known
effect tables: `RESS_FLOW` loads into `TabPartFlow`, `RESS_POF` into
`BufferPof`, and `RESS_IMPACT` into `BufferImpact`. Their envelopes are decoded;
field-level semantics remain explicit unknown evidence.

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
