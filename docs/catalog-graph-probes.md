# Catalog Graph Probes

Probe commands use the new read-only graph surface:

```powershell
python -m lba2_lm2_viewer catalog-graph --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 probe --ids BODY.HQR:2 BODY.HQR:29 SCENE.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 scene-object SCENE.HQR:2 2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 edges BODY.HQR:2 --direction incoming --proof-scope classic_source_rule --evidence-status source_backed --json
python -m lba2_lm2_viewer catalog-graph --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 prove BODY.HQR:2 ANIM.HQR:2 --json
python -m lba2_lm2_viewer catalog-graph --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 build --output temp/catalog-graph.json
python -m lba2_lm2_viewer catalog-graph --graph-json temp/catalog-graph.json usages BODY.HQR:29 --proof-scope scene_object_state --evidence-status source_backed --json
```

The script-level validation entrypoint uses the same builder:

```powershell
python scripts/catalog_graph_probe.py --graph-json temp/catalog-graph.json scene-object SCENE.HQR:2 2 --json
```

## Probe Matrix

| Family | Real ids | Expected assertion | Status |
| --- | --- | --- | --- |
| Archive identity | `BODY.HQR:2`, `ANIM3DS.HQR:127`, `SPRIRAW.HQR:0`, `OBJFIX.HQR:60`, `SAMPLES.HQR:0`, `SCREEN.HQR:0`, `HOLOMAP.HQR:0`, `RESS.HQR:48` | Node/edge source carries archive, entry index, and index rule. `BODY.HQR:2` has `classic_index: 1`; sample/video runtime ids are zero-based with HQR table index + 1. | Partly automated; broad fixture still manual. |
| Scene object visual links | `SCENE.HQR:2#object:2` | Emits `HAS_FILE3D_RECORD`, `USES_AS_BODY -> BODY.HQR:29`, `USES_AS_ANIMATION -> ANIM.HQR:220`; usage is not ownership. | Automated CLI and unit coverage. |
| Direct usage vs script reference | `SCENE.HQR:2`, assets with `script_*` usages | Initial-state usage edges use `scene_object_state`; script links use `SCRIPT_REFERENCES` and `script_reference`. Same endpoint evidence remains two edges. | Unit-covered with focused synthetic endpoint duplicate. |
| Runtime sprite backend | `SPRITE_3D`, `SPRIRAW.HQR:0`, `SPRITES.HQR:*`, `ANIM3DS.HQR:*` | Backend comes from runtime flags/index rule, not asset kind guessing. Low direct `SPRITES.HQR` slots are not resolved by calling projected sprite rules. | Unit-covered for `SPRIRAW`, `SPRITES`, and `ANIM3DS` backend selection. |
| ANIM3DS range/frame | `ANIM3DS.HQR:127`, `ANIM3DS.HQR:0` | `SpriteRange -> RANGE_CONTAINS_FRAME -> frame asset`, with range table separate from scene FPS/timing. | Implemented; graph range/frame/table identity unit-covered. |
| Compatibility | `BODY.HQR:2`, `ANIM.HQR:2` | `COMPATIBLE_WITH` is `classic_source_rule`, `source_backed`, `file3d_allowlist`. Bone-count-only remains weaker and separate. | Automated CLI and unit coverage. |
| Empty relationships | `BODY.HQR:2`, `BODY.HQR:29` | `BODY.HQR:2` has no known scene usage but compatibility edges; `BODY.HQR:29` has many incoming scene usage edges. | CLI validated. |
| Resource records | `RESS.HQR:48`, `SAMPLES.HQR:0`, `SCREEN.HQR:0` | Resource subrecords are payload-local nodes with `RESOURCE_RECORD_OF`; sample/screen index rules are preserved. | Unit coverage for `RESS.HQR:48`; broader manual. |
| Proof-scope filtering | `BODY.HQR:2`, `BODY.HQR:29` | `--proof-scope` and `--evidence-status` return only matching edges. | CLI validated. |
| Consumer round-trip | `SCENE.HQR:2#object:2` | Query JSON includes stable selection id, inspector edge sections, workspace suggestion, export provenance fields, and port filter fields. | CLI validated. |
| Negative evidence | missing samples/text/video, runtime sprite, raw/deferred entries | Missing targets should be explicit `MissingTarget` or unknown/deferred evidence, not absent relationships. | Unit-covered for missing script sample/text/video targets and unresolved runtime sprite graph targets; broader real-catalog raw/deferred coverage remains unresolved. |
| Export/import reuse | `temp/catalog-graph.json` | Build once with `build --output`; query with `--graph-json` without rebuilding the catalog. Export carries metadata and stale-cache warning. | Unit-covered for deterministic synthetic export/import; real CLI gate required per slice. |
| App consumer | Model workspace animation compatibility | Frontend compatibility filtering and labels consume backend graph projection, not local `compatible_body_ids`/bone-count rules. | Frontend build-covered and browser-validated in `docs/validation-catalog-graph-compatibility-2026-05-07.md`. |

## Representative Assertions

### Scene Object

`catalog-graph scene-object SCENE.HQR:2 2 --json` must include:

```json
{
  "schema": "catalog_graph.scene_object.v0",
  "sceneId": "SCENE.HQR:2",
  "objectIndex": 2,
  "consumerRoundTrip": {
    "selectionStableId": "SCENE.HQR:2#object:2",
    "workspaceSuggestion": "entity",
    "portFilterFields": ["proofScope", "evidenceStatus"]
  }
}
```

Required edge types: `HAS_SCENE_OBJECT`, `HAS_FILE3D_RECORD`,
`USES_AS_BODY`, `USES_AS_ANIMATION`.

### Compatibility

`catalog-graph prove BODY.HQR:2 ANIM.HQR:2 --json` must include:

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
      "compatibilityReason": "file3d_allowlist"
    }
  ]
}
```

### Usage Filtering

`catalog-graph usages BODY.HQR:29 --proof-scope scene_object_state --evidence-status source_backed --json`
must return only incoming scene-object usage edges such as
`SCENE.HQR:2#object:2 -> BODY.HQR:29`.

## Promotion Rules

Promote a probe to a unit or golden regression test when:

- It protects canonical id/index semantics.
- It prevents direct `GenBody`/`GenAnim` to asset-id shortcuts.
- It distinguishes File3D allow-list from bone-count-only compatibility.
- It protects edge direction/cardinality/proof scope/evidence status.
- It protects deterministic JSON shape used by CLI, port, agents, or exports.

Keep a probe manual or exploratory when:

- It depends on broad retail asset coverage and is too large for a focused test.
- It depends on live runtime state.
- The source interpretation is still unsettled.
- The expected output is a performance/profile threshold rather than semantic
  correctness.

## First Unit Coverage

`tests/test_catalog_graph.py` covers:

- Scene object usage preserves `File3DRecord` and does not map `GenBody` to
  `BODY.HQR:<GenBody>`.
- Scene object usage is materialized from the scene object's own `links`, even
  when all reverse `scene_usages` fields are removed from the catalog.
- `BODY.HQR:29` usage query emits `USES_AS_BODY` with
  `proofScope: scene_object_state` and `evidenceStatus: source_backed`, while
  same-endpoint script references remain separate `SCRIPT_REFERENCES` edges.
- `BODY.HQR:2` and `ANIM.HQR:2` compatibility is `file3d_allowlist`.
- `RESS.HQR:48` resource record is indexed as a payload-local node.
- Full graph export/import is deterministic with fixed metadata on a synthetic
  catalog.
- Missing script sample/text/video references and unresolved runtime sprite
  references become `MissingTarget` nodes with unknown evidence.
- Runtime sprite resolver tests protect `SPRIRAW`, projected `SPRITES`, and
  `ANIM3DS` backend selection and keep `ANIM3DS.HQR:127` distinct from frames.
- `SpriteRange` graph tests keep `ANIM3DS.HQR:127` as the range-table asset and
  `ANIM3DS.HQR:0`/`:1` as frame assets.
- The server catalog projection exposes graph-backed compatibility data for
  frontend consumers.
