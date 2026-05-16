# TASK_GPT Explorer/Inspector Graph Validation - 2026-05-09

## Environment

- URL: `http://127.0.0.1:8901/`
- Worktree: `<codex-worktree>\lba2-lm2-viewer`
- Frontend build: `npm run build`
- Browser: Codex in-app browser through agent-browser

## Checks

### Catalog Summary

Observed catalog summary:

- `573 models`
- `2082 decoded animations`
- `720 sprite assets`
- `222 scenes`
- `19062 resources`
- `Catalog relationship refs: 28128 refs across 2361 assets`

This validates the Explorer summary copy no longer overclaims that the summary
count itself is graph-derived. Graph-backed Explorer/search authority is
validated by the row metadata and query matches below.

### Model Explorer / Usage Strip

Selected `BODY.HQR:29`.

Observed Explorer row:

- `Piece of flying saucer model`
- `BODY.HQR[29] - 8 verts, 4 polys, 2 bones, graph-linked by 455 relationships (428 scene objects)`

Observed usage strip buttons included graph metadata:

- `scene_object_state`
- `source_backed`
- `matched scene GenBody to File3D body generic id`
- `fell back to first File3D body candidate`

### Graph-Backed Search

Filtered Explorer with query:

- `script_reference source_backed`

Observed:

- `Showing 260 of 1721 matching entries` across all asset kinds.
- After filtering Asset kind to `Resources`, observed `Showing 246 of 246 matching entries`.

This validates search indexes graph relationship metadata from
`graph.selectionByAssetId.links`.

### Resource Explorer / Inspector / Export

Selected `SAMPLES.HQR:0`.

Observed Explorer row:

- `Sample 0 pcm 1ch 8-bit 22050Hz (SAMPLES.HQR:0)`
- `SAMPLES.HQR[0] - sample 0 pcm 1ch 8-bit 22050Hz, graph-linked by 13 relationships (script/local evidence)`

Observed selection/Inspector state:

- Evidence status: `source_backed`
- Export action visible: `Export evidence bundle`
- Inspector section visible: `Graph Usage Evidence`
- Usage strip buttons included:
  - `script_reference`
  - `source_backed`
  - `resolved scene sample id through zero-based HQR_Get(HQR_Samples,index)`

This validates resource Explorer summaries, resource-record exportability, and
Inspector relationship content are consuming graph selection evidence.

## Screenshot

Agent-browser screenshot validation was captured after rerunning the browser pass:

- `docs/validation-task-gpt-agent-browser-screenshot-2026-05-09.png`
- `docs/validation-task-gpt-final-agent-browser-screenshot-2026-05-09.png`

The earlier CDP screenshot attempt timed out with `Timed out running CDP command
"Page.captureScreenshot" for tab 1`; the rerun used the agent-browser visible
screenshot path instead of relying on DOM evidence alone.

Follow-up final browser validation searched for `scene_object_state`, confirmed
graph relationship metadata affects Explorer results, selected `BODY.HQR:29`,
and observed source-backed scene-object evidence plus the scene usage strip.

## Resource-Record Export Follow-Up

- URL: `http://127.0.0.1:8903/`
- Asset root: `<asset-root>`
- Selected Explorer asset: `LBA_BKG.HQR:1`
- Opened Resource workspace and selected `Record 0`.
- Observed active selection `LBA_BKG.HQR:1#record:0`, kind
  `resource_record`, with `Export evidence bundle` visible.
- Export produced `manifest.json`, `LBA_BKG_HQR_1_composition.json`, and
  `LBA_BKG_HQR_1_preview.png` under
  `<codex-worktree>\lba2-lm2-viewer\exports\LBA_BKG.HQR_1`.
- UI status reported: `Wrote 3 files to ...\exports\LBA_BKG.HQR_1`.
- Manifest graph evidence for `LBA_BKG.HQR:1` had
  `scene_usage_count: 0`, `relationship_link_count: 0`, and
  `promotion_packet_ids: []`.

Screenshots:

- `docs/validation-task-gpt-resource-record-export-2026-05-09.png`
- `docs/validation-task-gpt-resource-record-export-done-2026-05-09.png`
