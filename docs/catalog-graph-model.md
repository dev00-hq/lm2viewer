# Catalog Graph Model

This is the canonical current-state catalog graph model. It is a typed
in-memory property graph with ER-style relationship discipline. It is not an
Explorer tree schema and not a database schema.

The implementation lives in `lba2_lm2_viewer/catalog_graph.py` and builds from
the same `viewer.build_catalog()` payload used by the HTTP server. The graph can
be exported as `catalog_graph.export.v1` JSON and reloaded by CLI/script queries
with `--graph-json`; exported freshness is reported as metadata and warning, not
silently trusted.

## Node Vocabulary

| Node type | Stable id | Meaning | Evidence |
| --- | --- | --- | --- |
| `Asset` | `BODY.HQR:2` | Cataloged decoded or retained asset. | `CatalogAsset.id`, kind, source, hashes. |
| `Archive` | `BODY.HQR` | HQR archive identity. | `Catalog.hqr_files[]`. |
| `ArchiveEntry` | `BODY.HQR:2` | Addressable HQR entry before semantic decode. | `CatalogAsset.source`. |
| `Scene` | `SCENE.HQR:2` | Decoded scene asset as a scene domain node. | `CatalogAsset.kind == scene`. |
| `SceneObject` | `SCENE.HQR:2#object:2` | Runtime scene object slot. | `SceneStats.reconnaissance.sampled_objects[]`; object index is zero-based. |
| `File3DRecord` | `RESS.HQR:44#file3d:16` | Runtime resolver table row for generic body/animation slots. | `SceneObject.file3d_index`, `RESS.HQR:44` File3D evidence. |
| `ScriptReference` | generated script-ref id | Life/track script asset or resource reference. | `track_script_analysis.asset_links`, `life_script_analysis.asset_links`. |
| `SpriteRange` | `ANIM3DS:0` | ANIM3DS projected sprite animation range. | `ANIM3DS.HQR:127 stats.entries[]`. |
| `ResourceRecord` | `RESS.HQR:48#record:0` | Payload-local resource subrecord. | `ResourceStats.sampled_records[]`, `text_links[]`. |
| `MissingTarget` | target stable id | Explicit unresolved asset/resource target. | Missing link metadata or range missing-frame warnings. |

Future node candidates are `SceneZone`, `Waypoint`, `PortContract`,
`RuntimeState`, `ExportArtifact`, and `EvidenceSource`. They are intentionally
not fully materialized in the first slice unless the current payload exposes a
selectable/queryable fact.

## Edge Vocabulary

Every edge carries direction, inverse, cardinality, proof scope, evidence
status, source rule, source field, index rule, materialization location,
selectability, and search participation.

| Edge | Direction | Inverse | Cardinality | Proof scope | Evidence status |
| --- | --- | --- | --- | --- | --- |
| `HAS_ENTRY` | `Archive -> ArchiveEntry` | entry of archive | `0..n -> 1` | `decoded_payload` | `decoded_only` |
| `DECODED_AS` | `ArchiveEntry -> Asset` | decoded from entry | `0..1 -> 1` | `decoded_payload` | asset status |
| `DECODED_AS` | `Asset -> Scene` | scene asset | `0..1 -> 1` | `decoded_payload` | asset status |
| `HAS_SCENE_OBJECT` | `Scene -> SceneObject` | object of scene | `0..n -> 1` | `decoded_payload` | `decoded_only` |
| `HAS_FILE3D_RECORD` | `SceneObject -> File3DRecord` | File3D record used by scene object | `0..1 -> 0..n` | `scene_object_state` | `source_backed` when resolved |
| `RESOLVES_TO` | `File3DRecord -> Asset` | resolved from File3D slot | `0..n -> 0..n` | `classic_source_rule` | `source_backed` or `unknown` |
| `USES_AS_BODY` | `SceneObject -> Asset` | used as body | `0..1 -> 0..n` | `scene_object_state` | `source_backed` |
| `USES_AS_ANIMATION` | `SceneObject -> Asset` | used as animation | `0..1 -> 0..n` | `scene_object_state` | `source_backed` |
| `USES_AS_SPRITE` | `SceneObject -> Asset` | used as sprite | `0..1 -> 0..n` | `scene_object_state` | `source_backed` or `unknown` |
| `SCRIPT_REFERENCES` | `ScriptReference -> Asset` | referenced by script | `0..1 -> 0..n` | `script_reference` | `source_backed` or `unknown` |
| `USES_SAMPLE` | `SceneObject/ScriptReference -> Asset` | sample used by scene/script | `0..n -> 0..n` | `scene_object_state` or `script_reference` | status from link |
| `USES_TEXT` | `SceneObject/ScriptReference -> Asset` | text used by scene/script | `0..n -> 0..n` | `script_reference` or `classic_source_rule` | status from link |
| `USES_VIDEO` | `ScriptReference -> Asset` | video used by script | `0..n -> 0..n` | `script_reference` | status from link |
| `USES_RESOURCE` | scene/resource context -> resource | resource used by context | `0..n -> 0..n` | source-specific | status from link |
| `COMPATIBLE_WITH` | `Animation Asset -> Model Asset` | model accepts animation | `0..n -> 0..n` | `classic_source_rule` or `frontend_compatibility_rule` | `source_backed` or `decoded_only` |
| `RANGE_CONTAINS_FRAME` | `SpriteRange -> Asset/MissingTarget` | frame of range | `1..n -> 0..n` | `decoded_payload` | `decoded_only` or `unknown` |
| `RESOURCE_RECORD_OF` | `Asset -> ResourceRecord` | record of resource | `0..n -> 1` | `decoded_payload` | asset status |
| `CONTAINS` | owner node -> contained evidence node | contained by | context-specific | source-specific | source-specific |

Rejected generic edge: `RELATED_TO`. Current evidence almost always supports a
more precise relationship name. If a future edge cannot be named precisely, it
must carry `proofScope: unknown` and a documented unresolved question.

## Edge Metadata Matrix

All first-slice graph edges are materialized by the backend graph builder from
the current catalog payload; none are derived in the frontend. All listed edges
participate in search unless noted.

| Edge | Source node | Target node | Source rule / field | Index rule | Selectable |
| --- | --- | --- | --- | --- | --- |
| `HAS_ENTRY` | `Archive` | `ArchiveEntry` | `build_catalog` HQR scan / `hqr_files[].path`, `CatalogAsset.source.entry_index` | Archive-specific `source.entry_index`, `classic_index`, or `hqr_table_index` | no |
| `DECODED_AS` | `ArchiveEntry` | `Asset` | Catalog asset creation / `Catalog.assets[]` | Same as asset source archive | yes |
| `DECODED_AS` | `Asset` | `Scene` | Scene semantic layout / `CatalogAsset.stats.reconnaissance` | `SCENE.HQR` entry is scene id + 1 | yes |
| `HAS_SCENE_OBJECT` | `Scene` | `SceneObject` | Scene decode / `SceneStats.reconnaissance.sampled_objects[]` | Scene object index is zero-based runtime object index | yes |
| `HAS_FILE3D_RECORD` | `SceneObject` | `File3DRecord` | Scene object `IndexFile3D` selects `RESS.HQR:44` resolver / `SceneObject.file3d_index` | File3D record index is zero-based in `RESS.HQR:44` | yes |
| `RESOLVES_TO` | `File3DRecord` | `Asset` or `MissingTarget` | File3D generic slot resolves to HQR asset / `file3d_index + gen_body/gen_anim` | File3D body ids become `BODY.HQR` catalog ids by body index + 1; animation ids are `ANIM.HQR` entries | yes |
| `USES_AS_BODY` | `SceneObject` | `Asset` or `MissingTarget` | Scene body link / `SceneObject.links.body.asset_id`, `SceneAssetUsage.target_asset_id` | File3D body generic id resolves to `BODY.HQR` catalog entry index | yes |
| `USES_AS_ANIMATION` | `SceneObject` | `Asset` or `MissingTarget` | Scene animation link / `SceneObject.links.animation.asset_id`, `SceneAssetUsage.target_asset_id` | File3D animation generic id resolves to `ANIM.HQR` catalog entry index | yes |
| `USES_AS_SPRITE` | `SceneObject` | `Asset` or `MissingTarget` | Runtime sprite link / `SceneObject.links.sprite.asset_id`, `SceneAssetUsage.target_asset_id` | `SPRITE_3D`/`ANIM_3DS` flags select `SPRIRAW`, `SPRITES`, or `ANIM3DS` backend | yes |
| `SCRIPT_REFERENCES` | `ScriptReference` | `Asset` or `MissingTarget` | Script asset link / `track_script_analysis.asset_links`, `life_script_analysis.asset_links` | Opcode-specific reference value; target archive rule retained on edge | yes |
| `USES_SAMPLE` | `SceneObject` or `ScriptReference` | sample `Asset` or `MissingTarget` | Ambience or script sample link / `sample_ambience_links`, script `asset_links` | Runtime sample id maps to `SAMPLES.HQR` zero-based catalog id; HQR table index is id + 1 | yes |
| `USES_TEXT` | `SceneObject`, zone context, or `ScriptReference` | text `Asset` or record | Text zone/script/holomap link / `text_zone_links`, script `asset_links`, `ResourceStats.text_links` | Logical text id plus text file/language and payload-local record index | yes |
| `USES_VIDEO` | `ScriptReference` | video `Asset` or `MissingTarget` | ACF script link / script `asset_links`, `acf_name` | Runtime ACF list index resolves through `RESS.HQR:48` to `VIDEO/VIDEO.HQR` zero-based id | yes |
| `USES_RESOURCE` | scene/resource context | resource `Asset` or `MissingTarget` | Resource-specific link / GRM, background, or semantic resource fields | Payload-specific; edge must state source field | yes |
| `COMPATIBLE_WITH` | animation `Asset` | model `Asset` | File3D allow-list or bone-count check / `animation_metadata.compatible_body_ids`, `AnimationStats.boneframes`, `ModelStats.bones` | `BODY.HQR` ids use catalog entry index; File3D body record stores body index + 1 | yes |
| `RANGE_CONTAINS_FRAME` | `SpriteRange` | frame `Asset` or `MissingTarget` | ANIM3DS range table / `Anim3dsInfoStats.entries[].start_frame/end_frame` | Frame id is zero-based `ANIM3DS.HQR` entry index | yes |
| `RESOURCE_RECORD_OF` | resource `Asset` | `ResourceRecord` | Resource semantic decode / `ResourceStats.sampled_records[]`, `text_links[]` | Record index is payload-local unless a source field gives an HQR entry | yes |
| `CONTAINS` | context-specific owner | contained evidence node | Context-specific containment such as script reference grouping | Context-specific | yes when contained node is selectable |

## Cardinality Rules

| Relationship family | Rule |
| --- | --- |
| Archive identity | One archive has `0..n` entries; one entry belongs to `1` archive. |
| Decode identity | One archive entry decodes as `0..1` primary asset; one asset has `1` source entry. |
| Scene objects | One scene has `0..n` scene objects; one scene object belongs to `1` scene. |
| File3D resolution | One scene object has `0..1` active File3D record; one File3D record may be used by `0..n` objects. |
| Scene visual usage | One scene object has `0..1` body, `0..1` animation, and `0..1` sprite/range initial visual usage. One asset has `0..n` incoming usages. |
| Script references | One script reference has `0..1` resolved target; one target may have `0..n` script references. Script reference is not current scene state. |
| Compatibility | Model-animation compatibility is many-to-many and must stay an edge with evidence metadata. |
| ANIM3DS ranges | One range contains `1..n` frame entries; one frame can belong to `0..n` ranges. |
| Resource records | One resource asset has `0..n` payload-local records; one record belongs to `1` resource asset. |

## Operation Contracts

`COMPATIBLE_WITH` is currently sufficient for the viewer's model-animation
pose/playback operation. Backend pose and sequence validation must call the
graph operation query instead of re-reading `animation_metadata` or comparing
bone counts independently.

The operation contract is:

- File3D allow-list compatibility creates a `COMPATIBLE_WITH` edge only when
  the listed `BODY.HQR` model exists and its decoded bone count matches the
  animation boneframe count.
- Bone-count-only compatibility creates a weaker `COMPATIBLE_WITH` edge only
  when no File3D allow-list metadata exists for that animation.
- A missing edge means pose/playback is not eligible. The graph operation query
  returns negative evidence such as bone-count mismatch, File3D allow-list
  mismatch, or no compatible edge.
- Non-`BODY.HQR` models follow the same graph contract as every other model:
  they are eligible only when a `COMPATIBLE_WITH` edge exists.

If a future viewer operation needs looser or stricter semantics than
`COMPATIBLE_WITH`, add a distinct operation projection and tests instead of
adding another local validator.

## Selection Projections

The HTTP catalog projection now includes
`catalog_graph.selection_projection.v0` records under `selectionByAssetId` for
migrated model and resource assets.

Current migrated asset selection projection fields include:

- selected graph node id and stable id;
- source archive/index/hash fields;
- evidence status;
- workspace suggestion;
- inspector route;
- export capability and export actions;
- preview and export actions;
- graph-backed usage/script relationship links with edge evidence fields;
- direct scene usage count separated from total relationship link count.

Frontend model-asset and resource-asset selection must consume this projection.
It may render or copy the fields locally, but it must not re-derive migrated
selection identity, workspace suggestion, exportability, or relationship links
from `asset.kind`, `semantic_layout`, `scene_usages`, or stable-id string
parsing.

Resource exportability is a graph projection decision for migrated resource
assets. The current exportable resource semantic layouts are
`sample_wave_audio`, `lba2_texture_atlas_indexed`, `lba2_indexed_image_256`,
`screen_indexed_image_640x480`, `bkg_grid_map`, `bkg_brick_graphic`,
`holomap_plan_image_640x480`, `text_payload_bank`, and `smacker_video`.

Inspector routing is also graph-projected for migrated model/resource assets.
Current routes are `model`, `sample_audio`, `smacker_video`, `text_order`,
`text_payload`, `palette_image`, `runtime_table`, `holomap`, `background`, and
`unclassified_resource`. Frontend code may call the existing renderer for that
route, but it must not rediscover the route from `asset.kind +
semantic_layout` for migrated selections.

## Scene Object Relationship Projections

The HTTP catalog projection includes
`catalog_graph.scene_object_relationship_projection.v0` records under
`sceneObjectRelationshipsByStableId` for scene objects materialized by the
graph.

Current migrated scene object relationship projection fields include:

- selected scene object graph node id and stable id;
- decoded object source fields;
- incident edge projections with endpoint node type, stable id, and label;
- edge `proofScope`, `evidenceStatus`, `sourceRule`, `sourceField`, and
  `indexRule`;
- `visualLinks` for `file3d`, `body`, `animation`, and `sprite` roles,
  including `MissingTarget` targets.

The scene object table's File3D and Visuals columns consume this projection.
They must not re-derive body, animation, sprite, or missing visual target ids
from `SceneStats.reconnaissance.sampled_objects[].links` once the projection is
present.

## Proof Scopes

| Scope | Meaning |
| --- | --- |
| `decoded_payload` | Directly decoded from HQR/catalog payload without claiming runtime behavior. |
| `classic_source_rule` | Backed by classic source rules such as `DISKFUNC.CPP`, `OBJECT.CPP`, `FICHE.CPP`, `GERELIFE.CPP`, `GERETRAK.CPP`. |
| `scene_object_state` | Decoded scene object initial state such as `file3d_index`, `gen_body`, `gen_anim`, flags, sprite, FPS. |
| `script_reference` | Life/track script reference or possible mutation, not current ownership. |
| `frontend_compatibility_rule` | Current frontend-only rule, mainly bone-count-only animation compatibility. |
| `runtime_live_proof` | Reserved for live runtime reads. Not emitted by the first slice. |
| `port_implication` | Reserved for port-facing contract/promotion packet implications. |
| `export_manifest` | Reserved for export artifact provenance edges. |
| `unknown` | Unresolved or ambiguous evidence. |

## Evidence Statuses

| Status | Rule |
| --- | --- |
| `source_backed` | A decoded fact is tied to a classic source rule, source provenance, File3D allow-list, runtime table provenance, or script resolution rule. |
| `decoded_only` | The payload is decoded, but runtime/source semantics are not stronger than the payload. |
| `render_only` | A preview/render artifact exists without implying runtime equivalence. |
| `live_confirmed` | Reserved for runtime proof. |
| `port_implied` | Reserved for port contract implication. |
| `intentionally_deferred` | Raw/deferred decode evidence retained as a known gap. |
| `unknown` | Missing target, unresolved reference, or ambiguous rule. |

## Index Rules

- `BODY.HQR`: catalog id is one higher than classic body table slot; for example `BODY.HQR:2` has `classic_index: 1`.
- `SCENE.HQR`: catalog entry index is classic runtime scene id plus one; source `LoadScene(numscene)` reads `scene.hqr` entry `numscene + 1`.
- `SAMPLES.HQR` and `VIDEO/VIDEO.HQR`: runtime ids are zero-based while HQR table indices are runtime id plus one.
- `SCREEN.HQR`: zero-based PCR constants; even entries are images and paired odd entries are palettes.
- `ANIM3DS.HQR`: frame ids are zero-based entries; `ANIM3DS.HQR:127` is the range metadata table.
- File3D body records store body index plus one as `BODY.HQR` catalog id; `GenBody` is a generic slot, not a body asset id.
- File3D animation records map generic `GenAnim` values to `ANIM.HQR` catalog entries; `GenAnim` is not an animation asset id.

## Real Examples

- `SCENE.HQR:2#object:2` has `HAS_FILE3D_RECORD -> RESS.HQR:44#file3d:16`, `USES_AS_BODY -> BODY.HQR:29`, and `USES_AS_ANIMATION -> ANIM.HQR:220`.
- `BODY.HQR:2` has no known scene usage edges in the current reverse index, but it has many incoming `COMPATIBLE_WITH` edges.
- `ANIM.HQR:2 -> BODY.HQR:2` is `COMPATIBLE_WITH` with `proofScope: classic_source_rule`, `evidenceStatus: source_backed`, and `compatibilityReason: file3d_allowlist`. Bone-count-only compatibility remains `frontend_compatibility_rule`/`decoded_only` until stronger source evidence exists.
- `ANIM3DS.HQR:127` materializes `SpriteRange` nodes; range `COQU 0..32` contains `ANIM3DS.HQR:0` through `ANIM3DS.HQR:32`.
- `RESS.HQR:48` materializes `ResourceRecord` nodes from sampled ACF-name records; record ids are payload-local.
- Missing script sample/text/video references and unresolved runtime sprite
  references are represented by `MissingTarget` nodes with `evidenceStatus:
  unknown` when the scene payload exposes the unresolved reference.
- The HTTP catalog payload now includes a graph projection for animation
  compatibility. The Model workspace consumes that graph projection; TypeScript
  no longer owns the authoritative File3D allow-list or bone-count rule.

## Implementation Target

The graph remains in-memory for now. The first live probe built from the default
asset root produced 22,659 assets, 74,850 graph nodes, 109,550 graph edges, and
2,361 assets with scene-usage targets. Build time is dominated by catalog
decode, not graph storage. A database is not justified yet; exported graph JSON
or backend memory caching should be evaluated before persistence.
