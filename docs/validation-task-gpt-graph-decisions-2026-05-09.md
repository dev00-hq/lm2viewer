# TASK_GPT Graph Decision Validation - 2026-05-09

## Environment

- Worktree: `C:\Users\sebam\.codex\worktrees\e82a\lba2-lm2-viewer`
- Server: `uv run python -m lba2_lm2_viewer --host 127.0.0.1 --port 8903 --no-browser`
- Asset root loaded through `/api/catalog/build`:
  `D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`
- Browser: Codex in-app browser at `http://127.0.0.1:8903`

## Checked

- Selected `BODY.HQR:29`.
- Observed active entity workflow for `SCENE.HQR:2#object:2`.
- Observed 12 rendered `.scene-usage-item` buttons for the active graph-backed usage strip.
- DOM contained graph edge proof metadata including `scene_object_state` and `source_backed`.
- Selected `SAMPLES.HQR:0`.
- Observed a single `Export evidence bundle` button and confirmed it was enabled.
- Follow-up agent-browser pass opened `http://127.0.0.1:8899`, confirmed the
  catalog page loaded, clicked the visible `BODY.HQR:29` Explorer entry, and
  observed 12 `.scene-usage-item` buttons with `scene_object_state` and
  `source_backed` evidence in the page DOM.
- The same browser session confirmed `/catalog.json` graph projections for
  `BODY.HQR:29`, `SAMPLES.HQR:0`, and `SCENE.HQR:2#object:2`: model usage links
  were graph-backed, sample exportability was graph-backed with route
  `sample_audio`, and scene-object visual links carried source-backed graph
  evidence.
- Follow-up resource-record export validation selected `LBA_BKG.HQR:1`, opened
  Resource workspace, selected `Record 0`, observed active selection
  `LBA_BKG.HQR:1#record:0` with kind `resource_record`, and confirmed the
  `Export evidence bundle` action remained available from the parent asset's
  graph projection.
- The browser export wrote `manifest.json`, `LBA_BKG_HQR_1_composition.json`,
  and `LBA_BKG_HQR_1_preview.png` to
  `C:\Users\sebam\.codex\worktrees\e82a\lba2-lm2-viewer\exports\LBA_BKG.HQR_1`.
- The written manifest reports graph export evidence for `LBA_BKG.HQR:1`:
  `scene_usage_count: 0`, `relationship_link_count: 0`, and
  `promotion_packet_ids: []`, matching the selected resource's graph evidence
  instead of stale reverse usage.

## Notes

- Initial CDP screenshot capture timed out in this session, but a follow-up
  agent-browser visible screenshot was captured at
  `docs/validation-task-gpt-agent-browser-screenshot-2026-05-09.png`.
  A final Explorer/search validation screenshot was captured at
  `docs/validation-task-gpt-final-agent-browser-screenshot-2026-05-09.png`.
  Resource-record export screenshots were captured at
  `docs/validation-task-gpt-resource-record-export-2026-05-09.png` and
  `docs/validation-task-gpt-resource-record-export-done-2026-05-09.png`.
- Backend and frontend build validation were run separately from this browser check.
- Follow-up validation on the stricter graph authority changes:
  `uv run python -m unittest tests.test_catalog_graph tests.test_export_probe`
  passed, `uv run python -m unittest discover -s tests` passed 151 tests, and
  `npm run build` passed.
