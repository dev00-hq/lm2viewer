from lba2_lm2_viewer.entities import (
    build_asset_entity_workflow,
    build_runtime_sprite_entity_workflow,
)


def synthetic_catalog():
    scene_object = {
        "index": 7,
        "flags": 1024,
        "file3d_index": -1,
        "gen_body": 0,
        "gen_anim": 0,
        "sprite": 127,
        "position": {"x": 10, "y": 20, "z": 30},
        "runtime": {
            "source": "synthetic scene object runtime semantics",
            "render_type": "projected_sprite",
            "movement": {"mode": 3, "mode_name": "MOVE_TRACK"},
            "collision": {"object": True},
            "combat": {"hit_force": 1, "armor": 0, "life_points": 10},
            "bonus": {"count": 0},
            "render_pipeline": {
                "source": "OBJECT.CPP::AffOneObject",
                "draw_path": "PtrAffGraph projected sprite draw",
                "sort_key": "TreeInsert sorted object",
                "recovery_path": "DrawRecover masking",
                "contract_steps": ["camera_preclip", "TreeInsert", "PtrAffGraph", "DrawRecover"],
                "redraw_contract": {"method": "DrawRecover", "moving_box": False},
                "aff_scene_policy": {"tree_insert": "scene objects insert before dynamic lists"},
            },
        },
        "links": {
            "sprite": {
                "asset_id": "SPRITES.HQR:127",
                "asset_available": True,
                "backend": "sprites",
                "runtime_sprite_index": 127,
                "index_rule": "SPRITE_3D without ANIM_3DS resolves SPRITES.HQR by Sprite value",
            },
            "missing_asset_ids": [],
        },
        "track_script_analysis": {"asset_links": []},
        "life_script_analysis": {
            "asset_links": [
                {
                    "kind": "sprite",
                    "reference_key": "sprite",
                    "reference_value": 127,
                    "asset_id": "SPRITES.HQR:127",
                    "asset_available": True,
                    "backend": "sprites",
                    "runtime_sprite_index": 127,
                    "index_rule": "script Sprite operand resolves through runtime sprite rule",
                }
            ],
            "local_links": [{"kind": "object", "reference_key": "obj", "reference_value": 7}],
            "cross_script_links": [],
        },
    }
    direct_usage = {
        "kind": "sprite",
        "scene_asset_id": "SCENE.HQR:22",
        "scene_label": "SCENE.HQR scene 22",
        "scene_entry_index": 22,
        "scene_index": 21,
        "object_index": 7,
        "position": scene_object["position"],
        "file3d_index": -1,
        "gen_body": 0,
        "gen_anim": 0,
        "sprite": 127,
        "flags": 1024,
        "target_asset_id": "SPRITES.HQR:127",
        "backend": "sprites",
        "runtime_sprite_index": 127,
        "index_rule": "SPRITE_3D without ANIM_3DS resolves SPRITES.HQR by Sprite value",
        "resolution_rule": "SPRITE_3D without ANIM_3DS resolves SPRITES.HQR by Sprite value",
    }
    script_usage = {
        **direct_usage,
        "kind": "script_sprite",
        "script_kind": "life",
        "reference_key": "sprite",
        "reference_value": 127,
    }
    return {
        "assets": [
            {
                "id": "SCENE.HQR:22",
                "kind": "scene",
                "label": "SCENE.HQR scene 22",
                "entry_type": "scene",
                "source": {"hqr": "SCENE.HQR", "entry_index": 22},
                "stats": {
                    "reconnaissance": {
                        "sampled_objects": [scene_object],
                    }
                },
            },
            {
                "id": "SPRITES.HQR:127",
                "kind": "sprite",
                "label": "SPRITES.HQR sprite 127",
                "entry_type": "sprite-frame",
                "source": {"hqr": "SPRITES.HQR", "entry_index": 127},
                "stats": {},
                "scene_usages": [direct_usage, script_usage],
            },
        ]
    }


def test_asset_entity_workflow_centers_scene_entity_and_contract():
    workflow = build_asset_entity_workflow(synthetic_catalog(), "SPRITES.HQR:127")

    assert workflow["resolved_asset"]["id"] == "SPRITES.HQR:127"
    assert workflow["usage_groups"][0]["entity_id"] == "SCENE.HQR:22#object:7"
    assert set(workflow["usage_groups"][0]["usage_classes"]) == {
        "direct_scene_state",
        "script_driven_state",
    }
    entity = workflow["selected_entity"]
    assert entity["entity_id"] == "SCENE.HQR:22#object:7"
    assert entity["render_backend"] == "projected_sprite"
    assert entity["render_contract"]["draw_path"] == "PtrAffGraph projected sprite draw"
    assert entity["script_driven_links"][0]["asset_id"] == "SPRITES.HQR:127"
    assert any(item["area"] == "redraw" for item in entity["port_implications"])


def test_runtime_sprite_workflow_marks_usage_as_runtime_dynamic_entrypoint():
    workflow = build_runtime_sprite_entity_workflow(
        synthetic_catalog(),
        {
            "flags": 1024,
            "sprite_index": 127,
            "object_index": 7,
            "body_num": 127,
            "label_track": None,
            "resolution": {
                "asset_id": "SPRITES.HQR:127",
                "index_rule": "SPRITE_3D without ANIM_3DS resolves SPRITES.HQR by Sprite value",
            },
        },
    )

    assert workflow["entrypoint"]["kind"] == "runtime_sprite"
    assert workflow["evidence_trail"][0]["label"] == "Runtime Sprite 127 flags 0x400"
    assert "runtime_dynamic_entrypoint" in workflow["usage_groups"][0]["usage_classes"]
    assert workflow["usage_groups"][0]["usages"][0]["usage_class"] == "direct_scene_state"
    assert workflow["selected_entity"]["entity_id"] == "SCENE.HQR:22#object:7"
