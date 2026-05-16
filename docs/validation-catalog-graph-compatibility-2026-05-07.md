# Catalog Graph Compatibility Browser Validation

- Date: 2026-05-07
- Tool: `agent-browser`
- URL: `http://127.0.0.1:8891/`
- Server command: `python -m lba2_lm2_viewer.viewer --host 127.0.0.1 --port 8891 --asset-root <asset-root> --no-browser`
- Asset root: `<asset-root>`
- Selected model: `BODY.HQR:2`
- Selected animation: `ANIM.HQR:2`
- Screenshot: `docs/validation-catalog-graph-compatibility-2026-05-07.png`

Expected state:

- Selecting `BODY.HQR:2` enables the compatible-animation combobox.
- The combobox is populated from the backend graph compatibility projection.
- `ANIM.HQR:2` is available as `Back up (ANIM.HQR:2)` without a `[bones]` prefix, matching `file3d_allowlist` graph evidence.

Observed state:

- The compatible-animation combobox showed `103 compatible animations`.
- `Back up (ANIM.HQR:2)` was present and selectable.
- Selecting `ANIM.HQR:2` updated the combobox value to `Back up (ANIM.HQR:2)`.

Note:

- Direct `agent-browser click` refs did not activate the asset button reliably in this session. The validation used `agent-browser eval` to trigger the same DOM click on the catalog asset button, then observed the normal HTTP `/api/catalog/load` and `/api/entity/asset` requests in the server log.
