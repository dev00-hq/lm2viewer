"""Shared LM2 model contract types and export helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import msgspec

from lba2_lm2_viewer import __version__

if TYPE_CHECKING:
    from lba2_lm2_viewer.viewer import Lm2Model


SCHEMA_VERSION = "lm2_model_contract.v0"


class ContractStruct(msgspec.Struct, forbid_unknown_fields=True):
    pass


class AxisBounds(ContractStruct):
    x: list[float]
    y: list[float]
    z: list[float]


class CountFacts(ContractStruct):
    bones: int
    vertices: int
    normals: int
    polygons: int
    lines: int
    spheres: int
    uv_groups: int


class ResourceHeader(ContractStruct):
    size_file: int
    compressed_size_file: int
    compress_method: int


class SourceIdentity(ContractStruct):
    format: str
    asset_id: str | None = None
    label: str | None = None
    archive: str | None = None
    entry_index: int | None = None
    classic_index: int | None = None
    archive_offset: int | None = None
    asset_root: str | None = None
    source_mode: str | None = None
    decoded_bytes: int | None = None
    decoded_sha256: str | None = None
    archive_raw_bytes: int | None = None
    archive_raw_sha256: str | None = None
    resource_header: ResourceHeader | None = None


class UnknownDescriptor(ContractStruct):
    section: str
    offset: int | None
    length: int
    sha256: str | None
    confidence: str
    note: str
    value: int | str | bool | None = None


class EvidenceReference(ContractStruct):
    kind: str
    path: str | None = None
    sha256: str | None = None
    note: str | None = None


class UvGroupFact(ContractStruct):
    index: int
    x: int
    y: int
    w: int
    h: int
    polygon_indices: list[int]


class MaterialFact(ContractStruct):
    kind: str
    value: int
    polygon_indices: list[int]


class GeometryFacts(ContractStruct):
    counts: CountFacts
    decoded_bounds: AxisBounds
    decoded_unit: str
    header_raw_bounds: AxisBounds
    header_raw_unit: str
    bone_parent_indices: list[int]
    skinned_vertex_count: int
    coordinate_space: str
    viewer_world_scale: float


class RenderFacts(ContractStruct):
    version: int
    flags: int
    no_sort: bool
    has_transparency: bool
    textured_polygon_count: int
    transparent_polygon_count: int
    palette_indices: list[int]
    materials: list[MaterialFact]
    uv_groups: list[UvGroupFact]


class AnimationFacts(ContractStruct):
    has_animation_flag: bool
    compatible_animation_ids: list[str]
    notes: list[str]


class GameplayFacts(ContractStruct):
    scale: float
    collision_bounds: AxisBounds
    attachment_points: list[str]
    notes: list[str]


class Confidence(ContractStruct):
    geometry: str
    render: str
    animation: str
    gameplay: str
    notes: list[str]


class ModelContract(ContractStruct):
    schema_version: str
    tool: str
    source: SourceIdentity
    geometry: GeometryFacts
    render: RenderFacts
    animation: AnimationFacts
    gameplay: GameplayFacts
    evidence: list[EvidenceReference]
    unknowns: list[UnknownDescriptor]
    confidence: Confidence


def export_catalog_asset_contract(
    *,
    asset_root: Path,
    asset_id: str,
    output_path: Path,
) -> ModelContract:
    from lba2_lm2_viewer import viewer

    resolved_root = asset_root.expanduser().resolve()
    catalog = viewer.build_catalog(resolved_root)
    asset = _find_catalog_asset(catalog, asset_id)
    if asset.get("kind") != "model":
        raise viewer.Lm2Error(f"catalog asset is not a model: {asset_id}")
    payload, resource = viewer.read_hqr_payload(resolved_root, asset["source"])
    model = viewer.load_lm2_bytes(payload, str(asset["relative_path"]))
    source = {
        "asset_root": str(resolved_root),
        "catalog_asset_id": asset["id"],
        "catalog_label": asset.get("label"),
        "archive": asset["source"].get("hqr"),
        "entry_index": asset["source"].get("entry_index"),
        "classic_index": asset["source"].get("classic_index"),
        "archive_offset": asset["source"].get("offset"),
        "archive_raw_bytes": asset["source"].get("raw_bytes"),
        "archive_raw_sha256": asset["source"].get("raw_sha256"),
        "decoded_bytes": len(payload),
        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
        "resource_header": resource,
        "source_mode": catalog.get("source_mode"),
    }
    evidence = [
        EvidenceReference(
            kind="hqr_resource",
            path=str(asset.get("relative_path")),
            sha256=asset["source"].get("raw_sha256"),
            note=f"resource metadata: {resource}",
        )
    ]
    contract = build_model_contract(model=model, source=source, evidence=evidence)
    write_model_contract(contract, output_path)
    return contract


def build_model_contract(
    *,
    model: "Lm2Model",
    source: dict[str, Any] | SourceIdentity,
    evidence: list[EvidenceReference] | None = None,
    confidence: Confidence | None = None,
) -> ModelContract:
    from lba2_lm2_viewer.viewer import WORLD_SCALE

    source_identity = (
        source if isinstance(source, SourceIdentity) else _source_identity(source)
    )
    return ModelContract(
        schema_version=SCHEMA_VERSION,
        tool=f"lba2-lm2-viewer {__version__}",
        source=source_identity,
        geometry=GeometryFacts(
            counts=CountFacts(
                bones=len(model.bones),
                vertices=len(model.vertices),
                normals=len(model.normals),
                polygons=len(model.polygons),
                lines=len(model.lines),
                spheres=len(model.spheres),
                uv_groups=len(model.uv_groups),
            ),
            decoded_bounds=_decoded_bounds(model),
            decoded_unit="viewer_world",
            header_raw_bounds=AxisBounds(
                x=[model.header.bounds[0], model.header.bounds[1]],
                y=[model.header.bounds[2], model.header.bounds[3]],
                z=[model.header.bounds[4], model.header.bounds[5]],
            ),
            header_raw_unit="lm2_header_integer",
            bone_parent_indices=[bone.parent for bone in model.bones],
            skinned_vertex_count=sum(1 for vertex in model.vertices if vertex.bone != 0),
            coordinate_space="decoded_source",
            viewer_world_scale=WORLD_SCALE,
        ),
        render=RenderFacts(
            version=model.header.version,
            flags=model.header.flags,
            no_sort=model.header.no_sort,
            has_transparency=model.header.has_transparency,
            textured_polygon_count=sum(1 for poly in model.polygons if poly.has_texture),
            transparent_polygon_count=sum(
                1 for poly in model.polygons if poly.has_transparency
            ),
            palette_indices=_palette_indices(model),
            materials=_material_facts(model),
            uv_groups=_uv_group_facts(model),
        ),
        animation=AnimationFacts(
            has_animation_flag=model.header.has_animation,
            compatible_animation_ids=[],
            notes=[
                "Compatibility is intentionally empty until animation semantics are decoded."
            ],
        ),
        gameplay=GameplayFacts(
            scale=WORLD_SCALE,
            collision_bounds=_decoded_bounds(model),
            attachment_points=[],
            notes=[
                "Gameplay-facing attachments and collision semantics are not yet decoded."
            ],
        ),
        evidence=evidence or [],
        unknowns=_unknown_descriptors(model),
        confidence=confidence or _default_confidence(model),
    )


def write_model_contract(contract: ModelContract, output_path: Path) -> None:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(contract_to_json(contract))


def contract_to_json(contract: ModelContract) -> bytes:
    return msgspec.json.format(msgspec.json.encode(contract), indent=2) + b"\n"


def read_model_contract(path: Path) -> ModelContract:
    data = path.read_bytes()
    raw = msgspec.json.decode(data)
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        found = raw.get("schema_version") if isinstance(raw, dict) else None
        raise ValueError(f"unsupported model contract schema_version: {found}")
    return msgspec.json.decode(data, type=ModelContract)


def _source_identity(source: dict[str, Any]) -> SourceIdentity:
    return SourceIdentity(
        format="lm2",
        asset_id=source.get("catalog_asset_id") or source.get("asset_id"),
        label=source.get("catalog_label") or source.get("label"),
        archive=source.get("archive"),
        entry_index=source.get("entry_index"),
        classic_index=source.get("classic_index"),
        archive_offset=source.get("archive_offset"),
        asset_root=source.get("asset_root"),
        source_mode=source.get("source_mode"),
        decoded_bytes=source.get("decoded_bytes"),
        decoded_sha256=source.get("decoded_sha256"),
        archive_raw_bytes=source.get("archive_raw_bytes"),
        archive_raw_sha256=source.get("archive_raw_sha256"),
        resource_header=_resource_header(source.get("resource_header")),
    )


def _resource_header(value: Any) -> ResourceHeader | None:
    if not isinstance(value, dict):
        return None
    return ResourceHeader(
        size_file=value["size_file"],
        compressed_size_file=value["compressed_size_file"],
        compress_method=value["compress_method"],
    )


def _find_catalog_asset(catalog: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for asset in catalog.get("assets", []):
        if asset.get("id") == asset_id:
            return asset
    from lba2_lm2_viewer.viewer import Lm2Error

    raise Lm2Error(f"catalog asset not found: {asset_id}")


def _decoded_bounds(model: "Lm2Model") -> AxisBounds:
    xs = [vertex.x for vertex in model.vertices]
    ys = [vertex.y for vertex in model.vertices]
    zs = [vertex.z for vertex in model.vertices]
    return AxisBounds(
        x=[min(xs, default=0.0), max(xs, default=0.0)],
        y=[min(ys, default=0.0), max(ys, default=0.0)],
        z=[min(zs, default=0.0), max(zs, default=0.0)],
    )


def _palette_indices(model: "Lm2Model") -> list[int]:
    values = {poly.palette_index for poly in model.polygons}
    values.update(line.palette_index for line in model.lines)
    values.update(sphere.palette_index for sphere in model.spheres)
    return sorted(values)


def _material_facts(model: "Lm2Model") -> list[MaterialFact]:
    groups: dict[tuple[str, int], list[int]] = {}
    for index, poly in enumerate(model.polygons):
        if poly.has_texture and poly.texture is not None:
            key = ("texture", poly.texture)
        else:
            key = ("palette", poly.palette_index)
        groups.setdefault(key, []).append(index)
    return [
        MaterialFact(kind=kind, value=value, polygon_indices=indices)
        for (kind, value), indices in sorted(groups.items())
    ]


def _uv_group_facts(model: "Lm2Model") -> list[UvGroupFact]:
    return [
        UvGroupFact(
            index=index,
            x=group.x,
            y=group.y,
            w=group.w,
            h=group.h,
            polygon_indices=[
                poly_index
                for poly_index, poly in enumerate(model.polygons)
                if poly.has_texture and poly.texture == index
            ],
        )
        for index, group in enumerate(model.uv_groups)
    ]


def _unknown_descriptors(model: "Lm2Model") -> list[UnknownDescriptor]:
    unknowns: list[UnknownDescriptor] = []
    if model.header.unknown_count:
        unknowns.append(
            UnknownDescriptor(
                section="header.unknown",
                offset=model.header.unknown_offset,
                length=model.header.unknown_count * 8,
                sha256=None,
                confidence="unknown",
                note="Parser records the header span but does not retain bytes yet.",
            )
        )
    for index, bone in enumerate(model.bones):
        unknowns.append(
            UnknownDescriptor(
                section=f"bones[{index}].unknown_1",
                offset=model.header.bones_offset + index * 8 + 4,
                length=2,
                sha256=None,
                confidence="parsed_unknown",
                note="Parsed LM2 bone field with unknown semantics.",
                value=bone.unknown_1,
            )
        )
        unknowns.append(
            UnknownDescriptor(
                section=f"bones[{index}].unknown_2",
                offset=model.header.bones_offset + index * 8 + 6,
                length=2,
                sha256=None,
                confidence="parsed_unknown",
                note="Parsed LM2 bone field with unknown semantics.",
                value=bone.unknown_2,
            )
        )
    for index, normal in enumerate(model.normals):
        unknowns.append(
            UnknownDescriptor(
                section=f"normals[{index}].unknown",
                offset=model.header.normals_offset + index * 8 + 6,
                length=2,
                sha256=None,
                confidence="parsed_unknown",
                note="Parsed LM2 normal field with unknown semantics.",
                value=normal.unknown,
            )
        )
    for index, poly in enumerate(model.polygons):
        if poly.has_extra:
            unknowns.append(
                UnknownDescriptor(
                    section=f"polygons[{index}].render_type.has_extra",
                    offset=None,
                    length=1,
                    sha256=None,
                    confidence="parsed_unknown",
                    note="Render-type flag is preserved, but parser does not retain polygon source offsets yet.",
                    value=poly.has_extra,
                )
            )
    for index, line in enumerate(model.lines):
        unknowns.append(
            UnknownDescriptor(
                section=f"lines[{index}].unknown",
                offset=model.header.lines_offset + index * 8,
                length=2,
                sha256=None,
                confidence="parsed_unknown",
                note="Parsed LM2 line field with unknown semantics.",
                value=line.unknown,
            )
        )
    for index, sphere in enumerate(model.spheres):
        unknowns.append(
            UnknownDescriptor(
                section=f"spheres[{index}].unknown",
                offset=model.header.spheres_offset + index * 8,
                length=2,
                sha256=None,
                confidence="parsed_unknown",
                note="Parsed LM2 sphere field with unknown semantics.",
                value=sphere.unknown,
            )
        )
    return unknowns


def _default_confidence(model: "Lm2Model") -> Confidence:
    animation = "medium" if model.header.has_animation else "not_applicable"
    return Confidence(
        geometry="high",
        render="medium",
        animation=animation,
        gameplay="low",
        notes=[
            "Geometry counts and bounds come from the parsed LM2 model.",
            "Render facts are structural until visual parity is separately proven.",
        ],
    )
