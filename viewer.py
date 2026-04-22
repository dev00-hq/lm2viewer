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
import mimetypes
import re
import struct
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import lba_hqr

WORLD_SCALE = 0.15
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PACKAGE_SUFFIXES = {".hqr"}
FRONTEND_DIST = Path(__file__).resolve().with_name("frontend") / "dist"
ANIMATION_ARCHIVE_NAMES = {"ANIM.HQR", "ANIM3DS.HQR"}
PALETTE_ARCHIVE_NAME = "RESS.HQR"
PALETTE_ENTRY_INDEX = 0
PALETTE_BYTES = 256 * 3
TEXTURE_ENTRY_INDEX = 6
TEXTURE_ATLAS_SIZE = 256
TEXTURE_ATLAS_PIXELS = TEXTURE_ATLAS_SIZE * TEXTURE_ATLAS_SIZE


class Lm2Error(ValueError):
    pass


class AnimationError(ValueError):
    pass


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
            elapsed = 0.0 if self.started_at is None else max(0.0, elapsed_source - self.started_at)
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
            raise Lm2Error(f"unexpected end of file at 0x{self.index:x}, need {size} bytes")

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise Lm2Error(f"offset 0x{offset:x} is outside file size 0x{len(self.data):x}")
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

    def to_viewer_json(
        self,
        source_name: str | None = None,
        palette: list[int] | None = None,
        texture_atlas: dict[str, Any] | None = None,
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
        return {
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
                {"parent": bone.parent, "vertex": bone.vertex, "unknown_1": bone.unknown_1, "unknown_2": bone.unknown_2}
                for bone in self.bones
            ],
        }


def read_header(reader: Reader) -> Lm2Header:
    if len(reader.data) < 0x60:
        raise Lm2Error(f"LM2 file is too small for a 0x60-byte header: {len(reader.data)} bytes")
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
            raise Lm2Error(f"section offset 0x{offset:x} exceeds file size 0x{len(reader.data):x}")
    return header


def parse_lm2(data: bytes) -> Lm2Model:
    reader = Reader(data)
    header = read_header(reader)

    reader.seek(header.bones_offset)
    bones = tuple(Bone(reader.u16(), reader.u16(), reader.u16(), reader.u16()) for _ in range(header.bones_count))

    reader.seek(header.vertices_offset)
    raw_vertices = tuple(
        Vertex(reader.s16() * WORLD_SCALE, reader.s16() * WORLD_SCALE, reader.s16() * WORLD_SCALE, reader.u16())
        for _ in range(header.vertices_count)
    )
    vertices = tuple(resolve_vertex(vertex, raw_vertices, bones, index) for index, vertex in enumerate(raw_vertices))

    reader.seek(header.normals_offset)
    normals = tuple(
        Normal(reader.s16() * WORLD_SCALE, reader.s16() * WORLD_SCALE, reader.s16() * WORLD_SCALE, reader.u16())
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
    uv_groups = tuple(UvGroup(reader.u8(), reader.u8(), reader.u8(), reader.u8()) for _ in range(header.uv_groups_count))

    validate_indices(vertices, bones, polygons, lines, spheres)
    return Lm2Model(header, bones, vertices, normals, polygons, tuple(lines), tuple(spheres), uv_groups)


def resolve_vertex(vertex: Vertex, raw_vertices: tuple[Vertex, ...], bones: tuple[Bone, ...], vertex_index: int) -> Vertex:
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
            raise Lm2Error(f"bone {next_bone_index} references missing vertex {bone.vertex}")
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


def parse_polygon(reader: Reader, offset: int, render_type: int, block_size: int) -> Polygon:
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


def parse_polygon_uv(reader: Reader, offset: int, vertex_count: int) -> tuple[tuple[float, float], ...]:
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
                raise Lm2Error(f"polygon {poly_index} references missing vertex {vertex_index}")
    for line_index, line in enumerate(lines):
        if line.vertex_1 >= vertex_count or line.vertex_2 >= vertex_count:
            raise Lm2Error(f"line {line_index} references missing vertex {line.vertex_1}/{line.vertex_2}")
    for sphere_index, sphere in enumerate(spheres):
        if sphere.vertex >= vertex_count:
            raise Lm2Error(f"sphere {sphere_index} references missing vertex {sphere.vertex}")
    for bone_index, bone in enumerate(bones):
        if bone.vertex >= vertex_count:
            raise Lm2Error(f"bone {bone_index} references missing vertex {bone.vertex}")


def parse_lba2_animation(data: bytes) -> AnimationSummary:
    reader = Reader(data)
    if len(data) < 8:
        raise AnimationError("animation is too small")
    keyframes = reader.u16()
    boneframes = reader.u16()
    loop_frame = reader.u16()
    reader.u16()
    if keyframes == 0:
        raise AnimationError("animation has no keyframes")
    if keyframes > 20000 or boneframes > 1024:
        raise AnimationError("animation header is outside plausible bounds")
    expected_size = 8 + keyframes * (8 + boneframes * 8)
    if expected_size > len(data):
        raise AnimationError(
            f"animation payload is truncated: expected {expected_size} bytes, found {len(data)}"
        )
    if loop_frame >= keyframes:
        raise AnimationError(f"animation loop frame {loop_frame} exceeds keyframe count {keyframes}")

    total_duration = 0
    translated_boneframes = 0
    can_fall = False
    for _ in range(keyframes):
        total_duration += reader.u16()
        reader.skip(6)
        for _ in range(boneframes):
            bone_type = reader.s16()
            reader.skip(6)
            if bone_type != 0:
                translated_boneframes += 1
                can_fall = True
    return AnimationSummary(keyframes, boneframes, loop_frame, total_duration, translated_boneframes, can_fall, len(data))


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
    lines = [f"# Exported from {name}", "# LM2 polygon mesh plus line primitives", "o lm2_model"]
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
        lines.append(f"# sphere vertex={sphere.vertex + 1} radius={sphere.size * WORLD_SCALE:.6f} color={sphere.color}")
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
        raise Lm2Error(f"palette payload must be {PALETTE_BYTES} bytes, got {len(payload)}")
    colors: list[int] = []
    for offset in range(0, PALETTE_BYTES, 3):
        r, g, b = payload[offset], payload[offset + 1], payload[offset + 2]
        colors.append((r << 16) | (g << 8) | b)
    return colors


def parse_texture_atlas_payload(payload: bytes, palette: list[int]) -> dict[str, Any]:
    if len(payload) != TEXTURE_ATLAS_PIXELS:
        raise Lm2Error(f"texture atlas payload must be {TEXTURE_ATLAS_PIXELS} bytes, got {len(payload)}")
    if len(palette) != 256:
        raise Lm2Error(f"texture atlas decode requires 256 palette entries, got {len(palette)}")
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
    if PALETTE_ENTRY_INDEX >= len(entries) or entries[PALETTE_ENTRY_INDEX].byte_length == 0:
        raise Lm2Error(f"{PALETTE_ARCHIVE_NAME} has no palette entry {PALETTE_ENTRY_INDEX}")
    raw = lba_hqr.read_entry(data, entries[PALETTE_ENTRY_INDEX])
    payload, _ = decoded_entry(raw)
    return parse_palette_payload(payload)


def load_texture_atlas_from_asset_root(asset_root: Path, palette: list[int]) -> dict[str, Any]:
    texture_path = asset_root / PALETTE_ARCHIVE_NAME
    if not texture_path.exists():
        raise Lm2Error(f"missing LBA2 texture archive: {texture_path}")
    data = texture_path.read_bytes()
    entries = lba_hqr.parse_classic_table(data)
    if TEXTURE_ENTRY_INDEX >= len(entries) or entries[TEXTURE_ENTRY_INDEX].byte_length == 0:
        raise Lm2Error(f"{PALETTE_ARCHIVE_NAME} has no texture entry {TEXTURE_ENTRY_INDEX}")
    raw = lba_hqr.read_entry(data, entries[TEXTURE_ENTRY_INDEX])
    payload, _ = decoded_entry(raw)
    return parse_texture_atlas_payload(payload, palette)


def hqr_paths(asset_root: Path) -> list[Path]:
    return sorted(
        (path for path in asset_root.rglob("*") if path.is_file() and path.suffix.upper() == ".HQR"),
        key=lambda path: path.relative_to(asset_root).as_posix().upper(),
    )


def read_hqr_payload(asset_root: Path, source: dict[str, Any]) -> tuple[bytes, dict[str, Any] | None]:
    hqr_relative = source.get("hqr")
    if not isinstance(hqr_relative, str) or not hqr_relative:
        raise Lm2Error("catalog asset is missing source.hqr")
    hqr_path = (asset_root / hqr_relative).resolve()
    try:
        hqr_path.relative_to(asset_root.resolve())
    except ValueError as exc:
        raise Lm2Error(f"catalog asset points outside asset root: {hqr_relative}") from exc
    if not hqr_path.exists():
        raise Lm2Error(f"HQR file is missing: {hqr_path}")

    data = hqr_path.read_bytes()
    is_body_archive = hqr_path.name.upper() == "BODY.HQR"
    entries = lba_hqr.parse_classic_table(data) if is_body_archive else lba_hqr.parse_table(data)
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
        raise Lm2Error(f"HQR entry is missing: {hqr_relative}:{source.get('entry_index')}")
    raw = lba_hqr.read_entry(data, matching[0])
    try:
        return decoded_entry(raw)
    except lba_hqr.HqrError:
        return raw, None


def build_catalog(asset_root: Path, progress: DecodeProgress | None = None) -> dict[str, Any]:
    if not asset_root.exists():
        raise Lm2Error(f"asset root does not exist: {asset_root}")
    if not asset_root.is_dir():
        raise Lm2Error(f"asset root is not a directory: {asset_root}")
    body_metadata = load_body_metadata()
    catalog: dict[str, Any] = {
        "schema": "lba2-lm2-explorer-v1",
        "asset_root": str(asset_root.resolve()),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hqr_files": [],
        "assets": [],
    }

    archive_jobs: list[dict[str, Any]] = []
    for hqr_path in hqr_paths(asset_root):
        hqr_relative = hqr_path.relative_to(asset_root).as_posix()
        is_body_archive = hqr_path.name.upper() == "BODY.HQR"
        data = hqr_path.read_bytes()
        entries = lba_hqr.parse_classic_table(data) if is_body_archive else lba_hqr.parse_table(data)
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
        progress.update(total=total_entries, label="Decoding HQR entries", phase="decoding")

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
                metadata = body_metadata.get(catalog_entry_index, {}) if is_body_archive else {}
                label = metadata.get("description") or f"{Path(hqr_relative).name} entry {catalog_entry_index}"
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

            if hqr_path.name.upper() in ANIMATION_ARCHIVE_NAMES:
                try:
                    animation = parse_lba2_animation(payload)
                    animation_error = ""
                except (AnimationError, Lm2Error) as exc:
                    animation = None
                    animation_error = str(exc)
                if animation is not None:
                    stats = animation.to_json()
                    entry_type = "animation"
                    features = {
                        "looping": animation.loop_frame < animation.keyframes - 1,
                        "can_fall": animation.can_fall,
                        "parsed": True,
                    }
                else:
                    head = list(struct.unpack_from("<" + "H" * min(6, len(payload) // 2), payload, 0)) if payload else []
                    stats = {
                        "decoded_bytes": len(payload),
                        "header_words": head,
                        "parse_status": "raw",
                        "parse_error": animation_error,
                    }
                    entry_type = "animation-raw"
                    features = {"parsed": False}
                asset = {
                    "id": asset_id,
                    "kind": "animation",
                    "label": f"{Path(hqr_relative).name} animation {catalog_entry_index}",
                    "entry_type": entry_type,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": features,
                }
                catalog["assets"].append(asset)
                file_summary["animations"] += 1
                file_summary["recognized"] += 1

            processed_entries += 1
            if progress is not None:
                progress.update(current=processed_entries)

        catalog["hqr_files"].append(file_summary)

    catalog["summary"] = {
        "hqr_files": len(catalog["hqr_files"]),
        "assets": len(catalog["assets"]),
        "models": sum(1 for asset in catalog["assets"] if asset["kind"] == "model"),
        "animations": sum(1 for asset in catalog["assets"] if asset["kind"] == "animation"),
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
        selected = filedialog.askdirectory(title="Select the folder containing your LBA2 HQR files")
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no folder selected")
    return Path(selected)


class ViewerServer:
    def __init__(self, initial_path: Path | None, asset_root: Path | None) -> None:
        self.initial_path = initial_path
        self.last_model: dict[str, Any] | None = None
        self.asset_root: Path | None = None
        self.catalog: dict[str, Any] | None = None
        self.palette: list[int] | None = None
        self.texture_atlas: dict[str, Any] | None = None
        self.decode_progress = DecodeProgress()
        if asset_root is not None:
            self.set_asset_root(asset_root)
        if initial_path is not None:
            self.last_model = self.model_json(load_lm2_path(initial_path), str(initial_path))

    def set_asset_root(self, asset_root: Path) -> dict[str, Any]:
        resolved = asset_root.expanduser().resolve()
        self.decode_progress.begin(f"Scanning {resolved}", phase="scanning")
        try:
            self.catalog = build_catalog(resolved, self.decode_progress)
            self.decode_progress.update(label="Loading palette and texture atlas", phase="finalizing")
            self.asset_root = resolved
            self.palette = load_palette_from_asset_root(resolved)
            self.texture_atlas = load_texture_atlas_from_asset_root(resolved, self.palette)
            self.decode_progress.finish(self.catalog.get("summary", {}))
            return self.catalog
        except Exception as exc:
            self.decode_progress.fail(str(exc))
            raise

    def load_catalog_palette(self) -> list[int] | None:
        if self.catalog is None:
            return None
        asset_root = self.catalog.get("asset_root")
        if not isinstance(asset_root, str) or not asset_root:
            raise Lm2Error("catalog is missing asset_root for palette lookup")
        return load_palette_from_asset_root(Path(asset_root))

    def load_catalog_texture_atlas(self) -> dict[str, Any] | None:
        if self.catalog is None:
            return None
        if self.palette is None:
            raise Lm2Error("catalog texture atlas requires a loaded palette")
        asset_root = self.catalog.get("asset_root")
        if not isinstance(asset_root, str) or not asset_root:
            raise Lm2Error("catalog is missing asset_root for texture lookup")
        return load_texture_atlas_from_asset_root(Path(asset_root), self.palette)

    def model_json(self, model: Lm2Model, source_name: str | None = None) -> dict[str, Any]:
        return model.to_viewer_json(source_name, palette=self.palette, texture_atlas=self.texture_atlas)

    def find_catalog_asset(self, asset_id: str) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        for asset in self.catalog.get("assets", []):
            if asset.get("id") == asset_id:
                return asset
        raise Lm2Error(f"catalog asset not found: {asset_id}")

    def handler_class(self) -> type[BaseHTTPRequestHandler]:
        server_state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                print("[lm2-viewer] " + fmt % args, file=sys.stderr)

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/model.json":
                    payload = server_state.last_model or {"error": "No model loaded yet."}
                    self.send_json(payload)
                elif parsed.path == "/catalog.json":
                    payload = server_state.catalog or {"error": "No catalog loaded yet."}
                    self.send_json(payload)
                elif parsed.path == "/api/decode/progress":
                    self.send_json(server_state.decode_progress.snapshot())
                elif parsed.path.startswith("/api/"):
                    self.send_error(404)
                else:
                    self.send_static(parsed.path)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                try:
                    if parsed.path == "/api/upload":
                        payload = self.read_upload()
                        model = server_state.model_json(load_lm2_bytes(payload["data"], payload["filename"]), payload["filename"])
                        server_state.last_model = model
                        self.send_json(model)
                    elif parsed.path == "/api/path":
                        length = int(self.headers.get("content-length", "0"))
                        body = self.rfile.read(length)
                        request = json.loads(body.decode("utf-8"))
                        path = Path(request["path"]).expanduser()
                        model = server_state.model_json(load_lm2_path(path), str(path))
                        server_state.last_model = model
                        self.send_json(model)
                    elif parsed.path == "/api/catalog/build":
                        length = int(self.headers.get("content-length", "0"))
                        body = self.rfile.read(length)
                        request = json.loads(body.decode("utf-8"))
                        asset_root = Path(request["asset_root"]).expanduser()
                        self.send_json(server_state.set_asset_root(asset_root))
                    elif parsed.path == "/api/catalog/pick":
                        server_state.decode_progress.begin("Waiting for folder selection", phase="waiting")
                        self.send_json(server_state.set_asset_root(pick_directory_dialog()))
                    elif parsed.path == "/api/catalog/load":
                        length = int(self.headers.get("content-length", "0"))
                        body = self.rfile.read(length)
                        request = json.loads(body.decode("utf-8"))
                        asset = server_state.find_catalog_asset(str(request["id"]))
                        if asset.get("kind") == "model":
                            if server_state.asset_root is None:
                                raise Lm2Error("no asset root loaded")
                            payload, _ = read_hqr_payload(server_state.asset_root, asset["source"])
                            model = server_state.model_json(load_lm2_bytes(payload, str(asset["relative_path"])), asset["label"])
                            model["catalog_asset"] = asset
                            server_state.last_model = model
                            self.send_json(model)
                        elif asset.get("kind") == "animation":
                            self.send_json({"animation": asset})
                        else:
                            raise Lm2Error(f"unsupported catalog asset kind: {asset.get('kind')}")
                    else:
                        self.send_error(404)
                except Exception as exc:
                    self.send_json({"error": str(exc)}, status=400)

            def read_upload(self) -> dict[str, Any]:
                content_type = self.headers.get("content-type", "")
                if "multipart/form-data" not in content_type or "boundary=" not in content_type:
                    raise Lm2Error("expected multipart/form-data upload")
                boundary = content_type.split("boundary=", 1)[1].strip().strip('"').encode("ascii")
                length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(length)
                marker = b"--" + boundary
                for part in body.split(marker):
                    if b'Content-Disposition:' not in part or b'name="file"' not in part:
                        continue
                    header_end = part.find(b"\r\n\r\n")
                    if header_end < 0:
                        continue
                    headers = part[:header_end].decode("utf-8", errors="replace")
                    data = part[header_end + 4 :]
                    if data.endswith(b"\r\n"):
                        data = data[:-2]
                    filename = "upload.lm2"
                    for item in headers.split(";"):
                        item = item.strip()
                        if item.startswith("filename="):
                            filename = item.split("=", 1)[1].strip('"') or filename
                    return {"filename": filename, "data": data}
                raise Lm2Error("upload did not include a file field")

            def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                self.send_bytes(json.dumps(payload).encode("utf-8"), "application/json", status)

            def send_static(self, request_path: str) -> None:
                if not FRONTEND_DIST.exists():
                    self.send_json(
                        {
                            "error": (
                                f"frontend build not found at {FRONTEND_DIST}. "
                                "Run npm install && npm run build in frontend."
                            )
                        },
                        status=500,
                    )
                    return
                relative = request_path.lstrip("/") or "index.html"
                if relative.endswith("/"):
                    relative += "index.html"
                candidate = (FRONTEND_DIST / urllib.parse.unquote(relative)).resolve()
                try:
                    candidate.relative_to(FRONTEND_DIST.resolve())
                except ValueError:
                    self.send_error(404)
                    return
                if not candidate.exists() or not candidate.is_file():
                    candidate = FRONTEND_DIST / "index.html"
                content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
                self.send_bytes(candidate.read_bytes(), content_type)

            def send_bytes(self, payload: bytes, content_type: str, status: int = 200) -> None:
                self.send_response(status)
                self.send_header("content-type", content_type)
                self.send_header("content-length", str(len(payload)))
                self.send_header("cache-control", "no-store, max-age=0")
                self.send_header("pragma", "no-cache")
                self.send_header("expires", "0")
                self.end_headers()
                self.wfile.write(payload)

        return Handler


def serve(initial_path: Path | None, host: str, port: int, open_browser: bool, asset_root: Path | None) -> None:
    viewer = ViewerServer(initial_path, asset_root)
    httpd = ThreadingHTTPServer((host, port), viewer.handler_class())
    url = f"http://{host}:{httpd.server_port}/"
    print(f"LM2 viewer listening on {url}")
    if initial_path is not None:
        print(f"Loaded {initial_path}")
    if viewer.catalog is not None:
        summary = viewer.catalog.get("summary", {})
        print(
            "Catalog loaded: "
            f"{summary.get('models', 0)} models, {summary.get('animations', 0)} animations"
        )
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LM2 viewer.")


def inspect(path: Path) -> None:
    model = load_lm2_path(path)
    print(json.dumps(model.to_viewer_json(str(path))["stats"], indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="View, inspect, or export LBA2 LM2 model files.")
    parser.add_argument("file", nargs="?", type=Path, help="LM2/LDC file to load")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"viewer bind host, default {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"viewer bind port, default {DEFAULT_PORT}")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    parser.add_argument("--inspect", action="store_true", help="print parsed model stats and exit")
    parser.add_argument("--export-obj", type=Path, help="write a simple OBJ export and exit")
    parser.add_argument("--asset-root", type=Path, help="folder containing the user's LBA2 HQR files")
    args = parser.parse_args(argv)

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
        serve(args.file, args.host, args.port, not args.no_browser, args.asset_root)
        return 0
    except (Lm2Error, lba_hqr.HqrError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
