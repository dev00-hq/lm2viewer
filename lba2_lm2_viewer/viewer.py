#!/usr/bin/env python3
"""View Little Big Adventure 2 LM2 body model files from user-owned HQR archives.

Python decodes HQR/LM2 bytes on demand, then serves a small Three.js page for
orbit/pan/zoom inspection. The package intentionally ships no extracted game
assets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import struct
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from . import lba_hqr
from .animation import (
    AnimationError,
    AnimationSummary,
    Lba2Animation,
    parse_lba2_animation,
    parse_lba2_animation_records,
    sample_keyframe_transition,
)

WORLD_SCALE = 0.15
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ASSET_ROOT = Path(
    r"D:\repos\reverse\littlebigreversing\work\_innoextract_full\Speedrun\Windows\LBA2_cdrom\LBA2"
)
PACKAGE_SUFFIXES = {".hqr"}
FRONTEND_DIST = Path(__file__).resolve().with_name("frontend") / "dist"
ANIM_ARCHIVE_NAME = "ANIM.HQR"
ANIM3DS_ARCHIVE_NAME = "ANIM3DS.HQR"
ANIMATION_ARCHIVE_NAMES = {ANIM_ARCHIVE_NAME, ANIM3DS_ARCHIVE_NAME}
PALETTE_ARCHIVE_NAME = "RESS.HQR"
PALETTE_ENTRY_INDEX = 0
PALETTE_BYTES = 256 * 3
TEXTURE_ENTRY_INDEX = 6
TEXTURE_ATLAS_SIZE = 256
TEXTURE_ATLAS_PIXELS = TEXTURE_ATLAS_SIZE * TEXTURE_ATLAS_SIZE


class Lm2Error(ValueError):
    pass


def parse_multipart_upload(content_type: str, body: bytes) -> dict[str, Any]:
    if "\r" in content_type or "\n" in content_type:
        raise Lm2Error("invalid content-type header")
    header_blob = (f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode(
        "utf-8"
    )
    message = BytesParser(policy=policy.default).parsebytes(header_blob + body)
    if (
        message.get_content_type() != "multipart/form-data"
        or not message.is_multipart()
    ):
        raise Lm2Error("expected multipart/form-data upload")

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "file":
            continue
        data = part.get_payload(decode=True)
        if data is None:
            raise Lm2Error("upload file field could not be decoded")
        filename = part.get_filename() or "upload.lm2"
        return {"filename": filename, "data": data}
    raise Lm2Error("upload did not include a file field")


@dataclass
class DecodeProgress:
    active: bool = False
    phase: str = "idle"
    label: str = ""
    current: int = 0
    total: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def begin(self, label: str, total: int = 0, phase: str = "decoding") -> None:
        now = time.monotonic()
        with self.lock:
            self.active = True
            self.phase = phase
            self.label = label
            self.current = 0
            self.total = total
            self.started_at = now
            self.finished_at = None
            self.error = None
            self.summary = None

    def update(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        label: str | None = None,
        phase: str | None = None,
    ) -> None:
        with self.lock:
            if current is not None:
                self.current = current
            if total is not None:
                self.total = total
            if label is not None:
                self.label = label
            if phase is not None:
                self.phase = phase

    def finish(self, summary: dict[str, Any] | None = None) -> None:
        now = time.monotonic()
        with self.lock:
            self.active = False
            self.phase = "complete"
            if self.total:
                self.current = self.total
            self.label = "Decode complete"
            self.finished_at = now
            self.error = None
            self.summary = summary

    def fail(self, error: str) -> None:
        now = time.monotonic()
        with self.lock:
            self.active = False
            self.phase = "error"
            self.label = "Decode failed"
            self.finished_at = now
            self.error = error

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            elapsed_source = self.finished_at if self.finished_at is not None else now
            elapsed = (
                0.0
                if self.started_at is None
                else max(0.0, elapsed_source - self.started_at)
            )
            percent = (self.current / self.total) if self.total else None
            return {
                "active": self.active,
                "phase": self.phase,
                "label": self.label,
                "current": self.current,
                "total": self.total,
                "percent": percent,
                "elapsed_seconds": elapsed,
                "error": self.error,
                "summary": self.summary,
            }


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.index = 0

    def require(self, size: int) -> None:
        if self.index + size > len(self.data):
            raise Lm2Error(
                f"unexpected end of file at 0x{self.index:x}, need {size} bytes"
            )

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise Lm2Error(
                f"offset 0x{offset:x} is outside file size 0x{len(self.data):x}"
            )
        self.index = offset

    def skip(self, size: int) -> None:
        self.seek(self.index + size)

    def u8(self) -> int:
        self.require(1)
        value = self.data[self.index]
        self.index += 1
        return value

    def u16(self) -> int:
        self.require(2)
        value = struct.unpack_from("<H", self.data, self.index)[0]
        self.index += 2
        return value

    def s16(self) -> int:
        self.require(2)
        value = struct.unpack_from("<h", self.data, self.index)[0]
        self.index += 2
        return value

    def u32(self) -> int:
        self.require(4)
        value = struct.unpack_from("<I", self.data, self.index)[0]
        self.index += 4
        return value

    def s32(self) -> int:
        self.require(4)
        value = struct.unpack_from("<i", self.data, self.index)[0]
        self.index += 4
        return value


@dataclass(frozen=True)
class Lm2Header:
    flags: int
    bounds: tuple[int, int, int, int, int, int]
    bones_count: int
    bones_offset: int
    vertices_count: int
    vertices_offset: int
    normals_count: int
    normals_offset: int
    unknown_count: int
    unknown_offset: int
    polygons_size: int
    polygons_offset: int
    lines_count: int
    lines_offset: int
    spheres_count: int
    spheres_offset: int
    uv_groups_count: int
    uv_groups_offset: int

    @property
    def version(self) -> int:
        return self.flags & 0xFF

    @property
    def has_animation(self) -> bool:
        return bool(self.flags & (1 << 8))

    @property
    def no_sort(self) -> bool:
        return bool(self.flags & (1 << 9))

    @property
    def has_transparency(self) -> bool:
        return bool(self.flags & (1 << 10))


@dataclass(frozen=True)
class Bone:
    parent: int
    vertex: int
    unknown_1: int
    unknown_2: int


@dataclass(frozen=True)
class Vertex:
    x: float
    y: float
    z: float
    bone: int


@dataclass(frozen=True)
class Normal:
    x: float
    y: float
    z: float
    unknown: int


@dataclass(frozen=True)
class Polygon:
    render_type: int
    vertices: tuple[int, ...]
    color: int
    color_word: int
    palette_index: int
    intensity: int
    has_texture: bool
    has_extra: bool
    has_transparency: bool
    texture: int | None
    uv: tuple[tuple[float, float], ...] | None


@dataclass(frozen=True)
class LinePrimitive:
    color: int
    color_word: int
    palette_index: int
    vertex_1: int
    vertex_2: int
    unknown: int


@dataclass(frozen=True)
class SpherePrimitive:
    color: int
    color_word: int
    palette_index: int
    vertex: int
    size: int
    unknown: int


@dataclass(frozen=True)
class UvGroup:
    x: int
    y: int
    w: int
    h: int

    def to_json(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class Lm2Model:
    header: Lm2Header
    bones: tuple[Bone, ...]
    vertices: tuple[Vertex, ...]
    normals: tuple[Normal, ...]
    polygons: tuple[Polygon, ...]
    lines: tuple[LinePrimitive, ...]
    spheres: tuple[SpherePrimitive, ...]
    uv_groups: tuple[UvGroup, ...]
    raw_vertices: tuple[Vertex, ...] = ()

    def to_viewer_json(
        self,
        source_name: str | None = None,
        palette: list[int] | None = None,
        texture_atlas: dict[str, Any] | None = None,
        pose: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw_bounds = self.header.bounds
        xs = [v.x for v in self.vertices]
        ys = [v.y for v in self.vertices]
        zs = [v.z for v in self.vertices]
        bounds = {
            "x": [min(xs, default=0), max(xs, default=0)],
            "y": [min(ys, default=0), max(ys, default=0)],
            "z": [min(zs, default=0), max(zs, default=0)],
            "raw": {
                "x": [raw_bounds[0], raw_bounds[1]],
                "y": [raw_bounds[2], raw_bounds[3]],
                "z": [raw_bounds[4], raw_bounds[5]],
            },
        }
        payload = {
            "source": source_name,
            "format": "lm2",
            "scale": WORLD_SCALE,
            "palette": palette,
            "texture_atlas": texture_atlas,
            "header": {
                "flags": self.header.flags,
                "version": self.header.version,
                "has_animation": self.header.has_animation,
                "no_sort": self.header.no_sort,
                "has_transparency": self.header.has_transparency,
            },
            "stats": {
                "bones": len(self.bones),
                "vertices": len(self.vertices),
                "normals": len(self.normals),
                "polygons": len(self.polygons),
                "lines": len(self.lines),
                "spheres": len(self.spheres),
                "uv_groups": len(self.uv_groups),
            },
            "bounds": bounds,
            "vertices": [[v.x, v.y, v.z, v.bone] for v in self.vertices],
            "uv_groups": [group.to_json() for group in self.uv_groups],
            "polygons": [
                {
                    "vertices": list(poly.vertices),
                    "color": poly.color,
                    "color_word": poly.color_word,
                    "palette_index": poly.palette_index,
                    "intensity": poly.intensity,
                    "render_type": poly.render_type,
                    "has_texture": poly.has_texture,
                    "has_extra": poly.has_extra,
                    "has_transparency": poly.has_transparency,
                    "texture": poly.texture,
                    "uv": [[u, v] for u, v in poly.uv] if poly.uv is not None else None,
                }
                for poly in self.polygons
            ],
            "lines": [
                {
                    "vertices": [line.vertex_1, line.vertex_2],
                    "color": line.color,
                    "color_word": line.color_word,
                    "palette_index": line.palette_index,
                    "unknown": line.unknown,
                }
                for line in self.lines
            ],
            "spheres": [
                {
                    "vertex": sphere.vertex,
                    "size": sphere.size * WORLD_SCALE,
                    "color": sphere.color,
                    "color_word": sphere.color_word,
                    "palette_index": sphere.palette_index,
                    "unknown": sphere.unknown,
                }
                for sphere in self.spheres
            ],
            "bones": [
                {
                    "parent": bone.parent,
                    "vertex": bone.vertex,
                    "unknown_1": bone.unknown_1,
                    "unknown_2": bone.unknown_2,
                }
                for bone in self.bones
            ],
        }
        if pose is not None:
            payload["pose"] = pose
        return payload


def read_header(reader: Reader) -> Lm2Header:
    if len(reader.data) < 0x60:
        raise Lm2Error(
            f"LM2 file is too small for a 0x60-byte header: {len(reader.data)} bytes"
        )
    flags = reader.s32()
    reader.s32()
    x_min = reader.s32()
    x_max = reader.s32()
    y_min = reader.s32()
    y_max = reader.s32()
    z_min = reader.s32()
    z_max = reader.s32()
    values = [reader.u32() for _ in range(16)]
    header = Lm2Header(
        flags=flags,
        bounds=(x_min, x_max, y_min, y_max, z_min, z_max),
        bones_count=values[0],
        bones_offset=values[1],
        vertices_count=values[2],
        vertices_offset=values[3],
        normals_count=values[4],
        normals_offset=values[5],
        unknown_count=values[6],
        unknown_offset=values[7],
        polygons_size=values[8],
        polygons_offset=values[9],
        lines_count=values[10],
        lines_offset=values[11],
        spheres_count=values[12],
        spheres_offset=values[13],
        uv_groups_count=values[14],
        uv_groups_offset=values[15],
    )
    offsets = [
        header.bones_offset,
        header.vertices_offset,
        header.normals_offset,
        header.unknown_offset,
        header.polygons_offset,
        header.lines_offset,
        header.spheres_offset,
        header.uv_groups_offset,
    ]
    for offset in offsets:
        if offset > len(reader.data):
            raise Lm2Error(
                f"section offset 0x{offset:x} exceeds file size 0x{len(reader.data):x}"
            )
    return header


def parse_lm2(data: bytes) -> Lm2Model:
    reader = Reader(data)
    header = read_header(reader)

    reader.seek(header.bones_offset)
    bones = tuple(
        Bone(reader.u16(), reader.u16(), reader.u16(), reader.u16())
        for _ in range(header.bones_count)
    )

    reader.seek(header.vertices_offset)
    raw_vertices = tuple(
        Vertex(
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.u16(),
        )
        for _ in range(header.vertices_count)
    )
    vertices = tuple(
        resolve_vertex(vertex, raw_vertices, bones, index)
        for index, vertex in enumerate(raw_vertices)
    )

    reader.seek(header.normals_offset)
    normals = tuple(
        Normal(
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.u16(),
        )
        for _ in range(header.normals_count)
    )

    reader.seek(header.unknown_offset)
    reader.skip(header.unknown_count * 8)

    polygons = parse_polygons(reader, header)

    reader.seek(header.lines_offset)
    lines: list[LinePrimitive] = []
    for _ in range(header.lines_count):
        unknown = reader.u16()
        color_word = reader.u16()
        color = color_index(color_word)
        lines.append(
            LinePrimitive(
                unknown=unknown,
                color=color,
                color_word=color_word,
                palette_index=color,
                vertex_1=reader.u16(),
                vertex_2=reader.u16(),
            )
        )

    reader.seek(header.spheres_offset)
    spheres: list[SpherePrimitive] = []
    for _ in range(header.spheres_count):
        unknown = reader.u16()
        color_word = reader.u16()
        color = color_index(color_word)
        spheres.append(
            SpherePrimitive(
                unknown=unknown,
                color=color,
                color_word=color_word,
                palette_index=color,
                vertex=reader.u16(),
                size=reader.u16(),
            )
        )

    reader.seek(header.uv_groups_offset)
    uv_groups = tuple(
        UvGroup(reader.u8(), reader.u8(), reader.u8(), reader.u8())
        for _ in range(header.uv_groups_count)
    )

    validate_indices(vertices, bones, polygons, lines, spheres)
    return Lm2Model(
        header,
        bones,
        vertices,
        normals,
        polygons,
        tuple(lines),
        tuple(spheres),
        uv_groups,
        raw_vertices,
    )


def resolve_vertex(
    vertex: Vertex,
    raw_vertices: tuple[Vertex, ...],
    bones: tuple[Bone, ...],
    vertex_index: int,
) -> Vertex:
    if vertex.bone >= len(bones):
        raise Lm2Error(f"vertex {vertex_index} references missing bone {vertex.bone}")
    x, y, z = vertex.x, vertex.y, vertex.z
    seen: set[int] = set()
    next_bone_index = vertex.bone
    while True:
        if next_bone_index in seen:
            raise Lm2Error(f"bone parent cycle while resolving vertex {vertex_index}")
        seen.add(next_bone_index)
        bone = bones[next_bone_index]
        if bone.vertex >= len(raw_vertices):
            raise Lm2Error(
                f"bone {next_bone_index} references missing vertex {bone.vertex}"
            )
        pivot = raw_vertices[bone.vertex]
        x += pivot.x
        y += pivot.y
        z += pivot.z
        if bone.parent > 1000:
            break
        if bone.parent >= len(bones):
            raise Lm2Error(f"bone {next_bone_index} has invalid parent {bone.parent}")
        next_bone_index = bone.parent
    return Vertex(x, y, z, vertex.bone)


Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


def pose_lm2_model(
    model: Lm2Model,
    animation: Lba2Animation,
    *,
    sample_frame: int = 0,
    previous_frame: int | None = None,
    elapsed_ms: int = 0,
) -> tuple[Lm2Model, dict[str, Any]]:
    if animation.bone_count != len(model.bones):
        raise AnimationError(
            "animation bone count "
            f"{animation.bone_count} does not match model bone count {len(model.bones)}"
        )
    local_vertices = model.raw_vertices
    if not local_vertices:
        raise Lm2Error("posing requires local raw vertices")
    if len(local_vertices) != len(model.vertices):
        raise Lm2Error("model raw vertex count does not match resolved vertex count")

    sample = sample_keyframe_transition(
        animation,
        target_frame_index=sample_frame,
        elapsed_ms=elapsed_ms,
        previous_index=previous_frame,
        body_bone_count=len(model.bones),
    )
    bone_samples = {bone["index"]: bone for bone in sample["bones"]}
    root_delta = sample["root_delta"]
    root_matrix = translation_matrix(
        root_delta[0] * WORLD_SCALE,
        root_delta[1] * WORLD_SCALE,
        root_delta[2] * WORLD_SCALE,
    )
    bone_matrices: list[Matrix4 | None] = [None] * len(model.bones)

    for index in range(len(model.bones)):
        build_bone_pose_matrix(index, model, local_vertices, bone_samples, bone_matrices, root_matrix)

    posed_vertices: list[Vertex] = []
    for vertex in local_vertices:
        matrix = bone_matrices[vertex.bone]
        if matrix is None:
            raise Lm2Error(f"missing pose matrix for bone {vertex.bone}")
        x, y, z = transform_point(matrix, (vertex.x, vertex.y, vertex.z))
        posed_vertices.append(Vertex(x, y, z, vertex.bone))

    pose = {
        "animation": {
            "keyframes": animation.keyframe_count,
            "boneframes": animation.bone_count,
            "loop_frame": animation.loop_start_keyframe,
        },
        "sample": sample,
        "transform": {
            "rotation_units": "12bit_turn",
            "rotation_order": "x_y_z",
            "translation_scale": WORLD_SCALE,
            "vertex_space": "lm2_local_vertices_transformed_to_world",
        },
    }
    return replace(model, vertices=tuple(posed_vertices)), pose


def build_bone_pose_matrix(
    index: int,
    model: Lm2Model,
    local_vertices: tuple[Vertex, ...],
    bone_samples: dict[int, dict[str, Any]],
    bone_matrices: list[Matrix4 | None],
    root_matrix: Matrix4,
) -> Matrix4:
    cached = bone_matrices[index]
    if cached is not None:
        return cached
    bone = model.bones[index]
    if bone.vertex >= len(local_vertices):
        raise Lm2Error(f"bone {index} references missing vertex {bone.vertex}")

    if bone.parent > 1000:
        parent_matrix = root_matrix
    else:
        if bone.parent >= len(model.bones):
            raise Lm2Error(f"bone {index} has invalid parent {bone.parent}")
        parent_matrix = build_bone_pose_matrix(
            bone.parent,
            model,
            local_vertices,
            bone_samples,
            bone_matrices,
            root_matrix,
        )

    pivot = local_vertices[bone.vertex]
    matrix = multiply_matrix(
        parent_matrix,
        multiply_matrix(
            translation_matrix(pivot.x, pivot.y, pivot.z),
            animation_bone_matrix(bone_samples.get(index)),
        ),
    )
    bone_matrices[index] = matrix
    return matrix


def animation_bone_matrix(bone_sample: dict[str, Any] | None) -> Matrix4:
    if bone_sample is None:
        return identity_matrix()
    values = bone_sample.get("values")
    if not isinstance(values, list) or len(values) != 3:
        raise AnimationError("sampled bone transform is missing three values")
    mode = bone_sample.get("mode")
    if mode == 0:
        return rotation_xyz_matrix(
            turn12_to_radians(values[0]),
            turn12_to_radians(values[1]),
            turn12_to_radians(values[2]),
        )
    if mode in (1, 2):
        return translation_matrix(
            values[0] * WORLD_SCALE,
            values[1] * WORLD_SCALE,
            values[2] * WORLD_SCALE,
        )
    raise AnimationError(f"unsupported animation mode {mode}")


def identity_matrix() -> Matrix4:
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def translation_matrix(x: float, y: float, z: float) -> Matrix4:
    return (
        (1.0, 0.0, 0.0, x),
        (0.0, 1.0, 0.0, y),
        (0.0, 0.0, 1.0, z),
        (0.0, 0.0, 0.0, 1.0),
    )


def rotation_xyz_matrix(x: float, y: float, z: float) -> Matrix4:
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    rotate_x: Matrix4 = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, cx, -sx, 0.0),
        (0.0, sx, cx, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    rotate_y: Matrix4 = (
        (cy, 0.0, sy, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (-sy, 0.0, cy, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    rotate_z: Matrix4 = (
        (cz, -sz, 0.0, 0.0),
        (sz, cz, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return multiply_matrix(multiply_matrix(rotate_z, rotate_y), rotate_x)


def multiply_matrix(left: Matrix4, right: Matrix4) -> Matrix4:
    return tuple(
        tuple(
            sum(left[row][index] * right[index][column] for index in range(4))
            for column in range(4)
        )
        for row in range(4)
    )  # type: ignore[return-value]


def transform_point(matrix: Matrix4, point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def turn12_to_radians(value: int) -> float:
    return (value & 0x0FFF) * math.tau / 0x1000


def parse_polygons(reader: Reader, header: Lm2Header) -> tuple[Polygon, ...]:
    polygons: list[Polygon] = []
    offset = header.polygons_offset
    end = header.lines_offset
    while offset + 8 <= end:
        reader.seek(offset)
        render_type = reader.u16()
        polygon_count = reader.u16()
        section_size = reader.u16()
        reader.u16()
        if section_size == 0:
            break
        if polygon_count == 0:
            raise Lm2Error(f"polygon section at 0x{offset:x} has zero polygons")
        if offset + section_size > end:
            raise Lm2Error(f"polygon section at 0x{offset:x} exceeds polygon data end")
        block_size = (section_size - 8) // polygon_count
        if block_size <= 0 or (section_size - 8) % polygon_count != 0:
            raise Lm2Error(f"polygon section at 0x{offset:x} has invalid block size")
        item_offset = offset + 8
        for _ in range(polygon_count):
            polygons.append(parse_polygon(reader, item_offset, render_type, block_size))
            item_offset += block_size
        offset += section_size
    return tuple(polygons)


def parse_polygon(
    reader: Reader, offset: int, render_type: int, block_size: int
) -> Polygon:
    reader.seek(offset)
    vertex_count = 4 if render_type & 0x8000 else 3
    mode = render_type & 0x00FF
    textured_size = 32 if vertex_count == 4 else 24
    has_texture = mode >= 8 and block_size >= textured_size
    has_extra = bool(render_type & 0x4000)
    has_transparency = render_type == 2
    if mode >= 8 and 16 < block_size < textured_size:
        raise Lm2Error(
            f"polygon at 0x{offset:x} has ambiguous texture block size {block_size}, expected {textured_size}"
        )
    vertices = tuple(reader.u16() for _ in range(vertex_count))
    texture: int | None = None
    uv: tuple[tuple[float, float], ...] | None = None
    if has_texture:
        texture_offset = offset + (28 if vertex_count == 4 else 6)
        reader.seek(texture_offset)
        texture = reader.u16()
        uv = parse_polygon_uv(reader, offset + 12, vertex_count)
    reader.seek(offset + 8)
    color_word = reader.u16()
    color = color_index(color_word)
    intensity = reader.s16()
    return Polygon(
        render_type,
        vertices,
        color,
        color_word,
        color,
        intensity,
        has_texture,
        has_extra,
        has_transparency,
        texture,
        uv,
    )


def parse_polygon_uv(
    reader: Reader, offset: int, vertex_count: int
) -> tuple[tuple[float, float], ...]:
    reader.seek(offset)
    coords: list[tuple[float, float]] = []
    for _ in range(vertex_count):
        x_high = reader.u8()
        x_low = reader.u8()
        y_high = reader.u8()
        y_low = reader.u8()
        coords.append((x_low + (x_high / 256.0), y_low + (y_high / 256.0)))
    return tuple(coords)


def color_index(encoded: int) -> int:
    return encoded & 0x00FF


def validate_indices(
    vertices: tuple[Vertex, ...],
    bones: tuple[Bone, ...],
    polygons: tuple[Polygon, ...],
    lines: tuple[LinePrimitive, ...],
    spheres: tuple[SpherePrimitive, ...],
) -> None:
    vertex_count = len(vertices)
    for poly_index, poly in enumerate(polygons):
        for vertex_index in poly.vertices:
            if vertex_index >= vertex_count:
                raise Lm2Error(
                    f"polygon {poly_index} references missing vertex {vertex_index}"
                )
    for line_index, line in enumerate(lines):
        if line.vertex_1 >= vertex_count or line.vertex_2 >= vertex_count:
            raise Lm2Error(
                f"line {line_index} references missing vertex {line.vertex_1}/{line.vertex_2}"
            )
    for sphere_index, sphere in enumerate(spheres):
        if sphere.vertex >= vertex_count:
            raise Lm2Error(
                f"sphere {sphere_index} references missing vertex {sphere.vertex}"
            )
    for bone_index, bone in enumerate(bones):
        if bone.vertex >= vertex_count:
            raise Lm2Error(f"bone {bone_index} references missing vertex {bone.vertex}")


def reject_package_input(source_name: str) -> None:
    suffix = Path(source_name).suffix.lower()
    if suffix in PACKAGE_SUFFIXES:
        raise Lm2Error(
            f"{source_name} is a package container, not an LM2 model. "
            "Extract one model entry first, then load the .lm2/.ldc file."
        )


def load_lm2_bytes(data: bytes, source_name: str) -> Lm2Model:
    reject_package_input(source_name)
    return parse_lm2(data)


def load_lm2_path(path: Path) -> Lm2Model:
    reject_package_input(str(path))
    return parse_lm2(path.read_bytes())


def export_obj(model: Lm2Model, output_path: Path, name: str) -> None:
    lines = [
        f"# Exported from {name}",
        "# LM2 polygon mesh plus line primitives",
        "o lm2_model",
    ]
    for vertex in model.vertices:
        x, y, z = to_view_coords(vertex)
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for poly in model.polygons:
        indexes = [index + 1 for index in poly.vertices]
        if len(indexes) == 3:
            lines.append("f " + " ".join(str(index) for index in indexes))
        elif len(indexes) == 4:
            lines.append(f"f {indexes[0]} {indexes[1]} {indexes[2]}")
            lines.append(f"f {indexes[0]} {indexes[2]} {indexes[3]}")
    for line in model.lines:
        lines.append(f"l {line.vertex_1 + 1} {line.vertex_2 + 1}")
    for sphere in model.spheres:
        lines.append(
            f"# sphere vertex={sphere.vertex + 1} radius={sphere.size * WORLD_SCALE:.6f} color={sphere.color}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_view_coords(vertex: Vertex) -> tuple[float, float, float]:
    return vertex.x, vertex.y, vertex.z


def safe_path_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "asset"


def load_body_metadata() -> dict[int, dict[str, str]]:
    metadata_path = Path(__file__).resolve().with_name("body_metadata.json")
    if metadata_path.exists():
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        return {int(index): value for index, value in raw.items()}

    metadata_path = Path("port/src/generated/reference_metadata.zig")
    if not metadata_path.exists():
        return {}
    text = metadata_path.read_text(encoding="utf-8")
    start = text.find("pub const body_hqr_entries")
    end = text.find("pub const xx_gam_vox_entries")
    if start >= 0 and end > start:
        text = text[start:end]
    entries: dict[int, dict[str, str]] = {}
    pattern = re.compile(
        r"\.entry_index = (?P<index>\d+),\s+"
        r"\.entry_type = (?P<type>null|\"(?:\\.|[^\"])*\"),\s+"
        r"\.entry_description = (?P<description>null|\"(?:\\.|[^\"])*\")",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        index = int(match.group("index"))
        entry_type = match.group("type")
        description = match.group("description")
        entries[index] = {
            "type": "" if entry_type == "null" else json.loads(entry_type),
            "description": "" if description == "null" else json.loads(description),
        }
    return entries


def decoded_entry(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    decoded, header = lba_hqr.decode_resource_entry(raw)
    return decoded, {
        "size_file": header.size_file,
        "compressed_size_file": header.compressed_size_file,
        "compress_method": header.compress_method,
    }


def parse_palette_payload(payload: bytes) -> list[int]:
    if len(payload) != PALETTE_BYTES:
        raise Lm2Error(
            f"palette payload must be {PALETTE_BYTES} bytes, got {len(payload)}"
        )
    colors: list[int] = []
    for offset in range(0, PALETTE_BYTES, 3):
        r, g, b = payload[offset], payload[offset + 1], payload[offset + 2]
        colors.append((r << 16) | (g << 8) | b)
    return colors


def parse_texture_atlas_payload(payload: bytes, palette: list[int]) -> dict[str, Any]:
    if len(payload) != TEXTURE_ATLAS_PIXELS:
        raise Lm2Error(
            f"texture atlas payload must be {TEXTURE_ATLAS_PIXELS} bytes, got {len(payload)}"
        )
    if len(palette) != 256:
        raise Lm2Error(
            f"texture atlas decode requires 256 palette entries, got {len(palette)}"
        )
    return {
        "width": TEXTURE_ATLAS_SIZE,
        "height": TEXTURE_ATLAS_SIZE,
        "pixels": [palette[index] for index in payload],
    }


def load_palette_from_asset_root(asset_root: Path) -> list[int]:
    palette_path = asset_root / PALETTE_ARCHIVE_NAME
    if not palette_path.exists():
        raise Lm2Error(f"missing LBA2 palette archive: {palette_path}")
    data = palette_path.read_bytes()
    entries = lba_hqr.parse_classic_table(data)
    if (
        PALETTE_ENTRY_INDEX >= len(entries)
        or entries[PALETTE_ENTRY_INDEX].byte_length == 0
    ):
        raise Lm2Error(
            f"{PALETTE_ARCHIVE_NAME} has no palette entry {PALETTE_ENTRY_INDEX}"
        )
    raw = lba_hqr.read_entry(data, entries[PALETTE_ENTRY_INDEX])
    payload, _ = decoded_entry(raw)
    return parse_palette_payload(payload)


def load_texture_atlas_from_asset_root(
    asset_root: Path, palette: list[int]
) -> dict[str, Any]:
    texture_path = asset_root / PALETTE_ARCHIVE_NAME
    if not texture_path.exists():
        raise Lm2Error(f"missing LBA2 texture archive: {texture_path}")
    data = texture_path.read_bytes()
    entries = lba_hqr.parse_classic_table(data)
    if (
        TEXTURE_ENTRY_INDEX >= len(entries)
        or entries[TEXTURE_ENTRY_INDEX].byte_length == 0
    ):
        raise Lm2Error(
            f"{PALETTE_ARCHIVE_NAME} has no texture entry {TEXTURE_ENTRY_INDEX}"
        )
    raw = lba_hqr.read_entry(data, entries[TEXTURE_ENTRY_INDEX])
    payload, _ = decoded_entry(raw)
    return parse_texture_atlas_payload(payload, palette)


def hqr_paths(asset_root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in asset_root.rglob("*")
            if path.is_file() and path.suffix.upper() == ".HQR"
        ),
        key=lambda path: path.relative_to(asset_root).as_posix().upper(),
    )


def selected_hqr_root(paths: list[Path]) -> Path:
    if not paths:
        raise Lm2Error("no HQR files selected")
    try:
        return Path(os.path.commonpath([str(path.parent) for path in paths])).resolve()
    except ValueError as exc:
        raise Lm2Error("selected HQR files must be on the same drive") from exc


def normalize_hqr_file_paths(paths: list[Path]) -> list[Path]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        if not resolved.exists():
            raise Lm2Error(f"HQR file does not exist: {resolved}")
        if not resolved.is_file():
            raise Lm2Error(f"selected HQR path is not a file: {resolved}")
        if resolved.suffix.upper() != ".HQR":
            raise Lm2Error(f"selected file is not an HQR archive: {resolved}")
        normalized.append(resolved)
        seen.add(resolved)
    if not normalized:
        raise Lm2Error("no HQR files selected")
    root = selected_hqr_root(normalized)
    return sorted(
        normalized, key=lambda path: path.relative_to(root).as_posix().upper()
    )


def read_hqr_payload(
    asset_root: Path, source: dict[str, Any]
) -> tuple[bytes, dict[str, Any] | None]:
    hqr_relative = source.get("hqr")
    if not isinstance(hqr_relative, str) or not hqr_relative:
        raise Lm2Error("catalog asset is missing source.hqr")
    hqr_path = (asset_root / hqr_relative).resolve()
    try:
        hqr_path.relative_to(asset_root.resolve())
    except ValueError as exc:
        raise Lm2Error(
            f"catalog asset points outside asset root: {hqr_relative}"
        ) from exc
    if not hqr_path.exists():
        raise Lm2Error(f"HQR file is missing: {hqr_path}")

    data = hqr_path.read_bytes()
    is_body_archive = hqr_path.name.upper() == "BODY.HQR"
    entries = (
        lba_hqr.parse_classic_table(data)
        if is_body_archive
        else lba_hqr.parse_table(data)
    )
    if is_body_archive:
        classic_index = source.get("classic_index")
        if not isinstance(classic_index, int):
            entry_index = source.get("entry_index")
            if not isinstance(entry_index, int):
                raise Lm2Error("BODY.HQR catalog asset is missing entry index")
            classic_index = entry_index - 1
        matching = [entry for entry in entries if entry.index == classic_index]
    else:
        entry_index = source.get("entry_index")
        if not isinstance(entry_index, int):
            raise Lm2Error("catalog asset is missing entry index")
        matching = [entry for entry in entries if entry.index == entry_index]
    if not matching or matching[0].byte_length == 0:
        raise Lm2Error(
            f"HQR entry is missing: {hqr_relative}:{source.get('entry_index')}"
        )
    raw = lba_hqr.read_entry(data, matching[0])
    try:
        return decoded_entry(raw)
    except lba_hqr.HqrError:
        return raw, None


def find_catalog_asset(catalog: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for asset in catalog.get("assets", []):
        if asset.get("id") == asset_id:
            return asset
    raise Lm2Error(f"catalog asset not found: {asset_id}")


def unknown_bytes_descriptor(
    payload: bytes,
    *,
    section: str,
    offset: int,
    length: int,
    confidence: str,
    note: str,
    related_fields: list[str] | None = None,
) -> dict[str, Any]:
    if offset < 0 or length < 0 or offset + length > len(payload):
        raise Lm2Error(f"invalid unknown descriptor range {offset}:{length}")
    descriptor: dict[str, Any] = {
        "section": section,
        "offset": offset,
        "length": length,
        "sha256": hashlib.sha256(payload[offset : offset + length]).hexdigest(),
        "confidence": confidence,
        "note": note,
    }
    if related_fields:
        descriptor["related_decoded_fields"] = related_fields
    return descriptor


def raw_animation_catalog_stats(
    payload: bytes,
    *,
    decode_status: str,
    decode_note: str,
    parse_error: str | None = None,
) -> dict[str, Any]:
    header_byte_length = min(16, len(payload) - (len(payload) % 2))
    header_words = (
        list(struct.unpack_from("<" + "H" * (header_byte_length // 2), payload, 0))
        if header_byte_length
        else []
    )
    descriptors: list[dict[str, Any]] = []
    if header_byte_length:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="header_words",
                offset=0,
                length=header_byte_length,
                confidence="high",
                note="Captured as little-endian words only; raw animation header semantics are not decoded.",
                related_fields=["header_words"],
            )
        )
    if len(payload) > header_byte_length:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="payload_after_header_words",
                offset=header_byte_length,
                length=len(payload) - header_byte_length,
                confidence="high",
                note="Opaque animation payload bytes retained only as a descriptor hash.",
            )
        )
    if not descriptors:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="empty_payload",
                offset=0,
                length=0,
                confidence="high",
                note="Empty animation payload.",
            )
        )

    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "header_words": header_words,
        "header_word_count": len(header_words),
        "parse_status": "raw",
        "decode_status": decode_status,
        "decode_note": decode_note,
        **({"parse_error": parse_error} if parse_error else {}),
        "semantic_layout": "unknown",
        "unknown_descriptors": descriptors,
    }


def build_catalog(
    asset_root: Path,
    progress: DecodeProgress | None = None,
    selected_files: list[Path] | None = None,
) -> dict[str, Any]:
    if not asset_root.exists():
        raise Lm2Error(f"asset root does not exist: {asset_root}")
    if not asset_root.is_dir():
        raise Lm2Error(f"asset root is not a directory: {asset_root}")
    body_metadata = load_body_metadata()
    catalog: dict[str, Any] = {
        "schema": "lba2-lm2-explorer-v1",
        "asset_root": str(asset_root.resolve()),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_mode": "files" if selected_files is not None else "folder",
        "hqr_files": [],
        "assets": [],
    }
    if selected_files is not None:
        catalog["selected_files"] = [
            path.relative_to(asset_root).as_posix() for path in selected_files
        ]

    archive_jobs: list[dict[str, Any]] = []
    for hqr_path in (
        selected_files if selected_files is not None else hqr_paths(asset_root)
    ):
        hqr_relative = hqr_path.relative_to(asset_root).as_posix()
        is_body_archive = hqr_path.name.upper() == "BODY.HQR"
        data = hqr_path.read_bytes()
        entries = (
            lba_hqr.parse_classic_table(data)
            if is_body_archive
            else lba_hqr.parse_table(data)
        )
        archive_jobs.append(
            {
                "path": hqr_path,
                "relative": hqr_relative,
                "is_body_archive": is_body_archive,
                "data": data,
                "entries": entries,
            }
        )

    total_entries = sum(
        1
        for archive in archive_jobs
        for entry in archive["entries"]
        if entry.byte_length > 0
    )
    processed_entries = 0
    if progress is not None:
        progress.update(
            total=total_entries, label="Decoding HQR entries", phase="decoding"
        )

    for archive in archive_jobs:
        hqr_path = archive["path"]
        hqr_relative = archive["relative"]
        is_body_archive = archive["is_body_archive"]
        data = archive["data"]
        entries = archive["entries"]
        file_summary: dict[str, Any] = {
            "path": hqr_relative,
            "indexing": "classic" if is_body_archive else "one-based",
            "entry_count": len(entries),
            "non_empty_entries": sum(1 for entry in entries if entry.byte_length > 0),
            "models": 0,
            "animations": 0,
            "decoded_animations": 0,
            "raw_animations": 0,
            "recognized": 0,
            "bytes": len(data),
        }

        for entry in entries:
            if entry.byte_length == 0:
                continue
            if progress is not None:
                progress.update(
                    current=processed_entries,
                    label=f"Decoding {hqr_relative}[{entry.index + 1 if is_body_archive else entry.index}]",
                )
            raw = lba_hqr.read_entry(data, entry)
            catalog_entry_index = entry.index + 1 if is_body_archive else entry.index
            try:
                payload, resource = decoded_entry(raw)
            except lba_hqr.HqrError:
                payload, resource = raw, None

            source = {
                "hqr": hqr_relative,
                "entry_index": catalog_entry_index,
                "offset": entry.offset,
                "raw_bytes": entry.byte_length,
                "raw_sha256": entry.sha256,
                "resource": resource,
            }
            if is_body_archive:
                source["classic_index"] = entry.index
            asset_id = f"{hqr_relative}:{catalog_entry_index}"

            try:
                model = parse_lm2(payload)
            except Lm2Error:
                model = None
            if model is not None:
                metadata = (
                    body_metadata.get(catalog_entry_index, {})
                    if is_body_archive
                    else {}
                )
                label = (
                    metadata.get("description")
                    or f"{Path(hqr_relative).name} entry {catalog_entry_index}"
                )
                asset = {
                    "id": asset_id,
                    "kind": "model",
                    "label": label,
                    "entry_type": metadata.get("type") or "mesh",
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": model.to_viewer_json(label)["stats"],
                    "bounds": model.header.bounds,
                    "features": {
                        "has_animation_flag": model.header.has_animation,
                        "has_transparency": model.header.has_transparency,
                        "has_lines": len(model.lines) > 0,
                        "has_spheres": len(model.spheres) > 0,
                    },
                }
                catalog["assets"].append(asset)
                file_summary["models"] += 1
                file_summary["recognized"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            archive_name = hqr_path.name.upper()
            if archive_name in ANIMATION_ARCHIVE_NAMES:
                if archive_name == ANIM_ARCHIVE_NAME:
                    try:
                        animation = parse_lba2_animation(payload)
                        animation_error = ""
                    except (AnimationError, Lm2Error) as exc:
                        animation = None
                        animation_error = str(exc)
                else:
                    animation = None
                    animation_error = ""
                if animation is not None:
                    stats = animation.to_json()
                    entry_type = "animation"
                    animation_state = "decoded"
                    features = {
                        "looping": animation.loop_frame < animation.keyframes - 1,
                        "can_fall": animation.can_fall,
                        "parsed": True,
                    }
                else:
                    if archive_name == ANIM3DS_ARCHIVE_NAME:
                        stats = raw_animation_catalog_stats(
                            payload,
                            decode_status="deferred",
                            decode_note="ANIM3DS semantic decode is not implemented",
                        )
                    else:
                        stats = raw_animation_catalog_stats(
                            payload,
                            decode_status="parse_failed",
                            decode_note="Animation parser rejected this payload; retained as raw evidence.",
                            parse_error=animation_error,
                        )
                    entry_type = "animation-raw"
                    animation_state = "raw"
                    features = {"parsed": False}
                asset = {
                    "id": asset_id,
                    "kind": "animation",
                    "label": f"{Path(hqr_relative).name} animation {catalog_entry_index}",
                    "entry_type": entry_type,
                    "animation_state": animation_state,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": features,
                }
                catalog["assets"].append(asset)
                if animation_state == "decoded":
                    file_summary["animations"] += 1
                    file_summary["decoded_animations"] += 1
                else:
                    file_summary["raw_animations"] += 1
                file_summary["recognized"] += 1

            processed_entries += 1
            if progress is not None:
                progress.update(current=processed_entries)

        catalog["hqr_files"].append(file_summary)

    decoded_animations = sum(
        1
        for asset in catalog["assets"]
        if asset["kind"] == "animation" and asset.get("animation_state") == "decoded"
    )
    raw_animations = sum(
        1
        for asset in catalog["assets"]
        if asset["kind"] == "animation" and asset.get("animation_state") == "raw"
    )
    catalog["summary"] = {
        "hqr_files": len(catalog["hqr_files"]),
        "assets": len(catalog["assets"]),
        "models": sum(1 for asset in catalog["assets"] if asset["kind"] == "model"),
        "animations": decoded_animations,
        "decoded_animations": decoded_animations,
        "raw_animations": raw_animations,
        "animation_assets": decoded_animations + raw_animations,
    }
    return catalog


def pick_directory_dialog() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build
        raise Lm2Error(f"folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Select the folder containing your LBA2 HQR files"
        )
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no folder selected")
    return Path(selected)


def pick_hqr_files_dialog() -> list[Path]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build
        raise Lm2Error(f"file picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilenames(
            title="Select one or more LBA2 HQR files",
            filetypes=(("HQR archives", "*.HQR *.hqr"), ("All files", "*.*")),
        )
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no files selected")
    return [Path(path) for path in selected]


def pick_export_directory_dialog() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build
        raise Lm2Error(f"export folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Select export folder for the LM2 evidence probe"
        )
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no export folder selected")
    return Path(selected)


def inspect(path: Path) -> None:
    model = load_lm2_path(path)
    print(json.dumps(model.to_viewer_json(str(path))["stats"], indent=2))


def export_probe_command(argv: list[str]) -> int:
    from .exports import export_catalog_asset_probe

    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer export",
        description="Export an LM2 evidence probe for one catalog model asset.",
    )
    parser.add_argument(
        "--asset-root",
        required=True,
        type=Path,
        help="folder containing the user's LBA2 HQR files",
    )
    parser.add_argument(
        "--asset",
        required=True,
        help='catalog asset id, for example "BODY.HQR:1"',
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="directory to write OBJ, MTL, PNG, and manifest files",
    )
    parser.add_argument(
        "--polygon-mode",
        choices=("original", "triangulated"),
        default="original",
        help="OBJ face mode, default original",
    )
    args = parser.parse_args(argv)

    manifest = export_catalog_asset_probe(
        asset_root=args.asset_root,
        asset_id=args.asset,
        output_dir=args.out,
        polygon_mode=args.polygon_mode,
    )
    print(f"Wrote {args.out.resolve()}")
    print(
        json.dumps(
            {"schema_version": manifest["schema_version"], "files": manifest["files"]},
            indent=2,
        )
    )
    return 0


def contract_command(argv: list[str]) -> int:
    from .contracts import export_catalog_asset_contract

    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer contract",
        description="Write a versioned LM2 model contract JSON file.",
    )
    parser.add_argument(
        "--asset-root",
        required=True,
        type=Path,
        help="folder containing the user's LBA2 HQR files",
    )
    parser.add_argument(
        "--asset",
        required=True,
        help='catalog asset id, for example "BODY.HQR:1"',
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="JSON file to write",
    )
    args = parser.parse_args(argv)

    contract = export_catalog_asset_contract(
        asset_root=args.asset_root,
        asset_id=args.asset,
        output_path=args.out,
    )
    print(f"Wrote {args.out.resolve()}")
    print(
        json.dumps(
            {
                "schema_version": contract.schema_version,
                "asset_id": contract.source.asset_id,
            },
            indent=2,
        )
    )
    return 0


def animation_command(argv: list[str]) -> int:
    from .animation import (
        build_animation_evidence,
        parse_lba2_animation_records,
        write_animation_evidence,
    )

    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer animation",
        description="Write decoded ANIM records and frame-step evidence as JSON.",
    )
    parser.add_argument(
        "--asset-root",
        required=True,
        type=Path,
        help="folder containing the user's LBA2 HQR files",
    )
    parser.add_argument(
        "--asset",
        required=True,
        help='catalog animation asset id, for example "ANIM.HQR:1"',
    )
    parser.add_argument(
        "--body-asset",
        help='optional catalog body asset id for bone-count compatibility, for example "BODY.HQR:1"',
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="JSON file to write",
    )
    parser.add_argument(
        "--sample-frame",
        type=int,
        default=0,
        help="target keyframe index to sample, default 0",
    )
    parser.add_argument(
        "--previous-frame",
        type=int,
        help="optional previous keyframe index for loop-transition samples",
    )
    parser.add_argument(
        "--elapsed-ms",
        type=int,
        default=0,
        help="elapsed milliseconds inside the sampled keyframe, default 0",
    )
    args = parser.parse_args(argv)

    asset_root = args.asset_root.resolve()
    catalog = build_catalog(asset_root)
    asset = find_catalog_asset(catalog, args.asset)
    if asset.get("kind") != "animation" or asset.get("entry_type") != "animation":
        raise Lm2Error(f"catalog asset is not a decoded animation: {args.asset}")
    payload, resource = read_hqr_payload(asset_root, asset["source"])
    animation = parse_lba2_animation_records(payload)

    body: dict[str, Any] | None = None
    if args.body_asset is not None:
        body_asset = find_catalog_asset(catalog, args.body_asset)
        if body_asset.get("kind") != "model":
            raise Lm2Error(f"catalog asset is not a model: {args.body_asset}")
        body_payload, _ = read_hqr_payload(asset_root, body_asset["source"])
        model = load_lm2_bytes(body_payload, str(body_asset.get("label") or args.body_asset))
        body = {"asset_id": body_asset["id"], "bone_count": len(model.bones)}

    evidence = build_animation_evidence(
        animation,
        source={
            "catalog_asset_id": asset["id"],
            "catalog_label": asset.get("label"),
            "asset_root": str(asset_root),
            "hqr": asset["source"].get("hqr"),
            "entry_index": asset["source"].get("entry_index"),
            "classic_index": asset["source"].get("classic_index"),
            "resource": resource,
        },
        sample_frame=args.sample_frame,
        previous_frame=args.previous_frame,
        elapsed_ms=args.elapsed_ms,
        body=body,
    )
    write_animation_evidence(evidence, args.out)
    print(f"Wrote {args.out.resolve()}")
    print(
        json.dumps(
            {
                "schema_version": evidence["schema_version"],
                "asset_id": evidence["source"]["catalog_asset_id"],
                "keyframes": evidence["animation"]["keyframe_count"],
                "boneframes": evidence["animation"]["bone_count"],
            },
            indent=2,
        )
    )
    return 0


def is_export_subcommand(arguments: list[str]) -> bool:
    if arguments[:1] != ["export"]:
        return False
    return any(
        argument in {"-h", "--help", "--asset-root", "--asset", "--out", "--polygon-mode"}
        or argument.startswith("--asset-root=")
        or argument.startswith("--asset=")
        or argument.startswith("--out=")
        or argument.startswith("--polygon-mode=")
        for argument in arguments[1:]
    )


def is_contract_subcommand(arguments: list[str]) -> bool:
    return arguments[:1] == ["contract"]


def is_animation_subcommand(arguments: list[str]) -> bool:
    return arguments[:1] == ["animation"]


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if is_export_subcommand(arguments):
        try:
            return export_probe_command(arguments[1:])
        except (Lm2Error, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if is_contract_subcommand(arguments):
        try:
            return contract_command(arguments[1:])
        except (Lm2Error, AnimationError, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if is_animation_subcommand(arguments):
        try:
            return animation_command(arguments[1:])
        except (Lm2Error, AnimationError, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    parser = argparse.ArgumentParser(
        description="View, inspect, or export LBA2 LM2 model files."
    )
    parser.add_argument("file", nargs="?", type=Path, help="LM2/LDC file to load")
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"viewer bind host, default {DEFAULT_HOST}"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"viewer bind port, default {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the browser automatically",
    )
    parser.add_argument(
        "--inspect", action="store_true", help="print parsed model stats and exit"
    )
    parser.add_argument(
        "--export-obj", type=Path, help="write a simple OBJ export and exit"
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=DEFAULT_ASSET_ROOT,
        help=f"folder containing the user's LBA2 HQR files, default {DEFAULT_ASSET_ROOT}",
    )
    args = parser.parse_args(arguments)

    try:
        if args.inspect:
            if args.file is None:
                parser.error("--inspect requires a file")
            inspect(args.file)
            return 0
        if args.export_obj is not None:
            if args.file is None:
                parser.error("--export-obj requires a file")
            model = load_lm2_path(args.file)
            export_obj(model, args.export_obj, str(args.file))
            print(f"Wrote {args.export_obj}")
            return 0
        from .server import serve

        serve(args.file, args.host, args.port, not args.no_browser, args.asset_root)
        return 0
    except (Lm2Error, lba_hqr.HqrError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
