import unittest

from lba2_lm2_viewer.entities import build_scene_object_entity_workflow


class EntityWorkflowTests(unittest.TestCase):
    def test_scene_object_workflow_selects_requested_object(self) -> None:
        catalog = {
            "assets": [
                {
                    "id": "SCENE.HQR:3",
                    "kind": "scene",
                    "label": "Scene 2",
                    "entry_type": "scene",
                    "source": {"hqr": "SCENE.HQR", "entry_index": 3},
                    "features": {},
                    "stats": {
                        "semantic_layout": "scene_runtime_layout_partial",
                        "reconnaissance": {
                            "objects": [
                                {
                                    "index": 1,
                                    "flags": 0x884,
                                    "file3d_index": 7,
                                    "gen_body": 26,
                                    "gen_anim": 205,
                                    "sprite": 0,
                                    "position": {"x": 140, "y": 0, "z": 0},
                                    "runtime": {
                                        "render_type": "body_model",
                                        "render_pipeline": {
                                            "draw_path": "AffObjetIso",
                                            "recovery_path": "DrawRecover",
                                            "contract_steps": ["sort object", "draw body"],
                                            "source": "OBJECT.CPP",
                                        },
                                    },
                                    "links": {
                                        "body": {
                                            "asset_id": "BODY.HQR:26",
                                            "asset_available": True,
                                            "resolution_rule": "File3D",
                                        },
                                        "animation": {
                                            "asset_id": "ANIM.HQR:205",
                                            "asset_available": True,
                                            "resolution_rule": "GenAnim",
                                        },
                                        "missing_asset_ids": [],
                                    },
                                    "track_script_bytes": 1,
                                    "life_script_bytes": 1,
                                }
                            ]
                        },
                    },
                }
            ]
        }

        workflow = build_scene_object_entity_workflow(catalog, "SCENE.HQR:3", 1)

        self.assertEqual(workflow["entrypoint"]["kind"], "scene_object")
        self.assertEqual(workflow["entrypoint"]["object_index"], 1)
        self.assertEqual(workflow["selected_entity"]["entity_id"], "SCENE.HQR:3#object:1")
        self.assertEqual(workflow["selected_entity"]["confidence"], "evidence")
        self.assertEqual(workflow["selected_entity"]["render_contract"]["draw_path"], "AffObjetIso")
        self.assertEqual(
            [link["asset_id"] for link in workflow["selected_entity"]["linked_visual_assets"]],
            ["BODY.HQR:26", "ANIM.HQR:205"],
        )
        self.assertEqual(workflow["usage_groups"][0]["entity_id"], "SCENE.HQR:3#object:1")

    def test_scene_object_workflow_carries_anim3ds_range_state(self) -> None:
        catalog = {
            "assets": [
                {
                    "id": "SCENE.HQR:1",
                    "kind": "scene",
                    "label": "Scene 0",
                    "entry_type": "scene",
                    "source": {"hqr": "SCENE.HQR", "entry_index": 1},
                    "features": {},
                    "stats": {
                        "semantic_layout": "scene_runtime_layout_partial",
                        "reconnaissance": {
                            "objects": [
                                {
                                    "index": 0,
                                    "flags": 0x800,
                                    "file3d_index": 0,
                                    "gen_body": 0,
                                    "gen_anim": 0,
                                    "sprite": 4,
                                    "runtime": {
                                        "render_type": "ANIM3DS sprite",
                                        "render_pipeline": {"draw_path": "AffObjetIso"},
                                    },
                                    "links": {
                                        "sprite": {
                                            "asset_id": "ANIM3DS.HQR:4",
                                            "asset_available": True,
                                            "resolution_rule": "ANIM3DS frame range",
                                            "anim3ds_range": {
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
                                        },
                                        "missing_asset_ids": [],
                                    },
                                }
                            ]
                        },
                    },
                }
            ]
        }

        workflow = build_scene_object_entity_workflow(catalog, "SCENE.HQR:1", 0)

        self.assertEqual(
            workflow["selected_entity"]["initial_state"]["anim3ds_range"]["name"],
            "ROUE",
        )
        self.assertEqual(
            workflow["selected_entity"]["initial_state"]["anim3ds_range"]["frames_per_second"],
            24,
        )


if __name__ == "__main__":
    unittest.main()
