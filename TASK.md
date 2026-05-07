# Task: Graph-Backed App Decisions

## 0. Metadata

- Owner: project maintainer
- Agent/session: Codex app-study team, 2026-05-07
- Created: 2026-05-07
- Last updated: 2026-05-07
- Current state: Designing
- Current milestone: M1 - Rewrite design contract around the graph spine

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

- [ ] `docs/design.md` names the catalog graph as the shared evidence substrate
  for selection, inspector sections, workspace suggestions, search/explorer
  projections, export provenance, CLI/agent queries, and future port joins.
- [ ] Each migrated app decision has one graph-backed authority path and no
  remaining local duplicate rule for that same decision.
- [ ] Animation compatibility and playback validation cannot disagree silently:
  either both use the same graph-backed operation contract, or the graph exposes
  distinct relationship/operation semantics with tests.
- [ ] Selection identity and workspace recommendation no longer depend on
  frontend stable-id string splitting for migrated selection types.
- [ ] Inspector/export routing for migrated types is driven by graph node/edge
  metadata or backend graph projections, not by parallel frontend
  `asset.kind + semantic_layout` inference.
- [ ] Scene/entity/resource relationship views for migrated types consume graph
  edges, including `MissingTarget`, `proofScope`, `evidenceStatus`,
  `sourceRule`, `sourceField`, and `indexRule` where relevant.
- [ ] Python tests pass for migrated backend graph/API behavior.
- [ ] Frontend build passes for migrated frontend behavior.
- [ ] Any visible browser behavior change has an `agent-browser` validation note
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

### Current duplicate or non-graph decision paths

- `server.py::animation_compatibility_error()` duplicates graph compatibility
  and still gates pose/sequence playback.
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
- Whether `docs/design.md` should include concrete graph node/edge vocabulary or
  defer deep vocabulary to `docs/catalog-graph-model.md` while naming authority
  boundaries.

### Assumptions

| Assumption | Confidence | How to validate |
| --- | ---: | --- |
| The graph is mature enough to become the app decision spine. | Medium | Migrate one operation contract and compare tests/browser behavior. |
| Selection/workspace recommendation should be migrated before broad Explorer redesign. | High | Code inspection shows stable-id parsing and workspace inference are cross-cutting risks. |
| Expanding backend graph projections is preferable to frontend re-derivation. | High | Project guidance rejects duplicate truth paths and frontend-only graph semantics. |
| A database is not needed for this migration yet. | Medium | Continue measuring graph build/query/projection cost after each milestone. |
| `docs/design.md` can be rewritten before implementation without changing user-visible behavior. | High | Documentation-only milestone; validate by review and consistency checks. |

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

Actions:

- [ ] Rewrite `docs/design.md` so the graph is the substrate behind selection,
  inspector sections, workspace suggestions, Explorer/search projections,
  export provenance, CLI/agent queries, and future port joins.
- [ ] State that Explorer is one projection of the graph, not the graph schema
  owner.
- [ ] Promote negative evidence, missing targets, direct usage vs script
  reference, File3D resolver evidence, and operation-specific eligibility into
  the design contract.
- [ ] Keep `docs/catalog-graph-model.md` as the deeper vocabulary reference;
  avoid duplicating every implementation detail in `design.md`.
- [ ] Update this `TASK.md` after the design rewrite with discoveries,
  decisions, changed assumptions, risks, validation results, and the next
  milestone state.

Validation:

- Review `docs/design.md` for these terms and boundaries:
  `catalog graph`, `graph projection`, `selection`, `workspace suggestion`,
  `proofScope`, `evidenceStatus`, `MissingTarget`, `ScriptReference`,
  `File3DRecord`, `export provenance`.
- `rg -n "graph|projection|proofScope|MissingTarget|ScriptReference|File3DRecord|workspace suggestion|export provenance" docs/design.md`
- No code validation required unless code changes are made.

Status: Not started

### M2 - Make animation operation compatibility graph-backed end to end

Goal:

- Remove the first high-risk duplicate truth path by making playback/pose
  eligibility agree with graph-backed compatibility semantics.

Actions:

- [ ] Define whether `COMPATIBLE_WITH` is sufficient for pose/playback or
  whether playback needs a distinct operation-specific projection such as
  `poseEligible`/`playbackEligible`.
- [ ] Add a focused backend test proving the graph result and pose/sequence
  validation cannot silently disagree for representative allow-list,
  bone-count-only, mismatch, and non-`BODY.HQR` cases.
- [ ] Replace or demote `server.py::animation_compatibility_error()` so it is no
  longer an independent authority for the migrated decision.
- [ ] Preserve current visible behavior unless the evidence requires a behavior
  change; if behavior must change, stop for approval first.
- [ ] Update graph docs and this `TASK.md` after validation.

Validation:

```powershell
python -m pytest tests/test_catalog_graph.py tests/test_animation_compatibility.py -q
python -m unittest discover -s tests -v
cd frontend
npm run build
```

Browser validation is required only if the visible animation dropdown,
selection, playback, labels, or errors change.

Status: Not started

### M3 - Define graph-backed selection/workspace projection

Goal:

- Create the smallest graph-backed projection needed for selection identity and
  workspace recommendation, before migrating Inspector or Explorer broadly.

Actions:

- [ ] Audit `frontend/src/selection.ts`, `frontend/src/main.ts`, and backend
  selection payloads for the minimum fields currently synthesized locally.
- [ ] Add or propose a backend graph projection/query that returns selected
  node identity, source, evidence status, links, unknowns, workspace suggestion,
  preview/export capabilities, and relevant edge evidence.
- [ ] Migrate one low-risk selection type to the projection and remove its
  superseded local authority.
- [ ] Validate selection stability with build/tests and an `agent-browser` flow
  if visible behavior changes.
- [ ] Update this `TASK.md` before planning the next milestone.

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

Status: Not started

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

## 11. Decision log

Record meaningful design decisions, especially reversals.

| Date | Decision | Why | Alternatives rejected |
| --- | --- | --- | --- |
| 2026-05-07 | Treat this as a living evolving-goal task, not a fixed workstream checklist. | The app migration is long-running and should adapt as graph/UI evidence appears. | Static all-project checklist with over-specified later milestones. |
| 2026-05-07 | Rewrite `docs/design.md` before the next implementation milestone. | The design contract currently lags the graph substrate and should guide future UI/API decisions. | Continue implementing graph consumers while design still frames Explorer/catalog as primary. |
| 2026-05-07 | Tackle animation operation compatibility before broad selection or Explorer migration. | It is the first graph-backed consumer and has a concrete duplicate backend authority path. | Start with Explorer tree/grouping or Inspector rewrite. |

## 12. Scope change log

Record any change to goalposts, success criteria, architecture, public behavior,
compatibility expectations, or validation requirements.

| Date | Change | Type | Reason | Requires user approval? | Approval status |
| --- | --- | --- | --- | --- | --- |
| 2026-05-07 | Replaced previous catalog-graph substrate slice task with this graph-backed app decision migration task. | Scope | The previous slice completed enough base graph work; the new task owns design rewrite plus implementation migration. | No | Not needed |

## 13. Risk register

| Risk | Likelihood | Impact | Mitigation | Status |
| --- | ---: | ---: | --- | --- |
| Graph relationship compatibility and playback operation eligibility diverge. | High | High | M2 defines/test one operation contract and removes duplicate backend authority. | Open |
| Frontend selection keeps parsing stable ids while graph node identity evolves. | High | High | M3 starts with selection/workspace projection before broad Inspector/Explorer work. | Open |
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

- Current state: Designing
- Current milestone: M1 - Rewrite design contract around the graph spine
- Last completed milestone: M0 - Define task and discover constraints
- Main discovery: The graph spine exists, but most app decisions still derive
  from local catalog/stats/stable-id rules.
- Current architecture direction: backend graph as evidence substrate, with
  operation-specific projections consumed by frontend/backend/export decisions.
- Open blocker: none
- Next action: rewrite `docs/design.md` to encode graph-backed authority and
  migration rules.
- Required approval: none for M1 documentation rewrite; approval may be needed
  later if operation semantics or user-visible behavior must change.

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
