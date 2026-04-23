"""LBA2 ANIM record decoding and frame-step evidence helpers."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "lm2_animation_evidence.v0"
MAX_KEYFRAMES = 20000
MAX_BONEFRAMES = 1024


class AnimationError(ValueError):
    pass


@dataclass(frozen=True)
class AnimationSummary:
    keyframes: int
    boneframes: int
    loop_frame: int
    total_duration: int
    translated_boneframes: int
    can_fall: bool
    byte_length: int

    def to_json(self) -> dict[str, Any]:
        return {
            "keyframes": self.keyframes,
            "boneframes": self.boneframes,
            "loop_frame": self.loop_frame,
            "total_duration": self.total_duration,
            "translated_boneframes": self.translated_boneframes,
            "can_fall": self.can_fall,
            "byte_length": self.byte_length,
        }


@dataclass(frozen=True)
class AnimationBoneFrame:
    mode: int
    value_1: int
    value_2: int
    value_3: int

    @property
    def values(self) -> tuple[int, int, int]:
        return (self.value_1, self.value_2, self.value_3)

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "values": [self.value_1, self.value_2, self.value_3],
            "raw": [self.mode, self.value_1, self.value_2, self.value_3],
        }


@dataclass(frozen=True)
class AnimationKeyframe:
    duration: int
    root_1: int
    root_2: int
    root_3: int
    bones: tuple[AnimationBoneFrame, ...]

    @property
    def root_values(self) -> tuple[int, int, int]:
        return (self.root_1, self.root_2, self.root_3)

    def to_json(self) -> dict[str, Any]:
        return {
            "duration": self.duration,
            "root_delta": [self.root_1, self.root_2, self.root_3],
            "raw_header": [self.duration, self.root_1, self.root_2, self.root_3],
            "bones": [bone.to_json() for bone in self.bones],
        }


@dataclass(frozen=True)
class Lba2Animation:
    keyframe_count: int
    bone_count: int
    loop_start_keyframe: int
    reserved: int
    expected_size: int
    byte_length: int
    trailing_bytes: int
    keyframes: tuple[AnimationKeyframe, ...]

    def summary(self) -> AnimationSummary:
        translated = sum(
            1
            for frame in self.keyframes
            for bone in frame.bones
            if bone.mode != 0
        )
        return AnimationSummary(
            keyframes=self.keyframe_count,
            boneframes=self.bone_count,
            loop_frame=self.loop_start_keyframe,
            total_duration=sum(frame.duration for frame in self.keyframes),
            translated_boneframes=translated,
            can_fall=translated > 0,
            byte_length=self.byte_length,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "keyframe_count": self.keyframe_count,
            "bone_count": self.bone_count,
            "loop_start_keyframe": self.loop_start_keyframe,
            "reserved": self.reserved,
            "expected_size": self.expected_size,
            "byte_length": self.byte_length,
            "trailing_bytes": self.trailing_bytes,
            "summary": self.summary().to_json(),
            "keyframes": [frame.to_json() for frame in self.keyframes],
        }


def parse_lba2_animation(data: bytes) -> AnimationSummary:
    return parse_lba2_animation_records(data).summary()


def parse_lba2_animation_records(data: bytes) -> Lba2Animation:
    if len(data) < 8:
        raise AnimationError("animation is too small")
    keyframe_count, bone_count, loop_start, reserved = struct.unpack_from("<HHHH", data)
    if keyframe_count <= 0:
        raise AnimationError("animation has no keyframes")
    if keyframe_count > MAX_KEYFRAMES or bone_count > MAX_BONEFRAMES:
        raise AnimationError("animation header is outside plausible bounds")
    expected_size = 8 + keyframe_count * (8 + bone_count * 8)
    if expected_size > len(data):
        raise AnimationError(
            f"animation payload is truncated: expected {expected_size} bytes, found {len(data)}"
        )
    if loop_start >= keyframe_count:
        raise AnimationError(
            f"animation loop frame {loop_start} exceeds keyframe count {keyframe_count}"
        )

    cursor = 8
    keyframes: list[AnimationKeyframe] = []
    for _ in range(keyframe_count):
        duration, root_1, root_2, root_3 = struct.unpack_from("<Hhhh", data, cursor)
        cursor += 8
        bones: list[AnimationBoneFrame] = []
        for _ in range(bone_count):
            mode, value_1, value_2, value_3 = struct.unpack_from("<hhhh", data, cursor)
            cursor += 8
            bones.append(AnimationBoneFrame(mode, value_1, value_2, value_3))
        keyframes.append(AnimationKeyframe(duration, root_1, root_2, root_3, tuple(bones)))

    return Lba2Animation(
        keyframe_count=keyframe_count,
        bone_count=bone_count,
        loop_start_keyframe=loop_start,
        reserved=reserved,
        expected_size=expected_size,
        byte_length=len(data),
        trailing_bytes=len(data) - expected_size,
        keyframes=tuple(keyframes),
    )


def previous_frame_index(animation: Lba2Animation, target_frame_index: int) -> int:
    validate_frame_index(animation, target_frame_index)
    if target_frame_index == 0:
        return 0
    return target_frame_index - 1


def next_frame_index(animation: Lba2Animation, frame_index: int) -> int:
    validate_frame_index(animation, frame_index)
    next_index = frame_index + 1
    if next_index >= animation.keyframe_count:
        return animation.loop_start_keyframe
    return next_index


def sample_keyframe_transition(
    animation: Lba2Animation,
    target_frame_index: int,
    elapsed_ms: int,
    previous_index: int | None = None,
    body_bone_count: int | None = None,
) -> dict[str, Any]:
    validate_frame_index(animation, target_frame_index)
    if previous_index is None:
        previous_index = previous_frame_index(animation, target_frame_index)
    validate_frame_index(animation, previous_index)
    if elapsed_ms < 0:
        raise AnimationError("elapsed_ms must be non-negative")
    if body_bone_count is not None and body_bone_count < 0:
        raise AnimationError("body_bone_count must be non-negative")

    target = animation.keyframes[target_frame_index]
    previous = animation.keyframes[previous_index]
    duration = target.duration
    complete = duration <= 0 or elapsed_ms >= duration
    clamped_elapsed = duration if complete and duration > 0 else elapsed_ms
    bone_limit = body_bone_count if body_bone_count is not None else animation.bone_count
    if complete:
        root = list(target.root_values)
        bones = [
            {
                "index": index,
                "mode": bone.mode,
                "values": list(bone.values),
                "source": "target",
            }
            for index, bone in enumerate(target.bones[: body_bone_count])
        ]
    else:
        root = [linear_from_zero(value, elapsed_ms, duration) for value in target.root_values]
        bones = []
        if bone_limit > 0 and previous.bones:
            bones.append(
                {
                    "index": 0,
                    "mode": previous.bones[0].mode,
                    "target_mode": target.bones[0].mode,
                    "values": list(previous.bones[0].values),
                    "source": "previous_held",
                    "interpolation": "root_record_not_interpolated",
                }
            )
        bones.extend(
            sample_bone_transition(index, previous_bone, target_bone, elapsed_ms, duration)
            for index, (previous_bone, target_bone) in enumerate(
                zip(
                    previous.bones[1:bone_limit],
                    target.bones[1:bone_limit],
                ),
                start=1,
            )
        )

    return {
        "target_frame_index": target_frame_index,
        "previous_frame_index": previous_index,
        "next_frame_index": next_frame_index(animation, target_frame_index),
        "elapsed_ms": elapsed_ms,
        "clamped_elapsed_ms": clamped_elapsed,
        "duration_ms": duration,
        "complete": complete,
        "root_delta": root,
        "bone_count": min(animation.bone_count, bone_limit),
        "bones": bones,
        "notes": [
            "Root values are scaled from the target keyframe raw root deltas.",
            "Bone record 0 is held during interpolation; 0040caf0 starts bone interpolation at index 1.",
            "Bone interpolation follows model-viewer 0040ce90/0040cf10 evidence.",
            "Bone values preserve raw ANIM value_1/value_2/value_3 order.",
        ],
    }


def sample_bone_transition(
    index: int,
    previous_bone: AnimationBoneFrame,
    target_bone: AnimationBoneFrame,
    elapsed_ms: int,
    duration_ms: int,
) -> dict[str, Any]:
    mode = previous_bone.mode
    if mode != target_bone.mode:
        raise AnimationError(
            f"animation mode changed from {mode} to {target_bone.mode} in bone {index}"
        )
    if mode == 0:
        values = [
            rotation_lerp_12bit(start, end, elapsed_ms, duration_ms)
            for start, end in zip(previous_bone.values, target_bone.values)
        ]
        interpolation = "wrapped_12bit_rotation"
    elif mode in (1, 2):
        values = [
            signed_lerp_i16(start, end, elapsed_ms, duration_ms)
            for start, end in zip(previous_bone.values, target_bone.values)
        ]
        interpolation = "signed_linear"
    else:
        raise AnimationError(f"unsupported animation mode {mode} in bone {index}")
    return {
        "index": index,
        "mode": mode,
        "target_mode": target_bone.mode,
        "values": values,
        "source": "interpolated",
        "interpolation": interpolation,
    }


def rotation_lerp_12bit(start: int, target: int, elapsed: int, duration: int) -> int:
    if duration <= 0:
        return target & 0x0FFF
    start_12 = start & 0x0FFF
    diff = (target & 0x0FFF) - start_12
    if diff == 0:
        return start_12
    if diff < -0x800:
        diff += 0x1000
    elif diff > 0x800:
        diff -= 0x1000
    return (classic_scaled_delta(diff, elapsed, duration) + start_12) & 0x0FFF


def signed_lerp_i16(start: int, target: int, elapsed: int, duration: int) -> int:
    if duration <= 0:
        return wrap_i16(target)
    diff = target - start
    if diff == 0:
        return wrap_i16(start)
    return wrap_i16(classic_scaled_delta(diff, elapsed, duration) + start)


def linear_from_zero(target: int, elapsed: int, duration: int) -> int:
    if duration <= 0:
        return wrap_i16(target)
    return wrap_i16(classic_scaled_delta(target, elapsed, duration))


def classic_interpolator(elapsed: int, duration: int) -> int:
    if duration <= 0:
        return 0x10000
    return ((elapsed << 16) + ((duration + 1) >> 1)) // duration


def classic_scaled_delta(delta: int, elapsed: int, duration: int) -> int:
    return (delta * classic_interpolator(elapsed, duration)) >> 16


def wrap_i16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def validate_frame_index(animation: Lba2Animation, frame_index: int) -> None:
    if frame_index < 0 or frame_index >= animation.keyframe_count:
        raise AnimationError(
            f"animation frame index {frame_index} exceeds keyframe count {animation.keyframe_count}"
        )


def build_animation_evidence(
    animation: Lba2Animation,
    *,
    source: dict[str, Any],
    sample_frame: int = 0,
    previous_frame: int | None = None,
    elapsed_ms: int = 0,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body_bone_count = None
    body_compatibility = None
    if body is not None:
        body_bone_count = body.get("bone_count")
        if not isinstance(body_bone_count, int):
            raise AnimationError("body compatibility data is missing bone_count")
        body_compatibility = {
            "asset_id": body.get("asset_id"),
            "bone_count": body_bone_count,
            "animation_bone_count": animation.bone_count,
            "bone_count_matches": body_bone_count == animation.bone_count,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "animation": animation.to_json(),
        "body_compatibility": body_compatibility,
        "samples": [
            sample_keyframe_transition(
                animation,
                target_frame_index=sample_frame,
                elapsed_ms=elapsed_ms,
                previous_index=previous_frame,
                body_bone_count=body_bone_count,
            )
        ],
        "evidence": [
            {
                "reference": "dl19_model-viewer ghidra_out animation_helpers_lba2.txt",
                "notes": [
                    "ANIM header and keyframe layout match 00404ca0/model_viewer_decode evidence.",
                    "Frame interpolation follows 0040caf0, 0040ce90, and 0040cf10.",
                ],
            }
        ],
    }


def animation_evidence_to_json(evidence: dict[str, Any]) -> bytes:
    return json.dumps(evidence, indent=2).encode("utf-8") + b"\n"


def write_animation_evidence(evidence: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(animation_evidence_to_json(evidence))
