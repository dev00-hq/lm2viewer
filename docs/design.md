# LM2 Viewer Design Contract

## Purpose

The LM2 Viewer is a local visual falsification workbench for original LBA2
asset evidence and the Zig port at `D:\repos\reverse\littlebigreversing`.

It answers:

> Does this decoded asset, runtime linkage, or port-facing visual claim look
> wrong, and what evidence explains why?

The viewer is not a general model editor, sprite editor, scene editor, archive
manager, conversion suite, plugin host, or replacement-asset authoring tool. It
is an evidence instrument for original LBA2 assets, runtime relationships, and
port contracts.

Future remake review is out of product scope until real candidate assets and
review workflows exist.

## Current Boundary

The active boundary is original-runtime evidence and port behavioral
compatibility.

Compatibility means compatibility with original-runtime behavior and the port
contract. It does not mean preserving old viewer UI/data shapes, legacy local
states, alternate loaders, migration shims, fallback paths, or dual behavior.

The viewer must make these tasks direct:

- find original assets by semantic identity, runtime use, and archive entry
- inspect models, sprites, scenes, entities, resources, and decoded metadata
- visually falsify decode, linkage, palette, animation, and runtime-usage claims
- pivot from a visual asset to scene usage, runtime state, provenance, and port
  implication
- export evidence bundles with manifests
- identify what is source-backed, decoded-only, render-only, live-confirmed,
  port-implied, unknown, or intentionally deferred

A successful preview cannot upgrade evidence status by itself. Unknown,
decoded-only, render-only, source-backed, live-confirmed, and port-implied
states must remain visible and distinct.

## Port Integration

The port's runtime truth is guarded by the Zig runtime, CLI tools, verification
scripts, and promotion packets. This viewer supplies evidence and falsification
surfaces; it does not become the canonical runtime.

Port-facing design rules:

- Evidence bundles should be shaped so they can feed promotion packets.
- `canonical_runtime: true` requires `live_positive` or `approved_exception`
  status in the port evidence workflow; decoded or rendered evidence alone is
  not enough.
- `Port implications` should expose known packet ids, contract ids, promotion
  status, and links when available.
- Root-motion and animation correlation must distinguish "supports hypothesis"
  from "live-proved writer/commit path".
- Canonical port evidence roots should fail loudly when unavailable; do not
  silently search alternate local layouts when acting as a port instrument.

Known port evidence context:

- canonical asset root:
  `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- classic source root:
  `D:\repos\reverse\littlebigreversing\reference\lba2-classic\SOURCES`
- current guarded positive viewer/load pairs include `19/19`, `2/2`, `11/10`,
  and `187/187`
- `44/2` is an explicit guarded negative for unsupported exterior viewer load

These entries are evidence anchors, not UI hard-coding requirements.

## Borrowed Constraints

Use RenderDoc as the primary conceptual reference, but only for
selection-driven evidence inspection: one selected event/resource establishes
the current context, and all viewers expose state, provenance, usage, linked
resources, and inspection actions for that selection.

Use Godot Editor only as a workbench layout reference: one technical window,
top-level workspaces, docked explorer/inspector panels, contextual viewport
controls, and folded bottom evidence panels. Do not inherit Godot's authoring
model, mutable property inspector, asset library, project manager, saved
layouts, floating docks, or live-edit workflow.

Use Aseprite only for sprite and animation inspection patterns: visible frame
identity, frame strip, nearby-frame context, playback near the visual, scrub
controls, loop/range visibility, and optional previous/next ghost overlays. Do
not inherit pixel editing, cel editing, art layers, drag-reordering, copy/paste
frame workflows, arbitrary tags, or configurable frame numbering.

Use Noesis only as a weak reference for lightweight asset preview: semantic
catalog, central preview, viewport controls, animation preview, metadata
inspection, and explicit export actions. Reject Noesis as a product model: this
viewer is not a universal converter, plugin host, format browser, archive
extractor, or batch-processing tool.

## Canonical Workbench And Selection Model

The canonical layout must be:

`Explorer Dock -> Workspace -> Inspector Dock -> Evidence/Timeline Panel`

The viewer must be driven by one global selection. All workspaces, inspector
sections, export state, timeline strips, and evidence panels must update from
that selection.

### Selection Union

Near-term selectable targets:

- `asset`: catalog asset such as `BODY.HQR:49`, `ANIM.HQR:66`, or
  `SPRITES.HQR:127`
- `scene_usage`: scene object or script usage such as `SCENE.HQR:44 object 7`
- `runtime_resolution`: runtime resolver input and resolved asset state
- `sprite_frame`: selected sprite/range frame
- `animation_sample`: selected BODY + ANIM sequence/frame state
- `model_surface`: selected polygon, UV group, vertex, bone, line, or sphere
- `resource_record`: selected resource subrecord such as text, palette,
  sample, table row, or background composition part
- `evidence_artifact`: export manifest or evidence packet reference

Each selection must expose:

- stable id
- kind
- label
- source archive/index
- provenance
- evidence status
- links
- unknowns
- preview actions
- export actions, when supported
- compatibility or confidence status

Selection can show a non-destructive workspace suggestion. It must not
auto-switch workspaces without user action unless the current workspace cannot
display the selected target.

### Canonical Ids

Canonical ids must match runtime/source identities, including archive-specific
zero-based or one-based indexing. The UI must never offer configurable
numbering, shifted display ids, or alternate id modes.

Stable ids must be visible and copyable wherever they identify the current
selection, frame, usage, export, or evidence row.

## Explorer Dock

The explorer is a semantic HQR catalog, not a raw filesystem tree.

Minimum facets:

- asset kind
- archive
- semantic layout
- decode/evidence status
- runtime backend
- scene usage presence
- exportability

Text search remains available for labels, ids, source paths, direct code
references, unknown descriptors, scene usage text, script references, and
semantic metadata.

The catalog list must avoid decorative thumbnails unless the thumbnail carries
falsification data such as frame id, palette source, dimensions, offset,
runtime backend, decode state, or range ownership.

## Workspace Rules

The center workspace is the active visual falsification surface.

Primary workspaces:

- `Model`: LM2/BODY/OBJFIX model preview, geometry, animation, UV, primitive
  visibility, and pose checks.
- `Sprite`: projected sprites, raw sprites, ANIM3DS ranges, indexed images,
  background previews, frame playback, palette and offset checks.
- `Scene/Entity`: runtime object evidence, linked visuals, render contracts,
  local/script links, and port implications.
- `Resource`: semantic resource inspection for audio, text, palette, indexed
  image, background, video metadata, runtime tables, and unknown payloads.

`Resource` is a real target in the design, even though current visual resources
are routed through Sprite View and many nonvisual resources are rendered in
catalog detail. The migration must replace that implicit routing with semantic
resource inspection instead of preserving both paths.

Workspace switching must preserve selection and inspector state.

## Inspector Dock

The inspector is shared across workspaces. It adapts to the current selection
instead of each workspace inventing a separate detail model.

Inspector rows should come from a structured section model, not branchy HTML
string blobs. Section ids are stable API/UI concepts.

Default section order:

1. `Summary`
2. `Source`
3. `Evidence status`
4. `Runtime`
5. `Geometry`
6. `Render`
7. `Animation`
8. `Sprite`
9. `Palette`
10. `Scene usages`
11. `Script links`
12. `Visual links`
13. `Port implications`
14. `Export`
15. `Unknown descriptors`
16. `Raw evidence`

Defaults:

- `Summary`, `Source`, `Evidence status`, and the most relevant workspace
  section are open.
- Raw hashes, sampled object rows, opcode lists, raw descriptors, long usage
  lists, and large unknown sections are folded.
- Search matches section names and rows, opens matching sections, and reports
  hidden/matching counts.

First migration target: move existing catalog detail branches and Entity View
sections into this section model. Do not keep the old detail blob as a hidden
fallback once the canonical inspector section is implemented.

## Evidence And Timeline Panel

The bottom panel is for heavyweight evidence that should be available without
permanently crowding the inspector:

- decode progress
- export manifests
- sprite frame strips
- animation sequence strips
- selected asset usage strips
- raw descriptor tables
- script/control-flow tables
- logs and diagnostics

Add strips only when they reduce a listed falsification check. Do not add
timeline-like decoration without frame, usage, or evidence identity.

## Fast Visual Falsification Checks

The UI must reduce these checks to visible state, adjacent controls, or one
click from the current selection:

- wrong archive entry or off-by-one index
- wrong model/animation compatibility
- wrong animation loop boundary
- root-motion or wrap snap
- wrong sprite backend
- wrong sprite frame order
- wrong palette or transparency
- wrong sprite offset, hotspot, or bounds
- wrong UV group or atlas region
- missing line/sphere primitives
- wrong scene object visual link
- wrong runtime flags or resolver rule
- decoded preview mistaken for final runtime rendering
- mismatch between original evidence and port fixture

Evidence controls must be adjacent to the visual they affect. Animation
transport belongs near the model viewport. Sprite playback belongs near the
sprite frame strip. Pixel, polygon, UV, frame, and runtime readouts must remain
visible while inspecting the corresponding visual.

## Model Workspace

The model workspace is a 3D work surface, not a hero section.

It must support:

- reset, zoom, pan, rotate, horizon lock, and background control
- face, wireframe, line, sphere, and grid visibility
- selected polygon/vertex/bone/UV group inspection
- synchronized UV atlas and polygon evidence
- compatible animation selection scoped by BODY/File3D evidence
- transport controls with frame/time/loop/root-motion state
- clear BODY + ANIM identity and compatibility status
- evidence copy/download for selected geometry or UV facts

Line and sphere primitives are first-class geometry evidence, not decorations.

## Sprite Workspace

The sprite workspace is a first-class workspace, not a catalog detail pane.

It must support:

- nearest-neighbor canvas rendering
- zoom, fit, and pan
- exact hover and picked pixel values
- palette index and RGBA display
- visible canonical frame identity
- frame strip with thumbnails, current-frame highlight, and decoded/missing
  state
- previous/play/next/scrub controls near the frame strip
- ANIM3DS range-relative frame labels
- runtime sprite id, backend, archive id, dimensions, offset, hotspot, bounds,
  and palette source
- optional previous/next ghost overlays for jump and offset falsification
- export of selected frame/range with manifest provenance

"Layers" in this workspace mean evidence lanes, not editable art layers.
Useful lanes include pixels, palette, hotspot/bounds, runtime resolver, entity
usage, source/code references, and port expectation.

Do not add pixel editing, cel editing, arbitrary tagging, drag-reorder
workflows, sprite-sheet production flows, or configurable frame numbering.

## Scene And Entity Workspace

The scene/entity workspace is the correlation surface.

It must answer:

- which scene object or runtime state selected this visual?
- which BODY/ANIM/sprite/resource assets are linked?
- which flags, scripts, zones, and local references affect it?
- which render backend, draw path, sort/recovery rule, and redraw contract apply?
- what is known, unknown, decode-only, render-only, source-backed, or
  live-confirmed?
- what must the port preserve?

Runtime usage is often a higher-value selection than a raw asset. A selected
usage such as `SCENE.HQR:44 object 7` must be able to drive the model, sprite,
resource, and inspector workspaces through linked visuals.

## Resource Workspace

Resources must be inspected by semantic layout, not by generic byte payload.

Examples:

- palettes and texture atlases
- indexed screens and images
- holomap maps and plans
- background grids, blocks, bricks, GRM fragments, and scene compositions
- text order tables and text banks
- WAVE samples
- Smacker/ACF metadata
- File3D and runtime tables
- unclassified payload evidence

Each resource inspector must expose preview, source identity, semantic layout,
scene usage, direct references, export support, unknowns, and raw evidence
without making nonvisual resources compete with model/sprite controls.

## Export Rules

Export is an explicit evidence action on the current selection.

Export must behave more like RenderDoc evidence export than Noesis conversion:
it records the selected evidence and manifest context first; generated OBJ,
PNG, WAV, text, or video files are secondary carriers, not the product boundary.

The manifest is authoritative and must preserve:

- selected asset id
- source archive/index
- raw and decoded hashes where available
- options used
- coordinate or palette context
- warnings
- generated files
- provenance relevant to the port

Current exportable surfaces:

| Selection | Export carrier |
| --- | --- |
| model assets | OBJ/MTL, atlas PNGs, UV PNGs, evidence manifest |
| sprite frames and ANIM3DS ranges | PNG frames/sheet, evidence manifest |
| indexed image resources | paired-palette PNG, evidence manifest |
| background grids and scene backgrounds | composition JSON, preview PNGs, evidence manifest |
| WAVE samples | decoded WAV, evidence manifest |
| text banks | JSON text bundle, evidence manifest |
| Smacker/video resources | original container/metadata bundle, evidence manifest |

Do not silently export, auto-migrate, or create alternate compatibility paths.

## Contract Vocabulary

The active contract vocabulary is `Compatibility Contract`.

It maps onto current model/entity contracts and evidence manifests. It is not a
new visible UI feature by itself.

It preserves original gameplay-facing behavior:

- scale
- bounds
- collision footprint
- anchors and hotspots
- animation timing and events
- scene usage
- runtime render role
- script/entity implications
- source provenance and confidence

The reserved future vocabulary is `Remake Intent Contract`.

It may later describe explicit divergence such as improved movement feel,
adjusted hitboxes, new animation events, modernized asset formats, gameplay
balance changes, or intentional behavior differences.

These contract vocabularies must remain separate. The viewer must never
silently treat remake improvements as original-runtime truth.

For now:

- reserve the terminology and data model only
- do not expose visible replacement/remake panes
- do not add empty tabs, disabled buttons, or placeholder flows
- add UI only when real candidate assets and review workflows exist

## Migration Order

Migration is replacement, not coexistence. When a new canonical workbench
surface lands, remove the superseded sidebar/tab behavior in the same change
unless explicitly deferred in a tracked issue. Do not keep hidden alternate UI,
old routing, compatibility adapters, fallback detail renderers, or temporary
second paths.

Implementation order:

1. Define global selection state and stable ids.
2. Split catalog browsing from inspector state.
3. Move existing asset detail and Entity View detail into structured inspector
   sections.
4. Promote `Model`, `Sprite`, `Scene/Entity`, and `Resource` to peer
   workspaces.
5. Move playback and visual controls beside their visuals.
6. Replace dense blobs with named inspector sections.
7. Add frame strips and usage strips only where they shorten a listed
   falsification check.
8. Delete superseded sidebar/tab code.

Each step must preserve one canonical current-state implementation. Do not add
compatibility bridges for old UI shapes or local states.

## Validation

UI changes must be validated with `agent-browser` against the current checkout.
Before trusting browser evidence, confirm the validation server is serving this
repository, not a stale listener or generated bundle from another checkout.

Use type checks, build commands, and relevant Python tests according to
`docs/implement.md`. If validation cannot run, the handoff must say why.
