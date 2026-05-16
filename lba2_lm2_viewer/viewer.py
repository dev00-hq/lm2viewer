#!/usr/bin/env python3
"""View Little Big Adventure 2 LM2 body model files from user-owned HQR archives.

Python decodes HQR/LM2 bytes on demand, then serves a small Three.js page for
orbit/pan/zoom inspection. The package intentionally ships no extracted game
assets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import struct
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from . import lba_hqr
from .animation import (
    AnimationError,
    AnimationSummary,
    Lba2Animation,
    parse_lba2_animation,
    parse_lba2_animation_records,
    sample_keyframe_transition,
)
from .scene_scripts import (
    LIFE_FUNCTION_RETURN_TYPES,
    LIFE_FUNCTIONS_WITH_U8,
    analyze_life_script,
    analyze_track_script,
    decode_scene_script_instruction_graph,
    script_target_offset_evidence,
)

WORLD_SCALE = 0.15
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ASSET_ROOT = Path(os.environ.get("LBA2_ASSET_ROOT", "assets"))
PACKAGE_SUFFIXES = {".hqr"}
FRONTEND_DIST = Path(__file__).resolve().with_name("frontend") / "dist"
ANIM_ARCHIVE_NAME = "ANIM.HQR"
ANIM3DS_ARCHIVE_NAME = "ANIM3DS.HQR"
ANIM3DS_INFO_ENTRY_INDEX = 127
SCENE_ARCHIVE_NAME = "SCENE.HQR"
LBA_BKG_ARCHIVE_NAME = "LBA_BKG.HQR"
SPRITES_ARCHIVE_NAME = "SPRITES.HQR"
SPRIRAW_ARCHIVE_NAME = "SPRIRAW.HQR"
SPRITE_ARCHIVE_NAMES = {ANIM3DS_ARCHIVE_NAME, SPRITES_ARCHIVE_NAME, SPRIRAW_ARCHIVE_NAME}
ANIMATION_ARCHIVE_NAMES = {ANIM_ARCHIVE_NAME, ANIM3DS_ARCHIVE_NAME}
HOLOMAP_ARCHIVE_NAME = "HOLOMAP.HQR"
RESS_ARCHIVE_NAME = "RESS.HQR"
SCREEN_ARCHIVE_NAME = "SCREEN.HQR"
TEXT_ARCHIVE_NAME = "TEXT.HQR"
SAMPLES_ARCHIVE_NAME = "SAMPLES.HQR"
VIDEO_ARCHIVE_NAME = "VIDEO.HQR"
SMACKER_MAGIC_PREFIX = b"SMK"
SMACKER_HEADER_MIN_BYTES = 28
SCREEN_IMAGE_WIDTH = 640
SCREEN_IMAGE_HEIGHT = 480
SCREEN_IMAGE_PIXELS = SCREEN_IMAGE_WIDTH * SCREEN_IMAGE_HEIGHT
HOLOMAP_GLOBE_UV_BYTES = 2244
HOLOMAP_GLOBE_ALTITUDE_BYTES = 544
HOLOMAP_GLOBE_TEXTURE_PIXELS = 256 * 256
HOLOMAP_ARROW_RECORD_BYTES = 32
HOLOMAP_ARROW_RECORD_COUNT = 305
HOLOMAP_PLAN_PARAM_BYTES = 36
HOLOMAP_TEXT_FILE_INDEX = 2
HOLOMAP_BEGIN_MAP_ENTRY_INDEX = 18
HOLOMAP_PLAN_VARIANT_COUNT = 14
BKG_HEADER_BYTES = 28
BKG_CUBE_SIZE_X = 64
BKG_CUBE_SIZE_Y = 25
BKG_CUBE_SIZE_Z = 64
BKG_GRID_HEADER_BYTES = 34
BKG_GRID_COLUMN_COUNT = BKG_CUBE_SIZE_X * BKG_CUBE_SIZE_Z
BKG_GRID_OFFSET_TABLE_BYTES = BKG_GRID_COLUMN_COUNT * 2
BKG_BLOCK_RECORD_BYTES = 4
BKG_GRAPH_HEADER_BYTES = 4
BKG_CUBE_MAP_RECORD_BYTES = 2
BKG_CUBE_MAP_RECORD_COUNT = 256
BKG_WORLD_CELL_SIZE_XZ = 512
BKG_WORLD_CELL_SIZE_Y = 256
TEXT_FILES_PER_LANGUAGE = 15
TEXT_ENTRIES_PER_LANGUAGE = TEXT_FILES_PER_LANGUAGE * 2
TEXT_START_FILE_ISLAND = 3
TEXT_LANGUAGE_NAMES = ("English", "Francais", "Deutsch", "Espanol", "Italiano", "Portugues")
TEXT_FILE_NAMES = (
    "sys",
    "cre",
    "gam",
    "000",
    "001",
    "002",
    "003",
    "004",
    "005",
    "006",
    "007",
    "008",
    "009",
    "010",
    "011",
)
RESS_GOODIES_GPC_ENTRY_INDEX = 5
RESS_GOODRAW_GPC_ENTRY_INDEX = 8
RESS_ANIM3DS_GPC_ENTRY_INDEX = 43
RESS_EXT_SIZE_INFO_ENTRY_INDEX = 2
RESS_ACFLIST_ENTRY_INDEX = 48
RESS_XPL_ENTRY_NAMES = {
    27: "Citadel",
    28: "Puits de Sendell",
    29: "desert",
    30: "emeraude",
    31: "otringal",
    32: "celebrat",
    33: "Blafards/Plateforme",
    34: "Mosquibees",
    35: "Knartas",
    36: "Ilot CX",
    37: "Ascenceur",
    38: "orphan shading palette",
    42: "citabau",
}
RESS_XPL_COMMON_H_ENTRY_INDICES = frozenset({27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 42})
RESS_XPL_HQD_ONLY_ENTRY_INDICES = frozenset({38})
RESS_XPL0_ENTRY_INDEX = 27
RESS_XPL00_ENTRY_INDEX = 42
CUBE_INTERIEUR = 0
CUBE_EXTERIEUR = 1
SCREEN_PCR_ENTRY_NAMES = {
    0: "logo",
    2: "bumper",
    4: "menu",
    6: "slate",
    8: "Citadel sewer",
    10: "Citadel exterior",
    12: "principal labyrinth",
    14: "ascenceur labyrinth",
    16: "principal moon",
    18: "ascenceur moon",
    20: "hacienda",
    22: "lighthouse view",
    24: "lighthouse view 2",
    60: "CD-ROM wait",
    72: "Activision logo",
    74: "EA logo",
    76: "Virgin logo",
}
SCREEN_PCR_CODE_REFERENCES: dict[int, list[dict[str, Any]]] = {
    0: [
        {
            "symbol": "PCR_LOGO",
            "purpose": "startup logo screen loaded with its paired PCR_LOGO+1 palette",
            "source": "COMMON.H / GAMEMENU.CPP::ShowLogo",
        }
    ],
    2: [
        {
            "symbol": "PCR_BUMPER",
            "purpose": "bumper/logo screen loaded with its paired PCR_BUMPER+1 palette",
            "source": "COMMON.H / GAMEMENU.CPP::ShowLogo",
        }
    ],
    4: [
        {
            "symbol": "PCR_MENU",
            "purpose": "main menu background reloaded into Screen/Log around menu flows",
            "source": "COMMON.H / GAMEMENU.CPP",
        }
    ],
    6: [
        {
            "symbol": "PCR_ARDOISE",
            "purpose": "inventory slate background",
            "source": "COMMON.H / INVENT.CPP",
        }
    ],
    60: [
        {
            "symbol": "PCR_CDROM",
            "purpose": "CD-ROM wait/change-disc screen used by config/message startup paths",
            "source": "COMMON.H / CONFIG.CPP / MESSAGE.CPP / PERSO.CPP",
        }
    ],
    72: [
        {
            "symbol": "PCR_ACTIVISION",
            "purpose": "publisher logo screen",
            "source": "COMMON.H / GAMEMENU.CPP::ShowLogo",
        }
    ],
    74: [
        {
            "symbol": "PCR_EA",
            "purpose": "publisher logo screen",
            "source": "COMMON.H / GAMEMENU.CPP::ShowLogo",
        }
    ],
    76: [
        {
            "symbol": "PCR_VIRGIN",
            "purpose": "publisher logo screen",
            "source": "COMMON.H / GAMEMENU.CPP::ShowLogo",
        }
    ],
}
HOLOMAP_ENTRY_NAMES = {
    0: "globe coordinate map",
    1: "Twinsun altitude map",
    2: "Twinsun texture map",
    3: "Moon altitude map",
    4: "Moon texture map",
    5: "Zeelich altitude map",
    6: "Zeelich texture map",
    7: "Under-gas altitude map",
    8: "Under-gas texture map",
    9: "Sun texture map",
    10: "holomap arrow model",
    11: "holomap short arrow model",
    12: "holomap arrow table",
    13: "holomap buggy model",
    14: "holomap Dino-Fly model",
}
HOLOMAP_PLAN_BASE_NAMES = {
    0: "Citadel",
    1: "Puits de Sendell",
    2: "Desert",
    3: "Emerald Moon",
    4: "Otringal",
    5: "Celebration Island",
    6: "Blafards/Platform",
    7: "Mosquibees",
    8: "Knartas",
    9: "Island CX",
    10: "Elevator",
    11: "Island 11",
    12: "Citadel after storm",
    13: "Celebration Island after celebration",
}
SPRITE_3D_FLAG = 1 << 10
ANIM_3DS_FLAG = 1 << 18
SPRITE_CLIP_FLAG = 1 << 3
INVISIBLE_FLAG = 1 << 9
NO_SHADOW_FLAG = 1 << 12
OBJ_BACKGROUND_FLAG = 1 << 13
NO_PRE_CLIP_FLAG = 1 << 19
OBJ_ZBUFFER_FLAG = 1 << 20
OBJ_IN_WATER_FLAG = 1 << 21
SCENE_OBJECT_FLAG_NAMES = {
    1 << 0: "CHECK_OBJ_COL",
    1 << 1: "CHECK_BRICK_COL",
    1 << 2: "CHECK_ZONE",
    SPRITE_CLIP_FLAG: "SPRITE_CLIP",
    1 << 4: "PUSHABLE",
    1 << 5: "COL_BASSE",
    1 << 6: "CHECK_CODE_JEU",
    1 << 7: "CHECK_ONLY_FLOOR",
    INVISIBLE_FLAG: "INVISIBLE",
    SPRITE_3D_FLAG: "SPRITE_3D",
    1 << 11: "OBJ_FALLABLE",
    NO_SHADOW_FLAG: "NO_SHADOW",
    OBJ_BACKGROUND_FLAG: "OBJ_BACKGROUND",
    1 << 14: "OBJ_CARRIER",
    1 << 15: "MINI_ZV",
    1 << 16: "POS_INVALIDE",
    1 << 17: "NO_CHOC",
    ANIM_3DS_FLAG: "ANIM_3DS",
    NO_PRE_CLIP_FLAG: "NO_PRE_CLIP",
    OBJ_ZBUFFER_FLAG: "OBJ_ZBUFFER",
    OBJ_IN_WATER_FLAG: "OBJ_IN_WATER",
}
SCENE_OBJECT_OPTION_FLAG_NAMES = {
    1: "EXTRA_GIVE_NOTHING",
    16: "EXTRA_GIVE_MONEY",
    32: "EXTRA_GIVE_LIFE",
    64: "EXTRA_GIVE_MAGIC",
    128: "EXTRA_GIVE_KEY",
    256: "EXTRA_GIVE_CLOVER",
}
SCENE_MOVE_NAMES = {
    0: "NO_MOVE",
    1: "MOVE_MANUAL",
    2: "MOVE_FOLLOW",
    3: "MOVE_TRACK",
    4: "MOVE_FOLLOW_2",
    5: "MOVE_TRACK_ATTACK",
    6: "MOVE_SAME_XZ",
    7: "MOVE_PINGOUIN",
    8: "MOVE_WAGON",
    9: "MOVE_CIRCLE",
    10: "MOVE_CIRCLE2",
    11: "MOVE_SAME_XZ_BETA",
    12: "MOVE_BUGGY",
    13: "MOVE_BUGGY_MANUAL",
}
SCENE_ZONE_RECORD_BYTES = 60
SCENE_TRACK_RECORD_BYTES = 12
SCENE_PATCH_RECORD_BYTES = 4
PALETTE_ARCHIVE_NAME = "RESS.HQR"
OBJFIX_ARCHIVE_NAME = "OBJFIX.HQR"
PALETTE_ENTRY_INDEX = 0
PALETTE_CATALOG_ENTRY_INDEX = 0
PALETTE_BYTES = 256 * 3
TEXTURE_ENTRY_INDEX = 6
TEXTURE_CATALOG_ENTRY_INDEX = 6
TEXTURE_ATLAS_SIZE = 256
TEXTURE_ATLAS_PIXELS = TEXTURE_ATLAS_SIZE * TEXTURE_ATLAS_SIZE
FILE3D_ENTRY_INDEX = 44
RESS_FIXED_S16_TABLE_ENTRY_INDEX = 45
RESS_OFFSET_TABLE_ENTRY_INDICES = {1, 46, 47}
RESS_FIXED_S16_RECORD_BYTES = 16
RESS_RUNTIME_TABLES: dict[int, dict[str, str]] = {
    45: {
        "runtime_table_name": "RESS_FLOW",
        "runtime_buffer": "TabPartFlow",
        "runtime_purpose": "Particle flow definitions loaded for ListPartFlow runtime effects.",
        "runtime_reference_status": "classic RESS_FLOW entry loaded into TabPartFlow",
        "source_provenance": "COMMON.H defines RESS_FLOW=45; MEM.CPP sizes TabPartFlowMem from HQF_ResSize(RESS_FLOW); FLOW.CPP::Load_HQR loads RESS_FLOW into TabPartFlow.",
    },
    46: {
        "runtime_table_name": "RESS_POF",
        "runtime_buffer": "BufferPof",
        "runtime_purpose": "POF effect records addressed through BufferPof offset entries.",
        "runtime_reference_status": "classic RESS_POF entry loaded into BufferPof",
        "source_provenance": "COMMON.H defines RESS_POF=46; MEM.CPP sizes BufferPofMem from HQF_ResSize(RESS_POF); PERSO.CPP loads RESS_POF into BufferPof; POF.CPP addresses records through the table offsets.",
    },
    47: {
        "runtime_table_name": "RESS_IMPACT",
        "runtime_buffer": "BufferImpact",
        "runtime_purpose": "Impact effect records addressed through BufferImpact offset entries.",
        "runtime_reference_status": "classic RESS_IMPACT entry loaded into BufferImpact",
        "source_provenance": "COMMON.H defines RESS_IMPACT=47; MEM.CPP sizes BufferImpactMem from HQF_ResSize(RESS_IMPACT); PERSO.CPP loads RESS_IMPACT into BufferImpact; IMPACT.CPP addresses records through the table offsets.",
    },
}
FILE3D_COMMAND_BODY = 1
FILE3D_COMMAND_ANIM = 3
FILE3D_COMMAND_END = 255
SCENE_ZONE_TYPE_NAMES = {
    0: "change_cube",
    1: "camera",
    2: "scenario",
    3: "fragment_grm",
    4: "giver",
    5: "message",
    6: "ladder",
    7: "escalator",
    8: "hit",
    9: "rail",
}
ZONE_INIT_ON = 1
ZONE_ON = 2
ZONE_ACTIVE = 4
ZONE_OBLIGATOIRE = 8
ZONE_DONT_REAJUST_POS_TWINSEN = 2
ZONE_TEST_BRICK = 2
ZONE_INFO7_FLAG_NAMES = {
    ZONE_INIT_ON: "ZONE_INIT_ON",
    ZONE_ON: "ZONE_ON",
    ZONE_ACTIVE: "ZONE_ACTIVE",
    ZONE_OBLIGATOIRE: "ZONE_OBLIGATOIRE",
}
ZONE_INFO5_FLAG_NAMES = {ZONE_TEST_BRICK: "ZONE_TEST_BRICK"}
ZONE_INFO6_FLAG_NAMES = {
    ZONE_DONT_REAJUST_POS_TWINSEN: "ZONE_DONT_REAJUST_POS_TWINSEN"
}
SCENE_ZONE_DIRECTION_NAMES = {
    1: "north",
    2: "south",
    4: "east",
    8: "west",
}
SCENE_MESSAGE_FACING_RULES: dict[int, dict[str, Any]] = {
    1: {
        "direction": "north",
        "angle_points": {
            "angle": {"x": "X0", "z": "Z0"},
            "angle1": {"x": "X1", "z": "Z0"},
        },
        "beta_condition": "Obj.Beta >= angle1 && Obj.Beta <= angle",
        "wraps_zero": False,
    },
    2: {
        "direction": "south",
        "angle_points": {
            "angle": {"x": "X0", "z": "Z1"},
            "angle1": {"x": "X1", "z": "Z1"},
        },
        "beta_condition": "Obj.Beta >= angle || Obj.Beta <= angle1",
        "wraps_zero": True,
    },
    4: {
        "direction": "east",
        "angle_points": {
            "angle": {"x": "X1", "z": "Z0"},
            "angle1": {"x": "X1", "z": "Z1"},
        },
        "beta_condition": "Obj.Beta >= angle1 && Obj.Beta <= angle",
        "wraps_zero": False,
    },
    8: {
        "direction": "west",
        "angle_points": {
            "angle": {"x": "X0", "z": "Z1"},
            "angle1": {"x": "X0", "z": "Z0"},
        },
        "beta_condition": "Obj.Beta >= angle1 && Obj.Beta <= angle",
        "wraps_zero": False,
    },
}
SCENE_ZONE_RUNTIME_CONTRACT_FIELDS = {
    "camera_application": "camera",
    "change_cube_application": "change_cube",
    "message_application": "message",
    "bonus_application": "bonus",
    "hit_application": "hit",
    "ladder_application": "ladder",
    "escalator_application": "escalator",
    "rail_application": "rail",
    "grm_application": "grm",
    "scenario_application": "scenario",
}
GENERIC_ANIMATION_LABELS = {
    0: "Idle",
    1: "Walk",
    2: "Back up",
    3: "Turn left",
    4: "Turn right",
    5: "Take hit",
    6: "Impact",
    7: "Fall",
    8: "Land",
    9: "Hard land",
    10: "Death",
    11: "Action",
    12: "Climb up",
    13: "Ladder",
    14: "Jump",
    15: "Throw",
    16: "Hide",
    17: "Punch 1",
    18: "Punch 2",
    19: "Punch 3",
    20: "Found item",
    21: "Drown",
    22: "Impact 2",
    23: "Sword attack",
    24: "Draw sword",
    25: "Jump left",
    26: "Jump right",
    27: "Push",
    28: "Talk",
    29: "Dart",
    30: "Climb down",
    31: "Ladder down",
    32: "Dock/attach",
    33: "Skate",
    34: "Skate left",
    35: "Blowgun",
    36: "Glove right",
    37: "Glove left",
    38: "Laser pistol",
    39: "Lightning",
    40: "Dodge right",
    41: "Dodge left",
    42: "Dodge forward",
    43: "Dodge backward",
    44: "Burning",
    45: "Blowtron",
    46: "Gas death",
    47: "Labyrinth death",
}
GENERIC_ANIMATION_NAMES = {
    0: "GEN_ANIM_RIEN",
    1: "GEN_ANIM_MARCHE",
    2: "GEN_ANIM_RECULE",
    3: "GEN_ANIM_GAUCHE",
    4: "GEN_ANIM_DROITE",
    5: "GEN_ANIM_ENCAISSE",
    6: "GEN_ANIM_CHOC",
    7: "GEN_ANIM_TOMBE",
    8: "GEN_ANIM_RECEPTION",
    9: "GEN_ANIM_RECEPTION_2",
    10: "GEN_ANIM_MORT",
    11: "GEN_ANIM_ACTION",
    12: "GEN_ANIM_MONTE",
    13: "GEN_ANIM_ECHELLE",
    14: "GEN_ANIM_SAUTE",
    15: "GEN_ANIM_LANCE",
    16: "GEN_ANIM_CACHE",
    17: "GEN_ANIM_COUP_1",
    18: "GEN_ANIM_COUP_2",
    19: "GEN_ANIM_COUP_3",
    20: "GEN_ANIM_TROUVE",
    21: "GEN_ANIM_NOYADE",
    22: "GEN_ANIM_CHOC2",
    23: "GEN_ANIM_SABRE",
    24: "GEN_ANIM_DEGAINE",
    25: "GEN_ANIM_SAUTE_GAUCHE",
    26: "GEN_ANIM_SAUTE_DROIT",
    27: "GEN_ANIM_POUSSE",
    28: "GEN_ANIM_PARLE",
    29: "GEN_ANIM_DART",
    30: "GEN_ANIM_DESCEND",
    31: "GEN_ANIM_ECHDESC",
    32: "GEN_ANIM_ARRIMAGE",
    33: "GEN_ANIM_SKATE",
    34: "GEN_ANIM_SKATEG",
    35: "GEN_ANIM_SARBACANE",
    36: "GEN_ANIM_GANT_DROIT",
    37: "GEN_ANIM_GANT_GAUCHE",
    38: "GEN_ANIM_PISTOLASER",
    39: "GEN_ANIM_FOUDRE",
    40: "GEN_ANIM_ESQUIVE_DROITE",
    41: "GEN_ANIM_ESQUIVE_GAUCHE",
    42: "GEN_ANIM_ESQUIVE_AVANT",
    43: "GEN_ANIM_ESQUIVE_ARRIERE",
    44: "GEN_ANIM_FEU",
    45: "GEN_ANIM_SARBATRON",
    46: "GEN_ANIM_GAZ",
    47: "GEN_ANIM_LABYRINTHE",
}


class Lm2Error(ValueError):
    pass


def parse_multipart_upload(content_type: str, body: bytes) -> dict[str, Any]:
    if "\r" in content_type or "\n" in content_type:
        raise Lm2Error("invalid content-type header")
    header_blob = (f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode(
        "utf-8"
    )
    message = BytesParser(policy=policy.default).parsebytes(header_blob + body)
    if (
        message.get_content_type() != "multipart/form-data"
        or not message.is_multipart()
    ):
        raise Lm2Error("expected multipart/form-data upload")

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "file":
            continue
        data = part.get_payload(decode=True)
        if data is None:
            raise Lm2Error("upload file field could not be decoded")
        filename = part.get_filename() or "upload.lm2"
        return {"filename": filename, "data": data}
    raise Lm2Error("upload did not include a file field")


@dataclass
class DecodeProgress:
    active: bool = False
    phase: str = "idle"
    label: str = ""
    current: int = 0
    total: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def begin(self, label: str, total: int = 0, phase: str = "decoding") -> None:
        now = time.monotonic()
        with self.lock:
            self.active = True
            self.phase = phase
            self.label = label
            self.current = 0
            self.total = total
            self.started_at = now
            self.finished_at = None
            self.error = None
            self.summary = None

    def update(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        label: str | None = None,
        phase: str | None = None,
    ) -> None:
        with self.lock:
            if current is not None:
                self.current = current
            if total is not None:
                self.total = total
            if label is not None:
                self.label = label
            if phase is not None:
                self.phase = phase

    def finish(self, summary: dict[str, Any] | None = None) -> None:
        now = time.monotonic()
        with self.lock:
            self.active = False
            self.phase = "complete"
            if self.total:
                self.current = self.total
            self.label = "Decode complete"
            self.finished_at = now
            self.error = None
            self.summary = summary

    def fail(self, error: str) -> None:
        now = time.monotonic()
        with self.lock:
            self.active = False
            self.phase = "error"
            self.label = "Decode failed"
            self.finished_at = now
            self.error = error

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            elapsed_source = self.finished_at if self.finished_at is not None else now
            elapsed = (
                0.0
                if self.started_at is None
                else max(0.0, elapsed_source - self.started_at)
            )
            percent = (self.current / self.total) if self.total else None
            return {
                "active": self.active,
                "phase": self.phase,
                "label": self.label,
                "current": self.current,
                "total": self.total,
                "percent": percent,
                "elapsed_seconds": elapsed,
                "error": self.error,
                "summary": self.summary,
            }


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.index = 0

    def require(self, size: int) -> None:
        if self.index + size > len(self.data):
            raise Lm2Error(
                f"unexpected end of file at 0x{self.index:x}, need {size} bytes"
            )

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise Lm2Error(
                f"offset 0x{offset:x} is outside file size 0x{len(self.data):x}"
            )
        self.index = offset

    def skip(self, size: int) -> None:
        self.seek(self.index + size)

    def u8(self) -> int:
        self.require(1)
        value = self.data[self.index]
        self.index += 1
        return value

    def s8(self) -> int:
        self.require(1)
        value = struct.unpack_from("<b", self.data, self.index)[0]
        self.index += 1
        return value

    def u16(self) -> int:
        self.require(2)
        value = struct.unpack_from("<H", self.data, self.index)[0]
        self.index += 2
        return value

    def s16(self) -> int:
        self.require(2)
        value = struct.unpack_from("<h", self.data, self.index)[0]
        self.index += 2
        return value

    def u32(self) -> int:
        self.require(4)
        value = struct.unpack_from("<I", self.data, self.index)[0]
        self.index += 4
        return value

    def s32(self) -> int:
        self.require(4)
        value = struct.unpack_from("<i", self.data, self.index)[0]
        self.index += 4
        return value


@dataclass(frozen=True)
class Lm2Header:
    flags: int
    bounds: tuple[int, int, int, int, int, int]
    bones_count: int
    bones_offset: int
    vertices_count: int
    vertices_offset: int
    normals_count: int
    normals_offset: int
    unknown_count: int
    unknown_offset: int
    polygons_size: int
    polygons_offset: int
    lines_count: int
    lines_offset: int
    spheres_count: int
    spheres_offset: int
    uv_groups_count: int
    uv_groups_offset: int

    @property
    def version(self) -> int:
        return self.flags & 0xFF

    @property
    def has_animation(self) -> bool:
        return bool(self.flags & (1 << 8))

    @property
    def no_sort(self) -> bool:
        return bool(self.flags & (1 << 9))

    @property
    def has_transparency(self) -> bool:
        return bool(self.flags & (1 << 10))


@dataclass(frozen=True)
class Bone:
    parent: int
    vertex: int
    unknown_1: int
    unknown_2: int


@dataclass(frozen=True)
class Vertex:
    x: float
    y: float
    z: float
    bone: int


@dataclass(frozen=True)
class Normal:
    x: float
    y: float
    z: float
    unknown: int


@dataclass(frozen=True)
class Polygon:
    render_type: int
    vertices: tuple[int, ...]
    color: int
    color_word: int
    palette_index: int
    intensity: int
    has_texture: bool
    has_extra: bool
    has_transparency: bool
    texture: int | None
    uv: tuple[tuple[float, float], ...] | None


@dataclass(frozen=True)
class LinePrimitive:
    color: int
    color_word: int
    palette_index: int
    vertex_1: int
    vertex_2: int
    unknown: int


@dataclass(frozen=True)
class SpherePrimitive:
    color: int
    color_word: int
    palette_index: int
    vertex: int
    size: int
    unknown: int


@dataclass(frozen=True)
class UvGroup:
    x: int
    y: int
    w: int
    h: int

    def to_json(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class Lm2Model:
    header: Lm2Header
    bones: tuple[Bone, ...]
    vertices: tuple[Vertex, ...]
    normals: tuple[Normal, ...]
    polygons: tuple[Polygon, ...]
    lines: tuple[LinePrimitive, ...]
    spheres: tuple[SpherePrimitive, ...]
    uv_groups: tuple[UvGroup, ...]
    raw_vertices: tuple[Vertex, ...] = ()

    def to_viewer_json(
        self,
        source_name: str | None = None,
        palette: list[int] | None = None,
        texture_atlas: dict[str, Any] | None = None,
        pose: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw_bounds = self.header.bounds
        xs = [v.x for v in self.vertices]
        ys = [v.y for v in self.vertices]
        zs = [v.z for v in self.vertices]
        bounds = {
            "x": [min(xs, default=0), max(xs, default=0)],
            "y": [min(ys, default=0), max(ys, default=0)],
            "z": [min(zs, default=0), max(zs, default=0)],
            "raw": {
                "x": [raw_bounds[0], raw_bounds[1]],
                "y": [raw_bounds[2], raw_bounds[3]],
                "z": [raw_bounds[4], raw_bounds[5]],
            },
        }
        payload = {
            "source": source_name,
            "format": "lm2",
            "scale": WORLD_SCALE,
            "palette": palette,
            "texture_atlas": texture_atlas,
            "header": {
                "flags": self.header.flags,
                "version": self.header.version,
                "has_animation": self.header.has_animation,
                "no_sort": self.header.no_sort,
                "has_transparency": self.header.has_transparency,
            },
            "stats": {
                "bones": len(self.bones),
                "vertices": len(self.vertices),
                "normals": len(self.normals),
                "polygons": len(self.polygons),
                "lines": len(self.lines),
                "spheres": len(self.spheres),
                "uv_groups": len(self.uv_groups),
            },
            "bounds": bounds,
            "vertices": [[v.x, v.y, v.z, v.bone] for v in self.vertices],
            "uv_groups": [group.to_json() for group in self.uv_groups],
            "polygons": [
                {
                    "vertices": list(poly.vertices),
                    "color": poly.color,
                    "color_word": poly.color_word,
                    "palette_index": poly.palette_index,
                    "intensity": poly.intensity,
                    "render_type": poly.render_type,
                    "has_texture": poly.has_texture,
                    "has_extra": poly.has_extra,
                    "has_transparency": poly.has_transparency,
                    "texture": poly.texture,
                    "uv": [[u, v] for u, v in poly.uv] if poly.uv is not None else None,
                }
                for poly in self.polygons
            ],
            "lines": [
                {
                    "vertices": [line.vertex_1, line.vertex_2],
                    "color": line.color,
                    "color_word": line.color_word,
                    "palette_index": line.palette_index,
                    "unknown": line.unknown,
                }
                for line in self.lines
            ],
            "spheres": [
                {
                    "vertex": sphere.vertex,
                    "size": sphere.size * WORLD_SCALE,
                    "color": sphere.color,
                    "color_word": sphere.color_word,
                    "palette_index": sphere.palette_index,
                    "unknown": sphere.unknown,
                }
                for sphere in self.spheres
            ],
            "bones": [
                {
                    "parent": bone.parent,
                    "vertex": bone.vertex,
                    "unknown_1": bone.unknown_1,
                    "unknown_2": bone.unknown_2,
                }
                for bone in self.bones
            ],
        }
        if pose is not None:
            payload["pose"] = pose
        return payload


def read_header(reader: Reader) -> Lm2Header:
    if len(reader.data) < 0x60:
        raise Lm2Error(
            f"LM2 file is too small for a 0x60-byte header: {len(reader.data)} bytes"
        )
    flags = reader.s32()
    reader.s32()
    x_min = reader.s32()
    x_max = reader.s32()
    y_min = reader.s32()
    y_max = reader.s32()
    z_min = reader.s32()
    z_max = reader.s32()
    values = [reader.u32() for _ in range(16)]
    header = Lm2Header(
        flags=flags,
        bounds=(x_min, x_max, y_min, y_max, z_min, z_max),
        bones_count=values[0],
        bones_offset=values[1],
        vertices_count=values[2],
        vertices_offset=values[3],
        normals_count=values[4],
        normals_offset=values[5],
        unknown_count=values[6],
        unknown_offset=values[7],
        polygons_size=values[8],
        polygons_offset=values[9],
        lines_count=values[10],
        lines_offset=values[11],
        spheres_count=values[12],
        spheres_offset=values[13],
        uv_groups_count=values[14],
        uv_groups_offset=values[15],
    )
    offsets = [
        header.bones_offset,
        header.vertices_offset,
        header.normals_offset,
        header.unknown_offset,
        header.polygons_offset,
        header.lines_offset,
        header.spheres_offset,
        header.uv_groups_offset,
    ]
    for offset in offsets:
        if offset > len(reader.data):
            raise Lm2Error(
                f"section offset 0x{offset:x} exceeds file size 0x{len(reader.data):x}"
            )
    return header


def parse_lm2(data: bytes) -> Lm2Model:
    reader = Reader(data)
    header = read_header(reader)

    reader.seek(header.bones_offset)
    bones = tuple(
        Bone(reader.u16(), reader.u16(), reader.u16(), reader.u16())
        for _ in range(header.bones_count)
    )

    reader.seek(header.vertices_offset)
    raw_vertices = tuple(
        Vertex(
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.u16(),
        )
        for _ in range(header.vertices_count)
    )
    vertices = tuple(
        resolve_vertex(vertex, raw_vertices, bones, index)
        for index, vertex in enumerate(raw_vertices)
    )

    reader.seek(header.normals_offset)
    normals = tuple(
        Normal(
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.s16() * WORLD_SCALE,
            reader.u16(),
        )
        for _ in range(header.normals_count)
    )

    reader.seek(header.unknown_offset)
    reader.skip(header.unknown_count * 8)

    polygons = parse_polygons(reader, header)

    reader.seek(header.lines_offset)
    lines: list[LinePrimitive] = []
    for _ in range(header.lines_count):
        unknown = reader.u16()
        color_word = reader.u16()
        color = color_index(color_word)
        lines.append(
            LinePrimitive(
                unknown=unknown,
                color=color,
                color_word=color_word,
                palette_index=color,
                vertex_1=reader.u16(),
                vertex_2=reader.u16(),
            )
        )

    reader.seek(header.spheres_offset)
    spheres: list[SpherePrimitive] = []
    for _ in range(header.spheres_count):
        unknown = reader.u16()
        color_word = reader.u16()
        color = color_index(color_word)
        spheres.append(
            SpherePrimitive(
                unknown=unknown,
                color=color,
                color_word=color_word,
                palette_index=color,
                vertex=reader.u16(),
                size=reader.u16(),
            )
        )

    reader.seek(header.uv_groups_offset)
    uv_groups = tuple(
        UvGroup(reader.u8(), reader.u8(), reader.u8(), reader.u8())
        for _ in range(header.uv_groups_count)
    )

    validate_indices(vertices, bones, polygons, lines, spheres)
    return Lm2Model(
        header,
        bones,
        vertices,
        normals,
        polygons,
        tuple(lines),
        tuple(spheres),
        uv_groups,
        raw_vertices,
    )


def resolve_vertex(
    vertex: Vertex,
    raw_vertices: tuple[Vertex, ...],
    bones: tuple[Bone, ...],
    vertex_index: int,
) -> Vertex:
    if vertex.bone >= len(bones):
        raise Lm2Error(f"vertex {vertex_index} references missing bone {vertex.bone}")
    x, y, z = vertex.x, vertex.y, vertex.z
    seen: set[int] = set()
    next_bone_index = vertex.bone
    while True:
        if next_bone_index in seen:
            raise Lm2Error(f"bone parent cycle while resolving vertex {vertex_index}")
        seen.add(next_bone_index)
        bone = bones[next_bone_index]
        if bone.vertex >= len(raw_vertices):
            raise Lm2Error(
                f"bone {next_bone_index} references missing vertex {bone.vertex}"
            )
        pivot = raw_vertices[bone.vertex]
        x += pivot.x
        y += pivot.y
        z += pivot.z
        if bone.parent > 1000:
            break
        if bone.parent >= len(bones):
            raise Lm2Error(f"bone {next_bone_index} has invalid parent {bone.parent}")
        next_bone_index = bone.parent
    return Vertex(x, y, z, vertex.bone)


Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


def pose_lm2_model(
    model: Lm2Model,
    animation: Lba2Animation,
    *,
    sample_frame: int = 0,
    previous_frame: int | None = None,
    elapsed_ms: int = 0,
) -> tuple[Lm2Model, dict[str, Any]]:
    if animation.bone_count != len(model.bones):
        raise AnimationError(
            "animation bone count "
            f"{animation.bone_count} does not match model bone count {len(model.bones)}"
        )
    local_vertices = model.raw_vertices
    if not local_vertices:
        raise Lm2Error("posing requires local raw vertices")
    if len(local_vertices) != len(model.vertices):
        raise Lm2Error("model raw vertex count does not match resolved vertex count")

    sample = sample_keyframe_transition(
        animation,
        target_frame_index=sample_frame,
        elapsed_ms=elapsed_ms,
        previous_index=previous_frame,
        body_bone_count=len(model.bones),
    )
    bone_samples = {bone["index"]: bone for bone in sample["bones"]}
    root_delta = sample["root_delta"]
    root_matrix = translation_matrix(
        root_delta[0] * WORLD_SCALE,
        root_delta[1] * WORLD_SCALE,
        root_delta[2] * WORLD_SCALE,
    )
    bone_matrices: list[Matrix4 | None] = [None] * len(model.bones)

    for index in range(len(model.bones)):
        build_bone_pose_matrix(index, model, local_vertices, bone_samples, bone_matrices, root_matrix)

    posed_vertices: list[Vertex] = []
    for vertex in local_vertices:
        matrix = bone_matrices[vertex.bone]
        if matrix is None:
            raise Lm2Error(f"missing pose matrix for bone {vertex.bone}")
        x, y, z = transform_point(matrix, (vertex.x, vertex.y, vertex.z))
        posed_vertices.append(Vertex(x, y, z, vertex.bone))

    pose = {
        "animation": {
            "keyframes": animation.keyframe_count,
            "boneframes": animation.bone_count,
            "loop_frame": animation.loop_start_keyframe,
        },
        "sample": sample,
        "transform": {
            "rotation_units": "12bit_turn",
            "rotation_order": "x_y_z",
            "translation_scale": WORLD_SCALE,
            "vertex_space": "lm2_local_vertices_transformed_to_world",
        },
    }
    return replace(model, vertices=tuple(posed_vertices)), pose


def build_bone_pose_matrix(
    index: int,
    model: Lm2Model,
    local_vertices: tuple[Vertex, ...],
    bone_samples: dict[int, dict[str, Any]],
    bone_matrices: list[Matrix4 | None],
    root_matrix: Matrix4,
) -> Matrix4:
    cached = bone_matrices[index]
    if cached is not None:
        return cached
    bone = model.bones[index]
    if bone.vertex >= len(local_vertices):
        raise Lm2Error(f"bone {index} references missing vertex {bone.vertex}")

    if bone.parent > 1000:
        parent_matrix = root_matrix
    else:
        if bone.parent >= len(model.bones):
            raise Lm2Error(f"bone {index} has invalid parent {bone.parent}")
        parent_matrix = build_bone_pose_matrix(
            bone.parent,
            model,
            local_vertices,
            bone_samples,
            bone_matrices,
            root_matrix,
        )

    pivot = local_vertices[bone.vertex]
    matrix = multiply_matrix(
        parent_matrix,
        multiply_matrix(
            translation_matrix(pivot.x, pivot.y, pivot.z),
            animation_bone_matrix(bone_samples.get(index)),
        ),
    )
    bone_matrices[index] = matrix
    return matrix


def animation_bone_matrix(bone_sample: dict[str, Any] | None) -> Matrix4:
    if bone_sample is None:
        return identity_matrix()
    values = bone_sample.get("values")
    if not isinstance(values, list) or len(values) != 3:
        raise AnimationError("sampled bone transform is missing three values")
    mode = bone_sample.get("mode")
    if mode == 0:
        return rotation_xyz_matrix(
            turn12_to_radians(values[0]),
            turn12_to_radians(values[1]),
            turn12_to_radians(values[2]),
        )
    if mode in (1, 2):
        return translation_matrix(
            values[0] * WORLD_SCALE,
            values[1] * WORLD_SCALE,
            values[2] * WORLD_SCALE,
        )
    raise AnimationError(f"unsupported animation mode {mode}")


def identity_matrix() -> Matrix4:
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def translation_matrix(x: float, y: float, z: float) -> Matrix4:
    return (
        (1.0, 0.0, 0.0, x),
        (0.0, 1.0, 0.0, y),
        (0.0, 0.0, 1.0, z),
        (0.0, 0.0, 0.0, 1.0),
    )


def rotation_xyz_matrix(x: float, y: float, z: float) -> Matrix4:
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    rotate_x: Matrix4 = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, cx, -sx, 0.0),
        (0.0, sx, cx, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    rotate_y: Matrix4 = (
        (cy, 0.0, sy, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (-sy, 0.0, cy, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    rotate_z: Matrix4 = (
        (cz, -sz, 0.0, 0.0),
        (sz, cz, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return multiply_matrix(multiply_matrix(rotate_z, rotate_y), rotate_x)


def multiply_matrix(left: Matrix4, right: Matrix4) -> Matrix4:
    return tuple(
        tuple(
            sum(left[row][index] * right[index][column] for index in range(4))
            for column in range(4)
        )
        for row in range(4)
    )  # type: ignore[return-value]


def transform_point(matrix: Matrix4, point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def turn12_to_radians(value: int) -> float:
    return (value & 0x0FFF) * math.tau / 0x1000


def parse_polygons(reader: Reader, header: Lm2Header) -> tuple[Polygon, ...]:
    polygons: list[Polygon] = []
    offset = header.polygons_offset
    end = header.lines_offset
    while offset + 8 <= end:
        reader.seek(offset)
        render_type = reader.u16()
        polygon_count = reader.u16()
        section_size = reader.u16()
        reader.u16()
        if section_size == 0:
            break
        if polygon_count == 0:
            raise Lm2Error(f"polygon section at 0x{offset:x} has zero polygons")
        if offset + section_size > end:
            raise Lm2Error(f"polygon section at 0x{offset:x} exceeds polygon data end")
        block_size = (section_size - 8) // polygon_count
        if block_size <= 0 or (section_size - 8) % polygon_count != 0:
            raise Lm2Error(f"polygon section at 0x{offset:x} has invalid block size")
        item_offset = offset + 8
        for _ in range(polygon_count):
            polygons.append(parse_polygon(reader, item_offset, render_type, block_size))
            item_offset += block_size
        offset += section_size
    return tuple(polygons)


def parse_polygon(
    reader: Reader, offset: int, render_type: int, block_size: int
) -> Polygon:
    reader.seek(offset)
    vertex_count = 4 if render_type & 0x8000 else 3
    mode = render_type & 0x00FF
    textured_size = 32 if vertex_count == 4 else 24
    has_texture = mode >= 8 and block_size >= textured_size
    has_extra = bool(render_type & 0x4000)
    has_transparency = render_type == 2
    if mode >= 8 and 16 < block_size < textured_size:
        raise Lm2Error(
            f"polygon at 0x{offset:x} has ambiguous texture block size {block_size}, expected {textured_size}"
        )
    vertices = tuple(reader.u16() for _ in range(vertex_count))
    texture: int | None = None
    uv: tuple[tuple[float, float], ...] | None = None
    if has_texture:
        texture_offset = offset + (28 if vertex_count == 4 else 6)
        reader.seek(texture_offset)
        texture = reader.u16()
        uv = parse_polygon_uv(reader, offset + 12, vertex_count)
    reader.seek(offset + 8)
    color_word = reader.u16()
    color = color_index(color_word)
    intensity = reader.s16()
    return Polygon(
        render_type,
        vertices,
        color,
        color_word,
        color,
        intensity,
        has_texture,
        has_extra,
        has_transparency,
        texture,
        uv,
    )


def parse_polygon_uv(
    reader: Reader, offset: int, vertex_count: int
) -> tuple[tuple[float, float], ...]:
    reader.seek(offset)
    coords: list[tuple[float, float]] = []
    for _ in range(vertex_count):
        x_high = reader.u8()
        x_low = reader.u8()
        y_high = reader.u8()
        y_low = reader.u8()
        coords.append((x_low + (x_high / 256.0), y_low + (y_high / 256.0)))
    return tuple(coords)


def color_index(encoded: int) -> int:
    return encoded & 0x00FF


def validate_indices(
    vertices: tuple[Vertex, ...],
    bones: tuple[Bone, ...],
    polygons: tuple[Polygon, ...],
    lines: tuple[LinePrimitive, ...],
    spheres: tuple[SpherePrimitive, ...],
) -> None:
    vertex_count = len(vertices)
    for poly_index, poly in enumerate(polygons):
        for vertex_index in poly.vertices:
            if vertex_index >= vertex_count:
                raise Lm2Error(
                    f"polygon {poly_index} references missing vertex {vertex_index}"
                )
    for line_index, line in enumerate(lines):
        if line.vertex_1 >= vertex_count or line.vertex_2 >= vertex_count:
            raise Lm2Error(
                f"line {line_index} references missing vertex {line.vertex_1}/{line.vertex_2}"
            )
    for sphere_index, sphere in enumerate(spheres):
        if sphere.vertex >= vertex_count:
            raise Lm2Error(
                f"sphere {sphere_index} references missing vertex {sphere.vertex}"
            )
    for bone_index, bone in enumerate(bones):
        if bone.vertex >= vertex_count:
            raise Lm2Error(f"bone {bone_index} references missing vertex {bone.vertex}")


def reject_package_input(source_name: str) -> None:
    suffix = Path(source_name).suffix.lower()
    if suffix in PACKAGE_SUFFIXES:
        raise Lm2Error(
            f"{source_name} is a package container, not an LM2 model. "
            "Extract one model entry first, then load the .lm2/.ldc file."
        )


def load_lm2_bytes(data: bytes, source_name: str) -> Lm2Model:
    reject_package_input(source_name)
    return parse_lm2(data)


def load_lm2_path(path: Path) -> Lm2Model:
    reject_package_input(str(path))
    return parse_lm2(path.read_bytes())


def export_obj(model: Lm2Model, output_path: Path, name: str) -> None:
    lines = [
        f"# Exported from {name}",
        "# LM2 polygon mesh plus line primitives",
        "o lm2_model",
    ]
    for vertex in model.vertices:
        x, y, z = to_view_coords(vertex)
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for poly in model.polygons:
        indexes = [index + 1 for index in poly.vertices]
        if len(indexes) == 3:
            lines.append("f " + " ".join(str(index) for index in indexes))
        elif len(indexes) == 4:
            lines.append(f"f {indexes[0]} {indexes[1]} {indexes[2]}")
            lines.append(f"f {indexes[0]} {indexes[2]} {indexes[3]}")
    for line in model.lines:
        lines.append(f"l {line.vertex_1 + 1} {line.vertex_2 + 1}")
    for sphere in model.spheres:
        lines.append(
            f"# sphere vertex={sphere.vertex + 1} radius={sphere.size * WORLD_SCALE:.6f} color={sphere.color}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_view_coords(vertex: Vertex) -> tuple[float, float, float]:
    return vertex.x, vertex.y, vertex.z


def safe_path_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "asset"


def load_body_metadata() -> dict[int, dict[str, str]]:
    metadata_path = Path(__file__).resolve().with_name("body_metadata.json")
    if metadata_path.exists():
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        return {int(index): value for index, value in raw.items()}

    metadata_path = Path("port/src/generated/reference_metadata.zig")
    if not metadata_path.exists():
        return {}
    text = metadata_path.read_text(encoding="utf-8")
    start = text.find("pub const body_hqr_entries")
    end = text.find("pub const xx_gam_vox_entries")
    if start >= 0 and end > start:
        text = text[start:end]
    entries: dict[int, dict[str, str]] = {}
    pattern = re.compile(
        r"\.entry_index = (?P<index>\d+),\s+"
        r"\.entry_type = (?P<type>null|\"(?:\\.|[^\"])*\"),\s+"
        r"\.entry_description = (?P<description>null|\"(?:\\.|[^\"])*\")",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        index = int(match.group("index"))
        entry_type = match.group("type")
        description = match.group("description")
        entries[index] = {
            "type": "" if entry_type == "null" else json.loads(entry_type),
            "description": "" if description == "null" else json.loads(description),
        }
    return entries


def load_file3d_animation_metadata(asset_root: Path) -> dict[int, dict[str, Any]]:
    return load_file3d_metadata(asset_root)["animations"]


def load_file3d_metadata(asset_root: Path) -> dict[str, Any]:
    resource_path = asset_root / PALETTE_ARCHIVE_NAME
    if not resource_path.exists():
        return {"objects": {}, "animations": {}}
    data = resource_path.read_bytes()
    entries = lba_hqr.parse_table(data)
    matches = [entry for entry in entries if entry.index == FILE3D_ENTRY_INDEX]
    if not matches or matches[0].byte_length == 0:
        return {"objects": {}, "animations": {}}
    raw = lba_hqr.read_entry(data, matches[0])
    payload, _ = decoded_entry(raw)
    return parse_file3d_metadata(payload)


def parse_file3d_animation_metadata(payload: bytes) -> dict[int, dict[str, Any]]:
    return parse_file3d_metadata(payload)["animations"]


def parse_file3d_metadata(payload: bytes) -> dict[str, Any]:
    if len(payload) < 4:
        raise Lm2Error("File3D payload is too small")
    table_end = struct.unpack_from("<I", payload, 0)[0]
    if table_end < 4 or table_end % 4 != 0 or table_end > len(payload):
        raise Lm2Error(f"invalid File3D table header: 0x{table_end:x}")
    offsets = [
        struct.unpack_from("<I", payload, index * 4)[0]
        for index in range(table_end // 4)
    ]
    for offset in offsets:
        if offset != 0 and (offset < table_end or offset > len(payload)):
            raise Lm2Error(f"invalid File3D record offset: 0x{offset:x}")

    animation_metadata: dict[int, dict[str, Any]] = {}
    object_metadata: dict[int, dict[str, Any]] = {}
    for object_index, offset in enumerate(offsets):
        if offset == 0:
            continue
        next_offset = len(payload)
        for candidate in offsets[object_index + 1 :]:
            if candidate > offset:
                next_offset = min(next_offset, candidate)
        record_metadata = parse_file3d_record_details(
            payload[offset:next_offset], object_index
        )
        object_metadata[object_index] = record_metadata
        body_catalog_indices = sorted(
            {
                body["body_index"] + 1
                for body in record_metadata["body_records"]
                if body["body_index"] >= 0
            }
        )
        for animation in record_metadata["animation_records"]:
            animation_index = animation["animation_index"]
            generic_id = animation["generic_id"]
            if animation_index < 0:
                continue
            item = animation_metadata.setdefault(
                animation_index,
                {
                    "generic_ids": set(),
                    "generic_names": set(),
                    "labels": set(),
                    "file3d_objects": set(),
                    "compatible_body_ids": set(),
                },
            )
            item["generic_ids"].add(generic_id)
            item["generic_names"].add(
                GENERIC_ANIMATION_NAMES.get(generic_id, f"GEN_ANIM_{generic_id}")
            )
            item["labels"].add(
                GENERIC_ANIMATION_LABELS.get(generic_id, f"Generic animation {generic_id}")
            )
            item["file3d_objects"].add(object_index)
            item["compatible_body_ids"].update(body_catalog_indices)

    return {
        "objects": object_metadata,
        "animations": {
            index: {
                "generic_ids": sorted(value["generic_ids"]),
                "generic_names": sorted(value["generic_names"]),
                "labels": sorted(value["labels"]),
                "file3d_objects": sorted(value["file3d_objects"]),
                "compatible_body_ids": sorted(value["compatible_body_ids"]),
            }
            for index, value in animation_metadata.items()
        },
    }


def parse_file3d_record_details(record: bytes, object_index: int) -> dict[str, Any]:
    cursor = 0
    body_records: list[dict[str, Any]] = []
    animation_records: list[dict[str, Any]] = []
    unknown_commands: list[dict[str, Any]] = []
    while cursor < len(record):
        command_offset = cursor
        command = record[cursor]
        cursor += 1
        if command == FILE3D_COMMAND_END:
            break
        if command == FILE3D_COMMAND_ANIM:
            require_file3d_bytes(record, cursor, 3, object_index)
            generic_id = struct.unpack_from("<H", record, cursor)[0]
            cursor += 2
            size_offset = cursor
            size = record[cursor]
            require_file3d_bytes(record, size_offset, size, object_index)
            animation_index = struct.unpack_from("<h", record, cursor + 1)[0]
            animation_records.append(
                {
                    "generic_id": generic_id,
                    "generic_name": GENERIC_ANIMATION_NAMES.get(
                        generic_id, f"GEN_ANIM_{generic_id}"
                    ),
                    "label": GENERIC_ANIMATION_LABELS.get(
                        generic_id, f"Generic animation {generic_id}"
                    ),
                    "animation_index": animation_index,
                    "asset_id": f"{ANIM_ARCHIVE_NAME}:{animation_index}"
                    if animation_index >= 0
                    else None,
                }
            )
            cursor = size_offset + size
            continue
        if command == FILE3D_COMMAND_BODY:
            require_file3d_bytes(record, cursor, 2, object_index)
            generic_id = record[cursor]
            cursor += 1
            size_offset = cursor
            size = record[cursor]
            require_file3d_bytes(record, size_offset, size, object_index)
            body_index = struct.unpack_from("<h", record, cursor + 1)[0]
            body_records.append(
                {
                    "generic_id": generic_id,
                    "body_index": body_index,
                    "asset_id": f"BODY.HQR:{body_index + 1}"
                    if body_index >= 0
                    else None,
                }
            )
            cursor = size_offset + size
            continue

        require_file3d_bytes(record, cursor, 2, object_index)
        generic_id = record[cursor]
        cursor += 1
        size_offset = cursor
        size = record[cursor]
        require_file3d_bytes(record, size_offset, size, object_index)
        unknown_commands.append(
            {
                "command": command,
                "generic_id": generic_id,
                "offset": command_offset,
                "payload_bytes": size,
            }
        )
        cursor = size_offset + size
    return {
        "body_records": body_records,
        "animation_records": animation_records,
        "unknown_commands": unknown_commands,
    }


def parse_file3d_record(
    record: bytes, object_index: int
) -> tuple[list[int], list[tuple[int, int]]]:
    metadata = parse_file3d_record_details(record, object_index)
    return (
        [body["body_index"] for body in metadata["body_records"]],
        [
            (animation["animation_index"], animation["generic_id"])
            for animation in metadata["animation_records"]
        ],
    )


def require_file3d_bytes(
    record: bytes, offset: int, size: int, object_index: int
) -> None:
    if size < 0 or offset + size > len(record):
        raise Lm2Error(
            f"File3D object {object_index} record is truncated at offset 0x{offset:x}"
        )


def scene_object_runtime_links(
    scene_object: dict[str, Any],
    file3d_objects: dict[int, dict[str, Any]],
    available_asset_ids: set[str],
    anim3ds_ranges: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    flags = int(scene_object.get("flags", 0))
    file3d_index = int(scene_object.get("file3d_index", -1))
    gen_body = int(scene_object.get("gen_body", 0))
    gen_anim = int(scene_object.get("gen_anim", 0))
    sprite_index = int(scene_object.get("sprite", 0))
    links: dict[str, Any] = {
        "file3d_index": file3d_index,
        "file3d_available": file3d_index in file3d_objects,
        "body": None,
        "animation": None,
        "sprite": None,
        "missing_asset_ids": [],
    }
    missing: list[str] = []

    if flags & SPRITE_3D_FLAG:
        sprite = resolve_runtime_sprite(flags, sprite_index)
        asset_id = sprite.get("asset_id")
        sprite["asset_available"] = asset_id in available_asset_ids if asset_id else False
        anim3ds = scene_object.get("anim3ds")
        if sprite.get("backend") == "anim3ds" and isinstance(anim3ds, dict):
            animation_number = int(anim3ds.get("animation_number", -1))
            range_info = anim3ds_ranges.get(animation_number)
            if range_info is not None:
                sprite["anim3ds_range"] = {
                    "animation_number": animation_number,
                    "name": range_info.get("name"),
                    "start_frame": range_info.get("start_frame"),
                    "end_frame": range_info.get("end_frame"),
                    "frame_count": range_info.get("frame_count"),
                    "relative_frame": sprite_index - int(range_info.get("start_frame", 0)),
                    "range_matches_sprite": int(range_info.get("start_frame", -1))
                    <= sprite_index
                    <= int(range_info.get("end_frame", -1)),
                    "size_s_hit": anim3ds.get("size_s_hit"),
                    "frames_per_second": anim3ds.get("frames_per_second"),
                }
            else:
                sprite["anim3ds_range"] = {
                    "animation_number": animation_number,
                    "name": None,
                    "start_frame": None,
                    "end_frame": None,
                    "frame_count": None,
                    "relative_frame": None,
                    "range_matches_sprite": False,
                    "size_s_hit": anim3ds.get("size_s_hit"),
                    "frames_per_second": anim3ds.get("frames_per_second"),
                }
        if asset_id and asset_id not in available_asset_ids:
            missing.append(asset_id)
        links["sprite"] = sprite
    else:
        file3d = file3d_objects.get(file3d_index)
        if file3d is not None:
            body_candidates = [
                body
                for body in file3d.get("body_records", [])
                if body.get("generic_id") == gen_body
            ] or list(file3d.get("body_records", []))
            animation_candidates = [
                animation
                for animation in file3d.get("animation_records", [])
                if animation.get("generic_id") == gen_anim
            ] or list(file3d.get("animation_records", []))
            if body_candidates:
                body = dict(body_candidates[0])
                asset_id = body.get("asset_id")
                body["asset_available"] = (
                    asset_id in available_asset_ids if asset_id else False
                )
                body["resolution_rule"] = (
                    "matched scene GenBody to File3D body generic id"
                    if body.get("generic_id") == gen_body
                    else "fell back to first File3D body candidate"
                )
                if asset_id and asset_id not in available_asset_ids:
                    missing.append(asset_id)
                links["body"] = body
            if animation_candidates:
                animation = dict(animation_candidates[0])
                asset_id = animation.get("asset_id")
                animation["asset_available"] = (
                    asset_id in available_asset_ids if asset_id else False
                )
                animation["resolution_rule"] = (
                    "matched scene GenAnim to File3D animation generic id"
                    if animation.get("generic_id") == gen_anim
                    else "fell back to first File3D animation candidate"
                )
                if asset_id and asset_id not in available_asset_ids:
                    missing.append(asset_id)
                links["animation"] = animation
    links["missing_asset_ids"] = sorted(set(missing))
    return links


def resolve_file3d_body_reference(
    file3d: dict[str, Any] | None, generic_body_id: int
) -> dict[str, Any] | None:
    if file3d is None:
        return None
    candidates = [
        body
        for body in file3d.get("body_records", [])
        if body.get("generic_id") == generic_body_id
    ]
    if not candidates:
        return None
    body = dict(candidates[0])
    body["reference_value"] = generic_body_id
    body["resolution_rule"] = "resolved script generic body through owner File3D SearchBody rule"
    return body


def resolve_file3d_animation_reference(
    file3d: dict[str, Any] | None, generic_animation_id: int
) -> dict[str, Any] | None:
    if file3d is None:
        return None
    candidates = [
        animation
        for animation in file3d.get("animation_records", [])
        if animation.get("generic_id") == generic_animation_id
    ]
    if not candidates:
        return None
    animation = dict(candidates[0])
    animation["reference_value"] = generic_animation_id
    animation["resolution_rule"] = "resolved script generic animation through owner File3D SearchAnim rule"
    return animation


def resolve_script_asset_links(
    script: dict[str, Any],
    owner: dict[str, Any],
    file3d_objects: dict[int, dict[str, Any]],
    available_asset_ids: set[str],
    anim3ds_ranges: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    references = script.get("references") or {}
    file3d_index = int(owner.get("file3d_index", -1))
    file3d = file3d_objects.get(file3d_index)
    flags = int(owner.get("flags", 0))
    links: list[dict[str, Any]] = []

    for generic_body_id in references.get("body") or []:
        body = resolve_file3d_body_reference(file3d, int(generic_body_id))
        if body is None:
            continue
        asset_id = body.get("asset_id")
        body["asset_available"] = asset_id in available_asset_ids if asset_id else False
        links.append(
            {
                "kind": "body",
                "source": "script_reference",
                "reference_key": "body",
                "reference_value": int(generic_body_id),
                "file3d_index": file3d_index,
                **body,
            }
        )

    for generic_animation_id in references.get("animation") or []:
        animation = resolve_file3d_animation_reference(file3d, int(generic_animation_id))
        if animation is None:
            continue
        asset_id = animation.get("asset_id")
        animation["asset_available"] = asset_id in available_asset_ids if asset_id else False
        links.append(
            {
                "kind": "animation",
                "source": "script_reference",
                "reference_key": "animation",
                "reference_value": int(generic_animation_id),
                "file3d_index": file3d_index,
                **animation,
            }
        )

    if flags & SPRITE_3D_FLAG:
        for sprite_index in references.get("sprite") or []:
            sprite = resolve_runtime_sprite(flags, int(sprite_index))
            asset_id = sprite.get("asset_id")
            sprite["asset_available"] = asset_id in available_asset_ids if asset_id else False
            anim3ds = owner.get("anim3ds")
            if sprite.get("backend") == "anim3ds" and isinstance(anim3ds, dict):
                animation_number = int(anim3ds.get("animation_number", -1))
                range_info = anim3ds_ranges.get(animation_number)
                if range_info is not None:
                    sprite["anim3ds_range"] = {
                        "animation_number": animation_number,
                        "name": range_info.get("name"),
                        "start_frame": range_info.get("start_frame"),
                        "end_frame": range_info.get("end_frame"),
                        "frame_count": range_info.get("frame_count"),
                        "relative_frame": int(sprite_index) - int(range_info.get("start_frame", 0)),
                        "range_matches_sprite": int(range_info.get("start_frame", -1))
                        <= int(sprite_index)
                        <= int(range_info.get("end_frame", -1)),
                        "size_s_hit": anim3ds.get("size_s_hit"),
                        "frames_per_second": anim3ds.get("frames_per_second"),
                    }
            links.append(
                {
                    "kind": "sprite",
                    "source": "script_reference",
                    "reference_key": "sprite",
                    "reference_value": int(sprite_index),
                    "file3d_index": file3d_index,
                    **sprite,
                }
            )

    return links


def add_script_asset_links(
    owner: dict[str, Any],
    file3d_objects: dict[int, dict[str, Any]],
    available_asset_ids: set[str],
    anim3ds_ranges: dict[int, dict[str, Any]],
) -> tuple[dict[str, int], set[str]]:
    counts: dict[str, int] = {"body": 0, "animation": 0, "sprite": 0}
    missing_asset_ids: set[str] = set()
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = owner.get(script_key)
        if not script:
            continue
        links = resolve_script_asset_links(
            script, owner, file3d_objects, available_asset_ids, anim3ds_ranges
        )
        if not links:
            continue
        script["asset_links"] = links
        for link in links:
            kind = str(link.get("kind") or "unknown")
            counts[kind] = counts.get(kind, 0) + 1
            asset_id = link.get("asset_id")
            if asset_id and not link.get("asset_available"):
                missing_asset_ids.add(str(asset_id))
    return counts, missing_asset_ids


def enrich_scene_script_links(
    catalog: dict[str, Any], file3d_objects: dict[int, dict[str, Any]]
) -> None:
    available_asset_ids = {asset["id"] for asset in catalog.get("assets", [])}
    anim3ds_ranges = anim3ds_range_by_index(catalog)
    totals: dict[str, int] = {"body": 0, "animation": 0, "sprite": 0}
    missing_asset_ids: set[str] = set()

    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        reconnaissance = (asset.get("stats") or {}).get("reconnaissance") or {}
        scene_counts: dict[str, int] = {"body": 0, "animation": 0, "sprite": 0}
        for scene_object in reconnaissance.get("sampled_objects") or []:
            counts, missing = add_script_asset_links(
                scene_object, file3d_objects, available_asset_ids, anim3ds_ranges
            )
            missing_asset_ids.update(missing)
            for kind, count in counts.items():
                scene_counts[kind] = scene_counts.get(kind, 0) + count
                totals[kind] = totals.get(kind, 0) + count
        reconnaissance["script_linked_body_refs"] = scene_counts.get("body", 0)
        reconnaissance["script_linked_animation_refs"] = scene_counts.get("animation", 0)
        reconnaissance["script_linked_sprite_refs"] = scene_counts.get("sprite", 0)

    catalog["metadata"]["scene_script_links"] = {
        "source": f"{RESS_ARCHIVE_NAME}:{FILE3D_ENTRY_INDEX}",
        "body_refs": totals.get("body", 0),
        "animation_refs": totals.get("animation", 0),
        "sprite_refs": totals.get("sprite", 0),
        "missing_asset_ids": sorted(missing_asset_ids),
    }


def enrich_scene_runtime_links(
    catalog: dict[str, Any], file3d_objects: dict[int, dict[str, Any]]
) -> None:
    available_asset_ids = {asset["id"] for asset in catalog.get("assets", [])}
    anim3ds_ranges = anim3ds_range_by_index(catalog)
    linked_body_refs = 0
    linked_animation_refs = 0
    linked_sprite_refs = 0
    missing_asset_ids: set[str] = set()
    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        stats = asset.get("stats") or {}
        reconnaissance = stats.get("reconnaissance") or {}
        objects = reconnaissance.get("sampled_objects") or []
        for scene_object in objects:
            links = scene_object_runtime_links(
                scene_object, file3d_objects, available_asset_ids, anim3ds_ranges
            )
            scene_object["links"] = links
            if links.get("body"):
                linked_body_refs += 1
            if links.get("animation"):
                linked_animation_refs += 1
            if links.get("sprite"):
                linked_sprite_refs += 1
            missing_asset_ids.update(links.get("missing_asset_ids") or [])
        reconnaissance["linked_body_refs"] = sum(
            1 for scene_object in objects if scene_object.get("links", {}).get("body")
        )
        reconnaissance["linked_animation_refs"] = sum(
            1
            for scene_object in objects
            if scene_object.get("links", {}).get("animation")
        )
        reconnaissance["linked_sprite_refs"] = sum(
            1 for scene_object in objects if scene_object.get("links", {}).get("sprite")
        )
    catalog["metadata"]["scene_runtime_links"] = {
        "source": f"{RESS_ARCHIVE_NAME}:{FILE3D_ENTRY_INDEX}",
        "file3d_objects": len(file3d_objects),
        "body_refs": linked_body_refs,
        "animation_refs": linked_animation_refs,
        "sprite_refs": linked_sprite_refs,
        "missing_asset_ids": sorted(missing_asset_ids),
    }


def file_summary_by_path(catalog: dict[str, Any], path: str) -> dict[str, Any] | None:
    for file_summary in catalog.get("hqr_files", []):
        if file_summary.get("path") == path:
            return file_summary
    return None


def update_scene_link_summary(catalog: dict[str, Any]) -> None:
    metadata = catalog.get("metadata", {}).get("scene_runtime_links") or {}
    script_metadata = catalog.get("metadata", {}).get("scene_script_links") or {}
    text_metadata = catalog.get("metadata", {}).get("scene_text_links") or {}
    sample_metadata = catalog.get("metadata", {}).get("scene_sample_links") or {}
    video_metadata = catalog.get("metadata", {}).get("scene_video_links") or {}
    background_metadata = catalog.get("metadata", {}).get("scene_background_links") or {}
    grm_metadata = catalog.get("metadata", {}).get("scene_grm_links") or {}
    scene_summary = file_summary_by_path(catalog, SCENE_ARCHIVE_NAME)
    if scene_summary is not None:
        scene_summary["linked_body_refs"] = metadata.get("body_refs", 0)
        scene_summary["linked_animation_refs"] = metadata.get("animation_refs", 0)
        scene_summary["linked_sprite_refs"] = metadata.get("sprite_refs", 0)
        scene_summary["script_linked_body_refs"] = script_metadata.get("body_refs", 0)
        scene_summary["script_linked_animation_refs"] = script_metadata.get("animation_refs", 0)
        scene_summary["script_linked_sprite_refs"] = script_metadata.get("sprite_refs", 0)
        scene_summary["script_linked_text_refs"] = text_metadata.get("script_logical_refs", 0)
        scene_summary["zone_linked_text_refs"] = text_metadata.get("zone_logical_refs", 0)
        scene_summary["script_linked_sample_refs"] = sample_metadata.get("script_linked_refs", 0)
        scene_summary["script_linked_video_refs"] = video_metadata.get("script_linked_refs", 0)
        scene_summary["ambience_linked_sample_refs"] = sample_metadata.get("ambience_linked_refs", 0)
        scene_summary["background_cube_links"] = background_metadata.get("scene_cube_links", 0)
        scene_summary["grm_fragment_links"] = grm_metadata.get("linked_grm_fragments", 0)
        scene_summary["missing_asset_links"] = len(metadata.get("missing_asset_ids") or [])


def build_text_record_lookup(catalog: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    assets_by_id = {
        asset.get("id"): asset for asset in catalog.get("assets", []) if asset.get("id")
    }
    lookup: dict[tuple[int, int, int], dict[str, Any]] = {}
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "text_order_table":
            continue
        language_index = int(stats.get("language_index", -1))
        text_file_index = int(stats.get("text_file_index", -1))
        paired_entry_index = stats.get("paired_entry_index")
        bank_asset_id = f"{TEXT_ARCHIVE_NAME}:{paired_entry_index}"
        bank_asset = assets_by_id.get(bank_asset_id)
        bank_stats = (bank_asset or {}).get("stats") or {}
        if bank_stats.get("semantic_layout") != "text_payload_bank":
            continue
        records = bank_stats.get("records") or []
        for record_index, message_id in enumerate(stats.get("message_ids") or []):
            key = (language_index, text_file_index, int(message_id))
            if key in lookup or record_index >= len(records):
                continue
            record = records[record_index] or {}
            lookup[key] = {
                "kind": "text",
                "source": "scene_text_reference",
                "reference_key": "text",
                "reference_value": int(message_id),
                "text_id": int(message_id),
                "text_file_index": text_file_index,
                "text_file_name": stats.get("text_file_name"),
                "language_index": language_index,
                "language": stats.get("language"),
                "asset_id": bank_asset_id,
                "asset_available": bank_asset is not None,
                "order_asset_id": asset.get("id"),
                "order_entry_index": asset.get("source", {}).get("entry_index"),
                "record_index": record_index,
                "record_flag": record.get("flag"),
                "preview": record.get("preview", ""),
                "resolution_rule": "resolved scene text id through InitDial(START_FILE_ISLAND+Island) and BufOrder/BufText",
            }
    return lookup


def scene_text_file_index(reconnaissance: dict[str, Any]) -> int | None:
    world = reconnaissance.get("world") or {}
    island = world.get("island")
    if not isinstance(island, int) or isinstance(island, bool):
        return None
    return TEXT_START_FILE_ISLAND + island


def resolve_scene_text_links(
    text_lookup: dict[tuple[int, int, int], dict[str, Any]],
    text_file_index: int,
    text_id: int,
) -> list[dict[str, Any]]:
    links = [
        dict(link)
        for (language_index, file_index, message_id), link in sorted(text_lookup.items())
        if file_index == text_file_index and message_id == text_id
    ]
    return links


def add_script_text_links(
    owner: dict[str, Any],
    text_lookup: dict[tuple[int, int, int], dict[str, Any]],
    text_file_index: int,
) -> tuple[int, int, int]:
    logical_refs = 0
    localized_refs = 0
    missing_refs = 0
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = owner.get(script_key)
        if not script:
            continue
        text_ids = sorted(int(text_id) for text_id in (script.get("references") or {}).get("text") or [])
        if not text_ids:
            continue
        asset_links = list(script.get("asset_links") or [])
        text_links: list[dict[str, Any]] = []
        for text_id in text_ids:
            logical_refs += 1
            links = resolve_scene_text_links(text_lookup, text_file_index, text_id)
            if not links:
                missing_refs += 1
                continue
            localized_refs += len(links)
            text_links.extend(links)
            asset_links.extend(links)
        if text_links:
            script["text_links"] = text_links
            script["asset_links"] = asset_links
    return logical_refs, localized_refs, missing_refs


def scene_message_zone_records(reconnaissance: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for zone in reconnaissance.get("text_message_zones") or []:
        runtime = zone.get("runtime") or {}
        fields = runtime.get("fields") or {}
        message_id = fields.get("message_id", zone.get("value"))
        if not isinstance(message_id, int) or isinstance(message_id, bool):
            continue
        records.append(
            {
                "zone_index": zone.get("index"),
                "message_id": message_id,
                "zone_value": zone.get("value"),
                "start": zone.get("start"),
                "end": zone.get("end"),
                "facing_direction": fields.get("facing_direction"),
            }
        )
    return records


def enrich_scene_text_links(catalog: dict[str, Any]) -> None:
    text_lookup = build_text_record_lookup(catalog)
    totals: dict[str, int] = {
        "script_logical_refs": 0,
        "script_localized_refs": 0,
        "script_missing_refs": 0,
        "zone_logical_refs": 0,
        "zone_localized_refs": 0,
        "zone_missing_refs": 0,
    }
    if not text_lookup:
        catalog["metadata"]["scene_text_links"] = {
            **totals,
            "source": f"{TEXT_ARCHIVE_NAME} unavailable",
            "missing_text_ids": [],
        }
        return

    missing_text_ids: set[str] = set()
    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        reconnaissance = (asset.get("stats") or {}).get("reconnaissance") or {}
        text_file_index = scene_text_file_index(reconnaissance)
        if text_file_index is None:
            continue
        reconnaissance["text_file_index"] = text_file_index
        scene_counts = {key: 0 for key in totals}
        owners = [reconnaissance.get("hero") or {}, *(reconnaissance.get("sampled_objects") or [])]
        for owner in owners:
            logical, localized, missing = add_script_text_links(owner, text_lookup, text_file_index)
            scene_counts["script_logical_refs"] += logical
            scene_counts["script_localized_refs"] += localized
            scene_counts["script_missing_refs"] += missing
            for text_id in sorted((owner.get("track_script_analysis") or {}).get("references", {}).get("text") or []):
                if not resolve_scene_text_links(text_lookup, text_file_index, int(text_id)):
                    missing_text_ids.add(f"{text_file_index}:{int(text_id)}")
            for text_id in sorted((owner.get("life_script_analysis") or {}).get("references", {}).get("text") or []):
                if not resolve_scene_text_links(text_lookup, text_file_index, int(text_id)):
                    missing_text_ids.add(f"{text_file_index}:{int(text_id)}")

        zone_links: list[dict[str, Any]] = []
        for zone_record in scene_message_zone_records(reconnaissance):
            text_id = int(zone_record["message_id"])
            scene_counts["zone_logical_refs"] += 1
            links = resolve_scene_text_links(text_lookup, text_file_index, text_id)
            if not links:
                scene_counts["zone_missing_refs"] += 1
                missing_text_ids.add(f"{text_file_index}:{text_id}")
                continue
            scene_counts["zone_localized_refs"] += len(links)
            for link in links:
                zone_links.append({**link, **zone_record, "reference_key": "zone_message"})
        if zone_links:
            reconnaissance["text_zone_links"] = zone_links
        reconnaissance["text_link_counts"] = scene_counts
        for key, count in scene_counts.items():
            totals[key] = totals.get(key, 0) + count

    catalog["metadata"]["scene_text_links"] = {
        **totals,
        "source": "MESSAGE.CPP InitDial(START_FILE_ISLAND+Island), FindText, and GetText",
        "missing_text_ids": sorted(missing_text_ids),
    }


def enrich_holomap_text_links(catalog: dict[str, Any]) -> None:
    text_lookup = build_text_record_lookup(catalog)
    totals: dict[str, Any] = {
        "arrow_message_refs": 0,
        "unique_message_ids": 0,
        "linked_unique_message_ids": 0,
        "localized_text_records": 0,
        "missing_message_ids": [],
    }
    missing_message_ids: set[int] = set()
    linked_unique_ids: set[int] = set()
    localized_records = 0

    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "holomap_arrow_table":
            continue
        records = stats.get("records") or []
        asset_linked_unique_ids: set[int] = set()
        asset_localized_records = 0
        message_to_records: dict[int, list[dict[str, Any]]] = {}
        for record in records:
            message_id = int(record.get("message", -1))
            if message_id < 0:
                continue
            message_to_records.setdefault(message_id, []).append(record)
        text_links: list[dict[str, Any]] = []
        for message_id, arrow_records in sorted(message_to_records.items()):
            links = resolve_scene_text_links(text_lookup, HOLOMAP_TEXT_FILE_INDEX, message_id)
            if not links:
                missing_message_ids.add(message_id)
                continue
            linked_unique_ids.add(message_id)
            asset_linked_unique_ids.add(message_id)
            localized_records += len(links)
            asset_localized_records += len(links)
            text_links.append(
                {
                    "kind": "holomap_text",
                    "message_id": message_id,
                    "text_file_index": HOLOMAP_TEXT_FILE_INDEX,
                    "text_file_name": TEXT_FILE_NAMES[HOLOMAP_TEXT_FILE_INDEX],
                    "arrow_indices": [record.get("index") for record in arrow_records],
                    "arrow_count": len(arrow_records),
                    "localized_records": len(links),
                    "localized_links": [
                        {
                            **link,
                            "source": "holomap_text_reference",
                            "reference_key": "holomap_arrow_message",
                            "resolution_rule": "resolved holomap TabArrow.Mess through HOLOGLOB.CPP InitDial(2) and GetText",
                        }
                        for link in links
                    ],
                }
            )
        stats["text_file_index"] = HOLOMAP_TEXT_FILE_INDEX
        stats["text_file_name"] = TEXT_FILE_NAMES[HOLOMAP_TEXT_FILE_INDEX]
        stats["text_link_counts"] = {
            "arrow_message_refs": sum(len(items) for items in message_to_records.values()),
            "unique_message_ids": len(message_to_records),
            "linked_unique_message_ids": len(asset_linked_unique_ids),
            "localized_text_records": asset_localized_records,
            "missing_message_ids": len(missing_message_ids),
        }
        if text_links:
            stats["text_links"] = text_links
        totals["arrow_message_refs"] += stats["text_link_counts"]["arrow_message_refs"]
        totals["unique_message_ids"] += stats["text_link_counts"]["unique_message_ids"]
        totals["linked_unique_message_ids"] += stats["text_link_counts"]["linked_unique_message_ids"]
        totals["localized_text_records"] += asset_localized_records

    totals["missing_message_ids"] = sorted(missing_message_ids)
    catalog["metadata"]["holomap_text_links"] = {
        **totals,
        "source": "HOLOGLOB.CPP AffHoloMess uses TabArrow.Mess while HoloMap has InitDial(2)",
        "text_file_index": HOLOMAP_TEXT_FILE_INDEX,
        "text_file_name": TEXT_FILE_NAMES[HOLOMAP_TEXT_FILE_INDEX],
    }
    holomap_summary = file_summary_by_path(catalog, HOLOMAP_ARCHIVE_NAME)
    if holomap_summary is not None:
        holomap_summary["linked_text_refs"] = totals["linked_unique_message_ids"]


def scene_background_palette_context(world: dict[str, Any]) -> dict[str, Any]:
    island = world.get("island")
    cube_mode = world.get("cube_mode")
    context: dict[str, Any] = {
        "source": "AMBIANCE.CPP ChoicePalette",
        "rule": "interior cubes use RESS_XPL00; exterior cubes use RESS_XPL0+Island except island 0 can switch to RESS_XPL00 when TEMPETE_FINIE is true.",
        "island": island,
        "cube_mode": cube_mode,
    }
    if cube_mode == CUBE_INTERIEUR:
        context.update(
            {
                "resolved_palette_entry": RESS_XPL00_ENTRY_INDEX,
                "resolved_palette_name": RESS_XPL_ENTRY_NAMES[RESS_XPL00_ENTRY_INDEX],
                "confidence": "direct_classic_rule",
            }
        )
    elif cube_mode == CUBE_EXTERIEUR and isinstance(island, int) and not isinstance(island, bool):
        normal_entry = RESS_XPL0_ENTRY_INDEX + island
        context.update(
            {
                "resolved_palette_entry": normal_entry,
                "resolved_palette_name": RESS_XPL_ENTRY_NAMES.get(normal_entry, f"XPL{normal_entry}"),
                "confidence": "direct_classic_rule" if island != 0 else "runtime_conditioned",
            }
        )
        if island == 0:
            context["alternate_palette_entry"] = RESS_XPL00_ENTRY_INDEX
            context["alternate_palette_name"] = RESS_XPL_ENTRY_NAMES[RESS_XPL00_ENTRY_INDEX]
            context["alternate_condition"] = "TEMPETE_FINIE"
    else:
        context["confidence"] = "unresolved"
    return context


def build_bkg_cube_record_lookup(catalog: dict[str, Any]) -> dict[int, dict[str, Any]]:
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") == "bkg_cube_map":
            return {
                int(record["index"]): record
                for record in stats.get("records", [])
                if isinstance(record, dict) and "index" in record
            }
    return {}


def enrich_bkg_grid_block_links(catalog: dict[str, Any]) -> None:
    bll_by_entry: dict[int, dict[str, Any]] = {}
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") == "bkg_block_table":
            bll_by_entry[int(asset["source"]["entry_index"])] = stats

    linked = 0
    missing = 0
    invalid_block_refs = 0
    invalid_cell_slots = 0
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "bkg_grid_map":
            continue
        fields = stats.setdefault("fields", {})
        bll_entry = fields.get("resolved_bll_entry")
        bll_stats = bll_by_entry.get(int(bll_entry)) if bll_entry is not None else None
        composition = stats.get("composition", {})
        if bll_stats is None:
            missing += 1
            fields["composition_bll_link_found"] = 0
            continue

        linked += 1
        fields["composition_bll_link_found"] = 1
        fields["composition_bll_block_count"] = bll_stats.get("record_count", 0)
        block_count = int(bll_stats.get("record_count", 0))
        invalid_refs = [
            ref for ref in composition.get("unique_block_refs", [])
            if ref <= 0 or ref > block_count
        ]
        fields["composition_invalid_block_ref_count"] = len(invalid_refs)
        invalid_block_refs += len(invalid_refs)

        bll_records = bll_stats.get("sampled_records", [])
        bll_cell_counts = {
            int(record["index"]) + 1: int(record.get("cell_count", 0))
            for record in bll_records
        }
        invalid_slot_refs = []
        for block_ref_text, max_slot in composition.get("block_ref_cell_slot_max", {}).items():
            block_ref = int(block_ref_text)
            cell_count = bll_cell_counts.get(block_ref)
            if cell_count is not None and int(max_slot) >= cell_count:
                invalid_slot_refs.append(
                    {
                        "block_ref": block_ref,
                        "max_cell_slot": int(max_slot),
                        "bll_cell_count": cell_count,
                    }
                )
        fields["composition_invalid_sampled_cell_slot_count"] = len(invalid_slot_refs)
        invalid_cell_slots += len(invalid_slot_refs)
        stats["invalid_composition_block_refs"] = invalid_refs[:32]
        stats["invalid_composition_cell_slots"] = invalid_slot_refs[:32]
        for cell in stats.get("sampled_occupied_cells", []):
            block_ref = int(cell.get("block_ref", 0))
            cell_count = bll_cell_counts.get(block_ref)
            cell["resolved_bll_entry"] = int(bll_entry)
            cell["block_ref_valid"] = 1 <= block_ref <= block_count
            if cell_count is not None:
                cell["bll_cell_count"] = cell_count
                cell["cell_slot_valid"] = int(cell.get("cell_slot", 0)) < cell_count

    catalog.setdefault("metadata", {})["bkg_grid_composition_links"] = {
        "grid_maps": linked + missing,
        "linked_bll_tables": linked,
        "missing_bll_tables": missing,
        "invalid_block_refs": invalid_block_refs,
        "invalid_sampled_cell_slots": invalid_cell_slots,
    }


def enrich_scene_background_links(catalog: dict[str, Any]) -> None:
    cube_records = build_bkg_cube_record_lookup(catalog)
    linked = 0
    missing = 0
    palette_counts: dict[str, int] = {}
    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        stats = asset.get("stats") or {}
        reconnaissance = stats.get("reconnaissance") or {}
        world = reconnaissance.get("world") or {}
        source = asset.get("source") or {}
        entry_index = source.get("entry_index")
        if not isinstance(entry_index, int) or isinstance(entry_index, bool):
            continue
        runtime_cube = entry_index - 1
        background: dict[str, Any] = {
            "runtime_cube": runtime_cube,
            "scene_entry_index": entry_index,
            "palette": scene_background_palette_context(world),
            "source_provenance": "DISKFUNC.CPP LoadScene(numscene) loads SCENE.HQR numscene+1; OBJECT.CPP ChangeCube sets NumCube=NewCube and calls PtrInitGrille(NewCube); GRILLE.CPP InitGrille indexes TabAllCube[numcube].",
        }
        record = cube_records.get(runtime_cube)
        if record is not None:
            background.update(
                {
                    "cube_map_record_found": True,
                    "cube_record_type": record.get("type"),
                    "cube_record_num": record.get("num"),
                    "resolved_gri_entry": record.get("resolved_gri_entry"),
                    "resolved_bll_entry": record.get("resolved_bll_entry"),
                    "resolved_grm_entry": record.get("resolved_grm_entry"),
                    "used_block_count": record.get("used_block_count"),
                }
            )
            linked += 1
        else:
            background["cube_map_record_found"] = False
            missing += 1
        palette_entry = (background.get("palette") or {}).get("resolved_palette_entry")
        if isinstance(palette_entry, int) and not isinstance(palette_entry, bool):
            key = str(palette_entry)
            palette_counts[key] = palette_counts.get(key, 0) + 1
        reconnaissance["background"] = background
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "xpl_palette_bundle":
            continue
        entry_index = (asset.get("source") or {}).get("entry_index")
        if not isinstance(entry_index, int) or isinstance(entry_index, bool):
            continue
        count = palette_counts.get(str(entry_index), 0)
        if count:
            stats["scene_palette_reference_count"] = count
            stats["runtime_reference_status"] = "selected_by_scene_choice_palette"
    catalog.setdefault("metadata", {})["scene_background_links"] = {
        "scene_cube_links": linked,
        "missing_cube_records": missing,
        "palette_entry_counts": palette_counts,
    }


def enrich_scene_grm_links(catalog: dict[str, Any]) -> None:
    grm_assets_by_entry: dict[int, dict[str, Any]] = {}
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") == "bkg_grm_fragment":
            source = asset.get("source") or {}
            entry_index = source.get("entry_index")
            if isinstance(entry_index, int) and not isinstance(entry_index, bool):
                grm_assets_by_entry[entry_index] = asset

    total_zones = 0
    linked = 0
    missing = 0
    dimension_mismatches = 0
    out_of_cube_bounds = 0
    column_y_overflow_cells = 0
    scenes_with_grm = 0
    for scene_asset in catalog.get("assets", []):
        if scene_asset.get("kind") != "scene":
            continue
        reconnaissance = (scene_asset.get("stats") or {}).get("reconnaissance") or {}
        grm_zones = reconnaissance.get("grm_fragment_zones") or []
        if not grm_zones:
            continue
        scenes_with_grm += 1
        background = reconnaissance.get("background") or {}
        grm_base_entry = background.get("resolved_grm_entry")
        links: list[dict[str, Any]] = []
        scene_counts = {
            "zones": len(grm_zones),
            "linked": 0,
            "missing": 0,
            "dimension_mismatches": 0,
            "out_of_cube_bounds": 0,
            "column_y_overflow_cells": 0,
        }
        for zone in grm_zones:
            total_zones += 1
            info = zone.get("info") or []
            grm_index = int(info[0]) if info else 0
            runtime_state = int(info[2]) if len(info) > 2 else 0
            bounds = zone_cell_bounds(zone)
            span = {
                "x": bounds["x1"] - bounds["x0"] + 1,
                "y": bounds["y1"] - bounds["y0"] + 1,
                "z": bounds["z1"] - bounds["z0"] + 1,
            }
            resolved_entry = (
                int(grm_base_entry) + grm_index
                if isinstance(grm_base_entry, int) and not isinstance(grm_base_entry, bool)
                else None
            )
            grm_asset = grm_assets_by_entry.get(resolved_entry) if resolved_entry is not None else None
            grm_stats = (grm_asset or {}).get("stats") or {}
            dims = {
                "x": grm_stats.get("width"),
                "y": grm_stats.get("height"),
                "z": grm_stats.get("depth"),
            }
            has_dims = all(isinstance(value, int) for value in dims.values())
            dimensions_match = (
                bool(has_dims)
                and int(dims["x"]) == span["x"]
                and int(dims["y"]) == span["y"]
                and int(dims["z"]) == span["z"]
            )
            exceeds_cube = (
                not has_dims
                or bounds["x0"] < 0
                or bounds["y0"] < 0
                or bounds["z0"] < 0
                or bounds["x0"] + int(dims["x"]) > BKG_CUBE_SIZE_X
                or bounds["z0"] + int(dims["z"]) > BKG_CUBE_SIZE_Z
            )
            y_overflow = (
                max(0, bounds["y0"] + int(dims["y"]) - BKG_CUBE_SIZE_Y) * int(dims["x"]) * int(dims["z"])
                if has_dims
                else 0
            )
            if grm_asset is None:
                missing += 1
                scene_counts["missing"] += 1
            else:
                linked += 1
                scene_counts["linked"] += 1
            if has_dims and not dimensions_match:
                dimension_mismatches += 1
                scene_counts["dimension_mismatches"] += 1
            if exceeds_cube:
                out_of_cube_bounds += 1
                scene_counts["out_of_cube_bounds"] += 1
            column_y_overflow_cells += y_overflow
            scene_counts["column_y_overflow_cells"] += y_overflow

            link = {
                "kind": "grm_fragment",
                "zone_index": zone.get("index"),
                "zone_value": zone.get("value"),
                "grm_index": grm_index,
                "initial_runtime_state": runtime_state,
                "background_grm_base_entry": grm_base_entry,
                "resolved_grm_entry": resolved_entry,
                "asset_id": grm_asset.get("id") if grm_asset else None,
                "asset_available": grm_asset is not None,
                "target_cell_start": {
                    "x": bounds["x0"],
                    "y": bounds["y0"],
                    "z": bounds["z0"],
                },
                "zone_cell_span": span,
                "fragment_dimensions": dims,
                "dimensions_match_zone_bounds": dimensions_match,
                "out_of_cube_bounds": exceeds_cube,
                "column_y_overflow_cells": y_overflow,
                "script_control": "LM_SET_GRM",
                "source_provenance": "GRILLE.CPP IncrustGrm uses Grm_Start+GriHeader->My_Grm+zone.Info0; GERELIFE.CPP LM_SET_GRM matches zone.Num and toggles Info2.",
            }
            links.append(link)
        reconnaissance["grm_fragment_links"] = links
        reconnaissance["grm_fragment_link_counts"] = scene_counts

    catalog.setdefault("metadata", {})["scene_grm_links"] = {
        "source": "GRILLE.CPP IncrustGrm/DesIncrustGrm/RedrawGRMs and GERELIFE.CPP LM_SET_GRM",
        "scenes_with_grm_zones": scenes_with_grm,
        "fragment_zones": total_zones,
        "linked_grm_fragments": linked,
        "missing_grm_fragments": missing,
        "dimension_mismatches": dimension_mismatches,
        "out_of_cube_bounds": out_of_cube_bounds,
        "column_y_overflow_cells": column_y_overflow_cells,
    }


def build_sample_lookup(catalog: dict[str, Any]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "sample_wave_audio":
            continue
        runtime_index = stats.get("sample_runtime_index")
        if not isinstance(runtime_index, int) or isinstance(runtime_index, bool):
            continue
        lookup[runtime_index] = {
            "kind": "sample",
            "source": "scene_sample_reference",
            "reference_key": "sample",
            "reference_value": runtime_index,
            "sample_id": runtime_index,
            "asset_id": asset.get("id"),
            "asset_available": True,
            "audio_format": stats.get("audio_format"),
            "sample_rate": (stats.get("fields") or {}).get("sample_rate"),
            "bits_per_sample": (stats.get("fields") or {}).get("bits_per_sample"),
            "channels": (stats.get("fields") or {}).get("channels"),
            "duration_ms": stats.get("duration_ms"),
            "resolution_rule": "resolved scene sample id through zero-based HQR_Get(HQR_Samples,index)",
        }
    return lookup


def missing_sample_detail(
    sample_id: int, archive_entry_count: int | None
) -> dict[str, Any]:
    detail = {
        "sample_id": sample_id,
        "hqr_table_index": sample_id + 1,
    }
    if archive_entry_count is None:
        return {
            **detail,
            "status": "no_samples_archive_loaded",
            "reason": f"{SAMPLES_ARCHIVE_NAME} was not loaded",
        }
    if sample_id + 1 > archive_entry_count:
        return {
            **detail,
            "status": "outside_archive_table",
            "reason": "outside SAMPLES.HQR table",
        }
    return {
        **detail,
        "status": "empty_or_undecoded_hqr_slot",
        "reason": "empty or undecoded SAMPLES.HQR slot",
    }


def count_missing_sample_statuses(
    missing_details: list[dict[str, Any]]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for detail in missing_details:
        status = detail.get("status")
        if not isinstance(status, str) or not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return counts


def add_script_sample_links(
    owner: dict[str, Any],
    sample_lookup: dict[int, dict[str, Any]],
    archive_entry_count: int | None,
) -> tuple[int, int, int]:
    logical_refs = 0
    linked_refs = 0
    missing_refs = 0
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = owner.get(script_key)
        if not script:
            continue
        sample_ids = sorted(
            int(sample_id)
            for sample_id in (script.get("references") or {}).get("sample") or []
            if isinstance(sample_id, int) and not isinstance(sample_id, bool)
        )
        if not sample_ids:
            continue
        asset_links = list(script.get("asset_links") or [])
        sample_links: list[dict[str, Any]] = []
        missing_sample_links: list[dict[str, Any]] = []
        for sample_id in sample_ids:
            logical_refs += 1
            link = sample_lookup.get(sample_id)
            if link is None:
                missing_refs += 1
                missing_sample_links.append(
                    {
                        **missing_sample_detail(sample_id, archive_entry_count),
                        "kind": "script_sample_missing",
                        "source": "scene_sample_reference",
                        "reference_key": "sample",
                        "reference_value": sample_id,
                    }
                )
                continue
            linked_refs += 1
            sample_links.append(dict(link))
            asset_links.append(dict(link))
        if sample_links:
            script["sample_links"] = sample_links
            script["asset_links"] = asset_links
        if missing_sample_links:
            script["missing_sample_links"] = missing_sample_links
    return logical_refs, linked_refs, missing_refs


def scene_ambience_sample_records(reconnaissance: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ambience = reconnaissance.get("ambience") or {}
    for slot_index, sample in enumerate(ambience.get("samples") or []):
        sample_id = sample.get("sample")
        if not isinstance(sample_id, int) or isinstance(sample_id, bool) or sample_id < 0:
            continue
        records.append(
            {
                "slot_index": slot_index,
                "sample_id": sample_id,
                "repeat": sample.get("repeat"),
                "random": sample.get("random"),
                "frequency": sample.get("frequency"),
                "volume": sample.get("volume"),
            }
        )
    return records


def enrich_scene_sample_links(catalog: dict[str, Any]) -> None:
    sample_lookup = build_sample_lookup(catalog)
    sample_archive_summary = next(
        (
            summary
            for summary in catalog.get("hqr_files", [])
            if summary.get("path") == SAMPLES_ARCHIVE_NAME
            or summary.get("archive") == SAMPLES_ARCHIVE_NAME
        ),
        None,
    )
    archive_entry_count = (
        int(sample_archive_summary.get("entry_count", 0))
        if isinstance(sample_archive_summary, dict)
        else None
    )
    available_sample_ids = sorted(sample_lookup)
    highest_decoded_sample_id = available_sample_ids[-1] if available_sample_ids else None
    totals: dict[str, int] = {
        "script_logical_refs": 0,
        "script_linked_refs": 0,
        "script_missing_refs": 0,
        "ambience_logical_refs": 0,
        "ambience_linked_refs": 0,
        "ambience_missing_refs": 0,
    }
    missing_sample_ids: set[int] = set()
    all_missing_details_by_id: dict[int, dict[str, Any]] = {}
    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        reconnaissance = (asset.get("stats") or {}).get("reconnaissance") or {}
        scene_counts = {key: 0 for key in totals}
        scene_missing_links: list[dict[str, Any]] = []
        owners = [reconnaissance.get("hero") or {}, *(reconnaissance.get("sampled_objects") or [])]
        for owner in owners:
            logical, linked, missing = add_script_sample_links(
                owner, sample_lookup, archive_entry_count
            )
            scene_counts["script_logical_refs"] += logical
            scene_counts["script_linked_refs"] += linked
            scene_counts["script_missing_refs"] += missing
            for script_key in ("track_script_analysis", "life_script_analysis"):
                script = owner.get(script_key) or {}
                scene_missing_links.extend(script.get("missing_sample_links") or [])
                for sample_id in sorted((script.get("references") or {}).get("sample") or []):
                    if (
                        isinstance(sample_id, int)
                        and not isinstance(sample_id, bool)
                        and sample_id not in sample_lookup
                    ):
                        missing_sample_ids.add(sample_id)
                        all_missing_details_by_id[sample_id] = missing_sample_detail(
                            sample_id, archive_entry_count
                        )

        ambience_links: list[dict[str, Any]] = []
        ambience_missing_links: list[dict[str, Any]] = []
        for sample_record in scene_ambience_sample_records(reconnaissance):
            sample_id = int(sample_record["sample_id"])
            scene_counts["ambience_logical_refs"] += 1
            link = sample_lookup.get(sample_id)
            if link is None:
                scene_counts["ambience_missing_refs"] += 1
                missing_sample_ids.add(sample_id)
                missing_detail = {
                    **missing_sample_detail(sample_id, archive_entry_count),
                    **sample_record,
                    "kind": "ambience_sample_missing",
                    "source": "scene_ambience",
                    "reference_key": "ambience_sample",
                    "reference_value": sample_id,
                }
                ambience_missing_links.append(missing_detail)
                scene_missing_links.append(missing_detail)
                all_missing_details_by_id[sample_id] = missing_sample_detail(
                    sample_id, archive_entry_count
                )
                continue
            scene_counts["ambience_linked_refs"] += 1
            ambience_links.append({**link, **sample_record, "reference_key": "ambience_sample"})
        if ambience_links:
            reconnaissance["sample_ambience_links"] = ambience_links
        if ambience_missing_links:
            reconnaissance["sample_ambience_missing_links"] = ambience_missing_links
        if scene_missing_links:
            reconnaissance["missing_sample_links"] = scene_missing_links
        reconnaissance["sample_link_counts"] = scene_counts
        for key, count in scene_counts.items():
            totals[key] = totals.get(key, 0) + count

    missing_details = [
        all_missing_details_by_id.get(sample_id)
        or missing_sample_detail(sample_id, archive_entry_count)
        for sample_id in sorted(missing_sample_ids)
    ]
    missing_status_counts = count_missing_sample_statuses(missing_details)

    catalog["metadata"]["scene_sample_links"] = {
        **totals,
        "source": "AMBIANCE.CPP HQ_MixSample/HQ_3D_MixSample and OBJECT.H GivePtrSample",
        "missing_sample_ids": sorted(missing_sample_ids),
        "missing_sample_id_details": missing_details,
        "missing_sample_status_counts": missing_status_counts,
        "observed_sample_id_max": max(missing_sample_ids | set(sample_lookup))
        if missing_sample_ids or sample_lookup
        else None,
        "sample_archive": (
            {
                "archive": SAMPLES_ARCHIVE_NAME,
                "entry_count": archive_entry_count,
                "non_empty_entries": (
                    sample_archive_summary.get("non_empty_entries", 0)
                    if isinstance(sample_archive_summary, dict)
                    else 0
                ),
                "decoded_audio_entries": len(sample_lookup),
                "highest_decoded_sample_id": highest_decoded_sample_id,
                "highest_runtime_sample_id": archive_entry_count - 1
                if isinstance(archive_entry_count, int) and archive_entry_count > 0
                else None,
                "runtime_id_rule": "runtime sample id N maps to SAMPLES.HQR table slot N+1",
            }
            if isinstance(sample_archive_summary, dict)
            else None
        ),
    }


def build_video_lookup(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for asset in catalog.get("assets", []):
        stats = asset.get("stats") or {}
        if stats.get("semantic_layout") != "smacker_video":
            continue
        acf_key = stats.get("acf_basename")
        if not isinstance(acf_key, str) or not acf_key:
            continue
        lookup[acf_key] = {
            "kind": "video",
            "source": "scene_cinematic_reference",
            "reference_key": "acf_name",
            "reference_value": stats.get("acf_name"),
            "acf_name": stats.get("acf_name"),
            "acf_index": stats.get("acf_index"),
            "asset_id": asset.get("id"),
            "asset_available": True,
            "width": stats.get("width"),
            "height": stats.get("height"),
            "frame_count": stats.get("frame_count"),
            "duration_ms": stats.get("duration_ms"),
            "resolution_rule": "GetNumAcf matches the PLAY_ACF string against RESS.HQR:48 names without the .SMK extension, then HQF_Init loads VIDEO/VIDEO.HQR by that zero-based index.",
        }
    return lookup


def add_script_video_links(
    owner: dict[str, Any], video_lookup: dict[str, dict[str, Any]]
) -> tuple[int, int, int, set[str]]:
    logical_refs = 0
    linked_refs = 0
    missing_refs = 0
    missing_names: set[str] = set()
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = owner.get(script_key)
        if not script:
            continue
        cinematic_refs = [
            ref
            for ref in script.get("cinematic_refs") or []
            if isinstance(ref.get("acf_name"), str) and ref.get("acf_name")
        ]
        if not cinematic_refs:
            continue
        asset_links = list(script.get("asset_links") or [])
        video_links: list[dict[str, Any]] = []
        for ref in cinematic_refs:
            logical_refs += 1
            acf_name = str(ref["acf_name"])
            acf_key = normalize_acf_name(acf_name)
            link = video_lookup.get(acf_key)
            if link is None:
                missing_refs += 1
                missing_names.add(acf_name)
                video_links.append(
                    {
                        "kind": "video",
                        "source": "scene_cinematic_reference",
                        "reference_key": "acf_name",
                        "reference_value": acf_name,
                        "acf_name": acf_name,
                        "acf_name_hex": acf_name.encode("latin-1", errors="replace").hex(),
                        "acf_basename": acf_key,
                        "asset_available": False,
                        "missing_reason": "name_not_found_in_loaded_video_assets",
                        **ref,
                    }
                )
                continue
            linked_refs += 1
            linked = {**dict(link), **ref, "acf_basename": acf_key}
            video_links.append(linked)
            asset_links.append(linked)
        if video_links:
            script["video_links"] = video_links
            script["asset_links"] = asset_links
    return logical_refs, linked_refs, missing_refs, missing_names


def enrich_scene_video_links(catalog: dict[str, Any]) -> None:
    video_lookup = build_video_lookup(catalog)
    totals: dict[str, int] = {
        "script_logical_refs": 0,
        "script_linked_refs": 0,
        "script_missing_refs": 0,
    }
    missing_names: set[str] = set()
    if not video_lookup:
        catalog["metadata"]["scene_video_links"] = {
            **totals,
            "source": f"{VIDEO_ARCHIVE_NAME} unavailable",
            "missing_acf_names": [],
        }
        return

    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        reconnaissance = (asset.get("stats") or {}).get("reconnaissance") or {}
        scene_counts = {key: 0 for key in totals}
        owners = [reconnaissance.get("hero") or {}, *(reconnaissance.get("sampled_objects") or [])]
        for owner in owners:
            logical, linked, missing, names = add_script_video_links(owner, video_lookup)
            scene_counts["script_logical_refs"] += logical
            scene_counts["script_linked_refs"] += linked
            scene_counts["script_missing_refs"] += missing
            missing_names.update(names)
        reconnaissance["video_link_counts"] = scene_counts
        for key, count in scene_counts.items():
            totals[key] = totals.get(key, 0) + count

    catalog["metadata"]["scene_video_links"] = {
        **totals,
        "source": "PLAYACF.CPP GetNumAcf/PlayAcf with RESS.HQR:48 and VIDEO/VIDEO.HQR",
        "missing_acf_names": sorted(missing_names, key=str.upper),
        "missing_acf_details": [
            {
                "acf_name": name,
                "acf_basename": normalize_acf_name(name),
                "acf_name_hex": name.encode("latin-1", errors="replace").hex(),
            }
            for name in sorted(missing_names, key=str.upper)
        ],
        "video_asset_count": len(video_lookup),
    }


def build_scene_usage_record(
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    link_kind: str,
    link: dict[str, Any],
) -> dict[str, Any]:
    source = scene_asset.get("source") or {}
    scene_entry_index = int(source.get("entry_index") or 0)
    usage: dict[str, Any] = {
        "kind": link_kind,
        "scene_asset_id": scene_asset.get("id"),
        "scene_label": scene_asset.get("label"),
        "scene_entry_index": scene_entry_index,
        "scene_index": scene_entry_index - 1
        if source.get("hqr") == SCENE_ARCHIVE_NAME and scene_entry_index > 0
        else None,
        "object_index": scene_object.get("index"),
        "position": scene_object.get("position"),
        "file3d_index": scene_object.get("file3d_index"),
        "gen_body": scene_object.get("gen_body"),
        "gen_anim": scene_object.get("gen_anim"),
        "sprite": scene_object.get("sprite"),
        "flags": scene_object.get("flags"),
        "target_asset_id": link.get("asset_id"),
        "resolution_rule": link.get("resolution_rule") or link.get("index_rule"),
    }
    if link_kind == "body":
        usage["generic_id"] = link.get("generic_id")
        usage["body_index"] = link.get("body_index")
    elif link_kind == "animation":
        usage["generic_id"] = link.get("generic_id")
        usage["generic_name"] = link.get("generic_name")
        usage["label"] = link.get("label")
        usage["animation_index"] = link.get("animation_index")
    elif link_kind == "sprite":
        usage["backend"] = link.get("backend")
        usage["runtime_sprite_index"] = link.get("runtime_sprite_index", link.get("sprite_index"))
        usage["index_rule"] = link.get("index_rule")
        if isinstance(link.get("anim3ds_range"), dict):
            usage["anim3ds_range"] = link["anim3ds_range"]
    elif link_kind == "text":
        usage["text_id"] = link.get("text_id", link.get("reference_value"))
        usage["text_file_index"] = link.get("text_file_index")
        usage["text_file_name"] = link.get("text_file_name")
        usage["language"] = link.get("language")
        usage["record_index"] = link.get("record_index")
        usage["record_flag"] = link.get("record_flag")
        usage["preview"] = link.get("preview")
    elif link_kind == "sample":
        usage["sample_id"] = link.get("sample_id", link.get("reference_value"))
        usage["audio_format"] = link.get("audio_format")
        usage["sample_rate"] = link.get("sample_rate")
        usage["bits_per_sample"] = link.get("bits_per_sample")
        usage["channels"] = link.get("channels")
        usage["duration_ms"] = link.get("duration_ms")
    elif link_kind == "video":
        usage["acf_name"] = link.get("acf_name", link.get("reference_value"))
        usage["acf_index"] = link.get("acf_index")
        usage["width"] = link.get("width")
        usage["height"] = link.get("height")
        usage["frame_count"] = link.get("frame_count")
        usage["duration_ms"] = link.get("duration_ms")
    return usage


def build_scene_zone_text_usage_record(
    scene_asset: dict[str, Any], link: dict[str, Any]
) -> dict[str, Any]:
    source = scene_asset.get("source") or {}
    scene_entry_index = int(source.get("entry_index") or 0)
    return {
        "kind": "zone_text",
        "scene_asset_id": scene_asset.get("id"),
        "scene_label": scene_asset.get("label"),
        "scene_entry_index": scene_entry_index,
        "scene_index": scene_entry_index - 1
        if source.get("hqr") == SCENE_ARCHIVE_NAME and scene_entry_index > 0
        else None,
        "object_index": None,
        "position": link.get("start"),
        "file3d_index": None,
        "gen_body": None,
        "gen_anim": None,
        "sprite": None,
        "flags": None,
        "target_asset_id": link.get("asset_id"),
        "resolution_rule": link.get("resolution_rule"),
        "reference_key": "zone_message",
        "reference_value": link.get("text_id"),
        "zone_index": link.get("zone_index"),
        "text_id": link.get("text_id"),
        "text_file_index": link.get("text_file_index"),
        "text_file_name": link.get("text_file_name"),
        "language": link.get("language"),
        "record_index": link.get("record_index"),
        "record_flag": link.get("record_flag"),
        "preview": link.get("preview"),
        "facing_direction": link.get("facing_direction"),
    }


def build_scene_ambience_sample_usage_record(
    scene_asset: dict[str, Any], link: dict[str, Any]
) -> dict[str, Any]:
    source = scene_asset.get("source") or {}
    scene_entry_index = int(source.get("entry_index") or 0)
    return {
        "kind": "ambience_sample",
        "scene_asset_id": scene_asset.get("id"),
        "scene_label": scene_asset.get("label"),
        "scene_entry_index": scene_entry_index,
        "scene_index": scene_entry_index - 1
        if source.get("hqr") == SCENE_ARCHIVE_NAME and scene_entry_index > 0
        else None,
        "object_index": None,
        "position": None,
        "file3d_index": None,
        "gen_body": None,
        "gen_anim": None,
        "sprite": None,
        "flags": None,
        "target_asset_id": link.get("asset_id"),
        "resolution_rule": link.get("resolution_rule"),
        "reference_key": "ambience_sample",
        "reference_value": link.get("sample_id"),
        "sample_id": link.get("sample_id"),
        "slot_index": link.get("slot_index"),
        "repeat": link.get("repeat"),
        "random": link.get("random"),
        "frequency": link.get("frequency"),
        "volume": link.get("volume"),
        "audio_format": link.get("audio_format"),
        "sample_rate": link.get("sample_rate"),
        "bits_per_sample": link.get("bits_per_sample"),
        "channels": link.get("channels"),
        "duration_ms": link.get("duration_ms"),
    }


def build_scene_script_usage_record(
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    script_key: str,
    link: dict[str, Any],
) -> dict[str, Any]:
    source = scene_asset.get("source") or {}
    scene_entry_index = int(source.get("entry_index") or 0)
    link_kind = str(link.get("kind") or "unknown")
    usage: dict[str, Any] = {
        "kind": f"script_{link_kind}",
        "scene_asset_id": scene_asset.get("id"),
        "scene_label": scene_asset.get("label"),
        "scene_entry_index": scene_entry_index,
        "scene_index": scene_entry_index - 1
        if source.get("hqr") == SCENE_ARCHIVE_NAME and scene_entry_index > 0
        else None,
        "object_index": scene_object.get("index"),
        "position": scene_object.get("position"),
        "file3d_index": scene_object.get("file3d_index"),
        "gen_body": scene_object.get("gen_body"),
        "gen_anim": scene_object.get("gen_anim"),
        "sprite": scene_object.get("sprite"),
        "flags": scene_object.get("flags"),
        "target_asset_id": link.get("asset_id"),
        "resolution_rule": link.get("resolution_rule") or link.get("index_rule"),
        "script_kind": "track" if script_key.startswith("track_") else "life",
        "reference_key": link.get("reference_key"),
        "reference_value": link.get("reference_value"),
    }
    if link_kind == "body":
        usage["generic_id"] = link.get("generic_id")
        usage["body_index"] = link.get("body_index")
    elif link_kind == "animation":
        usage["generic_id"] = link.get("generic_id")
        usage["generic_name"] = link.get("generic_name")
        usage["label"] = link.get("label")
        usage["animation_index"] = link.get("animation_index")
    elif link_kind == "sprite":
        usage["backend"] = link.get("backend")
        usage["runtime_sprite_index"] = link.get("runtime_sprite_index", link.get("sprite_index"))
        usage["index_rule"] = link.get("index_rule")
        if isinstance(link.get("anim3ds_range"), dict):
            usage["anim3ds_range"] = link["anim3ds_range"]
    elif link_kind == "text":
        usage["text_id"] = link.get("text_id", link.get("reference_value"))
        usage["text_file_index"] = link.get("text_file_index")
        usage["text_file_name"] = link.get("text_file_name")
        usage["language"] = link.get("language")
        usage["record_index"] = link.get("record_index")
        usage["record_flag"] = link.get("record_flag")
        usage["preview"] = link.get("preview")
    elif link_kind == "sample":
        usage["sample_id"] = link.get("sample_id", link.get("reference_value"))
        usage["audio_format"] = link.get("audio_format")
        usage["sample_rate"] = link.get("sample_rate")
        usage["bits_per_sample"] = link.get("bits_per_sample")
        usage["channels"] = link.get("channels")
        usage["duration_ms"] = link.get("duration_ms")
    return usage


def enrich_scene_asset_usage(catalog: dict[str, Any]) -> None:
    assets_by_id = {
        asset.get("id"): asset for asset in catalog.get("assets", []) if asset.get("id")
    }
    usage_ref_count = 0
    by_kind: dict[str, int] = {}
    used_asset_ids: set[str] = set()

    for scene_asset in catalog.get("assets", []):
        if scene_asset.get("kind") != "scene":
            continue
        reconnaissance = (scene_asset.get("stats") or {}).get("reconnaissance") or {}
        hero = reconnaissance.get("hero") or {}
        hero_owner = {
            **hero,
            "index": 0,
            "position": hero.get("start"),
            "file3d_index": -1,
            "gen_body": 0,
            "gen_anim": 0,
            "sprite": 0,
            "flags": 0,
        }
        for scene_object in [hero_owner, *(reconnaissance.get("sampled_objects") or [])]:
            links = scene_object.get("links") or {}
            for link_kind in ("body", "animation", "sprite"):
                link = links.get(link_kind)
                if not link:
                    continue
                target_asset_id = link.get("asset_id")
                target_asset = assets_by_id.get(target_asset_id)
                if target_asset is None:
                    continue
                usage = build_scene_usage_record(
                    scene_asset, scene_object, link_kind, link
                )
                target_asset.setdefault("scene_usages", []).append(usage)
                target_asset.setdefault("features", {})["scene_usage_count"] = len(
                    target_asset["scene_usages"]
                )
                usage_ref_count += 1
                by_kind[link_kind] = by_kind.get(link_kind, 0) + 1
                used_asset_ids.add(target_asset_id)
            for script_key in ("track_script_analysis", "life_script_analysis"):
                script = scene_object.get(script_key) or {}
                for script_link in script.get("asset_links") or []:
                    target_asset_id = script_link.get("asset_id")
                    target_asset = assets_by_id.get(target_asset_id)
                    if target_asset is None:
                        continue
                    usage = build_scene_script_usage_record(
                        scene_asset, scene_object, script_key, script_link
                    )
                    usage_kind = str(usage.get("kind") or "unknown")
                    target_asset.setdefault("scene_usages", []).append(usage)
                    target_asset.setdefault("features", {})["scene_usage_count"] = len(
                        target_asset["scene_usages"]
                    )
                    usage_ref_count += 1
                    by_kind[usage_kind] = by_kind.get(usage_kind, 0) + 1
                    used_asset_ids.add(target_asset_id)
        for text_link in reconnaissance.get("text_zone_links") or []:
            target_asset_id = text_link.get("asset_id")
            target_asset = assets_by_id.get(target_asset_id)
            if target_asset is None:
                continue
            usage = build_scene_zone_text_usage_record(scene_asset, text_link)
            usage_kind = str(usage.get("kind") or "unknown")
            target_asset.setdefault("scene_usages", []).append(usage)
            target_asset.setdefault("features", {})["scene_usage_count"] = len(
                target_asset["scene_usages"]
            )
            usage_ref_count += 1
            by_kind[usage_kind] = by_kind.get(usage_kind, 0) + 1
            used_asset_ids.add(target_asset_id)
        for sample_link in reconnaissance.get("sample_ambience_links") or []:
            target_asset_id = sample_link.get("asset_id")
            target_asset = assets_by_id.get(target_asset_id)
            if target_asset is None:
                continue
            usage = build_scene_ambience_sample_usage_record(scene_asset, sample_link)
            usage_kind = str(usage.get("kind") or "unknown")
            target_asset.setdefault("scene_usages", []).append(usage)
            target_asset.setdefault("features", {})["scene_usage_count"] = len(
                target_asset["scene_usages"]
            )
            usage_ref_count += 1
            by_kind[usage_kind] = by_kind.get(usage_kind, 0) + 1
            used_asset_ids.add(target_asset_id)
        for grm_link in reconnaissance.get("grm_fragment_links") or []:
            target_asset_id = grm_link.get("asset_id")
            target_asset = assets_by_id.get(target_asset_id)
            if target_asset is None:
                continue
            scene_source = scene_asset.get("source") or {}
            usage = {
                "kind": "grm_fragment",
                "scene_asset_id": scene_asset.get("id"),
                "scene_label": scene_asset.get("label"),
                "scene_entry_index": scene_source.get("entry_index"),
                "scene_index": int(scene_source["entry_index"]) - 1
                if isinstance(scene_source.get("entry_index"), int)
                else None,
                "zone_index": grm_link.get("zone_index"),
                "reference_key": "grm_zone",
                "reference_value": grm_link.get("zone_value"),
                "target_asset_id": target_asset_id,
                "grm_index": grm_link.get("grm_index"),
                "resolved_grm_entry": grm_link.get("resolved_grm_entry"),
                "target_cell_start": grm_link.get("target_cell_start"),
                "fragment_dimensions": grm_link.get("fragment_dimensions"),
                "resolution_rule": "scene GRM zone Info0 plus selected GRI My_Grm base resolves LBA_BKG.HQR fragment entry",
            }
            target_asset.setdefault("scene_usages", []).append(usage)
            target_asset.setdefault("features", {})["scene_usage_count"] = len(
                target_asset["scene_usages"]
            )
            usage_ref_count += 1
            by_kind["grm_fragment"] = by_kind.get("grm_fragment", 0) + 1
            used_asset_ids.add(str(target_asset_id))

    for asset_id in used_asset_ids:
        assets_by_id[asset_id]["scene_usages"].sort(
            key=lambda usage: (
                usage.get("scene_index") is None,
                usage.get("scene_index") or 0,
                usage.get("object_index") or 0,
                usage.get("kind") or "",
            )
        )

    catalog["metadata"]["scene_asset_usage"] = {
        "usage_ref_count": usage_ref_count,
        "used_asset_count": len(used_asset_ids),
        "by_kind": by_kind,
    }


def animation_catalog_label(
    archive_name: str, entry_index: int, metadata: dict[str, Any] | None
) -> str:
    if not metadata:
        return f"{archive_name} animation {entry_index}"
    labels = metadata.get("labels")
    generic_names = metadata.get("generic_names")
    if isinstance(labels, list) and labels:
        label = ", ".join(str(value) for value in labels[:2])
        if len(labels) > 2:
            label += f" +{len(labels) - 2}"
    elif isinstance(generic_names, list) and generic_names:
        label = ", ".join(str(value) for value in generic_names[:2])
        if len(generic_names) > 2:
            label += f" +{len(generic_names) - 2}"
    else:
        return f"{archive_name} animation {entry_index}"
    return f"{label} ({archive_name}:{entry_index})"


def anim_hqr_catalog_asset(
    *,
    asset_id: str,
    hqr_relative: str,
    catalog_entry_index: int,
    source: dict[str, Any],
    payload: bytes,
    animation_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        animation = parse_lba2_animation(payload)
        animation_error = ""
    except (AnimationError, Lm2Error) as exc:
        animation = None
        animation_error = str(exc)

    if animation is not None:
        stats = animation.to_json()
        entry_type = "animation"
        animation_state = "decoded"
        features = {
            "looping": animation.loop_frame < animation.keyframes - 1,
            "can_fall": animation.can_fall,
            "parsed": True,
        }
    else:
        stats = raw_animation_catalog_stats(
            payload,
            decode_status="parse_failed",
            decode_note="Animation parser rejected this payload; retained as raw evidence.",
            parse_error=animation_error,
        )
        entry_type = "animation-raw"
        animation_state = "raw"
        features = {"parsed": False}

    asset = {
        "id": asset_id,
        "kind": "animation",
        "label": animation_catalog_label(
            Path(hqr_relative).name,
            catalog_entry_index,
            animation_metadata,
        ),
        "entry_type": entry_type,
        "source": source,
        "path": hqr_relative,
        "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "stats": stats,
        "features": features,
        "animation_state": animation_state,
    }
    if animation_metadata is not None:
        asset["animation_metadata"] = animation_metadata
    return asset


def anim3ds_catalog_label(entry_index: int, stats: dict[str, Any]) -> str:
    if stats.get("semantic_layout") == "anim3ds_frame_ranges":
        count = stats.get("entry_count", 0)
        return f"ANIM3DS frame range table ({count} animations)"
    info = stats.get("anim3ds_info")
    if isinstance(info, dict):
        name = info.get("name") or f"animation {info.get('animation_index', '?')}"
        relative_frame = info.get("relative_frame")
        return f"{name} sprite frame {relative_frame} (ANIM3DS.HQR:{entry_index})"
    return f"ANIM3DS sprite frame {entry_index}"


def sprite_backend_for_archive(archive_name: str) -> str | None:
    if archive_name == ANIM3DS_ARCHIVE_NAME:
        return "anim3ds"
    if archive_name == SPRITES_ARCHIVE_NAME:
        return "sprites"
    if archive_name == SPRIRAW_ARCHIVE_NAME:
        return "spriraw"
    return None


def sprite_backend_label(backend: str) -> str:
    if backend == "anim3ds":
        return "ANIM3DS.HQR"
    if backend == "sprites":
        return "SPRITES.HQR"
    if backend == "spriraw":
        return "SPRIRAW.HQR"
    return backend


def sprite_runtime_index_rule(backend: str) -> str:
    if backend == "sprites":
        return "InitSprite selects SPRITES.HQR when SPRITE_3D is set, ANIM_3DS is clear, and Sprite >= 100."
    if backend == "spriraw":
        return "InitSprite selects SPRIRAW.HQR when SPRITE_3D is set, ANIM_3DS is clear, and Sprite < 100."
    if backend == "anim3ds":
        return "InitSprite selects ANIM3DS.HQR when SPRITE_3D and ANIM_3DS are both set."
    return ""


def sprite_bounds_source_entry(backend: str) -> int | None:
    if backend == "sprites":
        return RESS_GOODIES_GPC_ENTRY_INDEX
    if backend == "spriraw":
        return RESS_GOODRAW_GPC_ENTRY_INDEX
    if backend == "anim3ds":
        return RESS_ANIM3DS_GPC_ENTRY_INDEX
    return None


def resolve_runtime_sprite(flags: int, sprite_index: int) -> dict[str, Any]:
    is_sprite_3d = bool(flags & SPRITE_3D_FLAG)
    is_anim_3ds = bool(flags & ANIM_3DS_FLAG)
    result: dict[str, Any] = {
        "flags": flags,
        "sprite_index": sprite_index,
        "flags_decoded": {
            "SPRITE_3D": is_sprite_3d,
            "ANIM_3DS": is_anim_3ds,
        },
        "resolved": False,
        "backend": None,
        "archive": None,
        "asset_id": None,
        "bounds_source": None,
        "index_rule": "SPRITE_3D is not set; InitSprite stores Sprite but does not resolve a projected sprite backend.",
    }
    if not is_sprite_3d or sprite_index < 0:
        if sprite_index < 0:
            result["index_rule"] = "Sprite -1 is a sentinel; InitSprite does not load frame bounds for it."
        return result

    if is_anim_3ds:
        backend = "anim3ds"
    elif sprite_index >= 100:
        backend = "sprites"
    else:
        backend = "spriraw"

    archive = sprite_backend_label(backend)
    bounds_entry = sprite_bounds_source_entry(backend)
    result.update(
        {
            "resolved": True,
            "backend": backend,
            "archive": archive,
            "asset_id": f"{archive}:{sprite_index}",
            "bounds_source": (
                {"hqr": RESS_ARCHIVE_NAME, "entry_index": bounds_entry}
                if bounds_entry is not None
                else None
            ),
            "index_rule": sprite_runtime_index_rule(backend),
        }
    )
    return result


def sprite_archive_runtime_info(backend: str, runtime_index: int) -> dict[str, Any]:
    archive = sprite_backend_label(backend)
    bounds_entry = sprite_bounds_source_entry(backend)
    flags = SPRITE_3D_FLAG | (ANIM_3DS_FLAG if backend == "anim3ds" else 0)
    if backend == "sprites" and runtime_index < 100:
        index_rule = (
            "SPRITES.HQR low slots are valid direct HQRPtrSprite entries for UI/system drawing; "
            "projected scene sprites select this archive only when Sprite >= 100."
        )
    else:
        index_rule = sprite_runtime_index_rule(backend)
    return {
        "flags": flags,
        "sprite_index": runtime_index,
        "flags_decoded": {
            "SPRITE_3D": True,
            "ANIM_3DS": backend == "anim3ds",
        },
        "resolved": True,
        "backend": backend,
        "archive": archive,
        "asset_id": f"{archive}:{runtime_index}",
        "bounds_source": (
            {"hqr": RESS_ARCHIVE_NAME, "entry_index": bounds_entry}
            if bounds_entry is not None
            else None
        ),
        "index_rule": index_rule,
        "runtime_sprite_index": runtime_index,
    }


def runtime_object_sprite_state(
    *,
    flags: int,
    sprite_index: int,
    body_num: int | None = None,
    label_track: int | None = None,
    object_index: int | None = None,
) -> dict[str, Any]:
    resolution = resolve_runtime_sprite(flags, sprite_index)
    state: dict[str, Any] = {
        "object_index": object_index,
        "flags": flags,
        "sprite_index": sprite_index,
        "body_num": body_num,
        "label_track": label_track,
        "resolution": resolution,
    }
    if body_num is not None:
        state["body_num_matches_sprite"] = body_num == sprite_index
        state["body_num_note"] = (
            "Obj.Body.Num mirrors Sprite after InitSprite applies a new projected sprite."
            if body_num == sprite_index
            else "Obj.Body.Num differs from Sprite; runtime may not have applied this Sprite yet, or the snapshot is from an intermediate transition."
        )
    return state


def sprite_runtime_model_metadata() -> dict[str, Any]:
    return {
        "source": "classic InitSprite / projected sprite render path",
        "flags": {
            "SPRITE_3D": SPRITE_3D_FLAG,
            "ANIM_3DS": ANIM_3DS_FLAG,
        },
        "rules": [
            resolve_runtime_sprite(SPRITE_3D_FLAG | ANIM_3DS_FLAG, 0),
            resolve_runtime_sprite(SPRITE_3D_FLAG, 100),
            resolve_runtime_sprite(SPRITE_3D_FLAG, 99),
        ],
    }


DIRECT_SPRITE_CODE_REFERENCES: dict[str, dict[int, list[dict[str, Any]]]] = {
    "sprites": {
        0: [
            {
                "symbol": "SYS_SPRITE_SG",
                "purpose": "frame upper-left corner sprite",
                "source": "COMMON.H / DrawCadre",
            }
        ],
        1: [
            {
                "symbol": "SYS_SPRITE_IG",
                "purpose": "frame lower-left corner sprite",
                "source": "COMMON.H / DrawCadre",
            }
        ],
        2: [
            {
                "symbol": "SYS_SPRITE_ID",
                "purpose": "frame lower-right corner sprite",
                "source": "COMMON.H / DrawCadre",
            }
        ],
        3: [
            {
                "symbol": "SYS_SPRITE_SD",
                "purpose": "frame upper-right corner sprite",
                "source": "COMMON.H / DrawCadre",
            }
        ],
        4: [
            {
                "symbol": "ARROW_SG sprite",
                "purpose": "frame upper-left arrow drawn by DrawCadre",
                "source": "INVENT.CPP::DrawCadre",
            }
        ],
        5: [
            {
                "symbol": "ARROW_IG sprite",
                "purpose": "frame lower-left arrow drawn by DrawCadre",
                "source": "INVENT.CPP::DrawCadre",
            }
        ],
        6: [
            {
                "symbol": "ARROW_ID sprite",
                "purpose": "frame lower-right arrow drawn by DrawCadre",
                "source": "INVENT.CPP::DrawCadre",
            }
        ],
        7: [
            {
                "symbol": "ARROW_SD sprite",
                "purpose": "frame upper-right arrow drawn by DrawCadre",
                "source": "INVENT.CPP::DrawCadre",
            }
        ],
        9: [
            {
                "symbol": "DrawCursor",
                "purpose": "player-name input cursor sprite",
                "source": "GAMEMENU.CPP::DrawCursor",
            }
        ],
        11: [
            {
                "symbol": "EA_VERSION logo",
                "purpose": "new-game save-frame logo for EA/unknown distribution",
                "source": "GAMEMENU.CPP::DrawCadreNewGame",
            }
        ],
        13: [
            {
                "symbol": "SYS_SPRITE_INV",
                "purpose": "unusable inventory-object overlay",
                "source": "COMMON.H / INVENT.CPP::AffOneInv",
            }
        ],
        14: [
            {
                "symbol": "SYS_SPRITE_BALD",
                "purpose": "Baldino radio portrait vignette",
                "source": "COMMON.H",
            }
        ],
        15: [
            {
                "symbol": "SYS_SPRITE_ZOE",
                "purpose": "Zoe radio portrait vignette",
                "source": "COMMON.H",
            }
        ],
        16: [
            {
                "symbol": "American logo",
                "purpose": "new-game save-frame logo for non-EA distribution",
                "source": "GAMEMENU.CPP::DrawCadreNewGame",
            }
        ],
    },
    "spriraw": {
        0: [{"symbol": "SPRITE_CLOVER_BOX", "purpose": "empty clover box extra", "source": "COMMON.H"}],
        1: [{"symbol": "SPRITE_FULL_CLOVER_BOX", "purpose": "full clover box extra", "source": "COMMON.H"}],
        2: [{"symbol": "SPRITE_DART", "purpose": "dart projectile", "source": "COMMON.H"}],
        4: [{"symbol": "SPRITE_COEUR", "purpose": "life heart extra", "source": "COMMON.H"}],
        5: [{"symbol": "SPRITE_MAGIE", "purpose": "magic extra", "source": "COMMON.H"}],
        6: [{"symbol": "SPRITE_CLE", "purpose": "key extra", "source": "COMMON.H"}],
        7: [{"symbol": "SPRITE_CLOVER", "purpose": "clover extra", "source": "COMMON.H"}],
        8: [{"symbol": "SPRITE_BALLE_LVL_01", "purpose": "magic-ball level 1 projectile", "source": "COMMON.H"}],
        9: [{"symbol": "SPRITE_BALLE_LVL_2", "purpose": "magic-ball level 2 projectile", "source": "COMMON.H"}],
        10: [{"symbol": "SPRITE_BALLE_LVL_3", "purpose": "magic-ball level 3 projectile", "source": "COMMON.H"}],
        11: [{"symbol": "SPRITE_BALLE_LVL_4", "purpose": "magic-ball level 4 projectile", "source": "COMMON.H"}],
        12: [{"symbol": "SPRITE_BALLE_SHADOW", "purpose": "magic-ball shadow", "source": "COMMON.H"}],
        13: [{"symbol": "SPRITE_BALLE_SHADOW_2", "purpose": "magic-ball shadow variant", "source": "COMMON.H"}],
        14: [{"symbol": "SPRITE_BALLE_SHADOW_3", "purpose": "magic-ball shadow variant", "source": "COMMON.H"}],
        15: [{"symbol": "SPRITE_TRAINEE_BALLE_1", "purpose": "magic-ball trail", "source": "COMMON.H"}],
        16: [{"symbol": "SPRITE_TRAINEE_BALLE_2", "purpose": "magic-ball trail", "source": "COMMON.H"}],
        17: [{"symbol": "SPRITE_TRAINEE_BALLE_3", "purpose": "magic-ball trail", "source": "COMMON.H"}],
        18: [{"symbol": "SPRITE_KASHES", "purpose": "Kashes currency extra", "source": "COMMON.H"}],
        19: [{"symbol": "SPRITE_ZLITOS", "purpose": "Zlitos currency extra", "source": "COMMON.H"}],
        21: [{"symbol": "SPRITE_FOUDRE", "purpose": "lightning effect sprite", "source": "COMMON.H"}],
        30: [{"symbol": "SPRITE_PROTECT", "purpose": "protection effect sprite", "source": "COMMON.H"}],
    },
}


def direct_sprite_code_references(backend: str, runtime_index: int) -> list[dict[str, Any]]:
    references = DIRECT_SPRITE_CODE_REFERENCES.get(backend, {}).get(runtime_index, [])
    return [dict(reference) for reference in references]


OBJFIX_DIRECT_REFERENCES: dict[int, list[dict[str, Any]]] = {
    0: [{"symbol": "FLAG_HOLOMAP", "purpose": "inventory holomap object", "source": "INVENT.CPP InitTabInv"}],
    1: [{"symbol": "FLAG_BALLE_MAGIQUE", "purpose": "inventory magic ball level 1", "source": "INVENT.CPP InitTabInv"}],
    2: [{"symbol": "FLAG_DART", "purpose": "inventory dart", "source": "INVENT.CPP InitTabInv"}],
    3: [{"symbol": "FLAG_BOULE_SENDELL", "purpose": "inventory Sendell ball", "source": "INVENT.CPP InitTabInv"}],
    4: [{"symbol": "FLAG_TUNIQUE", "purpose": "inventory tunic", "source": "INVENT.CPP InitTabInv"}],
    5: [{"symbol": "FLAG_PERLE", "purpose": "inventory pearl / route disk slot", "source": "INVENT.CPP InitTabInv"}],
    6: [{"symbol": "FLAG_CLEF_PYRAMID", "purpose": "inventory pyramid key", "source": "INVENT.CPP InitTabInv"}],
    7: [{"symbol": "FLAG_VOLANT", "purpose": "inventory steering wheel", "source": "INVENT.CPP InitTabInv"}],
    8: [{"symbol": "FLAG_MONEY", "purpose": "inventory Kashes currency variant", "source": "INVENT.CPP InitTabInv"}],
    9: [{"symbol": "FLAG_PISTOLASER", "purpose": "inventory laser pistol variant", "source": "INVENT.CPP InitTabInv"}],
    10: [{"symbol": "FLAG_SABRE", "purpose": "inventory sword", "source": "INVENT.CPP InitTabInv"}],
    11: [{"symbol": "FLAG_GANT", "purpose": "inventory glove", "source": "INVENT.CPP InitTabInv"}],
    12: [{"symbol": "FLAG_PROTOPACK", "purpose": "inventory protopack variant", "source": "INVENT.CPP InitTabInv"}],
    13: [{"symbol": "FLAG_TICKET_FERRY", "purpose": "inventory ferry ticket", "source": "INVENT.CPP InitTabInv"}],
    14: [{"symbol": "FLAG_MECA_PINGOUIN", "purpose": "inventory meca-penguin", "source": "INVENT.CPP InitTabInv"}],
    15: [{"symbol": "FLAG_GAZOGEM", "purpose": "inventory gazogem", "source": "INVENT.CPP InitTabInv"}],
    16: [{"symbol": "FLAG_DEMI_MEDAILLON", "purpose": "inventory half medallion", "source": "INVENT.CPP InitTabInv"}],
    17: [{"symbol": "FLAG_ACIDE_GALLIQUE", "purpose": "inventory gallic acid", "source": "INVENT.CPP InitTabInv"}],
    18: [{"symbol": "FLAG_CHANSON", "purpose": "inventory song", "source": "INVENT.CPP InitTabInv"}],
    19: [{"symbol": "FLAG_ANNEAU_FOUDRE", "purpose": "inventory lightning ring level 1", "source": "INVENT.CPP InitTabInv"}],
    20: [{"symbol": "FLAG_PARAPLUIE", "purpose": "inventory umbrella", "source": "INVENT.CPP InitTabInv"}],
    21: [{"symbol": "FLAG_GEMME", "purpose": "inventory gem", "source": "INVENT.CPP InitTabInv"}],
    22: [{"symbol": "FLAG_CONQUE", "purpose": "inventory Horn of Blue Triton", "source": "INVENT.CPP InitTabInv"}],
    23: [{"symbol": "FLAG_SARBACANE", "purpose": "inventory blowgun variant", "source": "INVENT.CPP InitTabInv"}],
    24: [{"symbol": "FLAG_PERLE", "purpose": "inventory route disk alternate object", "source": "INVENT.CPP InitTabInv"}],
    25: [{"symbol": "FLAG_TART_LUCI", "purpose": "inventory Luci tart", "source": "INVENT.CPP InitTabInv"}],
    26: [{"symbol": "FLAG_RADIO", "purpose": "inventory radio", "source": "INVENT.CPP InitTabInv"}],
    27: [{"symbol": "FLAG_FLEUR", "purpose": "inventory flower", "source": "INVENT.CPP InitTabInv"}],
    28: [{"symbol": "FLAG_ARDOISE", "purpose": "inventory slate", "source": "INVENT.CPP InitTabInv"}],
    29: [{"symbol": "FLAG_TRADUCTEUR", "purpose": "inventory translator", "source": "INVENT.CPP InitTabInv"}],
    30: [{"symbol": "FLAG_DIPLOME", "purpose": "inventory diploma", "source": "INVENT.CPP InitTabInv"}],
    31: [{"symbol": "FLAG_DMKEY_KNARTA", "purpose": "inventory Dark Monk key", "source": "INVENT.CPP InitTabInv"}],
    32: [{"symbol": "FLAG_DMKEY_SUP", "purpose": "inventory Sup Dark Monk key", "source": "INVENT.CPP InitTabInv"}],
    33: [{"symbol": "FLAG_DMKEY_MOSQUI", "purpose": "inventory Mosquibee Dark Monk key", "source": "INVENT.CPP InitTabInv"}],
    34: [{"symbol": "FLAG_DMKEY_BLAFARD", "purpose": "inventory Blafard Dark Monk key", "source": "INVENT.CPP InitTabInv"}],
    35: [{"symbol": "FLAG_CLE_REINE", "purpose": "inventory queen key", "source": "INVENT.CPP InitTabInv"}],
    36: [{"symbol": "FLAG_PIOCHE", "purpose": "inventory pickaxe", "source": "INVENT.CPP InitTabInv"}],
    37: [{"symbol": "FLAG_CLEF_BOURGMESTRE", "purpose": "inventory mayor key", "source": "INVENT.CPP InitTabInv"}],
    38: [{"symbol": "FLAG_NOTE_BOURGMESTRE", "purpose": "inventory mayor note", "source": "INVENT.CPP InitTabInv"}],
    39: [{"symbol": "FLAG_PROTECTION", "purpose": "inventory protection spell", "source": "INVENT.CPP InitTabInv"}],
    40: [{"symbol": "FLAG_BALLE_MAGIQUE", "purpose": "inventory magic ball level 2", "source": "INVENT.CPP InitTabInv"}],
    41: [{"symbol": "FLAG_BALLE_MAGIQUE", "purpose": "inventory magic ball level 3", "source": "INVENT.CPP InitTabInv"}],
    42: [{"symbol": "FLAG_BALLE_MAGIQUE", "purpose": "inventory magic ball level 4", "source": "INVENT.CPP InitTabInv"}],
    43: [{"symbol": "FLAG_MONEY", "purpose": "inventory Zlitos currency variant", "source": "INVENT.CPP InitTabInv"}],
    44: [{"symbol": "FLAG_DMKEY_KNARTA", "purpose": "inventory Dark Monk key alternate object", "source": "INVENT.CPP InitTabInv"}],
    45: [{"symbol": "VISIONNEUSE", "purpose": "inventory memory viewer", "source": "INVENT.CPP InitTabInv"}],
    46: [{"symbol": "FLAG_SARBACANE", "purpose": "inventory blowgun alternate object", "source": "INVENT.CPP InitTabInv"}],
    47: [{"symbol": "FLAG_TUNIQUE", "purpose": "inventory tunic alternate object", "source": "INVENT.CPP InitTabInv"}],
    48: [{"symbol": "FLAG_PROTOPACK", "purpose": "inventory protopack alternate object", "source": "INVENT.CPP InitTabInv"}],
    49: [{"symbol": "FLAG_PISTOLASER", "purpose": "inventory laser pistol initial variant", "source": "INVENT.CPP InitTabInv"}],
    50: [{"symbol": "FLAG_PISTOLASER", "purpose": "inventory laser pistol final variant", "source": "INVENT.CPP InitTabInv"}],
    51: [{"symbol": "FLAG_ANNEAU_FOUDRE", "purpose": "inventory lightning ring level 2", "source": "INVENT.CPP InitTabInv"}],
    52: [{"symbol": "FLAG_ANNEAU_FOUDRE", "purpose": "inventory lightning ring level 3", "source": "INVENT.CPP InitTabInv"}],
    53: [{"symbol": "FLAG_ANNEAU_FOUDRE", "purpose": "inventory lightning ring level 4", "source": "INVENT.CPP InitTabInv"}],
    60: [{"symbol": "BODY_3D_CLOVER", "purpose": "runtime clover extra fixed object", "source": "COMMON.H / EXTRA.CPP"}],
    61: [{"symbol": "BODY_3D_DART", "purpose": "runtime dart fixed object", "source": "DART.H / DART.CPP"}],
    62: [{"symbol": "BODY_SORT_PROTECT", "purpose": "sorted protection fixed object", "source": "INVENT.H"}],
}


def direct_objfix_code_references(entry_index: int) -> list[dict[str, Any]]:
    references = OBJFIX_DIRECT_REFERENCES.get(entry_index, [])
    return [dict(reference) for reference in references]


def sprite_catalog_label(archive_name: str, entry_index: int, stats: dict[str, Any]) -> str:
    if archive_name == ANIM3DS_ARCHIVE_NAME:
        return anim3ds_catalog_label(entry_index, stats)
    if archive_name == SPRITES_ARCHIVE_NAME:
        return f"Runtime sprite {entry_index} (SPRITES.HQR:{entry_index})"
    if archive_name == SPRIRAW_ARCHIVE_NAME:
        return f"Raw runtime sprite {entry_index} (SPRIRAW.HQR:{entry_index})"
    return f"{archive_name} sprite frame {entry_index}"


def decoded_entry(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    decoded, header = lba_hqr.decode_resource_entry(raw)
    return decoded, {
        "size_file": header.size_file,
        "compressed_size_file": header.compressed_size_file,
        "compress_method": header.compress_method,
    }


WAVE_FORMAT_NAMES = {
    1: "pcm",
    17: "ima_adpcm",
}


def parse_wave_sample(payload: bytes) -> dict[str, Any]:
    if len(payload) < 44 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise Lm2Error("sample payload is not a RIFF/WAVE stream")
    riff_size = struct.unpack_from("<I", payload, 4)[0]
    pos = 12
    fmt: dict[str, Any] | None = None
    fact_samples: int | None = None
    data_offset: int | None = None
    data_bytes: int | None = None
    chunk_ids: list[str] = []
    while pos + 8 <= len(payload):
        chunk_id = payload[pos : pos + 4]
        chunk_size = struct.unpack_from("<I", payload, pos + 4)[0]
        chunk_body = pos + 8
        chunk_end = chunk_body + chunk_size
        if chunk_end > len(payload):
            raise Lm2Error(f"WAVE chunk {chunk_id!r} exceeds payload bounds")
        chunk_ids.append(chunk_id.decode("ascii", errors="replace"))
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise Lm2Error("WAVE fmt chunk is too small")
            (
                format_tag,
                channels,
                sample_rate,
                byte_rate,
                block_align,
                bits_per_sample,
            ) = struct.unpack_from("<HHIIHH", payload, chunk_body)
            extra_size = 0
            samples_per_block = None
            if chunk_size > 16:
                if chunk_size < 18:
                    raise Lm2Error("WAVE fmt extension is truncated")
                extra_size = struct.unpack_from("<H", payload, chunk_body + 16)[0]
                if extra_size >= 2 and chunk_body + 20 <= chunk_end:
                    samples_per_block = struct.unpack_from("<H", payload, chunk_body + 18)[0]
            fmt = {
                "format_tag": format_tag,
                "format_name": WAVE_FORMAT_NAMES.get(format_tag, f"format_{format_tag}"),
                "channels": channels,
                "sample_rate": sample_rate,
                "byte_rate": byte_rate,
                "block_align": block_align,
                "bits_per_sample": bits_per_sample,
                "fmt_chunk_bytes": chunk_size,
                "fmt_extra_bytes": extra_size,
                "samples_per_block": samples_per_block,
            }
        elif chunk_id == b"fact":
            if chunk_size >= 4:
                fact_samples = struct.unpack_from("<I", payload, chunk_body)[0]
        elif chunk_id == b"data":
            data_offset = chunk_body
            data_bytes = chunk_size
            break
        pos = chunk_end + (chunk_size & 1)
    if fmt is None:
        raise Lm2Error("WAVE stream has no fmt chunk")
    if data_offset is None or data_bytes is None:
        raise Lm2Error("WAVE stream has no data chunk")

    sample_frames: int | None = None
    if fact_samples is not None:
        sample_frames = fact_samples
    elif fmt["format_tag"] == 1 and fmt["channels"] and fmt["bits_per_sample"]:
        bytes_per_frame = fmt["channels"] * max(1, fmt["bits_per_sample"] // 8)
        sample_frames = data_bytes // bytes_per_frame if bytes_per_frame else None
    elif fmt["samples_per_block"] and fmt["block_align"]:
        sample_frames = (data_bytes // fmt["block_align"]) * fmt["samples_per_block"]
    duration_ms = (
        round(sample_frames * 1000 / fmt["sample_rate"], 3)
        if sample_frames is not None and fmt["sample_rate"]
        else None
    )
    return {
        "riff_size": riff_size,
        "chunk_ids": chunk_ids,
        **fmt,
        "fact_sample_frames": fact_samples,
        "data_offset": data_offset,
        "data_bytes": data_bytes,
        "trailing_bytes": max(0, len(payload) - (data_offset + data_bytes)),
        "sample_frames": sample_frames,
        "duration_ms": duration_ms,
    }


def sample_resource_catalog_stats(
    entry_index: int,
    payload: bytes,
    resource: dict[str, Any],
) -> dict[str, Any]:
    wave_info = parse_wave_sample(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded SAMPLES.HQR resource through the classic HQF/HQR LZ path and parsed the RIFF/WAVE audio container.",
        "semantic_layout": "sample_wave_audio",
        "sample_runtime_index": entry_index,
        "runtime_reference_status": "runtime sample ids are zero-based HQR_Get/HQF_Init indices",
        "source_provenance": "OBJECT.H GivePtrSample(index) calls HQR_Get(HQR_Samples,index); HQFILE.CPP HQF_Init seeks index*4, so sample 0 resolves to the first archive offset slot.",
        "resource_header": resource,
        "fields": {
            "riff_size": wave_info["riff_size"],
            "format_tag": wave_info["format_tag"],
            "channels": wave_info["channels"],
            "sample_rate": wave_info["sample_rate"],
            "byte_rate": wave_info["byte_rate"],
            "block_align": wave_info["block_align"],
            "bits_per_sample": wave_info["bits_per_sample"],
            "fmt_chunk_bytes": wave_info["fmt_chunk_bytes"],
            "fmt_extra_bytes": wave_info["fmt_extra_bytes"],
            "data_offset": wave_info["data_offset"],
            "data_bytes": wave_info["data_bytes"],
            "trailing_bytes": wave_info["trailing_bytes"],
        },
        "audio_format": wave_info["format_name"],
        "chunk_ids": wave_info["chunk_ids"],
        "sample_frames": wave_info["sample_frames"],
        "duration_ms": wave_info["duration_ms"],
        "samples_per_block": wave_info["samples_per_block"],
        "fact_sample_frames": wave_info["fact_sample_frames"],
        "unknown_descriptors": [],
    }


def sample_resource_catalog_label(entry_index: int, stats: dict[str, Any]) -> str:
    rate = stats.get("fields", {}).get("sample_rate", "-")
    bits = stats.get("fields", {}).get("bits_per_sample", "-")
    channels = stats.get("fields", {}).get("channels", "-")
    audio_format = stats.get("audio_format", "audio")
    return f"Sample {entry_index} {audio_format} {channels}ch {bits}-bit {rate}Hz ({SAMPLES_ARCHIVE_NAME}:{entry_index})"


def parse_palette_payload(payload: bytes) -> list[int]:
    if len(payload) != PALETTE_BYTES:
        raise Lm2Error(
            f"palette payload must be {PALETTE_BYTES} bytes, got {len(payload)}"
        )
    colors: list[int] = []
    for offset in range(0, PALETTE_BYTES, 3):
        r, g, b = payload[offset], payload[offset + 1], payload[offset + 2]
        colors.append((r << 16) | (g << 8) | b)
    return colors


def parse_texture_atlas_payload(payload: bytes, palette: list[int]) -> dict[str, Any]:
    if len(payload) != TEXTURE_ATLAS_PIXELS:
        raise Lm2Error(
            f"texture atlas payload must be {TEXTURE_ATLAS_PIXELS} bytes, got {len(payload)}"
        )
    if len(palette) != 256:
        raise Lm2Error(
            f"texture atlas decode requires 256 palette entries, got {len(palette)}"
        )
    return {
        "width": TEXTURE_ATLAS_SIZE,
        "height": TEXTURE_ATLAS_SIZE,
        "pixels": [palette[index] for index in payload],
    }


def load_palette_from_asset_root(asset_root: Path) -> list[int]:
    palette_path = asset_root / PALETTE_ARCHIVE_NAME
    if not palette_path.exists():
        raise Lm2Error(f"missing LBA2 palette archive: {palette_path}")
    data = palette_path.read_bytes()
    entries = lba_hqr.parse_classic_table(data)
    if (
        PALETTE_ENTRY_INDEX >= len(entries)
        or entries[PALETTE_ENTRY_INDEX].byte_length == 0
    ):
        raise Lm2Error(
            f"{PALETTE_ARCHIVE_NAME} has no palette entry {PALETTE_ENTRY_INDEX}"
        )
    raw = lba_hqr.read_entry(data, entries[PALETTE_ENTRY_INDEX])
    payload, _ = decoded_entry(raw)
    return parse_palette_payload(payload)


def load_texture_atlas_from_asset_root(
    asset_root: Path, palette: list[int]
) -> dict[str, Any]:
    texture_path = asset_root / PALETTE_ARCHIVE_NAME
    if not texture_path.exists():
        raise Lm2Error(f"missing LBA2 texture archive: {texture_path}")
    data = texture_path.read_bytes()
    entries = lba_hqr.parse_classic_table(data)
    if (
        TEXTURE_ENTRY_INDEX >= len(entries)
        or entries[TEXTURE_ENTRY_INDEX].byte_length == 0
    ):
        raise Lm2Error(
            f"{PALETTE_ARCHIVE_NAME} has no texture entry {TEXTURE_ENTRY_INDEX}"
        )
    raw = lba_hqr.read_entry(data, entries[TEXTURE_ENTRY_INDEX])
    payload, _ = decoded_entry(raw)
    return parse_texture_atlas_payload(payload, palette)


def load_ress_payload(asset_root: Path, entry_index: int) -> bytes | None:
    ress_path = asset_root / RESS_ARCHIVE_NAME
    if not ress_path.exists():
        return None
    data = ress_path.read_bytes()
    entries = lba_hqr.parse_table(data)
    matching = [entry for entry in entries if entry.index == entry_index]
    if not matching or matching[0].byte_length == 0:
        return None
    payload, _ = decoded_entry(lba_hqr.read_entry(data, matching[0]))
    return payload


def parse_sprite_zv_table(payload: bytes, *, backend: str, source_entry: int) -> list[dict[str, Any]]:
    if len(payload) % 16 != 0:
        raise Lm2Error(
            f"{sprite_backend_label(backend)} ZV table byte length {len(payload)} is not a multiple of 16"
        )
    records: list[dict[str, Any]] = []
    for index, offset in enumerate(range(0, len(payload), 16)):
        hotspot_x, hotspot_y, min_x, max_x, min_y, max_y, min_z, max_z = struct.unpack_from(
            "<hhhhhhhh", payload, offset
        )
        records.append(
            {
                "backend": backend,
                "index": index,
                "source": {"hqr": RESS_ARCHIVE_NAME, "entry_index": source_entry},
                "hotspot": {"x": hotspot_x, "y": hotspot_y},
                "bounds": {
                    "min_x": min_x,
                    "max_x": max_x,
                    "min_y": min_y,
                    "max_y": max_y,
                    "min_z": min_z,
                    "max_z": max_z,
                },
            }
        )
    return records


def load_sprite_zv_tables(asset_root: Path) -> dict[str, list[dict[str, Any]]]:
    table_specs = {
        "sprites": RESS_GOODIES_GPC_ENTRY_INDEX,
        "spriraw": RESS_GOODRAW_GPC_ENTRY_INDEX,
        "anim3ds": RESS_ANIM3DS_GPC_ENTRY_INDEX,
    }
    tables: dict[str, list[dict[str, Any]]] = {}
    for backend, entry_index in table_specs.items():
        payload = load_ress_payload(asset_root, entry_index)
        if payload is not None:
            tables[backend] = parse_sprite_zv_table(
                payload, backend=backend, source_entry=entry_index
            )
    return tables


def resource_unknown_descriptors(payload: bytes, note: str) -> list[dict[str, Any]]:
    return [
        unknown_bytes_descriptor(
            payload,
            section="resource_payload",
            offset=0,
            length=len(payload),
            confidence="parsed_unknown",
            note=note,
        )
    ]


def palette_catalog_stats(payload: bytes) -> dict[str, Any]:
    colors = parse_palette_payload(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded classic 256-color RGB palette used by model textures and sprite previews.",
        "semantic_layout": "lba2_palette",
        "color_count": len(colors),
        "transparent_index": 0,
        "sample_colors": colors[:16],
        "unknown_descriptors": [],
    }


def texture_atlas_catalog_stats(payload: bytes) -> dict[str, Any]:
    if len(payload) != TEXTURE_ATLAS_PIXELS:
        raise Lm2Error(
            f"texture atlas payload must be {TEXTURE_ATLAS_PIXELS} bytes, got {len(payload)}"
        )
    indices = set(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded indexed 256x256 texture atlas bytes; palette application is handled by the viewer render path.",
        "semantic_layout": "lba2_texture_atlas_indexed",
        "width": TEXTURE_ATLAS_SIZE,
        "height": TEXTURE_ATLAS_SIZE,
        "pixel_count": len(payload),
        "unique_palette_indices": len(indices),
        "palette_entry": {"hqr": RESS_ARCHIVE_NAME, "entry_index": PALETTE_CATALOG_ENTRY_INDEX},
        "unknown_descriptors": [],
    }


def indexed_image_catalog_stats(payload: bytes) -> dict[str, Any]:
    if len(payload) != TEXTURE_ATLAS_PIXELS:
        raise Lm2Error(
            f"indexed image payload must be {TEXTURE_ATLAS_PIXELS} bytes, got {len(payload)}"
        )
    indices = set(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded indexed 256x256 image bytes. Runtime role is not named yet; retain source entry identity for loader correlation.",
        "semantic_layout": "lba2_indexed_image_256",
        "width": TEXTURE_ATLAS_SIZE,
        "height": TEXTURE_ATLAS_SIZE,
        "pixel_count": len(payload),
        "unique_palette_indices": len(indices),
        "palette_entry": {"hqr": RESS_ARCHIVE_NAME, "entry_index": PALETTE_CATALOG_ENTRY_INDEX},
        "unknown_descriptors": [
            unknown_bytes_descriptor(
                payload,
                section="indexed_image_semantics",
                offset=0,
                length=0,
                confidence="parsed_unknown",
                note="Image dimensions and indexed pixels are decoded; the runtime purpose of this RESS image entry is not identified yet.",
            )
        ],
    }


def screen_pair_base(entry_index: int) -> int:
    return (entry_index // 2) * 2


def screen_pair_name(entry_index: int) -> str:
    pair_base = screen_pair_base(entry_index)
    return SCREEN_PCR_ENTRY_NAMES.get(pair_base, f"screen pair {pair_base}")


def screen_direct_code_references(entry_index: int, role: str) -> list[dict[str, Any]]:
    pair_base = screen_pair_base(entry_index)
    references = SCREEN_PCR_CODE_REFERENCES.get(pair_base, [])
    if role == "palette" and references:
        return [
            {
                **reference,
                "purpose": f"paired palette for {reference['purpose']}",
            }
            for reference in references
        ]
    return [dict(reference) for reference in references]


def screen_palette_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    stats = palette_catalog_stats(payload)
    pair_base = screen_pair_base(entry_index)
    direct_references = screen_direct_code_references(entry_index, "palette")
    stats.update(
        {
            "decode_note": "Decoded SCREEN.HQR 256-color RGB palette payload.",
            "semantic_layout": "screen_palette",
            "screen_name": screen_pair_name(entry_index),
            "screen_pair_base": pair_base,
            "paired_entry_index": pair_base,
            "direct_code_references": direct_references,
            "direct_reference_count": len(direct_references),
            "source_provenance": "Payload is 768 RGB bytes; classic zero-based SCREEN.HQR PCR constants identify odd PCR+1 palette slots.",
            "runtime_reference_status": "classic_pcr_palette_slot",
        }
    )
    return stats


def screen_indexed_image_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    if len(payload) != SCREEN_IMAGE_PIXELS:
        raise Lm2Error(
            f"screen image payload must be {SCREEN_IMAGE_PIXELS} bytes, got {len(payload)}"
        )
    pair_base = screen_pair_base(entry_index)
    direct_references = screen_direct_code_references(entry_index, "image")
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded SCREEN.HQR 640x480 indexed framebuffer payload.",
        "semantic_layout": "screen_indexed_image_640x480",
        "screen_name": screen_pair_name(entry_index),
        "screen_pair_base": pair_base,
        "width": SCREEN_IMAGE_WIDTH,
        "height": SCREEN_IMAGE_HEIGHT,
        "pixel_count": len(payload),
        "unique_palette_indices": len(set(payload)),
        "palette_entry": {"hqr": SCREEN_ARCHIVE_NAME, "entry_index": entry_index + 1},
        "direct_code_references": direct_references,
        "direct_reference_count": len(direct_references),
        "source_provenance": "Payload is 640x480 indexed screen bytes; classic zero-based SCREEN.HQR PCR constants identify even image slots.",
        "runtime_reference_status": "classic_pcr_image_slot",
        "unknown_descriptors": [],
    }


def screen_resource_catalog_stats(entry_index: int, payload: bytes) -> tuple[str, dict[str, Any]] | None:
    if len(payload) == PALETTE_BYTES:
        return "screen-palette", screen_palette_catalog_stats(entry_index, payload)
    if len(payload) == SCREEN_IMAGE_PIXELS:
        return "screen-indexed-image", screen_indexed_image_catalog_stats(entry_index, payload)
    return None


def holomap_entry_name(entry_index: int) -> str:
    return HOLOMAP_ENTRY_NAMES.get(entry_index, f"holomap entry {entry_index}")


def holomap_plan_variant_info(entry_index: int) -> dict[str, Any] | None:
    if entry_index < HOLOMAP_BEGIN_MAP_ENTRY_INDEX:
        return None
    relative = entry_index - HOLOMAP_BEGIN_MAP_ENTRY_INDEX
    if relative < 0 or relative >= HOLOMAP_PLAN_VARIANT_COUNT * 2:
        return None
    variant_index = relative // 2
    is_image = relative % 2 == 0
    selected_island = variant_index if variant_index < 12 else (0 if variant_index == 12 else 5)
    if variant_index == 12:
        condition = "ZoomedIsland == 0 and TEMPETE_FINIE"
    elif variant_index == 13:
        condition = "ZoomedIsland == 5 and FLAG_CELEBRATION"
    else:
        condition = f"ZoomedIsland == {variant_index}"
    image_entry = HOLOMAP_BEGIN_MAP_ENTRY_INDEX + (variant_index * 2)
    return {
        "variant_index": variant_index,
        "plan_name": HOLOMAP_PLAN_BASE_NAMES.get(variant_index, f"plan {variant_index}"),
        "selected_island": selected_island,
        "selection_condition": condition,
        "image_entry_index": image_entry,
        "params_entry_index": image_entry + 1,
        "entry_role": "image" if is_image else "params",
        "selection_rule": "HOLOPLAN.CPP InitHoloPlan chooses id = HQR_BEGIN_MAP + 2*ZoomedIsland, except island 0 after storm uses variant 12 and island 5 after celebration uses variant 13.",
        "render_path": "Load_HQR(HOLO_HQR_NAME, Log, id), CopyScreen(Log, Screen), then DrawListHoloPlan overlays sorted arrows/Twinsen/vehicles with BodyDisplay.",
    }


def holomap_globe_uv_catalog_stats(payload: bytes) -> dict[str, Any]:
    if len(payload) != HOLOMAP_GLOBE_UV_BYTES:
        raise Lm2Error(
            f"holomap globe UV map must be {HOLOMAP_GLOBE_UV_BYTES} bytes, got {len(payload)}"
        )
    values = struct.unpack(f"<{len(payload) // 2}H", payload)
    pairs = [
        {"u": values[index], "v": values[index + 1]}
        for index in range(0, min(len(values), 24), 2)
    ]
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded HOLOMAP globe texture coordinate mapping table used by DrawHolomap.",
        "semantic_layout": "holomap_globe_uv_map",
        "record_count": len(values) // 2,
        "record_bytes": 4,
        "sampled_records": pairs,
        "source_provenance": "HOLO.H HQR_COORMAPP_HMM and HOLOGLOB.CPP PtrMapping/DrawHolomap.",
        "unknown_descriptors": [],
    }


def holomap_globe_altitude_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    if len(payload) != HOLOMAP_GLOBE_ALTITUDE_BYTES:
        raise Lm2Error(
            f"holomap altitude map must be {HOLOMAP_GLOBE_ALTITUDE_BYTES} bytes, got {len(payload)}"
        )
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded HOLOMAP globe altitude bytes used by ComputeCoorGlobe.",
        "semantic_layout": "holomap_globe_altitude_map",
        "holomap_name": holomap_entry_name(entry_index),
        "width": 32,
        "height": 17,
        "pixel_count": len(payload),
        "unique_palette_indices": len(set(payload)),
        "source_provenance": "HOLO.H HQR_*_HMT constants and HOLOGLOB.CPP PtrAlt/ComputeCoorGlobe.",
        "unknown_descriptors": [],
    }


def holomap_globe_texture_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    if len(payload) != HOLOMAP_GLOBE_TEXTURE_PIXELS:
        raise Lm2Error(
            f"holomap texture map must be {HOLOMAP_GLOBE_TEXTURE_PIXELS} bytes, got {len(payload)}"
        )
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded HOLOMAP indexed globe texture map bytes.",
        "semantic_layout": "holomap_globe_texture_map",
        "holomap_name": holomap_entry_name(entry_index),
        "width": 256,
        "height": 256,
        "pixel_count": len(payload),
        "unique_palette_indices": len(set(payload)),
        "source_provenance": "HOLO.H HQR_*_HMG constants and HOLOGLOB.CPP PtrTextMap/DrawHolomap.",
        "unknown_descriptors": [],
    }


def parse_holomap_arrow_table(payload: bytes) -> list[dict[str, Any]]:
    if len(payload) % HOLOMAP_ARROW_RECORD_BYTES != 0:
        raise Lm2Error(
            f"holomap arrow table size {len(payload)} is not a multiple of {HOLOMAP_ARROW_RECORD_BYTES}"
        )
    records: list[dict[str, Any]] = []
    for index in range(len(payload) // HOLOMAP_ARROW_RECORD_BYTES):
        offset = index * HOLOMAP_ARROW_RECORD_BYTES
        x, y, z, alpha, beta, alt, message, objfix, flag_holo, planet, island = struct.unpack_from(
            "<iiiiiiibBBB", payload, offset
        )
        records.append(
            {
                "index": index,
                "x": x,
                "y": y,
                "z": z,
                "alpha": alpha,
                "beta": beta,
                "alt": alt,
                "message": message,
                "objfix": objfix,
                "flag_holo": flag_holo,
                "flags": {
                    "active": bool(flag_holo & 1),
                    "already_asked": bool(flag_holo & 2),
                    "exterior": bool(flag_holo & 4),
                },
                "planet": planet,
                "island": island,
            }
        )
    return records


def holomap_arrow_table_catalog_stats(payload: bytes) -> dict[str, Any]:
    records = parse_holomap_arrow_table(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded HOLOMAP T_ARROW table used for objectives, island/cube markers, and holomap flags.",
        "semantic_layout": "holomap_arrow_table",
        "record_count": len(records),
        "record_bytes": HOLOMAP_ARROW_RECORD_BYTES,
        "active_count": sum(1 for record in records if record["flag_holo"] & 1),
        "exterior_count": sum(1 for record in records if record["flag_holo"] & 4),
        "message_count": sum(1 for record in records if record["message"] >= 0),
        "unique_message_ids": sorted({record["message"] for record in records if record["message"] >= 0}),
        "objfix_field_note": "HOLO.H T_ARROW.ObjFix is present, but classic HOLOPLAN.CPP has DrawObjFix and its call commented out.",
        "records": records,
        "sampled_records": records[:24],
        "source_provenance": "HOLO.H T_ARROW and HOLOGLOB.CPP InitHoloMap/TabArrow.",
        "unknown_descriptors": [],
    }


def holomap_plan_image_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    if len(payload) != SCREEN_IMAGE_PIXELS:
        raise Lm2Error(
            f"holomap plan image payload must be {SCREEN_IMAGE_PIXELS} bytes, got {len(payload)}"
        )
    variant = holomap_plan_variant_info(entry_index) or {}
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded HOLOMAP plan-screen indexed framebuffer bytes.",
        "semantic_layout": "holomap_plan_image_640x480",
        "holomap_name": variant.get("plan_name") or holomap_entry_name(entry_index),
        "plan_variant": variant,
        "width": SCREEN_IMAGE_WIDTH,
        "height": SCREEN_IMAGE_HEIGHT,
        "pixel_count": len(payload),
        "unique_palette_indices": len(set(payload)),
        "paired_entry_index": entry_index + 1,
        "source_provenance": "HOLO.H HQR_BEGIN_MAP and HOLOPLAN.CPP Load_HQR(Log, id).",
        "unknown_descriptors": [],
    }


def holomap_plan_params_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    if len(payload) != HOLOMAP_PLAN_PARAM_BYTES:
        raise Lm2Error(
            f"holomap plan params payload must be {HOLOMAP_PLAN_PARAM_BYTES} bytes, got {len(payload)}"
        )
    fields = struct.unpack("<iiiiiiiii", payload)
    keys = ("orgmx", "orgmz", "offx", "offz", "alpha", "beta", "distance", "lalpha", "lbeta")
    variant = holomap_plan_variant_info(entry_index) or {}
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded HOLOMAP plan view parameter record loaded after each plan image.",
        "semantic_layout": "holomap_plan_view_params",
        "holomap_name": variant.get("plan_name") or holomap_entry_name(entry_index),
        "plan_variant": variant,
        "record_count": 1,
        "record_bytes": HOLOMAP_PLAN_PARAM_BYTES,
        "paired_entry_index": entry_index - 1,
        "fields": dict(zip(keys, fields)),
        "source_provenance": "HOLOPLAN.CPP InitHoloPlan loads id+1 and reads orgmx, orgmz, offx, offz, alpha, beta, distance, lalpha, lbeta.",
        "unknown_descriptors": [],
    }


def holomap_resource_catalog_stats(entry_index: int, payload: bytes) -> tuple[str, dict[str, Any]] | None:
    if entry_index == 0:
        return "holomap-globe-uv-map", holomap_globe_uv_catalog_stats(payload)
    if entry_index in {1, 3, 5, 7}:
        return "holomap-globe-altitude-map", holomap_globe_altitude_catalog_stats(entry_index, payload)
    if entry_index in {2, 4, 6, 8, 9}:
        return "holomap-globe-texture-map", holomap_globe_texture_catalog_stats(entry_index, payload)
    if entry_index == 12:
        return "holomap-arrow-table", holomap_arrow_table_catalog_stats(payload)
    if entry_index >= 18 and len(payload) == SCREEN_IMAGE_PIXELS:
        return "holomap-plan-image", holomap_plan_image_catalog_stats(entry_index, payload)
    if entry_index >= 18 and len(payload) == HOLOMAP_PLAN_PARAM_BYTES:
        return "holomap-plan-params", holomap_plan_params_catalog_stats(entry_index, payload)
    return None


def parse_bkg_header(payload: bytes) -> dict[str, Any]:
    if len(payload) != BKG_HEADER_BYTES:
        raise Lm2Error(
            f"LBA_BKG header must be {BKG_HEADER_BYTES} bytes, got {len(payload)}"
        )
    values = struct.unpack("<HHHHHHIIII", payload)
    keys = (
        "gri_start",
        "grm_start",
        "bll_start",
        "brk_start",
        "max_brk",
        "forbiden_brick",
        "max_size_gri",
        "max_size_bll",
        "max_size_brick_cube",
        "max_size_mask_brick_cube",
    )
    header = dict(zip(keys, values))
    if not (
        header["gri_start"]
        <= header["grm_start"]
        <= header["bll_start"]
        <= header["brk_start"]
    ):
        raise Lm2Error("LBA_BKG header range starts are not monotonic")
    header["cube_map_entry_index"] = header["brk_start"] + header["max_brk"]
    return header


def bkg_header_catalog_stats(payload: bytes) -> dict[str, Any]:
    header = parse_bkg_header(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded classic T_BKG_HEADER range table for LBA_BKG.HQR.",
        "semantic_layout": "bkg_header",
        "header": header,
        "fields": header,
        "source_provenance": "GRILLE.CPP InitBufferCube loads LBA_BKG.HQR entry 0 into T_BKG_HEADER.",
        "unknown_descriptors": [],
    }


def bkg_used_block_indices(used_block_bits: bytes) -> list[int]:
    indices: list[int] = []
    for block_id in range(1, 256):
        if used_block_bits[block_id >> 3] & (1 << (7 - (block_id & 7))):
            indices.append(block_id)
    return indices


def decode_bkg_grid_columns(payload: bytes, include_cells: bool = False) -> dict[str, Any]:
    offsets = struct.unpack_from(f"<{BKG_GRID_COLUMN_COUNT}H", payload, BKG_GRID_HEADER_BYTES)
    column_region_bytes = len(payload) - BKG_GRID_HEADER_BYTES
    run_type_counts: dict[str, int] = {}
    unique_block_refs: set[int] = set()
    block_ref_cell_slot_max: dict[int, int] = {}
    nonzero_cells = 0
    transparent_code_cells = 0
    active_columns = 0
    max_column_entities = 0
    max_column_stream_bytes = 0
    max_y = 0
    sampled_occupied_cells: list[dict[str, Any]] = []
    sampled_transparent_code_cells: list[dict[str, Any]] = []
    sampled_columns: list[dict[str, Any]] = []
    flat_block_refs: list[int] = []
    flat_cell_slots_or_codes: list[int] = []

    for column_index, offset in enumerate(offsets):
        ptr = BKG_GRID_HEADER_BYTES + offset
        if ptr >= len(payload):
            raise Lm2Error(f"BKG grid column {column_index} offset is out of range")
        start = ptr
        entity_count = payload[ptr]
        ptr += 1
        if entity_count == 0:
            raise Lm2Error(f"BKG grid column {column_index} has zero RLE entities")
        y = 0
        column_nonzero = 0
        column_blocks: set[int] = set()
        x = column_index % BKG_CUBE_SIZE_X
        z = column_index // BKG_CUBE_SIZE_X
        for entity_index in range(entity_count):
            if ptr >= len(payload):
                raise Lm2Error(f"BKG grid column {column_index} ended before entity {entity_index}")
            opcode = payload[ptr]
            ptr += 1
            run_length = (opcode & 0x3F) + 1
            run_type = (opcode >> 6) & 0x03
            if y + run_length > BKG_CUBE_SIZE_Y:
                raise Lm2Error(
                    f"BKG grid column {column_index} run {entity_index} exceeds cube height"
                )
            run_type_counts[str(run_type)] = run_type_counts.get(str(run_type), 0) + 1
            if run_type == 0:
                if include_cells:
                    flat_block_refs.extend([0] * run_length)
                    flat_cell_slots_or_codes.extend([0] * run_length)
                y += run_length
                continue
            if run_type == 2:
                if ptr + 2 > len(payload):
                    raise Lm2Error(f"BKG grid column {column_index} ended inside repeated block")
                word = payload[ptr : ptr + 2]
                ptr += 2
                words = [word] * run_length
            else:
                byte_length = run_length * 2
                if ptr + byte_length > len(payload):
                    raise Lm2Error(f"BKG grid column {column_index} ended inside literal blocks")
                words = [
                    payload[ptr + word_index * 2 : ptr + word_index * 2 + 2]
                    for word_index in range(run_length)
                ]
                ptr += byte_length
            for word in words:
                block_ref = word[0]
                cell_slot = word[1]
                if include_cells:
                    flat_block_refs.append(block_ref)
                    flat_cell_slots_or_codes.append(cell_slot)
                if block_ref:
                    unique_block_refs.add(block_ref)
                    column_blocks.add(block_ref)
                    block_ref_cell_slot_max[block_ref] = max(
                        block_ref_cell_slot_max.get(block_ref, -1), cell_slot
                    )
                    nonzero_cells += 1
                    column_nonzero += 1
                    max_y = max(max_y, y)
                    if len(sampled_occupied_cells) < 32:
                        sampled_occupied_cells.append(
                            {
                                "column": column_index,
                                "x": x,
                                "y": y,
                                "z": z,
                                "word": word[0] | (word[1] << 8),
                                "block_ref": block_ref,
                                "block_index": block_ref - 1,
                                "cell_slot": cell_slot,
                            }
                        )
                elif cell_slot:
                    transparent_code_cells += 1
                    if len(sampled_transparent_code_cells) < 16:
                        sampled_transparent_code_cells.append(
                            {
                                "column": column_index,
                                "x": x,
                                "y": y,
                                "z": z,
                                "code": cell_slot,
                            }
                        )
                y += 1
        if y != BKG_CUBE_SIZE_Y:
            raise Lm2Error(
                f"BKG grid column {column_index} decoded {y} cells, expected {BKG_CUBE_SIZE_Y}"
            )
        consumed = ptr - start
        max_column_entities = max(max_column_entities, entity_count)
        max_column_stream_bytes = max(max_column_stream_bytes, consumed)
        if column_nonzero:
            active_columns += 1
        if len(sampled_columns) < 16:
            sampled_columns.append(
                {
                    "index": column_index,
                    "x": x,
                    "z": z,
                    "offset": offset,
                    "entities": entity_count,
                    "encoded_bytes": consumed,
                    "nonzero_cells": column_nonzero,
                    "unique_block_refs": len(column_blocks),
                }
            )

    result = {
        "cube_dimensions": {
            "x": BKG_CUBE_SIZE_X,
            "y": BKG_CUBE_SIZE_Y,
            "z": BKG_CUBE_SIZE_Z,
        },
        "column_count": BKG_GRID_COLUMN_COUNT,
        "active_columns": active_columns,
        "empty_columns": BKG_GRID_COLUMN_COUNT - active_columns,
        "nonzero_cells": nonzero_cells,
        "transparent_code_cells": transparent_code_cells,
        "unique_block_ref_count": len(unique_block_refs),
        "unique_block_refs": sorted(unique_block_refs),
        "block_ref_cell_slot_max": {
            str(block_ref): slot
            for block_ref, slot in sorted(block_ref_cell_slot_max.items())
        },
        "max_y": max_y if nonzero_cells else 0,
        "run_type_counts": run_type_counts,
        "max_column_entities": max_column_entities,
        "max_column_stream_bytes": max_column_stream_bytes,
        "sampled_columns": sampled_columns,
        "sampled_occupied_cells": sampled_occupied_cells,
        "sampled_transparent_code_cells": sampled_transparent_code_cells,
        "source_provenance": "GRILLE_A.ASM DecompColonne expands each GRI column into 25 two-byte cube cells; byte 0 is the 1-based BLL block id, byte 1 is the block cell slot or transparent code when byte 0 is zero.",
        "encoded_region_bytes": column_region_bytes - BKG_GRID_OFFSET_TABLE_BYTES,
    }
    if include_cells:
        result["cell_order"] = "column-major: column = x + z*64, flat index = ((z*64 + x)*25) + y"
        result["flat_block_refs"] = flat_block_refs
        result["flat_cell_slots_or_codes"] = flat_cell_slots_or_codes
    return result


def bkg_grid_map_catalog_stats(
    entry_index: int, payload: bytes, header: dict[str, Any]
) -> dict[str, Any]:
    min_size = BKG_GRID_HEADER_BYTES + BKG_GRID_OFFSET_TABLE_BYTES
    if len(payload) < min_size:
        raise Lm2Error(f"BKG grid map is too small: {len(payload)} bytes")
    my_bll = payload[0]
    my_grm = payload[1]
    used_blocks = bkg_used_block_indices(payload[2:BKG_GRID_HEADER_BYTES])
    offsets = struct.unpack_from(f"<{BKG_GRID_COLUMN_COUNT}H", payload, BKG_GRID_HEADER_BYTES)
    column_region_bytes = len(payload) - BKG_GRID_HEADER_BYTES
    bad_offsets = [
        offset
        for offset in offsets
        if offset < BKG_GRID_OFFSET_TABLE_BYTES or offset > column_region_bytes
    ]
    if bad_offsets:
        raise Lm2Error(f"BKG grid map has invalid column offset {bad_offsets[0]}")
    composition = decode_bkg_grid_columns(payload)
    used_block_set = set(used_blocks)
    composition_block_set = set(composition["unique_block_refs"])
    referenced_without_used_bit = sorted(composition_block_set - used_block_set)
    used_without_column_ref = sorted(used_block_set - composition_block_set)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded BKG grid-map header, used-block bitset, 64x64 column offset table, and column composition streams.",
        "semantic_layout": "bkg_grid_map",
        "bkg_entry_role": "gri",
        "bkg_relative_index": entry_index - header["gri_start"],
        "fields": {
            "my_bll": my_bll,
            "my_grm": my_grm,
            "resolved_bll_entry": header["bll_start"] + my_bll,
            "resolved_grm_entry": header["grm_start"] + my_grm,
            "column_count": BKG_GRID_COLUMN_COUNT,
            "column_stream_bytes": column_region_bytes - BKG_GRID_OFFSET_TABLE_BYTES,
            "used_block_count": len(used_blocks),
            "min_column_offset": min(offsets),
            "max_column_offset": max(offsets),
            "active_columns": composition["active_columns"],
            "nonzero_cells": composition["nonzero_cells"],
            "transparent_code_cells": composition["transparent_code_cells"],
            "unique_column_block_refs": composition["unique_block_ref_count"],
            "referenced_without_used_bit_count": len(referenced_without_used_bit),
            "used_without_column_ref_count": len(used_without_column_ref),
        },
        "record_count": BKG_GRID_COLUMN_COUNT,
        "offset_table_bytes": BKG_GRID_OFFSET_TABLE_BYTES,
        "composition": composition,
        "sampled_records": [
            {"index": index, "offset": offsets[index]}
            for index in range(min(16, len(offsets)))
        ],
        "used_block_indices": used_blocks,
        "sampled_block_indices": used_blocks[:32],
        "referenced_block_refs_without_used_bit": referenced_without_used_bit[:32],
        "used_block_refs_without_column_refs": used_without_column_ref[:32],
        "sampled_occupied_cells": composition["sampled_occupied_cells"],
        "sampled_transparent_code_cells": composition["sampled_transparent_code_cells"],
        "source_provenance": "GRILLE.CPP InitGrille loads Gri_Start+cube and treats the first bytes as T_GRI_HEADER.",
        "unknown_descriptors": [],
    }


def decode_bkg_grm_fragment(payload: bytes, include_cells: bool = False) -> dict[str, Any]:
    if len(payload) < 3:
        raise Lm2Error(f"BKG GRM fragment is too small: {len(payload)} bytes")
    dx, dy, dz = payload[0], payload[1], payload[2]
    expected = 3 + dx * dy * dz * 2
    if len(payload) != expected:
        raise Lm2Error(
            f"BKG GRM fragment dimensions {dx}x{dy}x{dz} imply {expected} bytes, got {len(payload)}"
        )
    unique_block_refs: set[int] = set()
    block_ref_cell_slot_max: dict[int, int] = {}
    occupied_cells = 0
    transparent_code_cells = 0
    sampled_occupied_cells: list[dict[str, Any]] = []
    sampled_transparent_code_cells: list[dict[str, Any]] = []
    flat_block_refs: list[int] = []
    flat_cell_slots_or_codes: list[int] = []
    ptr = 3
    for local_z in range(dz):
        for local_x in range(dx):
            for local_y in range(dy):
                block_ref = payload[ptr]
                cell_slot = payload[ptr + 1]
                ptr += 2
                if include_cells:
                    flat_block_refs.append(block_ref)
                    flat_cell_slots_or_codes.append(cell_slot)
                if block_ref:
                    unique_block_refs.add(block_ref)
                    block_ref_cell_slot_max[block_ref] = max(
                        block_ref_cell_slot_max.get(block_ref, -1), cell_slot
                    )
                    occupied_cells += 1
                    if len(sampled_occupied_cells) < 24:
                        sampled_occupied_cells.append(
                            {
                                "local_x": local_x,
                                "local_y": local_y,
                                "local_z": local_z,
                                "word": block_ref | (cell_slot << 8),
                                "block_ref": block_ref,
                                "block_index": block_ref - 1,
                                "cell_slot": cell_slot,
                            }
                        )
                elif cell_slot:
                    transparent_code_cells += 1
                    if len(sampled_transparent_code_cells) < 12:
                        sampled_transparent_code_cells.append(
                            {
                                "local_x": local_x,
                                "local_y": local_y,
                                "local_z": local_z,
                                "code": cell_slot,
                            }
                        )

    result: dict[str, Any] = {
        "dimensions": {"x": dx, "y": dy, "z": dz},
        "cell_count": dx * dy * dz,
        "occupied_block_cells": occupied_cells,
        "transparent_code_cells": transparent_code_cells,
        "unique_block_ref_count": len(unique_block_refs),
        "unique_block_refs": sorted(unique_block_refs),
        "block_ref_cell_slot_max": {
            str(block_ref): slot
            for block_ref, slot in sorted(block_ref_cell_slot_max.items())
        },
        "sampled_occupied_cells": sampled_occupied_cells,
        "sampled_transparent_code_cells": sampled_transparent_code_cells,
        "cell_order": "fragment column-major: flat index = ((local_z*dx + local_x)*dy) + local_y",
        "source_provenance": "GRILLE.CPP IncrustGrm reads dx/dy/dz, then copies each z/x column's dy two-byte cells into BufCube at the GRM zone start.",
    }
    if include_cells:
        result["flat_block_refs"] = flat_block_refs
        result["flat_cell_slots_or_codes"] = flat_cell_slots_or_codes
    return result


def zone_cell_bounds(zone: dict[str, Any]) -> dict[str, int]:
    start = zone.get("start") or {}
    end = zone.get("end") or {}
    return {
        "x0": int(start.get("x", 0)) // BKG_WORLD_CELL_SIZE_XZ,
        "y0": int(start.get("y", 0)) // BKG_WORLD_CELL_SIZE_Y,
        "z0": int(start.get("z", 0)) // BKG_WORLD_CELL_SIZE_XZ,
        "x1": int(end.get("x", 0)) // BKG_WORLD_CELL_SIZE_XZ,
        "y1": int(end.get("y", 0)) // BKG_WORLD_CELL_SIZE_Y,
        "z1": int(end.get("z", 0)) // BKG_WORLD_CELL_SIZE_XZ,
    }


def apply_bkg_grm_fragment_to_composition(
    base_block_refs: list[int],
    base_cell_slots_or_codes: list[int],
    zone: dict[str, Any],
    fragment: dict[str, Any],
) -> dict[str, Any]:
    expected_cells = BKG_CUBE_SIZE_X * BKG_CUBE_SIZE_Y * BKG_CUBE_SIZE_Z
    if len(base_block_refs) != expected_cells or len(base_cell_slots_or_codes) != expected_cells:
        raise Lm2Error("BKG composition arrays do not match 64x25x64 cube dimensions")
    fragment_block_refs = fragment.get("flat_block_refs")
    fragment_slots = fragment.get("flat_cell_slots_or_codes")
    if not isinstance(fragment_block_refs, list) or not isinstance(fragment_slots, list):
        raise Lm2Error("GRM fragment must be decoded with include_cells=True before applying")
    dims = fragment.get("dimensions") or {}
    dx, dy, dz = int(dims.get("x", 0)), int(dims.get("y", 0)), int(dims.get("z", 0))
    if len(fragment_block_refs) != dx * dy * dz or len(fragment_slots) != dx * dy * dz:
        raise Lm2Error("GRM fragment cell arrays do not match decoded dimensions")
    bounds = zone_cell_bounds(zone)
    x0, y0, z0 = bounds["x0"], bounds["y0"], bounds["z0"]
    if x0 < 0 or y0 < 0 or z0 < 0 or x0 + dx > BKG_CUBE_SIZE_X or z0 + dz > BKG_CUBE_SIZE_Z:
        raise Lm2Error(
            f"GRM fragment {dx}x{dy}x{dz} at {x0},{y0},{z0} exceeds 64x25x64 cube x/z bounds"
        )

    block_refs = list(base_block_refs)
    slots = list(base_cell_slots_or_codes)
    changed_cells = 0
    occupied_cells = 0
    transparent_code_cells = 0
    unique_block_refs: set[int] = set()
    for local_z in range(dz):
        for local_x in range(dx):
            for local_y in range(dy):
                fragment_index = ((local_z * dx) + local_x) * dy + local_y
                target_index = (((z0 + local_z) * BKG_CUBE_SIZE_X + (x0 + local_x)) * BKG_CUBE_SIZE_Y) + (y0 + local_y)
                if target_index < 0 or target_index >= expected_cells:
                    raise Lm2Error("GRM fragment linear write exceeds the 64x25x64 cube buffer")
                block_ref = int(fragment_block_refs[fragment_index])
                cell_slot = int(fragment_slots[fragment_index])
                if block_refs[target_index] != block_ref or slots[target_index] != cell_slot:
                    changed_cells += 1
                block_refs[target_index] = block_ref
                slots[target_index] = cell_slot
                if block_ref:
                    occupied_cells += 1
                    unique_block_refs.add(block_ref)
                elif cell_slot:
                    transparent_code_cells += 1

    return {
        "flat_block_refs": block_refs,
        "flat_cell_slots_or_codes": slots,
        "applied_cell_count": dx * dy * dz,
        "changed_cells": changed_cells,
        "occupied_block_cells": occupied_cells,
        "transparent_code_cells": transparent_code_cells,
        "unique_block_refs": sorted(unique_block_refs),
        "target_cell_bounds": {
            "x0": x0,
            "y0": y0,
            "z0": z0,
            "x1_exclusive": x0 + dx,
            "y1_exclusive": y0 + dy,
            "z1_exclusive": z0 + dz,
        },
        "column_y_overflow_cells": max(0, y0 + dy - BKG_CUBE_SIZE_Y) * dx * dz,
        "source_provenance": "Matches GRILLE.CPP IncrustGrm ON path; DesIncrustGrm OFF restores the same rectangular span from the source GRI columns.",
    }


def bkg_grm_fragment_catalog_stats(
    entry_index: int, payload: bytes, header: dict[str, Any]
) -> dict[str, Any]:
    fragment = decode_bkg_grm_fragment(payload)
    dx, dy, dz = (
        fragment["dimensions"]["x"],
        fragment["dimensions"]["y"],
        fragment["dimensions"]["z"],
    )
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded BKG GRM fragment dimensions and packed cube-cell payload.",
        "semantic_layout": "bkg_grm_fragment",
        "bkg_entry_role": "grm",
        "bkg_relative_index": entry_index - header["grm_start"],
        "width": dx,
        "height": dy,
        "depth": dz,
        "record_count": dx * dy * dz,
        "record_bytes": 2,
        "fields": {
            "dx": dx,
            "dy": dy,
            "dz": dz,
            "occupied_block_cells": fragment["occupied_block_cells"],
            "transparent_code_cells": fragment["transparent_code_cells"],
            "unique_block_refs": fragment["unique_block_ref_count"],
        },
        "composition": fragment,
        "sampled_occupied_cells": fragment["sampled_occupied_cells"],
        "sampled_transparent_code_cells": fragment["sampled_transparent_code_cells"],
        "source_provenance": "GRILLE.CPP IncrustGrm loads Grm_Start+My_Grm+zone.Info0 and copies dx*dy*dz S16 cells.",
        "unknown_descriptors": [],
    }


def parse_bkg_block_table(
    payload: bytes, header: dict[str, Any], include_cells: bool = False
) -> tuple[list[int], list[dict[str, Any]], dict[str, Any]]:
    if len(payload) < 4:
        raise Lm2Error("BKG block table is too small")
    first_offset = struct.unpack_from("<I", payload, 0)[0]
    if first_offset < 4 or first_offset % 4 != 0 or first_offset > len(payload):
        raise Lm2Error(f"invalid BKG block offset table size: {first_offset}")
    block_count = first_offset // 4
    offsets = list(struct.unpack_from(f"<{block_count}I", payload, 0))
    if offsets[0] != first_offset:
        raise Lm2Error("BKG block table first offset does not match table size")
    if any(offset < first_offset or offset > len(payload) for offset in offsets):
        raise Lm2Error("BKG block table contains an out-of-range block offset")
    if any(offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)):
        raise Lm2Error("BKG block table offsets are not monotonic")
    blocks: list[dict[str, Any]] = []
    unique_brick_refs: set[int] = set()
    invalid_brick_refs: set[int] = set()
    forbidden_refs = 0
    nonzero_cells = 0
    sampled_cell_refs: list[dict[str, Any]] = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(payload)
        block = payload[start:end]
        if len(block) < 3:
            raise Lm2Error(f"BKG block {index} is too small")
        dx, dy, dz = block[0], block[1], block[2]
        cell_count = dx * dy * dz
        expected = 3 + cell_count * BKG_BLOCK_RECORD_BYTES
        if len(block) != expected:
            raise Lm2Error(
                f"BKG block {index} dimensions {dx}x{dy}x{dz} imply {expected} bytes, got {len(block)}"
            )
        brick_refs: list[int] = []
        code_counts: dict[str, int] = {}
        collision_counts: dict[str, int] = {}
        block_cell_samples: list[dict[str, Any]] = []
        for cell in range(cell_count):
            record_offset = 3 + cell * BKG_BLOCK_RECORD_BYTES
            collision = block[record_offset]
            code_byte = block[record_offset + 1]
            brick_ref = struct.unpack_from("<H", block, record_offset + 2)[0]
            code = code_byte >> 4
            x = cell % dx if dx else 0
            z = (cell // dx) % dz if dx and dz else 0
            y = cell // (dx * dz) if dx and dz else 0
            if brick_ref:
                brick_refs.append(brick_ref)
                unique_brick_refs.add(brick_ref)
                nonzero_cells += 1
                resolved_brk_index = brick_ref - 1
                if resolved_brk_index < 0 or resolved_brk_index >= header["max_brk"]:
                    invalid_brick_refs.add(brick_ref)
                if resolved_brk_index == header["forbiden_brick"]:
                    forbidden_refs += 1
                cell_ref = {
                    "block": index,
                    "cell": cell,
                    "x": x,
                    "y": y,
                    "z": z,
                    "collision": collision,
                    "code": code,
                    "code_raw": code_byte,
                    "brick_ref": brick_ref,
                    "resolved_brk_index": resolved_brk_index,
                    "resolved_brk_entry": header["brk_start"] + resolved_brk_index,
                    "is_forbidden_brick": resolved_brk_index == header["forbiden_brick"],
                }
                if len(block_cell_samples) < 6:
                    block_cell_samples.append(cell_ref)
                if len(sampled_cell_refs) < 24:
                    sampled_cell_refs.append(cell_ref)
            code_key = str(code)
            code_counts[code_key] = code_counts.get(code_key, 0) + 1
            collision_key = str(collision)
            collision_counts[collision_key] = collision_counts.get(collision_key, 0) + 1
        block_record = {
            "index": index,
            "offset": start,
            "byte_length": len(block),
            "dx": dx,
            "dy": dy,
            "dz": dz,
            "cell_count": cell_count,
            "nonzero_brick_refs": len(brick_refs),
            "max_brick_ref": max(brick_refs) if brick_refs else 0,
            "unique_brick_refs": len(set(brick_refs)),
            "sampled_cell_refs": block_cell_samples,
            "code_counts": code_counts,
            "collision_counts": collision_counts,
        }
        if include_cells:
            cells: list[dict[str, Any]] = []
            for cell in range(cell_count):
                record_offset = 3 + cell * BKG_BLOCK_RECORD_BYTES
                collision = block[record_offset]
                code_byte = block[record_offset + 1]
                brick_ref = struct.unpack_from("<H", block, record_offset + 2)[0]
                cells.append(
                    {
                        "collision": collision,
                        "code": code_byte >> 4,
                        "code_raw": code_byte,
                        "brick_ref": brick_ref,
                    }
                )
            block_record["cells"] = cells
        blocks.append(block_record)
    summary = {
        "unique_brick_ref_count": len(unique_brick_refs),
        "nonzero_cell_refs": nonzero_cells,
        "invalid_brick_ref_count": len(invalid_brick_refs),
        "forbidden_brick_ref_count": forbidden_refs,
        "sampled_cell_refs": sampled_cell_refs,
        "min_brick_ref": min(unique_brick_refs) if unique_brick_refs else 0,
        "max_brick_ref": max(unique_brick_refs) if unique_brick_refs else 0,
    }
    return offsets, blocks, summary


def bkg_block_table_catalog_stats(
    entry_index: int, payload: bytes, header: dict[str, Any]
) -> dict[str, Any]:
    offsets, blocks, block_summary = parse_bkg_block_table(payload, header)
    fields = {
        "block_count": len(blocks),
        "max_cell_count": max((block["cell_count"] for block in blocks), default=0),
        "max_brick_ref": max((block["max_brick_ref"] for block in blocks), default=0),
        "unique_brick_ref_count": block_summary["unique_brick_ref_count"],
        "nonzero_cell_refs": block_summary["nonzero_cell_refs"],
        "invalid_brick_ref_count": block_summary["invalid_brick_ref_count"],
        "forbidden_brick_ref_count": block_summary["forbidden_brick_ref_count"],
    }
    if block_summary["min_brick_ref"]:
        fields["min_resolved_brk_entry"] = header["brk_start"] + block_summary["min_brick_ref"] - 1
    if block_summary["max_brick_ref"]:
        fields["max_resolved_brk_entry"] = header["brk_start"] + block_summary["max_brick_ref"] - 1

    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded BKG block table offsets and block cell records.",
        "semantic_layout": "bkg_block_table",
        "bkg_entry_role": "bll",
        "bkg_relative_index": entry_index - header["bll_start"],
        "record_count": len(blocks),
        "offset_table_bytes": len(offsets) * 4,
        "fields": fields,
        "sampled_records": blocks[:16],
        "sampled_cell_refs": block_summary["sampled_cell_refs"],
        "source_provenance": "GRILLE.CPP LoadUsedBrick reads original BLL brick refs, loads Brk_Start+brick_ref-1, then AffBrickBlock draws the remapped local ref with AffGraph.",
        "unknown_descriptors": [],
    }


def parse_bkg_brick_graphic(payload: bytes) -> dict[str, Any]:
    if len(payload) < BKG_GRAPH_HEADER_BYTES:
        raise Lm2Error(f"BKG BRK graphic is too small: {len(payload)} bytes")
    width = payload[0]
    height = payload[1]
    offset_x = struct.unpack_from("<b", payload, 2)[0]
    offset_y = struct.unpack_from("<b", payload, 3)[0]
    if width <= 0 or height <= 0:
        raise Lm2Error(f"BKG BRK graphic has invalid dimensions: {width}x{height}")

    pixels = [0] * (width * height)
    opaque_mask = [False] * (width * height)
    ptr = BKG_GRAPH_HEADER_BYTES
    run_type_counts: dict[str, int] = {}
    row_run_counts: list[int] = []
    for y in range(height):
        if ptr >= len(payload):
            raise Lm2Error(f"BKG BRK graphic ended before row {y} run count")
        run_count = payload[ptr]
        ptr += 1
        row_run_counts.append(run_count)
        x = 0
        for run_index in range(run_count):
            if ptr >= len(payload):
                raise Lm2Error(f"BKG BRK graphic ended before row {y} run {run_index}")
            run_spec = payload[ptr]
            ptr += 1
            run_length = (run_spec & 0x3F) + 1
            run_type = (run_spec >> 6) & 0x03
            if x + run_length > width:
                raise Lm2Error(
                    f"BKG BRK graphic row {y} run {run_index} exceeds width {width}"
                )
            run_type_counts[str(run_type)] = run_type_counts.get(str(run_type), 0) + 1
            if run_type == 0:
                x += run_length
                continue
            if run_type == 2:
                if ptr >= len(payload):
                    raise Lm2Error(f"BKG BRK graphic ended before fill color at row {y}")
                color = payload[ptr]
                ptr += 1
                for _ in range(run_length):
                    pixel_index = (y * width) + x
                    pixels[pixel_index] = color
                    opaque_mask[pixel_index] = True
                    x += 1
                continue
            if ptr + run_length > len(payload):
                raise Lm2Error(f"BKG BRK graphic ended inside literal run at row {y}")
            for _ in range(run_length):
                pixel_index = (y * width) + x
                pixels[pixel_index] = payload[ptr]
                opaque_mask[pixel_index] = True
                ptr += 1
                x += 1
        if x != width:
            raise Lm2Error(
                f"BKG BRK graphic row {y} decoded to {x} pixels, expected {width}"
            )

    colors = sorted({pixel for pixel, opaque in zip(pixels, opaque_mask) if opaque})
    return {
        "format": "bkg_affgraph",
        "width": width,
        "height": height,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "pixels": pixels,
        "opaque_mask": opaque_mask,
        "encoded_bytes_consumed": ptr,
        "trailing_bytes": len(payload) - ptr,
        "opaque_pixels": sum(1 for opaque in opaque_mask if opaque),
        "transparent_pixels": sum(1 for opaque in opaque_mask if not opaque),
        "color_count": len(colors),
        "palette_indices": colors,
        "run_type_counts": run_type_counts,
        "row_run_counts": row_run_counts,
        "max_row_run_count": max(row_run_counts, default=0),
    }


def bkg_brick_graphic_catalog_stats(
    entry_index: int, payload: bytes, header: dict[str, Any]
) -> dict[str, Any]:
    brick = parse_bkg_brick_graphic(payload)
    descriptors: list[dict[str, Any]] = []
    if brick["trailing_bytes"]:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="trailing_bytes",
                offset=brick["encoded_bytes_consumed"],
                length=brick["trailing_bytes"],
                confidence="medium",
                note="Bytes after the decoded AffGraph BRK command stream.",
            )
        )
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded BRK AffGraph command stream used by background block cells.",
        "semantic_layout": "bkg_brick_graphic",
        "bkg_entry_role": "brk",
        "bkg_relative_index": entry_index - header["brk_start"],
        "preview_hex": payload[:32].hex(),
        "format": brick["format"],
        "width": brick["width"],
        "height": brick["height"],
        "offset_x": brick["offset_x"],
        "offset_y": brick["offset_y"],
        "encoded_bytes_consumed": brick["encoded_bytes_consumed"],
        "trailing_bytes": brick["trailing_bytes"],
        "opaque_pixels": brick["opaque_pixels"],
        "transparent_pixels": brick["transparent_pixels"],
        "color_count": brick["color_count"],
        "palette_indices": brick["palette_indices"],
        "run_type_counts": brick["run_type_counts"],
        "max_row_run_count": brick["max_row_run_count"],
        "fields": {
            "width": brick["width"],
            "height": brick["height"],
            "hot_x": brick["offset_x"],
            "hot_y": brick["offset_y"],
            "encoded_bytes": len(payload),
            "encoded_bytes_consumed": brick["encoded_bytes_consumed"],
            "trailing_bytes": brick["trailing_bytes"],
        },
        "source_provenance": "GRILLE.CPP LoadUsedBrick loads selected Brk_Start+brick entries into BufferBrick; GRILLE.CPP AffBrickBlock calls SVGA GRAPH.ASM AffGraph on the selected graph.",
        "unknown_descriptors": descriptors,
    }


def bkg_cube_map_catalog_stats(
    payload: bytes,
    header: dict[str, Any],
    grid_lookup: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected = BKG_CUBE_MAP_RECORD_COUNT * BKG_CUBE_MAP_RECORD_BYTES
    if len(payload) != expected:
        raise Lm2Error(f"BKG cube map must be {expected} bytes, got {len(payload)}")
    records = []
    linked_count = 0
    missing_grid_ids: list[int] = []
    for index in range(BKG_CUBE_MAP_RECORD_COUNT):
        num = payload[index * 2 + 1]
        resolved_gri_entry = header["gri_start"] + num
        record: dict[str, Any] = {
            "index": index,
            "type": payload[index * 2],
            "num": num,
            "resolved_gri_entry": resolved_gri_entry,
        }
        grid = grid_lookup.get(resolved_gri_entry) if grid_lookup is not None else None
        if grid is not None:
            record.update(
                {
                    "resolved_bll_entry": grid["resolved_bll_entry"],
                    "resolved_grm_entry": grid["resolved_grm_entry"],
                    "used_block_count": grid["used_block_count"],
                }
            )
            linked_count += 1
        elif grid_lookup is not None:
            missing_grid_ids.append(resolved_gri_entry)
        records.append(record)
    type_counts: dict[str, int] = {}
    for record in records:
        key = str(record["type"])
        type_counts[key] = type_counts.get(key, 0) + 1
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded T_TABALLCUBE cube indirection records.",
        "semantic_layout": "bkg_cube_map",
        "bkg_entry_role": "taballcube",
        "record_count": len(records),
        "record_bytes": BKG_CUBE_MAP_RECORD_BYTES,
        "fields": {
            "cube_count": len(records),
            "max_num": max(record["num"] for record in records),
            "linked_grid_records": linked_count,
            "missing_grid_records": len(missing_grid_ids),
        },
        "type_counts": type_counts,
        "records": records,
        "sampled_records": records[:32],
        "missing_grid_entries": sorted(set(missing_grid_ids))[:32],
        "source_provenance": "GRILLE.CPP InitBufferCube loads Brk_Start+Max_Brk into TabAllCube; InitGrille uses TabAllCube[numcube].Num.",
        "unknown_descriptors": [],
    }


def bkg_resource_catalog_stats(
    entry_index: int,
    payload: bytes,
    header: dict[str, Any],
    grid_lookup: dict[int, dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    if entry_index == 0:
        return "bkg-header", bkg_header_catalog_stats(payload)
    if header["gri_start"] <= entry_index < header["grm_start"]:
        return "bkg-grid-map", bkg_grid_map_catalog_stats(entry_index, payload, header)
    if header["grm_start"] <= entry_index < header["bll_start"]:
        return "bkg-grm-fragment", bkg_grm_fragment_catalog_stats(entry_index, payload, header)
    if header["bll_start"] <= entry_index < header["brk_start"]:
        return "bkg-block-table", bkg_block_table_catalog_stats(entry_index, payload, header)
    if header["brk_start"] <= entry_index < header["cube_map_entry_index"]:
        return "bkg-brick-graphic", bkg_brick_graphic_catalog_stats(entry_index, payload, header)
    if entry_index == header["cube_map_entry_index"]:
        return "bkg-cube-map", bkg_cube_map_catalog_stats(payload, header, grid_lookup)
    return None


def text_bank_metadata(entry_index: int) -> dict[str, Any]:
    group = entry_index // TEXT_ENTRIES_PER_LANGUAGE
    within_group = entry_index % TEXT_ENTRIES_PER_LANGUAGE
    file_index = within_group // 2
    paired_entry = entry_index + 1 if entry_index % 2 == 0 else entry_index - 1
    return {
        "language_index": group,
        "language": TEXT_LANGUAGE_NAMES[group] if group < len(TEXT_LANGUAGE_NAMES) else f"language {group}",
        "text_file_index": file_index,
        "text_file_name": TEXT_FILE_NAMES[file_index] if file_index < len(TEXT_FILE_NAMES) else f"file {file_index}",
        "paired_entry_index": paired_entry,
    }


def text_order_table_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    if len(payload) == 0 or len(payload) % 2 != 0:
        raise Lm2Error(f"TEXT order table must be a non-empty U16 table, got {len(payload)} bytes")
    message_ids = list(struct.unpack(f"<{len(payload) // 2}H", payload))
    metadata = text_bank_metadata(entry_index)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded TEXT.HQR BufOrder table: runtime message IDs searched by FindText before indexing the paired text bank.",
        "semantic_layout": "text_order_table",
        **metadata,
        "record_count": len(message_ids),
        "record_bytes": 2,
        "message_ids": message_ids,
        "fields": {
            "min_message_id": min(message_ids),
            "max_message_id": max(message_ids),
            "unique_message_ids": len(set(message_ids)),
        },
        "sampled_message_ids": message_ids[:32],
        "source_provenance": "MESSAGE.CPP InitDial loads file*2 into BufOrder; FindText scans BufOrder for the requested message id.",
        "unknown_descriptors": [],
    }


def text_preview(record_body: bytes) -> str:
    text = record_body.replace(b"\x01", b"\n").split(b"\x00", 1)[0]
    return text[:160].decode("cp850", errors="replace")


def parse_text_payload_bank(payload: bytes) -> tuple[list[int], list[dict[str, Any]]]:
    if len(payload) < 4:
        raise Lm2Error("TEXT payload bank is too small")
    first_offset = struct.unpack_from("<H", payload, 0)[0]
    if first_offset < 4 or first_offset % 2 != 0 or first_offset > len(payload):
        raise Lm2Error(f"invalid TEXT payload offset table size: {first_offset}")
    offsets = list(struct.unpack_from(f"<{first_offset // 2}H", payload, 0))
    if offsets[0] != first_offset:
        raise Lm2Error("TEXT payload first offset does not match offset table size")
    if offsets[-1] > len(payload):
        raise Lm2Error("TEXT payload final offset is outside the bank")
    if any(offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)):
        raise Lm2Error("TEXT payload offsets are not monotonic")
    records: list[dict[str, Any]] = []
    for index in range(len(offsets) - 1):
        start = offsets[index]
        end = offsets[index + 1]
        record = payload[start:end]
        if not record:
            raise Lm2Error(f"TEXT record {index} is empty")
        body = record[1:]
        records.append(
            {
                "index": index,
                "offset": start,
                "byte_length": len(record),
                "flag": record[0],
                "text_bytes": max(0, len(record) - 1),
                "preview": text_preview(body),
                "terminates_with_nul": bool(body.endswith(b"\x00")),
                "page_break_count": body.count(1),
            }
        )
    return offsets, records


def text_payload_bank_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    offsets, records = parse_text_payload_bank(payload)
    metadata = text_bank_metadata(entry_index)
    flag_counts: dict[str, int] = {}
    for record in records:
        key = str(record["flag"])
        flag_counts[key] = flag_counts.get(key, 0) + 1
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded TEXT.HQR BufText bank: U16 offset table plus flagged dialog byte strings.",
        "semantic_layout": "text_payload_bank",
        **metadata,
        "record_count": len(records),
        "offset_table_bytes": len(offsets) * 2,
        "preview_codepage": "cp850",
        "fields": {
            "first_text_offset": offsets[0],
            "last_text_offset": offsets[-1],
            "max_record_bytes": max((record["byte_length"] for record in records), default=0),
            "nul_terminated_records": sum(1 for record in records if record["terminates_with_nul"]),
            "page_break_markers": sum(record["page_break_count"] for record in records),
        },
        "type_counts": flag_counts,
        "records": records,
        "sampled_records": records[:16],
        "source_provenance": "MESSAGE.CPP InitDial loads file*2+1 into BufText; GetText reads offsets from BufText, consumes the first byte as FlagDial, then exposes PtText/SizeText.",
        "unknown_descriptors": [],
    }


def text_resource_catalog_stats(entry_index: int, payload: bytes) -> tuple[str, dict[str, Any]] | None:
    if entry_index % 2 == 0:
        return "text-order-table", text_order_table_catalog_stats(entry_index, payload)
    return "text-payload-bank", text_payload_bank_catalog_stats(entry_index, payload)


def text_resource_catalog_label(entry_index: int, entry_type: str, stats: dict[str, Any]) -> str:
    language = stats.get("language", "language")
    text_file = stats.get("text_file_name", stats.get("text_file_index", "-"))
    if entry_type == "text-order-table":
        return f"Text order table {language}/{text_file} ({TEXT_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "text-payload-bank":
        return f"Text payload bank {language}/{text_file} ({TEXT_ARCHIVE_NAME}:{entry_index})"
    return f"{TEXT_ARCHIVE_NAME} resource {entry_index}"


def parse_ress_offset_record_table(payload: bytes) -> list[dict[str, Any]]:
    if len(payload) < 8:
        raise Lm2Error("RESS offset table payload is too small")
    table_end = struct.unpack_from("<I", payload, 0)[0]
    if table_end < 8 or table_end > len(payload) or table_end % 4 != 0:
        raise Lm2Error(f"invalid RESS offset table end: 0x{table_end:x}")
    offsets = [
        struct.unpack_from("<I", payload, offset)[0]
        for offset in range(0, table_end, 4)
    ]
    if offsets[0] != table_end:
        raise Lm2Error("RESS offset table first offset does not match table size")
    if offsets[-1] != len(payload):
        raise Lm2Error("RESS offset table last offset does not match payload size")
    previous_end = table_end
    records: list[dict[str, Any]] = []
    for index, start in enumerate(offsets[:-1]):
        end = offsets[index + 1]
        if start < table_end or start > end or end > len(payload) or start < previous_end:
            raise Lm2Error(f"invalid RESS offset table range at record {index}")
        record = payload[start:end]
        records.append(
            {
                "index": index,
                "offset": start,
                "byte_length": len(record),
                "sha256": hashlib.sha256(record).hexdigest(),
                "preview_hex": record[:32].hex(),
            }
        )
        previous_end = end
    return records


def apply_ress_runtime_table_info(
    stats: dict[str, Any], entry_index: int
) -> dict[str, Any]:
    info = RESS_RUNTIME_TABLES.get(entry_index)
    if not info:
        return stats
    stats.update(info)
    return stats


def ress_offset_table_catalog_stats(payload: bytes, entry_index: int) -> dict[str, Any]:
    records = parse_ress_offset_record_table(payload)
    lengths: dict[str, int] = {}
    for record in records:
        key = str(record["byte_length"])
        lengths[key] = lengths.get(key, 0) + 1
    stats = {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded RESS offset table envelope with variable-length records. Table identity is known where classic runtime loaders name the entry; per-record fields remain raw evidence.",
        "semantic_layout": "ress_offset_record_table",
        "record_count": len(records),
        "offset_table_bytes": (len(records) + 1) * 4,
        "record_length_counts": lengths,
        "sampled_records": records[:24],
        "unknown_descriptors": [
            unknown_bytes_descriptor(
                payload,
                section="ress_offset_record_semantics",
                offset=0,
                length=len(payload),
                confidence="parsed_unknown",
                note="Offset table boundaries and runtime table identity are decoded where applicable; per-record field semantics are not identified yet.",
            )
        ],
    }
    return apply_ress_runtime_table_info(stats, entry_index)


def parse_ress_fixed_s16_table(payload: bytes) -> list[dict[str, Any]]:
    if len(payload) == 0 or len(payload) % RESS_FIXED_S16_RECORD_BYTES != 0:
        raise Lm2Error(
            f"RESS fixed s16 table must be a non-empty multiple of {RESS_FIXED_S16_RECORD_BYTES} bytes"
        )
    records: list[dict[str, Any]] = []
    for index, offset in enumerate(range(0, len(payload), RESS_FIXED_S16_RECORD_BYTES)):
        values = list(struct.unpack_from("<hhhhhhhh", payload, offset))
        records.append({"index": index, "offset": offset, "values": values})
    return records


def ress_fixed_s16_table_catalog_stats(payload: bytes, entry_index: int) -> dict[str, Any]:
    records = parse_ress_fixed_s16_table(payload)
    stats = {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded fixed-width RESS table as eight signed 16-bit values per record. The classic loader names the table; field-level meaning remains unknown.",
        "semantic_layout": "ress_fixed_s16x8_table",
        "record_count": len(records),
        "record_bytes": RESS_FIXED_S16_RECORD_BYTES,
        "sampled_records": records[:24],
        "unknown_descriptors": [
            unknown_bytes_descriptor(
                payload,
                section="ress_fixed_s16x8_semantics",
                offset=0,
                length=len(payload),
                confidence="parsed_unknown",
                note="Fixed signed-word record structure and runtime table identity are decoded; field names are not identified yet.",
            )
        ],
    }
    return apply_ress_runtime_table_info(stats, entry_index)


def parse_ress_ext_size_info(payload: bytes) -> dict[str, int]:
    if len(payload) != 16:
        raise Lm2Error(f"RESS_EXT_SIZE_INFO must be 16 bytes, got {len(payload)}")
    (
        max_size_list_decors,
        max_size_body_decors,
        max_size_tex_def,
        max_total_body_decors,
    ) = struct.unpack("<iiii", payload)
    return {
        "max_size_list_decors": max_size_list_decors,
        "max_size_body_decors": max_size_body_decors,
        "max_size_tex_def": max_size_tex_def,
        "max_total_body_decors": max_total_body_decors,
    }


def ress_ext_size_info_catalog_stats(payload: bytes) -> dict[str, Any]:
    fields = parse_ress_ext_size_info(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded classic SizeInfo memory sizing record used by AdjustHQRMem for exterior-island buffers.",
        "semantic_layout": "ress_ext_size_info",
        **fields,
        "unknown_descriptors": [],
    }


def parse_xpl_palette_bundle(payload: bytes) -> dict[str, Any]:
    if len(payload) < 44:
        raise Lm2Error(f"XPL palette bundle header needs 44 bytes, got {len(payload)}")
    fields = struct.unpack_from("<iiiiiiiiiii", payload)
    header = {
        "version": fields[0],
        "offset_palette": fields[1],
        "offset_shade": fields[2],
        "offset_fog": fields[3],
        "offset_transparency": fields[4],
        "shade_start_percent": fields[5],
        "shade_normal_level": fields[6],
        "shade_end_percent": fields[7],
        "fog_color": fields[8],
        "transparency_start_percent": fields[9],
        "transparency_end_percent": fields[10],
    }
    for key in ("offset_palette", "offset_fog", "offset_transparency"):
        offset = header[key]
        if offset < 0 or offset >= len(payload):
            raise Lm2Error(f"XPL {key} points outside payload: 0x{offset:x}")
    if header["offset_palette"] + PALETTE_BYTES > len(payload):
        raise Lm2Error("XPL palette offset does not leave room for 768 palette bytes")
    palette_bytes = payload[header["offset_palette"] : header["offset_palette"] + PALETTE_BYTES]
    return {
        "header": header,
        "sample_colors": parse_palette_payload(palette_bytes)[:16],
    }


def xpl_palette_bundle_catalog_stats(entry_index: int, payload: bytes) -> dict[str, Any]:
    parsed = parse_xpl_palette_bundle(payload)
    if entry_index in RESS_XPL_COMMON_H_ENTRY_INDICES:
        provenance = "classic COMMON.H RESS_XPL constant"
        runtime_reference_status = "referenced_by_classic_palette_selection"
    elif entry_index in RESS_XPL_HQD_ONLY_ENTRY_INDICES:
        provenance = "lba2_ress.hqd labels this entry as shading palettes; classic COMMON.H comments this slot empty"
        runtime_reference_status = "no_classic_common_h_constant"
    else:
        provenance = "XPL-shaped RESS payload"
        runtime_reference_status = "unverified"
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded classic XPL ambience palette bundle header and primary palette sample.",
        "semantic_layout": "xpl_palette_bundle",
        "xpl_name": RESS_XPL_ENTRY_NAMES.get(entry_index, f"XPL{entry_index}"),
        "source_provenance": provenance,
        "runtime_reference_status": runtime_reference_status,
        "header": parsed["header"],
        "color_count": 256,
        "sample_colors": parsed["sample_colors"],
        "unknown_descriptors": [
            unknown_bytes_descriptor(
                payload,
                section="xpl_shade_fog_transparency_tables",
                offset=0,
                length=len(payload),
                confidence="parsed_unknown",
                note="XPL header offsets and primary palette are decoded; shade, fog, and transparency table internals still need renderer-level confirmation.",
                related_fields=["header.offset_fog", "header.offset_transparency"],
            )
        ],
    }


def parse_acf_list(payload: bytes) -> list[str]:
    text = payload.decode("latin-1", errors="replace").replace("\x1a", " ")
    return [part for part in re.split(r"\s+", text.strip()) if part]


def normalize_acf_name(name: str) -> str:
    basename = name.strip().replace("\\", "/").split("/")[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return stem.upper()


def load_acf_names(asset_root: Path) -> list[str]:
    ress_path = asset_root / RESS_ARCHIVE_NAME
    if not ress_path.exists():
        return []
    data = ress_path.read_bytes()
    entries = lba_hqr.parse_table(data)
    entry = next(
        (candidate for candidate in entries if candidate.index == RESS_ACFLIST_ENTRY_INDEX),
        None,
    )
    if entry is None:
        return []
    if entry.byte_length <= 0:
        return []
    payload, _ = decoded_entry(lba_hqr.read_entry(data, entry))
    return parse_acf_list(payload)


def acf_list_catalog_stats(payload: bytes) -> dict[str, Any]:
    names = parse_acf_list(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded whitespace-delimited SMK/ACF name list used by GetNumAcf and PlayAllAcf.",
        "semantic_layout": "acf_name_list",
        "entry_count": len(names),
        "sampled_names": names[:32],
        "unknown_descriptors": [],
    }


def parse_smacker_header(payload: bytes) -> dict[str, Any]:
    if len(payload) < SMACKER_HEADER_MIN_BYTES:
        raise Lm2Error("Smacker payload is shorter than the fixed header prefix")
    magic = payload[:4]
    if not magic.startswith(SMACKER_MAGIC_PREFIX):
        raise Lm2Error(f"Smacker payload has unexpected magic {magic!r}")
    width, height, frame_count, frame_rate_raw, flags, tree_size = struct.unpack_from(
        "<IIIIII", payload, 4
    )
    frame_rate_signed = struct.unpack_from("<i", payload, 16)[0]
    fps: float | None = None
    if frame_rate_signed < 0:
        fps = 100000.0 / abs(frame_rate_signed)
    elif frame_rate_signed > 0:
        fps = float(frame_rate_signed)
    duration_ms: int | None = (
        int(round((frame_count / fps) * 1000)) if fps else None
    )
    return {
        "magic": magic.decode("ascii", errors="replace"),
        "format_version": magic[3:4].decode("ascii", errors="replace"),
        "width": width,
        "height": height,
        "frame_count": frame_count,
        "frame_rate_raw": frame_rate_raw,
        "frame_rate_signed": frame_rate_signed,
        "frames_per_second": round(fps, 3) if fps else None,
        "duration_ms": duration_ms,
        "flags": flags,
        "tree_size": tree_size,
    }


def smacker_video_catalog_stats(
    payload: bytes,
    resource: dict[str, Any] | None,
    *,
    acf_index: int,
    acf_name: str | None,
) -> dict[str, Any]:
    header = parse_smacker_header(payload)
    display_name = acf_name or f"ACF index {acf_index}"
    stats: dict[str, Any] = {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded Smacker/ACF container header; frame/audio stream payload is retained as codec-owned data.",
        "semantic_layout": "smacker_video",
        "acf_index": acf_index,
        "acf_name": display_name,
        "acf_basename": normalize_acf_name(display_name),
        "name_source": f"{RESS_ARCHIVE_NAME}:{RESS_ACFLIST_ENTRY_INDEX}",
        "source_provenance": "PLAYACF.CPP InitAcf loads RESS_ACFLIST from RESS.HQR:48; GetNumAcf returns the zero-based name position; PlayAcf passes that index to HQF_Init on VIDEO/VIDEO.HQR.",
        "runtime_reference_status": "runtime ACF id is the zero-based position in the RESS.HQR:48 name list",
        "header": header,
        "width": header["width"],
        "height": header["height"],
        "frame_count": header["frame_count"],
        "frames_per_second": header["frames_per_second"],
        "duration_ms": header["duration_ms"],
        "unknown_descriptors": [],
    }
    if resource is not None:
        stats["resource_header"] = dict(resource)
    return stats


def smacker_video_catalog_label(entry_index: int, stats: dict[str, Any]) -> str:
    return f"ACF movie {stats.get('acf_name', entry_index)} ({VIDEO_ARCHIVE_NAME}:{entry_index})"


def ress_unclassified_payload_catalog_stats(payload: bytes) -> dict[str, Any]:
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Cataloged raw RESS payload evidence. Runtime loader and field semantics are not identified yet.",
        "semantic_layout": "ress_unclassified_payload",
        "preview_hex": payload[:64].hex(),
        "unknown_descriptors": [
            unknown_bytes_descriptor(
                payload,
                section="ress_unclassified_payload",
                offset=0,
                length=len(payload),
                confidence="unknown",
                note="RESS entry is decoded from the HQR container and retained as raw evidence; no runtime loader has been mapped yet.",
            )
        ],
    }


def file3d_catalog_stats(payload: bytes) -> dict[str, Any]:
    metadata = parse_file3d_metadata(payload)
    objects = metadata["objects"]
    body_refs = sum(len(item.get("body_records", [])) for item in objects.values())
    animation_refs = sum(
        len(item.get("animation_records", [])) for item in objects.values()
    )
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": "Decoded File3D object table used to map scene generic BODY/ANIM ids to HQR assets.",
        "semantic_layout": "file3d_table",
        "object_count": len(objects),
        "body_reference_count": body_refs,
        "animation_reference_count": animation_refs,
        "sampled_objects": [
            {
                "index": index,
                "body_records": item.get("body_records", [])[:8],
                "animation_records": item.get("animation_records", [])[:8],
                "command_count": len(item.get("commands", [])),
            }
            for index, item in list(objects.items())[:24]
        ],
        "unknown_descriptors": [],
    }


def sprite_zv_catalog_stats(
    payload: bytes, *, backend: str, source_entry: int
) -> dict[str, Any]:
    records = parse_sprite_zv_table(payload, backend=backend, source_entry=source_entry)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": f"Decoded {sprite_backend_label(backend)} projected-sprite hotspot and bounds table.",
        "semantic_layout": "sprite_zv_table",
        "backend": backend,
        "record_count": len(records),
        "sampled_records": records[:24],
        "unknown_descriptors": [],
    }


def ress_resource_catalog_stats(entry_index: int, payload: bytes) -> tuple[str, dict[str, Any]] | None:
    if entry_index == RESS_EXT_SIZE_INFO_ENTRY_INDEX:
        return "ext-size-info", ress_ext_size_info_catalog_stats(payload)
    if entry_index in RESS_OFFSET_TABLE_ENTRY_INDICES:
        return "offset-record-table", ress_offset_table_catalog_stats(payload, entry_index)
    if entry_index == RESS_FIXED_S16_TABLE_ENTRY_INDEX:
        return "fixed-s16-table", ress_fixed_s16_table_catalog_stats(payload, entry_index)
    if entry_index in RESS_XPL_ENTRY_NAMES:
        return "xpl-palette-bundle", xpl_palette_bundle_catalog_stats(entry_index, payload)
    if entry_index == RESS_ACFLIST_ENTRY_INDEX:
        return "acf-name-list", acf_list_catalog_stats(payload)
    if entry_index == PALETTE_CATALOG_ENTRY_INDEX:
        return "palette", palette_catalog_stats(payload)
    if entry_index == TEXTURE_CATALOG_ENTRY_INDEX:
        return "texture-atlas", texture_atlas_catalog_stats(payload)
    if entry_index == RESS_GOODIES_GPC_ENTRY_INDEX:
        return "sprite-zv", sprite_zv_catalog_stats(
            payload, backend="sprites", source_entry=entry_index
        )
    if entry_index == RESS_GOODRAW_GPC_ENTRY_INDEX:
        return "sprite-zv", sprite_zv_catalog_stats(
            payload, backend="spriraw", source_entry=entry_index
        )
    if entry_index == RESS_ANIM3DS_GPC_ENTRY_INDEX:
        return "sprite-zv", sprite_zv_catalog_stats(
            payload, backend="anim3ds", source_entry=entry_index
        )
    if entry_index == FILE3D_ENTRY_INDEX:
        return "file3d-table", file3d_catalog_stats(payload)
    if len(payload) == PALETTE_BYTES:
        return "palette", palette_catalog_stats(payload)
    if len(payload) == TEXTURE_ATLAS_PIXELS:
        return "indexed-image", indexed_image_catalog_stats(payload)
    return None


def resource_catalog_label(entry_index: int, entry_type: str, stats: dict[str, Any]) -> str:
    if entry_type == "palette":
        return f"LBA2 palette ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "texture-atlas":
        return f"Texture atlas ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "indexed-image":
        return f"Indexed image ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "sprite-zv":
        return f"{stats.get('backend', 'sprite')} sprite bounds table ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "file3d-table":
        return f"File3D scene object table ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "offset-record-table":
        if stats.get("runtime_table_name"):
            return f"{stats['runtime_table_name']} runtime table ({RESS_ARCHIVE_NAME}:{entry_index})"
        return f"RESS offset table ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "fixed-s16-table":
        if stats.get("runtime_table_name"):
            return f"{stats['runtime_table_name']} signed-word table ({RESS_ARCHIVE_NAME}:{entry_index})"
        return f"RESS signed-word table ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "ext-size-info":
        return f"Exterior size info ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "xpl-palette-bundle":
        return f"XPL palette bundle {stats.get('xpl_name', entry_index)} ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "acf-name-list":
        return f"ACF movie list ({RESS_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "unclassified-payload":
        return f"Unclassified RESS payload ({RESS_ARCHIVE_NAME}:{entry_index})"
    return f"{RESS_ARCHIVE_NAME} resource {entry_index}"


def screen_resource_catalog_label(entry_index: int, entry_type: str, stats: dict[str, Any]) -> str:
    if entry_type == "screen-palette":
        return f"Screen palette {stats.get('screen_name', entry_index)} ({SCREEN_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "screen-indexed-image":
        return f"Screen image {stats.get('screen_name', entry_index)} ({SCREEN_ARCHIVE_NAME}:{entry_index})"
    return f"{SCREEN_ARCHIVE_NAME} resource {entry_index}"


def holomap_resource_catalog_label(entry_index: int, entry_type: str, stats: dict[str, Any]) -> str:
    name = stats.get("holomap_name") or holomap_entry_name(entry_index)
    if entry_type == "holomap-globe-uv-map":
        return f"Holomap globe UV map ({HOLOMAP_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "holomap-globe-altitude-map":
        return f"Holomap globe altitude {name} ({HOLOMAP_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "holomap-globe-texture-map":
        return f"Holomap globe texture {name} ({HOLOMAP_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "holomap-arrow-table":
        return f"Holomap arrow table ({HOLOMAP_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "holomap-plan-image":
        return f"Holomap plan image {name} ({HOLOMAP_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "holomap-plan-params":
        return f"Holomap plan params {name} ({HOLOMAP_ARCHIVE_NAME}:{entry_index})"
    return f"{HOLOMAP_ARCHIVE_NAME} resource {entry_index}"


def bkg_resource_catalog_label(entry_index: int, entry_type: str, stats: dict[str, Any]) -> str:
    relative = stats.get("bkg_relative_index")
    if entry_type == "bkg-header":
        return f"Background header ({LBA_BKG_ARCHIVE_NAME}:0)"
    if entry_type == "bkg-grid-map":
        return f"Background grid map {relative} ({LBA_BKG_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "bkg-grm-fragment":
        return f"Background GRM fragment {relative} ({LBA_BKG_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "bkg-block-table":
        return f"Background block table {relative} ({LBA_BKG_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "bkg-brick-graphic":
        return f"Background brick graphic {relative} ({LBA_BKG_ARCHIVE_NAME}:{entry_index})"
    if entry_type == "bkg-cube-map":
        return f"Background cube indirection table ({LBA_BKG_ARCHIVE_NAME}:{entry_index})"
    return f"{LBA_BKG_ARCHIVE_NAME} resource {entry_index}"


def hqr_paths(asset_root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in asset_root.rglob("*")
            if path.is_file() and path.suffix.upper() == ".HQR"
        ),
        key=lambda path: path.relative_to(asset_root).as_posix().upper(),
    )


def selected_hqr_root(paths: list[Path]) -> Path:
    if not paths:
        raise Lm2Error("no HQR files selected")
    try:
        return Path(os.path.commonpath([str(path.parent) for path in paths])).resolve()
    except ValueError as exc:
        raise Lm2Error("selected HQR files must be on the same drive") from exc


def normalize_hqr_file_paths(paths: list[Path]) -> list[Path]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        if not resolved.exists():
            raise Lm2Error(f"HQR file does not exist: {resolved}")
        if not resolved.is_file():
            raise Lm2Error(f"selected HQR path is not a file: {resolved}")
        if resolved.suffix.upper() != ".HQR":
            raise Lm2Error(f"selected file is not an HQR archive: {resolved}")
        normalized.append(resolved)
        seen.add(resolved)
    if not normalized:
        raise Lm2Error("no HQR files selected")
    root = selected_hqr_root(normalized)
    return sorted(
        normalized, key=lambda path: path.relative_to(root).as_posix().upper()
    )


def read_hqr_payload(
    asset_root: Path, source: dict[str, Any]
) -> tuple[bytes, dict[str, Any] | None]:
    hqr_relative = source.get("hqr")
    if not isinstance(hqr_relative, str) or not hqr_relative:
        raise Lm2Error("catalog asset is missing source.hqr")
    hqr_path = (asset_root / hqr_relative).resolve()
    try:
        hqr_path.relative_to(asset_root.resolve())
    except ValueError as exc:
        raise Lm2Error(
            f"catalog asset points outside asset root: {hqr_relative}"
        ) from exc
    if not hqr_path.exists():
        raise Lm2Error(f"HQR file is missing: {hqr_path}")

    data = hqr_path.read_bytes()
    archive_name = hqr_path.name.upper()
    is_body_archive = archive_name == "BODY.HQR"
    is_anim3ds_archive = archive_name == ANIM3DS_ARCHIVE_NAME
    classic_index = source.get("classic_index")
    if isinstance(classic_index, int):
        entries = lba_hqr.parse_classic_table(data)
        matching = [entry for entry in entries if entry.index == classic_index]
    else:
        entries = (
            lba_hqr.parse_classic_table(data)
            if is_body_archive or is_anim3ds_archive
            else lba_hqr.parse_table(data)
        )
        if archive_name in {SAMPLES_ARCHIVE_NAME, VIDEO_ARCHIVE_NAME}:
            hqr_table_index = source.get("hqr_table_index")
            if not isinstance(hqr_table_index, int):
                raise Lm2Error(f"{archive_name} catalog asset is missing HQR table index")
            matching = [entry for entry in entries if entry.index == hqr_table_index]
        elif is_body_archive:
            entry_index = source.get("entry_index")
            if not isinstance(entry_index, int):
                raise Lm2Error("BODY.HQR catalog asset is missing entry index")
            matching = [entry for entry in entries if entry.index == entry_index - 1]
        else:
            entry_index = source.get("entry_index")
            if not isinstance(entry_index, int):
                raise Lm2Error("catalog asset is missing entry index")
            matching = [entry for entry in entries if entry.index == entry_index]
    if not matching or matching[0].byte_length == 0:
        raise Lm2Error(
            f"HQR entry is missing: {hqr_relative}:{source.get('entry_index')}"
        )
    raw = lba_hqr.read_entry(data, matching[0])
    try:
        return decoded_entry(raw)
    except lba_hqr.HqrError:
        return raw, None


def find_catalog_asset(catalog: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for asset in catalog.get("assets", []):
        if asset.get("id") == asset_id:
            return asset
    raise Lm2Error(f"catalog asset not found: {asset_id}")


def unknown_bytes_descriptor(
    payload: bytes,
    *,
    section: str,
    offset: int,
    length: int,
    confidence: str,
    note: str,
    related_fields: list[str] | None = None,
) -> dict[str, Any]:
    if offset < 0 or length < 0 or offset + length > len(payload):
        raise Lm2Error(f"invalid unknown descriptor range {offset}:{length}")
    descriptor: dict[str, Any] = {
        "section": section,
        "offset": offset,
        "length": length,
        "sha256": hashlib.sha256(payload[offset : offset + length]).hexdigest(),
        "confidence": confidence,
        "note": note,
    }
    if related_fields:
        descriptor["related_decoded_fields"] = related_fields
    return descriptor


def raw_animation_catalog_stats(
    payload: bytes,
    *,
    decode_status: str,
    decode_note: str,
    parse_error: str | None = None,
) -> dict[str, Any]:
    header_byte_length = min(16, len(payload) - (len(payload) % 2))
    header_words = (
        list(struct.unpack_from("<" + "H" * (header_byte_length // 2), payload, 0))
        if header_byte_length
        else []
    )
    descriptors: list[dict[str, Any]] = []
    if header_byte_length:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="header_words",
                offset=0,
                length=header_byte_length,
                confidence="high",
                note="Captured as little-endian words only; raw animation header semantics are not decoded.",
                related_fields=["header_words"],
            )
        )
    if len(payload) > header_byte_length:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="payload_after_header_words",
                offset=header_byte_length,
                length=len(payload) - header_byte_length,
                confidence="high",
                note="Opaque animation payload bytes retained only as a descriptor hash.",
            )
        )
    if not descriptors:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="empty_payload",
                offset=0,
                length=0,
                confidence="high",
                note="Empty animation payload.",
            )
        )

    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "header_words": header_words,
        "header_word_count": len(header_words),
        "parse_status": "raw",
        "decode_status": decode_status,
        "decode_note": decode_note,
        **({"parse_error": parse_error} if parse_error else {}),
        "semantic_layout": "unknown",
        "unknown_descriptors": descriptors,
    }


def zone_flag_names(value: int, names: dict[int, str]) -> list[str]:
    return [name for bit, name in sorted(names.items()) if value & bit]


def zone_post_load_info7(value: int) -> int:
    if value & ZONE_INIT_ON:
        value |= ZONE_ON
    else:
        value &= ~ZONE_ON
    return value & ~ZONE_ACTIVE


def zone_post_load_info5(value: int) -> int:
    if value & 1:
        return value | ZONE_TEST_BRICK
    return value & ~ZONE_TEST_BRICK


def zone_post_load_info6(value: int) -> int:
    if value & 1:
        return value | ZONE_DONT_REAJUST_POS_TWINSEN
    return value & ~ZONE_DONT_REAJUST_POS_TWINSEN


def scene_zone_load_rules(zone_type: int, info: list[int]) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    if zone_type == 0:
        rules["change_cube_test_brick"] = bool(info[5] & 1)
        rules["change_cube_readjust_twinsen"] = not bool(info[6] & 1)
    if zone_type in (0, 1):
        rules["starts_on"] = bool(info[7] & 1)
        rules["active_cleared_on_load"] = True
    if zone_type == 3:
        rules["info1_reset_on_load"] = True
    if zone_type == 4:
        rules["info2_reset_on_load"] = True
    if zone_type in (6, 9):
        rules["info1_copied_from_info0_on_load"] = True
    if zone_type == 8:
        rules["info3_timer_reset_on_load"] = True
    return rules


def scene_zone_load_state(zone_type: int, info: list[int]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "source": "DISKFUNC.CPP::LoadScene zone post-load normalization",
    }
    if zone_type == 0:
        post_info5 = zone_post_load_info5(info[5])
        post_info6 = zone_post_load_info6(info[6])
        post_info7 = zone_post_load_info7(info[7])
        state.update(
            {
                "serialized_info5_flags": zone_flag_names(info[5], ZONE_INFO5_FLAG_NAMES),
                "post_load_info5_flags": zone_flag_names(post_info5, ZONE_INFO5_FLAG_NAMES),
                "serialized_info6_flags": zone_flag_names(info[6], ZONE_INFO6_FLAG_NAMES),
                "post_load_info6_flags": zone_flag_names(post_info6, ZONE_INFO6_FLAG_NAMES),
                "serialized_info7_flags": zone_flag_names(info[7], ZONE_INFO7_FLAG_NAMES),
                "post_load_info7_flags": zone_flag_names(post_info7, ZONE_INFO7_FLAG_NAMES),
                "enabled_after_load": bool(post_info7 & ZONE_ON),
                "active_after_load": bool(post_info7 & ZONE_ACTIVE),
            }
        )
    elif zone_type == 1:
        post_info7 = zone_post_load_info7(info[7])
        state.update(
            {
                "serialized_info7_flags": zone_flag_names(info[7], ZONE_INFO7_FLAG_NAMES),
                "post_load_info7_flags": zone_flag_names(post_info7, ZONE_INFO7_FLAG_NAMES),
                "enabled_after_load": bool(post_info7 & ZONE_ON),
                "active_after_load": bool(post_info7 & ZONE_ACTIVE),
                "mandatory": bool(post_info7 & ZONE_OBLIGATOIRE),
            }
        )
    elif zone_type == 3:
        state.update(
            {
                "serialized_info1": info[1],
                "post_load_info1": 0,
                "grm_state_note": "Info2 is toggled by LM_SET_GRM; LoadScene only resets Info1.",
            }
        )
    elif zone_type == 4:
        state.update(
            {
                "serialized_taken_state": bool(info[2]),
                "already_taken_after_load": False,
                "post_load_info2": 0,
            }
        )
    elif zone_type in (6, 9):
        state.update(
            {
                "serialized_initial_active": bool(info[0]),
                "serialized_runtime_active": bool(info[1]),
                "runtime_active_after_load": bool(info[0]),
                "post_load_info1": info[0],
            }
        )
    elif zone_type == 8:
        state.update(
            {
                "serialized_timer_ref": info[3],
                "timer_ref_after_load": 0,
                "post_load_info3": 0,
            }
        )
    return state


def scene_message_facing_rule(direction_code: int) -> dict[str, Any]:
    rule = {
        "source": "OBJECT.CPP::GereZoneMessage",
        "direction_code": direction_code,
        "direction": SCENE_ZONE_DIRECTION_NAMES.get(direction_code, "unknown"),
        "requires_action_normal": True,
        "object_position_source": "ptrobj->Obj.X/Z",
        "angle_function": "GetAngle2D",
    }
    facing_rule = SCENE_MESSAGE_FACING_RULES.get(direction_code)
    if facing_rule is None:
        rule.update(
            {
                "status": "unknown_direction_code",
                "beta_condition": "unclassified",
                "wraps_zero": None,
            }
        )
        return rule
    rule.update({"status": "classified", **facing_rule})
    return rule


def scene_zone_runtime_semantics(
    zone_type: int,
    info: list[int],
    zone_value: int,
    start: dict[str, int],
    end: dict[str, int],
) -> dict[str, Any]:
    zone_name = SCENE_ZONE_TYPE_NAMES.get(zone_type, "unknown")
    semantics: dict[str, Any] = {
        "source": "classic CheckZoneSce/LoadScene",
        "type": zone_name,
        "trigger": "object_position_inside_zone_bounds",
        "bounds_rule": "x >= X0, x < X1, y >= Y0, y <= Y1, z >= Z0, z < Z1",
        "fields": {"num": zone_value},
        "load_state": scene_zone_load_state(zone_type, info),
        "script_controls": [],
        "runtime_readers": [],
    }
    fields = semantics["fields"]

    if zone_type == 0:
        semantics["effect"] = "change_cube"
        semantics["trigger"] = "hero_inside_enabled_zone_after_first_loop"
        fields.update(
            {
                "target_cube": zone_value,
                "target_position_base": {"x": info[0], "y": info[1], "z": info[2]},
                "beta_quarter_turns": info[3],
                "script_control_id": info[4],
                "requires_brick_collision": bool(zone_post_load_info5(info[5]) & ZONE_TEST_BRICK),
                "readjust_twinsen_position": not bool(
                    zone_post_load_info6(info[6]) & ZONE_DONT_REAJUST_POS_TWINSEN
                ),
                "starts_enabled": bool(zone_post_load_info7(info[7]) & ZONE_ON),
            }
        )
        semantics["change_cube_application"] = {
            "source": "OBJECT.CPP::GereZoneChangeCube and GERELIFE.CPP::LM_SET_CHANGE_CUBE",
            "activation_gate": "Object movement is not manual buggy/buggy unless exterior objective flag allows it, Info7 has ZONE_ON, and object LifePoint is greater than 0.",
            "brick_collision_gate": "When Info5 has ZONE_TEST_BRICK, rotated object bounds must collide with decor via WorldColBrickDecors or the change-cube returns FALSE.",
            "exterior_edge_gate": "Exterior transition zones can require FlagHeroOutX/FlagHeroOutZ before accepting north/south/east/west edge exits.",
            "new_cube": "NewCube = zone.Num",
            "new_position_y": "NewPosY = object.Y - zone.Y0 + Info1",
            "new_beta": "object.Beta is rotated by (-Info3*1024)&4095",
            "new_position_xz": "LongRotate(object.X-zone.X0, object.Z-zone.Z0, new_beta), then NewPosX=Info0+X0 and NewPosZ=Info2+Z0 unless an exterior edge gate already supplied that axis.",
            "readjust_rule": "Info6 ZONE_DONT_REAJUST_POS_TWINSEN clears FlagReajustPosTwinsen; otherwise FlagReajustPosTwinsen is set.",
            "success_flag": "FlagChgCube = 1 and function returns TRUE.",
            "script_control": "LM_SET_CHANGE_CUBE matches Type==0 and Info4, then toggles Info7 ZONE_ON from the script operand.",
            "control_field": "Info4",
            "enabled_field": "Info7",
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_SET_CHANGE_CUBE",
                "match_field": "Info4",
                "match_value": info[4],
                "action": "toggles Info7 ZONE_ON",
            }
        )
    elif zone_type == 1:
        semantics["effect"] = "camera_zone"
        semantics["trigger"] = "followed_object_inside_enabled_zone"
        fields.update(
            {
                "target_cube_cell": {"x": info[0], "y": info[1], "z": info[2]},
                "exterior_alpha": info[3],
                "exterior_beta": info[4],
                "exterior_gamma": info[5],
                "exterior_distance": info[6],
                "starts_enabled": bool(zone_post_load_info7(info[7]) & ZONE_ON),
                "mandatory": bool(zone_post_load_info7(info[7]) & ZONE_OBLIGATOIRE),
            }
        )
        semantics["camera_application"] = {
            "source": "OBJECT.CPP::SetZoneCamera",
            "forced_camera_flags": ["CameraZone", "FlagCameraForcee"],
            "start_cube_fields": {
                "StartXCube": info[0],
                "StartYCube": info[1],
                "StartZCube": info[2],
            },
            "interior_rule": "CUBE_INTERIEUR applies only StartXCube/StartYCube/StartZCube, then CameraCenter(0) and AFF_ALL_FLIP when changed.",
            "exterior_rule": "Exterior cubes also apply AlphaCam/BetaCam/GammaCam/VueDistance, SaveCamera(), CameraCenter(0), and AFF_ALL_FLIP when camera state changed.",
            "exterior_camera_fields": {
                "AlphaCam": info[3],
                "BetaCam": info[4],
                "GammaCam": info[5],
                "VueDistance": info[6],
            },
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_SET_CAMERA",
                "match_field": "Num",
                "match_value": zone_value,
                "action": "toggles Info7 ZONE_ON and clears ZONE_ACTIVE",
            }
        )
    elif zone_type == 2:
        semantics["effect"] = "set_object_scenario_zone"
        fields["zone_id"] = zone_value
        semantics["scenario_application"] = {
            "source": "OBJECT.CPP::CheckZoneSce and GERELIFE.CPP condition functions",
            "reset_rule": "CheckZoneSce resets ptrobj->ZoneSce to -1 before testing zones.",
            "write_rule": "When an object is inside a Type==2 scenario zone, ptrobj->ZoneSce = zone.Num.",
            "self_reader": "LF_ZONE returns the current object's ZoneSce.",
            "object_reader": "LF_ZONE_OBJ reads an object id operand and returns ListObjet[id].ZoneSce.",
            "stored_field": "T_OBJET.ZoneSce",
            "zone_value_field": "zone.Num",
        }
        semantics["runtime_readers"].extend(["LF_ZONE", "LF_ZONE_OBJ"])
    elif zone_type == 3:
        semantics["effect"] = "toggle_grm_fragment"
        fields.update(
            {
                "grm_index": info[0],
                "runtime_state": info[2],
                "zone_id": zone_value,
            }
        )
        semantics["grm_application"] = {
            "source": "GERELIFE.CPP::LM_SET_GRM and GRILLE.CPP::IncrustGrm/DesIncrustGrm/RedrawGRMs",
            "script_match": "LM_SET_GRM matches zones with Type==3 and Num==script zone id.",
            "on_transition": "If script operand is nonzero and Info2 is currently 0, IncrustGrm(zone) applies the fragment.",
            "off_transition": "If script operand is zero and Info2 is currently nonzero, DesIncrustGrm(zone) restores the covered cube span.",
            "state_write": "Info2 is written to the script operand after the optional apply/remove call.",
            "incrust_source": "IncrustGrm loads BkgHeader.Grm_Start + GriHeader->My_Grm + Info0.",
            "incrust_copy": "Fragment dx/dy/dz cells are copied into BufCube columns starting at zone X0/Y0/Z0, with y cell bytes doubled because cube cells are S16.",
            "restore_source": "DesIncrustGrm decompresses original GRI columns and copies the same rectangular Y span back into BufCube.",
            "redraw_flag": "Both IncrustGrm and DesIncrustGrm set FirstTime = AFF_ALL_FLIP.",
            "redraw_reload": "RedrawGRMs reapplies IncrustGrm for Type==3 zones whose Info2 is nonzero.",
            "fragment_field": "Info0",
            "state_field": "Info2",
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_SET_GRM",
                "match_field": "Num",
                "match_value": zone_value,
                "action": "toggles Info2 and incrusts/restores GRM decor",
            }
        )
    elif zone_type == 4:
        semantics["effect"] = "give_bonus_extra"
        semantics["trigger"] = "hero_action_inside_zone"
        fields.update(
            {
                "bonus_selector": info[0],
                "bonus_selector_flags": enabled_bit_names(
                    info[0], SCENE_OBJECT_OPTION_FLAG_NAMES
                ),
                "bonus_count": info[1],
                "already_taken": bool(info[2]),
                "spawn_position": {
                    "x": (start["x"] + end["x"]) // 2,
                    "y": end["y"],
                    "z": (start["z"] + end["z"]) // 2,
                },
            }
        )
        semantics["bonus_application"] = {
            "source": "EXTRA.CPP::ZoneGiveExtraBonus and OBJECT.CPP zone type 4 handling",
            "trigger_gate": "NUM_PERSO inside zone with ActionNormal==1; InitAnim(GEN_ANIM_ACTION, ANIM_ALL_THEN, NUM_PERSO), ZoneGiveExtraBonus, then ActionNormal=FALSE.",
            "already_taken_gate": "If Info2 is nonzero, ZoneGiveExtraBonus returns without spawning.",
            "bonus_selection": "WhichBonus(Info0) chooses among EXTRA_GIVE_MONEY/LIFE/MAGIC/KEY/CLOVER by need, or returns 255 for no spawn.",
            "spawn_call": "ExtraBonus(center_x, Y1, center_z, 180*MUL_ANGLE, beta_to_twinsen_plus_random, selected_bonus_sprite, Info1)",
            "success_state_change": "Only when ExtraBonus returns a slot, ListExtra[p].Flags gains EXTRA_TIME_IN and zone Info2 is set to 1.",
            "spawn_position": {
                "x": (start["x"] + end["x"]) // 2,
                "y": end["y"],
                "z": (start["z"] + end["z"]) // 2,
            },
            "count_field": "Info1",
            "taken_field": "Info2",
        }
    elif zone_type == 5:
        semantics["effect"] = "show_message"
        semantics["trigger"] = "hero_action_inside_zone_facing_required_side"
        fields.update(
            {
                "message_id": zone_value,
                "associated_camera_zone": info[1] or None,
                "facing_direction_code": info[2],
                "facing_direction": SCENE_ZONE_DIRECTION_NAMES.get(info[2], "unknown"),
            }
        )
        semantics["message_application"] = {
            "source": "OBJECT.CPP::GereZoneMessage",
            "requires_action_normal": True,
            "direction_rule": scene_message_facing_rule(info[2]),
            "dialogue_call": "Dial(zone.Num, TRUE)",
            "speaker_state": ["NumObjDial=NUM_PERSO", "NumObjSpeak=NUM_PERSO under CDROM"],
            "palette_restore": "Palette(PtrPal) before Dial",
            "associated_camera_rule": "If Info1 is nonzero, find Type==1 camera zone with matching Num, SetZoneCamera, force FlagCameraForcee, and AffScene(AFF_ALL_FLIP) before Dial.",
        }
    elif zone_type == 6:
        semantics["effect"] = "ladder_climb"
        semantics["trigger"] = "hero_inside_active_ladder_with_climb_behavior"
        fields.update(
            {
                "initial_active": bool(info[0]),
                "runtime_active": bool(info[0]),
                "serialized_runtime_active": bool(info[1]),
                "top_y": end["y"],
            }
        )
        semantics["ladder_application"] = {
            "source": "OBJECT.CPP zone type 6 and GERELIFE.CPP::LM_ECHELLE",
            "activation_gate": "Info1 active, NUM_PERSO inside zone, and current behavior flags include CF_CLIMB.",
            "runtime_pointer": "PtrZoneClimb is assigned to the active ladder zone.",
            "up_gate": "Input I_UP or walk/ladder/up animations, while FlagAnim is not ANIM_ALL_THEN.",
            "up_effect": "When there is climb support ahead and y <= Y1-256, clears FALLING, sets FlagClimbing=CLIMBING_UP, resets StartYFalling, and starts GEN_ANIM_MONTE or GEN_ANIM_ECHELLE near the top.",
            "down_gate": "Input I_DOWN or back/down ladder animations.",
            "down_effect": "When descent space is valid, clears FALLING, sets FlagClimbing=CLIMBING_DOWN, resets StartYFalling, and starts GEN_ANIM_DESCEND or GEN_ANIM_ECHDESC.",
            "fall_effect": "If support checks fail and gravity is not animation-mastered, starts GEN_ANIM_TOMBE, sets FALLING, and initializes StartYFalling.",
            "script_control": "LM_ECHELLE matches Type==6 and Num, then writes Info1 from the script operand.",
            "active_field": "Info1",
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_ECHELLE",
                "match_field": "Num",
                "match_value": zone_value,
                "action": "writes Info1 ladder active state",
            }
        )
    elif zone_type == 7:
        semantics["effect"] = "escalator_conveyor"
        fields.update(
            {
                "active": bool(info[1]),
                "direction_code": info[2],
                "direction": SCENE_ZONE_DIRECTION_NAMES.get(info[2], "unknown"),
            }
        )
        semantics["escalator_application"] = {
            "source": "OBJECT.CPP zone type 7 and GERELIFE.CPP::LM_ESCALATOR",
            "activation_gate": "Info1 active and object CarryBy == -1.",
            "direction_field": "Info2",
            "direction_codejeu": {
                1: "CJ_ESCALATOR_NORD<<4",
                2: "CJ_ESCALATOR_SUD<<4",
                4: "CJ_ESCALATOR_EST<<4",
                8: "CJ_ESCALATOR_OUEST<<4",
            },
            "effect": "Writes object CodeJeu from the direction and sets WorkFlags DONT_PICK_CODE_JEU.",
            "script_control": "LM_ESCALATOR matches Type==7 and Num, then writes Info1 from the script operand.",
            "active_field": "Info1",
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_ESCALATOR",
                "match_field": "Num",
                "match_value": zone_value,
                "action": "writes Info1 escalator active state",
            }
        )
    elif zone_type == 8:
        semantics["effect"] = "hit_object"
        fields.update(
            {
                "hit_force": info[1],
                "cooldown_source": info[2],
                "cooldown_ticks": info[2] * 5 * 20,
                "timer_ref": info[3],
            }
        )
        semantics["hit_application"] = {
            "source": "OBJECT.CPP zone type 8 and GERELIFE.CPP::LM_SET_HIT_ZONE",
            "activation_gate": "Object inside zone, Info3 cooldown timer is 0, and Info1 hit force/enabled value is nonzero.",
            "life_gate": "HitObj is called only when the object LifePoint is greater than 0.",
            "hit_call": "HitObj(numobj, numobj, Info1, object.Beta)",
            "cooldown_start": "After the hit gate, Info3 is set to TimerRefHR + Info2*5*20.",
            "cooldown_clear": "While Info3 is nonzero, it is reset to 0 when TimerRefHR >= Info3.",
            "script_control": "LM_SET_HIT_ZONE matches Type==8 and Num, then writes Info1 from the script operand.",
            "force_field": "Info1",
            "cooldown_source_field": "Info2",
            "timer_field": "Info3",
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_SET_HIT_ZONE",
                "match_field": "Num",
                "match_value": zone_value,
                "action": "writes Info1 hit force/enabled state",
            }
        )
    elif zone_type == 9:
        semantics["effect"] = "wagon_rail_zone"
        semantics["trigger"] = "wagon_object_inside_zone"
        fields.update(
            {
                "initial_active": bool(info[0]),
                "runtime_active": bool(info[0]),
                "serialized_runtime_active": bool(info[1]),
            }
        )
        semantics["rail_application"] = {
            "source": "OBJECT.CPP zone type 9, GERELIFE.CPP::LM_SET_RAIL, and WAGON.CPP PtrZoneRail checks",
            "activation_gate": "Object inside zone with Move == MOVE_WAGON.",
            "runtime_pointer": "The wagon object's PtrZoneRail is assigned to the zone.",
            "active_field": "Info1",
            "post_load_rule": "LoadScene copies Info0 into Info1, so authored initial_active becomes runtime active state.",
            "wagon_use": "WAGON.CPP checks PtrZoneRail and PtrZoneRail->Info1 before applying rail turn behavior.",
            "script_control": "LM_SET_RAIL matches Type==9 and Num, then writes Info1 from the script operand.",
        }
        semantics["script_controls"].append(
            {
                "opcode": "LM_SET_RAIL",
                "match_field": "Num",
                "match_value": zone_value,
                "action": "writes Info1 rail active state",
            }
        )
    else:
        semantics["effect"] = "unknown"

    return semantics


def parse_scene_zones(reader: Reader, count: int) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for index in range(count):
        offset = reader.index
        start = {"x": reader.s32(), "y": reader.s32(), "z": reader.s32()}
        end = {"x": reader.s32(), "y": reader.s32(), "z": reader.s32()}
        info = [reader.s32() for _ in range(8)]
        zone_type = reader.s16()
        zone_value = reader.s16()
        zones.append(
            {
                "index": index,
                "offset": offset,
                "start": start,
                "end": end,
                "info": info,
                "type": zone_type,
                "type_name": SCENE_ZONE_TYPE_NAMES.get(zone_type, "unknown"),
                "value": zone_value,
                "load_rules": scene_zone_load_rules(zone_type, info),
                "runtime": scene_zone_runtime_semantics(
                    zone_type,
                    info,
                    zone_value,
                    start,
                    end,
                ),
            }
        )
    return zones


def scene_message_camera_links(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    camera_by_num: dict[int, dict[str, Any]] = {
        int(zone["value"]): zone
        for zone in zones
        if zone.get("type") == 1
        and isinstance(zone.get("value"), int)
        and not isinstance(zone.get("value"), bool)
    }
    links: list[dict[str, Any]] = []
    for zone in zones:
        runtime = zone.get("runtime") or {}
        if runtime.get("effect") != "show_message":
            continue
        fields = runtime.get("fields") or {}
        camera_num = fields.get("associated_camera_zone")
        if not isinstance(camera_num, int) or isinstance(camera_num, bool):
            continue
        target = camera_by_num.get(camera_num)
        link: dict[str, Any] = {
            "kind": "message_camera_zone",
            "zone_index": zone.get("index"),
            "zone_value": zone.get("value"),
            "message_id": fields.get("message_id", zone.get("value")),
            "associated_camera_zone": camera_num,
            "target_available": target is not None,
            "source_provenance": "OBJECT.CPP::GereZoneMessage looks up Type==1 camera zones by Num==Info1 before Dial().",
        }
        if target is not None:
            link.update(
                {
                    "target_zone_index": target.get("index"),
                    "target_zone_value": target.get("value"),
                    "target_type": target.get("type"),
                    "target_type_name": target.get("type_name"),
                    "target_runtime_effect": (target.get("runtime") or {}).get("effect"),
                }
            )
        links.append(link)
    return links


def parse_scene_tracks(reader: Reader, count: int) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for index in range(count):
        tracks.append(
            {
                "index": index,
                "offset": reader.index,
                "position": {"x": reader.s32(), "y": reader.s32(), "z": reader.s32()},
            }
        )
    return tracks


def enabled_bit_names(value: int, names: dict[int, str]) -> list[str]:
    return [name for bit, name in sorted(names.items()) if value & bit]


def scene_object_render_type(flags: int) -> str:
    if flags & ANIM_3DS_FLAG:
        return "anim3ds_sprite"
    if flags & SPRITE_3D_FLAG:
        return "projected_sprite"
    return "body_model"


def scene_object_srot_runtime_value(flags: int, move: int, srot: int) -> int:
    if flags & SPRITE_3D_FLAG:
        return srot
    if move == 8 or srot == 0:
        return srot
    adjusted = 2 if srot == 1 else srot
    return int(51200 / adjusted)


def scene_frame_render_contract(object_count: int) -> dict[str, Any]:
    scene_object_count = max(0, object_count - 1)
    return {
        "source": "OBJECT.CPP AffScene/AffOneObject draw tree evidence",
        "scene_object_records": scene_object_count,
        "hqr_backed_sources": [
            "scene_objects_from_SCENE_HQR",
        ],
        "runtime_dynamic_sources": [
            "ListExtra temporary bonuses/projectiles/effects",
            "ListDart fixed-object darts",
            "ListPartFlow particle flows",
            "ListIncrustDisp UI/text/sprite/inventory overlays",
        ],
        "runtime_dynamic_source_details": [
            {
                "name": "ListExtra",
                "runtime_owner": "temporary bonuses/projectiles/effects",
                "source": "OBJECT.CPP::AffScene",
                "insertion_stage": "after SCENE.HQR scene objects, before BaseSort",
                "sorted_tree_types": ["TYPE_EXTRA", "TYPE_LABY", "TYPE_SHADOW"],
                "asset_backing": "runtime extra state can draw SPRIRAW/SPRITES payloads and optional shadows; records are not serialized in SCENE.HQR",
                "preview_status": "not included in scene background previews or exports",
            },
            {
                "name": "ListDart",
                "runtime_owner": "fixed-object darts",
                "source": "OBJECT.CPP::AffScene",
                "insertion_stage": "after extras, before particle flows and BaseSort",
                "sorted_tree_types": ["TYPE_DART", "TYPE_LABY"],
                "asset_backing": "runtime dart state selects fixed-object draw data; records are not serialized in SCENE.HQR",
                "preview_status": "not included in scene background previews or exports",
            },
            {
                "name": "ListPartFlow",
                "runtime_owner": "particle flows",
                "source": "OBJECT.CPP::AffScene",
                "insertion_stage": "after darts, before BaseSort",
                "sorted_tree_types": ["TYPE_FLOW"],
                "asset_backing": "runtime particle flow state uses RESS_FLOW/TabPartFlow support data; records are not serialized in SCENE.HQR",
                "preview_status": "not included in scene background previews or exports",
            },
            {
                "name": "ListIncrustDisp",
                "runtime_owner": "UI/text/sprite/inventory overlays",
                "source": "OBJECT.CPP::AffScene",
                "insertion_stage": "after BaseSort and exterior rain",
                "sorted_tree_types": [],
                "asset_backing": "runtime incrust display state can draw text, sprites, and fixed objects directly; records are not serialized in SCENE.HQR",
                "preview_status": "not included in scene background previews or exports",
            },
        ],
        "aff_scene_phases": [
            "AFF_OBJETS passes clean moving boxes and restore cinema/animated decor without refreshing the whole grid",
            "AFF_ALL passes reset moving boxes, clear Log, RefreshGrille decor, move incrust positions, then CopyScreen Log to Screen",
            "Scene objects are preclipped and TreeInsert'ed first, with optional TYPE_SHADOW entries or inline DRAW_SHADOW flags",
            "Runtime extras are filtered by timers/message state, preclipped, and TreeInsert'ed as TYPE_EXTRA or TYPE_LABY",
            "Runtime darts are filtered by current cube/taken state, preclipped, and TreeInsert'ed as TYPE_DART with optional labyrinth slabs",
            "Runtime particle flows are preclipped and TreeInsert'ed as TYPE_FLOW",
            "BaseSort draws the sorted tree through AffOneObject and may restart AFF_ALL if the followed object is fully masked",
            "Exterior rain can draw after the sorted tree",
            "Incrust displays draw after the sorted tree and mark moving boxes directly",
        ],
        "sorted_tree_sources": [
            "TYPE_OBJ_3D scene body objects",
            "TYPE_OBJ_SPRITE projected scene sprites",
            "TYPE_OBJ_ANIM_3DS projected ANIM3DS scene sprites",
            "TYPE_SHADOW object/extra shadows",
            "TYPE_EXTRA runtime extras",
            "TYPE_DART runtime darts",
            "TYPE_FLOW runtime particle flows",
            "TYPE_LABY labyrinth slabs",
        ],
        "recovery_paths": {
            "scene_body": "ObjectDisplay then DrawRecover, or DrawOverBrickCage plus BoxMovingAdd for effective z-buffer/water",
            "scene_projected_sprite": "PtrAffGraph then DrawRecover3, LastAnimStep DrawRecover3 for SPRITE_CLIP, or moving-box recovery for effective z-buffer/water",
            "scene_anim3ds_sprite": "AffGraph(GetPtrAnim3DS) then DrawRecover3",
            "runtime_extra": "raw/effect sprite draw then DrawRecover3",
            "runtime_flow": "AffParticleFlow then DrawRecover",
            "runtime_dart": "BodyDisplay_AlphaBeta fixed object then DrawRecover",
            "runtime_incrust": "direct UI/sprite/fixed-object draw then BoxMovingAdd",
        },
        "preview_limitations": [
            "Scene background composition exports and previews stop after decor/GRM composition.",
            "They do not include BaseSort scene object, extra, dart, flow, shadow, rain, or incrust overdraw.",
            "SCENE.HQR can only enumerate scene object candidates; extras, darts, flows, and incrust displays are runtime state.",
        ],
    }


def scene_object_render_pipeline_semantics(flags: int, render_type: str) -> dict[str, Any]:
    is_sprite = render_type in {"projected_sprite", "anim3ds_sprite"}
    zbuffer_or_water = bool(flags & (OBJ_ZBUFFER_FLAG | OBJ_IN_WATER_FLAG))
    sprite_clip = bool(flags & SPRITE_CLIP_FLAG)
    casts_shadow = not bool(flags & NO_SHADOW_FLAG)
    invisible = bool(flags & INVISIBLE_FLAG)
    background = bool(flags & OBJ_BACKGROUND_FLAG)
    no_pre_clip = bool(flags & NO_PRE_CLIP_FLAG)
    zbuffer_or_water_effective = (not invisible) and (
        (render_type == "body_model" and zbuffer_or_water)
        or (render_type == "projected_sprite" and zbuffer_or_water and not sprite_clip)
    )
    effect_flags: list[str] = []
    if invisible:
        effect_flags.append("invisible_skips_draw")
    if sprite_clip:
        effect_flags.append("sprite_clip_fixed_zone")
    if background:
        effect_flags.append("background_incrust_copy_to_screen")
    if zbuffer_or_water:
        effect_flags.append("zbuffer_or_water_flag_present")
    if zbuffer_or_water_effective:
        effect_flags.append("zbuffer_or_water_moving_box")
    if no_pre_clip:
        effect_flags.append("no_pre_clip_tree_sort")
    effect_flags.append("shadow_suppressed" if not casts_shadow else "casts_shadow_when_shadow_enabled")

    if render_type == "body_model":
        draw_path = "ObjectDisplay"
        if zbuffer_or_water_effective:
            recovery_path = "DrawOverBrickCage in interiors plus BoxMovingAdd"
            recovery_method = "DrawOverBrickCage + BoxMovingAdd"
            recovery_anchor = "Obj.X+XMax, Obj.Y, Obj.Z+ZMax brick cell"
        else:
            recovery_path = "DrawRecover unless OBJ_ZBUFFER or OBJ_IN_WATER"
            recovery_method = "DrawRecover"
            recovery_anchor = "Obj.X, adjusted Obj.Y, Obj.Z with object radius"
    elif render_type == "anim3ds_sprite":
        draw_path = "AffGraph(GetPtrAnim3DS)"
        if sprite_clip:
            recovery_path = "DrawRecover3 from LastAnimStep after fixed ANIM_3DS sprite clip"
            recovery_anchor = "Obj.LastAnimStepX/Y/Z"
        else:
            recovery_path = "DrawRecover3 after projected ANIM_3DS sprite draw"
            recovery_anchor = "Obj.X+XMax, Obj.Y, Obj.Z+ZMax"
        recovery_method = "DrawRecover3"
    else:
        draw_path = "PtrAffGraph projected sprite"
        if sprite_clip:
            recovery_path = "DrawRecover3 from LastAnimStep after fixed sprite clip"
            recovery_method = "DrawRecover3"
            recovery_anchor = "Obj.LastAnimStepX/Y/Z"
        elif zbuffer_or_water_effective:
            recovery_path = "DrawOverBrickCage plus BoxMovingAdd after projected sprite draw"
            recovery_method = "DrawOverBrickCage + BoxMovingAdd"
            recovery_anchor = "Obj.X+XMax, Obj.Y, Obj.Z+ZMax brick cell"
        else:
            recovery_path = "DrawRecover3 after projected sprite draw"
            recovery_method = "DrawRecover3"
            recovery_anchor = "Obj.X+XMax, Obj.Y, Obj.Z+ZMax"

    contract_steps: list[str] = []
    if background:
        contract_steps.append("aff_scene_object_only_background_presence_probe")
    if invisible:
        contract_steps.append("aff_scene_invisible_skip_before_tree")
    else:
        contract_steps.append("aff_scene_camera_preclip")
        contract_steps.append(
            "aff_scene_tree_insert_sort_no_preclip"
            if no_pre_clip
            else "aff_scene_tree_insert_preclip_sort"
        )
        contract_steps.append(
            "shadow_suppressed" if not casts_shadow else "shadow_candidate_insert_or_inline_draw"
        )
        if render_type == "body_model":
            contract_steps.append("aff_one_object_draw_body_objectdisplay")
        elif render_type == "anim3ds_sprite":
            contract_steps.append("aff_one_object_draw_anim3ds_affgraph")
        else:
            contract_steps.append("aff_one_object_draw_sprite_ptraffgraph")
        if zbuffer_or_water_effective:
            contract_steps.append("redraw_draw_over_brick_cage_and_moving_box")
        elif sprite_clip and is_sprite:
            contract_steps.append("redraw_drawrecover3_last_anim_step")
        elif render_type == "body_model":
            contract_steps.append("redraw_drawrecover_mask")
        else:
            contract_steps.append("redraw_drawrecover3_object_max_corner")
        if background:
            contract_steps.append("background_copy_log_to_screen_on_all_flip")

    return {
        "source": "COMMON.H flags, OBJECT.CPP AffObjet/AffScene, GERELIFE.CPP LM_BACKGROUND/LM_SHADOW_OBJ, and GERETRAK.CPP TM_BACKGROUND",
        "draw_path": draw_path,
        "sort_key": "SORT_NO_PRECLIP" if no_pre_clip else "normal tree insert with camera preclip",
        "recovery_path": recovery_path,
        "effect_flags": effect_flags,
        "contract_steps": contract_steps,
        "aff_scene_policy": {
            "scene_redraw_setup": "AFF_ALL clears moving boxes, redraws the grid to Log, moves incrust displays, then copies Log to Screen before object tree draw",
            "object_only_background_skip": background,
            "object_only_background_skip_rule": "OBJ_BACKGROUND objects are projected for WAS_DRAWN presence only and skip TreeInsert during AFF_OBJETS_* passes",
            "invisible_or_bodyless_skip_before_tree": invisible,
            "camera_preclip_before_tree": "always before TreeInsert; NO_PRE_CLIP only changes the sort key",
            "tree_insert": "object bounding box enters the sorted draw tree unless background object-only or invisible/bodyless skip applies",
            "shadow": "NO_SHADOW suppresses insertion; otherwise AffScene inserts TYPE_SHADOW or marks DRAW_SHADOW for inline draw before the object",
        },
        "redraw_contract": {
            "method": recovery_method,
            "anchor": recovery_anchor,
            "moving_box": zbuffer_or_water_effective,
            "draw_over_brick_cage": zbuffer_or_water_effective,
            "zbuffer_or_water_flag_present": zbuffer_or_water,
            "zbuffer_or_water_effective": zbuffer_or_water_effective,
            "sprite_clip_info_rect": sprite_clip and is_sprite,
            "camera_recenter_on_full_mask": render_type == "body_model" and not zbuffer_or_water_effective,
        },
        "background_copy": {
            "enabled": background,
            "trigger_opcodes": ["LM_BACKGROUND", "TM_BACKGROUND"] if background else [],
            "all_scene_flip_copy": background,
            "object_only_flip_skip": background,
            "copy_source": "Log",
            "copy_destination": "Screen",
        },
        "decor_order_notes": [
            "RefreshGrille redraws the decor before object tree insertion on AFF_ALL passes.",
            "Temporary extras, darts, and incrust displays are inserted after scene objects in AffScene and share the sorted draw tree.",
            "Current background previews stop before this sorted object/extra/dart/incrust overdraw pass.",
        ],
        "invisible_skips_draw": invisible,
        "background_incrust_once": background,
        "background_toggle_opcodes": ["LM_BACKGROUND", "TM_BACKGROUND"]
        if background
        else [],
        "zbuffer_or_water": zbuffer_or_water,
        "uses_zbuffer": bool(flags & OBJ_ZBUFFER_FLAG),
        "in_water": bool(flags & OBJ_IN_WATER_FLAG),
        "uses_moving_box_instead_of_recover": zbuffer_or_water_effective,
        "sprite_clip_fixed_zone": sprite_clip,
        "sprite_clip_uses_info_rect": sprite_clip and is_sprite,
        "no_pre_clip": no_pre_clip,
        "casts_shadow": casts_shadow,
        "shadow_toggle_opcode": "LM_SHADOW_OBJ",
        "notes": [
            "OBJ_BACKGROUND is handled before the body/invisible skip in AFF_OBJETS flip passes.",
            "OBJ_ZBUFFER/OBJ_IN_WATER only changes redraw recovery for body objects and non-clipped projected sprites.",
            "SPRITE_CLIP uses Info..Info3 and LastAnimStep DrawRecover3 even if z-buffer or water flags are present.",
            "ANIM_3DS projected sprites use DrawRecover3; the classic path does not switch to BoxMovingAdd for z-buffer/water flags.",
        ],
    }


def scene_object_runtime_semantics(
    *,
    flags: int,
    option_flags: int,
    move: int,
    beta: int,
    srot: int,
    hit_force: int,
    bonus_count: int,
    armor: int,
    life_points: int,
) -> dict[str, Any]:
    render_type = scene_object_render_type(flags)
    move_name = SCENE_MOVE_NAMES.get(move, f"MOVE_{move}")
    return {
        "source": "COMMON.H object flags and DISKFUNC.CPP LoadScene object init",
        "render_type": render_type,
        "render_pipeline": scene_object_render_pipeline_semantics(flags, render_type),
        "flags": enabled_bit_names(flags, SCENE_OBJECT_FLAG_NAMES),
        "option_flags": enabled_bit_names(option_flags, SCENE_OBJECT_OPTION_FLAG_NAMES),
        "collision": {
            "object": bool(flags & (1 << 0)),
            "brick": bool(flags & (1 << 1)),
            "zone": bool(flags & (1 << 2)),
            "code_jeu": bool(flags & (1 << 6)),
            "only_floor": bool(flags & (1 << 7)),
        },
        "movement": {
            "mode": move,
            "mode_name": move_name,
            "initial_beta": beta,
            "srot_scene_value": srot,
            "srot_runtime_value": scene_object_srot_runtime_value(flags, move, srot),
            "srot_conversion": "sprite_or_wagon_or_zero"
            if (flags & SPRITE_3D_FLAG) or move == 8 or srot == 0
            else "non_sprite_non_wagon_51200_divisor",
        },
        "combat": {
            "hit_force": hit_force,
            "armor": armor,
            "life_points": life_points,
        },
        "bonus": {
            "count": bonus_count,
            "options": enabled_bit_names(option_flags, SCENE_OBJECT_OPTION_FLAG_NAMES),
        },
    }


def scene_reference_found(kind: str, value: int, object_count: int, track_count: int) -> bool:
    if kind == "object":
        return 0 <= value < object_count
    if kind == "waypoint":
        return 0 <= value < track_count
    return False


def scene_reference_label(kind: str, value: int) -> str:
    if kind == "object":
        return "hero" if value == 0 else f"object:{value}"
    if kind == "waypoint":
        return f"waypoint:{value}"
    return str(value)


def scene_object_movement_info_semantics(
    *,
    move: int,
    info: list[int],
    object_count: int,
    track_count: int,
) -> dict[str, Any]:
    move_name = SCENE_MOVE_NAMES.get(move, f"MOVE_{move}")
    references: list[dict[str, Any]] = []
    state_fields: list[dict[str, Any]] = []

    def add_reference(field_index: int, role: str, kind: str) -> None:
        value = int(info[field_index])
        references.append(
            {
                "field": f"Info{'' if field_index == 0 else field_index}",
                "field_index": field_index,
                "role": role,
                "kind": kind,
                "value": value,
                "target": scene_reference_label(kind, value),
                "target_found": scene_reference_found(kind, value, object_count, track_count),
                "source": "OBJECT.CPP DoDirObject and GERELIFE.CPP AdjustDirObject",
            }
        )

    def add_state(field_index: int, role: str, load_rule: str) -> None:
        state_fields.append(
            {
                "field": f"Info{'' if field_index == 0 else field_index}",
                "field_index": field_index,
                "role": role,
                "initial_value": int(info[field_index]),
                "load_rule": load_rule,
                "source": "OBJECT.CPP StartInitObj/DoDirObject and WAGON.CPP",
            }
        )

    if move in {2, 6, 11}:
        add_reference(3, "target_object_id", "object")
    elif move in {9, 10}:
        add_reference(3, "circle_waypoint_id", "waypoint")
        add_state(0, "circle_radius", "computed from object position to Info3 waypoint")
        add_state(1, "circle_origin_angle", "computed from object position to Info3 waypoint")
        add_state(2, "circle_timer_ref", "reset on start/init before circle motion")
    elif move == 7:
        add_state(0, "pingouin_timeout_timer_ref", "runtime timeout written when meca-pingouin starts")
        add_state(1, "pingouin_incrust_display_id", "runtime display id while countdown is visible")
    elif move == 8:
        add_state(0, "wagon_turn_direction", "runtime rail direction state")
        add_state(1, "wagon_turn_init_flag", "runtime straight/turn initialization flag")
        add_state(2, "wagon_rotation_x", "runtime rail turn pivot x")
        add_state(3, "wagon_rotation_z", "runtime rail turn pivot z")
    elif move == 3:
        state_fields.append(
            {
                "field": "track_script",
                "field_index": None,
                "role": "own_track_script_driver",
                "initial_value": None,
                "load_rule": "movement advances the object's own track script offset",
                "source": "OBJECT.CPP DoDirObject MOVE_TRACK",
            }
        )

    return {
        "mode": move,
        "mode_name": move_name,
        "references": references,
        "state_fields": state_fields,
    }


def classify_scene_patch_target(
    offset: int,
    script_ranges: list[dict[str, Any]],
) -> dict[str, Any]:
    for script_range in script_ranges:
        start = int(script_range["offset"])
        length = int(script_range["length"])
        if start <= offset < start + length:
            return {
                "kind": script_range["kind"],
                "owner": script_range["owner"],
                "script_relative_offset": offset - start,
            }
    return {
        "kind": "unknown",
        "owner": None,
        "script_relative_offset": None,
    }


def script_field_span(name: str, offset: int, size: int, source: str) -> dict[str, Any]:
    return {"field": name, "offset": offset, "size": size, "source": source}


def life_value_field_size(raw: bytes, offset: int, return_type: str) -> int | None:
    if return_type in {"s8", "u8"}:
        return 1 if offset + 1 <= len(raw) else None
    if return_type == "s16":
        return 2 if offset + 2 <= len(raw) else None
    if return_type == "string":
        terminator = raw.find(b"\x00", offset)
        if terminator == -1:
            return None
        return terminator - offset + 1
    return None


def life_condition_operand_fields(raw: bytes) -> list[dict[str, Any]]:
    if not raw:
        return []
    function_id = raw[0]
    function_size = 2 if function_id in LIFE_FUNCTIONS_WITH_U8 else 1
    if len(raw) < function_size + 1:
        return []
    return_type = LIFE_FUNCTION_RETURN_TYPES.get(function_id, "s8")
    compare_value_offset = function_size + 1
    compare_value_size = life_value_field_size(raw, compare_value_offset, return_type)
    if compare_value_size is None:
        return []
    branch_offset = compare_value_offset + compare_value_size
    if branch_offset + 2 > len(raw):
        return []
    fields = [
        script_field_span("function_id", 0, 1, "life_condition_layout"),
        script_field_span("comparator", function_size, 1, "life_condition_layout"),
        script_field_span(
            "compare_value",
            compare_value_offset,
            compare_value_size,
            "life_condition_layout",
        ),
        script_field_span("branch_offset", branch_offset, 2, "life_condition_layout"),
    ]
    if function_size == 2:
        fields.insert(
            1,
            script_field_span("function_parameter", 1, 1, "life_condition_layout"),
        )
    return fields


def life_case_operand_fields(raw: bytes, return_type: str | None) -> list[dict[str, Any]]:
    if return_type is None or len(raw) < 3:
        return []
    compare_value_size = life_value_field_size(raw, 3, return_type)
    if compare_value_size is None:
        return []
    return [
        script_field_span("target_offset", 0, 2, "life_case_layout"),
        script_field_span("comparator", 2, 1, "life_case_layout"),
        script_field_span("compare_value", 3, compare_value_size, "life_case_layout"),
    ]


def scalar_semantic_fields(
    raw: bytes,
    semantics: dict[str, Any],
    sizes: list[int],
    source: str,
) -> list[dict[str, Any]]:
    scalar_items = [
        (key, value)
        for key, value in semantics.items()
        if isinstance(value, (bool, int))
    ]
    if len(scalar_items) != len(sizes) or sum(sizes) != len(raw):
        return []
    fields: list[dict[str, Any]] = []
    offset = 0
    for (key, _value), size in zip(scalar_items, sizes):
        fields.append(script_field_span(key, offset, size, source))
        offset += size
    return fields


def script_instruction_operand_fields(instruction: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        raw = bytes.fromhex(str(instruction.get("operand_hex") or ""))
    except ValueError:
        return []
    opcode = int(instruction.get("opcode") or 0)
    mnemonic = str(instruction.get("mnemonic") or "")
    layout = str(instruction.get("operand_layout") or "")
    semantics = instruction.get("operand_semantics")
    if not isinstance(semantics, dict):
        semantics = {}

    if mnemonic.startswith("TM_"):
        if opcode == 6:
            return [
                script_field_span("initial_count", 0, 1, "track_opcode_layout"),
                script_field_span("current_count", 1, 1, "classic_track_runtime"),
                script_field_span("target_offset", 2, 2, "track_opcode_layout"),
            ]
        if opcode == 7:
            return [
                script_field_span(
                    "target_beta_runtime_flag",
                    0,
                    2,
                    "classic_track_runtime",
                )
            ]
        if opcode == 10:
            return [script_field_span("target_offset", 0, 2, "track_opcode_layout")]
        if opcode == 13:
            return [
                script_field_span("target_count", 0, 1, "track_opcode_layout"),
                script_field_span("current_count", 1, 1, "classic_track_runtime"),
            ]
        if opcode in {18, 36}:
            return [
                script_field_span("duration_count", 0, 1, "track_opcode_layout"),
                script_field_span("runtime_timer_ref", 1, 4, "classic_track_runtime"),
            ]
        if opcode in {39, 49}:
            return [
                script_field_span("duration_max", 0, 1, "track_opcode_layout"),
                script_field_span("runtime_timer_ref", 1, 4, "classic_track_runtime"),
            ]
        if opcode == 33:
            return [
                script_field_span("runtime_face_beta", 0, 2, "classic_track_runtime")
            ]
        if opcode == 34:
            return [
                script_field_span("random_beta_span", 0, 2, "track_opcode_layout"),
                script_field_span("runtime_target_beta", 2, 2, "classic_track_runtime"),
            ]
        if layout == "u8" and len(semantics) == 1:
            return scalar_semantic_fields(raw, semantics, [1], "track_operand_semantics")
        if layout in {"i16", "angle"} and len(semantics) == 1:
            return scalar_semantic_fields(raw, semantics, [2], "track_operand_semantics")
        return []

    if layout == "condition":
        return life_condition_operand_fields(raw)
    if layout == "case_branch":
        return life_case_operand_fields(raw, semantics.get("switch_return_type"))
    layout_sizes = {
        "u8": [1],
        "i8": [1],
        "u16": [2],
        "i16": [2],
        "u8_pair": [1, 1],
        "u8_i8": [1, 1],
        "u8_i16": [1, 2],
        "i16_u8": [2, 1],
        "u8_u16": [1, 2],
        "u8_u16_i16": [1, 2, 2],
        "i16_u8_i16": [2, 1, 2],
        "u8_u8_u8_i16": [1, 1, 1, 2],
        "i16_i16_u8_i16": [2, 2, 1, 2],
    }
    sizes = layout_sizes.get(layout)
    if sizes is None:
        return []
    return scalar_semantic_fields(raw, semantics, sizes, "life_operand_semantics")


def scene_patch_field_target(
    instruction: dict[str, Any], instruction_relative_offset: int
) -> dict[str, Any]:
    if instruction_relative_offset == 0:
        return {
            "patched_field": "opcode",
            "patched_field_offset": 0,
            "patched_field_size": 1,
            "patched_field_byte_offset": 0,
            "patched_field_source": "script_opcode",
        }
    operand_relative_offset = instruction_relative_offset - 1
    for field in script_instruction_operand_fields(instruction):
        field_offset = int(field["offset"])
        field_size = int(field["size"])
        if field_offset <= operand_relative_offset < field_offset + field_size:
            return {
                "patched_field": str(field["field"]),
                "patched_field_offset": instruction_relative_offset
                - (operand_relative_offset - field_offset),
                "patched_field_size": field_size,
                "patched_field_byte_offset": operand_relative_offset - field_offset,
                "patched_field_source": str(field["source"]),
            }
    return {}


def scene_patch_instruction_target(
    target: dict[str, Any],
    script_instruction_map: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    script_kind = target.get("kind")
    owner = target.get("owner")
    relative_offset = target.get("script_relative_offset")
    if not isinstance(script_kind, str) or not isinstance(owner, str):
        return {"instruction_found": False}
    if not isinstance(relative_offset, int):
        return {"instruction_found": False}
    for instruction in script_instruction_map.get((owner, script_kind), []):
        instruction_offset = int(instruction["offset"])
        instruction_length = int(instruction["byte_length"])
        if instruction_offset <= relative_offset < instruction_offset + instruction_length:
            instruction_relative_offset = relative_offset - instruction_offset
            result: dict[str, Any] = {
                "instruction_found": True,
                "instruction_offset": instruction_offset,
                "instruction_relative_offset": instruction_relative_offset,
                "instruction_opcode": instruction["mnemonic"],
                "instruction_behavior_category": instruction["behavior_category"],
                "hits_opcode_byte": instruction_relative_offset == 0,
            }
            if instruction_relative_offset > 0:
                result["operand_relative_offset"] = instruction_relative_offset - 1
            result.update(scene_patch_field_target(instruction, instruction_relative_offset))
            return result
    return {"instruction_found": False}


def parse_scene_patches(
    reader: Reader,
    count: int,
    script_ranges: list[dict[str, Any]],
    script_instruction_map: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []
    for index in range(count):
        offset = reader.index
        size = reader.s16()
        target_offset = reader.s16()
        target = classify_scene_patch_target(target_offset, script_ranges)
        if script_instruction_map is not None:
            target.update(scene_patch_instruction_target(target, script_instruction_map))
        patches.append(
            {
                "index": index,
                "offset": offset,
                "size": size,
                "target_offset": target_offset,
                "target": target,
            }
        )
    return patches


def add_script_behavior_counts(
    totals: dict[str, int], analysis: dict[str, Any] | None
) -> None:
    if not analysis:
        return
    for item in analysis.get("behavior_categories") or []:
        category = str(item.get("category") or "unknown_behavior")
        count = int(item.get("count") or 0)
        totals[category] = totals.get(category, 0) + count


def add_script_control_flow_counts(
    totals: dict[str, int], analysis: dict[str, Any] | None
) -> None:
    if not analysis:
        return
    links = analysis.get("control_flow_links") or []
    labels = analysis.get("label_definitions") or []
    totals["links"] = totals.get("links", 0) + len(links)
    totals["found"] = totals.get("found", 0) + sum(
        1 for link in links if link.get("target_found")
    )
    totals["missing"] = totals.get("missing", 0) + sum(
        1 for link in links if not link.get("target_found")
    )
    totals["labels"] = totals.get("labels", 0) + len(labels)


def add_script_link_target_status_counts(
    totals: dict[str, int], analysis: dict[str, Any] | None, link_key: str
) -> None:
    if not analysis:
        return
    for link in analysis.get(link_key) or []:
        status = str(link.get("target_status") or "unknown")
        totals[status] = totals.get(status, 0) + 1


def add_script_skipped_byte_counts(
    totals: dict[str, int], analysis: dict[str, Any] | None
) -> None:
    if not analysis:
        return
    skipped_bytes = int(analysis.get("unreachable_bytes") or 0)
    ranges = analysis.get("unreachable_byte_ranges") or []
    if skipped_bytes <= 0:
        return
    totals["scripts"] = totals.get("scripts", 0) + 1
    totals["bytes"] = totals.get("bytes", 0) + skipped_bytes
    totals["ranges"] = totals.get("ranges", 0) + len(ranges)


def add_script_runtime_state_counts(
    field_totals: dict[str, int],
    instruction_field_totals: dict[str, int],
    analysis: dict[str, Any] | None,
) -> None:
    if not analysis:
        return
    for field in analysis.get("runtime_state_fields") or []:
        field_name = str(field.get("field") or "unknown_field")
        field_totals[field_name] = field_totals.get(field_name, 0) + 1
        opcode = str(field.get("opcode") or "unknown")
        instruction_field = f"{opcode}.{field_name}"
        instruction_field_totals[instruction_field] = (
            instruction_field_totals.get(instruction_field, 0) + 1
        )


def add_script_execution_contract_counts(
    totals: dict[str, int], analysis: dict[str, Any] | None
) -> None:
    if not analysis:
        return
    for contract in analysis.get("execution_contracts") or []:
        name = str(contract.get("contract") or "unknown_contract")
        count = int(contract.get("count") or 0)
        totals[name] = totals.get(name, 0) + count


def add_script_condition_function_counts(
    function_totals: dict[str, int],
    return_type_totals: dict[str, int],
    analysis: dict[str, Any] | None,
) -> None:
    if not analysis:
        return
    for function in analysis.get("condition_functions") or []:
        name = str(function.get("function") or "unknown_function")
        count = int(function.get("count") or 0)
        return_type = str(function.get("return_type") or "unknown")
        function_totals[name] = function_totals.get(name, 0) + count
        return_type_totals[return_type] = return_type_totals.get(return_type, 0) + count


def add_script_condition_comparator_counts(
    comparator_totals: dict[str, int],
    analysis: dict[str, Any] | None,
) -> None:
    if not analysis:
        return
    for comparator in analysis.get("condition_comparators") or []:
        name = str(comparator.get("comparator") or "unknown_comparator")
        count = int(comparator.get("count") or 0)
        comparator_totals[name] = comparator_totals.get(name, 0) + count


def scene_script_instructions(kind: str, script: bytes) -> list[dict[str, Any]]:
    return decode_scene_script_instruction_graph(kind, script)["instructions"]


def scene_owner_name(object_index: int) -> str:
    return "hero" if object_index == 0 else f"object:{object_index}"


def scene_object_index_from_owner(owner_name: str) -> int:
    if owner_name == "hero":
        return 0
    if owner_name.startswith("object:"):
        return int(owner_name.split(":", 1)[1])
    raise ValueError(f"unknown scene owner: {owner_name}")


def add_scene_script_cross_links(
    owner: dict[str, Any],
    owner_name: str,
    owners_by_index: dict[int, dict[str, Any]],
    script_instructions: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, int]:
    counts: dict[str, int] = {
        "links": 0,
        "found": 0,
        "missing": 0,
        "track": 0,
        "life": 0,
        "missing_owner": 0,
    }
    script = owner.get("life_script_analysis")
    if not script:
        return counts
    source_instructions = script_instructions.get((owner_name, "life"), [])
    if not source_instructions:
        return counts

    links: list[dict[str, Any]] = []
    source_object_index = scene_object_index_from_owner(owner_name)
    for instruction in source_instructions:
        semantics = instruction.get("operand_semantics") or {}
        targets: list[tuple[str, str, int, int]] = []
        target_track_offset = semantics.get("target_track_offset")
        if isinstance(target_track_offset, int) and not isinstance(target_track_offset, bool):
            targets.append(
                (
                    "target_track_offset",
                    "track",
                    int(semantics.get("object_id", source_object_index)),
                    target_track_offset,
                )
            )
        target_life_offset = semantics.get("target_life_offset")
        if (
            isinstance(target_life_offset, int)
            and not isinstance(target_life_offset, bool)
            and "object_id" in semantics
        ):
            targets.append(
                (
                    "target_life_offset",
                    "life",
                    int(semantics["object_id"]),
                    target_life_offset,
                )
            )

        for target_field, target_script_kind, target_object_index, target_offset in targets:
            target_owner_name = scene_owner_name(target_object_index)
            target_owner = owners_by_index.get(target_object_index)
            target_instructions = script_instructions.get((target_owner_name, target_script_kind), [])
            target_instruction_map = {item["offset"]: item for item in target_instructions}
            target_instruction = target_instruction_map.get(target_offset)
            target_owner_found = target_owner is not None
            target_script_bytes = None
            if target_owner_found:
                target_script_bytes = int(target_owner.get(f"{target_script_kind}_script_bytes") or 0)
            link: dict[str, Any] = {
                "source_owner": owner_name,
                "source_script_kind": "life",
                "source_offset": instruction["offset"],
                "source_opcode": instruction["mnemonic"],
                "source_behavior_category": instruction["behavior_category"],
                "target_field": target_field,
                "target_owner": target_owner_name,
                "target_object_index": target_object_index,
                "target_owner_found": target_owner_found,
                "target_script_kind": target_script_kind,
                "target_offset": target_offset,
                "target_found": target_instruction is not None,
            }
            if target_owner_found:
                link.update(
                    script_target_offset_evidence(
                        target_offset,
                        target_instructions,
                        target_script_bytes,
                    )
                )
            else:
                link["target_status"] = "missing_owner"
            if target_instruction is not None:
                link["target_opcode"] = target_instruction["mnemonic"]
                link["target_behavior_category"] = target_instruction["behavior_category"]
            links.append(link)
            counts["links"] += 1
            counts[target_script_kind] = counts.get(target_script_kind, 0) + 1
            if target_instruction is not None:
                counts["found"] += 1
            else:
                counts["missing"] += 1
            if not target_owner_found:
                counts["missing_owner"] += 1

    if links:
        script["cross_script_links"] = links
    return counts


SCRIPT_ZONE_REFERENCE_TYPES = {
    "camera_zone": 1,
    "grm_zone": 3,
    "ladder_zone": 6,
    "escalator_zone": 7,
    "hit_zone": 8,
    "rail_zone": 9,
    "change_cube_control": 0,
}


def scene_object_local_target(
    object_id: int, objects_by_index: dict[int, dict[str, Any]]
) -> dict[str, Any] | None:
    if object_id == 0:
        return {
            "target": "hero",
            "object_index": 0,
            "target_available": True,
        }
    scene_object = objects_by_index.get(object_id)
    if scene_object is None:
        return None
    return {
        "target": "scene_object",
        "object_index": object_id,
        "target_available": True,
        "position": scene_object.get("position"),
        "file3d_index": scene_object.get("file3d_index"),
        "gen_body": scene_object.get("gen_body"),
        "gen_anim": scene_object.get("gen_anim"),
        "sprite": scene_object.get("sprite"),
    }


def scene_waypoint_local_target(
    waypoint_id: int, tracks_by_index: dict[int, dict[str, Any]]
) -> dict[str, Any] | None:
    track = tracks_by_index.get(waypoint_id)
    if track is None:
        return None
    return {
        "target": "waypoint",
        "waypoint_index": waypoint_id,
        "target_available": True,
        "position": track.get("position"),
    }


def scene_zone_local_target(
    reference_key: str, zone_id: int, zones_by_index: dict[int, dict[str, Any]]
) -> dict[str, Any] | None:
    zone = zones_by_index.get(zone_id)
    if zone is None:
        return None
    expected_type = SCRIPT_ZONE_REFERENCE_TYPES[reference_key]
    return {
        "target": "zone",
        "zone_index": zone_id,
        "target_available": True,
        "type": zone.get("type"),
        "type_name": zone.get("type_name"),
        "expected_type": expected_type,
        "type_matches_reference": zone.get("type") == expected_type,
        "value": zone.get("value"),
        "runtime_effect": (zone.get("runtime") or {}).get("effect"),
    }


def add_scene_script_local_links(
    owner: dict[str, Any],
    objects_by_index: dict[int, dict[str, Any]],
    zones_by_index: dict[int, dict[str, Any]],
    tracks_by_index: dict[int, dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {"object": 0, "waypoint": 0, "zone": 0}
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = owner.get(script_key)
        if not script:
            continue
        references = script.get("references") or {}
        links: list[dict[str, Any]] = []
        for object_id in references.get("object") or []:
            target = scene_object_local_target(int(object_id), objects_by_index)
            if target is None:
                continue
            links.append(
                {
                    "kind": "object",
                    "reference_key": "object",
                    "reference_value": int(object_id),
                    **target,
                }
            )
            counts["object"] += 1
        for waypoint_id in references.get("waypoint") or []:
            target = scene_waypoint_local_target(int(waypoint_id), tracks_by_index)
            if target is None:
                continue
            links.append(
                {
                    "kind": "waypoint",
                    "reference_key": "waypoint",
                    "reference_value": int(waypoint_id),
                    **target,
                }
            )
            counts["waypoint"] += 1
        for reference_key in SCRIPT_ZONE_REFERENCE_TYPES:
            for zone_id in references.get(reference_key) or []:
                target = scene_zone_local_target(reference_key, int(zone_id), zones_by_index)
                if target is None:
                    continue
                links.append(
                    {
                        "kind": "zone",
                        "reference_key": reference_key,
                        "reference_value": int(zone_id),
                        **target,
                    }
                )
                counts["zone"] += 1
        if links:
            script["local_links"] = links
    return counts


def parse_scene_reconnaissance(payload: bytes) -> dict[str, Any]:
    reader = Reader(payload)
    script_ranges: list[dict[str, Any]] = []
    script_instruction_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    island = reader.s8()
    world = {
        "island": island,
        "cube_x": reader.s8(),
        "cube_y": reader.s8(),
        "shadow_level": reader.s8(),
        "labyrinth_mode": reader.s8(),
        "cube_mode": reader.s8(),
        "unknown_world_byte": reader.s8(),
    }
    world["runtime_environment"] = {
        "source_provenance": "DISKFUNC.CPP::LoadScene INFO_WORLD reads Island, CurrentCubeX, CurrentCubeY, ShadowLevel, ModeLabyrinthe, CubeMode, then one local byte n.",
        "island_effect": "Island selects TabArrow[Island].Planet, island text file START_FILE_ISLAND+Island, exterior island resources, and scene palette selection.",
        "cube_coordinate_effect": "CurrentCubeX and CurrentCubeY are marked by the classic source as used only for 3DExt.",
        "shadow_effect": "ShadowLevel feeds classic shadow shading; global Shadow and object flags decide whether shadows are inserted.",
        "labyrinth_effect": "ModeLabyrinthe changes object/shadow rendering behavior in classic OBJECT.CPP.",
        "cube_mode_effect": "CubeMode participates in fade/sample-stop decisions and interior/exterior palette/background selection.",
        "post_cube_mode_byte": world["unknown_world_byte"],
        "post_cube_mode_byte_status": "Read into local variable n after CubeMode in LoadScene; no source-backed runtime use identified yet.",
    }
    ambience = {
        "alpha_light": reader.s16(),
        "beta_light": reader.s16(),
        "samples": [
            {
                "sample": reader.s16(),
                "repeat": reader.s16(),
                "random": reader.s16(),
                "frequency": reader.s16(),
                "volume": reader.s16(),
            }
            for _ in range(4)
        ],
        "second_min": reader.s16(),
        "second_range": reader.s16(),
        "cube_jingle": reader.s8(),
    }
    ambience["runtime_audio_lighting"] = {
        "source_provenance": "DISKFUNC.CPP::LoadScene fills AlphaLight/BetaLight, SampleAmbiance/SampleRepeat/SampleRnd/SampleFreq/SampleVol, SecondMin/SecondEcart, and CubeJingle; AMBIANCE.CPP::LaunchAmbiance/GereAmbiance schedule ambient samples; OBJECT.CPP/PERSO.CPP apply lighting and music.",
        "lighting_effect": "AlphaLight and BetaLight are passed to SetLightVector when scene/cube lighting is initialized.",
        "ambient_sample_rule": "Four SampleAmbiance slots are optional sample ids; -1 is an empty sentinel. Repeat, random, frequency, and volume fields are passed to HQ_3D_MixSample/HQ_MixSample behavior.",
        "ambient_timer_rule": "GereAmbiance schedules the next random ambience at TimerRefHR + (MyRnd(SecondEcart) + SecondMin) * 1000; SecondMin < 0 postpones ambience for 200000 ms.",
        "music_rule": "CubeJingle is the scene music/jingle id; 255 is treated as a no-music/no-stack sentinel before PlayMusic.",
    }
    hero = {
        "start": {"x": reader.s16(), "y": reader.s16(), "z": reader.s16()},
        "track_script_offset": 0,
        "track_script_bytes": 0,
        "life_script_offset": 0,
        "life_script_bytes": 0,
    }
    hero_track_size = reader.s16()
    hero["track_script_offset"] = reader.index
    hero["track_script_bytes"] = hero_track_size
    hero_track_script = payload[reader.index : reader.index + hero_track_size]
    hero["track_script_sha256"] = hashlib.sha256(
        hero_track_script
    ).hexdigest()
    hero["track_script_analysis"] = analyze_track_script(hero_track_script)
    script_instruction_map[("hero", "track")] = scene_script_instructions(
        "track", hero_track_script
    )
    script_ranges.append(
        {
            "kind": "track",
            "owner": "hero",
            "offset": hero["track_script_offset"],
            "length": hero["track_script_bytes"],
        }
    )
    reader.skip(hero_track_size)
    hero_life_size = reader.s16()
    hero["life_script_offset"] = reader.index
    hero["life_script_bytes"] = hero_life_size
    hero_life_script = payload[reader.index : reader.index + hero_life_size]
    hero["life_script_sha256"] = hashlib.sha256(
        hero_life_script
    ).hexdigest()
    hero["life_script_analysis"] = analyze_life_script(hero_life_script)
    script_instruction_map[("hero", "life")] = scene_script_instructions(
        "life", hero_life_script
    )
    script_behavior_counts: dict[str, int] = {}
    script_control_flow_counts: dict[str, int] = {
        "links": 0,
        "found": 0,
        "missing": 0,
        "labels": 0,
    }
    script_control_flow_target_status_counts: dict[str, int] = {}
    script_runtime_state_counts: dict[str, int] = {}
    script_runtime_instruction_state_counts: dict[str, int] = {}
    script_execution_contract_counts: dict[str, int] = {}
    script_condition_function_counts: dict[str, int] = {}
    script_condition_return_type_counts: dict[str, int] = {}
    script_condition_comparator_counts: dict[str, int] = {}
    script_skipped_byte_counts: dict[str, int] = {}
    add_script_behavior_counts(script_behavior_counts, hero["track_script_analysis"])
    add_script_behavior_counts(script_behavior_counts, hero["life_script_analysis"])
    add_script_control_flow_counts(script_control_flow_counts, hero["track_script_analysis"])
    add_script_control_flow_counts(script_control_flow_counts, hero["life_script_analysis"])
    add_script_link_target_status_counts(
        script_control_flow_target_status_counts,
        hero["track_script_analysis"],
        "control_flow_links",
    )
    add_script_link_target_status_counts(
        script_control_flow_target_status_counts,
        hero["life_script_analysis"],
        "control_flow_links",
    )
    add_script_runtime_state_counts(
        script_runtime_state_counts,
        script_runtime_instruction_state_counts,
        hero["track_script_analysis"],
    )
    add_script_runtime_state_counts(
        script_runtime_state_counts,
        script_runtime_instruction_state_counts,
        hero["life_script_analysis"],
    )
    add_script_execution_contract_counts(
        script_execution_contract_counts, hero["track_script_analysis"]
    )
    add_script_execution_contract_counts(
        script_execution_contract_counts, hero["life_script_analysis"]
    )
    add_script_condition_function_counts(
        script_condition_function_counts,
        script_condition_return_type_counts,
        hero["track_script_analysis"],
    )
    add_script_condition_comparator_counts(
        script_condition_comparator_counts, hero["track_script_analysis"]
    )
    add_script_condition_function_counts(
        script_condition_function_counts,
        script_condition_return_type_counts,
        hero["life_script_analysis"],
    )
    add_script_condition_comparator_counts(
        script_condition_comparator_counts, hero["life_script_analysis"]
    )
    add_script_skipped_byte_counts(script_skipped_byte_counts, hero["track_script_analysis"])
    add_script_skipped_byte_counts(script_skipped_byte_counts, hero["life_script_analysis"])
    script_ranges.append(
        {
            "kind": "life",
            "owner": "hero",
            "offset": hero["life_script_offset"],
            "length": hero["life_script_bytes"],
        }
    )
    reader.skip(hero_life_size)

    objects_offset = reader.index
    object_count = reader.s16()
    object_summaries: list[dict[str, Any]] = []
    sprite_objects = 0
    anim3ds_objects = 0
    for object_index in range(1, object_count):
        object_offset = reader.index
        flags = reader.u32()
        file3d_index = reader.s16()
        gen_body = reader.s8()
        gen_anim = reader.s16()
        sprite = reader.s16()
        position = {"x": reader.s16(), "y": reader.s16(), "z": reader.s16()}
        hit_force = reader.s8()
        option_flags = reader.s16()
        beta = reader.s16()
        srot = reader.s16()
        move = reader.s8()
        info = [reader.s16(), reader.s16(), reader.s16(), reader.s16()]
        bonus_count = reader.s16()
        color = reader.s8()
        anim3ds: dict[str, Any] | None = None
        if flags & ANIM_3DS_FLAG:
            animation_number = reader.u32()
            frames_per_second = reader.s16()
            anim3ds = {
                "animation_number": animation_number,
                "size_s_hit": frames_per_second,
                "frames_per_second": frames_per_second,
                "timing_field": "Info3 is copied to SizeSHit and used as ANIM3DS frames-per-second.",
            }
            anim3ds_objects += 1
        armor = reader.s8()
        life_points = reader.s8()
        track_size = reader.s16()
        track_offset = reader.index
        track_script = payload[reader.index : reader.index + track_size]
        track_sha256 = hashlib.sha256(track_script).hexdigest()
        track_analysis = analyze_track_script(track_script)
        owner_name = scene_owner_name(object_index)
        script_instruction_map[(owner_name, "track")] = scene_script_instructions(
            "track", track_script
        )
        script_ranges.append(
            {
                "kind": "track",
                "owner": f"object:{object_index}",
                "offset": track_offset,
                "length": track_size,
            }
        )
        reader.skip(track_size)
        life_size = reader.s16()
        life_offset = reader.index
        life_script = payload[reader.index : reader.index + life_size]
        life_sha256 = hashlib.sha256(life_script).hexdigest()
        life_analysis = analyze_life_script(life_script)
        script_instruction_map[(owner_name, "life")] = scene_script_instructions(
            "life", life_script
        )
        add_script_behavior_counts(script_behavior_counts, track_analysis)
        add_script_behavior_counts(script_behavior_counts, life_analysis)
        add_script_control_flow_counts(script_control_flow_counts, track_analysis)
        add_script_control_flow_counts(script_control_flow_counts, life_analysis)
        add_script_link_target_status_counts(
            script_control_flow_target_status_counts, track_analysis, "control_flow_links"
        )
        add_script_link_target_status_counts(
            script_control_flow_target_status_counts, life_analysis, "control_flow_links"
        )
        add_script_runtime_state_counts(
            script_runtime_state_counts,
            script_runtime_instruction_state_counts,
            track_analysis,
        )
        add_script_runtime_state_counts(
            script_runtime_state_counts,
            script_runtime_instruction_state_counts,
            life_analysis,
        )
        add_script_execution_contract_counts(script_execution_contract_counts, track_analysis)
        add_script_execution_contract_counts(script_execution_contract_counts, life_analysis)
        add_script_condition_function_counts(
            script_condition_function_counts,
            script_condition_return_type_counts,
            track_analysis,
        )
        add_script_condition_comparator_counts(
            script_condition_comparator_counts, track_analysis
        )
        add_script_condition_function_counts(
            script_condition_function_counts,
            script_condition_return_type_counts,
            life_analysis,
        )
        add_script_condition_comparator_counts(
            script_condition_comparator_counts, life_analysis
        )
        add_script_skipped_byte_counts(script_skipped_byte_counts, track_analysis)
        add_script_skipped_byte_counts(script_skipped_byte_counts, life_analysis)
        script_ranges.append(
            {
                "kind": "life",
                "owner": f"object:{object_index}",
                "offset": life_offset,
                "length": life_size,
            }
        )
        reader.skip(life_size)
        if flags & SPRITE_3D_FLAG:
            sprite_objects += 1
        runtime = scene_object_runtime_semantics(
            flags=flags,
            option_flags=option_flags,
            move=move,
            beta=beta,
            srot=srot,
            hit_force=hit_force,
            bonus_count=bonus_count,
            armor=armor,
            life_points=life_points,
        )
        summary: dict[str, Any] = {
            "index": object_index,
            "offset": object_offset,
            "flags": flags,
            "file3d_index": file3d_index,
            "gen_body": gen_body,
            "gen_anim": gen_anim,
            "sprite": sprite,
            "position": position,
            "hit_force": hit_force,
            "option_flags": option_flags,
            "beta": beta,
            "srot": srot,
            "move": move,
            "info": info,
            "bonus_count": bonus_count,
            "color": color,
            "armor": armor,
            "life_points": life_points,
            "runtime": runtime,
            "track_script_offset": track_offset,
            "track_script_bytes": track_size,
            "track_script_sha256": track_sha256,
            "track_script_analysis": track_analysis,
            "life_script_offset": life_offset,
            "life_script_bytes": life_size,
            "life_script_sha256": life_sha256,
            "life_script_analysis": life_analysis,
        }
        if anim3ds is not None:
            summary["anim3ds"] = anim3ds
        object_summaries.append(summary)

    checksum_offset = reader.index
    checksum = reader.u32()
    zones_offset = reader.index
    zone_count = reader.s16()
    zones = parse_scene_zones(reader, zone_count)
    tracks_offset = reader.index
    track_count = reader.s16()
    tracks = parse_scene_tracks(reader, track_count)
    for scene_object in object_summaries:
        movement = (scene_object.get("runtime") or {}).get("movement") or {}
        movement_info = scene_object_movement_info_semantics(
            move=int(scene_object.get("move", 0)),
            info=list(scene_object.get("info") or [0, 0, 0, 0]),
            object_count=object_count,
            track_count=track_count,
        )
        movement["references"] = movement_info["references"]
        movement["state_fields"] = movement_info["state_fields"]
    patches_offset = reader.index
    patch_count = reader.u32()
    patches = parse_scene_patches(reader, patch_count, script_ranges, script_instruction_map)
    trailing_bytes = len(payload) - reader.index
    if trailing_bytes < 0:
        raise Lm2Error("scene parser consumed past payload end")

    zone_type_counts: dict[str, int] = {}
    zone_effect_counts: dict[str, int] = {}
    zone_runtime_contract_counts: dict[str, int] = {}
    for zone in zones:
        type_name = str(zone["type_name"])
        zone_type_counts[type_name] = zone_type_counts.get(type_name, 0) + 1
        runtime = zone.get("runtime") or {}
        effect = str(runtime.get("effect") or "unknown")
        zone_effect_counts[effect] = zone_effect_counts.get(effect, 0) + 1
        for field, label in SCENE_ZONE_RUNTIME_CONTRACT_FIELDS.items():
            if field in runtime:
                zone_runtime_contract_counts[label] = (
                    zone_runtime_contract_counts.get(label, 0) + 1
                )
    object_render_type_counts: dict[str, int] = {}
    object_move_counts: dict[str, int] = {}
    object_flag_counts: dict[str, int] = {}
    object_render_pipeline_counts: dict[str, int] = {}
    object_render_contract_counts: dict[str, int] = {}
    object_redraw_method_counts: dict[str, int] = {}
    object_collision_counts: dict[str, int] = {}
    object_srot_conversion_counts: dict[str, int] = {}
    object_combat_counts: dict[str, int] = {}
    object_option_flag_counts: dict[str, int] = {}
    object_movement_reference_counts: dict[str, int] = {}
    object_movement_missing_reference_counts: dict[str, int] = {}
    object_movement_state_counts: dict[str, int] = {}
    for scene_object in object_summaries:
        runtime = scene_object.get("runtime") or {}
        render_type = str(runtime.get("render_type") or "unknown")
        object_render_type_counts[render_type] = object_render_type_counts.get(render_type, 0) + 1
        movement = runtime.get("movement") or {}
        move_name = str(movement.get("mode_name") or "unknown")
        object_move_counts[move_name] = object_move_counts.get(move_name, 0) + 1
        srot_conversion = str(movement.get("srot_conversion") or "unknown")
        object_srot_conversion_counts[srot_conversion] = (
            object_srot_conversion_counts.get(srot_conversion, 0) + 1
        )
        collision = runtime.get("collision") or {}
        for key, enabled in collision.items():
            if enabled:
                collision_name = str(key)
                object_collision_counts[collision_name] = (
                    object_collision_counts.get(collision_name, 0) + 1
                )
        combat = runtime.get("combat") or {}
        bonus = runtime.get("bonus") or {}
        life_points = int(combat.get("life_points") or 0)
        hit_force = int(combat.get("hit_force") or 0)
        armor = int(combat.get("armor") or 0)
        bonus_count = int(bonus.get("count") or 0)
        object_combat_counts["alive" if life_points > 0 else "dead_or_zero_life"] = (
            object_combat_counts.get(
                "alive" if life_points > 0 else "dead_or_zero_life", 0
            )
            + 1
        )
        if hit_force:
            object_combat_counts["hit_force_nonzero"] = (
                object_combat_counts.get("hit_force_nonzero", 0) + 1
            )
        if armor:
            object_combat_counts["armor_nonzero"] = (
                object_combat_counts.get("armor_nonzero", 0) + 1
            )
        if bonus_count:
            object_combat_counts["bonus_count_nonzero"] = (
                object_combat_counts.get("bonus_count_nonzero", 0) + 1
            )
        for flag in runtime.get("flags") or []:
            flag_name = str(flag)
            object_flag_counts[flag_name] = object_flag_counts.get(flag_name, 0) + 1
        render_pipeline = runtime.get("render_pipeline") or {}
        for effect in render_pipeline.get("effect_flags") or []:
            effect_name = str(effect)
            object_render_pipeline_counts[effect_name] = (
                object_render_pipeline_counts.get(effect_name, 0) + 1
            )
        for step in render_pipeline.get("contract_steps") or []:
            step_name = str(step)
            object_render_contract_counts[step_name] = (
                object_render_contract_counts.get(step_name, 0) + 1
            )
        redraw = render_pipeline.get("redraw_contract") or {}
        redraw_method = str(redraw.get("method") or "unknown")
        object_redraw_method_counts[redraw_method] = (
            object_redraw_method_counts.get(redraw_method, 0) + 1
        )
        for flag in runtime.get("option_flags") or []:
            flag_name = str(flag)
            object_option_flag_counts[flag_name] = (
                object_option_flag_counts.get(flag_name, 0) + 1
            )
        for reference in movement.get("references") or []:
            key = f"{move_name}.{reference.get('role')}"
            object_movement_reference_counts[key] = (
                object_movement_reference_counts.get(key, 0) + 1
            )
            if not reference.get("target_found"):
                object_movement_missing_reference_counts[key] = (
                    object_movement_missing_reference_counts.get(key, 0) + 1
                )
        for state_field in movement.get("state_fields") or []:
            key = f"{move_name}.{state_field.get('role')}"
            object_movement_state_counts[key] = (
                object_movement_state_counts.get(key, 0) + 1
            )
    patch_size_counts: dict[str, int] = {}
    patch_target_counts: dict[str, int] = {}
    patch_instruction_counts: dict[str, int] = {}
    patch_instruction_byte_counts: dict[str, int] = {}
    patch_field_counts: dict[str, int] = {}
    patch_field_source_counts: dict[str, int] = {}
    patch_instruction_field_counts: dict[str, int] = {}
    for patch in patches:
        size_key = str(patch["size"])
        patch_size_counts[size_key] = patch_size_counts.get(size_key, 0) + 1
        target = patch.get("target") or {}
        kind = str(target.get("kind") or "unknown")
        patch_target_counts[kind] = patch_target_counts.get(kind, 0) + 1
        if target.get("instruction_found"):
            opcode = str(target.get("instruction_opcode") or "unknown")
            patch_instruction_counts[opcode] = patch_instruction_counts.get(opcode, 0) + 1
            byte_key = "opcode_byte" if target.get("hits_opcode_byte") else "operand_byte"
        else:
            byte_key = "missing_instruction"
        patch_instruction_byte_counts[byte_key] = patch_instruction_byte_counts.get(byte_key, 0) + 1
        field_key = str(target.get("patched_field") or "unknown_field")
        patch_field_counts[field_key] = patch_field_counts.get(field_key, 0) + 1
        source_key = str(target.get("patched_field_source") or "unknown_source")
        patch_field_source_counts[source_key] = patch_field_source_counts.get(source_key, 0) + 1
        if target.get("instruction_found") and target.get("patched_field"):
            opcode = str(target.get("instruction_opcode") or "unknown")
            instruction_field = f"{opcode}.{field_key}"
            patch_instruction_field_counts[instruction_field] = (
                patch_instruction_field_counts.get(instruction_field, 0) + 1
            )

    local_link_counts: dict[str, int] = {"object": 0, "waypoint": 0, "zone": 0}
    cross_link_counts: dict[str, int] = {
        "links": 0,
        "found": 0,
        "missing": 0,
        "track": 0,
        "life": 0,
        "missing_owner": 0,
    }
    cross_link_target_status_counts: dict[str, int] = {}
    objects_by_index = {int(scene_object["index"]): scene_object for scene_object in object_summaries}
    owners_by_index = {0: hero, **objects_by_index}
    zones_by_index = {int(zone["index"]): zone for zone in zones}
    tracks_by_index = {int(track["index"]): track for track in tracks}
    for owner_name, owner in [
        ("hero", hero),
        *[(scene_owner_name(int(scene_object["index"])), scene_object) for scene_object in object_summaries],
    ]:
        counts = add_scene_script_local_links(
            owner, objects_by_index, zones_by_index, tracks_by_index
        )
        for key, count in counts.items():
            local_link_counts[key] = local_link_counts.get(key, 0) + count
        cross_counts = add_scene_script_cross_links(
            owner, owner_name, owners_by_index, script_instruction_map
        )
        for key, count in cross_counts.items():
            cross_link_counts[key] = cross_link_counts.get(key, 0) + count
        add_script_link_target_status_counts(
            cross_link_target_status_counts,
            owner.get("life_script_analysis"),
            "cross_script_links",
        )

    text_message_zones = [
        zone
        for zone in zones
        if (zone.get("runtime") or {}).get("effect") == "show_message"
    ]
    message_camera_links = scene_message_camera_links(zones)
    message_camera_link_counts = {
        "links": len(message_camera_links),
        "found": sum(1 for link in message_camera_links if link.get("target_available")),
        "missing": sum(1 for link in message_camera_links if not link.get("target_available")),
    }
    grm_fragment_zones = [
        zone
        for zone in zones
        if (zone.get("runtime") or {}).get("effect") == "toggle_grm_fragment"
    ]

    return {
        "world": world,
        "ambience": ambience,
        "hero": hero,
        "objects_offset": objects_offset,
        "object_count": object_count,
        "scene_frame_render_contract": scene_frame_render_contract(object_count),
        "objects": object_summaries,
        "object_record_count": len(object_summaries),
        "sampled_objects": object_summaries[:24],
        "sampled_object_count": len(object_summaries),
        "object_render_type_counts": object_render_type_counts,
        "object_render_pipeline_counts": object_render_pipeline_counts,
        "object_render_contract_counts": object_render_contract_counts,
        "object_redraw_method_counts": object_redraw_method_counts,
        "object_collision_counts": object_collision_counts,
        "object_srot_conversion_counts": object_srot_conversion_counts,
        "object_combat_counts": object_combat_counts,
        "object_move_counts": object_move_counts,
        "object_flag_counts": object_flag_counts,
        "object_option_flag_counts": object_option_flag_counts,
        "object_movement_reference_counts": object_movement_reference_counts,
        "object_movement_missing_reference_counts": object_movement_missing_reference_counts,
        "object_movement_state_counts": object_movement_state_counts,
        "script_behavior_counts": script_behavior_counts,
        "script_control_flow_counts": script_control_flow_counts,
        "script_control_flow_target_status_counts": script_control_flow_target_status_counts,
        "script_runtime_state_counts": script_runtime_state_counts,
        "script_runtime_instruction_state_counts": script_runtime_instruction_state_counts,
        "script_execution_contract_counts": script_execution_contract_counts,
        "script_condition_function_counts": script_condition_function_counts,
        "script_condition_return_type_counts": script_condition_return_type_counts,
        "script_condition_comparator_counts": script_condition_comparator_counts,
        "script_skipped_byte_counts": script_skipped_byte_counts,
        "script_cross_link_counts": cross_link_counts,
        "script_cross_link_target_status_counts": cross_link_target_status_counts,
        "script_local_link_counts": local_link_counts,
        "sprite_object_count": sprite_objects,
        "anim3ds_object_count": anim3ds_objects,
        "checksum_offset": checksum_offset,
        "checksum": checksum,
        "zones_offset": zones_offset,
        "zone_count": zone_count,
        "zone_record_bytes": SCENE_ZONE_RECORD_BYTES,
        "zone_type_counts": zone_type_counts,
        "zone_effect_counts": zone_effect_counts,
        "zone_runtime_contract_counts": zone_runtime_contract_counts,
        "zones": zones,
        "sampled_zones": zones[:24],
        "sampled_zone_count": len(zones),
        "text_message_zones": text_message_zones,
        "message_camera_links": message_camera_links,
        "message_camera_link_counts": message_camera_link_counts,
        "grm_fragment_zones": grm_fragment_zones,
        "tracks_offset": tracks_offset,
        "track_count": track_count,
        "track_record_bytes": SCENE_TRACK_RECORD_BYTES,
        "tracks": tracks,
        "sampled_tracks": tracks[:24],
        "sampled_track_count": len(tracks),
        "patches_offset": patches_offset,
        "patch_count": patch_count,
        "patch_record_bytes": SCENE_PATCH_RECORD_BYTES,
        "patch_size_counts": patch_size_counts,
        "patch_target_counts": patch_target_counts,
        "patch_instruction_counts": patch_instruction_counts,
        "patch_instruction_byte_counts": patch_instruction_byte_counts,
        "patch_field_counts": patch_field_counts,
        "patch_field_source_counts": patch_field_source_counts,
        "patch_instruction_field_counts": patch_instruction_field_counts,
        "patches": patches,
        "sampled_patches": patches[:32],
        "sampled_patch_count": len(patches),
        "bytes_consumed": reader.index,
        "bytes_consumed_before_patches": patches_offset + 4,
        "trailing_patch_bytes": trailing_bytes,
    }


CATALOG_SCRIPT_LIST_SAMPLE_LIMITS = {
    "control_flow_links": 12,
    "cross_script_links": 12,
    "local_links": 12,
    "asset_links": 16,
    "first_instructions": 12,
    "unique_opcodes": 24,
    "runtime_state_fields": 12,
    "execution_contracts": 12,
    "condition_functions": 12,
    "condition_comparators": 12,
    "label_definitions": 12,
}


def compact_scene_script_analysis_for_catalog(script: dict[str, Any]) -> None:
    truncated: dict[str, dict[str, int]] = {}
    for key, limit in CATALOG_SCRIPT_LIST_SAMPLE_LIMITS.items():
        value = script.get(key)
        if not isinstance(value, list):
            continue
        total = len(value)
        script[f"{key}_total"] = total
        if total > limit:
            script[key] = value[:limit]
            truncated[key] = {"total": total, "sampled": limit}
    if truncated:
        script["catalog_truncated_lists"] = truncated


def compact_scene_catalog_payload(catalog: dict[str, Any]) -> None:
    for asset in catalog.get("assets", []):
        if asset.get("kind") != "scene":
            continue
        reconnaissance = (asset.get("stats") or {}).get("reconnaissance") or {}
        objects = reconnaissance.get("objects") or []
        if isinstance(objects, list):
            reconnaissance["object_record_count"] = len(objects)
            reconnaissance["sampled_objects"] = objects[:24]
            reconnaissance["sampled_object_count"] = len(objects)
            if len(objects) > 24:
                reconnaissance["catalog_sampled_object_limit"] = 24
            else:
                reconnaissance.pop("catalog_sampled_object_limit", None)
        zones = reconnaissance.get("zones")
        if isinstance(zones, list):
            reconnaissance["sampled_zones"] = zones[:24]
            reconnaissance["sampled_zone_count"] = len(zones)
        tracks = reconnaissance.get("tracks")
        if isinstance(tracks, list):
            reconnaissance["sampled_tracks"] = tracks[:24]
            reconnaissance["sampled_track_count"] = len(tracks)
        patches = reconnaissance.get("patches")
        if isinstance(patches, list):
            reconnaissance["sampled_patches"] = patches[:32]
            reconnaissance["sampled_patch_count"] = len(patches)
        owners = [
            reconnaissance.get("hero") or {},
            *(objects if isinstance(objects, list) else []),
        ]
        for owner in owners:
            for script_key in ("track_script_analysis", "life_script_analysis"):
                script = owner.get(script_key)
                if isinstance(script, dict):
                    compact_scene_script_analysis_for_catalog(script)


def scene_catalog_stats(payload: bytes) -> dict[str, Any]:
    descriptors: list[dict[str, Any]] = []
    try:
        reconnaissance = parse_scene_reconnaissance(payload)
        parse_status = "partial"
        decode_status = "partial"
        decode_note = (
            "Decoded SCENE.HQR top-level runtime layout from classic LoadScene: "
            "world header, ambience, hero scripts, object records, checksum, zones, "
            "waypoints, and patch records. Script bytecode is structurally classified "
            "and grouped into mechanic categories with selected operand semantics, "
            "condition-function/comparator counts, and source-backed execution contracts; "
            "classic zone mechanics expose "
            "source-backed runtime contracts; full script behavior execution remains "
            "raw evidence."
        )
        parsed_end = min(
            reconnaissance.get("bytes_consumed", len(payload)),
            len(payload),
        )
        if parsed_end:
            descriptors.append(
                unknown_bytes_descriptor(
                    payload,
                    section="scene_parsed_prefix",
                    offset=0,
                    length=parsed_end,
                    confidence="parsed_unknown",
                    note=(
                        "Top-level SCENE layout is walked, but many individual fields "
                        "still need semantic names beyond the classic loader assignment."
                    ),
                    related_fields=[
                        "world",
                        "ambience",
                        "hero",
                        "object_count",
                        "zone_count",
                        "track_count",
                        "patch_count",
                    ],
                )
            )
        trailing = len(payload) - parsed_end
        if trailing:
            descriptors.append(
                unknown_bytes_descriptor(
                    payload,
                    section="scene_patch_payload",
                    offset=parsed_end,
                    length=trailing,
                    confidence="high",
                    note="Bytes after decoded T_PATCH records are preserved as raw evidence.",
                    related_fields=["patch_count"],
                )
            )
        if not descriptors:
            descriptors.append(
                unknown_bytes_descriptor(
                    payload,
                    section="empty_scene_payload",
                    offset=0,
                    length=0,
                    confidence="high",
                    note="Empty SCENE payload.",
                )
            )
    except Lm2Error as exc:
        reconnaissance = {}
        parse_status = "raw"
        decode_status = "parse_failed"
        decode_note = f"SCENE.HQR top-level reconnaissance failed; retained raw payload evidence: {exc}"
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="scene_payload",
                offset=0,
                length=len(payload),
                confidence="high",
                note="Opaque SCENE payload bytes retained only as a descriptor hash.",
            )
        )

    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": parse_status,
        "decode_status": decode_status,
        "decode_note": decode_note,
        "semantic_layout": "scene_runtime_layout_partial",
        "reconnaissance": reconnaissance,
        "unknown_descriptors": descriptors,
    }


def parse_lsp_sprite_frame(payload: bytes) -> dict[str, Any]:
    if len(payload) < 12:
        raise Lm2Error(f"LSP sprite payload is too small: {len(payload)} bytes")
    width = payload[8]
    height = payload[9]
    offset_x = payload[10]
    offset_y = payload[11]
    if width <= 0 or height <= 0:
        raise Lm2Error(f"LSP sprite has invalid dimensions: {width}x{height}")

    pixels = [0] * (width * height)
    ptr = 12
    for y in range(height):
        if ptr >= len(payload):
            raise Lm2Error(f"LSP sprite ended before row {y} run count")
        run_count = payload[ptr]
        ptr += 1
        x = 0
        for run_index in range(run_count):
            if ptr >= len(payload):
                raise Lm2Error(f"LSP sprite ended before row {y} run {run_index}")
            run_spec = payload[ptr]
            ptr += 1
            run_length = (run_spec & 0x3F) + 1
            run_type = (run_spec >> 6) & 0x03
            if x + run_length > width:
                raise Lm2Error(
                    f"LSP sprite row {y} run {run_index} exceeds width {width}"
                )
            if run_type == 0:
                x += run_length
                continue
            if run_type == 2:
                if ptr >= len(payload):
                    raise Lm2Error(f"LSP sprite ended before fill color at row {y}")
                color = payload[ptr]
                ptr += 1
                for _ in range(run_length):
                    pixels[(y * width) + x] = color
                    x += 1
                continue
            if ptr + run_length > len(payload):
                raise Lm2Error(f"LSP sprite ended inside literal run at row {y}")
            for _ in range(run_length):
                pixels[(y * width) + x] = payload[ptr]
                ptr += 1
                x += 1
        if x > width:
            raise Lm2Error(f"LSP sprite row {y} decoded past width {width}")

    colors = sorted(set(pixels))
    return {
        "format": "lsp_sprite",
        "width": width,
        "height": height,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "pixels": pixels,
        "encoded_bytes_consumed": ptr,
        "trailing_bytes": len(payload) - ptr,
        "opaque_pixels": sum(1 for pixel in pixels if pixel != 0),
        "transparent_pixels": sum(1 for pixel in pixels if pixel == 0),
        "color_count": len(colors),
        "palette_indices": colors,
    }


def parse_raw_sprite_frame(payload: bytes) -> dict[str, Any]:
    if len(payload) < 12:
        raise Lm2Error(f"raw sprite payload is too small: {len(payload)} bytes")
    width = payload[8]
    height = payload[9]
    offset_x = struct.unpack_from("<b", payload, 10)[0]
    offset_y = struct.unpack_from("<b", payload, 11)[0]
    if width <= 0 or height <= 0:
        raise Lm2Error(f"raw sprite has invalid dimensions: {width}x{height}")
    pixel_count = width * height
    expected = 12 + pixel_count
    if len(payload) < expected:
        raise Lm2Error(
            f"raw sprite payload is shorter than {width}x{height} pixels: {len(payload)} bytes"
        )
    pixels = list(payload[12:expected])
    colors = sorted(set(pixels))
    return {
        "format": "raw_sprite",
        "width": width,
        "height": height,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "pixels": pixels,
        "encoded_bytes_consumed": expected,
        "trailing_bytes": len(payload) - expected,
        "opaque_pixels": sum(1 for pixel in pixels if pixel != 0),
        "transparent_pixels": sum(1 for pixel in pixels if pixel == 0),
        "color_count": len(colors),
        "palette_indices": colors,
    }


def sprite_frame_catalog_stats(
    payload: bytes,
    *,
    backend: str,
    runtime_index: int,
    zv_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sprite = (
        parse_raw_sprite_frame(payload)
        if backend == "spriraw"
        else parse_lsp_sprite_frame(payload)
    )
    semantic_layout = "raw_sprite_frame" if backend == "spriraw" else "lsp_sprite_frame"
    descriptor_section = (
        "raw_sprite_header_prefix" if backend == "spriraw" else "lsp_header_prefix"
    )
    descriptor_note = (
        "Raw scaled sprite bytes before width/height/offset fields are not yet semantically named."
        if backend == "spriraw"
        else "LSP bytes before width/height/offset fields are not yet semantically named."
    )
    descriptors: list[dict[str, Any]] = [
        unknown_bytes_descriptor(
            payload,
            section=descriptor_section,
            offset=0,
            length=8,
            confidence="medium",
            note=descriptor_note,
        )
    ]
    if sprite["trailing_bytes"]:
        descriptors.append(
            unknown_bytes_descriptor(
                payload,
                section="trailing_bytes",
                offset=sprite["encoded_bytes_consumed"],
                length=sprite["trailing_bytes"],
                confidence="medium",
                note="Bytes after decoded LSP rows are preserved as a descriptor hash.",
            )
        )
    label = sprite_backend_label(backend)
    runtime = sprite_archive_runtime_info(backend, runtime_index)
    if zv_record is not None:
        runtime["hotspot"] = zv_record["hotspot"]
        runtime["bounds"] = zv_record["bounds"]
        runtime["bounds_source"] = zv_record["source"]
    direct_references = direct_sprite_code_references(backend, runtime_index)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "decoded",
        "decode_status": "decoded",
        "decode_note": f"Decoded {label} entry as a {sprite['format']} payload.",
        "semantic_layout": semantic_layout,
        "format": sprite["format"],
        "sprite_backend": backend,
        "runtime": runtime,
        "direct_code_references": direct_references,
        "direct_reference_count": len(direct_references),
        "width": sprite["width"],
        "height": sprite["height"],
        "offset_x": sprite["offset_x"],
        "offset_y": sprite["offset_y"],
        "encoded_bytes_consumed": sprite["encoded_bytes_consumed"],
        "trailing_bytes": sprite["trailing_bytes"],
        "opaque_pixels": sprite["opaque_pixels"],
        "transparent_pixels": sprite["transparent_pixels"],
        "color_count": sprite["color_count"],
        "palette_indices": sprite["palette_indices"],
        "unknown_descriptors": descriptors,
    }


def anim3ds_frame_catalog_stats(payload: bytes) -> dict[str, Any]:
    return sprite_frame_catalog_stats(payload, backend="anim3ds", runtime_index=0)


def anim3ds_runtime_playback_info() -> dict[str, Any]:
    return {
        "range_table_source": "PERSO.CPP::LoadListAnim3DS loads the final ANIM3DS.HQR entry as a T_ANIM_3DS table.",
        "range_record_layout": "COMMON.H T_ANIM_3DS stores Name[4], Deb start frame, and Fin end frame.",
        "scene_initialization": "DISKFUNC.CPP reads ANIM_3DS object A3DS.Num plus Info3/SizeSHit as NbFps; OBJECT.CPP initializes Deb from the scene Sprite and Fin from ListAnim3DS[Num].Fin.",
        "advance_rule": "OBJECT.CPP advances the object Sprite from Deb to Fin using elapsed TimerRefHR and total_time=(abs(Fin-Deb)+1)*1000/NbFps, then wraps to Deb and resets the timer.",
        "reverse_rule": "If Fin is less than Deb, the same OBJECT.CPP rule plays backward and wraps back to Deb after crossing Fin.",
        "track_controls": {
            "TM_SET_FRAME_3DS": "Clamp a relative frame to the selected T_ANIM_3DS range, add Deb, then InitSprite.",
            "TM_SET_START_3DS": "Clamp a relative frame to the selected range, add Deb, then replace Coord.A3DS.Deb.",
            "TM_SET_END_3DS": "Clamp a relative frame to the selected range, add Deb, then replace Coord.A3DS.Fin.",
            "TM_START_ANIM_3DS": "InitSprite at Deb, set SizeSHit to the opcode FPS operand, and store TimerRefHR as the animation start time.",
            "TM_STOP_ANIM_3DS": "Set SizeSHit to zero, stopping automatic frame advancement.",
            "TM_WAIT_ANIM_3DS": "Hold the track script while Sprite is not Fin and SizeSHit is nonzero.",
            "TM_WAIT_FRAME_3DS": "Hold the track script until Sprite reaches the clamped relative target frame.",
        },
        "timing_source": "The T_ANIM_3DS table has no frame durations; scene object Info3 and TM_START_ANIM_3DS provide FPS.",
    }


def parse_anim3ds_info(payload: bytes) -> list[dict[str, Any]]:
    if len(payload) == 0:
        raise Lm2Error("ANIM3DS info table is empty")
    if len(payload) % 8 != 0:
        raise Lm2Error(
            f"ANIM3DS info table length {len(payload)} is not a multiple of 8"
        )
    entries: list[dict[str, Any]] = []
    for index, offset in enumerate(range(0, len(payload), 8)):
        name_bytes = payload[offset : offset + 4]
        start_frame, end_frame = struct.unpack_from("<hh", payload, offset + 4)
        if start_frame < 0 or end_frame < start_frame:
            raise Lm2Error(
                f"invalid ANIM3DS frame range at info entry {index}: "
                f"{start_frame}..{end_frame}"
            )
        entries.append(
            {
                "index": index,
                "name": name_bytes.decode("ascii", errors="replace").rstrip("\x00 "),
                "name_bytes": list(name_bytes),
                "start_frame": start_frame,
                "end_frame": end_frame,
                "frame_count": end_frame - start_frame + 1,
            }
        )
    return entries


def anim3ds_info_catalog_stats(
    payload: bytes, range_warnings: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    entries = parse_anim3ds_info(payload)
    return {
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "parse_status": "metadata",
        "decode_status": "decoded",
        "decode_note": (
            "Decoded classic T_ANIM_3DS frame ranges; ANIM3DS frames are LSP "
            "sprite frames, not skeletal BODY animations."
        ),
        "semantic_layout": "anim3ds_frame_ranges",
        "entry_count": len(entries),
        "entries": entries,
        "frame_min": min(entry["start_frame"] for entry in entries),
        "frame_max": max(entry["end_frame"] for entry in entries),
        "frame_total": sum(entry["frame_count"] for entry in entries),
        "range_warnings": range_warnings or [],
        "runtime_reference_status": "classic ANIM_3DS runtime range table with FPS supplied by scene object state or TM_START_ANIM_3DS",
        "source_provenance": "COMMON.H T_ANIM_3DS/TM_*_3DS definitions; PERSO.CPP LoadListAnim3DS; DISKFUNC.CPP ANIM_3DS object load; GERETRAK.CPP TM_SET_FRAME_3DS/TM_START_ANIM_3DS/TM_WAIT_ANIM_3DS; OBJECT.CPP frame advancement.",
        "runtime_playback": anim3ds_runtime_playback_info(),
    }


def anim3ds_frame_lookup(info_entries: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for info_entry in info_entries:
        for frame in range(info_entry["start_frame"], info_entry["end_frame"] + 1):
            lookup[frame] = info_entry
    return lookup


def anim3ds_range_by_index(catalog: dict[str, Any]) -> dict[int, dict[str, Any]]:
    try:
        info_asset = find_catalog_asset(catalog, f"{ANIM3DS_ARCHIVE_NAME}:{ANIM3DS_INFO_ENTRY_INDEX}")
    except Lm2Error:
        return {}
    stats = info_asset.get("stats") or {}
    if stats.get("semantic_layout") != "anim3ds_frame_ranges":
        return {}
    return {
        int(entry["index"]): entry
        for entry in stats.get("entries", [])
        if "index" in entry
    }


def validate_anim3ds_frame_ranges(
    info_entries: list[dict[str, Any]], available_frames: set[int]
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for info_entry in info_entries:
        missing = [
            frame
            for frame in range(info_entry["start_frame"], info_entry["end_frame"] + 1)
            if frame not in available_frames
        ]
        if missing:
            warnings.append(
                {
                    "animation_index": info_entry["index"],
                    "name": info_entry["name"],
                    "missing_frames": missing,
                    "note": "ANIM3DS frame range references missing or empty HQR entries.",
                }
            )
    return warnings


HQR_COVERAGE_PROFILES: dict[str, dict[str, str]] = {
    "ANIM.HQR": {
        "runtime_purpose": "Skeletal BODY animation records used by runtime generic/action animation slots.",
        "parser_support": "Decoded LBA2 animation records; parse failures are retained as raw evidence.",
        "viewer_support": "Playable on compatible BODY.HQR models through the model canvas.",
        "export_support": "Animation evidence JSON through the animation command.",
        "default_status": "covered",
        "next_required_evidence": "Broaden real-asset sampling for unusual animation flags and root-motion edge cases.",
    },
    "ANIM3DS.HQR": {
        "runtime_purpose": "Projected 3D sprite animation frames plus the classic T_ANIM_3DS range table.",
        "parser_support": "Decodes LSP sprite frames, the frame-range metadata table, and classic FPS-driven playback rules from scene object state plus TM_*_3DS track controls.",
        "viewer_support": "Sprite View can scrub decoded range frames; catalog detail explains ANIM3DS runtime playback timing and scene usage links expose object FPS.",
        "export_support": "Sprite PNG export writes the selected ANIM3DS range as per-frame PNGs plus a deterministic sheet manifest.",
        "default_status": "partial",
        "next_required_evidence": "Use live runtime only if a specific ANIM3DS object shows timing behavior that differs from the classic FPS-driven Sprite advancement rule.",
    },
    "BODY.HQR": {
        "runtime_purpose": "Animated actor BODY meshes referenced by File3D and scene object records.",
        "parser_support": "Decoded LM2 model geometry and bounds.",
        "viewer_support": "Model canvas with animation pairing and UV inspector.",
        "export_support": "OBJ/MTL plus evidence manifest.",
        "default_status": "covered",
        "next_required_evidence": "Audit model flags with live runtime usage when a flag affects port behavior.",
    },
    "HOLOMAP.HQR": {
        "runtime_purpose": "Holomap globe, plan-screen, marker/objective, and vehicle/arrow model resources.",
        "parser_support": "Classic zero-based indexing; decodes globe UV map, globe altitude maps, globe texture maps, T_ARROW marker table with GAME text links, plan-screen images, plan view parameter records, and LM2 model entries.",
        "viewer_support": "Catalog detail for decoded holomap tables/images, marker text links, Sprite View plan-screen previews with RESS.HQR:0, and model canvas for recognized LM2 entries.",
        "export_support": "OBJ export for recognized model entries; plan-screen image PNG export with manifests preserving variant and paired parameter provenance.",
        "default_status": "partial",
        "next_required_evidence": "Promote holomap globe rendering only if the port needs original globe projection behavior beyond decoded source tables.",
    },
    "LBA2.HQR": {
        "runtime_purpose": "Archive present in the asset set but empty in this installation.",
        "parser_support": "No non-empty entries to parse.",
        "viewer_support": "None.",
        "export_support": "None.",
        "default_status": "empty",
        "next_required_evidence": "None for the current asset set.",
    },
    "LBA_BKG.HQR": {
        "runtime_purpose": "Background grid archive: header ranges, cube grid maps, GRM fragments, block tables, brick graphics, and cube indirection.",
        "parser_support": "Classic zero-based indexing; decodes T_BKG_HEADER ranges, GRI map headers/column offsets and compressed column composition, GRM dimensions/cell composition, BLL block tables with cell-to-BRK links, BRK AffGraph command streams, and T_TABALLCUBE.",
        "viewer_support": "Catalog detail for decoded background runtime tables, GRI column composition, GRM fragment composition, and BLL cell BRK references; Sprite View previews individual BRK AffGraph frames with an explicit palette-context caveat.",
        "export_support": "GRI grid resources export a JSON composition manifest, flat block-ref/slot arrays, and a 640x480 evidence preview PNG; scene backgrounds export base plus explicit GRM-on composition/preview variants.",
        "default_status": "partial",
        "next_required_evidence": "Confirm remaining object/decor overdraw and z-buffer/mask passes before treating previews as final renderer output.",
    },
    "OBJFIX.HQR": {
        "runtime_purpose": "Fixed object LM2 models loaded by GivePtrObjFix for extras, darts, inventory/incrust displays, and selected fixed 3D UI objects.",
        "parser_support": "Classic zero-based HQR indexing, decoded LM2 model geometry and bounds, and direct GivePtrObjFix reference provenance for known inventory/extra/dart ids.",
        "viewer_support": "Model canvas, UV inspector, and catalog detail with direct code-reference provenance.",
        "export_support": "OBJ/MTL plus evidence manifest.",
        "default_status": "covered",
        "next_required_evidence": "Broaden direct reference mapping only if remaining anonymous fixed objects become port/editor blockers.",
    },
    "RESS.HQR": {
        "runtime_purpose": "Shared resources including palette, XPL ambience palette bundles, texture atlas, File3D table, sprite bounds/hotspots, RESS_FLOW/RESS_POF/RESS_IMPACT runtime effect tables, ACF movie list, exterior sizing info, and mixed payloads.",
        "parser_support": "First-class palette, XPL palette bundle, indexed atlas/image, File3D, sprite ZV table, named RESS_FLOW fixed signed-word table, named RESS_POF/RESS_IMPACT offset-record tables, ACF name list, exterior size info, raw unclassified payload evidence for future unknowns, and LM2 auto-detection for model-like entries.",
        "viewer_support": "Catalog detail for runtime tables, XPL bundles, ACF names, indexed image payloads, and raw unclassified payload evidence; Sprite View renders indexed image and texture-atlas payloads with RESS.HQR:0; palette/atlas/metadata feed other viewers; recognized model entries render.",
        "export_support": "Model exports include palette/atlas evidence when available; indexed image and texture-atlas payloads export as paired-palette PNGs with manifests.",
        "default_status": "partial",
        "next_required_evidence": "Confirm XPL shade/fog/transparency internals if renderer-level palette effects become necessary; entry 38 runtime selection is explained by scene island palette links.",
    },
    "SAMPLES.HQR": {
        "runtime_purpose": "Audio samples loaded by zero-based runtime sample IDs.",
        "parser_support": "Decodes classic HQR resource compression and parses RIFF/WAVE metadata for PCM and IMA ADPCM samples.",
        "viewer_support": "Catalog detail for sample format/rate/duration, reverse scene script/ambience usage, and browser audio preview through the decoded WAVE container.",
        "export_support": "Decoded RIFF/WAVE export with manifest preserving runtime id, HQR table index, resource header, and audio metadata.",
        "default_status": "partial",
        "next_required_evidence": "Local extracted/reference variants all have the same empty scene-referenced sample slots; add PCM decode only if consistent waveform tooling becomes necessary.",
    },
    "SCENE.HQR": {
        "runtime_purpose": "Scene runtime payloads: world header, ambience, hero start/scripts, objects, zones, waypoints, and patches.",
        "parser_support": "Partial top-level reconnaissance based on classic LoadScene with object links to File3D, BODY, ANIM, sprites, TEXT records, SAMPLES records, LBA_BKG TabAllCube/GRI/BLL/GRM records, and concrete GRM fragment entries; object render-pipeline flags are named from COMMON.H/OBJECT.CPP draw paths; zone runtime mechanics include LoadScene post-load state normalization, SetZoneCamera application rules, message-zone camera links and facing-angle gates, and script controls for GRM/change-cube/camera/ladder/escalator/hit/rail zones; track/life scripts get opcode, mechanic-category, operand, condition-function/comparator counts, source-backed execution-contract counts, nested switch/case sizing, hybrid linear-plus-target decoding, same-script control-flow target status, scene-context cross-script target status, and scene-text target classification; patch records resolve to containing script instructions but no full behavior execution semantics.",
        "viewer_support": "Catalog search/detail inspection with object links, render-pipeline flag counts, script opcode/control-flow/cross-script target-status summaries, text/sample/background/GRM-link counts, zone summaries, waypoint samples, patch targets, and Sprite View background variants for base plus explicit GRM-on states.",
        "export_support": "Scene background exports write a base GRI composition/preview plus one explicit GRM-on composition/preview per resolved GRM zone; no live script state is guessed.",
        "default_status": "partial",
        "next_required_evidence": "Promote script and zone execution semantics where evidence supports it; renderer work still needs actual object/decor overdraw and mask/z-buffer behavior beyond named flag effects.",
    },
    "SCREEN.HQR": {
        "runtime_purpose": "Screen/menu PCX-like resources stored as indexed framebuffers plus paired palettes.",
        "parser_support": "Uses classic zero-based PCR indexing; classifies even 640x480 indexed framebuffer payloads and odd 768-byte RGB palettes with pair provenance, plus named PCR direct code references for menu/logo/slate call sites.",
        "viewer_support": "Catalog detail for decoded SCREEN palettes and indexed images with direct code-reference provenance; Sprite View renders indexed framebuffers with their paired PCR palettes.",
        "export_support": "Paired-palette PNG export with manifest preserving PCR index, palette pair, and source hashes.",
        "default_status": "partial",
        "next_required_evidence": "Broaden SCREEN call-site provenance only if UI port work needs dynamic ListArdoise/help-screen selection rules.",
    },
    "SPRIRAW.HQR": {
        "runtime_purpose": "Normal projected sprite frames selected by runtime Sprite values below 100.",
        "parser_support": "Classic zero-based indexing; decoded raw scaled sprite frames plus runtime bounds/hotspots when RESS tables are present.",
        "viewer_support": "Sprite View renders decoded frames.",
        "export_support": "Sprite PNG export writes the selected frame plus a deterministic one-cell sheet manifest.",
        "default_status": "partial",
        "next_required_evidence": "Confirm any remaining direct code-driven raw sprite uses outside scene objects and extras.",
    },
    "SPRITES.HQR": {
        "runtime_purpose": "Normal projected sprite frames selected by runtime Sprite values 100 and above, plus low system/UI sprite entries addressed directly through HQRPtrSprite.",
        "parser_support": "Classic zero-based indexing; decoded LSP sprite frames plus runtime bounds/hotspots when RESS tables are present.",
        "viewer_support": "Sprite View renders decoded frames.",
        "export_support": "Sprite PNG export writes the selected frame plus a deterministic one-cell sheet manifest.",
        "default_status": "partial",
        "next_required_evidence": "Map direct code-driven UI/system sprite references if port UI provenance needs them.",
    },
    "TEXT.HQR": {
        "runtime_purpose": "Dialogue/text resources grouped by language and text file. Each runtime InitDial(file) uses a paired order table and text payload bank.",
        "parser_support": "Classifies classic zero-based BufOrder U16 message-id tables and paired BufText banks with U16 offset tables, FlagDial byte, and dialog byte strings.",
        "viewer_support": "Catalog detail for language/file pair metadata, message counts, offset-table bounds, flag counts, sampled decoded text previews, and reverse scene usage on linked text banks.",
        "export_support": "Text payload bank export writes a port-ready JSON bundle with message ids, FlagDial bytes, decoded CP850 text, raw record bytes, and paired order-table provenance.",
        "default_status": "partial",
        "next_required_evidence": "Connect remaining menu/inventory calls to concrete TEXT.HQR language/file/message records if port UI provenance needs call-site links.",
    },
    "VIDEO.HQR": {
        "runtime_purpose": "Smacker/ACF cinematic resources selected by zero-based names from RESS.HQR:48.",
        "parser_support": "Decodes HQR resource headers and Smacker container headers, names entries through the ACF list, and links scene PLAY_ACF script refs where available.",
        "viewer_support": "Catalog detail for movie name, zero-based runtime index, dimensions, frame count, timing estimate, resource header, and reverse scene usage.",
        "export_support": "Smacker container passthrough export with manifest preserving ACF index/name, header metadata, scene usages, source hashes, and the original codec-owned bytes.",
        "default_status": "partial",
        "next_required_evidence": "Add codec frame/audio decode only if port video playback work needs decoded frames or audio tracks.",
    },
}


def hqr_coverage_key(path: str) -> str:
    return Path(path).name.upper()


def coverage_formats(file_summary: dict[str, Any]) -> list[str]:
    formats: list[str] = []
    if file_summary.get("models"):
        formats.append("lm2-model")
    if file_summary.get("decoded_animations"):
        formats.append("lba2-animation")
    if file_summary.get("raw_animations"):
        formats.append("raw-animation-evidence")
    if file_summary.get("sprite_frames"):
        formats.extend(file_summary.get("sprite_formats") or ["lsp-sprite-frame"])
    if file_summary.get("sprite_metadata"):
        formats.append("anim3ds-range-table")
    if file_summary.get("scenes"):
        formats.append("scene-runtime-layout-partial")
        formats.append("scene-object-movement-info")
        formats.append("scene-object-render-pipeline")
        formats.append("scene-object-render-contract")
        formats.append("scene-runtime-draw-sources")
        formats.append("scene-script-opcode-layout")
        formats.append("scene-script-behavior-partial")
        formats.append("scene-script-operand-semantics-partial")
        formats.append("scene-script-execution-contracts")
        formats.append("scene-script-condition-functions")
        formats.append("scene-script-condition-comparators")
        formats.append("scene-script-control-flow-links")
        formats.append("scene-script-cross-links")
        formats.append("scene-zone-track-patch-layout")
        formats.append("scene-patch-instruction-links")
        formats.append("scene-patch-field-links")
        formats.append("scene-zone-behavior-partial")
        formats.append("scene-zone-change-cube-contract")
        formats.append("scene-message-facing-gates")
        formats.append("scene-zone-bonus-contract")
        formats.append("scene-zone-hit-contract")
        formats.append("scene-zone-movement-contracts")
        formats.append("scene-zone-grm-contract")
        formats.append("scene-zone-scenario-contract")
        if file_summary.get("script_linked_text_refs") or file_summary.get("zone_linked_text_refs"):
            formats.append("scene-text-record-links")
        if file_summary.get("script_linked_sample_refs") or file_summary.get("ambience_linked_sample_refs"):
            formats.append("scene-sample-audio-links")
        if file_summary.get("background_cube_links"):
            formats.append("scene-background-cube-links")
        if file_summary.get("grm_fragment_links"):
            formats.append("scene-grm-fragment-links")
    if file_summary.get("path") == HOLOMAP_ARCHIVE_NAME and file_summary.get("linked_text_refs"):
        formats.append("holomap-text-record-links")
    resource_formats = file_summary.get("resource_formats") or []
    formats.extend(resource_formats)
    if file_summary.get("script_linked_video_refs"):
        formats.append("scene-video-links")
    if "bkg_block_table" in resource_formats:
        formats.append("bkg_block_cell_brk_links")
    if "bkg_grid_map" in resource_formats:
        formats.append("bkg_grid_column_composition")
    return list(dict.fromkeys(formats)) or ["unknown"]


def build_hqr_coverage_matrix(catalog: dict[str, Any]) -> dict[str, Any]:
    archives: list[dict[str, Any]] = []
    for file_summary in catalog.get("hqr_files", []):
        path = file_summary.get("path", "")
        key = hqr_coverage_key(path)
        profile = HQR_COVERAGE_PROFILES.get(
            key,
            {
                "runtime_purpose": "Unknown archive purpose.",
                "parser_support": "No dedicated parser.",
                "viewer_support": "None.",
                "export_support": "None.",
                "default_status": "unknown",
                "next_required_evidence": "Locate runtime loader references and classify non-empty entries.",
            },
        )
        non_empty = int(file_summary.get("non_empty_entries") or 0)
        recognized = int(file_summary.get("recognized") or 0)
        unknown_entries = max(0, non_empty - recognized)
        semantic_unknown_entries = (
            unknown_entries
            + int(file_summary.get("raw_scenes") or 0)
            + int(file_summary.get("semantic_unknown") or 0)
        )
        unknown_formats: list[str] = []
        if unknown_entries:
            unknown_formats.append("unclassified-payload")
        if file_summary.get("semantic_unknown"):
            unknown_formats.append("unclassified-payload")
        if file_summary.get("raw_animations"):
            unknown_formats.append("raw-animation-layout")
        if file_summary.get("raw_scenes"):
            unknown_formats.append("scene-behavior-semantics")
        if not unknown_formats and coverage_formats(file_summary) == ["unknown"] and non_empty:
            unknown_formats.append("unknown")

        default_status = profile["default_status"]
        if non_empty == 0:
            status = "empty"
        elif default_status == "deferred":
            status = "deferred"
        elif unknown_entries or semantic_unknown_entries or default_status == "partial":
            status = "partial"
        elif default_status == "covered":
            status = "covered"
        else:
            status = "unknown"

        archives.append(
            {
                "path": path,
                "archive": key,
                "entry_count": file_summary.get("entry_count", 0),
                "non_empty_entries": non_empty,
                "cataloged_entries": recognized,
                "unknown_entries": unknown_entries,
                "semantic_unknown_entries": semantic_unknown_entries,
                "recognized_formats": coverage_formats(file_summary),
                "unknown_formats": unknown_formats,
                "runtime_purpose": profile["runtime_purpose"],
                "parser_support": profile["parser_support"],
                "viewer_support": profile["viewer_support"],
                "export_support": profile["export_support"],
                "coverage_status": status,
                "next_required_evidence": profile["next_required_evidence"],
            }
        )
    status_counts: dict[str, int] = {}
    for archive in archives:
        status = str(archive["coverage_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema": "lba2-hqr-coverage-v1",
        "archive_count": len(archives),
        "statuses": status_counts,
        "archives": archives,
    }


def build_catalog(
    asset_root: Path,
    progress: DecodeProgress | None = None,
    selected_files: list[Path] | None = None,
) -> dict[str, Any]:
    if not asset_root.exists():
        raise Lm2Error(f"asset root does not exist: {asset_root}")
    if not asset_root.is_dir():
        raise Lm2Error(f"asset root is not a directory: {asset_root}")
    body_metadata = load_body_metadata()
    try:
        file3d_metadata = load_file3d_metadata(asset_root)
    except (Lm2Error, lba_hqr.HqrError):
        file3d_metadata = {"objects": {}, "animations": {}}
    try:
        acf_names = load_acf_names(asset_root)
    except (Lm2Error, lba_hqr.HqrError):
        acf_names = []
    file3d_animation_metadata = file3d_metadata["animations"]
    file3d_object_metadata = file3d_metadata["objects"]
    sprite_zv_tables = load_sprite_zv_tables(asset_root)
    catalog: dict[str, Any] = {
        "schema": "lba2-lm2-explorer-v1",
        "asset_root": str(asset_root.resolve()),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_mode": "files" if selected_files is not None else "folder",
        "metadata": {
            "file3d_animation_labels": bool(file3d_animation_metadata),
            "sprite_runtime_model": sprite_runtime_model_metadata(),
        },
        "hqr_files": [],
        "assets": [],
    }

    if selected_files is not None:
        catalog["selected_files"] = [
            path.relative_to(asset_root).as_posix() for path in selected_files
        ]

    archive_jobs: list[dict[str, Any]] = []
    for hqr_path in (
        selected_files if selected_files is not None else hqr_paths(asset_root)
    ):
        hqr_relative = hqr_path.relative_to(asset_root).as_posix()
        archive_name = hqr_path.name.upper()
        is_body_archive = archive_name == "BODY.HQR"
        is_objfix_archive = archive_name == OBJFIX_ARCHIVE_NAME
        is_anim3ds_archive = archive_name == ANIM3DS_ARCHIVE_NAME
        is_holomap_archive = archive_name == HOLOMAP_ARCHIVE_NAME
        is_bkg_archive = archive_name == LBA_BKG_ARCHIVE_NAME
        is_text_archive = archive_name == TEXT_ARCHIVE_NAME
        is_screen_archive = archive_name == SCREEN_ARCHIVE_NAME
        is_sample_archive = archive_name == SAMPLES_ARCHIVE_NAME
        is_video_archive = archive_name == VIDEO_ARCHIVE_NAME
        is_sprite_archive = archive_name in SPRITE_ARCHIVE_NAMES
        data = hqr_path.read_bytes()
        entries = (
            lba_hqr.parse_classic_table(data)
            if is_body_archive or is_objfix_archive or is_anim3ds_archive or is_holomap_archive or is_bkg_archive or is_text_archive or is_screen_archive or is_sprite_archive
            else lba_hqr.parse_table(data)
        )
        archive_jobs.append(
            {
                "path": hqr_path,
                "relative": hqr_relative,
                "archive_name": archive_name,
                "is_body_archive": is_body_archive,
                "is_objfix_archive": is_objfix_archive,
                "is_anim3ds_archive": is_anim3ds_archive,
                "is_holomap_archive": is_holomap_archive,
                "is_bkg_archive": is_bkg_archive,
                "is_text_archive": is_text_archive,
                "is_screen_archive": is_screen_archive,
                "is_sample_archive": is_sample_archive,
                "is_video_archive": is_video_archive,
                "is_sprite_archive": is_sprite_archive,
                "data": data,
                "entries": entries,
            }
        )

    total_entries = sum(
        1
        for archive in archive_jobs
        for entry in archive["entries"]
        if entry.byte_length > 0
    )
    processed_entries = 0
    if progress is not None:
        progress.update(
            total=total_entries, label="Decoding HQR entries", phase="decoding"
        )

    for archive in archive_jobs:
        hqr_path = archive["path"]
        hqr_relative = archive["relative"]
        archive_name = archive["archive_name"]
        is_body_archive = archive["is_body_archive"]
        is_objfix_archive = archive["is_objfix_archive"]
        is_anim3ds_archive = archive["is_anim3ds_archive"]
        is_holomap_archive = archive["is_holomap_archive"]
        is_bkg_archive = archive["is_bkg_archive"]
        is_text_archive = archive["is_text_archive"]
        is_screen_archive = archive["is_screen_archive"]
        is_sample_archive = archive["is_sample_archive"]
        is_video_archive = archive["is_video_archive"]
        is_sprite_archive = archive["is_sprite_archive"]
        sprite_backend = sprite_backend_for_archive(archive_name)
        data = archive["data"]
        entries = archive["entries"]
        anim3ds_ranges: list[dict[str, Any]] = []
        anim3ds_frames: dict[int, dict[str, Any]] = {}
        anim3ds_range_warnings: list[dict[str, Any]] = []
        if is_anim3ds_archive:
            info_entry = next(
                (entry for entry in entries if entry.index == ANIM3DS_INFO_ENTRY_INDEX),
                None,
            )
            if info_entry is not None and info_entry.byte_length > 0:
                try:
                    info_payload, _ = decoded_entry(lba_hqr.read_entry(data, info_entry))
                    anim3ds_ranges = parse_anim3ds_info(info_payload)
                    anim3ds_frames = anim3ds_frame_lookup(anim3ds_ranges)
                    available_frames = {
                        entry.index
                        for entry in entries
                        if entry.byte_length > 0
                        and entry.index != ANIM3DS_INFO_ENTRY_INDEX
                    }
                    anim3ds_range_warnings = validate_anim3ds_frame_ranges(
                        anim3ds_ranges, available_frames
                    )
                except (Lm2Error, lba_hqr.HqrError):
                    anim3ds_ranges = []
                    anim3ds_frames = {}
                    anim3ds_range_warnings = []
        file_summary: dict[str, Any] = {
            "path": hqr_relative,
            "indexing": "runtime-zero-based" if is_sample_archive or is_video_archive else "classic" if is_body_archive or is_objfix_archive or is_anim3ds_archive or is_holomap_archive or is_bkg_archive or is_text_archive or is_screen_archive or is_sprite_archive else "one-based",
            "runtime_sprite_backend": sprite_backend,
            "entry_count": len(entries),
            "non_empty_entries": sum(1 for entry in entries if entry.byte_length > 0),
            "models": 0,
            "animations": 0,
            "decoded_animations": 0,
            "raw_animations": 0,
            "sprites": 0,
            "sprite_frames": 0,
            "sprite_metadata": 0,
            "scenes": 0,
            "raw_scenes": 0,
        "resources": 0,
            "resource_formats": [],
            "sprite_formats": [],
            "recognized": 0,
            "semantic_unknown": 0,
            "bytes": len(data),
        }
        if is_video_archive:
            file_summary["acf_name_count"] = len(acf_names)
            file_summary["acf_names_without_payload"] = [
                name
                for index, name in enumerate(acf_names)
                if index >= len(entries) or entries[index].byte_length <= 0
            ]
        bkg_header: dict[str, Any] | None = None
        bkg_grid_lookup: dict[int, dict[str, Any]] = {}
        if is_bkg_archive:
            header_entry = next((entry for entry in entries if entry.index == 0), None)
            if header_entry is not None and header_entry.byte_length > 0:
                try:
                    header_payload, _ = decoded_entry(lba_hqr.read_entry(data, header_entry))
                    bkg_header = parse_bkg_header(header_payload)
                except (Lm2Error, lba_hqr.HqrError):
                    bkg_header = None
        if archive_name == RESS_ARCHIVE_NAME:
            classic_entries = lba_hqr.parse_classic_table(data)
            if (
                PALETTE_ENTRY_INDEX < len(classic_entries)
                and classic_entries[PALETTE_ENTRY_INDEX].byte_length > 0
            ):
                palette_entry = classic_entries[PALETTE_ENTRY_INDEX]
                palette_raw = lba_hqr.read_entry(data, palette_entry)
                try:
                    palette_payload, palette_resource = decoded_entry(palette_raw)
                    resource_result = ress_resource_catalog_stats(
                        PALETTE_CATALOG_ENTRY_INDEX, palette_payload
                    )
                except (Lm2Error, lba_hqr.HqrError):
                    resource_result = None
                    palette_payload = palette_raw
                    palette_resource = None
                if resource_result is not None:
                    entry_type, stats = resource_result
                    source = {
                        "hqr": hqr_relative,
                        "entry_index": PALETTE_CATALOG_ENTRY_INDEX,
                        "classic_index": PALETTE_ENTRY_INDEX,
                        "offset": palette_entry.offset,
                        "raw_bytes": palette_entry.byte_length,
                        "raw_sha256": palette_entry.sha256,
                        "resource": palette_resource,
                    }
                    catalog["assets"].append(
                        {
                            "id": f"{hqr_relative}:{PALETTE_CATALOG_ENTRY_INDEX}",
                            "kind": "resource",
                            "label": resource_catalog_label(
                                PALETTE_CATALOG_ENTRY_INDEX, entry_type, stats
                            ),
                            "entry_type": entry_type,
                            "source": source,
                            "path": hqr_relative,
                            "relative_path": f"{hqr_relative}[{PALETTE_CATALOG_ENTRY_INDEX}]",
                            "decoded_bytes": len(palette_payload),
                            "decoded_sha256": hashlib.sha256(palette_payload).hexdigest(),
                            "stats": stats,
                            "features": {"parsed": True, "runtime_resource": True},
                        }
                    )
                    file_summary["entry_count"] += 1
                    file_summary["non_empty_entries"] += 1
                    file_summary["resources"] += 1
                    file_summary["resource_formats"].append(stats["semantic_layout"])
                    file_summary["recognized"] += 1

        for entry in entries:
            if entry.byte_length == 0:
                continue
            if progress is not None:
                progress.update(
                    current=processed_entries,
                    label=f"Decoding {hqr_relative}[{entry.index + 1 if is_body_archive else entry.index}]",
                )
            raw = lba_hqr.read_entry(data, entry)
            catalog_entry_index = (
                entry.index + 1
                if is_body_archive
                else entry.index - 1
                if is_sample_archive or is_video_archive
                else entry.index
            )
            try:
                payload, resource = decoded_entry(raw)
            except lba_hqr.HqrError:
                payload, resource = raw, None

            source = {
                "hqr": hqr_relative,
                "entry_index": catalog_entry_index,
                "offset": entry.offset,
                "raw_bytes": entry.byte_length,
                "raw_sha256": entry.sha256,
                "resource": resource,
            }
            if is_body_archive or is_objfix_archive or is_bkg_archive or is_text_archive or is_screen_archive or is_sprite_archive:
                source["classic_index"] = entry.index
            if is_sample_archive:
                source["hqr_table_index"] = entry.index
            if is_video_archive:
                source["hqr_table_index"] = entry.index
            asset_id = f"{hqr_relative}:{catalog_entry_index}"

            if archive_name == ANIM_ARCHIVE_NAME:
                asset = anim_hqr_catalog_asset(
                    asset_id=asset_id,
                    hqr_relative=hqr_relative,
                    catalog_entry_index=catalog_entry_index,
                    source=source,
                    payload=payload,
                    animation_metadata=file3d_animation_metadata.get(catalog_entry_index),
                )
                catalog["assets"].append(asset)
                if asset.get("animation_state") == "decoded":
                    file_summary["animations"] += 1
                    file_summary["decoded_animations"] += 1
                else:
                    file_summary["raw_animations"] += 1
                file_summary["recognized"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            if archive_name == RESS_ARCHIVE_NAME:
                resource_result = ress_resource_catalog_stats(catalog_entry_index, payload)
                if resource_result is not None:
                    entry_type, stats = resource_result
                    asset = {
                        "id": asset_id,
                        "kind": "resource",
                        "label": resource_catalog_label(
                            catalog_entry_index, entry_type, stats
                        ),
                        "entry_type": entry_type,
                        "source": source,
                        "path": hqr_relative,
                        "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                        "decoded_bytes": len(payload),
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "stats": stats,
                        "features": {
                            "parsed": True,
                            "runtime_resource": True,
                        },
                    }
                    catalog["assets"].append(asset)
                    file_summary["resources"] += 1
                    file_summary["resource_formats"].append(stats["semantic_layout"])
                    file_summary["recognized"] += 1
                    processed_entries += 1
                    if progress is not None:
                        progress.update(current=processed_entries)
                    continue

            if archive_name == SCREEN_ARCHIVE_NAME:
                resource_result = screen_resource_catalog_stats(catalog_entry_index, payload)
                if resource_result is not None:
                    entry_type, stats = resource_result
                    asset = {
                        "id": asset_id,
                        "kind": "resource",
                        "label": screen_resource_catalog_label(
                            catalog_entry_index, entry_type, stats
                        ),
                        "entry_type": entry_type,
                        "source": source,
                        "path": hqr_relative,
                        "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                        "decoded_bytes": len(payload),
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "stats": stats,
                        "features": {
                            "parsed": True,
                            "runtime_resource": True,
                        },
                    }
                    catalog["assets"].append(asset)
                    file_summary["resources"] += 1
                    file_summary["resource_formats"].append(stats["semantic_layout"])
                    file_summary["recognized"] += 1
                    processed_entries += 1
                    if progress is not None:
                        progress.update(current=processed_entries)
                    continue

            if archive_name == HOLOMAP_ARCHIVE_NAME:
                resource_result = holomap_resource_catalog_stats(catalog_entry_index, payload)
                if resource_result is not None:
                    entry_type, stats = resource_result
                    asset = {
                        "id": asset_id,
                        "kind": "resource",
                        "label": holomap_resource_catalog_label(
                            catalog_entry_index, entry_type, stats
                        ),
                        "entry_type": entry_type,
                        "source": source,
                        "path": hqr_relative,
                        "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                        "decoded_bytes": len(payload),
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "stats": stats,
                        "features": {
                            "parsed": True,
                            "runtime_resource": True,
                        },
                    }
                    catalog["assets"].append(asset)
                    file_summary["resources"] += 1
                    file_summary["resource_formats"].append(stats["semantic_layout"])
                    file_summary["recognized"] += 1
                    processed_entries += 1
                    if progress is not None:
                        progress.update(current=processed_entries)
                    continue

            if archive_name == LBA_BKG_ARCHIVE_NAME and bkg_header is not None:
                resource_result = bkg_resource_catalog_stats(
                    catalog_entry_index, payload, bkg_header, bkg_grid_lookup
                )
                if resource_result is not None:
                    entry_type, stats = resource_result
                    if stats["semantic_layout"] == "bkg_grid_map":
                        bkg_grid_lookup[catalog_entry_index] = {
                            "resolved_bll_entry": stats["fields"]["resolved_bll_entry"],
                            "resolved_grm_entry": stats["fields"]["resolved_grm_entry"],
                            "used_block_count": stats["fields"]["used_block_count"],
                        }
                    asset = {
                        "id": asset_id,
                        "kind": "resource",
                        "label": bkg_resource_catalog_label(
                            catalog_entry_index, entry_type, stats
                        ),
                        "entry_type": entry_type,
                        "source": source,
                        "path": hqr_relative,
                        "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                        "decoded_bytes": len(payload),
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "stats": stats,
                        "features": {
                            "parsed": True,
                            "runtime_resource": True,
                        },
                    }
                    catalog["assets"].append(asset)
                    file_summary["resources"] += 1
                    file_summary["resource_formats"].append(stats["semantic_layout"])
                    file_summary["recognized"] += 1
                    processed_entries += 1
                    if progress is not None:
                        progress.update(current=processed_entries)
                    continue

            if archive_name == TEXT_ARCHIVE_NAME:
                resource_result = text_resource_catalog_stats(catalog_entry_index, payload)
                if resource_result is not None:
                    entry_type, stats = resource_result
                    asset = {
                        "id": asset_id,
                        "kind": "resource",
                        "label": text_resource_catalog_label(
                            catalog_entry_index, entry_type, stats
                        ),
                        "entry_type": entry_type,
                        "source": source,
                        "path": hqr_relative,
                        "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                        "decoded_bytes": len(payload),
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "stats": stats,
                        "features": {
                            "parsed": True,
                            "runtime_resource": True,
                        },
                    }
                    catalog["assets"].append(asset)
                    file_summary["resources"] += 1
                    file_summary["resource_formats"].append(stats["semantic_layout"])
                    file_summary["recognized"] += 1
                    processed_entries += 1
                    if progress is not None:
                        progress.update(current=processed_entries)
                    continue

            if archive_name == SAMPLES_ARCHIVE_NAME and resource is not None:
                entry_type = "sample-wave-audio"
                stats = sample_resource_catalog_stats(
                    catalog_entry_index, payload, resource
                )
                asset = {
                    "id": asset_id,
                    "kind": "resource",
                    "label": sample_resource_catalog_label(catalog_entry_index, stats),
                    "entry_type": entry_type,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": {
                        "parsed": True,
                        "runtime_resource": True,
                        "audio_sample": True,
                    },
                }
                catalog["assets"].append(asset)
                file_summary["resources"] += 1
                file_summary["resource_formats"].append(stats["semantic_layout"])
                file_summary["recognized"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            if archive_name == VIDEO_ARCHIVE_NAME and resource is not None:
                try:
                    stats = smacker_video_catalog_stats(
                        payload,
                        resource,
                        acf_index=catalog_entry_index,
                        acf_name=acf_names[catalog_entry_index]
                        if 0 <= catalog_entry_index < len(acf_names)
                        else None,
                    )
                    parsed = True
                    features = {
                        "parsed": True,
                        "runtime_resource": True,
                        "video": True,
                    }
                    file_summary["recognized"] += 1
                except Lm2Error as exc:
                    stats = {
                        "decoded_bytes": len(payload),
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "parse_status": "decoded",
                        "decode_status": "deferred",
                        "decode_note": (
                            "VIDEO.HQR entry is expected to be a Smacker movie "
                            f"payload, but the header was not decoded: {exc}"
                        ),
                        "semantic_layout": "unknown",
                        "preview_hex": payload[:64].hex(),
                        "unknown_descriptors": [
                            unknown_bytes_descriptor(
                                payload,
                                section="video_unclassified_payload",
                                offset=0,
                                length=len(payload),
                                confidence="unknown",
                                note="VIDEO.HQR payload did not match the expected Smacker header.",
                            )
                        ],
                    }
                    parsed = False
                    features = {
                        "parsed": False,
                        "runtime_resource": True,
                        "video": True,
                        "semantic_unknown": True,
                    }
                    file_summary["semantic_unknown"] += 1
                entry_type = "smacker-video" if parsed else "video-raw"
                asset = {
                    "id": asset_id,
                    "kind": "resource",
                    "label": (
                        smacker_video_catalog_label(catalog_entry_index, stats)
                        if parsed
                        else f"Unclassified video payload ({VIDEO_ARCHIVE_NAME}:{catalog_entry_index})"
                    ),
                    "entry_type": entry_type,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": features,
                }
                catalog["assets"].append(asset)
                file_summary["resources"] += 1
                file_summary["resource_formats"].append(stats["semantic_layout"])
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            if is_sprite_archive and archive_name != ANIM3DS_ARCHIVE_NAME:
                assert sprite_backend is not None
                zv_table = sprite_zv_tables.get(sprite_backend, [])
                zv_record = (
                    zv_table[catalog_entry_index]
                    if 0 <= catalog_entry_index < len(zv_table)
                    else None
                )
                try:
                    stats = sprite_frame_catalog_stats(
                        payload,
                        backend=sprite_backend,
                        runtime_index=catalog_entry_index,
                        zv_record=zv_record,
                    )
                    parsed = True
                except Lm2Error as exc:
                    stats = raw_animation_catalog_stats(
                        payload,
                        decode_status="deferred",
                        decode_note=(
                            f"{archive_name} entry is expected to be a sprite "
                            f"payload, but decode failed: {exc}"
                        ),
                    )
                    stats["sprite_backend"] = sprite_backend
                    stats["runtime"] = sprite_archive_runtime_info(
                        sprite_backend,
                        catalog_entry_index,
                    )
                    parsed = False
                entry_type = (
                    "sprite-frame"
                    if archive_name == SPRITES_ARCHIVE_NAME
                    else "sprite-raw-frame"
                )
                asset = {
                    "id": asset_id,
                    "kind": "sprite",
                    "label": sprite_catalog_label(archive_name, catalog_entry_index, stats),
                    "entry_type": entry_type,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": {
                        "parsed": parsed,
                        "sprite_frame": True,
                        "runtime_sprite_backend": sprite_backend,
                        "has_runtime_bounds": bool(zv_record),
                    },
                }
                catalog["assets"].append(asset)
                file_summary["sprites"] += 1
                file_summary["sprite_frames"] += 1
                file_summary["sprite_formats"].append(stats["semantic_layout"])
                file_summary["recognized"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            try:
                model = parse_lm2(payload)
            except Lm2Error:
                model = None
            if model is not None:
                metadata = (
                    body_metadata.get(catalog_entry_index, {})
                    if is_body_archive
                    else {}
                )
                label = (
                    metadata.get("description")
                    or f"{Path(hqr_relative).name} entry {catalog_entry_index}"
                )
                stats = model.to_viewer_json(label)["stats"]
                if is_objfix_archive:
                    direct_references = direct_objfix_code_references(
                        catalog_entry_index
                    )
                    stats["direct_code_references"] = direct_references
                    stats["direct_reference_count"] = len(direct_references)
                    stats["runtime_reference_status"] = (
                        "direct GivePtrObjFix runtime id"
                    )
                asset = {
                    "id": asset_id,
                    "kind": "model",
                    "label": label,
                    "entry_type": metadata.get("type") or "mesh",
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "bounds": model.header.bounds,
                    "features": {
                        "has_animation_flag": model.header.has_animation,
                        "has_transparency": model.header.has_transparency,
                        "has_lines": len(model.lines) > 0,
                        "has_spheres": len(model.spheres) > 0,
                        "direct_code_references": bool(
                            stats.get("direct_reference_count")
                        ),
                    },
                }
                catalog["assets"].append(asset)
                file_summary["models"] += 1
                file_summary["recognized"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            if archive_name == RESS_ARCHIVE_NAME:
                entry_type = "unclassified-payload"
                stats = ress_unclassified_payload_catalog_stats(payload)
                asset = {
                    "id": asset_id,
                    "kind": "resource",
                    "label": resource_catalog_label(catalog_entry_index, entry_type, stats),
                    "entry_type": entry_type,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": {
                        "parsed": True,
                        "runtime_resource": True,
                        "semantic_unknown": True,
                    },
                }
                catalog["assets"].append(asset)
                file_summary["resources"] += 1
                file_summary["resource_formats"].append(stats["semantic_layout"])
                file_summary["recognized"] += 1
                file_summary["semantic_unknown"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            if archive_name == SCENE_ARCHIVE_NAME:
                stats = scene_catalog_stats(payload)
                asset = {
                    "id": asset_id,
                    "kind": "scene",
                    "label": f"Scene {catalog_entry_index - 1} (SCENE.HQR:{catalog_entry_index})",
                    "entry_type": "scene-runtime",
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": {
                        "parsed": stats["parse_status"] == "partial",
                        "scene_runtime": True,
                    },
                }
                catalog["assets"].append(asset)
                file_summary["scenes"] += 1
                file_summary["raw_scenes"] += 1
                file_summary["recognized"] += 1
                processed_entries += 1
                if progress is not None:
                    progress.update(current=processed_entries)
                continue

            if archive_name in ANIMATION_ARCHIVE_NAMES:
                if archive_name == ANIM_ARCHIVE_NAME:
                    try:
                        animation = parse_lba2_animation(payload)
                        animation_error = ""
                    except (AnimationError, Lm2Error) as exc:
                        animation = None
                        animation_error = str(exc)
                else:
                    animation = None
                    animation_error = ""
                if animation is not None:
                    stats = animation.to_json()
                    entry_type = "animation"
                    animation_state = "decoded"
                    features = {
                        "looping": animation.loop_frame < animation.keyframes - 1,
                        "can_fall": animation.can_fall,
                        "parsed": True,
                    }
                elif (
                    archive_name == ANIM3DS_ARCHIVE_NAME
                    and catalog_entry_index == ANIM3DS_INFO_ENTRY_INDEX
                ):
                    stats = anim3ds_info_catalog_stats(payload, anim3ds_range_warnings)
                    asset_kind = "sprite"
                    entry_type = "anim3ds-info"
                    animation_state = None
                    features = {
                        "parsed": True,
                        "metadata_only": True,
                        "sprite_animation": True,
                    }
                else:
                    asset_kind = "animation"
                    if archive_name == ANIM3DS_ARCHIVE_NAME:
                        asset_kind = "sprite"
                        zv_table = sprite_zv_tables.get("anim3ds", [])
                        zv_record = (
                            zv_table[catalog_entry_index]
                            if 0 <= catalog_entry_index < len(zv_table)
                            else None
                        )
                        try:
                            stats = sprite_frame_catalog_stats(
                                payload,
                                backend="anim3ds",
                                runtime_index=catalog_entry_index,
                                zv_record=zv_record,
                            )
                        except Lm2Error as exc:
                            stats = raw_animation_catalog_stats(
                                payload,
                                decode_status="deferred",
                                decode_note=(
                                    "ANIM3DS frame is expected to be an LSP sprite "
                                    f"payload, but decode failed: {exc}"
                                ),
                            )
                    else:
                        stats = raw_animation_catalog_stats(
                            payload,
                            decode_status="parse_failed",
                            decode_note="Animation parser rejected this payload; retained as raw evidence.",
                            parse_error=animation_error,
                        )
                    entry_type = "animation-raw"
                    animation_state = "raw"
                    features = {"parsed": False}
                    if archive_name == ANIM3DS_ARCHIVE_NAME:
                        entry_type = "anim3ds-frame"
                        animation_state = None
                        features["sprite_frame"] = True
                        features["parsed"] = stats.get("parse_status") == "decoded"
                        features["runtime_sprite_backend"] = "anim3ds"
                        features["has_runtime_bounds"] = bool(zv_record)
                        if catalog_entry_index in anim3ds_frames:
                            info = anim3ds_frames[catalog_entry_index]
                            stats["anim3ds_info"] = {
                                "animation_index": info["index"],
                                "name": info["name"],
                                "start_frame": info["start_frame"],
                                "end_frame": info["end_frame"],
                                "relative_frame": catalog_entry_index
                                - info["start_frame"],
                            }
                if animation is not None:
                    asset_kind = "animation"
                animation_metadata = (
                    file3d_animation_metadata.get(catalog_entry_index)
                    if archive_name == ANIM_ARCHIVE_NAME
                    else None
                )
                asset = {
                    "id": asset_id,
                    "kind": asset_kind,
                    "label": (
                        anim3ds_catalog_label(catalog_entry_index, stats)
                        if archive_name == ANIM3DS_ARCHIVE_NAME
                        else animation_catalog_label(
                            Path(hqr_relative).name,
                            catalog_entry_index,
                            animation_metadata,
                        )
                    ),
                    "entry_type": entry_type,
                    "source": source,
                    "path": hqr_relative,
                    "relative_path": f"{hqr_relative}[{catalog_entry_index}]",
                    "decoded_bytes": len(payload),
                    "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                    "stats": stats,
                    "features": features,
                }
                if animation_state is not None:
                    asset["animation_state"] = animation_state
                if animation_metadata is not None:
                    asset["animation_metadata"] = animation_metadata
                catalog["assets"].append(asset)
                if animation_state == "decoded":
                    file_summary["animations"] += 1
                    file_summary["decoded_animations"] += 1
                elif asset_kind == "animation":
                    file_summary["raw_animations"] += 1
                elif entry_type == "anim3ds-info":
                    file_summary["sprite_metadata"] += 1
                    file_summary["sprites"] += 1
                else:
                    file_summary["sprite_frames"] += 1
                    file_summary["sprites"] += 1
                file_summary["recognized"] += 1

            processed_entries += 1
            if progress is not None:
                progress.update(current=processed_entries)

        catalog["hqr_files"].append(file_summary)

    enrich_scene_runtime_links(catalog, file3d_object_metadata)
    enrich_scene_script_links(catalog, file3d_object_metadata)
    enrich_scene_sample_links(catalog)
    enrich_scene_video_links(catalog)
    enrich_scene_text_links(catalog)
    enrich_holomap_text_links(catalog)
    enrich_bkg_grid_block_links(catalog)
    enrich_scene_background_links(catalog)
    enrich_scene_grm_links(catalog)
    enrich_scene_asset_usage(catalog)
    update_scene_link_summary(catalog)

    decoded_animations = sum(
        1
        for asset in catalog["assets"]
        if asset["kind"] == "animation" and asset.get("animation_state") == "decoded"
    )
    raw_animations = sum(
        1
        for asset in catalog["assets"]
        if asset["kind"] == "animation" and asset.get("animation_state") == "raw"
    )
    sprite_assets = sum(1 for asset in catalog["assets"] if asset["kind"] == "sprite")
    sprite_frames = sum(
        1
        for asset in catalog["assets"]
        if asset["kind"] == "sprite"
        and asset.get("entry_type") in {"anim3ds-frame", "sprite-frame", "sprite-raw-frame"}
    )
    sprite_metadata = sum(
        1
        for asset in catalog["assets"]
        if asset["kind"] == "sprite" and asset.get("entry_type") == "anim3ds-info"
    )
    scene_assets = sum(1 for asset in catalog["assets"] if asset["kind"] == "scene")
    resource_assets = sum(1 for asset in catalog["assets"] if asset["kind"] == "resource")
    catalog["summary"] = {
        "hqr_files": len(catalog["hqr_files"]),
        "assets": len(catalog["assets"]),
        "models": sum(1 for asset in catalog["assets"] if asset["kind"] == "model"),
        "animations": decoded_animations,
        "decoded_animations": decoded_animations,
        "raw_animations": raw_animations,
        "animation_assets": decoded_animations + raw_animations,
        "sprite_assets": sprite_assets,
        "sprite_frames": sprite_frames,
        "sprite_metadata": sprite_metadata,
        "scene_assets": scene_assets,
        "resource_assets": resource_assets,
        "scene_linked_body_refs": catalog["metadata"]["scene_runtime_links"]["body_refs"],
        "scene_linked_animation_refs": catalog["metadata"]["scene_runtime_links"]["animation_refs"],
        "scene_linked_sprite_refs": catalog["metadata"]["scene_runtime_links"]["sprite_refs"],
        "scene_script_linked_body_refs": catalog["metadata"]["scene_script_links"]["body_refs"],
        "scene_script_linked_animation_refs": catalog["metadata"]["scene_script_links"]["animation_refs"],
        "scene_script_linked_sprite_refs": catalog["metadata"]["scene_script_links"]["sprite_refs"],
        "scene_script_linked_text_refs": catalog["metadata"]["scene_text_links"]["script_logical_refs"],
        "scene_zone_linked_text_refs": catalog["metadata"]["scene_text_links"]["zone_logical_refs"],
        "holomap_linked_text_refs": catalog["metadata"]["holomap_text_links"]["linked_unique_message_ids"],
        "scene_script_linked_sample_refs": catalog["metadata"]["scene_sample_links"]["script_linked_refs"],
        "scene_script_linked_video_refs": catalog["metadata"]["scene_video_links"]["script_linked_refs"],
        "scene_ambience_linked_sample_refs": catalog["metadata"]["scene_sample_links"]["ambience_linked_refs"],
        "scene_background_cube_links": catalog["metadata"]["scene_background_links"]["scene_cube_links"],
        "scene_grm_fragment_links": catalog["metadata"]["scene_grm_links"]["linked_grm_fragments"],
        "scene_usage_refs": catalog["metadata"]["scene_asset_usage"]["usage_ref_count"],
        "scene_used_assets": catalog["metadata"]["scene_asset_usage"]["used_asset_count"],
    }
    catalog["coverage"] = build_hqr_coverage_matrix(catalog)
    compact_scene_catalog_payload(catalog)
    return catalog


def pick_directory_dialog() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build
        raise Lm2Error(f"folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Select the folder containing your LBA2 HQR files"
        )
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no folder selected")
    return Path(selected)


def pick_hqr_files_dialog() -> list[Path]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build
        raise Lm2Error(f"file picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilenames(
            title="Select one or more LBA2 HQR files",
            filetypes=(("HQR archives", "*.HQR *.hqr"), ("All files", "*.*")),
        )
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no files selected")
    return [Path(path) for path in selected]


def pick_export_directory_dialog() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python build
        raise Lm2Error(f"export folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Select export folder for the LM2 evidence probe"
        )
    finally:
        root.destroy()
    if not selected:
        raise Lm2Error("no export folder selected")
    return Path(selected)


def inspect(path: Path) -> None:
    model = load_lm2_path(path)
    print(json.dumps(model.to_viewer_json(str(path))["stats"], indent=2))


def export_probe_command(argv: list[str]) -> int:
    from .exports import export_catalog_asset_probe

    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer export",
        description="Export an LM2 evidence probe for one catalog model asset.",
    )
    parser.add_argument(
        "--asset-root",
        required=True,
        type=Path,
        help="folder containing the user's LBA2 HQR files",
    )
    parser.add_argument(
        "--asset",
        required=True,
        help='catalog asset id, for example "BODY.HQR:1"',
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="directory to write OBJ, MTL, PNG, and manifest files",
    )
    parser.add_argument(
        "--polygon-mode",
        choices=("original", "triangulated"),
        default="original",
        help="OBJ face mode, default original",
    )
    args = parser.parse_args(argv)

    manifest = export_catalog_asset_probe(
        asset_root=args.asset_root,
        asset_id=args.asset,
        output_dir=args.out,
        polygon_mode=args.polygon_mode,
    )
    print(f"Wrote {args.out.resolve()}")
    print(
        json.dumps(
            {"schema_version": manifest["schema_version"], "files": manifest["files"]},
            indent=2,
        )
    )
    return 0


def contract_command(argv: list[str]) -> int:
    from .contracts import export_catalog_asset_contract

    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer contract",
        description="Write a versioned LM2 model contract JSON file.",
    )
    parser.add_argument(
        "--asset-root",
        required=True,
        type=Path,
        help="folder containing the user's LBA2 HQR files",
    )
    parser.add_argument(
        "--asset",
        required=True,
        help='catalog asset id, for example "BODY.HQR:1"',
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="JSON file to write",
    )
    args = parser.parse_args(argv)

    contract = export_catalog_asset_contract(
        asset_root=args.asset_root,
        asset_id=args.asset,
        output_path=args.out,
    )
    print(f"Wrote {args.out.resolve()}")
    print(
        json.dumps(
            {
                "schema_version": contract.schema_version,
                "asset_id": contract.source.asset_id,
            },
            indent=2,
        )
    )
    return 0


def animation_command(argv: list[str]) -> int:
    from .animation import (
        build_animation_evidence,
        parse_lba2_animation_records,
        playback_frame_indices,
        write_animation_evidence,
    )

    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer animation",
        description="Write decoded ANIM records and frame-step evidence as JSON.",
    )
    parser.add_argument(
        "--asset-root",
        required=True,
        type=Path,
        help="folder containing the user's LBA2 HQR files",
    )
    parser.add_argument(
        "--asset",
        required=True,
        help='catalog animation asset id, for example "ANIM.HQR:1"',
    )
    parser.add_argument(
        "--body-asset",
        help='optional catalog body asset id for bone-count compatibility, for example "BODY.HQR:1"',
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="JSON file to write",
    )
    parser.add_argument(
        "--sample-frame",
        type=int,
        default=0,
        help="target keyframe index to sample, default 0",
    )
    parser.add_argument(
        "--previous-frame",
        type=int,
        help="optional previous keyframe index for loop-transition samples",
    )
    parser.add_argument(
        "--sample-loop-transition",
        action="store_true",
        help="sample the canonical loop-start transition from the last keyframe",
    )
    parser.add_argument(
        "--elapsed-ms",
        type=int,
        default=0,
        help="elapsed milliseconds inside the sampled keyframe, default 0",
    )
    args = parser.parse_args(argv)

    asset_root = args.asset_root.resolve()
    catalog = build_catalog(asset_root)
    asset = find_catalog_asset(catalog, args.asset)
    if asset.get("kind") != "animation" or asset.get("entry_type") != "animation":
        raise Lm2Error(f"catalog asset is not a decoded animation: {args.asset}")
    payload, resource = read_hqr_payload(asset_root, asset["source"])
    animation = parse_lba2_animation_records(payload)
    sample_frame = args.sample_frame
    previous_frame = args.previous_frame
    if args.sample_loop_transition:
        if args.previous_frame is not None:
            parser.error("--sample-loop-transition cannot be combined with --previous-frame")
        frame_pairs, loop_pair_index = playback_frame_indices(animation)
        if loop_pair_index >= len(frame_pairs):
            raise Lm2Error("animation does not have a loop transition to sample")
        sample_frame, previous_frame = frame_pairs[loop_pair_index]

    body: dict[str, Any] | None = None
    if args.body_asset is not None:
        body_asset = find_catalog_asset(catalog, args.body_asset)
        if body_asset.get("kind") != "model":
            raise Lm2Error(f"catalog asset is not a model: {args.body_asset}")
        body_payload, _ = read_hqr_payload(asset_root, body_asset["source"])
        model = load_lm2_bytes(body_payload, str(body_asset.get("label") or args.body_asset))
        body = {"asset_id": body_asset["id"], "bone_count": len(model.bones)}

    evidence = build_animation_evidence(
        animation,
        source={
            "catalog_asset_id": asset["id"],
            "catalog_label": asset.get("label"),
            "asset_root": str(asset_root),
            "hqr": asset["source"].get("hqr"),
            "entry_index": asset["source"].get("entry_index"),
            "classic_index": asset["source"].get("classic_index"),
            "resource": resource,
        },
        sample_frame=sample_frame,
        previous_frame=previous_frame,
        elapsed_ms=args.elapsed_ms,
        body=body,
    )
    write_animation_evidence(evidence, args.out)
    print(f"Wrote {args.out.resolve()}")
    print(
        json.dumps(
            {
                "schema_version": evidence["schema_version"],
                "asset_id": evidence["source"]["catalog_asset_id"],
                "keyframes": evidence["animation"]["keyframe_count"],
                "boneframes": evidence["animation"]["bone_count"],
            },
            indent=2,
        )
    )
    return 0


def is_export_subcommand(arguments: list[str]) -> bool:
    if arguments[:1] != ["export"]:
        return False
    return any(
        argument in {"-h", "--help", "--asset-root", "--asset", "--out", "--polygon-mode"}
        or argument.startswith("--asset-root=")
        or argument.startswith("--asset=")
        or argument.startswith("--out=")
        or argument.startswith("--polygon-mode=")
        for argument in arguments[1:]
    )


def is_contract_subcommand(arguments: list[str]) -> bool:
    return arguments[:1] == ["contract"]


def is_animation_subcommand(arguments: list[str]) -> bool:
    return arguments[:1] == ["animation"]


def is_catalog_graph_subcommand(arguments: list[str]) -> bool:
    return arguments[:1] == ["catalog-graph"]


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if is_export_subcommand(arguments):
        try:
            return export_probe_command(arguments[1:])
        except (Lm2Error, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if is_contract_subcommand(arguments):
        try:
            return contract_command(arguments[1:])
        except (Lm2Error, AnimationError, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if is_animation_subcommand(arguments):
        try:
            return animation_command(arguments[1:])
        except (Lm2Error, AnimationError, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if is_catalog_graph_subcommand(arguments):
        try:
            from .catalog_graph import catalog_graph_command

            return catalog_graph_command(arguments[1:])
        except (Lm2Error, AnimationError, lba_hqr.HqrError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    parser = argparse.ArgumentParser(
        description="View, inspect, or export LBA2 LM2 model files."
    )
    parser.add_argument("file", nargs="?", type=Path, help="LM2/LDC file to load")
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"viewer bind host, default {DEFAULT_HOST}"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"viewer bind port, default {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the browser automatically",
    )
    parser.add_argument(
        "--inspect", action="store_true", help="print parsed model stats and exit"
    )
    parser.add_argument(
        "--export-obj", type=Path, help="write a simple OBJ export and exit"
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=DEFAULT_ASSET_ROOT,
        help=f"folder containing the user's LBA2 HQR files, default {DEFAULT_ASSET_ROOT}",
    )
    args = parser.parse_args(arguments)

    try:
        if args.inspect:
            if args.file is None:
                parser.error("--inspect requires a file")
            inspect(args.file)
            return 0
        if args.export_obj is not None:
            if args.file is None:
                parser.error("--export-obj requires a file")
            model = load_lm2_path(args.file)
            export_obj(model, args.export_obj, str(args.file))
            print(f"Wrote {args.export_obj}")
            return 0
        from .server import serve

        serve(args.file, args.host, args.port, not args.no_browser, args.asset_root)
        return 0
    except (Lm2Error, lba_hqr.HqrError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
