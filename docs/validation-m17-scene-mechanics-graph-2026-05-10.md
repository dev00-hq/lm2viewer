# M17 Scene Mechanics Graph Validation - 2026-05-10

Validated after implementing Scene Mechanics Graph v1.

## Automated

- `uv run python -m unittest tests.test_catalog_graph tests.test_export_probe`
- `npm run build`
- Continuation pass: `uv run python -m unittest discover -s tests` passed with
  179 tests.
- Continuation pass: `npm run build` passed with the existing Vite chunk-size
  warning.

## Agent Browser

- Started backend on `http://127.0.0.1:8765` and Vite on `http://127.0.0.1:5173`.
- Indexed the local LBA2 asset root.
- Selected graph-linked model `BODY.HQR:29`.
- Confirmed the Scene Usages strip renders graph-backed usage rows.
- Clicked a usage row and confirmed `aria-current` moved from `false` to `true`, exercising edge-id based usage selection.

Screenshot: `docs/validation-m17-scene-mechanics-graph-2026-05-10.png`

## Continuation Agent Browser

- Started a narrow synthetic asset root at
  `temp/validation-assets` with a decoded `SCENE.HQR:2` scene containing one
  object, one zone, one waypoint, and one patch.
- Opened `http://127.0.0.1:5173` against the local backend.
- Indexed `temp/validation-assets`.
- Selected `Scene 1 (SCENE.HQR:2)`.
- Confirmed the scene local table rendered canonical decoded local rows for
  `SCENE.HQR:2#zone:0`, `SCENE.HQR:2#waypoint:0`, and
  `SCENE.HQR:2#patch:0`.
- Activated the zone row through the browser and confirmed the inspector
  selected `SCENE.HQR:2#zone:0` as a `scene_zone` graph-node selection with a
  `Graph Evidence` section.

Screenshot:
`docs/validation-m17-scene-mechanics-graph-2026-05-10-continuation.png`

## Final Agent Browser Gap Check

- A full retail catalog and a four-HQR subset catalog were too large for the
  in-app browser `/catalog.json` load. The final browser check used the small
  synthetic scene-mechanics catalog from the Python tests, served through the
  real `ViewerServer` handler with `temp/validation-subset-assets` as the asset
  root.
- Selected `BODY.HQR:29` and confirmed the Scene Usages strip rendered a graph
  usage row.
- Activated the Scene Usages row and confirmed the active selection became
  `graph_edge` with the stable id equal to the backend graph edge id.
- Confirmed the graph-edge selection exposed the backend-projected `Export edge
  evidence bundle` action. The browser click reached `/api/catalog/export`, but
  the synthetic model payload is not a complete model export fixture; selected
  edge manifest persistence is covered by
  `test_export_from_relationship_row_records_selected_edge_id`.
- Selected `RESS.HQR:48`, opened the Resource workspace, selected
  `RESS.HQR:48#record:0`, and confirmed the active selection became
  `resource_record` from `graph.selectionByStableId`.

Screenshot:
`docs/validation-m17-scene-mechanics-graph-2026-05-10-final.png`
