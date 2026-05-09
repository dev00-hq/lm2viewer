# Task: Finish Graph-Backed Authority Migration

## 0. Metadata

- Owner: project maintainer
- Agent/session: Codex, 2026-05-09
- Created: 2026-05-09
- Last updated: 2026-05-09
- Current state: Designing
- Current milestone: M0 (define)

## 1. Mission

The durable purpose of this task is:

> Finish removing app-facing authority from catalog enrichment fields —
> specifically `asset.scene_usages`, `asset.kind`, `stats.semantic_layout`,
> and `stats.reconnaissance` — so every remaining app decision consumes
> backend graph projections instead of re-deriving truth from local catalog
> payloads.

This task is the completion arc for the broader graph-backed migration from
[TASK.md](TASK.md). That task established the graph spine and migrated
animation compatibility, model/resource selection identity, inspector/export
routing, and one scene relationship view. This task finishes the remaining
duplicate truth paths:

- entity workflow builders (`entities.py`)
- export evidence context and promotion-packet joins (`server.py`)
- scene usage strip rendering (`main.ts`)
- server-side load and export routing (`server.py`)
- script evidence tables (`main.ts`)

This task should optimize for:

- one canonical current-state implementation;
- evidence clarity across UI, backend, CLI, exports, and port-facing probes;
- reduced human review burden by migrating one decision surface at a time.

## 2. Hard constraints

Same as TASK.md §2. In particular:

- Migration is replacement, not coexistence: when a decision moves to the
  graph, remove the superseded local authority in the same milestone unless a
  tracked risk explicitly defers removal.
- The backend Python graph builder remains the source of graph semantics.
- Do not move graph semantics into frontend-only TypeScript.
- Do not redesign Explorer or rewrite Inspector section content in this task;
  only move authority for routing/relationship/source decisions that are still
  local.
- Use `agent-browser` to validate visible UI changes.
- If a change affects hard constraints, public APIs, data compatibility,
  security, privacy, performance budgets, release process, or user-visible
  product scope, stop and request approval.

## 3. Soft constraints and preferences

- Prefer graph projections/query responses over sending full graph exports to
  the frontend.
- Prefer operation-specific graph contracts over vague relationship labels.
- Keep near-term milestones narrow enough to validate with focused tests and
  one browser flow.
- Use synthetic tests for graph semantics whenever retail asset coverage would
  be slow or brittle.
- Keep `docs/catalog-graph-model.md` and `docs/catalog-graph-queries.md`
  synchronized when graph vocabulary changes.

## 4. Current success criteria

The task is considered successful when:

- [ ] `entities.py` workflow builders consume graph projections instead of
  `asset.scene_usages`, `stats.reconnaissance.sampled_objects[].links`, and
  direct `catalog.assets` iteration for entity resolution.
- [ ] `server.py` export evidence context (`export_evidence_context`,
  `export_scene_indices_for_asset`, `export_evidence_status`) consumes graph
  projections instead of `asset.scene_usages`.
- [ ] Frontend scene usage strip for migrated model/resource selections
  consumes `selectionByAssetId[].links` instead of `asset.scene_usages`.
- [ ] `server.py` `handle_catalog_load` routing and `export_catalog_asset`
  routing consume graph projection metadata instead of `asset.kind +
  semantic_layout` for migrated types.
- [ ] Script evidence tables consume `sceneObjectRelationshipsByStableId`
  incident edges instead of `stats.reconnaissance.sampled_objects[].scripts`.
- [ ] Each migrated authority path has no remaining local duplicate rule.
- [ ] Python tests pass for all migrated backend behavior.
- [ ] Frontend build passes for all migrated frontend behavior.
- [ ] Any visible browser behavior change has an `agent-browser` validation
  note under `docs/` with URL, asset root, selected ids, expected state,
  observed state, and screenshot path.

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

## 6. Current understanding

### Problem model

TASK.md migrated six specific decision surfaces to the graph (M2–M6). Six more
remain — some are small duplicate paths, others are cross-cutting workflow
builders.

The remaining local authorities all read from the same catalog enrichment
fields:

- `asset.scene_usages` — used by `entities.py` workflow builders, server
  export evidence context, and frontend usage strip.
- `stats.semantic_layout` — used by server load/export routing and frontend
  `isExportableCatalogAsset`.
- `stats.reconnaissance.sampled_objects[].links` — used by `entities.py`
  `build_entity_contract` for linked visual assets.
- `stats.reconnaissance.sampled_objects[].track_script_analysis` /
  `life_script_analysis` — used by frontend script evidence tables.

The catalog graph already has all the evidence needed to replace every one of
these reads:

- `graph.indexes.sceneUsagesByAssetId` — usage edges indexed by target asset.
- `graph.selectionByAssetId[assetId].links` — graph-backed usage links with
  edge evidence fields.
- `graph.sceneObjectRelationshipsByStableId` — incident edges per scene object
  with `MissingTarget`, `proofScope`, `evidenceStatus`, `sourceRule`,
  `sourceField`, `indexRule`.
- `graph.indexes.assetsByKind`, `graph.indexes.resourcesBySemanticLayout` —
  graph-level asset classification.

The catalog payload still provides raw facts that build the graph. The
migration is about routing app decisions through the graph projections, not
removing the payload itself.

### Current duplicate or non-graph decision paths

| Surface | File | Local field | Graph replacement available? |
|---|---|---|---|
| Entity workflow — usage selection | `entities.py:23` | `asset.scene_usages` | `sceneUsagesByAssetId` index |
| Entity workflow — runtime sprite | `entities.py:112` | `asset.scene_usages` | `sceneUsagesByAssetId` index |
| Entity workflow — scene object lookup | `entities.py:242` | `reconnaissance.sampled_objects` | `sceneObjectRelationshipsByStableId` |
| Entity workflow — linked visuals | `entities.py:286` | `links.body/animation/sprite` | `sceneObjectRelationshipsByStableId.visualLinks` |
| Export evidence context | `server.py:420-425` | `asset.scene_usages` count | `selectionByAssetId.facets.sceneUsageCount` |
| Export scene indices | `server.py:485-495` | `asset.scene_usages` iteration | `sceneUsagesByAssetId` index |
| Export evidence status | `server.py:498-509` | `asset.stats` directly | `catalog_graph.evidence_status_for_asset` |
| Scene usage strip | `main.ts:731` | `asset.scene_usages` | `selectionByAssetId.links` |
| Server load routing | `server.py:2133-2143` | `asset.kind` | `selectionByAssetId.inspectorRoute` |
| Server export routing | `server.py:526-544` | `asset.kind + semantic_layout` | `selectionByAssetId.exportCapability` |
| Script evidence tables | `main.ts:1300-1330` | `reconnaissance.sampled_objects[].scripts` | `sceneObjectRelationshipsByStableId.edges` (partial) |
| `hasSceneUsages` | `main.ts:585` | `asset.scene_usages.length` | `selectionByAssetId.facets.sceneUsageCount` |

### Known unknowns

- Will the entity workflow output change shape visibly for Entity View
  consumers? If so, what browser validation is needed?
- Can `build_entity_contract` remove its dependency on `reconnaissance` fully,
  or will some fields (position, flags, render type) still need to come from
  sampled scene object stats?
- Does the script evidence table need instruction-level detail from the graph,
  or is the incident-edge evidence (ScriptReference nodes + SCRIPT_REFERENCES
  edges) sufficient for the inspector table?
- Which of the remaining `.split('#')` calls in `main.ts` can be removed in
  this task without blocking non-migrated selection types?

### Assumptions

| Assumption | Confidence | How to validate |
|---|---|---|
| `entities.py` can consume `sceneObjectRelationshipsByStableId` for linked visuals without changing Entity View rendering. | Medium | Build a graph-backed entity contract and compare output fields against current browser state. |
| Server export routing can use graph projection metadata without changing which assets are exportable. | High | The `exportCapability` field already matches `isExportableCatalogAsset` for model/resource. |
| Script evidence migration can start with incident edges; instruction-level detail can stay local until the graph models it. | Medium | Compare existing instruction rows with what `ScriptReference` edges provide. |
| Scene local evidence (zones, waypoints, GRM links, patches) is out of scope for this task. | High | These aren't relationship data; they're scene-local structural evidence not yet graph-modeled. |

## 7. Current architecture hypothesis

Same as TASK.md §7. The flow is:

1. `viewer.build_catalog()` produces catalog facts.
2. `catalog_graph.build_catalog_graph()` materializes relationship evidence.
3. Backend services expose graph-backed projections for each app decision.
4. Frontend components consume those projections instead of raw catalog fields.
5. CLI/agent/port use the same graph query vocabulary.

The new work adds two projection consumers:

- `entities.py` will consume `sceneObjectRelationshipsByStableId` and
  `sceneUsagesByAssetId` instead of raw `scene_usages` and `reconnaissance`.
- `server.py` export context will consume `selectionByAssetId` and
  `sceneUsagesByAssetId` instead of `asset.scene_usages`.

Components likely to change:

- `lba2_lm2_viewer/entities.py`
- `lba2_lm2_viewer/server.py`
- `lba2_lm2_viewer/catalog_graph.py` (minor projection additions)
- `frontend/src/main.ts`
- `tests/test_catalog_graph.py`
- `tests/test_entities.py`
- `tests/test_entity_workflows.py`
- `docs/catalog-graph-model.md` (if vocabulary changes)

Components that should not change:

- HQR parsing and core decoder semantics.
- Product boundary as a local evidence workbench.
- Existing selection/routing/inspector projections from TASK.md (M3–M6).
- Explorer, Catalog UI, Sprite Viewer, Resource Workspace, UV Inspector
  (unless their authority path is directly targeted).

## 8. Current plan

### M7 — Migrate entity workflows to graph projections

Goal: Make `entities.py` consume graph-backed projections instead of raw
`scene_usages` and `reconnaissance.sampled_objects`.

Recommended subagents before implementation:

- Entity workflow auditor: trace all `asset.scene_usages`,
  `scene_asset.stats.reconnaissance`, `find_asset(catalog, ...)`,
  `linked_visual_assets(links)`, and `find_scene_object()` calls in
  `entities.py` and map them to the graph projections they could consume.
- Frontend Entity View auditor: check `entityView.ts` and the Entity View
  rendering path in `main.ts` for fields consumed from the workflow payload
  that must survive.
- Test reviewer: check `test_entities.py` and `test_entity_workflows.py` for
  coverage of the workflow build paths that will change.

Subagents should not implement changes. The main agent owns implementation.

Actions:

- [ ] Add a graph-backed entity projection to `catalog_graph.py` (or extend
  `sceneObjectRelationshipsByStableId`) that returns the entity contract
  fields currently derived from `scene_usages` and `reconnaissance`.
- [ ] Rewrite `build_asset_entity_workflow`, `build_scene_object_entity_workflow`,
  and `build_runtime_sprite_entity_workflow` to consume the graph projection.
- [ ] Replace `linked_visual_assets(links)` with graph-backed visual links
  from `sceneObjectRelationshipsByStableId.visualLinks`.
- [ ] Replace `find_scene_object()` with a graph query that reads scene
  object node metadata.
- [ ] Remove superseded local authority for the migrated decisions.
- [ ] Update tests and add focused graph-backed entity contract tests.
- [ ] Validate with Python tests, frontend build, and `agent-browser` against
  Entity View for a scene object selection.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py tests/test_entities.py tests/test_entity_workflows.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation: Entity View visible content for `SCENE.HQR:2#object:2`
must match current behavior (linked visuals, render backend, script links,
port implications).

### M8 — Migrate export evidence context to graph

Goal: Make `server.py` export evidence context methods consume graph
projections instead of `asset.scene_usages`.

Recommended focus:

- `export_evidence_context()` — replace `len(asset.scene_usages)` with
  `selectionByAssetId.facets.sceneUsageCount`.
- `export_scene_indices_for_asset()` — replace `scene_usages` iteration with
  graph `sceneUsagesByAssetId` index queries.
- `export_evidence_status()` — replace standalone status derivation with
  `catalog_graph.evidence_status_for_asset()` (already exists).

Actions:

- [ ] Replace `export_evidence_status` with a call to
  `catalog_graph.evidence_status_for_asset`.
- [ ] Replace `export_scene_indices_for_asset` scene_usage iteration with
  graph index queries.
- [ ] Replace `export_evidence_context` scene_usage_count with graph
  projection field.
- [ ] Add focused tests proving export context agrees with graph projection.
- [ ] Update `TASK_DS.md` after validation.

Validation:

```powershell
python -m pytest tests/ -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

### M9 — Migrate frontend scene usage strip for migrated types

Goal: Make the scene usage strip consume `selectionByAssetId[].links` for
model and resource selections instead of `asset.scene_usages`.

Recommended focus:

- `renderSceneUsageStrip()` currently renders usage buttons from
  `asset.scene_usages` for all selection types.
- For model/resource selections, the graph projection already carries
  `links` with `stableId`, `label`, `proofScope`, `evidenceStatus`,
  `sourceRule`, `sourceField`, and `indexRule`.
- Keep non-migrated types (scene, sprite, animation) on the local path.

Actions:

- [ ] Add a branch in `renderSceneUsageStrip()` that renders from
  `selection.links` when the selection is a migrated type.
- [ ] Render each link with its edge evidence fields visible in the button
  title or detail span.
- [ ] Remove the local `asset.scene_usages` read for migrated types.
- [ ] Validate with frontend build and `agent-browser` for a model and
  resource selection with known scene usages.

### M10 — Migrate server load/export routing for migrated types

Goal: Make server-side `handle_catalog_load` and `export_catalog_asset`
routing consume graph projection metadata instead of `asset.kind +
semantic_layout`.

Recommended focus:

- `handle_catalog_load` (line 2133): replace `asset.kind` dispatch with
  graph-backed inspector route lookup.
- `export_catalog_asset` (lines 526–544): replace the 16-line
  `kind + semantic_layout` chain with graph-backed export capability check.
- Keep non-migrated types on the local path.

Actions:

- [ ] Add a graph-backed `export_route_for_asset` method to `catalog_graph`
  (or reuse `is_exportable_asset_node` + `inspector_route_for_asset_node`).
- [ ] Change `handle_catalog_load` to look up the inspector route from the
  graph projection for model/resource assets.
- [ ] Change `export_catalog_asset` to look up export capability from the
  graph projection for model/resource assets.
- [ ] Remove superseded local dispatch branches for migrated types.
- [ ] Validate with Python tests, frontend build, and `agent-browser` for
  model and resource export flows.

### M11 — Migrate script evidence tables to graph

Goal: Make script evidence tables consume graph `ScriptReference` edges and
`sceneObjectRelationshipsByStableId` incident edges instead of reading
`reconnaissance.sampled_objects[].track_script_analysis` /
`life_script_analysis` directly.

Recommended focus:

- The graph already has `ScriptReference` nodes and `SCRIPT_REFERENCES`
  edges attached to scene objects with `sourceRule`, `sourceField`,
  `indexRule`, and link-to-target evidence.
- Instruction-level detail (opcodes, offsets) may remain local since the
  graph doesn't model individual instructions yet.
- The table's structural evidence (owner stable ID, script kind, link
  counts) can move to graph immediately.

Actions:

- [ ] Extend `sceneObjectRelationshipsByStableId` to include script evidence
  summary fields (script kind, instruction count, control flow link count)
  derived from graph edges.
- [ ] Change `scriptEvidenceForSelection()` to consume the graph projection
  instead of reading `reconnaissance` directly.
- [ ] Keep instruction-level rows on the local path with a clear boundary
  comment.
- [ ] Validate with Python tests and `agent-browser` against script evidence
  table for `SCENE.HQR:2#object:2`.

### M12 — Final audit and cleanup

Goal: Verify every remaining local authority is either migrated or explicitly
scoped as non-migrated.

Actions:

- [ ] Audit all `asset.scene_usages`, `asset.kind`, `semantic_layout`, and
  `reconnaissance` reads in `entities.py`, `server.py`, and `main.ts`.
- [ ] Confirm each remaining read is either graph-backed or explicitly
  scoped as catalog enrichment input or non-migrated surface.
- [ ] Update `docs/catalog-graph-model.md` if new projections were added.
- [ ] Update `ISSUES.md` if any surprising traps were encountered.
- [ ] Final validation suite.

## 9. Validation strategy

Same as TASK.md §9 with the addition of entity workflow tests:

```powershell
python -m pytest tests/test_catalog_graph.py tests/test_entities.py tests/test_entity_workflows.py tests/test_animation_compatibility.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation flows needed:

- M7: Entity View for `SCENE.HQR:2#object:2` — linked visuals, render
  backend, script links, port implications.
- M8: Export manifest for a model asset — evidence context fields.
- M9: Scene usage strip for `BODY.HQR:29` (a used model) — usage buttons
  with edge evidence.
- M10: Model and resource export flows — routing and export capability.
- M11: Script evidence table for `SCENE.HQR:2#object:2` — script summaries
  and instruction samples.

Each browser validation must record: URL, server command, asset root,
selected id(s), expected state, observed state, and screenshot path under
`docs/`.

## 10. Discovery log

| Date | Discovery | Evidence | Impact |
| --- | --- | --- | --- |
| 2026-05-09 | Six remaining duplicate/local authority surfaces exist across entities.py, server.py, and main.ts after TASK.md M0–M6. | Code audit of all `scene_usages`, `semantic_layout`, `reconnaissance` reads. | This task can focus on these six surfaces in dependency order. |
| 2026-05-09 | `entities.py` is the most cross-cutting remaining surface — it feeds Entity View, runtime sprite resolution, and scene-object selection. | `build_asset_entity_workflow`, `build_scene_object_entity_workflow`, `build_runtime_sprite_entity_workflow` all read `scene_usages` and `reconnaissance`. | M7 should be first; unblocking entities.py unblocks cleaner migration of the other authority paths. |
| 2026-05-09 | Scene local evidence (zones, waypoints, GRM links, patches) is not yet graph-modeled and is out of scope for this task. | `renderSceneLocalTable` reads `reconnaissance.sampled_zones`, `sampled_tracks`, `grm_fragment_links`, `sampled_patches`. | Defer to a future task that models scene-local structural evidence in the graph. |

## 11. Decision log

| Date | Decision | Why | Alternatives rejected |
| --- | --- | --- | --- |
| 2026-05-09 | Start with `entities.py` (M7) before export context or frontend strips. | Entity workflows are the most cross-cutting remaining surface; they feed Entity View, runtime sprite resolution, and scene-object selection. Cleaning them first unblocks cleaner migration of downstream consumers. | Start with smaller M8/M9/M10 surfaces first, leaving entities.py with both local and graph paths. |
| 2026-05-09 | Keep instruction-level script evidence local in M11; migrate structural evidence only. | The graph has `ScriptReference` nodes and edges but doesn't model individual opcodes. Adding that now would be a vocabulary expansion, not an authority migration. | Add instruction-level nodes to the graph; delay until a measured need exists. |
| 2026-05-09 | Keep scene local evidence (zones, waypoints, GRM links, patches) out of scope. | These aren't relationship data; they're scene-local structural evidence not yet graph-modeled. | Model them in the graph now. |

## 12. Scope change log

| Date | Change | Type | Reason | Requires user approval? | Approval status |
| --- | --- | --- | --- | --- | --- |
| 2026-05-09 | Task created as completion arc for TASK.md graph-backed migration. | Scope | TASK.md completed M0–M6 but left six duplicate/local authority surfaces. | No | Not needed |

## 13. Risk register

| Risk | Likelihood | Impact | Mitigation | Status |
| --- | ---: | ---: | --- |
| Entity View behavior changes visibly when entities.py switches to graph projections. | Medium | High | Validate against `agent-browser` for `SCENE.HQR:2#object:2` before marking M7 complete. | Open |
| Entity contract fields that don't have graph equivalents (position, flags, render type) require a mixed authority path that complicates the clean-cut rule. | Medium | Medium | Explicitly scope non-relationship fields as "catalog enrichment input" with a boundary comment; keep the migration focused on relationship/usage/source authority. | Open |
| Server export routing changes could break export for non-migrated types if the fallback path is accidentally removed. | Low | High | Keep non-migrated type dispatch as explicit fallback branches with clear boundary comments. | Open |
| Graph projection size under `/catalog.json` increases with each new projection added. | Low | Low | The projections in this task are small field additions to existing selection/relationship projections, not new bulk exports. | Open |

## 14. Failed approaches

(Empty — no approaches attempted yet.)

## 15. Current state summary

As of 2026-05-09:

- Current state: Designing
- Current milestone: M0 (define)
- Last completed milestone: none yet
- Main discovery: TASK.md M0–M6 migrated animation compatibility, model/resource
  selection identity, inspector/export routing, and scene object relationship
  cells. Six duplicate/local authority surfaces remain in `entities.py`,
  `server.py`, and `main.ts`.
- Current architecture direction: backend graph as evidence substrate, with
  operation-specific projections consumed by all app decision surfaces.
- Open blocker: none
- Next action: begin M7 after subagent audit of entity workflow paths.
- Required approval: none for internal authority migration that preserves
  visible behavior.

## 16. Operating rules for the agent

Same as TASK.md §16.
