import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

import lba_hqr
import viewer


def resource_entry(payload: bytes, compress_method: int = 0, compressed_size: int | None = None) -> bytes:
    if compressed_size is None:
        compressed_size = len(payload)
    return struct.pack("<IIH", len(payload), compressed_size, compress_method) + payload


def classic_hqr(entries: list[bytes]) -> bytes:
    table_end = len(entries) * 4
    offsets: list[int] = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return struct.pack("<I", table_end) + b"".join(struct.pack("<I", offset) for offset in offsets[1:]) + payloads


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


def lm2_header(
    *,
    bones_count: int = 1,
    bones_offset: int = 0x60,
    vertices_count: int = 1,
    vertices_offset: int = 0x68,
    normals_count: int = 0,
    normals_offset: int = 0x70,
    unknown_count: int = 0,
    unknown_offset: int = 0x70,
    polygons_size: int = 0,
    polygons_offset: int = 0x70,
    lines_count: int = 0,
    lines_offset: int = 0x70,
    spheres_count: int = 0,
    spheres_offset: int = 0x70,
    uv_groups_count: int = 0,
    uv_groups_offset: int = 0x70,
) -> bytes:
    bounds = (0, 0, 0, 0, 0, 0)
    values = (
        bones_count,
        bones_offset,
        vertices_count,
        vertices_offset,
        normals_count,
        normals_offset,
        unknown_count,
        unknown_offset,
        polygons_size,
        polygons_offset,
        lines_count,
        lines_offset,
        spheres_count,
        spheres_offset,
        uv_groups_count,
        uv_groups_offset,
    )
    return struct.pack("<ii6i16I", 1, 0, *bounds, *values)


def minimal_lm2() -> bytes:
    header = lm2_header()
    bone = struct.pack("<HHHH", 1001, 0, 0, 0)
    vertex = struct.pack("<hhhH", 10, 20, -30, 0)
    return header + bone + vertex


class HqrParserTests(unittest.TestCase):
    def test_parse_table_reports_one_based_entries_and_hashes_payloads(self) -> None:
        payload = resource_entry(b"model-bytes")
        archive = hqr([payload])

        entries = lba_hqr.parse_table(archive)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].index, 1)
        self.assertEqual(entries[0].offset, 8)
        self.assertEqual(entries[0].byte_length, len(payload))
        self.assertEqual(entries[0].sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(lba_hqr.read_entry(archive, entries[0]), payload)

    def test_decode_resource_entry_returns_advertised_uncompressed_payload(self) -> None:
        raw = struct.pack("<IIH", 4, 99, 0) + b"data-padding"

        decoded, header = lba_hqr.decode_resource_entry(raw)

        self.assertEqual(decoded, b"data")
        self.assertEqual(header.size_file, 4)
        self.assertEqual(header.compressed_size_file, 99)
        self.assertEqual(header.compress_method, 0)

    def test_decode_resource_entry_expands_method_one_lz_payload(self) -> None:
        compressed = b"\x07ABC" + struct.pack("<H", 0x21)
        raw = struct.pack("<IIH", 6, len(compressed), 1) + compressed

        decoded, header = lba_hqr.decode_resource_entry(raw)

        self.assertEqual(decoded, b"ABCABC")
        self.assertEqual(header.compress_method, 1)

    def test_expand_lz_rejects_invalid_back_reference(self) -> None:
        with self.assertRaisesRegex(lba_hqr.HqrError, "invalid back-reference"):
            lba_hqr.expand_lz(b"\x00\x00\x00", decompressed_size=2, min_block_size=2)

    def test_decode_resource_entry_rejects_truncated_compressed_payload(self) -> None:
        raw = struct.pack("<IIH", 4, 8, 1) + b"\xffabc"

        with self.assertRaisesRegex(lba_hqr.HqrError, "truncated"):
            lba_hqr.decode_resource_entry(raw)


class Lm2ParserFailureTests(unittest.TestCase):
    def test_parse_lm2_rejects_too_small_header(self) -> None:
        with self.assertRaisesRegex(viewer.Lm2Error, "too small"):
            viewer.parse_lm2(b"\x00" * 4)

    def test_parse_lm2_rejects_section_offset_past_file_end(self) -> None:
        data = lm2_header(vertices_offset=0x100) + struct.pack("<HHHH", 1001, 0, 0, 0)

        with self.assertRaisesRegex(viewer.Lm2Error, "section offset 0x100 exceeds"):
            viewer.parse_lm2(data)

    def test_parse_lm2_rejects_vertex_referencing_missing_bone(self) -> None:
        data = lm2_header(
            bones_count=0,
            bones_offset=0x60,
            vertices_offset=0x60,
            normals_offset=0x68,
            unknown_offset=0x68,
            polygons_offset=0x68,
            lines_offset=0x68,
            spheres_offset=0x68,
            uv_groups_offset=0x68,
        ) + struct.pack("<hhhH", 0, 0, 0, 0)

        with self.assertRaisesRegex(viewer.Lm2Error, "vertex 0 references missing bone 0"):
            viewer.parse_lm2(data)

    def test_parse_lm2_rejects_line_referencing_missing_vertex(self) -> None:
        data = (
            lm2_header(
                lines_count=1,
                lines_offset=0x70,
                spheres_offset=0x78,
                uv_groups_offset=0x78,
            )
            + struct.pack("<HHHH", 1001, 0, 0, 0)
            + struct.pack("<hhhH", 0, 0, 0, 0)
            + struct.pack("<HHHH", 0, 7, 0, 2)
        )

        with self.assertRaisesRegex(viewer.Lm2Error, "line 0 references missing vertex"):
            viewer.parse_lm2(data)


class SelectedFileCatalogIndexingTests(unittest.TestCase):
    def test_selected_body_hqr_uses_one_based_catalog_index_and_classic_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            body_path = root / "BODY.HQR"
            payload = minimal_lm2()
            body_path.write_bytes(classic_hqr([resource_entry(payload)]))

            catalog = viewer.build_catalog(root, selected_files=[body_path])

            self.assertEqual(catalog["source_mode"], "files")
            self.assertEqual(catalog["selected_files"], ["BODY.HQR"])
            self.assertEqual(catalog["hqr_files"][0]["indexing"], "classic")
            self.assertEqual(catalog["summary"]["models"], 1)
            asset = catalog["assets"][0]
            self.assertEqual(asset["id"], "BODY.HQR:1")
            self.assertEqual(asset["source"]["entry_index"], 1)
            self.assertEqual(asset["source"]["classic_index"], 0)

            decoded, resource = viewer.read_hqr_payload(root, asset["source"])
            self.assertEqual(decoded, payload)
            self.assertEqual(resource["compress_method"], 0)

    def test_selected_regular_hqr_keeps_one_based_entry_index_without_classic_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            models_path = root / "MODELS.HQR"
            models_path.write_bytes(hqr([resource_entry(minimal_lm2())]))

            catalog = viewer.build_catalog(root, selected_files=[models_path])

            self.assertEqual(catalog["source_mode"], "files")
            self.assertEqual(catalog["selected_files"], ["MODELS.HQR"])
            self.assertEqual(catalog["hqr_files"][0]["indexing"], "one-based")
            asset = catalog["assets"][0]
            self.assertEqual(asset["id"], "MODELS.HQR:1")
            self.assertEqual(asset["source"]["entry_index"], 1)
            self.assertNotIn("classic_index", asset["source"])

    def test_normalize_selected_hqr_files_deduplicates_and_sorts_under_common_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subdir = root / "sub"
            subdir.mkdir()
            b_path = subdir / "B.HQR"
            a_path = root / "A.HQR"
            b_path.write_bytes(hqr([b"raw"]))
            a_path.write_bytes(hqr([b"raw"]))

            normalized = viewer.normalize_hqr_file_paths([b_path, a_path, b_path])

            self.assertEqual([path.relative_to(root).as_posix() for path in normalized], ["A.HQR", "sub/B.HQR"])


if __name__ == "__main__":
    unittest.main()
