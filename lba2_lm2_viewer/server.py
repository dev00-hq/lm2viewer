"""HTTP server and mutable viewer session state."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .animation import parse_lba2_animation_records, playback_frame_indices
from .viewer import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    FRONTEND_DIST,
    DecodeProgress,
    Lm2Error,
    Lm2Model,
    build_catalog,
    load_lm2_bytes,
    load_lm2_path,
    load_palette_from_asset_root,
    load_texture_atlas_from_asset_root,
    normalize_hqr_file_paths,
    parse_multipart_upload,
    pick_directory_dialog,
    pick_export_directory_dialog,
    pick_hqr_files_dialog,
    pose_lm2_model,
    read_hqr_payload,
    selected_hqr_root,
)


def animation_compatibility_error(
    body_asset: dict[str, Any], animation_asset: dict[str, Any]
) -> str | None:
    if animation_asset.get("kind") != "animation" or animation_asset.get("entry_type") != "animation":
        return "catalog asset is not a decoded animation"
    animation_stats = animation_asset.get("stats") or {}
    body_stats = body_asset.get("stats") or {}
    if animation_stats.get("boneframes") != body_stats.get("bones"):
        return (
            f"animation bone count {animation_stats.get('boneframes')} does not match "
            f"model bone count {body_stats.get('bones')}"
        )
    metadata = animation_asset.get("animation_metadata") or {}
    compatible_body_ids = metadata.get("compatible_body_ids") or []
    if (
        body_asset.get("source", {}).get("hqr") == "BODY.HQR"
        and compatible_body_ids
        and body_asset.get("source", {}).get("entry_index") not in compatible_body_ids
    ):
        return (
            f"animation {animation_asset.get('id')} is linked to BODY.HQR entries "
            f"{compatible_body_ids}, not {body_asset.get('id')}"
        )
    return None


def ensure_animation_compatible(
    body_asset: dict[str, Any], animation_asset: dict[str, Any]
) -> None:
    error = animation_compatibility_error(body_asset, animation_asset)
    if error is not None:
        raise Lm2Error(error)


class ViewerServer:
    def __init__(self, initial_path: Path | None, asset_root: Path | None) -> None:
        self.initial_path = initial_path
        self.operation_lock = threading.RLock()
        self.last_model: dict[str, Any] | None = None
        self.asset_root: Path | None = None
        self.catalog: dict[str, Any] | None = None
        self.palette: list[int] | None = None
        self.texture_atlas: dict[str, Any] | None = None
        self.decode_progress = DecodeProgress()
        if asset_root is not None:
            self.set_asset_root(asset_root)
        if initial_path is not None:
            self.last_model = self.model_json(
                load_lm2_path(initial_path), str(initial_path)
            )

    def set_asset_root(self, asset_root: Path) -> dict[str, Any]:
        with self.operation_lock:
            resolved = asset_root.expanduser().resolve()
            self.decode_progress.begin(f"Scanning {resolved}", phase="scanning")
            try:
                self.catalog = build_catalog(resolved, self.decode_progress)
                self.decode_progress.update(
                    label="Loading palette and texture atlas", phase="finalizing"
                )
                self.asset_root = resolved
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
            try:
                self.catalog = build_catalog(resolved_root, self.decode_progress, files)
                self.decode_progress.update(
                    label="Loading palette and texture atlas", phase="finalizing"
                )
                self.asset_root = resolved_root
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
            if asset.get("kind") != "model":
                raise Lm2Error(f"catalog asset is not a model: {asset_id}")
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
            ensure_animation_compatible(body_asset, animation_asset)

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
            ensure_animation_compatible(body_asset, animation_asset)

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
                    "/api/animation/pose": self.handle_animation_pose,
                    "/api/animation/sequence": self.handle_animation_sequence,
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

            def handle_catalog_export(self) -> dict[str, Any]:
                request = self.read_json_body()
                output_dir_value = request.get("output_dir")
                output_dir = (
                    Path(output_dir_value).expanduser()
                    if isinstance(output_dir_value, str) and output_dir_value
                    else pick_export_directory_dialog()
                )
                return server_state.export_catalog_asset(
                    str(request["id"]),
                    output_dir,
                    str(request.get("polygon_mode") or "original"),
                )

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
            f"{summary.get('raw_animations', 0)} raw animation entries"
        )
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LM2 viewer.")


