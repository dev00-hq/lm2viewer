import json
import struct
import tempfile
import threading
import unittest
import urllib.request
import hashlib
from contextlib import redirect_stdout
from dataclasses import replace
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path

from lba2_lm2_viewer import animation
from lba2_lm2_viewer import scene_scripts
from lba2_lm2_viewer import server
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
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
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


def classic_hqr(entries: list[bytes]) -> bytes:
    table_end = len(entries) * 4
    offsets: list[int] = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return b"".join(struct.pack("<I", offset) for offset in offsets) + payloads


def minimal_lm2() -> bytes:
    header = struct.pack(
        "<ii6i16I",
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        0x60,
        1,
        0x68,
        0,
        0x70,
        0,
        0x70,
        0,
        0x70,
        0,
        0x70,
        0,
        0x70,
        0,
        0x70,
    )
    bone = struct.pack("<HHHH", 1001, 0, 0, 0)
    vertex = struct.pack("<hhhH", 10, 20, -30, 0)
    return header + bone + vertex


def file3d_record(commands: bytes) -> bytes:
    return struct.pack("<I", 4) + commands + b"\xff"


def file3d_anim(generic_id: int, animation_index: int) -> bytes:
    return b"\x03" + struct.pack("<H", generic_id) + b"\x04" + struct.pack("<h", animation_index) + b"\x00"


def file3d_body(generic_id: int, body_index: int) -> bytes:
    return b"\x01" + bytes([generic_id]) + b"\x04" + struct.pack("<h", body_index) + b"\x00"


def lsp_sprite_payload(width: int = 4, height: int = 2) -> bytes:
    if width != 4 or height != 2:
        raise ValueError("test helper currently emits a fixed 4x2 sprite")
    return (
        b"\x00" * 8
        + bytes([4, 2, 1, 2])
        + bytes([3, 0x00, 0x81, 7, 0x40, 8])
        + bytes([1, 0xC3, 1, 2, 0, 3])
    )


def raw_sprite_payload(width: int = 4, height: int = 2) -> bytes:
    pixels = bytes((index % 8 for index in range(width * height)))
    return (
        b"\x08\x00\x00\x00"
        + struct.pack("<I", len(pixels))
        + bytes([width, height, 0xFE, 3])
        + pixels
    )


def bkg_affgraph_payload(width: int = 4, height: int = 2) -> bytes:
    if width != 4 or height != 2:
        raise ValueError("test helper currently emits a fixed 4x2 brick graph")
    return (
        bytes([4, 2, 1, 0xFE])
        + bytes([3, 0x00, 0x81, 7, 0x40, 8])
        + bytes([1, 0x43, 1, 2, 0, 3])
    )


def bkg_grid_payload(column_word: int = 0x0001) -> bytes:
    column_stream = bytes([2, 0x80]) + struct.pack("<H", column_word) + bytes([0x17])
    offsets = struct.pack(
        f"<{viewer.BKG_GRID_COLUMN_COUNT}H",
        *([viewer.BKG_GRID_OFFSET_TABLE_BYTES] * viewer.BKG_GRID_COLUMN_COUNT),
    )
    used_blocks = bytes([0x40]) + (b"\x00" * 31)
    return bytes([0, 0]) + used_blocks + offsets + column_stream


def scene_payload(
    *,
    island: int = 2,
    cube_x: int = 11,
    cube_y: int = 12,
    start: tuple[int, int, int] = (100, 200, 300),
    hero_track_script: bytes = b"",
    hero_life_script: bytes = b"",
    object_count: int = 1,
    object_records: list[bytes] | None = None,
    zone_count: int = 0,
    zone_records: list[bytes] | None = None,
    track_count: int = 0,
    track_records: list[bytes] | None = None,
    patch_count: int = 0,
    patch_records: list[bytes] | None = None,
) -> bytes:
    if object_records is not None:
        object_count = len(object_records) + 1
    if zone_records is not None:
        zone_count = len(zone_records)
    if track_records is not None:
        track_count = len(track_records)
    if patch_records is not None:
        patch_count = len(patch_records)
    payload = bytearray()
    payload.extend(struct.pack("<bbbbbbb", island, cube_x, cube_y, 3, 0, 1, 9))
    payload.extend(struct.pack("<hh", 45, 90))
    for sample in range(4):
        payload.extend(struct.pack("<hhhhh", sample, 1, 2, 22050, 64))
    payload.extend(struct.pack("<hhb", 5, 6, 7))
    payload.extend(struct.pack("<hhh", *start))
    payload.extend(struct.pack("<h", len(hero_track_script)))
    payload.extend(hero_track_script)
    payload.extend(struct.pack("<h", len(hero_life_script)))
    payload.extend(hero_life_script)
    payload.extend(struct.pack("<h", object_count))
    for record in object_records or []:
        payload.extend(record)
    payload.extend(struct.pack("<I", 0x12345678))
    payload.extend(struct.pack("<h", zone_count))
    for record in zone_records or [b"\x00" * viewer.SCENE_ZONE_RECORD_BYTES] * zone_count:
        payload.extend(record)
    payload.extend(struct.pack("<h", track_count))
    for record in track_records or [b"\x00" * viewer.SCENE_TRACK_RECORD_BYTES] * track_count:
        payload.extend(record)
    payload.extend(struct.pack("<I", patch_count))
    for record in patch_records or []:
        payload.extend(record)
    return bytes(payload)


def scene_zone_record(
    *,
    start: tuple[int, int, int] = (0, 0, 0),
    end: tuple[int, int, int] = (10, 20, 30),
    info: tuple[int, int, int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0, 0, 0),
    zone_type: int = 0,
    value: int = 0,
) -> bytes:
    return (
        struct.pack("<iii", *start)
        + struct.pack("<iii", *end)
        + struct.pack("<iiiiiiii", *info)
        + struct.pack("<hh", zone_type, value)
    )


def scene_track_record(position: tuple[int, int, int] = (1, 2, 3)) -> bytes:
    return struct.pack("<iii", *position)


def scene_patch_record(size: int, target_offset: int) -> bytes:
    return struct.pack("<hh", size, target_offset)


def scene_object_record(
    *,
    flags: int = 0,
    file3d_index: int = -1,
    gen_body: int = 0,
    gen_anim: int = 0,
    sprite: int = 0,
    anim3ds_animation_number: int = 0,
    anim3ds_size_s_hit: int = 0,
    position: tuple[int, int, int] = (0, 0, 0),
    hit_force: int = 0,
    option_flags: int = 0,
    beta: int = 0,
    srot: int = 0,
    move: int = 0,
    info: tuple[int, int, int, int] = (0, 0, 0, 0),
    bonus_count: int = 0,
    color: int = 0,
    armor: int = 0,
    life_points: int = 1,
    track_script: bytes = b"",
    life_script: bytes = b"",
) -> bytes:
    payload = bytearray()
    payload.extend(struct.pack("<Ihbhh", flags, file3d_index, gen_body, gen_anim, sprite))
    payload.extend(struct.pack("<hhh", *position))
    payload.extend(struct.pack("<bhhhb", hit_force, option_flags, beta, srot, move))
    payload.extend(struct.pack("<hhhh", *info))
    payload.extend(struct.pack("<hb", bonus_count, color))
    if flags & viewer.ANIM_3DS_FLAG:
        payload.extend(struct.pack("<Ih", anim3ds_animation_number, anim3ds_size_s_hit))
    payload.extend(struct.pack("<bb", armor, life_points))
    payload.extend(struct.pack("<h", len(track_script)))
    payload.extend(track_script)
    payload.extend(struct.pack("<h", len(life_script)))
    payload.extend(life_script)
    return bytes(payload)


def sprite_zv_payload(record_count: int, selected_index: int, values: tuple[int, int, int, int, int, int, int, int]) -> bytes:
    records = [struct.pack("<hhhhhhhh", 0, 0, 0, 0, 0, 0, 0, 0) for _ in range(record_count)]
    records[selected_index] = struct.pack("<hhhhhhhh", *values)
    return b"".join(records)


class AnimationParserTests(unittest.TestCase):
    def test_life_script_analyzer_handles_distance3d_condition_operand(self) -> None:
        script = (
            bytes([12, 22, 11, 2])
            + struct.pack("<h", 1700)
            + struct.pack("<h", 674)
            + bytes([0])
        )

        analysis = scene_scripts.analyze_life_script(script)

        self.assertEqual(analysis["status"], "decoded")
        self.assertEqual(analysis["instruction_count"], 2)
        self.assertEqual(analysis["first_instructions"][0]["mnemonic"], "LM_IF")
        self.assertEqual(analysis["first_instructions"][0]["byte_length"], 8)
        self.assertEqual(analysis["first_instructions"][0]["behavior_category"], "control_flow")
        self.assertEqual(
            analysis["first_instructions"][0]["operand_semantics"],
            {
                "function_id": 22,
                "function": "LF_DISTANCE_3D",
                "return_type": "s16",
                "object_id": 11,
                "comparator": "LT_LESS",
                "compare_value": 1700,
                "branch_offset": 674,
            },
        )
        self.assertEqual(analysis["references"]["object"], [11])
        self.assertEqual(analysis["references"]["script_offset"], [674])
        self.assertIn({"category": "control_flow", "count": 2}, analysis["behavior_categories"])
        self.assertEqual(
            analysis["condition_functions"],
            [
                {
                    "function": "LF_DISTANCE_3D",
                    "function_id": 22,
                    "count": 1,
                    "return_type": "s16",
                    "opcodes": ["LM_IF"],
                }
            ],
        )
        self.assertEqual(
            analysis["condition_comparators"],
            [
                {
                    "comparator": "LT_LESS",
                    "count": 1,
                    "opcodes": ["LM_IF"],
                    "functions": ["LF_DISTANCE_3D"],
                }
            ],
        )

    def test_scene_script_analyzer_resolves_same_script_control_flow_targets(self) -> None:
        track = bytes([9, 7, 10]) + struct.pack("<h", 0) + bytes([0])
        life = bytes([12, 14, 0, 1]) + struct.pack("<h", 6) + bytes([0])

        track_analysis = scene_scripts.analyze_track_script(track)
        life_analysis = scene_scripts.analyze_life_script(life)

        self.assertEqual(
            track_analysis["label_definitions"],
            [{"label": 7, "offset": 0, "opcode": "TM_LABEL"}],
        )
        self.assertEqual(
            track_analysis["control_flow_links"],
            [
                {
                    "source_offset": 2,
                    "source_opcode": "TM_GOTO",
                    "source_behavior_category": "control_flow",
                    "target_field": "target_offset",
                    "target_script_kind": "track",
                    "target_offset": 0,
                    "target_found": True,
                    "target_status": "instruction_start",
                    "target_decoded_bytes": 6,
                    "target_script_bytes": 6,
                    "target_opcode": "TM_LABEL",
                    "target_behavior_category": "control_flow",
                }
            ],
        )
        self.assertEqual(
            life_analysis["control_flow_links"],
            [
                {
                    "source_offset": 0,
                    "source_opcode": "LM_IF",
                    "source_behavior_category": "control_flow",
                    "target_field": "branch_offset",
                    "target_script_kind": "life",
                    "target_offset": 6,
                    "target_found": True,
                    "target_status": "instruction_start",
                    "target_decoded_bytes": 7,
                    "target_script_bytes": 7,
                    "target_opcode": "LM_END",
                    "target_behavior_category": "control_flow",
                }
            ],
        )

    def test_scene_script_control_flow_targets_explain_after_decoded_prefix(self) -> None:
        life = bytes([15]) + struct.pack("<h", 3) + bytes([115, 0, 0, 0])

        analysis = scene_scripts.analyze_life_script(life)
        link = analysis["control_flow_links"][0]

        self.assertEqual(analysis["status"], "missing_switch_context")
        self.assertEqual(analysis["decoded_bytes"], 3)
        self.assertEqual(link["target_found"], False)
        self.assertEqual(link["target_status"], "after_decoded_prefix")
        self.assertEqual(link["target_decoded_bytes"], 3)
        self.assertEqual(link["target_script_bytes"], 7)
        self.assertEqual(link["target_previous_decoded_offset"], 0)
        self.assertEqual(link["target_previous_decoded_opcode"], "LM_ELSE")

    def test_life_script_analyzer_skips_byte_islands_before_known_targets(self) -> None:
        life = bytes([15]) + struct.pack("<h", 5) + bytes([250, 251, 0])

        analysis = scene_scripts.analyze_life_script(life)

        self.assertEqual(analysis["status"], "decoded")
        self.assertEqual(analysis["decoded_bytes"], len(life))
        self.assertEqual(analysis["unreachable_bytes"], 2)
        self.assertEqual(analysis["unreachable_byte_ranges"][0]["offset"], 3)
        self.assertEqual(analysis["unreachable_byte_ranges"][0]["length"], 2)
        self.assertEqual(analysis["control_flow_links"][0]["target_offset"], 5)
        self.assertTrue(analysis["control_flow_links"][0]["target_found"])

    def test_scene_script_behavior_classifier_covers_known_opcodes(self) -> None:
        missing_track = [
            opcode
            for opcode in scene_scripts.TRACK_OPERAND_LAYOUTS
            if scene_scripts.script_behavior_category("track", opcode) == "unknown_behavior"
        ]
        missing_life = [
            opcode
            for opcode in scene_scripts.LIFE_OPERAND_LAYOUTS
            if scene_scripts.script_behavior_category("life", opcode) == "unknown_behavior"
        ]

        self.assertEqual(missing_track, [])
        self.assertEqual(missing_life, [])

    def test_scene_script_operand_semantics_decode_port_relevant_fields(self) -> None:
        track = (
            bytes([2, 7, 3])
            + struct.pack("<H", 4)
            + bytes([4, 9, 38])
            + struct.pack("<h", 127)
            + bytes([45, 12, 48, 7, 0])
        )
        life = (
            bytes([17, 7, 19])
            + struct.pack("<H", 4)
            + bytes([21, 3, 1, 77, 5, 0, 84])
            + struct.pack("<h", 127)
            + bytes([0])
        )

        track_analysis = scene_scripts.analyze_track_script(track)
        life_analysis = scene_scripts.analyze_life_script(life)
        track_instructions = track_analysis["first_instructions"]
        life_instructions = life_analysis["first_instructions"]

        self.assertEqual(track_instructions[0]["operand_semantics"], {"body_id": 7})
        self.assertEqual(track_instructions[1]["operand_semantics"], {"animation_id": 4})
        self.assertEqual(track_instructions[2]["operand_semantics"], {"waypoint_id": 9})
        self.assertEqual(track_instructions[3]["operand_semantics"], {"sprite_id": 127})
        self.assertEqual(track_instructions[4]["operand_semantics"], {"frames_per_second": 12})
        self.assertEqual(track_instructions[5]["operand_semantics"], {"frame": 7})
        self.assertEqual(track_analysis["references"]["waypoint"], [9])
        self.assertNotIn(7, track_analysis["references"]["waypoint"])
        self.assertEqual(life_instructions[0]["operand_semantics"], {"body_id": 7})
        self.assertEqual(life_instructions[1]["operand_semantics"], {"animation_id": 4})
        self.assertEqual(
            life_instructions[2]["operand_semantics"],
            {"camera_zone_id": 3, "enabled": True},
        )
        self.assertEqual(
            life_instructions[3]["operand_semantics"],
            {"change_cube_control_id": 5, "enabled": False},
        )
        self.assertEqual(life_instructions[4]["operand_semantics"], {"sprite_id": 127})
        self.assertEqual(life_analysis["references"]["camera_zone"], [3])
        self.assertEqual(life_analysis["references"]["change_cube_control"], [5])

    def test_scene_script_operand_semantics_decode_runtime_state_fields(self) -> None:
        switch_script = (
            bytes([113, 15, 40, 115])
            + struct.pack("<h", 24)
            + bytes([0])
            + struct.pack("<h", 3)
            + bytes([114])
            + struct.pack("<h", 28)
            + bytes([5])
            + struct.pack("<h", -1)
            + bytes([117])
            + struct.pack("<h", 40)
            + bytes([118, 0])
        )
        state_script = (
            bytes([31, 2, 7, 36, 4])
            + struct.pack("<h", 100)
            + bytes([128, 4])
            + struct.pack("<h", 3)
            + bytes([129, 4])
            + struct.pack("<h", 2)
            + bytes([46, 9, 67, 8, 111, 8, 12, 53, 1, 54, 2, 61, 3, 20, 62, 3, 5, 63, 3, 9, 110, 3, 4, 119, 6, 1, 100, 5])
            + bytes([122])
            + struct.pack("<h", 12)
            + bytes([126])
            + struct.pack("<h", 13)
            + bytes([2, 151])
            + struct.pack("<h", -10)
            + bytes([64])
            + struct.pack("<h", 22050)
            + bytes([152])
            + struct.pack("<h", 14)
            + struct.pack("<h", -20)
            + bytes([80])
            + struct.pack("<h", 11025)
            + bytes([0])
        )
        track_script = (
            bytes([6, 3, 2])
            + struct.pack("<h", 8)
            + bytes([7])
            + struct.pack("<h", 600)
            + bytes([14])
            + struct.pack("<h", 83)
            + bytes([0])
        )

        switch_analysis = scene_scripts.analyze_life_script(switch_script)
        state_analysis = scene_scripts.analyze_life_script(state_script)
        track_analysis = scene_scripts.analyze_track_script(track_script)

        self.assertEqual(switch_analysis["status"], "decoded")
        self.assertEqual(
            switch_analysis["first_instructions"][0]["operand_semantics"],
            {
                "function_id": 15,
                "function": "LF_VAR_GAME",
                "return_type": "s16",
                "var_game_id": 40,
            },
        )
        self.assertEqual(
            switch_analysis["condition_functions"],
            [
                {
                    "function": "LF_VAR_GAME",
                    "function_id": 15,
                    "count": 1,
                    "return_type": "s16",
                    "opcodes": ["LM_SWITCH"],
                }
            ],
        )
        self.assertEqual(
            switch_analysis["first_instructions"][1]["operand_semantics"],
            {
                "target_offset": 24,
                "switch_return_type": "s16",
                "comparator": "LT_EQUAL",
                "compare_value": 3,
            },
        )
        self.assertEqual(
            switch_analysis["first_instructions"][2]["operand_semantics"],
            {
                "target_offset": 28,
                "switch_return_type": "s16",
                "comparator": "LT_DIFFERENT",
                "compare_value": -1,
            },
        )
        self.assertEqual(switch_analysis["references"]["script_offset"], [24, 28, 40])
        self.assertEqual(switch_analysis["references"]["var_game"], [40])

        nested_switch = (
            bytes([113, 11, 3])
            + bytes([115])
            + struct.pack("<h", 23)
            + bytes([0, 1])
            + bytes([113, 10, 14])
            + bytes([115])
            + struct.pack("<h", 20)
            + bytes([0, 25])
            + bytes([118])
            + bytes([115])
            + struct.pack("<h", 23)
            + bytes([0, 2])
            + bytes([118, 0])
        )
        nested_analysis = scene_scripts.analyze_life_script(nested_switch)

        self.assertEqual(nested_analysis["status"], "decoded")
        self.assertEqual(nested_analysis["decoded_bytes"], len(nested_switch))
        self.assertEqual(nested_analysis["instruction_count"], 8)
        self.assertEqual(
            [
                instruction["operand_semantics"]
                for instruction in nested_analysis["first_instructions"]
                if instruction["mnemonic"] == "LM_CASE"
            ],
            [
                {
                    "target_offset": 23,
                    "switch_return_type": "u8",
                    "comparator": "LT_EQUAL",
                    "compare_value": 1,
                },
                {
                    "target_offset": 20,
                    "switch_return_type": "u8",
                    "comparator": "LT_EQUAL",
                    "compare_value": 25,
                },
                {
                    "target_offset": 23,
                    "switch_return_type": "u8",
                    "comparator": "LT_EQUAL",
                    "compare_value": 2,
                },
            ],
        )

        semantics = [instruction["operand_semantics"] for instruction in state_analysis["first_instructions"]]
        self.assertIn({"var_cube_id": 2, "value": 7}, semantics)
        self.assertIn({"var_game_id": 4, "value": 100}, semantics)
        self.assertIn({"var_game_id": 4, "delta": 3}, semantics)
        self.assertIn({"inventory_id": 9}, semantics)
        self.assertIn({"inventory_id": 8, "used": True}, semantics)
        self.assertIn({"inventory_id": 8, "inventory_object_3d_id": 12}, semantics)
        self.assertIn({"enabled": True}, semantics)
        self.assertIn({"brick_collision_mode": 2}, semantics)
        self.assertIn({"object_id": 3, "life_points": 20}, semantics)
        self.assertIn({"object_id": 3, "damage": 9}, semantics)
        self.assertIn({"hit_zone_id": 6, "enabled": True}, semantics)
        self.assertIn({"music_id": 5}, semantics)
        self.assertIn({"sample_id": 12}, semantics)
        self.assertEqual(state_analysis["references"]["var_cube"], [2])
        self.assertEqual(state_analysis["references"]["var_game"], [4])
        self.assertEqual(state_analysis["references"]["inventory"], [8, 9])
        self.assertEqual(state_analysis["references"]["object"], [3])
        self.assertEqual(state_analysis["references"]["sample"], [12, 13, 14])
        self.assertEqual(state_analysis["references"]["music"], [5])
        self.assertEqual(state_analysis["references"]["hit_zone"], [6])
        self.assertEqual(track_analysis["references"]["sample"], [83])
        self.assertEqual(
            track_analysis["runtime_state_fields"],
            [
                {
                    "source_offset": 0,
                    "opcode": "TM_LOOP",
                    "behavior_category": "control_flow",
                    "field": "current_count",
                    "instruction_relative_offset": 2,
                    "operand_offset": 1,
                    "size": 1,
                    "initial_hex": "02",
                    "source": "classic_track_runtime",
                    "initial_value": 2,
                },
                {
                    "source_offset": 5,
                    "opcode": "TM_ANGLE",
                    "behavior_category": "movement_path",
                    "field": "target_beta_runtime_flag",
                    "instruction_relative_offset": 1,
                    "operand_offset": 0,
                    "size": 2,
                    "initial_hex": "5802",
                    "source": "classic_track_runtime",
                    "initial_value": 600,
                },
            ],
        )

    def test_scene_script_operand_semantics_decode_movement_lifecycle_and_effect_fields(self) -> None:
        movement_script = (
            bytes([27, 2, 4, 28, 5, 9, 9, 29, 3, 30, 2, 32, 7, 33])
            + struct.pack("<h", 44)
            + bytes([34, 6])
            + struct.pack("<h", 55)
            + bytes([37, 8, 70, 2, 0])
        )
        effect_script = (
            bytes([10, 3, 57, 5, 1, 65, 4, 72, 11, 73, 11, 81, 4, 96, 5, 99, 7, 1, 145, 2, 99, 146, 3, 88, 148, 1, 2, 153, 2, 8, 154, 3, 4, 5])
            + struct.pack("<h", 100)
            + bytes([0])
        )

        movement_analysis = scene_scripts.analyze_life_script(movement_script)
        effect_analysis = scene_scripts.analyze_life_script(effect_script)
        movement_semantics = [instruction["operand_semantics"] for instruction in movement_analysis["first_instructions"]]
        effect_semantics = [instruction["operand_semantics"] for instruction in effect_analysis["first_instructions"]]

        self.assertEqual(movement_analysis["status"], "decoded")
        self.assertIn(
            {"move_mode": 2, "move_mode_name": "MOVE_FOLLOW", "follow_object_id": 4},
            movement_semantics,
        )
        self.assertIn(
            {
                "object_id": 5,
                "move_mode": 9,
                "move_mode_name": "MOVE_CIRCLE",
                "circle_waypoint_id": 9,
            },
            movement_semantics,
        )
        self.assertIn(
            {"hero_behavior_id": 2, "hero_behavior": "C_AGRESSIF"},
            movement_semantics,
        )
        self.assertIn({"behavior_id": 7}, movement_semantics)
        self.assertIn({"target_life_offset": 44}, movement_semantics)
        self.assertIn({"object_id": 6, "target_life_offset": 55}, movement_semantics)
        self.assertIn(
            {
                "object_id": 8,
                "lifecycle_state": "dead",
                "body_action": "hide_object_body",
                "zone_action": "clear_object_zone",
                "life_points": 0,
            },
            movement_semantics,
        )
        self.assertIn({"buggy_id": 2}, movement_semantics)
        self.assertEqual(movement_analysis["references"]["object"], [3, 4, 5, 6, 8])
        self.assertEqual(movement_analysis["references"]["waypoint"], [9])
        self.assertEqual(movement_analysis["references"]["behavior"], [2, 7])
        self.assertEqual(movement_analysis["references"]["buggy"], [2])
        self.assertEqual(movement_analysis["references"]["script_offset"], [44, 55])

        self.assertEqual(effect_analysis["status"], "decoded")
        self.assertIn({"palette_id": 3}, effect_semantics)
        self.assertIn({"object_id": 5, "enabled": True}, effect_semantics)
        self.assertIn({"effect": "lightning", "duration_tenths": 4}, effect_semantics)
        self.assertIn({"holomap_location_id": 11}, effect_semantics)
        self.assertIn({"palette_id": 4}, effect_semantics)
        self.assertIn({"effect": "rain", "duration_tenths": 5}, effect_semantics)
        self.assertIn({"escalator_zone_id": 7, "enabled": True}, effect_semantics)
        self.assertIn({"waypoint_id": 2, "flow_strength": 99}, effect_semantics)
        self.assertIn({"object_id": 3, "flow_strength": 88}, effect_semantics)
        self.assertIn({"pcx_id": 1, "effect_id": 2, "dialogue_action": "show_pcx"}, effect_semantics)
        self.assertIn({"object_id": 2, "around_object_id": 8}, effect_semantics)
        self.assertIn(
            {"pcx_id": 3, "effect_id": 4, "object_id": 5, "text_id": 100, "dialogue_action": "show_pcx_message_object"},
            effect_semantics,
        )
        self.assertEqual(effect_analysis["references"]["palette"], [3, 4])
        self.assertEqual(effect_analysis["references"]["pcx"], [1, 3])
        self.assertEqual(effect_analysis["references"]["holomap"], [11])
        self.assertEqual(effect_analysis["references"]["escalator_zone"], [7])
        self.assertEqual(effect_analysis["references"]["waypoint"], [2])
        self.assertEqual(effect_analysis["references"]["object"], [2, 3, 5, 8])
        self.assertEqual(effect_analysis["references"]["text"], [100])

    def test_scene_script_operand_semantics_decode_execution_and_audio_fields(self) -> None:
        track_script = (
            bytes([0, 5, 11, 19, 25, 26, 30])
            + b"intro\x00"
            + bytes([50])
            + struct.pack("<h", 120)
            + bytes([51])
            + struct.pack("<h", 22050)
            + bytes([52, 96, 46, 47])
        )
        life_script = (
            bytes([38, 42, 43, 39, 64])
            + b"cut\x00"
            + bytes([79, 86, 5])
            + struct.pack("<Hh", 0x1234, -7)
            + bytes([93, 94, 134, 135, 120, 121, 0])
        )
        life_state_script = bytes([0, 11, 35, 41, 66, 71, 5, 82, 97, 98, 116, 118, 144])

        track_analysis = scene_scripts.analyze_track_script(track_script)
        life_analysis = scene_scripts.analyze_life_script(life_script)
        life_state_analysis = scene_scripts.analyze_life_script(life_state_script)
        track_semantics = [instruction["operand_semantics"] for instruction in track_analysis["first_instructions"]]
        life_semantics = [instruction["operand_semantics"] for instruction in life_analysis["first_instructions"]]
        life_state_semantics = [instruction["operand_semantics"] for instruction in life_state_analysis["first_instructions"]]

        self.assertIn({"track_action": "stop_current_track", "offset_track": -1}, track_semantics)
        self.assertIn({"wait_for_animation_end": True, "completion_action": "clear_real_angle"}, track_semantics)
        self.assertIn({"body_action": "hide_current_object_body"}, track_semantics)
        self.assertIn({"door_action": "close"}, track_semantics)
        self.assertIn({"wait_for_door": True}, track_semantics)
        self.assertIn({"acf_name": "intro", "cinematic_action": "play_acf"}, track_semantics)
        self.assertIn({"sample_offset": 120}, track_semantics)
        self.assertIn({"sample_frequency": 22050}, track_semantics)
        self.assertIn({"sample_volume": 96}, track_semantics)
        self.assertIn({"anim3ds_action": "stop_animation"}, track_semantics)
        self.assertIn({"wait_for_anim3ds_end": True}, track_semantics)

        self.assertIn(
            {
                "target": "current_object",
                "lifecycle_state": "dead",
                "body_action": "hide_current_object_body",
                "zone_action": "clear_current_object_zone",
                "life_points": 0,
            },
            life_semantics,
        )
        self.assertIn({"target": "current_object", "track_action": "stop"}, life_semantics)
        self.assertIn({"target": "current_object", "track_action": "restore"}, life_semantics)
        self.assertIn({"inventory_action": "use_one_little_key"}, life_semantics)
        self.assertIn({"acf_name": "cut", "cinematic_action": "play_acf"}, life_semantics)
        self.assertIn({"hero_life_points": "max", "magic_points": "max_for_magic_level"}, life_semantics)
        self.assertIn({"object_id": 5, "impact_id": 0x1234, "y_offset": -7}, life_semantics)
        self.assertIn({"hero_state_action": "save"}, life_semantics)
        self.assertIn({"hero_state_action": "restore"}, life_semantics)
        self.assertIn({"beta_action": "invert_current_object"}, life_semantics)
        self.assertIn({"body_action": "hide_current_object_body"}, life_semantics)
        self.assertIn({"behavior_memory_action": "save_current_behavior"}, life_semantics)
        self.assertIn({"behavior_memory_action": "restore_current_behavior"}, life_semantics)
        self.assertIn({"clover_box_delta": 1, "clover_box_cap": "MAX_CLOVER_BOX"}, life_state_semantics)
        self.assertIn({"life_action": "stop_current_life", "offset_life": -1}, life_state_semantics)
        self.assertIn({"life_action": "return_from_life_pass"}, life_state_semantics)
        self.assertIn({"life_action": "end_current_behavior_pass"}, life_state_semantics)
        self.assertIn({"slate_memo_id": 5, "inventory_feedback": "slate"}, life_state_semantics)
        self.assertIn({"action_state": "normal_action_enabled"}, life_state_semantics)
        self.assertIn({"game_state_action": "game_over"}, life_state_semantics)
        self.assertIn({"game_state_action": "the_end"}, life_state_semantics)
        self.assertIn({"switch_marker": "default_case"}, life_state_semantics)
        self.assertIn({"switch_marker": "end_switch"}, life_state_semantics)
        self.assertIn({"external_action": "popcorn", "runtime_effect": "disabled_in_classic_source"}, life_state_semantics)
        self.assertIn(
            {
                "contract": "cinematic_playback_control",
                "count": 1,
                "source": "GERETRAK.CPP",
                "effect": "play ACF cinematic by name, restore timers/palette state, and request AFF_ALL redraw after playback",
                "mnemonics": ["TM_PLAY_ACF"],
            },
            track_analysis["execution_contracts"],
        )
        self.assertIn(
            {
                "contract": "cinematic_playback_control",
                "count": 1,
                "source": "GERELIFE.CPP",
                "effect": "play ACF cinematic by name, restore timers/palette state, and request AFF_ALL redraw after playback",
                "mnemonics": ["LM_PLAY_ACF"],
            },
            life_analysis["execution_contracts"],
        )
        self.assertEqual(life_analysis["references"]["object"], [5])

    def test_scene_script_operand_semantics_decode_object_lifecycle_edge_cases(self) -> None:
        script = bytes([37, 4, 105, 137, 5, 138, 6, 139, 7, 140, 8])

        analysis = scene_scripts.analyze_life_script(script)
        semantics = [instruction["operand_semantics"] for instruction in analysis["first_instructions"]]

        self.assertEqual(analysis["status"], "decoded")
        self.assertIn(
            {
                "object_id": 4,
                "lifecycle_state": "dead",
                "body_action": "hide_object_body",
                "zone_action": "clear_object_zone",
                "life_points": 0,
            },
            semantics,
        )
        self.assertIn({"game_state_action": "brutal_exit"}, semantics)
        self.assertIn(
            {
                "object_id": 5,
                "target": "object",
                "track_action": "stop",
                "life_point_guard": "only_if_alive",
            },
            semantics,
        )
        self.assertIn(
            {
                "object_id": 6,
                "target": "object",
                "track_action": "restore",
                "life_point_guard": "only_if_alive",
            },
            semantics,
        )
        self.assertIn(
            {
                "object_id": 7,
                "target": "object",
                "behavior_memory_action": "save_object_behavior",
                "life_point_guard": "only_if_alive",
            },
            semantics,
        )
        self.assertIn(
            {
                "object_id": 8,
                "target": "object",
                "behavior_memory_action": "restore_object_behavior",
                "life_point_guard": "only_if_alive",
            },
            semantics,
        )
        self.assertEqual(
            analysis["execution_contracts"],
            [
                {
                    "contract": "behavior_memory_control",
                    "count": 2,
                    "source": "GERELIFE.CPP",
                    "effect": "save target object behavior when alive",
                    "mnemonics": [
                        "LM_RESTORE_COMPORTEMENT_OBJ",
                        "LM_SAVE_COMPORTEMENT_OBJ",
                    ],
                },
                {
                    "contract": "game_flow_terminal",
                    "count": 1,
                    "source": "GERELIFE.CPP",
                    "effect": "force runtime exit path",
                    "mnemonics": ["LM_BRUTAL_EXIT"],
                },
                {
                    "contract": "object_lifecycle_death",
                    "count": 1,
                    "source": "GERELIFE.CPP",
                    "effect": "clear target object body, zone, and life points",
                    "mnemonics": ["LM_KILL_OBJ"],
                },
                {
                    "contract": "track_pass_control",
                    "count": 2,
                    "source": "GERELIFE.CPP",
                    "effect": "stop target object track when alive",
                    "mnemonics": ["LM_RESTORE_L_TRACK_OBJ", "LM_STOP_L_TRACK_OBJ"],
                },
            ],
        )
        self.assertEqual(analysis["references"]["object"], [4, 5, 6, 7, 8])

    def test_scene_script_execution_contracts_include_background_redraw_control(self) -> None:
        track_analysis = scene_scripts.analyze_track_script(bytes([17, 1, 0]))
        life_analysis = scene_scripts.analyze_life_script(bytes([127, 0, 0]))
        recon = viewer.parse_scene_reconnaissance(
            scene_payload(
                hero_track_script=bytes([17, 1, 0]),
                hero_life_script=bytes([127, 0, 0]),
            )
        )

        self.assertIn(
            {
                "contract": "background_incrust_redraw_control",
                "count": 1,
                "source": "GERETRAK.CPP",
                "effect": "toggle OBJ_BACKGROUND on the current object and request AFF_ALL redraw when the flag changes",
                "mnemonics": ["TM_BACKGROUND"],
            },
            track_analysis["execution_contracts"],
        )
        self.assertIn(
            {
                "contract": "background_incrust_redraw_control",
                "count": 1,
                "source": "GERELIFE.CPP",
                "effect": "toggle OBJ_BACKGROUND on the current object and request AFF_ALL redraw when the flag changes",
                "mnemonics": ["LM_BACKGROUND"],
            },
            life_analysis["execution_contracts"],
        )
        self.assertEqual(
            recon["script_execution_contract_counts"],
            {
                "background_incrust_redraw_control": 2,
                "life_pass_control": 1,
                "track_pass_control": 1,
            },
        )

    def test_scene_script_operand_semantics_decode_dialogue_choice_fields(self) -> None:
        script = (
            bytes([25])
            + struct.pack("<h", 100)
            + bytes([88])
            + struct.pack("<h", 101)
            + bytes([78])
            + struct.pack("<h", 102)
            + bytes([44, 3])
            + struct.pack("<h", 103)
            + bytes([104, 4])
            + struct.pack("<h", 104)
            + bytes([68])
            + struct.pack("<h", 201)
            + bytes([69])
            + struct.pack("<h", 200)
            + bytes([91, 5])
            + struct.pack("<h", 202)
            + bytes([89, 1, 149, 150, 6, 0])
        )

        analysis = scene_scripts.analyze_life_script(script)
        semantics = [instruction["operand_semantics"] for instruction in analysis["first_instructions"]]

        self.assertEqual(analysis["status"], "decoded")
        self.assertIn(
            {
                "text_id": 100,
                "dialogue_action": "dial_text",
                "dialogue_variant": "message",
                "dialogue_speaker": "current_object",
                "dialogue_target": "current_object",
            },
            semantics,
        )
        self.assertIn(
            {
                "text_id": 101,
                "dialogue_action": "dial_text",
                "dialogue_variant": "add_message",
                "dialogue_speaker": "current_object",
                "dialogue_target": "current_object",
            },
            semantics,
        )
        self.assertIn(
            {
                "text_id": 102,
                "dialogue_action": "dial_text",
                "dialogue_variant": "zoe_message",
                "dialogue_speaker": "current_object",
                "dialogue_target": "hero",
                "dialogue_color": "zoe",
            },
            semantics,
        )
        self.assertIn(
            {
                "object_id": 3,
                "text_id": 103,
                "dialogue_action": "dial_text",
                "dialogue_variant": "message_object",
                "dialogue_speaker": "object",
                "dialogue_target": "object",
            },
            semantics,
        )
        self.assertIn(
            {
                "object_id": 4,
                "text_id": 104,
                "dialogue_action": "dial_text",
                "dialogue_variant": "add_message_object",
                "dialogue_speaker": "object",
                "dialogue_target": "object",
            },
            semantics,
        )
        self.assertIn({"text_id": 201, "choice_action": "append_choice"}, semantics)
        self.assertIn(
            {
                "text_id": 200,
                "choice_action": "ask_choice",
                "choice_prompt_source": "text",
                "choice_reset_after_ask": True,
                "dialogue_target": "current_object",
            },
            semantics,
        )
        self.assertIn(
            {
                "object_id": 5,
                "text_id": 202,
                "choice_action": "ask_choice",
                "choice_prompt_source": "text",
                "choice_reset_after_ask": True,
                "dialogue_target": "object",
            },
            semantics,
        )
        self.assertIn(
            {"dialogue_action": "set_bubble_mode", "bubble_enabled": True, "bubble_raw": 1},
            semantics,
        )
        self.assertIn({"dialogue_action": "end_message"}, semantics)
        self.assertIn({"object_id": 6, "dialogue_action": "end_message_object"}, semantics)
        self.assertEqual(analysis["references"]["text"], [100, 101, 102, 103, 104, 200, 201, 202])
        self.assertEqual(analysis["references"]["object"], [3, 4, 5, 6])

    def test_runtime_sprite_resolver_matches_classic_backend_rules(self) -> None:
        normal = viewer.resolve_runtime_sprite(viewer.SPRITE_3D_FLAG, 127)
        self.assertTrue(normal["resolved"])
        self.assertEqual(normal["backend"], "sprites")
        self.assertEqual(normal["archive"], "SPRITES.HQR")
        self.assertEqual(normal["asset_id"], "SPRITES.HQR:127")
        self.assertEqual(normal["bounds_source"], {"hqr": "RESS.HQR", "entry_index": 5})

        raw = viewer.resolve_runtime_sprite(viewer.SPRITE_3D_FLAG, 99)
        self.assertTrue(raw["resolved"])
        self.assertEqual(raw["backend"], "spriraw")
        self.assertEqual(raw["asset_id"], "SPRIRAW.HQR:99")
        self.assertEqual(raw["bounds_source"], {"hqr": "RESS.HQR", "entry_index": 8})

        anim3ds = viewer.resolve_runtime_sprite(
            viewer.SPRITE_3D_FLAG | viewer.ANIM_3DS_FLAG,
            127,
        )
        self.assertTrue(anim3ds["resolved"])
        self.assertEqual(anim3ds["backend"], "anim3ds")
        self.assertEqual(anim3ds["asset_id"], "ANIM3DS.HQR:127")
        self.assertEqual(anim3ds["bounds_source"], {"hqr": "RESS.HQR", "entry_index": 43})

        body = viewer.resolve_runtime_sprite(0, 127)
        self.assertFalse(body["resolved"])
        self.assertIsNone(body["backend"])

    def test_runtime_object_sprite_state_tracks_body_num_mirror(self) -> None:
        state = viewer.runtime_object_sprite_state(
            flags=viewer.SPRITE_3D_FLAG,
            sprite_index=127,
            body_num=128,
            label_track=1,
            object_index=7,
        )

        self.assertEqual(state["object_index"], 7)
        self.assertEqual(state["label_track"], 1)
        self.assertFalse(state["body_num_matches_sprite"])
        self.assertIn("differs from Sprite", state["body_num_note"])
        self.assertEqual(state["resolution"]["asset_id"], "SPRITES.HQR:127")

        mirrored = viewer.runtime_object_sprite_state(
            flags=viewer.SPRITE_3D_FLAG,
            sprite_index=127,
            body_num=127,
        )
        self.assertTrue(mirrored["body_num_matches_sprite"])

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

    def test_build_evidence_records_playback_transition_table(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), []),
                    (100, (0, 0, 0), []),
                    (100, (0, 0, 0), []),
                ],
                loop_start=1,
            )
        )

        evidence = animation.build_animation_evidence(
            decoded,
            source={"catalog_asset_id": "ANIM.HQR:1"},
        )

        playback = evidence["playback"]
        self.assertEqual(playback["loop_index"], 3)
        self.assertEqual(playback["playback_end_index"], 3)
        self.assertEqual(
            playback["transitions"],
            [
                {
                    "sequence_index": 0,
                    "segment": "intro",
                    "target_frame_index": 0,
                    "previous_frame_index": 0,
                },
                {
                    "sequence_index": 1,
                    "segment": "intro",
                    "target_frame_index": 1,
                    "previous_frame_index": 0,
                },
                {
                    "sequence_index": 2,
                    "segment": "intro",
                    "target_frame_index": 2,
                    "previous_frame_index": 1,
                },
                {
                    "sequence_index": 3,
                    "segment": "loop",
                    "target_frame_index": 1,
                    "previous_frame_index": 2,
                },
                {
                    "sequence_index": 4,
                    "segment": "loop",
                    "target_frame_index": 2,
                    "previous_frame_index": 1,
                },
            ],
        )

    def test_playback_frame_indices_add_loop_segment_with_last_previous_frame(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), []),
                    (100, (0, 0, 0), []),
                    (100, (0, 0, 0), []),
                ],
                loop_start=0,
            )
        )

        frame_pairs, loop_index = animation.playback_frame_indices(decoded)

        self.assertEqual(loop_index, 3)
        self.assertEqual(frame_pairs, ((0, 0), (1, 0), (2, 1), (0, 2), (1, 0), (2, 1)))

    def test_playback_frame_indices_preserve_intro_before_nonzero_loop(self) -> None:
        decoded = animation.parse_lba2_animation_records(
            anim_payload(
                [
                    (100, (0, 0, 0), []),
                    (100, (0, 0, 0), []),
                    (100, (0, 0, 0), []),
                ],
                loop_start=1,
            )
        )

        frame_pairs, loop_index = animation.playback_frame_indices(decoded)

        self.assertEqual(loop_index, 3)
        self.assertEqual(frame_pairs, ((0, 0), (1, 0), (2, 1), (1, 2), (2, 1)))

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
            self.assertEqual(evidence["playback"]["loop_index"], 0)
            self.assertEqual(evidence["animation"]["keyframes"][0]["bones"][0]["raw"], [0, 4, 5, 6])

    def test_animation_command_can_sample_canonical_loop_transition(self) -> None:
        data = anim_payload(
            [
                (100, (0, 0, 0), [(0, 0, 0, 0)]),
                (100, (0, 0, 0), [(0, 10, 0, 0)]),
                (100, (0, 0, 0), [(0, 20, 0, 0)]),
            ],
            loop_start=1,
        )
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
                        "--sample-loop-transition",
                    ]
                )

            self.assertEqual(exit_code, 0)
            evidence = json.loads(output.read_text(encoding="utf-8"))
            sample = evidence["samples"][0]
            self.assertEqual(sample["target_frame_index"], 1)
            self.assertEqual(sample["previous_frame_index"], 2)
            self.assertEqual(sample["bones"][0]["values"][0], 20)

    def test_catalog_keeps_anim3ds_entries_raw_even_when_header_looks_like_anim(self) -> None:
        data = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(classic_hqr([resource_entry(data)]))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["animations"], 0)
            self.assertEqual(catalog["summary"]["decoded_animations"], 0)
            self.assertEqual(catalog["summary"]["raw_animations"], 0)
            self.assertEqual(catalog["summary"]["animation_assets"], 0)
            self.assertEqual(catalog["summary"]["sprite_assets"], 1)
            self.assertEqual(catalog["summary"]["sprite_frames"], 1)
            asset = catalog["assets"][0]
            self.assertEqual(asset["kind"], "sprite")
            self.assertEqual(asset["entry_type"], "anim3ds-frame")
            self.assertNotIn("animation_state", asset)
            self.assertEqual(asset["features"]["parsed"], False)
            self.assertEqual(asset["features"]["sprite_frame"], True)
            self.assertEqual(asset["features"]["runtime_sprite_backend"], "anim3ds")
            self.assertEqual(asset["features"]["has_runtime_bounds"], False)
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
            self.assertIn("ANIM3DS frame is expected to be an LSP sprite payload", stats["decode_note"])
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

    def test_catalog_decodes_anim3ds_lsp_sprite_frame_pixels(self) -> None:
        data = lsp_sprite_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(classic_hqr([resource_entry(data)]))

            catalog = viewer.build_catalog(root)

            asset = viewer.find_catalog_asset(catalog, "ANIM3DS.HQR:0")
            self.assertEqual(asset["kind"], "sprite")
            self.assertEqual(asset["entry_type"], "anim3ds-frame")
            self.assertEqual(asset["features"]["parsed"], True)
            self.assertEqual(asset["features"]["sprite_frame"], True)
            self.assertEqual(asset["features"]["runtime_sprite_backend"], "anim3ds")
            self.assertEqual(asset["features"]["has_runtime_bounds"], False)
            stats = asset["stats"]
            self.assertEqual(stats["parse_status"], "decoded")
            self.assertEqual(stats["decode_status"], "decoded")
            self.assertEqual(stats["semantic_layout"], "lsp_sprite_frame")
            self.assertEqual(stats["sprite_backend"], "anim3ds")
            self.assertEqual(stats["runtime"]["backend"], "anim3ds")
            self.assertEqual(stats["runtime"]["runtime_sprite_index"], 0)
            self.assertEqual(stats["width"], 4)
            self.assertEqual(stats["height"], 2)
            self.assertEqual(stats["offset_x"], 1)
            self.assertEqual(stats["offset_y"], 2)
            self.assertEqual(stats["encoded_bytes_consumed"], len(data))
            self.assertEqual(stats["trailing_bytes"], 0)
            self.assertEqual(stats["opaque_pixels"], 6)
            self.assertEqual(stats["transparent_pixels"], 2)
            self.assertEqual(stats["palette_indices"], [0, 1, 2, 3, 7, 8])
            self.assertEqual(stats["unknown_descriptors"][0]["section"], "lsp_header_prefix")
            payload, _ = viewer.read_hqr_payload(root, asset["source"])
            self.assertEqual(payload, data)

    def test_catalog_decodes_normal_sprites_hqr_with_runtime_bounds(self) -> None:
        data = lsp_sprite_payload()
        zv = sprite_zv_payload(128, 127, (11, -12, -30, 31, -40, 41, -50, 51))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            entries = [resource_entry(lsp_sprite_payload())] + [b""] * 126 + [resource_entry(data)]
            (root / "SPRITES.HQR").write_bytes(classic_hqr(entries))
            (root / "RESS.HQR").write_bytes(hqr([b""] * 4 + [resource_entry(zv)]))

            catalog = viewer.build_catalog(root)

            asset = viewer.find_catalog_asset(catalog, "SPRITES.HQR:127")
            self.assertEqual(asset["kind"], "sprite")
            self.assertEqual(asset["entry_type"], "sprite-frame")
            self.assertEqual(asset["label"], "Runtime sprite 127 (SPRITES.HQR:127)")
            self.assertEqual(asset["features"]["runtime_sprite_backend"], "sprites")
            self.assertEqual(asset["features"]["has_runtime_bounds"], True)
            self.assertEqual(catalog["summary"]["sprite_assets"], 2)
            self.assertEqual(catalog["summary"]["sprite_frames"], 2)
            stats = asset["stats"]
            self.assertEqual(stats["semantic_layout"], "lsp_sprite_frame")
            self.assertEqual(stats["sprite_backend"], "sprites")
            self.assertEqual(stats["runtime"]["backend"], "sprites")
            self.assertEqual(stats["runtime"]["runtime_sprite_index"], 127)
            self.assertIn("Sprite >= 100", stats["runtime"]["index_rule"])
            self.assertEqual(stats["runtime"]["hotspot"], {"x": 11, "y": -12})
            self.assertEqual(stats["runtime"]["bounds"]["min_x"], -30)
            self.assertEqual(stats["runtime"]["bounds"]["max_z"], 51)

            low_asset = viewer.find_catalog_asset(catalog, "SPRITES.HQR:0")
            self.assertEqual(low_asset["features"]["runtime_sprite_backend"], "sprites")
            self.assertEqual(low_asset["stats"]["runtime"]["backend"], "sprites")
            self.assertIn("direct HQRPtrSprite", low_asset["stats"]["runtime"]["index_rule"])
            self.assertEqual(low_asset["stats"]["direct_reference_count"], 1)
            self.assertEqual(
                low_asset["stats"]["direct_code_references"][0]["symbol"],
                "SYS_SPRITE_SG",
            )

    def test_catalog_promotes_ress_runtime_tables_to_resource_assets(self) -> None:
        palette = bytes(range(256)) * 3
        texture = bytes([0, 1, 2, 3]) * (viewer.TEXTURE_ATLAS_PIXELS // 4)
        indexed_image = bytes([3, 4, 5, 6]) * (viewer.TEXTURE_ATLAS_PIXELS // 4)
        zv = bytes(96)
        file3d = file3d_record(file3d_body(0, 0) + file3d_anim(1, 1))
        offset_table = struct.pack("<III", 12, 16, 20) + b"ABCDWXYZ"
        fixed_table = struct.pack("<hhhhhhhh", 1, -2, 3, -4, 5, -6, 7, -8)
        xpl_payload = (
            struct.pack("<iiiiiiiiiii", 0, 44, 0, 812, 900, 20, 12, 170, 33, 3683, 9633)
            + palette
            + bytes(900 - 44 - len(palette))
            + bytes(128)
        )
        acf_list = b"INTRO.SMK\r\nEND.SMK\r\n"
        entries = [b""] * 48
        entries[0] = resource_entry(offset_table)
        entries[1] = resource_entry(struct.pack("<iiii", 7680, 18264, 5052, 390976))
        entries[4] = resource_entry(zv)
        entries[5] = resource_entry(texture)
        entries[6] = resource_entry(b"raw!")
        entries[8] = resource_entry(palette)
        entries[10] = resource_entry(indexed_image)
        entries[26] = resource_entry(xpl_payload)
        entries[37] = resource_entry(xpl_payload)
        entries[44] = resource_entry(fixed_table)
        entries[45] = resource_entry(offset_table)
        entries[46] = resource_entry(offset_table)
        entries[47] = resource_entry(acf_list)
        entries[43] = resource_entry(file3d)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "RESS.HQR").write_bytes(hqr(entries))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["resource_assets"], 14)
            first_offset_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:1")
            self.assertEqual(first_offset_asset["entry_type"], "offset-record-table")
            self.assertEqual(
                first_offset_asset["stats"]["semantic_layout"],
                "ress_offset_record_table",
            )
            extra_palette = viewer.find_catalog_asset(catalog, "RESS.HQR:9")
            self.assertEqual(extra_palette["entry_type"], "palette")
            texture_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:6")
            self.assertEqual(texture_asset["stats"]["semantic_layout"], "lba2_texture_atlas_indexed")
            self.assertEqual(texture_asset["stats"]["unique_palette_indices"], 4)
            image_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:11")
            self.assertEqual(image_asset["entry_type"], "indexed-image")
            self.assertEqual(image_asset["stats"]["semantic_layout"], "lba2_indexed_image_256")
            self.assertEqual(image_asset["stats"]["unique_palette_indices"], 4)
            self.assertEqual(
                image_asset["stats"]["unknown_descriptors"][0]["section"],
                "indexed_image_semantics",
            )
            zv_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:5")
            self.assertEqual(zv_asset["kind"], "resource")
            self.assertEqual(zv_asset["stats"]["semantic_layout"], "sprite_zv_table")
            self.assertEqual(zv_asset["stats"]["record_count"], 6)
            file3d_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:44")
            self.assertEqual(file3d_asset["stats"]["semantic_layout"], "file3d_table")
            self.assertEqual(file3d_asset["stats"]["object_count"], 1)
            fixed_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:45")
            self.assertEqual(fixed_asset["entry_type"], "fixed-s16-table")
            self.assertEqual(fixed_asset["label"], "RESS_FLOW signed-word table (RESS.HQR:45)")
            self.assertEqual(fixed_asset["stats"]["semantic_layout"], "ress_fixed_s16x8_table")
            self.assertEqual(fixed_asset["stats"]["runtime_table_name"], "RESS_FLOW")
            self.assertEqual(fixed_asset["stats"]["runtime_buffer"], "TabPartFlow")
            self.assertIn("particle", fixed_asset["stats"]["runtime_purpose"].lower())
            self.assertIn("FLOW.CPP", fixed_asset["stats"]["source_provenance"])
            self.assertIn(
                "field names are not identified",
                fixed_asset["stats"]["unknown_descriptors"][0]["note"],
            )
            self.assertEqual(fixed_asset["stats"]["sampled_records"][0]["values"], [1, -2, 3, -4, 5, -6, 7, -8])
            offset_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:46")
            self.assertEqual(offset_asset["entry_type"], "offset-record-table")
            self.assertEqual(offset_asset["label"], "RESS_POF runtime table (RESS.HQR:46)")
            self.assertEqual(offset_asset["stats"]["semantic_layout"], "ress_offset_record_table")
            self.assertEqual(offset_asset["stats"]["runtime_table_name"], "RESS_POF")
            self.assertEqual(offset_asset["stats"]["runtime_buffer"], "BufferPof")
            self.assertIn("POF.CPP", offset_asset["stats"]["source_provenance"])
            self.assertEqual(offset_asset["stats"]["record_count"], 2)
            self.assertEqual(offset_asset["stats"]["sampled_records"][0]["preview_hex"], b"ABCD".hex())
            impact_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:47")
            self.assertEqual(impact_asset["entry_type"], "offset-record-table")
            self.assertEqual(impact_asset["label"], "RESS_IMPACT runtime table (RESS.HQR:47)")
            self.assertEqual(impact_asset["stats"]["runtime_table_name"], "RESS_IMPACT")
            self.assertEqual(impact_asset["stats"]["runtime_buffer"], "BufferImpact")
            self.assertIn("IMPACT.CPP", impact_asset["stats"]["source_provenance"])
            raw_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:7")
            self.assertEqual(raw_asset["kind"], "resource")
            self.assertEqual(raw_asset["entry_type"], "unclassified-payload")
            self.assertEqual(raw_asset["stats"]["semantic_layout"], "ress_unclassified_payload")
            self.assertEqual(raw_asset["stats"]["preview_hex"], b"raw!".hex())
            self.assertEqual(raw_asset["stats"]["unknown_descriptors"][0]["section"], "ress_unclassified_payload")
            size_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:2")
            self.assertEqual(size_asset["entry_type"], "ext-size-info")
            self.assertEqual(size_asset["stats"]["semantic_layout"], "ress_ext_size_info")
            self.assertEqual(size_asset["stats"]["max_size_body_decors"], 18264)
            xpl_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:27")
            self.assertEqual(xpl_asset["entry_type"], "xpl-palette-bundle")
            self.assertEqual(xpl_asset["stats"]["semantic_layout"], "xpl_palette_bundle")
            self.assertEqual(xpl_asset["stats"]["xpl_name"], "Citadel")
            self.assertEqual(xpl_asset["stats"]["header"]["offset_palette"], 44)
            self.assertEqual(xpl_asset["stats"]["sample_colors"][0], 0x000102)
            orphan_xpl_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:38")
            self.assertEqual(orphan_xpl_asset["entry_type"], "xpl-palette-bundle")
            self.assertEqual(orphan_xpl_asset["stats"]["semantic_layout"], "xpl_palette_bundle")
            self.assertEqual(orphan_xpl_asset["stats"]["xpl_name"], "orphan shading palette")
            self.assertEqual(
                orphan_xpl_asset["stats"]["runtime_reference_status"],
                "no_classic_common_h_constant",
            )
            acf_asset = viewer.find_catalog_asset(catalog, "RESS.HQR:48")
            self.assertEqual(acf_asset["entry_type"], "acf-name-list")
            self.assertEqual(acf_asset["stats"]["semantic_layout"], "acf_name_list")
            self.assertEqual(acf_asset["stats"]["sampled_names"], ["INTRO.SMK", "END.SMK"])
            ress_coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "RESS.HQR"
            ][0]
            self.assertEqual(ress_coverage["unknown_entries"], 0)
            self.assertEqual(ress_coverage["semantic_unknown_entries"], 1)
            self.assertIn("lba2_palette", ress_coverage["recognized_formats"])
            self.assertIn("sprite_zv_table", ress_coverage["recognized_formats"])
            self.assertIn("lba2_indexed_image_256", ress_coverage["recognized_formats"])
            self.assertIn("ress_offset_record_table", ress_coverage["recognized_formats"])
            self.assertIn("ress_fixed_s16x8_table", ress_coverage["recognized_formats"])
            self.assertIn("file3d_table", ress_coverage["recognized_formats"])
            self.assertIn("ress_ext_size_info", ress_coverage["recognized_formats"])
            self.assertIn("xpl_palette_bundle", ress_coverage["recognized_formats"])
            self.assertIn("acf_name_list", ress_coverage["recognized_formats"])
            self.assertIn("ress_unclassified_payload", ress_coverage["recognized_formats"])
            self.assertIn("unclassified-payload", ress_coverage["unknown_formats"])

    def test_catalog_classifies_screen_hqr_palette_and_indexed_images(self) -> None:
        palette = bytes(range(256)) * 3
        image = bytes([0, 1, 2, 3]) * (640 * 480 // 4)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCREEN.HQR").write_bytes(classic_hqr([resource_entry(image), resource_entry(palette)]))

            catalog = viewer.build_catalog(root)

            image_asset = viewer.find_catalog_asset(catalog, "SCREEN.HQR:0")
            self.assertEqual(image_asset["kind"], "resource")
            self.assertEqual(image_asset["entry_type"], "screen-indexed-image")
            self.assertEqual(
                image_asset["stats"]["semantic_layout"],
                "screen_indexed_image_640x480",
            )
            self.assertEqual(image_asset["stats"]["screen_name"], "logo")
            self.assertEqual(image_asset["stats"]["width"], 640)
            self.assertEqual(image_asset["stats"]["height"], 480)
            self.assertEqual(image_asset["stats"]["unique_palette_indices"], 4)
            self.assertEqual(
                image_asset["stats"]["palette_entry"],
                {"hqr": "SCREEN.HQR", "entry_index": 1},
            )
            self.assertEqual(
                image_asset["stats"]["runtime_reference_status"],
                "classic_pcr_image_slot",
            )
            self.assertEqual(
                image_asset["stats"]["direct_code_references"][0]["symbol"],
                "PCR_LOGO",
            )
            self.assertIn(
                "startup logo",
                image_asset["stats"]["direct_code_references"][0]["purpose"],
            )

            palette_asset = viewer.find_catalog_asset(catalog, "SCREEN.HQR:1")
            self.assertEqual(palette_asset["kind"], "resource")
            self.assertEqual(palette_asset["entry_type"], "screen-palette")
            self.assertEqual(palette_asset["stats"]["semantic_layout"], "screen_palette")
            self.assertEqual(palette_asset["stats"]["screen_name"], "logo")
            self.assertEqual(palette_asset["stats"]["paired_entry_index"], 0)
            self.assertEqual(
                palette_asset["stats"]["runtime_reference_status"],
                "classic_pcr_palette_slot",
            )
            self.assertEqual(
                palette_asset["stats"]["direct_code_references"][0]["symbol"],
                "PCR_LOGO",
            )
            self.assertIn(
                "paired palette",
                palette_asset["stats"]["direct_code_references"][0]["purpose"],
            )

            screen_coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "SCREEN.HQR"
            ][0]
            self.assertEqual(screen_coverage["unknown_entries"], 0)
            self.assertEqual(screen_coverage["semantic_unknown_entries"], 0)
            self.assertIn("screen_palette", screen_coverage["recognized_formats"])
            self.assertIn("screen_indexed_image_640x480", screen_coverage["recognized_formats"])

    def test_catalog_classifies_holomap_classic_runtime_tables(self) -> None:
        uv_map = struct.pack("<1122H", *range(1122))
        altitude = bytes([0, 1, 2, 255]) * (544 // 4)
        texture = bytes([3, 4, 5, 6]) * (256 * 256 // 4)
        arrow_record = struct.pack(
            "<iiiiiiibBBB",
            10,
            20,
            30,
            40,
            50,
            60,
            70,
            -1,
            0b111,
            2,
            3,
        )
        arrow_table = arrow_record + bytes(32 * 304)
        plan_image = bytes([7, 8, 9, 10]) * (640 * 480 // 4)
        plan_params = struct.pack("<iiiiiiiii", 8, 9, 16384, 10240, 453, -407, 152000, 309, 3368)
        entries = [b""] * 20
        entries[0] = resource_entry(uv_map)
        entries[1] = resource_entry(altitude)
        entries[2] = resource_entry(texture)
        entries[12] = resource_entry(arrow_table)
        entries[18] = resource_entry(plan_image)
        entries[19] = resource_entry(plan_params)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HOLOMAP.HQR").write_bytes(classic_hqr(entries))

            catalog = viewer.build_catalog(root)

            uv_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:0")
            self.assertEqual(uv_asset["entry_type"], "holomap-globe-uv-map")
            self.assertEqual(uv_asset["stats"]["semantic_layout"], "holomap_globe_uv_map")
            self.assertEqual(uv_asset["stats"]["record_count"], 561)
            altitude_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:1")
            self.assertEqual(
                altitude_asset["stats"]["semantic_layout"],
                "holomap_globe_altitude_map",
            )
            self.assertEqual(altitude_asset["stats"]["holomap_name"], "Twinsun altitude map")
            texture_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:2")
            self.assertEqual(
                texture_asset["stats"]["semantic_layout"],
                "holomap_globe_texture_map",
            )
            self.assertEqual(texture_asset["stats"]["width"], 256)
            arrow_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:12")
            self.assertEqual(arrow_asset["entry_type"], "holomap-arrow-table")
            self.assertEqual(arrow_asset["stats"]["record_count"], 305)
            self.assertEqual(arrow_asset["stats"]["active_count"], 1)
            self.assertEqual(arrow_asset["stats"]["exterior_count"], 1)
            self.assertEqual(arrow_asset["stats"]["sampled_records"][0]["message"], 70)
            plan_image_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:18")
            self.assertEqual(
                plan_image_asset["stats"]["semantic_layout"],
                "holomap_plan_image_640x480",
            )
            self.assertEqual(plan_image_asset["stats"]["paired_entry_index"], 19)
            self.assertEqual(plan_image_asset["stats"]["holomap_name"], "Citadel")
            self.assertEqual(plan_image_asset["stats"]["plan_variant"]["selected_island"], 0)
            self.assertEqual(
                plan_image_asset["stats"]["plan_variant"]["selection_condition"],
                "ZoomedIsland == 0",
            )
            plan_params_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:19")
            self.assertEqual(
                plan_params_asset["stats"]["semantic_layout"],
                "holomap_plan_view_params",
            )
            self.assertEqual(plan_params_asset["stats"]["fields"]["alpha"], 453)
            self.assertEqual(plan_params_asset["stats"]["fields"]["beta"], -407)
            self.assertEqual(plan_params_asset["stats"]["fields"]["distance"], 152000)
            self.assertEqual(plan_params_asset["stats"]["fields"]["lalpha"], 309)
            self.assertEqual(plan_params_asset["stats"]["fields"]["lbeta"], 3368)
            self.assertEqual(plan_params_asset["stats"]["plan_variant"]["entry_role"], "params")

            holomap_coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "HOLOMAP.HQR"
            ][0]
            self.assertEqual(holomap_coverage["entry_count"], 20)
            self.assertEqual(holomap_coverage["unknown_entries"], 0)
            self.assertEqual(holomap_coverage["semantic_unknown_entries"], 0)
            self.assertIn("holomap_globe_uv_map", holomap_coverage["recognized_formats"])
            self.assertIn("holomap_arrow_table", holomap_coverage["recognized_formats"])
            self.assertIn("holomap_plan_view_params", holomap_coverage["recognized_formats"])

    def test_catalog_links_holomap_arrow_messages_to_game_text_records(self) -> None:
        arrow_record = struct.pack(
            "<iiiiiiibBBB",
            1,
            2,
            3,
            4,
            5,
            6,
            70,
            -1,
            1,
            2,
            3,
        )
        arrow_table = arrow_record + bytes(32 * 304)
        text_record = b"\x01Holomap line\x00"
        text_bank = struct.pack("<HH", 4, 4 + len(text_record)) + text_record
        text_entries = [b""] * 6
        text_entries[0] = resource_entry(struct.pack("<H", 1))
        text_entries[1] = resource_entry(struct.pack("<HH", 4, 10) + b"\x01Unused\x00")
        text_entries[4] = resource_entry(struct.pack("<H", 70))
        text_entries[5] = resource_entry(text_bank)
        holomap_entries = [b""] * 13
        holomap_entries[0] = resource_entry(bytes(viewer.HOLOMAP_GLOBE_UV_BYTES))
        holomap_entries[12] = resource_entry(arrow_table)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HOLOMAP.HQR").write_bytes(classic_hqr(holomap_entries))
            (root / "TEXT.HQR").write_bytes(classic_hqr(text_entries))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["holomap_linked_text_refs"], 1)
            self.assertEqual(
                catalog["metadata"]["holomap_text_links"]["text_file_name"], "gam"
            )
            arrow_asset = viewer.find_catalog_asset(catalog, "HOLOMAP.HQR:12")
            self.assertEqual(arrow_asset["stats"]["text_link_counts"]["arrow_message_refs"], 305)
            self.assertEqual(arrow_asset["stats"]["text_link_counts"]["unique_message_ids"], 2)
            self.assertEqual(
                arrow_asset["stats"]["text_link_counts"]["linked_unique_message_ids"], 1
            )
            self.assertEqual(arrow_asset["stats"]["text_links"][0]["message_id"], 70)
            self.assertEqual(arrow_asset["stats"]["text_links"][0]["localized_records"], 1)
            self.assertEqual(
                arrow_asset["stats"]["text_links"][0]["localized_links"][0]["preview"],
                "Holomap line",
            )
            holomap_coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "HOLOMAP.HQR"
            ][0]
            self.assertIn("holomap-text-record-links", holomap_coverage["recognized_formats"])

    def test_catalog_classifies_lba_bkg_classic_runtime_tables(self) -> None:
        header = struct.pack(
            "<HHHHHHIIII",
            1,
            2,
            3,
            4,
            2,
            1,
            9000,
            128,
            512,
            256,
        )
        grid = bkg_grid_payload()
        grm = bytes([1, 2, 1]) + struct.pack("<HH", 0x0102, 0x0304)
        block = bytes([1, 1, 1, 2, 0x10]) + struct.pack("<H", 1)
        bll = struct.pack("<I", 4) + block
        brick_a = bkg_affgraph_payload()
        brick_b = bkg_affgraph_payload()
        cube_records = bytearray(
            viewer.BKG_CUBE_MAP_RECORD_COUNT * viewer.BKG_CUBE_MAP_RECORD_BYTES
        )
        cube_records[0:2] = bytes([1, 0])
        cube_records[2:4] = bytes([2, 1])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        resource_entry(grid),
                        resource_entry(grm),
                        resource_entry(bll),
                        resource_entry(brick_a),
                        resource_entry(brick_b),
                        resource_entry(bytes(cube_records)),
                        b"",
                    ]
                )
            )

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["hqr_files"][0]["indexing"], "classic")
            self.assertEqual(catalog["summary"]["resource_assets"], 7)
            self.assertEqual(catalog["summary"]["models"], 0)
            header_asset = viewer.find_catalog_asset(catalog, "LBA_BKG.HQR:0")
            self.assertEqual(header_asset["entry_type"], "bkg-header")
            self.assertEqual(header_asset["stats"]["semantic_layout"], "bkg_header")
            self.assertEqual(header_asset["stats"]["fields"]["cube_map_entry_index"], 6)
            grid_asset = viewer.find_catalog_asset(catalog, "LBA_BKG.HQR:1")
            self.assertEqual(grid_asset["stats"]["semantic_layout"], "bkg_grid_map")
            self.assertEqual(grid_asset["stats"]["fields"]["resolved_bll_entry"], 3)
            self.assertEqual(grid_asset["stats"]["fields"]["used_block_count"], 1)
            self.assertEqual(grid_asset["stats"]["fields"]["active_columns"], 4096)
            self.assertEqual(grid_asset["stats"]["fields"]["nonzero_cells"], 4096)
            self.assertEqual(grid_asset["stats"]["fields"]["unique_column_block_refs"], 1)
            self.assertEqual(grid_asset["stats"]["fields"]["composition_bll_link_found"], 1)
            self.assertEqual(grid_asset["stats"]["fields"]["composition_invalid_block_ref_count"], 0)
            self.assertEqual(grid_asset["stats"]["sampled_occupied_cells"][0]["block_ref"], 1)
            self.assertEqual(grid_asset["stats"]["sampled_occupied_cells"][0]["cell_slot"], 0)
            grm_asset = viewer.find_catalog_asset(catalog, "LBA_BKG.HQR:2")
            self.assertEqual(grm_asset["stats"]["semantic_layout"], "bkg_grm_fragment")
            self.assertEqual(grm_asset["stats"]["record_count"], 2)
            bll_asset = viewer.find_catalog_asset(catalog, "LBA_BKG.HQR:3")
            self.assertEqual(bll_asset["stats"]["semantic_layout"], "bkg_block_table")
            self.assertEqual(bll_asset["stats"]["sampled_records"][0]["max_brick_ref"], 1)
            self.assertEqual(bll_asset["stats"]["fields"]["unique_brick_ref_count"], 1)
            self.assertEqual(bll_asset["stats"]["fields"]["nonzero_cell_refs"], 1)
            self.assertEqual(bll_asset["stats"]["fields"]["invalid_brick_ref_count"], 0)
            self.assertEqual(bll_asset["stats"]["fields"]["min_resolved_brk_entry"], 4)
            self.assertEqual(bll_asset["stats"]["fields"]["max_resolved_brk_entry"], 4)
            self.assertEqual(
                bll_asset["stats"]["sampled_cell_refs"][0]["resolved_brk_entry"], 4
            )
            self.assertEqual(
                bll_asset["stats"]["sampled_records"][0]["sampled_cell_refs"][0]["code_raw"],
                0x10,
            )
            brick_asset = viewer.find_catalog_asset(catalog, "LBA_BKG.HQR:4")
            self.assertEqual(brick_asset["stats"]["semantic_layout"], "bkg_brick_graphic")
            self.assertEqual(brick_asset["stats"]["format"], "bkg_affgraph")
            self.assertEqual(brick_asset["stats"]["width"], 4)
            self.assertEqual(brick_asset["stats"]["height"], 2)
            self.assertEqual(brick_asset["stats"]["offset_x"], 1)
            self.assertEqual(brick_asset["stats"]["offset_y"], -2)
            self.assertEqual(brick_asset["stats"]["opaque_pixels"], 7)
            self.assertEqual(brick_asset["stats"]["transparent_pixels"], 1)
            self.assertEqual(brick_asset["stats"]["run_type_counts"], {"0": 1, "1": 2, "2": 1})
            self.assertEqual(brick_asset["stats"]["unknown_descriptors"], [])
            cube_asset = viewer.find_catalog_asset(catalog, "LBA_BKG.HQR:6")
            self.assertEqual(cube_asset["stats"]["semantic_layout"], "bkg_cube_map")
            self.assertEqual(cube_asset["stats"]["record_count"], 256)
            self.assertEqual(cube_asset["stats"]["fields"]["linked_grid_records"], 255)
            self.assertEqual(cube_asset["stats"]["fields"]["missing_grid_records"], 1)
            self.assertEqual(cube_asset["stats"]["missing_grid_entries"], [2])
            self.assertEqual(cube_asset["stats"]["sampled_records"][0]["resolved_gri_entry"], 1)
            self.assertEqual(cube_asset["stats"]["sampled_records"][0]["resolved_bll_entry"], 3)
            self.assertEqual(cube_asset["stats"]["sampled_records"][0]["resolved_grm_entry"], 2)
            self.assertEqual(cube_asset["stats"]["sampled_records"][0]["used_block_count"], 1)
            coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "LBA_BKG.HQR"
            ][0]
            self.assertEqual(coverage["cataloged_entries"], 7)
            self.assertEqual(coverage["unknown_entries"], 0)
            self.assertIn("bkg_block_table", coverage["recognized_formats"])
            self.assertIn("bkg_grid_column_composition", coverage["recognized_formats"])

    def test_catalog_links_scene_runtime_cube_to_background_grid_and_palette(self) -> None:
        header = struct.pack(
            "<HHHHHHIIII",
            1,
            2,
            3,
            4,
            2,
            1,
            4096,
            9000,
            512,
            256,
        )
        grid = bkg_grid_payload()
        grm = bytes([1, 1, 1]) + struct.pack("<H", 0x0102)
        bll = struct.pack("<I", 4) + bytes([1, 1, 1, 2, 0x10]) + struct.pack("<H", 1)
        cube_records = bytearray(
            viewer.BKG_CUBE_MAP_RECORD_COUNT * viewer.BKG_CUBE_MAP_RECORD_BYTES
        )
        cube_records[0:2] = bytes([1, 0])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            grm_zone = scene_zone_record(
                start=(0, 0, 0),
                end=(0, 0, 0),
                info=(0, 0, 1, 0, 0, 0, 0, 0),
                zone_type=3,
                value=55,
            )
            (root / "SCENE.HQR").write_bytes(
                hqr([resource_entry(scene_payload(zone_records=[grm_zone]))])
            )
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        resource_entry(grid),
                        resource_entry(grm),
                        resource_entry(bll),
                        resource_entry(bkg_affgraph_payload()),
                        resource_entry(bkg_affgraph_payload()),
                        resource_entry(bytes(cube_records)),
                    ]
                )
            )

            catalog = viewer.build_catalog(root)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            background = scene_asset["stats"]["reconnaissance"]["background"]
            self.assertEqual(background["runtime_cube"], 0)
            self.assertTrue(background["cube_map_record_found"])
            self.assertEqual(background["resolved_gri_entry"], 1)
            self.assertEqual(background["resolved_bll_entry"], 3)
            self.assertEqual(background["resolved_grm_entry"], 2)
            self.assertEqual(background["used_block_count"], 1)
            self.assertEqual(background["palette"]["resolved_palette_entry"], 29)
            self.assertEqual(background["palette"]["resolved_palette_name"], "desert")
            self.assertEqual(
                catalog["metadata"]["scene_background_links"]["scene_cube_links"], 1
            )
            grm_links = scene_asset["stats"]["reconnaissance"]["grm_fragment_links"]
            self.assertEqual(len(grm_links), 1)
            self.assertEqual(grm_links[0]["zone_value"], 55)
            self.assertEqual(grm_links[0]["grm_index"], 0)
            self.assertEqual(grm_links[0]["resolved_grm_entry"], 2)
            self.assertEqual(grm_links[0]["asset_id"], "LBA_BKG.HQR:2")
            self.assertTrue(grm_links[0]["asset_available"])
            self.assertEqual(grm_links[0]["target_cell_start"], {"x": 0, "y": 0, "z": 0})
            self.assertEqual(grm_links[0]["fragment_dimensions"], {"x": 1, "y": 1, "z": 1})
            self.assertTrue(grm_links[0]["dimensions_match_zone_bounds"])
            self.assertEqual(catalog["metadata"]["scene_grm_links"]["linked_grm_fragments"], 1)
            self.assertEqual(catalog["summary"]["scene_background_cube_links"], 1)
            self.assertEqual(catalog["summary"]["scene_grm_fragment_links"], 1)
            coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "SCENE.HQR"
            ][0]
            self.assertIn("scene-background-cube-links", coverage["recognized_formats"])
            self.assertIn("scene-grm-fragment-links", coverage["recognized_formats"])
            self.assertIn("scene-object-render-pipeline", coverage["recognized_formats"])
            self.assertIn("scene-object-render-contract", coverage["recognized_formats"])

    def test_bkg_grm_fragment_application_matches_incrust_column_order(self) -> None:
        base = viewer.decode_bkg_grid_columns(bkg_grid_payload(0x0001), include_cells=True)
        fragment = viewer.decode_bkg_grm_fragment(
            bytes([2, 2, 1])
            + struct.pack("<HHHH", 0x0302, 0x0504, 0x0706, 0x0908),
            include_cells=True,
        )
        zone = {
            "start": {
                "x": viewer.BKG_WORLD_CELL_SIZE_XZ,
                "y": viewer.BKG_WORLD_CELL_SIZE_Y,
                "z": 0,
            },
            "end": {
                "x": viewer.BKG_WORLD_CELL_SIZE_XZ * 2 - 1,
                "y": viewer.BKG_WORLD_CELL_SIZE_Y * 3 - 1,
                "z": viewer.BKG_WORLD_CELL_SIZE_XZ - 1,
            },
        }

        applied = viewer.apply_bkg_grm_fragment_to_composition(
            base["flat_block_refs"],
            base["flat_cell_slots_or_codes"],
            zone,
            fragment,
        )

        def target_index(x: int, y: int, z: int) -> int:
            return (((z * viewer.BKG_CUBE_SIZE_X) + x) * viewer.BKG_CUBE_SIZE_Y) + y

        self.assertEqual(applied["applied_cell_count"], 4)
        self.assertEqual(applied["target_cell_bounds"]["x0"], 1)
        self.assertEqual(applied["target_cell_bounds"]["y0"], 1)
        self.assertEqual(applied["target_cell_bounds"]["z0"], 0)
        self.assertEqual(applied["flat_block_refs"][target_index(1, 1, 0)], 2)
        self.assertEqual(applied["flat_cell_slots_or_codes"][target_index(1, 1, 0)], 3)
        self.assertEqual(applied["flat_block_refs"][target_index(1, 2, 0)], 4)
        self.assertEqual(applied["flat_cell_slots_or_codes"][target_index(1, 2, 0)], 5)
        self.assertEqual(applied["flat_block_refs"][target_index(2, 1, 0)], 6)
        self.assertEqual(applied["flat_cell_slots_or_codes"][target_index(2, 1, 0)], 7)
        self.assertEqual(applied["flat_block_refs"][target_index(2, 2, 0)], 8)
        self.assertEqual(applied["flat_cell_slots_or_codes"][target_index(2, 2, 0)], 9)

    def test_catalog_classifies_text_hqr_dialog_tables(self) -> None:
        order = struct.pack("<HH", 10, 42)
        first_record = b"\x01Hello\x00"
        second_record = b"\x04Line 1\x01Line 2\x00"
        first_offset = 6
        payload = struct.pack(
            "<HHH",
            first_offset,
            first_offset + len(first_record),
            first_offset + len(first_record) + len(second_record),
        ) + first_record + second_record
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "TEXT.HQR").write_bytes(
                classic_hqr([resource_entry(order), resource_entry(payload)])
            )

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["hqr_files"][0]["indexing"], "classic")
            order_asset = viewer.find_catalog_asset(catalog, "TEXT.HQR:0")
            self.assertEqual(order_asset["entry_type"], "text-order-table")
            self.assertEqual(order_asset["stats"]["semantic_layout"], "text_order_table")
            self.assertEqual(order_asset["stats"]["record_count"], 2)
            self.assertEqual(order_asset["stats"]["sampled_message_ids"], [10, 42])
            text_asset = viewer.find_catalog_asset(catalog, "TEXT.HQR:1")
            self.assertEqual(text_asset["entry_type"], "text-payload-bank")
            self.assertEqual(text_asset["stats"]["semantic_layout"], "text_payload_bank")
            self.assertEqual(text_asset["stats"]["record_count"], 2)
            self.assertEqual(text_asset["stats"]["fields"]["page_break_markers"], 1)
            self.assertEqual(text_asset["stats"]["sampled_records"][1]["preview"], "Line 1\nLine 2")
            coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "TEXT.HQR"
            ][0]
            self.assertEqual(coverage["cataloged_entries"], 2)
            self.assertEqual(coverage["unknown_entries"], 0)
            self.assertIn("text_order_table", coverage["recognized_formats"])
            self.assertIn("text_payload_bank", coverage["recognized_formats"])

    def test_catalog_links_scene_dialogue_refs_to_text_records(self) -> None:
        order = struct.pack("<HH", 42, 77)
        first_record = b"\x01Scene line\x00"
        second_record = b"\x04Zone line\x00"
        first_offset = 6
        text_bank = struct.pack(
            "<HHH",
            first_offset,
            first_offset + len(first_record),
            first_offset + len(first_record) + len(second_record),
        ) + first_record + second_record
        text_entries = [b""] * 12
        text_entries[0] = resource_entry(struct.pack("<H", 1))
        text_entries[1] = resource_entry(struct.pack("<HH", 4, 11) + b"\x01Unused\x00")
        text_entries[10] = resource_entry(order)
        text_entries[11] = resource_entry(text_bank)
        scene = scene_payload(
            island=2,
            hero_life_script=bytes([25]) + struct.pack("<h", 42) + bytes([0]),
            zone_records=[
                scene_zone_record(
                    zone_type=5,
                    value=77,
                    info=(0, 0, 0, 0, 0, 0, 0, 1),
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "TEXT.HQR").write_bytes(classic_hqr(text_entries))

            catalog = viewer.build_catalog(root)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            recon = scene_asset["stats"]["reconnaissance"]
            self.assertEqual(recon["text_file_index"], 5)
            self.assertEqual(recon["text_link_counts"]["script_logical_refs"], 1)
            self.assertEqual(recon["text_link_counts"]["script_localized_refs"], 1)
            self.assertEqual(recon["text_link_counts"]["zone_logical_refs"], 1)
            self.assertEqual(recon["text_link_counts"]["zone_localized_refs"], 1)
            hero_text_link = recon["hero"]["life_script_analysis"]["text_links"][0]
            self.assertEqual(hero_text_link["asset_id"], "TEXT.HQR:11")
            self.assertEqual(hero_text_link["record_index"], 0)
            self.assertEqual(hero_text_link["preview"], "Scene line")
            zone_text_link = recon["text_zone_links"][0]
            self.assertEqual(zone_text_link["zone_index"], 0)
            self.assertEqual(zone_text_link["record_index"], 1)
            self.assertEqual(zone_text_link["preview"], "Zone line")
            text_bank_asset = viewer.find_catalog_asset(catalog, "TEXT.HQR:11")
            usage_kinds = {usage["kind"] for usage in text_bank_asset["scene_usages"]}
            self.assertIn("script_text", usage_kinds)
            self.assertIn("zone_text", usage_kinds)
            self.assertEqual(catalog["summary"]["scene_script_linked_text_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_zone_linked_text_refs"], 1)

    def test_catalog_decodes_samples_hqr_and_links_scene_audio_refs(self) -> None:
        sample_entries = [
            resource_entry(wave_payload(bytes([0x80 + index] * 8)))
            for index in range(4)
        ]
        scene = scene_payload(
            hero_track_script=bytes([14]) + struct.pack("<h", 3) + bytes([0])
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "SAMPLES.HQR").write_bytes(hqr(sample_entries))

            catalog = viewer.build_catalog(root)

            sample_asset = viewer.find_catalog_asset(catalog, "SAMPLES.HQR:3")
            self.assertEqual(sample_asset["kind"], "resource")
            self.assertEqual(sample_asset["stats"]["semantic_layout"], "sample_wave_audio")
            self.assertEqual(sample_asset["stats"]["sample_runtime_index"], 3)
            self.assertEqual(sample_asset["stats"]["fields"]["sample_rate"], 22050)
            self.assertEqual(sample_asset["stats"]["fields"]["bits_per_sample"], 8)
            self.assertEqual(sample_asset["source"]["entry_index"], 3)
            self.assertEqual(sample_asset["source"]["hqr_table_index"], 4)
            sample_payload, _ = viewer.read_hqr_payload(root, sample_asset["source"])
            self.assertTrue(sample_payload.startswith(b"RIFF"))

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            recon = scene_asset["stats"]["reconnaissance"]
            self.assertEqual(recon["sample_link_counts"]["script_linked_refs"], 1)
            self.assertEqual(recon["sample_link_counts"]["ambience_linked_refs"], 4)
            hero_sample_link = recon["hero"]["track_script_analysis"]["sample_links"][0]
            self.assertEqual(hero_sample_link["asset_id"], "SAMPLES.HQR:3")
            self.assertEqual(hero_sample_link["sample_id"], 3)
            self.assertEqual(recon["sample_ambience_links"][0]["asset_id"], "SAMPLES.HQR:0")

            usage_kinds = {usage["kind"] for usage in sample_asset["scene_usages"]}
            self.assertIn("script_sample", usage_kinds)
            self.assertIn("ambience_sample", usage_kinds)
            self.assertEqual(catalog["summary"]["scene_script_linked_sample_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_ambience_linked_sample_refs"], 4)
            sample_metadata = catalog["metadata"]["scene_sample_links"]
            self.assertEqual(sample_metadata["missing_sample_ids"], [])
            self.assertEqual(sample_metadata["missing_sample_id_details"], [])
            self.assertEqual(sample_metadata["missing_sample_status_counts"], {})
            self.assertEqual(sample_metadata["sample_archive"]["decoded_audio_entries"], 4)
            self.assertEqual(
                sample_metadata["sample_archive"]["runtime_id_rule"],
                "runtime sample id N maps to SAMPLES.HQR table slot N+1",
            )
            by_archive = {
                entry["archive"]: entry for entry in catalog["coverage"]["archives"]
            }
            self.assertEqual(by_archive["SAMPLES.HQR"]["coverage_status"], "partial")
            self.assertEqual(by_archive["SAMPLES.HQR"]["cataloged_entries"], 4)
            self.assertEqual(by_archive["SAMPLES.HQR"]["unknown_entries"], 0)
            self.assertIn(
                "sample_wave_audio", by_archive["SAMPLES.HQR"]["recognized_formats"]
            )
            self.assertIn(
                "scene-sample-audio-links", by_archive["SCENE.HQR"]["recognized_formats"]
            )

    def test_catalog_audits_missing_scene_sample_refs_by_reason(self) -> None:
        scene = scene_payload(
            hero_track_script=bytes([14]) + struct.pack("<h", 4) + bytes([0])
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "SAMPLES.HQR").write_bytes(
                hqr([resource_entry(wave_payload()), b""])
            )

            catalog = viewer.build_catalog(root)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            recon = scene_asset["stats"]["reconnaissance"]
            self.assertEqual(recon["sample_link_counts"]["script_logical_refs"], 1)
            self.assertEqual(recon["sample_link_counts"]["script_missing_refs"], 1)
            self.assertEqual(recon["sample_link_counts"]["ambience_logical_refs"], 4)
            self.assertEqual(recon["sample_link_counts"]["ambience_linked_refs"], 1)
            self.assertEqual(recon["sample_link_counts"]["ambience_missing_refs"], 3)

            hero_missing = recon["hero"]["track_script_analysis"]["missing_sample_links"][0]
            self.assertEqual(hero_missing["sample_id"], 4)
            self.assertEqual(hero_missing["status"], "outside_archive_table")
            ambience_missing_by_id = {
                link["sample_id"]: link for link in recon["sample_ambience_missing_links"]
            }
            self.assertEqual(
                ambience_missing_by_id[1]["status"], "empty_or_undecoded_hqr_slot"
            )
            self.assertEqual(ambience_missing_by_id[1]["hqr_table_index"], 2)
            self.assertEqual(ambience_missing_by_id[2]["status"], "outside_archive_table")
            self.assertEqual(ambience_missing_by_id[3]["status"], "outside_archive_table")

            sample_metadata = catalog["metadata"]["scene_sample_links"]
            self.assertEqual(sample_metadata["missing_sample_ids"], [1, 2, 3, 4])
            statuses_by_id = {
                detail["sample_id"]: detail["status"]
                for detail in sample_metadata["missing_sample_id_details"]
            }
            self.assertEqual(statuses_by_id[1], "empty_or_undecoded_hqr_slot")
            self.assertEqual(statuses_by_id[4], "outside_archive_table")
            self.assertEqual(
                sample_metadata["missing_sample_status_counts"],
                {"empty_or_undecoded_hqr_slot": 1, "outside_archive_table": 3},
            )
            self.assertEqual(sample_metadata["observed_sample_id_max"], 4)
            self.assertEqual(sample_metadata["sample_archive"]["highest_runtime_sample_id"], 1)

    def test_catalog_decodes_video_hqr_and_links_scene_acf_refs(self) -> None:
        ress_entries = [b""] * 48
        ress_entries[47] = resource_entry(b"INTRO.SMK\r\nBABY.SMK\r\n")
        scene = scene_payload(
            hero_track_script=bytes([30]) + b"intro\x00" + bytes([0])
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "RESS.HQR").write_bytes(hqr(ress_entries))
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            video_dir = root / "VIDEO"
            video_dir.mkdir()
            (video_dir / "VIDEO.HQR").write_bytes(
                hqr([resource_entry(smacker_payload(frames=45)), b""])
            )

            catalog = viewer.build_catalog(root)

            video_asset = viewer.find_catalog_asset(catalog, "VIDEO/VIDEO.HQR:0")
            self.assertEqual(video_asset["kind"], "resource")
            self.assertEqual(video_asset["entry_type"], "smacker-video")
            self.assertEqual(video_asset["stats"]["semantic_layout"], "smacker_video")
            self.assertEqual(video_asset["stats"]["acf_name"], "INTRO.SMK")
            self.assertEqual(video_asset["stats"]["acf_index"], 0)
            self.assertEqual(video_asset["stats"]["width"], 320)
            self.assertEqual(video_asset["stats"]["height"], 200)
            self.assertEqual(video_asset["stats"]["frame_count"], 45)
            self.assertEqual(video_asset["source"]["hqr_table_index"], 1)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            recon = scene_asset["stats"]["reconnaissance"]
            self.assertEqual(recon["video_link_counts"]["script_linked_refs"], 1)
            video_link = recon["hero"]["track_script_analysis"]["video_links"][0]
            self.assertEqual(video_link["asset_id"], "VIDEO/VIDEO.HQR:0")
            self.assertEqual(video_link["acf_index"], 0)

            usage_kinds = {usage["kind"] for usage in video_asset["scene_usages"]}
            self.assertIn("script_video", usage_kinds)
            self.assertEqual(catalog["summary"]["scene_script_linked_video_refs"], 1)
            self.assertEqual(
                catalog["metadata"]["scene_video_links"]["missing_acf_names"], []
            )
            video_summary = next(
                item for item in catalog["hqr_files"] if item["path"] == "VIDEO/VIDEO.HQR"
            )
            self.assertEqual(video_summary["indexing"], "runtime-zero-based")
            self.assertEqual(video_summary["acf_names_without_payload"], ["BABY.SMK"])
            by_archive = {
                entry["archive"]: entry for entry in catalog["coverage"]["archives"]
            }
            self.assertEqual(by_archive["VIDEO.HQR"]["cataloged_entries"], 1)
            self.assertEqual(by_archive["VIDEO.HQR"]["unknown_entries"], 0)
            self.assertIn(
                "smacker_video", by_archive["VIDEO.HQR"]["recognized_formats"]
            )
            self.assertIn(
                "scene-video-links", by_archive["SCENE.HQR"]["recognized_formats"]
            )

    def test_catalog_adds_hqr_coverage_matrix(self) -> None:
        scene = scene_payload()
        text_order = resource_entry(struct.pack("<H", 7))
        text_payload = resource_entry(struct.pack("<HH", 4, 10) + b"\x01Text\x00")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "TEXT.HQR").write_bytes(classic_hqr([text_order, text_payload]))
            (root / "LBA2.HQR").write_bytes(hqr([b""]))

            catalog = viewer.build_catalog(root)

            coverage = catalog["coverage"]
            self.assertEqual(coverage["schema"], "lba2-hqr-coverage-v1")
            self.assertEqual(coverage["archive_count"], 3)
            by_archive = {entry["archive"]: entry for entry in coverage["archives"]}
            self.assertEqual(by_archive["SCENE.HQR"]["coverage_status"], "partial")
            self.assertEqual(by_archive["SCENE.HQR"]["cataloged_entries"], 1)
            self.assertEqual(by_archive["SCENE.HQR"]["semantic_unknown_entries"], 1)
            self.assertIn("scene-runtime-layout-partial", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-object-movement-info", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-object-render-pipeline", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-object-render-contract", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-runtime-draw-sources", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-opcode-layout", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-behavior-partial", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-operand-semantics-partial", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-control-flow-links", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-cross-links", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-condition-functions", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-script-condition-comparators", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-track-patch-layout", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-patch-instruction-links", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-patch-field-links", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-behavior-partial", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-change-cube-contract", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-message-facing-gates", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-bonus-contract", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-hit-contract", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-movement-contracts", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-grm-contract", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-zone-scenario-contract", by_archive["SCENE.HQR"]["recognized_formats"])
            self.assertIn("scene-behavior-semantics", by_archive["SCENE.HQR"]["unknown_formats"])
            self.assertEqual(by_archive["TEXT.HQR"]["coverage_status"], "partial")
            self.assertEqual(by_archive["TEXT.HQR"]["unknown_entries"], 0)
            self.assertIn("text_order_table", by_archive["TEXT.HQR"]["recognized_formats"])
            self.assertIn("text_payload_bank", by_archive["TEXT.HQR"]["recognized_formats"])
            self.assertEqual(by_archive["LBA2.HQR"]["coverage_status"], "empty")

    def test_catalog_reconnoiters_scene_hqr_entries(self) -> None:
        hero_track = bytes([2, 7, 3]) + struct.pack("<H", 4) + bytes([0])
        hero_life = (
            bytes([17, 7, 19])
            + struct.pack("<H", 4)
            + bytes([84])
            + struct.pack("<h", 127)
            + bytes([0])
        )
        object_track = bytes([38]) + struct.pack("<h", 127) + bytes([0])
        object_life = bytes([23]) + struct.pack("<h", 12) + bytes([0])
        object_record = scene_object_record(
            flags=(1 << 0) | (1 << 1) | (1 << 11),
            option_flags=16 | 32,
            beta=256,
            srot=10,
            move=3,
            hit_force=7,
            bonus_count=2,
            armor=4,
            life_points=9,
            track_script=object_track,
            life_script=object_life,
        )
        zone = scene_zone_record(
            start=(10, 20, 30),
            end=(40, 50, 60),
            info=(0, 0, 0, 0, 0, 1, 0, 1),
            zone_type=0,
            value=9,
        )
        track = scene_track_record((70, 80, 90))
        base_data = scene_payload(
            island=4,
            cube_x=21,
            cube_y=22,
            start=(1, 2, 3),
            hero_track_script=hero_track,
            hero_life_script=hero_life,
            object_records=[object_record],
            zone_records=[zone],
            track_records=[track, scene_track_record((71, 81, 91))],
        )
        patch_target = viewer.parse_scene_reconnaissance(base_data)["hero"][
            "track_script_offset"
        ]
        data = scene_payload(
            island=4,
            cube_x=21,
            cube_y=22,
            start=(1, 2, 3),
            hero_track_script=hero_track,
            hero_life_script=hero_life,
            object_records=[object_record],
            zone_records=[zone],
            track_records=[track, scene_track_record((71, 81, 91))],
            patch_records=[scene_patch_record(2, patch_target)],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(data)]))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["scene_assets"], 1)
            asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            self.assertEqual(asset["kind"], "scene")
            self.assertEqual(asset["entry_type"], "scene-runtime")
            self.assertEqual(asset["label"], "Scene 0 (SCENE.HQR:1)")
            self.assertTrue(asset["features"]["scene_runtime"])
            stats = asset["stats"]
            self.assertEqual(stats["parse_status"], "partial")
            self.assertEqual(stats["decode_status"], "partial")
            self.assertEqual(stats["semantic_layout"], "scene_runtime_layout_partial")
            self.assertIn("source-backed runtime contracts", stats["decode_note"])
            self.assertIn("script behavior execution remains raw evidence", stats["decode_note"])
            recon = stats["reconnaissance"]
            self.assertEqual(recon["world"]["island"], 4)
            self.assertEqual(recon["world"]["cube_x"], 21)
            self.assertEqual(recon["world"]["cube_y"], 22)
            self.assertEqual(recon["world"]["unknown_world_byte"], 9)
            self.assertIn("DISKFUNC.CPP::LoadScene", recon["world"]["runtime_environment"]["source_provenance"])
            self.assertIn("3DExt", recon["world"]["runtime_environment"]["cube_coordinate_effect"])
            self.assertEqual(recon["world"]["runtime_environment"]["post_cube_mode_byte"], 9)
            self.assertIn(
                "no source-backed runtime use",
                recon["world"]["runtime_environment"]["post_cube_mode_byte_status"],
            )
            self.assertIn(
                "SetLightVector",
                recon["ambience"]["runtime_audio_lighting"]["lighting_effect"],
            )
            self.assertIn(
                "TimerRefHR",
                recon["ambience"]["runtime_audio_lighting"]["ambient_timer_rule"],
            )
            self.assertIn(
                "255",
                recon["ambience"]["runtime_audio_lighting"]["music_rule"],
            )
            self.assertEqual(recon["hero"]["start"], {"x": 1, "y": 2, "z": 3})
            self.assertEqual(recon["hero"]["track_script_bytes"], len(hero_track))
            self.assertEqual(recon["hero"]["life_script_bytes"], len(hero_life))
            self.assertEqual(
                recon["hero"]["track_script_sha256"],
                hashlib.sha256(hero_track).hexdigest(),
            )
            self.assertEqual(
                recon["hero"]["life_script_sha256"],
                hashlib.sha256(hero_life).hexdigest(),
            )
            self.assertEqual(recon["hero"]["track_script_analysis"]["status"], "decoded")
            self.assertEqual(recon["hero"]["track_script_analysis"]["instruction_count"], 3)
            self.assertEqual(
                recon["hero"]["track_script_analysis"]["behavior_categories"],
                [
                    {"category": "control_flow", "count": 1},
                    {"category": "model_animation", "count": 2},
                ],
            )
            self.assertEqual(
                recon["hero"]["track_script_analysis"]["references"]["body"],
                [7],
            )
            self.assertEqual(
                recon["hero"]["track_script_analysis"]["references"]["animation"],
                [4],
            )
            self.assertEqual(
                recon["hero"]["track_script_analysis"]["first_instructions"][0]["operand_semantics"],
                {"body_id": 7},
            )
            self.assertEqual(
                recon["hero"]["track_script_analysis"]["first_instructions"][1]["operand_semantics"],
                {"animation_id": 4},
            )
            self.assertEqual(recon["hero"]["life_script_analysis"]["status"], "decoded")
            self.assertEqual(recon["hero"]["life_script_analysis"]["instruction_count"], 4)
            self.assertEqual(recon["script_behavior_counts"]["model_animation"], 4)
            self.assertEqual(recon["script_behavior_counts"]["sprite_3d_state"], 2)
            self.assertEqual(recon["script_behavior_counts"]["movement_path"], 1)
            self.assertEqual(
                recon["script_execution_contract_counts"],
                {"life_pass_control": 2, "track_pass_control": 2},
            )
            self.assertEqual(
                recon["hero"]["life_script_analysis"]["references"]["sprite"],
                [127],
            )
            self.assertEqual(
                recon["hero"]["life_script_analysis"]["first_instructions"][2]["operand_semantics"],
                {"sprite_id": 127},
            )
            self.assertEqual(recon["object_count"], 2)
            frame_contract = recon["scene_frame_render_contract"]
            self.assertEqual(frame_contract["scene_object_records"], 1)
            self.assertIn(
                "scene_objects_from_SCENE_HQR",
                frame_contract["hqr_backed_sources"],
            )
            self.assertIn(
                "ListExtra temporary bonuses/projectiles/effects",
                frame_contract["runtime_dynamic_sources"],
            )
            self.assertIn(
                "TYPE_EXTRA runtime extras",
                frame_contract["sorted_tree_sources"],
            )
            dynamic_sources = {
                source["name"]: source
                for source in frame_contract["runtime_dynamic_source_details"]
            }
            self.assertEqual(
                dynamic_sources["ListExtra"]["sorted_tree_types"],
                ["TYPE_EXTRA", "TYPE_LABY", "TYPE_SHADOW"],
            )
            self.assertEqual(
                dynamic_sources["ListPartFlow"]["asset_backing"],
                "runtime particle flow state uses RESS_FLOW/TabPartFlow support data; records are not serialized in SCENE.HQR",
            )
            self.assertEqual(
                dynamic_sources["ListIncrustDisp"]["insertion_stage"],
                "after BaseSort and exterior rain",
            )
            self.assertIn(
                "SCENE.HQR can only enumerate scene object candidates; extras, darts, flows, and incrust displays are runtime state.",
                frame_contract["preview_limitations"],
            )
            self.assertEqual(recon["object_render_type_counts"], {"body_model": 1})
            self.assertEqual(recon["object_move_counts"], {"MOVE_TRACK": 1})
            self.assertEqual(
                recon["object_flag_counts"],
                {"CHECK_OBJ_COL": 1, "CHECK_BRICK_COL": 1, "OBJ_FALLABLE": 1},
            )
            self.assertEqual(
                recon["object_option_flag_counts"],
                {"EXTRA_GIVE_MONEY": 1, "EXTRA_GIVE_LIFE": 1},
            )
            self.assertEqual(
                recon["object_render_pipeline_counts"],
                {"casts_shadow_when_shadow_enabled": 1},
            )
            sampled_object = recon["sampled_objects"][0]
            self.assertEqual(sampled_object["runtime"]["render_type"], "body_model")
            self.assertEqual(sampled_object["runtime"]["flags"], [
                "CHECK_OBJ_COL",
                "CHECK_BRICK_COL",
                "OBJ_FALLABLE",
            ])
            self.assertEqual(sampled_object["runtime"]["option_flags"], [
                "EXTRA_GIVE_MONEY",
                "EXTRA_GIVE_LIFE",
            ])
            self.assertEqual(sampled_object["runtime"]["movement"]["mode_name"], "MOVE_TRACK")
            self.assertEqual(sampled_object["runtime"]["movement"]["initial_beta"], 256)
            self.assertEqual(sampled_object["runtime"]["movement"]["srot_scene_value"], 10)
            self.assertEqual(sampled_object["runtime"]["movement"]["srot_runtime_value"], 5120)
            self.assertEqual(
                sampled_object["runtime"]["movement"]["srot_conversion"],
                "non_sprite_non_wagon_51200_divisor",
            )
            self.assertEqual(sampled_object["runtime"]["combat"]["hit_force"], 7)
            self.assertEqual(sampled_object["runtime"]["combat"]["armor"], 4)
            self.assertEqual(sampled_object["runtime"]["combat"]["life_points"], 9)
            self.assertEqual(sampled_object["runtime"]["bonus"]["count"], 2)
            self.assertEqual(
                sampled_object["runtime"]["movement"]["state_fields"][0]["role"],
                "own_track_script_driver",
            )
            self.assertEqual(
                sampled_object["runtime"]["render_pipeline"]["draw_path"],
                "ObjectDisplay",
            )
            self.assertEqual(
                sampled_object["runtime"]["render_pipeline"]["recovery_path"],
                "DrawRecover unless OBJ_ZBUFFER or OBJ_IN_WATER",
            )
            self.assertEqual(
                recon["object_movement_state_counts"],
                {"MOVE_TRACK.own_track_script_driver": 1},
            )
            self.assertEqual(
                recon["object_collision_counts"],
                {"object": 1, "brick": 1},
            )
            self.assertEqual(
                recon["object_srot_conversion_counts"],
                {"non_sprite_non_wagon_51200_divisor": 1},
            )
            self.assertEqual(
                recon["object_combat_counts"],
                {
                    "alive": 1,
                    "armor_nonzero": 1,
                    "bonus_count_nonzero": 1,
                    "hit_force_nonzero": 1,
                },
            )
            self.assertEqual(sampled_object["track_script_bytes"], len(object_track))
            self.assertEqual(sampled_object["life_script_bytes"], len(object_life))
            self.assertEqual(
                sampled_object["track_script_sha256"],
                hashlib.sha256(object_track).hexdigest(),
            )
            self.assertEqual(
                sampled_object["life_script_sha256"],
                hashlib.sha256(object_life).hexdigest(),
            )
            self.assertEqual(sampled_object["track_script_analysis"]["status"], "decoded")
            self.assertEqual(
                sampled_object["track_script_analysis"]["references"]["sprite"],
                [127],
            )
            self.assertEqual(
                sampled_object["track_script_analysis"]["first_instructions"][0]["operand_semantics"],
                {"sprite_id": 127},
            )
            self.assertEqual(sampled_object["life_script_analysis"]["status"], "decoded")
            self.assertEqual(
                sampled_object["life_script_analysis"]["references"]["script_offset"],
                [12],
            )
            self.assertEqual(
                sampled_object["life_script_analysis"]["first_instructions"][0]["operand_semantics"],
                {"target_track_offset": 12},
            )
            self.assertEqual(recon["zone_count"], 1)
            self.assertEqual(recon["zone_type_counts"], {"change_cube": 1})
            self.assertEqual(recon["zone_effect_counts"], {"change_cube": 1})
            sampled_zone = recon["sampled_zones"][0]
            self.assertEqual(sampled_zone["type_name"], "change_cube")
            self.assertEqual(sampled_zone["value"], 9)
            self.assertEqual(sampled_zone["start"], {"x": 10, "y": 20, "z": 30})
            self.assertEqual(sampled_zone["end"], {"x": 40, "y": 50, "z": 60})
            self.assertTrue(sampled_zone["load_rules"]["change_cube_test_brick"])
            self.assertTrue(sampled_zone["load_rules"]["starts_on"])
            self.assertEqual(sampled_zone["runtime"]["effect"], "change_cube")
            self.assertEqual(
                sampled_zone["runtime"]["trigger"],
                "hero_inside_enabled_zone_after_first_loop",
            )
            self.assertEqual(sampled_zone["runtime"]["fields"]["target_cube"], 9)
            self.assertEqual(
                sampled_zone["runtime"]["change_cube_application"]["new_cube"],
                "NewCube = zone.Num",
            )
            self.assertIn(
                "NewPosY",
                sampled_zone["runtime"]["change_cube_application"]["new_position_y"],
            )
            self.assertEqual(
                sampled_zone["runtime"]["script_controls"][0]["opcode"],
                "LM_SET_CHANGE_CUBE",
            )
            self.assertEqual(recon["track_count"], 2)
            self.assertEqual(recon["sampled_tracks"][0]["position"], {"x": 70, "y": 80, "z": 90})
            self.assertEqual(recon["patch_count"], 1)
            self.assertEqual(recon["patch_size_counts"], {"2": 1})
            self.assertEqual(recon["patch_target_counts"], {"track": 1})
            sampled_patch = recon["sampled_patches"][0]
            self.assertEqual(sampled_patch["size"], 2)
            self.assertEqual(sampled_patch["target_offset"], patch_target)
            self.assertEqual(sampled_patch["target"]["kind"], "track")
            self.assertEqual(sampled_patch["target"]["owner"], "hero")
            self.assertEqual(stats["unknown_descriptors"][0]["section"], "scene_parsed_prefix")

    def test_scene_object_render_pipeline_semantics_name_classic_draw_flags(self) -> None:
        flags = (
            viewer.SPRITE_3D_FLAG
            | viewer.SPRITE_CLIP_FLAG
            | viewer.INVISIBLE_FLAG
            | viewer.NO_SHADOW_FLAG
            | viewer.OBJ_BACKGROUND_FLAG
            | viewer.NO_PRE_CLIP_FLAG
            | viewer.OBJ_ZBUFFER_FLAG
            | viewer.OBJ_IN_WATER_FLAG
        )
        recon = viewer.parse_scene_reconnaissance(
            scene_payload(object_records=[scene_object_record(flags=flags)])
        )

        self.assertEqual(
            recon["object_render_pipeline_counts"],
            {
                "invisible_skips_draw": 1,
                "sprite_clip_fixed_zone": 1,
                "background_incrust_copy_to_screen": 1,
                "zbuffer_or_water_flag_present": 1,
                "no_pre_clip_tree_sort": 1,
                "shadow_suppressed": 1,
            },
        )
        self.assertEqual(
            recon["object_render_contract_counts"],
            {
                "aff_scene_object_only_background_presence_probe": 1,
                "aff_scene_invisible_skip_before_tree": 1,
            },
        )
        runtime = recon["sampled_objects"][0]["runtime"]
        self.assertEqual(runtime["render_type"], "projected_sprite")
        pipeline = runtime["render_pipeline"]
        self.assertEqual(pipeline["draw_path"], "PtrAffGraph projected sprite")
        self.assertEqual(pipeline["sort_key"], "SORT_NO_PRECLIP")
        self.assertEqual(
            pipeline["recovery_path"],
            "DrawRecover3 from LastAnimStep after fixed sprite clip",
        )
        self.assertTrue(pipeline["invisible_skips_draw"])
        self.assertTrue(pipeline["background_incrust_once"])
        self.assertEqual(pipeline["background_toggle_opcodes"], ["LM_BACKGROUND", "TM_BACKGROUND"])
        self.assertTrue(pipeline["zbuffer_or_water"])
        self.assertTrue(pipeline["uses_zbuffer"])
        self.assertTrue(pipeline["in_water"])
        self.assertFalse(pipeline["uses_moving_box_instead_of_recover"])
        self.assertTrue(pipeline["sprite_clip_uses_info_rect"])
        self.assertFalse(pipeline["casts_shadow"])
        self.assertEqual(
            pipeline["contract_steps"],
            [
                "aff_scene_object_only_background_presence_probe",
                "aff_scene_invisible_skip_before_tree",
            ],
        )
        self.assertEqual(pipeline["redraw_contract"]["method"], "DrawRecover3")
        self.assertEqual(pipeline["redraw_contract"]["anchor"], "Obj.LastAnimStepX/Y/Z")
        self.assertFalse(pipeline["redraw_contract"]["moving_box"])
        self.assertTrue(pipeline["redraw_contract"]["zbuffer_or_water_flag_present"])
        self.assertFalse(pipeline["redraw_contract"]["zbuffer_or_water_effective"])
        self.assertTrue(pipeline["background_copy"]["object_only_flip_skip"])

    def test_scene_object_render_contract_distinguishes_effective_zbuffer_path(self) -> None:
        recon = viewer.parse_scene_reconnaissance(
            scene_payload(
                object_records=[
                    scene_object_record(flags=viewer.SPRITE_3D_FLAG | viewer.OBJ_ZBUFFER_FLAG),
                    scene_object_record(flags=viewer.ANIM_3DS_FLAG | viewer.OBJ_ZBUFFER_FLAG),
                ]
            )
        )

        self.assertEqual(
            recon["object_render_pipeline_counts"],
            {
                "casts_shadow_when_shadow_enabled": 2,
                "zbuffer_or_water_flag_present": 2,
                "zbuffer_or_water_moving_box": 1,
            },
        )
        self.assertEqual(
            recon["object_render_contract_counts"],
            {
                "aff_scene_camera_preclip": 2,
                "aff_scene_tree_insert_preclip_sort": 2,
                "shadow_candidate_insert_or_inline_draw": 2,
                "aff_one_object_draw_sprite_ptraffgraph": 1,
                "redraw_draw_over_brick_cage_and_moving_box": 1,
                "aff_one_object_draw_anim3ds_affgraph": 1,
                "redraw_drawrecover3_object_max_corner": 1,
            },
        )
        self.assertEqual(
            recon["object_redraw_method_counts"],
            {"DrawOverBrickCage + BoxMovingAdd": 1, "DrawRecover3": 1},
        )
        sprite_pipeline = recon["sampled_objects"][0]["runtime"]["render_pipeline"]
        self.assertEqual(
            sprite_pipeline["recovery_path"],
            "DrawOverBrickCage plus BoxMovingAdd after projected sprite draw",
        )
        self.assertTrue(sprite_pipeline["redraw_contract"]["zbuffer_or_water_effective"])
        self.assertTrue(sprite_pipeline["redraw_contract"]["moving_box"])
        anim3ds_pipeline = recon["sampled_objects"][1]["runtime"]["render_pipeline"]
        self.assertEqual(anim3ds_pipeline["draw_path"], "AffGraph(GetPtrAnim3DS)")
        self.assertEqual(anim3ds_pipeline["redraw_contract"]["method"], "DrawRecover3")
        self.assertFalse(anim3ds_pipeline["redraw_contract"]["zbuffer_or_water_effective"])

    def test_scene_catalog_compaction_keeps_script_link_counts_with_samples(self) -> None:
        script = {
            "control_flow_links": [{"source_offset": index} for index in range(20)],
            "cross_script_links": [{"source_offset": index} for index in range(18)],
            "local_links": [{"reference_value": index} for index in range(14)],
            "asset_links": [{"reference_value": index} for index in range(17)],
            "first_instructions": [{"offset": index} for index in range(13)],
            "unique_opcodes": [{"opcode": index} for index in range(25)],
            "runtime_state_fields": [{"field": index} for index in range(13)],
            "label_definitions": [{"label": index} for index in range(13)],
        }

        viewer.compact_scene_script_analysis_for_catalog(script)

        self.assertEqual(script["control_flow_links_total"], 20)
        self.assertEqual(len(script["control_flow_links"]), 12)
        self.assertEqual(script["cross_script_links_total"], 18)
        self.assertEqual(len(script["cross_script_links"]), 12)
        self.assertEqual(script["local_links_total"], 14)
        self.assertEqual(len(script["local_links"]), 12)
        self.assertEqual(script["asset_links_total"], 17)
        self.assertEqual(len(script["asset_links"]), 16)
        self.assertEqual(script["first_instructions_total"], 13)
        self.assertEqual(len(script["first_instructions"]), 12)
        self.assertEqual(script["unique_opcodes_total"], 25)
        self.assertEqual(len(script["unique_opcodes"]), 24)
        self.assertEqual(script["runtime_state_fields_total"], 13)
        self.assertEqual(len(script["runtime_state_fields"]), 12)
        self.assertEqual(script["label_definitions_total"], 13)
        self.assertEqual(len(script["label_definitions"]), 12)
        self.assertEqual(
            script["catalog_truncated_lists"]["control_flow_links"],
            {"total": 20, "sampled": 12},
        )

    def test_scene_catalog_compaction_samples_large_object_lists(self) -> None:
        catalog = {
            "assets": [
                {
                    "kind": "scene",
                    "stats": {
                        "reconnaissance": {
                            "hero": {},
                            "sampled_objects": [
                                {"index": index, "track_script_analysis": {"first_instructions": []}}
                                for index in range(30)
                            ],
                        }
                    },
                }
            ]
        }

        viewer.compact_scene_catalog_payload(catalog)

        recon = catalog["assets"][0]["stats"]["reconnaissance"]
        self.assertEqual(len(recon["sampled_objects"]), 24)
        self.assertEqual(recon["sampled_objects"][-1]["index"], 23)
        self.assertEqual(recon["catalog_sampled_object_limit"], 24)

    def test_scene_zone_runtime_semantics_name_classic_zone_types(self) -> None:
        zones = [
            scene_zone_record(info=(100, 200, 300, 2, 77, 1, 1, 1), zone_type=0, value=9),
            scene_zone_record(info=(1, 2, 3, 4, 5, 6, 9, 9), zone_type=1, value=12),
            scene_zone_record(zone_type=2, value=33),
            scene_zone_record(info=(44, 0, 1, 0, 0, 0, 0, 0), zone_type=3, value=55),
            scene_zone_record(info=(16 | 32, 3, 0, 0, 0, 0, 0, 0), zone_type=4, value=0),
            scene_zone_record(info=(0, 12, 4, 0, 0, 0, 0, 0), zone_type=5, value=99),
            scene_zone_record(info=(1, 0, 0, 0, 0, 0, 0, 0), zone_type=6, value=0),
            scene_zone_record(info=(0, 1, 8, 0, 0, 0, 0, 0), zone_type=7, value=0),
            scene_zone_record(info=(0, 6, 7, 123, 0, 0, 0, 0), zone_type=8, value=0),
            scene_zone_record(info=(1, 0, 0, 0, 0, 0, 0, 0), zone_type=9, value=0),
        ]
        recon = viewer.parse_scene_reconnaissance(scene_payload(zone_records=zones))
        runtime = [zone["runtime"] for zone in recon["sampled_zones"]]

        self.assertEqual(recon["zone_effect_counts"]["change_cube"], 1)
        self.assertEqual(recon["zone_effect_counts"]["show_message"], 1)
        self.assertEqual(
            recon["zone_runtime_contract_counts"],
            {
                "change_cube": 1,
                "camera": 1,
                "scenario": 1,
                "grm": 1,
                "bonus": 1,
                "message": 1,
                "ladder": 1,
                "escalator": 1,
                "hit": 1,
                "rail": 1,
            },
        )
        self.assertEqual([item["effect"] for item in runtime], [
            "change_cube",
            "camera_zone",
            "set_object_scenario_zone",
            "toggle_grm_fragment",
            "give_bonus_extra",
            "show_message",
            "ladder_climb",
            "escalator_conveyor",
            "hit_object",
            "wagon_rail_zone",
        ])
        self.assertEqual(runtime[0]["fields"]["script_control_id"], 77)
        self.assertIn(
            "FlagChgCube = 1",
            runtime[0]["change_cube_application"]["success_flag"],
        )
        self.assertIn("Info4", runtime[0]["change_cube_application"]["script_control"])
        self.assertEqual(
            runtime[0]["load_state"]["post_load_info7_flags"],
            ["ZONE_INIT_ON", "ZONE_ON"],
        )
        self.assertFalse(runtime[0]["load_state"]["active_after_load"])
        self.assertEqual(runtime[1]["fields"]["mandatory"], True)
        self.assertEqual(
            runtime[1]["load_state"]["post_load_info7_flags"],
            ["ZONE_INIT_ON", "ZONE_ON", "ZONE_OBLIGATOIRE"],
        )
        self.assertEqual(
            runtime[1]["camera_application"]["start_cube_fields"],
            {"StartXCube": 1, "StartYCube": 2, "StartZCube": 3},
        )
        self.assertEqual(
            runtime[1]["camera_application"]["exterior_camera_fields"],
            {"AlphaCam": 4, "BetaCam": 5, "GammaCam": 6, "VueDistance": 9},
        )
        self.assertIn(
            "Exterior cubes also apply AlphaCam",
            runtime[1]["camera_application"]["exterior_rule"],
        )
        self.assertEqual(runtime[2]["runtime_readers"], ["LF_ZONE", "LF_ZONE_OBJ"])
        self.assertEqual(
            runtime[2]["scenario_application"]["write_rule"],
            "When an object is inside a Type==2 scenario zone, ptrobj->ZoneSce = zone.Num.",
        )
        self.assertEqual(
            runtime[2]["scenario_application"]["self_reader"],
            "LF_ZONE returns the current object's ZoneSce.",
        )
        self.assertEqual(runtime[3]["script_controls"][0]["opcode"], "LM_SET_GRM")
        self.assertEqual(runtime[3]["load_state"]["post_load_info1"], 0)
        self.assertIn("IncrustGrm(zone)", runtime[3]["grm_application"]["on_transition"])
        self.assertIn("DesIncrustGrm(zone)", runtime[3]["grm_application"]["off_transition"])
        self.assertEqual(runtime[3]["grm_application"]["state_field"], "Info2")
        self.assertEqual(runtime[4]["fields"]["spawn_position"], {"x": 5, "y": 20, "z": 15})
        self.assertEqual(
            runtime[4]["fields"]["bonus_selector_flags"],
            ["EXTRA_GIVE_MONEY", "EXTRA_GIVE_LIFE"],
        )
        self.assertFalse(runtime[4]["load_state"]["already_taken_after_load"])
        self.assertIn("WhichBonus(Info0)", runtime[4]["bonus_application"]["bonus_selection"])
        self.assertEqual(
            runtime[4]["bonus_application"]["success_state_change"],
            "Only when ExtraBonus returns a slot, ListExtra[p].Flags gains EXTRA_TIME_IN and zone Info2 is set to 1.",
        )
        self.assertEqual(runtime[5]["fields"]["facing_direction"], "east")
        self.assertTrue(runtime[5]["message_application"]["requires_action_normal"])
        self.assertEqual(
            runtime[5]["message_application"]["direction_rule"]["angle_points"],
            {
                "angle": {"x": "X1", "z": "Z0"},
                "angle1": {"x": "X1", "z": "Z1"},
            },
        )
        self.assertEqual(
            runtime[5]["message_application"]["direction_rule"]["beta_condition"],
            "Obj.Beta >= angle1 && Obj.Beta <= angle",
        )
        self.assertEqual(
            runtime[5]["message_application"]["dialogue_call"], "Dial(zone.Num, TRUE)"
        )
        self.assertEqual(runtime[6]["fields"]["top_y"], 20)
        self.assertTrue(runtime[6]["fields"]["runtime_active"])
        self.assertFalse(runtime[6]["fields"]["serialized_runtime_active"])
        self.assertEqual(
            runtime[6]["ladder_application"]["runtime_pointer"],
            "PtrZoneClimb is assigned to the active ladder zone.",
        )
        self.assertIn("CLIMBING_UP", runtime[6]["ladder_application"]["up_effect"])
        self.assertEqual(runtime[6]["script_controls"][0]["opcode"], "LM_ECHELLE")
        self.assertEqual(runtime[7]["fields"]["direction"], "west")
        self.assertEqual(
            runtime[7]["escalator_application"]["direction_codejeu"][8],
            "CJ_ESCALATOR_OUEST<<4",
        )
        self.assertIn("DONT_PICK_CODE_JEU", runtime[7]["escalator_application"]["effect"])
        self.assertEqual(runtime[7]["script_controls"][0]["opcode"], "LM_ESCALATOR")
        self.assertEqual(runtime[8]["fields"]["cooldown_ticks"], 700)
        self.assertEqual(runtime[8]["load_state"]["timer_ref_after_load"], 0)
        self.assertEqual(
            runtime[8]["hit_application"]["hit_call"],
            "HitObj(numobj, numobj, Info1, object.Beta)",
        )
        self.assertIn("Info2*5*20", runtime[8]["hit_application"]["cooldown_start"])
        self.assertIn("TimerRefHR >=", runtime[8]["hit_application"]["cooldown_clear"])
        self.assertEqual(runtime[8]["script_controls"][0]["opcode"], "LM_SET_HIT_ZONE")
        self.assertTrue(runtime[9]["fields"]["runtime_active"])
        self.assertFalse(runtime[9]["fields"]["serialized_runtime_active"])
        self.assertEqual(
            runtime[9]["rail_application"]["runtime_pointer"],
            "The wagon object's PtrZoneRail is assigned to the zone.",
        )
        self.assertIn("PtrZoneRail->Info1", runtime[9]["rail_application"]["wagon_use"])
        self.assertEqual(runtime[9]["script_controls"][0]["opcode"], "LM_SET_RAIL")
        self.assertEqual(
            recon["message_camera_link_counts"],
            {"links": 1, "found": 1, "missing": 0},
        )
        self.assertEqual(
            recon["message_camera_links"][0],
            {
                "kind": "message_camera_zone",
                "zone_index": 5,
                "zone_value": 99,
                "message_id": 99,
                "associated_camera_zone": 12,
                "target_available": True,
                "source_provenance": "OBJECT.CPP::GereZoneMessage looks up Type==1 camera zones by Num==Info1 before Dial().",
                "target_zone_index": 1,
                "target_zone_value": 12,
                "target_type": 1,
                "target_type_name": "camera",
                "target_runtime_effect": "camera_zone",
            },
        )
        self.assertTrue(viewer.scene_message_facing_rule(2)["wraps_zero"])
        self.assertEqual(
            viewer.scene_message_facing_rule(99)["status"], "unknown_direction_code"
        )

    def test_scene_script_local_links_resolve_objects_waypoints_and_zones(self) -> None:
        hero_life = bytes([29, 2, 58, 1, 21, 0, 1, 119, 2, 1, 0])
        zones = [
            scene_zone_record(zone_type=1, value=12),
            scene_zone_record(zone_type=0, value=9),
            scene_zone_record(zone_type=8, value=0),
        ]
        tracks = [
            scene_track_record((10, 20, 30)),
            scene_track_record((70, 80, 90)),
        ]
        scene = scene_payload(
            hero_life_script=hero_life,
            object_records=[
                scene_object_record(file3d_index=4, position=(100, 200, 300)),
                scene_object_record(file3d_index=5, position=(400, 500, 600)),
            ],
            zone_records=zones,
            track_records=tracks,
        )

        recon = viewer.parse_scene_reconnaissance(scene)
        analysis = recon["hero"]["life_script_analysis"]
        links = analysis["local_links"]

        self.assertEqual(recon["script_local_link_counts"], {"object": 1, "waypoint": 1, "zone": 2})
        self.assertIn(
            {
                "kind": "object",
                "reference_key": "object",
                "reference_value": 2,
                "target": "scene_object",
                "object_index": 2,
                "target_available": True,
                "position": {"x": 400, "y": 500, "z": 600},
                "file3d_index": 5,
                "gen_body": 0,
                "gen_anim": 0,
                "sprite": 0,
            },
            links,
        )
        self.assertIn(
            {
                "kind": "waypoint",
                "reference_key": "waypoint",
                "reference_value": 1,
                "target": "waypoint",
                "waypoint_index": 1,
                "target_available": True,
                "position": {"x": 70, "y": 80, "z": 90},
            },
            links,
        )
        self.assertIn(
            {
                "kind": "zone",
                "reference_key": "camera_zone",
                "reference_value": 0,
                "target": "zone",
                "zone_index": 0,
                "target_available": True,
                "type": 1,
                "type_name": "camera",
                "expected_type": 1,
                "type_matches_reference": True,
                "value": 12,
                "runtime_effect": "camera_zone",
            },
            links,
        )
        self.assertIn(
            {
                "kind": "zone",
                "reference_key": "hit_zone",
                "reference_value": 2,
                "target": "zone",
                "zone_index": 2,
                "target_available": True,
                "type": 8,
                "type_name": "hit",
                "expected_type": 8,
                "type_matches_reference": True,
                "value": 0,
                "runtime_effect": "hit_object",
            },
            links,
        )

    def test_scene_script_cross_links_resolve_track_and_life_targets(self) -> None:
        hero_track = bytes([9, 7, 0])
        object_track = bytes([9, 8, 0])
        object_life = bytes([0])
        hero_life = (
            bytes([23])
            + struct.pack("<h", 0)
            + bytes([24, 1])
            + struct.pack("<h", 0)
            + bytes([34, 1])
            + struct.pack("<h", 0)
            + bytes([0])
        )
        scene = scene_payload(
            hero_track_script=hero_track,
            hero_life_script=hero_life,
            object_records=[
                scene_object_record(track_script=object_track, life_script=object_life)
            ],
        )

        recon = viewer.parse_scene_reconnaissance(scene)
        links = recon["hero"]["life_script_analysis"]["cross_script_links"]

        self.assertEqual(
            recon["script_cross_link_counts"],
            {
                "links": 3,
                "found": 3,
                "missing": 0,
                "track": 2,
                "life": 1,
                "missing_owner": 0,
            },
        )
        self.assertEqual(
            links,
            [
                {
                    "source_owner": "hero",
                    "source_script_kind": "life",
                    "source_offset": 0,
                    "source_opcode": "LM_SET_TRACK",
                    "source_behavior_category": "movement_path",
                    "target_field": "target_track_offset",
                    "target_owner": "hero",
                    "target_object_index": 0,
                    "target_owner_found": True,
                    "target_script_kind": "track",
                    "target_offset": 0,
                    "target_found": True,
                    "target_status": "instruction_start",
                    "target_decoded_bytes": 3,
                    "target_script_bytes": 3,
                    "target_opcode": "TM_LABEL",
                    "target_behavior_category": "control_flow",
                },
                {
                    "source_owner": "hero",
                    "source_script_kind": "life",
                    "source_offset": 3,
                    "source_opcode": "LM_SET_TRACK_OBJ",
                    "source_behavior_category": "movement_path",
                    "target_field": "target_track_offset",
                    "target_owner": "object:1",
                    "target_object_index": 1,
                    "target_owner_found": True,
                    "target_script_kind": "track",
                    "target_offset": 0,
                    "target_found": True,
                    "target_status": "instruction_start",
                    "target_decoded_bytes": 3,
                    "target_script_bytes": 3,
                    "target_opcode": "TM_LABEL",
                    "target_behavior_category": "control_flow",
                },
                {
                    "source_owner": "hero",
                    "source_script_kind": "life",
                    "source_offset": 7,
                    "source_opcode": "LM_SET_COMPORTEMENT_OBJ",
                    "source_behavior_category": "model_animation",
                    "target_field": "target_life_offset",
                    "target_owner": "object:1",
                    "target_object_index": 1,
                    "target_owner_found": True,
                    "target_script_kind": "life",
                    "target_offset": 0,
                    "target_found": True,
                    "target_status": "instruction_start",
                    "target_decoded_bytes": 1,
                    "target_script_bytes": 1,
                    "target_opcode": "LM_END",
                    "target_behavior_category": "control_flow",
                },
            ],
        )

    def test_scene_script_cross_links_explain_unreachable_gap_targets(self) -> None:
        object_life = bytes([15]) + struct.pack("<h", 5) + bytes([115, 0, 0, 0])
        hero_life = bytes([34, 1]) + struct.pack("<h", 3) + bytes([0])
        scene = scene_payload(
            hero_life_script=hero_life,
            object_records=[scene_object_record(life_script=object_life)],
        )

        recon = viewer.parse_scene_reconnaissance(scene)
        link = recon["hero"]["life_script_analysis"]["cross_script_links"][0]

        self.assertEqual(
            recon["script_cross_link_counts"],
            {
                "links": 1,
                "found": 0,
                "missing": 1,
                "track": 0,
                "life": 1,
                "missing_owner": 0,
            },
        )
        self.assertEqual(link["target_owner"], "object:1")
        self.assertEqual(link["target_offset"], 3)
        self.assertEqual(link["target_found"], False)
        self.assertEqual(link["target_status"], "undecoded_gap")
        self.assertEqual(link["target_decoded_bytes"], 7)
        self.assertEqual(link["target_script_bytes"], 7)
        self.assertEqual(
            recon["script_control_flow_target_status_counts"],
            {"instruction_start": 1},
        )
        self.assertEqual(
            recon["script_cross_link_target_status_counts"],
            {"undecoded_gap": 1},
        )

    def test_scene_patches_resolve_target_instruction_and_operand_byte(self) -> None:
        hero_track = bytes([9, 7, 10]) + struct.pack("<h", 0) + bytes([0])
        base_scene = scene_payload(hero_track_script=hero_track)
        base_recon = viewer.parse_scene_reconnaissance(base_scene)
        target_offset = base_recon["hero"]["track_script_offset"] + 3
        scene = scene_payload(
            hero_track_script=hero_track,
            patch_records=[scene_patch_record(2, target_offset)],
        )

        recon = viewer.parse_scene_reconnaissance(scene)
        patch = recon["sampled_patches"][0]

        self.assertEqual(recon["patch_instruction_counts"], {"TM_GOTO": 1})
        self.assertEqual(recon["patch_instruction_byte_counts"], {"operand_byte": 1})
        self.assertEqual(patch["target"]["kind"], "track")
        self.assertEqual(patch["target"]["owner"], "hero")
        self.assertEqual(patch["target"]["script_relative_offset"], 3)
        self.assertEqual(patch["target"]["instruction_found"], True)
        self.assertEqual(patch["target"]["instruction_offset"], 2)
        self.assertEqual(patch["target"]["instruction_relative_offset"], 1)
        self.assertEqual(patch["target"]["instruction_opcode"], "TM_GOTO")
        self.assertEqual(patch["target"]["instruction_behavior_category"], "control_flow")
        self.assertEqual(patch["target"]["hits_opcode_byte"], False)
        self.assertEqual(patch["target"]["operand_relative_offset"], 0)
        self.assertEqual(patch["target"]["patched_field"], "target_offset")
        self.assertEqual(patch["target"]["patched_field_offset"], 1)
        self.assertEqual(patch["target"]["patched_field_size"], 2)
        self.assertEqual(patch["target"]["patched_field_byte_offset"], 0)
        self.assertEqual(patch["target"]["patched_field_source"], "track_opcode_layout")
        self.assertEqual(recon["patch_field_counts"], {"target_offset": 1})
        self.assertEqual(recon["patch_field_source_counts"], {"track_opcode_layout": 1})
        self.assertEqual(recon["patch_instruction_field_counts"], {"TM_GOTO.target_offset": 1})

    def test_scene_patches_classify_track_runtime_timer_field(self) -> None:
        hero_track = bytes([36, 5]) + struct.pack("<I", 0x11223344) + bytes([0])
        base_scene = scene_payload(hero_track_script=hero_track)
        base_recon = viewer.parse_scene_reconnaissance(base_scene)
        target_offset = base_recon["hero"]["track_script_offset"] + 2
        scene = scene_payload(
            hero_track_script=hero_track,
            patch_records=[scene_patch_record(4, target_offset)],
        )

        recon = viewer.parse_scene_reconnaissance(scene)
        patch = recon["sampled_patches"][0]
        instruction = recon["hero"]["track_script_analysis"]["first_instructions"][0]

        self.assertEqual(
            instruction["operand_semantics"],
            {"duration_count": 5, "runtime_timer_ref": 0x11223344},
        )
        self.assertEqual(recon["patch_instruction_counts"], {"TM_WAIT_NB_DIZIEME": 1})
        self.assertEqual(recon["patch_instruction_byte_counts"], {"operand_byte": 1})
        self.assertEqual(patch["target"]["instruction_relative_offset"], 2)
        self.assertEqual(patch["target"]["operand_relative_offset"], 1)
        self.assertEqual(patch["target"]["patched_field"], "runtime_timer_ref")
        self.assertEqual(patch["target"]["patched_field_offset"], 2)
        self.assertEqual(patch["target"]["patched_field_size"], 4)
        self.assertEqual(patch["target"]["patched_field_byte_offset"], 0)
        self.assertEqual(patch["target"]["patched_field_source"], "classic_track_runtime")
        self.assertEqual(recon["patch_field_counts"], {"runtime_timer_ref": 1})
        self.assertEqual(recon["patch_field_source_counts"], {"classic_track_runtime": 1})
        self.assertEqual(
            recon["patch_instruction_field_counts"],
            {"TM_WAIT_NB_DIZIEME.runtime_timer_ref": 1},
        )
        self.assertEqual(recon["script_runtime_state_counts"], {"runtime_timer_ref": 1})
        self.assertEqual(
            recon["script_runtime_instruction_state_counts"],
            {"TM_WAIT_NB_DIZIEME.runtime_timer_ref": 1},
        )

    def test_scene_object_movement_info_semantics_link_runtime_targets(self) -> None:
        scene = scene_payload(
            object_records=[
                scene_object_record(move=2, info=(0, 0, 0, 0)),
                scene_object_record(move=9, info=(11, 22, 33, 1)),
            ],
            track_records=[
                scene_track_record((100, 0, 200)),
                scene_track_record((300, 0, 400)),
            ],
        )

        recon = viewer.parse_scene_reconnaissance(scene)

        follow = recon["sampled_objects"][0]["runtime"]["movement"]
        circle = recon["sampled_objects"][1]["runtime"]["movement"]
        self.assertEqual(
            follow["references"],
            [
                {
                    "field": "Info3",
                    "field_index": 3,
                    "role": "target_object_id",
                    "kind": "object",
                    "value": 0,
                    "target": "hero",
                    "target_found": True,
                    "source": "OBJECT.CPP DoDirObject and GERELIFE.CPP AdjustDirObject",
                }
            ],
        )
        self.assertEqual(circle["references"][0]["role"], "circle_waypoint_id")
        self.assertEqual(circle["references"][0]["target"], "waypoint:1")
        self.assertTrue(circle["references"][0]["target_found"])
        self.assertEqual(
            [field["role"] for field in circle["state_fields"]],
            ["circle_radius", "circle_origin_angle", "circle_timer_ref"],
        )
        self.assertEqual(
            recon["object_movement_reference_counts"],
            {
                "MOVE_FOLLOW.target_object_id": 1,
                "MOVE_CIRCLE.circle_waypoint_id": 1,
            },
        )
        self.assertEqual(recon["object_movement_missing_reference_counts"], {})
        self.assertEqual(
            recon["object_movement_state_counts"],
            {
                "MOVE_CIRCLE.circle_radius": 1,
                "MOVE_CIRCLE.circle_origin_angle": 1,
                "MOVE_CIRCLE.circle_timer_ref": 1,
            },
        )

    def test_scene_reconnaissance_aggregates_life_condition_functions(self) -> None:
        hero_life = (
            bytes([12, 3, 0, 9])
            + struct.pack("<h", 0)
            + bytes([113, 15, 4])
            + bytes([0])
        )

        recon = viewer.parse_scene_reconnaissance(
            scene_payload(hero_life_script=hero_life)
        )

        self.assertEqual(
            recon["script_condition_function_counts"],
            {"LF_VAR_GAME": 1, "LF_ZONE": 1},
        )
        self.assertEqual(
            recon["script_condition_return_type_counts"],
            {"s16": 1, "s8": 1},
        )
        self.assertEqual(
            recon["script_condition_comparator_counts"],
            {"LT_EQUAL": 1},
        )

    def test_catalog_links_scene_objects_to_runtime_assets(self) -> None:
        sprite = lsp_sprite_payload()
        anim = anim_payload([(100, (0, 0, 0), [(0, 0, 0, 0)])])
        file3d = file3d_record(file3d_body(0, 0) + file3d_anim(1, 1))
        scene = scene_payload(
            object_records=[
                scene_object_record(file3d_index=0, gen_body=0, gen_anim=1),
                scene_object_record(
                    flags=viewer.SPRITE_3D_FLAG,
                    file3d_index=-1,
                    sprite=127,
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BODY.HQR").write_bytes(classic_hqr([resource_entry(minimal_lm2())]))
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(anim)]))
            (root / "SPRITES.HQR").write_bytes(
                classic_hqr([resource_entry(sprite)] + [b""] * 126 + [resource_entry(sprite)])
            )
            (root / "RESS.HQR").write_bytes(
                hqr([b""] * 43 + [resource_entry(file3d)])
            )

            catalog = viewer.build_catalog(root)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            objects = scene_asset["stats"]["reconnaissance"]["sampled_objects"]
            model_object = objects[0]
            sprite_object = objects[1]
            self.assertEqual(model_object["links"]["body"]["asset_id"], "BODY.HQR:1")
            self.assertTrue(model_object["links"]["body"]["asset_available"])
            self.assertEqual(model_object["links"]["animation"]["asset_id"], "ANIM.HQR:1")
            self.assertTrue(model_object["links"]["animation"]["asset_available"])
            self.assertIn("matched scene GenAnim", model_object["links"]["animation"]["resolution_rule"])
            self.assertEqual(sprite_object["links"]["sprite"]["asset_id"], "SPRITES.HQR:127")
            self.assertTrue(sprite_object["links"]["sprite"]["asset_available"])
            self.assertEqual(
                scene_asset["stats"]["reconnaissance"]["linked_animation_refs"], 1
            )
            self.assertEqual(catalog["summary"]["scene_linked_animation_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_linked_sprite_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_usage_refs"], 3)
            self.assertEqual(catalog["summary"]["scene_used_assets"], 3)
            self.assertEqual(
                catalog["metadata"]["scene_asset_usage"]["by_kind"],
                {"body": 1, "animation": 1, "sprite": 1},
            )
            body_asset = viewer.find_catalog_asset(catalog, "BODY.HQR:1")
            animation_asset = viewer.find_catalog_asset(catalog, "ANIM.HQR:1")
            sprite_asset = viewer.find_catalog_asset(catalog, "SPRITES.HQR:127")
            self.assertEqual(body_asset["scene_usages"][0]["kind"], "body")
            self.assertEqual(body_asset["scene_usages"][0]["scene_index"], 0)
            self.assertEqual(body_asset["scene_usages"][0]["object_index"], 1)
            self.assertEqual(animation_asset["scene_usages"][0]["kind"], "animation")
            self.assertEqual(animation_asset["scene_usages"][0]["generic_id"], 1)
            self.assertEqual(sprite_asset["scene_usages"][0]["kind"], "sprite")
            self.assertEqual(sprite_asset["scene_usages"][0]["runtime_sprite_index"], 127)
            self.assertEqual(
                catalog["metadata"]["scene_runtime_links"]["missing_asset_ids"], []
            )

    def test_catalog_links_scene_script_references_to_runtime_assets(self) -> None:
        sprite = lsp_sprite_payload()
        anim = anim_payload([(100, (0, 0, 0), [(0, 0, 0, 0)])])
        file3d = file3d_record(file3d_body(0, 0) + file3d_anim(1, 1))
        model_track = bytes([2, 0, 3]) + struct.pack("<h", 1) + bytes([0])
        sprite_life = bytes([84]) + struct.pack("<h", 127) + bytes([0])
        scene = scene_payload(
            object_records=[
                scene_object_record(
                    file3d_index=0,
                    gen_body=0,
                    gen_anim=1,
                    track_script=model_track,
                ),
                scene_object_record(
                    flags=viewer.SPRITE_3D_FLAG,
                    file3d_index=-1,
                    sprite=127,
                    life_script=sprite_life,
                ),
            ]
        )
        ress_entries = [b""] * 44
        ress_entries[4] = resource_entry(
            sprite_zv_payload(128, 127, (11, -12, -30, 31, -40, 41, -50, 51))
        )
        ress_entries[43] = resource_entry(file3d)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BODY.HQR").write_bytes(classic_hqr([resource_entry(minimal_lm2())]))
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(anim)]))
            (root / "SPRITES.HQR").write_bytes(
                classic_hqr([resource_entry(sprite)] + [b""] * 126 + [resource_entry(sprite)])
            )
            (root / "RESS.HQR").write_bytes(hqr(ress_entries))

            catalog = viewer.build_catalog(root)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            recon = scene_asset["stats"]["reconnaissance"]
            objects = recon["sampled_objects"]
            model_links = objects[0]["track_script_analysis"]["asset_links"]
            sprite_links = objects[1]["life_script_analysis"]["asset_links"]
            self.assertEqual(recon["script_linked_body_refs"], 1)
            self.assertEqual(recon["script_linked_animation_refs"], 1)
            self.assertEqual(recon["script_linked_sprite_refs"], 1)
            self.assertEqual(model_links[0]["kind"], "body")
            self.assertEqual(model_links[0]["asset_id"], "BODY.HQR:1")
            self.assertEqual(model_links[0]["reference_value"], 0)
            self.assertEqual(model_links[0]["resolution_rule"], "resolved script generic body through owner File3D SearchBody rule")
            self.assertEqual(model_links[1]["kind"], "animation")
            self.assertEqual(model_links[1]["asset_id"], "ANIM.HQR:1")
            self.assertEqual(model_links[1]["reference_value"], 1)
            self.assertEqual(sprite_links[0]["kind"], "sprite")
            self.assertEqual(sprite_links[0]["asset_id"], "SPRITES.HQR:127")
            self.assertTrue(sprite_links[0]["asset_available"])
            self.assertEqual(
                catalog["metadata"]["scene_script_links"],
                {
                    "source": "RESS.HQR:44",
                    "body_refs": 1,
                    "animation_refs": 1,
                    "sprite_refs": 1,
                    "missing_asset_ids": [],
                },
            )
            self.assertEqual(catalog["summary"]["scene_script_linked_body_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_script_linked_animation_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_script_linked_sprite_refs"], 1)
            self.assertEqual(catalog["summary"]["scene_usage_refs"], 6)
            self.assertEqual(catalog["summary"]["scene_used_assets"], 3)
            self.assertEqual(
                catalog["metadata"]["scene_asset_usage"]["by_kind"],
                {
                    "body": 1,
                    "animation": 1,
                    "sprite": 1,
                    "script_body": 1,
                    "script_animation": 1,
                    "script_sprite": 1,
                },
            )
            body_asset = viewer.find_catalog_asset(catalog, "BODY.HQR:1")
            animation_asset = viewer.find_catalog_asset(catalog, "ANIM.HQR:1")
            sprite_asset = viewer.find_catalog_asset(catalog, "SPRITES.HQR:127")
            self.assertIn("script_body", [usage["kind"] for usage in body_asset["scene_usages"]])
            self.assertIn("script_animation", [usage["kind"] for usage in animation_asset["scene_usages"]])
            self.assertIn("script_sprite", [usage["kind"] for usage in sprite_asset["scene_usages"]])

    def test_catalog_decodes_spriraw_hqr_with_runtime_rule(self) -> None:
        data = raw_sprite_payload()
        zv = sprite_zv_payload(4, 3, (-1, 2, -3, 4, -5, 6, -7, 8))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SPRIRAW.HQR").write_bytes(
                classic_hqr([resource_entry(raw_sprite_payload()), b"", b"", resource_entry(data)])
            )
            (root / "RESS.HQR").write_bytes(hqr([b""] * 7 + [resource_entry(zv)]))

            catalog = viewer.build_catalog(root)

            asset = viewer.find_catalog_asset(catalog, "SPRIRAW.HQR:3")
            self.assertEqual(asset["kind"], "sprite")
            self.assertEqual(asset["entry_type"], "sprite-raw-frame")
            self.assertEqual(asset["features"]["runtime_sprite_backend"], "spriraw")
            stats = asset["stats"]
            self.assertEqual(stats["sprite_backend"], "spriraw")
            self.assertEqual(stats["semantic_layout"], "raw_sprite_frame")
            self.assertEqual(stats["format"], "raw_sprite")
            self.assertEqual(stats["offset_x"], -2)
            self.assertEqual(stats["offset_y"], 3)
            self.assertEqual(stats["runtime"]["runtime_sprite_index"], 3)
            self.assertIn("Sprite < 100", stats["runtime"]["index_rule"])
            self.assertEqual(stats["runtime"]["hotspot"], {"x": -1, "y": 2})

            direct_asset = viewer.find_catalog_asset(catalog, "SPRIRAW.HQR:0")
            self.assertEqual(direct_asset["stats"]["direct_reference_count"], 1)
            self.assertEqual(
                direct_asset["stats"]["direct_code_references"][0]["symbol"],
                "SPRITE_CLOVER_BOX",
            )

    def test_catalog_decodes_objfix_hqr_with_classic_runtime_ids(self) -> None:
        entries = [resource_entry(minimal_lm2())] + [b""] * 59 + [
            resource_entry(minimal_lm2()),
            resource_entry(minimal_lm2()),
            resource_entry(minimal_lm2()),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "OBJFIX.HQR").write_bytes(classic_hqr(entries))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["hqr_files"][0]["indexing"], "classic")
            self.assertEqual(catalog["hqr_files"][0]["entry_count"], 63)
            self.assertEqual(catalog["summary"]["models"], 4)
            first = viewer.find_catalog_asset(catalog, "OBJFIX.HQR:0")
            self.assertEqual(first["source"]["classic_index"], 0)
            self.assertEqual(first["stats"]["direct_code_references"][0]["symbol"], "FLAG_HOLOMAP")
            clover = viewer.find_catalog_asset(catalog, "OBJFIX.HQR:60")
            self.assertEqual(clover["stats"]["runtime_reference_status"], "direct GivePtrObjFix runtime id")
            self.assertEqual(clover["stats"]["direct_code_references"][0]["symbol"], "BODY_3D_CLOVER")
            dart = viewer.find_catalog_asset(catalog, "OBJFIX.HQR:61")
            self.assertEqual(dart["stats"]["direct_code_references"][0]["symbol"], "BODY_3D_DART")
            protect = viewer.find_catalog_asset(catalog, "OBJFIX.HQR:62")
            self.assertEqual(protect["features"]["direct_code_references"], True)
            self.assertEqual(protect["stats"]["direct_code_references"][0]["symbol"], "BODY_SORT_PROTECT")

    def test_server_loads_decoded_normal_sprite_frame_payload(self) -> None:
        data = lsp_sprite_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SPRITES.HQR").write_bytes(classic_hqr([resource_entry(data)]))
            state = server.ViewerServer(None, root)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), state.handler_class())
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{httpd.server_port}/api/catalog/load"
                request = urllib.request.Request(
                    url,
                    data=json.dumps({"id": "SPRITES.HQR:0"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(2)

            self.assertEqual(payload["sprite"]["entry_type"], "sprite-frame")
            self.assertEqual(payload["frame"]["format"], "lsp_sprite")
            self.assertEqual(payload["frame"]["width"], 4)
            self.assertEqual(payload["frame"]["height"], 2)
            self.assertEqual(payload["frame"]["pixels"], [0, 7, 7, 8, 1, 2, 0, 3])

    def test_server_loads_decoded_bkg_brick_graphic_frame_payload(self) -> None:
        header = struct.pack(
            "<HHHHHHIIII",
            1,
            2,
            3,
            4,
            2,
            1,
            4096,
            9000,
            512,
            256,
        )
        brick_a = bkg_affgraph_payload()
        brick_b = bkg_affgraph_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        b"",
                        b"",
                        b"",
                        resource_entry(brick_a),
                        resource_entry(brick_b),
                    ]
                )
            )
            state = server.ViewerServer(None, root)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), state.handler_class())
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{httpd.server_port}/api/catalog/load"
                request = urllib.request.Request(
                    url,
                    data=json.dumps({"id": "LBA_BKG.HQR:4"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(2)

            self.assertEqual(payload["sprite"]["kind"], "resource")
            self.assertEqual(payload["sprite"]["entry_type"], "bkg-brick-graphic")
            self.assertEqual(payload["frame"]["format"], "bkg_affgraph")
            self.assertEqual(payload["frame"]["width"], 4)
            self.assertEqual(payload["frame"]["height"], 2)
            self.assertEqual(payload["frame"]["pixels"], [0, 7, 7, 8, 1, 2, 0, 3])
            self.assertIn("ChoicePalette", payload["frame"]["palette_source"])

    def test_server_loads_decoded_bkg_grid_composition_payload(self) -> None:
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
            root = Path(temp_dir)
            (root / "LBA_BKG.HQR").write_bytes(
                classic_hqr(
                    [
                        resource_entry(header),
                        resource_entry(bkg_grid_payload(0x0001)),
                        resource_entry(grm),
                        resource_entry(bll),
                        resource_entry(bkg_affgraph_payload()),
                        resource_entry(bytes(cube_records)),
                    ]
                )
            )
            state = server.ViewerServer(None, root)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), state.handler_class())
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{httpd.server_port}/api/catalog/load"
                request = urllib.request.Request(
                    url,
                    data=json.dumps({"id": "LBA_BKG.HQR:1"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(2)

            self.assertEqual(payload["sprite"]["kind"], "resource")
            self.assertEqual(payload["frame"]["format"], "bkg_grid_preview")
            self.assertEqual(payload["frame"]["width"], 640)
            self.assertEqual(payload["frame"]["height"], 480)
            self.assertGreater(payload["frame"]["drawn_pixels"], 0)
            self.assertIn("AffGrille", payload["frame"]["render_source"])
            composition = payload["sprite"]["stats"]["composition_payload"]
            self.assertEqual(composition["format"], "bkg_grid_column_composition")
            self.assertEqual(composition["cell_count"], 64 * 25 * 64)
            self.assertEqual(composition["occupied_block_cells"], 4096)
            self.assertEqual(composition["flat_block_refs"][:25], [1] + [0] * 24)
            self.assertEqual(composition["flat_cell_slots_or_codes"][:25], [0] * 25)
            self.assertIn("flat index", composition["cell_order"])
            preview = payload["sprite"]["stats"]["preview"]
            self.assertEqual(preview["format"], "bkg_grid_preview")
            self.assertEqual(preview["drawn_cells"], 4096)

    def test_server_resolves_runtime_sprite_object_to_catalog_asset(self) -> None:
        data = lsp_sprite_payload()
        zv = sprite_zv_payload(128, 127, (11, -12, -30, 31, -40, 41, -50, 51))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            entries = [resource_entry(data)] + [b""] * 126 + [resource_entry(data)]
            (root / "SPRITES.HQR").write_bytes(classic_hqr(entries))
            (root / "RESS.HQR").write_bytes(hqr([b""] * 4 + [resource_entry(zv)]))
            state = server.ViewerServer(None, root)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), state.handler_class())
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{httpd.server_port}/api/runtime/sprite-resolve"
                request = urllib.request.Request(
                    url,
                    data=json.dumps(
                        {
                            "object_index": 7,
                            "flags": viewer.SPRITE_3D_FLAG,
                            "sprite_index": 127,
                            "body_num": 127,
                            "label_track": 1,
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(2)

            self.assertTrue(payload["catalog_asset_available"])
            self.assertEqual(payload["catalog_asset"]["id"], "SPRITES.HQR:127")
            self.assertEqual(payload["resolution"]["backend"], "sprites")
            self.assertEqual(payload["resolution"]["hotspot"], {"x": 11, "y": -12})
            self.assertEqual(payload["resolution"]["bounds"]["max_z"], 51)

    def test_catalog_tracks_every_anim3ds_entry_with_independent_unknown_descriptors(self) -> None:
        first = b"\x01\x00\x02\x00header-one"
        second = b"\x03\x00\x04\x00\x05\x00payload-two"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(
                classic_hqr([resource_entry(first), b"", resource_entry(second)])
            )

            catalog = viewer.build_catalog(root)

            assets = catalog["assets"]
            self.assertEqual([asset["id"] for asset in assets], ["ANIM3DS.HQR:0", "ANIM3DS.HQR:2"])
            self.assertEqual(catalog["summary"]["animations"], 0)
            self.assertEqual(catalog["summary"]["raw_animations"], 0)
            self.assertEqual(catalog["summary"]["animation_assets"], 0)
            self.assertEqual(catalog["summary"]["sprite_assets"], 2)
            self.assertEqual(catalog["summary"]["sprite_frames"], 2)
            self.assertEqual(assets[0]["stats"]["decoded_sha256"], hashlib.sha256(first).hexdigest())
            self.assertEqual(assets[1]["stats"]["decoded_sha256"], hashlib.sha256(second).hexdigest())
            self.assertNotEqual(
                assets[0]["stats"]["unknown_descriptors"][0]["sha256"],
                assets[1]["stats"]["unknown_descriptors"][0]["sha256"],
            )

    def test_catalog_decodes_anim3ds_frame_range_table(self) -> None:
        info = (
            b"COQU" + struct.pack("<hh", 0, 2) +
            b"ROUE" + struct.pack("<hh", 3, 5)
        )
        entries = [resource_entry(b"frame0"), resource_entry(b"frame1"), b""] + [b""] * 125
        entries[127] = resource_entry(info)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(classic_hqr(entries))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["hqr_files"][0]["indexing"], "classic")
            table = viewer.find_catalog_asset(catalog, "ANIM3DS.HQR:127")
            self.assertEqual(table["kind"], "sprite")
            self.assertEqual(table["entry_type"], "anim3ds-info")
            self.assertNotIn("animation_state", table)
            self.assertEqual(table["label"], "ANIM3DS frame range table (2 animations)")
            self.assertEqual(table["features"]["metadata_only"], True)
            self.assertEqual(catalog["summary"]["sprite_assets"], 3)
            self.assertEqual(catalog["summary"]["sprite_frames"], 2)
            self.assertEqual(catalog["summary"]["sprite_metadata"], 1)
            stats = table["stats"]
            self.assertEqual(stats["parse_status"], "metadata")
            self.assertEqual(stats["decode_status"], "decoded")
            self.assertEqual(stats["semantic_layout"], "anim3ds_frame_ranges")
            self.assertEqual(stats["frame_min"], 0)
            self.assertEqual(stats["frame_max"], 5)
            self.assertEqual(stats["range_warnings"][0]["name"], "COQU")
            self.assertEqual(stats["range_warnings"][0]["missing_frames"], [2])
            self.assertEqual(stats["range_warnings"][1]["name"], "ROUE")
            self.assertEqual(stats["range_warnings"][1]["missing_frames"], [3, 4, 5])
            self.assertEqual(stats["entries"][0]["name"], "COQU")
            self.assertEqual(stats["entries"][0]["start_frame"], 0)
            self.assertEqual(stats["entries"][0]["end_frame"], 2)
            self.assertIn("TM_START_ANIM_3DS", stats["source_provenance"])
            self.assertIn("scene object state", stats["runtime_reference_status"])
            self.assertIn(
                "no frame durations",
                stats["runtime_playback"]["timing_source"],
            )
            self.assertIn(
                "SizeSHit",
                stats["runtime_playback"]["track_controls"]["TM_STOP_ANIM_3DS"],
            )
            frame = viewer.find_catalog_asset(catalog, "ANIM3DS.HQR:0")
            self.assertEqual(frame["kind"], "sprite")
            self.assertEqual(frame["entry_type"], "anim3ds-frame")
            self.assertEqual(frame["label"], "COQU sprite frame 0 (ANIM3DS.HQR:0)")
            self.assertEqual(frame["stats"]["anim3ds_info"]["name"], "COQU")
            self.assertEqual(frame["stats"]["anim3ds_info"]["relative_frame"], 0)

    def test_catalog_links_scene_anim3ds_object_to_frame_range(self) -> None:
        info = (
            b"COQU" + struct.pack("<hh", 0, 2) +
            b"ROUE" + struct.pack("<hh", 3, 5)
        )
        scene = scene_payload(
            object_records=[
                scene_object_record(
                    flags=viewer.SPRITE_3D_FLAG | viewer.ANIM_3DS_FLAG,
                    sprite=4,
                    anim3ds_animation_number=1,
                    anim3ds_size_s_hit=24,
                )
            ]
        )
        entries = [resource_entry(lsp_sprite_payload()) for _ in range(6)] + [b""] * 122
        entries[127] = resource_entry(info)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SCENE.HQR").write_bytes(hqr([resource_entry(scene)]))
            (root / "ANIM3DS.HQR").write_bytes(classic_hqr(entries))

            catalog = viewer.build_catalog(root)

            scene_asset = viewer.find_catalog_asset(catalog, "SCENE.HQR:1")
            scene_object = scene_asset["stats"]["reconnaissance"]["sampled_objects"][0]
            sprite_link = scene_object["links"]["sprite"]
            self.assertEqual(sprite_link["asset_id"], "ANIM3DS.HQR:4")
            self.assertEqual(sprite_link["backend"], "anim3ds")
            self.assertEqual(
                sprite_link["anim3ds_range"],
                {
                    "animation_number": 1,
                    "name": "ROUE",
                    "start_frame": 3,
                    "end_frame": 5,
                    "frame_count": 3,
                    "relative_frame": 1,
                    "range_matches_sprite": True,
                    "size_s_hit": 24,
                    "frames_per_second": 24,
                },
            )
            self.assertEqual(scene_object["anim3ds"]["frames_per_second"], 24)
            self.assertIn("Info3", scene_object["anim3ds"]["timing_field"])
            frame = viewer.find_catalog_asset(catalog, "ANIM3DS.HQR:4")
            self.assertEqual(frame["scene_usages"][0]["anim3ds_range"]["name"], "ROUE")
            self.assertEqual(frame["scene_usages"][0]["anim3ds_range"]["frames_per_second"], 24)
            self.assertEqual(frame["scene_usages"][0]["runtime_sprite_index"], 4)

    def test_catalog_counts_decoded_and_raw_animation_entries_separately(self) -> None:
        decoded = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        raw = b"\x01\x00\x02\x00anim3ds"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(decoded)]))
            (root / "ANIM3DS.HQR").write_bytes(classic_hqr([resource_entry(raw)]))

            catalog = viewer.build_catalog(root)

            self.assertEqual(catalog["summary"]["animations"], 1)
            self.assertEqual(catalog["summary"]["decoded_animations"], 1)
            self.assertEqual(catalog["summary"]["raw_animations"], 0)
            self.assertEqual(catalog["summary"]["animation_assets"], 1)
            self.assertEqual(catalog["summary"]["sprite_assets"], 1)
            decoded_asset = viewer.find_catalog_asset(catalog, "ANIM.HQR:1")
            raw_asset = viewer.find_catalog_asset(catalog, "ANIM3DS.HQR:0")
            self.assertEqual(decoded_asset["entry_type"], "animation")
            self.assertEqual(decoded_asset["animation_state"], "decoded")
            self.assertEqual(raw_asset["kind"], "sprite")
            self.assertEqual(raw_asset["entry_type"], "anim3ds-frame")
            self.assertNotIn("animation_state", raw_asset)

    def test_catalog_prioritizes_anim_hqr_parser_before_lm2_autodetect(self) -> None:
        ambiguous = minimal_lm2()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM.HQR").write_bytes(hqr([resource_entry(ambiguous)]))

            catalog = viewer.build_catalog(root)

            asset = viewer.find_catalog_asset(catalog, "ANIM.HQR:1")
            self.assertEqual(asset["kind"], "animation")
            self.assertEqual(asset["entry_type"], "animation")
            self.assertEqual(asset["animation_state"], "decoded")
            self.assertEqual(catalog["summary"]["models"], 0)
            self.assertEqual(catalog["summary"]["decoded_animations"], 1)
            anim_coverage = [
                archive
                for archive in catalog["coverage"]["archives"]
                if archive["archive"] == "ANIM.HQR"
            ][0]
            self.assertEqual(anim_coverage["recognized_formats"], ["lba2-animation"])

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

    def test_animation_command_rejects_non_animation_catalog_entries(self) -> None:
        data = anim_payload([(100, (1, 2, 3), [(0, 4, 5, 6)])])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ANIM3DS.HQR").write_bytes(classic_hqr([resource_entry(data)]))

            with self.assertRaisesRegex(viewer.Lm2Error, "not a decoded animation"):
                with redirect_stdout(StringIO()):
                    viewer.animation_command(
                        [
                            "--asset-root",
                            str(root),
                            "--asset",
                            "ANIM3DS.HQR:0",
                            "--out",
                            str(root / "anim3ds.evidence.json"),
                        ]
                    )


if __name__ == "__main__":
    unittest.main()
