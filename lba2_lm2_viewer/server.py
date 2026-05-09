"""HTTP server and mutable viewer session state."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import struct
import sys
import threading
import urllib.parse
import webbrowser
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import lba_hqr
from .animation import parse_lba2_animation_records, playback_frame_indices
from .catalog_graph import (
    build_catalog_graph,
    catalog_scene_object_relationship_projection,
    catalog_selection_projection,
    query_animation_operation_compatibility,
    query_compatible,
)
from .entities import (
    build_asset_entity_workflow,
    build_runtime_sprite_entity_workflow,
    build_scene_object_entity_workflow,
)
from .viewer import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    FRONTEND_DIST,
    DecodeProgress,
    Lm2Error,
    Lm2Model,
    build_catalog,
    apply_bkg_grm_fragment_to_composition,
    load_lm2_bytes,
    load_lm2_path,
    load_palette_from_asset_root,
    load_texture_atlas_from_asset_root,
    LBA_BKG_ARCHIVE_NAME,
    BKG_WORLD_CELL_SIZE_XZ,
    BKG_WORLD_CELL_SIZE_Y,
    SCREEN_IMAGE_WIDTH,
    SCREEN_IMAGE_HEIGHT,
    normalize_hqr_file_paths,
    parse_palette_payload,
    parse_text_payload_bank,
    parse_bkg_brick_graphic,
    parse_bkg_block_table,
    decode_bkg_grid_columns,
    decode_bkg_grm_fragment,
    parse_lsp_sprite_frame,
    parse_raw_sprite_frame,
    parse_multipart_upload,
    pick_directory_dialog,
    pick_hqr_files_dialog,
    pose_lm2_model,
    read_hqr_payload,
    runtime_object_sprite_state,
    selected_hqr_root,
)

DEFAULT_BROWSER_EXPORT_ROOT = Path("exports")
DEFAULT_PORT_REPO_ROOT = Path(r"D:\repos\reverse\littlebigreversing")
PROMOTABLE_PACKET_STATUSES = {"live_positive", "approved_exception"}


def default_browser_export_directory(asset_id: str) -> Path:
    safe_id = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in asset_id
    ).strip("._")
    return DEFAULT_BROWSER_EXPORT_ROOT / (safe_id or "asset")


def read_port_promotion_packets(
    port_root: Path = DEFAULT_PORT_REPO_ROOT,
) -> dict[str, Any]:
    manifest_path = port_root / "docs" / "promotion_packets" / "manifest.json"
    if not port_root.exists():
        raise Lm2Error(f"canonical port root is unavailable: {port_root}")
    if not manifest_path.is_file():
        raise Lm2Error(f"promotion packet manifest is unavailable: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "promotion-packets-v1":
        raise Lm2Error(f"unsupported promotion packet manifest schema: {manifest.get('schema')}")

    packets: list[dict[str, Any]] = []
    for packet in manifest.get("packets") or []:
        status = str(packet.get("status") or "")
        canonical_runtime = bool(packet.get("canonical_runtime"))
        if canonical_runtime and status not in PROMOTABLE_PACKET_STATUSES:
            raise Lm2Error(
                f"{packet.get('id')}: canonical_runtime=true requires live_positive or approved_exception"
            )
        fixture = packet.get("fixture")
        fixture_source = None
        fixture_path = None
        if isinstance(fixture, str) and fixture:
            fixture_path = port_root / fixture
            if fixture_path.is_file():
                fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
                source = fixture_payload.get("source")
                if isinstance(source, dict):
                    fixture_source = source
        packets.append(
            {
                "id": packet.get("id"),
                "status": status,
                "evidence_class": packet.get("evidence_class"),
                "canonical_runtime": canonical_runtime,
                "runtime_contracts": packet.get("runtime_contracts") or [],
                "packet": packet.get("packet"),
                "fixture": fixture,
                "fixture_source": fixture_source,
                "fixture_available": fixture_path.is_file() if fixture_path is not None else False,
            }
        )
    return {
        "schema": "viewer_port_promotion_packets.v0",
        "port_root": str(port_root),
        "manifest": str(manifest_path),
        "packets": packets,
    }


def indexed_frame_rgba(
    pixels: list[int],
    palette: list[int] | None,
    opaque_mask: list[bool] | None = None,
) -> list[int] | None:
    if palette is None:
        return None
    rgba: list[int] = []
    for index, pixel in enumerate(pixels):
        color = palette[pixel] if 0 <= pixel < len(palette) else 0
        opaque = opaque_mask[index] if opaque_mask is not None and index < len(opaque_mask) else pixel != 0
        rgba.extend(
            [
                (color >> 16) & 0xFF,
                (color >> 8) & 0xFF,
                color & 0xFF,
                255 if opaque else 0,
            ]
        )
    return rgba


def write_rgba_png(path: Path, width: int, height: int, rgba: list[int]) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        start = y * width * 4
        end = start + width * 4
        rows.extend(rgba[start:end])
    payload = b"".join(
        (
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            png_chunk(b"IDAT", zlib.compress(bytes(rows))),
            png_chunk(b"IEND", b""),
        )
    )
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + payload)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


class ViewerServer:
    def __init__(self, initial_path: Path | None, asset_root: Path | None) -> None:
        self.initial_path = initial_path
        self.operation_lock = threading.RLock()
        self.last_model: dict[str, Any] | None = None
        self.asset_root: Path | None = None
        self.catalog: dict[str, Any] | None = None
        self.catalog_graph = None
        self.palette: list[int] | None = None
        self.texture_atlas: dict[str, Any] | None = None
        self.decode_progress = DecodeProgress()
        if asset_root is not None:
            self.set_asset_root(asset_root)
        if initial_path is not None:
            self.last_model = self.model_json(
                load_lm2_path(initial_path), str(initial_path)
            )

    def clear_loaded_assets(self) -> None:
        self.last_model = None
        self.catalog = None
        self.catalog_graph = None
        self.palette = None
        self.texture_atlas = None

    def set_asset_root(self, asset_root: Path) -> dict[str, Any]:
        with self.operation_lock:
            resolved = asset_root.expanduser().resolve()
            self.decode_progress.begin(f"Scanning {resolved}", phase="scanning")
            self.clear_loaded_assets()
            self.asset_root = resolved
            try:
                self.catalog = build_catalog(resolved, self.decode_progress)
                self.attach_catalog_graph_projection()
                self.decode_progress.update(
                    label="Loading palette and texture atlas", phase="finalizing"
                )
                self.load_visual_assets(resolved)
                self.decode_progress.finish(self.catalog.get("summary", {}))
                return self.catalog
            except Exception as exc:
                self.decode_progress.fail(str(exc))
                raise

    def set_asset_files(self, paths: list[Path]) -> dict[str, Any]:
        with self.operation_lock:
            files = normalize_hqr_file_paths(paths)
            resolved_root = selected_hqr_root(files)
            self.decode_progress.begin(
                f"Scanning {len(files)} selected HQR file(s)", phase="scanning"
            )
            self.clear_loaded_assets()
            self.asset_root = resolved_root
            try:
                self.catalog = build_catalog(resolved_root, self.decode_progress, files)
                self.attach_catalog_graph_projection()
                self.decode_progress.update(
                    label="Loading palette and texture atlas", phase="finalizing"
                )
                self.load_visual_assets(resolved_root)
                self.decode_progress.finish(self.catalog.get("summary", {}))
                return self.catalog
            except Exception as exc:
                self.decode_progress.fail(str(exc))
                raise

    def load_visual_assets(self, asset_root: Path) -> None:
        try:
            self.palette = load_palette_from_asset_root(asset_root)
            self.texture_atlas = load_texture_atlas_from_asset_root(
                asset_root, self.palette
            )
        except Lm2Error:
            self.palette = None
            self.texture_atlas = None

    def attach_catalog_graph_projection(self) -> None:
        if self.catalog is None:
            self.catalog_graph = None
            return
        self.catalog_graph = build_catalog_graph(self.catalog)
        compatibility_by_model: dict[str, list[dict[str, Any]]] = {}
        for model_id, animation_ids in self.catalog_graph.indexes.get("compatibleAnimationsByModelId", {}).items():
            compatible = query_compatible(self.catalog_graph, str(model_id))
            edges_by_animation = {
                edge.get("from", "").removeprefix("asset:"): edge
                for edge in compatible.get("edges") or []
            }
            compatibility_by_model[str(model_id)] = [
                {
                    "animationId": animation_id,
                    "compatibilityReason": (edges_by_animation.get(animation_id) or {}).get("compatibilityReason"),
                    "proofScope": (edges_by_animation.get(animation_id) or {}).get("proofScope"),
                    "evidenceStatus": (edges_by_animation.get(animation_id) or {}).get("evidenceStatus"),
                    "sourceRule": (edges_by_animation.get(animation_id) or {}).get("sourceRule"),
                    "sourceField": (edges_by_animation.get(animation_id) or {}).get("sourceField"),
                    "indexRule": (edges_by_animation.get(animation_id) or {}).get("indexRule"),
                }
                for animation_id in animation_ids
            ]
        self.catalog["graph"] = {
            "schema": "catalog_graph.catalog_projection.v0",
            "indexes": {
                "compatibleAnimationsByModelId": self.catalog_graph.indexes.get("compatibleAnimationsByModelId", {}),
            },
            "compatibilityByModelId": compatibility_by_model,
            "selectionByAssetId": catalog_selection_projection(self.catalog_graph),
            "sceneObjectRelationshipsByStableId": catalog_scene_object_relationship_projection(self.catalog_graph),
        }

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

    def model_json(
        self,
        model: Lm2Model,
        source_name: str | None = None,
        pose: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return model.to_viewer_json(
            source_name,
            palette=self.palette,
            texture_atlas=self.texture_atlas,
            pose=pose,
        )

    def find_catalog_asset(self, asset_id: str) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        for asset in self.catalog.get("assets", []):
            if asset.get("id") == asset_id:
                return asset
        raise Lm2Error(f"catalog asset not found: {asset_id}")

    def maybe_find_catalog_asset(self, asset_id: str | None) -> dict[str, Any] | None:
        if self.catalog is None or not asset_id:
            return None
        for asset in self.catalog.get("assets", []):
            if asset.get("id") == asset_id:
                return asset
        return None

    def resolve_runtime_sprite_object(self, request: dict[str, Any]) -> dict[str, Any]:
        body_num_value = request.get("body_num")
        label_track_value = request.get("label_track")
        object_index_value = request.get("object_index")
        state = runtime_object_sprite_state(
            flags=int(request.get("flags") or 0),
            sprite_index=int(request.get("sprite_index") or 0),
            body_num=int(body_num_value) if body_num_value is not None else None,
            label_track=int(label_track_value) if label_track_value is not None else None,
            object_index=int(object_index_value) if object_index_value is not None else None,
        )
        resolution = state["resolution"]
        asset = self.maybe_find_catalog_asset(resolution.get("asset_id"))
        state["catalog_asset"] = asset
        state["catalog_asset_available"] = asset is not None
        if asset is not None:
            stats = asset.get("stats") or {}
            runtime = stats.get("runtime") if isinstance(stats, dict) else None
            if isinstance(runtime, dict):
                resolution["hotspot"] = runtime.get("hotspot")
                resolution["bounds"] = runtime.get("bounds")
                resolution["runtime_sprite_index"] = runtime.get("runtime_sprite_index")
        return state

    def asset_entity_workflow(self, asset_id: str) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        workflow = build_asset_entity_workflow(self.catalog, asset_id)
        if workflow.get("resolved_asset") is None:
            raise Lm2Error(f"catalog asset not found: {asset_id}")
        return workflow

    def scene_object_entity_workflow(
        self, scene_asset_id: str, object_index: int
    ) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        workflow = build_scene_object_entity_workflow(
            self.catalog, scene_asset_id, object_index
        )
        if workflow.get("resolved_asset") is None:
            raise Lm2Error(f"scene asset not found: {scene_asset_id}")
        return workflow

    def runtime_sprite_entity_workflow(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        state = self.resolve_runtime_sprite_object(request)
        return build_runtime_sprite_entity_workflow(self.catalog, state)

    def catalog_graph_compatible(self, model_id: str) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        if self.catalog_graph is None:
            self.attach_catalog_graph_projection()
        return query_compatible(self.catalog_graph, model_id)

    def ensure_animation_operation_compatible(
        self,
        body_asset: dict[str, Any],
        animation_asset: dict[str, Any],
        operation: str = "pose_playback",
    ) -> None:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        if self.catalog_graph is None:
            self.attach_catalog_graph_projection()
        result = query_animation_operation_compatibility(
            self.catalog_graph,
            str(body_asset.get("id")),
            str(animation_asset.get("id")),
            operation=operation,
        )
        if not result["eligible"]:
            raise Lm2Error(
                str(result.get("error") or "animation is not graph-compatible with the selected model")
            )

    def export_evidence_context(
        self, asset: dict[str, Any], proof_scope: str
    ) -> dict[str, Any]:
        packet_links = self.export_promotion_packet_links(asset)
        return {
            "stable_id": asset.get("id"),
            "evidence_status": self.export_evidence_status(asset),
            "proof_scope": proof_scope,
            "scene_usage_count": len(asset.get("scene_usages") or []),
            "runtime_contract_ids": packet_links["runtime_contract_ids"],
            "promotion_packet_ids": packet_links["promotion_packet_ids"],
            "promotion_packet_source": packet_links["promotion_packet_source"],
        }

    def export_evidence_source_fields(
        self, asset: dict[str, Any], proof_scope: str
    ) -> dict[str, Any]:
        context = self.export_evidence_context(asset, proof_scope)
        return {
            "evidence_status": context["evidence_status"],
            "proof_scope": context["proof_scope"],
            "scene_usage_count": context["scene_usage_count"],
            "runtime_contract_ids": context["runtime_contract_ids"],
            "promotion_packet_ids": context["promotion_packet_ids"],
            "promotion_packet_source": context["promotion_packet_source"],
        }

    def export_promotion_packet_links(self, asset: dict[str, Any]) -> dict[str, Any]:
        scene_indices = self.export_scene_indices_for_asset(asset)
        if not scene_indices:
            return {
                "promotion_packet_ids": [],
                "runtime_contract_ids": [],
                "promotion_packet_source": "not_scene_linked",
            }
        try:
            payload = read_port_promotion_packets()
        except Lm2Error as exc:
            return {
                "promotion_packet_ids": [],
                "runtime_contract_ids": [],
                "promotion_packet_source": f"unavailable: {exc}",
            }
        packet_ids: list[str] = []
        contract_ids: list[str] = []
        for packet in payload.get("packets") or []:
            fixture_source = packet.get("fixture_source")
            if not isinstance(fixture_source, dict):
                continue
            if fixture_source.get("scene") not in scene_indices:
                continue
            packet_id = packet.get("id")
            if isinstance(packet_id, str) and packet_id not in packet_ids:
                packet_ids.append(packet_id)
            for contract_id in packet.get("runtime_contracts") or []:
                if isinstance(contract_id, str) and contract_id not in contract_ids:
                    contract_ids.append(contract_id)
        return {
            "promotion_packet_ids": packet_ids,
            "runtime_contract_ids": contract_ids,
            "promotion_packet_source": payload.get("manifest") or "canonical_manifest",
        }

    @staticmethod
    def export_scene_indices_for_asset(asset: dict[str, Any]) -> set[int]:
        indices: set[int] = set()
        source = asset.get("source") or {}
        if asset.get("kind") == "scene" and source.get("hqr") == "SCENE.HQR":
            entry_index = source.get("entry_index")
            if isinstance(entry_index, int):
                indices.add(entry_index - 1)
        for usage in asset.get("scene_usages") or []:
            if not isinstance(usage, dict):
                continue
            scene_index = usage.get("scene_index")
            if isinstance(scene_index, int):
                indices.add(scene_index)
                continue
            scene_entry_index = usage.get("scene_entry_index")
            if isinstance(scene_entry_index, int):
                indices.add(scene_entry_index - 1)
        return indices

    @staticmethod
    def export_evidence_status(asset: dict[str, Any]) -> str:
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

    def export_catalog_asset(
        self, asset_id: str, output_dir: Path, polygon_mode: str = "original"
    ) -> dict[str, Any]:
        from .exports import export_model_probe

        if polygon_mode not in ("original", "triangulated"):
            raise Lm2Error(f"unsupported polygon mode: {polygon_mode}")

        with self.operation_lock:
            if self.asset_root is None:
                raise Lm2Error("no asset root loaded")
            asset = self.find_catalog_asset(asset_id)
            stats = asset.get("stats") or {}
            if asset.get("kind") == "resource" and stats.get("semantic_layout") == "bkg_grid_map":
                return self.export_bkg_grid_composition(asset, output_dir)
            if asset.get("kind") == "resource" and stats.get("semantic_layout") == "screen_indexed_image_640x480":
                return self.export_screen_indexed_image_asset(asset, output_dir)
            if asset.get("kind") == "resource" and stats.get("semantic_layout") in ("lba2_indexed_image_256", "lba2_texture_atlas_indexed"):
                return self.export_ress_indexed_image_asset(asset, output_dir)
            if asset.get("kind") == "resource" and stats.get("semantic_layout") == "holomap_plan_image_640x480":
                return self.export_holomap_plan_image_asset(asset, output_dir)
            if asset.get("kind") == "resource" and stats.get("semantic_layout") == "text_payload_bank":
                return self.export_text_payload_bank_asset(asset, output_dir)
            if asset.get("kind") == "resource" and stats.get("semantic_layout") == "smacker_video":
                return self.export_smacker_video_asset(asset, output_dir)
            if asset.get("kind") == "scene":
                return self.export_scene_background_composition(asset, output_dir)
            if asset.get("kind") == "sprite" and stats.get("semantic_layout") in ("lsp_sprite_frame", "raw_sprite_frame"):
                return self.export_sprite_frame_asset(asset, output_dir)
            if asset.get("kind") == "resource" and stats.get("semantic_layout") == "sample_wave_audio":
                return self.export_sample_audio_asset(asset, output_dir)
            if asset.get("kind") != "model":
                raise Lm2Error(f"catalog asset is not exportable: {asset_id}")
            payload, resource = read_hqr_payload(self.asset_root, asset["source"])
            model = load_lm2_bytes(payload, str(asset["relative_path"]))
            warnings: list[str] = []
            if self.texture_atlas is None and any(
                poly.has_texture for poly in model.polygons
            ):
                warnings.append("texture atlas unavailable; texture PNGs not exported")
            source = {
                "asset_root": str(self.asset_root),
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
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
                **self.export_evidence_source_fields(
                    asset,
                    "decoded model geometry and generated OBJ/texture evidence; not live runtime gameplay proof",
                ),
            }
            manifest = export_model_probe(
                model=model,
                output_dir=output_dir,
                source=source,
                polygon_mode=polygon_mode,
                palette=self.palette,
                texture_atlas=self.texture_atlas,
                warnings=warnings,
            )
            return {"output_dir": str(output_dir.resolve()), "manifest": manifest}

    def sample_audio_payload(self, asset_id: str) -> tuple[bytes, dict[str, Any]]:
        with self.operation_lock:
            if self.asset_root is None:
                raise Lm2Error("no asset root loaded")
            asset = self.find_catalog_asset(asset_id)
            stats = asset.get("stats") or {}
            if asset.get("kind") != "resource" or stats.get("semantic_layout") != "sample_wave_audio":
                raise Lm2Error(f"catalog asset is not a decoded sample: {asset_id}")
            payload, _ = read_hqr_payload(self.asset_root, asset["source"])
            if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
                raise Lm2Error(f"sample asset is not decoded RIFF/WAVE audio: {asset_id}")
            return payload, asset

    def export_sprite_frame_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        if self.palette is None:
            raise Lm2Error("sprite PNG export requires RESS.HQR:0 normal palette")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        frames = self.sprite_export_frames(asset)
        if not frames:
            raise Lm2Error(f"sprite export found no decoded frames for {asset.get('id')}")

        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        manifest_name = "manifest.json"
        cell_width = max(int(frame["decoded"]["width"]) for frame in frames)
        cell_height = max(int(frame["decoded"]["height"]) for frame in frames)
        columns = max(1, int(len(frames) ** 0.5))
        while columns * columns < len(frames):
            columns += 1
        rows = (len(frames) + columns - 1) // columns
        sheet_width = cell_width * columns
        sheet_height = cell_height * rows
        sheet_rgba = [0] * (sheet_width * sheet_height * 4)
        frame_files: list[dict[str, Any]] = []

        for index, frame in enumerate(frames):
            decoded = frame["decoded"]
            frame_asset = frame["asset"]
            rgba = indexed_frame_rgba(decoded["pixels"], self.palette)
            if rgba is None:
                raise Lm2Error("sprite PNG export requires a loaded palette")
            frame_name = f"{base_name}_frame_{index:03d}_{frame_asset['source']['entry_index']}.png"
            write_rgba_png(
                output_dir / frame_name,
                int(decoded["width"]),
                int(decoded["height"]),
                rgba,
            )
            sheet_x = (index % columns) * cell_width
            sheet_y = (index // columns) * cell_height
            self.blit_rgba(
                sheet_rgba,
                sheet_width,
                sheet_x,
                sheet_y,
                rgba,
                int(decoded["width"]),
                int(decoded["height"]),
            )
            frame_stats = frame_asset.get("stats") or {}
            runtime = frame_stats.get("runtime") if isinstance(frame_stats, dict) else None
            anim3ds_info = frame_stats.get("anim3ds_info") if isinstance(frame_stats, dict) else None
            frame_files.append(
                {
                    "asset_id": frame_asset.get("id"),
                    "label": frame_asset.get("label"),
                    "entry_index": frame_asset.get("source", {}).get("entry_index"),
                    "png": frame_name,
                    "sheet_x": sheet_x,
                    "sheet_y": sheet_y,
                    "width": int(decoded["width"]),
                    "height": int(decoded["height"]),
                    "offset_x": int(decoded["offset_x"]),
                    "offset_y": int(decoded["offset_y"]),
                    "runtime_sprite_index": (
                        runtime.get("runtime_sprite_index")
                        if isinstance(runtime, dict)
                        else None
                    ),
                    "anim3ds_range": anim3ds_info if isinstance(anim3ds_info, dict) else None,
                }
            )

        sheet_name = f"{base_name}_sheet.png"
        write_rgba_png(output_dir / sheet_name, sheet_width, sheet_height, sheet_rgba)
        selected_stats = asset.get("stats") or {}
        selected_runtime = (
            selected_stats.get("runtime") if isinstance(selected_stats, dict) else None
        )
        manifest = {
            "schema_version": "sprite_frame_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
                "catalog_asset_id": asset["id"],
                "catalog_label": asset.get("label"),
                "archive": asset["source"].get("hqr"),
                "entry_index": asset["source"].get("entry_index"),
                "classic_index": asset["source"].get("classic_index"),
                "archive_offset": asset["source"].get("offset"),
                "archive_raw_bytes": asset["source"].get("raw_bytes"),
                "archive_raw_sha256": asset["source"].get("raw_sha256"),
                "decoded_bytes": asset.get("decoded_bytes"),
                "decoded_sha256": asset.get("decoded_sha256"),
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "decoded sprite frame pixels and sheet export; not live runtime gameplay proof",
            ),
            "options": {
                "format": (
                    "raw_sprite_rgba_png"
                    if selected_stats.get("semantic_layout") == "raw_sprite_frame"
                    else "lsp_sprite_rgba_png"
                ),
                "sheet_layout": "fixed_cell_grid",
                "cell_width": cell_width,
                "cell_height": cell_height,
                "columns": columns,
                "rows": rows,
                "palette_source": "RESS.HQR:0 normal palette",
                "range_policy": (
                    "selected ANIM3DS range"
                    if selected_stats.get("anim3ds_info")
                    else "selected sprite frame"
                ),
            },
            "stats": {
                "frame_count": len(frames),
                "sheet_width": sheet_width,
                "sheet_height": sheet_height,
                "runtime_sprite_index": (
                    selected_runtime.get("runtime_sprite_index")
                    if isinstance(selected_runtime, dict)
                    else None
                ),
                "opaque_pixels": sum(
                    int(frame["decoded"].get("opaque_pixels", 0)) for frame in frames
                ),
            },
            "files": {
                "manifest": manifest_name,
                "sprite_png": frame_files[0]["png"],
                "sheet_png": sheet_name,
                "frames": frame_files,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def sprite_export_frames(self, asset: dict[str, Any]) -> list[dict[str, Any]]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        anim3ds_info = stats.get("anim3ds_info") if isinstance(stats, dict) else None
        if not isinstance(anim3ds_info, dict):
            return [self.sprite_export_frame(asset)]
        start = anim3ds_info.get("start_frame")
        end = anim3ds_info.get("end_frame")
        name = anim3ds_info.get("name")
        if not isinstance(start, int) or not isinstance(end, int):
            return [self.sprite_export_frame(asset)]
        candidates: list[dict[str, Any]] = []
        for candidate in (self.catalog or {}).get("assets", []):
            if candidate.get("kind") != "sprite" or candidate.get("entry_type") != "anim3ds-frame":
                continue
            candidate_stats = candidate.get("stats") or {}
            candidate_info = (
                candidate_stats.get("anim3ds_info")
                if isinstance(candidate_stats, dict)
                else None
            )
            if not isinstance(candidate_info, dict):
                continue
            if (
                candidate_info.get("name") == name
                and candidate_info.get("start_frame") == start
                and candidate_info.get("end_frame") == end
            ):
                candidates.append(candidate)
        candidates.sort(
            key=lambda candidate: (
                ((candidate.get("stats") or {}).get("anim3ds_info") or {}).get(
                    "relative_frame", candidate.get("source", {}).get("entry_index", 0)
                ),
                candidate.get("source", {}).get("entry_index", 0),
            )
        )
        return [self.sprite_export_frame(candidate) for candidate in candidates] or [
            self.sprite_export_frame(asset)
        ]

    def sprite_export_frame(self, asset: dict[str, Any]) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        payload, _ = read_hqr_payload(self.asset_root, asset["source"])
        stats = asset.get("stats") or {}
        decoded = (
            parse_raw_sprite_frame(payload)
            if stats.get("semantic_layout") == "raw_sprite_frame"
            else parse_lsp_sprite_frame(payload)
        )
        return {"asset": asset, "decoded": decoded}

    def export_sample_audio_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
            raise Lm2Error(f"sample asset is not decoded RIFF/WAVE audio: {asset.get('id')}")
        stats = asset.get("stats") or {}
        fields = stats.get("fields") if isinstance(stats, dict) else None
        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        wav_name = f"{base_name}.wav"
        manifest_name = "manifest.json"
        (output_dir / wav_name).write_bytes(payload)
        manifest = {
            "schema_version": "sample_audio_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
                "catalog_asset_id": asset["id"],
                "catalog_label": asset.get("label"),
                "archive": asset["source"].get("hqr"),
                "entry_index": asset["source"].get("entry_index"),
                "hqr_table_index": asset["source"].get("hqr_table_index"),
                "archive_offset": asset["source"].get("offset"),
                "archive_raw_bytes": asset["source"].get("raw_bytes"),
                "archive_raw_sha256": asset["source"].get("raw_sha256"),
                "decoded_bytes": len(payload),
                "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                "resource": resource,
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "decoded RIFF/WAVE sample evidence; not live audio playback or gameplay proof",
            ),
            "options": {
                "format": "decoded_riff_wave",
                "runtime_id_rule": "SAMPLES.HQR catalog id equals zero-based runtime sample id; source hqr_table_index is runtime id + 1.",
                "preserve_container": True,
            },
            "audio": {
                "runtime_sample_id": stats.get("sample_runtime_index"),
                "audio_format": stats.get("audio_format"),
                "channels": (fields or {}).get("channels") if isinstance(fields, dict) else None,
                "sample_rate": (fields or {}).get("sample_rate") if isinstance(fields, dict) else None,
                "bits_per_sample": (fields or {}).get("bits_per_sample") if isinstance(fields, dict) else None,
                "block_align": (fields or {}).get("block_align") if isinstance(fields, dict) else None,
                "data_bytes": (fields or {}).get("data_bytes") if isinstance(fields, dict) else None,
                "sample_frames": stats.get("sample_frames"),
                "duration_ms": stats.get("duration_ms"),
                "samples_per_block": stats.get("samples_per_block"),
                "fact_sample_frames": stats.get("fact_sample_frames"),
                "chunk_ids": stats.get("chunk_ids"),
            },
            "files": {
                "manifest": manifest_name,
                "wav": wav_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def export_text_payload_bank_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "text_payload_bank":
            raise Lm2Error(f"catalog asset is not a TEXT payload bank: {asset.get('id')}")
        paired_entry = stats.get("paired_entry_index")
        if not isinstance(paired_entry, int):
            raise Lm2Error(f"TEXT payload bank is missing paired order table: {asset.get('id')}")
        order_asset = self.find_catalog_asset(f"{asset['source']['hqr']}:{paired_entry}")
        order_stats = order_asset.get("stats") or {}
        if order_stats.get("semantic_layout") != "text_order_table":
            raise Lm2Error(f"paired TEXT asset is not an order table: {order_asset.get('id')}")

        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        order_payload, order_resource = read_hqr_payload(self.asset_root, order_asset["source"])
        if len(order_payload) == 0 or len(order_payload) % 2 != 0:
            raise Lm2Error(f"TEXT order table has invalid byte length: {len(order_payload)}")
        message_ids = list(struct.unpack(f"<{len(order_payload) // 2}H", order_payload))
        offsets, parsed_records = parse_text_payload_bank(payload)
        if len(message_ids) != len(parsed_records):
            raise Lm2Error(
                f"TEXT order table/message bank count mismatch: {len(message_ids)} ids, "
                f"{len(parsed_records)} records"
            )

        records: list[dict[str, Any]] = []
        for record, message_id in zip(parsed_records, message_ids):
            start = int(record["offset"])
            end = start + int(record["byte_length"])
            raw_record = payload[start:end]
            text_body = raw_record[1:]
            text = text_body.replace(b"\x01", b"\n").split(b"\x00", 1)[0].decode(
                "cp850", errors="replace"
            )
            records.append(
                {
                    "record_index": record["index"],
                    "message_id": message_id,
                    "offset": start,
                    "byte_length": record["byte_length"],
                    "flag": record["flag"],
                    "text": text,
                    "raw_record_hex": raw_record.hex(),
                    "raw_text_hex": text_body.hex(),
                    "terminates_with_nul": record["terminates_with_nul"],
                    "page_break_count": record["page_break_count"],
                }
            )

        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        bundle_name = f"{base_name}_text.json"
        manifest_name = "manifest.json"
        bundle = {
            "schema_version": "text_payload_bank_bundle.v0",
            "catalog_asset_id": asset["id"],
            "order_asset_id": order_asset["id"],
            "language_index": stats.get("language_index"),
            "language": stats.get("language"),
            "text_file_index": stats.get("text_file_index"),
            "text_file_name": stats.get("text_file_name"),
            "record_count": len(records),
            "codepage": "cp850",
            "records": records,
            "runtime_resolution_rule": "InitDial(file) loads TEXT.HQR[file*2] into BufOrder and TEXT.HQR[file*2+1] into BufText; FindText(message_id) finds the order-table slot, then GetText reads the same slot from the payload bank.",
        }
        (output_dir / bundle_name).write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        manifest = {
            "schema_version": "text_payload_bank_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
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
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "decoded text bank and paired order-table evidence; not live dialog flow proof",
            ),
            "order_table": {
                "catalog_asset_id": order_asset["id"],
                "archive": order_asset["source"].get("hqr"),
                "entry_index": order_asset["source"].get("entry_index"),
                "classic_index": order_asset["source"].get("classic_index"),
                "archive_offset": order_asset["source"].get("offset"),
                "archive_raw_bytes": order_asset["source"].get("raw_bytes"),
                "archive_raw_sha256": order_asset["source"].get("raw_sha256"),
                "decoded_bytes": len(order_payload),
                "decoded_sha256": hashlib.sha256(order_payload).hexdigest(),
                "resource": order_resource,
                "unique_message_ids": len(set(message_ids)),
            },
            "options": {
                "format": "decoded_text_json",
                "codepage": "cp850",
                "preserve_raw_record_bytes": True,
                "runtime_resolution_rule": bundle["runtime_resolution_rule"],
            },
            "text": {
                "language_index": stats.get("language_index"),
                "language": stats.get("language"),
                "text_file_index": stats.get("text_file_index"),
                "text_file_name": stats.get("text_file_name"),
                "paired_order_entry": paired_entry,
                "record_count": len(records),
                "offset_table_bytes": stats.get("offset_table_bytes"),
                "flag_counts": stats.get("type_counts"),
            },
            "files": {
                "manifest": manifest_name,
                "bundle_json": bundle_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def export_smacker_video_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "smacker_video":
            raise Lm2Error(f"catalog asset is not a Smacker video: {asset.get('id')}")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        if payload[:3] != b"SMK":
            raise Lm2Error(f"video asset is not a Smacker container: {asset.get('id')}")
        acf_name = str(stats.get("acf_name") or f"ACF_{stats.get('acf_index', asset['source']['entry_index'])}")
        stem = "".join(
            char if char.isalnum() or char in ("-", "_", ".") else "_"
            for char in acf_name
        ).strip("._")
        if not stem:
            stem = f"VIDEO_HQR_{asset['source']['entry_index']}"
        if not stem.lower().endswith(".smk"):
            stem = f"{stem}.SMK"
        smk_name = stem
        manifest_name = "manifest.json"
        (output_dir / smk_name).write_bytes(payload)
        manifest = {
            "schema_version": "smacker_video_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
                "catalog_asset_id": asset["id"],
                "catalog_label": asset.get("label"),
                "archive": asset["source"].get("hqr"),
                "entry_index": asset["source"].get("entry_index"),
                "hqr_table_index": asset["source"].get("hqr_table_index"),
                "archive_offset": asset["source"].get("offset"),
                "archive_raw_bytes": asset["source"].get("raw_bytes"),
                "archive_raw_sha256": asset["source"].get("raw_sha256"),
                "decoded_bytes": len(payload),
                "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                "resource": resource,
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "original Smacker container and metadata evidence; not codec decode or live playback proof",
            ),
            "options": {
                "format": "smacker_container_passthrough",
                "codec_decode": False,
                "runtime_id_rule": "GetNumAcf matches PLAY_ACF names against RESS.HQR:48 and uses that zero-based index to load VIDEO/VIDEO.HQR.",
                "preserve_container": True,
            },
            "video": {
                "acf_index": stats.get("acf_index"),
                "acf_name": stats.get("acf_name"),
                "acf_basename": stats.get("acf_basename"),
                "name_source": stats.get("name_source"),
                "width": stats.get("width"),
                "height": stats.get("height"),
                "frame_count": stats.get("frame_count"),
                "frames_per_second": stats.get("frames_per_second"),
                "duration_ms": stats.get("duration_ms"),
                "header": stats.get("header"),
                "scene_usage_count": len(asset.get("scene_usages") or []),
                "scene_usages": asset.get("scene_usages") or [],
            },
            "files": {
                "manifest": manifest_name,
                "smk": smk_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def screen_indexed_image_frame(self, asset: dict[str, Any]) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "screen_indexed_image_640x480":
            raise Lm2Error(f"catalog asset is not a SCREEN indexed image: {asset.get('id')}")
        payload, _ = read_hqr_payload(self.asset_root, asset["source"])
        if len(payload) != SCREEN_IMAGE_WIDTH * SCREEN_IMAGE_HEIGHT:
            raise Lm2Error(f"SCREEN image payload has invalid size: {len(payload)}")
        palette_ref = stats.get("palette_entry")
        if not isinstance(palette_ref, dict):
            raise Lm2Error(f"SCREEN image is missing paired palette reference: {asset.get('id')}")
        palette_asset = self.find_catalog_asset(
            f"{palette_ref.get('hqr')}:{palette_ref.get('entry_index')}"
        )
        palette_payload, _ = read_hqr_payload(self.asset_root, palette_asset["source"])
        palette = parse_palette_payload(palette_payload)
        pixels = list(payload)
        return {
            "format": "screen_indexed_image",
            "width": SCREEN_IMAGE_WIDTH,
            "height": SCREEN_IMAGE_HEIGHT,
            "offset_x": 0,
            "offset_y": 0,
            "pixels": pixels,
            "rgba": indexed_frame_rgba(pixels, palette, [True] * len(pixels)),
            "palette_available": True,
            "palette_source": f"{palette_ref.get('hqr')}:{palette_ref.get('entry_index')} paired PCR palette",
        }

    def export_screen_indexed_image_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        frame = self.screen_indexed_image_frame(asset)
        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        png_name = f"{base_name}.png"
        manifest_name = "manifest.json"
        write_rgba_png(
            output_dir / png_name,
            int(frame["width"]),
            int(frame["height"]),
            frame["rgba"],
        )
        stats = asset.get("stats") or {}
        manifest = {
            "schema_version": "screen_indexed_image_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
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
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "indexed screen image with paired palette evidence; not live UI flow proof",
            ),
            "options": {
                "format": "screen_indexed_rgba_png",
                "palette_source": frame["palette_source"],
                "runtime_id_rule": "SCREEN.HQR catalog ids match classic zero-based PCR constants; even slots are indexed images and odd PCR+1 slots are palettes.",
            },
            "screen": {
                "screen_name": stats.get("screen_name"),
                "screen_pair_base": stats.get("screen_pair_base"),
                "palette_entry": stats.get("palette_entry"),
                "width": frame["width"],
                "height": frame["height"],
                "unique_palette_indices": stats.get("unique_palette_indices"),
            },
            "files": {
                "manifest": manifest_name,
                "png": png_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def ress_indexed_image_frame(self, asset: dict[str, Any]) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") not in ("lba2_indexed_image_256", "lba2_texture_atlas_indexed"):
            raise Lm2Error(f"catalog asset is not a RESS indexed image: {asset.get('id')}")
        if self.palette is None:
            raise Lm2Error("RESS indexed image preview requires RESS.HQR:0 normal palette")
        payload, _ = read_hqr_payload(self.asset_root, asset["source"])
        width = int(stats.get("width") or 0)
        height = int(stats.get("height") or 0)
        if width <= 0 or height <= 0 or len(payload) != width * height:
            raise Lm2Error(f"RESS indexed image payload has invalid dimensions/size: {width}x{height}, {len(payload)} bytes")
        pixels = list(payload)
        return {
            "format": str(stats.get("semantic_layout")),
            "width": width,
            "height": height,
            "offset_x": 0,
            "offset_y": 0,
            "pixels": pixels,
            "rgba": indexed_frame_rgba(pixels, self.palette, [True] * len(pixels)),
            "palette_available": True,
            "palette_source": "RESS.HQR:0 normal palette",
        }

    def export_ress_indexed_image_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        frame = self.ress_indexed_image_frame(asset)
        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        png_name = f"{base_name}.png"
        manifest_name = "manifest.json"
        write_rgba_png(
            output_dir / png_name,
            int(frame["width"]),
            int(frame["height"]),
            frame["rgba"],
        )
        stats = asset.get("stats") or {}
        manifest = {
            "schema_version": "ress_indexed_image_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
                "catalog_asset_id": asset["id"],
                "catalog_label": asset.get("label"),
                "archive": asset["source"].get("hqr"),
                "entry_index": asset["source"].get("entry_index"),
                "archive_offset": asset["source"].get("offset"),
                "archive_raw_bytes": asset["source"].get("raw_bytes"),
                "archive_raw_sha256": asset["source"].get("raw_sha256"),
                "decoded_bytes": len(payload),
                "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                "resource": resource,
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "indexed RESS image rendered with explicit palette context; not live runtime proof",
            ),
            "options": {
                "format": "ress_indexed_rgba_png",
                "semantic_layout": stats.get("semantic_layout"),
                "palette_source": frame["palette_source"],
            },
            "image": {
                "width": frame["width"],
                "height": frame["height"],
                "unique_palette_indices": stats.get("unique_palette_indices"),
                "palette_entry": stats.get("palette_entry"),
            },
            "files": {
                "manifest": manifest_name,
                "png": png_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def holomap_plan_image_frame(self, asset: dict[str, Any]) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "holomap_plan_image_640x480":
            raise Lm2Error(f"catalog asset is not a HOLOMAP plan image: {asset.get('id')}")
        if self.palette is None:
            raise Lm2Error("HOLOMAP plan image preview requires RESS.HQR:0 normal palette")
        payload, _ = read_hqr_payload(self.asset_root, asset["source"])
        if len(payload) != SCREEN_IMAGE_WIDTH * SCREEN_IMAGE_HEIGHT:
            raise Lm2Error(f"HOLOMAP plan image payload has invalid size: {len(payload)}")
        pixels = list(payload)
        return {
            "format": "holomap_plan_image",
            "width": SCREEN_IMAGE_WIDTH,
            "height": SCREEN_IMAGE_HEIGHT,
            "offset_x": 0,
            "offset_y": 0,
            "pixels": pixels,
            "rgba": indexed_frame_rgba(pixels, self.palette, [True] * len(pixels)),
            "palette_available": True,
            "palette_source": "RESS.HQR:0 normal palette",
        }

    def export_holomap_plan_image_asset(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        frame = self.holomap_plan_image_frame(asset)
        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        png_name = f"{base_name}.png"
        manifest_name = "manifest.json"
        write_rgba_png(
            output_dir / png_name,
            int(frame["width"]),
            int(frame["height"]),
            frame["rgba"],
        )
        stats = asset.get("stats") or {}
        manifest = {
            "schema_version": "holomap_plan_image_export_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
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
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "holomap plan image rendered with explicit palette context; not live holomap behavior proof",
            ),
            "options": {
                "format": "holomap_plan_rgba_png",
                "palette_source": frame["palette_source"],
                "runtime_selection_rule": "HOLOPLAN.CPP InitHoloPlan uses HQR_BEGIN_MAP + 2*ZoomedIsland, with storm/celebration variants.",
            },
            "plan": {
                "holomap_name": stats.get("holomap_name"),
                "plan_variant": stats.get("plan_variant"),
                "paired_params_entry": stats.get("paired_entry_index"),
                "width": frame["width"],
                "height": frame["height"],
                "unique_palette_indices": stats.get("unique_palette_indices"),
            },
            "files": {
                "manifest": manifest_name,
                "png": png_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    @staticmethod
    def blit_rgba(
        target: list[int],
        target_width: int,
        dst_x: int,
        dst_y: int,
        source: list[int],
        source_width: int,
        source_height: int,
    ) -> None:
        for y in range(source_height):
            target_start = ((dst_y + y) * target_width + dst_x) * 4
            source_start = y * source_width * 4
            target[target_start : target_start + source_width * 4] = source[
                source_start : source_start + source_width * 4
            ]

    def export_bkg_grid_composition(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        payload, resource = read_hqr_payload(self.asset_root, asset["source"])
        composition = decode_bkg_grid_columns(payload, include_cells=True)
        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}"
        composition_name = f"{base_name}_composition.json"
        preview_name = f"{base_name}_preview.png"
        manifest_name = "manifest.json"
        preview = self.render_bkg_grid_preview(asset)
        composition_payload = {
            "schema_version": "bkg_grid_composition.v0",
            "catalog_asset_id": asset["id"],
            "catalog_label": asset.get("label"),
            "archive": asset["source"].get("hqr"),
            "entry_index": asset["source"].get("entry_index"),
            "cube_dimensions": composition["cube_dimensions"],
            "cell_order": composition["cell_order"],
            "flat_block_refs": composition["flat_block_refs"],
            "flat_cell_slots_or_codes": composition["flat_cell_slots_or_codes"],
            "occupied_block_cells": composition["nonzero_cells"],
            "transparent_code_cells": composition["transparent_code_cells"],
            "unique_block_refs": composition["unique_block_refs"],
            "source_provenance": composition["source_provenance"],
        }
        (output_dir / composition_name).write_text(
            json.dumps(composition_payload, indent=2) + "\n", encoding="utf-8"
        )
        write_rgba_png(
            output_dir / preview_name,
            int(preview["width"]),
            int(preview["height"]),
            preview["rgba"],
        )
        manifest = {
            "schema_version": "bkg_grid_composition_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
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
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "decoded background grid composition plus render-only preview; not live scene behavior proof",
            ),
            "options": {
                "format": "bkg_grid_column_composition",
                "cell_order": composition["cell_order"],
            },
            "stats": {
                "cell_count": len(composition["flat_block_refs"]),
                "occupied_block_cells": composition["nonzero_cells"],
                "transparent_code_cells": composition["transparent_code_cells"],
                "active_columns": composition["active_columns"],
                "unique_block_refs": len(composition["unique_block_refs"]),
                "preview_drawn_cells": preview["drawn_cells"],
                "preview_drawn_pixels": preview["drawn_pixels"],
                "preview_unique_bricks_loaded": preview["unique_bricks_loaded"],
                "preview_missing_bricks": preview["missing_bricks"],
                "preview_skipped_forbidden": preview["skipped_forbidden"],
            },
            "files": {
                "manifest": manifest_name,
                "composition_json": composition_name,
                "preview_png": preview_name,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def export_scene_background_composition(
        self, asset: dict[str, Any], output_dir: Path
    ) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        reconnaissance = stats.get("reconnaissance") or {}
        background = reconnaissance.get("background") or {}
        gri_entry = background.get("resolved_gri_entry")
        bll_entry = background.get("resolved_bll_entry")
        if not isinstance(gri_entry, int) or not isinstance(bll_entry, int):
            raise Lm2Error("scene is missing resolved background GRI/BLL links")

        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        base_composition, variant_compositions = self.scene_background_variant_compositions(asset)

        base_name = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}_background"
        manifest_name = "manifest.json"
        variants: list[dict[str, Any]] = []

        def composition_payload(
            variant: str,
            block_refs: list[int],
            slots: list[int],
            *,
            source_provenance: str,
            grm_link: dict[str, Any] | None = None,
            applied: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            unique_blocks = sorted({int(ref) for ref in block_refs if int(ref)})
            transparent_codes = sum(
                1
                for ref, slot in zip(block_refs, slots)
                if not int(ref) and int(slot)
            )
            return {
                "schema_version": "scene_background_composition.v0",
                "variant": variant,
                "catalog_asset_id": asset["id"],
                "catalog_label": asset.get("label"),
                "scene_entry_index": asset["source"].get("entry_index"),
                "scene_index": int(asset["source"].get("entry_index", 0)) - 1,
                "runtime_cube": background.get("runtime_cube"),
                "resolved_gri_entry": gri_entry,
                "resolved_bll_entry": bll_entry,
                "resolved_grm_entry": background.get("resolved_grm_entry"),
                "cube_dimensions": base_composition["cube_dimensions"],
                "cell_order": base_composition["cell_order"],
                "flat_block_refs": block_refs,
                "flat_cell_slots_or_codes": slots,
                "occupied_block_cells": sum(1 for ref in block_refs if int(ref)),
                "transparent_code_cells": transparent_codes,
                "unique_block_refs": unique_blocks,
                "grm_link": grm_link,
                "applied_grm_stats": applied,
                "source_provenance": source_provenance,
            }

        def write_variant(
            variant: str,
            block_refs: list[int],
            slots: list[int],
            *,
            source_provenance: str,
            grm_link: dict[str, Any] | None = None,
            applied: dict[str, Any] | None = None,
        ) -> None:
            json_name = f"{base_name}_{variant}_composition.json"
            preview_name = f"{base_name}_{variant}_preview.png"
            payload = composition_payload(
                variant,
                block_refs,
                slots,
                source_provenance=source_provenance,
                grm_link=grm_link,
                applied=applied,
            )
            (output_dir / json_name).write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            preview = self.render_bkg_composition_preview(
                bll_entry,
                block_refs,
                slots,
                render_source=source_provenance,
            )
            write_rgba_png(
                output_dir / preview_name,
                int(preview["width"]),
                int(preview["height"]),
                preview["rgba"],
            )
            variants.append(
                {
                    "variant": variant,
                    "composition_json": json_name,
                    "preview_png": preview_name,
                    "occupied_block_cells": payload["occupied_block_cells"],
                    "transparent_code_cells": payload["transparent_code_cells"],
                    "unique_block_refs": len(payload["unique_block_refs"]),
                    "preview_drawn_cells": preview["drawn_cells"],
                    "preview_drawn_pixels": preview["drawn_pixels"],
                    "preview_missing_bricks": preview["missing_bricks"],
                    "preview_skipped_forbidden": preview["skipped_forbidden"],
                    **(
                        {
                            "zone_index": grm_link.get("zone_index"),
                            "zone_value": grm_link.get("zone_value"),
                            "resolved_grm_entry": grm_link.get("resolved_grm_entry"),
                            "changed_cells": (applied or {}).get("changed_cells"),
                            "column_y_overflow_cells": grm_link.get("column_y_overflow_cells"),
                        }
                        if grm_link
                        else {}
                    ),
                }
            )

        for variant_data in variant_compositions:
            write_variant(
                str(variant_data["variant"]),
                variant_data["block_refs"],
                variant_data["slots"],
                source_provenance=str(variant_data["source_provenance"]),
                grm_link=variant_data.get("grm_link"),
                applied=variant_data.get("applied_grm_stats"),
            )

        manifest = {
            "schema_version": "scene_background_composition_manifest.v0",
            "source": {
                "asset_root": str(self.asset_root),
                "catalog_asset_id": asset["id"],
                "catalog_label": asset.get("label"),
                "archive": asset["source"].get("hqr"),
                "entry_index": asset["source"].get("entry_index"),
                "classic_index": asset["source"].get("classic_index"),
                "archive_offset": asset["source"].get("offset"),
                "archive_raw_bytes": asset["source"].get("raw_bytes"),
                "archive_raw_sha256": asset["source"].get("raw_sha256"),
                "decoded_bytes": asset.get("decoded_bytes"),
                "decoded_sha256": asset.get("decoded_sha256"),
                "source_mode": self.catalog.get("source_mode") if self.catalog else None,
            },
            "evidence": self.export_evidence_context(
                asset,
                "decoded scene background composition variants with render-only previews; no live script state guessed",
            ),
            "background": {
                "runtime_cube": background.get("runtime_cube"),
                "resolved_gri_entry": gri_entry,
                "resolved_bll_entry": bll_entry,
                "resolved_grm_entry": background.get("resolved_grm_entry"),
                "palette": background.get("palette"),
            },
            "options": {
                "format": "scene_background_composition",
                "variant_policy": "base plus each resolved GRM zone forced ON; no live script state guessed",
                "cell_order": base_composition["cell_order"],
            },
            "stats": {
                "variant_count": len(variants),
                "grm_zone_count": len(reconnaissance.get("grm_fragment_links") or []),
                "exported_grm_on_variants": max(0, len(variants) - 1),
            },
            "files": {
                "manifest": manifest_name,
                "variants": variants,
            },
        }
        (output_dir / manifest_name).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return {"output_dir": str(output_dir), "manifest": manifest}

    def scene_background_variant_compositions(
        self, asset: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        reconnaissance = stats.get("reconnaissance") or {}
        background = reconnaissance.get("background") or {}
        gri_entry = background.get("resolved_gri_entry")
        bll_entry = background.get("resolved_bll_entry")
        if not isinstance(gri_entry, int) or not isinstance(bll_entry, int):
            raise Lm2Error("scene is missing resolved background GRI/BLL links")

        read_bkg_entry = self.lba_bkg_entry_reader()
        grid_payload = read_bkg_entry(gri_entry)
        base_composition = decode_bkg_grid_columns(grid_payload, include_cells=True)
        variants: list[dict[str, Any]] = [
            {
                "variant": "base",
                "label": "Base",
                "block_refs": list(base_composition["flat_block_refs"]),
                "slots": list(base_composition["flat_cell_slots_or_codes"]),
                "source_provenance": (
                    "Base scene background from TabAllCube-selected GRI columns. "
                    "No GRM state is assumed; GRM-on variants are listed separately."
                ),
            }
        ]
        for link in reconnaissance.get("grm_fragment_links") or []:
            if not link.get("asset_available") or not isinstance(link.get("resolved_grm_entry"), int):
                continue
            fragment_payload = read_bkg_entry(int(link["resolved_grm_entry"]))
            fragment = decode_bkg_grm_fragment(fragment_payload, include_cells=True)
            start = link.get("target_cell_start") or {}
            applied = apply_bkg_grm_fragment_to_composition(
                base_composition["flat_block_refs"],
                base_composition["flat_cell_slots_or_codes"],
                {
                    "start": {
                        "x": int(start.get("x", 0)) * BKG_WORLD_CELL_SIZE_XZ,
                        "y": int(start.get("y", 0)) * BKG_WORLD_CELL_SIZE_Y,
                        "z": int(start.get("z", 0)) * BKG_WORLD_CELL_SIZE_XZ,
                    },
                    "end": {},
                },
                fragment,
            )
            zone_index = int(link.get("zone_index", 0))
            variants.append(
                {
                    "variant": f"grm_zone_{zone_index:03d}_on",
                    "label": f"GRM zone {zone_index} ON",
                    "block_refs": applied["flat_block_refs"],
                    "slots": applied["flat_cell_slots_or_codes"],
                    "grm_link": link,
                    "applied_grm_stats": {
                        key: value for key, value in applied.items() if not key.startswith("flat_")
                    },
                    "source_provenance": (
                        "Explicit GRM ON variant using GRILLE.CPP IncrustGrm semantics. "
                        "This is not a guessed live runtime state."
                    ),
                }
            )
        return base_composition, variants

    def render_scene_background_preview_frames(self, asset: dict[str, Any]) -> list[dict[str, Any]]:
        stats = asset.get("stats") or {}
        reconnaissance = stats.get("reconnaissance") or {}
        background = reconnaissance.get("background") or {}
        bll_entry = background.get("resolved_bll_entry")
        if not isinstance(bll_entry, int):
            raise Lm2Error("scene is missing resolved background BLL link")
        _base_composition, variants = self.scene_background_variant_compositions(asset)
        frames: list[dict[str, Any]] = []
        for index, variant in enumerate(variants):
            preview = self.render_bkg_composition_preview(
                bll_entry,
                variant["block_refs"],
                variant["slots"],
                render_source=variant["source_provenance"],
            )
            link = variant.get("grm_link") or {}
            applied = variant.get("applied_grm_stats") or {}
            preview.update(
                {
                    "variant": variant["variant"],
                    "variant_label": variant["label"],
                    "variant_index": index,
                    "variant_count": len(variants),
                    "variant_policy": "base plus each resolved GRM zone forced ON; no live script state guessed",
                    "scene_background": {
                        "runtime_cube": background.get("runtime_cube"),
                        "resolved_gri_entry": background.get("resolved_gri_entry"),
                        "resolved_bll_entry": background.get("resolved_bll_entry"),
                        "resolved_grm_entry": background.get("resolved_grm_entry"),
                    },
                    "grm_zone_index": link.get("zone_index"),
                    "grm_zone_value": link.get("zone_value"),
                    "resolved_grm_entry": link.get("resolved_grm_entry"),
                    "changed_cells": applied.get("changed_cells"),
                    "column_y_overflow_cells": link.get("column_y_overflow_cells"),
                }
            )
            frames.append(preview)
        return frames

    def bkg_header_fields(self) -> dict[str, Any]:
        if self.catalog is None:
            raise Lm2Error("no catalog loaded")
        for asset in self.catalog.get("assets", []):
            stats = asset.get("stats") or {}
            if stats.get("semantic_layout") == "bkg_header":
                return stats.get("fields") or {}
        raise Lm2Error("LBA_BKG header is not available in the catalog")

    def lba_bkg_entry_reader(self):
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        bkg_path = (self.asset_root / LBA_BKG_ARCHIVE_NAME).resolve()
        bkg_data = bkg_path.read_bytes()
        bkg_entries = {
            entry.index: entry for entry in lba_hqr.parse_classic_table(bkg_data)
        }

        def read_bkg_entry(entry_index: int) -> bytes:
            entry = bkg_entries.get(entry_index)
            if entry is None or entry.byte_length == 0:
                raise Lm2Error(f"{LBA_BKG_ARCHIVE_NAME} entry is missing: {entry_index}")
            raw = lba_hqr.read_entry(bkg_data, entry)
            try:
                payload, _ = lba_hqr.decode_resource_entry(raw)
            except lba_hqr.HqrError as exc:
                raise Lm2Error(f"failed to decode {LBA_BKG_ARCHIVE_NAME}:{entry_index}: {exc}") from exc
            return payload

        return read_bkg_entry

    def render_bkg_composition_preview(
        self,
        bll_entry: int,
        block_refs: list[int],
        slots: list[int],
        *,
        render_source: str,
    ) -> dict[str, Any]:
        header = self.bkg_header_fields()
        read_bkg_entry = self.lba_bkg_entry_reader()
        bll_payload = read_bkg_entry(bll_entry)
        _, blocks, _ = parse_bkg_block_table(bll_payload, header, include_cells=True)

        width = 640
        height = 480
        rgba = [0] * (width * height * 4)
        palette = self.palette
        brk_start = int(header["brk_start"])
        forbidden_brick = int(header["forbiden_brick"])
        brick_cache: dict[int, dict[str, Any] | None] = {}
        drawn_cells = 0
        drawn_pixels = 0
        skipped_forbidden = 0
        missing_bricks = 0

        def load_brick(brick_ref: int) -> dict[str, Any] | None:
            if brick_ref in brick_cache:
                return brick_cache[brick_ref]
            try:
                payload = read_bkg_entry(brk_start + brick_ref - 1)
                brick = parse_bkg_brick_graphic(payload)
            except Lm2Error:
                brick = None
            brick_cache[brick_ref] = brick
            return brick

        for z in range(64):
            for x in range(64):
                column_base = ((z * 64) + x) * 25
                for y in range(25):
                    cell_index = column_base + y
                    block_ref = block_refs[cell_index]
                    if not block_ref:
                        continue
                    block_index = block_ref - 1
                    if block_index < 0 or block_index >= len(blocks):
                        continue
                    cells = blocks[block_index].get("cells") or []
                    slot = slots[cell_index]
                    if slot < 0 or slot >= len(cells):
                        continue
                    brick_ref = int(cells[slot].get("brick_ref") or 0)
                    if not brick_ref:
                        continue
                    if brick_ref - 1 == forbidden_brick:
                        skipped_forbidden += 1
                        continue
                    brick = load_brick(brick_ref)
                    if brick is None:
                        missing_bricks += 1
                        continue
                    screen_x = (x - z) * 24 + 288 + int(brick["offset_x"])
                    screen_y = (x + z) * 12 - y * 15 + 226 + int(brick["offset_y"])
                    brick_pixels = brick["pixels"]
                    mask = brick["opaque_mask"]
                    for py in range(int(brick["height"])):
                        dy = screen_y + py
                        if dy < 0 or dy >= height:
                            continue
                        for px in range(int(brick["width"])):
                            sx = screen_x + px
                            if sx < 0 or sx >= width:
                                continue
                            source_index = py * int(brick["width"]) + px
                            if not mask[source_index]:
                                continue
                            palette_index = int(brick_pixels[source_index])
                            target_index = dy * width + sx
                            color = palette[palette_index] if palette and 0 <= palette_index < len(palette) else palette_index
                            rgba_index = target_index * 4
                            rgba[rgba_index] = (color >> 16) & 0xFF
                            rgba[rgba_index + 1] = (color >> 8) & 0xFF
                            rgba[rgba_index + 2] = color & 0xFF
                            rgba[rgba_index + 3] = 255
                            drawn_pixels += 1
                    drawn_cells += 1

        return {
            "format": "bkg_grid_preview",
            "width": width,
            "height": height,
            "offset_x": 0,
            "offset_y": 0,
            "pixels": [],
            "rgba": rgba,
            "palette_available": palette is not None,
            "palette_source": "RESS.HQR:0 normal palette evidence preview; gameplay colors use the active scene PtrPal/XPL palette.",
            "render_source": render_source,
            "drawn_cells": drawn_cells,
            "drawn_pixels": drawn_pixels,
            "unique_bricks_loaded": len([brick for brick in brick_cache.values() if brick is not None]),
            "missing_bricks": missing_bricks,
            "skipped_forbidden": skipped_forbidden,
        }

    def render_bkg_grid_preview(self, asset: dict[str, Any]) -> dict[str, Any]:
        if self.asset_root is None:
            raise Lm2Error("no asset root loaded")
        stats = asset.get("stats") or {}
        fields = stats.get("fields") or {}
        bll_entry = fields.get("resolved_bll_entry")
        if not isinstance(bll_entry, int):
            raise Lm2Error("BKG grid asset is missing resolved BLL entry")

        grid_payload, _ = read_hqr_payload(self.asset_root, asset["source"])
        composition = decode_bkg_grid_columns(grid_payload, include_cells=True)
        return self.render_bkg_composition_preview(
            bll_entry,
            composition["flat_block_refs"],
            composition["flat_cell_slots_or_codes"],
            render_source=(
                "Evidence render from GRILLE.CPP AffGrille/AffBrickBlock and GRILLE_A.ASM "
                "Map2Screen; does not include object/decor overdraw or z-buffer mask passes."
            ),
        )

    def pose_catalog_animation(
        self,
        body_id: str,
        animation_id: str,
        sample_frame: int,
        elapsed_ms: int,
        previous_frame: int | None = None,
    ) -> dict[str, Any]:
        with self.operation_lock:
            if self.asset_root is None:
                raise Lm2Error("no asset root loaded")
            body_asset = self.find_catalog_asset(body_id)
            if body_asset.get("kind") != "model":
                raise Lm2Error(f"catalog asset is not a model: {body_id}")
            animation_asset = self.find_catalog_asset(animation_id)
            if (
                animation_asset.get("kind") != "animation"
                or animation_asset.get("entry_type") != "animation"
            ):
                raise Lm2Error(f"catalog asset is not a decoded animation: {animation_id}")
            self.ensure_animation_operation_compatible(body_asset, animation_asset)

            body_payload, _ = read_hqr_payload(self.asset_root, body_asset["source"])
            animation_payload, _ = read_hqr_payload(
                self.asset_root, animation_asset["source"]
            )
            model = load_lm2_bytes(body_payload, str(body_asset["relative_path"]))
            animation = parse_lba2_animation_records(animation_payload)
            posed_model, pose = pose_lm2_model(
                model,
                animation,
                sample_frame=sample_frame,
                previous_frame=previous_frame,
                elapsed_ms=elapsed_ms,
            )
            pose["body_asset_id"] = body_asset["id"]
            pose["animation_asset_id"] = animation_asset["id"]
            response = self.model_json(posed_model, body_asset["label"], pose=pose)
            response["catalog_asset"] = body_asset
            self.last_model = response
            return response

    def pose_catalog_animation_sequence(
        self,
        body_id: str,
        animation_id: str,
        step_ms: int,
    ) -> dict[str, Any]:
        if step_ms <= 0:
            raise Lm2Error("animation sequence step_ms must be positive")
        with self.operation_lock:
            if self.asset_root is None:
                raise Lm2Error("no asset root loaded")
            body_asset = self.find_catalog_asset(body_id)
            if body_asset.get("kind") != "model":
                raise Lm2Error(f"catalog asset is not a model: {body_id}")
            animation_asset = self.find_catalog_asset(animation_id)
            if (
                animation_asset.get("kind") != "animation"
                or animation_asset.get("entry_type") != "animation"
            ):
                raise Lm2Error(f"catalog asset is not a decoded animation: {animation_id}")
            self.ensure_animation_operation_compatible(body_asset, animation_asset)

            body_payload, _ = read_hqr_payload(self.asset_root, body_asset["source"])
            animation_payload, _ = read_hqr_payload(
                self.asset_root, animation_asset["source"]
            )
            model = load_lm2_bytes(body_payload, str(body_asset["relative_path"]))
            animation = parse_lba2_animation_records(animation_payload)
            frames: list[dict[str, Any]] = []
            cumulative_root = [0, 0, 0]
            frame_pairs, loop_pair_index = playback_frame_indices(animation)
            loop_index = 0
            timeline_ms = 0
            loop_root_baseline = [0, 0, 0]
            has_loop_segment = animation.keyframe_count > 1
            for pair_index, (frame_index, previous_frame) in enumerate(frame_pairs):
                if pair_index == loop_pair_index:
                    loop_index = len(frames)
                    loop_root_baseline = cumulative_root.copy()
                keyframe = animation.keyframes[frame_index]
                previous_sample_root = [0, 0, 0]
                elapsed_values = list(range(0, max(1, keyframe.duration), step_ms))
                if not elapsed_values:
                    elapsed_values = [0]
                for elapsed_ms in elapsed_values:
                    posed_model, pose = pose_lm2_model(
                        model,
                        animation,
                        sample_frame=frame_index,
                        previous_frame=previous_frame,
                        elapsed_ms=elapsed_ms,
                    )
                    pose["body_asset_id"] = body_asset["id"]
                    pose["animation_asset_id"] = animation_asset["id"]
                    sample = pose["sample"]
                    sample_root = list(sample.get("root_delta") or [0, 0, 0])
                    cumulative_root = [
                        cumulative_root[index] + sample_root[index] - previous_sample_root[index]
                        for index in range(3)
                    ]
                    previous_sample_root = sample_root
                    frames.append(
                        {
                            "sequence_index": len(frames),
                            "segment": "loop"
                            if has_loop_segment and pair_index >= loop_pair_index
                            else "intro",
                            "frame": frame_index,
                            "previous_frame": previous_frame,
                            "next_frame": sample["next_frame_index"],
                            "elapsed_ms": elapsed_ms,
                            "timeline_ms": timeline_ms,
                            "duration_ms": sample["duration_ms"],
                            "root_motion": cumulative_root.copy(),
                            "vertices": [
                                [vertex.x, vertex.y, vertex.z, vertex.bone]
                                for vertex in posed_model.vertices
                            ],
                            "pose": pose,
                        }
                    )
                    timeline_ms += step_ms
            loop_cycle_root_delta = [
                cumulative_root[index] - loop_root_baseline[index] for index in range(3)
            ]
            return {
                "body_asset_id": body_asset["id"],
                "animation_asset_id": animation_asset["id"],
                "step_ms": step_ms,
                "keyframes": animation.keyframe_count,
                "loop_frame": animation.loop_start_keyframe,
                "loop_index": loop_index,
                "playback_end_index": loop_index if has_loop_segment else len(frames),
                "loop_cycle_root_delta": loop_cycle_root_delta,
                "frames": frames,
            }

    def handler_class(self) -> type[BaseHTTPRequestHandler]:
        server_state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                print("[lm2-viewer] " + fmt % args, file=sys.stderr)

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/model.json":
                    payload = server_state.last_model or {
                        "error": "No model loaded yet."
                    }
                    self.send_json(payload)
                elif parsed.path == "/catalog.json":
                    payload = server_state.catalog or {
                        "error": "No catalog loaded yet."
                    }
                    self.send_json(payload)
                elif parsed.path == "/api/decode/progress":
                    self.send_json(server_state.decode_progress.snapshot())
                elif parsed.path == "/api/catalog/audio":
                    self.handle_catalog_audio(parsed)
                elif parsed.path.startswith("/api/"):
                    self.send_error(404)
                else:
                    self.send_static(parsed.path)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                routes = {
                    "/api/upload": self.handle_upload,
                    "/api/path": self.handle_path,
                    "/api/catalog/build": self.handle_catalog_build,
                    "/api/catalog/pick": self.handle_catalog_pick,
                    "/api/catalog/pick-files": self.handle_catalog_pick_files,
                    "/api/catalog/load": self.handle_catalog_load,
                    "/api/catalog/export": self.handle_catalog_export,
                    "/api/catalog-graph/compatible": self.handle_catalog_graph_compatible,
                    "/api/animation/pose": self.handle_animation_pose,
                    "/api/animation/sequence": self.handle_animation_sequence,
                    "/api/runtime/sprite-resolve": self.handle_runtime_sprite_resolve,
                    "/api/entity/asset": self.handle_entity_asset,
                    "/api/entity/scene-object": self.handle_entity_scene_object,
                    "/api/entity/runtime-sprite": self.handle_entity_runtime_sprite,
                    "/api/port/promotion-packets": self.handle_port_promotion_packets,
                }
                handler = routes.get(parsed.path)
                if handler is None:
                    self.send_error(404)
                    return
                try:
                    self.send_json(handler())
                except Exception as exc:
                    self.send_json({"error": str(exc)}, status=400)

            def read_json_body(self) -> dict[str, Any]:
                length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(length)
                return json.loads(body.decode("utf-8"))

            def read_upload(self) -> dict[str, Any]:
                content_type = self.headers.get("content-type", "")
                length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(length)
                return parse_multipart_upload(content_type, body)

            def handle_upload(self) -> dict[str, Any]:
                payload = self.read_upload()
                with server_state.operation_lock:
                    model = server_state.model_json(
                        load_lm2_bytes(payload["data"], payload["filename"]),
                        payload["filename"],
                    )
                    server_state.last_model = model
                    return model

            def handle_path(self) -> dict[str, Any]:
                request = self.read_json_body()
                path = Path(request["path"]).expanduser()
                with server_state.operation_lock:
                    model = server_state.model_json(load_lm2_path(path), str(path))
                    server_state.last_model = model
                    return model

            def handle_catalog_build(self) -> dict[str, Any]:
                request = self.read_json_body()
                return server_state.set_asset_root(Path(request["asset_root"]).expanduser())

            def handle_catalog_pick(self) -> dict[str, Any]:
                with server_state.operation_lock:
                    server_state.decode_progress.begin(
                        "Waiting for folder selection", phase="waiting"
                    )
                    try:
                        selected = pick_directory_dialog()
                    except Exception as exc:
                        server_state.decode_progress.fail(str(exc))
                        raise
                    return server_state.set_asset_root(selected)

            def handle_catalog_pick_files(self) -> dict[str, Any]:
                with server_state.operation_lock:
                    server_state.decode_progress.begin(
                        "Waiting for file selection", phase="waiting"
                    )
                    try:
                        selected = pick_hqr_files_dialog()
                    except Exception as exc:
                        server_state.decode_progress.fail(str(exc))
                        raise
                    return server_state.set_asset_files(selected)

            def handle_catalog_load(self) -> dict[str, Any]:
                request = self.read_json_body()
                with server_state.operation_lock:
                    asset = server_state.find_catalog_asset(str(request["id"]))
                    if asset.get("kind") == "model":
                        return self.load_model_asset(asset)
                    if asset.get("kind") == "animation":
                        return {"animation": asset}
                    if asset.get("kind") == "sprite":
                        return self.load_sprite_asset(asset)
                    if asset.get("kind") == "scene":
                        return self.load_scene_asset(asset)
                    if asset.get("kind") == "resource":
                        return self.load_resource_asset(asset)
                    raise Lm2Error(f"unsupported catalog asset kind: {asset.get('kind')}")

            def load_model_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
                if server_state.asset_root is None:
                    raise Lm2Error("no asset root loaded")
                payload, _ = read_hqr_payload(server_state.asset_root, asset["source"])
                model = server_state.model_json(
                    load_lm2_bytes(payload, str(asset["relative_path"])),
                    asset["label"],
                )
                model["catalog_asset"] = asset
                server_state.last_model = model
                return model

            def load_sprite_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
                if server_state.asset_root is None:
                    raise Lm2Error("no asset root loaded")
                stats = asset.get("stats") or {}
                if stats.get("semantic_layout") not in ("lsp_sprite_frame", "raw_sprite_frame"):
                    return {"sprite": asset}
                payload, _ = read_hqr_payload(server_state.asset_root, asset["source"])
                sprite = (
                    parse_raw_sprite_frame(payload)
                    if stats.get("semantic_layout") == "raw_sprite_frame"
                    else parse_lsp_sprite_frame(payload)
                )
                palette = server_state.palette
                rgba = indexed_frame_rgba(sprite["pixels"], palette)
                return {
                    "sprite": asset,
                    "frame": {
                        "format": sprite["format"],
                        "width": sprite["width"],
                        "height": sprite["height"],
                        "offset_x": sprite["offset_x"],
                        "offset_y": sprite["offset_y"],
                        "pixels": sprite["pixels"],
                        "rgba": rgba,
                        "palette_available": palette is not None,
                        "palette_source": "RESS.HQR:0 normal palette",
                    },
                }

            def load_scene_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
                stats = asset.get("stats") or {}
                reconnaissance = stats.get("reconnaissance") or {}
                background = reconnaissance.get("background") or {}
                if not isinstance(background.get("resolved_gri_entry"), int):
                    return {"scene": asset}
                frames = server_state.render_scene_background_preview_frames(asset)
                enriched_asset = {
                    **asset,
                    "stats": {
                        **stats,
                        "background_preview": {
                            "format": "scene_background_preview_variants",
                            "variant_count": len(frames),
                            "variant_policy": "base plus each resolved GRM zone forced ON; no live script state guessed",
                            "source_provenance": "Scene background preview uses TabAllCube-selected GRI plus explicit GRILLE.CPP IncrustGrm variants.",
                        },
                    },
                }
                return {
                    "sprite": enriched_asset,
                    "frame": frames[0] if frames else None,
                    "frames": frames,
                }

            def load_resource_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
                if server_state.asset_root is None:
                    raise Lm2Error("no asset root loaded")
                stats = asset.get("stats") or {}
                if stats.get("semantic_layout") == "bkg_grid_map":
                    payload, _ = read_hqr_payload(server_state.asset_root, asset["source"])
                    composition = decode_bkg_grid_columns(payload, include_cells=True)
                    preview = server_state.render_bkg_grid_preview(asset)
                    enriched_asset = {
                        **asset,
                        "stats": {
                            **stats,
                            "composition_payload": {
                                "format": "bkg_grid_column_composition",
                                "cube_dimensions": composition["cube_dimensions"],
                                "cell_order": composition["cell_order"],
                                "cell_count": len(composition["flat_block_refs"]),
                                "flat_block_refs": composition["flat_block_refs"],
                                "flat_cell_slots_or_codes": composition["flat_cell_slots_or_codes"],
                                "occupied_block_cells": composition["nonzero_cells"],
                                "transparent_code_cells": composition["transparent_code_cells"],
                                "unique_block_refs": composition["unique_block_refs"],
                                "source_provenance": composition["source_provenance"],
                            },
                            "preview": {
                                "format": preview["format"],
                                "width": preview["width"],
                                "height": preview["height"],
                                "drawn_cells": preview["drawn_cells"],
                                "drawn_pixels": preview["drawn_pixels"],
                                "unique_bricks_loaded": preview["unique_bricks_loaded"],
                                "missing_bricks": preview["missing_bricks"],
                                "skipped_forbidden": preview["skipped_forbidden"],
                                "source_provenance": preview["render_source"],
                                "palette_source": preview["palette_source"],
                            },
                        },
                    }
                    return {
                        "sprite": enriched_asset,
                        "frame": preview,
                    }
                if stats.get("semantic_layout") == "screen_indexed_image_640x480":
                    preview = server_state.screen_indexed_image_frame(asset)
                    enriched_asset = {
                        **asset,
                        "stats": {
                            **stats,
                            "preview": {
                                "format": preview["format"],
                                "width": preview["width"],
                                "height": preview["height"],
                                "palette_source": preview["palette_source"],
                            },
                        },
                    }
                    return {
                        "sprite": enriched_asset,
                        "frame": preview,
                    }
                if stats.get("semantic_layout") in ("lba2_indexed_image_256", "lba2_texture_atlas_indexed"):
                    preview = server_state.ress_indexed_image_frame(asset)
                    enriched_asset = {
                        **asset,
                        "stats": {
                            **stats,
                            "preview": {
                                "format": preview["format"],
                                "width": preview["width"],
                                "height": preview["height"],
                                "palette_source": preview["palette_source"],
                            },
                        },
                    }
                    return {
                        "sprite": enriched_asset,
                        "frame": preview,
                    }
                if stats.get("semantic_layout") == "holomap_plan_image_640x480":
                    preview = server_state.holomap_plan_image_frame(asset)
                    enriched_asset = {
                        **asset,
                        "stats": {
                            **stats,
                            "preview": {
                                "format": preview["format"],
                                "width": preview["width"],
                                "height": preview["height"],
                                "palette_source": preview["palette_source"],
                            },
                        },
                    }
                    return {
                        "sprite": enriched_asset,
                        "frame": preview,
                    }
                if stats.get("semantic_layout") != "bkg_brick_graphic":
                    return {"resource": asset}
                payload, _ = read_hqr_payload(server_state.asset_root, asset["source"])
                brick = parse_bkg_brick_graphic(payload)
                palette = server_state.palette
                return {
                    "sprite": asset,
                    "frame": {
                        "format": brick["format"],
                        "width": brick["width"],
                        "height": brick["height"],
                        "offset_x": brick["offset_x"],
                        "offset_y": brick["offset_y"],
                        "pixels": brick["pixels"],
                        "rgba": indexed_frame_rgba(
                            brick["pixels"], palette, brick["opaque_mask"]
                        ),
                        "palette_available": palette is not None,
                        "palette_source": "RESS.HQR:0 normal palette preview; gameplay BRK colors use the active PtrPal selected by ChoicePalette from XPL palettes.",
                    },
                }

            def handle_catalog_export(self) -> dict[str, Any]:
                request = self.read_json_body()
                output_dir_value = request.get("output_dir")
                output_dir = (
                    Path(output_dir_value).expanduser()
                    if isinstance(output_dir_value, str) and output_dir_value
                    else default_browser_export_directory(str(request["id"]))
                )
                return server_state.export_catalog_asset(
                    str(request["id"]),
                    output_dir,
                    str(request.get("polygon_mode") or "original"),
                )

            def handle_catalog_graph_compatible(self) -> dict[str, Any]:
                request = self.read_json_body()
                return server_state.catalog_graph_compatible(str(request["model_id"]))

            def handle_animation_pose(self) -> dict[str, Any]:
                request = self.read_json_body()
                previous_frame_value = request.get("previous_frame")
                previous_frame = (
                    int(previous_frame_value)
                    if previous_frame_value is not None
                    else None
                )
                return server_state.pose_catalog_animation(
                    str(request["body_id"]),
                    str(request["animation_id"]),
                    int(request.get("sample_frame") or 0),
                    int(request.get("elapsed_ms") or 0),
                    previous_frame,
                )

            def handle_animation_sequence(self) -> dict[str, Any]:
                request = self.read_json_body()
                return server_state.pose_catalog_animation_sequence(
                    str(request["body_id"]),
                    str(request["animation_id"]),
                    int(request.get("step_ms") or 40),
                )

            def handle_runtime_sprite_resolve(self) -> dict[str, Any]:
                return server_state.resolve_runtime_sprite_object(self.read_json_body())

            def handle_entity_asset(self) -> dict[str, Any]:
                request = self.read_json_body()
                return server_state.asset_entity_workflow(str(request["id"]))

            def handle_entity_scene_object(self) -> dict[str, Any]:
                request = self.read_json_body()
                return server_state.scene_object_entity_workflow(
                    str(request["scene_asset_id"]),
                    int(request["object_index"]),
                )

            def handle_entity_runtime_sprite(self) -> dict[str, Any]:
                return server_state.runtime_sprite_entity_workflow(self.read_json_body())

            def handle_port_promotion_packets(self) -> dict[str, Any]:
                return read_port_promotion_packets()

            def handle_catalog_audio(self, parsed: urllib.parse.ParseResult) -> None:
                try:
                    query = urllib.parse.parse_qs(parsed.query)
                    asset_id = (query.get("id") or [""])[0]
                    payload, asset = server_state.sample_audio_payload(asset_id)
                    filename = f"{asset['source']['hqr'].replace('.', '_')}_{asset['source']['entry_index']}.wav"
                    self.send_response(200)
                    self.send_header("content-type", "audio/wav")
                    self.send_header("content-length", str(len(payload)))
                    self.send_header("cache-control", "no-store, max-age=0")
                    self.send_header("pragma", "no-cache")
                    self.send_header("expires", "0")
                    self.send_header("content-disposition", f'inline; filename="{filename}"')
                    self.end_headers()
                    self.wfile.write(payload)
                except Exception as exc:
                    self.send_json({"error": str(exc)}, status=400)

            def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                self.send_bytes(
                    json.dumps(payload).encode("utf-8"), "application/json", status
                )

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
                content_type = (
                    mimetypes.guess_type(candidate.name)[0]
                    or "application/octet-stream"
                )
                self.send_bytes(candidate.read_bytes(), content_type)

            def send_bytes(
                self, payload: bytes, content_type: str, status: int = 200
            ) -> None:
                self.send_response(status)
                self.send_header("content-type", content_type)
                self.send_header("content-length", str(len(payload)))
                self.send_header("cache-control", "no-store, max-age=0")
                self.send_header("pragma", "no-cache")
                self.send_header("expires", "0")
                self.end_headers()
                self.wfile.write(payload)

        return Handler


def serve(
    initial_path: Path | None,
    host: str,
    port: int,
    open_browser: bool,
    asset_root: Path | None,
) -> None:
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
            f"{summary.get('models', 0)} models, "
            f"{summary.get('decoded_animations', 0)} decoded animations, "
            f"{summary.get('raw_animations', 0)} raw animation entries, "
            f"{summary.get('sprite_assets', 0)} sprite assets"
        )
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LM2 viewer.")


