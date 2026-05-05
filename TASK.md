# Task: Evidence Graph And Entity Workflow

## Working Thesis

The project is no longer just an LM2 model viewer. It is becoming a local LBA2
evidence workbench for answering port/editor questions:

> Given a runtime value, scene object, or asset id, what game mechanic does it
> represent, where is it used, which archive records back it, and what behavior
> must a port preserve?

The next task is to make that evidence graph explicit and usable instead of
continuing to add isolated catalog details.

## Problem

Current capabilities are broad but fragmented:

- Catalog search can find assets.
- Runtime Sprite can resolve a small object-like state to a sprite asset.
- Scene detail exposes object, script, zone, background, and render contract
  evidence.
- Sprite View and Model View can inspect visual payloads.
- Reverse scene usage exists, but the user has to manually connect it.

This makes demos and workflows weak. The app can contain the answer, but the UI
does not reliably explain the chain:

`runtime observation -> scene object -> asset -> script/zone reference -> render contract -> port implication`

## Non-Goals

- Do not add a new archive family just because it is catalogable.
- Do not build a general replacement-asset editor.
- Do not claim final renderer parity for scene previews.
- Do not add compatibility bridges for old local states.
- Do not hide uncertainty; unresolved mechanics must stay labeled as evidence,
  inference, or unknown.

## Proposed Product Concept

Add a first-class evidence workflow centered on scene entities and asset usage.

### Entity View

A scene entity is a normalized presentation of one SCENE object plus its linked
evidence:

- scene id and object index
- render backend: body model, projected sprite, ANIM3DS sprite, invisible, or
  background/incrust behavior
- current body/animation/sprite links
- script-driven body/animation/sprite/sample/text/video links
- flags, movement mode, collision participation, combat/bonus initialization
- draw/recovery contract and render-phase participation
- local object/waypoint/zone/script cross-links
- unresolved or low-confidence fields

### Usage Graph

Every selected asset should answer:

- Which scenes and objects use this asset?
- Is the usage direct scene state, script-driven state, zone-driven state, or
  runtime dynamic state?
- Which runtime rule resolves the reference?
- What does the port need to model for this usage to behave correctly?

### Evidence Trail

The UI should expose a readable trail:

1. Runtime observation or selected asset.
2. Resolved catalog asset.
3. Scene usages.
4. Entity/object detail.
5. Script/zone/render contract.
6. Visual payload preview where applicable.

## Implementation Shape

### Backend

Create narrow modules instead of growing `viewer.py`:

- `lba2_lm2_viewer/catalog.py`
- `lba2_lm2_viewer/scene.py`
- `lba2_lm2_viewer/sprites.py`
- `lba2_lm2_viewer/background.py`
- `lba2_lm2_viewer/resources.py`

The first extraction should follow actual feature boundaries. Do not move code
only for aesthetics.

Add an entity/usage payload builder that derives from existing catalog data.
Prefer structured JSON over frontend string parsing.

### Frontend

Add a main-area workflow for entity/usage inspection. Candidate shape:

- Keep `Model View`.
- Keep `Sprite View`.
- Add `Entity View` or `Usage View`.

The new view should not be a second catalog detail dump. It should be a
workflow surface with:

- selected asset or runtime observation summary
- usage list grouped by scene/object
- selected entity detail
- linked visual preview controls
- render contract and port implication sections

### Validation

Minimum validation:

- Python unit tests for entity/usage payloads using synthetic fixtures.
- Existing Python test suite.
- Frontend build.
- `agent-browser` progress validation during implementation. Load the live
  workflow with `agent-browser skills get core` before browser work, then use
  snapshots/screenshots to verify each meaningful UI slice while it is built.
- `agent-browser` final e2e validation on a real asset root showing:
  `runtime sprite 127 -> SPRITES.HQR:127 -> Scene 21 obj 7 -> script sprite link -> draw contract`.

The e2e proof must validate the user-visible workflow, not only backend JSON.
It should leave the browser on the strongest evidence screen and capture a
screenshot artifact for review.

## Open Design Decisions

## Decisions

- Primary workflow object: scene entity. Assets, runtime observations, and scene
  records are entry points, but the destination is the entity/mechanic: one
  object in one scene, its state, links, scripts, render contract, and port
  implications.
- Scene entities are addressable derived evidence nodes, not archive-backed HQR
  assets. Use stable ids shaped like `SCENE.HQR:22#object:7`; keep archive
  assets such as `SPRITES.HQR:127` in the catalog, and connect them to entity
  ids through usage graph links.
- Main workflow tab name: `Entity View`. It must center one selected entity and
  explain its links/contracts; if it degenerates into a generic usage report,
  the implementation has missed the concept.
- Product concept: `LBA2 Evidence Workbench`. `LBA2 LM2 Viewer` is legacy
  naming that undersells the current scope. Move UI/docs language toward the
  workbench concept during this task. Defer package/CLI renaming unless a
  dedicated cleanup task explicitly takes it on.
- Live-runtime validation threshold: require live runtime only when behavior or
  visual parity is ambiguous after static/classic evidence, especially
  pixel-level render order, masking/z-buffer behavior, timing, state mutation
  order, or exact-port-behavior claims. Static/classic evidence is sufficient
  for archive identity, provenance, parser layout, source-backed contracts, and
  UI workflow validation.
- Stable port-facing JSON should be entity contracts, not raw catalog detail.
  Include entity id, scene/object identity, render backend, linked visual
  assets, initial gameplay/render state, movement/collision/combat/bonus facts,
  script-driven links, render phase, redraw/recovery contract, provenance,
  confidence, and unknown descriptors. Keep full instruction dumps, huge reverse
  indexes, preview pixels, broad summary counters, and raw live-run traces out
  of the stable contract unless they are distilled into a named behavior claim.

## Success Criteria

- A user can start from `SPRITES.HQR:127` or a runtime sprite observation and
  reach the relevant scene object/mechanic without manual search gymnastics.
- A user can understand whether a usage is direct, script-driven, or runtime
  dynamic.
- A port developer can identify the render/update contract attached to a scene
  object.
- The implementation reduces `viewer.py` and `catalog.ts` responsibility rather
  than adding another layer of string-heavy UI.
- Unknowns remain explicit.
