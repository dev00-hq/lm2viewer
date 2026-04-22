# LBA2 LM2 Viewer Plans

## Project Mode

This is an existing codebase with a legacy-reference workflow.

The implementation lives in this repository. The original game runtime, classic
source, IDA/JS notes, and MBN tools are evidence sources, not codebases to copy
into this package.

## Product Boundary

The viewer is a reverse-engineering instrument until original BODY, ANIM,
ANIM3DS, and required RESS semantics are decoded with high confidence.

Export, metadata, and contract helpers are allowed when they produce reusable
facts for the port. They are not general authoring tools and must preserve
provenance.

This viewer is centered on model, animation, texture, palette, and
model-to-gameplay evidence. Other asset families may be cataloged or inspected
only when they explain model identity, animation selection, attachments, scene
usage, render behavior, or port-facing entity contracts.

## Authority Model

Use these sources in this order:

1. Original game runtime as behavioral and aesthetic oracle.
2. Classic source, IDA/JS notes, and MBN tools as evidence for layout, rendering,
   state, and edge cases.
3. This viewer and the port code as canonical modern implementations once backed
   by evidence.
4. New art pipeline as an optional replacement layer that preserves style and
   gameplay contracts.

The port should preserve meaningful behavior and asset semantics, not obsolete
renderer constraints.

## Current Baseline

- Python package: `lba2_lm2_viewer`
- Backend entry point: `lba2_lm2_viewer.viewer:main`
- Compatibility wrappers: root `viewer.py` and `lba_hqr.py`
- Frontend: Vite/TypeScript/Three.js under `frontend/`
- Built frontend target: `lba2_lm2_viewer/frontend/dist/`
- Tests: `unittest` under `tests/`
- Build command: `py -3 .\scripts\build.py`
- Release command: `py -3 .\scripts\package.py`

Generated frontend bundles, release zips, wheels, build folders, caches, and
local game assets are not source artifacts.

## In Scope

- HQR table and resource-entry decoding.
- BODY/LM2 model parsing and inspection.
- ANIM and ANIM3DS cataloging.
- RESS palette and texture atlas support needed by models.
- Texture/UV inspection and export probes.
- Animation semantic decode, frame stepping, and validated playback.
- Evidence manifests and contract probes for the future port.
- Small synthetic fixtures for tests and docs.

## Out Of Scope

- Shipping game data or decoded copyrighted assets.
- A general LBA2 asset browser.
- UV editing or mesh authoring inside the viewer.
- Production replacement-asset conversion before contracts stabilize.
- Broad scene, island, sound, text, video, or sprite tooling unless directly
  needed for model or animation evidence.
- Compatibility shims for old local states.

## Milestones

### M1: Parser and Catalog Baseline

Status: implemented.

Proof:

- HQR parser tests cover table indexing, resource decoding, compression, and
  selected-file catalog indexing.
- Catalog supports folder selection and selected HQR files.
- Backend serializes current model and animation summaries.

Validation:

```powershell
py -3 -m unittest discover -s tests -v
```

### M2: Frontend and Packaging Baseline

Status: implemented.

Proof:

- Single build command installs frontend dependencies, builds Vite output, and
  installs editable Python package.
- Release script builds both zip and wheel artifacts.
- `frontend/dist/` and package `frontend/dist/` are generated and ignored.

Validation:

```powershell
py -3 .\scripts\build.py
py -3 .\scripts\package.py
```

### M3: Model Evidence Exports

Status: planned.

Deliverable:

- CLI-first, frontend-ready export probe for a selected catalog asset.
- Output bundle: OBJ, MTL, shared atlas PNG, per-UV-group PNGs, and JSON evidence
  manifest.
- Default coordinate space: raw decoded/source coordinates.
- OBJ polygon modes: `original` and `triangulated`.

Design decisions:

- `OBJ + PNG + JSON` is the first external inspection target.
- OBJ is a Blender-friendly carrier, not the contract.
- PNG files carry texture evidence and tool convenience.
- JSON is the authoritative evidence manifest.
- glTF/GLB remains the likely future replacement-asset format, but not the first
  RE probe target.

### M4: Contract Draft

Status: planned.

Deliverable:

- Versioned `msgspec.Struct` contract types under the viewer package.
- Plain JSON export as the stable interchange artifact.
- Tiny synthetic contract fixtures committed for tests and examples.
- No committed exports from copyrighted game assets.

The first contract should include source identity, geometry facts, render facts,
animation facts, gameplay-facing facts, evidence references, confidence, and
unknown-field descriptors.

If this milestone adds `msgspec`, update `pyproject.toml`, `requirements.txt`,
and packaging docs together.

### M5: Texture and UV Inspector

Status: planned.

Deliverable:

- Read-only inspector panel for polygon, material, UV group, sampled atlas
  region, render flags, and unknowns.
- Atlas preview with selected-region highlight.
- Evidence copy/export affordance.

Do not build a UV editor. Use external tools such as Blender for UV editing
experiments.

### M6: Animation Semantic Decode and Frame Stepping

Status: planned.

Deliverable:

- Full ANIM record decode beyond current summaries.
- Tests for header, keyframe, boneframe, loop, and interpolation behavior.
- Evidence JSON for at least one known animation.
- Frame stepping for selected BODY + ANIM pairs.
- Continuous playback only after frame stepping matches MBN/original evidence.

Use the updated MBN model viewer decompilation as reference for animation header
layout, keyframe records, boneframe records, animation case handling, rotation
interpolation, linear interpolation, and body transform application.

### M7: ANIM3DS Track

Status: planned.

Deliverable:

- Catalog every ANIM3DS entry with parse status, size, hash, header words, and
  unknown descriptors.
- Add deeper decode only when source, MBN, or original runtime evidence identifies
  the semantic layout.
- Connect ANIM3DS entries to contracts once usage evidence is known.

ANIM3DS deep decode should not block the first validated BODY + ANIM frame
stepping path unless a selected reference model depends on it.

## Evidence Rules

- Parser and decoder fixes must leave permanent tests or fixtures when the bug
  can be reproduced from small synthetic input.
- Rendering, material, camera, and interaction fixes may use screenshot evidence
  plus a short note when automated visual tests would be brittle.
- Visual parity claims must cite their evidence source.
- If a real game asset is needed for manual proof, document the asset id and
  entry, but do not commit the decoded asset or screenshot unless project policy
  explicitly changes.

## Unknown Field Policy

Canonical manifests should not embed raw unknown bytes by default.

Unknown areas should be represented as descriptors:

- source section or field name
- offset
- length
- sha256
- confidence
- note
- related decoded fields, if any

Committed synthetic fixtures may include raw unknown bytes when tiny and needed
to prove parser behavior. Real game asset exports should not include raw unknown
bytes by default. A local-only `--include-raw-unknowns` option may write a
separate debug artifact, but raw dumps should not become part of the
authoritative manifest schema.

## Reference Set Policy

Track reference sets as metadata first, pointing to user-owned asset ids and
expected evidence categories.

The reference set should include:

- simple untextured model
- simple textured model
- model with transparency
- model with lines
- model with spheres
- model with multiple UV groups
- main character/body with known animation compatibility
- at least one failing or unknown-heavy edge case

## Extraction Strategy

Do not block export probes on a broad backend rewrite. Extract narrow reusable
modules as needed for the next capability.

New parser, texture, contract, and export code must be callable outside argparse
and HTTP routing. Each new capability should reduce `viewer.py` responsibility
instead of adding another subsystem to it.

## Validation Contract

Minimum validation before committing parser/backend changes:

```powershell
py -3 -m unittest discover -s tests -v
```

Minimum validation before committing frontend or packaging changes:

```powershell
py -3 .\scripts\build.py
```

Minimum validation before release-package changes:

```powershell
py -3 .\scripts\package.py
```

## Decision Log

- The viewer remains an RE instrument until core asset and animation semantics
  are trustworthy.
- Export helpers are evidence probes, not production asset pipeline outputs.
- First external inspection export target is `OBJ + PNG + JSON`.
- Blender and similar tools handle UV editing experiments.
- Raw decoded coordinates are the default export space.
- Export manifests keep unknown descriptors, not raw unknown bytes.
- Tool provenance should include package version, git commit when available,
  dirty state when available, generated timestamp, and command/options.
- Frontend render payloads and export manifests stay separate but derive from
  shared decoded structures.
- Animation playback is near-term only after structured decode and frame
  stepping are validated against MBN/original evidence.
