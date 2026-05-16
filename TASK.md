# Task: Scene Mechanics Graph v1

## 0. Metadata

- Owner: project maintainer
- Created: 2026-05-10
- Source: GPT Pro architecture review of
  `temp/gpt-pro-evidence/lba2-lm2-viewer-gpt-pro-evidence.zip`
- Current state: M17 implementation completed after critical-sparring audit;
  formerly significant graph cardinality, edge-selection, relationship-export,
  edge-vocabulary, query-surface, and resource-record selection gaps are now
  implemented and validated
- Current milestone: M17 - Scene Mechanics Graph v1

## 1. North Star

Keep the app on the current backend-owned evidence graph path:

```text
catalog graph -> selection projection -> inspector route -> export/proof context
```

The next work should be a scene mechanics graph slice, not a broad runtime
interpreter, general asset browser, or port-contract layer.

The highest-risk gap is relationship occurrence identity. Before promoting many
new node types, graph edges and frontend relationship selections need stable
edge/occurrence identities so repeated references, relationship-row exports,
usage strips, and proof contexts cannot collapse distinct facts.

## 2. Hard Constraints

- Keep one canonical current-state implementation.
- Do not add compatibility bridges, migration shims, dual old/new paths, or
  silent fallbacks.
- Backend Python owns graph semantics, exportability, routing, workspace
  ownership, and operation eligibility.
- Frontend TypeScript may render graph projections and local visual state, but
  must not rediscover graph relationship truth.
- The catalog graph describes decoded initial state, source-backed rules,
  resolver contracts, and potential effects. It must not claim live runtime
  state unless a separate runtime/event evidence source exists.
- Missing, unknown, unresolved, and intentionally deferred facts must stay
  explicit evidence.
- Use `agent-browser` for visible UI changes and record validation notes under
  `docs/`.
- If a surprising project trap appears, alert the developer and update
  `ISSUES.md`.

## 3. Recommended Promotion Order

1. Relationship occurrence identity and edge selection.
2. `SceneZone`.
3. `Waypoint`.
4. Limited script occurrence / `ScriptInstruction` layer for selectable and
   queryable facts.
5. `RuntimeStateField` and `PatchRecord` as static decoded evidence, not live
   runtime state.
6. Defer full `EvidenceSource` and `PortContract` nodes until graph-selected
   node/edge exports are stable.

Do not put dynamic runtime behavior into the existing catalog graph. Add a
separate runtime/event graph later for observations, simulations, live
confirmations, or trace-derived state transitions.

## 4. M17.1 - Relationship Occurrence Identity

Goal:

- Make every selectable graph relationship addressable by a stable edge and
  occurrence identity.
- Stop relationship-row UI and export behavior from joining by stable-id string
  heuristics or fallback metadata.

Add to selectable edge projections where applicable:

- `edgeId`
- `sourceEvidenceId`
- `occurrenceOrdinal`
- `ownerNodeId`
- `sourcePath`
- `sourceOffset`
- `rawReference`
- `targetStableId`
- `resolverKind`

Actions:

- [ ] Audit current edge creation in `catalog_graph.py` for relationship
      families that can repeat with the same type/from/to/proof/source fields.
- [ ] Add source occurrence identity to graph edge construction without
      collapsing repeated same-target script/resource references.
- [ ] Carry `edgeId` and `sourceEvidenceId` into:
      `selectionByAssetId.links`, usage records, scene-object relationship
      projections, export context, and graph export JSON.
- [ ] Make relationship-row selections edge selections, not reconstructed
      `scene#object` or target-asset selections.
- [ ] Make scene usage strip selection edge-id based and fail closed when the
      edge record is missing.
- [ ] Ensure subgraph export and relationship-row export can preserve selected
      edge identity.

Validation:

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe
```

New/updated tests:

- [ ] `test_script_reference_occurrences_do_not_collapse`
- [ ] `test_relationship_row_selection_uses_edge_id`
- [ ] `test_subgraph_export_includes_selected_edge_identity`
- [ ] `test_export_from_relationship_row_records_selected_edge_id`

## 5. M17.2 - Promote SceneZone

Goal:

- Promote decoded scene zones to first-class graph nodes with precise,
  source-backed contract evidence where known.

Minimal node:

```text
Node type: SceneZone
Stable id: SCENE.HQR:<entry>#zone:<zeroBasedZoneIndex>
Core attrs:
  sceneAssetId
  zoneIndex
  zoneType
  zoneNum / value
  bounds: x0,y0,z0,x1,y1,z1
  serializedInfo: Info0..Info7
  loadState: normalized post-load fields where source-backed
  contractKinds:
    change_cube | camera | scenario | grm | giver | message |
    hit | ladder | escalator | rail
```

Minimal edges:

```text
Scene             -HAS_ZONE->                 SceneZone
SceneZone         -USES_TEXT->                ResourceRecord | Asset | MissingTarget
SceneZone         -APPLIES_GRM_FRAGMENT->     Asset | MissingTarget
SceneZone         -CHANGES_CUBE_TO->          ResourceRecord | MissingTarget
SceneZone         -REFERENCES_ZONE->          SceneZone
ScriptInstruction -CONTROLS_ZONE->            SceneZone
SceneZone         -DECLARES_RUNTIME_CONTRACT-> contract facet or summary
```

Actions:

- [ ] Materialize `SceneZone` nodes from decoded `SCENE.HQR` zone records.
- [ ] Preserve serialized fields separately from source-backed load-normalized
      fields.
- [ ] Add precise zone relationships for text/message, GRM fragment, change
      cube, camera/message gates, hit, ladder, escalator, rail, scenario, and
      giver evidence where already decoded.
- [ ] Keep unknown zone fields as unknown descriptors until evidence supports
      promotion.
- [ ] Add Inspector/query projections for selected scene zones.
- [ ] Update `docs/catalog-graph-model.md` so `SceneZone` is no longer listed
      as merely a future candidate.

Validation:

- [ ] `test_scene_zones_materialized_with_contract_edges`
- [ ] Agent-browser validation for selecting a zone relationship or query
      result and seeing graph-backed Inspector evidence.

## 6. M17.3 - Promote Waypoint

Goal:

- Promote decoded scene waypoints as addressable graph nodes and connect
  movement/script references without implying executed movement paths.

Minimal node:

```text
Node type: Waypoint
Stable id: SCENE.HQR:<entry>#waypoint:<zeroBasedWaypointIndex>
Core attrs:
  sceneAssetId
  waypointIndex
  position: x,y,z
  evidenceStatus: decoded_only or source_backed when referenced by rule
```

Minimal edges:

```text
Scene             -HAS_WAYPOINT->          Waypoint
SceneObject       -MOVEMENT_TARGETS->      Waypoint
ScriptInstruction -REFERENCES_WAYPOINT->   Waypoint
ScriptInstruction -TRACK_LABEL_TARGETS->   Waypoint
```

Actions:

- [ ] Materialize `Waypoint` nodes from decoded `T_TRACK` coordinate records.
- [ ] Connect source-backed scene-object movement references such as
      `MOVE_CIRCLE` and `MOVE_CIRCLE2`.
- [ ] Connect script references only when operand semantics support the
      relationship.
- [ ] Do not claim pathfinding, route traversal, or execution semantics from
      waypoint references.
- [ ] Add Inspector/query projections for selected waypoints.

Validation:

- [ ] `test_waypoints_materialized_and_script_refs_resolve`
- [ ] Search/query validation for scene waypoint references.

## 7. M17.4 - Script Occurrence Layer

Goal:

- Represent script structure and selectable/queryable script occurrences
  without pretending the app has a full interpreter.

Promote graph facts that are structural, addressable, or source-backed:

- decoded script block and instruction identity;
- instruction byte offsets;
- resolved same-script control-flow targets;
- resolved cross-script targets;
- asset/resource references;
- object/zone/waypoint local references;
- patch target instruction/field links;
- source-backed execution contracts;
- runtime-mutable operand fields.

Keep decoded-local:

- raw full script listings;
- preview tables and aggregate opcode/category counts;
- condition function/comparator count summaries;
- raw operands that are not selected/queryable;
- large local analysis payloads used only by scene detail rendering.

Reserve for runtime/event or symbolic layers:

- branch execution;
- current behavior/comportment;
- current body/animation/sprite after script mutation;
- actual sample playback;
- actual GRM on/off state;
- actual cube transition success;
- live animation frame, loop, or timer state;
- final dynamic render ordering with runtime lists.

Minimal nodes:

```text
Node type: ScriptBlock
Stable id: SCENE.HQR:<entry>#object:<idx>#script:<track|life>

Node type: ScriptInstruction
Stable id: SCENE.HQR:<entry>#object:<idx>#script:<track|life>#offset:<byteOffset>
Core attrs:
  opcode
  mnemonic
  byteLength
  operandHex
  behaviorCategory
  decodedOperandSemantics subset
```

Minimal edges:

```text
SceneObject       -HAS_SCRIPT->                  ScriptBlock
ScriptBlock       -HAS_INSTRUCTION->             ScriptInstruction
ScriptInstruction -CONTROL_FLOW_TO->             ScriptInstruction
ScriptInstruction -REFERENCES_OBJECT->           SceneObject | MissingTarget
ScriptInstruction -REFERENCES_WAYPOINT->         Waypoint | MissingTarget
ScriptInstruction -CONTROLS_ZONE->               SceneZone | MissingTarget
ScriptInstruction -SCRIPT_REFERENCES->           Asset | ResourceRecord | MissingTarget
ScriptInstruction -DECLARES_EXECUTION_CONTRACT-> contract facet or summary
```

Actions:

- [ ] Add a new proof scope such as `script_structure` for decoded layout,
      local control-flow, cross-script targets, and targetable instruction
      facts.
- [ ] Keep `script_reference` for asset/resource references.
- [ ] Keep `classic_source_rule` for source-backed opcode effects.
- [ ] Start with selectable/queryable instruction occurrences instead of
      materializing every possible display row.
- [ ] Measure graph size after instruction promotion.

Validation:

- [ ] `test_script_reference_occurrences_do_not_collapse`
- [ ] `test_search_returns_edges_and_nodes`
- [ ] Graph-size audit against the full retail asset root.

## 8. M17.5 - PatchRecord And RuntimeStateField

Goal:

- Promote patch and runtime-mutable field evidence as static decoded/catalog
  facts, not live state.

Minimal nodes:

```text
Node type: PatchRecord
Stable id: SCENE.HQR:<entry>#patch:<idx>

Node type: RuntimeStateField
Stable id:
  SCENE.HQR:<entry>#object:<idx>#script:<track|life>#offset:<byteOffset>#field:<fieldName>
Core attrs:
  fieldName
  operandOffset
  size
  initialValue / initialHex
  source
  mutableByRuntime: true
```

Minimal edges:

```text
Scene             -HAS_PATCH->              PatchRecord
PatchRecord       -PATCHES_INSTRUCTION->    ScriptInstruction | MissingTarget
PatchRecord       -PATCHES_FIELD->          RuntimeStateField | MissingTarget
ScriptInstruction -OWNS_RUNTIME_FIELD->     RuntimeStateField
ScriptInstruction -MAY_MUTATE_FIELD->       RuntimeStateField
```

Actions:

- [ ] Materialize patch records only where decoded scene payload supports them.
- [ ] Preserve unknown/non-instruction patch targets as explicit
      `MissingTarget` or `UnknownEvidence`.
- [ ] Do not add a broad `RuntimeState` catalog node.
- [ ] Add Inspector/query surfaces only for selected/queryable patch and field
      evidence.

Validation:

- [ ] `test_patch_record_targets_runtime_state_field`

## 9. Selection Identity Contract

Goal:

- Adopt one selection envelope across catalog graph selections, future runtime
  event selections, and frontend-local visual facets.

Recommended selection fields:

```text
selectionId
authority: catalog_graph | runtime_event_graph | local_visual
kind
nodeId?
edgeId?
stableId
ownerNodeId?
parentSelectionId?
source
proofScope
evidenceStatus
links
unknowns
inspectorRoute
workspaceSuggestion
exportActions
inheritedFrom?
uiStatus?
```

Rules:

- Catalog asset selections use backend graph node identity and backend
  projected route/workspace/export actions.
- Scene object selections use `SceneObject` node identity and incident graph
  relationships.
- Scene usage and relationship-row selections use graph edge identity.
- Resource record selections should use `ResourceRecord` node identity, not
  locally fabricated selection truth.
- Model surface, animation pose, palette context, and similar visual facets are
  local visual selections. They may show inherited parent graph links, but must
  label inherited evidence/actions explicitly.
- Runtime sprite resolution should eventually return a runtime/event selection
  projection from the backend, anchored to catalog evidence.
- UI statuses such as preview/live badges must stay separate from graph
  evidence statuses.

Frontend hardening actions:

- [ ] Fail closed for all graph-migrated assets when an expected selection
      projection is missing.
- [ ] Stop deriving ANIM3DS ranges in the frontend; consume graph indexes or a
      backend projection.
- [ ] Make resource-record selection graph-projected through `selectionByNodeId`
      or equivalent.
- [ ] Move runtime sprite resolution selection to a backend runtime/event
      projection before treating it as evidence.
- [ ] Separate `uiStatus` from graph `evidenceStatus`.
- [ ] Update entity facets to consume graph relationships once zones,
      waypoints, runtime-state fields, and edge identity are modeled.
- [ ] Prefer graph export actions as the single export authority instead of
      independently routing through asset kind/layout.

Validation:

- [ ] `test_graph_projected_asset_missing_selection_fails_closed_for_all_kinds`
- [ ] `test_derived_visual_selection_does_not_inherit_export_action_implicitly`
- [ ] `test_resource_record_selection_comes_from_graph_node`
- [ ] `test_runtime_resolution_selection_is_event_projection`
- [ ] `test_export_route_comes_from_graph_action`
- [ ] Agent-browser regression for selection, Inspector clearing, relationship
      row selection, and resource-record selection.

## 10. Runtime/Event Graph Direction

Goal:

- Keep catalog evidence pure while leaving a clear path for runtime/live proof.

Do not emit `live_confirmed` from the catalog graph. The catalog graph may say:

- a zone may apply a GRM fragment;
- an instruction may mutate `OBJ_BACKGROUND`;
- a scene object initially uses a body/animation/sprite;
- an animation is operation-compatible with a model;
- a sample/text/video target is referenced.

A future runtime/event graph should say:

- a GRM toggle happened;
- a sample played with parameters;
- an object flag changed;
- a cube transition was attempted and succeeded/failed;
- an animation advanced to a frame/loop state;
- a runtime sprite resolver request resolved to a target.

Future runtime/event node candidates:

```text
RuntimeSession
RuntimeEvent
RuntimeStateSnapshot
RuntimeResolutionEvent
RuntimeMutationEvent
RuntimePlaybackEvent
```

Future runtime/event edges:

```text
RuntimeEvent -ANCHORS_TO-> CatalogGraph node/edge
RuntimeEvent -RESOLVES_TO-> Asset | MissingTarget
RuntimeEvent -MUTATES_FIELD-> RuntimeStateField
RuntimeEvent -APPLIES_GRM-> SceneZone / background resource
RuntimeEvent -CHANGES_CUBE-> SceneZone / background cube evidence
RuntimeEvent -PLAYS_SAMPLE-> Asset | MissingTarget
RuntimeEvent -ADVANCES_ANIMATION-> Asset pair / animation pose
```

Validation for this milestone:

- [ ] `test_catalog_graph_never_emits_live_confirmed_without_event_graph`
- [ ] No catalog graph test should require live runtime observations.

Deferred runtime/event tests:

- [ ] `test_runtime_event_anchors_to_catalog_nodes`
- [ ] `test_grm_toggle_event_does_not_mutate_catalog_zone`

## 11. MissingTarget And UnknownEvidence Policy

Goal:

- Distinguish unavailable addressable targets from unknown semantics.

`MissingTarget` means an addressable target was referenced, but the resolver
could not produce an available graph target.

Use `UnknownEvidence` or unknown descriptors for field/semantic meaning that is
not yet understood.

Recommended `MissingTarget` fields:

```text
targetStableId
targetKind:
  asset | resource_record | scene_object | scene_zone | waypoint |
  script_instruction | background_resource | sample | text | video
resolutionState:
  outside_table
  empty_archive_slot
  undecoded_slot
  unresolved_name
  ambiguous_generic_resolver
  owner_missing
  outside_script
  not_loaded_archive
  backend_unresolved
  intentionally_deferred_target
rawReference
ownerNodeId
sourceEvidenceId
resolverKind
candidateTargets[]
absenceEvidenceStatus
missingReason
```

Policy:

- Outside-table ids become `MissingTarget` with
  `resolutionState=outside_table`.
- Empty HQR slots become `MissingTarget` with
  `resolutionState=empty_archive_slot`.
- Undecoded slots become `MissingTarget` only when an addressable target exists;
  otherwise use `UnknownEvidence`.
- Unresolved names preserve raw name and resolver source.
- Ambiguous generic resolver outputs preserve candidates and must never guess.
- Outside-script targets use `targetKind=script_instruction` with source offset.
- Intentionally deferred semantics are `UnknownEvidence` unless they name a
  target.
- Missing `COMPATIBLE_WITH` means operation not eligible.
- Missing usage edges mean only no known decoded/source-backed usage, not
  unused.

Validation:

- [ ] `test_missing_target_taxonomy`
- [ ] `test_multiple_occurrences_share_missing_target_but_keep_distinct_edges`
- [ ] `test_empty_sample_slot_is_not_decode_failure`

## 12. Query And Search UX

Goal:

- Let users search graph facts, not just assets, while keeping graph logic in
  the backend.

Recommended backend query surfaces:

```text
catalog-graph search
catalog-graph explain
catalog-graph edges
catalog-graph usages
catalog-graph relationship
catalog-graph scene-object
catalog-graph zone
catalog-graph waypoint
catalog-graph script-instruction
catalog-graph missing-targets
catalog-graph subgraph
catalog-graph prove
catalog-graph operation
catalog-graph selection
```

Recommended search request shape:

```json
{
  "q": "LM_SET_GRM",
  "nodeTypes": ["SceneZone", "ScriptInstruction", "Asset", "MissingTarget"],
  "edgeTypes": ["APPLIES_GRM_FRAGMENT", "CONTROLS_ZONE", "USES_RESOURCE"],
  "proofScopes": ["classic_source_rule", "script_structure"],
  "evidenceStatuses": ["source_backed", "unknown"],
  "targetAvailability": "available|missing|both",
  "owner": "SCENE.HQR:126",
  "includeEdges": true,
  "limit": 50,
  "cursor": null
}
```

Search results should return:

```text
nodeId / edgeId
stableId
label
nodeType / edgeType
proofScope
evidenceStatus
sourceRule
sourceField
indexRule
sourceEvidenceId
targetAvailable
snippet
selectionProjection
```

Actions:

- [ ] Add proof/evidence filters to backend search/query responses.
- [ ] Return edge results as first-class selectable rows.
- [ ] Add missing-target query surface.
- [ ] Add subgraph export rooted at selected node or edge.
- [ ] Frontend renders filters/results only; it must not compute eligibility,
      exportability, workspace, route, compatibility, or relationship truth.

Validation:

- [ ] `test_search_filters_proof_and_evidence_status`
- [ ] `test_search_returns_edges_and_nodes`
- [ ] `test_subgraph_export_includes_selected_edge_identity`

## 13. Export And Port Contract Boundary

Goal:

- Stabilize graph-selected export context before adding full port-contract
  nodes.

Stable port-facing contract data should include:

- graph node id / edge id;
- source archive/index/hash;
- decoded geometry, animation, resource facts;
- scene object initial state;
- File3D resolver evidence;
- zone, waypoint, and script structural facts;
- source-backed execution contracts;
- `MissingTarget` / `UnknownEvidence` records;
- export manifest ids;
- no-guessed-live-state policy.

Viewer-only data should stay out of stable port contracts:

- `workspaceSuggestion`;
- `inspectorRoute`;
- preview actions;
- canvas/UI facet state;
- `searchText`;
- render-only preview screenshots unless exported as evidence artifacts;
- frontend local selection fallbacks.

Actions:

- [ ] Make export manifests launched from relationship rows carry selected
      graph edge id, source/target node ids, and proof/evidence fields.
- [ ] Clarify `query_export_context(graph, stable_id, proof_scope)`: either
      rename the argument if it is a proof statement or actually filter
      relationship evidence by proof scope.
- [ ] Keep promotion packet links graph-derived and extend stale reverse-usage
      tests to zone/waypoint/script evidence.
- [ ] Defer `PortContract` graph nodes until selected node/edge export context
      is stable.

Validation:

- [ ] `test_export_context_proof_scope_not_ambiguous`
- [ ] `test_export_from_relationship_row_records_selected_edge_id`
- [ ] `test_promotion_packet_links_use_only_graph_scene_evidence`

## 14. Documentation Work

Actions:

- [ ] Update `docs/catalog-graph-model.md` after `SceneZone` and `Waypoint`
      promotion decisions.
- [ ] Document the new `script_structure` proof scope if added.
- [ ] Document the `MissingTarget` taxonomy and `UnknownEvidence` distinction.
- [ ] Document that root-level `viewer.py` and `lba_hqr.py` remain explicit
      compatibility-wrapper exceptions, not a pattern to extend.
- [ ] Keep `docs/plans.md` and `TASK.md` as current planning authority when
      older architecture summaries disagree.
- [ ] Add validation notes and screenshots under `docs/` for any visible UI
      changes validated with agent-browser.

## 15. Known Risks

- Edge occurrence identity is the highest-risk gap. Without it, repeated script
  references, relationship-row exports, and frontend joins can become subtly
  wrong.
- `query_export_context` currently has ambiguous naming/semantics around
  `proof_scope`.
- Promoting all script instructions may add many graph nodes. Start with
  selectable/queryable instruction occurrences and measure full-catalog graph
  size.
- Runtime proof source is not defined yet. Do not introduce `live_confirmed`
  without runtime trace, emulator hook, port fixture, or deterministic
  simulation provenance.
- Confirmed empty archive slots are stronger than unknown unresolved names, but
  both still target unavailable evidence. Keep `targetAvailable=false`,
  `resolutionState`, and `absenceEvidenceStatus` distinct.

## 16. Suggested Milestone Exit Criteria

M17 is complete when:

- selectable graph edges have stable occurrence identity;
- relationship-row selection and export use edge ids;
- `SceneZone` and `Waypoint` nodes are graph materialized and queryable;
- the first limited `ScriptInstruction` relationships are graph-backed where
  selectable/queryable;
- `MissingTarget` taxonomy is implemented for new scene mechanics links;
- frontend graph-migrated selections fail closed instead of rediscovering
  authority locally;
- tests cover graph promotion, edge identity, missing-target taxonomy, query
  filters, and export context;
- agent-browser validation covers any visible UI changes.

## 17. Partial Implementation Notes

Implemented and validated as a focused slice on 2026-05-10. The older
unchecked checklist items above are historical planning detail; use this
section, the validation notes, and the current tests as the M17 completion
record:

- Stable selectable edge occurrence identity is now part of graph edges and is
  projected through usage records, scene-object relationship projections,
  selection links, subgraph export, and export context.
- Scene usage strip matching now uses graph edge ids and fails closed when an
  edge-linked usage record is missing.
- `SceneZone`, `Waypoint`, `ScriptBlock`, `ScriptInstruction`,
  `PatchRecord`, and `RuntimeStateField` are materialized from the currently
  catalog-projected scene mechanics evidence.
- Zone text/camera/GRM and runtime-contract evidence, waypoint movement and
  script references, structural control-flow links, runtime-mutable fields, and
  patch instruction/field links are graph-backed where decoded evidence
  supports them.
- `MissingTarget` records now carry target kind, resolution state, resolver,
  owner, raw reference, absence status, and missing reason fields.
- Backend graph search returns selectable node and edge results with
  proof/evidence filters; missing-target and edge-rooted subgraph query
  surfaces exist.
- `query_export_context` now distinguishes the export proof statement from an
  optional graph relationship proof filter and reports selected edge ids.
- `docs/catalog-graph-model.md` documents the promoted node/edge vocabulary,
  `script_structure`, edge occurrence identity, and missing-target taxonomy.
- Agent-browser validation notes and screenshot were added under `docs/`.

Validation completed:

```powershell
uv run python -m unittest discover -s tests
npm run build
```

Agent-browser validation:

- Opened `http://127.0.0.1:5173`.
- Indexed the local LBA2 asset root.
- Selected graph-linked `BODY.HQR:29`.
- Confirmed the Scene Usages strip renders graph-backed relationship rows.
- Clicked a usage row and confirmed active usage selection is keyed by the
  graph edge id.

Critical-sparring gaps addressed in the continuation pass:

- Scene mechanics graph materialization now consumes canonical uncapped decoded
  `objects`, `zones`, `tracks`, and `patches` arrays. `sampled_*` fields remain
  bounded preview/UI data and are not graph authority.
- Relationship-row export is wired through the real `/api/catalog/export` path
  for edge-backed model exports. The selected graph edge id is validated against
  the exported asset and recorded in the export manifest evidence.
- Frontend usage-strip clicks now create first-class `graph_edge` selections
  with `stableId == edgeId`, sourced from backend edge projections in
  `graph.selectionByStableId` instead of locally reconstructing export
  authority.
- Resource-record selection no longer inherits parent resource authority; it
  consumes backend `ResourceRecord` node selection projections by stable id.
- `CHANGES_CUBE_TO` and `DECLARES_EXECUTION_CONTRACT` are graph-backed where
  decoded/source-backed evidence supports them. `TRACK_LABEL_TARGETS` remains
  intentionally out of scope until decoded evidence maps track labels to
  waypoint records.
- Dedicated CLI/backend query surfaces now exist for `zone`, `waypoint`,
  `script-instruction`, `selection`, and animation `operation`.
- Zone/waypoint/patch rows in the scene local table are selectable graph-node
  selections and show graph-backed inspector evidence.

Validation added in the continuation pass:

- `test_scene_mechanics_graph_uses_full_decoded_lists_not_samples`
- `test_scene_mechanics_graph_requires_canonical_decoded_lists`
- `test_export_from_relationship_row_records_selected_edge_id`
- `test_resource_record_selection_comes_from_graph_node`
- query-surface tests for zone, waypoint, script instruction, selection, and
  operation
- existing full test discovery: `uv run python -m unittest discover -s tests`
  passed with 179 tests
- frontend build: `npm run build` passed with the existing Vite chunk-size
  warning
- final agent-browser gap check confirmed graph-edge usage selection,
  backend-projected edge export action visibility, and graph-projected
  resource-record selection; see
  `docs/validation-m17-scene-mechanics-graph-2026-05-10.md`

Deferred beyond this partial slice:

- A separate runtime/event graph for live observations and runtime resolver
  selections.
- Full `PortContract` and `EvidenceSource` graph nodes.
- Runtime/event graph evidence for live observations.
- `TRACK_LABEL_TARGETS` until decoded track-label-to-waypoint evidence exists.

## 17.9. M17.9 - Catalog Payload Boundary And Query Surface

Immediate next milestone before M18:

- Status: completed on 2026-05-15. Validation record:
  `docs/validation-m17-9-catalog-payload-boundary-2026-05-15.md`.
- Fix the full-retail startup scaling failure before building the Model Port
  Asset Contract.
- Treat this as a boundary correction for the Remaster Evidence Pipeline, not
  as a cosmetic performance pass.

Problem statement:

- Full retail asset-root startup can decode successfully while the frontend
  still shows no assets because `/catalog.json` serializes the backend's
  internal catalog plus full graph projections.
- On 2026-05-15, `D:\LBA2_cdrom\LBA2` decoded in about 55s, but
  `/catalog.json` was 2,156,373,462 bytes.
- The architectural mistake is that `server_state.catalog` is both the
  backend's canonical decoded working set and the browser startup API payload.

Decision:

- The canonical HTTP catalog must become a compact Explorer index with hard
  payload budgets.
- Backend Python still owns the full decoded catalog and catalog graph in
  memory.
- Graph truth must be exposed through bounded query/detail/selection/export
  context endpoints, not embedded wholesale in the startup catalog.
- Full graph export remains an explicit offline artifact, not browser startup
  state.
- Frontend code must not rediscover graph relationships, exportability, proof
  status, or selection authority from compact catalog fields.

Required API direction:

- `GET /catalog.json` returns only a compact catalog shell: summary, HQR
  summaries, compact asset rows or first page, source identity, and capability
  hints. It must not include full `graph`, deep scene/script `stats`, or
  all graph selections.
- `POST /api/catalog/build` returns the same compact shape as `/catalog.json`.
- `POST /api/catalog/search` returns bounded compact Explorer rows with
  `q`, `kind`, `offset`, and `limit`.
- `POST /api/catalog/asset` returns full detail for one asset id.
- `POST /api/catalog-graph/selection` returns one backend-owned graph selection
  projection by asset/node/edge stable id.
- `POST /api/catalog-graph/edges` and `/api/catalog-graph/usages` return
  bounded graph relationship rows.
- `POST /api/catalog-graph/compatible` returns compact compatible-animation
  summaries for one model.
- `/api/catalog/load` remains the workspace payload endpoint for opening a
  selected asset.

Implementation sequencing constraints:

- Do not simply add `/catalog-compact.json` beside the current full
  `/catalog.json`; keep one canonical current startup catalog.
- Introduce an explicit response DTO/builder for the compact catalog. Do not
  serialize `server_state.catalog` directly as public API state.
- Stop mutating the canonical catalog with full graph projections during
  startup. Add an `ensure_catalog_graph()`-style boundary that can build/cache
  graph state without writing `catalog["graph"]` into the startup payload.
- Move frontend selection to explicit async hydration: fetch asset detail and
  graph selection before committing `selectionStore.set()`.
- Move Explorer search/paging server-side or through a bounded compact search
  document.
- Preserve backend graph authority. Compact catalog fields are display/search
  hints, not proof of relationships, exportability, or selection authority.

Tempting non-solutions:

- gzip, streaming JSON, larger browser timeouts, or chunked `/catalog.json`;
  these move the giant payload faster but still force browser parse/heap
  failure.
- Sampling/truncating canonical graph evidence to fit the startup payload.
- Moving graph truth into frontend inference from compact fields.
- Introducing a database before proving memory/query requirements demand one.
- Letting M18 contracts depend on Explorer payload shape instead of backend
  graph/detail APIs.

Validation:

- Add payload-budget tests for startup catalog, search results, asset detail,
  graph selection, usage/edge queries, and export context.
- Assert `/catalog.json` and `/api/catalog/build` exclude
  `graph.selectionByAssetId`, `graph.selectionByStableId`, and
  `graph.sceneObjectRelationshipsByStableId`.
- Assert compacting the HTTP payload does not remove canonical graph evidence
  needed by graph queries, exports, entity workflows, or future contracts.
- Add an E2E UI validation: startup renders compact Explorer rows, selecting one
  exportable model hydrates asset detail and graph selection, then Active
  Selection, Inspector, compatible-animation summary, and Export still work.

M17.9 is complete when:

- Full retail startup no longer requires the browser to fetch or parse a
  multi-GB catalog payload.
- Graph-migrated selections still fail closed when detail/projection endpoints
  are unavailable.
- Existing export/entity/graph evidence paths continue to use backend graph
  authority.
- M18 can build `Model Port Asset Contract v0` from backend detail/graph
  context rather than from Explorer startup state.

## 18. M18 - Model Port Asset Contract v0

Goal:

- Turn the viewer's model evidence into the first stable port-facing contract
  slice.
- Prove the contract boundary with a downstream consumer harness before building
  creative tooling such as Blender import.

Domain terms:

- **Remaster Evidence Pipeline**: the project role targeted by this milestone.
- **Model Port Asset Contract**: the stable contract artifact emitted for
  `BODY.HQR` and `OBJFIX.HQR` model assets.
- **Contract Consumer Harness**: the first downstream consumer; it lives in this
  repository but must not import viewer parser, server, or catalog-graph
  internals.
- **Blender Remaster Adapter**: deferred creative consumer that depends on the
  contract after the harness proves it.

Hard constraints:

- Keep evidence exports and contracts separate. OBJ/PNG/manifest exports are
  linked artifacts, not the contract body.
- Contract data must come from backend-owned decoded structures and catalog
  graph context, not frontend selection state.
- The contract must preserve proof scopes, evidence statuses, missing targets,
  unknowns, and explicit non-claims.
- The consumer harness must fail if the contract is insufficient and must not
  repair gaps by calling viewer internals.

### M18.1 - Contract Producer

Deliverable:

- Add `lba2-lm2-viewer port-contract model ...`.
- Emit `model_port_asset_contract.v0` JSON for one `BODY.HQR` or `OBJFIX.HQR`
  model asset.
- Reject non-model assets and unsupported schema/version requests.

Required contract sections:

- `schema_version`
- `contract_id`
- `source`
- `graph_identity`
- `geometry`
- `render`
- `materials`
- `animation_compatibility`
- `scene_usage_context`
- `export_artifacts`
- `missing_targets`
- `unknowns`
- `non_claims`

Required `non_claims`:

- The contract does not prove final in-game renderer parity.
- The contract does not prove live runtime state.
- The contract does not prove collision semantics beyond explicitly included
  decoded/source-backed facts.
- The contract does not prove attachment points unless they are decoded and
  explicitly carried later.
- The contract does not prove animation compatibility except through graph
  `COMPATIBLE_WITH` evidence.
- The contract does not include remastered art decisions.
- The contract does not promise Blender import fidelity beyond linked evidence
  artifacts and consumer validation.

### M18.2 - Graph Context

Deliverable:

- Include graph node id, stable asset id, selected edge ids where applicable,
  incoming scene usage edges, File3D resolver evidence, compatible animation
  edges, proof scopes, evidence statuses, source rules, source fields, and index
  rules.
- Preserve missing or unavailable targets as explicit contract records.
- Do not emit `live_confirmed`; runtime proof belongs to a future runtime/event
  graph.

### M18.3 - Evidence Artifact Links

Deliverable:

- Link existing model export probe outputs by manifest path and artifact hashes
  when the contract command is asked to produce or attach evidence artifacts.
- Keep OBJ, MTL, PNG, and probe manifest payloads outside the contract body.
- Record artifact generation options and git/tool provenance.

### M18.4 - Contract Consumer Harness

Deliverable:

- Add a minimal downstream consumer that reads `model_port_asset_contract.v0`
  without importing viewer internals.
- Validate schema/version and reject unknown fields.
- Resolve linked evidence artifacts from contract paths.
- Reconstruct a deterministic render/import-facing model summary from contract
  data.
- Write `consumer_report.json` with the facts a port/remaster consumer can rely
  on and the explicit non-claims it must honor.

### M18.5 - E2E Gate

Validation:

- Produce a model contract from a synthetic HQR fixture.
- Consume that contract with the harness.
- Assert the consumer report proves the contract boundary without calling
  `viewer.build_catalog()`, parser internals, server code, or catalog graph
  builder code.
- Run targeted contract tests plus full test discovery before considering M18
  complete.

Suggested tests:

- `test_model_port_contract_emits_graph_backed_context`
- `test_model_port_contract_links_export_artifacts_without_embedding_payloads`
- `test_contract_consumer_harness_rejects_unknown_fields`
- `test_contract_consumer_harness_uses_no_viewer_internals`
- `test_model_port_contract_e2e_producer_to_consumer_report`

### M18.6 - Blender Remaster Adapter Spike

Deferred until the harness passes:

- Design a Blender adapter that consumes the same contract and linked evidence
  artifacts.
- Keep Blender out of the first contract-completeness proof so failures remain
  attributable to the contract boundary.

## 19. Pipeline Roadmap After M18

Roadmap principle:

- Build contract slices around consumer obligations, not around parser novelty.
- Static asset contracts come before scene runtime contracts.
- Runtime/event proof comes before any contract emits live behavior claims.
- Blender follows the contract harness; it is the first creative consumer, not
  the first proof of contract completeness.

### M19 - Sprite, Image, Audio, Text, And Video Evidence Contracts

Goal:

- Promote already exportable resource families into stable evidence contracts.

Candidate contract slices:

- sprite frame and ANIM3DS range contracts;
- indexed image contracts for `RESS.HQR`, `SCREEN.HQR`, and `HOLOMAP.HQR`;
- sample audio contracts;
- text payload contracts;
- Smacker container passthrough contracts.

Non-goals:

- no live runtime state;
- no final remastered art decisions;
- no codec/frame decode claim for Smacker unless implemented and validated.

### M20 - Scene Background Contract

Goal:

- Promote background grid/composition evidence into a stable contract slice.

Scope:

- `LBA_BKG.HQR` GRI/BLL/BRK/GRM evidence;
- scene background cube links;
- exported base and GRM-on variants;
- preview artifact links with explicit renderer-parity non-claims.

Non-goals:

- no final object/decor overdraw parity claim;
- no live dynamic draw-source ordering claim beyond source-backed requirements.

### M21 - Runtime/Event Evidence Graph

Goal:

- Add the separate evidence layer needed for live observations, deterministic
  simulation provenance, runtime resolver events, and eventual
  `live_confirmed` facts.

Scope:

- event anchors back to catalog graph nodes and edges;
- runtime resolver requests and outputs;
- emulator/runtime trace observations when available;
- deterministic simulation fixtures when trustworthy;
- explicit distinction between decoded initial state, source-backed rule, and
  observed runtime event.

Non-goals:

- do not retrofit live evidence into the catalog graph;
- do not emit `live_confirmed` without runtime/event provenance.

### M22 - Scene Runtime Contract

Goal:

- Promote scene object, zone, script, patch, and dynamic draw-source obligations
  into port-facing contracts after runtime/event evidence exists.

Scope:

- decoded initial scene state;
- source-backed object/zone/script contracts;
- graph-backed missing targets and unknowns;
- runtime/event proof where available;
- explicit render, behavior, and live-state non-claims where proof is absent.

Non-goals:

- no broad interpreter hidden inside the contract producer;
- no guessed final renderer parity.

### M23 - Blender Remaster Adapter

Goal:

- Build the first creative consumer for actual remastering workflows.

Scope:

- consume `Model Port Asset Contract` and linked evidence artifacts first;
- import geometry/material evidence into Blender;
- preserve contract provenance in Blender-side metadata where practical;
- report adapter gaps separately from contract gaps.

Non-goals:

- Blender is not the schema-completeness oracle;
- Blender output is not automatically a final shippable asset package.
