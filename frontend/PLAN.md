# LM2 Viewer Plan

## Purpose

The LM2 viewer is the working inspection tool for LBA2 body models, animations, palettes, and texture behavior. It should stay useful for reverse engineering while also guiding the future model path in the port.

This viewer is not the final game renderer. It is the reference and exploration surface.

## Authority Model

Use these sources in this order:

1. Original game runtime: behavioral and aesthetic oracle.
2. IDA/JS, classic source, and MBN: evidence for asset layouts, render conventions, state, and edge cases.
3. Viewer and port code: canonical modern implementation.
4. New art pipeline: optional replacement layer that must preserve style and gameplay contracts.

The port should preserve meaningful behavior and asset semantics, not obsolete renderer constraints.

## Current Rules

- Original LM2 assets remain the baseline reference path.
- BODY/ANIM catalog exploration should stay fast and searchable.
- Texture decode follows MBN evidence for offsets, UV byte order, palette source, and V orientation.
- Viewer implementation should be one clean current-state path. Do not add compatibility shims for old local states.
- Visual parity issues need evidence: original or MBN screenshot, decoded model data, and viewer screenshot.

## Modern Asset Direction

Future upgraded models should not be forced into LM2.

Preferred shape:

- LM2 decoder: original game assets and regression reference.
- Modern model loader: likely `glTF/GLB` for replacement assets.
- Shared entity contract: gameplay-facing model id, scale, bounds, attachment points, animation names/events, and collision footprint.

Replacement models may change geometry and texture detail, but they must preserve:

- world scale
- silhouette readability
- costume identity
- low-poly-adjacent LBA2 aesthetic
- animation timing and event semantics
- gameplay footprint and interactions

## Non-Goals

- Recreating every MBN/OpenGL implementation detail in Three.js.
- Treating decompiled code as architecture.
- Making LM2 the only possible future model format.
- Letting upgraded visuals change gameplay behavior.
- Carrying parallel old/new rendering paths without an active comparison task.

## Near-Term Work

1. Add viewer debug tools for texture refs, UV groups, and sampled atlas regions.
2. Capture a small reference set for key BODY entries against MBN/original where possible.
3. Define the first draft of the shared model/entity contract for the port.
4. Decide whether the viewer should expose export helpers for original LM2 geometry and textures.
5. Keep hard-cut cleanup: remove temporary comparison code once an evidence question is settled.

