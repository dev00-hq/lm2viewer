import unittest

from lba2_lm2_viewer.catalog_graph import (
    build_catalog_graph,
    query_animation_operation_compatibility,
)
from lba2_lm2_viewer.server import ViewerServer
from lba2_lm2_viewer.viewer import Lm2Error


def model_asset(entry_index: int, bones: int, hqr: str = "BODY.HQR") -> dict[str, object]:
    return {
        "id": f"{hqr}:{entry_index}",
        "kind": "model",
        "entry_type": "body",
        "label": f"{hqr}:{entry_index} model",
        "source": {"hqr": hqr, "entry_index": entry_index},
        "stats": {"bones": bones},
    }


def animation_asset(
    boneframes: int,
    compatible_body_ids: list[int] | None = None,
) -> dict[str, object]:
    asset: dict[str, object] = {
        "id": "ANIM.HQR:2018",
        "kind": "animation",
        "entry_type": "animation",
        "label": "test animation",
        "source": {"hqr": "ANIM.HQR", "entry_index": 2018},
        "stats": {"boneframes": boneframes},
    }
    if compatible_body_ids is not None:
        asset["animation_metadata"] = {"compatible_body_ids": compatible_body_ids}
    return asset


def catalog_with_assets(*assets: dict[str, object]) -> dict[str, object]:
    archives = sorted(
        {
            str((asset.get("source") or {}).get("hqr"))
            for asset in assets
            if isinstance(asset.get("source"), dict)
        }
    )
    return {
        "schema": "viewer-catalog-v1",
        "hqr_files": [{"path": archive, "entry_count": 3000} for archive in archives],
        "assets": list(assets),
    }


def operation_result(catalog: dict[str, object], model_id: str = "BODY.HQR:454") -> dict[str, object]:
    graph = build_catalog_graph(catalog)
    return query_animation_operation_compatibility(graph, model_id, "ANIM.HQR:2018")


class AnimationCompatibilityTests(unittest.TestCase):
    def test_file3d_body_metadata_rejects_same_bone_wrong_body(self) -> None:
        catalog = catalog_with_assets(
            model_asset(8, 23),
            model_asset(454, 23),
            animation_asset(23, [454]),
        )

        result = operation_result(catalog, "BODY.HQR:8")

        self.assertFalse(result["eligible"])
        self.assertIn("not BODY.HQR:8", str(result["error"]))

    def test_file3d_body_metadata_accepts_listed_body(self) -> None:
        catalog = catalog_with_assets(model_asset(454, 23), animation_asset(23, [454]))

        result = operation_result(catalog)

        self.assertTrue(result["eligible"])
        self.assertEqual(result["proofs"][0]["compatibilityReason"], "file3d_allowlist")

    def test_missing_file3d_metadata_uses_bone_count_graph_edge(self) -> None:
        catalog = catalog_with_assets(model_asset(8, 23), animation_asset(23))

        result = operation_result(catalog, "BODY.HQR:8")

        self.assertTrue(result["eligible"])
        self.assertEqual(result["proofs"][0]["compatibilityReason"], "bone_count_only")

    def test_non_body_hqr_models_follow_graph_allowlist_contract(self) -> None:
        catalog = catalog_with_assets(
            model_asset(1, 23, hqr="CUSTOM.HQR"),
            model_asset(454, 23),
            animation_asset(23, [454]),
        )

        result = operation_result(catalog, "CUSTOM.HQR:1")

        self.assertFalse(result["eligible"])
        self.assertIn("BODY.HQR entries [454]", str(result["error"]))

    def test_bone_mismatch_blocks_allowlist_edge_for_playback(self) -> None:
        catalog = catalog_with_assets(model_asset(454, 19), animation_asset(23, [454]))

        result = operation_result(catalog)

        self.assertFalse(result["eligible"])
        self.assertEqual(result["proofs"], [])
        self.assertIn("bone count", str(result["error"]))

    def test_server_pose_guard_uses_graph_operation_result(self) -> None:
        catalog = catalog_with_assets(
            model_asset(8, 23),
            model_asset(454, 23),
            animation_asset(23, [454]),
        )
        server = ViewerServer(None, None)
        server.catalog = catalog
        server.attach_catalog_graph_projection()

        with self.assertRaisesRegex(Lm2Error, "ANIM.HQR:2018"):
            server.ensure_animation_operation_compatible(
                catalog["assets"][0],  # type: ignore[index]
                catalog["assets"][2],  # type: ignore[index]
            )


if __name__ == "__main__":
    unittest.main()
