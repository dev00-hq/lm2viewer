#!/usr/bin/env python3
"""Read classic Little Big Adventure HQR resource archives."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


class HqrError(ValueError):
    pass


@dataclass(frozen=True)
class HqrEntry:
    index: int
    offset: int
    byte_length: int
    sha256: str


@dataclass(frozen=True)
class ResourceHeader:
    size_file: int
    compressed_size_file: int
    compress_method: int


RESOURCE_HEADER_SIZE = 10


def parse_table(data: bytes) -> tuple[HqrEntry, ...]:
    if len(data) < 8:
        raise HqrError("invalid HQR: archive is smaller than the table header")
    table_end = struct.unpack_from("<I", data, 0)[0]
    if table_end < 8 or table_end % 4 != 0 or table_end > len(data):
        raise HqrError(f"invalid HQR table header: 0x{table_end:x}")

    entry_count = table_end // 4 - 1
    offsets = [struct.unpack_from("<I", data, 4 + index * 4)[0] for index in range(entry_count)]
    for offset in offsets:
        if offset != 0 and (offset < table_end or offset > len(data)):
            raise HqrError(f"invalid HQR entry offset: 0x{offset:x}")

    entries: list[HqrEntry] = []
    for index, offset in enumerate(offsets, start=1):
        if offset == 0:
            entries.append(HqrEntry(index, 0, 0, hashlib.sha256(b"").hexdigest()))
            continue
        next_offset = len(data)
        for candidate in offsets[index:]:
            if candidate > offset:
                next_offset = min(next_offset, candidate)
        if next_offset < offset:
            raise HqrError(f"invalid HQR entry range at index {index}")
        payload = data[offset:next_offset]
        entries.append(HqrEntry(index, offset, len(payload), hashlib.sha256(payload).hexdigest()))
    return tuple(entries)


def parse_classic_table(data: bytes) -> tuple[HqrEntry, ...]:
    if len(data) < 4:
        raise HqrError("invalid HQR: archive is smaller than the classic table header")
    table_end = struct.unpack_from("<I", data, 0)[0]
    if table_end < 4 or table_end % 4 != 0 or table_end > len(data):
        raise HqrError(f"invalid classic HQR table header: 0x{table_end:x}")

    entry_count = table_end // 4
    offsets = [struct.unpack_from("<I", data, index * 4)[0] for index in range(entry_count)]
    for offset in offsets:
        if offset != 0 and (offset < table_end or offset > len(data)):
            raise HqrError(f"invalid classic HQR entry offset: 0x{offset:x}")

    entries: list[HqrEntry] = []
    for index, offset in enumerate(offsets):
        if offset == 0:
            entries.append(HqrEntry(index, 0, 0, hashlib.sha256(b"").hexdigest()))
            continue
        next_offset = len(data)
        for candidate in offsets[index + 1 :]:
            if candidate > offset:
                next_offset = min(next_offset, candidate)
        if next_offset < offset:
            raise HqrError(f"invalid classic HQR entry range at index {index}")
        payload = data[offset:next_offset]
        entries.append(HqrEntry(index, offset, len(payload), hashlib.sha256(payload).hexdigest()))
    return tuple(entries)


def read_entry(data: bytes, entry: HqrEntry) -> bytes:
    if entry.offset == 0 or entry.byte_length == 0:
        return b""
    return data[entry.offset : entry.offset + entry.byte_length]


def parse_resource_header(raw_entry: bytes) -> ResourceHeader:
    if len(raw_entry) < RESOURCE_HEADER_SIZE:
        raise HqrError("resource entry is too small for a compression header")
    size_file, compressed_size_file, compress_method = struct.unpack_from("<IIH", raw_entry, 0)
    return ResourceHeader(size_file, compressed_size_file, compress_method)


def decode_resource_entry(raw_entry: bytes) -> tuple[bytes, ResourceHeader]:
    header = parse_resource_header(raw_entry)
    payload = raw_entry[RESOURCE_HEADER_SIZE:]

    if header.compress_method == 0:
        if len(payload) < header.size_file:
            raise HqrError("resource payload is shorter than its advertised size")
        return payload[: header.size_file], header
    if header.compress_method in (1, 2):
        if len(payload) < header.compressed_size_file:
            raise HqrError("compressed resource payload is truncated")
        return (
            expand_lz(payload[: header.compressed_size_file], header.size_file, header.compress_method + 1),
            header,
        )
    raise HqrError(f"unsupported HQR compression method {header.compress_method}")


def expand_lz(source: bytes, decompressed_size: int, min_block_size: int) -> bytes:
    output = bytearray(decompressed_size)
    src_index = 0
    dst_index = 0

    while dst_index < decompressed_size:
        if src_index >= len(source):
            raise HqrError("compressed resource payload is truncated")
        info = source[src_index]
        src_index += 1

        for _ in range(8):
            if dst_index >= decompressed_size:
                break
            is_literal = (info & 1) == 1
            info >>= 1

            if is_literal:
                if src_index >= len(source):
                    raise HqrError("compressed resource literal is truncated")
                output[dst_index] = source[src_index]
                src_index += 1
                dst_index += 1
                continue

            if src_index + 1 >= len(source):
                raise HqrError("compressed resource back-reference is truncated")
            token = struct.unpack_from("<H", source, src_index)[0]
            src_index += 2
            copy_len = (token & 0x000F) + min_block_size
            backwards = (token >> 4) + 1
            if backwards > dst_index:
                raise HqrError("compressed resource has an invalid back-reference")
            copy_src = dst_index - backwards
            for _ in range(copy_len):
                if dst_index >= decompressed_size:
                    break
                output[dst_index] = output[copy_src]
                dst_index += 1
                copy_src += 1

    return bytes(output)


def read_archive(path: Path) -> tuple[bytes, tuple[HqrEntry, ...]]:
    data = path.read_bytes()
    return data, parse_table(data)
