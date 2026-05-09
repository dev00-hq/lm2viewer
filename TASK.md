# Task: Graph-Backed App Decisions

## 0. Metadata

- Owner: project maintainer
- Agent/session: Codex app-study team, 2026-05-07
- Created: 2026-05-07
- Last updated: 2026-05-07
- Current state: Done
- Current milestone: Done

## 1. Mission

The durable purpose of this task is:

> Make the catalog graph the shared evidence substrate for app decisions, then
> migrate selection, routing, inspector, workspace, export, and relationship
> decisions onto that graph one decision at a time while removing duplicate
> truth paths.

This task owns both:

- rewriting `docs/design.md` so the design contract reflects the graph-backed
  backend/spine, not just a selection-driven catalog UI;
- implementing the migration in the app through small validated milestones.

This task should optimize for:

- one canonical current-state implementation;
- evidence clarity across UI, backend, CLI, exports, and port-facing probes;
- reduced human review burden by migrating one decision surface at a time.

## 2. Hard constraints

These may not be changed without explicit user approval.

- Do not preserve or introduce compatibility bridges, migration shims, fallback
  paths, compact adapters, old local-state support, or dual behavior unless the
  user explicitly asks for that support.
- The backend Python graph builder remains the source of graph semantics for
  CLI, HTTP/backend APIs, exports, and UI projections. Do not move graph
  semantics into frontend-only TypeScript.
- Migration is replacement, not coexistence: when a decision is moved to the
  graph, remove the superseded local authority in the same milestone unless a
  tracked risk explicitly defers removal.
- The app must remain a local evidence/falsification workbench for original LBA2
  assets and port compatibility, not an editor, converter, plugin host, remake
  workflow, or replacement-asset authoring tool.
- Do not commit game assets, decoded real asset payloads, real texture exports,
  real animation exports, or generated evidence bundles from retail assets.
- Use `agent-browser` to validate visible UI changes against a fresh viewer
  process from this checkout.
- If a required change affects hard constraints, public APIs, data
  compatibility guarantees, security, privacy, performance budgets, release
  process, or user-visible product scope, stop and request approval before
  making that change.
- If a surprising project trap appears, alert the developer and update
  `ISSUES.md` so future agents do not repeat it.

## 3. Soft constraints and preferences

These may change if evidence supports a better path, but meaningful changes
must be logged.

- Prefer graph projections/query responses over sending full graph exports to
  the frontend until a measured need exists.
- Prefer operation-specific graph contracts over vague relationship labels. A
  graph edge may prove a relationship without proving that a UI operation is
  allowed.
- Keep near-term milestones narrow enough to validate with focused tests and one
  browser flow.
- Use synthetic tests for graph semantics whenever retail asset coverage would
  be slow or brittle.
- Keep `docs/design.md`, `docs/catalog-graph-model.md`,
  `docs/catalog-graph-probes.md`, and `docs/catalog-graph-queries.md`
  synchronized when graph vocabulary or UI authority changes.
- Do not redesign Explorer before the graph-backed selection/routing/inspector
  substrate is stable.

## 4. Current success criteria

The task is considered successful when:

- [x] `docs/design.md` names the catalog graph as the shared evidence substrate
  for selection, inspector sections, workspace suggestions, search/explorer
  projections, export provenance, CLI/agent queries, and future port joins.
- [x] Each migrated app decision has one graph-backed authority path and no
  remaining local duplicate rule for that same decision.
- [x] Animation compatibility and playback validation cannot disagree silently:
  either both use the same graph-backed operation contract, or the graph exposes
  distinct relationship/operation semantics with tests.
- [x] Selection identity and workspace recommendation no longer depend on
  frontend stable-id string splitting for migrated selection types.
- [x] Inspector/export routing for migrated types is driven by graph node/edge
  metadata or backend graph projections, not by parallel frontend
  `asset.kind + semantic_layout` inference.
- [x] Scene/entity/resource relationship views for migrated types consume graph
  edges, including `MissingTarget`, `proofScope`, `evidenceStatus`,
  `sourceRule`, `sourceField`, and `indexRule` where relevant.
- [x] Python tests pass for migrated backend graph/API behavior.
- [x] Frontend build passes for migrated frontend behavior.
- [x] Any visible browser behavior change has an `agent-browser` validation note
  under `docs/` with URL, asset root, selected ids, expected state, observed
  state, and screenshot path.

Success criteria may be refined as discoveries are made. Any refinement must be
recorded in the Scope Change Log.

## 5. Task state

Current state: `Designing`

Allowed states:

- `Exploring`: discovering the codebase, constraints, and unknowns.
- `Designing`: shaping or revising the architecture hypothesis.
- `Implementing`: changing code for the current milestone.
- `Refactoring`: restructuring to support the goal without changing behavior.
- `Validating`: running tests, checks, or manual verification.
- `Stabilizing`: fixing edge cases, documentation, regressions, and polish.
- `Blocked`: unable to continue without user input or an external dependency.
- `Done`: success criteria and validation are complete.

Transition rules:

- Any state may return to `Designing` if a core assumption is invalidated.
- Any state may become `Blocked` if progress would require violating a hard
  constraint.
- `Done` requires validation evidence.

## 6. Current understanding

### Problem model

The previous catalog-graph slice created a real graph spine:

- `lba2_lm2_viewer/catalog_graph.py` builds a typed in-memory graph from the
  current catalog payload.
- The `catalog-graph` CLI can build deterministic graph JSON and query an
  exported graph with `--graph-json`.
- The backend attaches a narrow graph projection to `/catalog.json` and exposes
  `/api/catalog-graph/compatible`.
- The Model workspace animation compatibility list is the first graph-backed UI
  consumer.

The remaining problem is parallel truth. Many app decisions still derive from
`catalog.assets`, `asset.scene_usages`, `stats.semantic_layout`, compact entity
workflow payloads, and frontend stable-id string conventions. The graph may
know a relationship with evidence metadata while the app still routes,
inspects, exports, or validates the same behavior through local rules.

### Current graph-backed decisions

- Graph construction owns archive/entry/asset identity, scene object projection,
  File3D resolver preservation, compatibility edges, ANIM3DS ranges, resource
  records, script references, and missing targets.
- Backend catalog projection currently exposes graph-backed animation
  compatibility.
- Frontend `compatibility.ts`, animation Explorer filtering, and the canvas
  animation dropdown use the graph compatibility projection.
- Backend pose and sequence validation use the graph-backed
  `catalog_graph.animation_operation_compatibility.v0` operation projection.

### Current duplicate or non-graph decision paths

- `entities.py` workflow builders derive selected entity state from
  `catalog.assets`, `scene_usages`, and compact scene payloads.
- Export evidence context and promotion-packet joins still use
  `asset.scene_usages`.
- `server.py::handle_catalog_load()` routes by `asset.kind` and
  `semantic_layout`.
- `frontend/src/selection.ts` synthesizes selection identity, links, workspace
  suggestion, evidence status, and exportability from raw asset fields.
- `frontend/src/main.ts` still parses stable ids with `.split('#')` in several
  decision paths and routes workspaces/inspector/export through local
  type/layout checks.
- `frontend/src/inspector.ts`, `frontend/src/ui/entityView.ts`, and
  `frontend/src/ui/resourceWorkspace.ts` still read scene usages and resource
  records from embedded catalog stats.

### Known unknowns

- Which graph projection is the smallest sufficient backend payload for
  selection identity, workspace recommendation, inspector routing, and export
  capability?
- Does graph `COMPATIBLE_WITH` currently mean "relationship compatibility" or
  "safe to pose/play in this viewer"? If those differ, what operation-specific
  edge or projection should name playback eligibility?
- How much of `scene_usages` should remain as catalog enrichment input versus
  app-facing authority?
- Which UI surfaces can be migrated without changing user-visible behavior, and
  which require explicit approval because behavior/scope changes?
- Whether frontend graph projection size/performance remains acceptable as more
  decisions move to graph metadata.
- Which selection/workspace fields can be projected without sending broad graph
  exports to the frontend.

### Assumptions

| Assumption | Confidence | How to validate |
| --- | ---: | --- |
| The graph is mature enough to become the app decision spine. | Medium | Migrate one operation contract and compare tests/browser behavior. |
| Selection/workspace recommendation should be migrated before broad Explorer redesign. | High | Code inspection shows stable-id parsing and workspace inference are cross-cutting risks. |
| Expanding backend graph projections is preferable to frontend re-derivation. | High | Project guidance rejects duplicate truth paths and frontend-only graph semantics. |
| A database is not needed for this migration yet. | Medium | Continue measuring graph build/query/projection cost after each milestone. |
| `COMPATIBLE_WITH` can be sufficient for current pose/playback eligibility if the graph only materializes edges whose decoded counts can actually pose together. | High | `tests/test_animation_compatibility.py` covers allow-list, bone-count-only, mismatch, and non-`BODY.HQR` cases. |

## 7. Current architecture hypothesis

The app should treat the catalog graph as the canonical evidence substrate and
expose operation-specific projections to consumers.

Hypothesized flow:

1. `viewer.build_catalog()` still decodes source payloads and produces catalog
   facts.
2. `catalog_graph.build_catalog_graph()` materializes relationship evidence,
   proof scopes, evidence statuses, source/index rules, missing targets, and
   query indexes.
3. Backend services expose small graph-backed projections for UI decisions:
   compatibility, selection identity, workspace suggestion, inspector section
   routing, export capability, scene/entity links, and resource records.
4. Frontend components render those projections and keep only presentation
   logic, local UI state, and visual controls.
5. CLI/agent/port use the same graph query vocabulary and exported graph JSON
   for offline or repeated analysis.

Components likely to change:

- `docs/design.md`
- `TASK.md`
- `lba2_lm2_viewer/catalog_graph.py`
- `lba2_lm2_viewer/server.py`
- `lba2_lm2_viewer/entities.py`
- frontend selection/routing/inspector/catalog/workspace files
- graph tests and browser validation docs

Components that should not change unless evidence demands it:

- HQR parsing and core decoder semantics unrelated to graph authority.
- Product boundary as a local evidence workbench.
- Current graph CLI/export vocabulary except through logged contract changes.
- Existing compatibility wrappers unless explicitly targeted by another task.

Risky areas:

- Playback compatibility can diverge from graph compatibility.
- Broad graph projections could become too large for `/catalog.json`.
- Migrating Inspector before selection identity could encode another temporary
  truth path.
- Explorer tree/grouping can collapse many relationship dimensions into one
  hierarchy if done before graph-backed relationship queries are stable.

## 8. Current plan

Only the next one to three milestones are detailed. Later work must be planned
after the next evidence checkpoint.

### Subagent use policy

Use subagents for independent discovery, critique, and validation planning when
a milestone crosses multiple app surfaces. Do not use subagents as parallel
implementers.

Good subagent tasks:

- fact-check graph vocabulary and evidence semantics;
- audit frontend/backend duplicate truth paths;
- propose focused tests and browser validation flows;
- review docs/design changes for contradiction with graph docs and product
  constraints.

Bad subagent tasks:

- multiple agents directly rewriting files.
- parallel implementation.
- broad Explorer redesign before selection/routing/inspector graph authority is
  stable.

The main agent owns final synthesis, file edits, integration, validation, and
`TASK.md` updates.

### M0 - Define task and discover constraints

Goal:

- Establish the mission, constraints, affected modules, validation strategy, and
  first milestones.

Actions:

- [x] Read `AGENTS.md`, repo docs, package scripts, current graph docs, current
  `TASK.md`, and relevant frontend/backend code paths.
- [x] Spawn read-only subagents for backend graph/API, frontend decision paths,
  design/docs alignment, and validation strategy.
- [x] Record known unknowns, assumptions, risks, and validation gates.
- [x] Convert `TASK.md` from the previous static slice into this evolving goal.

Validation:

- `TASK.md` has Mission, Hard Constraints, Current Plan, Validation Strategy,
  append-only logs, Current State Summary, and Operating Rules.

Status: Completed

### M1 - Rewrite design contract around the graph spine

Goal:

- Make `docs/design.md` describe the graph-backed evidence workbench the app is
  becoming, while preserving the existing product boundary and UX principles.

Recommended subagents before editing:

- Design/docs reviewer: check current `docs/design.md`, `docs/catalog-graph-*`,
  and `docs/explorer-grouping-prototype.md` for terms that must survive or
  change.
- Graph vocabulary reviewer: verify node/edge names, proof scopes, evidence
  statuses, and operation-specific language against `catalog_graph.py` and
  `docs/catalog-graph-model.md`.
- Implementation feasibility reviewer: scan frontend/backend decision paths and
  flag design claims that would imply a large code migration or public behavior
  change.

Subagents should not edit files in M1. The main agent writes the final
`docs/design.md` update and reconciles this file afterward.

Actions:

- [x] Rewrite `docs/design.md` so the graph is the substrate behind selection,
  inspector sections, workspace suggestions, Explorer/search projections,
  export provenance, CLI/agent queries, and future port joins.
- [x] State that Explorer is one projection of the graph, not the graph schema
  owner.
- [x] Promote negative evidence, missing targets, direct usage vs script
  reference, File3D resolver evidence, and operation-specific eligibility into
  the design contract.
- [x] Keep `docs/catalog-graph-model.md` as the deeper vocabulary reference;
  avoid duplicating every implementation detail in `design.md`.
- [x] Update this `TASK.md` after the design rewrite with discoveries,
  decisions, changed assumptions, risks, validation results, and the next
  milestone state.

Validation:

- Review `docs/design.md` for these terms and boundaries:
  `catalog graph`, `graph projection`, `selection`, `workspace suggestion`,
  `proofScope`, `evidenceStatus`, `MissingTarget`, `ScriptReference`,
  `File3DRecord`, `export provenance`.
- `rg -n "graph|projection|proofScope|MissingTarget|ScriptReference|File3DRecord|workspace suggestion|export provenance" docs/design.md`
- No code validation required unless code changes are made.

Checkpoint:

- Intended: rewrite `docs/design.md` so it names the catalog graph as the
  backend-owned evidence substrate for UI/backend/CLI/export/port decisions
  without duplicating the detailed graph vocabulary from
  `docs/catalog-graph-model.md`.
- Actual: updated `docs/design.md` with a `Catalog Graph Authority` section and
  graph-backed authority rules for selection, workspace suggestion,
  Explorer/search projections, inspector sections, scene/entity/resource
  relationship views, export provenance, compatibility contracts, and migration
  order.
- Learned: the existing graph docs already contain enough node/edge vocabulary;
  the design contract only needed to state authority boundaries and operation
  projection rules.
- Assumptions changed: none.
- Architecture status: still valid; backend graph remains the evidence spine
  and frontend code should consume narrow projections.
- Scope changed: no.
- Success criteria status: the design-document success criterion is complete;
  implementation criteria remain open.
- Next smallest useful milestone: M2 animation operation compatibility.
- Validation: `rg -n "catalog graph|graph projection|selection|workspace suggestion|proofScope|MissingTarget|ScriptReference|File3DRecord|export provenance" docs/design.md`
  confirmed the required M1 terms and boundaries. No code validation was
  required because M1 changed documentation only.

Status: Completed

### M2 - Make animation operation compatibility graph-backed end to end

Goal:

- Remove the first high-risk duplicate truth path by making playback/pose
  eligibility agree with graph-backed compatibility semantics.

Recommended subagents before implementation:

- Backend compatibility auditor: compare `catalog_graph.py` compatibility edges
  with `server.py::animation_compatibility_error()`,
  `pose_catalog_animation()`, and `pose_catalog_animation_sequence()`.
- Frontend animation auditor: inspect `frontend/src/compatibility.ts`,
  animation dropdown behavior, labels, and playback assumptions.
- Test-contract reviewer: inspect `tests/test_catalog_graph.py` and
  `tests/test_animation_compatibility.py`, then propose focused parity tests for
  allow-list, bone-count-only, mismatch, and non-`BODY.HQR` cases.

Subagents should produce findings and proposed assertions only. The main agent
owns the operation contract decision and implementation because this milestone
touches a small, semantically delicate authority path.

Actions:

- [x] Define whether `COMPATIBLE_WITH` is sufficient for pose/playback or
  whether playback needs a distinct operation-specific projection such as
  `poseEligible`/`playbackEligible`.
- [x] Add a focused backend test proving the graph result and pose/sequence
  validation cannot silently disagree for representative allow-list,
  bone-count-only, mismatch, and non-`BODY.HQR` cases.
- [x] Replace or demote `server.py::animation_compatibility_error()` so it is no
  longer an independent authority for the migrated decision.
- [x] Preserve current visible behavior unless the evidence requires a behavior
  change; if behavior must change, stop for approval first.
- [x] Update graph docs and this `TASK.md` after validation.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation is required only if the visible animation dropdown,
selection, playback, labels, or errors change.

Checkpoint:

- Intended: make animation pose/playback validation consume the same
  graph-backed compatibility authority as the frontend animation list.
- Actual: added `catalog_graph.animation_operation_compatibility.v0`, tightened
  File3D allow-list edge materialization so playback-compatible edges require
  matching decoded bone counts, and changed `ViewerServer` pose/sequence guards
  to call the graph operation projection. Removed the old standalone
  `server.py` compatibility helper.
- Learned: `COMPATIBLE_WITH` is sufficient for current pose/playback only when
  the graph does not emit File3D allow-list edges for mismatched decoded counts.
  Non-`BODY.HQR` models now follow the same graph contract as the frontend: they
  need an explicit graph edge.
- Assumptions changed: replaced the completed design-doc assumption with an
  operation-contract assumption covering `COMPATIBLE_WITH` as playback
  eligibility.
- Architecture status: still valid; graph relationship evidence and operation
  projection now govern compatibility decisions end to end for this path.
- Scope changed: no product scope change. Direct backend/API attempts to pose a
  non-graph-compatible pair now align with the already graph-backed frontend
  selection list.
- Success criteria status: animation compatibility/playback divergence
  criterion is complete; selection/workspace/inspector/export criteria remain
  open.
- Next smallest useful milestone: M3 graph-backed selection/workspace
  projection.
- Validation:
  `python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q`
  passed with 17 tests.
  `python -m unittest discover -s tests -v` passed with 142 tests.
  `cd frontend; npm run build` passed. Browser validation was not required
  because no visible UI, labels, dropdown, or playback controls changed.

Status: Completed

### M3 - Define graph-backed selection/workspace projection

Goal:

- Create the smallest graph-backed projection needed for selection identity and
  workspace recommendation, before migrating Inspector or Explorer broadly.

Recommended subagents before implementation:

- Selection identity auditor: inspect `frontend/src/selection.ts` for stable-id,
  evidence status, links, export action, and workspace derivations.
- Workspace/routing auditor: inspect `frontend/src/main.ts` for
  `asset.kind`, `semantic_layout`, payload-shape, and `.split('#')` decision
  paths.
- Inspector/export auditor: inspect `frontend/src/inspector.ts`,
  `isExportableCatalogAsset()`, entity/resource workspaces, and export
  enablement paths.
- Backend projection auditor: inspect `server.py` and `catalog_graph.py` for the
  smallest graph query/projection shape that can replace one selection
  authority path.

Subagents should not implement overlapping frontend/backend changes. Their
output should be a minimal projection proposal plus risks and validation flows.

Actions:

- [x] Audit `frontend/src/selection.ts`, `frontend/src/main.ts`, and backend
  selection payloads for the minimum fields currently synthesized locally.
- [x] Add or propose a backend graph projection/query that returns selected
  node identity, source, evidence status, links, unknowns, workspace suggestion,
  preview/export capabilities, and relevant edge evidence.
- [x] Migrate one low-risk selection type to the projection and remove its
  superseded local authority.
- [x] Validate selection stability with build/tests and an `agent-browser` flow
  if visible behavior changes.
- [x] Update this `TASK.md` before planning the next milestone.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Manual/browser checks, if UI-visible:

- Select a model asset and confirm active selection, workspace, inspector, and
  animation dropdown stay coherent.
- Select a direct resource asset and confirm it remains resource-owned rather
  than auto-promoting to a scene object.
- Select a scene object/entity path and confirm linked visuals remain explicit.

Checkpoint:

- Intended: define the smallest graph-backed projection needed for selection
  identity and workspace recommendation, then migrate one low-risk selection
  type without redesigning Inspector or Explorer.
- Actual: added `catalog_graph.selection_projection.v0` under
  `graph.selectionByAssetId` for model assets. The projection includes selected
  graph node id, stable id, source, evidence status, workspace suggestion,
  preview/export actions, direct scene usage count, total relationship link
  count, and usage/script relationship links with edge evidence. Frontend model
  asset selection now requires this projection; non-migrated asset types remain
  on the existing local path.
- Learned: model relationship links need both direct scene-object usage and
  script reference evidence, but direct usage must be ordered and counted
  separately to avoid collapsing relationship semantics.
- Assumptions changed: the smallest useful selection projection is per migrated
  selection type, not a full graph export or universal frontend graph import.
- Architecture status: still valid; backend graph projections can replace
  frontend selection authority incrementally.
- Scope changed: no product scope change. Visible model selection state remains
  the same for no-known-usage models, with graph-backed source/selection fields.
- Success criteria status: the migrated-selection stable-id/workspace criterion
  is complete for model assets. Inspector/export routing and broader
  scene/entity/resource relationship criteria remain open.
- Next smallest useful milestone: M4 expand graph-backed selection/routing to a
  second type that exercises routing pressure, likely resource or scene assets,
  before migrating Inspector routing.
- Validation:
  `python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q`
  passed with 19 tests.
  `python -m unittest discover -s tests -v` passed with 144 tests.
  `cd frontend; npm run build` passed.
  `agent-browser` validation passed against `http://127.0.0.1:8892` with
  selected id `BODY.HQR:2`; note and screenshot are in
  `docs/validation-m3-model-selection-2026-05-07.md` and
  `docs/validation-m3-model-selection-2026-05-07.png`.

Status: Completed

### M4 - Expand graph-backed selection routing beyond model assets

Goal:

- Migrate a second low-risk asset selection type to the graph selection
  projection so routing pressure is tested before Inspector/export routing is
  moved broadly.

Recommended focus:

- Prefer a resource or scene asset type whose workspace suggestion currently
  depends on `asset.kind + semantic_layout` and whose export action is
  straightforward to preserve.
- Avoid migrating Inspector section selection in the same milestone unless the
  graph projection already contains enough metadata to remove the old local
  branch cleanly.

Actions:

- [x] Choose one next selection type by comparing model, resource, scene, and
  sprite risks.
- [x] Extend `catalog_graph.selection_projection.v0` for that type with the
  minimum source, workspace, preview/export, and relationship fields needed.
- [x] Make frontend selection for that type require the graph projection and
  remove the superseded local authority for the migrated decisions.
- [x] Add focused backend/frontend validation and an `agent-browser` note if the
  visible active selection or workspace state changes.
- [x] Update graph docs and this `TASK.md` after validation.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation is required if active selection text, workspace, export
state, or link rows change.

Checkpoint:

- Intended: migrate a second low-risk asset selection type to the graph
  selection projection to test routing pressure before Inspector/export routing
  moves broadly.
- Actual: migrated resource asset selection. `catalog_graph.selection_projection.v0`
  now covers model and resource assets. Resource selections get graph-backed
  source/provenance, evidence status, workspace suggestion, preview action,
  export action based on backend semantic-layout rules, and usage/script
  relationship links with edge evidence. Frontend resource selection now
  requires this graph projection and no longer computes resource exportability
  or workspace suggestion locally.
- Learned: resource selection is a good pressure test because real sample
  resources can have many script references; the projection keeps them as links
  without auto-promoting the active selection to a scene object.
- Assumptions changed: M4 confirms type-by-type projection expansion is still
  viable without sending a full graph export to the frontend.
- Architecture status: still valid; backend graph projections now own
  workspace/export selection decisions for model and resource asset selections.
- Scope changed: no product scope change. Direct resource selection remains
  resource-owned.
- Success criteria status: validation criteria are current-green. Inspector
  routing, scene/entity/resource relationship views, and broader export
  provenance are still open.
- Next smallest useful milestone: M5 move Inspector/export routing for migrated
  model/resource selections onto graph projection metadata, without migrating
  every Inspector section.
- Validation:
  `python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q`
  passed with 20 tests.
  `python -m pytest tests/test_catalog_graph.py -q` passed with 14 tests.
  `python -m unittest discover -s tests -v` passed with 145 tests.
  `cd frontend; npm run build` passed.
  `agent-browser` validation passed against `http://127.0.0.1:8893` with
  selected id `SAMPLES.HQR:0`; note and screenshot are in
  `docs/validation-m4-resource-selection-2026-05-07.md` and
  `docs/validation-m4-resource-selection-2026-05-07.png`.

Status: Completed

### M5 - Move Inspector/export routing for model and resource selections onto graph projections

Goal:

- Remove the next duplicate frontend decision path for already-migrated model
  and resource selections by letting graph projection metadata tell the
  frontend which inspector route/export capability applies.

Recommended focus:

- Keep the existing inspector section renderers. This milestone should route to
  the right existing renderer from graph projection fields; it should not
  rewrite every model/resource section into graph rows.
- Keep non-migrated scene, sprite, animation, and entity paths on their current
  local routing until their selection projections exist.

Actions:

- [x] Add graph projection fields for migrated model/resource inspector route
  and export capability.
- [x] Replace frontend `asset.kind + semantic_layout` routing for migrated
  model/resource active selections with those graph fields.
- [x] Keep local `asset.kind + semantic_layout` routing only for non-migrated
  types and explicitly name that boundary in code/tests.
- [x] Add focused tests or build-time checks that model/resource selection
  export capability and inspector route come from graph projection metadata.
- [x] Validate with Python tests, frontend build, and `agent-browser` if visible
  Inspector/export state changes.
- [x] Update graph docs and this `TASK.md` after validation.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation is required if active Inspector sections or export state
change.

Checkpoint:

- Intended: remove the next duplicate frontend decision path for already
  migrated model/resource selections by routing Inspector/export state from
  graph projection metadata.
- Actual: added `inspectorRoute` and `exportCapability` to
  `catalog_graph.selection_projection.v0`. Frontend `AppSelection` now carries
  those fields, and `renderSelectionInspector()` dispatches migrated
  model/resource asset selections through the graph route before falling back to
  local routing for non-migrated types. Existing inspector section renderers
  were reused.
- Learned: graph-projected routing can remove the authority decision without
  rewriting section content yet. Resource `SAMPLES.HQR:0` validates the
  `sample_audio` route and export-enabled state.
- Assumptions changed: none.
- Architecture status: still valid; model/resource selection, workspace,
  export action, export capability, and inspector route now share the same
  backend graph projection.
- Scope changed: no product scope change. Inspector contents still come from
  existing renderers; this milestone only migrated the route authority.
- Success criteria status: migrated model/resource selection and
  inspector/export routing criteria are complete. Scene/entity/resource
  relationship views and broader export provenance remain open.
- Next smallest useful milestone: M6 define a graph-backed scene/entity
  relationship projection before migrating Entity View or scene usage strips.
- Validation:
  `python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q`
  passed with 20 tests.
  `python -m unittest discover -s tests -v` passed with 145 tests.
  `cd frontend; npm run build` passed.
  `agent-browser` validation passed against `http://127.0.0.1:8894` with
  selected id `SAMPLES.HQR:0`; note and screenshot are in
  `docs/validation-m5-inspector-routing-2026-05-07.md` and
  `docs/validation-m5-inspector-routing-2026-05-07.png`.

Status: Completed

### M6 - Define graph-backed scene/entity relationship projection

Goal:

- Create the smallest backend graph projection needed for scene/entity/resource
  relationship views before replacing Entity View, scene usage strips, or
  export provenance joins.

Recommended focus:

- Start with one scene object such as `SCENE.HQR:2#object:2` and expose its
  incident graph edges, preserving `MissingTarget`, `proofScope`,
  `evidenceStatus`, `sourceRule`, `sourceField`, and `indexRule`.
- Do not migrate the whole Entity View in one step. First define the projection
  and validate one consumer path.

Actions:

- [x] Audit current scene/entity relationship consumers:
  `frontend/src/ui/entityView.ts`, scene usage strip/table helpers in
  `frontend/src/main.ts`, `entities.py`, and export evidence context.
- [x] Add a backend projection or catalog slice for one scene object/resource
  relationship view that returns typed graph edges and missing targets.
- [x] Migrate one narrow relationship view to consume the graph projection and
  remove the superseded local authority for that view.
- [x] Add focused Python tests using synthetic scene object evidence and missing
  targets.
- [x] Validate frontend build and `agent-browser` if visible relationship rows
  change.
- [x] Update graph docs and this `TASK.md` after validation.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation is required if scene/entity/resource relationship rows,
usage strips, or active selection links change.

- Intended: define the smallest graph-backed scene/entity relationship
  projection before replacing Entity View, scene usage strips, or export joins.
- Actual: added
  `catalog_graph.scene_object_relationship_projection.v0` under
  `graph.sceneObjectRelationshipsByStableId`, preserving incident endpoints,
  `MissingTarget`, `proofScope`, `evidenceStatus`, `sourceRule`,
  `sourceField`, and `indexRule`. The scene object table now uses that
  projection for File3D and Visuals cells and no longer reads compact
  `sampled_objects[].links` for those migrated relationship cells.
- Learned: a narrow relationship projection is enough to remove the local
  visual-link authority from one visible scene table without rewriting Entity
  View or scene usage strips yet. Real `SCENE.HQR:2#object:2` validates the
  graph File3D/body/animation row; synthetic graph tests cover unresolved
  sprite `MissingTarget`.
- Assumptions changed: none.
- Architecture status: still valid; relationship decisions can move as small
  backend projections instead of requiring a frontend graph import.
- Scope changed: no product scope change. Non-relationship row facts such as
  flags, position, and render type still come from sampled scene object stats.
- Success criteria status: all current success criteria are now satisfied by
  migrated graph-backed decision surfaces. A final completion audit is required
  before marking the task done.
- Next smallest useful milestone: completion audit across code, docs, tests,
  validation artifacts, and remaining known local authorities.
- Validation:
  `python -m pytest tests/test_catalog_graph.py -q` passed with 16 tests.
  `python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q`
  passed with 22 tests.
  `python -m unittest discover -s tests -v` passed with 147 tests.
  `cd frontend; npm run build` passed.
  `agent-browser` validation passed against `http://127.0.0.1:8896` with
  selected id `SCENE.HQR:2`; note and screenshot are in
  `docs/validation-m6-scene-object-relationships-2026-05-07.md` and
  `docs/validation-m6-scene-object-relationships-2026-05-07.png`.

Status: Completed

## 9. Validation strategy

Use the strongest practical validation available after each milestone.

Commands:

```powershell
python -m pytest tests/test_catalog_graph.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Graph CLI probes:

```powershell
python -m lba2_lm2_viewer catalog-graph --asset-root <root> build --output temp/catalog-graph.json
python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json scene-object SCENE.HQR:2 2 --json
python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json prove BODY.HQR:2 ANIM.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json usages BODY.HQR:29 --proof-scope scene_object_state --evidence-status source_backed --json
```

Manual/browser checks:

- Start a fresh viewer process from this checkout:

```powershell
python -m lba2_lm2_viewer.viewer --host 127.0.0.1 --port <port> --asset-root <retail-root> --no-browser
```

- Use `agent-browser` for visible UI changes.
- Record browser validation under `docs/` with URL, asset root, selected ids,
  expected state, observed state, and screenshot path.
- Confirm the server is not a stale listener before trusting browser evidence.

Validation policy:

- Run relevant validation after each milestone.
- If validation fails, fix or log the failure before starting the next
  milestone.
- If a validation command is unavailable, record why and use the best available
  substitute.
- Documentation-only changes require documentation review and targeted `rg`
  checks, not a full code gate unless code changed.

## 10. Discovery log

Append new facts here as they are discovered. Do not remove historical entries
unless explicitly cleaning up the document.

| Date | Discovery | Evidence | Impact |
| --- | --- | --- | --- |
| 2026-05-07 | The catalog graph spine exists and covers archive/asset identity, scene object projection, File3D resolver evidence, compatibility, ANIM3DS ranges, resource records, script references, and missing targets. | `lba2_lm2_viewer/catalog_graph.py`, graph docs, backend subagent study | Long task can focus on app decision migration rather than inventing the graph model. |
| 2026-05-07 | Animation compatibility is the only clearly graph-backed frontend decision today. | `frontend/src/compatibility.ts`, `frontend/src/ui/catalog.ts`, `frontend/src/main.ts`, frontend subagent study | Next implementation should remove backend playback compatibility divergence before broader UI migration. |
| 2026-05-07 | `docs/design.md` already has the right product boundary and selection-driven workbench posture but does not yet define graph-as-substrate authority. | `docs/design.md`, docs subagent study | First milestone should rewrite design before implementation. |
| 2026-05-07 | Validation currently relies on Python tests, TypeScript/Vite build, graph CLI probes, and manual `agent-browser`; frontend has no automated browser/unit tests. | `pyproject.toml`, `frontend/package.json`, validation subagent study | Each UI milestone needs explicit browser validation notes. |
| 2026-05-07 | `docs/design.md` now treats the catalog graph as the app decision substrate while leaving detailed node/edge vocabulary in the graph docs. | `docs/design.md`, targeted `rg` validation | M2 can focus on the concrete animation operation duplicate path instead of reopening broad design authority. |
| 2026-05-07 | File3D allow-list graph edges need decoded bone-count agreement to be sufficient for pose/playback. | `catalog_graph.add_compatibility_edges`, `tests/test_animation_compatibility.py` | `COMPATIBLE_WITH` can serve current pose/playback eligibility without a second backend validator. |
| 2026-05-07 | Non-`BODY.HQR` model animation playback now follows the graph contract instead of the old server-only bone-count fallback. | `query_animation_operation_compatibility`, frontend compatibility already consumed graph projection | Backend direct pose attempts and frontend animation choices now agree. |
| 2026-05-07 | Model asset selection can be migrated with a narrow `selectionByAssetId` projection instead of a frontend graph import. | `catalog_selection_projection`, `selectionFromCatalogAsset`, browser validation | M4 should extend the projection by selection type rather than sending full graph exports to the frontend. |
| 2026-05-07 | Model relationship links must keep direct scene usage and script reference evidence distinct. | `selection_links_for_usage_edges`, tests on synthetic catalog without reverse usages | Selection projections should carry edge evidence and separate direct usage count from total relationship links. |
| 2026-05-07 | Browser validation of pure model-asset selection should use a no-known-usage model because used models can auto-promote to entity selection. | `agent-browser` validation with `BODY.HQR:29` and `BODY.HQR:2`; `ISSUES.md` | Future selection validation should test pure asset selection and entity-promotion paths separately. |
| 2026-05-07 | Resource asset selection can use the same `selectionByAssetId` projection as model selection while preserving direct Resource ownership. | `catalog_selection_projection`, frontend resource selection, `docs/validation-m4-resource-selection-2026-05-07.md` | M5 can focus on Inspector/export routing metadata for already-migrated model/resource selections. |
| 2026-05-07 | Resource assets can have many script-reference links without implying scene-object ownership. | `SAMPLES.HQR:0` browser validation links and active selection state | Resource projections should carry relationship links as evidence, not as automatic routing instructions. |
| 2026-05-07 | Inspector route authority can move to graph projection metadata without rewriting existing Inspector section renderers. | `inspectorRoute` in `selectionByAssetId`, `renderSelectionInspector()`, M5 browser validation | Next relationship migration can first move route/edge authority, then rewrite richer section content later. |
| 2026-05-07 | Scene object relationship rows can be migrated with an incident-edge projection rather than a full Entity View rewrite. | `catalog_scene_object_relationship_projection`, scene object table File3D/Visuals cells, M6 browser validation | Continue migrating relationship surfaces one consumer path at a time and keep missing targets/evidence fields in backend projections. |

## 11. Decision log

Record meaningful design decisions, especially reversals.

| Date | Decision | Why | Alternatives rejected |
| --- | --- | --- | --- |
| 2026-05-07 | Treat this as a living evolving-goal task, not a fixed workstream checklist. | The app migration is long-running and should adapt as graph/UI evidence appears. | Static all-project checklist with over-specified later milestones. |
| 2026-05-07 | Rewrite `docs/design.md` before the next implementation milestone. | The design contract currently lags the graph substrate and should guide future UI/API decisions. | Continue implementing graph consumers while design still frames Explorer/catalog as primary. |
| 2026-05-07 | Tackle animation operation compatibility before broad selection or Explorer migration. | It is the first graph-backed consumer and has a concrete duplicate backend authority path. | Start with Explorer tree/grouping or Inspector rewrite. |
| 2026-05-07 | Keep `docs/design.md` at the authority-boundary level and keep detailed graph vocabulary in `docs/catalog-graph-model.md`. | The graph docs already define node/edge/proof vocabulary; duplicating it in design would increase review burden and drift risk. | Copy the full graph model into the design contract. |
| 2026-05-07 | Treat `COMPATIBLE_WITH` as sufficient for current pose/playback eligibility, guarded by a graph operation projection. | Current frontend already consumes graph compatibility; adding a separate eligibility edge would duplicate semantics without evidence of different behavior. | Keep `server.py` as a second validator; add distinct playback edges before proving the semantics differ. |
| 2026-05-07 | Start selection migration with model assets only. | Model selection has simple workspace/export semantics and gives a small way to prove projection plumbing. | Migrate all asset types or Inspector routing in the same milestone. |
| 2026-05-07 | Expand selection migration to resource assets before scene or sprite assets. | Resource selection exercises workspace/export routing pressure while avoiding scene auto-promotion and sprite-frame variant complexity. | Migrate scene or sprite selections as the second type. |
| 2026-05-07 | Reuse existing Inspector section renderers while moving migrated Inspector route authority to graph metadata. | The open duplicate was route authority, not section content fidelity; a full Inspector rewrite would be larger than M5 needs. | Rewrite all model/resource Inspector rows into graph section models in one milestone. |
| 2026-05-07 | Migrate the scene object table File3D/Visuals cells before Entity View. | It proves graph-backed relationship projection shape with one visible consumer and avoids a broad workflow rewrite. | Replace all of `entities.py` or scene usage strips in the same milestone. |

## 12. Scope change log

Record any change to goalposts, success criteria, architecture, public behavior,
compatibility expectations, or validation requirements.

| Date | Change | Type | Reason | Requires user approval? | Approval status |
| --- | --- | --- | --- | --- | --- |
| 2026-05-07 | Replaced previous catalog-graph substrate slice task with this graph-backed app decision migration task. | Scope | The previous slice completed enough base graph work; the new task owns design rewrite plus implementation migration. | No | Not needed |

## 13. Risk register

| Risk | Likelihood | Impact | Mitigation | Status |
| --- | ---: | ---: | --- | --- |
| Graph relationship compatibility and playback operation eligibility diverge. | Low | High | M2 defined/tested one operation contract and removed duplicate backend authority. Keep future operation semantics in graph projections. | Mitigated |
| Frontend selection keeps parsing stable ids while graph node identity evolves. | Medium | High | M3/M4 migrated model and resource asset selection to `selectionByAssetId`; continue type-by-type before broad Inspector/Explorer work. | Open |
| Explorer redesign collapses graph relationships into one misleading tree. | Medium | High | Keep Explorer redesign out of near-term milestones; treat it as graph projection later. | Open |
| Graph projections become too large for `/catalog.json` as more UI decisions migrate. | Medium | Medium | Prefer small operation-specific projections and measure before broad exports. | Open |
| Entity/export paths miss `MissingTarget` or evidence metadata by reading `scene_usages`. | High | Medium | Plan later milestones to migrate entity/export relationship decisions to graph edges. | Open |
| Browser validation accidentally hits stale server or generated bundle. | Medium | Medium | Follow `ISSUES.md` stale-listener guidance and record validation server command/URL. | Open |

## 14. Failed approaches

Record failed or abandoned approaches so future sessions do not repeat them.

| Date | Approach | Why it failed | Evidence | Reusable lesson |
| --- | --- | --- | --- | --- |
| 2026-05-07 | Treat Explorer redesign as the next main task after graph base landed. | It would center presentation before graph-backed decision authority is stable. | Prior task discussion and subagent findings show selection/routing/inspector/export still have duplicate truth paths. | Migrate authority paths first; Explorer becomes a later projection. |

## 15. Current state summary

As of 2026-05-07:

- Current state: Done
- Current milestone: Done
- Last completed milestone: M6 - Define graph-backed scene/entity relationship
  projection
- Main discovery: Model/resource selection decisions and one scene object
  relationship view now consume backend graph projections. Remaining local
  authorities are either non-migrated surfaces or future deeper migrations such
  as full Entity View relationship content, scene usage strips, and export
  provenance joins.
- Current architecture direction: backend graph as evidence substrate, with
  operation-specific projections consumed by frontend/backend/export decisions.
- Completion audit: passed. All current success criteria and milestone action
  checklists are checked, focused graph/API tests pass, full Python tests pass,
  frontend build passes, and every visible UI milestone has an `agent-browser`
  validation note and screenshot under `docs/`.
- Open blocker: none
- Next action: none for this task.
- Required approval: none for an internal projection that preserves visible
  behavior; approval may be needed if selection routing or user-visible product
  behavior must change.

## 16. Operating rules for the agent

The agent must follow these rules:

1. Treat the Mission and Hard Constraints as stable.
2. Treat the Current Plan and Architecture Hypothesis as provisional.
3. Work one milestone at a time.
4. After each milestone, update this file before continuing.
5. For each milestone checkpoint, record what was intended, what happened, what
   was learned, whether assumptions changed, whether architecture still makes
   sense, whether scope changed, whether success criteria are still correct, the
   next smallest useful milestone, and the validation that proves it.
6. If implementation evidence contradicts the plan, revise the plan instead of
   brute-forcing it.
7. If a change affects hard constraints, public APIs, data compatibility,
   security, privacy, performance budgets, release process, or user-visible
   product scope, stop and ask for approval.
8. If a change only affects internal implementation strategy, update the
   Decision Log and continue.
9. Prefer evidence from code, tests, errors, runtime behavior, and repo
   conventions over the original plan.
10. Preserve append-only logs unless explicitly asked to clean them up.
11. Keep Current State Summary accurate enough for another session to resume
    without hidden context.
12. Use `agent-browser` for visible UI validation and record the result under
    `docs/`.
13. Update `ISSUES.md` when a surprising project trap is encountered.
14. Do not leave migrated decisions with both graph-backed and local authority
    paths.
