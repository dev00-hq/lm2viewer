# HQR Coverage Matrix

Generated against:

`<asset-root>`

Last full real-asset catalog audit in this workspace: 15 HQR archives, 22,659
catalog assets, coverage statuses `covered:3`, `partial:11`, `empty:1`, and
629.5 MB peak traced Python allocation. The audit artifact is local-only:
`work-coverage-audit-current.json`.

This matrix is port-oriented. `cataloged` means the archive entry is represented in the catalog with provenance and hashes. `semantic unknown` means the entry still has important runtime semantics that are not decoded even if the top-level payload is classified.

| Archive | Entries | Non-empty | Cataloged | Unknown entries | Semantic unknown | Status | Recognized formats | Unknown formats |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| ANIM.HQR | 2083 | 2082 | 2082 | 0 | 0 | covered | lba2-animation | - |
| ANIM3DS.HQR | 129 | 128 | 128 | 0 | 0 | partial | lsp-sprite-frame, anim3ds-range-table | - |
| BODY.HQR | 470 | 469 | 469 | 0 | 0 | covered | lm2-model | - |
| HOLOMAP.HQR | 47 | 41 | 41 | 0 | 0 | partial | lm2-model, holomap-text-record-links, holomap_globe_uv_map, holomap_globe_altitude_map, holomap_globe_texture_map, holomap_arrow_table, holomap_plan_image_640x480, holomap_plan_view_params | - |
| LBA2.HQR | 1 | 0 | 0 | 0 | 0 | empty | unknown | - |
| LBA_BKG.HQR | 18102 | 18101 | 18101 | 0 | 0 | partial | bkg_header, bkg_grid_map, bkg_grm_fragment, bkg_block_table, bkg_brick_graphic, bkg_cube_map, bkg_block_cell_brk_links, bkg_grid_column_composition | - |
| OBJFIX.HQR | 106 | 99 | 99 | 0 | 0 | covered | lm2-model | - |
| RESS.HQR | 50 | 40 | 40 | 0 | 0 | partial | lm2-model, lba2_palette, ress_offset_record_table, ress_ext_size_info, sprite_zv_table, lba2_texture_atlas_indexed, lba2_indexed_image_256, xpl_palette_bundle, file3d_table, ress_fixed_s16x8_table, acf_name_list | - |
| SAMPLES.HQR | 895 | 606 | 606 | 0 | 0 | partial | sample_wave_audio | - |
| SCENE.HQR | 223 | 222 | 222 | 0 | 222 | partial | scene-runtime-layout-partial, scene-object-movement-info, scene-object-render-pipeline, scene-object-render-contract, scene-runtime-draw-sources, scene-script-opcode-layout, scene-script-behavior-partial, scene-script-operand-semantics-partial, scene-script-execution-contracts, scene-script-condition-functions, scene-script-condition-comparators, scene-script-control-flow-links, scene-script-cross-links, scene-zone-track-patch-layout, scene-patch-instruction-links, scene-patch-field-links, scene-zone-behavior-partial, scene-zone-change-cube-contract, scene-message-facing-gates, scene-zone-bonus-contract, scene-zone-hit-contract, scene-zone-movement-contracts, scene-zone-grm-contract, scene-zone-scenario-contract, scene-text-record-links, scene-sample-audio-links, scene-background-cube-links, scene-grm-fragment-links, scene-video-links | scene-behavior-semantics |
| SCREEN.HQR | 79 | 78 | 78 | 0 | 0 | partial | screen_indexed_image_640x480, screen_palette | - |
| SPRIRAW.HQR | 168 | 167 | 167 | 0 | 0 | partial | raw_sprite_frame | - |
| SPRITES.HQR | 426 | 425 | 425 | 0 | 0 | partial | lsp_sprite_frame | - |
| TEXT.HQR | 181 | 168 | 168 | 0 | 0 | partial | text_order_table, text_payload_bank | - |
| VIDEO/VIDEO.HQR | 34 | 33 | 33 | 0 | 0 | partial | smacker_video | - |

## Runtime Purpose And Next Evidence

| Archive | Runtime purpose | Parser/viewer/export support | Next required evidence |
| --- | --- | --- | --- |
| ANIM.HQR | Skeletal BODY animation records used by runtime generic/action animation slots. | Animation parser, model-canvas playback with compatible BODY, animation evidence JSON. | Broaden real-asset sampling for unusual animation flags and root-motion edge cases. |
| ANIM3DS.HQR | Projected 3D sprite animation frames plus the classic T_ANIM_3DS range table. | LSP sprite decode, range table decode, classic FPS-driven playback rule from scene object state and `TM_*_3DS` track controls, Sprite View, per-frame PNG plus deterministic sheet export for a selected range. | Use live runtime only if a specific ANIM3DS object shows timing behavior that differs from the classic FPS-driven Sprite advancement rule. |
| BODY.HQR | Animated actor BODY meshes referenced by File3D and scene object records. | LM2 model parser, model canvas, UV inspector, OBJ/MTL export. | Audit model flags with live runtime usage when a flag affects port behavior. |
| OBJFIX.HQR | Fixed object LM2 models loaded by `GivePtrObjFix` for extras, darts, inventory/incrust displays, and selected fixed 3D UI objects. | Classic zero-based indexing, LM2 model parser, model canvas, UV inspector, OBJ/MTL export, and 57 direct code-reference ids from `INVENT.CPP`, `COMMON.H`, `DART.H`, and `INVENT.H`. | Broaden direct reference mapping only if remaining anonymous fixed objects become port/editor blockers. |
| SPRITES.HQR / SPRIRAW.HQR | Projected sprite frames selected by runtime Sprite values; `SPRITES.HQR` also carries low system/UI sprite entries addressed directly through `HQRPtrSprite`, and `SPRIRAW.HQR` carries raw extra/projectile/effect sprites addressed through `HQRPtrSpriteRaw`. | Classic zero-based indexing, normal LSP sprite decode for `SPRITES.HQR`, raw scaled sprite decode for `SPRIRAW.HQR`, runtime bounds/hotspots where RESS tables exist, 35 direct code-reference ids from `COMMON.H`/`GAMEMENU.CPP`/`INVENT.CPP` (14 `SPRITES`, 21 `SPRIRAW`), Sprite View, per-frame PNG plus deterministic sheet export. | Broaden direct reference mapping only when a port/editor feature needs remaining anonymous ids; the known system, extra, projectile, currency, and effect ids are now explicit. |
| SCENE.HQR | Scene runtime payloads: world header, ambience, hero start/scripts, objects, zones, waypoints, and patches. | Partial top-level parser, object-to-asset links, object render-pipeline flag semantics, scene-level render frame order, object draw/recovery contract evidence from `AffScene`/`AffOneObject`, script-reference-to-asset links through File3D where evidence is unambiguous, script sample links to `SAMPLES.HQR`, script ACF/movie links to `VIDEO/VIDEO.HQR`, scene runtime cube links to `LBA_BKG.HQR` TabAllCube/GRI/BLL/GRM and `ChoicePalette` XPL entries, scene GRM zone links to concrete `LBA_BKG.HQR` fragments, script-local object/waypoint/zone links, same-script control-flow target checks, scene-context cross-script target checks, patch-to-instruction and patch-to-field target checks, reverse scene-usage index, structural track/life opcode classification, script mechanic categories, selected operand semantics, partial zone behavior semantics, structural waypoint/patch classification, catalog detail, scene background Sprite View variants, and scene background composition export variants. | Continue promoting script/zone execution semantics where evidence supports it; renderer work still needs live pixel-level confirmation for final object/decor overdraw, but catalog evidence now names the classic redraw contract, dynamic runtime draw sources, and preview limitation explicitly. |
| RESS.HQR | Shared palette, XPL ambience palette bundles, texture atlas, File3D table, sprite ZV tables, indexed image payloads, RESS_FLOW/RESS_POF/RESS_IMPACT runtime effect tables, ACF movie list, exterior sizing info, and mixed resources. | First-class catalog entries for palettes, XPL bundles, texture atlas, indexed 256x256 images, File3D, sprite ZV tables, named RESS_FLOW fixed signed-word table, named RESS_POF/RESS_IMPACT offset-record tables, ACF movie list, exterior sizing info, raw unclassified payload evidence for future unknowns, sparse model entries where LM2 auto-detection succeeds, scene-derived XPL palette selection counts, Sprite View previews for indexed image/texture-atlas payloads, and PNG export for indexed image payloads. | Confirm XPL shade/fog/transparency internals only if renderer-level palette effects become necessary. |
| HOLOMAP.HQR | Holomap globe, plan-screen, marker/objective, and vehicle/arrow model resources. | Classic zero-based indexing; decodes globe UV map, globe altitude maps, globe texture maps, `T_ARROW` marker table with GAME text links, plan-screen images, plan view parameter records with classic field names, LM2 model entries, Sprite View plan-image previews with `RESS.HQR:0`, and PNG export for plan-screen images. | Promote holomap globe rendering only if the port needs original globe projection behavior beyond decoded source tables. |
| SCREEN.HQR | Menu/logo/slate screen resources stored as paired indexed framebuffers and palettes. | Uses classic zero-based PCR indexing; classifies even 640x480 indexed framebuffer payloads and odd 768-byte RGB palettes with pair provenance, attaches named PCR direct code-reference provenance for menu/logo/slate call sites, previews indexed images with paired PCR palettes in Sprite View, and exports paired-palette PNGs with manifests. | Broaden SCREEN call-site provenance only if UI port work needs dynamic ListArdoise/help-screen selection rules. |
| LBA_BKG.HQR | Background grid archive: header ranges, cube grid maps, GRM fragments, block tables, brick graphics, and cube indirection. | Classic zero-based indexing; catalog detail decodes `T_BKG_HEADER`, `T_GRI_HEADER`/column offsets and compressed 64x25x64 column composition, GRM dimensions/cell composition, BLL block tables with cell-to-BRK links, BRK `AffGraph` command streams, Sprite View previews individual BRK graphs with an explicit palette-context caveat, `T_TABALLCUBE` cube-to-grid links, GRI composition JSON export, scene background composition variant exports, and 640x480 evidence preview PNGs. | Confirm remaining object/decor overdraw and z-buffer/mask passes before treating previews as final renderer output. |
| TEXT.HQR | Dialogue/text resources grouped by language and text file. `InitDial(file)` loads a paired order table and text bank. | Classic zero-based indexing; catalog detail decodes BufOrder message-id tables and BufText offset/flag/string banks, sampled text previews, reverse scene usage on linked text banks, holomap arrow message links to GAME text records, and JSON export for text payload banks with paired order-table provenance. | Connect remaining menu/inventory calls to concrete language/file/message records if port UI provenance needs call-site links. |
| SAMPLES.HQR | Audio samples loaded by zero-based runtime sample IDs. | Decodes classic HQR compression, parses RIFF/WAVE metadata, reverse-indexes scene script/ambience usage, audits referenced missing ids against archive slots with reason counts, previews decoded WAVE payloads in the browser, and exports decoded WAV files with manifests. | Local extracted/reference variants all have the same empty referenced slots; add PCM decode only if consistent waveform tooling becomes necessary. |
| VIDEO.HQR | Smacker/ACF cinematic resources selected by zero-based names from `RESS.HQR:48`. | Decodes HQR resource headers and Smacker container headers, names entries through the ACF list, exposes catalog detail, reverse-indexes scene `PLAY_ACF` script refs, and exports original Smacker containers with ACF/header/scene provenance. | Add codec frame/audio decode only if port video playback work needs decoded frames or audio tracks. |

## SCENE.HQR Reconnaissance

Classic evidence comes from `LoadScene` in `littlebigreversing/reference/lba2-classic/SOURCES/DISKFUNC.CPP`: the runtime loads `scene.hqr` entry `numscene + 1`, then reads world fields, ambience, hero start and scripts, object records, checksum, zones, waypoint tracks, and patch count.

Current parser status:

- Catalogs all 222 non-empty scene entries as `scene` assets.
- Preserves source HQR index, offsets, raw byte length, raw SHA-256, decoded byte length, and decoded SHA-256.
- Extracts top-level counts and offsets: world header, ambience, hero script byte ranges and SHA-256 hashes, object count, sampled object records with track/life script byte ranges and SHA-256 hashes, sprite/ANIM3DS object counts, zone count, waypoint count, and patch count.
- Names scene environment and ambience fields from `DISKFUNC.CPP::LoadScene`, `AMBIANCE.CPP`, `OBJECT.CPP`, and `PERSO.CPP`: `Island` selects planet/text/island/palette context, `CurrentCubeX/Y` are classic 3DExt cube coordinates, `ShadowLevel` and `ModeLabyrinthe` affect shadow/object rendering, `CubeMode` participates in fade/sample-stop and interior/exterior selection, `AlphaLight`/`BetaLight` feed `SetLightVector`, four ambience sample slots use repeat/random/frequency/volume fields, `SecondMin`/`SecondEcart` schedule ambience with `TimerRefHR`, and `CubeJingle=255` is the no-music sentinel. The byte read into local `n` after `CubeMode` is preserved as an explicit no-source-backed-use field.
- Names scene object runtime record fields from classic `COMMON.H` and `DISKFUNC.CPP`: render backend, flags, option flags, collision toggles, movement mode, initial beta, scene-vs-runtime SRot conversion, combat/life fields, and bonus fields. Real render distribution: 2,104 body models, 747 projected sprites, and 42 ANIM3DS projected sprites. Real movement distribution: 2,599 `NO_MOVE`, 222 `MOVE_PINGOUIN`, 51 `MOVE_FOLLOW`, 6 `MOVE_WAGON`, 5 `MOVE_SAME_XZ_BETA`, 5 `MOVE_CIRCLE`, 4 `MOVE_CIRCLE2`, and 1 `MOVE_SAME_XZ`. Common object flags: 1,498 `CHECK_OBJ_COL`, 1,365 `NO_SHADOW`, 1,321 `CHECK_BRICK_COL`, 959 `OBJ_FALLABLE`, 789 `SPRITE_3D`, 518 `CHECK_ZONE`, 510 `NO_CHOC`, 462 `INVISIBLE`, 295 `CHECK_CODE_JEU`, and 262 `OBJ_CARRIER`. Real option flags: 832 `EXTRA_GIVE_LIFE`, 710 `EXTRA_GIVE_MAGIC`, 253 `EXTRA_GIVE_MONEY`, 101 `EXTRA_GIVE_KEY`, 66 `EXTRA_GIVE_CLOVER`, and 19 `EXTRA_GIVE_NOTHING`.
- Names object render-pipeline flag effects and redraw contract from classic `COMMON.H`, `OBJECT.CPP::AffScene`/`AffOneObject`, `GERELIFE.CPP::LM_BACKGROUND`/`LM_SHADOW_OBJ`, and `GERETRAK.CPP::TM_BACKGROUND`:
  - `OBJ_BACKGROUND` means the object can be copied into the screen/background pass after it draws; script and track opcodes can toggle it.
  - `OBJ_BACKGROUND` objects are projected only for presence and skip `TreeInsert` during object-only redraws; on all-scene redraws they copy their drawn rectangle from `Log` to `Screen`.
  - `OBJ_ZBUFFER`/`OBJ_IN_WATER` skip normal `DrawRecover`/`DrawRecover3` masking and add the drawn box to moving regions only for visible body objects and non-clipped projected sprites.
  - `SPRITE_CLIP` makes projected sprites draw through a fixed `Info..Info3` clip rectangle.
  - `SPRITE_CLIP` wins over z-buffer/water flags for sprite recovery and uses `LastAnimStep` with `DrawRecover3`; `ANIM_3DS` projected sprites also recover through `DrawRecover3` instead of moving-box recovery.
  - `NO_PRE_CLIP` inserts the object with `SORT_NO_PRECLIP`; `INVISIBLE` skips normal draw; `NO_SHADOW` suppresses shadow insertion.
  - Real flag-effect distribution: 1,528 objects cast shadows when global shadow rendering is active, 1,365 suppress shadows, 462 skip normal draw as invisible, 238 use fixed sprite clip rectangles, 118 carry z-buffer/water flags, 114 effectively use z-buffer/water moving-box behavior, 107 use background incrust copy behavior, and 82 bypass normal preclip sorting.
  - Real render-contract distribution after invisible/background skips: 2,431 objects reach camera preclip and `TreeInsert`, 462 skip before tree insertion as invisible, 107 have the object-only background presence probe, 2,352 use normal tree-sort insertion, 79 use `SORT_NO_PRECLIP`, 1,704 draw through `ObjectDisplay`, 689 draw through projected `PtrAffGraph`, 38 draw through projected ANIM3DS `AffGraph`, 1,594 recover through `DrawRecover` masking, 486 recover through object-corner `DrawRecover3`, 237 recover through `LastAnimStep` `DrawRecover3`, 114 use `DrawOverBrickCage` plus `BoxMovingAdd`, and 105 copy the drawn rectangle from `Log` to `Screen` on all-scene redraws.
  - Scene detail also aggregates object redraw method counts (`DrawRecover`, `DrawRecover3`, and `DrawOverBrickCage + BoxMovingAdd`) so mask/z-buffer obligations are visible without drilling into every object record.
  - Scene-level frame contract names the classic `AffScene` order: `AFF_ALL` resets/refreshes decor into `Log` and copies `Log` to `Screen`; scene objects insert first; runtime `ListExtra`, `ListDart`, and `ListPartFlow` entries insert into the same sorted tree after scene objects; `BaseSort` draws the sorted tree and can restart a full redraw if the followed object is fully masked; exterior rain and `ListIncrustDisp` overlays draw after the sorted tree. The catalog exposes each dynamic runtime source as structured evidence with its owner, insertion stage, sorted-tree type, asset backing, and preview/export limitation. These dynamic lists are not serialized in `SCENE.HQR`, so they remain render-order requirements rather than scene-owned records.
- Names port-relevant object movement `Info` semantics from classic `OBJECT.CPP`, `GERELIFE.CPP`, and `WAGON.CPP`: `MOVE_FOLLOW`, `MOVE_SAME_XZ`, and `MOVE_SAME_XZ_BETA` use `Info3` as a target object id; `MOVE_CIRCLE` and `MOVE_CIRCLE2` use `Info3` as a waypoint id and rewrite `Info`, `Info1`, and `Info2` as radius/origin-angle/timer runtime state; `MOVE_WAGON` uses all four `Info` fields as rail-turn runtime state; `MOVE_PINGOUIN` uses `Info`/`Info1` for timeout/display runtime state. Real movement references: 51 `MOVE_FOLLOW.target_object_id`, 5 `MOVE_SAME_XZ_BETA.target_object_id`, 1 `MOVE_SAME_XZ.target_object_id`, 5 `MOVE_CIRCLE.circle_waypoint_id`, and 4 `MOVE_CIRCLE2.circle_waypoint_id`; all resolve inside the current scene objects/waypoints. Real movement state fields: 222 each for `MOVE_PINGOUIN.pingouin_timeout_timer_ref` and `MOVE_PINGOUIN.pingouin_incrust_display_id`, 6 each for wagon turn fields, 5 each for `MOVE_CIRCLE` radius/origin-angle/timer fields, and 4 each for `MOVE_CIRCLE2` radius/origin-angle/timer fields.
  - Scene detail aggregates object collision participation, `SRot` conversion paths, and combat/bonus initialization counts so ports can quickly see which scenes need object/brick/zone/code-jeu/floor collision handling, which objects use sprite/wagon direct rotation versus the non-sprite `51200 / SRot` divisor, and which objects start alive, armored, damaging, or bonus-bearing.
- Classifies SCENE mechanics records:
  - 3,285/3,285 zone records decode as classic `T_ZONE` bounds, eight registers, type, and value.
  - Real zone type distribution: 610 change-cube, 600 camera, 1,155 scenario, 39 fragment/GRM, 483 giver, 214 message, 50 ladder, 2 escalator, 115 hit, and 17 rail zones.
  - Zone behavior effects are partially named from classic `LoadScene`, `CheckZoneSce`, `GereZoneChangeCube`, `SetZoneCamera`, `GereZoneMessage`, `ZoneGiveExtraBonus`, `LM_SET_GRM`, `LM_SET_CHANGE_CUBE`, `LM_SET_CAMERA`, `LM_ECHELLE`, `LM_ESCALATOR`, `LM_SET_HIT_ZONE`, and `LM_SET_RAIL` evidence.
  - Zone records now distinguish serialized scene bytes from runtime post-load state: change-cube/camera `Info7` init/on/active/mandatory flags are normalized exactly as `LoadScene` does, change-cube `Info5`/`Info6` one-bit authoring flags are promoted to `ZONE_TEST_BRICK` and `ZONE_DONT_REAJUST_POS_TWINSEN`, ladder/rail `Info1` is shown after copying `Info0`, giver `Info2` is shown as reset, and hit-zone `Info3` timer refs are shown as cleared before gameplay.
  - Change-cube zones now expose the `GereZoneChangeCube` application contract: enabled/life gates, optional decor-collision gate, exterior edge gates, `NewCube`/`NewPosX/Y/Z` computation, beta rotation from `Info3`, `FlagReajustPosTwinsen` behavior from `Info6`, success via `FlagChgCube=1`, and `LM_SET_CHANGE_CUBE` toggling `Info7` by `Info4`.
  - GRM fragment zones now expose the `LM_SET_GRM` runtime contract: match `Type==3`/`Num`, call `IncrustGrm` on off-to-on transitions, call `DesIncrustGrm` on on-to-off transitions, write `Info2` after the optional call, load fragments from `Grm_Start + My_Grm + Info0`, copy or restore BufCube spans, and set `FirstTime = AFF_ALL_FLIP`.
  - Scenario zones now expose the `ZoneSce` contract: `CheckZoneSce` resets `ptrobj->ZoneSce` to `-1`, type 2 zones write `zone.Num`, `LF_ZONE` reads the current object's field, and `LF_ZONE_OBJ` reads another object's field by script operand.
  - Camera zones now expose the `SetZoneCamera` application contract: `CameraZone`/`FlagCameraForcee`, `StartXCube`/`StartYCube`/`StartZCube`, the interior-only focus update rule, and the exterior `AlphaCam`/`BetaCam`/`GammaCam`/`VueDistance` update rule.
  - Message zones with `Info1` now link to the camera zone whose `Num` matches that value, matching `GereZoneMessage` behavior before `Dial()`. Their facing gate also preserves the source-backed north/south/east/west `GetAngle2D` point pairs, `Obj.Beta` condition, south wrap-around case, speaker/palette setup, and `Dial(zone.Num, TRUE)`.
  - Giver zones now expose the `ZoneGiveExtraBonus` application contract: `ActionNormal==1` hero trigger, `Info2` already-taken gate, `WhichBonus(Info0)` selection from bonus flags, zone-center/`Y1` `ExtraBonus` spawn call, `Info1` count field, and the successful-spawn mutation that sets `EXTRA_TIME_IN` and `Info2=1`.
  - Hit zones now expose the source-backed runtime contract: `Info1` is the hit force/enabled field, `Info2*5*20` is the cooldown duration added to `TimerRefHR`, `Info3` is the active timer reset on load and cleared when elapsed, `HitObj(numobj,numobj,Info1,Obj.Beta)` is gated by positive life points, and `LM_SET_HIT_ZONE` writes `Info1`.
  - Ladder, escalator, and rail zones now expose movement contracts: ladders assign `PtrZoneClimb` and gate climb/fall animation state through `Info1`/`CF_CLIMB`; escalators map `Info2` directions to `CJ_ESCALATOR_*<<4` and set `DONT_PICK_CODE_JEU`; rail zones assign wagon `PtrZoneRail`, use post-load `Info1` active state, and are controlled by `LM_SET_RAIL`.
  - Scene detail now aggregates `zone_runtime_contract_counts`, so port work can quickly see which source-backed zone contracts are represented in a scene without inspecting every sampled zone row.
  - Real zone effect distribution: 610 change-cube transitions, 600 camera zones, 1,155 scenario-zone assignments, 39 GRM fragment toggles, 483 bonus giver zones, 214 message zones, 50 ladder climb zones, 2 escalator/conveyor zones, 115 hit zones, and 17 wagon rail zones.
  - 4,367/4,367 waypoint records decode as classic `T_TRACK` x/y/z points.
  - 12,548/12,548 patch records decode as classic `T_PATCH` size/offset pairs; all point into decoded track/life script byte ranges.
  - Patch target distribution: 10,235 track script patches and 2,313 life script patches. Patch sizes observed: 2,442 one-byte, 2,170 two-byte, and 7,936 four-byte patches.
  - Patch target offsets now resolve to containing script instructions where possible. Real distribution: 12,537 resolved instruction targets, 11 unresolved/non-instruction targets retained as evidence, 10,235 operand-byte patches, and 2,302 opcode-byte patches. Most common patched opcodes are `TM_WAIT_NB_DIZIEME` (5,803), `LM_SWIF` (1,795), `TM_ANGLE` (1,597), `TM_WAIT_NB_SECOND` (1,182), `TM_WAIT_NB_DIZIEME_RND` (653), and `LM_ONEIF` (507).
  - Patch target bytes now resolve to instruction fields where evidence supports the byte layout. Real field distribution: 7,936 `runtime_timer_ref`, 2,302 `opcode`, 1,597 `target_beta_runtime_flag`, 348 `runtime_face_beta`, 225 `runtime_target_beta`, 129 `current_count`, and 11 unknown/non-instruction fields retained as evidence. Field source distribution: 10,235 classic track-runtime fields from `GERETRAK.CPP` behavior, 2,302 script opcode bytes, and 11 unknowns. Most common patched instruction fields are `TM_WAIT_NB_DIZIEME.runtime_timer_ref` (5,803), `LM_SWIF.opcode` (1,795), `TM_ANGLE.target_beta_runtime_flag` (1,597), `TM_WAIT_NB_SECOND.runtime_timer_ref` (1,182), `TM_WAIT_NB_DIZIEME_RND.runtime_timer_ref` (653), `LM_ONEIF.opcode` (507), `TM_FACE_TWINSEN.runtime_face_beta` (348), `TM_WAIT_NB_SECOND_RND.runtime_timer_ref` (298), `TM_ANGLE_RND.runtime_target_beta` (225), and `TM_WAIT_NB_ANIM.current_count` (129).
- Classifies all real sampled hero/object track and life script byte blobs structurally:
  - 3115/3115 track scripts decode to known `TM_*` opcodes.
  - 3115/3115 life scripts decode to known `LM_*` byte layouts.
  - Script metadata includes command count, decoded bytes, first instructions, unique opcodes, mechanic categories, selected operand semantics, and typed references for bodies, animations, sprites, waypoints, script offsets, labels, objects, text ids, variables, inventory ids, sample/music ids, behavior ids, palette/PCX ids, holomap ids, buggy ids, zone controls, and cube targets.
  - Selected operand semantics expose port-relevant fields for high-value opcodes, including body ids, animation ids, waypoint ids, sprite ids, script offsets, track labels, camera zone toggles, change-cube control toggles, GRM/rail/hit/escalator-zone toggles, movement modes with exact follow-object vs circle-waypoint parameters, frames, 3DS animation FPS, dialogue text ids, dialogue speaker/target variants, choice append/ask/reset state, bubble/end-message controls, cube targets, game/cube variable writes and deltas, inventory state, behavior/lifecycle fields, collision/combat object ids and values, sample/music ids and parameter commands, palette/PCX/effect fields, switch/case test operands, and life condition function/comparator/test operands. Raw operand bytes remain available for every instruction.
  - Scene detail now aggregates life-script condition function counts, return-type counts, and comparator counts, so a port can see which `LF_*` runtime readers and `LT_*` tests a scene depends on without inspecting every condition instruction. This is still decoded-operand evidence, not branch execution.
  - Promotes additional execution/runtime opcodes from classic `GERELIFE.CPP` and `GERETRAK.CPP` evidence: object death side effects (`LM_SUICIDE`, 1,705 real uses, and `LM_KILL_OBJ`, 364, clear body/zone/life points), life termination/return markers (`LM_END_COMPORTEMENT` 8,072, `LM_END` 3,094, `LM_END_LIFE` 646, `LM_RETURN` 534), switch structure markers (`LM_END_SWITCH` 654, `LM_DEFAULT` 282), track stop/restore (`LM_STOP_L_TRACK` 613, `LM_RESTORE_L_TRACK` 449, `LM_STOP_L_TRACK_OBJ` 14, `LM_RESTORE_L_TRACK_OBJ` 1, `TM_END` 3,115, `TM_STOP` 4,837), track comments (`TM_REM` 1,906), animation waits (`TM_WAIT_ANIM` 3,197), 3DS animation stop/wait (`TM_STOP_ANIM_3DS` 27, `TM_WAIT_ANIM_3DS` 29), hero save/restore (`LM_SAVE_HERO` 109, `LM_RESTORE_HERO` 116), body hiding (`LM_NO_BODY` 323, `TM_NO_BODY` 33), current/object behavior save/restore (`LM_SAVE_COMPORTEMENT` 50, `LM_RESTORE_COMPORTEMENT` 38, `LM_SAVE_COMPORTEMENT_OBJ` 5, object variants guarded by positive life points), background incrust/redraw toggles (`TM_BACKGROUND` 111 and `LM_BACKGROUND` 162, which toggle `OBJ_BACKGROUND` and request `AFF_ALL` redraw when the flag changes), ACF playback names (`LM_PLAY_ACF` 90 and `TM_PLAY_ACF`, which restore timers/palette state and request `AFF_ALL` redraw after playback), object impact payloads (`LM_IMPACT_OBJ` 70), track sample parameter writes (`TM_VOLUME` 98, `TM_FREQUENCE` 34, `TM_DECALAGE` 17), slate memo (`LM_MEMO_ARDOISE` 6), and small game-state actions (`LM_INC_CLOVER_BOX` 11, `LM_ACTION` 4, `LM_THE_END` 3, `LM_GAME_OVER` 1, `LM_POPCORN` 1 disabled in the classic source, plus `LM_BRUTAL_EXIT` semantics when present). Scene and script detail now aggregate these as execution-contract counts for object lifecycle, life/track pass control, animation/ANIM3DS waits, body visibility, behavior memory, background incrust redraw, cinematic playback, terminal game flow, and sample parameter control.
  - Track scripts now inventory embedded mutable runtime-state fields whether or not a savegame patch currently points at them. Real distribution: 7,936 `runtime_timer_ref`, 1,597 `target_beta_runtime_flag`, 348 `runtime_face_beta`, 225 `runtime_target_beta`, and 129 `current_count` fields. Instruction-field distribution: `TM_WAIT_NB_DIZIEME.runtime_timer_ref` (5,803), `TM_ANGLE.target_beta_runtime_flag` (1,597), `TM_WAIT_NB_SECOND.runtime_timer_ref` (1,182), `TM_WAIT_NB_DIZIEME_RND.runtime_timer_ref` (653), `TM_FACE_TWINSEN.runtime_face_beta` (348), `TM_WAIT_NB_SECOND_RND.runtime_timer_ref` (298), `TM_ANGLE_RND.runtime_target_beta` (225), and `TM_WAIT_NB_ANIM.current_count` (129). This is sourced from classic `GERETRAK.CPP` behavior, where track instructions store timers, angle progress flags, face-angle caches, random-angle targets, and animation wait counters in operand bytes.
  - All decoded script opcodes map to a mechanic category. Real category distribution across scene scripts: 76,517 control-flow, 24,998 model/animation, 23,445 movement/path, 7,936 timing/wait, 4,718 variables/conditions, 2,751 dialogue/UI, 2,450 object lifecycle, 1,661 audio, 1,330 sprite/3D state, 1,216 visual effects, 1,135 door/background, 1,009 collision/combat, 986 inventory/state, 610 camera, 222 zone/scene control, 26 vehicle, and 4 action-state commands.
  - Same-script byte-offset control-flow operands now resolve to decoded instruction targets for track and life scripts where the target script is known locally. Real distribution after hybrid linear-plus-target life decoding: 43,751 same-script control-flow links, all 43,751 resolved target offsets, and 16,622 track label definitions.
  - Scene-context cross-script operands now resolve `LM_SET_TRACK`, `LM_SET_TRACK_OBJ`, and object behavior-switch targets to the addressed owner track/life script. Real distribution: 11,053 cross-script links, 11,052 resolved target offsets, one `outside_script` target retained as typed evidence (`SCENE.HQR:201` hero `LM_SET_TRACK_OBJ` to object 3 track offset 27684), 10,136 track-script targets, 917 life-script targets, and no missing owner records.
  - Life-script decode now combines linear layout coverage with explicit target resumes. This decodes nested `LM_SWITCH`/`LM_CASE` blocks and skips non-instruction byte islands only when a later known target provides a safe resume point. The only retained skipped-byte evidence is in `SCENE.HQR:198` hero life (90 bytes) and `SCENE.HQR:201` hero life (56 bytes).
  - This is mechanic-category plus selected operand evidence. It does not execute scripts or claim full branch/control-flow semantics.
- Links parsed scene objects back to runtime assets through `RESS.HQR:44` File3D and sprite backend rules:
  - 346 File3D object records available.
  - 2104 BODY references resolved from scene `file3d_index` + `GenBody`.
  - 2104 ANIM references resolved from scene `file3d_index` + `GenAnim`.
  - 789 projected sprite references resolved from scene `Flags` + `Sprite`.
- `SPRIRAW.HQR:0` is present after parsing sprite archives with classic zero-based indexing.
- `SPRIRAW.HQR` entries decode as raw scaled sprite frames: the first 12 bytes carry the raw sprite header prefix plus width, height, and signed draw offsets, followed by `width*height` direct palette-index pixels for `ScaleSprite`.
- `ANIM3DS.HQR:127` is the `T_ANIM_3DS` range table loaded by `PERSO.CPP::LoadListAnim3DS`. The table stores only `Name[4]`, `Deb`, and `Fin`; it has no per-frame timing bytes. Runtime timing comes from scene `ANIM_3DS` object state and track scripts: `DISKFUNC.CPP` reads the object animation number and `Info3`/`SizeSHit` FPS, `OBJECT.CPP` advances `Sprite` from `Deb` to `Fin` using `(abs(Fin-Deb)+1)*1000/NbFps` total time and wraps to `Deb`, while `GERETRAK.CPP` `TM_START_ANIM_3DS`, `TM_STOP_ANIM_3DS`, `TM_WAIT_ANIM_3DS`, and `TM_WAIT_FRAME_3DS` start, stop, and wait on that same sprite-frame state.
- Reverse-indexes linked scene object usage onto catalog assets:
  - 4,987 resolved scene usage refs across 1,013 catalog assets.
  - Usage refs by target kind: 2,104 BODY refs, 2,104 ANIM refs, and 779 projected sprite refs.
- All projected scene sprite refs resolve to catalog assets in the current asset set.
  - 42 scene objects use `ANIM_3DS`; all map their `animation_number` to a decoded `T_ANIM_3DS` range and their `Sprite` value to a frame inside that range.
  - Observed ANIM3DS scene range usage: 11 VENT, 9 AERO, 5 LAVE, 4 ECR5, 3 ECR1, 2 PORT, 2 ROUE, and one each for COQU, DESI, EC_6, ECR2, ECR3, and ECR4.
- Links decoded script references back to catalog assets when classic runtime evidence makes the rule unambiguous:
  - Generic body references from object track/life scripts resolve through the owning object's File3D `SearchBody` table.
  - Generic animation references from object track/life scripts resolve through the owning object's File3D `SearchAnim` table.
  - Sprite references from sprite-object scripts resolve through the normal `SPRITES.HQR` / `SPRIRAW.HQR` / `ANIM3DS.HQR` backend rules.
  - Real resolved script-link distribution: 779 body refs, 5,142 animation refs, and 760 sprite refs, with no missing target assets in the current asset set.
  - Unresolved script references remain as typed raw references instead of guessed asset links.
- Resolves scene dialogue references to `TEXT.HQR` records through the classic `InitDial(START_FILE_ISLAND+Island)` rule:
  - 2,531 distinct script text-id refs resolve to 14,214 localized `TEXT.HQR` record refs across available language banks; 162 script refs remain explicit missing text-id evidence.
  - 214 message-zone refs resolve to 1,236 localized `TEXT.HQR` record refs; 8 zone refs remain explicit missing text-id evidence.
  - Linked text bank assets now expose reverse scene usage for `script_text` and `zone_text`, including scene id, owner/object or zone, text file, language, message id, record index, flag byte, and preview.
- Resolves scene audio references to `SAMPLES.HQR` through the classic zero-based `HQR_Get(HQR_Samples,index)` rule:
  - 788 distinct script sample refs were observed in owner scripts; 628 resolve to decoded sample assets and 160 remain missing-reference evidence.
  - 265 non-negative ambience sample slots were observed; 218 resolve to decoded sample assets and 47 remain missing-reference evidence. `-1` ambience slots are treated as empty sentinels.
- Missing sample ids are classified as empty/undecoded archive slots versus ids outside the loaded `SAMPLES.HQR` table, and the same classified records are retained on the owning script or ambience slot for scene-level inspection.
- Missing sample ids observed from scene refs are: 356, 362, 398, 415, 419, 430, 446, 448, 455, 457, 461, 495, 515, 556, 569, 571, 581, 614, 617, 622, 629, 654, 660, 668, 709, 713, 723, 725, 771, 775, 782, 788, 835, 839, 843, 850, and 894.
- Resolves scene cinematic references to `VIDEO/VIDEO.HQR` through the classic `PLAYACF.CPP::GetNumAcf` rule:
  - `RESS.HQR:48` supplies the whitespace-delimited `.SMK` name list; `GetNumAcf` compares names without extensions and returns the zero-based list position passed to `HQF_Init(PathAcf,n)`.
  - Real audit: 97 script `PLAY_ACF` refs were observed, 95 resolve to decoded Smacker assets, and 2 remain explicit missing-name evidence.
  - The unresolved refs are preserved as raw script strings rather than guessed movie ids; their decoded strings are `CRASHZEL` and hex `03246c05`.
  - Linked movie assets expose reverse scene usage for `script_video`, including scene id, owner/object, script kind, ACF name, zero-based ACF index, frame count, dimensions, and timing estimate.
- Resolves scene runtime cube state to `LBA_BKG.HQR` background resources:
  - `DISKFUNC.CPP::LoadScene(numscene)` loads `SCENE.HQR` entry `numscene+1`; `OBJECT.CPP::ChangeCube` sets `NumCube=NewCube` and calls `PtrInitGrille(NewCube)`; `GRILLE.CPP::InitGrille` indexes `TabAllCube[numcube]`.
  - All 222 retail scene assets resolve to a decoded `TabAllCube` record, with 0 missing cube records.
  - Scene detail now exposes runtime cube, selected GRI/BLL/GRM entries, used-block count, and `ChoicePalette` XPL palette entry. This is the first scene-to-background bridge needed for grid/block preview or export.
  - Linked sample assets expose reverse scene usage for `script_sample` and `ambience_sample`, including scene id, owner/object or ambience slot, sample id, audio format, rate, channel count, bit depth, duration, and ambience repeat/random/frequency/volume fields.
- Resolves scene GRM fragment zones to concrete `LBA_BKG.HQR` overlays:
  - `GRILLE.CPP::IncrustGrm` loads `Grm_Start + GriHeader->My_Grm + zone.Info0`; `GERELIFE.CPP::LM_SET_GRM` matches `zone.Num`, toggles `Info2`, and applies/removes the fragment.
  - Real audit: 21 scenes contain GRM zones; 39/39 fragment zones resolve to decoded `LBA_BKG.HQR` GRM entries, with 0 missing fragment assets and 0 x/z cube-bound failures.
  - Two scene 125 zones resolve to fragments with `y0 + dy = 26`, producing 756 total column-y overflow cells. This is preserved as raw contiguous `BufCube` write evidence because classic `IncrustGrm` uses `memcpy`, rather than being rejected as an impossible bounds error.
  - Linked GRM fragment assets expose reverse scene usage for `grm_fragment`, including scene id, zone index/value, `Info0`, resolved BKG entry, target cell start, fragment dimensions, dimension-match flag, and y-overflow cell count.
- Exports scene background composition variants for port/editor use:
  - Selecting a scene with a resolved background enables export of `scene_background_composition_manifest.v0`.
  - The manifest writes one `base` composition/preview pair and one `grm_zone_*_on` composition/preview pair for each resolved GRM zone. The export policy is explicit: no live script state is guessed.
  - Real E2E validation against `SCENE.HQR:126` produced 4 variants: base plus three GRM-on variants. The exported GRM variants recorded changed-cell counts of 1,543, 642, and 1,582; the two y-spill fragments each preserved 378 overflow cells.
- Previews scene background variants in Sprite View:
  - Loading a scene with a resolved background renders the same base plus explicit GRM-on variants in-app, with scrub/previous/next controls.
  - Sprite facts identify the variant, selected runtime cube, GRI/BLL/GRM entries, changed cells, y-overflow cells, and the no-guessed-live-state policy.
  - Browser E2E against `SCENE.HQR:126` verified the GRM variant loop, export button availability, and a nonblank 640x480 preview canvas for `GRM zone 1 ON`.
- Resolves scene-local script references where the target is inside the same decoded scene payload:
  - Object references resolve to hero/object records.
  - Waypoint references resolve to decoded `T_TRACK` coordinate records.
  - Zone-control references resolve to decoded `T_ZONE` records with expected type and type-match evidence.
  - Real resolved local-link distribution: 3,964 object refs, 4,336 waypoint refs, and 342 zone refs.
- Keeps script execution semantics and remaining unresolved zone field semantics as unknown descriptors. Runtime-state and patch-field meaning is only promoted where instruction layout or classic runtime code supports it; unknown/non-instruction patch targets remain explicit evidence.

Local variant audit:

- A targeted SCENE/SAMPLES audit parsed 222 scene entries without building the full catalog and checked five local `SAMPLES.HQR` copies:
  - `reference/lba2-classic/Common/SAMPLES.HQR`
  - `reference/lba2-classic/Speedrun/Windows/SAMPLES.HQR`
  - `<extracted-assets>/Common/SAMPLES.HQR`
  - `<extracted-assets>/Speedrun/Windows/SAMPLES.HQR`
  - `<asset-root>/SAMPLES.HQR`
- All five sample archives have SHA-256 `d5c770a901da97033b1fff47bd7c993fcb12bc4a4a189e87f2b02be85cc21dc2`.
- The scene set references 230 distinct sample ids: 788 script reference events and 265 ambience reference events.
- 193 referenced sample ids resolve to decoded WAVE payloads.
- The same 37 referenced ids are empty HQR slots in every checked local copy: 356, 362, 398, 415, 419, 430, 446, 448, 455, 457, 461, 495, 515, 556, 569, 571, 581, 614, 617, 622, 629, 654, 660, 668, 709, 713, 723, 725, 771, 775, 782, 788, 835, 839, 843, 850, and 894. None were decode failures or outside-table references.
- Missing ids 419, 614, and 894 are ambience-only in this scene set; the others are referenced from scripts.

Next useful implementation step:

Keep missing sample ids as explicit empty-slot evidence unless a new external/CD variant with non-empty payloads is introduced. For ADPCM entries, keep the original WAVE container unless waveform-level editing or normalized PCM analysis becomes necessary.

## SAMPLES.HQR Audio

Classic evidence comes from `OBJECT.H`, `AMBIANCE.CPP`, `HQFILE.CPP`, and `HQRRESS.CPP`: `GivePtrSample(index)` calls `HQR_Get(HQR_Samples,index)`, `HQ_MixSample` and `HQ_3D_MixSample` pass script/ambience sample ids directly into that function, and `HQF_Init` seeks `index*4` in the HQR offset table. Therefore `SAMPLES.HQR` catalog ids are runtime-zero-based: sample `0` is the first HQR block.

Current parser status:

- Catalogs all 606 non-empty entries as `sample_wave_audio` resources.
- Decodes classic HQR resource compression before parsing the audio container.
- Parses RIFF/WAVE metadata: format tag/name, chunk list, channels, sample rate, byte rate, block align, bit depth, data offset/length, sample frames, duration, and IMA ADPCM samples-per-block/fact count where present.
- Real format distribution: 525 mono 8-bit PCM at 22050 Hz, 63 mono 8-bit PCM at 11025 Hz, 17 mono 4-bit IMA ADPCM at 22050 Hz, and 1 stereo 8-bit PCM at 22050 Hz.
- Retains the classic HQR resource header for each sample: decoded size, compressed size, and compression method.
- Reverse usage is attached to linked sample assets from scene script refs and ambience slots.
- Selecting a decoded sample in the browser exposes an audio control backed by the decoded RIFF/WAVE payload.

Next useful implementation step:

Keep missing scene-referenced sample ids as empty-slot evidence unless a new external/CD variant with non-empty payloads is introduced. For ADPCM entries, keep the original WAVE container unless waveform-level editing or normalized PCM analysis becomes necessary.

## VIDEO.HQR Cinematics

Classic evidence comes from `DEFINES.H` and `PLAYACF.CPP`: `PATH_ACF` points at `VIDEO\VIDEO.HQR`, `InitAcf` loads `RESS.HQR:48` into `ListAcf`, `GetNumAcf(name)` scans the whitespace-delimited name list without extensions, and `PlayAcf` passes that zero-based index to `HQF_Init(PathAcf,n)` before opening the Smacker stream.

Current parser status:

- Catalogs all 33 non-empty `VIDEO/VIDEO.HQR` entries as `smacker_video` resources.
- Treats catalog ids as zero-based runtime ACF indices: `VIDEO/VIDEO.HQR:0` is `ASCENSEU.SMK`, and `VIDEO/VIDEO.HQR:32` is `ZEELP.SMK`.
- Decodes the HQR resource header plus Smacker header fields: magic/version, dimensions, frame count, raw/signed frame-rate field, approximate FPS, duration, flags, and tree size.
- Names every decoded video entry through `RESS.HQR:48`. The name list contains 34 names; `BABY.SMK` has no non-empty payload in the current archive and is retained in file-summary evidence as an ACF name without payload.
- Reverse scene usage is attached to linked movie assets from scene `TM_PLAY_ACF` and `LM_PLAY_ACF` script refs.
- Export writes the original Smacker container bytes plus `smacker_video_export_manifest.v0` with ACF index/name, header metadata, scene usages, source hashes, and an explicit no-codec-decode option.

Next useful implementation step:

Do not implement a custom Smacker codec unless the port needs decoded cinematic frames or audio tracks.

## TEXT.HQR Dialog Tables

Classic evidence comes from `MESSAGE.CPP`: `InitDial(file)` loads `TEXT.HQR[(Language*MAX_TEXT_LANG*2)+(file*2)]` into `BufOrder` and `TEXT.HQR[(Language*MAX_TEXT_LANG*2)+(file*2)+1]` into `BufText`. `FindText(text)` scans `BufOrder` for the requested message id; `GetText` then reads two U16 offsets from `BufText`, treats the first byte of the selected record as `FlagDial`, and exposes the remaining byte string through `PtText`/`SizeText`.

Current parser status:

- Treats `TEXT.HQR` as classic zero-based. Entry 0 is real data, not a hidden table header.
- Catalogs all 168 non-empty entries as first-class resources.
- Decodes even entries as `text_order_table`: U16 message-id lists used by `FindText`.
- Decodes odd entries as `text_payload_bank`: U16 offset table plus flagged dialog byte strings.
- Adds language/file pairing metadata from the classic `TabLanguage`/`ListFileText` order: English, Francais, Deutsch, Espanol, Italiano, and Portugues across `sys`, `cre`, `gam`, and island files `000`..`011`.
- Exposes record counts, ID ranges, paired entry links, flag counts, offset table bounds, page-break marker counts, and sampled CP850 text previews.
- Links scene script dialogue refs and message zones back to localized payload-bank records using the scene `Island` field and classic `START_FILE_ISLAND = 3`.
- Reverse scene usage is attached to linked payload-bank assets, so a text bank can answer which scenes/scripts/zones reference its records.
- Links holomap marker messages to `TEXT.HQR` GAME records: `HOLOGLOB.CPP::HoloMap` calls `InitDial(2)` while `AffHoloMess` reads `TabArrow[].Mess`. Real audit: 72 holomap arrow message refs collapse to 34 unique message ids, all 34 resolve across 204 localized `gam` text records, with 0 missing ids.
- Exports a selected text payload bank as JSON with message ids from the paired order table, `FlagDial` bytes, decoded CP850 text, raw record bytes, hashes, and runtime resolution rules.

Next useful implementation step:

Connect remaining object/menu/inventory calls to specific `TEXT.HQR` language/file/message records if port UI provenance needs call-site links.

## RESS.HQR Resource Tables

RESS now exposes runtime support tables directly in the catalog instead of hiding them as implementation-only side data. `RESS.HQR:0` is the classic palette entry, so the catalog counts it as an additional addressable resource alongside the regular one-based HQR table.

Current parser status:

- Catalogs all 40 non-empty RESS entries as addressable catalog assets: 39 resource assets plus one sparse LM2 model entry (`RESS.HQR:7`).
- Catalogs 39 classified first-class RESS resource assets:
  - `RESS.HQR:0` palette: 768 decoded bytes, 256 RGB colors.
  - `RESS.HQR:1` offset-record table: 256 variable-length records, 1,028-byte offset table, raw record hashes/previews retained.
  - `RESS.HQR:2` exterior size info: four signed 32-bit memory sizing fields from classic `SizeInfo` (`MaxSizeListDecors`, `MaxSizeBodyDecors`, `MaxSizeTexDef`, `MaxTotalBodyDecors`) used by `AdjustHQRMem`.
  - `RESS.HQR:5` normal sprite ZV table: 425 hotspot/bounds records for `SPRITES.HQR`.
  - `RESS.HQR:6` indexed texture atlas: 256x256 bytes with 214 palette indices observed.
  - `RESS.HQR:8` raw sprite ZV table: 167 hotspot/bounds records for `SPRIRAW.HQR`.
  - `RESS.HQR:9` and `RESS.HQR:10` palette-shaped 768-byte payloads, decoded structurally as RGB palettes.
  - 12 generic 256x256 indexed image payloads at `RESS.HQR:11`, `13`-`22`, and `26`; dimensions and palette-index counts are decoded, but runtime purpose remains unknown evidence.
  - 13 XPL ambience palette bundles at `RESS.HQR:27`-`38` and `42`, decoded from classic `XPL_HEADER` evidence with palette/fog/transparency offsets and palette samples. Entries `27`-`37` and `42` are named by classic `COMMON.H`; entry `38` is named from legacy `lba2_ress.hqd` as a shading palette but marked as having no classic `COMMON.H` runtime constant.
  - `RESS.HQR:43` ANIM3DS sprite ZV table: 125 hotspot/bounds records for `ANIM3DS.HQR`.
  - `RESS.HQR:44` File3D table: 346 object records, 619 BODY references, and 2,900 animation references.
  - `RESS.HQR:45` `RESS_FLOW`: 216 fixed records, eight signed 16-bit values per record, loaded into `TabPartFlow`; field semantics unknown.
  - `RESS.HQR:46` `RESS_POF`: 11 variable-length records, 48-byte offset table, loaded into `BufferPof`; raw record hashes/previews retained while field semantics remain unknown.
  - `RESS.HQR:47` `RESS_IMPACT`: 42 variable-length records, 172-byte offset table, loaded into `BufferImpact`; raw record hashes/previews retained while field semantics remain unknown.
  - `RESS.HQR:48` ACF movie list: whitespace-delimited `.SMK` names used by classic `GetNumAcf` and `PlayAllAcf`.
- No non-empty RESS entries are left unclassified at the archive-entry level.
- Prioritizes known RESS resource table identities before generic LM2 auto-detection. This matters because valid-looking table bytes can otherwise be falsely promoted as zero-content or sparse models.
- `RESS.HQR:38` is structurally decoded as an XPL palette bundle based on its payload and legacy `lba2_ress.hqd` descriptor. It has no named classic `COMMON.H` constant, but it is selected by real scenes through `ChoicePalette`: `RESS_XPL0 + Island` reaches entry 38 for island 11. Retail scene palette-link counts are `27:13`, `29:26`, `30:5`, `31:10`, `32:1`, `33:5`, `34:4`, `35:4`, `36:1`, `37:1`, `38:4`, and `42:148`.

Next useful implementation step:

Use Ghidra/runtime evidence only if we need the remaining XPL shade/fog/transparency internals; archive-level runtime selection for entry 38 is now explained by scene island palette selection.

## HOLOMAP.HQR Runtime Tables

Classic evidence comes from `HOLO.H`, `HOLOGLOB.CPP`, and `HOLOPLAN.CPP`. `HOLOMAP.HQR` uses classic zero-based HQR indexing, so catalog ids now match the `HQR_*` constants, including `HOLOMAP.HQR:0`.

Current parser status:

- Catalogs all 41 non-empty `HOLOMAP.HQR` entries.
- Decodes `HOLOMAP.HQR:0` as `holomap_globe_uv_map`: 561 UV pairs, 2,244 bytes, loaded as `HQR_COORMAPP_HMM` and used by `PtrMapping` in `DrawHolomap`.
- Decodes `HOLOMAP.HQR:1`, `3`, `5`, and `7` as `holomap_globe_altitude_map`: 544-byte `.HMT` altitude maps used by `PtrAlt` in `ComputeCoorGlobe`.
- Decodes `HOLOMAP.HQR:2`, `4`, `6`, `8`, and `9` as `holomap_globe_texture_map`: 256x256 indexed `.HMG` maps used by `PtrTextMap`.
- Keeps `HOLOMAP.HQR:10`, `11`, `13`, `14`, and `24` as LM2 model entries where the model parser succeeds.
- Decodes `HOLOMAP.HQR:12` as `holomap_arrow_table`: 305 `T_ARROW` records for objective/island/cube holomap markers, including active/already-asked/exterior flag bits and `Mess` links to `TEXT.HQR` file 2 (`gam`).
  - Real audit: 72 arrow records carry message ids; 34 unique message ids resolve to 204 localized GAME text records with no missing ids.
  - `T_ARROW.ObjFix` is retained as a raw field, but not promoted as a live OBJFIX reference because classic `HOLO.H` says it is free/not used and `HOLOPLAN.CPP` has `DrawObjFix` plus its call commented out.
- Decodes 13 plan-screen images as `holomap_plan_image_640x480` and 13 paired records as `holomap_plan_view_params`.
  - Names the classic plan selection rule from `HOLOPLAN.CPP::InitHoloPlan`: normal plans use `HQR_BEGIN_MAP + 2*ZoomedIsland`, Citadel after `TEMPETE_FINIE` uses variant 12, and Celebration Island after `FLAG_CELEBRATION` uses variant 13.
  - Correctly names plan parameter fields as `orgmx`, `orgmz`, `offx`, `offz`, `alpha`, `beta`, `distance`, `lalpha`, and `lbeta`, then records the render path: load plan image to `Log`, copy it to `Screen`, then overlay sorted arrows/Twinsen/vehicles with `BodyDisplay`.
  - Selecting a plan image renders the 640x480 indexed framebuffer in Sprite View with `RESS.HQR:0`; export writes `holomap_plan_image_export_manifest.v0` plus a PNG.

Next useful implementation step:

Promote holomap globe rendering only if the port needs original globe projection behavior beyond decoded source tables.

## LBA_BKG.HQR Background Runtime Tables

Classic evidence comes from `GRILLE.CPP`, `GRILLE_A.ASM`, `COMMON.H`, and `DEFINES.H`. `LBA_BKG.HQR` uses classic zero-based HQR indexing; entry `0` is the `T_BKG_HEADER` that defines all following ranges.

Current parser status:

- Catalogs all 18,101 non-empty entries.
- Decodes `LBA_BKG.HQR:0` as `bkg_header`: `Gri_Start=1`, `Grm_Start=149`, `Bll_Start=179`, `Brk_Start=197`, `Max_Brk=17903`, and `TabAllCube=18100`.
- Decodes 148 GRI grid-map entries with `My_Bll`, `My_Grm`, used-block bitsets, 4,096 64x64 column offsets, and `GRILLE_A.ASM::DecompColonne` RLE composition streams into 64x25x64 cube cells. For each two-byte cube cell, byte 0 is the 1-based BLL block id; byte 1 is the block cell slot when byte 0 is nonzero, or the transparent collision/code byte when byte 0 is zero, matching `AffGrille`, `GetColBrick`, and `WorldCodeBrick`.
  - Real retail audit: 148/148 GRI maps decode and link to BLL tables, with 0 missing BLL links, 0 invalid block refs, 110,770 active columns, 401,020 occupied block cells, 83,119 transparent code cells, and observed RLE run counts of 681,761 transparent skips, 120,183 literal block runs, and 17,926 repeated block runs.
  - Loading an individual GRI resource through the app now returns the full lightweight cube composition payload for port/editor use: two flat 102,400-cell arrays, one for byte-0 block refs and one for byte-1 block slots or transparent codes, ordered as `((z*64+x)*25)+y`.
  - Loading or exporting an individual GRI resource also produces a 640x480 evidence preview using `AffGrille` z/x/y scan order, `AffBrickBlock` BLL cell lookup, `GRAPH.ASM::AffGraph` hot-point placement, and `Map2Screen` projection. The preview intentionally labels palette and overdraw limitations; individual GRI previews do not include scene object/decor overdraw or mask/z-buffer pass behavior.
- Decodes 30 GRM fragments with dimensions and packed two-byte cube-cell composition in the same byte-0/byte-1 semantics as GRI cells. Fragment cell order follows `IncrustGrm`: for each local z, then local x, copy the local y span into the destination column.
  - The reusable overlay application helper models the ON path as a contiguous `BufCube` write. It intentionally records y-overflow evidence instead of clipping when retail data spills past a nominal 25-cell column.
- Decodes 18 BLL block tables with offset tables, block dimensions, cell counts, collision/code buckets, and direct cell-to-BRK links. BLL `brick_ref` values resolve to `Brk_Start+brick_ref-1`, matching `LoadUsedBrick` before it remaps loaded bricks for `AffBrickBlock`. Real retail audit: 3,071 blocks, 21,537 non-zero cell references, 19,320 per-table unique BRK references, 1,297 references to the forbidden brick, and 0 invalid BRK references.
- Decodes 17,903 BRK entries as background brick graphics used by `LoadUsedBrick`/`AffGraph`; every retail BRK command stream consumes exactly and decodes to a bounded indexed graph. Observed graph dimensions are at most 48x38. The command stream uses a four-byte `dx/dy/hotx/hoty` header, per-line block counts, 6-bit run lengths, transparent skips, literal pixel copies, and repeated-color fills as implemented by `LIB386/SVGA/GRAPH.ASM::AffGraph`. Real run counts are 630,076 transparent skips, 838,306 literal copies, and 619,365 repeated-color fills; no retail BRK uses the ambiguous run-type-3 bit pattern.
- Sprite View can preview a selected BRK entry as an indexed frame. The preview uses the catalog's `RESS.HQR:0` normal palette when available and labels this as preview-only, because gameplay colors come from the active `PtrPal`; classic `ChoicePalette()` selects XPL palettes from `RESS.HQR` by island/interior state after `InitGrille()`.
- Decodes `LBA_BKG.HQR:18100` as `T_TABALLCUBE`, the 256-record cube indirection table used before loading a grid. Cube records now resolve their `Num` field to `Gri_Start+Num` and, where that GRI is present, expose the selected BLL/GRM entries and used-block count.

Next useful implementation step:

Promote the next renderer contract from static scene records into runtime object/decor draw-list behavior: sorted insertions, extra/dart/particle sources, and live redraw triggers that are not serialized in `SCENE.HQR`.

## SCREEN.HQR Screen Assets

Classic evidence comes from `COMMON.H` `PCR_*` constants and menu/slate code in `GAMEMENU.CPP` and `INVENT.CPP`, which load paired screen resources from `SCREEN.HQR`.

Current parser status:

- Parses `SCREEN.HQR` with the classic zero-based HQR table so catalog ids match `PCR_*` constants.
- Catalogs all 78 non-empty `SCREEN.HQR` entries as first-class resource assets.
- Classifies 39 palette payloads by exact 768-byte RGB palette size as `screen_palette`.
- Classifies 39 full-screen indexed payloads by exact 640x480 byte size as `screen_indexed_image_640x480`.
- Attaches PCR pair names where `COMMON.H` gives constants, including logo, bumper, menu, slate, CD-ROM wait, and publisher logo slots.
- Attaches direct code-reference provenance for named PCR call sites such as `ShowLogo`, menu background reloads, inventory slate, CD-ROM wait, and publisher logos.
- Resolves the prior pair-order conflict: even PCR slots are indexed images loaded into screen/log buffers, and odd PCR+1 slots are palettes loaded into `PalettePcx`.
- Selecting an indexed screen image renders the paired-palette 640x480 framebuffer in Sprite View.
- Export writes a PNG plus `screen_indexed_image_export_manifest.v0` with PCR index and palette-pair provenance.

Next useful implementation step:

Broaden SCREEN call-site provenance only if UI port work needs dynamic `ListArdoise` or help-screen selection rules.
