"""Canonical catalog export route eligibility."""

from __future__ import annotations

from typing import Any


CATALOG_EXPORT_ROUTES_BY_KIND_LAYOUT: dict[tuple[str, str | None], str] = {
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


def catalog_export_route_for_kind_layout(kind: Any, semantic_layout: Any) -> str | None:
    if kind == "model":
        return CATALOG_EXPORT_ROUTES_BY_KIND_LAYOUT.get(("model", None))
    if not isinstance(kind, str):
        return None
    layout = semantic_layout if isinstance(semantic_layout, str) else None
    return CATALOG_EXPORT_ROUTES_BY_KIND_LAYOUT.get((kind, layout))


def has_exact_scene_background_links(stats: Any) -> bool:
    if not isinstance(stats, dict):
        return False
    background = ((stats.get("reconnaissance") or {}).get("background") or {})
    return (
        type(background.get("resolved_gri_entry")) is int
        and type(background.get("resolved_bll_entry")) is int
    )


def catalog_asset_export_route(asset: dict[str, Any]) -> str | None:
    stats = asset.get("stats") or {}
    layout = stats.get("semantic_layout") if isinstance(stats, dict) else None
    route = catalog_export_route_for_kind_layout(asset.get("kind"), layout)
    if route == "scene_background_composition" and not has_exact_scene_background_links(stats):
        return None
    return route


def graph_asset_export_route(node: dict[str, Any]) -> str | None:
    route = catalog_export_route_for_kind_layout(node.get("assetKind"), node.get("semanticLayout"))
    if route == "scene_background_composition" and not node.get("sceneBackgroundResolved"):
        return None
    return route
