import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lba2_lm2_viewer import server
from lba2_lm2_viewer import viewer
from lba2_lm2_viewer.catalog_graph import build_catalog_graph
from lba2_lm2_viewer.exports import export_catalog_asset_probe, export_model_probe


def resource_entry(payload: bytes) -> bytes:
    return struct.pack("<IIH", len(payload), len(payload), 0) + payload


def classic_hqr(entries: list[bytes]) -> bytes:
    table_end = len(entries) * 4
    offsets: list[int] = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return struct.pack("<I", table_end) + b"".join(
        struct.pack("<I", offset) for offset in offsets[1:]
    ) + payloads


def hqr(entries: list[bytes]) -> bytes:
    table_end = (len(entries) + 1) * 4
    offsets: list[int] = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return struct.pack("<I", table_end) + b"".join(
        struct.pack("<I", offset) for offset in offsets
    ) + payloads


def classic_zero_hqr(entries: list[bytes]) -> bytes:
    table_end = len(entries) * 4
    offsets: list[int] = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return b"".join(struct.pack("<I", offset) for offset in offsets) + payloads


def lsp_sprite_payload() -> bytes:
    return (
        b"\x00" * 8
        + bytes([4, 2, 1, 2])
        + bytes([3, 0x00, 0x81, 7, 0x40, 8])
        + bytes([1, 0xC3, 1, 2, 0, 3])
    )


def wave_payload(
    data: bytes = b"\x80\x81\x82\x83",
    *,
    sample_rate: int = 22050,
    channels: int = 1,
    bits_per_sample: int = 8,
) -> bytes:
    block_align = channels * max(1, bits_per_sample // 8)
    byte_rate = sample_rate * block_align
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )
    body = (
        b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def smacker_payload(
    *,
    width: int = 320,
    height: int = 200,
    frames: int = 30,
    frame_rate: int = -6666,
) -> bytes:
    return (
        b"SMK2"
        + struct.pack("<IIIiII", width, height, frames, frame_rate, 0, 64)
        + b"\x00" * 64
    )


def visual_ress_hqr() -> bytes:
    palette = bytearray()
    for index in range(256):
        palette.extend((index, index, index))
    texture = bytes([0, 1, 2, 3]) * (viewer.TEXTURE_ATLAS_PIXELS // 4)
    return classic_zero_hqr([resource_entry(bytes(palette))] + [b""] * 5 + [resource_entry(texture)])


def scene_zone_record(
    *,
    start: tuple[int, int, int] = (0, 0, 0),
    end: tuple[int, int, int] = (511, 255, 511),
    info: tuple[int, int, int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0, 0, 0),
    zone_type: int = 3,
    value: int = 7,
) -> bytes:
    return (
        struct.pack("<iii", *start)
        + struct.pack("<iii", *end)
        + struct.pack("<iiiiiiii", *info)
        + struct.pack("<hh", zone_type, value)
    )


def scene_payload(zone_records: list[bytes]) -> bytes:
    payload = bytearray()
    payload.extend(struct.pack("<bbbbbbb", 2, 0, 0, 3, 0, 0, 9))
    payload.extend(struct.pack("<hh", 45, 90))
    for sample in range(4):
        payload.extend(struct.pack("<hhhhh", sample, 1, 2, 22050, 64))
    payload.extend(struct.pack("<hhb", 5, 6, 7))
    payload.extend(struct.pack("<hhh", 100, 200, 300))
    payload.extend(struct.pack("<h", 0))
    payload.extend(struct.pack("<h", 0))
    payload.extend(struct.pack("<h", 1))
    payload.extend(struct.pack("<I", 0x12345678))
    payload.extend(struct.pack("<h", len(zone_records)))
    for record in zone_records:
        payload.extend(record)
    payload.extend(struct.pack("<h", 0))
    payload.extend(struct.pack("<I", 0))
    return bytes(payload)


def bkg_grid_payload(column_word: int = 0x0001) -> bytes:
    column_stream = bytes([2, 0x80]) + struct.pack("<H", column_word) + bytes([0x17])
    offsets = struct.pack(
        f"<{viewer.BKG_GRID_COLUMN_COUNT}H",
        *([viewer.BKG_GRID_OFFSET_TABLE_BYTES] * viewer.BKG_GRID_COLUMN_COUNT),
    )
    used_blocks = bytes([0x40]) + (b"\x00" * 31)
    return bytes([0, 0]) + used_blocks + offsets + column_stream


def bkg_affgraph_payload() -> bytes:
    return (
        bytes([1, 1, 0, 0])
        + bytes([1, 0x80, 7])
    )


def textured_triangle_lm2() -> bytes:
    bones_offset = 0x60
    vertices_offset = 0x68
    normals_offset = 0x80
    polygons_offset = 0x80
    lines_offset = 0xA0
    uv_groups_offset = 0xA0
    values = (
        1,
        bones_offset,
        3,
        vertices_offset,
        0,
        normals_offset,
        0,
        normals_offset,
        0x20,
        polygons_offset,
        0,
        lines_offset,
        0,
        lines_offset,
        1,
        uv_groups_offset,
    )
    header = struct.pack("<ii6i16I", 1, 0, 0, 10, 0, 10, 0, 0, *values)
    bone = struct.pack("<HHHH", 1001, 0, 0, 0)
    vertices = b"".join(
        (
            struct.pack("<hhhH", 0, 0, 0, 0),
            struct.pack("<hhhH", 10, 0, 0, 0),
            struct.pack("<hhhH", 0, 10, 0, 0),
        )
    )
    section_header = struct.pack("<HHHH", 8, 1, 0x20, 0)
    polygon = b"".join(
        (
            struct.pack("<HHH", 0, 1, 2),
            struct.pack("<H", 0),
            struct.pack("<H", 12),
            struct.pack("<h", 0),
            bytes(
                (
                    0,
                    0,
                    0,
                    0,
                    0,
                    4,
                    0,
                    0,
                    0,
                    0,
                    0,
                    4,
                )
            ),
        )
    )
    uv_group = bytes((0, 0, 4, 4))
    return header + bone + vertices + section_header + polygon + uv_group


class ExportProbeTests(unittest.TestCase):
    def test_export_subcommand_detection_preserves_literal_export_path(self) -> None:
        self.assertFalse(viewer.is_export_subcommand(["export"]))
        self.assertFalse(viewer.is_export_subcommand(["export", "--no-browser"]))
        self.assertTrue(viewer.is_export_subcommand(["export", "--help"]))
        self.assertTrue(
            viewer.is_export_subcommand(
                ["export", "--asset-root", "assets", "--asset", "BODY.HQR:1", "--out", "out"]
            )
        )

    def test_export_model_probe_writes_obj_manifest_and_textures(self) -> None:
        model = viewer.parse_lm2(textured_triangle_lm2())
        pixels = [0x112233 for _ in range(16)]
        atlas = {"width": 4, "height": 4, "pixels": pixels}
        palette = [0 for _ in range(256)]
        palette[12] = 0x445566

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "probe"
            manifest = export_model_probe(
                model=model,
                output_dir=output_dir,
                source={
                    "catalog_asset_id": "BODY.HQR:1",
                    "archive": "BODY.HQR",
                    "entry_index": 1,
                    "classic_index": 0,
                    "decoded_bytes": len(textured_triangle_lm2()),
                },
                polygon_mode="original",
                palette=palette,
                texture_atlas=atlas,
            )

            self.assertEqual(manifest["schema_version"], "lm2_probe.v0")
            self.assertEqual(manifest["options"]["polygon_mode"], "original")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "BODY.HQR:1")
            self.assertEqual(manifest["evidence"]["stable_id"], "BODY.HQR:1")
            self.assertEqual(manifest["evidence"]["evidence_status"], "decoded_only")
            self.assertIn("not live runtime gameplay proof", manifest["evidence"]["proof_scope"])
            self.assertEqual(manifest["files"]["obj"], "BODY.HQR_1.obj")
            self.assertEqual(manifest["files"]["shared_atlas_png"], "BODY.HQR_1_atlas.png")
            self.assertEqual(
                manifest["files"]["uv_group_pngs"],
                [{"uv_group": 0, "path": "BODY.HQR_1_uv000.png"}],
            )

            manifest_path = output_dir / "manifest.json"
            obj_path = output_dir / "BODY.HQR_1.obj"
            mtl_path = output_dir / "BODY.HQR_1.mtl"
            atlas_path = output_dir / "BODY.HQR_1_atlas.png"
            group_path = output_dir / "BODY.HQR_1_uv000.png"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(obj_path.exists())
            self.assertTrue(mtl_path.exists())
            self.assertTrue(atlas_path.exists())
            self.assertTrue(group_path.exists())
            self.assertEqual(atlas_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

            obj = obj_path.read_text(encoding="utf-8")
            self.assertIn("mtllib BODY.HQR_1.mtl", obj)
            self.assertIn("usemtl lm2_texture_000", obj)
            self.assertIn("f 1/1 2/2 3/3", obj)

            written_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(written_manifest["stats"]["polygons"], 1)
            self.assertEqual(written_manifest["uv_groups"][0]["polygons"], [0])

    def test_triangulated_mode_records_triangle_mapping(self) -> None:
        model = viewer.parse_lm2(textured_triangle_lm2())

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = export_model_probe(
                model=model,
                output_dir=Path(temp_dir),
                source={"catalog_asset_id": "BODY.HQR:1"},
                polygon_mode="triangulated",
            )

            self.assertEqual(manifest["options"]["polygon_mode"], "triangulated")
            self.assertEqual(manifest["obj_faces"][0]["faces_local_indices"], [[0, 1, 2]])

    def test_export_catalog_asset_probe_uses_catalog_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "BODY.HQR").write_bytes(
                classic_hqr([resource_entry(textured_triangle_lm2())])
            )
            output_dir = Path(temp_dir) / "export"

            manifest = export_catalog_asset_probe(
                asset_root=root,
                asset_id="BODY.HQR:1",
                output_dir=output_dir,
            )

            self.assertEqual(manifest["source"]["catalog_asset_id"], "BODY.HQR:1")
            self.assertEqual(manifest["source"]["archive"], "BODY.HQR")
            self.assertEqual(manifest["source"]["entry_index"], 1)
            self.assertEqual(manifest["source"]["classic_index"], 0)
            self.assertEqual(manifest["evidence"]["stable_id"], "BODY.HQR:1")
            self.assertEqual(manifest["evidence"]["runtime_contract_ids"], [])
            self.assertIn("missing LBA2 palette archive", manifest["warnings"][0])
            self.assertTrue((output_dir / "BODY.HQR_1.obj").exists())

    def test_export_catalog_asset_probe_ignores_stale_reverse_usage(self) -> None:
        payload = textured_triangle_lm2()
        catalog = {
            "schema": "viewer-catalog-v1",
            "source_mode": "test",
            "assets": [
                {
                    "id": "BODY.HQR:1",
                    "kind": "model",
                    "label": "Standalone model",
                    "entry_type": "body",
                    "relative_path": "BODY.HQR/1",
                    "source": {
                        "hqr": "BODY.HQR",
                        "entry_index": 1,
                        "classic_index": 0,
                        "offset": 0,
                        "raw_bytes": len(payload),
                    },
                    "stats": {"bones": 1},
                    "scene_usages": [
                        {
                            "kind": "body",
                            "scene_asset_id": "SCENE.HQR:3",
                            "scene_entry_index": 3,
                            "scene_index": 2,
                            "object_index": 1,
                            "target_asset_id": "BODY.HQR:1",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            output_dir = Path(temp_dir) / "export"

            with (
                patch("lba2_lm2_viewer.viewer.build_catalog", return_value=catalog),
                patch("lba2_lm2_viewer.viewer.read_hqr_payload", return_value=(payload, {"compression": 0})),
            ):
                manifest = export_catalog_asset_probe(
                    asset_root=root,
                    asset_id="BODY.HQR:1",
                    output_dir=output_dir,
                )

        self.assertEqual(manifest["evidence"]["scene_usage_count"], 0)
        self.assertEqual(manifest["evidence"]["relationship_link_count"], 0)
        self.assertEqual(manifest["evidence"]["promotion_packet_ids"], [])

    def test_viewer_server_exports_loaded_catalog_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "BODY.HQR").write_bytes(
                classic_hqr([resource_entry(textured_triangle_lm2())])
            )
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "server-export"

            response = viewer_server.export_catalog_asset("BODY.HQR:1", output_dir)

            self.assertEqual(response["output_dir"], str(output_dir.resolve()))
            self.assertEqual(
                response["manifest"]["source"]["catalog_asset_id"], "BODY.HQR:1"
            )
            self.assertEqual(
                response["manifest"]["evidence"]["proof_scope"],
                "decoded model geometry and generated OBJ/texture evidence; not live runtime gameplay proof",
            )
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_export_from_relationship_row_records_selected_edge_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "BODY.HQR").write_bytes(
                classic_hqr([resource_entry(textured_triangle_lm2())])
            )
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            assert viewer_server.catalog is not None
            viewer_server.catalog["assets"].append(
                {
                    "id": "SCENE.HQR:3",
                    "kind": "scene",
                    "label": "Scene 3",
                    "entry_type": "scene",
                    "source": {"hqr": "SCENE.HQR", "entry_index": 3},
                    "stats": {
                        "semantic_layout": "scene_runtime_layout_partial",
                        "reconnaissance": {
                            "objects": [
                                {
                                    "index": 1,
                                    "links": {
                                        "body": {
                                            "asset_id": "BODY.HQR:1",
                                            "asset_available": True,
                                            "resolution_rule": "synthetic relationship-row export evidence",
                                        }
                                    },
                                }
                            ]
                        },
                    },
                }
            )
            viewer_server.catalog_graph = build_catalog_graph(viewer_server.catalog)
            edge_id = viewer_server.catalog_graph.indexes["sceneUsagesByAssetId"]["BODY.HQR:1"][0]
            output_dir = Path(temp_dir) / "server-export"

            response = viewer_server.export_catalog_asset(
                "BODY.HQR:1",
                output_dir,
                selected_edge_id=edge_id,
            )

            evidence = response["manifest"]["evidence"]
            self.assertEqual(evidence["selected_edge_ids"], [edge_id])
            self.assertEqual(evidence["relationship_link_count"], 1)
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_viewer_server_export_manifest_ignores_stale_reverse_usage_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "BODY.HQR").write_bytes(
                classic_hqr([resource_entry(textured_triangle_lm2())])
            )
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            asset = viewer_server.find_catalog_asset("BODY.HQR:1")
            asset["scene_usages"] = [
                {
                    "kind": "body",
                    "scene_asset_id": "SCENE.HQR:3",
                    "scene_entry_index": 3,
                    "scene_index": 2,
                    "object_index": 1,
                    "target_asset_id": "BODY.HQR:1",
                    "resolution_rule": "synthetic graph usage evidence",
                }
            ]
            viewer_server.catalog_graph = None
            output_dir = Path(temp_dir) / "server-export"
            packets = {
                "manifest": "<port-repo>/docs/promotion_packets/manifest.json",
                "packets": [
                    {
                        "id": "scene_packet",
                        "runtime_contracts": ["scene_contract"],
                        "fixture_source": {"scene": 2},
                    },
                    {
                        "id": "other_scene_packet",
                        "runtime_contracts": ["other_contract"],
                        "fixture_source": {"scene": 9},
                    },
                ],
            }

            with patch("lba2_lm2_viewer.server.read_port_promotion_packets", return_value=packets):
                response = viewer_server.export_catalog_asset("BODY.HQR:1", output_dir)

            evidence = response["manifest"]["evidence"]
            self.assertEqual(evidence["scene_usage_count"], 0)
            self.assertEqual(evidence["promotion_packet_ids"], [])
            self.assertEqual(evidence["runtime_contract_ids"], [])
            self.assertEqual(
                evidence["promotion_packet_source"],
                "not_scene_linked",
            )

    def test_viewer_server_promotion_packet_links_use_graph_scene_evidence(self) -> None:
        catalog = {
            "schema": "viewer-catalog-v1",
            "assets": [
                {
                    "id": "SCENE.HQR:3",
                    "kind": "scene",
                    "label": "Scene 3",
                    "entry_type": "scene",
                    "source": {"hqr": "SCENE.HQR", "entry_index": 3},
                    "stats": {
                        "semantic_layout": "scene_runtime_layout_partial",
                        "reconnaissance": {
                            "objects": [
                                {
                                    "index": 1,
                                    "links": {
                                        "body": {
                                            "asset_id": "BODY.HQR:1",
                                            "asset_available": True,
                                            "resolution_rule": "synthetic scene object evidence",
                                        },
                                    },
                                },
                            ],
                        },
                    },
                },
                {
                    "id": "BODY.HQR:1",
                    "kind": "model",
                    "label": "Linked model",
                    "entry_type": "body",
                    "source": {"hqr": "BODY.HQR", "entry_index": 1},
                    "stats": {"bones": 1},
                },
            ],
        }
        viewer_server = server.ViewerServer(None, None)
        viewer_server.catalog = catalog
        viewer_server.catalog_graph = build_catalog_graph(catalog)
        packets = {
            "manifest": "<port-repo>/docs/promotion_packets/manifest.json",
            "packets": [
                {
                    "id": "scene_packet",
                    "runtime_contracts": ["scene_contract"],
                    "fixture_source": {"scene": 2},
                },
                {
                    "id": "other_scene_packet",
                    "runtime_contracts": ["other_contract"],
                    "fixture_source": {"scene": 9},
                },
            ],
        }

        with patch("lba2_lm2_viewer.server.read_port_promotion_packets", return_value=packets):
            links = viewer_server.export_promotion_packet_links(catalog["assets"][1])

        self.assertEqual(links["promotion_packet_ids"], ["scene_packet"])
        self.assertEqual(links["runtime_contract_ids"], ["scene_contract"])

    def test_viewer_server_exports_sprite_frame_png_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "SPRITES.HQR").write_bytes(
                classic_zero_hqr(
                    [resource_entry(lsp_sprite_payload())]
                    + [b""] * 126
                    + [resource_entry(lsp_sprite_payload())]
                )
            )
            (root / "RESS.HQR").write_bytes(visual_ress_hqr())
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "sprite-export"

            response = viewer_server.export_catalog_asset("SPRITES.HQR:127", output_dir)

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "sprite_frame_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "SPRITES.HQR:127")
            self.assertEqual(manifest["evidence"]["stable_id"], "SPRITES.HQR:127")
            self.assertIn("not live runtime gameplay proof", manifest["evidence"]["proof_scope"])
            self.assertEqual(manifest["options"]["range_policy"], "selected sprite frame")
            self.assertEqual(manifest["stats"]["frame_count"], 1)
            self.assertEqual(manifest["files"]["frames"][0]["runtime_sprite_index"], 127)
            self.assertTrue((output_dir / manifest["files"]["sprite_png"]).exists())
            self.assertTrue((output_dir / manifest["files"]["sheet_png"]).exists())
            self.assertEqual(
                (output_dir / manifest["files"]["sprite_png"]).read_bytes()[:8],
                b"\x89PNG\r\n\x1a\n",
            )

    def test_viewer_server_exports_anim3ds_range_sheet(self) -> None:
        info = b"TEST" + struct.pack("<hh", 0, 1)
        entries = [resource_entry(lsp_sprite_payload()), resource_entry(lsp_sprite_payload())] + [b""] * 125
        entries.append(resource_entry(info))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "ANIM3DS.HQR").write_bytes(classic_zero_hqr(entries))
            (root / "RESS.HQR").write_bytes(visual_ress_hqr())
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "anim3ds-export"

            response = viewer_server.export_catalog_asset("ANIM3DS.HQR:0", output_dir)

            manifest = response["manifest"]
            self.assertEqual(manifest["options"]["range_policy"], "selected ANIM3DS range")
            self.assertEqual(manifest["stats"]["frame_count"], 2)
            self.assertEqual(
                [frame["asset_id"] for frame in manifest["files"]["frames"]],
                ["ANIM3DS.HQR:0", "ANIM3DS.HQR:1"],
            )
            self.assertTrue((output_dir / manifest["files"]["sheet_png"]).exists())

    def test_viewer_server_exports_sample_wave_audio(self) -> None:
        sample = wave_payload(sample_rate=11025, data=b"\x80\x81\x82\x83")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "SAMPLES.HQR").write_bytes(hqr([resource_entry(sample)]))
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "sample-export"

            response = viewer_server.export_catalog_asset("SAMPLES.HQR:0", output_dir)

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "sample_audio_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "SAMPLES.HQR:0")
            self.assertEqual(manifest["evidence"]["stable_id"], "SAMPLES.HQR:0")
            self.assertIn("not live audio playback", manifest["evidence"]["proof_scope"])
            self.assertEqual(manifest["source"]["hqr_table_index"], 1)
            self.assertEqual(manifest["audio"]["runtime_sample_id"], 0)
            self.assertEqual(manifest["audio"]["sample_rate"], 11025)
            self.assertEqual(manifest["audio"]["duration_ms"], 0.363)
            wav_path = output_dir / manifest["files"]["wav"]
            self.assertEqual(wav_path.read_bytes(), sample)
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_viewer_server_serves_sample_audio_payload(self) -> None:
        sample = wave_payload(sample_rate=11025, data=b"\x80\x81\x82\x83")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "SAMPLES.HQR").write_bytes(hqr([resource_entry(sample)]))
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)

            payload, asset = viewer_server.sample_audio_payload("SAMPLES.HQR:0")

            self.assertEqual(payload, sample)
            self.assertEqual(asset["stats"]["semantic_layout"], "sample_wave_audio")

    def test_viewer_server_exports_text_payload_bank_bundle(self) -> None:
        order = resource_entry(struct.pack("<HH", 100, 200))
        first_record = b"\x01Hi\x00"
        second_record = b"\x02Line\x01Two\x00"
        text_payload = (
            struct.pack("<HHH", 6, 6 + len(first_record), 6 + len(first_record) + len(second_record))
            + first_record
            + second_record
        )
        bank = resource_entry(text_payload)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "TEXT.HQR").write_bytes(classic_hqr([order, bank]))
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "text-export"

            response = viewer_server.export_catalog_asset("TEXT.HQR:1", output_dir)

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "text_payload_bank_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "TEXT.HQR:1")
            self.assertEqual(manifest["order_table"]["catalog_asset_id"], "TEXT.HQR:0")
            self.assertEqual(manifest["text"]["record_count"], 2)
            bundle = json.loads((output_dir / manifest["files"]["bundle_json"]).read_text(encoding="utf-8"))
            self.assertEqual(bundle["schema_version"], "text_payload_bank_bundle.v0")
            self.assertEqual(bundle["records"][0]["message_id"], 100)
            self.assertEqual(bundle["records"][0]["flag"], 1)
            self.assertEqual(bundle["records"][0]["text"], "Hi")
            self.assertEqual(bundle["records"][1]["message_id"], 200)
            self.assertEqual(bundle["records"][1]["text"], "Line\nTwo")
            self.assertEqual(bundle["records"][1]["raw_record_hex"], second_record.hex())
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_viewer_server_exports_smacker_video_container(self) -> None:
        names = b"INTRO.SMK\r\n"
        video = smacker_payload(frames=45)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            ress_entries = [b""] * 48
            ress_entries[47] = resource_entry(names)
            (root / "RESS.HQR").write_bytes(hqr(ress_entries))
            video_dir = root / "VIDEO"
            video_dir.mkdir()
            (video_dir / "VIDEO.HQR").write_bytes(hqr([resource_entry(video)]))
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "video-export"

            response = viewer_server.export_catalog_asset("VIDEO/VIDEO.HQR:0", output_dir)

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "smacker_video_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "VIDEO/VIDEO.HQR:0")
            self.assertEqual(manifest["source"]["hqr_table_index"], 1)
            self.assertEqual(manifest["options"]["format"], "smacker_container_passthrough")
            self.assertFalse(manifest["options"]["codec_decode"])
            self.assertEqual(manifest["video"]["acf_index"], 0)
            self.assertEqual(manifest["video"]["acf_name"], "INTRO.SMK")
            self.assertEqual(manifest["video"]["frame_count"], 45)
            smk_path = output_dir / manifest["files"]["smk"]
            self.assertEqual(smk_path.name, "INTRO.SMK")
            self.assertEqual(smk_path.read_bytes(), video)
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_viewer_server_exports_screen_indexed_image_with_paired_palette(self) -> None:
        image = bytes([0, 1, 2, 3]) * (viewer.SCREEN_IMAGE_PIXELS // 4)
        palette = bytes(range(256)) * 3
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "SCREEN.HQR").write_bytes(classic_hqr([resource_entry(image), resource_entry(palette)]))
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "screen-export"

            response = viewer_server.export_catalog_asset("SCREEN.HQR:0", output_dir)
            frame = viewer_server.screen_indexed_image_frame(
                viewer_server.find_catalog_asset("SCREEN.HQR:0")
            )

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "screen_indexed_image_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "SCREEN.HQR:0")
            self.assertEqual(manifest["screen"]["palette_entry"], {"hqr": "SCREEN.HQR", "entry_index": 1})
            self.assertEqual(manifest["screen"]["width"], 640)
            self.assertEqual(manifest["screen"]["height"], 480)
            self.assertEqual(frame["rgba"][:4], [0, 1, 2, 255])
            png_path = output_dir / manifest["files"]["png"]
            self.assertTrue(png_path.exists())
            self.assertEqual(png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_viewer_server_exports_ress_indexed_image_with_normal_palette(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "RESS.HQR").write_bytes(visual_ress_hqr())
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "ress-export"

            response = viewer_server.export_catalog_asset("RESS.HQR:6", output_dir)
            frame = viewer_server.ress_indexed_image_frame(
                viewer_server.find_catalog_asset("RESS.HQR:6")
            )

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "ress_indexed_image_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "RESS.HQR:6")
            self.assertEqual(manifest["image"]["width"], 256)
            self.assertEqual(manifest["image"]["height"], 256)
            self.assertEqual(frame["rgba"][:4], [0, 0, 0, 255])
            self.assertTrue((output_dir / manifest["files"]["png"]).exists())

    def test_viewer_server_exports_holomap_plan_image_with_normal_palette(self) -> None:
        plan_image = bytes([0, 1, 2, 3]) * (viewer.SCREEN_IMAGE_PIXELS // 4)
        plan_params = struct.pack("<iiiiiiiii", 1, 2, 3, 4, 5, 6, 7, 8, 9)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            entries = [b""] * 20
            entries[0] = resource_entry(bytes(viewer.HOLOMAP_GLOBE_UV_BYTES))
            entries[18] = resource_entry(plan_image)
            entries[19] = resource_entry(plan_params)
            (root / "HOLOMAP.HQR").write_bytes(classic_hqr(entries))
            (root / "RESS.HQR").write_bytes(visual_ress_hqr())
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "holomap-export"

            response = viewer_server.export_catalog_asset("HOLOMAP.HQR:18", output_dir)
            frame = viewer_server.holomap_plan_image_frame(
                viewer_server.find_catalog_asset("HOLOMAP.HQR:18")
            )

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "holomap_plan_image_export_manifest.v0")
            self.assertEqual(manifest["source"]["catalog_asset_id"], "HOLOMAP.HQR:18")
            self.assertEqual(manifest["plan"]["paired_params_entry"], 19)
            self.assertEqual(manifest["plan"]["width"], 640)
            self.assertEqual(manifest["plan"]["height"], 480)
            self.assertEqual(frame["rgba"][:4], [0, 0, 0, 255])
            self.assertTrue((output_dir / manifest["files"]["png"]).exists())

    def test_viewer_server_exports_bkg_grid_composition_asset(self) -> None:
        header = struct.pack(
            "<HHHHHHIIII",
            1,
            2,
            3,
            4,
            1,
            1,
            4096,
            9000,
            512,
            256,
        )
        grm = bytes([1, 1, 1]) + struct.pack("<H", 0x0102)
        bll = struct.pack("<I", 4) + bytes([1, 1, 1, 2, 0x10]) + struct.pack("<H", 1)
        cube_records = bytearray(
            viewer.BKG_CUBE_MAP_RECORD_COUNT * viewer.BKG_CUBE_MAP_RECORD_BYTES
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        resource_entry(bkg_grid_payload()),
                        resource_entry(grm),
                        resource_entry(bll),
                        resource_entry(bkg_affgraph_payload()),
                        resource_entry(bytes(cube_records)),
                    ]
                )
            )
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "bkg-export"

            response = viewer_server.export_catalog_asset("LBA_BKG.HQR:1", output_dir)

            self.assertEqual(response["manifest"]["schema_version"], "bkg_grid_composition_manifest.v0")
            self.assertEqual(response["manifest"]["stats"]["cell_count"], 64 * 25 * 64)
            composition_path = output_dir / response["manifest"]["files"]["composition_json"]
            preview_path = output_dir / response["manifest"]["files"]["preview_png"]
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue(composition_path.exists())
            self.assertTrue(preview_path.exists())
            self.assertEqual(preview_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            composition = json.loads(composition_path.read_text(encoding="utf-8"))
            self.assertEqual(composition["flat_block_refs"][:25], [1] + [0] * 24)
            self.assertEqual(composition["occupied_block_cells"], 4096)
            self.assertEqual(response["manifest"]["stats"]["preview_drawn_cells"], 4096)

    def test_viewer_server_rejects_bkg_brick_graphic_export_without_route(self) -> None:
        header = struct.pack(
            "<HHHHHHIIII",
            1,
            2,
            3,
            4,
            1,
            1,
            4096,
            9000,
            512,
            256,
        )
        grm = bytes([1, 1, 1]) + struct.pack("<H", 0x0102)
        bll = struct.pack("<I", 4) + bytes([1, 1, 1, 2, 0x10]) + struct.pack("<H", 1)
        cube_records = bytearray(
            viewer.BKG_CUBE_MAP_RECORD_COUNT * viewer.BKG_CUBE_MAP_RECORD_BYTES
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        resource_entry(bkg_grid_payload()),
                        resource_entry(grm),
                        resource_entry(bll),
                        resource_entry(bkg_affgraph_payload()),
                        resource_entry(bytes(cube_records)),
                    ]
                )
            )
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            brick_asset = viewer_server.find_catalog_asset("LBA_BKG.HQR:4")
            self.assertEqual(brick_asset["stats"]["semantic_layout"], "bkg_brick_graphic")

            with self.assertRaisesRegex(server.Lm2Error, "catalog asset is not exportable"):
                viewer_server.export_catalog_asset("LBA_BKG.HQR:4", Path(temp_dir) / "brick-export")

    def test_viewer_server_rejects_non_exact_int_scene_background_links(self) -> None:
        invalid_backgrounds = {
            "missing_gri": {"resolved_bll_entry": 3},
            "missing_bll": {"resolved_gri_entry": 1},
            "string_gri": {"resolved_gri_entry": "1", "resolved_bll_entry": 3},
            "string_bll": {"resolved_gri_entry": 1, "resolved_bll_entry": "3"},
            "bool_gri": {"resolved_gri_entry": True, "resolved_bll_entry": 3},
            "bool_bll": {"resolved_gri_entry": 1, "resolved_bll_entry": True},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            scene_asset = {
                "id": "SCENE.HQR:1",
                "kind": "scene",
                "label": "Scene 0",
                "entry_type": "scene",
                "source": {"hqr": "SCENE.HQR", "entry_index": 1},
                "stats": {
                    "semantic_layout": "scene_runtime_layout_partial",
                    "reconnaissance": {"background": {}},
                },
            }
            viewer_server = server.ViewerServer(None, None)
            viewer_server.asset_root = root
            viewer_server.catalog = {"assets": [scene_asset]}

            for name, background in invalid_backgrounds.items():
                with self.subTest(name=name):
                    scene_asset["stats"]["reconnaissance"]["background"] = background
                    with self.assertRaisesRegex(server.Lm2Error, "catalog asset is not exportable"):
                        viewer_server.export_catalog_asset("SCENE.HQR:1", Path(temp_dir) / f"{name}-export")
                    with self.assertRaisesRegex(server.Lm2Error, "missing resolved background GRI/BLL"):
                        viewer_server.scene_background_variant_compositions(scene_asset)
                    with self.assertRaisesRegex(server.Lm2Error, "missing resolved background"):
                        viewer_server.render_scene_background_preview_frames(scene_asset)

    def test_viewer_server_rejects_scene_background_without_scene_runtime_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            scene_asset = {
                "id": "SCENE.HQR:1",
                "kind": "scene",
                "label": "Scene 0",
                "entry_type": "scene",
                "source": {"hqr": "SCENE.HQR", "entry_index": 1},
                "stats": {
                    "semantic_layout": "unknown",
                    "reconnaissance": {
                        "background": {
                            "resolved_gri_entry": 1,
                            "resolved_bll_entry": 3,
                        }
                    },
                },
            }
            viewer_server = server.ViewerServer(None, None)
            viewer_server.asset_root = root
            viewer_server.catalog = {"assets": [scene_asset]}

            with self.assertRaisesRegex(server.Lm2Error, "catalog asset is not exportable"):
                viewer_server.export_catalog_asset("SCENE.HQR:1", Path(temp_dir) / "scene-export")
            with self.assertRaisesRegex(server.Lm2Error, "not an exportable scene background"):
                viewer_server.export_scene_background_composition(scene_asset, Path(temp_dir) / "direct-export")

    def test_viewer_server_exports_scene_background_grm_variants(self) -> None:
        header = struct.pack(
            "<HHHHHHIIII",
            1,
            2,
            3,
            4,
            1,
            99,
            4096,
            9000,
            512,
            256,
        )
        grm = bytes([1, 1, 1]) + struct.pack("<H", 0x0101)
        block = (
            bytes([1, 2, 1])
            + bytes([0, 0x10])
            + struct.pack("<H", 1)
            + bytes([0, 0x20])
            + struct.pack("<H", 1)
        )
        bll = struct.pack("<I", 4) + block
        cube_records = bytearray(
            viewer.BKG_CUBE_MAP_RECORD_COUNT * viewer.BKG_CUBE_MAP_RECORD_BYTES
        )
        cube_records[0:2] = bytes([1, 0])
        grm_zone = scene_zone_record(info=(0, 0, 0, 0, 0, 0, 0, 0))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "SCENE.HQR").write_bytes(
                hqr([resource_entry(scene_payload([grm_zone]))])
            )
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        resource_entry(bkg_grid_payload()),
                        resource_entry(grm),
                        resource_entry(bll),
                        resource_entry(bkg_affgraph_payload()),
                        resource_entry(bytes(cube_records)),
                    ]
                )
            )
            viewer_server = server.ViewerServer(None, None)
            viewer_server.set_asset_root(root)
            output_dir = Path(temp_dir) / "scene-background-export"

            scene_asset = viewer_server.find_catalog_asset("SCENE.HQR:1")
            frames = viewer_server.render_scene_background_preview_frames(scene_asset)
            self.assertEqual([frame["variant"] for frame in frames], ["base", "grm_zone_000_on"])
            self.assertEqual(frames[1]["changed_cells"], 1)
            self.assertEqual(frames[1]["resolved_grm_entry"], 2)

            response = viewer_server.export_catalog_asset("SCENE.HQR:1", output_dir)

            manifest = response["manifest"]
            self.assertEqual(manifest["schema_version"], "scene_background_composition_manifest.v0")
            self.assertEqual(manifest["background"]["resolved_gri_entry"], 1)
            self.assertEqual(manifest["stats"]["variant_count"], 2)
            self.assertEqual(manifest["stats"]["exported_grm_on_variants"], 1)
            variants = manifest["files"]["variants"]
            self.assertEqual([variant["variant"] for variant in variants], ["base", "grm_zone_000_on"])
            base_path = output_dir / variants[0]["composition_json"]
            grm_path = output_dir / variants[1]["composition_json"]
            self.assertTrue((output_dir / variants[0]["preview_png"]).exists())
            self.assertTrue((output_dir / variants[1]["preview_png"]).exists())
            base = json.loads(base_path.read_text(encoding="utf-8"))
            grm_variant = json.loads(grm_path.read_text(encoding="utf-8"))
            self.assertEqual(base["flat_cell_slots_or_codes"][0], 0)
            self.assertEqual(grm_variant["flat_cell_slots_or_codes"][0], 1)
            self.assertEqual(grm_variant["grm_link"]["resolved_grm_entry"], 2)
            self.assertEqual(grm_variant["applied_grm_stats"]["changed_cells"], 1)
            self.assertEqual(variants[1]["changed_cells"], 1)

    def test_viewer_server_caches_scene_background_preview_frames(self) -> None:
        viewer_server = server.ViewerServer(None, None)
        scene_asset = {
            "id": "SCENE.HQR:1",
            "kind": "scene",
            "source": {"hqr": "SCENE.HQR", "entry_index": 1},
            "stats": {
                "semantic_layout": "scene_runtime_layout_partial",
                "reconnaissance": {
                    "background": {
                        "runtime_cube": 0,
                        "resolved_gri_entry": 1,
                        "resolved_bll_entry": 3,
                        "resolved_grm_entry": 2,
                    },
                    "grm_fragment_links": [],
                },
            },
        }
        variants = (
            {"flat_block_refs": [1], "flat_cell_slots_or_codes": [2]},
            [
                {
                    "variant": "base",
                    "label": "Base",
                    "block_refs": [1],
                    "slots": [2],
                    "source_provenance": "test preview",
                }
            ],
        )

        with (
            patch.object(viewer_server, "scene_background_variant_compositions", return_value=variants)
            as variant_compositions,
            patch.object(
                viewer_server,
                "render_bkg_composition_preview",
                return_value={"format": "bkg_grid_preview", "rgba": [1, 2, 3, 4]},
            ) as render_preview,
        ):
            first = viewer_server.render_scene_background_preview_frames(scene_asset)
            first[0]["variant"] = "mutated-by-caller"
            second = viewer_server.render_scene_background_preview_frames(scene_asset)

        self.assertEqual(variant_compositions.call_count, 1)
        self.assertEqual(render_preview.call_count, 1)
        self.assertEqual(second[0]["variant"], "base")


if __name__ == "__main__":
    unittest.main()
