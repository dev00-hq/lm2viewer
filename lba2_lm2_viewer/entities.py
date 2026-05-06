"""Entity-centered evidence workflow payloads."""

from __future__ import annotations

from typing import Any


SCENE_ARCHIVE_NAME = "SCENE.HQR"


def build_asset_entity_workflow(catalog: dict[str, Any], asset_id: str) -> dict[str, Any]:
    asset = find_asset(catalog, asset_id)
    if asset is None:
        return {
            "schema": "lba2_entity_workflow.v0",
            "entrypoint": {"kind": "asset", "asset_id": asset_id},
            "resolved_asset": None,
            "usage_groups": [],
            "selected_entity": None,
            "evidence_trail": [{"step": "entrypoint", "label": f"Selected asset {asset_id}"}],
            "unknowns": unknowns_for(None, None, []),
        }
    usages = list(asset.get("scene_usages") or [])
    selected_usage = first_object_usage(usages)
    entity = build_entity_contract(catalog, selected_usage) if selected_usage else None
    return {
        "schema": "lba2_entity_workflow.v0",
        "entrypoint": {
            "kind": "asset",
            "asset_id": asset_id,
            "label": asset.get("label"),
        },
        "resolved_asset": compact_asset(asset),
        "usage_groups": group_usages(usages),
        "selected_entity": entity,
        "evidence_trail": build_evidence_trail(
            entrypoint=f"Selected asset {asset_id}",
            resolved_asset=asset,
            selected_usage=selected_usage,
            entity=entity,
        ),
        "unknowns": unknowns_for(asset, entity, usages),
    }


def build_scene_object_entity_workflow(
    catalog: dict[str, Any], scene_asset_id: str, object_index: int
) -> dict[str, Any]:
    scene_asset = find_asset(catalog, scene_asset_id)
    if scene_asset is None:
        return {
            "schema": "lba2_entity_workflow.v0",
            "entrypoint": {
                "kind": "scene_object",
                "scene_asset_id": scene_asset_id,
                "object_index": object_index,
            },
            "resolved_asset": None,
            "usage_groups": [],
            "selected_entity": None,
            "evidence_trail": [
                {
                    "step": "entrypoint",
                    "label": f"Scene object {scene_asset_id}#{object_index}",
                }
            ],
            "unknowns": unknowns_for(None, None, []),
        }
    source = scene_asset.get("source") or {}
    scene_entry_index = source.get("entry_index")
    scene_index = (
        int(scene_entry_index) - 1
        if isinstance(scene_entry_index, int)
        else source.get("classic_index")
    )
    selected_usage = {
        "kind": "scene_object",
        "scene_asset_id": scene_asset_id,
        "scene_entry_index": scene_entry_index,
        "scene_index": scene_index,
        "scene_label": scene_asset.get("label"),
        "object_index": object_index,
        "resolution_rule": "direct sampled scene object row",
    }
    entity = build_entity_contract(catalog, selected_usage)
    return {
        "schema": "lba2_entity_workflow.v0",
        "entrypoint": {
            "kind": "scene_object",
            "scene_asset_id": scene_asset_id,
            "object_index": object_index,
        },
        "resolved_asset": compact_asset(scene_asset),
        "usage_groups": group_usages([selected_usage]),
        "selected_entity": entity,
        "evidence_trail": build_evidence_trail(
            entrypoint=f"Scene object {scene_asset_id}#{object_index}",
            resolved_asset=scene_asset,
            selected_usage=selected_usage,
            entity=entity,
        ),
        "unknowns": unknowns_for(scene_asset, entity, [selected_usage]),
    }


def build_runtime_sprite_entity_workflow(
    catalog: dict[str, Any], runtime_state: dict[str, Any]
) -> dict[str, Any]:
    resolution = runtime_state.get("resolution") or {}
    asset_id = resolution.get("asset_id")
    asset = find_asset(catalog, asset_id) if isinstance(asset_id, str) else None
    usages = list(asset.get("scene_usages") or []) if asset else []
    object_index = runtime_state.get("object_index")
    selected_usage = matching_runtime_usage(usages, object_index) or first_object_usage(usages)
    entity = build_entity_contract(catalog, selected_usage) if selected_usage else None
    return {
        "schema": "lba2_entity_workflow.v0",
        "entrypoint": {
            "kind": "runtime_sprite",
            "flags": runtime_state.get("flags"),
            "sprite_index": runtime_state.get("sprite_index"),
            "object_index": object_index,
            "body_num": runtime_state.get("body_num"),
            "label_track": runtime_state.get("label_track"),
            "resolution_rule": resolution.get("index_rule"),
        },
        "resolved_asset": compact_asset(asset) if asset else None,
        "runtime_resolution": resolution,
        "usage_groups": group_usages(usages, runtime_dynamic=True),
        "selected_entity": entity,
        "evidence_trail": build_evidence_trail(
            entrypoint=(
                f"Runtime Sprite {runtime_state.get('sprite_index')} "
                f"flags 0x{int(runtime_state.get('flags') or 0):X}"
            ),
            resolved_asset=asset,
            selected_usage=selected_usage,
            entity=entity,
        ),
        "unknowns": unknowns_for(asset, entity, usages),
    }


def find_asset(catalog: dict[str, Any], asset_id: str | None) -> dict[str, Any] | None:
    if not asset_id:
        return None
    for asset in catalog.get("assets", []):
        if asset.get("id") == asset_id:
            return asset
    return None


def first_object_usage(usages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for usage in usages:
        if usage.get("object_index") is not None:
            return usage
    return usages[0] if usages else None


def matching_runtime_usage(
    usages: list[dict[str, Any]], object_index: Any
) -> dict[str, Any] | None:
    for usage in usages:
        if object_index is not None and usage.get("object_index") == object_index:
            return usage
    return None


def build_entity_contract(
    catalog: dict[str, Any], usage: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not usage:
        return None
    scene_asset = find_asset(catalog, usage.get("scene_asset_id"))
    if scene_asset is None:
        return None
    scene_entry_index = usage.get("scene_entry_index")
    object_index = usage.get("object_index")
    scene_id = scene_asset.get("id")
    entity_id = f"{scene_id}#object:{object_index}"
    scene_object = find_scene_object(scene_asset, object_index)
    runtime = (scene_object or {}).get("runtime") or {}
    scripts = script_summary(scene_object or {})
    links = (scene_object or {}).get("links") or {}
    sprite_link = links.get("sprite") if isinstance(links.get("sprite"), dict) else {}
    render_pipeline = runtime.get("render_pipeline") or {}
    return {
        "schema": "lba2_entity_contract.v0",
        "entity_id": entity_id,
        "scene_asset_id": scene_id,
        "scene_entry_index": scene_entry_index,
        "scene_index": usage.get("scene_index"),
        "object_index": object_index,
        "object_sample_status": "sampled" if scene_object else "not_in_compact_scene_sample",
        "label": (
            f"Scene {usage.get('scene_index')} object {object_index}"
            if usage.get("scene_index") is not None
            else entity_id
        ),
        "position": (scene_object or usage).get("position"),
        "render_backend": runtime.get("render_type") or render_backend_from_usage(usage),
        "linked_visual_assets": linked_visual_assets(links),
        "initial_state": {
            "flags": (scene_object or {}).get("flags", usage.get("flags")),
            "file3d_index": (scene_object or {}).get("file3d_index", usage.get("file3d_index")),
            "gen_body": (scene_object or {}).get("gen_body", usage.get("gen_body")),
            "gen_anim": (scene_object or {}).get("gen_anim", usage.get("gen_anim")),
            "sprite": (scene_object or {}).get("sprite", usage.get("sprite")),
            "anim3ds_range": sprite_link.get("anim3ds_range"),
            "movement": runtime.get("movement"),
            "collision": runtime.get("collision"),
            "combat": runtime.get("combat"),
            "bonus": runtime.get("bonus"),
        },
        "script_driven_links": scripts["asset_links"],
        "local_links": scripts["local_links"],
        "cross_script_links": scripts["cross_script_links"],
        "render_contract": {
            "draw_path": render_pipeline.get("draw_path"),
            "sort_key": render_pipeline.get("sort_key"),
            "recovery_path": render_pipeline.get("recovery_path"),
            "contract_steps": render_pipeline.get("contract_steps") or [],
            "redraw_contract": render_pipeline.get("redraw_contract"),
            "render_phase": render_pipeline.get("aff_scene_policy"),
            "source": render_pipeline.get("source") or runtime.get("source"),
        },
        "port_implications": port_implications(runtime, scripts),
        "provenance": {
            "scene_asset": compact_asset(scene_asset),
            "usage_kind": usage.get("kind"),
            "usage_class": usage_class(usage),
            "resolution_rule": usage.get("resolution_rule") or usage.get("index_rule"),
        },
        "confidence": "evidence" if scene_object else "partial",
        "unknowns": entity_unknowns(scene_object, runtime, scripts),
    }


def find_scene_object(scene_asset: dict[str, Any], object_index: Any) -> dict[str, Any] | None:
    if object_index is None:
        return None
    recon = (scene_asset.get("stats") or {}).get("reconnaissance") or {}
    if object_index == 0 and isinstance(recon.get("hero"), dict):
        hero = dict(recon["hero"])
        hero.setdefault("index", 0)
        hero.setdefault("position", hero.get("start"))
        return hero
    for scene_object in recon.get("sampled_objects") or []:
        if scene_object.get("index") == object_index:
            return scene_object
    return None


def group_usages(
    usages: list[dict[str, Any]], *, runtime_dynamic: bool = False
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, Any], dict[str, Any]] = {}
    for usage in usages:
        key = (usage.get("scene_asset_id"), usage.get("object_index"))
        group = groups.setdefault(
            key,
            {
                "scene_asset_id": usage.get("scene_asset_id"),
                "scene_label": usage.get("scene_label"),
                "scene_index": usage.get("scene_index"),
                "object_index": usage.get("object_index"),
                "entity_id": (
                    f"{usage.get('scene_asset_id')}#object:{usage.get('object_index')}"
                    if usage.get("object_index") is not None
                    else None
                ),
                "usage_classes": [],
                "usages": [],
            },
        )
        usage_payload = dict(usage)
        usage_payload["usage_class"] = usage_class(usage)
        group["usages"].append(usage_payload)
        if runtime_dynamic and "runtime_dynamic_entrypoint" not in group["usage_classes"]:
            group["usage_classes"].append("runtime_dynamic_entrypoint")
        if usage_payload["usage_class"] not in group["usage_classes"]:
            group["usage_classes"].append(usage_payload["usage_class"])
    return sorted(
        groups.values(),
        key=lambda group: (
            group.get("scene_index") is None,
            group.get("scene_index") or 0,
            group.get("object_index") is None,
            group.get("object_index") or 0,
        ),
    )


def usage_class(usage: dict[str, Any]) -> str:
    kind = str(usage.get("kind") or "")
    if kind.startswith("script_"):
        return "script_driven_state"
    if kind.startswith("zone_") or kind in {"grm_fragment", "ambience_sample"}:
        return "zone_or_scene_state"
    return "direct_scene_state"


def compact_asset(asset: dict[str, Any] | None) -> dict[str, Any] | None:
    if asset is None:
        return None
    source = asset.get("source") or {}
    return {
        "id": asset.get("id"),
        "kind": asset.get("kind"),
        "label": asset.get("label"),
        "entry_type": asset.get("entry_type"),
        "source": {
            "hqr": source.get("hqr"),
            "entry_index": source.get("entry_index"),
            "classic_index": source.get("classic_index"),
        },
        "features": asset.get("features") or {},
    }


def linked_visual_assets(links: dict[str, Any]) -> list[dict[str, Any]]:
    visuals: list[dict[str, Any]] = []
    for role in ("body", "animation", "sprite"):
        link = links.get(role)
        if isinstance(link, dict) and link.get("asset_id"):
            visuals.append(
                {
                    "role": role,
                    "asset_id": link.get("asset_id"),
                    "asset_available": link.get("asset_available"),
                    "resolution_rule": link.get("resolution_rule") or link.get("index_rule"),
                }
            )
    return visuals


def script_summary(scene_object: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result = {"asset_links": [], "local_links": [], "cross_script_links": []}
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = scene_object.get(script_key) or {}
        script_kind = "track" if script_key.startswith("track") else "life"
        for key in result:
            for item in script.get(key) or []:
                result[key].append({"script_kind": script_kind, **item})
    return result


def render_backend_from_usage(usage: dict[str, Any]) -> str:
    if usage.get("kind") == "sprite" or usage.get("kind") == "script_sprite":
        backend = usage.get("backend")
        if backend == "anim3ds":
            return "ANIM3DS sprite"
        if backend == "sprites":
            return "projected sprite"
        return str(backend or "projected sprite")
    if usage.get("kind") in {"body", "script_body", "animation", "script_animation"}:
        return "body model"
    return "unknown"


def port_implications(
    runtime: dict[str, Any], scripts: dict[str, list[dict[str, Any]]]
) -> list[dict[str, str]]:
    implications: list[dict[str, str]] = []
    pipeline = runtime.get("render_pipeline") or {}
    if pipeline.get("draw_path"):
        implications.append(
            {
                "area": "render",
                "claim": str(pipeline["draw_path"]),
                "evidence": str(pipeline.get("source") or runtime.get("source") or "scene object runtime semantics"),
            }
        )
    if pipeline.get("recovery_path"):
        implications.append(
            {
                "area": "redraw",
                "claim": str(pipeline["recovery_path"]),
                "evidence": str(pipeline.get("source") or runtime.get("source") or "scene object runtime semantics"),
            }
        )
    movement = runtime.get("movement") or {}
    if movement.get("mode_name"):
        implications.append(
            {
                "area": "update",
                "claim": f"initialize and update movement mode {movement['mode_name']}",
                "evidence": "DISKFUNC.CPP LoadScene object init and OBJECT.CPP movement semantics",
            }
        )
    if scripts.get("asset_links"):
        implications.append(
            {
                "area": "script",
                "claim": "script opcodes can replace body, animation, sprite, sample, text, or video state",
                "evidence": "decoded track/life script asset links",
            }
        )
    if not implications:
        implications.append(
            {
                "area": "unknown",
                "claim": "no source-backed port implication is available for this compact entity",
                "evidence": "entity workflow builder",
            }
        )
    return implications


def build_evidence_trail(
    *,
    entrypoint: str,
    resolved_asset: dict[str, Any] | None,
    selected_usage: dict[str, Any] | None,
    entity: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    trail = [{"step": "entrypoint", "label": entrypoint}]
    if resolved_asset:
        trail.append(
            {
                "step": "resolved_asset",
                "label": resolved_asset.get("id"),
                "asset_id": resolved_asset.get("id"),
            }
        )
    if selected_usage:
        trail.append(
            {
                "step": "scene_usage",
                "label": (
                    f"Scene {selected_usage.get('scene_index')} object "
                    f"{selected_usage.get('object_index')} {selected_usage.get('kind')}"
                ),
                "usage_class": usage_class(selected_usage),
            }
        )
    if entity:
        trail.append(
            {
                "step": "entity_contract",
                "label": entity.get("entity_id"),
                "render_backend": entity.get("render_backend"),
            }
        )
    return trail


def unknowns_for(
    asset: dict[str, Any] | None,
    entity: dict[str, Any] | None,
    usages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    unknowns: list[dict[str, str]] = []
    if asset is None:
        unknowns.append({"field": "resolved_asset", "status": "unknown", "note": "No catalog asset resolved."})
    if not usages:
        unknowns.append({"field": "scene_usages", "status": "unknown", "note": "No reverse scene usage is currently known for this asset."})
    if entity is None:
        unknowns.append({"field": "selected_entity", "status": "unknown", "note": "No scene entity could be selected from the available evidence."})
    elif entity.get("unknowns"):
        unknowns.extend(entity["unknowns"])
    return unknowns


def entity_unknowns(
    scene_object: dict[str, Any] | None,
    runtime: dict[str, Any],
    scripts: dict[str, list[dict[str, Any]]],
) -> list[dict[str, str]]:
    unknowns: list[dict[str, str]] = []
    if scene_object is None:
        unknowns.append(
            {
                "field": "scene_object",
                "status": "partial",
                "note": "The object is outside the compact sampled object payload.",
            }
        )
    if not runtime.get("render_pipeline"):
        unknowns.append(
            {
                "field": "render_pipeline",
                "status": "unknown",
                "note": "Render pipeline semantics are unavailable for this entity.",
            }
        )
    if not scripts["asset_links"]:
        unknowns.append(
            {
                "field": "script_driven_links",
                "status": "evidence_absent",
                "note": "No script-driven asset links were decoded for this entity.",
            }
        )
    return unknowns
