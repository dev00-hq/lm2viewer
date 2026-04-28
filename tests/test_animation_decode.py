import json
import struct
import tempfile
import unittest
import hashlib
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

from lba2_lm2_viewer import animation
from lba2_lm2_viewer import viewer


def anim_payload(
    frames: list[tuple[int, tuple[int, int, int], list[tuple[int, int, int, int]]]],
    *,
    loop_start: int = 0,
    reserved: int = 0,
) -> bytes:
    bone_count = len(frames[0][2]) if frames else 0
    payload = bytearray(struct.pack("<HHHH", len(frames), bone_count, loop_start, reserved))
    for duration, root, bones in frames:
        if len(bones) != bone_count:
            raise ValueError("all frames must have the same bone count")
        payload.extend(struct.pack("<Hhhh", duration, *root))
        for bone in bones:
            payload.extend(struct.pack("<hhhh", *bone))
    return bytes(payload)


def resource_entry(payload: bytes) -> bytes:
    return struct.pack("<IIH", len(payload), len(payload), 0) + payload


def hqr(entries: list[bytes]) -> bytes:
    table_end = (len(entries) + 1) * 4
    offsets: list[int] = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return struct.pack("<I", table_end) + b"".join(struct.pack("<I", offset) for offset in offsets) + payloads


def file3d_record(commands: bytes) -> bytes:
    return struct.pack("<I", 4) + commands + b"\xff"


def file3d_anim(generic_id: int, animation_index: int) -> bytes:
    return b"\x03" + struct.pack("<H", generic_id) + b"\x04" + struct.pack("<h", animation_index) + b"\x00"


def file3d_body(generic_id: int, body_index: int) -> bytes:
    return b"\x01" + bytes([generic_id]) + b"\x04" + struct.pack("<h", body_index) + b"\x00"


class AnimationParserTests(unittest.TestCase):
    def test_parse_full_anim_records_preserves_raw_keyframes(self) -> None:
        data = anim_payload(
            [
                (100, (10, 20, -30), [(0, 0x0FF0, 0, 100), (1, 0, 10, -10)]),
                (80, (40, -20, 12), [(0, 0x0010, 0, 50), (1, 20, -10, 30)]),
            ],
            loop_start=1,
            reserved=7,
        )

        decoded = animation.parse_lba2_animation_records(data)

        self.assertEqual(decoded.keyframe_count, 2)
        self.assertEqual(decoded.bone_count, 2)
        self.assertEqual(decoded.loop_start_keyframe, 1)
        self.assertEqual(decoded.reserved, 7)
        self.assertEqual(decoded.trailing_bytes, 0)
        self.assertEqual(decoded.keyframes[0].to_json()["raw_header"], [100, 10, 20, -30])
        self.assertEqual(decoded.keyframes[0].bones[0].to_json()["raw"], [0, 4080, 0, 100])

    def test_summary_matches_viewer_catalog_parser(self) -> None:
        data = anim_payload(
            [
                (100, (0, 0, 0), [(0, 0, 0, 0), (1, 2, 3, 4)]),
                (50, (0, 0, 0), [(0, 0, 0, 0), (2, 5, 6, 7)]),
            ]
        )

        summary = viewer.parse_lba2_animation(data)

        self.assertEqual(summary.keyframes, 2)
        self.assertEqual(summary.boneframes, 2)
        self.assertEqual(summary.total_duration, 150)
        self.assertEqual(summary.translated_boneframes, 2)
        self.assertTrue(summary.can_fall)

    def test_parse_rejects_truncated_payload(self) -> None:
        data = anim_payload([(100, (0, 0, 0), [(0, 1, 2, 3)])])

        with self.assertRaisesRegex(animation.AnimationError, "truncated"):
            animation.parse_lba2_animation_records(data[:-1])

    def test_parse_rejects_loop_outside_keyframes(self) -> None:
        data = anim_payload([(100, (0, 0, 0), [])], loop_start=1)

        with self.assertRaisesRegex(animation.AnimationError, "loop frame 1 exceeds"):
            animation.parse_lba2_animation_records(data)

    def test_parse_keeps_unsigned_frame_duration_for_long_frames(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), [(0, 0, 0, 0)]),
                    (40000, (400, 0, 0), [(0, 0, 0, 0)]),
                ]
            )
        )

        sample = animation.sample_keyframe_transition(decoded, 1, 20000)

        self.assertFalse(sample["complete"])
        self.assertEqual(sample["duration_ms"], 40000)
        self.assertEqual(sample["root_delta"], [200, 0, 0])

    def test_rotation_lerp_uses_shortest_12bit_wrap_path(self) -> None:
        self.assertEqual(animation.rotation_lerp_12bit(0x0FF0, 0x0010, 50, 100), 0)
        self.assertEqual(animation.rotation_lerp_12bit(0x0010, 0x0FF0, 50, 100), 0)

    def test_signed_lerp_preserves_exact_quarter_steps(self) -> None:
        self.assertEqual(animation.signed_lerp_i16(-10, 10, 25, 100), -5)
        self.assertEqual(animation.signed_lerp_i16(10, -10, 25, 100), 5)

    def test_signed_lerp_matches_classic_rounded_interpolator(self) -> None:
        self.assertEqual(animation.signed_lerp_i16(0, -182, 50, 200), -46)

    def test_sample_keyframe_transition_interpolates_root_and_bones(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (
                        100,
                        (10, 20, -30),
                        [(0, 0x0FF0, 0, 100), (1, 0, 10, -10), (0, 0x0FF0, 0, 100)],
                    ),
                    (
                        100,
                        (100, -50, 25),
                        [(0, 0x0010, 0, 50), (1, 20, -10, 30), (0, 0x0010, 0, 50)],
                    ),
                ],
                loop_start=1,
            )
        )

        sample = animation.sample_keyframe_transition(decoded, 1, 50)

        self.assertEqual(sample["previous_frame_index"], 0)
        self.assertEqual(sample["root_delta"], [50, -25, 12])
        self.assertEqual(sample["bones"][0]["values"], [0x0FF0, 0, 100])
        self.assertEqual(sample["bones"][0]["interpolation"], "root_record_not_interpolated")
        self.assertEqual(sample["bones"][1]["values"], [10, 0, 10])
        self.assertEqual(sample["bones"][1]["interpolation"], "signed_linear")
        self.assertEqual(sample["bones"][2]["values"], [0, 0, 75])
        self.assertEqual(sample["bones"][2]["interpolation"], "wrapped_12bit_rotation")

    def test_sample_rejects_bone_mode_changes_until_evidence_defines_them(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), [(0, 0, 0, 0), (0, 1, 2, 3)]),
                    (100, (0, 0, 0), [(0, 0, 0, 0), (1, 4, 5, 6)]),
                ]
            )
        )

        with self.assertRaisesRegex(animation.AnimationError, "mode changed"):
            animation.sample_keyframe_transition(decoded, 1, 50)

    def test_complete_sample_uses_target_raw_values(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), [(0, 0, 0, 0)]),
                    (100, (8, 9, 10), [(0, 1, 2, 3)]),
                ]
            )
        )

        sample = animation.sample_keyframe_transition(decoded, 1, 100)

        self.assertTrue(sample["complete"])
        self.assertEqual(sample["root_delta"], [8, 9, 10])
        self.assertEqual(sample["bones"][0]["values"], [1, 2, 3])

    def test_pose_lm2_model_rotates_vertices_through_bone_hierarchy(self) -> None:
        header = viewer.Lm2Header(
            flags=1 | (1 << 8),
            bounds=(0, 15, 0, 5, 0, 0),
            bones_count=2,
            bones_offset=0,
            vertices_count=3,
            vertices_offset=0,
            normals_count=0,
            normals_offset=0,
            unknown_count=0,
            unknown_offset=0,
            polygons_size=0,
            polygons_offset=0,
            lines_count=0,
            lines_offset=0,
            spheres_count=0,
            spheres_offset=0,
            uv_groups_count=0,
            uv_groups_offset=0,
        )
        raw_vertices = (
            viewer.Vertex(0.0, 0.0, 0.0, 0),
            viewer.Vertex(10.0, 0.0, 0.0, 1),
            viewer.Vertex(5.0, 0.0, 0.0, 1),
        )
        model = viewer.Lm2Model(
            header=header,
            bones=(
                viewer.Bone(parent=1001, vertex=0, unknown_1=0, unknown_2=0),
                viewer.Bone(parent=0, vertex=1, unknown_1=0, unknown_2=0),
            ),
            vertices=(
                viewer.Vertex(0.0, 0.0, 0.0, 0),
                viewer.Vertex(10.0, 0.0, 0.0, 1),
                viewer.Vertex(15.0, 0.0, 0.0, 1),
            ),
            normals=(),
            polygons=(),
            lines=(),
            spheres=(),
            uv_groups=(),
            raw_vertices=raw_vertices,
        )
        decoded = animation.parse_lba2_animation_records(
            anim_payload([(100, (0, 0, 0), [(0, 0, 0, 0), (0, 0, 0, 1024)])])
        )

        posed, pose = viewer.pose_lm2_model(
            model,
            decoded,
            sample_frame=0,
            elapsed_ms=100,
        )

        self.assertAlmostEqual(posed.vertices[2].x, 10.0, places=6)
        self.assertAlmostEqual(posed.vertices[2].y, 5.0, places=6)
        self.assertEqual(pose["transform"]["rotation_order"], "x_y_z")

    def test_pose_lm2_model_requires_raw_local_vertices(self) -> None:
        header = viewer.Lm2Header(
            flags=1 | (1 << 8),
            bounds=(0, 0, 0, 0, 0, 0),
            bones_count=1,
            bones_offset=0,
            vertices_count=1,
            vertices_offset=0,
            normals_count=0,
            normals_offset=0,
            unknown_count=0,
            unknown_offset=0,
            polygons_size=0,
            polygons_offset=0,
            lines_count=0,
            lines_offset=0,
            spheres_count=0,
            spheres_offset=0,
            uv_groups_count=0,
            uv_groups_offset=0,
        )
        model = viewer.Lm2Model(
            header=header,
            bones=(viewer.Bone(parent=1001, vertex=0, unknown_1=0, unknown_2=0),),
            vertices=(viewer.Vertex(0.0, 0.0, 0.0, 0),),
            normals=(),
            polygons=(),
            lines=(),
            spheres=(),
            uv_groups=(),
            raw_vertices=(viewer.Vertex(0.0, 0.0, 0.0, 0),),
        )
        decoded = animation.parse_lba2_animation_records(
            anim_payload([(100, (0, 0, 0), [(0, 0, 0, 0)])])
        )

        with self.assertRaisesRegex(viewer.Lm2Error, "raw vertices"):
            viewer.pose_lm2_model(replace(model, raw_vertices=()), decoded)

    def test_build_evidence_accepts_explicit_previous_frame_for_loop_sample(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), [(0, 0, 0, 0)]),
                    (100, (0, 0, 0), [(0, 0x0FF0, 0, 0)]),
                    (100, (0, 0, 0), [(0, 0x0010, 0, 0)]),
                ],
                loop_start=1,
            )
        )

        evidence = animation.build_animation_evidence(
            decoded,
            source={"catalog_asset_id": "ANIM.HQR:1"},
            sample_frame=1,
            previous_frame=2,
            elapsed_ms=50,
        )

        sample = evidence["samples"][0]
        self.assertEqual(sample["previous_frame_index"], 2)
        self.assertEqual(sample["bones"][0]["values"][0], 0x0010)

    def test_write_animation_evidence_emits_json_with_body_compatibility(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload([(100, (0, 0, 0), [(0, 1, 2, 3), (1, 4, 5, 6)])])
        )

        evidence = animation.build_animation_evidence(
            decoded,
            source={"catalog_asset_id": "ANIM.HQR:1"},
            body={"asset_id": "BODY.HQR:1", "bone_count": 2},
        )

        self.assertEqual(evidence["schema_version"], animation.SCHEMA_VERSION)
        self.assertTrue(evidence["body_compatibility"]["bone_count_matches"])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "anim.json"
            animation.write_animation_evidence(evidence, path)
            self.assertIn('"lm2_animation_evidence.v0"', path.read_text(encoding="utf-8"))

    def test_animation_subcommand_detection_owns_animation_command(self) -> None:
        self.assertTrue(viewer.is_animation_subcommand(["animation"]))
        self.assertTrue(viewer.is_animation_subcommand(["animation", "--help"]))
        self.assertFalse(viewer.is_animation_subcommand(["export"]))

    def test_animation_command_exports_catalog_animation_evidence(self) -> None:
        data = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(data)]))
            output = root / "anim.evidence.json"

            with redirect_stdout(StringIO()):
                exit_code = viewer.animation_command(
                    [
                        "--asset-root",
                        str(root),
                        "--asset",
                        "ANIM.HQR:1",
                        "--out",
                        str(output),
                    ]
                )

            self.assertEqual(exit_code, 0)
            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(evidence["schema_version"], animation.SCHEMA_VERSION)
            self.assertEqual(evidence["animation"]["keyframe_count"], 1)
            self.assertEqual(evidence["animation"]["keyframes"][0]["bones"][0]["raw"], [0, 4, 5, 6])

    def test_catalog_keeps_anim3ds_entries_raw_even_when_header_looks_like_anim(self) -> None:
        data = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(hqr([resource_entry(data)]))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["animations"], 0)
            self.assertEqual(catalog["summary"]["decoded_animations"], 0)
            self.assertEqual(catalog["summary"]["raw_animations"], 1)
            self.assertEqual(catalog["summary"]["animation_assets"], 1)
            asset = catalog["assets"][0]
            self.assertEqual(asset["entry_type"], "animation-raw")
            self.assertEqual(asset["animation_state"], "raw")
            self.assertEqual(asset["features"], {"parsed": False})
            stats = asset["stats"]
            self.assertEqual(stats["decoded_bytes"], len(data))
            self.assertEqual(stats["decoded_sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(
                stats["header_words"],
                list(struct.unpack_from("<8H", data, 0)),
            )
            self.assertEqual(stats["header_word_count"], 8)
            self.assertEqual(stats["parse_status"], "raw")
            self.assertEqual(stats["decode_status"], "deferred")
            self.assertEqual(stats["decode_note"], "ANIM3DS semantic decode is not implemented")
            self.assertNotIn("parse_error", stats)
            self.assertEqual(stats["semantic_layout"], "unknown")
            self.assertEqual(len(stats["unknown_descriptors"]), 2)
            header_descriptor = stats["unknown_descriptors"][0]
            payload_descriptor = stats["unknown_descriptors"][1]
            self.assertEqual(header_descriptor["section"], "header_words")
            self.assertEqual(header_descriptor["offset"], 0)
            self.assertEqual(header_descriptor["length"], 16)
            self.assertEqual(header_descriptor["confidence"], "high")
            self.assertEqual(header_descriptor["related_decoded_fields"], ["header_words"])
            self.assertIn("raw animation header semantics", header_descriptor["note"])
            self.assertEqual(
                header_descriptor["sha256"],
                hashlib.sha256(data[:16]).hexdigest(),
            )
            self.assertEqual(payload_descriptor["section"], "payload_after_header_words")
            self.assertEqual(payload_descriptor["offset"], 16)
            self.assertEqual(payload_descriptor["length"], len(data) - 16)
            self.assertEqual(payload_descriptor["confidence"], "high")
            self.assertIn("Opaque animation payload", payload_descriptor["note"])
            self.assertEqual(
                payload_descriptor["sha256"],
                hashlib.sha256(data[16:]).hexdigest(),
            )

    def test_catalog_tracks_every_anim3ds_entry_with_independent_unknown_descriptors(self) -> None:
        first = b"\x01\x00\x02\x00header-one"
        second = b"\x03\x00\x04\x00\x05\x00payload-two"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(
                hqr([resource_entry(first), b"", resource_entry(second)])
            )

            catalog = viewer.build_catalog(root)

            assets = catalog["assets"]
            self.assertEqual([asset["id"] for asset in assets], ["ANIM3DS.HQR:1", "ANIM3DS.HQR:3"])
            self.assertEqual(catalog["summary"]["animations"], 0)
            self.assertEqual(catalog["summary"]["raw_animations"], 2)
            self.assertEqual(catalog["summary"]["animation_assets"], 2)
            self.assertEqual(assets[0]["stats"]["decoded_sha256"], hashlib.sha256(first).hexdigest())
            self.assertEqual(assets[1]["stats"]["decoded_sha256"], hashlib.sha256(second).hexdigest())
            self.assertNotEqual(
                assets[0]["stats"]["unknown_descriptors"][0]["sha256"],
                assets[1]["stats"]["unknown_descriptors"][0]["sha256"],
            )

    def test_catalog_counts_decoded_and_raw_animation_entries_separately(self) -> None:
        decoded = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        raw = b"\x01\x00\x02\x00anim3ds"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(decoded)]))
            (root / "ANIM3DS.HQR").write_bytes(hqr([resource_entry(raw)]))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["animations"], 1)
            self.assertEqual(catalog["summary"]["decoded_animations"], 1)
            self.assertEqual(catalog["summary"]["raw_animations"], 1)
            self.assertEqual(catalog["summary"]["animation_assets"], 2)
            decoded_asset = viewer.find_catalog_asset(catalog, "ANIM.HQR:1")
            raw_asset = viewer.find_catalog_asset(catalog, "ANIM3DS.HQR:1")
            self.assertEqual(decoded_asset["entry_type"], "animation")
            self.assertEqual(decoded_asset["animation_state"], "decoded")
            self.assertEqual(raw_asset["entry_type"], "animation-raw")
            self.assertEqual(raw_asset["animation_state"], "raw")

    def test_catalog_labels_anim_entries_from_file3d_metadata(self) -> None:
        decoded = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        file3d = file3d_record(file3d_body(0, 0) + file3d_anim(1, 1))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(decoded)]))
            (root / "RESS.HQR").write_bytes(
                hqr([b""] * 43 + [resource_entry(file3d)])
            )

            catalog = viewer.build_catalog(root)

            asset = viewer.find_catalog_asset(catalog, "ANIM.HQR:1")
            self.assertEqual(asset["label"], "Walk (ANIM.HQR:1)")
            self.assertEqual(asset["animation_metadata"]["generic_names"], ["GEN_ANIM_MARCHE"])
            self.assertEqual(asset["animation_metadata"]["compatible_body_ids"], [1])
            self.assertTrue(catalog["metadata"]["file3d_animation_labels"])

    def test_catalog_distinguishes_anim_parse_failures_from_anim3ds_deferment(self) -> None:
        data = b"\xff"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(data)]))

            catalog = viewer.build_catalog(root)

            asset = catalog["assets"][0]
            self.assertEqual(asset["entry_type"], "animation-raw")
            self.assertEqual(asset["animation_state"], "raw")
            self.assertEqual(catalog["summary"]["raw_animations"], 1)
            stats = asset["stats"]
            self.assertEqual(stats["decode_status"], "parse_failed")
            self.assertIn("Animation parser rejected", stats["decode_note"])
            self.assertIn("parse_error", stats)
            self.assertNotIn("ANIM3DS", stats["unknown_descriptors"][0]["note"])

    def test_animation_command_rejects_raw_animation_catalog_entries(self) -> None:
        data = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(hqr([resource_entry(data)]))

            with self.assertRaisesRegex(viewer.Lm2Error, "not a decoded animation"):
                with redirect_stdout(StringIO()):
                    viewer.animation_command(
                        [
                            "--asset-root",
                            str(root),
                            "--asset",
                            "ANIM3DS.HQR:1",
                            "--out",
                            str(root / "anim3ds.evidence.json"),
                        ]
                    )


if __name__ == "__main__":
    unittest.main()
