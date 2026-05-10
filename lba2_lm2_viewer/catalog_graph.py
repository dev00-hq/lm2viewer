"""Typed in-memory graph projection for the catalog evidence model."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import viewer


CatalogNodeId = str
CatalogEdgeId = str
GRAPH_EXPORT_SCHEMA = "catalog_graph.export.v1"
GRAPH_BUILD_METADATA_SCHEMA = "catalog_graph.build_metadata.v0"
QUERY_SCHEMA_VERSION = "v0"


USAGE_EDGE_TYPES = {
    "body": "USES_AS_BODY",
    "animation": "USES_AS_ANIMATION",
    "sprite": "USES_AS_SPRITE",
    "sample": "USES_SAMPLE",
    "ambience_sample": "USES_SAMPLE",
    "text": "USES_TEXT",
    "zone_text": "USES_TEXT",
    "video": "USES_VIDEO",
    "grm_fragment": "USES_RESOURCE",
}


_KNOWN_EDGE_KEYS: set[tuple[str, str, str, str, str, str]] = set()


@dataclass
class CatalogGraph:
    nodes_by_id: dict[CatalogNodeId, dict[str, Any]] = field(default_factory=dict)
    edges_by_id: dict[CatalogEdgeId, dict[str, Any]] = field(default_factory=dict)
    outgoing_by_node_id: dict[CatalogNodeId, list[CatalogEdgeId]] = field(
        default_factory=lambda: defaultdict(list)
    )
    incoming_by_node_id: dict[CatalogNodeId, list[CatalogEdgeId]] = field(
        default_factory=lambda: defaultdict(list)
    )
    indexes: dict[str, Any] = field(default_factory=dict)
    _edge_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _known_edge_keys: set[tuple[str, str, str, str, str, str]] = field(default_factory=set)

    def add_node(self, node: dict[str, Any]) -> dict[str, Any]:
        node_id = str(node["id"])
        existing = self.nodes_by_id.get(node_id)
        if existing is not None:
            existing.update({key: value for key, value in node.items() if value is not None})
            return existing
        normalized = dict(node)
        normalized.setdefault("stableId", stable_id_from_node_id(node_id))
        normalized.setdefault("searchText", search_text(normalized))
        self.nodes_by_id[node_id] = normalized
        return normalized

    def add_edge(self, edge: dict[str, Any]) -> dict[str, Any]:
        edge_key = (
            str(edge["type"]),
            str(edge["from"]),
            str(edge["to"]),
            str(edge.get("proofScope") or "unknown"),
            str(edge.get("sourceField") or ""),
            str(edge.get("sourceRule") or ""),
        )
        if edge_key in self._known_edge_keys:
            return self.edges_by_id[
                stable_edge_id("|".join(edge_key), 1)
            ]
        self._known_edge_keys.add(edge_key)
        base = "|".join(
            [
                edge_key[0],
                edge_key[1],
                edge_key[2],
                edge_key[3],
                edge_key[4],
                edge_key[5],
            ]
        )
        self._edge_counts[base] += 1
        edge_id = stable_edge_id(base, self._edge_counts[base])
        normalized = {
            "id": edge_id,
            "relationship": edge.get("relationship") or str(edge["type"]).lower(),
            "inverse": edge.get("inverse"),
            "cardinalityFromSource": edge.get("cardinalityFromSource"),
            "cardinalityFromTarget": edge.get("cardinalityFromTarget"),
            "proofScope": edge.get("proofScope") or "unknown",
            "evidenceStatus": edge.get("evidenceStatus") or "unknown",
            "sourceRule": edge.get("sourceRule") or "unknown",
            "sourceField": edge.get("sourceField"),
            "indexRule": edge.get("indexRule"),
            "materializedFrom": edge.get("materializedFrom") or "catalog_graph_builder",
            "derivedInFrontend": bool(edge.get("derivedInFrontend", False)),
            "selectable": bool(edge.get("selectable", False)),
            "participatesInSearch": bool(edge.get("participatesInSearch", True)),
            **edge,
            "id": edge_id,
        }
        normalized.setdefault("searchText", search_text(normalized))
        self.edges_by_id[edge_id] = normalized
        self.outgoing_by_node_id[str(edge["from"])].append(edge_id)
        self.incoming_by_node_id[str(edge["to"])].append(edge_id)
        return normalized

    def sorted_nodes(self) -> list[dict[str, Any]]:
        return [self.nodes_by_id[node_id] for node_id in sorted(self.nodes_by_id)]

    def sorted_edges(self) -> list[dict[str, Any]]:
        return [self.edges_by_id[edge_id] for edge_id in sorted(self.edges_by_id)]

    def node_edges(self, node_id: str, direction: str = "both") -> list[dict[str, Any]]:
        edge_ids: list[str] = []
        if direction in {"out", "both"}:
            edge_ids.extend(self.outgoing_by_node_id.get(node_id, []))
        if direction in {"in", "both"}:
            edge_ids.extend(self.incoming_by_node_id.get(node_id, []))
        return [self.edges_by_id[edge_id] for edge_id in sorted(set(edge_ids))]


def build_catalog_graph(catalog: dict[str, Any]) -> CatalogGraph:
    graph = CatalogGraph()
    assets = [asset for asset in catalog.get("assets", []) if isinstance(asset, dict)]
    assets_by_id = {str(asset.get("id")): asset for asset in assets if asset.get("id")}
    graph.indexes = {
        "assetById": {},
        "assetsByKind": defaultdict(list),
        "assetsByArchive": defaultdict(list),
        "archiveEntryByAssetId": {},
        "resourcesBySemanticLayout": defaultdict(list),
        "file3dRecordsByIndex": {},
        "spritesByRange": defaultdict(list),
        "compatibleAnimationsByModelId": defaultdict(list),
        "compatibleModelsByAnimationId": defaultdict(list),
        "sceneUsagesByAssetId": defaultdict(list),
        "searchTextByNodeId": {},
    }

    add_archives_and_assets(graph, catalog, assets)
    add_scene_projection(graph, assets_by_id)
    add_anim3ds_ranges(graph, assets_by_id)
    add_resource_records(graph, assets_by_id)
    add_compatibility_edges(graph, assets_by_id)
    finalize_indexes(graph)
    return graph


def graph_summary(catalog: dict[str, Any] | None, graph: CatalogGraph) -> dict[str, Any]:
    summary = catalog.get("summary", {}) if isinstance(catalog, dict) else {}
    hqr_files = catalog.get("hqr_files", []) if isinstance(catalog, dict) else []
    return {
        "hqrFileCount": len(hqr_files) if isinstance(hqr_files, list) else 0,
        "assetCount": len(graph.indexes.get("assetById", {})),
        "nodeCount": len(graph.nodes_by_id),
        "edgeCount": len(graph.edges_by_id),
        "catalogSummary": summary if isinstance(summary, dict) else {},
    }


def graph_build_metadata(catalog: dict[str, Any] | None, graph: CatalogGraph, asset_root: Path | None) -> dict[str, Any]:
    return {
        "schema": GRAPH_BUILD_METADATA_SCHEMA,
        "schemaVersion": GRAPH_EXPORT_SCHEMA,
        "assetRoot": str(asset_root) if asset_root is not None else (catalog or {}).get("asset_root"),
        "builtAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "summary": graph_summary(catalog, graph),
        "warnings": [
            "Exported graph freshness is not revalidated on load; rebuild from asset root when source HQR files may have changed."
        ],
    }


def export_graph_document(
    graph: CatalogGraph,
    catalog: dict[str, Any] | None = None,
    asset_root: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": GRAPH_EXPORT_SCHEMA,
        "metadata": metadata or graph_build_metadata(catalog, graph, asset_root),
        "nodes": graph.sorted_nodes(),
        "edges": graph.sorted_edges(),
        "indexes": graph.indexes,
    }


def graph_from_export_document(document: dict[str, Any]) -> CatalogGraph:
    if document.get("schema") != GRAPH_EXPORT_SCHEMA:
        raise viewer.Lm2Error(f"unsupported catalog graph export schema: {document.get('schema')}")
    graph = CatalogGraph()
    graph.indexes = document.get("indexes") or {}
    for node in document.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            graph.nodes_by_id[str(node["id"])] = dict(node)
    for edge in document.get("edges") or []:
        if not isinstance(edge, dict) or not edge.get("id"):
            continue
        edge_id = str(edge["id"])
        graph.edges_by_id[edge_id] = dict(edge)
        graph.outgoing_by_node_id[str(edge.get("from"))].append(edge_id)
        graph.incoming_by_node_id[str(edge.get("to"))].append(edge_id)
    return graph


def load_graph_export(path: Path) -> CatalogGraph:
    return graph_from_export_document(json.loads(path.read_text(encoding="utf-8")))


def add_archives_and_assets(graph: CatalogGraph, catalog: dict[str, Any], assets: list[dict[str, Any]]) -> None:
    for summary in sorted(catalog.get("hqr_files", []) or [], key=lambda item: str(item.get("path"))):
        archive = str(summary.get("path") or summary.get("archive") or "")
        if not archive:
            continue
        archive_node_id = archive_node_id_for(archive)
        graph.add_node(
            {
                "id": archive_node_id,
                "type": "Archive",
                "label": archive,
                "stableId": archive,
                "source": summary,
                "evidenceStatus": "decoded_only",
            }
        )

    for asset in sorted(assets, key=lambda item: str(item.get("id"))):
        asset_id = str(asset["id"])
        source = asset.get("source") or {}
        archive = str(source.get("hqr") or asset.get("path") or "")
        entry_index = source.get("entry_index")
        archive_node_id = archive_node_id_for(archive)
        entry_node_id = archive_entry_node_id_for(archive, entry_index)
        if archive and archive_node_id not in graph.nodes_by_id:
            graph.add_node(
                {
                    "id": archive_node_id,
                    "type": "Archive",
                    "label": archive,
                    "stableId": archive,
                    "source": {"path": archive},
                    "evidenceStatus": "decoded_only",
                }
            )
        graph.add_node(
            {
                "id": entry_node_id,
                "type": "ArchiveEntry",
                "label": f"{archive}:{entry_index}",
                "stableId": f"{archive}:{entry_index}",
                "source": source,
                "decodedSha256": asset.get("decoded_sha256"),
                "relativePath": asset.get("relative_path"),
                "evidenceStatus": evidence_status_for_asset(asset),
            }
        )
        graph.add_node(
            {
                "id": asset_node_id_for(asset_id),
                "type": "Asset",
                "label": asset.get("label") or asset_id,
                "stableId": asset_id,
                "source": source,
                "evidenceStatus": evidence_status_for_asset(asset),
                "assetKind": asset.get("kind"),
                "entryType": asset.get("entry_type"),
                "semanticLayout": (asset.get("stats") or {}).get("semantic_layout")
                if isinstance(asset.get("stats"), dict)
                else None,
                "sceneBackgroundResolved": (
                    type(
                        ((asset.get("stats") or {}).get("reconnaissance") or {})
                        .get("background", {})
                        .get("resolved_gri_entry"),
                    )
                    is int
                    and type(
                        ((asset.get("stats") or {}).get("reconnaissance") or {})
                        .get("background", {})
                        .get("resolved_bll_entry"),
                    )
                    is int
                )
                if asset.get("kind") == "scene" and isinstance(asset.get("stats"), dict)
                else None,
                "decodedBytes": asset.get("decoded_bytes"),
                "modelBoneCount": (asset.get("stats") or {}).get("bones")
                if asset.get("kind") == "model" and isinstance(asset.get("stats"), dict)
                else None,
                "animationBoneframes": (asset.get("stats") or {}).get("boneframes")
                if asset.get("kind") == "animation" and isinstance(asset.get("stats"), dict)
                else None,
                "sourceProvenance": (asset.get("stats") or {}).get("source_provenance")
                if isinstance(asset.get("stats"), dict)
                else None,
                "runtimeReferenceStatus": (asset.get("stats") or {}).get("runtime_reference_status")
                if isinstance(asset.get("stats"), dict)
                else None,
                "decodeStatus": (asset.get("stats") or {}).get("decode_status")
                if isinstance(asset.get("stats"), dict)
                else None,
                "decodeNote": (asset.get("stats") or {}).get("decode_note")
                if isinstance(asset.get("stats"), dict)
                else None,
                "unknownDescriptors": (asset.get("stats") or {}).get("unknown_descriptors")
                if isinstance(asset.get("stats"), dict)
                else None,
            }
        )
        graph.add_edge(
            {
                "type": "HAS_ENTRY",
                "from": archive_node_id,
                "to": entry_node_id,
                "relationship": "has entry",
                "inverse": "entry of archive",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "1",
                "proofScope": "decoded_payload",
                "evidenceStatus": "decoded_only",
                "sourceRule": "build_catalog HQR table scan",
                "sourceField": "hqr_files[].path + CatalogAsset.source.entry_index",
                "indexRule": index_rule_for_asset(asset),
                "selectable": False,
            }
        )
        graph.add_edge(
            {
                "type": "DECODED_AS",
                "from": entry_node_id,
                "to": asset_node_id_for(asset_id),
                "relationship": "decoded as asset",
                "inverse": "decoded from entry",
                "cardinalityFromSource": "0..1",
                "cardinalityFromTarget": "1",
                "proofScope": "decoded_payload",
                "evidenceStatus": evidence_status_for_asset(asset),
                "sourceRule": "CatalogAsset created from decoded HQR entry",
                "sourceField": "Catalog.assets[]",
                "indexRule": index_rule_for_asset(asset),
                "selectable": True,
            }
        )


def add_scene_projection(graph: CatalogGraph, assets_by_id: dict[str, dict[str, Any]]) -> None:
    for asset in sorted(assets_by_id.values(), key=lambda item: str(item.get("id"))):
        if asset.get("kind") != "scene":
            continue
        scene_id = str(asset.get("id"))
        scene_node_id = scene_node_id_for(scene_id)
        graph.add_node(
            {
                "id": scene_node_id,
                "type": "Scene",
                "label": asset.get("label") or scene_id,
                "stableId": scene_id,
                "source": asset.get("source"),
                "evidenceStatus": evidence_status_for_asset(asset),
            }
        )
        graph.add_edge(
            {
                "type": "DECODED_AS",
                "from": asset_node_id_for(scene_id),
                "to": scene_node_id,
                "relationship": "decoded as scene",
                "inverse": "scene asset",
                "cardinalityFromSource": "0..1",
                "cardinalityFromTarget": "1",
                "proofScope": "decoded_payload",
                "evidenceStatus": evidence_status_for_asset(asset),
                "sourceRule": "SceneStats semantic_layout scene_runtime_layout_partial",
                "sourceField": "CatalogAsset.stats.reconnaissance",
                "indexRule": "SCENE.HQR catalog entry index is classic scene index + 1.",
                "selectable": True,
            }
        )
        for scene_object in iter_scene_objects(asset):
            object_node_id = scene_object_node_id_for(scene_id, scene_object.get("index"))
            graph.add_node(scene_object_node(asset, scene_object))
            graph.add_edge(
                {
                    "type": "HAS_SCENE_OBJECT",
                    "from": scene_node_id,
                    "to": object_node_id,
                    "relationship": "has scene object",
                    "inverse": "object of scene",
                    "cardinalityFromSource": "0..n",
                    "cardinalityFromTarget": "1",
                    "proofScope": "decoded_payload",
                    "evidenceStatus": "decoded_only",
                    "sourceRule": "scene_catalog_stats sampled scene object records",
                    "sourceField": "SceneStats.reconnaissance.sampled_objects",
                    "indexRule": "Scene object index is zero-based runtime object index.",
                    "selectable": True,
                }
            )
            links = scene_object.get("links") or {}
            for link_kind in ("body", "animation", "sprite"):
                link = links.get(link_kind)
                if isinstance(link, dict):
                    add_scene_usage_edge(graph, asset, scene_object, link_kind, link, "scene_object_state")
            add_scene_script_reference_edges(graph, asset, scene_object)


def add_scene_usage_edge(
    graph: CatalogGraph,
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    link_kind: str,
    link: dict[str, Any],
    proof_scope: str,
) -> None:
    target_asset_id = (
        link.get("asset_id")
        or link.get("target_asset_id")
        or missing_target_stable_id_for_link(link_kind, link)
    )
    if not target_asset_id:
        return
    scene_id = str(scene_asset.get("id"))
    object_node_id = scene_object_node_id_for(scene_id, scene_object.get("index"))
    target_node_id = asset_node_id_for(str(target_asset_id))
    if link.get("asset_available") is False:
        target_node_id = missing_node_id_for(str(target_asset_id))
        graph.add_node(
            {
                "id": target_node_id,
                "type": "MissingTarget",
                "label": f"Missing {target_asset_id}",
                "stableId": str(target_asset_id),
                "source": {"asset_id": target_asset_id, "link": link},
                "evidenceStatus": "unknown",
            }
        )
    file3d_node_id = add_file3d_record_if_present(graph, scene_asset, scene_object, link)
    edge_type = USAGE_EDGE_TYPES.get(link_kind, "USES_RESOURCE")
    if link.get("script_kind"):
        reference_node_id = script_reference_node_id_for(scene_id, scene_object.get("index"), link)
        graph.add_node(
            {
                "id": reference_node_id,
                "type": "ScriptReference",
                "label": f"{scene_id} object {scene_object.get('index')} {link.get('script_kind')} {link.get('reference_key')}",
                "stableId": stable_id_from_node_id(reference_node_id),
                "source": {
                    "scene_asset_id": scene_id,
                    "object_index": scene_object.get("index"),
                    "script_kind": link.get("script_kind"),
                    "reference_key": link.get("reference_key"),
                    "reference_value": link.get("reference_value"),
                },
                "evidenceStatus": "source_backed",
            }
        )
        graph.add_edge(
            {
                "type": "CONTAINS",
                "from": object_node_id,
                "to": reference_node_id,
                "relationship": "has script reference",
                "inverse": "script reference of scene object",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "1",
                "proofScope": "script_reference",
                "evidenceStatus": "source_backed",
                "sourceRule": link.get("resolution_rule") or "scene script asset_links",
                "sourceField": "track_script_analysis.asset_links/life_script_analysis.asset_links",
                "indexRule": link.get("index_rule"),
                "selectable": True,
            }
        )
        graph.add_edge(
            {
                "type": "SCRIPT_REFERENCES",
                "from": reference_node_id,
                "to": target_node_id,
                "relationship": f"script references {link_kind}",
                "inverse": "referenced by script",
                "cardinalityFromSource": "0..1",
                "cardinalityFromTarget": "0..n",
                "proofScope": "script_reference",
                "evidenceStatus": "source_backed" if link.get("asset_available", True) else "unknown",
                "sourceRule": link.get("resolution_rule") or "script reference resolved to catalog asset",
                "sourceField": link.get("reference_key") or "asset_links[].asset_id",
                "indexRule": link.get("index_rule"),
                "selectable": True,
                "usageKind": link_kind,
            }
        )
        return
    graph.add_edge(
        {
            "type": edge_type,
            "from": object_node_id,
            "to": target_node_id,
            "relationship": f"uses {link_kind}",
            "inverse": f"used as {link_kind}",
            "cardinalityFromSource": "0..1" if link_kind in {"body", "animation", "sprite"} else "0..n",
            "cardinalityFromTarget": "0..n",
            "proofScope": proof_scope,
            "evidenceStatus": "unknown"
            if link.get("asset_available") is False
            else "source_backed" if link.get("resolution_rule") or link.get("index_rule") else "decoded_only",
            "sourceRule": link.get("resolution_rule") or link.get("index_rule") or "scene usage reverse link",
            "sourceField": source_field_for_usage(link_kind, link),
            "indexRule": link.get("index_rule") or index_rule_for_usage(link_kind, link),
            "selectable": True,
            "usageKind": link_kind,
        }
    )
    if file3d_node_id and link_kind in {"body", "animation"}:
        graph.add_edge(
            {
                "type": "RESOLVES_TO",
                "from": file3d_node_id,
                "to": target_node_id,
                "relationship": f"resolves generic {link_kind} slot",
                "inverse": f"resolved from File3D {link_kind} slot",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "0..n",
                "proofScope": "classic_source_rule",
                "evidenceStatus": "source_backed" if link.get("asset_available", True) else "unknown",
                "sourceRule": link.get("resolution_rule") or "File3D generic slot resolves to HQR asset id",
                "sourceField": "file3d_index + gen_body/gen_anim",
                "indexRule": index_rule_for_usage(link_kind, link),
                "selectable": True,
            }
        )


def add_scene_script_reference_edges(
    graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any]
) -> None:
    for script_key in ("track_script_analysis", "life_script_analysis"):
        script = scene_object.get(script_key) or {}
        script_kind = "track" if script_key.startswith("track_") else "life"
        for link in script.get("asset_links") or []:
            if not isinstance(link, dict):
                continue
            add_scene_usage_edge(
                graph,
                scene_asset,
                scene_object,
                str(link.get("kind") or "resource"),
                {**link, "script_kind": script_kind},
                "script_reference",
            )
        for missing_link in script.get("missing_sample_links") or []:
            if not isinstance(missing_link, dict):
                continue
            add_scene_usage_edge(
                graph,
                scene_asset,
                scene_object,
                "sample",
                {
                    **missing_link,
                    "kind": "sample",
                    "asset_available": False,
                    "script_kind": script_kind,
                    "resolution_rule": missing_link.get("reason") or missing_link.get("status"),
                    "index_rule": "Runtime sample id maps to SAMPLES.HQR table slot sample id + 1.",
                },
                "script_reference",
            )


def add_file3d_record_if_present(
    graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any], link: dict[str, Any]
) -> str | None:
    file3d_index = scene_object.get("file3d_index")
    if not isinstance(file3d_index, int) or file3d_index < 0:
        return None
    node_id = file3d_record_node_id_for(file3d_index)
    graph.add_node(
        {
            "id": node_id,
            "type": "File3DRecord",
            "label": f"File3D record {file3d_index}",
            "stableId": f"RESS.HQR:44#file3d:{file3d_index}",
            "source": {
                "file3d_index": file3d_index,
                "scene_asset_id": scene_asset.get("id"),
                "object_index": scene_object.get("index"),
                "gen_body": scene_object.get("gen_body"),
                "gen_anim": scene_object.get("gen_anim"),
                "resolution_rule": link.get("resolution_rule"),
            },
            "evidenceStatus": "source_backed" if link.get("resolution_rule") else "decoded_only",
        }
    )
    graph.add_edge(
        {
            "type": "HAS_FILE3D_RECORD",
            "from": scene_object_node_id_for(str(scene_asset.get("id")), scene_object.get("index")),
            "to": node_id,
            "relationship": "uses File3D record",
            "inverse": "File3D record used by scene object",
            "cardinalityFromSource": "0..1",
            "cardinalityFromTarget": "0..n",
            "proofScope": "scene_object_state",
            "evidenceStatus": "source_backed" if link.get("resolution_rule") else "decoded_only",
            "sourceRule": "Scene object IndexFile3D selects a resolver record from RESS.HQR:44",
            "sourceField": "SceneObject.file3d_index",
            "indexRule": "File3D record index is zero-based RESS.HQR:44 resolver table index.",
            "selectable": True,
        }
    )
    return node_id


def add_anim3ds_ranges(graph: CatalogGraph, assets_by_id: dict[str, dict[str, Any]]) -> None:
    info_asset = assets_by_id.get("ANIM3DS.HQR:127")
    if not info_asset:
        return
    stats = info_asset.get("stats") or {}
    if stats.get("semantic_layout") != "anim3ds_frame_ranges":
        return
    for entry in stats.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        range_node_id = sprite_range_node_id_for(entry.get("index"))
        graph.add_node(
            {
                "id": range_node_id,
                "type": "SpriteRange",
                "label": f"ANIM3DS range {entry.get('name')} ({entry.get('start_frame')}-{entry.get('end_frame')})",
                "stableId": f"ANIM3DS:{entry.get('index')}",
                "source": entry,
                "evidenceStatus": "source_backed" if stats.get("source_provenance") else "decoded_only",
            }
        )
        graph.add_edge(
            {
                "type": "CONTAINS",
                "from": asset_node_id_for("ANIM3DS.HQR:127"),
                "to": range_node_id,
                "relationship": "defines sprite range",
                "inverse": "range defined by metadata asset",
                "cardinalityFromSource": "1..n",
                "cardinalityFromTarget": "1",
                "proofScope": "classic_source_rule" if stats.get("source_provenance") else "decoded_payload",
                "evidenceStatus": "source_backed" if stats.get("source_provenance") else "decoded_only",
                "sourceRule": stats.get("source_provenance") or "ANIM3DS info entry decoded range table",
                "sourceField": "Anim3dsInfoStats.entries[]",
                "indexRule": "ANIM3DS.HQR:127 stores range metadata; range frames use zero-based ANIM3DS.HQR entries.",
                "selectable": True,
            }
        )
        start = entry.get("start_frame")
        end = entry.get("end_frame")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        for frame in range(start, end + 1):
            frame_asset_id = f"ANIM3DS.HQR:{frame}"
            frame_node_id = asset_node_id_for(frame_asset_id)
            if frame_asset_id not in assets_by_id:
                frame_node_id = missing_node_id_for(frame_asset_id)
                graph.add_node(
                    {
                        "id": frame_node_id,
                        "type": "MissingTarget",
                        "label": f"Missing {frame_asset_id}",
                        "stableId": frame_asset_id,
                        "source": {"asset_id": frame_asset_id},
                        "evidenceStatus": "unknown",
                    }
                )
            graph.add_edge(
                {
                    "type": "RANGE_CONTAINS_FRAME",
                    "from": range_node_id,
                    "to": frame_node_id,
                    "relationship": "contains frame",
                    "inverse": "frame of range",
                    "cardinalityFromSource": "1..n",
                    "cardinalityFromTarget": "0..n",
                    "proofScope": "decoded_payload",
                    "evidenceStatus": "decoded_only" if frame_asset_id in assets_by_id else "unknown",
                    "sourceRule": "ANIM3DS range start/end frame bounds",
                    "sourceField": "Anim3dsInfoStats.entries[].start_frame/end_frame",
                    "indexRule": "Frame id is ANIM3DS.HQR zero-based entry index.",
                    "selectable": True,
                }
            )


def add_resource_records(graph: CatalogGraph, assets_by_id: dict[str, dict[str, Any]]) -> None:
    for asset in sorted(assets_by_id.values(), key=lambda item: str(item.get("id"))):
        if asset.get("kind") != "resource":
            continue
        stats = asset.get("stats") or {}
        layout = stats.get("semantic_layout")
        asset_id = str(asset.get("id"))
        for record in stats.get("sampled_records") or []:
            if not isinstance(record, dict):
                continue
            record_index = record.get("index")
            record_node_id = resource_record_node_id_for(asset_id, record_index)
            graph.add_node(
                {
                    "id": record_node_id,
                    "type": "ResourceRecord",
                    "label": f"{asset_id} record {record_index}",
                    "stableId": f"{asset_id}#record:{record_index}",
                    "source": record,
                    "evidenceStatus": evidence_status_for_asset(asset),
                    "semanticLayout": layout,
                }
            )
            graph.add_edge(
                {
                    "type": "RESOURCE_RECORD_OF",
                    "from": asset_node_id_for(asset_id),
                    "to": record_node_id,
                    "relationship": "has resource record",
                    "inverse": "record of resource",
                    "cardinalityFromSource": "0..n",
                    "cardinalityFromTarget": "1",
                    "proofScope": "decoded_payload",
                    "evidenceStatus": evidence_status_for_asset(asset),
                    "sourceRule": f"decoded resource semantic layout {layout}",
                    "sourceField": "ResourceStats.sampled_records[]",
                    "indexRule": "Record index is payload-local unless source field gives an HQR entry.",
                    "selectable": True,
                }
            )
        for link in stats.get("text_links") or []:
            if not isinstance(link, dict):
                continue
            record_node_id = resource_record_node_id_for(asset_id, f"text:{link.get('message_id')}")
            graph.add_node(
                {
                    "id": record_node_id,
                    "type": "ResourceRecord",
                    "label": f"{asset_id} text message {link.get('message_id')}",
                    "stableId": f"{asset_id}#text:{link.get('message_id')}",
                    "source": link,
                    "evidenceStatus": "source_backed",
                    "semanticLayout": layout,
                }
            )
            graph.add_edge(
                {
                    "type": "RESOURCE_RECORD_OF",
                    "from": asset_node_id_for(asset_id),
                    "to": record_node_id,
                    "relationship": "has linked text record",
                    "inverse": "text record of resource",
                    "cardinalityFromSource": "0..n",
                    "cardinalityFromTarget": "1",
                    "proofScope": "decoded_payload",
                    "evidenceStatus": "source_backed",
                    "sourceRule": "holomap/text resource link enrichment",
                    "sourceField": "ResourceStats.text_links[]",
                    "indexRule": "Text message id is logical message id; localized payload identity is text_file_index + record_index.",
                    "selectable": True,
                }
            )


def add_compatibility_edges(graph: CatalogGraph, assets_by_id: dict[str, dict[str, Any]]) -> None:
    models_by_bones: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for asset in assets_by_id.values():
        if asset.get("kind") == "model":
            bones = (asset.get("stats") or {}).get("bones")
            if isinstance(bones, int):
                models_by_bones[bones].append(asset)

    for animation in sorted(assets_by_id.values(), key=lambda item: str(item.get("id"))):
        if animation.get("kind") != "animation" or animation.get("entry_type") != "animation":
            continue
        boneframes = (animation.get("stats") or {}).get("boneframes")
        if not isinstance(boneframes, int):
            continue
        compatible_ids = (animation.get("animation_metadata") or {}).get("compatible_body_ids") or []
        if compatible_ids:
            for body_index in sorted({int(value) for value in compatible_ids if isinstance(value, int)}):
                model = assets_by_id.get(f"BODY.HQR:{body_index}")
                if model is None:
                    continue
                if (model.get("stats") or {}).get("bones") != boneframes:
                    continue
                add_compatibility_edge(graph, animation, model, "file3d_allowlist")
            continue
        for model in sorted(models_by_bones.get(boneframes, []), key=lambda item: str(item.get("id"))):
            add_compatibility_edge(graph, animation, model, "bone_count_only")


def add_compatibility_edge(
    graph: CatalogGraph, animation: dict[str, Any], model: dict[str, Any], reason: str
) -> None:
    source_rule = (
        "File3D animation metadata compatible_body_ids allow-list"
        if reason == "file3d_allowlist"
        else "Decoded animation boneframes equals decoded model bones; no File3D allow-list metadata present"
    )
    graph.add_edge(
        {
            "type": "COMPATIBLE_WITH",
            "from": asset_node_id_for(str(animation.get("id"))),
            "to": asset_node_id_for(str(model.get("id"))),
            "relationship": "animation compatible with model",
            "inverse": "model accepts animation",
            "cardinalityFromSource": "0..n",
            "cardinalityFromTarget": "0..n",
            "proofScope": "frontend_compatibility_rule" if reason == "bone_count_only" else "classic_source_rule",
            "evidenceStatus": "decoded_only" if reason == "bone_count_only" else "source_backed",
            "sourceRule": source_rule,
            "sourceField": "animation_metadata.compatible_body_ids" if reason == "file3d_allowlist" else "AnimationStats.boneframes + ModelStats.bones",
            "indexRule": "BODY.HQR ids use catalog entry index; File3D body records store body_index + 1 as catalog id.",
            "selectable": True,
            "compatibilityReason": reason,
        }
    )


def finalize_indexes(graph: CatalogGraph) -> None:
    indexes = graph.indexes
    for node_id, node in graph.nodes_by_id.items():
        indexes["searchTextByNodeId"][node_id] = node.get("searchText") or search_text(node)
        if node.get("type") == "Asset":
            stable_id = str(node.get("stableId"))
            indexes["assetById"][stable_id] = node_id
            if node.get("assetKind"):
                indexes["assetsByKind"][node.get("assetKind")].append(stable_id)
            source = node.get("source") or {}
            if source.get("hqr"):
                indexes["assetsByArchive"][source.get("hqr")].append(stable_id)
                indexes["archiveEntryByAssetId"][stable_id] = archive_entry_node_id_for(
                    str(source.get("hqr")), source.get("entry_index")
                )
            stats_layout = node.get("semanticLayout")
            if stats_layout:
                indexes["resourcesBySemanticLayout"][stats_layout].append(stable_id)
    for edge in graph.edges_by_id.values():
        if edge.get("type") == "COMPATIBLE_WITH":
            animation_id = stable_id_from_node_id(str(edge.get("from")))
            model_id = stable_id_from_node_id(str(edge.get("to")))
            indexes["compatibleAnimationsByModelId"][model_id].append(animation_id)
            indexes["compatibleModelsByAnimationId"][animation_id].append(model_id)
        if edge.get("type") in set(USAGE_EDGE_TYPES.values()) | {"SCRIPT_REFERENCES"}:
            target_id = stable_id_from_node_id(str(edge.get("to")))
            indexes["sceneUsagesByAssetId"][target_id].append(edge["id"])
        if edge.get("type") == "RANGE_CONTAINS_FRAME":
            range_id = stable_id_from_node_id(str(edge.get("from")))
            indexes["spritesByRange"][range_id].append(stable_id_from_node_id(str(edge.get("to"))))
    for key, value in list(indexes.items()):
        if isinstance(value, defaultdict):
            indexes[key] = {inner_key: sorted(set(inner_value)) for inner_key, inner_value in sorted(value.items())}
        elif isinstance(value, dict):
            indexes[key] = {
                inner_key: sorted(set(inner_value)) if isinstance(inner_value, list) else inner_value
                for inner_key, inner_value in sorted(value.items())
            }


def query_explain(graph: CatalogGraph, stable_id: str) -> dict[str, Any]:
    node_id = resolve_node_id(graph, stable_id)
    node = graph.nodes_by_id.get(node_id)
    if node is None:
        return {"schema": "catalog_graph.explain.v0", "id": stable_id, "found": False}
    return {
        "schema": "catalog_graph.explain.v0",
        "id": stable_id,
        "node": node,
        "incoming": graph.node_edges(node_id, "in"),
        "outgoing": graph.node_edges(node_id, "out"),
        "consumerRoundTrip": consumer_round_trip_for_node(graph, node_id),
    }


def query_edges(
    graph: CatalogGraph,
    stable_id: str,
    direction: str,
    proof_scope: str | None = None,
    evidence_status: str | None = None,
) -> dict[str, Any]:
    normalized_direction = normalize_direction(direction)
    node_id = resolve_node_id(graph, stable_id)
    edges = filter_edges(graph.node_edges(node_id, normalized_direction), proof_scope, evidence_status)
    return {
        "schema": "catalog_graph.edges.v0",
        "id": stable_id,
        "direction": normalized_direction,
        "filters": {"proofScope": proof_scope, "evidenceStatus": evidence_status},
        "node": graph.nodes_by_id.get(node_id),
        "edges": edges,
    }


def query_usages(
    graph: CatalogGraph,
    stable_id: str,
    proof_scope: str | None = None,
    evidence_status: str | None = None,
) -> dict[str, Any]:
    edge_ids = graph.indexes.get("sceneUsagesByAssetId", {}).get(stable_id, [])
    edges = [graph.edges_by_id[edge_id] for edge_id in edge_ids if edge_id in graph.edges_by_id]
    return {
        "schema": "catalog_graph.usages.v0",
        "id": stable_id,
        "filters": {"proofScope": proof_scope, "evidenceStatus": evidence_status},
        "edges": sorted(filter_edges(edges, proof_scope, evidence_status), key=lambda edge: edge["id"]),
    }


def query_asset_usage_records(graph: CatalogGraph, stable_id: str) -> dict[str, Any]:
    edge_ids = graph.indexes.get("sceneUsagesByAssetId", {}).get(stable_id, [])
    records = [
        usage_record_from_edge(graph, graph.edges_by_id[edge_id])
        for edge_id in edge_ids
        if edge_id in graph.edges_by_id
    ]
    return {
        "schema": "catalog_graph.asset_usage_records.v0",
        "id": stable_id,
        "usageRecords": sorted(
            [record for record in records if record is not None],
            key=lambda record: (
                record.get("scene_index") is None,
                record.get("scene_index") or 0,
                record.get("object_index") is None,
                record.get("object_index") or 0,
                record.get("kind") or "",
                record.get("target_asset_id") or "",
            ),
        ),
    }


def query_export_context(graph: CatalogGraph, stable_id: str, proof_scope: str) -> dict[str, Any]:
    usage_records = query_asset_usage_records(graph, stable_id)["usageRecords"]
    direct_records = [record for record in usage_records if record.get("proofScope") == "scene_object_state"]
    script_records = [record for record in usage_records if record.get("proofScope") == "script_reference"]
    scene_indices = sorted(
        {
            record["scene_index"]
            for record in usage_records
            if isinstance(record.get("scene_index"), int)
        }
    )
    evidence_statuses = sorted(
        {
            str(record.get("evidenceStatus"))
            for record in usage_records
            if record.get("evidenceStatus")
        }
    )
    source_rules = sorted(
        {
            str(record.get("sourceRule"))
            for record in usage_records
            if record.get("sourceRule")
        }
    )
    source_fields = sorted(
        {
            str(record.get("sourceField"))
            for record in usage_records
            if record.get("sourceField")
        }
    )
    index_rules = sorted(
        {
            str(record.get("indexRule"))
            for record in usage_records
            if record.get("indexRule")
        }
    )
    return {
        "schema": "catalog_graph.export_context.v0",
        "stable_id": stable_id,
        "proof_scope": proof_scope,
        "scene_usage_count": len(direct_records),
        "relationship_link_count": len(usage_records),
        "direct_scene_object_usage_count": len(direct_records),
        "script_reference_count": len(script_records),
        "scene_indices": scene_indices,
        "proof_scopes": sorted({str(record.get("proofScope")) for record in usage_records if record.get("proofScope")}),
        "evidence_statuses": evidence_statuses,
        "source_rules": source_rules,
        "source_fields": source_fields,
        "index_rules": index_rules,
        "usage_records": usage_records,
    }


def usage_record_from_edge(graph: CatalogGraph, edge: dict[str, Any]) -> dict[str, Any] | None:
    proof_scope = edge.get("proofScope")
    if proof_scope == "script_reference":
        reference_node = graph.nodes_by_id.get(str(edge.get("from")), {})
        source = reference_node.get("source") if isinstance(reference_node.get("source"), dict) else {}
        scene_id = source.get("scene_asset_id")
        object_index = source.get("object_index")
        scene_object = graph.nodes_by_id.get(scene_object_node_id_for(str(scene_id), object_index), {})
        usage_kind = edge.get("usageKind") or edge.get("type")
        kind = f"script_{usage_kind}" if usage_kind else "script_reference"
    else:
        scene_object = graph.nodes_by_id.get(str(edge.get("from")), {})
        source = scene_object.get("source") if isinstance(scene_object.get("source"), dict) else {}
        scene_id = source.get("scene_asset_id")
        object_index = source.get("object_index")
        kind = edge.get("usageKind") or edge.get("type")
    if not scene_id:
        return None
    scene_node = graph.nodes_by_id.get(scene_node_id_for(str(scene_id)), {})
    scene_source = scene_node.get("source") if isinstance(scene_node.get("source"), dict) else {}
    scene_entry_index = source.get("scene_entry_index") or scene_source.get("entry_index")
    scene_index = scene_entry_index - 1 if isinstance(scene_entry_index, int) else None
    target = relationship_endpoint_projection(graph, str(edge.get("to")))
    object_source = scene_object.get("source") if isinstance(scene_object.get("source"), dict) else {}
    return {
        "kind": kind,
        "scene_asset_id": scene_id,
        "scene_label": scene_node.get("label") or scene_id,
        "scene_entry_index": scene_entry_index,
        "scene_index": scene_index,
        "object_index": object_index,
        "position": object_source.get("position"),
        "file3d_index": object_source.get("file3d_index"),
        "gen_body": object_source.get("gen_body"),
        "gen_anim": object_source.get("gen_anim"),
        "sprite": object_source.get("sprite"),
        "flags": object_source.get("flags"),
        "target_asset_id": target.get("stableId"),
        "target_label": target.get("label"),
        "target_type": target.get("type"),
        "target_available": target.get("type") != "MissingTarget",
        "resolution_rule": edge.get("sourceRule"),
        "proofScope": edge.get("proofScope"),
        "evidenceStatus": edge.get("evidenceStatus"),
        "sourceRule": edge.get("sourceRule"),
        "sourceField": edge.get("sourceField"),
        "indexRule": edge.get("indexRule"),
    }


def query_scene_object(graph: CatalogGraph, scene_id: str, object_index: str) -> dict[str, Any]:
    node_id = scene_object_node_id_for(scene_id, parse_object_index(object_index))
    return {
        "schema": "catalog_graph.scene_object.v0",
        "sceneId": scene_id,
        "objectIndex": parse_object_index(object_index),
        "node": graph.nodes_by_id.get(node_id),
        "edges": graph.node_edges(node_id, "both"),
        "consumerRoundTrip": consumer_round_trip_for_node(graph, node_id),
    }


def query_compatible(graph: CatalogGraph, model_id: str) -> dict[str, Any]:
    animations = graph.indexes.get("compatibleAnimationsByModelId", {}).get(model_id, [])
    return {
        "schema": "catalog_graph.compatible.v0",
        "modelId": model_id,
        "compatibleAnimationIds": animations,
        "edges": [
            graph.edges_by_id[edge_id]
            for edge_id in graph.incoming_by_node_id.get(asset_node_id_for(model_id), [])
            if graph.edges_by_id[edge_id].get("type") == "COMPATIBLE_WITH"
        ],
    }


def query_prove(graph: CatalogGraph, model_id: str, animation_id: str) -> dict[str, Any]:
    model_node_id = asset_node_id_for(model_id)
    animation_node_id = asset_node_id_for(animation_id)
    edges = [
        graph.edges_by_id[edge_id]
        for edge_id in graph.outgoing_by_node_id.get(animation_node_id, [])
        if graph.edges_by_id[edge_id].get("type") == "COMPATIBLE_WITH"
        and graph.edges_by_id[edge_id].get("to") == model_node_id
    ]
    return {
        "schema": "catalog_graph.prove.v0",
        "modelId": model_id,
        "animationId": animation_id,
        "compatible": bool(edges),
        "proofs": sorted(edges, key=lambda edge: edge["id"]),
        "negativeEvidence": [] if edges else ["No compatible edge exists in the current graph projection."],
    }


def query_animation_operation_compatibility(
    graph: CatalogGraph,
    model_id: str,
    animation_id: str,
    operation: str = "pose_playback",
) -> dict[str, Any]:
    model_node_id = asset_node_id_for(model_id)
    animation_node_id = asset_node_id_for(animation_id)
    model_node = graph.nodes_by_id.get(model_node_id)
    animation_node = graph.nodes_by_id.get(animation_node_id)
    proof = query_prove(graph, model_id, animation_id)

    error: str | None = None
    negative_evidence: list[str] = []
    if model_node is None:
        error = f"catalog asset is not in the graph: {model_id}"
    elif model_node.get("assetKind") != "model":
        error = f"catalog asset is not a model: {model_id}"
    elif animation_node is None:
        error = f"catalog asset is not in the graph: {animation_id}"
    elif animation_node.get("assetKind") != "animation" or animation_node.get("entryType") != "animation":
        error = f"catalog asset is not a decoded animation: {animation_id}"
    elif proof["compatible"]:
        error = None
    else:
        error = animation_operation_negative_reason(graph, model_node, animation_node)
        negative_evidence.append(error)

    eligible = error is None and bool(proof["compatible"])
    return {
        "schema": "catalog_graph.animation_operation_compatibility.v0",
        "operation": operation,
        "modelId": model_id,
        "animationId": animation_id,
        "eligible": eligible,
        "compatible": bool(proof["compatible"]),
        "relationship": "COMPATIBLE_WITH",
        "proofs": proof["proofs"],
        "negativeEvidence": negative_evidence if negative_evidence else proof["negativeEvidence"],
        "error": None if eligible else error,
    }


def animation_operation_negative_reason(
    graph: CatalogGraph,
    model_node: dict[str, Any],
    animation_node: dict[str, Any],
) -> str:
    model_bones = model_node.get("modelBoneCount")
    animation_boneframes = animation_node.get("animationBoneframes")
    if model_bones != animation_boneframes:
        return (
            f"animation bone count {animation_boneframes} does not match "
            f"model bone count {model_bones}"
        )

    allow_list = file3d_allow_list_for_animation(graph, str(animation_node["id"]))
    model_id = str(model_node.get("stableId") or stable_id_from_node_id(str(model_node["id"])))
    if allow_list:
        return (
            f"animation {animation_node.get('stableId')} is linked to BODY.HQR entries "
            f"{allow_list}, not {model_id}"
        )
    return "No compatible edge exists in the current graph projection."


def file3d_allow_list_for_animation(graph: CatalogGraph, animation_node_id: str) -> list[int]:
    body_ids: list[int] = []
    for edge_id in graph.outgoing_by_node_id.get(animation_node_id, []):
        edge = graph.edges_by_id[edge_id]
        if (
            edge.get("type") != "COMPATIBLE_WITH"
            or edge.get("compatibilityReason") != "file3d_allowlist"
        ):
            continue
        stable_id = stable_id_from_node_id(str(edge.get("to")))
        if not stable_id.startswith("BODY.HQR:"):
            continue
        try:
            body_ids.append(int(stable_id.split(":", 1)[1]))
        except ValueError:
            continue
    return sorted(set(body_ids))


def catalog_selection_projection(graph: CatalogGraph) -> dict[str, dict[str, Any]]:
    selections: dict[str, dict[str, Any]] = {}
    for node in graph.sorted_nodes():
        if node.get("type") != "Asset":
            continue
        stable_id = str(node.get("stableId"))
        selections[stable_id] = asset_selection_projection(graph, node)
    return selections


def catalog_scene_object_relationship_projection(graph: CatalogGraph) -> dict[str, dict[str, Any]]:
    relationships: dict[str, dict[str, Any]] = {}
    for node in graph.sorted_nodes():
        if node.get("type") != "SceneObject":
            continue
        stable_id = str(node.get("stableId"))
        relationships[stable_id] = scene_object_relationship_projection(graph, node)
    return relationships


def scene_object_relationship_projection(graph: CatalogGraph, node: dict[str, Any]) -> dict[str, Any]:
    node_id = str(node.get("id"))
    edges = [scene_object_relationship_edge_projection(graph, node_id, edge) for edge in graph.node_edges(node_id, "both")]
    return {
        "schema": "catalog_graph.scene_object_relationship_projection.v0",
        "kind": "scene_object_relationships",
        "nodeId": node_id,
        "stableId": node.get("stableId") or stable_id_from_node_id(node_id),
        "label": node.get("label") or node_id,
        "source": node.get("source") or {},
        "evidenceStatus": node.get("evidenceStatus") or "unknown",
        "edges": edges,
        "visualLinks": scene_object_visual_links_from_edges(edges),
    }


def scene_object_relationship_edge_projection(
    graph: CatalogGraph, owner_node_id: str, edge: dict[str, Any]
) -> dict[str, Any]:
    from_node_id = str(edge.get("from"))
    to_node_id = str(edge.get("to"))
    direction = "out" if from_node_id == owner_node_id else "in" if to_node_id == owner_node_id else "incident"
    return {
        "id": edge.get("id"),
        "type": edge.get("type"),
        "relationship": edge.get("relationship"),
        "direction": direction,
        "from": relationship_endpoint_projection(graph, from_node_id),
        "to": relationship_endpoint_projection(graph, to_node_id),
        "proofScope": edge.get("proofScope"),
        "evidenceStatus": edge.get("evidenceStatus"),
        "sourceRule": edge.get("sourceRule"),
        "sourceField": edge.get("sourceField"),
        "indexRule": edge.get("indexRule"),
        "usageKind": edge.get("usageKind"),
    }


def relationship_endpoint_projection(graph: CatalogGraph, node_id: str) -> dict[str, Any]:
    node = graph.nodes_by_id.get(node_id, {})
    return {
        "nodeId": node_id,
        "type": node.get("type") or "Unknown",
        "stableId": node.get("stableId") or stable_id_from_node_id(node_id),
        "label": node.get("label") or stable_id_from_node_id(node_id),
        "evidenceStatus": node.get("evidenceStatus") or "unknown",
    }


def scene_object_visual_links_from_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roles = {
        "HAS_FILE3D_RECORD": "file3d",
        "USES_AS_BODY": "body",
        "USES_AS_ANIMATION": "animation",
        "USES_AS_SPRITE": "sprite",
    }
    links: list[dict[str, Any]] = []
    for edge in edges:
        role = roles.get(str(edge.get("type")))
        if not role or edge.get("direction") != "out":
            continue
        target = edge.get("to") if isinstance(edge.get("to"), dict) else {}
        links.append(
            {
                "role": role,
                "stableId": target.get("stableId"),
                "label": target.get("label") or target.get("stableId"),
                "targetType": target.get("type"),
                "targetAvailable": target.get("type") != "MissingTarget",
                "proofScope": edge.get("proofScope"),
                "evidenceStatus": edge.get("evidenceStatus"),
                "sourceRule": edge.get("sourceRule"),
                "sourceField": edge.get("sourceField"),
                "indexRule": edge.get("indexRule"),
            }
        )
    role_order = {"file3d": 0, "body": 1, "animation": 2, "sprite": 3}
    return sorted(links, key=lambda link: (role_order.get(str(link.get("role")), 99), str(link.get("stableId"))))


def asset_selection_projection(graph: CatalogGraph, node: dict[str, Any]) -> dict[str, Any]:
    stable_id = str(node.get("stableId"))
    source = node.get("source") if isinstance(node.get("source"), dict) else {}
    workspace = workspace_for_node(node)
    usage_edge_ids = graph.indexes.get("sceneUsagesByAssetId", {}).get(stable_id, [])
    usage_links = selection_links_for_usage_edges(graph, usage_edge_ids)
    direct_scene_usage_count = sum(
        1
        for edge_id in usage_edge_ids
        if graph.edges_by_id.get(edge_id, {}).get("proofScope") == "scene_object_state"
    )
    export_actions = []
    exportable = is_exportable_asset_node(node)
    if exportable:
        export_actions.append(
            {
                "id": "export_catalog_asset",
                "label": "Export evidence bundle",
                "targetAssetId": stable_id,
            }
        )
    return {
        "schema": "catalog_graph.selection_projection.v0",
        "kind": "asset",
        "nodeId": node.get("id"),
        "stableId": stable_id,
        "label": node.get("label") or stable_id,
        "source": {
            "archive": source.get("hqr"),
            "entryIndex": source.get("entry_index"),
            "classicIndex": source.get("classic_index"),
            "rawSha256": source.get("raw_sha256"),
            "decodedSha256": node.get("decodedSha256"),
            "relativePath": node.get("relativePath"),
        },
        "provenance": provenance_for_asset_node(node),
        "evidenceStatus": node.get("evidenceStatus") or "unknown",
        "links": usage_links[:12],
        "unknowns": unknowns_for_asset_node(node),
        "previewActions": [
            {
                "id": "open_workspace",
                "label": f"Open {workspace or node.get('assetKind') or 'asset'} workspace",
                "targetAssetId": stable_id,
            }
        ] if workspace else [],
        "exportActions": export_actions,
        "exportCapability": {
            "exportable": exportable,
            "source": "catalog_graph.selection_projection.v0",
        },
        "inspectorRoute": inspector_route_for_asset_node(node),
        "workspaceSuggestion": workspace,
        "facets": {
            "archive": source.get("hqr"),
            "entryIndex": source.get("entry_index"),
            "kind": node.get("assetKind"),
            "entryType": node.get("entryType"),
            "semanticLayout": node.get("semanticLayout"),
            "decodedBytes": node.get("decodedBytes"),
            "sceneUsageCount": direct_scene_usage_count,
            "relationshipLinkCount": len(usage_edge_ids),
            "graphNodeId": node.get("id"),
        },
    }


def provenance_for_asset_node(node: dict[str, Any]) -> str:
    source = node.get("source") if isinstance(node.get("source"), dict) else {}
    for key in ("sourceProvenance", "runtimeReferenceStatus", "decodeNote"):
        value = node.get(key)
        if value:
            return str(value)
    if source.get("hqr") is not None:
        return f"{source.get('hqr')}[{source.get('entry_index')}]"
    return str(node.get("stableId") or node.get("id"))


def unknowns_for_asset_node(node: dict[str, Any]) -> list[str]:
    descriptors = node.get("unknownDescriptors")
    if isinstance(descriptors, list) and descriptors:
        unknowns: list[str] = []
        for descriptor in descriptors[:8]:
            if not isinstance(descriptor, dict):
                continue
            unknowns.append(f"{descriptor.get('section')}: {descriptor.get('note')}")
        return unknowns
    decode_status = node.get("decodeStatus")
    if decode_status and decode_status != "decoded":
        return [f"{decode_status}: {node.get('decodeNote')}"]
    return []


def is_exportable_asset_node(node: dict[str, Any]) -> bool:
    if node.get("assetKind") == "model":
        return True
    if node.get("assetKind") == "sprite":
        return node.get("semanticLayout") in {"lsp_sprite_frame", "raw_sprite_frame"}
    if node.get("assetKind") == "scene":
        return node.get("semanticLayout") == "scene_runtime_layout_partial" and bool(node.get("sceneBackgroundResolved"))
    if node.get("assetKind") != "resource":
        return False
    return node.get("semanticLayout") in {
        "sample_wave_audio",
        "lba2_texture_atlas_indexed",
        "lba2_indexed_image_256",
        "screen_indexed_image_640x480",
        "bkg_grid_map",
        "holomap_plan_image_640x480",
        "text_payload_bank",
        "smacker_video",
    }


def inspector_route_for_asset_node(node: dict[str, Any]) -> str | None:
    if node.get("assetKind") == "model":
        return "model"
    if node.get("assetKind") == "animation" and node.get("entryType") == "animation":
        return "animation"
    layout = node.get("semanticLayout")
    if node.get("assetKind") in {"animation", "sprite"} and layout == "unknown":
        return "raw_animation"
    if node.get("assetKind") == "scene":
        return "scene"
    if node.get("assetKind") == "sprite":
        if layout == "anim3ds_frame_ranges":
            return "anim3ds_range"
        if layout in {"lsp_sprite_frame", "raw_sprite_frame"}:
            return "sprite_frame"
        return None
    if node.get("assetKind") != "resource":
        return None
    if layout == "sample_wave_audio":
        return "sample_audio"
    if layout == "smacker_video":
        return "smacker_video"
    if layout == "text_order_table":
        return "text_order"
    if layout == "text_payload_bank":
        return "text_payload"
    if layout in {
        "lba2_palette",
        "screen_palette",
        "xpl_palette_bundle",
        "lba2_texture_atlas_indexed",
        "lba2_indexed_image_256",
        "screen_indexed_image_640x480",
    }:
        return "palette_image"
    if layout in {
        "file3d_table",
        "sprite_zv_table",
        "ress_offset_record_table",
        "ress_fixed_s16x8_table",
        "ress_ext_size_info",
        "acf_name_list",
    }:
        return "runtime_table"
    if layout in {
        "holomap_globe_uv_map",
        "holomap_globe_altitude_map",
        "holomap_globe_texture_map",
        "holomap_arrow_table",
        "holomap_plan_image_640x480",
        "holomap_plan_view_params",
    }:
        return "holomap"
    if layout in {
        "bkg_header",
        "bkg_grid_map",
        "bkg_grm_fragment",
        "bkg_block_table",
        "bkg_brick_graphic",
        "bkg_cube_map",
    }:
        return "background"
    if layout == "ress_unclassified_payload":
        return "unclassified_resource"
    return None


def selection_links_for_usage_edges(graph: CatalogGraph, edge_ids: list[str]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    def edge_sort_key(edge_id: str) -> tuple[int, str]:
        edge = graph.edges_by_id.get(edge_id, {})
        priority = 0 if edge.get("proofScope") == "scene_object_state" else 1
        return (priority, edge_id)

    for edge_id in sorted(edge_ids, key=edge_sort_key):
        edge = graph.edges_by_id.get(edge_id)
        if not edge:
            continue
        source_node_id = str(edge.get("from"))
        source_node = graph.nodes_by_id.get(source_node_id, {})
        stable_id = str(source_node.get("stableId") or stable_id_from_node_id(source_node_id))
        node_type = source_node.get("type")
        links.append(
            {
                "kind": "scene_object" if node_type == "SceneObject" else "scene_usage",
                "stableId": stable_id,
                "label": source_node.get("label") or stable_id,
                "proofScope": edge.get("proofScope"),
                "evidenceStatus": edge.get("evidenceStatus"),
                "sourceRule": edge.get("sourceRule"),
                "sourceField": edge.get("sourceField"),
                "indexRule": edge.get("indexRule"),
            }
        )
    return links


def query_export(graph: CatalogGraph, stable_id: str | None) -> dict[str, Any]:
    if not stable_id:
        return export_graph_document(graph)
    node_id = resolve_node_id(graph, stable_id)
    node_ids = {node_id}
    edge_ids = {edge["id"] for edge in graph.node_edges(node_id, "both")}
    for edge_id in list(edge_ids):
        edge = graph.edges_by_id[edge_id]
        node_ids.add(str(edge.get("from")))
        node_ids.add(str(edge.get("to")))
    return {
        "schema": "catalog_graph.subgraph.v0",
        "root": stable_id,
        "nodes": [graph.nodes_by_id[node_id] for node_id in sorted(node_ids) if node_id in graph.nodes_by_id],
        "edges": [graph.edges_by_id[edge_id] for edge_id in sorted(edge_ids)],
    }


def filter_edges(
    edges: list[dict[str, Any]],
    proof_scope: str | None = None,
    evidence_status: str | None = None,
) -> list[dict[str, Any]]:
    return [
        edge
        for edge in edges
        if (proof_scope is None or edge.get("proofScope") == proof_scope)
        and (evidence_status is None or edge.get("evidenceStatus") == evidence_status)
    ]


def query_probe(graph: CatalogGraph, stable_ids: list[str]) -> dict[str, Any]:
    subgraphs = [query_export(graph, stable_id) for stable_id in stable_ids]
    return {
        "schema": "catalog_graph.probe.v0",
        "ids": stable_ids,
        "graphSummary": {
            "nodes": len(graph.nodes_by_id),
            "edges": len(graph.edges_by_id),
            "assets": len(graph.indexes.get("assetById", {})),
            "sceneUsageTargets": len(graph.indexes.get("sceneUsagesByAssetId", {})),
        },
        "subgraphs": subgraphs,
        "consumerProbes": [
            consumer_probe("selection", "node stableId and selectable edges provide active selection context"),
            consumer_probe("inspector", "incoming/outgoing typed edges provide inspector sections"),
            consumer_probe("workspace", "Asset kind and edge context preserve workspace routing"),
            consumer_probe("export", "edge proofScope/evidenceStatus/sourceRule provide export provenance"),
            consumer_probe("cli_json", "this response is deterministic structured JSON"),
            consumer_probe("port_filtering", "proofScope and evidenceStatus fields support port-facing filters"),
        ],
    }


def consumer_probe(name: str, assertion: str) -> dict[str, str]:
    return {"consumer": name, "assertion": assertion, "status": "covered_by_probe_shape"}


def consumer_round_trip_for_node(graph: CatalogGraph, node_id: str) -> dict[str, Any]:
    node = graph.nodes_by_id.get(node_id) or {}
    stable_id = node.get("stableId") or stable_id_from_node_id(node_id)
    edge_types = sorted({edge.get("type") for edge in graph.node_edges(node_id, "both")})
    return {
        "selectionStableId": stable_id,
        "inspectorEdgeSections": edge_types,
        "workspaceSuggestion": workspace_for_node(node),
        "exportProvenanceFields": ["proofScope", "evidenceStatus", "sourceRule"],
        "queryJsonStable": True,
        "portFilterFields": ["proofScope", "evidenceStatus"],
    }


def workspace_for_node(node: dict[str, Any]) -> str | None:
    if node.get("type") == "SceneObject":
        return "entity"
    if node.get("type") == "ResourceRecord":
        return "resource"
    if node.get("type") != "Asset":
        return None
    kind = node.get("assetKind")
    if kind in {"model", "animation"}:
        return "model"
    if kind == "sprite":
        return "sprite"
    if kind == "scene":
        return "entity"
    if kind == "resource":
        return "resource"
    return None


def iter_scene_objects(scene_asset: dict[str, Any]) -> Iterable[dict[str, Any]]:
    recon = ((scene_asset.get("stats") or {}).get("reconnaissance") or {})
    hero = recon.get("hero") or {}
    if hero:
        yield {
            **hero,
            "index": 0,
            "position": hero.get("start"),
            "file3d_index": -1,
            "gen_body": 0,
            "gen_anim": 0,
            "sprite": 0,
            "flags": 0,
        }
    for scene_object in recon.get("sampled_objects") or []:
        if isinstance(scene_object, dict):
            yield scene_object


def scene_object_node(scene_asset: dict[str, Any], scene_object: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    object_index = scene_object.get("index")
    return {
        "id": scene_object_node_id_for(scene_id, object_index),
        "type": "SceneObject",
        "label": f"{scene_asset.get('label') or scene_id} object {object_index}",
        "stableId": f"{scene_id}#object:{object_index}",
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "object_index": object_index,
            "position": scene_object.get("position"),
            "file3d_index": scene_object.get("file3d_index"),
            "gen_body": scene_object.get("gen_body"),
            "gen_anim": scene_object.get("gen_anim"),
            "sprite": scene_object.get("sprite"),
            "flags": scene_object.get("flags"),
        },
        "evidenceStatus": "decoded_only",
    }


def proof_scope_for_usage(usage: dict[str, Any]) -> str:
    if usage.get("script_kind"):
        return "script_reference"
    if usage.get("kind") in {"body", "animation", "sprite"}:
        return "scene_object_state"
    if usage.get("kind") == "grm_fragment":
        return "classic_source_rule"
    if usage.get("resolution_rule"):
        return "classic_source_rule"
    return "decoded_payload"


def source_field_for_usage(link_kind: str, link: dict[str, Any]) -> str:
    if link_kind == "body":
        return "SceneObject.links.body.asset_id / SceneAssetUsage.target_asset_id"
    if link_kind == "animation":
        return "SceneObject.links.animation.asset_id / SceneAssetUsage.target_asset_id"
    if link_kind == "sprite":
        return "SceneObject.links.sprite.asset_id / SceneAssetUsage.target_asset_id"
    return link.get("reference_key") or "SceneAssetUsage.target_asset_id"


def index_rule_for_usage(link_kind: str, link: dict[str, Any]) -> str | None:
    if link_kind == "sample":
        return "SAMPLES.HQR catalog id equals zero-based runtime sample id; source hqr_table_index is runtime id + 1."
    if link_kind == "body":
        return "File3D body generic id resolves to BODY.HQR catalog entry index."
    if link_kind == "animation":
        return "File3D animation generic id resolves to ANIM.HQR catalog entry index."
    if link_kind == "sprite":
        return link.get("index_rule") or "Runtime sprite index resolves through SPRITE_3D/ANIM_3DS flags."
    return link.get("index_rule")


def missing_target_stable_id_for_link(link_kind: str, link: dict[str, Any]) -> str | None:
    if link.get("asset_available", True) is not False:
        return None
    reference_value = link.get("reference_value")
    if link_kind in {"sample", "script_sample_missing", "ambience_sample"}:
        sample_id = link.get("sample_id", reference_value)
        return f"SAMPLES.HQR:{sample_id}" if sample_id is not None else None
    if link_kind in {"text", "zone_text"}:
        text_id = link.get("text_id", reference_value)
        text_file = link.get("text_file_index")
        if text_id is None:
            return None
        return f"TEXT.HQR:{text_file if text_file is not None else 'unknown'}#message:{text_id}"
    if link_kind == "video":
        acf_name = link.get("acf_basename") or link.get("acf_name") or reference_value
        return f"VIDEO/VIDEO.HQR:{acf_name}" if acf_name else None
    if link_kind == "sprite":
        runtime_index = link.get("runtime_sprite_index", link.get("sprite_index", reference_value))
        backend = link.get("backend") or "runtime"
        return f"{backend}:{runtime_index}" if runtime_index is not None else None
    return str(reference_value) if reference_value is not None else None


def evidence_status_for_asset(asset: dict[str, Any]) -> str:
    stats = asset.get("stats") or {}
    if isinstance(stats, dict):
        if stats.get("source_provenance"):
            return "source_backed"
        if stats.get("runtime_reference_status") == "source-backed":
            return "source_backed"
        if stats.get("parse_status") == "raw":
            return "intentionally_deferred"
        if stats.get("decode_status") in {"decoded", "partial"}:
            return "decoded_only"
    if asset.get("kind") in {"model", "animation"}:
        return "decoded_only"
    return "unknown"


def index_rule_for_asset(asset: dict[str, Any]) -> str:
    source = asset.get("source") or {}
    hqr = source.get("hqr")
    if hqr == "SCENE.HQR":
        return "SCENE.HQR catalog entry index is classic scene index + 1."
    if hqr == "SAMPLES.HQR":
        return "SAMPLES.HQR catalog id equals zero-based runtime sample id; source hqr_table_index is runtime id + 1."
    if hqr == "SCREEN.HQR":
        return "SCREEN.HQR catalog ids match classic zero-based PCR constants; even slots are indexed images and odd PCR+1 slots are palettes."
    if hqr == "ANIM3DS.HQR":
        return "ANIM3DS.HQR frames use zero-based entry ids; entry 127 is the range metadata table."
    return "Catalog id uses HQR filename plus catalog entry index."


def resolve_node_id(graph: CatalogGraph, stable_id: str) -> str:
    if stable_id in graph.nodes_by_id:
        return stable_id
    if stable_id in graph.indexes.get("assetById", {}):
        return str(graph.indexes["assetById"][stable_id])
    if "#object:" in stable_id:
        scene_id, object_value = stable_id.split("#object:", 1)
        return scene_object_node_id_for(scene_id, parse_object_index(object_value))
    if stable_id.startswith("ANIM3DS:"):
        return sprite_range_node_id_for(stable_id.split(":", 1)[1])
    return asset_node_id_for(stable_id)


def parse_object_index(value: Any) -> int | str:
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def archive_node_id_for(archive: str) -> str:
    return f"archive:{archive}"


def archive_entry_node_id_for(archive: str, entry_index: Any) -> str:
    return f"archive-entry:{archive}:{entry_index}"


def asset_node_id_for(asset_id: str) -> str:
    return f"asset:{asset_id}"


def scene_node_id_for(scene_id: str) -> str:
    return f"scene:{scene_id}"


def scene_object_node_id_for(scene_id: str, object_index: Any) -> str:
    return f"scene-object:{scene_id}:{object_index}"


def script_reference_node_id_for(scene_id: str, object_index: Any, link: dict[str, Any]) -> str:
    parts = [
        scene_id,
        str(object_index),
        str(link.get("script_kind") or "script"),
        str(link.get("reference_key") or "ref"),
        str(link.get("reference_value") or ""),
        str(link.get("asset_id") or link.get("target_asset_id") or ""),
    ]
    return "script-ref:" + ":".join(safe_id_part(part) for part in parts)


def sprite_range_node_id_for(range_index: Any) -> str:
    return f"sprite-range:ANIM3DS:{range_index}"


def missing_node_id_for(stable_id: str) -> str:
    return f"missing:{stable_id}"


def resource_record_node_id_for(asset_id: str, record_index: Any) -> str:
    return f"resource-record:{asset_id}:{record_index}"


def file3d_record_node_id_for(file3d_index: int) -> str:
    return f"file3d-record:RESS.HQR:44:{file3d_index}"


def normalize_direction(direction: str) -> str:
    if direction == "incoming":
        return "in"
    if direction == "outgoing":
        return "out"
    return direction


def stable_id_from_node_id(node_id: str) -> str:
    for prefix in ("asset:", "archive:", "missing:"):
        if node_id.startswith(prefix):
            return node_id[len(prefix) :]
    if node_id.startswith("scene-object:"):
        rest = node_id[len("scene-object:") :]
        scene_id, object_index = rest.rsplit(":", 1)
        return f"{scene_id}#object:{object_index}"
    if node_id.startswith("scene:"):
        return node_id[len("scene:") :]
    if node_id.startswith("sprite-range:"):
        return node_id[len("sprite-range:") :]
    return node_id


def stable_edge_id(base: str, count: int) -> str:
    safe = safe_id_part(base)
    return f"edge:{safe}" if count == 1 else f"edge:{safe}:{count}"


def safe_id_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in ".:_#=-" else "_" for char in value)


def search_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("id", "type", "label", "stableId", "relationship", "proofScope", "evidenceStatus", "sourceRule", "sourceField"):
        value = payload.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def graph_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def build_graph_from_asset_root(asset_root: Path) -> CatalogGraph:
    catalog = viewer.build_catalog(asset_root)
    return build_catalog_graph(catalog)


def catalog_graph_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="lba2-lm2-viewer catalog-graph",
        description="Build and query the typed catalog evidence graph.",
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=viewer.DEFAULT_ASSET_ROOT,
        help="folder containing LBA2 HQR files",
    )
    parser.add_argument(
        "--graph-json",
        type=Path,
        help="load a previously exported graph JSON instead of rebuilding the catalog",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--output", required=True, type=Path)

    probe = subparsers.add_parser("probe")
    probe.add_argument("--ids", nargs="+", required=True)
    probe.add_argument("--json", action="store_true")

    explain = subparsers.add_parser("explain")
    explain.add_argument("id")
    explain.add_argument("--json", action="store_true")

    edges = subparsers.add_parser("edges")
    edges.add_argument("id")
    edges.add_argument("--direction", choices=("in", "out", "incoming", "outgoing", "both"), default="both")
    edges.add_argument("--proof-scope")
    edges.add_argument("--evidence-status")
    edges.add_argument("--json", action="store_true")

    compatible = subparsers.add_parser("compatible")
    compatible.add_argument("model_id")
    compatible.add_argument("--json", action="store_true")

    prove = subparsers.add_parser("prove")
    prove.add_argument("model_id")
    prove.add_argument("animation_id")
    prove.add_argument("--json", action="store_true")

    usages = subparsers.add_parser("usages")
    usages.add_argument("id")
    usages.add_argument("--proof-scope")
    usages.add_argument("--evidence-status")
    usages.add_argument("--json", action="store_true")

    scene_object = subparsers.add_parser("scene-object")
    scene_object.add_argument("scene_id")
    scene_object.add_argument("object_index")
    scene_object.add_argument("--json", action="store_true")

    export = subparsers.add_parser("export")
    export.add_argument("--subgraph")
    export.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    catalog: dict[str, Any] | None = None
    asset_root = args.asset_root.expanduser().resolve()
    if args.command == "build":
        catalog = viewer.build_catalog(asset_root)
        graph = build_catalog_graph(catalog)
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            graph_json(export_graph_document(graph, catalog, asset_root)),
            encoding="utf-8",
        )
        print(graph_json({"schema": "catalog_graph.build.v0", "output": str(output), "metadata": graph_build_metadata(catalog, graph, asset_root)}))
        return 0
    if args.graph_json is not None:
        graph = load_graph_export(args.graph_json.expanduser().resolve())
    else:
        graph = build_graph_from_asset_root(asset_root)
    if args.command == "probe":
        payload = query_probe(graph, args.ids)
    elif args.command == "explain":
        payload = query_explain(graph, args.id)
    elif args.command == "edges":
        payload = query_edges(graph, args.id, args.direction, args.proof_scope, args.evidence_status)
    elif args.command == "compatible":
        payload = query_compatible(graph, args.model_id)
    elif args.command == "prove":
        payload = query_prove(graph, args.model_id, args.animation_id)
    elif args.command == "usages":
        payload = query_usages(graph, args.id, args.proof_scope, args.evidence_status)
    elif args.command == "scene-object":
        payload = query_scene_object(graph, args.scene_id, args.object_index)
    elif args.command == "export":
        payload = query_export(graph, args.subgraph)
    else:  # pragma: no cover - argparse enforces choices
        raise viewer.Lm2Error(f"unsupported catalog-graph command: {args.command}")
    print(graph_json(payload))
    return 0
