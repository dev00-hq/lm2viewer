# M6 Scene Object Relationship Validation - 2026-05-07

## Setup

- URL: `http://127.0.0.1:8896`
- Viewer command: `python -m lba2_lm2_viewer --host 127.0.0.1 --port 8896 --no-browser`
- Asset root: `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- Screenshot: `docs/validation-m6-scene-object-relationships-2026-05-07.png`

## Selected Evidence

- Selected asset: `SCENE.HQR:2`
- Relationship row checked: `SCENE.HQR:2#object:2`
- Graph projection checked: `graph.sceneObjectRelationshipsByStableId["SCENE.HQR:2#object:2"]`

## Expected

- Scene object table is visible for `SCENE.HQR:2`.
- Row `SCENE.HQR:2#object:2` renders File3D/Visuals from the graph
  relationship projection.
- File3D cell uses graph stable id `RESS.HQR:44#file3d:16`, not the raw local
  object index.
- Projection includes incident graph edge evidence fields:
  `proofScope`, `evidenceStatus`, `sourceRule`, `sourceField`, and
  `indexRule`.

## Observed

- Scene object table showed `9 scene object records`.
- Row `SCENE.HQR:2#object:2` rendered:
  - File3D: `RESS.HQR:44#file3d:16`
  - Visuals: `BODY.HQR:29 | ANIM.HQR:220`
  - Render: `body_model`
- Fetched `/catalog.json` in-browser and confirmed
  `graph.sceneObjectRelationshipsByStableId["SCENE.HQR:2#object:2"]` existed.
- Projection `visualLinks` included graph roles `file3d`, `body`, and
  `animation` with `proofScope: scene_object_state` and source/index fields.
- Synthetic tests cover the missing sprite target path because this retail row
  has no unresolved sprite target.

## Result

Passed.
