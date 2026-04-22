import json
import struct
import tempfile
import unittest
from pathlib import Path

from lba2_lm2_viewer import viewer
from lba2_lm2_viewer.contracts import (
    EvidenceReference,
    SCHEMA_VERSION,
    build_model_contract,
    contract_to_json,
    export_catalog_asset_contract,
    read_model_contract,
    write_model_contract,
)


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "synthetic_model_contract_v0.json"


def synthetic_model() -> viewer.Lm2Model:
    header = viewer.Lm2Header(
        flags=1 | (1 << 8) | (1 << 10),
        bounds=(-1, 10, -2, 20, -3, 30),
        bones_count=2,
        bones_offset=0x60,
        vertices_count=3,
        vertices_offset=0x70,
        normals_count=0,
        normals_offset=0,
        unknown_count=1,
        unknown_offset=32,
        polygons_size=0,
        polygons_offset=0,
        lines_count=1,
        lines_offset=0xA0,
        spheres_count=1,
        spheres_offset=0xA8,
        uv_groups_count=1,
        uv_groups_offset=0xB0,
    )
    return viewer.Lm2Model(
        header=header,
        bones=(
            viewer.Bone(parent=0, vertex=0, unknown_1=7, unknown_2=8),
            viewer.Bone(parent=0, vertex=1, unknown_1=9, unknown_2=10),
        ),
        vertices=(
            viewer.Vertex(x=0.0, y=0.0, z=0.0, bone=0),
            viewer.Vertex(x=10.0, y=0.0, z=0.0, bone=1),
            viewer.Vertex(x=0.0, y=20.0, z=0.0, bone=1),
        ),
        normals=(),
        polygons=(
            viewer.Polygon(
                render_type=8,
                vertices=(0, 1, 2),
                color=12,
                color_word=12,
                palette_index=12,
                intensity=0,
                has_texture=True,
                has_extra=False,
                has_transparency=True,
                texture=0,
                uv=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
            ),
        ),
        lines=(
            viewer.LinePrimitive(
                color=2,
                color_word=2,
                palette_index=2,
                vertex_1=0,
                vertex_2=1,
                unknown=99,
            ),
        ),
        spheres=(
            viewer.SpherePrimitive(
                color=3,
                color_word=3,
                palette_index=3,
                vertex=2,
                size=4,
                unknown=77,
            ),
        ),
        uv_groups=(viewer.UvGroup(x=1, y=2, w=4, h=5),),
    )


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


def minimal_lm2() -> bytes:
    bones_offset = 0x60
    vertices_offset = 0x68
    polygons_offset = 0x80
    uv_groups_offset = 0xA0
    values = (
        1,
        bones_offset,
        3,
        vertices_offset,
        0,
        polygons_offset,
        0,
        polygons_offset,
        0x20,
        polygons_offset,
        0,
        uv_groups_offset,
        0,
        uv_groups_offset,
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
    polygon = (
        struct.pack("<HHH", 0, 1, 2)
        + struct.pack("<H", 0)
        + struct.pack("<H", 12)
        + struct.pack("<h", 0)
        + bytes((0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 4))
    )
    uv_group = bytes((0, 0, 4, 4))
    return header + bone + vertices + section_header + polygon + uv_group


class ModelContractTests(unittest.TestCase):
    def test_build_model_contract_matches_synthetic_fixture(self) -> None:
        contract = build_model_contract(
            model=synthetic_model(),
            source={
                "catalog_asset_id": "SYNTH.HQR:1",
                "catalog_label": "Synthetic test model",
                "archive": "SYNTH.HQR",
                "entry_index": 1,
                "classic_index": 0,
                "source_mode": "synthetic",
                "decoded_bytes": 96,
                "decoded_sha256": "synthetic-sha256",
                "archive_raw_bytes": 106,
                "archive_raw_sha256": "synthetic-raw-sha256",
            },
            evidence=[
                EvidenceReference(
                    kind="synthetic_fixture",
                    path="tests/fixtures/contracts/synthetic_model_contract_v0.json",
                    note="Synthetic contract fixture with no game-derived data.",
                )
            ],
        )

        self.assertEqual(contract.schema_version, SCHEMA_VERSION)
        self.assertEqual(
            json.loads(contract_to_json(contract)),
            json.loads(FIXTURE.read_text(encoding="utf-8")),
        )

    def test_write_and_read_model_contract_round_trips_msgspec_type(self) -> None:
        contract = build_model_contract(model=synthetic_model(), source={})

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract.json"
            write_model_contract(contract, path)
            loaded = read_model_contract(path)

        self.assertEqual(loaded.schema_version, SCHEMA_VERSION)
        self.assertEqual(loaded.geometry.counts.vertices, 3)
        self.assertEqual(loaded.render.uv_groups[0].polygon_indices, [0])

    def test_read_model_contract_rejects_schema_drift(self) -> None:
        contract = json.loads(contract_to_json(build_model_contract(model=synthetic_model(), source={})))
        contract["schema_version"] = "lm2_model_contract.v999"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_model_contract(path)

    def test_read_model_contract_rejects_unknown_fields(self) -> None:
        contract = json.loads(contract_to_json(build_model_contract(model=synthetic_model(), source={})))
        contract["unexpected"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(Exception):
                read_model_contract(path)

    def test_read_model_contract_rejects_nested_unknown_fields(self) -> None:
        contract = json.loads(contract_to_json(build_model_contract(model=synthetic_model(), source={})))
        contract["source"]["unexpected"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(Exception):
                read_model_contract(path)

    def test_export_catalog_asset_contract_writes_plain_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "assets"
            root.mkdir()
            (root / "BODY.HQR").write_bytes(classic_hqr([resource_entry(minimal_lm2())]))
            output_path = Path(temp_dir) / "body-001.contract.json"

            contract = export_catalog_asset_contract(
                asset_root=root,
                asset_id="BODY.HQR:1",
                output_path=output_path,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(contract.source.asset_id, "BODY.HQR:1")
            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            self.assertEqual(payload["source"]["archive"], "BODY.HQR")
            self.assertEqual(payload["source"]["archive_offset"], 4)
            self.assertEqual(payload["source"]["resource_header"]["size_file"], len(minimal_lm2()))
            self.assertEqual(payload["geometry"]["decoded_unit"], "viewer_world")
            self.assertEqual(payload["geometry"]["decoded_bounds"]["x"], [0.0, 1.5])
            self.assertEqual(payload["geometry"]["header_raw_unit"], "lm2_header_integer")
            self.assertEqual(payload["geometry"]["header_raw_bounds"]["x"], [0, 10])
            self.assertEqual(payload["render"]["materials"][0]["kind"], "texture")
            self.assertEqual(payload["render"]["uv_groups"][0]["polygon_indices"], [0])

    def test_contract_subcommand_detection_owns_contract_command(self) -> None:
        self.assertTrue(viewer.is_contract_subcommand(["contract"]))
        self.assertTrue(viewer.is_contract_subcommand(["contract", "--no-browser"]))
        self.assertTrue(viewer.is_contract_subcommand(["contract", "--help"]))
        self.assertTrue(
            viewer.is_contract_subcommand(
                ["contract", "--asset-root", "assets", "--asset", "BODY.HQR:1", "--out", "out.json"]
            )
        )


if __name__ == "__main__":
    unittest.main()
