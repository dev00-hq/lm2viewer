"""Export decoded LM2 evidence probes for external inspection tools."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import struct
import subprocess
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from lba2_lm2_viewer import __version__

if TYPE_CHECKING:
    from lba2_lm2_viewer.viewer import Lm2Model, Polygon, UvGroup


PolygonMode = Literal["original", "triangulated"]


def export_catalog_asset_probe(
    *,
    asset_root: Path,
    asset_id: str,
    output_dir: Path,
    polygon_mode: PolygonMode = "original",
) -> dict[str, Any]:
    from lba2_lm2_viewer import viewer
    from lba2_lm2_viewer.catalog_graph import build_catalog_graph, query_export_context

    resolved_root = asset_root.expanduser().resolve()
    catalog = viewer.build_catalog(resolved_root)
    graph = build_catalog_graph(catalog)
    asset = _find_catalog_asset(catalog, asset_id)
    if asset.get("kind") != "model":
        raise viewer.Lm2Error(f"catalog asset is not a model: {asset_id}")
    payload, resource = viewer.read_hqr_payload(resolved_root, asset["source"])
    model = viewer.load_lm2_bytes(payload, str(asset["relative_path"]))

    palette: list[int] | None = None
    texture_atlas: dict[str, Any] | None = None
    warnings: list[str] = []
    try:
        palette = viewer.load_palette_from_asset_root(resolved_root)
        texture_atlas = viewer.load_texture_atlas_from_asset_root(
            resolved_root, palette
        )
    except viewer.Lm2Error as exc:
        warnings.append(str(exc))

    proof_scope = "decoded model geometry and generated OBJ/texture evidence; not live runtime gameplay proof"
    graph_context = query_export_context(graph, asset["id"], proof_scope)
    source = {
        "asset_root": str(resolved_root),
        "catalog_asset_id": asset["id"],
        "catalog_label": asset.get("label"),
        "archive": asset["source"].get("hqr"),
        "entry_index": asset["source"].get("entry_index"),
        "classic_index": asset["source"].get("classic_index"),
        "archive_offset": asset["source"].get("offset"),
        "archive_raw_bytes": asset["source"].get("raw_bytes"),
        "archive_raw_sha256": asset["source"].get("raw_sha256"),
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "resource": resource,
        "source_mode": catalog.get("source_mode"),
        "evidence_status": _evidence_status_for_asset(asset),
        "proof_scope": proof_scope,
        "scene_usage_count": graph_context["scene_usage_count"],
        "relationship_link_count": graph_context["relationship_link_count"],
        "direct_scene_object_usage_count": graph_context["direct_scene_object_usage_count"],
        "script_reference_count": graph_context["script_reference_count"],
        "proof_scopes": graph_context["proof_scopes"],
        "evidence_statuses": graph_context["evidence_statuses"],
        "source_rules": graph_context["source_rules"],
        "source_fields": graph_context["source_fields"],
        "index_rules": graph_context["index_rules"],
        "runtime_contract_ids": [],
        "promotion_packet_ids": [],
        "promotion_packet_source": "not_scene_linked",
    }
    return export_model_probe(
        model=model,
        output_dir=output_dir,
        source=source,
        polygon_mode=polygon_mode,
        palette=palette,
        texture_atlas=texture_atlas,
        warnings=warnings,
    )


def export_model_probe(
    *,
    model: "Lm2Model",
    output_dir: Path,
    source: dict[str, Any],
    polygon_mode: PolygonMode = "original",
    palette: list[int] | None = None,
    texture_atlas: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    _validate_polygon_mode(polygon_mode)
    tool = {
        "name": "lba2-lm2-viewer",
        "version": __version__,
        **_git_info(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = _safe_stem(str(source.get("catalog_asset_id") or "lm2_model"))
    obj_name = f"{base_name}.obj"
    mtl_name = f"{base_name}.mtl"
    manifest_name = "manifest.json"

    atlas_info = _write_texture_outputs(
        model=model,
        output_dir=output_dir,
        base_name=base_name,
        texture_atlas=texture_atlas,
    )
    material_names = _material_names(model)
    _write_mtl(
        output_dir / mtl_name,
        material_names=material_names,
        texture_files=atlas_info["uv_group_files"],
        palette=palette,
    )
    polygon_exports = _write_obj(
        model=model,
        output_path=output_dir / obj_name,
        material_library=mtl_name,
        material_names=material_names,
        polygon_mode=polygon_mode,
    )

    manifest = _manifest(
        model=model,
        source=source,
        files={
            "obj": obj_name,
            "mtl": mtl_name,
            "manifest": manifest_name,
            **atlas_info["manifest_files"],
        },
        polygon_exports=polygon_exports,
        polygon_mode=polygon_mode,
        tool=tool,
        warnings=warnings or [],
    )
    (output_dir / manifest_name).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _find_catalog_asset(catalog: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for asset in catalog.get("assets", []):
        if asset.get("id") == asset_id:
            return asset
    from lba2_lm2_viewer.viewer import Lm2Error

    raise Lm2Error(f"catalog asset not found: {asset_id}")


def _validate_polygon_mode(polygon_mode: str) -> None:
    if polygon_mode not in ("original", "triangulated"):
        from lba2_lm2_viewer.viewer import Lm2Error

        raise Lm2Error(f"unsupported polygon mode: {polygon_mode}")


def _write_obj(
    *,
    model: "Lm2Model",
    output_path: Path,
    material_library: str,
    material_names: dict[str, str],
    polygon_mode: PolygonMode,
) -> list[dict[str, Any]]:
    lines = [
        "# LM2 evidence probe OBJ",
        f"mtllib {material_library}",
        "o lm2_model",
    ]
    for vertex in model.vertices:
        lines.append(f"v {vertex.x:.6f} {vertex.y:.6f} {vertex.z:.6f}")

    vt_lookup: dict[tuple[int, int], int] = {}
    for poly_index, poly in enumerate(model.polygons):
        if not _has_usable_uv(poly):
            continue
        for local_index, uv in enumerate(poly.uv or ()):
            vt_lookup[(poly_index, local_index)] = len(vt_lookup) + 1
            lines.append(f"vt {uv[0]:.6f} {1.0 - uv[1]:.6f}")

    polygon_exports: list[dict[str, Any]] = []
    for poly_index, poly in enumerate(model.polygons):
        key = _material_key(poly)
        lines.append(f"usemtl {material_names[key]}")
        faces = _polygon_faces(poly, polygon_mode)
        emitted_faces: list[list[int]] = []
        for face in faces:
            emitted_faces.append(list(face))
            terms = []
            for local_index in face:
                vertex_index = poly.vertices[local_index] + 1
                vt_index = vt_lookup.get((poly_index, local_index))
                terms.append(
                    f"{vertex_index}/{vt_index}" if vt_index is not None else str(vertex_index)
                )
            lines.append("f " + " ".join(terms))
        polygon_exports.append(
            {
                "polygon_index": poly_index,
                "mode": polygon_mode,
                "source_vertices": list(poly.vertices),
                "faces_local_indices": emitted_faces,
            }
        )

    for line in model.lines:
        lines.append(f"l {line.vertex_1 + 1} {line.vertex_2 + 1}")
    for sphere_index, sphere in enumerate(model.spheres):
        lines.append(
            f"# sphere index={sphere_index} vertex={sphere.vertex + 1} "
            f"radius={sphere.size} palette_index={sphere.palette_index} unknown={sphere.unknown}"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return polygon_exports


def _write_mtl(
    output_path: Path,
    *,
    material_names: dict[str, str],
    texture_files: dict[int, str],
    palette: list[int] | None,
) -> None:
    lines = ["# LM2 evidence probe materials"]
    for key, name in material_names.items():
        lines.append(f"newmtl {name}")
        parts = key.split(":")
        if parts[0] == "texture":
            texture_index = int(parts[1])
            lines.append("Kd 1.000000 1.000000 1.000000")
            if texture_index in texture_files:
                lines.append(f"map_Kd {texture_files[texture_index]}")
        else:
            palette_index = int(parts[1])
            color = palette[palette_index] if palette and palette_index < len(palette) else palette_index
            r = ((color >> 16) & 0xFF) / 255.0
            g = ((color >> 8) & 0xFF) / 255.0
            b = (color & 0xFF) / 255.0
            lines.append(f"Kd {r:.6f} {g:.6f} {b:.6f}")
        lines.append("Ka 0.000000 0.000000 0.000000")
        lines.append("Ks 0.000000 0.000000 0.000000")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_texture_outputs(
    *,
    model: "Lm2Model",
    output_dir: Path,
    base_name: str,
    texture_atlas: dict[str, Any] | None,
) -> dict[str, Any]:
    if not texture_atlas:
        return {"uv_group_files": {}, "manifest_files": {}}
    width = int(texture_atlas["width"])
    height = int(texture_atlas["height"])
    pixels = [int(pixel) for pixel in texture_atlas["pixels"]]
    atlas_name = f"{base_name}_atlas.png"
    _write_png(output_dir / atlas_name, width, height, pixels)

    uv_group_files: dict[int, str] = {}
    for texture_index in sorted(_used_texture_indices(model)):
        if texture_index < 0 or texture_index >= len(model.uv_groups):
            continue
        group = model.uv_groups[texture_index]
        cropped = _crop_pixels(pixels, width, height, group)
        group_name = f"{base_name}_uv{texture_index:03d}.png"
        _write_png(output_dir / group_name, group.w, group.h, cropped)
        uv_group_files[texture_index] = group_name

    return {
        "uv_group_files": uv_group_files,
        "manifest_files": {
            "shared_atlas_png": atlas_name,
            "uv_group_pngs": [
                {"uv_group": index, "path": path}
                for index, path in uv_group_files.items()
            ],
        },
    }


def _manifest(
    *,
    model: "Lm2Model",
    source: dict[str, Any],
    files: dict[str, Any],
    polygon_exports: list[dict[str, Any]],
    polygon_mode: PolygonMode,
    tool: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "lm2_probe.v0",
        "tool": tool,
        "source": source,
        "evidence": _evidence_context_from_source(
            source,
            default_scope="decoded model geometry and generated OBJ/texture evidence; not live runtime gameplay proof",
        ),
        "options": {
            "polygon_mode": polygon_mode,
            "coordinate_space": "decoded_source",
            "viewer_world_scale": _viewer_world_scale(),
        },
        "files": files,
        "stats": {
            "bones": len(model.bones),
            "vertices": len(model.vertices),
            "normals": len(model.normals),
            "polygons": len(model.polygons),
            "lines": len(model.lines),
            "spheres": len(model.spheres),
            "uv_groups": len(model.uv_groups),
        },
        "bounds": {
            "decoded": _decoded_bounds(model),
            "header_raw": {
                "x": [model.header.bounds[0], model.header.bounds[1]],
                "y": [model.header.bounds[2], model.header.bounds[3]],
                "z": [model.header.bounds[4], model.header.bounds[5]],
            },
        },
        "header": {
            "flags": model.header.flags,
            "version": model.header.version,
            "has_animation": model.header.has_animation,
            "no_sort": model.header.no_sort,
            "has_transparency": model.header.has_transparency,
            "unknown_region": _unknown_region(model),
        },
        "uv_groups": [
            {
                "index": index,
                "x": group.x,
                "y": group.y,
                "w": group.w,
                "h": group.h,
                "polygons": _polygons_for_texture(model, index),
            }
            for index, group in enumerate(model.uv_groups)
        ],
        "polygons": [
            {
                "index": index,
                "vertices": list(poly.vertices),
                "render_type": poly.render_type,
                "palette_index": poly.palette_index,
                "color_word": poly.color_word,
                "intensity": poly.intensity,
                "has_texture": poly.has_texture,
                "texture": poly.texture,
                "has_extra": poly.has_extra,
                "has_transparency": poly.has_transparency,
                "uv": [list(coord) for coord in poly.uv] if poly.uv else None,
            }
            for index, poly in enumerate(model.polygons)
        ],
        "obj_faces": polygon_exports,
        "lines": [
            {
                "index": index,
                "vertices": [line.vertex_1, line.vertex_2],
                "palette_index": line.palette_index,
                "color_word": line.color_word,
                "unknown": line.unknown,
            }
            for index, line in enumerate(model.lines)
        ],
        "spheres": [
            {
                "index": index,
                "vertex": sphere.vertex,
                "size": sphere.size,
                "palette_index": sphere.palette_index,
                "color_word": sphere.color_word,
                "unknown": sphere.unknown,
            }
            for index, sphere in enumerate(model.spheres)
        ],
        "warnings": warnings,
    }


def _evidence_context_from_source(source: dict[str, Any], *, default_scope: str) -> dict[str, Any]:
    return {
        "stable_id": source.get("catalog_asset_id"),
        "evidence_status": source.get("evidence_status") or "decoded_only",
        "proof_scope": source.get("proof_scope") or default_scope,
        "scene_usage_count": source.get("scene_usage_count", 0),
        "relationship_link_count": source.get("relationship_link_count", 0),
        "direct_scene_object_usage_count": source.get("direct_scene_object_usage_count", 0),
        "script_reference_count": source.get("script_reference_count", 0),
        "proof_scopes": list(source.get("proof_scopes") or []),
        "evidence_statuses": list(source.get("evidence_statuses") or []),
        "source_rules": list(source.get("source_rules") or []),
        "source_fields": list(source.get("source_fields") or []),
        "index_rules": list(source.get("index_rules") or []),
        "runtime_contract_ids": list(source.get("runtime_contract_ids") or []),
        "promotion_packet_ids": list(source.get("promotion_packet_ids") or []),
        "promotion_packet_source": source.get("promotion_packet_source") or "not_scene_linked",
    }


def _evidence_status_for_asset(asset: dict[str, Any]) -> str:
    stats = asset.get("stats") or {}
    if isinstance(stats, dict):
        if stats.get("source_provenance"):
            return "source_backed"
        if stats.get("runtime_reference_status") == "source-backed":
            return "source_backed"
        if stats.get("parse_status") == "raw":
            return "intentionally_deferred"
        if stats.get("decode_status") in ("decoded", "partial"):
            return "decoded_only"
    if asset.get("kind") in ("model", "animation"):
        return "decoded_only"
    return "unknown"


def _polygon_faces(poly: "Polygon", polygon_mode: PolygonMode) -> list[tuple[int, ...]]:
    local_indices = tuple(range(len(poly.vertices)))
    if polygon_mode == "original" or len(local_indices) <= 3:
        return [local_indices]
    return [(0, index, index + 1) for index in range(1, len(local_indices) - 1)]


def _material_names(model: "Lm2Model") -> dict[str, str]:
    keys = {_material_key(poly) for poly in model.polygons}
    names: dict[str, str] = {}
    for key in sorted(keys):
        prefix, value = key.split(":")
        names[key] = f"lm2_{prefix}_{int(value):03d}"
    return names


def _material_key(poly: "Polygon") -> str:
    if poly.has_texture and poly.texture is not None:
        return f"texture:{poly.texture}"
    return f"palette:{poly.palette_index}"


def _has_usable_uv(poly: "Polygon") -> bool:
    return bool(poly.has_texture and poly.uv and len(poly.uv) == len(poly.vertices))


def _used_texture_indices(model: "Lm2Model") -> set[int]:
    return {
        int(poly.texture)
        for poly in model.polygons
        if poly.has_texture and poly.texture is not None
    }


def _polygons_for_texture(model: "Lm2Model", texture_index: int) -> list[int]:
    return [
        index
        for index, poly in enumerate(model.polygons)
        if poly.has_texture and poly.texture == texture_index
    ]


def _crop_pixels(
    pixels: list[int], width: int, height: int, group: "UvGroup"
) -> list[int]:
    cropped: list[int] = []
    for y in range(group.h):
        source_y = min(height - 1, max(0, group.y + y))
        for x in range(group.w):
            source_x = min(width - 1, max(0, group.x + x))
            cropped.append(pixels[source_y * width + source_x])
    return cropped


def _write_png(path: Path, width: int, height: int, pixels: list[int]) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            color = pixels[y * width + x] if y * width + x < len(pixels) else 0
            rows.extend(
                (
                    (color >> 16) & 0xFF,
                    (color >> 8) & 0xFF,
                    color & 0xFF,
                    0xFF,
                )
            )
    payload = b"".join(
        (
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(bytes(rows))),
            _png_chunk(b"IEND", b""),
        )
    )
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + payload)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _decoded_bounds(model: "Lm2Model") -> dict[str, list[float]]:
    xs = [vertex.x for vertex in model.vertices]
    ys = [vertex.y for vertex in model.vertices]
    zs = [vertex.z for vertex in model.vertices]
    return {
        "x": [min(xs, default=0.0), max(xs, default=0.0)],
        "y": [min(ys, default=0.0), max(ys, default=0.0)],
        "z": [min(zs, default=0.0), max(zs, default=0.0)],
    }


def _unknown_region(model: "Lm2Model") -> dict[str, Any] | None:
    if model.header.unknown_count == 0:
        return None
    return {
        "section": "header.unknown",
        "offset": model.header.unknown_offset,
        "length": model.header.unknown_count * 8,
        "sha256": None,
        "confidence": "unknown",
        "note": "Parser currently skips this LM2 section and does not retain bytes.",
    }


def _viewer_world_scale() -> float:
    from lba2_lm2_viewer.viewer import WORLD_SCALE

    return WORLD_SCALE


def _git_info() -> dict[str, Any]:
    try:
        root = Path(__file__).resolve().parents[2]
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return {"git_commit": commit, "git_dirty": bool(dirty)}
    except Exception:
        return {"git_commit": None, "git_dirty": None}


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return stem or "lm2_model"
