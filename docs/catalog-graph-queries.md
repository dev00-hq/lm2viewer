# Catalog Graph Queries

The non-UI query surface is the `catalog-graph` CLI. It builds the same
in-memory graph as future UI/agent consumers and emits structured JSON. It does
not wrap `/catalog.json` or an Explorer projection.

The package and script entrypoints call the same graph builder. For repeated
agent or port queries, build the graph once and load it with `--graph-json`:

```powershell
python -m lba2_lm2_viewer catalog-graph --asset-root <root> build --output temp/catalog-graph.json
python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json scene-object SCENE.HQR:2 2 --json
python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json prove BODY.HQR:2 ANIM.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> scene-object SCENE.HQR:2 2 --json
python scripts/catalog_graph_probe.py --graph-json temp/catalog-graph.json scene-object SCENE.HQR:2 2 --json
```

## Commands

```powershell
python -m lba2_lm2_viewer catalog-graph --asset-root <root> probe --ids BODY.HQR:2 BODY.HQR:29 SCENE.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> explain BODY.HQR:29 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> edges BODY.HQR:29 --direction incoming --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> edges BODY.HQR:29 --direction incoming --proof-scope scene_object_state --evidence-status source_backed --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> usages BODY.HQR:29 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> scene-object SCENE.HQR:2 2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> compatible BODY.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> prove BODY.HQR:2 ANIM.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> export --subgraph BODY.HQR:29 --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> export --json
python -m lba2_lm2_viewer catalog-graph --asset-root <root> build --output temp/catalog-graph.json
```

## Query Semantics

| Query | Output | Allowed implication |
| --- | --- | --- |
| `probe` | Graph summary, selected subgraphs, consumer round-trip assertions. | The graph can feed selection/inspector/workspace/export/query/port shapes for selected ids. |
| `explain` | Node plus incoming/outgoing edges. | Explains known graph evidence for one stable id. |
| `edges` | Edges for a node, optionally filtered. | Lists relationship evidence; does not infer missing edges are impossible. |
| `usages` | Incoming usage/script edges for an asset. | Lists known decoded/source-backed scene or script usage. |
| `scene-object` | Scene object node and incident edges. | Explains initial-state visual links and resolver context. |
| `compatible` | Compatible animations for a model. | Lists graph compatibility edges and reasons. |
| `prove` | Compatibility proof between one model and one animation. | Explains why the pair is compatible, or returns explicit negative evidence. |
| `build` | Versioned full graph JSON written to disk. | Reusable offline graph snapshot for repeated agent/port queries. |
| `export` | Full graph or root subgraph JSON on stdout. | Machine-readable graph snapshot for agents, scripts, or port tooling. |

Backend pose/playback uses the same graph contract through the internal
`catalog_graph.animation_operation_compatibility.v0` projection. That projection
wraps the `COMPATIBLE_WITH` proof and returns `eligible`, operation name,
proofs, and negative evidence. It is intentionally internal until a CLI or HTTP
consumer needs it.

The HTTP catalog payload also exposes internal
`catalog_graph.selection_projection.v0` records for asset selection under
`graph.selectionByAssetId`. These records are the UI authority for migrated
selection identity, workspace suggestion, export action, export capability,
inspector route, and graph-backed relationship links.

Export manifests use `catalog_graph.export_context.v0` internally. The context
derives direct scene-object usage counts, script reference counts, scene
indices, proof scopes, evidence statuses, source rules, source fields, and
index rules from graph usage edges rather than from reverse `scene_usages`
arrays.

For migrated scene object relationship rows, the HTTP catalog payload exposes
`catalog_graph.scene_object_relationship_projection.v0` records under
`graph.sceneObjectRelationshipsByStableId`. These records are the UI authority
for scene object File3D/body/animation/sprite relationship display and preserve
edge endpoints, `MissingTarget`, `proofScope`, `evidenceStatus`, `sourceRule`,
`sourceField`, and `indexRule`.

Scene Inspector relationship sections consume these same records for
graph-modeled body, animation, sprite, text, sample, and video links. Decoded
script/control-flow rows remain local decoder evidence until graph vocabulary
covers opcode-level facts.

## JSON Rules

- Responses include `schema`; full graph exports use `catalog_graph.export.v1`.
- Nodes and edges use deterministic ordering.
- Edge fields use camelCase: `proofScope`, `evidenceStatus`, `sourceRule`,
  `sourceField`, `indexRule`.
- Edge filters are echoed under `filters`.
- Missing or unresolved targets must be explicit nodes or negative evidence. Current automated coverage includes missing script sample/video targets and unresolved runtime sprite targets when the catalog payload carries those facts.
- Prose is allowed only as field values such as `sourceRule`; query results must
  remain structured JSON.

## Example: Edges

```json
{
  "schema": "catalog_graph.edges.v0",
  "id": "BODY.HQR:29",
  "direction": "in",
  "filters": {
    "proofScope": "scene_object_state",
    "evidenceStatus": "source_backed"
  },
  "edges": [
    {
      "type": "USES_AS_BODY",
      "from": "scene-object:SCENE.HQR:2:2",
      "to": "asset:BODY.HQR:29",
      "proofScope": "scene_object_state",
      "evidenceStatus": "source_backed",
      "sourceRule": "matched scene GenBody to File3D body generic id",
      "sourceField": "SceneObject.links.body.asset_id / SceneAssetUsage.target_asset_id",
      "indexRule": "File3D body generic id resolves to BODY.HQR catalog entry index.",
      "cardinalityFromSource": "0..1",
      "cardinalityFromTarget": "0..n"
    }
  ]
}
```

## Example: Scene Object

```json
{
  "schema": "catalog_graph.scene_object.v0",
  "sceneId": "SCENE.HQR:2",
  "objectIndex": 2,
  "node": {
    "id": "scene-object:SCENE.HQR:2:2",
    "type": "SceneObject",
    "stableId": "SCENE.HQR:2#object:2"
  },
  "consumerRoundTrip": {
    "selectionStableId": "SCENE.HQR:2#object:2",
    "inspectorEdgeSections": [
      "HAS_FILE3D_RECORD",
      "HAS_SCENE_OBJECT",
      "USES_AS_ANIMATION",
      "USES_AS_BODY"
    ],
    "workspaceSuggestion": "entity",
    "exportProvenanceFields": ["proofScope", "evidenceStatus", "sourceRule"],
    "queryJsonStable": true,
    "portFilterFields": ["proofScope", "evidenceStatus"]
  }
}
```

## Example: Scene Object Relationship Projection

```json
{
  "schema": "catalog_graph.scene_object_relationship_projection.v0",
  "stableId": "SCENE.HQR:2#object:2",
  "visualLinks": [
    {
      "role": "file3d",
      "stableId": "RESS.HQR:44#file3d:7",
      "targetType": "File3DRecord",
      "proofScope": "scene_object_state"
    },
    {
      "role": "sprite",
      "stableId": "SPRITES.HQR:999",
      "targetType": "MissingTarget",
      "targetAvailable": false,
      "proofScope": "scene_object_state",
      "evidenceStatus": "unknown"
    }
  ],
  "edges": [
    {
      "type": "USES_AS_SPRITE",
      "to": {
        "type": "MissingTarget",
        "stableId": "SPRITES.HQR:999"
      },
      "sourceField": "SceneObject.links.sprite.asset_id / SceneAssetUsage.target_asset_id",
      "indexRule": "Runtime sprite index resolves through SPRITE_3D/ANIM_3DS flags."
    }
  ]
}
```

## Example: Prove Compatibility

```json
{
  "schema": "catalog_graph.prove.v0",
  "modelId": "BODY.HQR:2",
  "animationId": "ANIM.HQR:2",
  "compatible": true,
  "proofs": [
    {
      "type": "COMPATIBLE_WITH",
      "proofScope": "classic_source_rule",
      "evidenceStatus": "source_backed",
      "compatibilityReason": "file3d_allowlist",
      "sourceField": "animation_metadata.compatible_body_ids"
    }
  ],
  "negativeEvidence": []
}
```

## Example: Pose/Playback Operation

```json
{
  "schema": "catalog_graph.animation_operation_compatibility.v0",
  "operation": "pose_playback",
  "modelId": "BODY.HQR:2",
  "animationId": "ANIM.HQR:2",
  "eligible": true,
  "compatible": true,
  "relationship": "COMPATIBLE_WITH",
  "proofs": [
    {
      "type": "COMPATIBLE_WITH",
      "proofScope": "classic_source_rule",
      "evidenceStatus": "source_backed",
      "compatibilityReason": "file3d_allowlist"
    }
  ],
  "negativeEvidence": []
}
```

## Agent And Port Usage Notes

- Agents should prefer `explain`, `edges`, `scene-object`, and `prove` before
  inspecting raw catalog payloads.
- UI agents validating migrated model or resource selection should confirm
  `graph.selectionByAssetId[assetId]` exists before relying on frontend
  selection state.
- UI agents validating migrated scene relationship rows should confirm
  `graph.sceneObjectRelationshipsByStableId[sceneObjectStableId]` exists before
  relying on the File3D or Visuals table cells.
- UI agents validating migrated Inspector scene relationships should confirm
  the visible relationship section names graph evidence and that graph-modeled
  visual/audio/text/video rows come from
  `sceneObjectRelationshipsByStableId`, not compact scene-local link arrays.
- UI agents validating `resource_record` export should select the child record,
  confirm the active selection is `resource_record`, and verify the export
  action is inherited from the parent asset graph selection projection.
- Port checks should filter by `proofScope` and `evidenceStatus`; decoded-only
  evidence must not be treated as live proof.
- Promotion packet joins use graph-derived scene usage records and explicit
  scene asset source identity. Stale reverse `scene_usages` arrays are not
  promotion packet evidence; later `port_implication` edges can make that
  relationship explicit.
- Full graph export is suitable for offline analysis and repeated CLI calls.
  Export metadata includes schema version, asset root, HQR file count, asset
  count, graph node/edge counts, catalog summary, build timestamp, and a
  freshness warning. Rebuild from `--asset-root` when source HQR files may have
  changed; `--graph-json` deliberately does not silently prove freshness.

## Storage Decision

Current implementation uses backend Python memory. Frontend memory can consume a
graph export later for UI projection. Exported JSON is appropriate for port CI
snapshots. A database remains unjustified until there is evidence of
cross-process query requirements, unacceptable graph build time after caching,
unacceptable memory use, or query patterns that cannot be served by indexed
memory.
