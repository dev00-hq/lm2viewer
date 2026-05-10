# Task: Complete the Graph-Backed Evidence Workbench

## 0. Metadata

- Owner: project maintainer
- Created: 2026-05-07
- Consolidated: 2026-05-10
- Source files consolidated: historical `TASK.md`, `TASK_GPT.md`, audit findings,
  and agent-browser validation notes
- Current state: Complete
- Current milestone: M16 - completion hardening

## 1. North Star

The app is becoming an evidence graph workbench, not a collection of decoded
asset panels.

Every visible thing should answer:

1. What is this?
   - A canonical catalog/graph identity, not a guessed archive/index label.
2. Why do we believe that?
   - A graph-backed proof path to source evidence: scene object state, File3D
     resolution, script reference, runtime table, palette/source payload, export
     context, or explicit negative/missing-target evidence.
3. What can I safely do with it?
   - Inspect, navigate, export, compare, or promote it only when the backend
     graph and server operation contract agree that the action is valid.

The durable contract is:

```text
catalog graph -> selection projection -> inspector route -> export/proof context
```

The frontend should render backend graph projections and local visual state. It
must not become a second source of graph relationship, exportability, routing,
workspace, or owner truth.

## 2. Mission

Finish and stabilize the graph-backed app decision migration so selection,
routing, Inspector, workspace, export, Explorer/search summaries, relationship
views, and validation evidence use the backend catalog graph as their canonical
authority.

The original milestone slice is complete for animation compatibility,
model/resource asset selection, graph-backed Inspector routing, and one
scene-object relationship table view. The follow-up slice is also substantively
complete for export provenance, entity usage selection, Explorer/search
relationship summaries, graph export actions, derived selection export
inheritance, and removal of reverse `asset.scene_usages` as app-facing
authority.

This task remains open for completion hardening: tests, stale-state guards,
durable browser evidence, and final cleanup.

## 3. Hard Constraints

- One canonical current-state implementation. Do not add compatibility bridges,
  migration shims, fallback paths, old local-state support, or dual behavior
  unless the user explicitly asks for that support.
- Keep graph semantics in backend Python. Frontend TypeScript may consume graph
  projections but must not define graph relationship rules.
- Migration is replacement, not coexistence. When a decision moves to the
  graph, remove the superseded local authority in the same milestone unless a
  documented risk explicitly defers removal.
- The app remains a local evidence/falsification workbench for original LBA2
  assets and port compatibility, not an editor, converter, plugin host, remake
  workflow, or replacement-asset authoring tool.
- Do not commit retail assets, decoded retail payloads, real texture exports,
  real animation exports, or generated evidence bundles from retail assets.
- Use `agent-browser` for visible UI changes and record validation notes under
  `docs/`.
- If a surprising project trap appears, alert the developer and update
  `ISSUES.md`.

## 4. Canonical Authority Rules

If any visible app decision can disagree with the catalog graph, it is a bug.

Graph-backed authority owns:

- selection identity and stable parent/owner identity for migrated surfaces;
- workspace suggestion for migrated selections;
- Inspector route selection for catalog graph selections;
- exportability and export action availability;
- export provenance and graph usage context;
- scene/entity/resource relationship evidence for migrated rows;
- Explorer/search relationship summaries and graph relationship ranking;
- operation eligibility such as animation pose/playback compatibility.

Local decoded data may still own:

- byte decoding and payload parsing;
- renderer mechanics and preview payload shape;
- source-classification display;
- scene-local facts not yet graph-modeled, such as zones, waypoints, GRM links,
  patches, sampled object flags/positions, and opcode-level script rows;
- low-level loader branching needed to decode or draw a payload.

Rule of thumb: `asset.kind` and `stats.semantic_layout` may classify bytes for
loading/rendering, but they must not independently decide relationship truth,
exportability, graph route authority, or migrated selection ownership.

## 5. Completed Scope

The following surfaces are implemented as graph-backed or graph-consuming
decisions:

| Surface | Completed authority |
| --- | --- |
| Animation pose/playback eligibility | `catalog_graph.animation_operation_compatibility.v0` |
| Model/resource asset selection | `graph.selectionByAssetId` |
| Catalog asset workspace/route/export metadata | `catalog_graph.selection_projection.v0` |
| Scene object relationship table cells | `graph.sceneObjectRelationshipsByStableId` |
| Entity workflow usage selection | `query_asset_usage_records()` / graph `sceneUsagesByAssetId` |
| Entity linked visuals | `sceneObjectRelationshipsByStableId.visualLinks` |
| Export evidence context | `query_export_context()` |
| Standalone export probe metadata | graph export context |
| Frontend export gating | graph `exportCapability` / `exportActions` |
| Resource-record export actions | parent asset graph selection projection |
| Derived sprite/model/animation export actions | parent asset graph selection projection |
| Frontend scene usage strip | graph selection links |
| Inspector relationship sections | graph selection links and facets |
| Explorer/search relationship summaries | graph selection links and facets |
| Selection parent/owner identity | explicit selection evidence or typed facets |

Important completed decisions:

- Canonical graph builds no longer materialize reverse `asset.scene_usages`
  arrays into indexed usage edges.
- The stale reverse-usage materializer was removed from `catalog_graph.py`.
- Promotion packet links ignore stale reverse usage arrays and join through
  graph-derived scene usage records or explicit scene asset source identity.
- Frontend app-decision reads of `stableId.split('#')` were removed for
  migrated owner/highlight decisions.
- Graph-projected catalog selections fail closed when their graph
  `inspectorRoute` is missing or unknown instead of falling back to local
  `asset.kind + semantic_layout` route inference.
- `bkg_brick_graphic` resources are inspectable background resources but are not
  graph-exportable until `ViewerServer.export_catalog_asset()` has a matching
  export branch and test.
- `TASK_DS.md` is historical comparison material, not current scope.

## 6. Current Remaining Work

These completion-hardening items are complete.

### M16.1 - Lock graph/server exportability parity

Goal:

- Prevent graph export actions from drifting away from actual server export
  routes.

Actions:

- [x] Add a server-level negative test proving
  `ViewerServer.export_catalog_asset()` rejects a `bkg_brick_graphic` resource.
- [x] Add or document a parity test/table that compares graph-exportable
  semantic layouts with supported server export branches.
- [x] Keep `bkg_brick_graphic` inspectable via background route but
  non-exportable until the server route exists.

Result:

- `tests/test_export_probe.py` includes a server-level negative test for
  `bkg_brick_graphic`.
- Graph exportability remains aligned with actual
  `ViewerServer.export_catalog_asset()` branches; `bkg_brick_graphic` is
  inspectable through the background route and non-exportable.

Validation:

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe
```

### M16.2 - Close stale Inspector clearing edges

Goal:

- No active selection should leave stale Inspector details visible when the
  current selection cannot produce sections.

Actions:

- [x] Clear Inspector when `renderSelectionInspector()` cannot resolve the
  selected catalog asset.
- [x] Add a final clear fallback for selections that produce zero sections.
- [x] Harden unexpected graph projection kinds so they fail closed visibly.
- [x] Decide whether `palette_context` should inherit parent graph export
  capability or stay intentionally local/non-exportable.

Result:

- `renderSelectionInspector()` now clears the Inspector on unresolved assets,
  unsupported selection kinds, and zero-section results.
- Switching from a model UV selection to a non-model selection returns the
  Inspector to `Details` and hides stale UV/stat output.
- `palette_context` inherits parent graph export capability through the parent
  graph selection projection.

Validation:

```powershell
fnm use 24.15.0; npm run build
```

Add a focused frontend/browser regression if a test harness exists; otherwise
validate with agent-browser.

### M16.3 - Decide derived relationship evidence inheritance

Goal:

- Avoid a half-migrated state where derived selections inherit export actions
  but lose graph relationship evidence.

Actions:

- [x] Decide whether derived selections (`model_surface`, `sprite_frame`,
  `animation_sample`, `animation_pose`, `resource_record`) should inherit graph
  `links`, not only `graphNodeId` and `relationshipLinkCount`.
- [x] If yes, copy or project only the relationship evidence needed by Inspector
  and usage strips.
- [x] If no, document why derived selections are intentionally scoped to parent
  export action and local evidence.

Result:

- Derived selections inherit the parent graph relationship links needed by
  Inspector and usage strips, deduplicated with the parent asset link.

Validation:

- Inspector graph usage evidence for a graph-linked parent and a derived
  selection must either show relationship links or clearly explain that the
  derived selection delegates relationship evidence to its parent asset.

### M16.4 - Produce clean post-fix browser evidence

Goal:

- Replace the current weak browser artifact where a saved screenshot predates
  the stale UV/details fix.

Actions:

- [x] Start a fresh viewer from this checkout and confirm the listener is not
  stale.
- [x] Use agent-browser to select a graph-linked model surface and activate UV
  stats.
- [x] Select `LBA_BKG.HQR:197`.
- [x] Assert active selection is non-exportable.
- [x] Assert Inspector tab is `Details`.
- [x] Assert stale UV stats are cleared/hidden.
- [x] Capture a post-fix screenshot and record a validation note under `docs/`.

Evidence:

- `docs/validation-task-final-agent-browser-2026-05-10.md`
- `docs/validation-task-final-agent-browser-2026-05-10.png`

Validation note should include URL, asset root, selected ids, expected state,
observed state, screenshot path, and validation commands.

### M16.5 - Final cleanup

Actions:

- [x] Remove obsolete task files and stale references.
- [x] Keep historical validation artifact filenames if useful, but make clear
  that this `TASK.md` is the only current task source.
- [x] Run final validation:

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities
uv run python -m unittest discover -s tests
Set-Location frontend; fnm use 24.15.0; npm run build; Set-Location ..
git diff --check
```

- [x] Commit only after the current task state and validation evidence are
  coherent.

Result:

- `TASK_GPT.md` was removed during consolidation. `TASK_DS.md` remains
  discarded historical comparison material.
- Historical validation filenames are retained as evidence, while this
  `TASK.md` is the only current task authority.

## 7. Validation Strategy

Use the strongest practical validation available after each milestone.

Primary commands:

```powershell
uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities
uv run python -m unittest discover -s tests
fnm use 24.15.0; npm run build
git diff --check
```

Graph CLI probes:

```powershell
uv run python -m lba2_lm2_viewer catalog-graph --asset-root <root> build --output temp/catalog-graph.json
uv run python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json scene-object SCENE.HQR:2 2 --json
uv run python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json prove BODY.HQR:2 ANIM.HQR:2 --json
uv run python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json usages BODY.HQR:29 --proof-scope scene_object_state --evidence-status source_backed --json
```

Browser validation:

```powershell
uv run python -m lba2_lm2_viewer --host 127.0.0.1 --port <port> --no-browser
```

- Confirm the server process belongs to this checkout before trusting evidence.
- Use agent-browser for visible UI changes.
- Record validation under `docs/`.
- Do not treat DOM-only evidence as complete if a screenshot is required and
  screenshot capture fails; record the failure and rerun if the visual proof is
  material.

## 8. Known Validation Evidence

Recent validation reported:

- `uv run python -m unittest tests.test_catalog_graph tests.test_export_probe tests.test_entities`
  passed with 38 tests.
- `uv run python -m unittest discover -s tests` passed with 152 tests.
- `fnm use 24.15.0; npm run build` passed, with the existing Vite large chunk
  warning.
- `git diff --check` passed, with only CRLF normalization warnings.
- Agent-browser validated representative graph-backed flows for Explorer/search,
  graph usage strip, resource-record export action, `bkg_brick_graphic`
  non-exportability, and derived model-surface export inheritance.

Known evidence weakness:

- `docs/validation-task-gpt-final-fixes-2026-05-10.md` records that the saved
  screenshot for the stale UV/details case predates the final clear fix. The
  post-fix state was DOM-asserted, but a clean post-fix screenshot is still
  needed.

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation | Status |
| --- | ---: | ---: | --- | --- |
| Graph exportability drifts from server export routes. | Medium | High | Add server negative test and parity coverage. | Open |
| Inspector still shows stale details after a failed or zero-section selection. | Medium | Medium | Clear on unresolved assets and add final fallback. | Open |
| Derived selections inherit export action but not relationship evidence. | Medium | Medium | Decide and document inheritance semantics. | Open |
| Browser validation hits stale server or stale bundle. | Medium | Medium | Verify listener/process, rebuild, and record URL/asset root. | Open |
| Graph projection size grows too quickly. | Medium | Medium | Prefer narrow operation projections and measure before broadening. | Monitoring |
| Future agents treat all `semantic_layout` reads as migration bugs. | Medium | Medium | Keep decoder/render boundary documented here and in graph docs. | Monitoring |
| Script evidence expectations exceed graph vocabulary. | Medium | Medium | Keep opcode-level rows local until graph explicitly models instructions. | Monitoring |

## 10. Decision Log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-05-07 | Treat the catalog graph as the app decision substrate. | Reduces duplicate truth paths across UI, backend, exports, CLI, and port-facing probes. |
| 2026-05-07 | Keep detailed graph vocabulary in graph docs, not duplicated in design/task docs. | Avoids drift and lowers review burden. |
| 2026-05-07 | Use operation-specific graph projections instead of vague relationship labels for actions. | A relationship may prove evidence without proving an operation is allowed. |
| 2026-05-09 | Explorer/search is in scope. | Search ranking and summaries are app-facing decisions. |
| 2026-05-09 | Keep scene-local zones, waypoints, GRM links, patches, and opcode rows local. | They are decoded scene facts, not fully graph-modeled relationship authority. |
| 2026-05-09 | `TASK_DS.md` is discarded as current scope. | It is broader historical comparison material and can make completed work look incomplete. |
| 2026-05-10 | Consolidate `TASK_GPT.md` into `TASK.md` and remove the extra task file. | One canonical task file reduces ambiguity for future agents. |

## 11. Operating Rules

1. Treat this file as the canonical task source.
2. Work one milestone at a time.
3. Prefer code, tests, browser evidence, and graph docs over inherited plan
   claims.
4. After each milestone, update this file before continuing.
5. If implementation evidence contradicts the plan, revise the plan.
6. If a change affects hard constraints, public APIs, data compatibility,
   security, privacy, performance budgets, release process, or user-visible
   product scope, stop and ask for approval.
7. Use subagents for independent reading, critique, and validation planning;
   the main agent owns edits and integration.
8. Use agent-browser for visible UI validation.
9. Update `ISSUES.md` for surprising project traps.
10. Do not leave migrated decisions with both graph-backed and local authority
    paths.

## 12. Historical Notes

The old `TASK.md` M0-M6 milestone history and `TASK_GPT.md` follow-up history
were consolidated here on 2026-05-10. Historical validation notes under `docs/`
may keep their original filenames, including `validation-task-gpt-*`, but they
are artifacts, not task authority.
