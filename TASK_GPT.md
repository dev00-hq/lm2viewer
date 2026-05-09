# Task: Complete Graph-Backed App Decisions

## 0. Metadata

- Owner: project maintainer
- Created: 2026-05-09
- Source context: follow-up audit of `TASK.md`
- Current state: Planning
- Current milestone: M7 - Graph-backed export provenance

## 1. Mission

Finish the broader graph-backed app decision migration so app-facing selection,
routing, inspector, workspace, export, and relationship decisions use the
backend catalog graph as their canonical evidence authority.

The previous `TASK.md` is complete for its scoped milestones: animation
operation compatibility, model/resource asset selection, inspector routing for
migrated model/resource selections, and one scene-object relationship table
view. This task continues from there and targets the remaining local authority
paths that still read catalog enrichment fields directly.

The main local authority fields to eliminate from migrated app decisions are:

- `asset.scene_usages`
- `asset.kind`
- `stats.semantic_layout`
- `stats.reconnaissance`

These fields may remain graph input or decoder/render data where appropriate,
but they should not be parallel app-facing decision authorities for migrated
surfaces.

## 2. Hard Constraints

- Preserve the project rule: one canonical current-state implementation, no
  compatibility bridges or dual behavior for old local states.
- Keep graph semantics in backend Python. Frontend TypeScript may consume
  graph projections but must not become the source of graph relationship rules.
- Migration is replacement, not coexistence. When a decision moves to the
  graph, remove the superseded local authority in the same milestone unless a
  documented risk explicitly defers removal.
- Do not commit retail assets, decoded retail payloads, real texture exports,
  real animation exports, or generated evidence bundles from retail assets.
- Use agent-browser for visible UI changes and record validation notes under
  `docs/`.
- If a project trap appears, alert the developer and update `ISSUES.md`.

## 3. Current Completion Gap

The scoped task is done, but the broader mission is not fully true yet.
Remaining local app-facing authority includes:

- `entities.py` workflow builders still derive selected entity state from
  catalog assets, reverse `scene_usages`, and compact scene payloads.
- Export provenance still uses fields such as `asset.scene_usages` instead of
  graph edge counts and proof metadata.
- Frontend exportability still has local inference paths such as
  `isExportableCatalogAsset` for some selections, instead of consistently using
  graph-projected `exportCapability` and `exportActions` for migrated types.
- Scene usage strips, Entity View relationship content, and some inspector
  relationship rows still read embedded stats/reconnaissance payloads directly.
- Frontend still parses stable ids with `split('#')` for sprite-frame and other
  non-migrated selection paths.
- Backend and frontend preview/load decisions still branch on
  `asset.kind + stats.semantic_layout`; these need either graph-backed
  operation projections or a clear classification as decoder/render mechanics
  rather than app decision authority.
- Inspector route migration currently covers graph-projected model/resource
  asset selections, not every selection kind.

## 4. Success Criteria

This task is complete when:

- Export provenance for migrated exportable assets comes from graph-backed edge
  evidence, not `asset.scene_usages`.
- Frontend exportability gating for migrated selections consumes graph-projected
  `exportCapability` and `exportActions`, not `isExportableCatalogAsset`.
- Entity workflow relationship decisions consume graph projections or queries
  instead of reverse usage fields as app-facing authority.
- Scene usage strips and Entity View relationship sections render graph edge
  evidence, including `MissingTarget`, `proofScope`, `evidenceStatus`,
  `sourceRule`, `sourceField`, and `indexRule` where relevant.
- Selection parent/owner identity for migrated selection types no longer uses
  frontend stable-id string splitting.
- Inspector routing for migrated scene, sprite, animation, sprite-frame,
  resource-record, and entity-facet selections is driven by backend graph
  metadata or graph projections.
- Any remaining `asset.kind + semantic_layout` branching is documented as
  decoder/render mechanics, or replaced with graph-backed operation contracts.
- Python tests pass for migrated backend graph/API behavior.
- Frontend build passes for migrated frontend behavior.
- Visible UI changes have agent-browser validation notes and screenshots under
  `docs/`.

## 5. Remaining Authority Inventory

Use this inventory to keep implementation and review focused. The exact line
numbers may drift; verify with `rg` before editing.

| Surface | Local path | Local authority | Intended graph replacement |
| --- | --- | --- | --- |
| Entity workflow usage selection | `lba2_lm2_viewer/entities.py` | `asset.scene_usages` | `sceneUsagesByAssetId` / selection relationship links |
| Entity workflow scene object lookup | `lba2_lm2_viewer/entities.py` | `stats.reconnaissance.sampled_objects` | `sceneObjectRelationshipsByStableId` plus scene object node metadata |
| Entity linked visuals | `lba2_lm2_viewer/entities.py` | sampled object `links.body/animation/sprite` | `sceneObjectRelationshipsByStableId.visualLinks` |
| Export evidence context | `lba2_lm2_viewer/server.py` | `asset.scene_usages` count | graph export context projection |
| Export scene joins | `lba2_lm2_viewer/server.py` | `asset.scene_usages` iteration | graph usage edges/indexes |
| Frontend export gating | `frontend/src/main.ts` | `isExportableCatalogAsset` | selection `exportCapability` / `exportActions` for migrated types |
| Frontend scene usage strip | `frontend/src/main.ts` | `asset.scene_usages` | graph-projected selection links or usage projection |
| Server load routing | `lba2_lm2_viewer/server.py` | `asset.kind + stats.semantic_layout` | graph route/operation metadata for migrated types |
| Server export routing | `lba2_lm2_viewer/server.py` | `asset.kind + stats.semantic_layout` | graph export route/capability for migrated types |
| Script evidence tables | `frontend/src/main.ts` | `stats.reconnaissance.*_script_analysis` | graph script/incident edge summaries where modeled |
| Parent selection identity | `frontend/src/main.ts` | `stableId.split('#')` | projected `parentAssetId`, `ownerStableId`, or operation-specific owner field |

Scene-local evidence such as zones, waypoints, GRM links, and patches is out of
scope unless the graph already models it. Those are structural scene facts, not
relationship authority yet.

## 6. Milestone Plan

### M7 - Graph-backed export provenance

Goal:

- Replace export-facing provenance joins and migrated frontend exportability
  gates that currently use local catalog fields with graph-backed export
  context and capability.

Actions:

- Add a graph query/projection for export context by stable asset id.
- Include relationship counts, direct scene-object usage counts, script
  reference counts, proof scopes, evidence statuses, source rules, source
  fields, and index rules.
- Replace `ViewerServer.export_evidence_context()` and related manifest fields
  so migrated model/resource exports use graph export context.
- Remove the local `len(asset.get("scene_usages") or [])` authority for migrated
  export provenance.
- Audit `frontend/src/main.ts::isExportableCatalogAsset`.
- For migrated model/resource selections, rely on graph-projected
  `selection.exportCapability` and `selection.exportActions` for export button
  state and export eligibility.
- Keep any local exportability logic only for explicitly non-migrated selection
  types, with a clear boundary comment.
- Add focused synthetic tests for direct usage, script reference, missing
  target, and no-usage exports.
- Validate at least one browser export flow if visible export evidence changes.

Validation:

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe -v
uv run python -m unittest discover -s tests -v
cmd /c "cd frontend && node_modules\.bin\tsc.cmd && node_modules\.bin\vite.cmd build"
```

### M8 - Graph-backed Entity View relationship content

Goal:

- Move Entity View relationship content from compact workflow payload authority
  onto graph scene-object relationship projections.

Actions:

- Extend the existing scene-object relationship projection only as needed.
- Update `entities.py` or server workflow endpoints so entity relationship
  sections are graph-fed.
- Preserve existing non-relationship facts, such as position, flags, and
  decoded script summaries, unless they are acting as relationship authority.
- Remove duplicate local relationship derivation for migrated Entity View
  sections.
- Do not rewrite Entity View styling or Inspector section content as part of
  this milestone; migrate relationship authority only.
- Add tests for scene object body, animation, sprite, File3D, ANIM3DS, and
  missing target evidence.
- Validate an Entity View browser flow.

### M9 - Graph-backed scene usage strips

Goal:

- Replace scene usage strips/tables that read `asset.scene_usages` with graph
  usage projections.

Actions:

- Add or reuse a graph usage projection keyed by selected asset id.
- Preserve direct scene-object usage and script reference as distinct edge
  categories.
- Render relationship rows from graph metadata.
- Remove local reverse usage rendering for migrated asset types.
- Add tests for direct usage versus script reference ordering and counts.
- Validate model and resource usage-strip browser flows, including a used model
  such as `BODY.HQR:29`.

### M10 - Selection parent identity without stable-id parsing

Goal:

- Remove frontend `stableId.split('#')` as authority for migrated parent/owner
  decisions.

Actions:

- Add `parentAssetId`, `ownerStableId`, or operation-specific owner fields to
  graph selection projections for migrated non-asset selection types.
- Migrate sprite-frame, scene-object, resource-record, animation-sample, and
  entity-facet routing one type at a time.
- Replace relevant frontend `split('#')` calls with projected owner fields.
- Keep formatting-only stable-id parsing out of this milestone unless it affects
  decisions.
- Add frontend build validation and focused browser checks for each migrated
  selection kind.

### M11 - Broader graph-backed inspector routing

Goal:

- Extend graph-backed inspector route authority beyond model/resource asset
  selections.

Actions:

- Define route projections for scene assets, animation assets, sprite assets,
  sprite frames, resource records, scene objects, and entity facets.
- Update `renderSelectionInspector()` to prefer graph route metadata for each
  migrated type.
- Remove local route inference for migrated types.
- Keep existing section renderers where practical; this milestone owns route
  authority, not a full content rewrite.
- Add tests for projection shape and browser validation for representative
  routes.

### M12 - Graph-backed script evidence summaries

Goal:

- Move script evidence table authority onto graph-modeled script relationship
  summaries where the graph has enough evidence.

Actions:

- Audit script evidence rendering in `frontend/src/main.ts`.
- Extend `sceneObjectRelationshipsByStableId` only as needed to expose script
  relationship summaries, such as script kind, owner stable id, target link
  counts, proof scope, evidence status, source rule, source field, and index
  rule.
- Keep instruction-level opcode rows local unless the graph explicitly models
  individual instructions.
- Document that boundary in code or graph docs.
- Validate the script evidence table for a representative scene object such as
  `SCENE.HQR:2#object:2`.

### M13 - Classify or replace semantic-layout load routing

Goal:

- Decide which `asset.kind + stats.semantic_layout` branches are app decision
  authority and which are decoder/render mechanics.

Actions:

- Audit backend `handle_catalog_load()` and frontend workspace preview routing.
- For app decisions, add graph operation projections and migrate callers.
- For decoder/render mechanics, document the boundary in `docs/design.md` and
  related graph docs.
- Remove any duplicated local authority for migrated decisions.
- Add tests for operation routing where graph-backed.

### M14 - Final audit and cleanup

Goal:

- Prove every remaining local read is either migrated or explicitly scoped as
  graph input, decoder/render mechanics, or an intentionally non-migrated
  surface.

Actions:

- Audit all `scene_usages`, `semantic_layout`, `reconnaissance`, `asset.kind`,
  and `split('#')` reads in `entities.py`, `server.py`, and frontend UI code.
- Update graph docs if new projection vocabulary was added.
- Update `ISSUES.md` for any surprising traps encountered.
- Run the full validation suite and ensure all visible UI migrations have
  validation notes.

## 7. Validation Strategy

Use targeted validation after each milestone and the full suite before marking
this task done.

Primary commands:

```powershell
uv run python -m unittest discover -s tests -v
cmd /c "cd frontend && node_modules\.bin\tsc.cmd && node_modules\.bin\vite.cmd build"
```

Use `pytest` only when available in the active environment. This checkout may
not have `python`, `py`, or `npm` directly on `PATH`; prefer `uv run` and local
frontend binaries unless the environment is fixed.

Browser validation:

- Start a fresh viewer from this checkout.
- Confirm the listener is not stale before using browser evidence.
- Use agent-browser for visible UI changes.
- Record URL, asset root, selected ids, expected state, observed state, and
  screenshot path under `docs/`.

Suggested visible validation flows:

- M7: model/resource export flow and export button state.
- M8: Entity View for `SCENE.HQR:2#object:2`.
- M9: usage strip for `BODY.HQR:29` and a resource with script references.
- M10: sprite-frame or resource-record selection with projected parent identity.
- M11: representative inspector routes for one scene, one sprite-frame, one
  resource-record, and one entity-facet selection.
- M12: script evidence table for `SCENE.HQR:2#object:2`.

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
| --- | ---: | ---: | --- |
| Entity View behavior changes when workflow relationships switch to graph projections. | Medium | High | Validate `SCENE.HQR:2#object:2` in browser and preserve non-relationship fields unless they are authority. |
| Position, flags, render type, or opcode details do not yet have graph equivalents. | Medium | Medium | Scope them as catalog facts or decoder/render details, not relationship authority, and document the boundary. |
| Export routing changes accidentally affect non-migrated asset types. | Low | High | Migrate model/resource first and keep explicit non-migrated boundaries until their route metadata exists. |
| Graph projection size grows too quickly. | Low | Medium | Prefer narrow operation-specific projections and add fields only for active consumers. |
| Higher-level UI work turns into Explorer or Inspector redesign. | Medium | Medium | Keep milestones focused on authority paths; do not redesign Explorer or rewrite Inspector content unless required for migration. |

## 9. Decision Log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-05-09 | Start with export provenance/exportability before Entity View. | It is the narrowest remaining duplicate authority path and can be validated without opening the larger entity workflow surface. |
| 2026-05-09 | Keep scene-local zones, waypoints, GRM links, and patches out of scope. | They are not yet graph-modeled relationship authority. |
| 2026-05-09 | Keep instruction-level script rows local until graph vocabulary exists for opcodes. | Existing graph edges can own structural script relationship evidence, but not every decoded instruction detail. |
| 2026-05-09 | Do not redesign Explorer or rewrite Inspector content in this task. | The goal is authority migration, not a UI redesign. |

## 10. First Implementation Notes

Start with M7. It is the narrowest remaining duplicate authority path and is
already visible in code:

- `lba2_lm2_viewer/server.py::export_evidence_context()` counts
  `asset.scene_usages`.
- `lba2_lm2_viewer/exports/probe.py` also reports `scene_usage_count` from the
  asset payload.
- `frontend/src/main.ts::isExportableCatalogAsset` is the frontend exportability
  inference path to audit for migrated selections.
- Existing graph indexes already distinguish direct scene-object usage and
  script reference edges, so export provenance can likely be migrated with a
  small projection rather than a broad graph export.

Do not start with a full Entity View rewrite. Move one relationship/export
surface at a time and remove the local authority for that surface before moving
on.
