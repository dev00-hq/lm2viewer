# Catalog Graph Investigation

## Fact Base

The live HTTP `/catalog.json` server was not reliable evidence during the
investigation because the running listener reported `no files selected`. The
catalog was built directly through `viewer.build_catalog(DEFAULT_ASSET_ROOT)`.

Current catalog facts from the default asset root:

| Item | Count |
| --- | ---: |
| HQR files | 15 |
| assets | 22,659 |
| models | 573 |
| decoded animations | 2,082 |
| raw animations | 0 |
| sprite assets | 720 |
| sprite frames | 719 |
| sprite metadata assets | 1 |
| scene assets | 222 |
| resource assets | 19,062 |
| reverse scene usage refs | 28,128 |
| assets with reverse usage | 2,361 |

Graph probe facts from `catalog-graph probe --ids BODY.HQR:2 BODY.HQR:29 SCENE.HQR:2 --json`:

| Item | Count |
| --- | ---: |
| graph nodes | 74,850 |
| graph edges | 109,550 |
| indexed assets | 22,659 |
| scene-usage targets | 2,361 |

## Subagent Findings

### Catalog Payload Audit

The payload already carries many relationship facts, but they are embedded in
asset fields. Important embedded fields are `source`, `scene_usages`,
`animation_metadata.compatible_body_ids`, scene object `links`, script
`asset_links`, sprite runtime metadata, ANIM3DS range entries, and resource
subrecords.

The most important missing surface is explicit relationship identity. Current
`scene_usages` is a reverse index optimized for asset pages; it hides unresolved
targets, edge direction, edge-level proof scope, and edge-level evidence status.

The Explorer grouping prototype is mostly current: 22,659 assets, 573 models,
2,082 animations, 720 sprites, 222 scenes, 19,062 resources, and 28,128 usage
refs. Ambiguities: `720 sprites` includes one metadata asset, and `BODY.HQR:2`
having no known scene usages is not proof that the model is never used at
runtime.

### Viewer App Model Audit

Global selection is already broader than assets. Existing non-asset selections
include `scene_usage`, `runtime_resolution`, `sprite_frame`,
`animation_sample`, `model_surface`, `resource_record`, `evidence_artifact`,
`scene_object`, `runtime_sprite_state`, `file3d_resolution`,
`anim3ds_range_state`, `render_contract`, and `palette_context`.

Flat-list assumptions remain dominant. `CatalogUi` filters `catalog.assets`
directly, search flattens asset-local text, `findCatalogAsset` is a linear scan,
compatibility scans assets on selected-model update, and several paths recover
the owner asset by splitting `stableId` at `#`. Those are implementation risks
for graph projection work.

Required indexes are `assetById`, `nodesById`, `edgesById`,
`incomingByNodeId`, `outgoingByNodeId`, `sceneObjectsBySceneAssetId`,
`sceneUsagesByAssetId`, `spritesByRange`,
`compatibleAnimationsByModelId`, `compatibleModelsByAnimationId`,
`resourcesBySemanticLayout`, and search text indexes.

### Classic Runtime Source Audit

The strongest correction is that `GenBody` and `GenAnim` are resolver inputs,
not direct asset ids. Scene object state resolves through the object's File3D
record before reaching `BODY.HQR` or `ANIM.HQR`. Direct `GenBody -> BODY.HQR`
edges would encode a false shortcut.

Source-backed node candidates are `Scene`, `SceneObject`, `File3DRecord`,
body/animation assets, sprite assets/frames/ranges, and `ScriptReference`.
Script references must remain distinct from scene initial-state usage.

ANIM3DS timing is partly scene/runtime state, not derivable from the range table
alone. Missing targets and unresolved `SearchBody`/`SearchAnim` results must be
explicit unknown evidence, not absent edges.

### IDA/Legacy Source Audit

IDA/legacy evidence confirms that `File3DRecord` is a first-class graph concept.
It also confirms that `body id` is overloaded: viewer `compatible_body_ids`
refer to resolved `BODY.HQR` ids, while legacy/IDA "body id" often means
generic `GenBody`. The model uses "generic body slot" for `GenBody` and "body
asset" for `BODY.HQR`.

`Actor` can be a UI alias, but canonical low-level naming remains
`SceneObject`. `Zone` and `Waypoint` should become nodes when scripts and scene
navigation are promoted beyond the first slice.

### Query Surface Audit

Existing `export`, `contract`, and `animation` subcommands are not graph
queries. The required surface is a new `catalog-graph` command with structured
JSON, deterministic ordering, proof/evidence filtering, subgraph export, and no
wrapping of `/catalog.json`.

Backend memory is the correct first owner because CLI and port tooling need
headless access. Frontend memory can consume graph JSON later. A database is not
justified by current evidence.

## Rejected Assumptions

- Rejected: Explorer grouping can drive schema. Reason: Explorer is one
  projection; Inspector, exports, CLI, agents, and port checks need the same
  semantics.
- Rejected: `scene_usages` is already the graph. Reason: it is a reverse index
  and omits unresolved targets and edge metadata.
- Rejected: `GenBody` maps directly to `BODY.HQR:<GenBody>`. Reason: classic
  source resolves through File3D.
- Rejected: `GenAnim` maps directly to `ANIM.HQR:<GenAnim>`. Reason: File3D
  maps generic animation slots to HQR animation entries.
- Rejected: compatibility is one relationship. Reason: File3D allow-list and
  bone-count-only compatibility have different proof and evidence strength.
- Rejected: ANIM3DS range table owns timing. Reason: range table defines frames;
  scene object/runtime state carries FPS/range playback state.
- Rejected: empty incoming usage means asset is unused. Reason: it only means no
  known decoded/reverse usage exists.
- Rejected: database-first design. Reason: the need is graph semantics and
  indexes; persistence has not been proven necessary.

## Validation Results

Implemented and run:

- `python -m pytest tests/test_catalog_graph.py -q`: 10 passed after graph export/import, missing-target, script/direct distinction, runtime sprite, and server projection coverage were added.
- `cd frontend; npm run build`: passed after moving animation compatibility filtering to the backend graph projection.
- `python -m lba2_lm2_viewer catalog-graph ... probe --ids BODY.HQR:2 BODY.HQR:29 SCENE.HQR:2 --json`: built 74,850 nodes and 109,550 edges.
- `python -m lba2_lm2_viewer catalog-graph ... scene-object SCENE.HQR:2 2 --json`: emitted `HAS_FILE3D_RECORD`, `USES_AS_BODY`, and `USES_AS_ANIMATION` with `selectionStableId: SCENE.HQR:2#object:2`.
- `python -m lba2_lm2_viewer catalog-graph ... prove BODY.HQR:2 ANIM.HQR:2 --json`: returned compatible with `compatibilityReason: file3d_allowlist`.
- `python -m lba2_lm2_viewer catalog-graph ... usages BODY.HQR:29 --proof-scope scene_object_state --evidence-status source_backed --json`: returned the expected large incoming body-usage edge set.
- `python -m lba2_lm2_viewer catalog-graph ... edges BODY.HQR:2 --direction incoming --proof-scope classic_source_rule --evidence-status source_backed --json`: returned source-backed File3D allow-list compatibility edges.

## Model Revisions During Validation

- Added `File3DRecord` after source audits showed generic body/animation slots
  must not point straight to HQR assets.
- Added `RESOLVES_TO` to preserve File3D resolver evidence separately from
  scene object `USES_AS_BODY` and `USES_AS_ANIMATION`.
- Added query filters for `proofScope` and `evidenceStatus`.
- Kept `SceneObject -> Asset` usage edges for consumer ergonomics, but backed
  them with File3D resolver nodes and source fields.
- Revised graph construction so available scene-object usage edges are
  materialized directly from `SceneStats.reconnaissance.sampled_objects[].links`.
  `CatalogAsset.scene_usages[]` is now legacy reverse enrichment only; the
  canonical graph build does not index it as relationship authority.
- Removed the stale reverse-usage materializer helper from `catalog_graph.py`
  after validation showed it was no longer part of the canonical build path.
- Added `tests/test_catalog_graph.py::test_scene_object_usage_does_not_depend_on_reverse_scene_usages`
  to remove every `scene_usages` field from a synthetic catalog and still assert
  `SCENE.HQR:2#object:2 -> BODY.HQR:29` and `ANIM.HQR:220`.
- Added export regression coverage that injects stale `asset.scene_usages` and
  asserts promotion packet links remain empty unless scene evidence is present
  in the canonical graph.
- Added standalone export-probe regression coverage that injects stale reverse
  usage and asserts exported evidence counts and promotion packet ids stay
  graph-derived.

## Unresolved Questions

- Missing text/sample/video targets are still better represented by dedicated
  missing-target edges than by metadata arrays. The first slice supports
  `MissingTarget`, but broad missing-target materialization is not complete.
- `SceneZone` and `Waypoint` should be promoted when script/local navigation
  queries become first-class.
- Export manifests currently carry graph export context for asset ids. Later
  export work should carry the selected graph node/edge id when exports are
  launched from relationship rows rather than whole assets.
- Frontend selection no longer uses `stableId.split('#')` as app decision
  authority. Owner/highlight decisions use graph selection evidence, explicit
  selection evidence payloads, or typed facets.
- Graph-projected frontend selections now fail closed when an `inspectorRoute`
  is missing or unknown rather than falling back to local `asset.kind` or
  `semantic_layout` routing.
- Scene Inspector graph-modeled relationship rows now read
  `graph.sceneObjectRelationshipsByStableId`; local script/control-flow rows
  remain decoded scene facts until graph vocabulary covers opcode-level detail.
- Graph export/import now supports repeated CLI calls through
  `catalog-graph build --output temp/catalog-graph.json` and
  `--graph-json temp/catalog-graph.json`. Freshness is explicitly warned rather
  than silently trusted.
- The validation implementation has both a package CLI
  (`python -m lba2_lm2_viewer catalog-graph ...`) and a script entrypoint
  (`python scripts/catalog_graph_probe.py ...`) that can build from an asset
  root or load the same exported graph JSON.
