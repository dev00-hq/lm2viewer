# LBA2 BODY, ANIM, and ANIM3DS Findings for the Zig Port

This report summarizes what this viewer project has learned about Little Big
Adventure 2 model and animation assets. It is intended for the agent working on
the Zig port of the original game.

## Scope

The findings below cover:

- `BODY.HQR` LM2 body models.
- `ANIM.HQR` skeletal/body animations.
- `ANIM3DS.HQR` projected sprite animation assets.
- `RESS.HQR` data currently needed by the viewer for palettes, textures, and
  File3D animation metadata.

The viewer does not ship game data. All observations come from local user-owned
assets, the original/runtime-derived source references under
`D:\repos\reverse\lba-reference-repos`, and synthetic tests in this repo.

## HQR Indexing Rules

Do not assume all HQR archives use the same indexing convention.

- `ANIM.HQR` uses the regular one-based catalog path in this viewer.
- `BODY.HQR` uses classic zero-based HQR table parsing internally, but catalog
  entries are exposed as one-based body IDs to match user-facing body numbers.
- `ANIM3DS.HQR` uses classic zero-based indexing directly. Entry `0` is the
  first sprite frame. Entry `127` is the `T_ANIM_3DS` frame-range table.

This is a common source of off-by-one bugs. Treat archive identity as part of
the index contract.

## BODY.HQR / LM2 Models

The viewer parses LM2 body models into:

- vertices
- normals
- polygons
- line primitives
- sphere primitives
- bones
- UV groups
- optional palette and texture atlas references

The current viewer scale constant is:

```text
WORLD_SCALE = 0.15
```

The scale is applied to model vertex coordinates, sphere radii, and animation
translation/root motion values when converting decoded game units into viewer
world units.

Important rendering note: line and sphere primitives are real model primitives,
not debug overlays. The viewer renders line cylinders and spheres because the
LM2 data contains those primitive types.

## ANIM.HQR Skeletal Animations

`ANIM.HQR` entries are decoded as skeletal/body animations. The decoded animation
records contain:

- keyframe count
- bone count / boneframe count
- loop start frame
- per-keyframe duration
- per-keyframe root translation
- per-bone raw values

The viewer can sample a BODY model with a decoded ANIM entry and return posed
vertices. The port should preserve the distinction between raw local model
vertices and posed world/viewer vertices.

## Interpolation Rules

Animation interpolation is not simple `elapsed / duration` truncation.

The original behavior recovered for interpolation is:

- A rounded 16.16 interpolation factor is computed like:

```text
((deltaSteps << 16) + ((nbSteps + 1) >> 1)) / nbSteps
```

- Signed linear interpolation then applies signed right shifts.
- Rotations use wrapped 12-bit interpolation, so transitions across `0x000` /
  `0xFFF` must take the shortest wrapped path.

Tested examples:

```text
rotation_lerp_12bit(0x0FF0, 0x0010, 50, 100) == 0
rotation_lerp_12bit(0x0010, 0x0FF0, 50, 100) == 0
signed_lerp_i16(-10, 10, 25, 100) == -5
signed_lerp_i16(10, -10, 25, 100) == 5
signed_lerp_i16(0, -182, 50, 200) == -46
```

Port implication: implement the original integer interpolation path. Floating
point interpolation will produce visible off-by-one differences on real frames.

## Loop Playback Semantics

Looping animations need an explicit synthetic loop segment.

The important case is the transition from the last keyframe back to the loop
start frame. The loop-start frame must interpolate from the last keyframe, not
from itself. Otherwise animations such as Twinsen idle (`ANIM.HQR:66`) snap at
the wrap boundary.

Playback frames are not uniquely identified by `(frame, elapsed_ms)` once this
loop segment exists. A runtime should carry enough sequence identity to
distinguish:

- intro segment frames
- generated loop segment frames
- loop cycle count
- previous frame
- next frame
- timeline position

The viewer uses explicit sequence metadata:

- `sequence_index`
- `segment`
- `loop_index`
- `playback_end_index`
- `loop_cycle_root_delta`

Port implication: model playback as a sequence with an intro phase and a loop
phase, not as a raw modulo over frame numbers.

## Root Motion and World Motion

Some animations translate the actor. The viewer supports multiple presentation
modes, but the useful port distinction is:

- the actor should move in world mode;
- the surface/grid/world should not move with the actor;
- camera following is a viewer concern, not part of the animation data.

When repeating translating animations, root motion must accumulate across loop
cycles. Otherwise the actor snaps back to an earlier root offset when the loop
wraps.

## Animation Compatibility

Compatibility is not just matching bone count.

When File3D metadata is available, `animation_metadata.compatible_body_ids` is
an allow-list for `BODY.HQR` models. The viewer now enforces this on both
frontend filtering and backend animation posing endpoints.

Fallback to bone-count matching is only acceptable when metadata is absent or
the model is not from `BODY.HQR`. In the UI this is marked as `[fb]`.

Concrete failure case:

- Twinsen wizard tunic can share a bone count with unrelated models.
- Bone-count-only filtering can make unrelated animations look selectable.
- File3D metadata prevents those false positives.

Port implication: use File3D/body compatibility metadata when available. Bone
count is a last-resort structural check, not a semantic compatibility rule.

## File3D Metadata

The viewer parses File3D metadata from `RESS.HQR` entry `44`.

The currently useful facts are:

- generic animation names/labels;
- mapping from generic animation IDs to ANIM entries;
- compatible BODY IDs for animations.

Example:

- A generic animation such as walk can map to one or more `ANIM.HQR` entries.
- The same animation entry can list BODY IDs it is intended to animate.

Port implication: keep File3D metadata in the asset pipeline. It is not just UI
label data; it controls animation compatibility.

## ANIM3DS.HQR Is Not BODY Animation

`ANIM3DS.HQR` should not be treated as skeletal BODY animation.

Evidence from the original runtime source:

```c
typedef struct
{
    char Name[4];
    S16  Deb;
    S16  Fin;
} T_ANIM_3DS;
```

The original runtime loads this table from `ANIM3DS.HQR` entry `127`.

The game uses ANIM3DS as projected sprite animation data:

- `ANIM3DS.HQR` frame payloads are sprite/LSP-like frame data.
- `T_ANIM_3DS` groups frame ranges into named sprite animations.
- Track/life opcodes such as `SET_FRAME_3DS`, `START_ANIM_3DS`,
  `WAIT_ANIM_3DS`, and `WAIT_FRAME_3DS` operate on these sprite frame ranges.

Current real asset observation:

- `ANIM3DS.HQR:127` decodes to 13 range records.
- The frame ranges cover frames `0..126`.
- Example records include:
  - `COQU`: frames `0..32`
  - `ROUE`: frames `33..35`
  - `PORT`: frames `36..47`
  - `AERO`: frames `48..53`
  - `VENT`: frames `54..59`

The viewer now classifies ANIM3DS entries as `sprite` assets:

- `anim3ds-info` for entry `127`
- `anim3ds-frame` for individual frame payloads

Port implication: ANIM3DS belongs to the sprite/projected-object rendering path,
not the skeletal model animation path.

## ANIM3DS Frame Range Runtime Behavior

The original source clamps requested frame numbers to the selected range:

```text
if requested_frame > (Fin - Deb):
    requested_frame = Fin - Deb
absolute_frame = requested_frame + Deb
```

This pattern appears in 3DS frame operations such as:

- set frame
- set start
- set end
- wait frame

Port implication: expose animation-local frame numbers to scripting, then map
them to absolute ANIM3DS frame entries with `Deb + local_frame`.

## Texture and UV Notes

The UV inspector is evidence tooling, not an editor.

Important distinctions:

- A polygon is one face/primitive inside a model, not the whole model.
- The texture atlas is shared. Selecting different polygons can show the same
  atlas image because the atlas view is the full texture page; the selected UV
  region is what changes.
- Polygon UV evidence includes material, render flags, UV group, sampled atlas
  region, UV points, sampled colors, and unknown polygon flags.

Port implication: do not infer one texture image per polygon. Treat UVs as
coordinates into shared texture/atlas data.

## Viewer-Specific Behavior Not To Port Directly

Some behavior in this repo is for inspection only:

- camera controls
- horizon lock
- grid/surface rendering
- playback mode choices such as treadmill/world/pose presentation
- UV inspector UI
- evidence JSON/export probes

These are useful for validating decoded data, but not necessarily runtime game
semantics.

## Known Traps

1. Do not use one universal HQR indexing rule.
2. Do not classify ANIM3DS as skeletal animation.
3. Do not use bone count as the primary animation compatibility rule when File3D
   metadata exists.
4. Do not interpolate animation values with floats or direct truncating division.
5. Do not model looping playback as only `frame % frame_count`.
6. Do not move the world/surface when applying actor root motion.
7. Do not treat line and sphere primitives as debug render helpers.
8. Do not treat polygons as models.
9. Do not assume a selected polygon implies a unique texture image; it usually
   points into a shared atlas.

## Recommended Zig Port Priorities

1. Implement HQR parsing with per-archive indexing policy.
2. Implement LM2 BODY geometry, including polygons, lines, spheres, bones, and
   UV groups.
3. Implement `ANIM.HQR` decode with original integer interpolation.
4. Implement playback sequence generation with explicit intro/loop segments.
5. Integrate File3D compatibility metadata before exposing model-animation
   pairing in tooling.
6. Keep ANIM3DS in a separate sprite asset path.
7. Decode/render ANIM3DS LSP sprite frames only after the BODY + ANIM path is
   stable.

## Useful Test Anchors in This Repo

Relevant test files:

- `tests/test_animation_decode.py`
- `tests/test_animation_compatibility.py`
- `tests/test_binary_parsers.py`
- `tests/test_export_probe.py`
- `tests/test_model_contract.py`

Relevant implementation files:

- `lba2_lm2_viewer/animation.py`
- `lba2_lm2_viewer/viewer.py`
- `lba2_lm2_viewer/server.py`
- `frontend/src/compatibility.ts`
- `frontend/src/ui/animationController.ts`
- `frontend/src/ui/catalog.ts`

The tests are often the clearest executable specification for edge cases.
