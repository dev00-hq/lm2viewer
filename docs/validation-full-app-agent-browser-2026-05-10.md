# Full app agent-browser validation - 2026-05-10

Validated against `http://127.0.0.1:8916/` with the canonical asset root:

`D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2`

Result: **49/49 browser checks passed**.

## Run Context

- Checkout: `C:\Users\sebam\.codex\worktrees\e82a\lba2-lm2-viewer`
- URL: `http://127.0.0.1:8916/`
- Server command:

```powershell
uv run python -m lba2_lm2_viewer --host 127.0.0.1 --port 8916 --asset-root D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2 --no-browser
```

- Listener freshness: server process was started from this checkout for the validation run, then stopped after validation.
- Browser tool: agent-browser / Codex in-app browser.
- Export side effect: the run exercised a real triangulated export for `BODY.HQR:1`; the generated workspace-local `exports/` directory was removed after verifying it was inside the checkout.

## Coverage

- App shell, startup state, explorer and inspector collapse controls.
- File/folder/HQR picker control presence and server-path error reporting.
- Viewer workspace tabs: model, sprite, entity, resource.
- View controls popover, visibility toggles, zoom controls, horizon lock, background toggle, shade picker.
- Catalog indexing, search, and kind filters for all/model/animation/sprite/scene/resource.
- Model selection, model export control, triangulated export action, UV inspector, model surface promotion.
- Compatible animation picker, transport controls, pose application, animation sample inspection.
- Scene usage strip, usage activation, entity workflow, visual/usage evidence panels.
- Runtime sprite resolver defaults and open action.
- Sprite workspace, single-frame sprite control state, frame strip, frame inspection.
- Scene evidence dock: scene objects, scene locals, port evidence, script evidence, scene object promotion.
- Resource inspector/workspace routes for:
  - sample audio
  - background grid, brick, cube, and GRM fragment
  - palette, indexed image, screen image, texture atlas
  - File3D table, sprite ZV table, offset table, fixed table, ext size info
  - holomap plan and globe texture
  - text order and text payload
  - Smacker video
- Raw sprite and ANIM3DS specialty routes.
- Inspector search filtering.
- Browser console fatal-error scan.

## Candidate Assets

- Model export: `BODY.HQR:1`
- Usage-rich model: `BODY.HQR:26`
- Animation: `ANIM.HQR:100`
- Scene: `SCENE.HQR:2`
- Sprite: `SPRITES.HQR:127`
- Raw sprite: `SPRIRAW.HQR:0`
- ANIM3DS ranges: `ANIM3DS.HQR:127`
- Sample audio: `SAMPLES.HQR:0`
- Background grid: `LBA_BKG.HQR:1`
- Background brick: `LBA_BKG.HQR:197`
- Background cube: `LBA_BKG.HQR:18100`
- GRM fragment: `LBA_BKG.HQR:149`
- Palette: `RESS.HQR:0`
- Indexed image: `RESS.HQR:11`
- Screen image: `SCREEN.HQR:0`
- Texture atlas: `RESS.HQR:6`
- File3D table: `RESS.HQR:44`
- Sprite ZV table: `RESS.HQR:5`
- Offset table: `RESS.HQR:1`
- Fixed table: `RESS.HQR:45`
- Ext size info: `RESS.HQR:2`
- Holomap plan: `HOLOMAP.HQR:18`
- Holomap globe texture: `HOLOMAP.HQR:2`
- Text order: `TEXT.HQR:0`
- Text payload: `TEXT.HQR:1`
- Video: `VIDEO/VIDEO.HQR:0`

## Visual Checkpoints

Agent-browser screenshot checkpoints were taken during the run at these states:

- Shell, workspace switcher, view controls, dock controls.
- Model selection, UV inspector, animation controls, export result.
- Entity workflow and runtime sprite resolver.
- Sprite workspace and single-frame sprite controls.
- Scene evidence dock with object/local/port/script panels.
- Resource workspace and long-tail resource inspector routes.
- Correction pass for cached startup, toggled controls, animation pose, runtime resolver, and sprite control state.

The in-app browser run produced visual checkpoints during execution, but this full-app note does not attach separate image files. The narrower M16 task artifacts with persisted screenshot files remain:

- `docs/validation-task-final-agent-browser-2026-05-10.jpg`
- `docs/validation-task-final-usage-strip-agent-browser-2026-05-10.png`
- `docs/validation-task-final-derived-usage-strip-agent-browser-2026-05-10.png`

## Per-Check Appendix

All checks below passed in the final corrected browser report.

1. App shell loads with correct title.
2. Workspace tab `#modelViewTab` toggles.
3. Workspace tab `#spriteViewTab` toggles.
4. Workspace tab `#entityViewTab` toggles.
5. Workspace tab `#resourceViewTab` toggles.
6. View controls popover, visibility toggles, and zoom controls are usable.
7. Explorer and inspector dock collapse toggles are wired.
8. File, folder, and HQR picker controls are present.
9. Server path invalid load reports an error.
10. Catalog indexes the canonical asset root through the UI.
11. Candidate assets cover all route families present in the catalog.
12. Catalog filter `all` shows entries.
13. Catalog filter `model` shows entries.
14. Catalog filter `animation` shows entries.
15. Catalog filter `sprite` shows entries.
16. Catalog filter `scene` shows entries.
17. Catalog filter `resource` shows entries.
18. Model asset selection renders model and export controls.
19. Export action writes an evidence artifact.
20. UV inspector promotes model surface selections.
21. Usage strip and entity workflow work for a usage-rich model.
22. Scene evidence dock tables and scene object promotion work.
23. Resource route `sample audio` renders.
24. Resource route `background grid` renders.
25. Resource route `background brick` renders.
26. Resource route `background cube` renders.
27. Resource route `GRM fragment` renders.
28. Resource route `palette` renders.
29. Resource route `indexed image` renders.
30. Resource route `screen image` renders.
31. Resource route `texture atlas` renders.
32. Resource route `File3D table` renders.
33. Resource route `sprite ZV table` renders.
34. Resource route `offset table` renders.
35. Resource route `fixed table` renders.
36. Resource route `ext size info` renders.
37. Resource route `holomap plan` renders.
38. Resource route `holomap globe` renders.
39. Resource route `text order` renders.
40. Resource route `text payload` renders.
41. Resource route `smacker video` renders.
42. Raw sprite and ANIM3DS specialty routes render.
43. Inspector search filters visible sections without breaking selection.
44. Browser console has no recent fatal app errors.
45. Startup state renders a valid empty or cached catalog state.
46. Horizon, background, and shade controls change state.
47. Animation picker, transport, and pose inspection work for a compatible model.
48. Runtime sprite resolver resolves default runtime state and opens evidence.
49. Sprite workspace handles single-frame sprite controls and frame inspection.

## Validation Commands

Executed after the browser run:

```powershell
uv run python -m unittest discover -s tests
Set-Location frontend; fnm use 24.15.0; npm run build; Set-Location ..
git diff --check
```

Results:

- `uv run python -m unittest discover -s tests`: 158 tests passed.
- `npm run build` from `frontend/`: passed with the existing Vite large chunk warning.
- `git diff --check`: passed.

## Notes

- The picker buttons were validated as present controls. The automated run did not open OS-native folder/file dialogs because those are outside the browser surface.
- `SPRITES.HQR:127` is a single-frame sprite; previous/next sprite transport disabled state was validated as expected behavior, while zoom/fit and frame selection remained responsive.
- The animation validation uses pose application and inspection for `BODY.HQR:1` plus `ANIM.HQR:100`; the evidence strip is not required to populate for that pose-only interaction.
