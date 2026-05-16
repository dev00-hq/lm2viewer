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
from .exportability import graph_asset_export_route, has_exact_scene_background_links


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
        base = stable_edge_base(edge)
        self._edge_counts[base] += 1
        edge_id = stable_edge_id(base, self._edge_counts[base])
        occurrence_ordinal = edge.get("occurrenceOrdinal")
        if not isinstance(occurrence_ordinal, int) or isinstance(occurrence_ordinal, bool):
            occurrence_ordinal = self._edge_counts[base] - 1
        target_stable_id = edge.get("targetStableId")
        if target_stable_id is None:
            target_stable_id = stable_id_from_node_id(str(edge.get("to")))
        normalized = {
            "id": edge_id,
            "edgeId": edge_id,
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
            "sourceEvidenceId": edge.get("sourceEvidenceId") or f"{edge_id}#source",
            "occurrenceOrdinal": occurrence_ordinal,
            "ownerNodeId": edge.get("ownerNodeId") or edge.get("from"),
            "sourcePath": edge.get("sourcePath"),
            "sourceOffset": edge.get("sourceOffset"),
            "rawReference": edge.get("rawReference"),
            "targetStableId": target_stable_id,
            "resolverKind": edge.get("resolverKind") or str(edge.get("type")).lower(),
            **edge,
            "id": edge_id,
            "edgeId": edge_id,
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
        "sceneZonesBySceneId": defaultdict(list),
        "waypointsBySceneId": defaultdict(list),
        "selectionByNodeId": {},
        "missingTargetsByStableId": {},
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
                "sceneBackgroundResolved": has_exact_scene_background_links(asset.get("stats"))
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
                    "sourceRule": "scene_catalog_stats decoded scene object records",
                    "sourceField": "SceneStats.reconnaissance.objects",
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
        add_scene_mechanics_projection(graph, asset)


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
        graph.add_node(missing_target_node(str(target_asset_id), link, target_kind_for_usage(link_kind), owner_node_id=object_node_id))
    file3d_node_id = add_file3d_record_if_present(graph, scene_asset, scene_object, link)
    edge_type = USAGE_EDGE_TYPES.get(link_kind, "USES_RESOURCE")
    if link.get("script_kind"):
        reference_node_id = script_reference_node_id_for(scene_id, scene_object.get("index"), link)
        source_offset = link.get("source_offset") if isinstance(link.get("source_offset"), int) else link.get("offset")
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
                    "source_offset": source_offset,
                    "occurrence_index": link.get("occurrence_index"),
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
                "ownerNodeId": object_node_id,
                "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].{link.get('script_kind')}",
                "sourceOffset": source_offset,
                "rawReference": link.get("reference_value"),
                "resolverKind": "script_reference_container",
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
                "ownerNodeId": object_node_id,
                "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].{link.get('script_kind')}",
                "sourceOffset": source_offset,
                "rawReference": link.get("reference_value"),
                "resolverKind": f"script_{link_kind}",
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
            "ownerNodeId": object_node_id,
            "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].links.{link_kind}",
            "sourceOffset": link.get("source_offset") if isinstance(link.get("source_offset"), int) else None,
            "rawReference": link.get("reference_value", link.get("asset_id") or link.get("target_asset_id")),
            "resolverKind": f"scene_{link_kind}",
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
        for occurrence_index, link in enumerate(script.get("asset_links") or []):
            if not isinstance(link, dict):
                continue
            add_scene_usage_edge(
                graph,
                scene_asset,
                scene_object,
                str(link.get("kind") or "resource"),
                {**link, "script_kind": script_kind, "occurrence_index": occurrence_index},
                "script_reference",
            )
        for occurrence_index, missing_link in enumerate(script.get("missing_sample_links") or []):
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
                    "occurrence_index": occurrence_index,
                },
                "script_reference",
            )


def add_scene_mechanics_projection(graph: CatalogGraph, scene_asset: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    scene_node_id = scene_node_id_for(scene_id)
    recon = ((scene_asset.get("stats") or {}).get("reconnaissance") or {})
    if not isinstance(recon, dict):
        return
    for zone in recon.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        zone_node_id = scene_zone_node_id_for(scene_id, zone.get("index"))
        graph.add_node(scene_zone_node(scene_asset, zone))
        graph.add_edge(
            {
                "type": "HAS_ZONE",
                "from": scene_node_id,
                "to": zone_node_id,
                "relationship": "has zone",
                "inverse": "zone of scene",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "1",
                "proofScope": "decoded_payload",
                "evidenceStatus": "decoded_only",
                "sourceRule": "SCENE.HQR zone table decoded from scene payload",
                "sourceField": "SceneStats.reconnaissance.zones",
                "indexRule": "Scene zone index is zero-based within the scene zone table.",
                "selectable": True,
                "ownerNodeId": scene_node_id,
                "sourcePath": f"{scene_id}.zones[{zone.get('index')}]",
                "sourceOffset": zone.get("offset") if isinstance(zone.get("offset"), int) else None,
                "rawReference": zone.get("index"),
                "resolverKind": "scene_zone_table",
            }
        )
        add_scene_zone_contract_edges(graph, scene_asset, zone)
    add_scene_zone_relationship_edges(graph, scene_asset)
    for waypoint in recon.get("tracks") or []:
        if not isinstance(waypoint, dict):
            continue
        waypoint_node_id = waypoint_node_id_for(scene_id, waypoint.get("index"))
        graph.add_node(waypoint_node(scene_asset, waypoint))
        graph.add_edge(
            {
                "type": "HAS_WAYPOINT",
                "from": scene_node_id,
                "to": waypoint_node_id,
                "relationship": "has waypoint",
                "inverse": "waypoint of scene",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "1",
                "proofScope": "decoded_payload",
                "evidenceStatus": "decoded_only",
                "sourceRule": "SCENE.HQR T_TRACK coordinate table decoded from scene payload",
                "sourceField": "SceneStats.reconnaissance.tracks",
                "indexRule": "Waypoint index is zero-based within the scene T_TRACK table.",
                "selectable": True,
                "ownerNodeId": scene_node_id,
                "sourcePath": f"{scene_id}.waypoints[{waypoint.get('index')}]",
                "sourceOffset": waypoint.get("offset") if isinstance(waypoint.get("offset"), int) else None,
                "rawReference": waypoint.get("index"),
                "resolverKind": "scene_track_table",
            }
        )
    owners = list(iter_scene_script_owners(scene_asset))
    for scene_object in owners:
        add_script_structure_projection(graph, scene_asset, scene_object)
        add_scene_object_movement_edges(graph, scene_asset, scene_object)
    for scene_object in owners:
        add_scene_script_local_reference_edges(graph, scene_asset, scene_object)
        add_scene_script_control_flow_edges(graph, scene_asset, scene_object)
        add_runtime_state_field_edges(graph, scene_asset, scene_object)
    add_scene_patch_edges(graph, scene_asset)


def add_scene_zone_contract_edges(graph: CatalogGraph, scene_asset: dict[str, Any], zone: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    zone_node_id = scene_zone_node_id_for(scene_id, zone.get("index"))
    runtime = zone.get("runtime") if isinstance(zone.get("runtime"), dict) else {}
    fields = runtime.get("fields") if isinstance(runtime.get("fields"), dict) else {}
    for field, value in sorted(runtime.items()):
        if not field.endswith("_application") or value is None:
            continue
        graph.add_edge(
            {
                "type": "DECLARES_RUNTIME_CONTRACT",
                "from": zone_node_id,
                "to": zone_node_id,
                "relationship": "declares runtime contract",
                "inverse": "runtime contract declared by zone",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "0..n",
                "proofScope": "classic_source_rule",
                "evidenceStatus": "source_backed",
                "sourceRule": runtime.get("source") or "classic source zone runtime contract evidence",
                "sourceField": f"SceneZone.runtime.{field}",
                "indexRule": "Zone type and Info fields select a classic source contract; this is not live runtime state.",
                "selectable": True,
                "ownerNodeId": zone_node_id,
                "sourcePath": f"{scene_id}.zones[{zone.get('index')}].runtime.{field}",
                "sourceOffset": zone.get("offset") if isinstance(zone.get("offset"), int) else None,
                "rawReference": field,
                "resolverKind": "zone_runtime_contract",
            }
        )
    target_cube = fields.get("target_cube")
    if runtime.get("effect") != "change_cube" or not isinstance(target_cube, int) or isinstance(target_cube, bool):
        return
    target_stable_id = f"LBA_BKG.HQR#runtime-cube:{target_cube}"
    target_node_id = missing_node_id_for(target_stable_id)
    graph.add_node(
        missing_target_node(
            target_stable_id,
            {
                "kind": "background_resource",
                "reference_value": target_cube,
                "reason": "change-cube target cube resolver is intentionally deferred until background cube records are graph-addressable",
            },
            "background_resource",
            owner_node_id=zone_node_id,
            resolution_state="intentionally_deferred_target",
        )
    )
    graph.add_edge(
        {
            "type": "CHANGES_CUBE_TO",
            "from": zone_node_id,
            "to": target_node_id,
            "relationship": "changes cube to",
            "inverse": "target cube of change-cube zone",
            "cardinalityFromSource": "0..1",
            "cardinalityFromTarget": "0..n",
            "proofScope": "classic_source_rule",
            "evidenceStatus": "source_backed",
            "sourceRule": runtime.get("source") or "OBJECT.CPP::GereZoneChangeCube sets NewCube from zone.Num.",
            "sourceField": "SceneZone.runtime.fields.target_cube",
            "indexRule": "Change-cube zone Num is the runtime cube id; the graph does not yet materialize background cube records as addressable targets.",
            "selectable": True,
            "ownerNodeId": zone_node_id,
            "sourcePath": f"{scene_id}.zones[{zone.get('index')}].runtime.fields.target_cube",
            "sourceOffset": zone.get("offset") if isinstance(zone.get("offset"), int) else None,
            "rawReference": target_cube,
            "targetStableId": target_stable_id,
            "resolverKind": "zone_change_cube_target",
        }
    )


def add_scene_zone_relationship_edges(graph: CatalogGraph, scene_asset: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    recon = ((scene_asset.get("stats") or {}).get("reconnaissance") or {})
    for occurrence_index, link in enumerate(recon.get("text_zone_links") or []):
        if not isinstance(link, dict):
            continue
        zone_node_id = scene_zone_node_id_for(scene_id, link.get("zone_index"))
        if zone_node_id not in graph.nodes_by_id:
            continue
        target_asset_id = link.get("asset_id") or missing_target_stable_id_for_link("zone_text", {**link, "asset_available": False})
        if not target_asset_id:
            continue
        target_node_id = asset_node_id_for(str(target_asset_id))
        if link.get("asset_available") is False or target_node_id not in graph.nodes_by_id:
            target_node_id = missing_node_id_for(str(target_asset_id))
            graph.add_node(missing_target_node(str(target_asset_id), {**link, "asset_available": False}, "text", owner_node_id=zone_node_id))
        graph.add_edge(
            {
                "type": "USES_TEXT",
                "from": zone_node_id,
                "to": target_node_id,
                "relationship": "zone uses text",
                "inverse": "text used by zone",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "0..n",
                "proofScope": "classic_source_rule",
                "evidenceStatus": "source_backed" if target_node_id in graph.nodes_by_id and not target_node_id.startswith("missing:") else "unknown",
                "sourceRule": link.get("resolution_rule") or "Scene message zone resolves logical text record",
                "sourceField": "SceneStats.reconnaissance.text_zone_links",
                "indexRule": "Zone message value resolves through scene text file and payload-local text record index.",
                "selectable": True,
                "usageKind": "zone_text",
                "ownerNodeId": zone_node_id,
                "sourcePath": f"{scene_id}.text_zone_links[{occurrence_index}]",
                "rawReference": link.get("text_id", link.get("reference_value")),
                "resolverKind": "zone_text",
            }
        )
    for occurrence_index, link in enumerate(recon.get("grm_fragment_links") or []):
        if not isinstance(link, dict):
            continue
        zone_node_id = scene_zone_node_id_for(scene_id, link.get("zone_index"))
        if zone_node_id not in graph.nodes_by_id:
            continue
        target_asset_id = link.get("asset_id") or f"LBA_BKG.HQR:grm:{link.get('resolved_grm_entry')}"
        target_node_id = asset_node_id_for(str(target_asset_id))
        if link.get("asset_available") is False or target_node_id not in graph.nodes_by_id:
            target_node_id = missing_node_id_for(str(target_asset_id))
            graph.add_node(missing_target_node(str(target_asset_id), {**link, "asset_available": False}, "background_resource", owner_node_id=zone_node_id))
        graph.add_edge(
            {
                "type": "APPLIES_GRM_FRAGMENT",
                "from": zone_node_id,
                "to": target_node_id,
                "relationship": "applies GRM fragment",
                "inverse": "GRM fragment applied by zone",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "0..n",
                "proofScope": "classic_source_rule",
                "evidenceStatus": "source_backed" if not target_node_id.startswith("missing:") else "unknown",
                "sourceRule": link.get("source_provenance") or "Scene GRM zone resolves background GRM fragment",
                "sourceField": "SceneStats.reconnaissance.grm_fragment_links",
                "indexRule": "GRM fragment entry is resolved from background GRM base plus zone value.",
                "selectable": True,
                "usageKind": "grm_fragment",
                "ownerNodeId": zone_node_id,
                "sourcePath": f"{scene_id}.grm_fragment_links[{occurrence_index}]",
                "rawReference": link.get("zone_value"),
                "resolverKind": "zone_grm_fragment",
            }
        )
    for occurrence_index, link in enumerate(recon.get("message_camera_links") or []):
        if not isinstance(link, dict):
            continue
        zone_node_id = scene_zone_node_id_for(scene_id, link.get("zone_index"))
        if zone_node_id not in graph.nodes_by_id:
            continue
        target_zone_index = link.get("target_zone_index")
        target_node_id = scene_zone_node_id_for(scene_id, target_zone_index)
        if not link.get("target_available") or target_node_id not in graph.nodes_by_id:
            missing_id = f"{scene_id}#zone:{target_zone_index if target_zone_index is not None else link.get('associated_camera_zone')}"
            target_node_id = missing_node_id_for(missing_id)
            graph.add_node(missing_target_node(missing_id, link, "scene_zone", owner_node_id=zone_node_id, resolution_state="outside_table"))
        graph.add_edge(
            {
                "type": "REFERENCES_ZONE",
                "from": zone_node_id,
                "to": target_node_id,
                "relationship": "references zone",
                "inverse": "zone referenced by zone",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "0..n",
                "proofScope": "classic_source_rule",
                "evidenceStatus": "source_backed" if link.get("target_available") else "unknown",
                "sourceRule": link.get("source_provenance") or "Message zone camera lookup references a camera zone by Num.",
                "sourceField": "SceneStats.reconnaissance.message_camera_links",
                "indexRule": "Message Info1 references the camera zone Num, resolved to a zone table row.",
                "selectable": True,
                "ownerNodeId": zone_node_id,
                "sourcePath": f"{scene_id}.message_camera_links[{occurrence_index}]",
                "rawReference": link.get("associated_camera_zone"),
                "resolverKind": "zone_camera_reference",
            }
        )


def add_scene_object_movement_edges(graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    object_node_id = scene_object_node_id_for(scene_id, scene_object.get("index"))
    movement = ((scene_object.get("runtime") or {}).get("movement") or {})
    for occurrence_index, reference in enumerate(movement.get("references") or []):
        if not isinstance(reference, dict) or reference.get("kind") != "waypoint":
            continue
        waypoint_index = reference.get("value")
        target_node_id = waypoint_node_id_for(scene_id, waypoint_index)
        if not graph.nodes_by_id.get(target_node_id):
            target_node_id = missing_node_id_for(f"{scene_id}#waypoint:{waypoint_index}")
            graph.add_node(
                missing_target_node(
                    f"{scene_id}#waypoint:{waypoint_index}",
                    reference,
                    "waypoint",
                    owner_node_id=object_node_id,
                    resolution_state="outside_table",
                )
            )
        graph.add_edge(
            {
                "type": "MOVEMENT_TARGETS",
                "from": object_node_id,
                "to": target_node_id,
                "relationship": "movement targets waypoint",
                "inverse": "waypoint targeted by movement",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "0..n",
                "proofScope": "classic_source_rule",
                "evidenceStatus": "source_backed" if reference.get("target_found") else "unknown",
                "sourceRule": reference.get("source") or "scene object movement Info fields reference waypoint records",
                "sourceField": reference.get("field") or "SceneObject.runtime.movement.references",
                "indexRule": "Movement reference value addresses a zero-based T_TRACK waypoint index.",
                "selectable": True,
                "ownerNodeId": object_node_id,
                "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].movement.references[{occurrence_index}]",
                "rawReference": waypoint_index,
                "resolverKind": "scene_object_movement",
            }
        )


def add_script_structure_projection(graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    object_node_id = scene_object_node_id_for(scene_id, scene_object.get("index"))
    for script_kind, analysis in scene_object_scripts(scene_object):
        block_node_id = script_block_node_id_for(scene_id, scene_object.get("index"), script_kind)
        graph.add_node(script_block_node(scene_asset, scene_object, script_kind, analysis))
        graph.add_edge(
            {
                "type": "HAS_SCRIPT",
                "from": object_node_id,
                "to": block_node_id,
                "relationship": f"has {script_kind} script",
                "inverse": "script of scene object",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "1",
                "proofScope": "script_structure",
                "evidenceStatus": "decoded_only",
                "sourceRule": "SCENE.HQR embedded track/life script byte layout decoded",
                "sourceField": f"SceneObject.{script_kind}_script_analysis",
                "indexRule": "Script block belongs to a scene object and script kind.",
                "selectable": True,
                "ownerNodeId": object_node_id,
                "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].script.{script_kind}",
                "sourceOffset": scene_object.get(f"{script_kind}_script_offset") if isinstance(scene_object.get(f"{script_kind}_script_offset"), int) else None,
                "resolverKind": "scene_script_block",
            }
        )
        for instruction in analysis.get("first_instructions") or []:
            if not isinstance(instruction, dict):
                continue
            add_script_instruction_node_and_edge(graph, scene_asset, scene_object, script_kind, instruction)
        add_script_execution_contract_edges(graph, scene_asset, scene_object, script_kind, analysis)


def add_script_execution_contract_edges(
    graph: CatalogGraph,
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    script_kind: str,
    analysis: dict[str, Any],
) -> None:
    scene_id = str(scene_asset.get("id"))
    instructions = [item for item in analysis.get("first_instructions") or [] if isinstance(item, dict)]
    for contract_index, contract in enumerate(analysis.get("execution_contracts") or []):
        if not isinstance(contract, dict):
            continue
        mnemonics = {str(value) for value in contract.get("mnemonics") or []}
        if not mnemonics:
            continue
        for instruction in instructions:
            mnemonic = str(instruction.get("mnemonic") or "")
            if mnemonic not in mnemonics:
                continue
            instruction_node_id = script_instruction_node_id_for(
                scene_id,
                scene_object.get("index"),
                script_kind,
                instruction.get("offset"),
            )
            if instruction_node_id not in graph.nodes_by_id:
                graph.add_node(script_instruction_node(scene_asset, scene_object, script_kind, instruction))
            graph.add_edge(
                {
                    "type": "DECLARES_EXECUTION_CONTRACT",
                    "from": instruction_node_id,
                    "to": instruction_node_id,
                    "relationship": "declares execution contract",
                    "inverse": "execution contract declared by instruction",
                    "cardinalityFromSource": "0..n",
                    "cardinalityFromTarget": "0..n",
                    "proofScope": "classic_source_rule",
                    "evidenceStatus": "source_backed",
                    "sourceRule": contract.get("source") or "classic source script execution contract evidence",
                    "sourceField": f"ScriptAnalysis.execution_contracts.{contract.get('contract')}",
                    "indexRule": "Execution contracts are static source-backed opcode effects; this edge does not imply the instruction executed.",
                    "selectable": True,
                    "ownerNodeId": instruction_node_id,
                    "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].script.{script_kind}.execution_contracts[{contract_index}]",
                    "sourceOffset": instruction.get("offset") if isinstance(instruction.get("offset"), int) else None,
                    "rawReference": contract.get("contract"),
                    "resolverKind": "script_execution_contract",
                    "executionContract": contract.get("contract"),
                    "executionEffect": contract.get("effect"),
                    "executionContractCount": contract.get("count"),
                }
            )


def add_script_instruction_node_and_edge(
    graph: CatalogGraph,
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    script_kind: str,
    instruction: dict[str, Any],
) -> str:
    scene_id = str(scene_asset.get("id"))
    block_node_id = script_block_node_id_for(scene_id, scene_object.get("index"), script_kind)
    instruction_node_id = script_instruction_node_id_for(scene_id, scene_object.get("index"), script_kind, instruction.get("offset"))
    graph.add_node(script_instruction_node(scene_asset, scene_object, script_kind, instruction))
    graph.add_edge(
        {
            "type": "HAS_INSTRUCTION",
            "from": block_node_id,
            "to": instruction_node_id,
            "relationship": "has script instruction",
            "inverse": "instruction of script",
            "cardinalityFromSource": "0..n",
            "cardinalityFromTarget": "1",
            "proofScope": "script_structure",
            "evidenceStatus": "decoded_only",
            "sourceRule": "Script bytecode decoder produced an instruction boundary",
            "sourceField": "ScriptAnalysis.first_instructions",
            "indexRule": "Instruction stable id uses byte offset inside the owning script.",
            "selectable": True,
            "ownerNodeId": block_node_id,
            "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].script.{script_kind}.offset[{instruction.get('offset')}]",
            "sourceOffset": instruction.get("offset") if isinstance(instruction.get("offset"), int) else None,
            "rawReference": instruction.get("operand_hex"),
            "resolverKind": "script_instruction",
        }
    )
    return instruction_node_id


def add_scene_script_local_reference_edges(graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    for script_kind, analysis in scene_object_scripts(scene_object):
        instruction_by_reference = script_instructions_by_local_reference(analysis)
        for occurrence_index, link in enumerate(analysis.get("local_links") or []):
            if not isinstance(link, dict):
                continue
            reference_key = str(link.get("reference_key") or link.get("kind") or "")
            reference_value = link.get("reference_value")
            instruction = instruction_by_reference.get((reference_key, reference_value))
            if instruction is None:
                instruction = first_instruction_for_reference_value(analysis, reference_value)
            source_node_id = script_instruction_node_id_for(
                scene_id,
                scene_object.get("index"),
                script_kind,
                instruction.get("offset") if isinstance(instruction, dict) else f"local:{occurrence_index}",
            )
            if source_node_id not in graph.nodes_by_id:
                graph.add_node(script_instruction_node(scene_asset, scene_object, script_kind, instruction or {"offset": f"local:{occurrence_index}", "mnemonic": "UNKNOWN"}))
            target_kind = str(link.get("kind") or "")
            edge_type = "REFERENCES_OBJECT"
            target_node_id = scene_object_node_id_for(scene_id, link.get("object_index", reference_value))
            if target_kind == "waypoint":
                edge_type = "REFERENCES_WAYPOINT"
                target_node_id = waypoint_node_id_for(scene_id, link.get("waypoint_index", reference_value))
            elif target_kind == "zone":
                edge_type = "CONTROLS_ZONE"
                target_node_id = scene_zone_node_id_for(scene_id, link.get("zone_index", reference_value))
            if target_node_id not in graph.nodes_by_id:
                missing_id = f"{scene_id}#{target_kind or 'local'}:{reference_value}"
                target_node_id = missing_node_id_for(missing_id)
                graph.add_node(missing_target_node(missing_id, link, target_kind or "script_local", owner_node_id=source_node_id, resolution_state="outside_table"))
            graph.add_edge(
                {
                    "type": edge_type,
                    "from": source_node_id,
                    "to": target_node_id,
                    "relationship": edge_type.lower().replace("_", " "),
                    "inverse": "referenced by script instruction",
                    "cardinalityFromSource": "0..n",
                    "cardinalityFromTarget": "0..n",
                    "proofScope": "script_structure",
                    "evidenceStatus": "source_backed" if link.get("target_available") else "unknown",
                    "sourceRule": "Script operand semantics reference scene-local object, zone, or waypoint evidence.",
                    "sourceField": f"ScriptAnalysis.local_links.{reference_key}",
                    "indexRule": "Scene-local operands address zero-based object, zone, or T_TRACK waypoint indexes.",
                    "selectable": True,
                    "ownerNodeId": source_node_id,
                    "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].script.{script_kind}.local_links[{occurrence_index}]",
                    "sourceOffset": instruction.get("offset") if isinstance(instruction, dict) and isinstance(instruction.get("offset"), int) else None,
                    "rawReference": reference_value,
                    "resolverKind": f"script_local_{target_kind}",
                }
            )


def add_scene_script_control_flow_edges(graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    for script_kind, analysis in scene_object_scripts(scene_object):
        for occurrence_index, link in enumerate(analysis.get("control_flow_links") or []):
            if not isinstance(link, dict):
                continue
            source_offset = link.get("source_offset")
            target_offset = link.get("target_offset")
            source_node_id = script_instruction_node_id_for(scene_id, scene_object.get("index"), script_kind, source_offset)
            if source_node_id not in graph.nodes_by_id:
                graph.add_node(script_instruction_node(scene_asset, scene_object, script_kind, instruction_from_control_link(link, source=True)))
            target_node_id = script_instruction_node_id_for(scene_id, scene_object.get("index"), script_kind, target_offset)
            if not link.get("target_found"):
                missing_id = f"{scene_id}#object:{scene_object.get('index')}#script:{script_kind}#offset:{target_offset}"
                target_node_id = missing_node_id_for(missing_id)
                graph.add_node(missing_target_node(missing_id, link, "script_instruction", owner_node_id=source_node_id, resolution_state="outside_script"))
            elif target_node_id not in graph.nodes_by_id:
                graph.add_node(script_instruction_node(scene_asset, scene_object, script_kind, instruction_from_control_link(link, source=False)))
            graph.add_edge(
                {
                    "type": "CONTROL_FLOW_TO",
                    "from": source_node_id,
                    "to": target_node_id,
                    "relationship": "control flow to",
                    "inverse": "control flow from",
                    "cardinalityFromSource": "0..n",
                    "cardinalityFromTarget": "0..n",
                    "proofScope": "script_structure",
                    "evidenceStatus": "decoded_only" if link.get("target_found") else "unknown",
                    "sourceRule": "Script operand branch/target offset decoded structurally; no execution path is implied.",
                    "sourceField": f"ScriptAnalysis.control_flow_links.{link.get('target_field')}",
                    "indexRule": "Control-flow target offsets are byte offsets inside the same decoded script.",
                    "selectable": True,
                    "ownerNodeId": source_node_id,
                    "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].script.{script_kind}.control_flow_links[{occurrence_index}]",
                    "sourceOffset": source_offset if isinstance(source_offset, int) else None,
                    "rawReference": target_offset,
                    "resolverKind": "script_control_flow",
                }
            )


def add_runtime_state_field_edges(graph: CatalogGraph, scene_asset: dict[str, Any], scene_object: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    for script_kind, analysis in scene_object_scripts(scene_object):
        for occurrence_index, field in enumerate(analysis.get("runtime_state_fields") or []):
            if not isinstance(field, dict):
                continue
            source_offset = field.get("source_offset")
            instruction_node_id = script_instruction_node_id_for(scene_id, scene_object.get("index"), script_kind, source_offset)
            if instruction_node_id not in graph.nodes_by_id:
                graph.add_node(script_instruction_node(scene_asset, scene_object, script_kind, instruction_from_runtime_field(field)))
            field_node_id = runtime_state_field_node_id_for(scene_id, scene_object.get("index"), script_kind, source_offset, field.get("field"))
            graph.add_node(runtime_state_field_node(scene_asset, scene_object, script_kind, field))
            for edge_type, relationship in (("OWNS_RUNTIME_FIELD", "owns runtime field"), ("MAY_MUTATE_FIELD", "may mutate field")):
                graph.add_edge(
                    {
                        "type": edge_type,
                        "from": instruction_node_id,
                        "to": field_node_id,
                        "relationship": relationship,
                        "inverse": "runtime field of instruction",
                        "cardinalityFromSource": "0..n",
                        "cardinalityFromTarget": "1",
                        "proofScope": "script_structure",
                        "evidenceStatus": "source_backed",
                        "sourceRule": field.get("source") or "classic script runtime operand field evidence",
                        "sourceField": f"ScriptAnalysis.runtime_state_fields.{field.get('field')}",
                        "indexRule": "Runtime-mutable field stable id uses owner script, instruction offset, and field name.",
                        "selectable": True,
                        "ownerNodeId": instruction_node_id,
                        "sourcePath": f"{scene_id}.object[{scene_object.get('index')}].script.{script_kind}.runtime_state_fields[{occurrence_index}]",
                        "sourceOffset": source_offset if isinstance(source_offset, int) else None,
                        "rawReference": field.get("initial_hex", field.get("initial_value")),
                        "resolverKind": "runtime_state_field",
                    }
                )


def add_scene_patch_edges(graph: CatalogGraph, scene_asset: dict[str, Any]) -> None:
    scene_id = str(scene_asset.get("id"))
    scene_node_id = scene_node_id_for(scene_id)
    recon = ((scene_asset.get("stats") or {}).get("reconnaissance") or {})
    for patch in recon.get("patches") or []:
        if not isinstance(patch, dict):
            continue
        patch_node_id = patch_record_node_id_for(scene_id, patch.get("index"))
        graph.add_node(patch_record_node(scene_asset, patch))
        graph.add_edge(
            {
                "type": "HAS_PATCH",
                "from": scene_node_id,
                "to": patch_node_id,
                "relationship": "has patch record",
                "inverse": "patch of scene",
                "cardinalityFromSource": "0..n",
                "cardinalityFromTarget": "1",
                "proofScope": "decoded_payload",
                "evidenceStatus": "decoded_only",
                "sourceRule": "SCENE.HQR patch table decoded from scene payload",
                "sourceField": "SceneStats.reconnaissance.patches",
                "indexRule": "Patch index is zero-based within the scene patch table.",
                "selectable": True,
                "ownerNodeId": scene_node_id,
                "sourcePath": f"{scene_id}.patches[{patch.get('index')}]",
                "sourceOffset": patch.get("offset") if isinstance(patch.get("offset"), int) else None,
                "rawReference": patch.get("target_offset"),
                "resolverKind": "scene_patch_table",
            }
        )
        target = patch.get("target") if isinstance(patch.get("target"), dict) else {}
        object_index = object_index_from_owner(target.get("owner"))
        script_kind = str(target.get("kind") or "unknown")
        instruction_offset = target.get("instruction_offset")
        if object_index is None or not isinstance(instruction_offset, int):
            missing_id = f"{scene_id}#patch:{patch.get('index')}#target:{patch.get('target_offset')}"
            instruction_node_id = missing_node_id_for(missing_id)
            graph.add_node(missing_target_node(missing_id, patch, "script_instruction", owner_node_id=patch_node_id, resolution_state="outside_script"))
        else:
            instruction_node_id = script_instruction_node_id_for(scene_id, object_index, script_kind, instruction_offset)
            if instruction_node_id not in graph.nodes_by_id:
                graph.add_node(script_instruction_node(scene_asset, {"index": object_index}, script_kind, instruction_from_patch_target(target)))
        graph.add_edge(
            {
                "type": "PATCHES_INSTRUCTION",
                "from": patch_node_id,
                "to": instruction_node_id,
                "relationship": "patches instruction",
                "inverse": "instruction patched by",
                "cardinalityFromSource": "0..1",
                "cardinalityFromTarget": "0..n",
                "proofScope": "script_structure",
                "evidenceStatus": "decoded_only" if target.get("instruction_found") else "unknown",
                "sourceRule": "Patch target offset resolved to containing script instruction where possible.",
                "sourceField": "ScenePatch.target_offset",
                "indexRule": "Patch target offset is absolute inside the SCENE.HQR payload and is mapped to script-relative offset.",
                "selectable": True,
                "ownerNodeId": patch_node_id,
                "sourcePath": f"{scene_id}.patches[{patch.get('index')}].target",
                "sourceOffset": patch.get("offset") if isinstance(patch.get("offset"), int) else None,
                "rawReference": patch.get("target_offset"),
                "resolverKind": "scene_patch_instruction",
            }
        )
        field_name = target.get("patched_field")
        if object_index is None or not field_name:
            continue
        field_node_id = runtime_state_field_node_id_for(scene_id, object_index, script_kind, instruction_offset, field_name)
        if field_node_id not in graph.nodes_by_id:
            graph.add_node(runtime_state_field_node(scene_asset, {"index": object_index}, script_kind, runtime_field_from_patch_target(target)))
        graph.add_edge(
            {
                "type": "PATCHES_FIELD",
                "from": patch_node_id,
                "to": field_node_id,
                "relationship": "patches field",
                "inverse": "field patched by",
                "cardinalityFromSource": "0..1",
                "cardinalityFromTarget": "0..n",
                "proofScope": "script_structure",
                "evidenceStatus": "source_backed",
                "sourceRule": "Patch target byte maps to opcode or decoded operand field.",
                "sourceField": f"ScenePatch.target.{field_name}",
                "indexRule": "Patched field identity uses containing instruction and decoded operand field span.",
                "selectable": True,
                "ownerNodeId": patch_node_id,
                "sourcePath": f"{scene_id}.patches[{patch.get('index')}].field",
                "sourceOffset": patch.get("offset") if isinstance(patch.get("offset"), int) else None,
                "rawReference": patch.get("target_offset"),
                "resolverKind": "scene_patch_field",
            }
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
    object_node_id = scene_object_node_id_for(str(scene_asset.get("id")), scene_object.get("index"))
    for edge_id in graph.outgoing_by_node_id.get(object_node_id, []):
        edge = graph.edges_by_id.get(edge_id, {})
        if edge.get("type") == "HAS_FILE3D_RECORD" and edge.get("to") == node_id:
            return node_id
    graph.add_edge(
        {
            "type": "HAS_FILE3D_RECORD",
            "from": object_node_id,
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
                    missing_target_node(
                        frame_asset_id,
                        {"asset_id": frame_asset_id, "status": "empty_or_undecoded_hqr_slot"},
                        "asset",
                        owner_node_id=range_node_id,
                    )
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
        if edge.get("type") in set(USAGE_EDGE_TYPES.values()) | {"SCRIPT_REFERENCES", "APPLIES_GRM_FRAGMENT"}:
            target_id = stable_id_from_node_id(str(edge.get("to")))
            indexes["sceneUsagesByAssetId"][target_id].append(edge["id"])
        if edge.get("type") == "RANGE_CONTAINS_FRAME":
            range_id = stable_id_from_node_id(str(edge.get("from")))
            indexes["spritesByRange"][range_id].append(stable_id_from_node_id(str(edge.get("to"))))
    for node_id, node in graph.nodes_by_id.items():
        stable_id = str(node.get("stableId") or stable_id_from_node_id(node_id))
        if node.get("type") == "SceneZone":
            scene_id = str(node.get("sceneAssetId") or "")
            if scene_id:
                indexes["sceneZonesBySceneId"][scene_id].append(stable_id)
        elif node.get("type") == "Waypoint":
            scene_id = str(node.get("sceneAssetId") or "")
            if scene_id:
                indexes["waypointsBySceneId"][scene_id].append(stable_id)
        elif node.get("type") == "MissingTarget":
            indexes["missingTargetsByStableId"][stable_id] = node_id
        if node.get("selectable", True):
            indexes["selectionByNodeId"][node_id] = stable_id
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


def query_export_context(
    graph: CatalogGraph,
    stable_id: str,
    proof_scope: str,
    selected_edge_id: str | None = None,
) -> dict[str, Any]:
    usage_records = query_asset_usage_records(graph, stable_id)["usageRecords"]
    relationship_proof_filter = proof_scope if proof_scope in {
        "decoded_payload",
        "classic_source_rule",
        "scene_object_state",
        "script_reference",
        "script_structure",
        "frontend_compatibility_rule",
        "runtime_live_proof",
        "port_implication",
        "export_manifest",
        "unknown",
    } else None
    filtered_usage_records = [
        record for record in usage_records if relationship_proof_filter is None or record.get("proofScope") == relationship_proof_filter
    ]
    if selected_edge_id:
        filtered_usage_records = [
            record
            for record in filtered_usage_records
            if record.get("graphEdgeId") == selected_edge_id or record.get("selectedEdgeId") == selected_edge_id
        ]
    direct_records = [record for record in filtered_usage_records if record.get("proofScope") == "scene_object_state"]
    script_records = [record for record in filtered_usage_records if record.get("proofScope") == "script_reference"]
    scene_indices = sorted(
        {
            record["scene_index"]
            for record in filtered_usage_records
            if isinstance(record.get("scene_index"), int)
        }
    )
    evidence_statuses = sorted(
        {
            str(record.get("evidenceStatus"))
            for record in filtered_usage_records
            if record.get("evidenceStatus")
        }
    )
    source_rules = sorted(
        {
            str(record.get("sourceRule"))
            for record in filtered_usage_records
            if record.get("sourceRule")
        }
    )
    source_fields = sorted(
        {
            str(record.get("sourceField"))
            for record in filtered_usage_records
            if record.get("sourceField")
        }
    )
    index_rules = sorted(
        {
            str(record.get("indexRule"))
            for record in filtered_usage_records
            if record.get("indexRule")
        }
    )
    selected_edge_ids = sorted(
        {
            str(record.get("graphEdgeId") or record.get("selectedEdgeId"))
            for record in filtered_usage_records
            if record.get("graphEdgeId") or record.get("selectedEdgeId")
        }
    )
    return {
        "schema": "catalog_graph.export_context.v0",
        "stable_id": stable_id,
        "proof_scope": proof_scope,
        "relationship_proof_filter": relationship_proof_filter,
        "scene_usage_count": len(direct_records),
        "relationship_link_count": len(filtered_usage_records),
        "direct_scene_object_usage_count": len(direct_records),
        "script_reference_count": len(script_records),
        "scene_indices": scene_indices,
        "proof_scopes": sorted({str(record.get("proofScope")) for record in filtered_usage_records if record.get("proofScope")}),
        "evidence_statuses": evidence_statuses,
        "source_rules": source_rules,
        "source_fields": source_fields,
        "index_rules": index_rules,
        "selected_edge_ids": selected_edge_ids,
        "usage_records": filtered_usage_records,
    }


def usage_record_from_edge(graph: CatalogGraph, edge: dict[str, Any]) -> dict[str, Any] | None:
    proof_scope = edge.get("proofScope")
    if proof_scope == "script_reference":
        reference_node = graph.nodes_by_id.get(str(edge.get("from")), {})
        graph_link_node = reference_node
        source = reference_node.get("source") if isinstance(reference_node.get("source"), dict) else {}
        scene_id = source.get("scene_asset_id")
        object_index = source.get("object_index")
        scene_object = graph.nodes_by_id.get(scene_object_node_id_for(str(scene_id), object_index), {})
        usage_kind = edge.get("usageKind") or edge.get("type")
        kind = f"script_{usage_kind}" if usage_kind else "script_reference"
    else:
        scene_object = graph.nodes_by_id.get(str(edge.get("from")), {})
        graph_link_node = scene_object
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
        "edgeId": edge.get("id"),
        "sourceEvidenceId": edge.get("sourceEvidenceId"),
        "occurrenceOrdinal": edge.get("occurrenceOrdinal"),
        "ownerNodeId": edge.get("ownerNodeId"),
        "sourcePath": edge.get("sourcePath"),
        "sourceOffset": edge.get("sourceOffset"),
        "rawReference": edge.get("rawReference"),
        "targetStableId": edge.get("targetStableId"),
        "resolverKind": edge.get("resolverKind"),
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
        "graphLinkStableId": graph_link_node.get("stableId") or stable_id_from_node_id(str(edge.get("from"))),
        "graphEdgeId": edge.get("id"),
        "selectedEdgeId": edge.get("id"),
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


def query_zone(graph: CatalogGraph, scene_id: str, zone_index: str) -> dict[str, Any]:
    node_id = scene_zone_node_id_for(scene_id, parse_object_index(zone_index))
    return {
        "schema": "catalog_graph.zone.v0",
        "sceneId": scene_id,
        "zoneIndex": parse_object_index(zone_index),
        "node": graph.nodes_by_id.get(node_id),
        "edges": graph.node_edges(node_id, "both"),
        "consumerRoundTrip": consumer_round_trip_for_node(graph, node_id),
    }


def query_waypoint(graph: CatalogGraph, scene_id: str, waypoint_index: str) -> dict[str, Any]:
    node_id = waypoint_node_id_for(scene_id, parse_object_index(waypoint_index))
    return {
        "schema": "catalog_graph.waypoint.v0",
        "sceneId": scene_id,
        "waypointIndex": parse_object_index(waypoint_index),
        "node": graph.nodes_by_id.get(node_id),
        "edges": graph.node_edges(node_id, "both"),
        "consumerRoundTrip": consumer_round_trip_for_node(graph, node_id),
    }


def query_script_instruction(
    graph: CatalogGraph,
    scene_id: str,
    object_index: str,
    script_kind: str,
    offset: str,
) -> dict[str, Any]:
    node_id = script_instruction_node_id_for(
        scene_id,
        parse_object_index(object_index),
        script_kind,
        parse_object_index(offset),
    )
    return {
        "schema": "catalog_graph.script_instruction.v0",
        "sceneId": scene_id,
        "objectIndex": parse_object_index(object_index),
        "scriptKind": script_kind,
        "offset": parse_object_index(offset),
        "node": graph.nodes_by_id.get(node_id),
        "edges": graph.node_edges(node_id, "both"),
        "consumerRoundTrip": consumer_round_trip_for_node(graph, node_id),
    }


def query_selection(graph: CatalogGraph, stable_id: str) -> dict[str, Any]:
    if stable_id in graph.edges_by_id:
        return {
            "schema": "catalog_graph.selection.v0",
            "id": stable_id,
            "found": True,
            "selection": edge_selection_projection(graph, graph.edges_by_id[stable_id]),
        }
    node_id = resolve_node_id(graph, stable_id)
    node = graph.nodes_by_id.get(node_id)
    return {
        "schema": "catalog_graph.selection.v0",
        "id": stable_id,
        "found": node is not None,
        "selection": selection_projection_for_node(graph, node) if node is not None else None,
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


def catalog_node_selection_projection(graph: CatalogGraph) -> dict[str, dict[str, Any]]:
    selections: dict[str, dict[str, Any]] = {}
    for node in graph.sorted_nodes():
        if not node.get("selectable", True):
            continue
        stable_id = str(node.get("stableId") or stable_id_from_node_id(str(node.get("id"))))
        selections[stable_id] = selection_projection_for_node(graph, node)
    for edge in graph.sorted_edges():
        if not edge.get("selectable", False):
            continue
        edge_id = str(edge.get("id"))
        selections[edge_id] = edge_selection_projection(graph, edge)
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
        "edgeId": edge.get("id"),
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
        "sourceEvidenceId": edge.get("sourceEvidenceId"),
        "occurrenceOrdinal": edge.get("occurrenceOrdinal"),
        "ownerNodeId": edge.get("ownerNodeId"),
        "sourcePath": edge.get("sourcePath"),
        "sourceOffset": edge.get("sourceOffset"),
        "rawReference": edge.get("rawReference"),
        "targetStableId": edge.get("targetStableId"),
        "resolverKind": edge.get("resolverKind"),
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
                "edgeId": edge.get("edgeId") or edge.get("id"),
                "stableId": target.get("stableId"),
                "label": target.get("label") or target.get("stableId"),
                "targetType": target.get("type"),
                "targetAvailable": target.get("type") != "MissingTarget",
                "proofScope": edge.get("proofScope"),
                "evidenceStatus": edge.get("evidenceStatus"),
                "sourceRule": edge.get("sourceRule"),
                "sourceField": edge.get("sourceField"),
                "indexRule": edge.get("indexRule"),
                "sourceEvidenceId": edge.get("sourceEvidenceId"),
                "occurrenceOrdinal": edge.get("occurrenceOrdinal"),
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
    usage_records = query_asset_usage_records(graph, stable_id)["usageRecords"]
    visible_usage_link_ids = {str(link.get("stableId")) for link in usage_links[:48]}
    visible_usage_edge_ids = {str(link.get("edgeId")) for link in usage_links[:48] if link.get("edgeId")}
    visible_usage_records = [
        record
        for record in usage_records
        if str(record.get("graphEdgeId")) in visible_usage_edge_ids
        or str(record.get("selectedEdgeId")) in visible_usage_edge_ids
        or str(record.get("graphLinkStableId")) in visible_usage_link_ids
        or f"{record.get('scene_asset_id')}#object:{record.get('object_index')}" in visible_usage_link_ids
    ]
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
        "usageRecords": visible_usage_records,
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


def selection_projection_for_node(graph: CatalogGraph, node: dict[str, Any]) -> dict[str, Any]:
    if node.get("type") == "Asset":
        return asset_selection_projection(graph, node)
    node_id = str(node.get("id"))
    selection_kind_by_node_type = {
        "ResourceRecord": "resource_record",
        "SceneObject": "scene_object",
        "SceneZone": "scene_zone",
        "Waypoint": "waypoint",
        "ScriptInstruction": "script_instruction",
        "PatchRecord": "patch_record",
        "RuntimeStateField": "runtime_state_field",
    }
    return {
        "schema": "catalog_graph.selection_projection.v0",
        "kind": selection_kind_by_node_type.get(str(node.get("type")), str(node.get("type") or "node").lower()),
        "nodeId": node_id,
        "stableId": node.get("stableId") or stable_id_from_node_id(node_id),
        "label": node.get("label") or stable_id_from_node_id(node_id),
        "source": node.get("source") or {},
        "provenance": str((node.get("source") or {}).get("source") or node.get("type") or "catalog graph node"),
        "evidenceStatus": node.get("evidenceStatus") or "unknown",
        "links": [
            {
                "kind": "graph_edge",
                "edgeId": edge.get("id"),
                "stableId": edge.get("id"),
                "label": edge.get("relationship") or edge.get("type"),
                "proofScope": edge.get("proofScope"),
                "evidenceStatus": edge.get("evidenceStatus"),
                "sourceRule": edge.get("sourceRule"),
                "sourceField": edge.get("sourceField"),
                "indexRule": edge.get("indexRule"),
            }
            for edge in graph.node_edges(node_id, "both")[:12]
        ],
        "usageRecords": [],
        "unknowns": [] if node.get("type") != "MissingTarget" else [str(node.get("missingReason") or node.get("resolutionState") or "missing target")],
        "previewActions": [],
        "exportActions": [],
        "exportCapability": {"exportable": False, "source": "catalog_graph.selection_projection.v0"},
        "inspectorRoute": inspector_route_for_graph_node(node),
        "workspaceSuggestion": workspace_for_node(node),
        "facets": {
            "graphNodeId": node_id,
            "nodeType": node.get("type"),
            "sceneAssetId": node.get("sceneAssetId"),
        },
    }


def edge_selection_projection(graph: CatalogGraph, edge: dict[str, Any]) -> dict[str, Any]:
    edge_id = str(edge.get("id"))
    source = relationship_endpoint_projection(graph, str(edge.get("from")))
    target = relationship_endpoint_projection(graph, str(edge.get("to")))
    target_node = graph.nodes_by_id.get(str(edge.get("to")), {})
    target_asset_id = target.get("stableId") if target.get("type") == "Asset" else None
    export_actions = []
    export_capability = {"exportable": False, "source": "catalog_graph.edge_selection_projection.v0"}
    if target_asset_id and is_exportable_asset_node(target_node):
        export_actions.append(
            {
                "id": "export_catalog_graph_edge",
                "label": "Export edge evidence bundle",
                "targetAssetId": target_asset_id,
                "selectedEdgeId": edge_id,
            }
        )
        export_capability = {
            "exportable": True,
            "source": "catalog_graph.edge_selection_projection.v0",
        }
    return {
        "schema": "catalog_graph.selection_projection.v0",
        "kind": "graph_edge",
        "edgeId": edge_id,
        "nodeId": edge.get("ownerNodeId") or edge.get("from"),
        "stableId": edge_id,
        "label": edge.get("relationship") or edge.get("type") or edge_id,
        "source": {
            "sourcePath": edge.get("sourcePath"),
            "sourceOffset": edge.get("sourceOffset"),
        },
        "provenance": edge.get("sourceRule") or edge.get("sourceEvidenceId") or edge_id,
        "evidenceStatus": edge.get("evidenceStatus") or "unknown",
        "links": [
            {
                "kind": "graph_node",
                "edgeId": edge_id,
                "stableId": endpoint.get("stableId"),
                "label": endpoint.get("label"),
                "proofScope": edge.get("proofScope"),
                "evidenceStatus": edge.get("evidenceStatus"),
                "sourceRule": edge.get("sourceRule"),
                "sourceField": edge.get("sourceField"),
                "indexRule": edge.get("indexRule"),
                "sourceEvidenceId": edge.get("sourceEvidenceId"),
                "occurrenceOrdinal": edge.get("occurrenceOrdinal"),
                "ownerNodeId": edge.get("ownerNodeId"),
                "sourcePath": edge.get("sourcePath"),
                "sourceOffset": edge.get("sourceOffset"),
                "rawReference": edge.get("rawReference"),
                "targetStableId": edge.get("targetStableId"),
                "resolverKind": edge.get("resolverKind"),
            }
            for endpoint in (source, target)
        ],
        "unknowns": [],
        "previewActions": [],
        "exportActions": export_actions,
        "exportCapability": export_capability,
        "inspectorRoute": None,
        "workspaceSuggestion": "entity",
        "facets": {
            "graphEdgeId": edge_id,
            "selectedEdgeId": edge_id,
            "proofScope": edge.get("proofScope"),
            "sourceRule": edge.get("sourceRule"),
            "sourceField": edge.get("sourceField"),
            "indexRule": edge.get("indexRule"),
            "sourceEvidenceId": edge.get("sourceEvidenceId"),
            "occurrenceOrdinal": edge.get("occurrenceOrdinal"),
            "ownerNodeId": edge.get("ownerNodeId"),
            "sourcePath": edge.get("sourcePath"),
            "sourceOffset": edge.get("sourceOffset"),
            "rawReference": edge.get("rawReference"),
            "targetStableId": edge.get("targetStableId"),
            "resolverKind": edge.get("resolverKind"),
            "targetAssetId": target_asset_id,
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
    return graph_asset_export_route(node) is not None


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


def inspector_route_for_graph_node(node: dict[str, Any]) -> str | None:
    if node.get("type") == "SceneZone":
        return "scene_zone"
    if node.get("type") == "Waypoint":
        return "waypoint"
    if node.get("type") == "ScriptInstruction":
        return "script_instruction"
    if node.get("type") == "PatchRecord":
        return "patch_record"
    if node.get("type") == "RuntimeStateField":
        return "runtime_state_field"
    if node.get("type") == "SceneObject":
        return "scene_object"
    return inspector_route_for_asset_node(node) if node.get("type") == "Asset" else None


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
                "edgeId": edge.get("id"),
                "stableId": stable_id,
                "label": source_node.get("label") or stable_id,
                "proofScope": edge.get("proofScope"),
                "evidenceStatus": edge.get("evidenceStatus"),
                "sourceRule": edge.get("sourceRule"),
                "sourceField": edge.get("sourceField"),
                "indexRule": edge.get("indexRule"),
                "sourceEvidenceId": edge.get("sourceEvidenceId"),
                "occurrenceOrdinal": edge.get("occurrenceOrdinal"),
                "ownerNodeId": edge.get("ownerNodeId"),
                "sourcePath": edge.get("sourcePath"),
                "sourceOffset": edge.get("sourceOffset"),
                "rawReference": edge.get("rawReference"),
                "targetStableId": edge.get("targetStableId"),
                "resolverKind": edge.get("resolverKind"),
            }
        )
    return links


def query_export(graph: CatalogGraph, stable_id: str | None) -> dict[str, Any]:
    if not stable_id:
        return export_graph_document(graph)
    if stable_id in graph.edges_by_id:
        edge = graph.edges_by_id[stable_id]
        node_ids = {str(edge.get("from")), str(edge.get("to"))}
        edge_ids = {stable_id}
        for node_id in list(node_ids):
            for incident in graph.node_edges(node_id, "both"):
                edge_ids.add(str(incident.get("id")))
        return {
            "schema": "catalog_graph.subgraph.v0",
            "root": stable_id,
            "rootKind": "edge",
            "selectedEdgeId": stable_id,
            "nodes": [graph.nodes_by_id[node_id] for node_id in sorted(node_ids) if node_id in graph.nodes_by_id],
            "edges": [graph.edges_by_id[edge_id] for edge_id in sorted(edge_ids) if edge_id in graph.edges_by_id],
        }
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
        "rootKind": "node",
        "nodes": [graph.nodes_by_id[node_id] for node_id in sorted(node_ids) if node_id in graph.nodes_by_id],
        "edges": [graph.edges_by_id[edge_id] for edge_id in sorted(edge_ids)],
    }


def query_search(
    graph: CatalogGraph,
    q: str,
    node_types: list[str] | None = None,
    edge_types: list[str] | None = None,
    proof_scopes: list[str] | None = None,
    evidence_statuses: list[str] | None = None,
    include_edges: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    needle = q.lower().strip()
    node_type_set = set(node_types or [])
    edge_type_set = set(edge_types or [])
    proof_scope_set = set(proof_scopes or [])
    evidence_status_set = set(evidence_statuses or [])
    results: list[dict[str, Any]] = []
    for node in graph.sorted_nodes():
        if node_type_set and str(node.get("type")) not in node_type_set:
            continue
        if evidence_status_set and str(node.get("evidenceStatus")) not in evidence_status_set:
            continue
        text = str(node.get("searchText") or search_text(node))
        if needle and needle not in text:
            continue
        results.append(search_node_result(graph, node))
        if len(results) >= limit:
            break
    if include_edges and len(results) < limit:
        for edge in graph.sorted_edges():
            if edge_type_set and str(edge.get("type")) not in edge_type_set:
                continue
            if proof_scope_set and str(edge.get("proofScope")) not in proof_scope_set:
                continue
            if evidence_status_set and str(edge.get("evidenceStatus")) not in evidence_status_set:
                continue
            text = str(edge.get("searchText") or search_text(edge))
            if needle and needle not in text:
                continue
            results.append(search_edge_result(graph, edge))
            if len(results) >= limit:
                break
    return {
        "schema": "catalog_graph.search.v0",
        "query": {
            "q": q,
            "nodeTypes": node_types or [],
            "edgeTypes": edge_types or [],
            "proofScopes": proof_scopes or [],
            "evidenceStatuses": evidence_statuses or [],
            "includeEdges": include_edges,
            "limit": limit,
        },
        "results": results,
    }


def search_node_result(graph: CatalogGraph, node: dict[str, Any]) -> dict[str, Any]:
    node_id = str(node.get("id"))
    return {
        "kind": "node",
        "nodeId": node_id,
        "stableId": node.get("stableId") or stable_id_from_node_id(node_id),
        "label": node.get("label") or stable_id_from_node_id(node_id),
        "nodeType": node.get("type"),
        "proofScope": None,
        "evidenceStatus": node.get("evidenceStatus"),
        "sourceRule": None,
        "sourceField": None,
        "indexRule": None,
        "sourceEvidenceId": None,
        "targetAvailable": node.get("type") != "MissingTarget",
        "snippet": node.get("searchText") or search_text(node),
        "selectionProjection": selection_projection_for_node(graph, node),
    }


def search_edge_result(graph: CatalogGraph, edge: dict[str, Any]) -> dict[str, Any]:
    target = relationship_endpoint_projection(graph, str(edge.get("to")))
    return {
        "kind": "edge",
        "edgeId": edge.get("id"),
        "stableId": edge.get("id"),
        "label": edge.get("relationship") or edge.get("type"),
        "edgeType": edge.get("type"),
        "proofScope": edge.get("proofScope"),
        "evidenceStatus": edge.get("evidenceStatus"),
        "sourceRule": edge.get("sourceRule"),
        "sourceField": edge.get("sourceField"),
        "indexRule": edge.get("indexRule"),
        "sourceEvidenceId": edge.get("sourceEvidenceId"),
        "targetAvailable": target.get("type") != "MissingTarget",
        "snippet": edge.get("searchText") or search_text(edge),
        "selectionProjection": edge_selection_projection(graph, edge),
    }


def query_missing_targets(graph: CatalogGraph) -> dict[str, Any]:
    nodes = [node for node in graph.sorted_nodes() if node.get("type") == "MissingTarget"]
    return {"schema": "catalog_graph.missing_targets.v0", "missingTargets": nodes}


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
    if node.get("type") in {"SceneZone", "Waypoint", "ScriptBlock", "ScriptInstruction", "PatchRecord", "RuntimeStateField"}:
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
    for scene_object in recon.get("objects") or []:
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


def iter_scene_script_owners(scene_asset: dict[str, Any]) -> Iterable[dict[str, Any]]:
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
    for scene_object in recon.get("objects") or []:
        if isinstance(scene_object, dict):
            yield scene_object


def scene_object_scripts(scene_object: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for script_kind, script_key in (("track", "track_script_analysis"), ("life", "life_script_analysis")):
        analysis = scene_object.get(script_key)
        if isinstance(analysis, dict) and analysis.get("status") != "missing":
            yield script_kind, analysis


def scene_zone_node(scene_asset: dict[str, Any], zone: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    zone_index = zone.get("index")
    runtime = zone.get("runtime") if isinstance(zone.get("runtime"), dict) else {}
    info = list(zone.get("info") or [])
    return {
        "id": scene_zone_node_id_for(scene_id, zone_index),
        "type": "SceneZone",
        "label": f"{scene_asset.get('label') or scene_id} zone {zone_index} ({zone.get('type_name') or zone.get('type')})",
        "stableId": f"{scene_id}#zone:{zone_index}",
        "sceneAssetId": scene_id,
        "zoneIndex": zone_index,
        "zoneType": zone.get("type"),
        "zoneTypeName": zone.get("type_name"),
        "zoneNum": zone.get("value"),
        "value": zone.get("value"),
        "bounds": {"start": zone.get("start"), "end": zone.get("end")},
        "serializedInfo": {f"Info{index}": value for index, value in enumerate(info)},
        "loadState": zone.get("load_rules"),
        "contractKinds": zone_contract_kinds(runtime),
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "zone_index": zone_index,
            "offset": zone.get("offset"),
        },
        "evidenceStatus": "decoded_only",
    }


def waypoint_node(scene_asset: dict[str, Any], waypoint: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    waypoint_index = waypoint.get("index")
    return {
        "id": waypoint_node_id_for(scene_id, waypoint_index),
        "type": "Waypoint",
        "label": f"{scene_asset.get('label') or scene_id} waypoint {waypoint_index}",
        "stableId": f"{scene_id}#waypoint:{waypoint_index}",
        "sceneAssetId": scene_id,
        "waypointIndex": waypoint_index,
        "position": waypoint.get("position"),
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "waypoint_index": waypoint_index,
            "offset": waypoint.get("offset"),
        },
        "evidenceStatus": "decoded_only",
    }


def script_block_node(
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    script_kind: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    object_index = scene_object.get("index")
    return {
        "id": script_block_node_id_for(scene_id, object_index, script_kind),
        "type": "ScriptBlock",
        "label": f"{scene_asset.get('label') or scene_id} object {object_index} {script_kind} script",
        "stableId": f"{scene_id}#object:{object_index}#script:{script_kind}",
        "sceneAssetId": scene_id,
        "objectIndex": object_index,
        "scriptKind": script_kind,
        "byteLength": analysis.get("byte_length"),
        "instructionCount": analysis.get("instruction_count"),
        "decodedBytes": analysis.get("decoded_bytes"),
        "sha256": analysis.get("sha256"),
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "object_index": object_index,
            "script_kind": script_kind,
            "script_offset": scene_object.get(f"{script_kind}_script_offset"),
        },
        "evidenceStatus": "decoded_only",
    }


def script_instruction_node(
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    script_kind: str,
    instruction: dict[str, Any],
) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    object_index = scene_object.get("index")
    offset = instruction.get("offset")
    return {
        "id": script_instruction_node_id_for(scene_id, object_index, script_kind, offset),
        "type": "ScriptInstruction",
        "label": f"{scene_asset.get('label') or scene_id} object {object_index} {script_kind} @{offset} {instruction.get('mnemonic') or instruction.get('opcode') or 'UNKNOWN'}",
        "stableId": f"{scene_id}#object:{object_index}#script:{script_kind}#offset:{offset}",
        "sceneAssetId": scene_id,
        "objectIndex": object_index,
        "scriptKind": script_kind,
        "offset": offset,
        "opcode": instruction.get("opcode"),
        "mnemonic": instruction.get("mnemonic") or instruction.get("source_opcode") or instruction.get("target_opcode"),
        "byteLength": instruction.get("byte_length") or instruction.get("target_containing_byte_length"),
        "operandHex": instruction.get("operand_hex"),
        "behaviorCategory": instruction.get("behavior_category") or instruction.get("source_behavior_category") or instruction.get("target_behavior_category"),
        "decodedOperandSemantics": instruction.get("operand_semantics"),
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "object_index": object_index,
            "script_kind": script_kind,
            "offset": offset,
        },
        "evidenceStatus": "decoded_only",
    }


def runtime_state_field_node(
    scene_asset: dict[str, Any],
    scene_object: dict[str, Any],
    script_kind: str,
    field: dict[str, Any],
) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    object_index = scene_object.get("index")
    source_offset = field.get("source_offset")
    field_name = field.get("field") or field.get("patched_field")
    return {
        "id": runtime_state_field_node_id_for(scene_id, object_index, script_kind, source_offset, field_name),
        "type": "RuntimeStateField",
        "label": f"{scene_id} object {object_index} {script_kind} @{source_offset} field {field_name}",
        "stableId": f"{scene_id}#object:{object_index}#script:{script_kind}#offset:{source_offset}#field:{field_name}",
        "sceneAssetId": scene_id,
        "objectIndex": object_index,
        "scriptKind": script_kind,
        "fieldName": field_name,
        "sourceOffset": source_offset,
        "operandOffset": field.get("operand_offset"),
        "size": field.get("size") or field.get("patched_field_size"),
        "initialValue": field.get("initial_value"),
        "initialHex": field.get("initial_hex"),
        "fieldSource": field.get("source") or field.get("patched_field_source"),
        "mutableByRuntime": True,
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "object_index": object_index,
            "script_kind": script_kind,
            "source_offset": source_offset,
        },
        "evidenceStatus": "source_backed",
    }


def patch_record_node(scene_asset: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(scene_asset.get("id"))
    patch_index = patch.get("index")
    return {
        "id": patch_record_node_id_for(scene_id, patch_index),
        "type": "PatchRecord",
        "label": f"{scene_asset.get('label') or scene_id} patch {patch_index}",
        "stableId": f"{scene_id}#patch:{patch_index}",
        "sceneAssetId": scene_id,
        "patchIndex": patch_index,
        "size": patch.get("size"),
        "targetOffset": patch.get("target_offset"),
        "target": patch.get("target"),
        "source": {
            "scene_asset_id": scene_id,
            "scene_entry_index": (scene_asset.get("source") or {}).get("entry_index"),
            "patch_index": patch_index,
            "offset": patch.get("offset"),
        },
        "evidenceStatus": "decoded_only",
    }


def missing_target_node(
    stable_id: str,
    source: dict[str, Any],
    target_kind: str,
    *,
    owner_node_id: str | None = None,
    resolution_state: str | None = None,
) -> dict[str, Any]:
    return {
        "id": missing_node_id_for(stable_id),
        "type": "MissingTarget",
        "label": f"Missing {stable_id}",
        "stableId": stable_id,
        "targetStableId": stable_id,
        "targetKind": target_kind,
        "resolutionState": resolution_state or resolution_state_for_missing_source(source),
        "rawReference": source.get("reference_value", source.get("sample_id", stable_id)),
        "ownerNodeId": owner_node_id,
        "resolverKind": source.get("kind") or target_kind,
        "candidateTargets": source.get("candidate_targets") or [],
        "absenceEvidenceStatus": absence_evidence_status_for_resolution_state(
            resolution_state or resolution_state_for_missing_source(source)
        ),
        "missingReason": source.get("missing_reason") or source.get("reason") or source.get("status"),
        "source": {"target": stable_id, "link": source},
        "evidenceStatus": "unknown",
    }


def zone_contract_kinds(runtime: dict[str, Any]) -> list[str]:
    kinds: list[str] = []
    effect = runtime.get("effect")
    if isinstance(effect, str) and effect and effect not in kinds:
        kinds.append(effect)
    for field in sorted(runtime):
        if field.endswith("_application"):
            kinds.append(field[: -len("_application")])
    return sorted(set(kinds))


def script_instructions_by_local_reference(analysis: dict[str, Any]) -> dict[tuple[str, Any], dict[str, Any]]:
    result: dict[tuple[str, Any], dict[str, Any]] = {}
    semantic_keys = {
        "object": ("object_id",),
        "waypoint": ("waypoint_id", "circle_waypoint_id"),
        "camera_zone": ("camera_zone_id",),
        "grm_zone": ("grm_zone_id",),
        "ladder_zone": ("ladder_zone_id",),
        "escalator_zone": ("escalator_zone_id",),
        "hit_zone": ("hit_zone_id",),
        "rail_zone": ("rail_zone_id",),
        "change_cube_control": ("zone_id", "change_cube_zone_id"),
    }
    for instruction in analysis.get("first_instructions") or []:
        if not isinstance(instruction, dict):
            continue
        semantics = instruction.get("operand_semantics") if isinstance(instruction.get("operand_semantics"), dict) else {}
        for reference_key, keys in semantic_keys.items():
            for key in keys:
                if key in semantics:
                    result.setdefault((reference_key, semantics.get(key)), instruction)
                    result.setdefault((reference_key.replace("_zone", ""), semantics.get(key)), instruction)
    return result


def first_instruction_for_reference_value(analysis: dict[str, Any], reference_value: Any) -> dict[str, Any] | None:
    for instruction in analysis.get("first_instructions") or []:
        if not isinstance(instruction, dict):
            continue
        semantics = instruction.get("operand_semantics")
        if isinstance(semantics, dict) and reference_value in semantics.values():
            return instruction
    return None


def instruction_from_control_link(link: dict[str, Any], *, source: bool) -> dict[str, Any]:
    if source:
        return {
            "offset": link.get("source_offset"),
            "mnemonic": link.get("source_opcode"),
            "behavior_category": link.get("source_behavior_category"),
        }
    return {
        "offset": link.get("target_offset"),
        "mnemonic": link.get("target_opcode") or link.get("target_containing_opcode"),
        "behavior_category": link.get("target_behavior_category") or link.get("target_containing_behavior_category"),
        "byte_length": link.get("target_containing_byte_length"),
    }


def instruction_from_runtime_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "offset": field.get("source_offset"),
        "mnemonic": field.get("opcode"),
        "behavior_category": field.get("behavior_category"),
    }


def instruction_from_patch_target(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "offset": target.get("instruction_offset"),
        "mnemonic": target.get("instruction_opcode"),
        "behavior_category": target.get("instruction_behavior_category"),
    }


def runtime_field_from_patch_target(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_offset": target.get("instruction_offset"),
        "field": target.get("patched_field"),
        "operand_offset": target.get("operand_relative_offset"),
        "size": target.get("patched_field_size"),
        "source": target.get("patched_field_source"),
    }


def object_index_from_owner(owner: Any) -> int | None:
    if owner == "hero":
        return 0
    if isinstance(owner, str) and owner.startswith("object:"):
        try:
            return int(owner.split(":", 1)[1])
        except ValueError:
            return None
    if isinstance(owner, int) and not isinstance(owner, bool):
        return owner
    return None


def target_kind_for_usage(link_kind: str) -> str:
    if link_kind in {"sample", "ambience_sample", "script_sample_missing"}:
        return "sample"
    if link_kind in {"text", "zone_text"}:
        return "text"
    if link_kind == "video":
        return "video"
    if link_kind in {"body", "animation", "sprite"}:
        return "asset"
    if link_kind == "grm_fragment":
        return "background_resource"
    return "asset"


def resolution_state_for_missing_source(source: dict[str, Any]) -> str:
    status = str(source.get("status") or source.get("missing_reason") or source.get("reason") or "")
    if "outside" in status:
        return "outside_table"
    if "empty" in status:
        return "empty_archive_slot"
    if "undecoded" in status:
        return "undecoded_slot"
    if "name_not_found" in status or "not_found" in status:
        return "unresolved_name"
    if "not loaded" in status or "no_samples_archive_loaded" in status:
        return "not_loaded_archive"
    return "backend_unresolved"


def absence_evidence_status_for_missing_source(source: dict[str, Any]) -> str:
    return absence_evidence_status_for_resolution_state(resolution_state_for_missing_source(source))


def absence_evidence_status_for_resolution_state(resolution_state: str) -> str:
    if resolution_state in {"outside_table", "empty_archive_slot", "undecoded_slot"}:
        return "decoded_absent"
    if resolution_state == "not_loaded_archive":
        return "archive_not_loaded"
    if resolution_state == "intentionally_deferred_target":
        return "intentionally_deferred"
    return "unresolved"


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
        scene_id, rest = stable_id.split("#object:", 1)
        if "#script:" in rest:
            object_value, script_rest = rest.split("#script:", 1)
            if "#offset:" in script_rest:
                script_kind, offset = script_rest.split("#offset:", 1)
                if "#field:" in offset:
                    offset_value, field_name = offset.split("#field:", 1)
                    return runtime_state_field_node_id_for(scene_id, parse_object_index(object_value), script_kind, offset_value, field_name)
                return script_instruction_node_id_for(scene_id, parse_object_index(object_value), script_kind, offset)
            return script_block_node_id_for(scene_id, parse_object_index(object_value), script_rest)
        return scene_object_node_id_for(scene_id, parse_object_index(rest))
    if "#zone:" in stable_id:
        scene_id, zone_value = stable_id.split("#zone:", 1)
        return scene_zone_node_id_for(scene_id, parse_object_index(zone_value))
    if "#waypoint:" in stable_id:
        scene_id, waypoint_value = stable_id.split("#waypoint:", 1)
        return waypoint_node_id_for(scene_id, parse_object_index(waypoint_value))
    if "#patch:" in stable_id:
        scene_id, patch_value = stable_id.split("#patch:", 1)
        return patch_record_node_id_for(scene_id, parse_object_index(patch_value))
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


def scene_zone_node_id_for(scene_id: str, zone_index: Any) -> str:
    return f"scene-zone:{scene_id}:{zone_index}"


def waypoint_node_id_for(scene_id: str, waypoint_index: Any) -> str:
    return f"waypoint:{scene_id}:{waypoint_index}"


def script_block_node_id_for(scene_id: str, object_index: Any, script_kind: str) -> str:
    return f"script-block:{scene_id}:{object_index}:{script_kind}"


def script_instruction_node_id_for(scene_id: str, object_index: Any, script_kind: str, offset: Any) -> str:
    return f"script-instruction:{scene_id}:{object_index}:{script_kind}:{offset}"


def runtime_state_field_node_id_for(scene_id: str, object_index: Any, script_kind: str, offset: Any, field_name: Any) -> str:
    return f"runtime-state-field:{scene_id}:{object_index}:{script_kind}:{offset}:{field_name}"


def patch_record_node_id_for(scene_id: str, patch_index: Any) -> str:
    return f"patch-record:{scene_id}:{patch_index}"


def script_reference_node_id_for(scene_id: str, object_index: Any, link: dict[str, Any]) -> str:
    parts = [
        scene_id,
        str(object_index),
        str(link.get("script_kind") or "script"),
        str(link.get("source_offset") if link.get("source_offset") is not None else link.get("offset") or ""),
        str(link.get("occurrence_index") if link.get("occurrence_index") is not None else ""),
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
    if node_id.startswith("scene-zone:"):
        rest = node_id[len("scene-zone:") :]
        scene_id, zone_index = rest.rsplit(":", 1)
        return f"{scene_id}#zone:{zone_index}"
    if node_id.startswith("waypoint:"):
        rest = node_id[len("waypoint:") :]
        scene_id, waypoint_index = rest.rsplit(":", 1)
        return f"{scene_id}#waypoint:{waypoint_index}"
    if node_id.startswith("script-block:"):
        rest = node_id[len("script-block:") :]
        scene_id, object_index, script_kind = rest.rsplit(":", 2)
        return f"{scene_id}#object:{object_index}#script:{script_kind}"
    if node_id.startswith("script-instruction:"):
        rest = node_id[len("script-instruction:") :]
        scene_id, object_index, script_kind, offset = rest.rsplit(":", 3)
        return f"{scene_id}#object:{object_index}#script:{script_kind}#offset:{offset}"
    if node_id.startswith("runtime-state-field:"):
        rest = node_id[len("runtime-state-field:") :]
        scene_id, object_index, script_kind, offset, field_name = rest.rsplit(":", 4)
        return f"{scene_id}#object:{object_index}#script:{script_kind}#offset:{offset}#field:{field_name}"
    if node_id.startswith("patch-record:"):
        rest = node_id[len("patch-record:") :]
        scene_id, patch_index = rest.rsplit(":", 1)
        return f"{scene_id}#patch:{patch_index}"
    if node_id.startswith("scene:"):
        return node_id[len("scene:") :]
    if node_id.startswith("sprite-range:"):
        return node_id[len("sprite-range:") :]
    return node_id


def stable_edge_base(edge: dict[str, Any]) -> str:
    parts = [
        str(edge["type"]),
        str(edge["from"]),
        str(edge["to"]),
        str(edge.get("proofScope") or "unknown"),
        str(edge.get("sourceField") or ""),
        str(edge.get("sourceRule") or ""),
        str(edge.get("sourcePath") or ""),
        str(edge.get("sourceOffset") if edge.get("sourceOffset") is not None else ""),
        str(edge.get("rawReference") if edge.get("rawReference") is not None else ""),
        str(edge.get("resolverKind") or ""),
    ]
    occurrence_key = edge.get("occurrenceKey")
    if occurrence_key is not None:
        parts.append(str(occurrence_key))
    return "|".join(parts)


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

    zone = subparsers.add_parser("zone")
    zone.add_argument("scene_id")
    zone.add_argument("zone_index")
    zone.add_argument("--json", action="store_true")

    waypoint = subparsers.add_parser("waypoint")
    waypoint.add_argument("scene_id")
    waypoint.add_argument("waypoint_index")
    waypoint.add_argument("--json", action="store_true")

    script_instruction = subparsers.add_parser("script-instruction")
    script_instruction.add_argument("scene_id")
    script_instruction.add_argument("object_index")
    script_instruction.add_argument("script_kind")
    script_instruction.add_argument("offset")
    script_instruction.add_argument("--json", action="store_true")

    operation = subparsers.add_parser("operation")
    operation.add_argument("model_id")
    operation.add_argument("animation_id")
    operation.add_argument("--operation", default="pose_playback")
    operation.add_argument("--json", action="store_true")

    selection = subparsers.add_parser("selection")
    selection.add_argument("id")
    selection.add_argument("--json", action="store_true")

    search = subparsers.add_parser("search")
    search.add_argument("q")
    search.add_argument("--node-type", action="append", dest="node_types")
    search.add_argument("--edge-type", action="append", dest="edge_types")
    search.add_argument("--proof-scope", action="append", dest="proof_scopes")
    search.add_argument("--evidence-status", action="append", dest="evidence_statuses")
    search.add_argument("--nodes-only", action="store_true")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--json", action="store_true")

    missing_targets = subparsers.add_parser("missing-targets")
    missing_targets.add_argument("--json", action="store_true")

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
    elif args.command == "zone":
        payload = query_zone(graph, args.scene_id, args.zone_index)
    elif args.command == "waypoint":
        payload = query_waypoint(graph, args.scene_id, args.waypoint_index)
    elif args.command == "script-instruction":
        payload = query_script_instruction(graph, args.scene_id, args.object_index, args.script_kind, args.offset)
    elif args.command == "operation":
        payload = query_animation_operation_compatibility(graph, args.model_id, args.animation_id, args.operation)
    elif args.command == "selection":
        payload = query_selection(graph, args.id)
    elif args.command == "search":
        payload = query_search(
            graph,
            args.q,
            node_types=args.node_types,
            edge_types=args.edge_types,
            proof_scopes=args.proof_scopes,
            evidence_statuses=args.evidence_statuses,
            include_edges=not args.nodes_only,
            limit=args.limit,
        )
    elif args.command == "missing-targets":
        payload = query_missing_targets(graph)
    elif args.command == "export":
        payload = query_export(graph, args.subgraph)
    else:  # pragma: no cover - argparse enforces choices
        raise viewer.Lm2Error(f"unsupported catalog-graph command: {args.command}")
    print(graph_json(payload))
    return 0
