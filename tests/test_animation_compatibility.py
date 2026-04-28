import unittest

from lba2_lm2_viewer import server
from lba2_lm2_viewer import viewer


def model_asset(entry_index: int, bones: int, hqr: str = "BODY.HQR") -> dict[str, object]:
    return {
        "id": f"{hqr}:{entry_index}",
        "kind": "model",
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
        "stats": {"boneframes": boneframes},
    }
    if compatible_body_ids is not None:
        asset["animation_metadata"] = {"compatible_body_ids": compatible_body_ids}
    return asset


class AnimationCompatibilityTests(unittest.TestCase):
    def test_file3d_body_metadata_rejects_same_bone_wrong_body(self) -> None:
        error = server.animation_compatibility_error(
            model_asset(8, 23),
            animation_asset(23, [454]),
        )

        self.assertIn("not BODY.HQR:8", error or "")

    def test_file3d_body_metadata_accepts_listed_body(self) -> None:
        self.assertIsNone(
            server.animation_compatibility_error(
                model_asset(454, 23),
                animation_asset(23, [454]),
            )
        )

    def test_missing_file3d_metadata_falls_back_to_bone_count(self) -> None:
        self.assertIsNone(
            server.animation_compatibility_error(
                model_asset(8, 23),
                animation_asset(23),
            )
        )

    def test_non_body_hqr_models_fall_back_to_bone_count(self) -> None:
        self.assertIsNone(
            server.animation_compatibility_error(
                model_asset(1, 23, hqr="CUSTOM.HQR"),
                animation_asset(23, [454]),
            )
        )

    def test_bone_mismatch_rejects_before_metadata_fallback(self) -> None:
        error = server.animation_compatibility_error(
            model_asset(454, 19),
            animation_asset(23, [454]),
        )

        self.assertIn("bone count", error or "")

    def test_ensure_animation_compatible_raises_lm2_error(self) -> None:
        with self.assertRaisesRegex(viewer.Lm2Error, "ANIM.HQR:2018"):
            server.ensure_animation_compatible(
                model_asset(8, 23),
                animation_asset(23, [454]),
            )


if __name__ == "__main__":
    unittest.main()
