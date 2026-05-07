import unittest

from lba2_lm2_viewer.catalog_graph import (
    asset_node_id_for,
    build_catalog_graph,
    export_graph_document,
    file3d_record_node_id_for,
    graph_from_export_document,
    query_edges,
    query_prove,
    query_scene_object,
    query_usages,
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
                        "sampled_objects": [
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
                        ]
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


if __name__ == "__main__":
    unittest.main()
