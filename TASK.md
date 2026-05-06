# LM2 Viewer UX Migration Goal

## Goal

Migrate LM2 Viewer from a model-viewer-plus-sidebar UI into the evidence
workbench defined in `docs/design.md`, optimized for fast visual falsification
of original LBA2 asset evidence and port-facing contracts.

The finished app should make decoded assets, runtime relationships, visual
previews, provenance, unknowns, and export evidence inspectable as connected
workbench state. It must not rely on large text dumps, textarea-like metadata
presentation, or old viewer-specific detail panes as the main way to understand
an asset.

## Stable Prompt Contract

This file is intended to be used by a long-running Codex `/goal` workflow. Keep
the objective, constraints, acceptance gates, and stopping conditions stable.
Update only `Current Status`, `Completed Slices`, `Validation Notes`, and
`Remaining Risks` unless the developer explicitly changes the goal.

Avoid vague or contradictory instructions. If a milestone slice cannot satisfy
both replacement and deletion criteria, the slice is too small to mark complete.

## Done Means

- One app selection state module drives explorer, workspace, inspector, export
  state, evidence/timeline panels, and sub-selections.
- Model, Sprite, Scene/Entity, and Resource are peer workspaces.
- Catalog detail blobs are replaced by structured inspector sections.
- Decoded and runtime data is shown as navigable evidence, not dumped text.
- Current domain capabilities remain available through canonical workbench
  surfaces: model loading, sprite playback, entity evidence, resource previews,
  animation posing, UV inspection, runtime sprite resolution, and exports.
- Capability is preserved; old UI shape, old local state, old routing, and old
  fallback detail paths are not preserved.
- Scene/entity selections are runtime-state selections, not just decoded scene
  rows: object flags, File3D resolver state, sprite backend, animation state,
  palette context, render path, redraw/recovery path, and source/evidence status
  remain visible when linked visual assets are opened.
- Every visual claim distinguishes source-backed, decoded-only, render-only,
  live-confirmed, port-implied, unknown, intentionally deferred, and preview-only
  evidence. A successful browser preview must not upgrade evidence status.
- The app preserves gameplay-facing and port-facing contracts from
  `docs/design.md`.
- Python tests and frontend build pass.
- Every UI-affecting slice is validated with `agent-browser`.
- Each browser validation run is saved as a natural-language reproduction flow.

## Slice Completion Gates

A migrated slice is not complete unless:

- it replaces the old behavior for that migrated surface
- it deletes the superseded path for that migrated surface
- evidence statuses remain visually distinct
- stable ids are visible and copyable for active selections and evidence rows
- canonical port roots fail loudly when required and unavailable
- no alternate loader, id mode, fallback renderer, compatibility adapter, hidden
  legacy detail blob, or parallel old/new behavior is added
- relevant tests/build pass
- an `agent-browser` validation note is added or updated when browser behavior
  changes

## Non-Goals

- Do not make a framework migration part of this goal.
- Do not add visible remake-asset UI placeholders yet.
- Do not add compatibility paths for old viewer states.
- Do not add alternate numbering, shifted ids, configurable index bases, or
  display-id modes.
- Do not keep legacy detail blobs as hidden fallbacks after their canonical
  inspector sections exist.
- Do not write Playwright, Puppeteer, or browser automation test files as part
  of the validation milestone. The required artifact is a step-by-step human
  reproduction guide.
- Do not write or mutate
  `D:\repos\reverse\littlebigreversing\docs\promotion_packets` from this
  viewer. Viewer exports may generate packet-ready evidence material, but the
  port remains the authority for promotion.

## Operating Loop

At each iteration:

1. Read `docs/design.md` and this file before editing.
2. Inspect the current code before choosing the next change.
3. Pick the smallest unfinished milestone slice that can replace and delete one
   old surface without introducing a parallel path.
4. Implement one canonical current-state path.
5. Delete superseded UI and code paths in the same slice once the replacement is
   working.
6. Run the relevant Python tests and frontend build for the changed surface.
7. Use `agent-browser` for UI validation when the change affects browser
   behavior.
8. Save browser validation as a natural-language step-by-step flow that a human
   or another tool can repeat.
9. Update only the mutable sections of this file.

If a surprising project behavior or trap appears, tell the developer and record
the confusion point in `ISSUES.md` so future agents do not rediscover it.

## Stopping Conditions

Continue until all milestones pass acceptance checks, or stop only when blocked
by a concrete missing dependency, failing command, unavailable asset root, or
design contradiction that needs developer judgment.

Before stopping, record:

- last completed slice
- exact tests, build, and browser validation run
- remaining failing check
- next smallest slice

## Milestone 1: Selection Backbone

Outcome: catalog, workspace, inspector, export state, evidence panels, and
sub-selections are driven by one canonical app selection state.

Required work:

- Define a single app selection state module matching the selection targets in
  `docs/design.md`.
- Route catalog, runtime resolver, sprite frame, animation sample, model
  surface, UV, export, scene usage, resource record, and entity-link selections
  through that module.
- Include stable id, kind, label, source archive/index, provenance, evidence
  status, links, unknowns, preview actions, export actions, and compatibility
  or confidence status where available.
- Add `scene_object`, `runtime_sprite_state`, `file3d_resolution`,
  `anim3ds_range_state`, `render_contract`, and `palette_context` as selectable
  evidence targets or linked selection facets where current payloads support
  them.
- Canonical ids must preserve runtime identity exactly: scene object slot,
  archive/catalog id, File3D object index, generic body/animation id, resolved
  BODY/ANIM id, sprite backend/id, ANIM3DS range id, palette source, and any
  semantic-vs-physical slot distinction must not be collapsed into one display
  id.
- Make catalog selection emit `Selection` objects instead of directly owning
  workspace/detail behavior.
- Preserve selection while switching workspaces.
- Delete local selected-asset/export/workspace ownership once each state is
  represented.

Acceptance checks:

- Every currently reachable supported target kind produces one visible active
  `Selection`.
- Missing producers for design selection kinds are recorded as remaining work;
  no placeholder UI is added.
- Acceptance covers asset, scene usage, runtime resolution, sprite frame,
  animation sample, model surface or UV polygon, resource record, and export
  manifest artifact.
- Export enablement follows the active selection.
- No new compatibility bridge or alternate id mode exists.

## Milestone 2: Catalog And Inspector Split

Outcome: catalog browsing no longer owns the primary evidence explanation path.

Required work:

- Split catalog browsing state from active selection and inspector state.
- Introduce `InspectorSection` data shaped at minimum as `{ id, title, status?,
  rows, actions?, defaultOpen, searchText }`.
- Move the first migrated catalog and entity detail branches into pure section
  builders before rendering DOM.
- Keep the existing visual workspace usable while the canonical shell is not yet
  complete.
- Delete each migrated `CatalogUi.renderDetail()` path in the same slice; do not
  hide it as a fallback.
- Fold raw hashes, long sampled rows, opcode lists, descriptors, and large
  unknown sections by default.
- Add inspector search over section names and rows.

Acceptance checks:

- The migrated selection kind is explained by inspector sections, not by
  `CatalogUi.renderDetail()`.
- The old detail path for that migrated kind is removed, not hidden.
- Common selections show Summary, Source, Evidence status, and the relevant
  workspace section open by default.
- Raw evidence is reachable but not the first reading path.

## Milestone 3: Workbench Shell

Outcome: the app uses the canonical workbench structure:
`Explorer Dock -> Workspace -> Inspector Dock -> Evidence/Timeline Panel`.

Required work:

- Replace the current tab/sidebar mental model with the workbench shell.
- Keep the catalog as a semantic explorer, not a raw filesystem tree.
- Keep Model, Sprite, Scene/Entity, and Resource available as peer workspaces.
- Move asset root controls, explorer, runtime resolver, export result, UV
  inspector, view controls, stats, and decode progress into their canonical
  regions.
- Move visual controls next to the visual surfaces they affect.
- Keep workspace switching non-destructive to selection and inspector state.
- Remove `main-tabs` as the workspace authority after peer workspaces exist.

Acceptance checks:

- The model viewport is a work surface, not a hero section.
- Sprite inspection is not hidden among catalog/menu details.
- Resource inspection has a real workspace route instead of implicit Sprite View
  reuse or Model View ownership.
- The layout remains usable on the target desktop viewport.

## Milestone 4: Workspace Migration

Outcome: each primary workspace is selection-driven and exposes the inspection
controls needed for fast visual falsification.

Required work:

- Model workspace: preserve geometry visibility, horizon/background controls,
  animation compatibility, playback, UV inspection, File3D resolver evidence,
  and selected surface evidence.
- Sprite workspace: preserve nearest-neighbor rendering, zoom/fit/playback,
  frame identity, frame strip, runtime sprite data, backend resolution, palette
  source, offsets, hotspot/bounds, ANIM3DS range/FPS status, and export
  evidence.
- Scene/Entity workspace: expose scene object runtime state as the primary
  evidence object, including `Flags`, `GenBody`, `GenAnim`, `Sprite`, File3D
  resolver links, ANIM3DS range/FPS state, movement/collision/combat/bonus
  fields, script/local links, selected visual assets, render backend, sorted
  insertion stage, draw path, redraw/recovery contract, palette context, dynamic
  runtime draw-source limitations, and port implications.
- Resource workspace: expose semantic resource inspection for audio, text,
  palette, indexed images, background previews, video metadata, runtime tables,
  and unknown payloads.
- Create a real Resource workspace before migrating visual resources out of
  Sprite View.
- Remove old workspace routing once each canonical replacement is working.

Acceptance checks:

- Selecting supported assets lands in or suggests the correct workspace without
  losing selection.
- Workspace controls are adjacent to the visual/evidence they affect.
- Text, audio, indexed image, background/grid, video, runtime-table, and unknown
  resources never leave the user in Model View as the conceptual owner.
- Visual resources no longer depend on being conceptually treated as sprites.
- Opening a linked BODY, ANIM, SPRITES, SPRIRAW, or ANIM3DS asset from a scene
  object preserves the owning scene object/runtime-state evidence trail.
- ANIM3DS playback labels whether timing comes from selected scene object FPS,
  track-script evidence, decoded range metadata only, or unknown.
- Sprite previews label backend resolution as `ANIM3DS`, `SPRITES`, `SPRIRAW`,
  direct system/UI `HQRPtrSprite`, decoded-only, or unresolved.
- Indexed/background previews label palette status as active runtime palette,
  paired source palette, normal `RESS.HQR:0` preview palette, preview-only, or
  unknown.
- Render-contract panels show draw path and recovery path separately;
  `DrawRecover`, `DrawRecover3`, moving-box/z-buffer recovery, `OBJ_BACKGROUND`
  copy behavior, and preview limitations are not merged into a generic
  "rendered" status.

## Milestone 5: Port-Facing Evidence And Export Artifacts

Outcome: heavyweight evidence, port implications, and export manifests are
represented as evidence artifacts linked to the active selection.

Required work:

- Add bottom-panel surfaces for decode progress, export manifests, sprite frame
  strips, animation sequence strips, selected usage strips, raw descriptor
  tables, script/control-flow tables, logs, and diagnostics as needed.
- Add timeline/strip UI only when it reduces a named falsification check.
- After export, create/select an `evidence_artifact` selection with manifest
  schema, selected source id, output directory, generated files, warnings,
  hashes, provenance, evidence status, proof scope, and linked packet/runtime
  contract ids when available.
- Move export results and manifests into evidence artifacts linked to the active
  selection.
- Delete superseded catalog detail dumps, hidden fallback renderers, and stale
  tab-routing assumptions.

Port-facing acceptance checks:

- Port-facing evidence status uses the port vocabulary without collapsing
  meanings: `decode_only`, `live_negative`, `live_positive`,
  `approved_exception`, `render_only`, `source_backed`, `port_implied`,
  `unknown`, and `intentionally_deferred` remain visually distinct.
- The viewer never derives `canonical_runtime: true` from successful decode,
  successful preview, successful export, or `viewer_loadable=true`.
- `canonical_runtime: true` may be shown only when linked to a port promotion
  packet with `status=live_positive` or `status=approved_exception`.
- `Port implications` shows packet id, evidence class, promotion status,
  canonical runtime flag, runtime contract ids, fixture path, and source doc
  link when a matching promotion packet exists.
- Missing packet data is shown as unknown or unpromoted; it is not silently
  inferred from asset decode, render success, scene usage, or port CLI output.
- `validation.viewer_loadable` and visual admission are treated as admission
  hints only; they do not imply full runtime parity or gameplay promotion.
- `render_only` evidence is never reused as gameplay proof for transitions,
  collisions, inventory, dialog, object behavior, or locomotion.

Export acceptance checks:

- Large evidence remains accessible without crowding the inspector.
- Export manifests are connected to the selected evidence artifact.
- Export manifests include selected stable id, source archive/index, asset root,
  raw and decoded hashes where available, evidence status, proof scope,
  warnings, generated files, and linked packet/runtime contract ids when
  available.
- No old detail blob remains as the authoritative path for a migrated asset
  kind.

## Milestone 6: Autonomous Browser Validation Protocol

Outcome: the migrated workbench is validated end-to-end with `agent-browser`,
and every validation run leaves behind a reproducible natural-language flow.

Browser validation is not a final-phase activity. Every UI-affecting milestone
slice must include an `agent-browser` validation note before the slice is
considered complete. This milestone is the final cross-workspace replay audit.

Required work:

- Use the `agent-browser` snapshot-and-ref loop: open the local URL, snapshot,
  act on current refs, re-snapshot after every page change, and capture
  screenshot or observation references for important claims.
- For each run, save a step-by-step reproduction guide in this file or in a
  linked validation note under `docs/`.
- Write the guide in natural language, not Playwright/Puppeteer code.
- Include the starting URL, exact asset root, selected asset or scene pair, user
  actions, expected visible state, expected evidence state, observed result, and
  screenshot/observation references.
- Capture failures as reproduction flows too, including what looked wrong and
  the smallest suspected surface.

Minimum validation flows:

- Load the canonical asset root
  `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
  and verify the Explorer Dock summary/facets.
- Use the classic source root
  `D:\repos\reverse\littlebigreversing\reference\lba2-classic\SOURCES` where
  source-backed evidence is required.
- Select a BODY model, inspect Model workspace, verify source/evidence status,
  geometry controls, File3D resolver evidence, and export affordance.
- Select a compatible animation for that model, play/scrub it, and verify
  frame/time/loop state remains adjacent to the viewport.
- Select a sprite or ANIM3DS range, verify Sprite workspace frame identity,
  frame strip, playback, backend resolution, offset/hotspot/bounds, palette
  source, and export.
- Resolve or open a scene/entity workflow and verify linked visual assets,
  runtime resolver data, render contract, evidence trail, and port
  implications.
- Validate guarded-positive viewer/load pairs `19/19`, `2/2`, `11/10`, and
  `187/187` as evidence anchors.
- Validate guarded negative `44/2` and verify the UI fails loudly instead of
  routing through an alternate preview path.
- Select representative Resource assets for image/background, text, audio, and
  unknown payload cases, verifying they appear in Resource workspace rather
  than being dumped as text.
- Export at least one model and one sprite/resource evidence bundle and verify
  the manifest becomes or links to the active `evidence_artifact` selection.
- Demonstrate at least one linked promoted packet
  (`live_positive` / `canonical_runtime: true`) and at least one unpromoted or
  live-negative candidate remaining non-canonical.
- Confirm no migrated path relies on a large textarea-style or raw JSON/string
  dump as the primary inspection UI.

Acceptance checks:

- The final validation guide is detailed enough for a human, `agent-browser`, or
  another browser automation tool to replay.
- Screenshots or observations from each run are tied to the exact validation
  flow step they support.
- Validation failures are fixed or explicitly left as remaining work in this
  file.
- If port promotion packet metadata is consumed or transformed, the handoff
  cites `py -3 tools\validate_promotion_packets.py` or `zig build
  test-promotion-packets` as the authoritative validation gate in
  `littlebigreversing`; the viewer's own tests do not replace that gate.

## Current Status

- `docs/design.md` defines the target UX contract.
- Existing implementation baseline: sidebar catalog/detail, model/sprite/entity
  tabs, catalog-owned detail rendering, local export state, entity workflow
  panel, sprite playback panel, animation controller, UV inspector, runtime
  sprite resolver, and resource routing through model/sprite/detail paths.
- Milestone 1 selection backbone implementation has started. A canonical
  frontend selection module now drives the visible active selection summary and
  export enablement for catalog assets, runtime sprite resolutions, sprite
  frames, animation choices, loaded catalog models, and export manifest
  artifacts.
- Catalog button selection no longer directly renders detail as a side effect;
  model, decoded animation, decoded sprite frame, and ANIM3DS range metadata
  now render through structured inspector sections. Sample audio resources also
  render through structured inspector sections while preserving the audio
  preview, and Smacker video resources now render through structured inspector
  sections. Text payload bank resources now render through structured
  inspector sections. Text order table resources now render through structured
  inspector sections. Palette and indexed-image resources now render through
  structured inspector sections and keep resource selection ownership even when
  a visual preview payload is available. Runtime table resources now render
  through structured inspector sections. Holomap resources now render through
  structured inspector sections. Background resources now render through
  structured inspector sections while keeping previewable grid/brick payloads
  owned by resource selections. Scene top-level runtime layout assets now
  render through structured inspector sections. Unclassified RESS payloads now
  render through structured inspector sections. Raw/deferred animation payloads
  now render through structured inspector sections, and
  `CatalogUi.renderDetail()` has been deleted.
- Local `selectedExportAsset` ownership was removed. Export enablement now
  follows the active selection's export actions.
- A first real Resource workspace now exists as a peer main view. Resource
  selections, including visual resources returned through sprite-compatible
  preview payloads and nonvisual audio/text/table resources, route to Resource
  View instead of being conceptually owned by Model View or Sprite View.
- The shell has started moving from one overloaded sidebar toward the canonical
  workbench structure: Explorer Dock is left, Workspace is center, and
  Active Selection/Inspector/Export live in a right Inspector Dock.
- Model viewport controls and model decode stats now live in the Model
  workspace instead of the Explorer Dock.
- The UV inspector now lives in the Model workspace side panel with the model
  visual controls instead of being owned by the Explorer Dock.
- A first bottom Evidence panel now exists, and decode progress is owned there
  instead of by the Explorer Dock.
- Runtime sprite resolution now lives in the Scene/Entity workspace instead of
  the Explorer Dock, so runtime observations produce entity evidence from the
  workspace that owns that state.
- Browser exports now create/select an `evidence_artifact` selection, report
  the export result in the bottom Evidence panel, and render structured export
  inspector sections instead of leaving stale asset inspector content.
- Export manifests now include an explicit top-level `evidence` block with
  stable id, evidence status, proof scope, scene usage count, and port-link
  arrays. Scene-linked exports now populate promotion packet ids and runtime
  contract ids from the canonical promotion packet manifest when matching
  fixture scene evidence is available.
- Workspace switching is now a workbench switcher instead of ARIA tab/tabpanel
  ownership. The legacy `main-tabs`/`main-tab` authority is removed, and
  workspace switching preserves the active selection and inspector state.
- Scene/entity workflows now promote the selected scene object to the canonical
  active selection. Scene object runtime state, render contract, linked
  visuals, script links, port implications, and unknowns render through shared
  inspector sections instead of the Entity workspace owning a separate detail
  path.
- Model UV polygon navigation now promotes the selected polygon to a canonical
  `model_surface` active selection with shared inspector sections for decoded
  surface, render flags, UV group, atlas samples, and unknown descriptors.
- Sprite workspace frame sequences now have a bottom Evidence panel frame strip
  that preserves ANIM3DS frame identity, backend resolution, palette source,
  decoded timing status, and selection-driven frame navigation.
- Sprite workspace frame variants, including scene background GRM preview
  variants, now promote the clicked variant to a canonical `sprite_frame`
  selection instead of only repainting Sprite-local canvas state.
- Scene background `sprite_frame` variant selections now render a
  selection-aware scene inspector summary and Frame section, so the inspector
  names the selected variant rather than only the parent scene asset.
- Animation playback now promotes the current BODY+ANIM sequence sample to a
  canonical `animation_sample` selection with a bottom Evidence panel sequence
  strip and shared inspector sections.
- Manual animation pose actions now also promote the posed BODY+ANIM frame to a
  canonical `animation_sample` selection, so frame/elapsed pose evidence is not
  left as controller-local text after `showModel()` refreshes the viewport.
- Resource workspace sampled records now promote to canonical `resource_record`
  selections with shared inspector sections while direct resource selection
  stays resource-owned.
- Scene catalog assets, including scene loads that arrive through
  sprite-compatible preview payloads, now settle in the Scene/Entity workspace
  with asset selection ownership instead of being owned by Sprite or reset by
  startup model loading.
- Assets with reverse scene usage evidence now expose a bottom-panel Scene
  Usages strip, and selecting a usage promotes a canonical `scene_usage`
  selection with shared inspector sections.
- Active selections backed by assets with `unknown_descriptors` now expose a
  bottom-panel Raw Descriptors table for bulky descriptor evidence.
- Bottom-panel Raw Descriptors rows now show copyable stable descriptor ids
  such as `RESS.HQR:11#descriptor:indexed_image_semantics@0`.
- Scene-backed active selections now expose a bottom-panel Script Evidence
  table for sampled decoded instructions and control-flow targets.
- Scene-backed active selections now expose a bottom-panel Port Evidence table
  backed by the port repo's promotion packet manifest and fixtures.
- Catalog asset loading now ignores stale async responses when a newer Explorer
  selection has superseded them, keeping Active Selection and workspace content
  aligned during rapid audit navigation.
- Resource long-tail replay now covers palette, runtime-table-with-unknown
  semantics, video, and screen image resources in the Resource workspace. The
  canonical retail asset root currently has no generic unclassified resource
  payload entries to select; unknown Resource evidence is represented by
  descriptor/semantic gaps on decoded resources.
- Scene/entity File3D, runtime sprite state, render contract, and ANIM3DS
  range evidence can now be promoted from entity workspace rows into canonical
  active selections with shared inspector sections instead of remaining
  inspector-only facts.
- Selected entity contracts now carry ANIM3DS range evidence into the entity
  `ANIM3DS` evidence target, so both usage rows and the selected entity summary
  can promote `anim3ds_range_state` selections.
- Resource palette context now has a first-class `palette_context` active
  selection path from Resource workspace records for resources with paired
  palette, runtime reference, scene palette reference, or provenance fields.
- Resource workspace record highlighting is now synchronized from the canonical
  active selection, including palette-context selections whose canonical stable
  id differs from the producing row id.
- Resource workspace clear now resets its own selected record id, so direct
  workspace clears cannot retain a stale sampled-row highlight after switching
  to a non-resource selection.
- Evidence status badges now have distinct visual treatments for source-backed,
  decoded-only, render-only, live-confirmed, port-implied, unknown,
  intentionally-deferred, preview-only, live-positive, live-negative, and
  approved-exception states.
- Active Selection now renders selection-owned preview actions, so linked asset
  pivots such as opening a resolved palette entry are visible from the
  canonical selection surface instead of only workspace-specific controls.
- Sprite workspace hover and click inspection now exposes exact pixel
  coordinates, palette index, and RGBA values, with clicked pixel evidence
  retained in the sprite facts until the frame changes.
- Sprite picked-pixel evidence now also updates the active `sprite_frame`
  selection facets and inspector Frame section, so the durable clicked pixel is
  no longer owned only by Sprite workspace local state.
- Sprite frame strip entries now render decoded frame thumbnails when a frame
  payload is present, and unloaded sequence entries are explicitly marked as
  load-on-select instead of pretending to have visual evidence.
- Bottom-panel Script Evidence stable IDs and Port Evidence packet IDs now have
  inline Copy controls, making evidence-row identifiers copyable without first
  promoting another selection.
- Scene selections now expose a bottom-panel Scene Objects evidence table with
  copyable `SCENE.HQR:*#object:*` stable ids and Open controls that promote the
  row through the canonical `scene_object` selection and Entity workspace path.
- Scene selections now expose a bottom-panel Scene Locals evidence table with
  copyable zone, waypoint, GRM fragment, and patch ids such as
  `SCENE.HQR:*#zone:*`, `SCENE.HQR:*#waypoint:*`, and
  `SCENE.HQR:*#patch:*`.

## Completed Slices

- 2026-05-05: Selection backbone, first UI slice.
  - Added `frontend/src/selection.ts` with `AppSelection`,
    `AppSelectionStore`, stable id/source/provenance/evidence/export action
    fields, and near-term selection kinds from the design contract.
  - Added a visible Active Selection panel showing stable id, source, evidence
    status, provenance, workspace suggestion, links, unknowns, copy action, and
    selection-derived export action.
  - Routed catalog assets, runtime sprite resolver results, opened sprite
    frames, selected canvas animations, loaded catalog models, and export
    manifests through the selection store.
  - Removed the separate frontend `selectedExportAsset` state; the Export button
    is enabled only when the active selection exposes one export action.
- 2026-05-05: Model catalog detail moved to structured inspector sections.
  - Added `frontend/src/inspector.ts` with `InspectorSection` shaped as
    `{ id, title, status?, rows, actions?, defaultOpen, searchText }` and a
    renderer for searchable section DOM.
  - Added model section builders for Summary, Source, Evidence Status,
    Geometry, Runtime, Scene Usages, optional Source References, and Raw
    Evidence.
  - Added inspector search over section names and rows.
  - Removed the `asset.kind === 'model'` branch from
    `CatalogUi.renderDetail()`. Model assets are now explained by inspector
    sections, not the old catalog detail blob.
- 2026-05-05: Decoded animation detail moved to structured inspector sections.
  - Added decoded animation inspector sections for Summary, Source, Evidence
    Status, Animation, Runtime, Scene Usages, and Raw Evidence.
  - Routed compatible animation selection through the shared inspector instead
    of `CatalogUi.renderDetail()`.
  - Removed the old decoded animation detail blob from `CatalogUi.renderDetail()`;
    the remaining branch only reports that decoded animation detail is handled
    by structured inspector sections if accidentally called.
- 2026-05-05: Decoded sprite frame detail moved to structured inspector
  sections.
  - Added sprite frame inspector sections for Summary, Source, Evidence Status,
    Frame, Runtime, optional ANIM3DS Range, optional Source References, Scene
    Usages, Unknown Descriptors, and Raw Evidence.
  - Routed opened sprite frame selections through the shared inspector instead
    of `CatalogUi.renderDetail()`.
  - Removed the old decoded sprite frame detail blob and obsolete sprite
    runtime detail helper from `CatalogUi.renderDetail()`.
- 2026-05-05: ANIM3DS range metadata detail moved to structured inspector
  sections.
  - Added ANIM3DS range inspector sections for Summary, Source, Evidence
    Status, Ranges, Runtime Playback, Warnings, and Raw Evidence.
  - Routed ANIM3DS frame-range metadata selection through the shared inspector
    instead of `CatalogUi.renderDetail()`.
  - Removed the old ANIM3DS frame-range detail blob and its range/playback/
    warning HTML helpers from `CatalogUi.renderDetail()`.
- 2026-05-05: Sample audio resource detail moved to structured inspector
  sections.
  - Added sample audio inspector sections for Summary, Source, Evidence Status,
    Audio, Wave Container, Scene Usages, optional Source References, optional
    Unknown Descriptors, and Raw Evidence.
  - Routed `sample_wave_audio` resources through the shared inspector instead
    of `CatalogUi.renderDetail()`, while preserving the existing browser audio
    preview source and metadata panel.
  - Removed the old sample-specific resource detail blob from
    `renderResourceDetail()`.
- 2026-05-05: Smacker video resource detail moved to structured inspector
  sections.
  - Added Smacker video inspector sections for Summary, Source, Evidence
    Status, Video, Smacker Container, Scene Usages, optional Source References,
    optional Unknown Descriptors, and Raw Evidence.
  - Routed `smacker_video` resources through the shared inspector instead of
    `CatalogUi.renderDetail()`.
  - Removed the old Smacker-specific resource detail blob from
    `renderResourceDetail()`.
- 2026-05-05: Text payload bank resource detail moved to structured inspector
  sections.
  - Added text payload inspector sections for Summary, Source, Evidence Status,
    Text Bank, Sampled Records, Scene Usages, optional Source References,
    optional Unknown Descriptors, and Raw Evidence.
  - Routed `text_payload_bank` resources through the shared inspector instead
    of `CatalogUi.renderDetail()`.
  - Removed the old text-payload-specific resource detail blob from
    `renderResourceDetail()`.
- 2026-05-05: Text order table resource detail moved to structured inspector
  sections.
  - Added text order inspector sections for Summary, Source, Evidence Status,
    Text Order, Sampled Message IDs, optional Source References, optional
    Unknown Descriptors, and Raw Evidence.
  - Routed `text_order_table` resources through the shared inspector instead
    of `CatalogUi.renderDetail()`.
  - Removed the old text-order-specific resource detail blob from
    `renderResourceDetail()`.
- 2026-05-05: Palette and indexed-image resource detail moved to structured
  inspector sections.
  - Added palette/image inspector sections for Summary, Source, Evidence
    Status, Palette or Indexed Image, Palette Context, Scene Usages, optional
    Source References, optional Unknown Descriptors, and Raw Evidence.
  - Routed `lba2_palette`, `screen_palette`, `xpl_palette_bundle`,
    `lba2_texture_atlas_indexed`, `lba2_indexed_image_256`, and
    `screen_indexed_image_640x480` resources through the shared inspector
    instead of `CatalogUi.renderDetail()`.
  - Kept migrated resource visuals as resource selections even when the backend
    returns a sprite-compatible preview payload.
  - Removed the old palette/indexed-image-specific resource detail blobs from
    `renderResourceDetail()`.
- 2026-05-05: Runtime table resource detail moved to structured inspector
  sections.
  - Added runtime table inspector sections for Summary, Source, Evidence
    Status, Runtime Table or layout-specific table section, Sampled Records,
    Scene Usages, optional Source References, optional Unknown Descriptors, and
    Raw Evidence.
  - Routed `file3d_table`, `sprite_zv_table`, `ress_offset_record_table`,
    `ress_fixed_s16x8_table`, `ress_ext_size_info`, and `acf_name_list`
    resources through the shared inspector instead of
    `CatalogUi.renderDetail()`.
  - Removed the old runtime-table-specific resource detail blobs from
    `renderResourceDetail()`.
- 2026-05-05: Holomap resource detail moved to structured inspector sections.
  - Added holomap inspector sections for Summary, Source, Evidence Status,
    Holomap, Sampled Records, Text Links, Scene Usages, optional Source
    References, optional Unknown Descriptors, and Raw Evidence.
  - Routed `holomap_globe_uv_map`, `holomap_globe_altitude_map`,
    `holomap_globe_texture_map`, `holomap_arrow_table`,
    `holomap_plan_image_640x480`, and `holomap_plan_view_params` resources
    through the shared inspector instead of `CatalogUi.renderDetail()`.
  - Removed the old holomap-specific resource detail blobs from
    `renderResourceDetail()`.
- 2026-05-05: Background resource detail moved to structured inspector
  sections.
  - Added background inspector sections for Summary, Source, Evidence Status,
    Background, Composition, Sampled Records, Scene Usages, optional Source
    References, optional Unknown Descriptors, and Raw Evidence.
  - Routed `bkg_header`, `bkg_grid_map`, `bkg_grm_fragment`,
    `bkg_block_table`, `bkg_brick_graphic`, and `bkg_cube_map` resources
    through the shared inspector instead of `CatalogUi.renderDetail()`.
  - Kept background grid and brick visuals as resource selections even when the
    loaded payload is sprite-compatible.
  - Removed the old background-specific resource detail blobs and obsolete
    background HTML helpers from `renderResourceDetail()`.
- 2026-05-05: Scene runtime-layout detail moved to structured inspector
  sections.
  - Added scene inspector sections for Summary, Source, Evidence Status, World,
    Background, Hero Scripts, Runtime Links, Render Contract, Sampled Objects,
    Zones Tracks Patches, optional Unknown Descriptors, and Raw Evidence.
  - Routed `scene_runtime_layout_partial` scene assets through the shared
    inspector instead of `CatalogUi.renderDetail()`.
  - Removed the old scene-specific catalog detail blob and obsolete scene HTML
    helpers from `CatalogUi.renderDetail()`.
- 2026-05-05: Unclassified RESS payload detail moved to structured inspector
  sections.
  - Added unclassified resource inspector sections for Summary, Source,
    Evidence Status, Resource Payload, Scene Usages, optional Source
    References, optional Unknown Descriptors, and Raw Evidence.
  - Routed `ress_unclassified_payload` resources through the shared inspector
    instead of `CatalogUi.renderDetail()`.
  - Removed the old generic resource detail blob from `CatalogUi.renderDetail()`
    and deleted its obsolete resource HTML helpers.
- 2026-05-05: Raw/deferred animation detail moved to structured inspector
  sections.
  - Added raw animation inspector sections for Summary, Source, Evidence
    Status, Raw Payload, Header Words, Scene Usages, optional ANIM3DS Range,
    optional Unknown Descriptors, and Raw Evidence.
  - Routed raw animation and raw/deferred sprite payloads through the shared
    inspector instead of `CatalogUi.renderDetail()`.
  - Deleted `CatalogUi.renderDetail()` and its obsolete raw-detail HTML helper
    functions.
- 2026-05-05: First Resource workspace route.
  - Added a Resource View peer workspace with resource title, provenance meta,
    compact resource facts, visual preview canvas for indexed/background/brick
    resource frames, and audio controls for decoded sample resources.
  - Routed resource assets returned as `resource` payloads and visual resources
    returned as sprite-compatible payloads into Resource View with resource
    selection ownership.
  - Removed the old sidebar sample-audio preview path so decoded samples have
    one UI owner.
- 2026-05-05: First workbench shell dock split.
  - Split the previous overloaded sidebar into a left Explorer Dock and right
    Inspector Dock around the center workspace.
  - Moved Active Selection, shared inspector search/sections, and export
    controls into the Inspector Dock.
  - Preserved the existing workspace surfaces while moving toward the canonical
    Explorer -> Workspace -> Inspector structure.
- 2026-05-05: Model workspace controls moved next to the viewport.
  - Moved polygon/line/sphere/wireframe/grid/background/horizon toggles,
    zoom/reset controls, and model stats out of the Explorer Dock and into a
    compact Model workspace panel.
  - Kept the existing control ids and behavior while changing ownership to the
    model visual surface.
- 2026-05-05: Model UV inspector moved next to the viewport.
  - Moved the polygon selector, atlas preview, UV facts, previous/copy/next
    controls, and JSON download action out of the Explorer Dock and into the
    Model workspace panel.
  - Kept the existing UV inspector ids and behavior while changing ownership to
    the model visual surface.
- 2026-05-05: Decode progress moved to the Evidence panel.
  - Added a bottom Evidence/Timeline region to the workbench grid.
  - Moved the decode progress bar and status text out of the Explorer Dock and
    into that bottom Evidence region.
  - Kept the existing decode progress ids and polling behavior while changing
    ownership to the evidence surface.
- 2026-05-05: Runtime sprite resolver moved to the Entity workspace.
  - Moved the runtime flags/Sprite/Body.Num/Object/LabelTrack form, Resolve
    action, Open action, and resolver result out of Explorer Dock and into the
    Scene/Entity workspace usage panel.
  - Kept the existing runtime resolver ids and selection behavior while
    changing ownership to the runtime evidence workspace.
  - Tightened the narrow Entity workspace grid so resolved evidence trails do
    not push the runtime resolver out of the workspace stack.
- 2026-05-05: Export results moved to Evidence and export artifacts gained
  structured inspector sections.
  - Moved the export result status out of the Inspector Dock and into the bottom
    Evidence panel.
  - Added structured inspector sections for `evidence_artifact` selections:
    Summary, Evidence Status, Source, Export, and Unknown Descriptors.
  - Browser export no longer invokes a Tk directory picker when `output_dir` is
    omitted; it writes to the canonical repo-local `exports/<asset-id>/`
    directory and still honors explicit `output_dir` requests.
  - Recorded the old headless Tk-dialog trap in `ISSUES.md`.
- 2026-05-05: Main view tabs replaced with the workspace switcher.
  - Replaced the `main-tabs`/`main-tab` tablist markup with a
    `workspace-switcher` and pressed-state workspace buttons.
  - Removed `role="tab"`, `role="tabpanel"`, and `aria-selected` ownership
    from the peer workspace sections.
  - Kept the existing workspace ids and non-destructive switching behavior,
    with active state now expressed through `aria-pressed`.
- 2026-05-06: Scene object evidence promoted to active selection and shared
  inspector.
  - Added scene-object selection construction from entity workflow payloads,
    including stable id, scene source, provenance, evidence status, linked
    entrypoint/visual assets, and entity evidence payload.
  - Added scene-object inspector sections for Summary, Source, Evidence Status,
    Runtime State, Render Contract, Visual Links, Script Links, Port
    Implications, and Unknown Descriptors.
  - Replaced the Entity workspace's local render-contract/script/port detail
    sections with a compact selected-entity summary so the shared inspector is
    the canonical explanation path.
  - Opening linked visual assets from Entity/runtime context now preserves the
    owning scene-object selection and inspector trail while switching to the
    visual workspace.
- 2026-05-06: Model UV polygon evidence promoted to active selection and shared
  inspector.
  - Added `model_surface` selection construction from UV inspector polygon
    evidence, including stable id, source, evidence status, linked model asset,
    export action, material, render flags, UV group, and atlas sample facets.
  - Added shared model-surface inspector sections: Summary, Source, Evidence
    Status, Surface, Render Flags, UV Evidence, and Unknown Descriptors.
  - Kept model selection as the initial asset selection; explicit UV polygon
    selector/previous/next actions promote the surface selection.
  - Preserved model export affordance from the selected surface by linking the
    surface export action back to the owning model asset.
- 2026-05-06: Sprite frame sequence strip moved into the Evidence panel.
  - Added a bottom-panel Sprite Frames strip with one item per decoded sequence
    frame or frame variant.
  - Labeled each strip item with frame identity, backend (`ANIM3DS`,
    `SPRITES`, `SPRIRAW`, preview/decode-only variants), palette source, and
    timing status.
  - Routed strip clicks through the same sequence loader as Sprite previous,
    next, scrub, and playback so active `sprite_frame` selection, metadata, and
    export affordance stay synchronized.
  - Kept direct sprite catalog selection in Sprite workspace as a sprite-frame
    selection while preserving scene-object selection only for linked visual
    opens from runtime/entity context.
- 2026-05-06: Animation sequence samples promoted to active selection and
  Evidence strip.
  - Added a bottom-panel Animation Samples strip populated from the existing
    `/api/animation/sequence` playback loader.
  - Added `animation_sample` selection construction for BODY+ANIM sequence
    samples, preserving body id, animation id, sequence index, source frame,
    elapsed timing, segment, loop/playback indexes, root motion, and export
    affordance back to the body asset.
  - Added shared animation-sample inspector sections: Summary, Source,
    Evidence Status, Animation Sample, Playback Sequence, and Pose.
  - Routed strip clicks through the same animation seek/render path as scrub
    and playback so model pose, readout, current strip item, active selection,
    and inspector stay synchronized.
- 2026-05-06: Resource sampled records promoted to active selection and shared
  inspector.
  - Added a selectable Resource workspace record strip for sampled resource
    records, text message ids, sampled names, background cell refs, and occupied
    background cells when those decoded payloads are present.
  - Added `resource_record` selection construction with stable id, source,
    provenance, evidence status, parent resource link, record kind, summary,
    detail, and export affordance back to the parent resource when supported.
  - Added shared resource-record inspector sections: Summary, Source, Evidence
    Status, and Resource Record.
  - Kept direct resource catalog selection resource-owned even when the resource
    has scene usages; scene-object promotion remains an explicit Entity/runtime
    evidence path.
- 2026-05-06: Reverse scene usages promoted through a bottom Evidence strip.
  - Added a Scene Usages strip in the bottom Evidence panel for active catalog
    assets, sprite-frame selections, and resource-record selections backed by a
    parent catalog asset with reverse `scene_usages`.
  - Added `scene_usage` selection construction with stable ids preserving
    parent asset, scene asset, object slot, script kind, reference key/value,
    zone/record facets, source, provenance, status, and links back to the
    selected asset and scene.
  - Added shared scene-usage inspector sections: Summary, Source, Evidence
    Status, and Scene Usage.
  - Kept usage selection non-destructive to the current workspace while showing
    the Entity workspace suggestion.
- 2026-05-06: Raw descriptor evidence moved into the bottom Evidence panel.
  - Added a Raw Descriptors table surface in the bottom Evidence panel.
  - Populated it from the active selection's backing catalog asset when
    `unknown_descriptors` are present, including section, offset, length,
    confidence, note, and SHA-256.
  - Kept the table scrollable and bounded so bulky descriptor evidence does not
    crowd the shared Inspector or resize the workbench.
- 2026-05-06: Script/control-flow evidence moved into the bottom Evidence
  panel.
  - Added a Script Evidence table surface in the bottom Evidence panel for
    scene-backed selections.
  - Populated it from decoded SCENE reconnaissance for selected scene assets,
    scene-object selections, scene-usage selections, and scene-backed preview
    frame selections.
  - Included stable row ids, script kind, offsets, opcodes, byte lengths,
    behavior categories/effects, and resolved or missing control-flow targets.
  - Kept sampled instruction/control-flow rows scrollable and bounded so bulky
    script evidence stays out of the shared Inspector.
- 2026-05-06: Port promotion packet state moved into the bottom Evidence panel.
  - Added a read-only promotion packet endpoint that loads the canonical
    `D:\repos\reverse\littlebigreversing\docs\promotion_packets\manifest.json`
    and matching fixture sources without searching alternate roots or writing
    packet files.
  - Added a Port Evidence table for scene-backed selections showing packet id,
    evidence class, promotion status, canonical runtime flag, runtime contract
    ids, fixture path, and source doc link.
  - Preserved the promotion rule that `canonical_runtime: true` is shown only
    for `live_positive` or `approved_exception` packets; live-negative packets
    stay non-canonical, and missing packets remain unknown/unpromoted.
  - Added backend tests for fixture scene extraction and the canonical-runtime
    status guard.
- 2026-05-06: Final replay audit hardening.
  - Added a monotonic catalog selection request guard so a slow older
    `/api/catalog/load` response cannot repaint the workspace after a newer
    active selection.
  - Recorded the async selection drift trap in `ISSUES.md`.
- 2026-05-06: Resource long-tail replay audit.
  - Validated palette, runtime table with unknown per-record semantics, Smacker
    video, and SCREEN indexed image resources through the Resource workspace.
  - Confirmed the canonical asset root has zero `ress_unclassified_payload`
    resources and zero unknown resource entries in the HQR coverage summary.
- 2026-05-06: Scene/entity evidence facets promoted to active selections.
  - Added entity workspace evidence-target buttons for selected object runtime
    state, File3D resolution, and render contract.
  - Added per-usage evidence-target buttons for File3D, runtime sprite, and
    ANIM3DS range rows when the usage payload exposes those fields.
  - Added generic shared inspector sections for `runtime_sprite_state`,
    `file3d_resolution`, `anim3ds_range_state`, `render_contract`, and
    `palette_context` facet selections.
- 2026-05-06: Resource palette context promoted to active selections.
  - Added a Resource workspace `Palette Context` record when resource payloads
    expose palette entry, paired entry, scene palette references, runtime
    reference, or source provenance.
  - Added `palette_context` selection construction for Resource records,
    preserving the source asset id and resolved palette entry in the stable id,
    links, provenance, and shared inspector facets.
- 2026-05-06: Evidence status visual states split.
  - Split status badge CSS so source-backed, decoded-only, render-only,
    live-confirmed, port-implied, unknown, intentionally-deferred,
    preview-only, live-positive, live-negative, and approved-exception statuses
    do not share identical computed colors.
- 2026-05-06: Port `decode_only` status styled separately.
  - Completion audit found that promotion packets can use port status
    `decode_only`, while viewer selections use `decoded_only`; added a
    distinct CSS badge state for `decode_only` so port packet rows do not fall
    back to the generic evidence badge.
- 2026-05-06: Model stats renderer no longer uses HTML strings.
  - Replaced the Model workspace stats `innerHTML` renderer with explicit DOM
    text nodes so decoded model stats remain a structured workspace surface
    instead of an HTML-string detail path.
- 2026-05-06: Animation compatibility labels made evidence-explicit.
  - Renamed the frontend's bone-count-only animation match state away from
    `fallback` and fixed File3D allow-list handling so non-`BODY.HQR` models
    with matching bone counts are not labeled as fully compatible.
  - The compatible animation selector now prefixes those entries with
    `[bones]`, making the weaker evidence visible instead of implying a
    compatibility bridge.
- 2026-05-06: Render contract object summaries replaced JSON rows.
  - Replaced frontend `JSON.stringify` rendering for scene-object
    `render_phase` and `redraw_contract` evidence with named summaries for
    scene redraw setup, tree insertion, recovery method, moving-box behavior,
    and z-buffer/water flags.
- 2026-05-06: Nested inspector object rows summarized as key/value evidence.
  - Replaced the remaining primary-inspector JSON fallback for nested entity
    runtime state, script-link, and holomap sampled-record objects with compact
    key/value summaries.
- 2026-05-06: Catalog search indexing no longer stringifies composition JSON.
  - Replaced the hidden Explorer search text `JSON.stringify` path for resource
    composition payloads with recursive key/value indexing, preserving semantic
    search without keeping raw JSON blobs in catalog browse state.
- 2026-05-06: Model preview palette path made evidence-explicit.
  - Renamed the renderer's synthetic color ramp from fallback language to
    diagnostic preview language and added Model workspace stats for palette and
    texture-atlas evidence, so model colors report whether they came from
    `RESS.HQR:0`/`RESS.HQR:1` evidence or diagnostic preview colors.
  - Renamed view-transient Explorer highlight state and internal local
    variables so the remaining frontend audit scan no longer reports false
    selected-asset or fallback-renderer ownership markers.
- 2026-05-06: Active Selection preview actions exposed.
  - Rendered `previewActions` as buttons beside Copy ID and Export in the
    Active Selection panel.
  - Routed target-asset preview actions through the canonical linked-asset open
    path so the linked asset can be viewed while preserving the active evidence
    selection.
- 2026-05-06: Sprite pixel evidence made explicit.
  - Added hover pixel evidence with exact `x,y`, palette index, and RGBA values
    to the Sprite workspace metadata.
  - Added click-to-pick pixel evidence that remains visible in Sprite facts
    until the sprite frame changes.
- 2026-05-06: Sprite strip thumbnails added.
  - Reused the Sprite workspace frame painting path for mini canvas thumbnails
    in the bottom-panel Sprite Frames strip.
  - Marked currently loaded strip frames as decoded and catalog-only sequence
    entries as load-on-select, preserving one loader path for frame navigation.
- 2026-05-06: Evidence row IDs made copyable.
  - Added inline Copy controls for Script Evidence `Stable ID` cells.
  - Added inline Copy controls for Port Evidence `Packet ID` cells while keeping
    packet status/canonical-runtime semantics unchanged.
- 2026-05-06: Scene object evidence table added.
  - Added a bottom-panel Scene Objects table for selected scene-backed evidence,
    showing stable object id, flags, File3D, position, linked visuals, render
    backend, Copy, and Open controls.
  - Added `/api/entity/scene-object` and a focused builder test so sampled scene
    object rows promote into the existing `scene_object` selection/inspector
    path instead of staying inspector-only facts.
- 2026-05-06: Raw descriptor row IDs made copyable.
  - Added a Stable ID column to the bottom-panel Raw Descriptors table.
  - Added inline Copy controls for descriptor ids such as
    `RESS.HQR:11#descriptor:indexed_image_semantics@0`, matching the evidence
    row copy affordance used by Script and Port evidence.
- 2026-05-06: Scene local evidence table added.
  - Added a bottom-panel Scene Locals table for selected scene-backed evidence,
    showing sampled zones, waypoints, GRM fragment links, and patch records.
  - Added copyable stable ids for local rows rooted in the scene asset:
    `#zone:*`, `#waypoint:*`, `#zone:*#grm:*`, and `#patch:*`.
  - Kept patch rows explicit about target instruction/field evidence so patch
    runtime behavior is visible without reopening folded scene inspector rows.
- 2026-05-06: Export manifests carry proof-scope evidence context.
  - Added a canonical `evidence` manifest block to model probes and server
    export manifests for sprite frames/ranges, audio, text, video, indexed
    images, holomap plans, background grids, and scene background compositions.
  - The block records stable id, evidence status, proof scope, scene usage
    count, and `runtime_contract_ids` / `promotion_packet_ids`.
  - Scene-linked export manifests now read the canonical promotion packet
    manifest and copy only packets whose fixture source scene matches the
    selected scene asset or reverse scene usage evidence.
  - Added export tests that assert the evidence block on model, server model,
    sprite, and sample export paths, plus a packet-link regression test for
    matching scene evidence.
- 2026-05-06: Resource record selection sync tightened.
  - Added a selection-driven Resource workspace record highlight path so
    `resource_record` and `palette_context` active selections keep the sampled
    Resource row marked with `aria-current`.
  - Kept palette-context canonical ids unchanged while using the attached
    `resourceRecord` evidence id for row highlighting, avoiding a second local
    selected-record truth.
- 2026-05-06: Scene asset route ownership fixed.
  - Detected scene assets returned as sprite-compatible preview payloads and
    routed them to Scene/Entity ownership with canonical asset selection and
    export evidence actions.
  - Kept the decoded scene preview payload available to the Sprite workspace
    for manual inspection without making Sprite the route owner.
  - Guarded startup model loading so async initial model fetches cannot
    overwrite a user catalog selection made during app initialization.
- 2026-05-06: Manual animation pose selection fixed.
  - Added a pose-backed `animation_sample` selection path for the Model
    workspace `Apply animation pose` command.
  - Preserved existing playback sequence sample selection while allowing the
    shared animation sample inspector to render one-off pose samples without a
    playback sequence.
  - The active selection now records BODY id, ANIM id, target/previous/next
    frame, elapsed time, duration, completion status, bone count, and root
    delta after a manual pose.
- 2026-05-06: Sprite variant selection sync fixed.
  - Routed Sprite workspace frame-variant navigation through the same
    `onFrameLoaded` selection callback used by archive-backed sprite sequence
    navigation.
  - Scene background variants such as explicit GRM-on previews now update the
    active selection to stable ids like
    `SCENE.HQR:126#frame:grm_zone_000_on` with `render_only` evidence status.
- 2026-05-06: Scene variant inspector made selection-aware.
  - Added sprite-frame variant facets to `selectionFromSpriteFrame`.
  - Scene inspector sections now show `sprite_frame` kind and a Frame section
    with variant id, variant label, format, dimensions, offset, and palette
    source when the active selection is a scene background frame variant.
- 2026-05-06: Resource clear resets record highlight state.
  - Reset `ResourceWorkspace.currentRecordId` in `clear()` so the workspace's
    empty state cannot retain an old sampled record highlight.
  - Validated the clear path by selecting a resource palette-context row, then
    switching to a model asset and confirming no resource row remains selected.
- 2026-05-06: Entity ANIM3DS range facet promoted.
  - Carried `links.sprite.anim3ds_range` into selected entity contract
    `initial_state`.
  - Added the selected entity `ANIM3DS` evidence target and implemented
    `selectionFromEntityFacet(..., 'anim3ds_range_state')`.
  - Added a regression test for selected entity contracts preserving ANIM3DS
    range timing and range identity.
- 2026-05-06: Sprite picked pixel promoted into selection facets.
  - Added a Sprite workspace picked-pixel callback to update the current
    `sprite_frame` selection with pixel coordinates, palette index, and RGBA.
  - Rendered picked pixel rows in sprite and scene background frame inspector
    sections.
  - Kept hover evidence local/transient because it changes with pointer motion
    and is not a durable selection.

## Validation Notes

- 2026-05-05 selection backbone browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, wait for the catalog summary to show loaded assets, and
       confirm the Active Selection panel starts with `No active selection`.
    2. Select `BODY.HQR[19]` / `BODY.HQR:19`. Expected: Active Selection shows
       kind `asset`, stable id `BODY.HQR:19`, source `BODY.HQR[19]`, status
       `decoded_only`, workspace `model`, `Copy ID`, and `Export evidence
       bundle`. Observed as expected.
    3. Resolve runtime sprite state with flags `0x400`, Sprite `127`,
       Body.Num `127`, Object `7`. Expected: Active Selection changes to a
       runtime resolution preserving flags, sprite, object, and Body.Num in the
       stable id. Observed stable id
       `runtime_sprite_state:flags=0x400;sprite=127;object=7;body_num=127`,
       status `source_backed`, link `SPRITES.HQR:127`, and provenance from the
       runtime resolver rule.
    4. Open the resolved sprite. Expected: Active Selection changes to a
       sprite-frame selection with stable id, source, evidence status, scene
       usage links, unknown descriptors, and export affordance. Observed
       `SPRITES.HQR:127#frame:127`, source `SPRITES.HQR[127]`, status
       `decoded_only`, scene-object usage links, unknown descriptor text, and
       `Export evidence bundle`.
  - Screenshot: `docs/validation-selection-backbone-2026-05-05.png`.
  - Commands:
    - `npm run build` passed.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 model inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Select `BODY.HQR[19]` / `BODY.HQR:19`.
    3. Expected: the Active Selection panel shows stable id `BODY.HQR:19`,
       status `decoded_only`, workspace `model`, and export affordance.
    4. Expected: the detail area is no longer a freeform model detail blob; it
       shows structured inspector sections. Observed `7 structured inspector
       sections` with Summary, Source, Evidence Status, Geometry, Runtime,
       Scene Usages, and Raw Evidence. Summary/Source/Evidence/Geometry were
       open by default, and Raw Evidence was folded.
    5. Search inspector sections for `geometry`. Expected: only the Geometry
       section remains visible with vertices, polygons, bones, lines, spheres,
       and UV groups. Observed as expected.
  - Screenshot: `docs/validation-model-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 animation inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Select `BODY.HQR[19]`, then use the compatible animation selector to
       select `ANIM.HQR:3`.
    3. Expected: Active Selection changes to `ANIM.HQR:3`, status
       `decoded_only`, workspace `model`.
    4. Expected: the detail area shows structured animation inspector sections,
       not the old animation blob. Observed `7 structured inspector sections`
       with Summary, Source, Evidence Status, Animation, Runtime, Scene Usages,
       and Raw Evidence. Summary/Source/Evidence/Animation were open by
       default, and Raw Evidence was folded.
    5. Search inspector sections for `loop`. Expected: only the Animation
       section remains visible and shows loop frame/timing facts. Observed as
       expected.
  - Screenshot: `docs/validation-animation-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 sprite frame inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `SPRITES.HQR:127` and select
       `Runtime sprite 127 (SPRITES.HQR:127)`.
    3. Expected: Active Selection changes to a sprite-frame selection with
       stable id `SPRITES.HQR:127#frame:127`, source `SPRITES.HQR[127]`,
       status `decoded_only`, scene usage links, unknown descriptors, and
       export affordance. Observed as expected.
    4. Expected: the detail area shows structured sprite frame inspector
       sections, not the old decoded sprite blob. Observed `8 structured
       inspector sections` with Summary, Source, Evidence Status, Frame,
       Runtime, Scene Usages, Unknown Descriptors, and Raw Evidence. Summary,
       Source, Evidence, Frame, and Runtime were open by default, and Raw
       Evidence was folded.
    5. Search inspector sections for `runtime`. Expected: Runtime remains
       visible with backend, archive, runtime sprite index, rule, flags,
       hotspot, and bounds. Observed Summary and Runtime visible because the
       selected label also contains "Runtime".
  - Screenshot: `docs/validation-sprite-frame-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 ANIM3DS range inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `ANIM3DS.HQR:127` and select
       `ANIM3DS frame range table (13 animations)`.
    3. Expected: Active Selection shows stable id `ANIM3DS.HQR:127`, source
       `ANIM3DS.HQR[127]`, status `source_backed`, and workspace `sprite`.
       Observed as expected.
    4. Expected: the detail area shows structured ANIM3DS range sections, not
       the old range metadata blob. Observed `7 structured inspector sections`
       with Summary, Source, Evidence Status, Ranges, Runtime Playback,
       Warnings, and Raw Evidence. Summary, Source, Evidence, Ranges, and
       Runtime Playback were open by default, and Raw Evidence was folded.
    5. Search inspector sections for `timing`. Expected: only Runtime Playback
       remains visible and shows the timing source and playback rules. Observed
       as expected.
  - Screenshot: `docs/validation-anim3ds-range-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 sample audio inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `SAMPLES.HQR:0` and select
       `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`.
    3. Expected: Active Selection shows stable id `SAMPLES.HQR:0`, source
       `SAMPLES.HQR[0]`, status `source_backed`, workspace `resource`, scene
       usage links, and export affordance. Observed as expected.
    4. Expected: the detail area shows structured sample audio sections, not
       the old resource detail blob. Observed `7 structured inspector sections`
       with Summary, Source, Evidence Status, Audio, Wave Container, Scene
       Usages, and Raw Evidence. Summary, Source, Evidence, Audio, and Wave
       Container were open by default, and Raw Evidence was folded.
    5. Expected: the audio preview remains available. Observed sample preview
       visible with `Sample 0 | pcm | 22050Hz | 1ch | 2083.447 ms` and audio
       source `/api/catalog/audio?id=SAMPLES.HQR%3A0`.
    6. Search inspector sections for `sample rate`. Expected: only the Audio
       section remains visible and shows rate/duration facts. Observed as
       expected.
  - Screenshot: `docs/validation-sample-audio-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 Smacker video inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `VIDEO.HQR:0` and select
       `ACF movie ASCENSEU.SMK (VIDEO.HQR:0)`.
    3. Expected: Active Selection shows stable id `VIDEO/VIDEO.HQR:0`, source
       `VIDEO/VIDEO.HQR[0]`, status `source_backed`, workspace `resource`,
       scene usage link, and export affordance. Observed as expected.
    4. Expected: the detail area shows structured Smacker video sections, not
       the old resource detail blob. Observed `7 structured inspector sections`
       with Summary, Source, Evidence Status, Video, Smacker Container, Scene
       Usages, and Raw Evidence. Summary, Source, Evidence, Video, and Smacker
       Container were open by default, and Raw Evidence was folded.
    5. Search inspector sections for `frames`. Expected: only the Video section
       remains visible and shows dimensions, frame count, FPS, and duration.
       Observed as expected.
  - Screenshot: `docs/validation-smacker-video-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 text payload inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, trigger Index if the UI has not yet loaded catalog
       state, and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `TEXT.HQR:7` and select
       `Text payload bank English/000 (TEXT.HQR:7)`.
    3. Expected: Active Selection shows stable id `TEXT.HQR:7`, source
       `TEXT.HQR[7]`, status `source_backed`, workspace `resource`, scene
       usage links, and export affordance. Observed as expected.
    4. Expected: the detail area shows structured text payload sections, not
       the old resource detail blob. Observed `7 structured inspector sections`
       with Summary, Source, Evidence Status, Text Bank, Sampled Records, Scene
       Usages, and Raw Evidence. Summary, Source, Evidence, Text Bank, and
       Sampled Records were open by default, and Raw Evidence was folded.
    5. Search inspector sections for `Zoé`. Expected: only Sampled Records
       remains visible and shows the matching preview row. Observed as expected.
  - Screenshot: `docs/validation-text-payload-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 text order inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `TEXT.HQR:6` and select
       `Text order table English/000 (TEXT.HQR:6)`.
    3. Expected: Active Selection shows stable id `TEXT.HQR:6`, source
       `TEXT.HQR[6]`, status `source_backed`, workspace `resource`, and export
       affordance. Observed as expected.
    4. Expected: the detail area shows structured text order sections, not the
       old resource detail blob. Observed `6 structured inspector sections`
       with Summary, Source, Evidence Status, Text Order, Sampled Message IDs,
       and Raw Evidence. Summary, Source, Evidence, Text Order, and Sampled
       Message IDs were open by default, and Raw Evidence was folded.
    5. Search inspector sections for `paired`. Expected: Text Order remains
       visible and shows the paired text bank. Observed Text Order and the
       matching Evidence Status section visible.
  - Screenshot: `docs/validation-text-order-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 palette/indexed-image inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `RESS.HQR:0` and select
       `LBA2 palette (RESS.HQR:0)`. Expected: Active Selection shows stable id
       `RESS.HQR:0`, source `RESS.HQR[0]`, status `decoded_only`, and
       workspace `resource`; the inspector shows Summary, Source, Evidence
       Status, Palette, Palette Context, Scene Usages, and Raw Evidence.
       Observed as expected.
    3. Search the explorer for `RESS.HQR:11` and select
       `Indexed image (RESS.HQR:11)`.
    4. Expected: the migrated visual resource remains an asset/resource
       selection, not a sprite-frame selection. Observed Active Selection kind
       `asset`, stable id `RESS.HQR:11`, source `RESS.HQR[11]`, status
       `decoded_only`, workspace `resource`, unknown descriptor summary, and
       export affordance.
    5. Expected: the detail area shows structured indexed-image sections, not
       the old resource detail blob. Observed `8 structured inspector sections`
       with Summary, Source, Evidence Status, Indexed Image, Palette Context,
       Scene Usages, Unknown Descriptors, and Raw Evidence.
    6. Search inspector sections for `palette source`. Expected: only Palette
       Context remains visible and shows `RESS.HQR:0`. Observed as expected.
  - Screenshot: `docs/validation-palette-image-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 runtime table inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `RESS.HQR:1` and select
       `RESS offset table (RESS.HQR:1)`.
    3. Expected: Active Selection shows stable id `RESS.HQR:1`, source
       `RESS.HQR[1]`, status `decoded_only`, workspace `resource`, unknown
       descriptor summary, and no sprite/model ownership. Observed as expected.
    4. Expected: the detail area shows structured runtime-table sections, not
       the old resource detail blob. Observed `8 structured inspector sections`
       with Summary, Source, Evidence Status, Runtime Table, Sampled Records,
       Scene Usages, Unknown Descriptors, and Raw Evidence.
    5. Search inspector sections for `record length`. Expected: only Runtime
       Table remains visible and shows record length counts. Observed as
       expected.
  - Screenshot: `docs/validation-runtime-table-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 holomap inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `HOLOMAP.HQR` and select
       `Holomap arrow table (HOLOMAP.HQR:12)`.
    3. Expected: Active Selection shows stable id `HOLOMAP.HQR:12`, source
       `HOLOMAP.HQR[12]`, status `source_backed`, workspace `resource`, and no
       model/sprite ownership. Observed as expected.
    4. Expected: the detail area shows structured holomap sections, not the old
       resource detail blob. Observed `8 structured inspector sections` with
       Summary, Source, Evidence Status, Holomap, Sampled Records, Text Links,
       Scene Usages, and Raw Evidence.
    5. Search inspector sections for `localized`. Expected: Holomap and Text
       Links remain visible because both contain localized text-link evidence.
       Observed as expected.
  - Screenshot: `docs/validation-holomap-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 background inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `LBA_BKG.HQR` and select
       `Background grid map 0 (LBA_BKG.HQR:1)`.
    3. Expected: Active Selection shows stable id `LBA_BKG.HQR:1`, source
       `LBA_BKG.HQR[1]`, status `source_backed`, workspace `resource`, and no
       sprite/model ownership. Observed as expected.
    4. Expected: the detail area shows structured background sections, not the
       old resource detail blob. Observed `8 structured inspector sections`
       with Summary, Source, Evidence Status, Background, Composition,
       Sampled Records, Scene Usages, and Raw Evidence.
    5. Search inspector sections for `cells`. Expected: background/composition
       evidence rows remain visible, including transparent code cells and
       column-cell counts. Observed as expected.
  - Screenshot: `docs/validation-background-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 scene inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `SCENE.HQR`, set the kind filter to `Scenes`,
       and select `Scene 0 (SCENE.HQR:1)`.
    3. Expected: Active Selection shows stable id `SCENE.HQR:1`, source
       `SCENE.HQR[1]`, status `decoded_only`, workspace `entity`, and no
       model/resource ownership. Observed as expected.
    4. Expected: the detail area shows structured scene sections, not the old
       scene detail blob. Observed Summary, Source, Evidence Status, World,
       Background, Hero Scripts, Runtime Links, Render Contract, Sampled
       Objects, Zones Tracks Patches, Unknown Descriptors, and Raw Evidence.
    5. Search inspector sections for `GRI`. Expected: source-backed background
       and render-contract evidence rows remain visible. Observed as expected.
  - Screenshot: `docs/validation-scene-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 unclassified resource inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root: temporary validation root
    `%TEMP%\lm2-viewer-unclassified-validation` containing a synthetic
    `RESS.HQR` with one `RESS.HQR:7` raw payload. The canonical full LBA2 root
    had no `ress_unclassified_payload` entries to exercise this path.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Select `Unclassified RESS payload (RESS.HQR:7)`.
    3. Expected: Active Selection shows stable id `RESS.HQR:7`, source
       `RESS.HQR[7]`, status `decoded_only`, workspace `resource`, and the
       unclassified payload unknown descriptor. Observed as expected.
    4. Expected: the detail area shows structured unclassified-resource
       sections, not the old generic resource detail blob. Observed Summary,
       Source, Evidence Status, Resource Payload, Scene Usages, Unknown
       Descriptors, and Raw Evidence.
    5. Search inspector sections for `preview hex`. Expected: Resource Payload
       remains visible with preview hex `72617721`. Observed as expected.
  - Screenshot:
    `docs/validation-unclassified-resource-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 raw animation inspector section browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root: temporary validation root
    `%TEMP%\lm2-viewer-raw-animation-validation` containing a synthetic
    `ANIM.HQR` with one `ANIM.HQR:1` payload rejected by the animation parser.
    The canonical full LBA2 root had no raw animation entries to exercise this
    path.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show one raw
       animation entry.
    2. Select `ANIM.HQR animation 1`.
    3. Expected: Active Selection shows stable id `ANIM.HQR:1`, source
       `ANIM.HQR[1]`, status `intentionally_deferred`, workspace `model`, and
       unknown descriptor summaries. Observed as expected.
    4. Expected: the detail area shows structured raw-animation sections, not
       the old raw detail blob. Observed `8 structured inspector sections`
       with Summary, Source, Evidence Status, Raw Payload, Header Words, Scene
       Usages, Unknown Descriptors, and Raw Evidence.
    5. Search inspector sections for `header words`. Expected: only Header
       Words remains visible with the retained little-endian header words.
       Observed as expected.
  - Screenshot:
    `docs/validation-raw-animation-inspector-sections-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 Resource workspace browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Visual resource flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `RESS.HQR:11` and select
       `Indexed image (RESS.HQR:11)`.
    3. Expected: Active Selection remains kind `asset` with stable id
       `RESS.HQR:11`, source `RESS.HQR[11]`, status `decoded_only`, workspace
       `resource`, and export affordance. Observed as expected.
    4. Expected: Resource View, not Sprite View or Model View, becomes the
       selected workspace. Observed selected tab `Resource View`, with Model
       and Sprite panels hidden.
    5. Expected: Resource View shows a 256x256 canvas preview, resource layout
       facts, palette provenance, and the shared structured inspector remains
       populated. Observed as expected.
  - Audio resource flow:
    1. Search the explorer for `SAMPLES.HQR:0` and select
       `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`.
    2. Expected: Active Selection remains kind `asset`, stable id
       `SAMPLES.HQR:0`, status `source_backed`, workspace `resource`, and
       export affordance. Observed as expected.
    3. Expected: Resource View remains selected and shows the audio control
       sourced from `/api/catalog/audio?id=SAMPLES.HQR%3A0`; the old sidebar
       sample preview is absent. Observed as expected.
  - Screenshots:
    - `docs/validation-resource-workspace-visual-2026-05-05.png`.
    - `docs/validation-resource-workspace-audio-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 workbench shell dock browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Desktop flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Expected: the Explorer Dock is a left column, the active workspace is a
       center column, and the Inspector Dock is a right column. Observed element
       bounds: Explorer `x=0 width=320`, workspace `x=320 width=584`, Inspector
       `x=904 width=360` on a 1264px-wide browser viewport.
    3. Expected: Active Selection, inspector search/sections, and Export are in
       the right Inspector Dock, while catalog search/list remain in the left
       Explorer Dock. Observed as expected.
  - Narrow viewport flow:
    1. Set the browser viewport to `390x740`.
    2. Expected: the shell remains usable without overlapping UI by stacking
       workspace, Inspector Dock, and Explorer Dock vertically. Observed bounds:
       workspace `y=0 height=311`, Inspector `y=311 height=260`, Explorer
       `y=571 height=260`.
  - Screenshots:
    - `docs/validation-workbench-shell-docks-2026-05-05.png`.
    - `docs/validation-workbench-shell-mobile-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 model workspace controls browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `BODY.HQR:19` and select
       `Twinsen with tunic and Horn of Blue Triton model`.
    3. Expected: Active Selection shows stable id `BODY.HQR:19`, source
       `BODY.HQR[19]`, status `decoded_only`, workspace `model`, and export
       affordance. Observed as expected.
    4. Expected: the Model workspace owns View toggles, zoom/reset controls, and
       Stats. Observed the `.model-tool-panel` inside the center model panel
       with polygons, lines, spheres, wireframe, grid, light canvas, horizon
       lock, zoom/reset buttons, and populated stats for 24 bones, 258
       vertices, 390 polygons, 36 lines, 5 spheres, and flags `0x110`.
    5. Expected: Explorer no longer contains model stats or model view
       controls. Observed `#explorerDock #stats` and
       `#explorerDock #showFaces` absent.
  - Screenshot:
    `docs/validation-model-workspace-controls-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 model workspace UV inspector browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the catalog summary to show loaded assets.
    2. Search the explorer for `BODY.HQR:19` and select
       `Twinsen with tunic and Horn of Blue Triton model`.
    3. Expected: Model View remains selected and Active Selection shows stable
       id `BODY.HQR:19`, source `BODY.HQR[19]`, status `decoded_only`, and
       workspace `model`. Observed as expected.
    4. Expected: UV Inspector is owned by the Model workspace panel, not the
       Explorer Dock. Observed `#modelViewPanel #uvInspector` present and
       `#explorerDock #uvInspector` absent.
    5. Expected: UV inspection is populated for the selected model. Observed
       390 polygon options, a visible atlas canvas, and facts for polygon 0.
    6. Click the next-polygon control. Expected: UV selection and facts update
       without changing workspace. Observed polygon changed from 0 to 1 with
       updated vertex facts.
  - Screenshot:
    `docs/validation-model-workspace-uv-inspector-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 Evidence panel decode-progress browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Desktop flow:
    1. Open the viewer and wait for the initial catalog to load.
    2. Expected: the shell has Explorer, Workspace, Inspector, and a bottom
       Evidence panel. Observed bounds on a 1264px-wide viewport: Explorer
       `x=0 y=0 width=320 height=453`, workspace
       `x=320 y=0 width=584 height=453`, Inspector
       `x=904 y=0 width=360 height=453`, Evidence
       `x=0 y=453 width=1264 height=116`.
    3. Expected: decode progress is owned by the Evidence panel, not Explorer.
       Observed `#evidenceDock #decodeProgress` present and
       `#explorerDock #decodeProgress` absent.
    4. Click `Index` for the canonical asset root. Expected: progress becomes
       visible in the Evidence panel while indexing. Observed
       `progressParent=evidenceDock`, text `Indexing HQR folder`, and an
       indeterminate progress bar.
  - Narrow viewport flow:
    1. Set the browser viewport to `390x740`.
    2. Expected: the shell stacks without overlap as Workspace, Inspector,
       Evidence, then Explorer. Observed bounds: workspace `y=0 height=266`,
       Inspector `y=266 height=230`, Evidence `y=496 height=96`, Explorer
       `y=592 height=230`; decode progress remained in the Evidence panel.
  - Screenshots:
    - `docs/validation-evidence-panel-decode-progress-2026-05-05.png`.
    - `docs/validation-evidence-panel-decode-progress-mobile-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 Entity workspace runtime-resolver browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Desktop flow:
    1. Open the viewer and wait for the initial catalog to load.
    2. Switch to `Entity View`.
    3. Expected: runtime sprite resolver is owned by the Entity workspace, not
       Explorer. Observed `#entityViewPanel #runtimeSpriteResolver` present,
       visible, and `#explorerDock #runtimeSpriteResolver` absent.
    4. Resolve default runtime state with flags `0x400`, Sprite `127`,
       Body.Num `127`, Object `7`. Expected: Active Selection becomes a runtime
       resolution with stable id preserving all runtime input fields. Observed
       `runtime_sprite_state:flags=0x400;sprite=127;object=7;body_num=127`,
       status `source_backed`, workspace `entity`, link `SPRITES.HQR:127`,
       and an enabled Open action.
    5. Expected: Entity workspace receives the evidence trail. Observed
       `Scene 21 object 7` with trail from runtime sprite input to
       `SPRITES.HQR:127` to `SCENE.HQR:22#object:7`.
  - Narrow viewport flow:
    1. Set the browser viewport to `390x740` after resolving the runtime state.
    2. Expected: the shell still stacks as Workspace, Inspector, Evidence,
       Explorer, the resolver remains in Entity View, and Explorer still does
       not contain it. Observed as expected; the Entity header is bounded and
       scrollable while the usage panel contains the resolver.
  - Screenshots:
    - `docs/validation-runtime-resolver-entity-workspace-2026-05-05.png`.
    - `docs/validation-runtime-resolver-entity-workspace-mobile-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 export evidence-artifact browser validation.
  - Starting URL: `http://127.0.0.1:8765/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the initial catalog to load.
    2. Search the explorer for `BODY.HQR:19` and select
       `Twinsen with tunic and Horn of Blue Triton model`.
    3. Trigger `Export evidence bundle` from the active selection.
    4. Expected: browser export writes without opening a local directory dialog.
       Observed output directory
       `D:\repos\reverse\lba2-lm2-viewer\exports\BODY.HQR_19`.
    5. Expected: Active Selection becomes an `evidence_artifact`. Observed
       stable id `BODY.HQR:19#export:manifest.json`, status `decoded_only`,
       provenance set to the output directory, and link `BODY.HQR:19`.
    6. Expected: export result is in the bottom Evidence panel, not Inspector
       Dock. Observed `#evidenceDock #exportResult` present,
       `#inspectorDock #exportResult` absent, and status
       `Wrote 5 files to ...\exports\BODY.HQR_19`.
    7. Expected: Inspector shows export artifact sections, not stale model
       sections. Observed 5 structured sections: Summary, Evidence Status,
       Source, Export, and Unknown Descriptors. The sections showed output dir,
       manifest path, file count, source asset, polygon mode, generated files,
       warning count, and proof scope `viewer export artifact; not canonical
       runtime proof`.
    8. Verified generated files exist:
       `BODY.HQR_19.obj`, `BODY.HQR_19.mtl`, `manifest.json`,
       `BODY.HQR_19_atlas.png`, and `BODY.HQR_19_uv000.png`.
  - Screenshot:
    `docs/validation-export-evidence-artifact-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-05 workspace-switcher browser validation.
  - Starting URL: `http://127.0.0.1:8878/`, served by the integrated Python
    viewer from this checkout after `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and wait for the initial catalog to load.
    2. Expected: workspace switcher exists and the legacy tab authority is
       gone. Observed `.workspace-switcher` present and `.main-tabs`,
       `.main-tab`, `[role="tab"]`, `[role="tabpanel"]`, and
       `[aria-selected]` all absent.
    3. Expected: initial state is Model workspace selected through
       `aria-pressed="true"`. Observed Model pressed and visible; Sprite,
       Entity, and Resource not pressed and hidden.
    4. Click Sprite, Entity, Resource, and Model. Expected: exactly the clicked
       workspace button is pressed and exactly the matching panel is visible.
       Observed as expected for all four workspaces.
    5. Search the explorer for `BODY.HQR:19` and select
       `Twinsen with tunic and Horn of Blue Triton model`.
    6. Switch to Resource, then back to Model. Expected: active selection and
       inspector state are not destroyed by workspace switching. Observed
       Active Selection still showed stable id `BODY.HQR:19`, source
       `BODY.HQR[19]`, status `decoded_only`, provenance `BODY.HQR[19]`, and
       workspace `model`.
  - Narrow viewport flow:
    1. Set the browser viewport to `390x740`.
    2. Expected: switcher remains visible and the shell stack does not overlap.
       Observed switcher bounds `x=78 y=8 width=234 height=28`, Model
       workspace `y=0 height=266`, Inspector `y=266 height=230`, Evidence
       `y=496 height=96`, and Explorer `y=592 height=230`.
  - Screenshots:
    - `docs/validation-workspace-switcher-2026-05-05.png`.
    - `docs/validation-workspace-switcher-mobile-2026-05-05.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 scene-object selection and inspector browser validation.
  - Starting URL: `http://127.0.0.1:8879/?scene_object_selection=3`, served by
    the integrated Python 3.12 viewer from this checkout after
    `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, switch to Entity workspace, and resolve runtime state
       with flags `0x400`, Sprite `127`, Body.Num `127`, Object `7`.
    2. Expected: the runtime/entity workflow promotes a scene object as the
       active selection. Observed Active Selection kind `scene_object`, stable
       id `SCENE.HQR:22#object:7`, source `SCENE.HQR[22]`, status
       `source_backed`, confidence `evidence`, workspace `entity`, and links
       to `SCENE.HQR:22`, entrypoint `SPRITES.HQR:127`, and linked visual
       `SPRITES.HQR:128`.
    3. Expected: scene-object details are in the shared Inspector, not a local
       Entity detail blob. Observed `9 structured inspector sections`:
       Summary, Source, Evidence Status, Runtime State, Render Contract,
       Visual Links, Script Links, Port Implications, and Unknown Descriptors.
    4. Expected: runtime state and render contract remain distinct. Observed
       Runtime State rows for flags, File3D, GenBody, GenAnim, Sprite,
       position, movement, collision, combat, and bonus. Render Contract rows
       separately showed backend, draw path, sorted insertion, recovery path,
       contract steps, source, render phase, and redraw contract.
    5. Click the resolver's `Open` action for the resolved sprite. Expected:
       the visual workspace opens without replacing the owning scene-object
       selection. Observed Sprite workspace visible with
       `Runtime sprite 127 (SPRITES.HQR:127)` while Active Selection and
       Inspector stayed on `SCENE.HQR:22#object:7`; the evidence trail still
       included runtime input -> `SPRITES.HQR:127` -> scene usage ->
       `SCENE.HQR:22#object:7`.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after opening the linked sprite.
    2. Expected: the shell stack remains usable. Observed Sprite workspace
       `y=0 height=266`, Inspector `y=266 height=230`, Evidence
       `y=496 height=96`, and Explorer `y=592 height=230`.
  - Screenshots:
    - `docs/validation-scene-object-selection-inspector-2026-05-06.png`.
    - `docs/validation-scene-object-selection-inspector-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 model-surface selection and inspector browser validation.
  - Starting URL: `http://127.0.0.1:8880/?model_surface_selection=1`, served
    by the integrated Python 3.12 viewer from this checkout after
    `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, search for `BODY.HQR:19`, and select
       `Twinsen with tunic and Horn of Blue Triton model`.
    2. Expected: initial selection remains the model asset, not an implicit
       polygon. Observed Active Selection kind `asset`, stable id
       `BODY.HQR:19`, status `decoded_only`, workspace `model`, export
       affordance enabled, and model inspector sections visible.
    3. Click UV Inspector next-polygon. Expected: explicit UV navigation
       promotes a model-surface selection. Observed Active Selection kind
       `model_surface`, stable id `BODY.HQR:19#polygon:1`, source
       `BODY.HQR[19]`, status `decoded_only`, link `BODY.HQR:19`, and export
       affordance still enabled.
    4. Expected: the Inspector explains the selected surface through structured
       sections. Observed 7 sections: Summary, Source, Evidence Status,
       Surface, Render Flags, UV Evidence, and Unknown Descriptors.
    5. Select first textured polygon option, `Polygon 382 - texture 0`.
       Expected: UV evidence includes texture group and atlas samples. Observed
       stable id `BODY.HQR:19#polygon:382`, Render type `0x8`, texture `0`,
       UV group `0`, encoded `0,0 255x255`, sampled region `0,0 256x256`,
       UV coordinates, and atlas sample colors.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting textured polygon 382.
    2. Expected: the shell stack remains usable. Observed Model workspace
       `y=0 height=266`, Inspector `y=266 height=230`, Evidence
       `y=496 height=96`, and Explorer `y=592 height=230`.
  - Screenshots:
    - `docs/validation-model-surface-selection-inspector-2026-05-06.png`.
    - `docs/validation-model-surface-selection-inspector-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 sprite frame strip browser validation.
  - Starting URL: `http://127.0.0.1:8881/?sprite_frame_strip=3`, served by the
    integrated Python 3.12 viewer from this checkout after `npm run build` from
    `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, filter Explorer to Sprites, search for
       `ANIM3DS.HQR:0`, and select `COQU sprite frame 0`.
    2. Expected: direct sprite catalog selection opens Sprite workspace and
       promotes a `sprite_frame` selection. Observed stable id
       `ANIM3DS.HQR:0#frame:0`, status `decoded_only`, provenance
       `RESS.HQR:0 normal palette`, export affordance, and 33 frame-strip
       items.
    3. Expected: the strip preserves frame identity, backend, palette source,
       and decoded timing status. Observed first/current strip item
       `COQU frame 0`, `ANIM3DS`, `normal RESS.HQR:0 preview palette`, and
       `decoded ANIM3DS range order; FPS needs scene object evidence`.
    4. Click strip item 3. Expected: the frame loader and active selection move
       to frame 3. Observed the frame label advance to `4 / 33` and the current
       strip item become `COQU frame 3`.
    5. Click Sprite Next. Expected: the same sequence state advances to frame
       4. Observed current strip item `COQU frame 4`, frame label `5 / 33`, and
       sprite metadata `COQU frame 4 - anim3ds Sprite 4 - 134x87 ... decoded
       ANIM3DS range order; FPS needs scene object evidence`.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting frame 4.
    2. Expected: the shell remains usable, the Evidence panel stacks to one
       column, and the frame strip scrolls horizontally without increasing page
       width. Observed document width `390`, Evidence grid column `351px`, and
       strip bounds `clientWidth=351`, `scrollWidth=11605`.
  - Screenshots:
    - `docs/validation-sprite-frame-strip-2026-05-06.png`.
    - `docs/validation-sprite-frame-strip-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 animation sequence strip browser validation.
  - Starting URL: `http://127.0.0.1:8882/?animation_sequence_strip=1`,
    served by the integrated Python 3.12 viewer from this checkout after
    `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and select `BODY.HQR:19` / `Twinsen with tunic and Horn
       of Blue Triton model`.
    2. Select compatible animation `Turn left (ANIM.HQR:3)`.
    3. Expected: the animation controls are adjacent to the model workspace and
       the Animation Samples strip is empty before sequence load. Observed
       `Twinsen with tunic and Horn of Blue Triton model + Turn left
       (ANIM.HQR:3)`, Play enabled, and `No animation sequence strip`.
    4. Click Play. Expected: existing animation sequence loader populates the
       bottom strip and playback promotes the current sample selection.
       Observed 51 `animation-sample-item` entries and shared inspector
       sections for `animation_sample`.
    5. Stop playback and click strip item `Sample 4`. Expected: the same
       sequence seek/render path updates the model pose, readout, strip
       current item, active selection, and inspector. Observed active selection
       stable id `BODY.HQR:19+ANIM.HQR:3#sample:4;frame=0;elapsed=132`, status
       `decoded_only`, links to `BODY.HQR:19` and `ANIM.HQR:3`, current strip
       `Sample 4 / frame 0 intro / 132 ms / 160 ms`, readout
       `Frame 0, previous 0, next 1, 160 ms duration, intro sample 4`, and 6
       structured inspector sections.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting sample 4.
    2. Expected: the shell remains usable, Evidence panel stacks to one column,
       and the animation strip scrolls horizontally without increasing page
       width. Observed document width `390`, Evidence grid column `351px`, and
       strip bounds `clientWidth=351`, `scrollWidth=7948`.
  - Screenshots:
    - `docs/validation-animation-sequence-strip-2026-05-06.png`.
    - `docs/validation-animation-sequence-strip-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 resource-record selection browser validation.
  - Starting URL: `http://127.0.0.1:8884/?resource_record_selection=2`,
    served by the integrated Python 3.12 viewer from this checkout after
    `npm run build` from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, filter Explorer to Resources, search for `TEXT.HQR:7`,
       and select `Text payload bank English/000`.
    2. Expected: direct resource selection remains resource-owned even though
       the text bank has scene usages. Observed Active Selection kind `asset`,
       stable id `TEXT.HQR:7`, workspace `resource`, Resource workspace visible,
       and 16 selectable resource-record items.
    3. Click record item `Record 1`.
    4. Expected: selected subrecord becomes the active selection without leaving
       Resource workspace. Observed Active Selection kind `resource_record`,
       stable id `TEXT.HQR:7#record:1`, status `source_backed`, link
       `TEXT.HQR:7`, current record highlighted, and export affordance.
    5. Expected: shared Inspector explains the record rather than returning to a
       catalog blob. Observed 4 structured sections: Summary, Source, Evidence
       Status, and Resource Record, with record kind `text_payload_bank`,
       summary `Let's go to the lighthouse!`, offset `734`, byte length `29`,
       flag `1`, and preview text.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting `Record 1`.
    2. Expected: the shell remains usable, active selection stays
       `RESOURCE_RECORD`, and the record strip scrolls horizontally without
       increasing page width. Observed document width `390`, record strip
       bounds `clientWidth=354`, `scrollWidth=3385`.
  - Screenshots:
    - `docs/validation-resource-record-selection-2026-05-06.png`.
    - `docs/validation-resource-record-selection-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 scene-usage strip browser validation.
  - Starting URL: `http://127.0.0.1:8885/?scene_usage_strip=1`, served by the
    integrated Python 3.12 viewer from this checkout after `npm run build` from
    `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, filter Explorer to Resources, search for `TEXT.HQR:7`,
       and select `Text payload bank English/000`.
    2. Expected: the selected resource stays resource-owned and the bottom
       Scene Usages strip shows reverse usages. Observed Active Selection kind
       `asset`, stable id `TEXT.HQR:7`, workspace `resource`, Resource
       workspace visible, and 48 visible usage strip items.
    3. Click the usage item for `Scene 0 (SCENE.HQR:1)`, object `0`, life
       script text reference `29`.
    4. Expected: the usage becomes the active selection while the current
       workspace remains non-destructive. Observed Active Selection kind
       `scene_usage`, stable id
       `TEXT.HQR:7#usage:SCENE.HQR:1#object:0;script=life;text=29;record=50`,
       status `source_backed`, workspace suggestion `entity`, links
       `TEXT.HQR:7` and `SCENE.HQR:1`, and Resource workspace still visible.
    5. Expected: shared Inspector explains the selected usage. Observed 4
       structured sections: Summary, Source, Evidence Status, and Scene Usage,
       including scene index `0`, object index `0`, position
       `10496, 2048, 4352`, script kind `life`, reference `text 29`, text file
       `000`, and the decoded preview quote.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting the usage.
    2. Expected: the shell remains usable, active selection stays
       `SCENE_USAGE`, and the usage strip scrolls horizontally without
       increasing page width. Observed document width `390`, usage strip bounds
       `clientWidth=351`, `scrollWidth=8869`.
  - Screenshots:
    - `docs/validation-scene-usage-strip-2026-05-06.png`.
    - `docs/validation-scene-usage-strip-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 raw descriptor table browser validation.
  - Starting URL: `http://127.0.0.1:8886/?raw_descriptor_table=1`, served by
    the integrated Python 3.12 viewer from this checkout after `npm run build`
    from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, filter Explorer to Resources, search for `RESS.HQR:11`,
       and select `Indexed image (RESS.HQR:11)`.
    2. Expected: active selection remains the resource asset and the bottom Raw
       Descriptors table appears when unknown descriptors are present. Observed
       Active Selection kind `asset`, stable id `RESS.HQR:11`, workspace
       `resource`, status `decoded_only`, and one Raw Descriptors row.
    3. Expected: descriptor table shows section, offset, length, confidence,
       note, and SHA-256. Observed section `indexed_image_semantics`, offset
       `0`, length `0`, confidence `parsed_unknown`, note
       `Image dimensions and indexed pixels are decoded; the runtime purpose of
       this RESS image entry is not identified yet.`, and SHA-256
       `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting `RESS.HQR:11`.
    2. Expected: the shell remains usable, Resource workspace remains visible,
       and the descriptor table scrolls horizontally inside the Evidence panel
       without increasing page width. Observed document width `390`, descriptor
       table `clientWidth=351`, `scrollWidth=787`.
  - Screenshots:
    - `docs/validation-raw-descriptor-table-2026-05-06.png`.
    - `docs/validation-raw-descriptor-table-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 script evidence table browser validation.
  - Starting URL: `http://127.0.0.1:8876/?script_evidence_table=2`, served by
    the integrated Python viewer from this checkout after `npm run build` from
    `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, wait for the catalog summary to show loaded assets,
       filter Explorer to Scenes, search for `SCENE.HQR:1`, and select
       `Scene 0 (SCENE.HQR:1)`.
    2. Expected: active selection remains scene-backed and the bottom Script
       Evidence table appears. Observed Active Selection stable id
       `SCENE.HQR:1`, source `SCENE.HQR[1]`, status `decoded_only`, and a
       Script Evidence table.
    3. Expected: the table shows sampled decoded instructions and
       control-flow targets with stable row ids. Observed `2 decoded scripts`,
       `103 instructions`, `45 control-flow links`, and rows such as
       `SCENE.HQR:1#object:0#script:track@0`, script kind `track`, opcode
       `TM_LABEL`, category `control_flow`, plus the separate Control Flow
       table.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` after selecting `SCENE.HQR:1`.
    2. Expected: the shell remains usable and the script table scrolls inside
       the Evidence panel without increasing page width. Observed document
       width `390`, script table `clientWidth=336`, `scrollWidth=768`,
       `clientHeight=77`, and `scrollHeight=891`.
  - Screenshots:
    - `docs/validation-script-evidence-table-2026-05-06.png`.
    - `docs/validation-script-evidence-table-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 126 tests.
- 2026-05-06 port evidence table browser validation.
  - Starting URL: `http://127.0.0.1:8889/?port_evidence_table=1`, served by
    the integrated Python 3.12 viewer from this checkout after `npm run build`
    from `frontend/`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Port evidence root:
    `D:\repos\reverse\littlebigreversing\docs\promotion_packets\manifest.json`.
  - Live-positive flow:
    1. Open the viewer, wait for the catalog summary to show loaded assets,
       filter Explorer to Scenes, search for `SCENE.HQR:3`, and select
       `Scene 2 (SCENE.HQR:3)`.
    2. Expected: Port Evidence is loaded from the promotion packet manifest and
       shows linked promoted packet rows for scene `2`. Observed 3 rows:
       `phase5_magic_ball_pickup`, `phase5_magic_ball_throw_projectile_launch`,
       and `phase5_magic_ball_enemy_damage_tralu_level1`.
    3. Expected: `canonical_runtime` is true only because each row has
       `status=live_positive`. Observed each row shows status `LIVE_POSITIVE`,
       canonical runtime `true`, its runtime contract id, fixture path, and
       packet source doc path.
  - Live-negative flow:
    1. Search for `SCENE.HQR:4` and select `Scene 3 (SCENE.HQR:4)`.
    2. Expected: live-negative packet rows remain visible but non-canonical.
       Observed `phase5_003_003_zone1_cellar_to_cube19` and
       `phase5_003_003_zone8_cellar_to_cube20`, both status `LIVE_NEGATIVE`,
       canonical runtime `false`, no runtime contract ids, fixture paths, and
       packet source doc paths.
  - Narrow viewport flow:
    1. Set browser viewport to `390x740` with a scene-backed selection active.
    2. Expected: the shell remains usable and the Port Evidence table scrolls
       inside the Evidence panel without increasing page width. Observed
       document width `390`, table `clientWidth=336`, `scrollWidth=1216`,
       `clientHeight=77`, and `scrollHeight=127`.
  - Screenshots:
    - `docs/validation-port-evidence-live-positive-2026-05-06.png`.
    - `docs/validation-port-evidence-live-negative-2026-05-06.png`.
    - `docs/validation-port-evidence-mobile-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `py -3 tools\validate_promotion_packets.py` passed in
      `D:\repos\reverse\littlebigreversing`.
- 2026-05-06 final cross-workspace replay audit.
  - Starting URL: `http://127.0.0.1:8890/?final_replay_audit=2`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Classic source root checked for source-backed provenance:
    `D:\repos\reverse\littlebigreversing\reference\lba2-classic\SOURCES`.
    The viewer does not take a separate source-root flag; visible
    source-backed evidence cites classic source files such as `MESSAGE.CPP`,
    `OBJECT.H`, `HQFILE.CPP`, and `GRILLE.CPP`.
  - Flow:
    1. Open the viewer and verify Explorer summary/facets. Observed
       `573 models`, `2082 decoded animations`, `720 sprite assets`,
       `222 scenes`, and `19062 resources across 15 HQR files`.
    2. Select `BODY.HQR:19`. Expected Model workspace and export affordance.
       Observed Active Selection `BODY.HQR:19`, status `DECODED_ONLY`,
       workspace `model`, 7 structured inspector sections, export enabled, and
       33 compatible animation options.
    3. Select compatible `Turn left (ANIM.HQR:3)`, play, then stop. Expected
       animation controls and sequence strip adjacent to viewport. Observed 51
       animation sample strip entries and active `animation_sample`
       `BODY.HQR:19+ANIM.HQR:3#sample:3;frame=0;elapsed=99`.
    4. Export the model. Expected export manifest becomes active
       `evidence_artifact`. Observed `BODY.HQR:19#export:manifest.json` and
       `Wrote 5 files to ...\exports\BODY.HQR_19`.
    5. Select `ANIM3DS.HQR:0`. Expected Sprite workspace frame identity,
       backend/palette/bounds, frame strip, and export. Observed
       `ANIM3DS.HQR:0#frame:0`, backend `anim3ds`, `RESS.HQR:0 normal
       palette`, hotspot/bounds facts, 33 strip items, and export writing 135
       files to `exports\ANIM3DS.HQR_0`.
    6. Select `SCENE.HQR:3`, then `SCENE.HQR:4`. Expected Script Evidence and
       Port Evidence tables. Observed scene 2 with 3 `LIVE_POSITIVE`
       canonical-runtime packet rows, and scene 3 with 2 `LIVE_NEGATIVE`
       non-canonical packet rows.
    7. Validate guarded room/load admission in the port authority with
       `py -3 scripts\verify_viewer.py --fast`. Observed positives
       `19/19`, `2/2`, `11/10`, `187/187`, and explicit `44/2` rejection with
       `ViewerSceneMustBeInterior`. This remains a port-runtime gate; the
       viewer does not create a second admission path.
    8. Select representative Resource assets `RESS.HQR:11`, `TEXT.HQR:7`,
       `SAMPLES.HQR:0`, and `LBA_BKG.HQR:1`. Expected Resource workspace, not
       text dumps or Sprite ownership. Observed matching Resource workspace
       titles, structured inspector sections, source-backed statuses for text,
       audio, and background, and `DECODED_ONLY` plus unknown descriptor
       evidence for `RESS.HQR:11`.
    9. Confirm no textarea-style primary dump remains on the replayed paths.
       Observed `document.querySelectorAll('textarea').length === 0`.
  - Regression caught and fixed during this audit:
    1. Rapid Explorer selections could leave the Active Selection on a newer
       resource while Resource workspace content still showed an older one.
    2. Added the monotonic catalog selection request guard in
       `frontend/src/main.ts`.
    3. Replayed the resource sequence with waits requiring Active Selection,
       Resource title, and workspace visibility to match each asset.
  - Screenshots:
    - `docs/validation-final-replay-resource-workspace-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `py -3 tools\validate_promotion_packets.py` passed in
      `D:\repos\reverse\littlebigreversing`.
    - `py -3 scripts\verify_viewer.py --fast` passed in
      `D:\repos\reverse\littlebigreversing`.
- 2026-05-06 resource long-tail browser validation.
  - Starting URL: `http://127.0.0.1:8891/?resource_longtail=1`, served by a
    fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Precheck:
    1. Ran `build_catalog()` over the canonical asset root and inspected HQR
       coverage. Observed zero `unknown_entries` for resource archives and zero
       `ress_unclassified_payload` assets in this retail root.
    2. Used `RESS.HQR:1` as the unknown-resource-evidence representative
       because it is a decoded RESS offset table with
       `ress_offset_record_semantics` marked `parsed_unknown`.
  - Flow:
    1. Open the viewer and filter Explorer to Resources.
    2. Select `RESS.HQR:0`. Expected Resource workspace, not Sprite/Model.
       Observed title `LBA2 palette (RESS.HQR:0)`, stable asset `RESS.HQR:0`,
       layout `lba2_palette`, 7 structured inspector sections, no textareas.
    3. Select `RESS.HQR:1`. Expected unknown semantic evidence without dumping
       raw bytes. Observed title `RESS offset table (RESS.HQR:1)`, stable asset
       `RESS.HQR:1`, layout `ress_offset_record_table`, 8 structured inspector
       sections, Raw Descriptors row `ress_offset_record_semantics`, and no
       textareas.
    4. Select `VIDEO.HQR:0`. Expected Resource workspace video metadata.
       Observed title `ACF movie ASCENSEU.SMK (VIDEO.HQR:0)`, stable asset
       `VIDEO/VIDEO.HQR:0`, layout `smacker_video`, status `SOURCE_BACKED`, 7
       structured inspector sections, and no textareas.
    5. Select `SCREEN.HQR:0`. Expected Resource workspace indexed screen image
       with paired palette context. Observed title `Screen image logo
       (SCREEN.HQR:0)`, stable asset `SCREEN.HQR:0`, layout
       `screen_indexed_image_640x480`, paired `SCREEN.HQR:1` palette in
       workspace metadata, 8 structured inspector sections, and no textareas.
  - Screenshot:
    - `docs/validation-resource-longtail-2026-05-06.png`.
  - Commands:
    - `build_catalog()` precheck over the canonical asset root completed and
      showed no generic unclassified resource payload in the current retail
      asset set.
- 2026-05-06 entity facet selection browser validation.
  - Starting URL: `http://127.0.0.1:8892/?entity_facets=1`, served by a fresh
    integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `BODY.HQR:26`. Expected Entity workspace selected object evidence
       and object facet buttons. Observed active `scene_object`
       `SCENE.HQR:1#object:1`, workspace `entity`, and evidence buttons for
       `Runtime State`, `File3D`, and `Render Contract`.
    2. Click object `Runtime State`, `File3D`, and `Render Contract`. Expected
       each click updates Active Selection and shared Inspector. Observed
       `runtime_sprite_state`, `file3d_resolution`, and `render_contract`
       selections, each with 3 structured inspector sections.
    3. Select `ANIM3DS.HQR:0`. Expected usage row exposes ANIM3DS evidence.
       Observed entity title `Scene 113 object 5` and usage buttons `File3D`,
       `Runtime Sprite`, and `ANIM3DS`.
    4. Click usage `ANIM3DS`. Expected a canonical ANIM3DS range selection.
       Observed `anim3ds_range_state` stable id
       `ANIM3DS.HQR:0#usage:SCENE.HQR:114#object:5#anim3ds:0`, status
       `source_backed`, and 3 structured inspector sections.
  - Screenshot:
    - `docs/validation-entity-facet-selections-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 palette context selection browser validation.
  - Starting URL: `http://127.0.0.1:8893/?palette_context=1`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Search Explorer for `SCREEN.HQR:0` and select the screen image resource.
       Expected Resource workspace ownership and a palette-context record.
       Observed resource title `Screen image logo (SCREEN.HQR:0)` and a
       selectable `Palette Context` record summarizing `SCREEN.HQR:1`.
    2. Click `Palette Context`. Expected a canonical `palette_context` active
       selection. Observed stable id `SCREEN.HQR:0#palette:SCREEN.HQR:1`,
       source `SCREEN.HQR[0]`, status `source_backed`, workspace `resource`,
       links `SCREEN.HQR:0` and `SCREEN.HQR:1`, and 3 structured inspector
       sections.
    3. Confirm no textarea-style dump was introduced. Observed
       `document.querySelectorAll('textarea').length === 0`.
  - Screenshot:
    - `docs/validation-palette-context-selection-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 evidence status style browser validation.
  - Starting URL: `http://127.0.0.1:8894/?status_styles=1`, served by a fresh
    integrated viewer process from this checkout after `npm run build`.
  - Flow:
    1. Inject temporary `.evidence-status` badges for `source_backed`,
       `decoded_only`, `render_only`, `live_confirmed`, `port_implied`,
       `unknown`, `intentionally_deferred`, `preview_only`, `live_positive`,
       `live_negative`, and `approved_exception` into the loaded app page.
    2. Read computed `color`, `backgroundColor`, and `borderTopColor` for each
       badge. Expected all statuses to be visually distinguishable by the CSS
       actually served to the browser. Observed 11 unique style triples for 11
       statuses.
  - Screenshot:
    - `docs/validation-evidence-status-styles-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
- 2026-05-06 port `decode_only` status browser validation.
  - Starting URL: `http://127.0.0.1:8910/?port_decode_only_status=1`, served
    by a fresh integrated viewer process from this checkout after
    `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Inject temporary `.evidence-status` badges for `decode_only`,
       `decoded_only`, `live_negative`, `live_positive`, and
       `approved_exception`.
    2. Read computed `color`, `backgroundColor`, and `borderTopColor` for each
       badge. Expected the port packet status `decode_only` to be visually
       distinct from viewer selection status `decoded_only` and from the
       promotion statuses. Observed 5 unique style triples for 5 statuses.
    3. Expected no horizontal spill. Observed document width `1264` and
       viewport width `1264`.
  - Screenshot:
    - `docs/validation-port-decode-only-status-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 model stats DOM renderer browser validation.
  - Starting URL: `http://127.0.0.1:8911/?model_stats_dom=1`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Search `BODY.HQR:19` and select the model result.
    2. Expected Active Selection to stay on `BODY.HQR:19` and Model workspace
       stats to render as structured cells. Observed Active Selection contains
       `BODY.HQR:19`, stats render 18 `span` cells, and the first pairs are
       `bones 24`, `vertices 258`, `normals 258`, `polygons 390`, and
       `lines 36`.
    3. Expected no horizontal spill. Observed document width `1264` and
       viewport width `1264`.
  - Screenshot:
    - `docs/validation-model-stats-dom-render-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 animation bone-count compatibility label browser validation.
  - Starting URL: `http://127.0.0.1:8912/?anim_bone_count_label=1`, served by
    a fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Search `HOLOMAP.HQR:10` and select `HOLOMAP.HQR entry 10`.
    2. Expected the active selection to stay on `HOLOMAP.HQR:10`.
       Observed as expected.
    3. Expected compatible animations that only match by bone count, despite
       File3D BODY allow-list metadata on the ANIM entries, to be labeled as
       weaker evidence and not as `fallback`. Observed 24 animation options
       prefixed `[bones]`, including `[bones] Idle (ANIM.HQR:222)`, and 0
       options containing `[fb]` or `fallback`.
    4. Expected no horizontal spill. Observed document width `1264` and
       viewport width `1264`.
  - Screenshot:
    - `docs/validation-animation-bone-count-label-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 render contract summary browser validation.
  - Starting URL: `http://127.0.0.1:8913/?render_contract_summary=2`, served
    by a fresh integrated viewer process from this checkout after
    `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Search `BODY.HQR:26` and select `Nitro-meca-penguin`.
    2. Expected the active selection to stay on `BODY.HQR:26` while the
       Entity workspace exposes scene-object evidence. Observed as expected.
    3. Expected the selected entity Render Contract section to show named
       render-phase and recovery-contract rows instead of raw JSON strings.
       Observed `Scene redraw setup`, `Tree insert`, `Method: DrawRecover`,
       `Moving box: no`, and no `{` or `}` JSON braces in the section text.
    4. Expected no horizontal spill. Observed document width `1264` and
       viewport width `1264`.
  - Screenshot:
    - `docs/validation-render-contract-summary-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 inspector object summary browser validation.
  - Starting URL: `http://127.0.0.1:8914/?inspector_object_summary=1`, served
    by a fresh integrated viewer process from this checkout after
    `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Search `BODY.HQR:26` and select `Nitro-meca-penguin`.
    2. Expected the active selection to stay on `BODY.HQR:26` and the Entity
       workspace inspector to expose runtime object evidence. Observed as
       expected.
    3. Expected nested runtime state and script-link rows to render as named
       key/value evidence rather than raw JSON. Observed Runtime State rows
       for `Movement`, `Collision`, `Combat`, and `Bonus` with values such as
       `mode: 7`, `mode_name: MOVE_PINGOUIN`, `object: true`,
       `hit_force: 0`, and no `{` or `}` braces in Runtime State or Script
       Links.
    4. Expected no horizontal spill. Observed document width `1264` and
       viewport width `1264`.
  - Screenshot:
    - `docs/validation-inspector-object-summary-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 catalog key/value search browser validation.
  - Starting URL: `http://127.0.0.1:8915/?catalog_keyvalue_search=1`, served
    by a fresh integrated viewer process from this checkout after
    `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Load the catalog and inspect the first resource with a composition
       payload. Observed `LBA_BKG.HQR:1` with composition key
       `cube_dimensions`.
    2. Search Explorer for `cube_dimensions`. Expected composition-backed
       resources to remain discoverable through semantic key/value search.
       Observed `Background grid map 0 (LBA_BKG.HQR:1)` and related background
       grid resources in the result list.
    3. Expected no browser diagnostics. Observed no console or error output.
  - Screenshot:
    - `docs/validation-catalog-search-keyvalue-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 active selection preview action browser validation.
  - Starting URL: `http://127.0.0.1:8895/?preview_actions=1`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `SCREEN.HQR:0`, then select its Resource workspace
       `Palette Context` record. Expected the Active Selection panel to expose
       the palette preview action. Observed buttons `Copy ID` and
       `Open SCREEN.HQR:1`.
    2. Click `Open SCREEN.HQR:1`. Expected the linked palette asset to open
       without replacing the owning evidence selection. Observed Resource title
       `Screen palette logo (SCREEN.HQR:1)` while the Active Selection remained
       kind `palette_context` with stable id
       `SCREEN.HQR:0#palette:SCREEN.HQR:1`.
  - Screenshot:
    - `docs/validation-active-selection-preview-actions-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 sprite pixel evidence browser validation.
  - Starting URL: `http://127.0.0.1:8896/?sprite_pixel=1`, served by a fresh
    integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `ANIM3DS.HQR:0`. Expected Sprite workspace with a decoded frame.
       Observed title `COQU sprite frame 0 (ANIM3DS.HQR:0)` and active
       selection kind `sprite_frame`.
    2. Move the pointer over the sprite canvas. Expected exact hover pixel
       evidence. Observed metadata containing `hover 44,28 palette 63 rgba
       255,255,255,255`.
    3. Click the sprite canvas. Expected picked pixel evidence to persist in
       Sprite facts. Observed metadata containing `picked 44,24 palette 223
       rgba 239,235,251,255` and facts containing `Picked pixel44,24 palette
       223 rgba 239,235,251,255`.
  - Screenshot:
    - `docs/validation-sprite-pixel-evidence-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 sprite strip thumbnail browser validation.
  - Starting URL: `http://127.0.0.1:8897/?sprite_strip_thumbs=2`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `ANIM3DS.HQR:0`. Expected bottom Sprite Frames strip to show the
       full range and a decoded visual thumbnail for the current frame.
       Observed 33 strip items, one canvas thumbnail for the loaded frame, and
       the current item state `decoded`.
    2. Confirm unloaded range entries do not fake thumbnails. Observed 32
       state thumbnails marked `load_on_select`.
    3. Click Next. Expected the current frame, strip highlight, decoded state,
       and thumbnail canvas to move together. Observed frame label `2 / 33`,
       current title `COQU frame 1`, current state `decoded`, and one active
       strip item with a canvas thumbnail.
  - Screenshot:
    - `docs/validation-sprite-strip-thumbnails-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 copyable evidence row browser validation.
  - Starting URL: `http://127.0.0.1:8898/?copyable_evidence=1`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `SCENE.HQR:2`. Expected Script Evidence stable IDs to be visible
       and copyable. Observed 25 copy buttons with titles such as
       `Copy stable ID: SCENE.HQR:2#object:0#script:track@0`.
    2. Select `SCENE.HQR:3`. Expected Port Evidence packet IDs to be visible
       and copyable without changing promotion status semantics. Observed 3
       packet copy buttons for `phase5_magic_ball_*` packets and 3
       `live_positive` status badges.
    3. Click one Script Evidence copy button and one Port Evidence copy button.
       Expected no UI error. Observed no browser console or error output.
  - Screenshot:
    - `docs/validation-copyable-evidence-row-ids-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 128 tests.
    - `py -3 D:\repos\reverse\littlebigreversing\scripts\verify_viewer.py --fast`
      passed from the port repo.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 scene object table browser validation.
  - Starting URL: `http://127.0.0.1:8899/?scene_objects_table=2`, served by a
    fresh integrated viewer process from this checkout after `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `SCENE.HQR:3`. Expected a bottom-panel table of sampled scene
       objects with copyable stable ids. Observed 20 rows, first stable id
       `SCENE.HQR:3#object:0`, and Copy/Open controls for sampled objects.
    2. Click `Open SCENE.HQR:3#object:1`. Expected the selected row to promote
       through the canonical Entity workspace path. Observed Active Selection
       kind `scene_object`, stable id `SCENE.HQR:3#object:1`, status
       `source_backed`, Entity title `Scene 2 object 1`, one highlighted table
       row, and shared inspector sections for Runtime State, Render Contract,
       Visual Links, Script Links, Port Implications, and Unknown Descriptors.
    3. Confirm adjacent evidence stays scoped to the selected object/scene.
       Observed Script Evidence stable ids rooted at
       `SCENE.HQR:3#object:1#script:*` and Port Evidence still listing the
       three scene-2 `live_positive` packets without promoting them from preview
       success.
  - Screenshot:
    - `docs/validation-scene-object-table-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 129 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 raw descriptor copyable ID browser validation.
  - Starting URL: `http://127.0.0.1:8900/?raw_descriptor_copy=1`, served by a
    fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `RESS.HQR:11`. Expected the Raw Descriptors table to include a
       visible copyable stable descriptor id. Observed one descriptor row with
       stable id `RESS.HQR:11#descriptor:indexed_image_semantics@0`.
    2. Click the descriptor Copy control. Expected no UI/runtime error and the
       descriptor id to remain visible. Observed the copy action completed and
       the row still showed the same stable id.
    3. Check layout width and browser diagnostics. Observed document width
       `1264`, viewport width `1264`, and no browser console or error output.
  - Screenshot:
    - `docs/validation-raw-descriptor-copy-ids-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 129 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 scene local evidence table browser validation.
  - Starting URL: `http://127.0.0.1:8901/?scene_locals=1`, served by a fresh
    integrated viewer process from this checkout after the current frontend
    build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Select `SCENE.HQR:3`. Expected bottom-panel local scene evidence beyond
       sampled objects/scripts/ports. Observed Scene Locals summary
       `38 zones; 42 waypoints; 0 GRM links; 60 patches`.
    2. Expected local rows to expose copyable stable ids. Observed 36 Copy
       controls, including zone ids such as `SCENE.HQR:3#zone:0`, waypoint ids
       such as `SCENE.HQR:3#waypoint:0`, and patch ids such as
       `SCENE.HQR:3#patch:0`.
    3. Expected patch rows to preserve target instruction/field evidence.
       Observed patch rows such as
       `4 bytes -> TM_WAIT_NB_DIZIEME.runtime_timer_ref` with target
       `hero classic_track_runtime`.
    4. Click the first Scene Locals Copy control and check browser diagnostics.
       Observed no browser console or error output and no horizontal document
       spill at `1264` viewport width.
  - Screenshot:
    - `docs/validation-scene-local-evidence-table-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 129 tests.
    - `agent-browser errors` and `agent-browser console` reported no output.
- 2026-05-06 export manifest evidence context validation.
  - Backend-only slice; no browser behavior changed.
  - Audit finding: export manifests preserved source ids and hashes, but did
    not consistently expose the explicit proof scope/evidence status required
    by the export acceptance checks.
  - Implemented top-level manifest `evidence` blocks and regression assertions
    in `tests/test_export_probe.py` for direct model probe, server model export,
    sprite export, sample export, and promotion-packet links copied from
    matching scene fixture evidence.
  - Commands:
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 resource record selection sync browser validation.
  - Starting URL: `http://127.0.0.1:8902/?resource_selection_sync=2`, served
    by a fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Filter Explorer to Resources and select `LBA_BKG.HQR:11`. Expected the
       Resource workspace to own the preview and sampled records. Observed
       `Background grid map 10 (LBA_BKG.HQR:11)` with 41 resource record rows.
    2. Select the `Palette Context` record. Expected the active selection to
       become `palette_context` while the producing row remains highlighted
       even though the canonical selection id is `LBA_BKG.HQR:11#palette:unknown`.
       Observed one current row, index 0, for `Palette Context`.
    3. Select `Record 0`. Expected active selection kind `resource_record`,
       stable id `LBA_BKG.HQR:11#record:0`, structured inspector sections, and
       exactly one highlighted Resource row. Observed one current row, index 1,
       for `Record 0`, no visible error, and document width equal to viewport
       width at `1264`.
  - Screenshot:
    - `docs/validation-resource-selection-sync-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 scene asset entity route browser validation.
  - Starting URL: `http://127.0.0.1:8903/?scene_asset_entity_route=3`, served
    by a fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, filter Explorer to Scenes, and select
       `SCENE.HQR[3]` / `SCENE.HQR:3`.
    2. Expected active selection kind `asset`, stable id `SCENE.HQR:3`,
       workspace `entity`, and export affordance. Observed as expected.
    3. Expected active workspace to settle on Entity after catalog load,
       with Sprite hidden even though the backend payload contains
       `sprite.kind = "scene"`. Observed `entityViewPanel` active,
       `entityViewTab` pressed, and Sprite/Model/Resource panels hidden.
    4. Expected scene evidence tables to remain populated. Observed 20 scene
       object records and 38 zones / 42 waypoints / 60 patches in Scene
       Locals, with no visible error and no horizontal document spill at
       `1264` viewport width.
  - Screenshot:
    - `docs/validation-scene-asset-entity-route-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 animation pose selection browser validation.
  - Starting URL: `http://127.0.0.1:8904/?animation_pose_selection=1`, served
    by a fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer and select `BODY.HQR[19]` / `BODY.HQR:19`.
    2. Choose compatible animation `ANIM.HQR:3`, set frame `1` and elapsed
       `0`, then click `Apply animation pose`.
    3. Expected active selection kind `animation_sample`, stable id preserving
       BODY, ANIM, target frame, previous frame, and elapsed time. Observed
       `BODY.HQR:19+ANIM.HQR:3#pose:frame=1;previous=0;elapsed=0`.
    4. Expected structured inspector sections for the pose sample instead of
       reverting to the BODY asset inspector. Observed 5 structured sections:
       Summary, Source, Evidence Status, Animation Sample, and Pose, with
       `manual pose sample`, `Segment pose`, `Frame 1`, `Previous frame 0`,
       `Next frame 2`, and `Duration 260 ms`.
    5. Expected the Model workspace to remain active with no visible error and
       no horizontal document spill. Observed Model active, no visible error,
       and document width equal to viewport width at `1264`.
  - Screenshot:
    - `docs/validation-animation-pose-selection-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 sprite variant selection browser validation.
  - Starting URL: `http://127.0.0.1:8905/?sprite_variant_selection=1`, served
    by a fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Confirmed `/api/catalog/load` for `SCENE.HQR:126` returns four scene
       background frames: `base`, `grm_zone_000_on`, `grm_zone_001_on`, and
       `grm_zone_002_on`.
    2. Open the viewer, filter Explorer to Scenes, select `SCENE.HQR[126]`,
       wait for the scene load to complete, then open the Sprite workspace.
    3. Click the `GRM zone 0 ON` frame variant in the Sprite frame strip.
    4. Expected active selection kind `sprite_frame`, stable id
       `SCENE.HQR:126#frame:grm_zone_000_on`, `render_only` evidence status,
       and workspace `sprite`. Observed as expected.
    5. Expected the strip highlight, sprite title, frame label, and metadata to
       match the selected variant. Observed row index 1 marked
       `aria-current=true`, title `Scene 125 (SCENE.HQR:126) - GRM zone 0 ON`,
       frame label `2 / 4`, and metadata `scene background GRM zone 0 ON`.
    6. Expected no visible error and no horizontal document spill. Observed no
       error and document width equal to viewport width at `1264`.
  - Screenshot:
    - `docs/validation-sprite-variant-selection-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 scene variant inspector browser validation.
  - Starting URL: `http://127.0.0.1:8906/?scene_variant_inspector=1`, served
    by a fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, filter Explorer to Scenes, select `SCENE.HQR[126]`,
       wait for its scene background frame strip, open Sprite workspace, and
       click `GRM zone 0 ON`.
    2. Expected active selection stable id
       `SCENE.HQR:126#frame:grm_zone_000_on`, kind `sprite_frame`, status
       `render_only`, and Sprite row index 1 highlighted. Observed as expected.
    3. Expected the Inspector summary to reflect the selected frame variant,
       not just the parent scene asset. Observed `Kind sprite_frame`, label
       `Scene 125 (SCENE.HQR:126) GRM zone 0 ON`, and a Frame section with
       variant `grm_zone_000_on`.
    4. Expected no visible error and no horizontal document spill. Observed no
       error and document width equal to viewport width at `1264`.
  - Screenshot:
    - `docs/validation-scene-variant-inspector-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 resource clear selection reset browser validation.
  - Starting URL:
    `http://127.0.0.1:8907/?resource_clear_validation=1`, served by a fresh
    integrated viewer process from this checkout after the current frontend
    build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, search for `RESS.HQR:6`, select the texture atlas
       resource, and click its Resource workspace `Palette Context` record.
    2. Expected the resource row to be selected and Active Selection to show
       `palette_context` with stable id `RESS.HQR:6#palette:RESS.HQR:0`.
       Observed as expected.
    3. Search for `BODY.HQR:1` and select `Twinsen without tunic model`.
    4. Expected the Resource workspace to clear to `No resource selected`,
       Active Selection to show asset `BODY.HQR:1`, and no
       `.resource-record-item[aria-current="true"]` rows to remain. Observed
       as expected.
    5. Expected no visible error and no horizontal document spill. Observed no
       error and no horizontal spill.
  - Screenshot:
    - `docs/validation-resource-clear-selection-reset-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 130 tests.
- 2026-05-06 entity ANIM3DS facet browser validation.
  - Starting URL:
    `http://127.0.0.1:8908/?entity_anim3ds_facet=1`, served by a fresh
    integrated viewer process from this checkout after the current frontend
    build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, search for `ANIM3DS.HQR:0`, and select
       `COQU sprite frame 0`.
    2. Confirm the Entity workflow for `Scene 113 object 5` exposes both
       usage-level and selected-entity `ANIM3DS` evidence actions.
    3. Click the selected-entity `ANIM3DS` evidence target.
    4. Expected active selection kind `anim3ds_range_state`, stable id
       `SCENE.HQR:114#object:5#anim3ds:0`, source `SCENE.HQR[114]`, status
       `source_backed`, and a preview action for `ANIM3DS.HQR:0`. Observed as
       expected.
    5. Expected inspector facet rows to show animation number, range name,
       start/end frame, frame count, relative frame, range match, FPS, sprite,
       backend, and object index. Observed the `ANIM3DS Range State` section
       with those fields.
    6. Expected no visible error and no horizontal document spill. Observed no
       error and no horizontal spill.
  - Screenshot:
    - `docs/validation-entity-anim3ds-facet-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
- 2026-05-06 sprite picked pixel selection browser validation.
  - Starting URL:
    `http://127.0.0.1:8909/?sprite_picked_pixel_selection=1`, served by a
    fresh integrated viewer process from this checkout after the current
    frontend build.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Open the viewer, search for `ANIM3DS.HQR:0`, and select
       `COQU sprite frame 0`.
    2. Move over and click the Sprite canvas near its center.
    3. Expected the Sprite facts to keep the picked pixel readout. Observed
       `Picked pixel 67,38 palette 63 rgba 255,255,255,255`.
    4. Expected the active `sprite_frame` inspector Frame section to include
       selection-owned picked pixel rows. Observed `Picked pixel 67, 38`,
       `Picked palette index 63`, and `Picked RGBA 255,255,255,255`.
    5. Expected no visible error and no horizontal document spill. Observed no
       error and no horizontal spill.
  - Screenshot:
    - `docs/validation-sprite-picked-pixel-selection-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
- 2026-05-06 model palette evidence browser validation.
  - Starting URL: `http://127.0.0.1:8916/?model_palette_evidence=1`, served
    by a fresh integrated viewer process from this checkout after
    `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Load the catalog and select `Nitro-meca-penguin model`
       (`BODY.HQR:26`).
    2. Expected Model workspace stats to name palette and texture-atlas
       evidence explicitly. Observed `palette evidence` =
       `RESS.HQR:0 normal palette (256 colors)` and
       `texture atlas evidence` = `RESS.HQR:1 texture atlas (256x256)`.
    3. Expected no hidden fallback wording in the populated stats. Observed no
       `fallback` text in the Model stats.
    4. Expected no browser diagnostics. Observed no console or error output.
  - Screenshot:
    - `docs/validation-model-palette-evidence-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
- 2026-05-06 sprite export evidence-artifact browser validation.
  - Starting URL: `http://127.0.0.1:8917/?sprite_export_artifact=1`, served
    by a fresh integrated viewer process from this checkout after
    `npm run build`.
  - Asset root:
    `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`.
  - Flow:
    1. Search for `ANIM3DS.HQR:0` and select `COQU sprite frame 0`.
    2. Expected the active selection to be exportable. Observed active
       `sprite_frame` selection `ANIM3DS.HQR:0#frame:0` with `Export evidence
       bundle`.
    3. Click Export. Expected the sprite/range export manifest to become the
       active `evidence_artifact` selection, matching the model export behavior.
       Observed `EVIDENCE_ARTIFACT` with stable id
       `ANIM3DS.HQR:0#export:manifest.json`, provenance
       `D:\repos\reverse\lba2-lm2-viewer\exports\ANIM3DS.HQR_0`, link
       `ANIM3DS.HQR:0`, and bottom export status `Wrote 135 files to ...`.
    4. Verified `exports\ANIM3DS.HQR_0\manifest.json` exists and includes
       source id `ANIM3DS.HQR:0`, evidence status `decoded_only`, proof scope
       `decoded sprite frame pixels and sheet export; not live runtime gameplay
       proof`, generated frame/sheet files, and promotion-packet source.
    5. Expected no browser diagnostics. Observed no console or error output.
  - Screenshot:
    - `docs/validation-sprite-export-artifact-2026-05-06.png`.
  - Commands:
    - `npm run build` passed from `frontend/`.
    - `py -3 -m unittest discover -s tests -v` passed, 131 tests.
- 2026-05-06 completion audit.
  - Objective restated as concrete deliverables:
    1. Replace the model-viewer-plus-sidebar shape with the workbench contract
       from `docs/design.md`.
    2. Drive Explorer, peer workspaces, Inspector, Export, evidence panels, and
       sub-selections from one canonical selection model.
    3. Replace catalog/detail blobs and raw primary dumps with structured,
       searchable inspector sections and evidence tables.
    4. Preserve current capabilities: model loading, sprite playback, entity
       evidence, resource previews, animation posing, UV inspection, runtime
       sprite resolution, and exports.
    5. Keep evidence statuses and port promotion semantics distinct, with
       `canonical_runtime: true` only coming from promoted port evidence.
    6. Validate UI behavior with `agent-browser`, preserve reproducible flows,
       and keep Python tests plus frontend build passing.
  - Prompt-to-artifact checklist:
    - `docs/design.md` target workbench contract:
      implemented through the left Explorer Dock, central peer workspaces, right
      Inspector Dock, and bottom Evidence panel in `frontend/index.html`,
      `frontend/src/main.ts`, and `frontend/src/styles.css`; validated by
      workbench shell, workspace switcher, decode-progress, and final replay
      browser notes.
    - One selection module:
      `frontend/src/selection.ts` defines `AppSelection` and constructors for
      `asset`, `scene_usage`, `runtime_sprite_state`, `file3d_resolution`,
      `anim3ds_range_state`, `render_contract`, `sprite_frame`,
      `animation_sample`, `model_surface`, `resource_record`,
      `palette_context`, and `evidence_artifact`; `frontend/src/main.ts` owns
      the single `AppSelectionStore`.
    - Active selection and export state:
      Active Selection renders stable ids, copy actions, links, preview actions,
      unknowns, status, and workspace suggestions from `AppSelection`;
      `selectedExportAsset` is gone; export enablement follows
      `selection.exportActions`.
    - Catalog/detail split:
      `CatalogUi.renderDetail()` and `renderResourceDetail()` paths are absent;
      migrated assets use `frontend/src/inspector.ts` section builders. Browser
      notes cover model, animation, raw animation, sprite frame, ANIM3DS range,
      sample audio, Smacker video, text payload/order, palette/indexed image,
      runtime table, holomap, background, scene, and unclassified resources.
    - Primary dump removal:
      audit scan over `frontend/src` and `frontend/index.html` reports
      `JSON.stringify` only in API request bodies and explicit UV
      copy/download evidence artifacts; no `innerHTML`, `renderDetail`,
      `main-tabs`, `[fb]`, `selectedExportAsset`, selected-asset ownership, or
      fallback-renderer markers remain. Browser notes confirm no textareas and
      no raw JSON braces on replayed migrated paths.
    - Peer workspaces:
      Model, Sprite, Scene/Entity, and Resource panels exist as workspaces and
      switch non-destructively; validated on desktop and mobile by workspace
      switcher, Resource workspace, scene route, model controls/UV, sprite
      strip, and final replay notes.
    - Model workspace capability:
      geometry toggles, line/sphere evidence, UV inspector, animation
      compatibility, playback/pose samples, stats, palette/texture evidence,
      and model-surface inspector are implemented and validated by the model
      workspace, UV, surface, animation sequence, animation pose, bone-count
      label, stats DOM, and model palette evidence flows.
    - Sprite workspace capability:
      nearest-neighbor canvas, frame identity, frame strip/thumbnails,
      playback, backend/palette/offset/bounds metadata, pixel hover/pick
      evidence, scene variants, and sprite export are implemented and validated
      by sprite frame strip, pixel evidence, picked-pixel selection, strip
      thumbnail, variant inspector, and sprite export artifact flows.
    - Scene/Entity workspace capability:
      runtime resolver, scene object selections, File3D/runtime/render contract
      facets, selected entity ANIM3DS facets, render-path summaries, visual
      links, script links, local evidence, and port implications are
      implemented and validated by runtime resolver, scene-object inspector,
      entity facet, entity ANIM3DS, render contract, inspector object summary,
      scene object table, scene locals, script evidence, and port evidence
      flows.
    - Resource workspace capability:
      audio, text, palette, indexed images, background previews, video,
      runtime tables, sampled records, palette context, unknown descriptor
      evidence, row highlighting, and clear behavior are implemented and
      validated by Resource workspace, long-tail, resource record, scene usage,
      raw descriptor, palette context, record sync, clear reset, and catalog
      key/value search flows. The canonical retail root has no generic
      `ress_unclassified_payload`; unknown-resource evidence is represented by
      decoded resources with unknown descriptors.
    - Port-facing evidence:
      `lba2_lm2_viewer/server.py` reads the canonical promotion-packet manifest
      without searching alternate roots; `frontend/src/styles.css` distinguishes
      viewer and port statuses including `decode_only`; browser notes validate
      live-positive canonical rows, live-negative non-canonical rows, and
      `decode_only` styling.
    - Port authority gates:
      current `py -3 tools\validate_promotion_packets.py` passed in
      `D:\repos\reverse\littlebigreversing`; current
      `py -3 scripts\verify_viewer.py --fast` passed and showed guarded
      positives `19/19`, `2/2`, `11/10`, `187/187` plus explicit `44/2`
      `ViewerSceneMustBeInterior` rejection for both `inspect-room` and viewer
      launch.
    - Export artifacts:
      model export and sprite/ANIM3DS export both become active
      `evidence_artifact` selections; manifests include selected stable id,
      source archive/index, asset root, hashes where available, evidence
      status, proof scope, warnings/generated files, and promotion-packet
      source. Backend regression tests cover model, sprite, audio, text, video,
      indexed image, background, and promotion packet links.
    - Validation protocol:
      browser validation notes include starting URLs, asset roots, selected
      assets or scene pairs, actions, expected/observed states, commands, and
      screenshots under `docs/validation-*.png`. No generated Playwright or
      Puppeteer validation scripts were added.
    - Current command gates:
      `npm run build` passed from `frontend/`; current
      `py -3 -m unittest discover -s tests -v` passed, 131 tests; current
      promotion-packet validation passed; current `verify_viewer.py --fast`
      passed.
  - Audit conclusion:
    all `TASK.md` milestone acceptance checks are covered by concrete code,
    browser evidence, scans, and current command output. Remaining notes are
    residual engineering risks, not unmet acceptance requirements.

## Remaining Risks

- `frontend/src/main.ts` remains large and owns orchestration across selection,
  workspace routing, evidence panels, and export actions. This is a
  maintainability risk, but the completion audit did not find a second active
  selection path or acceptance-blocking legacy route.
- Backend response payloads are rich and unevenly shaped. Inspector sections
  handle the current canonical payloads, but future archive/resource expansion
  would benefit from tighter typed API contracts.
