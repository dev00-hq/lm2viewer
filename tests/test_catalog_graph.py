import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from lba2_lm2_viewer.catalog_graph import (
    asset_node_id_for,
    build_catalog_graph,
    catalog_node_selection_projection,
    catalog_scene_object_relationship_projection,
    catalog_selection_projection,
    export_graph_document,
    file3d_record_node_id_for,
    graph_from_export_document,
    query_animation_operation_compatibility,
    query_export,
    query_edges,
    query_search,
    query_export_context,
    query_prove,
    query_script_instruction,
    query_scene_object,
    query_selection,
    query_asset_usage_records,
    query_usages,
    query_waypoint,
    query_zone,
    runtime_state_field_node_id_for,
    scene_zone_node_id_for,
    script_instruction_node_id_for,
    waypoint_node_id_for,
)
from lba2_lm2_viewer.exportability import (
    CATALOG_EXPORT_ROUTES_BY_KIND_LAYOUT,
    catalog_asset_export_route,
    graph_asset_export_route,
)
from lba2_lm2_viewer.viewer import ANIM_3DS_FLAG, SPRITE_3D_FLAG, resolve_runtime_sprite
from lba2_lm2_viewer.server import ViewerServer


def synthetic_catalog() -> dict[str, object]:
    return {
        "schema": "viewer-catalog-v1",
        "hqr_files": [
            {"path": "SCENE.HQR", "entry_count": 4},
            {"path": "BODY.HQR", "entry_count": 61},
            {"path": "ANIM.HQR", "entry_count": 221},
            {"path": "ANIM3DS.HQR", "entry_count": 128},
            {"path": "RESS.HQR", "entry_count": 49},
            {"path": "SAMPLES.HQR", "entry_count": 2},
        ],
        "assets": [
            {
                "id": "SCENE.HQR:2",
                "kind": "scene",
                "label": "Scene 1",
                "entry_type": "scene",
                "source": {"hqr": "SCENE.HQR", "entry_index": 2},
                "stats": {
                    "semantic_layout": "scene_runtime_layout_partial",
                    "reconnaissance": {
                        "objects": [
                            {
                                "index": 2,
                                "file3d_index": 7,
                                "gen_body": 3,
                                "gen_anim": 4,
                                "sprite": 0,
                                "flags": 0,
                                "links": {
                                    "body": {
                                        "asset_id": "BODY.HQR:29",
                                        "asset_available": True,
                                        "resolution_rule": "matched scene GenBody to File3D body generic id",
                                    },
                                    "animation": {
                                        "asset_id": "ANIM.HQR:220",
                                        "asset_available": True,
                                        "resolution_rule": "matched scene GenAnim to File3D animation generic id",
                                    },
                                    "sprite": {
                                        "asset_id": "SPRITES.HQR:999",
                                        "asset_available": False,
                                        "backend": "sprites",
                                        "runtime_sprite_index": 999,
                                        "index_rule": "InitSprite selects SPRITES.HQR when SPRITE_3D is set, ANIM_3DS is clear, and Sprite >= 100.",
                                    },
                                },
                                "track_script_analysis": {
                                    "asset_links": [
                                        {
                                            "kind": "body",
                                            "asset_id": "BODY.HQR:29",
                                            "asset_available": True,
                                            "reference_key": "body",
                                            "reference_value": 3,
                                            "script_kind": "track",
                                            "resolution_rule": "resolved script generic body through owner File3D SearchBody rule",
                                        },
                                        {
                                            "kind": "video",
                                            "asset_available": False,
                                            "reference_key": "acf_name",
                                            "reference_value": "MISSING.SMK",
                                            "acf_basename": "MISSING",
                                            "missing_reason": "name_not_found_in_loaded_video_assets",
                                        },
                                        {
                                            "kind": "text",
                                            "asset_available": False,
                                            "reference_key": "text",
                                            "reference_value": 77,
                                            "text_file_index": 3,
                                            "missing_reason": "message_not_found_in_loaded_text_assets",
                                        },
                                    ],
                                    "missing_sample_links": [
                                        {
                                            "sample_id": 999,
                                            "hqr_table_index": 1000,
                                            "status": "outside_archive_table",
                                            "reason": "outside SAMPLES.HQR table",
                                            "reference_key": "sample",
                                            "reference_value": 999,
                                        }
                                    ],
                                },
                            }
                        ],
                        "sampled_objects": [],
                    },
                },
            },
            {
                "id": "BODY.HQR:29",
                "kind": "model",
                "label": "Piece of flying saucer model",
                "entry_type": "body",
                "source": {"hqr": "BODY.HQR", "entry_index": 29},
                "stats": {"bones": 19},
                "scene_usages": [
                    {
                        "kind": "body",
                        "scene_asset_id": "SCENE.HQR:2",
                        "scene_label": "Scene 1",
                        "scene_entry_index": 2,
                        "scene_index": 1,
                        "object_index": 2,
                        "file3d_index": 7,
                        "gen_body": 3,
                        "gen_anim": 4,
                        "sprite": 0,
                        "flags": 0,
                        "target_asset_id": "BODY.HQR:29",
                        "resolution_rule": "matched scene GenBody to File3D body generic id",
                    }
                ],
            },
            {
                "id": "BODY.HQR:2",
                "kind": "model",
                "label": "Twinsen with tunic model",
                "entry_type": "body",
                "source": {"hqr": "BODY.HQR", "entry_index": 2},
                "stats": {"bones": 19},
            },
            {
                "id": "ANIM.HQR:2",
                "kind": "animation",
                "label": "Back up",
                "entry_type": "animation",
                "source": {"hqr": "ANIM.HQR", "entry_index": 2},
                "stats": {"boneframes": 19},
                "animation_metadata": {"compatible_body_ids": [2]},
            },
            {
                "id": "ANIM.HQR:220",
                "kind": "animation",
                "label": "Scene anim",
                "entry_type": "animation",
                "source": {"hqr": "ANIM.HQR", "entry_index": 220},
                "stats": {"boneframes": 19},
                "scene_usages": [
                    {
                        "kind": "animation",
                        "scene_asset_id": "SCENE.HQR:2",
                        "scene_label": "Scene 1",
                        "scene_entry_index": 2,
                        "scene_index": 1,
                        "object_index": 2,
                        "file3d_index": 7,
                        "gen_body": 3,
                        "gen_anim": 4,
                        "sprite": 0,
                        "flags": 0,
                        "target_asset_id": "ANIM.HQR:220",
                        "resolution_rule": "matched scene GenAnim to File3D animation generic id",
                    }
                ],
            },
            {
                "id": "RESS.HQR:48",
                "kind": "resource",
                "label": "ACF name list",
                "entry_type": "resource",
                "source": {"hqr": "RESS.HQR", "entry_index": 48},
                "stats": {
                    "semantic_layout": "acf_name_list",
                    "decode_status": "decoded",
                    "sampled_records": [{"index": 0, "preview": "INTRO"}],
                },
            },
            {
                "id": "SAMPLES.HQR:0",
                "kind": "resource",
                "label": "Magic ball sample",
                "entry_type": "sample",
                "source": {"hqr": "SAMPLES.HQR", "entry_index": 0},
                "decoded_bytes": 12,
                "stats": {
                    "semantic_layout": "sample_wave_audio",
                    "decode_status": "decoded",
                    "source_provenance": "HQF_Init sample runtime id uses zero-based sample index.",
                },
            },
            {
                "id": "LBA_BKG.HQR:1024",
                "kind": "resource",
                "label": "Background brick graphic",
                "entry_type": "resource",
                "source": {"hqr": "LBA_BKG.HQR", "entry_index": 1024},
                "stats": {
                    "semantic_layout": "bkg_brick_graphic",
                    "decode_status": "decoded",
                    "width": 32,
                    "height": 24,
                },
            },
            {
                "id": "ANIM3DS.HQR:0",
                "kind": "sprite",
                "label": "COQU frame 0",
                "entry_type": "anim3ds-frame",
                "source": {"hqr": "ANIM3DS.HQR", "entry_index": 0},
                "stats": {
                    "semantic_layout": "lsp_sprite_frame",
                    "anim3ds_info": {
                        "animation_index": 0,
                        "name": "COQU",
                        "start_frame": 0,
                        "end_frame": 1,
                        "relative_frame": 0,
                    },
                },
            },
            {
                "id": "ANIM3DS.HQR:1",
                "kind": "sprite",
                "label": "COQU frame 1",
                "entry_type": "anim3ds-frame",
                "source": {"hqr": "ANIM3DS.HQR", "entry_index": 1},
                "stats": {
                    "semantic_layout": "lsp_sprite_frame",
                    "anim3ds_info": {
                        "animation_index": 0,
                        "name": "COQU",
                        "start_frame": 0,
                        "end_frame": 1,
                        "relative_frame": 1,
                    },
                },
            },
            {
                "id": "ANIM3DS.HQR:127",
                "kind": "sprite",
                "label": "ANIM3DS range metadata",
                "entry_type": "anim3ds-info",
                "source": {"hqr": "ANIM3DS.HQR", "entry_index": 127},
                "stats": {
                    "semantic_layout": "anim3ds_frame_ranges",
                    "source_provenance": "PERSO.CPP::LoadListAnim3DS loads ANIM3DS.HQR:127 as the range table.",
                    "entries": [
                        {
                            "index": 0,
                            "name": "COQU",
                            "start_frame": 0,
                            "end_frame": 1,
                            "frame_count": 2,
                        }
                    ],
                },
            },
        ],
    }


def synthetic_catalog_without_reverse_usages() -> dict[str, object]:
    catalog = synthetic_catalog()
    for asset in catalog["assets"]:  # type: ignore[index]
        if isinstance(asset, dict):
            asset.pop("scene_usages", None)
    return catalog


def synthetic_scene_mechanics_catalog() -> dict[str, object]:
    catalog = synthetic_catalog_without_reverse_usages()
    scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
    recon = scene["stats"]["reconnaissance"]  # type: ignore[index]
    sampled_object = recon["objects"][0]  # type: ignore[index]
    sampled_object["runtime"] = {
        "movement": {
            "references": [
                {
                    "field": "Info0",
                    "role": "circle_waypoint",
                    "kind": "waypoint",
                    "value": 1,
                    "target": "waypoint",
                    "target_found": True,
                    "source": "OBJECT.CPP movement target",
                }
            ]
        }
    }
    sampled_object["track_script_analysis"]["asset_links"].append(  # type: ignore[index]
        dict(sampled_object["track_script_analysis"]["asset_links"][0])  # type: ignore[index]
    )
    sampled_object["track_script_analysis"]["status"] = "decoded"  # type: ignore[index]
    sampled_object["track_script_analysis"]["byte_length"] = 9  # type: ignore[index]
    sampled_object["track_script_analysis"]["decoded_bytes"] = 9  # type: ignore[index]
    sampled_object["track_script_analysis"]["instruction_count"] = 4  # type: ignore[index]
    sampled_object["track_script_analysis"]["sha256"] = "track-sha"  # type: ignore[index]
    sampled_object["track_script_analysis"]["first_instructions"] = [  # type: ignore[index]
        {
            "offset": 0,
            "opcode": 4,
            "mnemonic": "TM_GOTO_POINT",
            "byte_length": 3,
            "operand_hex": "0100",
            "operand_semantics": {"waypoint_id": 1},
            "behavior_category": "movement",
        },
        {
            "offset": 3,
            "opcode": 10,
            "mnemonic": "TM_GOTO",
            "byte_length": 3,
            "operand_hex": "0000",
            "operand_semantics": {"target_offset": 0},
            "behavior_category": "control_flow",
        },
        {
            "offset": 6,
            "opcode": 9,
            "mnemonic": "TM_LABEL",
            "byte_length": 2,
            "operand_hex": "07",
            "operand_semantics": {"track_label": 7},
            "behavior_category": "control_flow",
        },
        {
            "offset": 8,
            "opcode": 11,
            "mnemonic": "TM_STOP",
            "byte_length": 1,
            "operand_hex": "",
            "operand_semantics": {},
            "behavior_category": "control_flow",
        },
    ]
    sampled_object["track_script_analysis"]["label_definitions"] = [  # type: ignore[index]
        {"label": 7, "offset": 6, "opcode": "TM_LABEL"}
    ]
    sampled_object["track_script_analysis"]["control_flow_links"] = [  # type: ignore[index]
        {
            "source_offset": 3,
            "source_opcode": "TM_GOTO",
            "source_behavior_category": "control_flow",
            "target_field": "target_offset",
            "target_script_kind": "track",
            "target_offset": 0,
            "target_found": True,
            "target_opcode": "TM_GOTO_POINT",
            "target_behavior_category": "movement",
        }
    ]
    sampled_object["track_script_analysis"]["execution_contracts"] = [  # type: ignore[index]
        {
            "contract": "track_pass_control",
            "count": 1,
            "source": "GERETRAK.CPP",
            "effect": "stop current track",
            "mnemonics": ["TM_STOP"],
        }
    ]
    sampled_object["track_script_analysis"]["local_links"] = [  # type: ignore[index]
        {
            "kind": "waypoint",
            "reference_key": "waypoint",
            "reference_value": 1,
            "target": "waypoint",
            "target_available": True,
            "waypoint_index": 1,
            "position": {"x": 10, "y": 20, "z": 30},
        }
    ]
    sampled_object["track_script_analysis"]["runtime_state_fields"] = [  # type: ignore[index]
        {
            "source_offset": 3,
            "opcode": "TM_GOTO",
            "behavior_category": "control_flow",
            "field": "target_offset",
            "instruction_relative_offset": 1,
            "operand_offset": 0,
            "size": 2,
            "initial_hex": "0000",
            "initial_value": 0,
            "source": "track_opcode_layout",
        }
    ]
    sampled_object["life_script_analysis"] = {  # type: ignore[index]
        "status": "decoded",
        "byte_length": 0,
        "decoded_bytes": 0,
        "instruction_count": 0,
        "sha256": "life-sha",
        "first_instructions": [],
    }
    recon["sampled_zones"] = [  # type: ignore[index]
        {
            "index": 0,
            "offset": 120,
            "start": {"x": 0, "y": 0, "z": 0},
            "end": {"x": 100, "y": 100, "z": 100},
            "info": [0, 12, 0, 0, 0, 0, 0, 0],
            "type": 5,
            "type_name": "message",
            "value": 77,
            "load_rules": {"starts_on": True},
            "runtime": {
                "source": "OBJECT.CPP::GereZoneMessage",
                "effect": "show_message",
                "fields": {"message_id": 77, "associated_camera_zone": 12},
                "message_application": {"dialogue_call": "Dial(zone.Num, TRUE)"},
            },
        },
        {
            "index": 1,
            "offset": 180,
            "start": {"x": 200, "y": 0, "z": 0},
            "end": {"x": 300, "y": 100, "z": 100},
            "info": [0, 0, 0, 0, 0, 0, 0, 0],
            "type": 1,
            "type_name": "camera",
            "value": 12,
            "load_rules": {},
            "runtime": {"source": "OBJECT.CPP::SetZoneCamera", "effect": "camera_zone", "camera_application": {}},
        },
        {
            "index": 2,
            "offset": 220,
            "start": {"x": 400, "y": 0, "z": 0},
            "end": {"x": 500, "y": 100, "z": 100},
            "info": [1, 2, 3, 0, 77, 0, 0, 1],
            "type": 0,
            "type_name": "change_cube",
            "value": 9,
            "load_rules": {"starts_on": True},
            "runtime": {
                "source": "OBJECT.CPP::GereZoneChangeCube",
                "effect": "change_cube",
                "fields": {"target_cube": 9, "script_control_id": 77},
                "change_cube_application": {"new_cube": "NewCube = zone.Num"},
            },
        },
    ]
    recon["zones"] = recon["sampled_zones"]  # type: ignore[index]
    recon["sampled_tracks"] = [  # type: ignore[index]
        {"index": 1, "offset": 240, "position": {"x": 10, "y": 20, "z": 30}}
    ]
    recon["tracks"] = recon["sampled_tracks"]  # type: ignore[index]
    recon["text_zone_links"] = [  # type: ignore[index]
        {
            "zone_index": 0,
            "asset_id": "RESS.HQR:48",
            "asset_available": True,
            "text_id": 77,
            "text_file_index": 3,
            "resolution_rule": "zone message text resolved",
        }
    ]
    recon["message_camera_links"] = [  # type: ignore[index]
        {
            "zone_index": 0,
            "associated_camera_zone": 12,
            "target_zone_index": 1,
            "target_available": True,
            "source_provenance": "OBJECT.CPP::GereZoneMessage camera lookup",
        }
    ]
    recon["sampled_patches"] = [  # type: ignore[index]
        {
            "index": 0,
            "offset": 300,
            "size": 2,
            "target_offset": 3,
            "target": {
                "kind": "track",
                "owner": "object:2",
                "script_relative_offset": 3,
                "instruction_found": True,
                "instruction_offset": 3,
                "instruction_opcode": "TM_GOTO",
                "instruction_behavior_category": "control_flow",
                "patched_field": "target_offset",
                "patched_field_size": 2,
                "patched_field_source": "track_opcode_layout",
            },
        }
    ]
    recon["patches"] = recon["sampled_patches"]  # type: ignore[index]
    return catalog


class CatalogGraphTests(unittest.TestCase):
    def test_scene_object_usage_preserves_file3d_resolver(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        scene_object = query_scene_object(graph, "SCENE.HQR:2", "2")
        edge_types = {edge["type"] for edge in scene_object["edges"]}

        self.assertIn("HAS_FILE3D_RECORD", edge_types)
        self.assertIn("USES_AS_BODY", edge_types)
        self.assertIn("USES_AS_ANIMATION", edge_types)
        self.assertIn(file3d_record_node_id_for(7), graph.nodes_by_id)
        self.assertFalse(
            any(
                edge["to"] == asset_node_id_for("BODY.HQR:3")
                for edge in scene_object["edges"]
            ),
            "GenBody must not be treated as a direct BODY.HQR asset id.",
        )

    def test_asset_usage_records_do_not_require_reverse_scene_usages(self) -> None:
        graph = build_catalog_graph(synthetic_catalog_without_reverse_usages())

        records = query_asset_usage_records(graph, "BODY.HQR:29")["usageRecords"]

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["scene_asset_id"], "SCENE.HQR:2")
        self.assertEqual(records[0]["object_index"], 2)
        self.assertEqual(records[0]["target_asset_id"], "BODY.HQR:29")
        self.assertEqual(records[0]["proofScope"], "scene_object_state")
        self.assertEqual(records[1]["proofScope"], "script_reference")

    def test_export_context_uses_graph_usage_evidence(self) -> None:
        graph = build_catalog_graph(synthetic_catalog_without_reverse_usages())

        context = query_export_context(graph, "BODY.HQR:29", "test export proof")

        self.assertEqual(context["scene_usage_count"], 1)
        self.assertEqual(context["direct_scene_object_usage_count"], 1)
        self.assertEqual(context["script_reference_count"], 1)
        self.assertIn("scene_object_state", context["proof_scopes"])
        self.assertIn("script_reference", context["proof_scopes"])
        self.assertTrue(any("SceneObject" in field for field in context["source_fields"]))

    def test_scene_object_usage_does_not_depend_on_reverse_scene_usages(self) -> None:
        graph = build_catalog_graph(synthetic_catalog_without_reverse_usages())

        scene_object = query_scene_object(graph, "SCENE.HQR:2", "2")
        usage_edges = {
            (edge["type"], edge["to"])
            for edge in scene_object["edges"]
            if edge["type"].startswith("USES_AS_")
        }

        self.assertIn(("USES_AS_BODY", asset_node_id_for("BODY.HQR:29")), usage_edges)
        self.assertIn(("USES_AS_ANIMATION", asset_node_id_for("ANIM.HQR:220")), usage_edges)

    def test_usage_query_returns_scene_object_state_edges(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        usages = query_usages(graph, "BODY.HQR:29")

        scene_state_edges = [
            edge for edge in usages["edges"] if edge["proofScope"] == "scene_object_state"
        ]
        self.assertEqual(len(scene_state_edges), 1)
        self.assertEqual(scene_state_edges[0]["type"], "USES_AS_BODY")
        self.assertEqual(scene_state_edges[0]["evidenceStatus"], "source_backed")

        filtered = query_edges(
            graph,
            "BODY.HQR:29",
            "incoming",
            proof_scope="scene_object_state",
            evidence_status="source_backed",
        )
        self.assertEqual([edge["type"] for edge in filtered["edges"]], ["USES_AS_BODY"])

    def test_prove_keeps_file3d_allowlist_evidence_distinct(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        proof = query_prove(graph, "BODY.HQR:2", "ANIM.HQR:2")

        self.assertTrue(proof["compatible"])
        self.assertEqual(proof["proofs"][0]["proofScope"], "classic_source_rule")
        self.assertEqual(proof["proofs"][0]["compatibilityReason"], "file3d_allowlist")

    def test_resource_records_are_indexed_as_payload_local_nodes(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        self.assertIn("resource-record:RESS.HQR:48:0", graph.nodes_by_id)
        self.assertEqual(
            graph.indexes["resourcesBySemanticLayout"]["acf_name_list"],
            ["RESS.HQR:48"],
        )

    def test_export_import_is_deterministic_for_synthetic_catalog(self) -> None:
        catalog = synthetic_catalog()
        metadata = {"schema": "catalog_graph.build_metadata.v0", "builtAt": "fixed"}

        first = export_graph_document(build_catalog_graph(catalog), catalog, metadata=metadata)
        second = export_graph_document(build_catalog_graph(catalog), catalog, metadata=metadata)
        imported = graph_from_export_document(first)

        self.assertEqual(first, second)
        self.assertEqual(
            query_prove(imported, "BODY.HQR:2", "ANIM.HQR:2")["proofs"][0]["compatibilityReason"],
            "file3d_allowlist",
        )

    def test_missing_sample_text_video_and_runtime_sprite_targets_are_materialized(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        sample_usages = query_usages(
            graph,
            "SAMPLES.HQR:999",
            proof_scope="script_reference",
            evidence_status="unknown",
        )
        video_usages = query_usages(
            graph,
            "VIDEO/VIDEO.HQR:MISSING",
            proof_scope="script_reference",
            evidence_status="unknown",
        )
        text_usages = query_usages(
            graph,
            "TEXT.HQR:3#message:77",
            proof_scope="script_reference",
            evidence_status="unknown",
        )
        sprite_usages = query_usages(
            graph,
            "SPRITES.HQR:999",
            proof_scope="scene_object_state",
            evidence_status="unknown",
        )

        self.assertEqual(sample_usages["edges"][0]["type"], "SCRIPT_REFERENCES")
        self.assertEqual(graph.nodes_by_id["missing:SAMPLES.HQR:999"]["type"], "MissingTarget")
        self.assertEqual(text_usages["edges"][0]["type"], "SCRIPT_REFERENCES")
        self.assertEqual(graph.nodes_by_id["missing:TEXT.HQR:3#message:77"]["type"], "MissingTarget")
        self.assertEqual(video_usages["edges"][0]["type"], "SCRIPT_REFERENCES")
        self.assertEqual(graph.nodes_by_id["missing:VIDEO/VIDEO.HQR:MISSING"]["type"], "MissingTarget")
        self.assertEqual(sprite_usages["edges"][0]["type"], "USES_AS_SPRITE")
        self.assertEqual(graph.nodes_by_id["missing:SPRITES.HQR:999"]["type"], "MissingTarget")

    def test_direct_usage_and_script_reference_same_endpoint_stay_distinct(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        usages = query_usages(graph, "BODY.HQR:29")
        families = {(edge["type"], edge["proofScope"]) for edge in usages["edges"]}

        self.assertIn(("USES_AS_BODY", "scene_object_state"), families)
        self.assertIn(("SCRIPT_REFERENCES", "script_reference"), families)

    def test_runtime_sprite_resolution_keeps_backend_and_anim3ds_range_distinct(self) -> None:
        anim3ds = resolve_runtime_sprite(SPRITE_3D_FLAG | ANIM_3DS_FLAG, 0)
        raw = resolve_runtime_sprite(SPRITE_3D_FLAG, 99)
        sprites = resolve_runtime_sprite(SPRITE_3D_FLAG, 100)

        self.assertEqual(anim3ds["asset_id"], "ANIM3DS.HQR:0")
        self.assertEqual(raw["asset_id"], "SPRIRAW.HQR:99")
        self.assertEqual(sprites["asset_id"], "SPRITES.HQR:100")
        self.assertNotEqual(anim3ds["asset_id"], "ANIM3DS.HQR:127")

    def test_anim3ds_range_node_stays_distinct_from_frame_assets(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        range_edges = query_edges(graph, "ANIM3DS:0", "out")

        self.assertEqual(graph.nodes_by_id["sprite-range:ANIM3DS:0"]["type"], "SpriteRange")
        self.assertEqual(graph.nodes_by_id[asset_node_id_for("ANIM3DS.HQR:127")]["type"], "Asset")
        self.assertEqual(graph.nodes_by_id[asset_node_id_for("ANIM3DS.HQR:0")]["type"], "Asset")
        self.assertEqual(
            [edge["to"] for edge in range_edges["edges"] if edge["type"] == "RANGE_CONTAINS_FRAME"],
            [asset_node_id_for("ANIM3DS.HQR:0"), asset_node_id_for("ANIM3DS.HQR:1")],
        )

    def test_server_catalog_projection_exposes_graph_compatibility(self) -> None:
        server = ViewerServer(None, None)
        server.catalog = synthetic_catalog()
        server.attach_catalog_graph_projection()

        compatible = server.catalog_graph_compatible("BODY.HQR:2")
        projected = server.catalog["graph"]["compatibilityByModelId"]["BODY.HQR:2"][0]  # type: ignore[index]

        self.assertIn("ANIM.HQR:2", server.catalog["graph"]["indexes"]["compatibleAnimationsByModelId"]["BODY.HQR:2"])  # type: ignore[index]
        self.assertEqual(projected["compatibilityReason"], "file3d_allowlist")
        self.assertEqual(compatible["edges"][0]["proofScope"], "classic_source_rule")

    def test_model_asset_selection_projection_uses_graph_usage_edges(self) -> None:
        graph = build_catalog_graph(synthetic_catalog_without_reverse_usages())

        selection = catalog_selection_projection(graph)["BODY.HQR:29"]

        self.assertEqual(selection["stableId"], "BODY.HQR:29")
        self.assertEqual(selection["workspaceSuggestion"], "model")
        self.assertEqual(selection["inspectorRoute"], "model")
        self.assertTrue(selection["exportCapability"]["exportable"])
        self.assertEqual(selection["exportActions"][0]["targetAssetId"], "BODY.HQR:29")
        self.assertEqual(selection["links"][0]["stableId"], "SCENE.HQR:2#object:2")
        self.assertEqual(selection["links"][0]["proofScope"], "scene_object_state")
        self.assertEqual(selection["links"][1]["proofScope"], "script_reference")

    def test_server_catalog_projection_exposes_model_selection_projection(self) -> None:
        server = ViewerServer(None, None)
        server.catalog = synthetic_catalog_without_reverse_usages()
        server.attach_catalog_graph_projection()

        selection = server.catalog["graph"]["selectionByAssetId"]["BODY.HQR:29"]  # type: ignore[index]

        self.assertEqual(selection["nodeId"], asset_node_id_for("BODY.HQR:29"))
        self.assertEqual(selection["facets"]["sceneUsageCount"], 1)
        self.assertEqual(selection["facets"]["relationshipLinkCount"], 2)

    def test_resource_asset_selection_projection_drives_workspace_and_export(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        sample_selection = catalog_selection_projection(graph)["SAMPLES.HQR:0"]
        table_selection = catalog_selection_projection(graph)["RESS.HQR:48"]

        self.assertEqual(sample_selection["workspaceSuggestion"], "resource")
        self.assertEqual(sample_selection["inspectorRoute"], "sample_audio")
        self.assertEqual(sample_selection["provenance"], "HQF_Init sample runtime id uses zero-based sample index.")
        self.assertEqual(sample_selection["evidenceStatus"], "source_backed")
        self.assertTrue(sample_selection["exportCapability"]["exportable"])
        self.assertEqual(sample_selection["exportActions"][0]["targetAssetId"], "SAMPLES.HQR:0")
        self.assertEqual(sample_selection["facets"]["semanticLayout"], "sample_wave_audio")
        self.assertEqual(sample_selection["facets"]["decodedBytes"], 12)
        self.assertEqual(table_selection["workspaceSuggestion"], "resource")
        self.assertEqual(table_selection["inspectorRoute"], "runtime_table")
        self.assertFalse(table_selection["exportCapability"]["exportable"])
        self.assertEqual(table_selection["exportActions"], [])

    def test_bkg_brick_graphic_selection_is_not_exportable_without_server_route(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        brick_selection = catalog_selection_projection(graph)["LBA_BKG.HQR:1024"]

        self.assertEqual(brick_selection["inspectorRoute"], "background")
        self.assertEqual(brick_selection["facets"]["semanticLayout"], "bkg_brick_graphic")
        self.assertFalse(brick_selection["exportCapability"]["exportable"])
        self.assertEqual(brick_selection["exportActions"], [])

    def test_catalog_graph_and_server_share_exportability_routes(self) -> None:
        expected_routes = {
            ("model", None): "model",
            ("resource", "sample_wave_audio"): "sample_audio",
            ("resource", "lba2_texture_atlas_indexed"): "ress_indexed_image",
            ("resource", "lba2_indexed_image_256"): "ress_indexed_image",
            ("resource", "screen_indexed_image_640x480"): "screen_indexed_image",
            ("resource", "bkg_grid_map"): "bkg_grid_composition",
            ("resource", "holomap_plan_image_640x480"): "holomap_plan_image",
            ("resource", "text_payload_bank"): "text_payload_bank",
            ("resource", "smacker_video"): "smacker_video",
            ("scene", "scene_runtime_layout_partial"): "scene_background_composition",
            ("sprite", "lsp_sprite_frame"): "sprite_frame",
            ("sprite", "raw_sprite_frame"): "sprite_frame",
        }
        self.assertEqual(CATALOG_EXPORT_ROUTES_BY_KIND_LAYOUT, expected_routes)
        for (kind, layout), route in expected_routes.items():
            with self.subTest(kind=kind, layout=layout):
                asset = {
                    "kind": kind,
                    "stats": {
                        "semantic_layout": layout,
                        "reconnaissance": {
                            "background": {
                                "resolved_gri_entry": 1,
                                "resolved_bll_entry": 3,
                            }
                        },
                    },
                }
                node = {
                    "assetKind": kind,
                    "semanticLayout": layout,
                    "sceneBackgroundResolved": True,
                }
                self.assertEqual(catalog_asset_export_route(asset), route)
                self.assertEqual(graph_asset_export_route(node), route)

        negatives = [
            ("resource", "bkg_brick_graphic"),
            ("resource", "bkg_grm_fragment"),
            ("animation", "unknown"),
            ("scene", "unknown"),
            ("sprite", "anim3ds_frame_ranges"),
        ]
        for kind, layout in negatives:
            with self.subTest(kind=kind, layout=layout):
                self.assertIsNone(catalog_asset_export_route({"kind": kind, "stats": {"semantic_layout": layout}}))
                self.assertIsNone(graph_asset_export_route({"assetKind": kind, "semanticLayout": layout}))

        scene_asset = {
            "kind": "scene",
            "stats": {
                "semantic_layout": "scene_runtime_layout_partial",
                "reconnaissance": {"background": {"resolved_gri_entry": "1", "resolved_bll_entry": 3}},
            },
        }
        scene_node = {
            "assetKind": "scene",
            "semanticLayout": "scene_runtime_layout_partial",
            "sceneBackgroundResolved": False,
        }
        self.assertIsNone(catalog_asset_export_route(scene_asset))
        self.assertIsNone(graph_asset_export_route(scene_node))

    def test_scene_selection_requires_exact_int_gri_and_bll_for_exportability(self) -> None:
        invalid_backgrounds = {
            "missing_gri": {"resolved_bll_entry": 3},
            "missing_bll": {"resolved_gri_entry": 1},
            "string_gri": {"resolved_gri_entry": "1", "resolved_bll_entry": 3},
            "string_bll": {"resolved_gri_entry": 1, "resolved_bll_entry": "3"},
            "bool_gri": {"resolved_gri_entry": True, "resolved_bll_entry": 3},
            "bool_bll": {"resolved_gri_entry": 1, "resolved_bll_entry": True},
        }
        for name, background in invalid_backgrounds.items():
            with self.subTest(name=name):
                catalog = synthetic_catalog()
                scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
                scene["stats"]["reconnaissance"]["background"] = background  # type: ignore[index]
                graph = build_catalog_graph(catalog)

                selection = catalog_selection_projection(graph)["SCENE.HQR:2"]

                self.assertEqual(selection["inspectorRoute"], "scene")
                self.assertFalse(selection["exportCapability"]["exportable"])
                self.assertEqual(selection["exportActions"], [])

        catalog = synthetic_catalog()
        scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
        scene["stats"]["reconnaissance"]["background"] = {  # type: ignore[index]
            "resolved_gri_entry": 1,
            "resolved_bll_entry": 3,
        }
        graph = build_catalog_graph(catalog)

        selection = catalog_selection_projection(graph)["SCENE.HQR:2"]

        self.assertTrue(selection["exportCapability"]["exportable"])
        self.assertEqual(selection["exportActions"][0]["targetAssetId"], "SCENE.HQR:2")

    def test_scene_load_does_not_preview_without_exact_int_gri_and_bll(self) -> None:
        invalid_backgrounds = {
            "missing_gri": {"resolved_bll_entry": 3},
            "missing_bll": {"resolved_gri_entry": 1},
            "string_gri": {"resolved_gri_entry": "1", "resolved_bll_entry": 3},
            "string_bll": {"resolved_gri_entry": 1, "resolved_bll_entry": "3"},
            "bool_gri": {"resolved_gri_entry": True, "resolved_bll_entry": 3},
            "bool_bll": {"resolved_gri_entry": 1, "resolved_bll_entry": True},
        }
        for name, background in invalid_backgrounds.items():
            with self.subTest(name=name):
                catalog = synthetic_catalog()
                scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
                scene["stats"]["reconnaissance"]["background"] = background  # type: ignore[index]
                server = ViewerServer(None, None)
                server.catalog = catalog
                httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_class())
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{httpd.server_port}/api/catalog/load",
                        data=json.dumps({"id": "SCENE.HQR:2"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=2) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                finally:
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join(2)

                self.assertEqual(payload["scene"]["id"], "SCENE.HQR:2")
                self.assertNotIn("sprite", payload)
                self.assertNotIn("error", payload)

    def test_scene_object_relationship_projection_preserves_graph_edges_and_missing_targets(self) -> None:
        graph = build_catalog_graph(synthetic_catalog_without_reverse_usages())

        projection = catalog_scene_object_relationship_projection(graph)["SCENE.HQR:2#object:2"]
        edge_types = {edge["type"] for edge in projection["edges"]}
        visual_links = {link["role"]: link for link in projection["visualLinks"]}
        sprite_edge = next(edge for edge in projection["edges"] if edge["type"] == "USES_AS_SPRITE")

        self.assertIn("HAS_FILE3D_RECORD", edge_types)
        self.assertIn("USES_AS_BODY", edge_types)
        self.assertIn("USES_AS_ANIMATION", edge_types)
        self.assertIn("USES_AS_SPRITE", edge_types)
        self.assertEqual(visual_links["file3d"]["stableId"], "RESS.HQR:44#file3d:7")
        self.assertEqual(visual_links["body"]["stableId"], "BODY.HQR:29")
        self.assertEqual(visual_links["animation"]["stableId"], "ANIM.HQR:220")
        self.assertEqual(visual_links["sprite"]["stableId"], "SPRITES.HQR:999")
        self.assertFalse(visual_links["sprite"]["targetAvailable"])
        self.assertEqual(sprite_edge["to"]["type"], "MissingTarget")
        self.assertEqual(sprite_edge["proofScope"], "scene_object_state")
        self.assertEqual(sprite_edge["evidenceStatus"], "unknown")
        self.assertEqual(sprite_edge["sourceField"], "SceneObject.links.sprite.asset_id / SceneAssetUsage.target_asset_id")
        self.assertEqual(sprite_edge["indexRule"], "InitSprite selects SPRITES.HQR when SPRITE_3D is set, ANIM_3DS is clear, and Sprite >= 100.")

    def test_server_catalog_projection_exposes_scene_object_relationship_projection(self) -> None:
        server = ViewerServer(None, None)
        server.catalog = synthetic_catalog_without_reverse_usages()
        server.attach_catalog_graph_projection()

        projection = server.catalog["graph"]["sceneObjectRelationshipsByStableId"]["SCENE.HQR:2#object:2"]  # type: ignore[index]

        self.assertEqual(projection["nodeId"], "scene-object:SCENE.HQR:2:2")
        self.assertEqual(projection["visualLinks"][1]["role"], "body")
        self.assertEqual(projection["visualLinks"][3]["stableId"], "SPRITES.HQR:999")

    def test_compact_catalog_response_excludes_full_graph_projections(self) -> None:
        server = ViewerServer(None, None)
        server.catalog = synthetic_catalog_without_reverse_usages()
        server.ensure_catalog_graph()

        compact = server.compact_catalog_response()
        selection = server.catalog_graph_selection("BODY.HQR:29")

        self.assertEqual(compact["schema"], "viewer-compact-catalog-v1")
        self.assertNotIn("graph", compact)
        self.assertNotIn("selectionByAssetId", json.dumps(compact))
        self.assertNotIn("selectionByStableId", json.dumps(compact))
        self.assertNotIn("sceneObjectRelationshipsByStableId", json.dumps(compact))
        self.assertLess(len(json.dumps(compact).encode("utf-8")), 20000)
        self.assertTrue(selection["found"])
        self.assertEqual(selection["selection"]["stableId"], "BODY.HQR:29")

    def test_http_catalog_and_build_return_compact_catalog(self) -> None:
        server = ViewerServer(None, None)
        server.catalog = synthetic_catalog_without_reverse_usages()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_class())
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{httpd.server_port}/catalog.json",
                timeout=2,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(2)

        self.assertEqual(payload["schema"], "viewer-compact-catalog-v1")
        self.assertNotIn("graph", payload)
        self.assertNotIn("capabilities", payload)

    def test_catalog_query_surface_is_bounded_and_backend_owned(self) -> None:
        server = ViewerServer(None, None)
        server.catalog = synthetic_catalog_without_reverse_usages()

        search = server.catalog_search_response({"q": "saucer", "kind": "model", "limit": 1})
        detail = server.catalog_asset_detail("BODY.HQR:29")
        selection = server.catalog_graph_selection("BODY.HQR:29")
        usages = server.catalog_graph_usages({"id": "BODY.HQR:29", "limit": 1})
        edges = server.catalog_graph_edges({"id": "BODY.HQR:29", "direction": "both", "limit": 1})
        compatible = server.catalog_graph_compatible_compact("BODY.HQR:2")

        self.assertEqual(len(search["assets"]), 1)
        self.assertEqual(search["assets"][0]["id"], "BODY.HQR:29")
        self.assertEqual(detail["asset"]["stats"]["bones"], 19)
        self.assertEqual(selection["selection"]["facets"]["relationshipLinkCount"], 2)
        self.assertEqual(usages["limit"], 1)
        self.assertLessEqual(len(usages["edges"]), 1)
        self.assertEqual(edges["limit"], 1)
        self.assertLessEqual(len(edges["edges"]), 1)
        self.assertIn("ANIM.HQR:2", compatible["compatibleAnimationIds"])
        self.assertNotIn("edges", compatible)

    def test_script_reference_occurrences_do_not_collapse(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())

        usages = query_usages(graph, "BODY.HQR:29", proof_scope="script_reference")
        body_script_edges = [edge for edge in usages["edges"] if edge["type"] == "SCRIPT_REFERENCES"]

        self.assertGreaterEqual(len(body_script_edges), 2)
        self.assertEqual(len({edge["id"] for edge in body_script_edges}), len(body_script_edges))
        self.assertTrue(all(edge["edgeId"] == edge["id"] for edge in body_script_edges))

    def test_relationship_row_selection_uses_edge_id(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())

        selection = catalog_selection_projection(graph)["BODY.HQR:29"]
        link = next(link for link in selection["links"] if link["proofScope"] == "scene_object_state")
        record = next(record for record in selection["usageRecords"] if record["proofScope"] == "scene_object_state")
        edge_selection = catalog_node_selection_projection(graph)[link["edgeId"]]

        self.assertTrue(str(link["edgeId"]).startswith("edge:"))
        self.assertEqual(record["graphEdgeId"], link["edgeId"])
        self.assertEqual(record["selectedEdgeId"], link["edgeId"])
        self.assertEqual(edge_selection["kind"], "graph_edge")
        self.assertEqual(edge_selection["stableId"], link["edgeId"])
        self.assertEqual(edge_selection["facets"]["selectedEdgeId"], link["edgeId"])
        self.assertEqual(edge_selection["exportActions"][0]["targetAssetId"], "BODY.HQR:29")
        self.assertEqual(edge_selection["exportActions"][0]["selectedEdgeId"], link["edgeId"])

    def test_resource_record_selection_comes_from_graph_node(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        selection = catalog_node_selection_projection(graph)["RESS.HQR:48#record:0"]

        self.assertEqual(selection["kind"], "resource_record")
        self.assertEqual(selection["stableId"], "RESS.HQR:48#record:0")
        self.assertEqual(selection["facets"]["graphNodeId"], "resource-record:RESS.HQR:48:0")
        self.assertEqual(selection["workspaceSuggestion"], "resource")

    def test_subgraph_export_includes_selected_edge_identity(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        edge_id = query_usages(graph, "BODY.HQR:29")["edges"][0]["id"]

        subgraph = query_export(graph, edge_id)

        self.assertEqual(subgraph["rootKind"], "edge")
        self.assertEqual(subgraph["selectedEdgeId"], edge_id)
        self.assertIn(edge_id, {edge["id"] for edge in subgraph["edges"]})

    def test_export_context_proof_scope_not_ambiguous(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        selected_edge_id = query_usages(graph, "BODY.HQR:29", proof_scope="scene_object_state")["edges"][0]["id"]

        filtered = query_export_context(graph, "BODY.HQR:29", "scene_object_state")
        selected = query_export_context(
            graph,
            "BODY.HQR:29",
            "decoded model export proof",
            selected_edge_id=selected_edge_id,
        )
        unfiltered = query_export_context(graph, "BODY.HQR:29", "decoded model export proof")

        self.assertEqual(filtered["relationship_proof_filter"], "scene_object_state")
        self.assertEqual(filtered["script_reference_count"], 0)
        self.assertEqual(len(filtered["selected_edge_ids"]), 1)
        self.assertEqual(selected["selected_edge_ids"], [selected_edge_id])
        self.assertEqual(selected["relationship_link_count"], 1)
        self.assertGreater(unfiltered["script_reference_count"], 0)
        self.assertIsNone(unfiltered["relationship_proof_filter"])

    def test_scene_zones_materialized_with_contract_edges(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        zone_id = scene_zone_node_id_for("SCENE.HQR:2", 0)

        zone = graph.nodes_by_id[zone_id]
        edges = graph.node_edges(zone_id, "out")
        edge_types = {edge["type"] for edge in edges}

        self.assertEqual(zone["type"], "SceneZone")
        self.assertIn("message", zone["contractKinds"])
        self.assertIn("HAS_ZONE", {edge["type"] for edge in graph.node_edges(zone_id, "in")})
        self.assertIn("DECLARES_RUNTIME_CONTRACT", edge_types)
        self.assertIn("USES_TEXT", edge_types)
        self.assertIn("REFERENCES_ZONE", edge_types)

    def test_change_cube_zone_edge_uses_deferred_background_target(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        zone_id = scene_zone_node_id_for("SCENE.HQR:2", 2)

        edge = next(edge for edge in graph.node_edges(zone_id, "out") if edge["type"] == "CHANGES_CUBE_TO")
        target = graph.nodes_by_id[edge["to"]]

        self.assertEqual(edge["proofScope"], "classic_source_rule")
        self.assertEqual(edge["evidenceStatus"], "source_backed")
        self.assertEqual(edge["rawReference"], 9)
        self.assertEqual(target["type"], "MissingTarget")
        self.assertEqual(target["targetKind"], "background_resource")
        self.assertEqual(target["resolutionState"], "intentionally_deferred_target")

    def test_waypoints_materialized_and_script_refs_resolve(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        waypoint_id = waypoint_node_id_for("SCENE.HQR:2", 1)
        instruction_id = script_instruction_node_id_for("SCENE.HQR:2", 2, "track", 0)

        self.assertEqual(graph.nodes_by_id[waypoint_id]["type"], "Waypoint")
        self.assertIn(
            ("MOVEMENT_TARGETS", waypoint_id),
            {(edge["type"], edge["to"]) for edge in graph.node_edges("scene-object:SCENE.HQR:2:2", "out")},
        )
        self.assertIn(
            ("REFERENCES_WAYPOINT", waypoint_id),
            {(edge["type"], edge["to"]) for edge in graph.node_edges(instruction_id, "out")},
        )

    def test_track_label_targets_stay_out_of_scope_without_waypoint_mapping(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())

        edge_types = {edge["type"] for edge in graph.sorted_edges()}

        self.assertIn(script_instruction_node_id_for("SCENE.HQR:2", 2, "track", 6), graph.nodes_by_id)
        self.assertNotIn("TRACK_LABEL_TARGETS", edge_types)

    def test_script_instruction_declares_execution_contract(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        instruction_id = script_instruction_node_id_for("SCENE.HQR:2", 2, "track", 8)

        edge = next(edge for edge in graph.node_edges(instruction_id, "out") if edge["type"] == "DECLARES_EXECUTION_CONTRACT")

        self.assertEqual(edge["executionContract"], "track_pass_control")
        self.assertEqual(edge["proofScope"], "classic_source_rule")
        self.assertEqual(edge["evidenceStatus"], "source_backed")

    def test_patch_record_targets_runtime_state_field(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        field_id = runtime_state_field_node_id_for("SCENE.HQR:2", 2, "track", 3, "target_offset")
        patch_edges = graph.node_edges("patch-record:SCENE.HQR:2:0", "out")

        self.assertEqual(graph.nodes_by_id[field_id]["type"], "RuntimeStateField")
        self.assertIn(("PATCHES_FIELD", field_id), {(edge["type"], edge["to"]) for edge in patch_edges})
        self.assertIn(
            ("PATCHES_INSTRUCTION", script_instruction_node_id_for("SCENE.HQR:2", 2, "track", 3)),
            {(edge["type"], edge["to"]) for edge in patch_edges},
        )

    def test_scene_mechanics_graph_uses_full_decoded_lists_not_samples(self) -> None:
        catalog = synthetic_scene_mechanics_catalog()
        scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
        recon = scene["stats"]["reconnaissance"]  # type: ignore[index]
        template_object = dict(recon["objects"][0])  # type: ignore[index]
        template_object.pop("runtime", None)
        template_object.pop("track_script_analysis", None)
        template_object.pop("life_script_analysis", None)
        recon["objects"] = [  # type: ignore[index]
            {**template_object, "index": index, "links": {}}
            for index in range(1, 26)
        ]
        recon["sampled_objects"] = recon["objects"][:24]  # type: ignore[index]
        recon["zones"] = [  # type: ignore[index]
            {
                "index": index,
                "offset": 120 + index * 16,
                "start": {"x": index, "y": 0, "z": 0},
                "end": {"x": index + 1, "y": 1, "z": 1},
                "info": [0, 0, 0, 0, 0, 0, 0, 0],
                "type": 1,
                "type_name": "camera",
                "value": index,
                "load_rules": {},
                "runtime": {},
            }
            for index in range(25)
        ]
        recon["sampled_zones"] = recon["zones"][:24]  # type: ignore[index]
        recon["tracks"] = [  # type: ignore[index]
            {"index": index, "offset": 240 + index * 6, "position": {"x": index, "y": index + 1, "z": index + 2}}
            for index in range(25)
        ]
        recon["sampled_tracks"] = recon["tracks"][:24]  # type: ignore[index]
        recon["patches"] = [  # type: ignore[index]
            {
                "index": index,
                "offset": 300 + index * 4,
                "size": 2,
                "target_offset": index,
                "target": {"kind": "unknown", "owner": None, "instruction_found": False},
            }
            for index in range(33)
        ]
        recon["sampled_patches"] = recon["patches"][:32]  # type: ignore[index]

        graph = build_catalog_graph(catalog)

        self.assertIn("scene-object:SCENE.HQR:2:25", graph.nodes_by_id)
        self.assertIn(scene_zone_node_id_for("SCENE.HQR:2", 24), graph.nodes_by_id)
        self.assertIn(waypoint_node_id_for("SCENE.HQR:2", 24), graph.nodes_by_id)
        self.assertIn("patch-record:SCENE.HQR:2:32", graph.nodes_by_id)

    def test_scene_mechanics_graph_requires_canonical_decoded_lists(self) -> None:
        catalog = synthetic_scene_mechanics_catalog()
        scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
        recon = scene["stats"]["reconnaissance"]  # type: ignore[index]
        recon.pop("objects", None)
        recon.pop("zones", None)
        recon.pop("tracks", None)
        recon.pop("patches", None)

        graph = build_catalog_graph(catalog)

        self.assertNotIn("scene-object:SCENE.HQR:2:2", graph.nodes_by_id)
        self.assertNotIn(scene_zone_node_id_for("SCENE.HQR:2", 0), graph.nodes_by_id)
        self.assertNotIn(waypoint_node_id_for("SCENE.HQR:2", 1), graph.nodes_by_id)
        self.assertNotIn("patch-record:SCENE.HQR:2:0", graph.nodes_by_id)

    def test_missing_target_taxonomy(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        sample = graph.nodes_by_id["missing:SAMPLES.HQR:999"]
        video = graph.nodes_by_id["missing:VIDEO/VIDEO.HQR:MISSING"]

        self.assertEqual(sample["targetKind"], "sample")
        self.assertEqual(sample["resolutionState"], "outside_table")
        self.assertEqual(video["resolutionState"], "unresolved_name")
        self.assertEqual(video["targetAvailable"] if "targetAvailable" in video else False, False)

    def test_multiple_occurrences_share_missing_target_but_keep_distinct_edges(self) -> None:
        catalog = synthetic_scene_mechanics_catalog()
        scene = next(asset for asset in catalog["assets"] if asset["id"] == "SCENE.HQR:2")  # type: ignore[index]
        script = scene["stats"]["reconnaissance"]["objects"][0]["track_script_analysis"]  # type: ignore[index]
        missing = {
            "sample_id": 999,
            "hqr_table_index": 1000,
            "status": "outside_archive_table",
            "reason": "outside SAMPLES.HQR table",
            "reference_key": "sample",
            "reference_value": 999,
        }
        script["missing_sample_links"] = [dict(missing), dict(missing)]
        graph = build_catalog_graph(catalog)

        usages = query_usages(graph, "SAMPLES.HQR:999", proof_scope="script_reference", evidence_status="unknown")

        self.assertEqual(graph.nodes_by_id["missing:SAMPLES.HQR:999"]["resolutionState"], "outside_table")
        self.assertEqual(len(usages["edges"]), 2)
        self.assertEqual(len({edge["id"] for edge in usages["edges"]}), 2)

    def test_empty_sample_slot_is_not_decode_failure(self) -> None:
        graph = build_catalog_graph(synthetic_catalog())

        sample = graph.nodes_by_id["missing:SAMPLES.HQR:999"]

        self.assertEqual(sample["absenceEvidenceStatus"], "decoded_absent")
        self.assertEqual(sample["evidenceStatus"], "unknown")

    def test_catalog_graph_never_emits_live_confirmed_without_event_graph(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())

        statuses = {
            str(payload.get("evidenceStatus"))
            for payload in [*graph.nodes_by_id.values(), *graph.edges_by_id.values()]
            if payload.get("evidenceStatus")
        }

        self.assertNotIn("live_confirmed", statuses)

    def test_search_filters_proof_and_evidence_status(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())

        results = query_search(
            graph,
            "target_offset",
            proof_scopes=["script_structure"],
            evidence_statuses=["source_backed"],
            include_edges=True,
        )["results"]

        self.assertTrue(results)
        self.assertTrue(all(result["kind"] == "edge" for result in results if result.get("proofScope")))
        self.assertTrue(all(result.get("proofScope") == "script_structure" for result in results if result["kind"] == "edge"))

    def test_search_returns_edges_and_nodes(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())

        results = query_search(graph, "waypoint", include_edges=True)["results"]
        kinds = {result["kind"] for result in results}

        self.assertIn("node", kinds)
        self.assertIn("edge", kinds)
        self.assertTrue(any(result.get("nodeType") == "Waypoint" for result in results))

    def test_scene_mechanics_query_surfaces_return_graph_backed_selections(self) -> None:
        graph = build_catalog_graph(synthetic_scene_mechanics_catalog())
        instruction_id = script_instruction_node_id_for("SCENE.HQR:2", 2, "track", 8)

        zone = query_zone(graph, "SCENE.HQR:2", "2")
        waypoint = query_waypoint(graph, "SCENE.HQR:2", "1")
        instruction = query_script_instruction(graph, "SCENE.HQR:2", "2", "track", "8")
        selection = query_selection(graph, instruction_id)
        operation = query_animation_operation_compatibility(graph, "BODY.HQR:2", "ANIM.HQR:2")

        self.assertEqual(zone["schema"], "catalog_graph.zone.v0")
        self.assertEqual(zone["node"]["type"], "SceneZone")
        self.assertTrue(any(edge["type"] == "CHANGES_CUBE_TO" for edge in zone["edges"]))
        self.assertEqual(waypoint["node"]["type"], "Waypoint")
        self.assertEqual(instruction["node"]["type"], "ScriptInstruction")
        self.assertTrue(selection["found"])
        self.assertEqual(selection["selection"]["kind"], "script_instruction")
        self.assertEqual(operation["schema"], "catalog_graph.animation_operation_compatibility.v0")


if __name__ == "__main__":
    unittest.main()
