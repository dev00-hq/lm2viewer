#!/usr/bin/env python3
"""Cross-check BODY+ANIM frame stepping against classic LBA2 animation math."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lba2_lm2_viewer import animation, lba_hqr, viewer


DEFAULT_ASSET_ROOT = Path(os.environ.get("LBA2_CLASSIC_RUNTIME_ROOT", "assets"))
DEFAULT_BODY_ASSET = "BODY.HQR:2"
DEFAULT_ANIMATION_ASSET = "ANIM.HQR:49"
DEFAULT_OUTPUT_ROOT = Path("build") / "animation-validation"
REFERENCE_REPOS_ROOT = Path(os.environ.get("LBA2_REFERENCE_REPOS_ROOT", "reference"))
PORT_REPO_ROOT = Path(os.environ.get("LBA2_PORT_REPO_ROOT", "../littlebigreversing"))
REFERENCE_SOURCES = [
    str(REFERENCE_REPOS_ROOT / "lba2-classic-community" / "LIB386" / "ANIM" / "ANIM.CPP"),
    str(REFERENCE_REPOS_ROOT / "lba2-classic-community" / "LIB386" / "ANIM" / "INTERDEP.CPP"),
    str(REFERENCE_REPOS_ROOT / "lba2-classic-community" / "LIB386" / "ANIM" / "INTFRAME.CPP"),
    str(REFERENCE_REPOS_ROOT / "metadata" / "LBA2" / "HQR" / "ANIM.HQR.json"),
    str(PORT_REPO_ROOT / "work" / "idajs_samples_save_map.jsonl"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate an LM2 viewer BODY+ANIM pose path frame by frame against "
            "the classic LBA2 source interpolation formulas."
        )
    )
    parser.add_argument("--asset-root", type=Path, default=DEFAULT_ASSET_ROOT)
    parser.add_argument("--body-asset", default=DEFAULT_BODY_ASSET)
    parser.add_argument("--animation-asset", default=DEFAULT_ANIMATION_ASSET)
    parser.add_argument(
        "--frames",
        default="all",
        help="comma-separated target frame indexes, or 'all'",
    )
    parser.add_argument(
        "--elapsed-fractions",
        default="0,0.25,0.5,0.75,1",
        help="comma-separated fractions inside each target frame duration",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    asset_root = args.asset_root.resolve()
    output_dir = (
        args.out
        if args.out is not None
        else DEFAULT_OUTPUT_ROOT / f"{safe_name(args.body_asset)}__{safe_name(args.animation_asset)}"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    body_payload, body_source = read_asset_payload(asset_root, args.body_asset)
    anim_payload, anim_source = read_asset_payload(asset_root, args.animation_asset)
    model = viewer.parse_lm2(body_payload)
    decoded_animation = animation.parse_lba2_animation_records(anim_payload)
    classic_animation = parse_classic_animation(anim_payload)

    if len(model.bones) != decoded_animation.bone_count:
        raise SystemExit(
            "Body/animation bone-count mismatch: "
            f"{args.body_asset} has {len(model.bones)} bones, "
            f"{args.animation_asset} has {decoded_animation.bone_count} boneframes"
        )
    if (
        classic_animation["keyframe_count"] != decoded_animation.keyframe_count
        or classic_animation["bone_count"] != decoded_animation.bone_count
        or classic_animation["loop_start_keyframe"] != decoded_animation.loop_start_keyframe
    ):
        raise SystemExit("Classic parser header did not match production parser header")

    frame_indexes = select_frames(args.frames, decoded_animation.keyframe_count)
    fractions = [float(item) for item in args.elapsed_fractions.split(",") if item.strip()]
    frame_reports: list[dict[str, Any]] = []

    for frame_index in frame_indexes:
        target = decoded_animation.keyframes[frame_index]
        elapsed_values = {
            max(0, min(target.duration, int(target.duration * fraction)))
            for fraction in fractions
        }
        if target.duration > 0:
            elapsed_values.add(target.duration - 1)
            elapsed_values.add(target.duration)
        for elapsed_ms in sorted(elapsed_values):
            previous_frame = animation.previous_frame_index(decoded_animation, frame_index)
            production_sample = animation.sample_keyframe_transition(
                decoded_animation,
                target_frame_index=frame_index,
                elapsed_ms=elapsed_ms,
                previous_index=previous_frame,
                body_bone_count=len(model.bones),
            )
            classic_sample = classic_sample_keyframe(
                classic_animation,
                target_frame_index=frame_index,
                elapsed_ms=elapsed_ms,
                previous_index=previous_frame,
                bone_limit=len(model.bones),
            )
            compare_samples(production_sample, classic_sample)
            posed_model, pose = viewer.pose_lm2_model(
                model,
                decoded_animation,
                sample_frame=frame_index,
                previous_frame=previous_frame,
                elapsed_ms=elapsed_ms,
            )
            report = {
                "status": "pass",
                "frame": frame_index,
                "previous_frame": previous_frame,
                "next_frame": production_sample["next_frame_index"],
                "elapsed_ms": elapsed_ms,
                "duration_ms": target.duration,
                "classic_interpolator": classic_sample["classic_interpolator"],
                "root_delta": production_sample["root_delta"],
                "vertex_digest": vertex_digest(posed_model),
                "vertex_bounds": vertex_bounds(posed_model),
                "changed_vertices": changed_vertices(model, posed_model),
                "production_sample": production_sample,
                "classic_sample": classic_sample,
                "pose": pose,
            }
            frame_path = frames_dir / f"frame_{frame_index:03d}_elapsed_{elapsed_ms:04d}.json"
            frame_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            frame_reports.append({**report, "artifact": str(frame_path.relative_to(output_dir))})

    manifest = {
        "schema_version": "lm2_animation_validation.v0",
        "validated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "asset_root": str(asset_root),
        "body_asset": args.body_asset,
        "animation_asset": args.animation_asset,
        "body_source": body_source,
        "animation_source": anim_source,
        "animation_summary": decoded_animation.summary().to_json(),
        "reference_sources": REFERENCE_SOURCES,
        "strategy": [
            "Read original BODY.HQR and ANIM.HQR bytes from the asset root.",
            "Parse animation records two ways: production decoder and independent classic-layout reader.",
            "For every selected frame and elapsed point, compute classic rounded 16.16 interpolation.",
            "Compare root deltas and every bone transform against the production sampler.",
            "Pose the BODY with the production transform path and persist per-frame vertex digests.",
        ],
        "checks": {
            "frame_samples": len(frame_reports),
            "bone_count": len(model.bones),
            "classic_source_crosscheck": "pass",
            "posed_vertex_digest": "recorded",
        },
        "frames": [
            {
                "frame": report["frame"],
                "elapsed_ms": report["elapsed_ms"],
                "duration_ms": report["duration_ms"],
                "classic_interpolator": report["classic_interpolator"],
                "root_delta": report["root_delta"],
                "changed_vertices": report["changed_vertices"],
                "vertex_digest": report["vertex_digest"],
                "artifact": report["artifact"],
            }
            for report in frame_reports
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_html_report(output_dir / "index.html", manifest)
    print(json.dumps({"status": "pass", "output_dir": str(output_dir), "frame_samples": len(frame_reports)}, indent=2))
    return 0


def read_asset_payload(asset_root: Path, asset_id: str) -> tuple[bytes, dict[str, Any]]:
    archive_name, entry_index = parse_asset_id(asset_id)
    archive_path = asset_root / archive_name
    if not archive_path.exists():
        raise SystemExit(f"Missing archive for {asset_id}: {archive_path}")
    data = archive_path.read_bytes()
    is_body = archive_name.upper() == "BODY.HQR"
    entries = lba_hqr.parse_classic_table(data) if is_body else lba_hqr.parse_table(data)
    archive_entry_index = entry_index - 1 if is_body else entry_index
    matches = [entry for entry in entries if entry.index == archive_entry_index]
    if not matches or matches[0].byte_length == 0:
        raise SystemExit(f"Missing HQR entry for {asset_id}")
    raw = lba_hqr.read_entry(data, matches[0])
    payload, resource = lba_hqr.decode_resource_entry(raw)
    return payload, {
        "hqr": archive_name,
        "entry_index": entry_index,
        "archive_entry_index": archive_entry_index,
        "offset": matches[0].offset,
        "raw_bytes": matches[0].byte_length,
        "raw_sha256": matches[0].sha256,
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "resource": resource.__dict__,
    }


def parse_asset_id(asset_id: str) -> tuple[str, int]:
    archive, _, entry = asset_id.partition(":")
    if not archive or not entry:
        raise SystemExit(f"Invalid asset id: {asset_id}")
    return archive, int(entry)


def parse_classic_animation(data: bytes) -> dict[str, Any]:
    if len(data) < 8:
        raise SystemExit("Animation payload is smaller than the classic header")
    keyframe_count = int.from_bytes(data[0:2], "little")
    bone_count = int.from_bytes(data[2:4], "little")
    loop_start = int.from_bytes(data[4:6], "little")
    frames = []
    cursor = 8
    for _ in range(keyframe_count):
        duration = u16(data, cursor)
        root = [s16(data, cursor + 2), s16(data, cursor + 4), s16(data, cursor + 6)]
        cursor += 8
        bones = []
        for _ in range(bone_count):
            bones.append(
                {
                    "mode": s16(data, cursor),
                    "values": [s16(data, cursor + 2), s16(data, cursor + 4), s16(data, cursor + 6)],
                }
            )
            cursor += 8
        frames.append({"duration": duration, "root_delta": root, "bones": bones})
    return {
        "keyframe_count": keyframe_count,
        "bone_count": bone_count,
        "loop_start_keyframe": loop_start,
        "frames": frames,
    }


def classic_sample_keyframe(
    classic: dict[str, Any],
    *,
    target_frame_index: int,
    elapsed_ms: int,
    previous_index: int,
    bone_limit: int,
) -> dict[str, Any]:
    target = classic["frames"][target_frame_index]
    previous = classic["frames"][previous_index]
    duration = target["duration"]
    complete = duration <= 0 or elapsed_ms >= duration
    interpolator = 0x10000 if complete else classic_interpolator(elapsed_ms, duration)
    if complete:
        root_delta = target["root_delta"]
        bones = [
            {"index": index, "mode": bone["mode"], "values": bone["values"]}
            for index, bone in enumerate(target["bones"][:bone_limit])
        ]
    else:
        root_delta = [wrap_i16(classic_scaled_delta(value, interpolator)) for value in target["root_delta"]]
        bones = [
            {
                "index": 0,
                "mode": previous["bones"][0]["mode"],
                "values": previous["bones"][0]["values"],
            }
        ]
        for index in range(1, bone_limit):
            previous_bone = previous["bones"][index]
            target_bone = target["bones"][index]
            if previous_bone["mode"] != target_bone["mode"]:
                raise SystemExit(
                    f"Classic validation cannot interpolate bone mode change at bone {index}: "
                    f"{previous_bone['mode']} -> {target_bone['mode']}"
                )
            mode = previous_bone["mode"]
            if mode == 0:
                values = [
                    rotation_lerp_12bit_classic(start, end, interpolator)
                    for start, end in zip(previous_bone["values"], target_bone["values"])
                ]
            elif mode in (1, 2):
                values = [
                    wrap_i16(start + classic_scaled_delta(end - start, interpolator))
                    for start, end in zip(previous_bone["values"], target_bone["values"])
                ]
            else:
                raise SystemExit(f"Unsupported classic animation mode {mode} in bone {index}")
            bones.append({"index": index, "mode": mode, "values": values})
    return {
        "target_frame_index": target_frame_index,
        "previous_frame_index": previous_index,
        "elapsed_ms": elapsed_ms,
        "duration_ms": duration,
        "complete": complete,
        "classic_interpolator": interpolator,
        "root_delta": root_delta,
        "bones": bones,
    }


def compare_samples(production: dict[str, Any], classic: dict[str, Any]) -> None:
    if production["root_delta"] != classic["root_delta"]:
        raise SystemExit(
            f"Root mismatch frame={production['target_frame_index']} elapsed={production['elapsed_ms']}: "
            f"production={production['root_delta']} classic={classic['root_delta']}"
        )
    production_bones = {bone["index"]: bone for bone in production["bones"]}
    for classic_bone in classic["bones"]:
        production_bone = production_bones.get(classic_bone["index"])
        if production_bone is None:
            raise SystemExit(f"Missing production bone sample {classic_bone['index']}")
        if production_bone["mode"] != classic_bone["mode"] or production_bone["values"] != classic_bone["values"]:
            raise SystemExit(
                f"Bone mismatch frame={production['target_frame_index']} elapsed={production['elapsed_ms']} "
                f"bone={classic_bone['index']}: production={production_bone} classic={classic_bone}"
            )


def classic_interpolator(elapsed: int, duration: int) -> int:
    return ((elapsed << 16) + ((duration + 1) >> 1)) // duration


def classic_scaled_delta(delta: int, interpolator: int) -> int:
    return (delta * interpolator) >> 16


def rotation_lerp_12bit_classic(start: int, target: int, interpolator: int) -> int:
    start_12 = start & 0x0FFF
    diff = sign_extend_12((target - start_12) & 0x0FFF)
    return (start_12 + classic_scaled_delta(diff, interpolator)) & 0x0FFF


def select_frames(spec: str, keyframe_count: int) -> list[int]:
    if spec == "all":
        return list(range(keyframe_count))
    frames = [int(item) for item in spec.split(",") if item.strip()]
    for frame in frames:
        if frame < 0 or frame >= keyframe_count:
            raise SystemExit(f"Frame {frame} is outside keyframe count {keyframe_count}")
    return frames


def vertex_digest(model: viewer.Lm2Model) -> str:
    rows = [[round(v.x, 6), round(v.y, 6), round(v.z, 6), v.bone] for v in model.vertices]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("utf-8")).hexdigest()


def vertex_bounds(model: viewer.Lm2Model) -> dict[str, list[float]]:
    return {
        "x": [min((v.x for v in model.vertices), default=0), max((v.x for v in model.vertices), default=0)],
        "y": [min((v.y for v in model.vertices), default=0), max((v.y for v in model.vertices), default=0)],
        "z": [min((v.z for v in model.vertices), default=0), max((v.z for v in model.vertices), default=0)],
    }


def changed_vertices(original: viewer.Lm2Model, posed: viewer.Lm2Model) -> int:
    return sum(
        1
        for left, right in zip(original.vertices, posed.vertices)
        if (left.x, left.y, left.z) != (right.x, right.y, right.z)
    )


def write_html_report(path: Path, manifest: dict[str, Any]) -> None:
    rows = "\n".join(
        "<tr>"
        f"<td>{frame['frame']}</td>"
        f"<td>{frame['elapsed_ms']} / {frame['duration_ms']}</td>"
        f"<td>{frame['classic_interpolator']}</td>"
        f"<td>{html.escape(str(frame['root_delta']))}</td>"
        f"<td>{frame['changed_vertices']}</td>"
        f"<td><code>{frame['vertex_digest'][:16]}</code></td>"
        f"<td><a href=\"{html.escape(frame['artifact'])}\">json</a></td>"
        "</tr>"
        for frame in manifest["frames"]
    )
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Animation validation {html.escape(manifest['animation_asset'])}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f8; color: #17202a; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #c9d1d9; padding: 6px 8px; text-align: left; }}
th {{ background: #e8edf2; }}
code {{ font-family: ui-monospace, Consolas, monospace; }}
</style>
<h1>Animation Validation</h1>
<p><strong>Body:</strong> {html.escape(manifest['body_asset'])}<br>
<strong>Animation:</strong> {html.escape(manifest['animation_asset'])}<br>
<strong>Status:</strong> pass, {manifest['checks']['frame_samples']} frame samples</p>
<table>
<thead><tr><th>Frame</th><th>Elapsed</th><th>Classic interpolator</th><th>Root delta</th><th>Changed vertices</th><th>Vertex digest</th><th>Artifact</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</html>
""",
        encoding="utf-8",
    )


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def s16(data: bytes, offset: int) -> int:
    value = u16(data, offset)
    return value - 0x10000 if value & 0x8000 else value


def wrap_i16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def sign_extend_12(value: int) -> int:
    value &= 0x0FFF
    return value - 0x1000 if value & 0x0800 else value


def safe_name(value: str) -> str:
    return value.replace(":", "_").replace("\\", "_").replace("/", "_")


if __name__ == "__main__":
    raise SystemExit(main())
