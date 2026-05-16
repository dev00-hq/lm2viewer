"""Structural SCENE track/life script classification.

This module is intentionally an offline byte-layout analyzer. It names and
sizes script opcodes from the classic source and port-side audit work; it does
not execute scripts or claim gameplay semantics.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any

TRACK_OPCODE_NAMES = {
    0: "TM_END",
    1: "TM_NOP",
    2: "TM_BODY",
    3: "TM_ANIM",
    4: "TM_GOTO_POINT",
    5: "TM_WAIT_ANIM",
    6: "TM_LOOP",
    7: "TM_ANGLE",
    8: "TM_POS_POINT",
    9: "TM_LABEL",
    10: "TM_GOTO",
    11: "TM_STOP",
    12: "TM_GOTO_SYM_POINT",
    13: "TM_WAIT_NB_ANIM",
    14: "TM_SAMPLE",
    15: "TM_GOTO_POINT_3D",
    16: "TM_SPEED",
    17: "TM_BACKGROUND",
    18: "TM_WAIT_NB_SECOND",
    19: "TM_NO_BODY",
    20: "TM_BETA",
    21: "TM_OPEN_LEFT",
    22: "TM_OPEN_RIGHT",
    23: "TM_OPEN_UP",
    24: "TM_OPEN_DOWN",
    25: "TM_CLOSE",
    26: "TM_WAIT_DOOR",
    27: "TM_SAMPLE_RND",
    28: "TM_SAMPLE_ALWAYS",
    29: "TM_SAMPLE_STOP",
    30: "TM_PLAY_ACF",
    31: "TM_REPEAT_SAMPLE",
    32: "TM_SIMPLE_SAMPLE",
    33: "TM_FACE_TWINSEN",
    34: "TM_ANGLE_RND",
    35: "TM_REM",
    36: "TM_WAIT_NB_DIZIEME",
    37: "TM_DO",
    38: "TM_SPRITE",
    39: "TM_WAIT_NB_SECOND_RND",
    40: "TM_AFF_TIMER",
    41: "TM_SET_FRAME",
    42: "TM_SET_FRAME_3DS",
    43: "TM_SET_START_3DS",
    44: "TM_SET_END_3DS",
    45: "TM_START_ANIM_3DS",
    46: "TM_STOP_ANIM_3DS",
    47: "TM_WAIT_ANIM_3DS",
    48: "TM_WAIT_FRAME_3DS",
    49: "TM_WAIT_NB_DIZIEME_RND",
    50: "TM_DECALAGE",
    51: "TM_FREQUENCE",
    52: "TM_VOLUME",
}

SCRIPT_EXECUTION_CONTRACTS = {
    "LM_KILL_OBJ": {
        "contract": "object_lifecycle_death",
        "source": "GERELIFE.CPP",
        "effect": "clear target object body, zone, and life points",
    },
    "LM_SUICIDE": {
        "contract": "object_lifecycle_death",
        "source": "GERELIFE.CPP",
        "effect": "clear current object body, zone, and life points",
    },
    "LM_END": {
        "contract": "life_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "stop current life script",
    },
    "LM_END_LIFE": {
        "contract": "life_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "stop current life script",
    },
    "LM_RETURN": {
        "contract": "life_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "return from current life pass",
    },
    "LM_END_COMPORTEMENT": {
        "contract": "life_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "end current behavior pass",
    },
    "TM_END": {
        "contract": "track_pass_control",
        "source": "GERETRAK.CPP",
        "effect": "end current track pass",
    },
    "TM_STOP": {
        "contract": "track_pass_control",
        "source": "GERETRAK.CPP",
        "effect": "stop current track",
    },
    "LM_STOP_L_TRACK": {
        "contract": "track_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "stop current object track",
    },
    "LM_RESTORE_L_TRACK": {
        "contract": "track_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "restore current object track",
    },
    "LM_STOP_L_TRACK_OBJ": {
        "contract": "track_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "stop target object track when alive",
    },
    "LM_RESTORE_L_TRACK_OBJ": {
        "contract": "track_pass_control",
        "source": "GERELIFE.CPP",
        "effect": "restore target object track when alive",
    },
    "TM_WAIT_ANIM": {
        "contract": "animation_wait_control",
        "source": "GERETRAK.CPP",
        "effect": "wait for current animation completion",
    },
    "TM_WAIT_NB_ANIM": {
        "contract": "animation_wait_control",
        "source": "GERETRAK.CPP",
        "effect": "wait for animation count state",
    },
    "TM_STOP_ANIM_3DS": {
        "contract": "anim3ds_playback_control",
        "source": "GERETRAK.CPP",
        "effect": "stop projected 3D sprite animation",
    },
    "TM_WAIT_ANIM_3DS": {
        "contract": "anim3ds_playback_control",
        "source": "GERETRAK.CPP",
        "effect": "wait for projected 3D sprite animation completion",
    },
    "TM_NO_BODY": {
        "contract": "body_visibility_control",
        "source": "GERETRAK.CPP",
        "effect": "hide current object body",
    },
    "LM_NO_BODY": {
        "contract": "body_visibility_control",
        "source": "GERELIFE.CPP",
        "effect": "hide current object body",
    },
    "LM_SAVE_COMPORTEMENT": {
        "contract": "behavior_memory_control",
        "source": "GERELIFE.CPP",
        "effect": "save current object behavior",
    },
    "LM_RESTORE_COMPORTEMENT": {
        "contract": "behavior_memory_control",
        "source": "GERELIFE.CPP",
        "effect": "restore current object behavior",
    },
    "LM_SAVE_COMPORTEMENT_OBJ": {
        "contract": "behavior_memory_control",
        "source": "GERELIFE.CPP",
        "effect": "save target object behavior when alive",
    },
    "LM_RESTORE_COMPORTEMENT_OBJ": {
        "contract": "behavior_memory_control",
        "source": "GERELIFE.CPP",
        "effect": "restore target object behavior when alive",
    },
    "TM_BACKGROUND": {
        "contract": "background_incrust_redraw_control",
        "source": "GERETRAK.CPP",
        "effect": "toggle OBJ_BACKGROUND on the current object and request AFF_ALL redraw when the flag changes",
    },
    "LM_BACKGROUND": {
        "contract": "background_incrust_redraw_control",
        "source": "GERELIFE.CPP",
        "effect": "toggle OBJ_BACKGROUND on the current object and request AFF_ALL redraw when the flag changes",
    },
    "TM_PLAY_ACF": {
        "contract": "cinematic_playback_control",
        "source": "GERETRAK.CPP",
        "effect": "play ACF cinematic by name, restore timers/palette state, and request AFF_ALL redraw after playback",
    },
    "LM_PLAY_ACF": {
        "contract": "cinematic_playback_control",
        "source": "GERELIFE.CPP",
        "effect": "play ACF cinematic by name, restore timers/palette state, and request AFF_ALL redraw after playback",
    },
    "LM_GAME_OVER": {
        "contract": "game_flow_terminal",
        "source": "GERELIFE.CPP",
        "effect": "trigger game over",
    },
    "LM_THE_END": {
        "contract": "game_flow_terminal",
        "source": "GERELIFE.CPP",
        "effect": "trigger ending",
    },
    "LM_BRUTAL_EXIT": {
        "contract": "game_flow_terminal",
        "source": "GERELIFE.CPP",
        "effect": "force runtime exit path",
    },
    "TM_VOLUME": {
        "contract": "sample_parameter_control",
        "source": "GERETRAK.CPP",
        "effect": "set track sample volume parameter",
    },
    "TM_FREQUENCE": {
        "contract": "sample_parameter_control",
        "source": "GERETRAK.CPP",
        "effect": "set track sample frequency parameter",
    },
    "TM_DECALAGE": {
        "contract": "sample_parameter_control",
        "source": "GERETRAK.CPP",
        "effect": "set track sample offset parameter",
    },
    "LM_PARM_SAMPLE": {
        "contract": "sample_parameter_control",
        "source": "GERELIFE.CPP",
        "effect": "set current sample offset, volume, and frequency parameters",
    },
    "LM_NEW_SAMPLE": {
        "contract": "sample_parameter_control",
        "source": "GERELIFE.CPP",
        "effect": "play sample with offset, volume, and frequency parameters",
    },
}

TRACK_OPERAND_LAYOUTS = {
    **{opcode: "none" for opcode in [0, 1, 5, 11, 19, 25, 26, 35, 37, 40, 46, 47]},
    **{opcode: "u8" for opcode in [2, 4, 8, 12, 15, 41, 42, 43, 44, 45, 48, 52]},
    **{opcode: "i16" for opcode in [3, 10, 14, 16, 20, 21, 22, 23, 24, 27, 28, 29, 31, 32, 38, 50, 51]},
    6: "loop",
    7: "angle",
    9: "label",
    13: "wait_nb_anim",
    17: "background",
    18: "wait_timer",
    30: "string",
    33: "face_twinsen",
    34: "angle_rnd",
    36: "wait_timer",
    39: "wait_timer",
    49: "wait_timer",
}

TRACK_LAYOUT_BYTES = {
    "none": 0,
    "u8": 1,
    "i16": 2,
    "angle": 2,
    "label": 1,
    "background": 1,
    "face_twinsen": 2,
    "wait_nb_anim": 2,
    "wait_timer": 5,
    "loop": 4,
    "angle_rnd": 4,
}

LIFE_OPCODE_NAMES = {
    0: "LM_END",
    1: "LM_NOP",
    2: "LM_SNIF",
    3: "LM_OFFSET",
    4: "LM_NEVERIF",
    10: "LM_PALETTE",
    11: "LM_RETURN",
    12: "LM_IF",
    13: "LM_SWIF",
    14: "LM_ONEIF",
    15: "LM_ELSE",
    16: "LM_ENDIF",
    17: "LM_BODY",
    18: "LM_BODY_OBJ",
    19: "LM_ANIM",
    20: "LM_ANIM_OBJ",
    21: "LM_SET_CAMERA",
    22: "LM_CAMERA_CENTER",
    23: "LM_SET_TRACK",
    24: "LM_SET_TRACK_OBJ",
    25: "LM_MESSAGE",
    26: "LM_FALLABLE",
    27: "LM_SET_DIR",
    28: "LM_SET_DIR_OBJ",
    29: "LM_CAM_FOLLOW",
    30: "LM_COMPORTEMENT_HERO",
    31: "LM_SET_VAR_CUBE",
    32: "LM_COMPORTEMENT",
    33: "LM_SET_COMPORTEMENT",
    34: "LM_SET_COMPORTEMENT_OBJ",
    35: "LM_END_COMPORTEMENT",
    36: "LM_SET_VAR_GAME",
    37: "LM_KILL_OBJ",
    38: "LM_SUICIDE",
    39: "LM_USE_ONE_LITTLE_KEY",
    40: "LM_GIVE_GOLD_PIECES",
    41: "LM_END_LIFE",
    42: "LM_STOP_L_TRACK",
    43: "LM_RESTORE_L_TRACK",
    44: "LM_MESSAGE_OBJ",
    45: "LM_INC_CHAPTER",
    46: "LM_FOUND_OBJECT",
    47: "LM_SET_DOOR_LEFT",
    48: "LM_SET_DOOR_RIGHT",
    49: "LM_SET_DOOR_UP",
    50: "LM_SET_DOOR_DOWN",
    51: "LM_GIVE_BONUS",
    52: "LM_CHANGE_CUBE",
    53: "LM_OBJ_COL",
    54: "LM_BRICK_COL",
    55: "LM_OR_IF",
    56: "LM_INVISIBLE",
    57: "LM_SHADOW_OBJ",
    58: "LM_POS_POINT",
    59: "LM_SET_MAGIC_LEVEL",
    60: "LM_SUB_MAGIC_POINT",
    61: "LM_SET_LIFE_POINT_OBJ",
    62: "LM_SUB_LIFE_POINT_OBJ",
    63: "LM_HIT_OBJ",
    64: "LM_PLAY_ACF",
    65: "LM_ECLAIR",
    66: "LM_INC_CLOVER_BOX",
    67: "LM_SET_USED_INVENTORY",
    68: "LM_ADD_CHOICE",
    69: "LM_ASK_CHOICE",
    70: "LM_INIT_BUGGY",
    71: "LM_MEMO_ARDOISE",
    72: "LM_SET_HOLO_POS",
    73: "LM_CLR_HOLO_POS",
    74: "LM_ADD_FUEL",
    75: "LM_SUB_FUEL",
    76: "LM_SET_GRM",
    77: "LM_SET_CHANGE_CUBE",
    78: "LM_MESSAGE_ZOE",
    79: "LM_FULL_POINT",
    80: "LM_BETA",
    81: "LM_FADE_TO_PAL",
    82: "LM_ACTION",
    83: "LM_SET_FRAME",
    84: "LM_SET_SPRITE",
    85: "LM_SET_FRAME_3DS",
    86: "LM_IMPACT_OBJ",
    87: "LM_IMPACT_POINT",
    88: "LM_ADD_MESSAGE",
    89: "LM_BULLE",
    90: "LM_NO_CHOC",
    91: "LM_ASK_CHOICE_OBJ",
    92: "LM_CINEMA_MODE",
    93: "LM_SAVE_HERO",
    94: "LM_RESTORE_HERO",
    95: "LM_ANIM_SET",
    96: "LM_PLUIE",
    97: "LM_GAME_OVER",
    98: "LM_THE_END",
    99: "LM_ESCALATOR",
    100: "LM_PLAY_MUSIC",
    101: "LM_TRACK_TO_VAR_GAME",
    102: "LM_VAR_GAME_TO_TRACK",
    103: "LM_ANIM_TEXTURE",
    104: "LM_ADD_MESSAGE_OBJ",
    105: "LM_BRUTAL_EXIT",
    106: "LM_REM",
    107: "LM_ECHELLE",
    108: "LM_SET_ARMURE",
    109: "LM_SET_ARMURE_OBJ",
    110: "LM_ADD_LIFE_POINT_OBJ",
    111: "LM_STATE_INVENTORY",
    112: "LM_AND_IF",
    113: "LM_SWITCH",
    114: "LM_OR_CASE",
    115: "LM_CASE",
    116: "LM_DEFAULT",
    117: "LM_BREAK",
    118: "LM_END_SWITCH",
    119: "LM_SET_HIT_ZONE",
    120: "LM_SAVE_COMPORTEMENT",
    121: "LM_RESTORE_COMPORTEMENT",
    122: "LM_SAMPLE",
    123: "LM_SAMPLE_RND",
    124: "LM_SAMPLE_ALWAYS",
    125: "LM_SAMPLE_STOP",
    126: "LM_REPEAT_SAMPLE",
    127: "LM_BACKGROUND",
    128: "LM_ADD_VAR_GAME",
    129: "LM_SUB_VAR_GAME",
    130: "LM_ADD_VAR_CUBE",
    131: "LM_SUB_VAR_CUBE",
    132: "LM_NOP_132",
    133: "LM_SET_RAIL",
    134: "LM_INVERSE_BETA",
    135: "LM_NO_BODY",
    136: "LM_ADD_GOLD_PIECES",
    137: "LM_STOP_L_TRACK_OBJ",
    138: "LM_RESTORE_L_TRACK_OBJ",
    139: "LM_SAVE_COMPORTEMENT_OBJ",
    140: "LM_RESTORE_COMPORTEMENT_OBJ",
    141: "LM_SPY",
    142: "LM_DEBUG",
    143: "LM_DEBUG_OBJ",
    144: "LM_POPCORN",
    145: "LM_FLOW_POINT",
    146: "LM_FLOW_OBJ",
    147: "LM_SET_ANIM_DIAL",
    148: "LM_PCX",
    149: "LM_END_MESSAGE",
    150: "LM_END_MESSAGE_OBJ",
    151: "LM_PARM_SAMPLE",
    152: "LM_NEW_SAMPLE",
    153: "LM_POS_OBJ_AROUND",
    154: "LM_PCX_MESS_OBJ",
}

LIFE_UNSUPPORTED_OPCODES = {1, 16, 106, 141, 142, 143}
LIFE_OPERAND_LAYOUTS = {
    **{opcode: "none" for opcode in [0, 11, 35, 38, 41, 42, 43, 45, 39, 66, 79, 97, 98, 105, 120, 121, 134, 135, 144, 93, 94, 82, 149, 132, 116, 118]},
    **{opcode: "u8" for opcode in [32, 26, 30, 59, 60, 29, 37, 17, 67, 46, 52, 74, 75, 72, 73, 53, 56, 54, 58, 89, 100, 10, 81, 22, 71, 101, 102, 83, 85, 90, 92, 103, 150, 70, 65, 96, 127, 51, 137, 138, 139, 140]},
    **{opcode: "u8_pair" for opcode in [61, 62, 110, 63, 18, 31, 130, 131, 111, 107, 119, 76, 77, 145, 148, 21, 133, 57, 146, 153, 99]},
    **{opcode: "i16" for opcode in [33, 23, 25, 88, 78, 40, 136, 47, 48, 49, 50, 68, 69, 80, 122, 123, 124, 125, 84, 3, 15, 117]},
    **{opcode: "u16" for opcode in [19, 95, 147]},
    **{opcode: "u8_i16" for opcode in [34, 24, 44, 104, 36, 128, 129, 91]},
    108: "i8",
    109: "u8_i8",
    126: "i16_u8",
    87: "u8_u16",
    20: "u8_u16",
    86: "u8_u16_i16",
    154: "u8_u8_u8_i16",
    151: "i16_u8_i16",
    152: "i16_i16_u8_i16",
    27: "move",
    28: "move_obj",
    64: "string",
    12: "condition",
    112: "condition",
    55: "condition",
    13: "condition",
    2: "condition",
    14: "condition",
    4: "condition",
    113: "switch_expr",
    115: "case_branch",
    114: "case_branch",
}

LIFE_LAYOUT_BYTES = {
    "none": 0,
    "u8": 1,
    "i8": 1,
    "u16": 2,
    "i16": 2,
    "u8_pair": 2,
    "u8_i8": 2,
    "u8_i16": 3,
    "i16_u8": 3,
    "u8_u16": 3,
    "u8_u16_i16": 5,
    "i16_u8_i16": 5,
    "u8_u8_u8_i16": 5,
    "i16_i16_u8_i16": 7,
}

LIFE_FUNCTION_NAMES = {
    0: "LF_COL",
    1: "LF_COL_OBJ",
    2: "LF_DISTANCE",
    3: "LF_ZONE",
    4: "LF_ZONE_OBJ",
    5: "LF_BODY",
    6: "LF_BODY_OBJ",
    7: "LF_ANIM",
    8: "LF_ANIM_OBJ",
    9: "LF_L_TRACK",
    10: "LF_L_TRACK_OBJ",
    11: "LF_VAR_CUBE",
    12: "LF_CONE_VIEW",
    13: "LF_HIT_BY",
    14: "LF_ACTION",
    15: "LF_VAR_GAME",
    16: "LF_LIFE_POINT",
    17: "LF_LIFE_POINT_OBJ",
    18: "LF_NB_LITTLE_KEYS",
    19: "LF_NB_GOLD_PIECES",
    20: "LF_COMPORTEMENT_HERO",
    21: "LF_CHAPTER",
    22: "LF_DISTANCE_3D",
    23: "LF_MAGIC_LEVEL",
    24: "LF_MAGIC_POINT",
    25: "LF_USE_INVENTORY",
    26: "LF_CHOICE",
    27: "LF_FUEL",
    28: "LF_CARRY_BY",
    29: "LF_CDROM",
    30: "LF_ECHELLE",
    31: "LF_RND",
    32: "LF_RAIL",
    33: "LF_BETA",
    34: "LF_BETA_OBJ",
    35: "LF_CARRY_OBJ_BY",
    36: "LF_ANGLE",
    37: "LF_DISTANCE_MESSAGE",
    38: "LF_HIT_OBJ_BY",
    39: "LF_REAL_ANGLE",
    40: "LF_DEMO",
    41: "LF_COL_DECORS",
    42: "LF_COL_DECORS_OBJ",
    43: "LF_PROCESSOR",
    44: "LF_OBJECT_DISPLAYED",
    45: "LF_ANGLE_OBJ",
}
LIFE_FUNCTIONS_WITH_U8 = {
    1, 2, 4, 6, 8, 10, 11, 12, 15, 17, 25, 30,
    22, 31, 32, 34, 35, 36, 37, 38, 39, 42, 44, 45,
}
LIFE_FUNCTION_RETURN_TYPES = {
    **{opcode: "s16" for opcode in [2, 7, 8, 12, 15, 16, 17, 19, 22, 26, 27, 33, 34, 36, 37, 39, 45]},
    **{opcode: "u8" for opcode in [9, 10, 11, 31, 41]},
}
LIFE_COMPARATOR_NAMES = {
    0: "LT_EQUAL",
    1: "LT_SUP",
    2: "LT_LESS",
    3: "LT_SUP_EQUAL",
    4: "LT_LESS_EQUAL",
    5: "LT_DIFFERENT",
}
LIFE_MOVES_WITH_PARAMETER = {2, 6, 9, 10, 11}
LIFE_MOVE_NAMES = {
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
LIFE_MOVE_PARAMETER_NAMES = {
    2: "follow_object_id",
    6: "follow_object_id",
    9: "circle_waypoint_id",
    10: "circle_waypoint_id",
    11: "follow_object_id",
}
LIFE_HERO_BEHAVIOR_NAMES = {
    0: "C_NORMAL",
    1: "C_SPORTIF",
    2: "C_AGRESSIF",
    3: "C_DISCRET",
    4: "C_PROTOPACK",
    5: "C_DOUBLE",
    6: "C_CONQUE",
    7: "C_SCAPH_INT_NORM",
    8: "C_JETPACK",
    9: "C_SCAPH_INT_SPOR",
    10: "C_SCAPH_EXT_NORM",
    11: "C_SCAPH_EXT_SPOR",
    12: "C_BUGGY",
    13: "C_SKELETON",
}
LIFE_FUNCTION_PARAMETER_NAMES = {
    **{function_id: "object_id" for function_id in [1, 2, 4, 6, 8, 10, 12, 17, 22, 34, 35, 38, 42, 44, 45]},
    11: "var_cube_id",
    15: "var_game_id",
    25: "inventory_id",
    30: "ladder_zone_id",
    31: "random_max",
    32: "rail_zone_id",
    37: "text_id",
    39: "object_id",
}

SCRIPT_REFERENCE_KEYS = (
    "body",
    "animation",
    "sprite",
    "waypoint",
    "script_offset",
    "track_label",
    "object",
    "text",
    "var_cube",
    "var_game",
    "inventory",
    "sample",
    "music",
    "behavior",
    "palette",
    "pcx",
    "holomap",
    "buggy",
    "camera_zone",
    "ladder_zone",
    "grm_zone",
    "rail_zone",
    "hit_zone",
    "escalator_zone",
    "change_cube_control",
    "cube",
)

SAME_SCRIPT_TARGET_FIELDS = ("target_offset", "branch_offset", "target_life_offset")
TRACK_RUNTIME_STATE_FIELDS = {
    6: [("current_count", 1, 1, "classic_track_runtime")],
    7: [("target_beta_runtime_flag", 0, 2, "classic_track_runtime")],
    13: [("current_count", 1, 1, "classic_track_runtime")],
    18: [("runtime_timer_ref", 1, 4, "classic_track_runtime")],
    33: [("runtime_face_beta", 0, 2, "classic_track_runtime")],
    34: [("runtime_target_beta", 2, 2, "classic_track_runtime")],
    36: [("runtime_timer_ref", 1, 4, "classic_track_runtime")],
    39: [("runtime_timer_ref", 1, 4, "classic_track_runtime")],
    49: [("runtime_timer_ref", 1, 4, "classic_track_runtime")],
}
TRACK_RUNTIME_STATE_VALUE_ALIASES = {
    "target_beta_runtime_flag": "target_beta",
}


TRACK_BEHAVIOR_CATEGORIES = {
    **{opcode: "control_flow" for opcode in [0, 1, 6, 9, 10, 11, 35, 37]},
    **{opcode: "model_animation" for opcode in [2, 3, 5, 13, 19, 41]},
    **{opcode: "movement_path" for opcode in [4, 7, 8, 12, 15, 16, 20, 33, 34, 50]},
    **{opcode: "timing_wait" for opcode in [18, 36, 39, 49]},
    **{opcode: "audio" for opcode in [14, 27, 28, 29, 30, 31, 32, 51, 52]},
    **{opcode: "door_background" for opcode in [17, 21, 22, 23, 24, 25, 26]},
    **{opcode: "sprite_3d_state" for opcode in [38, 42, 43, 44, 45, 46, 47, 48]},
    40: "ui_timer",
}

LIFE_BEHAVIOR_CATEGORIES = {
    **{opcode: "control_flow" for opcode in [0, 2, 3, 4, 11, 12, 13, 14, 15, 16, 35, 41, 55, 112, 113, 114, 115, 116, 117, 118, 132]},
    **{opcode: "model_animation" for opcode in [17, 18, 19, 20, 26, 32, 33, 34, 95, 107, 120, 121, 135, 139, 140, 147]},
    **{opcode: "movement_path" for opcode in [23, 24, 27, 28, 42, 43, 58, 80, 83, 101, 102, 134, 137, 138, 153]},
    **{opcode: "camera" for opcode in [21, 22, 29]},
    **{opcode: "dialogue_ui" for opcode in [25, 44, 68, 69, 78, 88, 89, 91, 104, 148, 149, 150, 154]},
    **{opcode: "inventory_state" for opcode in [39, 40, 46, 51, 59, 60, 66, 67, 72, 73, 74, 75, 79, 108, 109, 111, 136]},
    **{opcode: "variables_conditions" for opcode in [30, 31, 36, 45, 71, 128, 129, 130, 131]},
    **{opcode: "object_lifecycle" for opcode in [37, 38, 52, 93, 94, 97, 98, 105]},
    **{opcode: "collision_combat" for opcode in [53, 54, 61, 62, 63, 86, 87, 90, 110, 119]},
    **{opcode: "zone_scene_control" for opcode in [76, 77, 99, 133]},
    **{opcode: "sprite_3d_state" for opcode in [84, 85]},
    **{opcode: "door_background" for opcode in [47, 48, 49, 50, 127]},
    **{opcode: "audio" for opcode in [64, 100, 122, 123, 124, 125, 126, 151, 152]},
    **{opcode: "visual_effects" for opcode in [10, 56, 57, 65, 81, 92, 96, 103, 144, 145, 146]},
    **{opcode: "debug_noop" for opcode in [1, 106, 141, 142, 143]},
    70: "vehicle",
    82: "action_state",
}


def analyze_track_script(script: bytes) -> dict[str, Any]:
    return analyze_scene_script("track", script)


def analyze_life_script(script: bytes) -> dict[str, Any]:
    return analyze_scene_script("life", script)


def analyze_scene_script(kind: str, script: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": kind,
        "byte_length": len(script),
        "sha256": hashlib.sha256(script).hexdigest(),
        "instruction_count": 0,
        "decoded_bytes": 0,
        "status": "empty" if not script else "decoded",
        "unique_opcodes": [],
        "first_instructions": [],
        "control_flow_links": [],
        "label_definitions": [],
        "runtime_state_fields": [],
        "cinematic_refs": [],
        "references": {key: [] for key in SCRIPT_REFERENCE_KEYS},
    }
    if not script:
        return result

    counts: dict[int, int] = {}
    category_counts: dict[str, int] = {}
    references: dict[str, set[int]] = {key: set() for key in result["references"]}
    decoded_script = decode_scene_script_instruction_graph(kind, script)
    all_instructions = decoded_script["instructions"]
    for instruction in all_instructions:
        counts[instruction["opcode"]] = counts.get(instruction["opcode"], 0) + 1
        category = instruction["behavior_category"]
        category_counts[category] = category_counts.get(category, 0) + 1
        collect_script_references(instruction, references)

    result["status"] = decoded_script["status"]
    result["decoded_bytes"] = decoded_script["decoded_bytes"]
    result["instruction_count"] = len(all_instructions)
    if decoded_script.get("failure") is not None:
        result["failure"] = decoded_script["failure"]
    if decoded_script.get("unreachable_byte_ranges"):
        result["unreachable_byte_ranges"] = decoded_script["unreachable_byte_ranges"]
        result["unreachable_bytes"] = decoded_script["unreachable_bytes"]

    names = TRACK_OPCODE_NAMES if kind == "track" else LIFE_OPCODE_NAMES
    result["unique_opcodes"] = [
        {
            "opcode": opcode,
            "mnemonic": names.get(opcode, f"UNKNOWN_{opcode}"),
            "count": count,
        }
        for opcode, count in sorted(counts.items())
    ]
    result["behavior_categories"] = [
        {"category": category, "count": count}
        for category, count in sorted(category_counts.items())
    ]
    result["first_instructions"] = all_instructions[:16]
    result["control_flow_links"] = script_control_flow_links(kind, all_instructions, len(script))
    result["label_definitions"] = script_label_definitions(kind, all_instructions)
    result["runtime_state_fields"] = script_runtime_state_fields(kind, all_instructions)
    result["execution_contracts"] = script_execution_contracts(all_instructions)
    result["condition_functions"] = script_condition_functions(all_instructions)
    result["condition_comparators"] = script_condition_comparators(all_instructions)
    result["cinematic_refs"] = script_cinematic_refs(kind, all_instructions)
    result["references"] = {key: sorted(value) for key, value in references.items()}
    return result


def script_execution_contracts(instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    examples: dict[str, dict[str, str]] = {}
    mnemonics: dict[str, set[str]] = {}
    for instruction in instructions:
        mnemonic = str(instruction.get("mnemonic") or "")
        contract = SCRIPT_EXECUTION_CONTRACTS.get(mnemonic)
        if contract is None:
            continue
        key = contract["contract"]
        counts[key] = counts.get(key, 0) + 1
        examples.setdefault(key, contract)
        mnemonics.setdefault(key, set()).add(mnemonic)
    return [
        {
            "contract": key,
            "count": counts[key],
            "source": examples[key]["source"],
            "effect": examples[key]["effect"],
            "mnemonics": sorted(mnemonics[key]),
        }
        for key in sorted(counts)
    ]


def script_condition_functions(instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    return_types: dict[str, str] = {}
    function_ids: dict[str, int] = {}
    opcodes: dict[str, set[str]] = {}
    for instruction in instructions:
        semantics = instruction.get("operand_semantics") or {}
        function = semantics.get("function")
        if not isinstance(function, str):
            continue
        counts[function] = counts.get(function, 0) + 1
        return_type = semantics.get("return_type")
        if isinstance(return_type, str):
            return_types.setdefault(function, return_type)
        function_id = semantics.get("function_id")
        if isinstance(function_id, int) and not isinstance(function_id, bool):
            function_ids.setdefault(function, function_id)
        mnemonic = str(instruction.get("mnemonic") or "")
        if mnemonic:
            opcodes.setdefault(function, set()).add(mnemonic)
    return [
        {
            "function": function,
            "function_id": function_ids.get(function),
            "count": counts[function],
            "return_type": return_types.get(function, "unknown"),
            "opcodes": sorted(opcodes.get(function, set())),
        }
        for function in sorted(counts)
    ]


def script_condition_comparators(instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    opcodes: dict[str, set[str]] = {}
    functions: dict[str, set[str]] = {}
    for instruction in instructions:
        semantics = instruction.get("operand_semantics") or {}
        comparator = semantics.get("comparator")
        if not isinstance(comparator, str):
            continue
        counts[comparator] = counts.get(comparator, 0) + 1
        mnemonic = str(instruction.get("mnemonic") or "")
        if mnemonic:
            opcodes.setdefault(comparator, set()).add(mnemonic)
        function = semantics.get("function")
        if isinstance(function, str):
            functions.setdefault(comparator, set()).add(function)
    return [
        {
            "comparator": comparator,
            "count": counts[comparator],
            "opcodes": sorted(opcodes.get(comparator, set())),
            "functions": sorted(functions.get(comparator, set())),
        }
        for comparator in sorted(counts)
    ]


def decode_scene_script_instruction_graph(kind: str, script: bytes) -> dict[str, Any]:
    if kind == "track":
        return decode_track_script_linear(script)
    return decode_life_script_worklist(script)


def decode_track_script_linear(script: bytes) -> dict[str, Any]:
    instructions: list[dict[str, Any]] = []
    offset = 0
    failure: dict[str, Any] | None = None
    while offset < len(script):
        decoded = decode_track_instruction(script, offset)
        if decoded.get("status") != "decoded":
            failure = {
                "offset": offset,
                "opcode": decoded.get("opcode"),
                "mnemonic": decoded.get("mnemonic"),
            }
            break
        instruction = decoded["instruction"]
        instructions.append(instruction)
        offset += instruction["byte_length"]
    return {
        "instructions": instructions,
        "decoded_bytes": offset,
        "status": "decoded" if failure is None else decoded["status"],
        "failure": failure,
        "unreachable_byte_ranges": [],
        "unreachable_bytes": 0,
    }


def decode_life_script_worklist(script: bytes) -> dict[str, Any]:
    instructions_by_offset: dict[int, dict[str, Any]] = {}
    pending_targets: dict[int, tuple[str, ...]] = {0: ()}
    failures: list[dict[str, Any]] = []
    skipped_ranges: list[dict[str, Any]] = []

    while pending_targets:
        offset = min(pending_targets)
        stack_state = pending_targets.pop(offset)
        if offset < 0 or offset >= len(script):
            continue
        if offset in instructions_by_offset or offset_inside_instruction(offset, instructions_by_offset):
            continue

        switch_return_stack = list(stack_state)
        while offset < len(script):
            if offset in instructions_by_offset or offset_inside_instruction(offset, instructions_by_offset):
                break
            decoded = decode_life_instruction(
                script,
                offset,
                switch_return_stack[-1] if switch_return_stack else None,
            )
            if decoded.get("status") != "decoded":
                failure = {
                    "offset": offset,
                    "opcode": decoded.get("opcode"),
                    "mnemonic": decoded.get("mnemonic"),
                    "status": decoded.get("status"),
                    "switch_return_stack": list(switch_return_stack),
                }
                resume_offset = next(
                    (
                        target_offset
                        for target_offset in sorted(pending_targets)
                        if target_offset > offset
                    ),
                    None,
                )
                if resume_offset is None:
                    failures.append(failure)
                else:
                    raw = script[offset:resume_offset]
                    skipped_ranges.append(
                        {
                            "offset": offset,
                            "length": resume_offset - offset,
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "note": f"bytes skipped after {decoded.get('status')} until next known script target",
                        }
                    )
                break

            instruction = decoded["instruction"]
            instructions_by_offset[offset] = instruction
            enqueue_life_targets(instruction, switch_return_stack, pending_targets, len(script))
            update_life_switch_stack(switch_return_stack, instruction)
            offset += instruction["byte_length"]

    instructions = [
        instructions_by_offset[offset]
        for offset in sorted(instructions_by_offset)
    ]
    decoded_bytes = max(
        (instruction["offset"] + instruction["byte_length"] for instruction in instructions),
        default=0,
    )
    status = "decoded" if not failures else str(failures[0]["status"])
    return {
        "instructions": instructions,
        "decoded_bytes": decoded_bytes,
        "status": status,
        "failure": failures[0] if failures else None,
        "failures": failures,
        "unreachable_byte_ranges": skipped_ranges[:16],
        "unreachable_bytes": sum(item["length"] for item in skipped_ranges),
    }


def offset_inside_instruction(offset: int, instructions_by_offset: dict[int, dict[str, Any]]) -> bool:
    return any(
        instruction["offset"] < offset < instruction["offset"] + instruction["byte_length"]
        for instruction in instructions_by_offset.values()
    )


def enqueue_life_targets(
    instruction: dict[str, Any],
    switch_return_stack: list[str],
    pending_targets: dict[int, tuple[str, ...]],
    script_byte_length: int,
) -> None:
    semantics = instruction["operand_semantics"]
    current_stack = tuple(switch_return_stack)

    for field in SAME_SCRIPT_TARGET_FIELDS:
        target_offset = semantics.get(field)
        if not isinstance(target_offset, int) or isinstance(target_offset, bool):
            continue
        if target_offset < 0 or target_offset >= script_byte_length:
            continue
        target_stack: tuple[str, ...]
        if field == "target_life_offset" and "object_id" not in semantics:
            target_stack = ()
        else:
            target_stack = current_stack
        pending_targets.setdefault(target_offset, target_stack)


def update_life_switch_stack(switch_return_stack: list[str], instruction: dict[str, Any]) -> None:
    mnemonic = instruction["mnemonic"]
    if mnemonic == "LM_SWITCH":
        return_type = instruction["operand_semantics"].get("return_type")
        if isinstance(return_type, str):
            switch_return_stack.append(return_type)
    elif mnemonic == "LM_END_SWITCH" and switch_return_stack:
        switch_return_stack.pop()


def decode_track_instruction(script: bytes, offset: int) -> dict[str, Any]:
    opcode = script[offset]
    mnemonic = TRACK_OPCODE_NAMES.get(opcode)
    if mnemonic is None:
        return {"status": "unknown_opcode", "opcode": opcode}
    layout = TRACK_OPERAND_LAYOUTS[opcode]
    if layout == "string":
        end = script.find(b"\x00", offset + 1)
        if end == -1:
            return {"status": "malformed_string_operand", "opcode": opcode, "mnemonic": mnemonic}
        end += 1
    else:
        end = offset + 1 + TRACK_LAYOUT_BYTES[layout]
    if end > len(script):
        return {"status": "truncated_operand", "opcode": opcode, "mnemonic": mnemonic}
    return {
        "status": "decoded",
        "instruction": script_instruction_summary(script, offset, opcode, mnemonic, layout, end),
    }


def decode_life_instruction(
    script: bytes, offset: int, active_switch_return_type: str | None
) -> dict[str, Any]:
    opcode = script[offset]
    mnemonic = LIFE_OPCODE_NAMES.get(opcode)
    if mnemonic is None:
        return {"status": "unknown_opcode", "opcode": opcode}
    if opcode in LIFE_UNSUPPORTED_OPCODES:
        return {"status": "unsupported_opcode", "opcode": opcode, "mnemonic": mnemonic}
    layout = LIFE_OPERAND_LAYOUTS[opcode]
    switch_return_type = active_switch_return_type
    if layout == "string":
        end = script.find(b"\x00", offset + 1)
        if end == -1:
            return {"status": "malformed_string_operand", "opcode": opcode, "mnemonic": mnemonic}
        end += 1
    elif layout == "move":
        if offset + 2 > len(script):
            return {"status": "truncated_operand", "opcode": opcode, "mnemonic": mnemonic}
        end = offset + 2 + int(script[offset + 1] in LIFE_MOVES_WITH_PARAMETER)
    elif layout == "move_obj":
        if offset + 3 > len(script):
            return {"status": "truncated_operand", "opcode": opcode, "mnemonic": mnemonic}
        end = offset + 3 + int(script[offset + 2] in LIFE_MOVES_WITH_PARAMETER)
    elif layout == "condition":
        decoded = decode_life_condition_length(script, offset + 1)
        if decoded["status"] != "decoded":
            return {"opcode": opcode, "mnemonic": mnemonic, **decoded}
        end = decoded["end"] + 2
    elif layout == "switch_expr":
        decoded = decode_life_function_length(script, offset + 1)
        if decoded["status"] != "decoded":
            return {"opcode": opcode, "mnemonic": mnemonic, **decoded}
        end = decoded["end"]
        switch_return_type = decoded["return_type"]
    elif layout == "case_branch":
        if active_switch_return_type is None:
            return {"status": "missing_switch_context", "opcode": opcode, "mnemonic": mnemonic}
        if offset + 3 > len(script):
            return {"status": "truncated_operand", "opcode": opcode, "mnemonic": mnemonic}
        decoded = decode_life_test_length(script, offset + 3, active_switch_return_type)
        if decoded["status"] != "decoded":
            return {"opcode": opcode, "mnemonic": mnemonic, **decoded}
        end = decoded["end"]
    else:
        end = offset + 1 + LIFE_LAYOUT_BYTES[layout]
    if opcode == 118:
        switch_return_type = None
    if end > len(script):
        return {"status": "truncated_operand", "opcode": opcode, "mnemonic": mnemonic}
    return {
        "status": "decoded",
        "active_switch_return_type": switch_return_type,
        "instruction": script_instruction_summary(
            script,
            offset,
            opcode,
            mnemonic,
            layout,
            end,
            active_switch_return_type=active_switch_return_type,
        ),
    }


def decode_life_function_length(script: bytes, offset: int) -> dict[str, Any]:
    if offset >= len(script):
        return {"status": "truncated_operand"}
    function_id = script[offset]
    if function_id not in LIFE_FUNCTION_NAMES:
        return {"status": "unknown_life_function"}
    end = offset + (2 if function_id in LIFE_FUNCTIONS_WITH_U8 else 1)
    if end > len(script):
        return {"status": "truncated_operand"}
    return {
        "status": "decoded",
        "end": end,
        "return_type": LIFE_FUNCTION_RETURN_TYPES.get(function_id, "s8"),
    }


def decode_life_test_length(script: bytes, offset: int, return_type: str) -> dict[str, Any]:
    if offset >= len(script):
        return {"status": "truncated_operand"}
    if script[offset] not in LIFE_COMPARATOR_NAMES:
        return {"status": "unknown_life_comparator"}
    if return_type in {"s8", "u8"}:
        end = offset + 2
    elif return_type == "s16":
        end = offset + 3
    elif return_type == "string":
        terminator = script.find(b"\x00", offset + 1)
        if terminator == -1:
            return {"status": "malformed_string_operand"}
        end = terminator + 1
    else:
        return {"status": "unknown_life_function"}
    if end > len(script):
        return {"status": "truncated_operand"}
    return {"status": "decoded", "end": end}


def decode_life_condition_length(script: bytes, offset: int) -> dict[str, Any]:
    function = decode_life_function_length(script, offset)
    if function["status"] != "decoded":
        return function
    test = decode_life_test_length(script, function["end"], function["return_type"])
    if test["status"] != "decoded":
        return test
    if test["end"] + 2 > len(script):
        return {"status": "truncated_operand"}
    return {"status": "decoded", "end": test["end"]}


def script_instruction_summary(
    script: bytes,
    offset: int,
    opcode: int,
    mnemonic: str,
    layout: str,
    end: int,
    active_switch_return_type: str | None = None,
) -> dict[str, Any]:
    operand_bytes = script[offset + 1 : end]
    kind = "track" if mnemonic.startswith("TM_") else "life"
    category = script_behavior_category(kind, opcode)
    semantics = script_operand_semantics(kind, opcode, operand_bytes, active_switch_return_type)
    return {
        "offset": offset,
        "opcode": opcode,
        "mnemonic": mnemonic,
        "byte_length": end - offset,
        "operand_layout": layout,
        "operand_hex": operand_bytes.hex(),
        "operand_semantics": semantics,
        "behavior_category": category,
        "behavior_effect": script_behavior_effect(mnemonic, category),
    }


def script_operand_semantics(
    kind: str, opcode: int, raw: bytes, active_switch_return_type: str | None = None
) -> dict[str, Any]:
    if kind == "track":
        return track_operand_semantics(opcode, raw)
    return life_operand_semantics(opcode, raw, active_switch_return_type)


def track_operand_semantics(opcode: int, raw: bytes) -> dict[str, Any]:
    if opcode in {0, 11}:
        return {"track_action": "stop_current_track", "offset_track": -1}
    if opcode == 35:
        return {"structural_marker": "track_comment", "runtime_effect": "none"}
    if opcode == 2 and len(raw) >= 1:
        return {"body_id": raw[0]}
    if opcode == 3 and len(raw) >= 2:
        return {"animation_id": struct.unpack_from("<H", raw)[0]}
    if opcode in {4, 8, 12, 15} and len(raw) >= 1:
        return {"waypoint_id": raw[0]}
    if opcode == 5:
        return {"wait_for_animation_end": True, "completion_action": "clear_real_angle"}
    if opcode == 6 and len(raw) >= 4:
        return {
            "initial_count": raw[0],
            "current_count": raw[1],
            "target_offset": struct.unpack_from("<h", raw, 2)[0],
        }
    if opcode == 7 and len(raw) >= 2:
        return {"target_beta": struct.unpack_from("<h", raw)[0]}
    if opcode == 9 and len(raw) >= 1:
        return {"track_label": raw[0]}
    if opcode == 10 and len(raw) >= 2:
        return {"target_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 13 and len(raw) >= 2:
        return {"target_count": raw[0], "current_count": raw[1]}
    if opcode == 18 and len(raw) >= 5:
        return {
            "duration_count": raw[0],
            "runtime_timer_ref": struct.unpack_from("<I", raw, 1)[0],
        }
    if opcode == 19:
        return {"body_action": "hide_current_object_body"}
    if opcode == 16 and len(raw) >= 2:
        return {"speed_raw": struct.unpack_from("<h", raw)[0]}
    if opcode == 17 and len(raw) >= 1:
        return {"enabled": bool(raw[0])}
    if opcode == 20 and len(raw) >= 2:
        return {"beta": struct.unpack_from("<h", raw)[0]}
    if opcode in {21, 22, 23, 24} and len(raw) >= 2:
        return {"door_width": struct.unpack_from("<h", raw)[0]}
    if opcode == 25:
        return {"door_action": "close"}
    if opcode == 26:
        return {"wait_for_door": True}
    if opcode in {14, 27, 28, 29, 31, 32} and len(raw) >= 2:
        return {"sample_id": struct.unpack_from("<h", raw)[0]}
    if opcode == 30:
        return {
            "acf_name": raw.rstrip(b"\x00").decode("latin-1", errors="replace"),
            "cinematic_action": "play_acf",
        }
    if opcode == 33 and len(raw) >= 2:
        return {"runtime_face_beta": struct.unpack_from("<h", raw)[0]}
    if opcode == 34 and len(raw) >= 4:
        return {
            "random_beta_span": struct.unpack_from("<h", raw)[0],
            "runtime_target_beta": struct.unpack_from("<h", raw, 2)[0],
        }
    if opcode == 36 and len(raw) >= 5:
        return {
            "duration_count": raw[0],
            "runtime_timer_ref": struct.unpack_from("<I", raw, 1)[0],
        }
    if opcode in {39, 49} and len(raw) >= 5:
        return {
            "duration_max": raw[0],
            "runtime_timer_ref": struct.unpack_from("<I", raw, 1)[0],
        }
    if opcode == 38 and len(raw) >= 2:
        return {"sprite_id": struct.unpack_from("<h", raw)[0]}
    if opcode in {41, 42, 43, 44, 48} and len(raw) >= 1:
        return {"frame": raw[0]}
    if opcode == 45 and len(raw) >= 1:
        return {"frames_per_second": raw[0]}
    if opcode == 46:
        return {"anim3ds_action": "stop_animation"}
    if opcode == 47:
        return {"wait_for_anim3ds_end": True}
    if opcode == 50 and len(raw) >= 2:
        return {"sample_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 51 and len(raw) >= 2:
        return {"sample_frequency": struct.unpack_from("<h", raw)[0]}
    if opcode == 52 and len(raw) >= 1:
        return {"sample_volume": raw[0]}
    return {}


def life_operand_semantics(
    opcode: int, raw: bytes, active_switch_return_type: str | None = None
) -> dict[str, Any]:
    if opcode in {0, 41}:
        return {"life_action": "stop_current_life", "offset_life": -1}
    if opcode == 11:
        return {"life_action": "return_from_life_pass"}
    if opcode == 35:
        return {"life_action": "end_current_behavior_pass"}
    if opcode in {2, 4, 12, 13, 14, 55, 112}:
        return life_condition_semantics(raw)
    if opcode == 113:
        function = life_function_semantics(raw)
        return {key: value for key, value in function.items() if key != "byte_length"}
    if opcode in {114, 115}:
        return life_case_semantics(raw, active_switch_return_type)
    if opcode == 3 and len(raw) >= 2:
        return {"target_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 15 and len(raw) >= 2:
        return {"target_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 17 and len(raw) >= 1:
        return {"body_id": raw[0]}
    if opcode == 18 and len(raw) >= 2:
        return {"object_id": raw[0], "body_id": raw[1]}
    if opcode == 19 and len(raw) >= 2:
        return {"animation_id": struct.unpack_from("<H", raw)[0]}
    if opcode == 20 and len(raw) >= 3:
        return {"object_id": raw[0], "animation_id": struct.unpack_from("<H", raw, 1)[0]}
    if opcode == 21 and len(raw) >= 2:
        return {"camera_zone_id": raw[0], "enabled": bool(raw[1])}
    if opcode == 22 and len(raw) >= 1:
        return {"camera_center_beta_quadrant": raw[0]}
    if opcode == 23 and len(raw) >= 2:
        return {"target_track_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 24 and len(raw) >= 3:
        return {"object_id": raw[0], "target_track_offset": struct.unpack_from("<h", raw, 1)[0]}
    if opcode == 26 and len(raw) >= 1:
        return {"fallable_mode": raw[0]}
    if opcode == 27:
        return life_move_semantics(raw)
    if opcode == 28 and len(raw) >= 2:
        return {"object_id": raw[0], **life_move_semantics(raw[1:])}
    if opcode == 29 and len(raw) >= 1:
        return {"camera_follow_object_id": raw[0]}
    if opcode == 30 and len(raw) >= 1:
        behavior_id = raw[0]
        return {
            "hero_behavior_id": behavior_id,
            "hero_behavior": LIFE_HERO_BEHAVIOR_NAMES.get(behavior_id, f"C_{behavior_id}"),
        }
    if opcode in {25, 44, 68, 69, 78, 88, 89, 91, 104, 148, 149, 150, 154}:
        return life_dialogue_semantics(opcode, raw)
    if opcode == 32 and len(raw) >= 1:
        return {"behavior_id": raw[0]}
    if opcode == 33 and len(raw) >= 2:
        return {"target_life_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 34 and len(raw) >= 3:
        return {"object_id": raw[0], "target_life_offset": struct.unpack_from("<h", raw, 1)[0]}
    if opcode == 31 and len(raw) >= 2:
        return {"var_cube_id": raw[0], "value": raw[1]}
    if opcode == 36 and len(raw) >= 3:
        return {"var_game_id": raw[0], "value": struct.unpack_from("<h", raw, 1)[0]}
    if opcode == 37 and len(raw) >= 1:
        return {
            "object_id": raw[0],
            "lifecycle_state": "dead",
            "body_action": "hide_object_body",
            "zone_action": "clear_object_zone",
            "life_points": 0,
        }
    if opcode == 38:
        return {
            "target": "current_object",
            "lifecycle_state": "dead",
            "body_action": "hide_current_object_body",
            "zone_action": "clear_current_object_zone",
            "life_points": 0,
        }
    if opcode in {42, 43}:
        return {
            "target": "current_object",
            "track_action": "stop" if opcode == 42 else "restore",
        }
    if opcode in {40, 136} and len(raw) >= 2:
        return {"money_delta": struct.unpack_from("<h", raw)[0]}
    if opcode == 39:
        return {"inventory_action": "use_one_little_key"}
    if opcode == 46 and len(raw) >= 1:
        return {"inventory_id": raw[0]}
    if opcode == 66:
        return {"clover_box_delta": 1, "clover_box_cap": "MAX_CLOVER_BOX"}
    if opcode == 71 and len(raw) >= 1:
        return {"slate_memo_id": raw[0], "inventory_feedback": "slate"}
    if opcode in {53, 56, 90, 92, 127} and len(raw) >= 1:
        return {"enabled": bool(raw[0])}
    if opcode == 54 and len(raw) >= 1:
        return {"brick_collision_mode": raw[0]}
    if opcode == 57 and len(raw) >= 2:
        return {"object_id": raw[0], "enabled": bool(raw[1])}
    if opcode in {61, 62, 110} and len(raw) >= 2:
        return {"object_id": raw[0], "life_points": raw[1]}
    if opcode == 63 and len(raw) >= 2:
        return {"object_id": raw[0], "damage": raw[1]}
    if opcode == 67 and len(raw) >= 1:
        return {"inventory_id": raw[0], "used": True}
    if opcode in {47, 48, 49, 50} and len(raw) >= 2:
        return {"door_width": struct.unpack_from("<h", raw)[0]}
    if opcode == 52 and len(raw) >= 1:
        return {"target_cube": raw[0]}
    if opcode == 51 and len(raw) >= 1:
        return {"bonus_enabled": bool(raw[0])}
    if opcode == 58 and len(raw) >= 1:
        return {"waypoint_id": raw[0]}
    if opcode == 59 and len(raw) >= 1:
        return {"magic_level": raw[0]}
    if opcode == 60 and len(raw) >= 1:
        return {"magic_points": raw[0]}
    if opcode == 64:
        return {
            "acf_name": raw.rstrip(b"\x00").decode("latin-1", errors="replace"),
            "cinematic_action": "play_acf",
        }
    if opcode == 65 and len(raw) >= 1:
        return {"effect": "lightning", "duration_tenths": raw[0]}
    if opcode == 96 and len(raw) >= 1:
        return {"effect": "rain", "duration_tenths": raw[0]}
    if opcode == 70 and len(raw) >= 1:
        return {"buggy_id": raw[0]}
    if opcode in {72, 73} and len(raw) >= 1:
        return {"holomap_location_id": raw[0]}
    if opcode in {74, 75} and len(raw) >= 1:
        return {"fuel_delta": raw[0]}
    if opcode == 76 and len(raw) >= 2:
        return {"grm_zone_id": raw[0], "enabled": bool(raw[1])}
    if opcode == 77 and len(raw) >= 2:
        return {"change_cube_control_id": raw[0], "enabled": bool(raw[1])}
    if opcode == 79:
        return {
            "hero_life_points": "max",
            "magic_points": "max_for_magic_level",
        }
    if opcode == 80 and len(raw) >= 2:
        return {"beta": struct.unpack_from("<h", raw)[0]}
    if opcode in {83, 85} and len(raw) >= 1:
        return {"frame": raw[0]}
    if opcode == 84 and len(raw) >= 2:
        return {"sprite_id": struct.unpack_from("<h", raw)[0]}
    if opcode == 86 and len(raw) >= 5:
        return {
            "object_id": raw[0],
            "impact_id": struct.unpack_from("<H", raw, 1)[0],
            "y_offset": struct.unpack_from("<h", raw, 3)[0],
        }
    if opcode == 87 and len(raw) >= 3:
        return {"waypoint_id": raw[0], "impact_id": struct.unpack_from("<H", raw, 1)[0]}
    if opcode == 10 and len(raw) >= 1:
        return {"palette_id": raw[0]}
    if opcode == 81 and len(raw) >= 1:
        return {"palette_id": raw[0]}
    if opcode == 93:
        return {"hero_state_action": "save"}
    if opcode == 94:
        return {"hero_state_action": "restore"}
    if opcode == 97:
        return {"game_state_action": "game_over"}
    if opcode == 98:
        return {"game_state_action": "the_end"}
    if opcode == 105:
        return {"game_state_action": "brutal_exit"}
    if opcode == 116:
        return {"switch_marker": "default_case"}
    if opcode == 118:
        return {"switch_marker": "end_switch"}
    if opcode == 100 and len(raw) >= 1:
        return {"music_id": raw[0]}
    if opcode in {95, 147} and len(raw) >= 2:
        return {"animation_id": struct.unpack_from("<H", raw)[0]}
    if opcode in {101, 102} and len(raw) >= 1:
        return {"var_game_id": raw[0]}
    if opcode == 103 and len(raw) >= 1:
        return {"enabled": bool(raw[0])}
    if opcode == 107 and len(raw) >= 2:
        return {"ladder_zone_id": raw[0], "enabled": bool(raw[1])}
    if opcode == 108 and len(raw) >= 1:
        return {"armor": struct.unpack_from("<b", raw)[0]}
    if opcode == 109 and len(raw) >= 2:
        return {"object_id": raw[0], "armor": struct.unpack_from("<b", raw, 1)[0]}
    if opcode == 111 and len(raw) >= 2:
        return {"inventory_id": raw[0], "inventory_object_3d_id": raw[1]}
    if opcode == 117 and len(raw) >= 2:
        return {"target_offset": struct.unpack_from("<h", raw)[0]}
    if opcode == 119 and len(raw) >= 2:
        return {"hit_zone_id": raw[0], "enabled": bool(raw[1])}
    if opcode in {122, 123, 124, 125} and len(raw) >= 2:
        return {"sample_id": struct.unpack_from("<h", raw)[0]}
    if opcode == 126 and len(raw) >= 3:
        return {"sample_id": struct.unpack_from("<h", raw)[0], "repeat_count": raw[2]}
    if opcode in {128, 129} and len(raw) >= 3:
        return {"var_game_id": raw[0], "delta": struct.unpack_from("<h", raw, 1)[0]}
    if opcode in {130, 131} and len(raw) >= 2:
        return {"var_cube_id": raw[0], "delta": raw[1]}
    if opcode == 133 and len(raw) >= 2:
        return {"rail_zone_id": raw[0], "enabled": bool(raw[1])}
    if opcode == 134:
        return {"beta_action": "invert_current_object"}
    if opcode == 135:
        return {"body_action": "hide_current_object_body"}
    if opcode == 82:
        return {"action_state": "normal_action_enabled"}
    if opcode == 144:
        return {"external_action": "popcorn", "runtime_effect": "disabled_in_classic_source"}
    if opcode in {137, 138} and len(raw) >= 1:
        return {
            "object_id": raw[0],
            "target": "object",
            "track_action": "stop" if opcode == 137 else "restore",
            "life_point_guard": "only_if_alive",
        }
    if opcode in {139, 140} and len(raw) >= 1:
        return {
            "object_id": raw[0],
            "target": "object",
            "behavior_memory_action": "save_object_behavior" if opcode == 139 else "restore_object_behavior",
            "life_point_guard": "only_if_alive",
        }
    if opcode == 145 and len(raw) >= 2:
        return {"waypoint_id": raw[0], "flow_strength": raw[1]}
    if opcode == 146 and len(raw) >= 2:
        return {"object_id": raw[0], "flow_strength": raw[1]}
    if opcode == 151 and len(raw) >= 5:
        return {
            "sample_offset": struct.unpack_from("<h", raw)[0],
            "sample_volume": raw[2],
            "sample_frequency": struct.unpack_from("<h", raw, 3)[0],
        }
    if opcode == 152 and len(raw) >= 7:
        return {
            "sample_id": struct.unpack_from("<h", raw)[0],
            "sample_offset": struct.unpack_from("<h", raw, 2)[0],
            "sample_volume": raw[4],
            "sample_frequency": struct.unpack_from("<h", raw, 5)[0],
        }
    if opcode == 153 and len(raw) >= 2:
        return {"object_id": raw[0], "around_object_id": raw[1]}
    if opcode == 99 and len(raw) >= 2:
        return {"escalator_zone_id": raw[0], "enabled": bool(raw[1])}
    if opcode == 120:
        return {"behavior_memory_action": "save_current_behavior"}
    if opcode == 121:
        return {"behavior_memory_action": "restore_current_behavior"}
    return {}


def life_dialogue_semantics(opcode: int, raw: bytes) -> dict[str, Any]:
    if opcode in {25, 78, 88} and len(raw) >= 2:
        text_id = struct.unpack_from("<h", raw)[0]
        variant = {
            25: "message",
            78: "zoe_message",
            88: "add_message",
        }[opcode]
        result: dict[str, Any] = {
            "text_id": text_id,
            "dialogue_action": "dial_text",
            "dialogue_variant": variant,
            "dialogue_speaker": "current_object",
            "dialogue_target": "current_object",
        }
        if opcode == 78:
            result["dialogue_target"] = "hero"
            result["dialogue_color"] = "zoe"
        return result
    if opcode in {44, 104} and len(raw) >= 3:
        return {
            "object_id": raw[0],
            "text_id": struct.unpack_from("<h", raw, 1)[0],
            "dialogue_action": "dial_text",
            "dialogue_variant": "message_object" if opcode == 44 else "add_message_object",
            "dialogue_speaker": "object",
            "dialogue_target": "object",
        }
    if opcode == 68 and len(raw) >= 2:
        return {
            "text_id": struct.unpack_from("<h", raw)[0],
            "choice_action": "append_choice",
        }
    if opcode == 69 and len(raw) >= 2:
        return {
            "text_id": struct.unpack_from("<h", raw)[0],
            "choice_action": "ask_choice",
            "choice_prompt_source": "text",
            "choice_reset_after_ask": True,
            "dialogue_target": "current_object",
        }
    if opcode == 89 and len(raw) >= 1:
        return {
            "dialogue_action": "set_bubble_mode",
            "bubble_enabled": bool(raw[0]),
            "bubble_raw": raw[0],
        }
    if opcode == 91 and len(raw) >= 3:
        return {
            "object_id": raw[0],
            "text_id": struct.unpack_from("<h", raw, 1)[0],
            "choice_action": "ask_choice",
            "choice_prompt_source": "text",
            "choice_reset_after_ask": True,
            "dialogue_target": "object",
        }
    if opcode == 148 and len(raw) >= 2:
        return {
            "pcx_id": raw[0],
            "effect_id": raw[1],
            "dialogue_action": "show_pcx",
        }
    if opcode == 149:
        return {"dialogue_action": "end_message"}
    if opcode == 150 and len(raw) >= 1:
        return {"object_id": raw[0], "dialogue_action": "end_message_object"}
    if opcode == 154 and len(raw) >= 5:
        return {
            "pcx_id": raw[0],
            "effect_id": raw[1],
            "object_id": raw[2],
            "text_id": struct.unpack_from("<h", raw, 3)[0],
            "dialogue_action": "show_pcx_message_object",
        }
    return {}


def life_condition_semantics(raw: bytes) -> dict[str, Any]:
    function = life_function_semantics(raw)
    function_bytes = function.get("byte_length")
    if not isinstance(function_bytes, int) or len(raw) < function_bytes + 3:
        return {}
    comparator = raw[function_bytes]
    return_type = function.get("return_type")
    value_offset = function_bytes + 1
    if return_type in {"s8", "u8"}:
        if len(raw) < value_offset + 3:
            return {}
        compare_value = struct.unpack_from("<b", raw, value_offset)[0] if return_type == "s8" else raw[value_offset]
        branch_offset = struct.unpack_from("<h", raw, value_offset + 1)[0]
    elif return_type == "s16":
        if len(raw) < value_offset + 4:
            return {}
        compare_value = struct.unpack_from("<h", raw, value_offset)[0]
        branch_offset = struct.unpack_from("<h", raw, value_offset + 2)[0]
    elif return_type == "string":
        terminator = raw.find(b"\x00", value_offset)
        if terminator == -1 or len(raw) < terminator + 3:
            return {}
        compare_value = raw[value_offset:terminator].decode("latin-1", errors="replace")
        branch_offset = struct.unpack_from("<h", raw, terminator + 1)[0]
    else:
        return {}
    return {
        **{key: value for key, value in function.items() if key != "byte_length"},
        "comparator": LIFE_COMPARATOR_NAMES.get(comparator, f"LT_{comparator}"),
        "compare_value": compare_value,
        "branch_offset": branch_offset,
    }


def life_move_semantics(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    move_mode = raw[0]
    result: dict[str, Any] = {
        "move_mode": move_mode,
        "move_mode_name": LIFE_MOVE_NAMES.get(move_mode, f"MOVE_{move_mode}"),
    }
    parameter_name = LIFE_MOVE_PARAMETER_NAMES.get(move_mode)
    if parameter_name is not None and len(raw) >= 2:
        result[parameter_name] = raw[1]
    return result


def life_case_semantics(raw: bytes, return_type: str | None) -> dict[str, Any]:
    if return_type is None or len(raw) < 3:
        return {}
    target_offset = struct.unpack_from("<h", raw)[0]
    test = life_test_semantics(raw[2:], return_type)
    if not test:
        return {"target_offset": target_offset, "switch_return_type": return_type}
    return {
        "target_offset": target_offset,
        "switch_return_type": return_type,
        **test,
    }


def life_test_semantics(raw: bytes, return_type: str) -> dict[str, Any]:
    if not raw:
        return {}
    comparator = raw[0]
    if comparator not in LIFE_COMPARATOR_NAMES:
        return {}
    if return_type in {"s8", "u8"}:
        if len(raw) < 2:
            return {}
        compare_value = struct.unpack_from("<b", raw, 1)[0] if return_type == "s8" else raw[1]
    elif return_type == "s16":
        if len(raw) < 3:
            return {}
        compare_value = struct.unpack_from("<h", raw, 1)[0]
    elif return_type == "string":
        terminator = raw.find(b"\x00", 1)
        if terminator == -1:
            return {}
        compare_value = raw[1:terminator].decode("latin-1", errors="replace")
    else:
        return {}
    return {
        "comparator": LIFE_COMPARATOR_NAMES[comparator],
        "compare_value": compare_value,
    }


def life_function_semantics(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    function_id = raw[0]
    if function_id not in LIFE_FUNCTION_NAMES:
        return {}
    result: dict[str, Any] = {
        "function_id": function_id,
        "function": LIFE_FUNCTION_NAMES[function_id],
        "return_type": LIFE_FUNCTION_RETURN_TYPES.get(function_id, "s8"),
        "byte_length": 1,
    }
    if function_id in LIFE_FUNCTIONS_WITH_U8:
        if len(raw) < 2:
            return {}
        parameter_name = LIFE_FUNCTION_PARAMETER_NAMES.get(function_id, "parameter")
        result[parameter_name] = raw[1]
        result["byte_length"] = 2
    return result


def script_behavior_category(kind: str, opcode: int) -> str:
    if kind == "track":
        return TRACK_BEHAVIOR_CATEGORIES.get(opcode, "unknown_behavior")
    return LIFE_BEHAVIOR_CATEGORIES.get(opcode, "unknown_behavior")


def script_behavior_effect(mnemonic: str, category: str) -> str:
    name = mnemonic.removeprefix("TM_").removeprefix("LM_").lower()
    return f"{category}:{name}"


def script_target_offset_evidence(
    target_offset: int,
    instructions: list[dict[str, Any]],
    script_byte_length: int | None = None,
) -> dict[str, Any]:
    decoded_bytes = max(
        (instruction["offset"] + instruction["byte_length"] for instruction in instructions),
        default=0,
    )
    evidence: dict[str, Any] = {
        "target_status": "unknown",
        "target_decoded_bytes": decoded_bytes,
    }
    if script_byte_length is not None:
        evidence["target_script_bytes"] = script_byte_length

    if target_offset < 0:
        evidence["target_status"] = "before_script"
        return evidence

    by_offset = {instruction["offset"]: instruction for instruction in instructions}
    target = by_offset.get(target_offset)
    if target is not None:
        evidence["target_status"] = "instruction_start"
        return evidence

    containing = next(
        (
            instruction
            for instruction in instructions
            if instruction["offset"] < target_offset < instruction["offset"] + instruction["byte_length"]
        ),
        None,
    )
    if containing is not None:
        relative_offset = target_offset - containing["offset"]
        evidence.update(
            {
                "target_status": "inside_instruction_operand",
                "target_containing_offset": containing["offset"],
                "target_containing_opcode": containing["mnemonic"],
                "target_containing_behavior_category": containing["behavior_category"],
                "target_containing_byte_length": containing["byte_length"],
                "target_instruction_relative_offset": relative_offset,
                "target_byte_role": "opcode_byte" if relative_offset == 0 else "operand_byte",
            }
        )
        return evidence

    if script_byte_length is not None and target_offset >= script_byte_length:
        evidence["target_status"] = "outside_script"
        return evidence
    if target_offset >= decoded_bytes:
        if script_byte_length is not None and target_offset < script_byte_length:
            evidence["target_status"] = "after_decoded_prefix"
        elif target_offset == decoded_bytes:
            evidence["target_status"] = "end_of_decoded_script"
        else:
            evidence["target_status"] = "after_decoded_script"
        if instructions:
            previous = instructions[-1]
            evidence["target_previous_decoded_offset"] = previous["offset"]
            evidence["target_previous_decoded_opcode"] = previous["mnemonic"]
        return evidence

    evidence["target_status"] = "undecoded_gap"
    return evidence


def script_control_flow_links(
    kind: str, instructions: list[dict[str, Any]], script_byte_length: int | None = None
) -> list[dict[str, Any]]:
    by_offset = {instruction["offset"]: instruction for instruction in instructions}
    links: list[dict[str, Any]] = []
    for instruction in instructions:
        semantics = instruction["operand_semantics"]
        for field in SAME_SCRIPT_TARGET_FIELDS:
            target_offset = semantics.get(field)
            if not isinstance(target_offset, int) or isinstance(target_offset, bool):
                continue
            if field == "target_life_offset" and "object_id" in semantics:
                continue
            if kind == "track" and field in {"branch_offset", "target_life_offset"}:
                continue
            target = by_offset.get(target_offset)
            link: dict[str, Any] = {
                "source_offset": instruction["offset"],
                "source_opcode": instruction["mnemonic"],
                "source_behavior_category": instruction["behavior_category"],
                "target_field": field,
                "target_script_kind": kind,
                "target_offset": target_offset,
                "target_found": target is not None,
            }
            link.update(script_target_offset_evidence(target_offset, instructions, script_byte_length))
            if target is not None:
                link["target_opcode"] = target["mnemonic"]
                link["target_behavior_category"] = target["behavior_category"]
            links.append(link)
    return links


def script_label_definitions(kind: str, instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if kind != "track":
        return []
    labels: list[dict[str, Any]] = []
    for instruction in instructions:
        label = instruction["operand_semantics"].get("track_label")
        if isinstance(label, int) and not isinstance(label, bool):
            labels.append(
                {
                    "label": label,
                    "offset": instruction["offset"],
                    "opcode": instruction["mnemonic"],
                }
            )
    return labels


def script_runtime_state_fields(
    kind: str, instructions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if kind != "track":
        return []
    fields: list[dict[str, Any]] = []
    for instruction in instructions:
        raw = bytes.fromhex(instruction["operand_hex"])
        opcode = int(instruction["opcode"])
        semantics = instruction["operand_semantics"]
        for field_name, operand_offset, size, source in TRACK_RUNTIME_STATE_FIELDS.get(opcode, []):
            initial_value_key = TRACK_RUNTIME_STATE_VALUE_ALIASES.get(field_name, field_name)
            field: dict[str, Any] = {
                "source_offset": instruction["offset"],
                "opcode": instruction["mnemonic"],
                "behavior_category": instruction["behavior_category"],
                "field": field_name,
                "instruction_relative_offset": operand_offset + 1,
                "operand_offset": operand_offset,
                "size": size,
                "initial_hex": raw[operand_offset : operand_offset + size].hex(),
                "source": source,
            }
            initial_value = semantics.get(initial_value_key)
            if isinstance(initial_value, (bool, int)):
                field["initial_value"] = initial_value
            fields.append(field)
    return fields


def script_cinematic_refs(
    kind: str, instructions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for instruction in instructions:
        semantics = instruction["operand_semantics"]
        acf_name = semantics.get("acf_name")
        if not isinstance(acf_name, str) or not acf_name:
            continue
        refs.append(
            {
                "script_kind": kind,
                "offset": instruction["offset"],
                "opcode": instruction["mnemonic"],
                "behavior_category": instruction["behavior_category"],
                "acf_name": acf_name,
                "cinematic_action": semantics.get("cinematic_action", "play_acf"),
            }
        )
    return refs


def collect_script_references(
    instruction: dict[str, Any], references: dict[str, set[int]]
) -> None:
    semantics = instruction["operand_semantics"]
    add_reference(references, "body", semantics.get("body_id"))
    add_reference(references, "animation", semantics.get("animation_id"))
    add_reference(references, "sprite", semantics.get("sprite_id"))
    add_reference(references, "waypoint", semantics.get("waypoint_id"))
    add_reference(references, "script_offset", semantics.get("target_offset"))
    add_reference(references, "script_offset", semantics.get("target_track_offset"))
    add_reference(references, "script_offset", semantics.get("target_life_offset"))
    add_reference(references, "script_offset", semantics.get("branch_offset"))
    add_reference(references, "track_label", semantics.get("track_label"))
    add_reference(references, "object", semantics.get("object_id"))
    add_reference(references, "text", semantics.get("text_id"))
    add_reference(references, "var_cube", semantics.get("var_cube_id"))
    add_reference(references, "var_game", semantics.get("var_game_id"))
    add_reference(references, "inventory", semantics.get("inventory_id"))
    add_reference(references, "sample", semantics.get("sample_id"))
    add_reference(references, "music", semantics.get("music_id"))
    add_reference(references, "behavior", semantics.get("behavior_id"))
    add_reference(references, "behavior", semantics.get("hero_behavior_id"))
    add_reference(references, "palette", semantics.get("palette_id"))
    add_reference(references, "pcx", semantics.get("pcx_id"))
    add_reference(references, "holomap", semantics.get("holomap_location_id"))
    add_reference(references, "buggy", semantics.get("buggy_id"))
    add_reference(references, "camera_zone", semantics.get("camera_zone_id"))
    add_reference(references, "object", semantics.get("camera_follow_object_id"))
    add_reference(references, "object", semantics.get("follow_object_id"))
    add_reference(references, "object", semantics.get("around_object_id"))
    add_reference(references, "waypoint", semantics.get("circle_waypoint_id"))
    add_reference(references, "ladder_zone", semantics.get("ladder_zone_id"))
    add_reference(references, "grm_zone", semantics.get("grm_zone_id"))
    add_reference(references, "rail_zone", semantics.get("rail_zone_id"))
    add_reference(references, "hit_zone", semantics.get("hit_zone_id"))
    add_reference(references, "escalator_zone", semantics.get("escalator_zone_id"))
    add_reference(references, "change_cube_control", semantics.get("change_cube_control_id"))
    add_reference(references, "cube", semantics.get("target_cube"))


def add_reference(references: dict[str, set[int]], key: str, value: Any) -> None:
    if isinstance(value, int) and not isinstance(value, bool):
        references[key].add(value)
