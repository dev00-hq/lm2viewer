import json
import struct
import tempfile
import unittest
from pathlib import Path

from lba2_lm2_viewer import viewer
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
            self.assertIn("missing LBA2 palette archive", manifest["warnings"][0])
            self.assertTrue((output_dir / "BODY.HQR_1.obj").exists())

    def test_viewer_server_exports_loaded_catalog_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "BODY.HQR").write_bytes(
                classic_hqr([resource_entry(textured_triangle_lm2())])
            )
            server = viewer.ViewerServer(None, None)
            server.set_asset_root(root)
            output_dir = Path(temp_dir) / "server-export"

            response = server.export_catalog_asset("BODY.HQR:1", output_dir)

            self.assertEqual(response["output_dir"], str(output_dir.resolve()))
            self.assertEqual(
                response["manifest"]["source"]["catalog_asset_id"], "BODY.HQR:1"
            )
            self.assertTrue((output_dir / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
