import { loadPyodide, type PyodideInterface } from 'pyodide';
import { pythonSources } from './pythonSources.generated';

type DecodeRequest = {
  id: number;
  type: 'decodeModelFile';
  fileName: string;
  buffer: ArrayBuffer;
};

type CatalogFile = {
  name: string;
  relativePath: string;
  buffer: ArrayBuffer;
};

type BuildCatalogRequest = {
  id: number;
  type: 'buildCatalogFromFiles';
  files: CatalogFile[];
};

type GraphSelectionRequest = {
  id: number;
  type: 'loadCatalogGraphSelection';
  stableId: string;
};

type GraphCompatibleRequest = {
  id: number;
  type: 'loadCatalogGraphCompatible';
  modelId: string;
};

type LoadCatalogAssetRequest = {
  id: number;
  type: 'loadCatalogAsset';
  assetId: string;
};

type SearchCatalogRequest = {
  id: number;
  type: 'searchCatalog';
  q: string;
  kind: string;
  offset: number;
  limit: number;
};

type CatalogAssetDetailRequest = {
  id: number;
  type: 'loadCatalogAssetDetail';
  assetId: string;
};

type PoseAnimationRequest = {
  id: number;
  type: 'poseAnimation';
  bodyId: string;
  animationId: string;
  sampleFrame: number;
  elapsedMs: number;
  previousFrame: number | null;
};

type LoadAnimationSequenceRequest = {
  id: number;
  type: 'loadAnimationSequence';
  bodyId: string;
  animationId: string;
  stepMs: number;
};

type ExportCatalogAssetRequest = {
  id: number;
  type: 'exportCatalogAsset';
  assetId: string;
  polygonMode: string;
  selectedEdgeId: string | null;
};

type ResolveRuntimeSpriteRequest = {
  id: number;
  type: 'resolveRuntimeSprite';
  flags: number;
  spriteIndex: number;
  bodyNum: number | null;
  objectIndex: number | null;
  labelTrack: number | null;
};

type LoadAssetEntityWorkflowRequest = {
  id: number;
  type: 'loadAssetEntityWorkflow';
  assetId: string;
};

type LoadSceneObjectEntityWorkflowRequest = {
  id: number;
  type: 'loadSceneObjectEntityWorkflow';
  sceneAssetId: string;
  objectIndex: number;
};

type LoadRuntimeSpriteEntityWorkflowRequest = {
  id: number;
  type: 'loadRuntimeSpriteEntityWorkflow';
  flags: number;
  spriteIndex: number;
  bodyNum: number | null;
  objectIndex: number | null;
  labelTrack: number | null;
};

type WorkerRequest =
  | DecodeRequest
  | BuildCatalogRequest
  | GraphSelectionRequest
  | GraphCompatibleRequest
  | LoadCatalogAssetRequest
  | SearchCatalogRequest
  | CatalogAssetDetailRequest
  | PoseAnimationRequest
  | LoadAnimationSequenceRequest
  | ExportCatalogAssetRequest
  | ResolveRuntimeSpriteRequest
  | LoadAssetEntityWorkflowRequest
  | LoadSceneObjectEntityWorkflowRequest
  | LoadRuntimeSpriteEntityWorkflowRequest;

type WorkerResponse =
  | { id: number; ok: true; payload: unknown }
  | { id: number; ok: false; error: string };

let pyodidePromise: Promise<PyodideInterface> | null = null;
let mounted = false;
let requestChain: Promise<void> = Promise.resolve();

self.addEventListener('message', (event: MessageEvent<WorkerRequest>) => {
  requestChain = requestChain.then(async () => {
    self.postMessage(await handleRequest(event.data));
  });
});

async function handleRequest(request: WorkerRequest): Promise<WorkerResponse> {
  try {
    switch (request.type) {
      case 'decodeModelFile':
        return { id: request.id, ok: true, payload: await decodeModelFile(request) };
      case 'buildCatalogFromFiles':
        return { id: request.id, ok: true, payload: await buildCatalogFromFiles(request) };
      case 'loadCatalogGraphSelection':
        return { id: request.id, ok: true, payload: await loadCatalogGraphSelection(request) };
      case 'loadCatalogGraphCompatible':
        return { id: request.id, ok: true, payload: await loadCatalogGraphCompatible(request) };
      case 'loadCatalogAsset':
        return { id: request.id, ok: true, payload: await loadCatalogAsset(request) };
      case 'searchCatalog':
        return { id: request.id, ok: true, payload: await searchCatalog(request) };
      case 'loadCatalogAssetDetail':
        return { id: request.id, ok: true, payload: await loadCatalogAssetDetail(request) };
      case 'poseAnimation':
        return { id: request.id, ok: true, payload: await poseAnimation(request) };
      case 'loadAnimationSequence':
        return { id: request.id, ok: true, payload: await loadAnimationSequence(request) };
      case 'exportCatalogAsset':
        return { id: request.id, ok: true, payload: await exportCatalogAsset(request) };
      case 'resolveRuntimeSprite':
        return { id: request.id, ok: true, payload: await resolveRuntimeSprite(request) };
      case 'loadAssetEntityWorkflow':
        return { id: request.id, ok: true, payload: await loadAssetEntityWorkflow(request) };
      case 'loadSceneObjectEntityWorkflow':
        return { id: request.id, ok: true, payload: await loadSceneObjectEntityWorkflow(request) };
      case 'loadRuntimeSpriteEntityWorkflow':
        return { id: request.id, ok: true, payload: await loadRuntimeSpriteEntityWorkflow(request) };
    }
  } catch (error) {
    return {
      id: request.id,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function resolveRuntimeSprite(request: ResolveRuntimeSpriteRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  setRuntimeSpriteGlobals(pyodide, request);
  const result = pyodide.runPython(`
if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
sprite_request = {
    "flags": int(runtime_sprite_flags),
    "sprite_index": int(runtime_sprite_index),
}
if int(runtime_sprite_body_num) >= 0:
    sprite_request["body_num"] = int(runtime_sprite_body_num)
if int(runtime_sprite_object_index) >= 0:
    sprite_request["object_index"] = int(runtime_sprite_object_index)
if int(runtime_sprite_label_track) >= 0:
    sprite_request["label_track"] = int(runtime_sprite_label_track)
worker_visual_server.resolve_runtime_sprite_object(sprite_request)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadAssetEntityWorkflow(request: LoadAssetEntityWorkflowRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('entity_asset_id', request.assetId);
  const result = pyodide.runPython(`
if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
worker_visual_server.asset_entity_workflow(str(entity_asset_id))
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadSceneObjectEntityWorkflow(request: LoadSceneObjectEntityWorkflowRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('entity_scene_asset_id', request.sceneAssetId);
  pyodide.globals.set('entity_scene_object_index', request.objectIndex);
  const result = pyodide.runPython(`
if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
worker_visual_server.scene_object_entity_workflow(
    str(entity_scene_asset_id),
    int(entity_scene_object_index),
)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadRuntimeSpriteEntityWorkflow(request: LoadRuntimeSpriteEntityWorkflowRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  setRuntimeSpriteGlobals(pyodide, request);
  const result = pyodide.runPython(`
if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
sprite_request = {
    "flags": int(runtime_sprite_flags),
    "sprite_index": int(runtime_sprite_index),
}
if int(runtime_sprite_body_num) >= 0:
    sprite_request["body_num"] = int(runtime_sprite_body_num)
if int(runtime_sprite_object_index) >= 0:
    sprite_request["object_index"] = int(runtime_sprite_object_index)
if int(runtime_sprite_label_track) >= 0:
    sprite_request["label_track"] = int(runtime_sprite_label_track)
worker_visual_server.runtime_sprite_entity_workflow(sprite_request)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function exportCatalogAsset(request: ExportCatalogAssetRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.FS.mkdirTree('/session/exports');
  pyodide.globals.set('export_request_id', request.id);
  pyodide.globals.set('export_asset_id', request.assetId);
  pyodide.globals.set('export_polygon_mode', request.polygonMode);
  pyodide.globals.set('export_selected_edge_id', request.selectedEdgeId || '');
  const result = pyodide.runPython(`
from pathlib import Path
import base64
import io
import json
import re
import shutil
import zipfile

if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")

output_dir = Path(f"/session/exports/export-{int(export_request_id)}")
shutil.rmtree(output_dir, ignore_errors=True)
output_dir.mkdir(parents=True, exist_ok=True)
selected_edge_id = str(export_selected_edge_id or "") or None
export_result = worker_visual_server.export_catalog_asset(
    str(export_asset_id),
    output_dir,
    str(export_polygon_mode or "original"),
    selected_edge_id,
)
manifest = export_result.get("manifest") or {}
source = manifest.get("source") or {}
if isinstance(source, dict):
    source.pop("asset_root", None)
manifest_file = (manifest.get("files") or {}).get("manifest") or "manifest.json"
(output_dir / manifest_file).write_text(json.dumps(manifest, indent=2) + "\\n", encoding="utf-8")
archive = str(source.get("archive") or source.get("catalog_asset_id") or "catalog")
entry_index = source.get("entry_index")
stem = f"{archive}_{entry_index}_export" if entry_index is not None else f"{archive}_export"
stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "catalog_export"
filename = f"{stem}.zip"
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_STORED) as archive_file:
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            archive_file.write(path, path.relative_to(output_dir).as_posix())
{
    "output_dir": f"browser-download:{filename}",
    "manifest": manifest,
    "download": {
        "filename": filename,
        "mimeType": "application/zip",
        "base64": base64.b64encode(zip_buffer.getvalue()).decode("ascii"),
    },
}
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function buildCatalogFromFiles(request: BuildCatalogRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  const rootPath = `/session/catalog-${request.id}`;
  pyodide.FS.mkdirTree(rootPath);
  const selectedPaths: string[] = [];
  for (const file of request.files) {
    const relativePath = safeRelativePath(file.relativePath || file.name);
    const target = `${rootPath}/${relativePath}`;
    const directory = target.slice(0, target.lastIndexOf('/'));
    pyodide.FS.mkdirTree(directory);
    pyodide.FS.writeFile(target, new Uint8Array(file.buffer));
    selectedPaths.push(target);
  }
  pyodide.globals.set('catalog_root_path', rootPath);
  pyodide.globals.set('catalog_selected_paths', selectedPaths);
  const result = pyodide.runPython(`
from pathlib import Path
import shutil
from lba2_lm2_viewer import viewer
from lba2_lm2_viewer.server import ViewerServer, compact_catalog

catalog = viewer.build_catalog(
    Path(catalog_root_path),
    selected_files=[Path(path) for path in catalog_selected_paths],
)
visual_server = ViewerServer(None, None)
visual_server.asset_root = Path(catalog_root_path)
visual_server.catalog = catalog
visual_server.load_visual_assets(Path(catalog_root_path))
previous_catalog_root_path = globals().get("worker_catalog_root_path")
worker_catalog_root_path = catalog_root_path
worker_catalog = catalog
worker_graph = None
worker_visual_server = visual_server
if previous_catalog_root_path and previous_catalog_root_path != catalog_root_path:
    shutil.rmtree(previous_catalog_root_path, ignore_errors=True)
compact_catalog(worker_catalog)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadCatalogAsset(request: LoadCatalogAssetRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('catalog_asset_id', request.assetId);
  const result = pyodide.runPython(`
from pathlib import Path
from lba2_lm2_viewer import viewer
from lba2_lm2_viewer.server import indexed_frame_rgba
from lba2_lm2_viewer.viewer import decode_bkg_grid_columns, parse_bkg_brick_graphic

if "worker_catalog" not in globals() or "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
asset = worker_visual_server.find_catalog_asset(catalog_asset_id)
if asset.get("kind") == "model":
    payload, _resource = viewer.read_hqr_payload(Path(worker_catalog_root_path), asset["source"])
    model = viewer.load_lm2_bytes(payload, str(asset.get("relative_path") or asset.get("label") or asset["id"]))
    result = worker_visual_server.model_json(model, asset.get("label") or asset["id"])
    result["catalog_asset"] = asset
elif asset.get("kind") == "animation":
    result = {"animation": asset}
elif asset.get("kind") == "sprite":
    stats = asset.get("stats") or {}
    semantic_layout = stats.get("semantic_layout")
    if semantic_layout not in ("lsp_sprite_frame", "raw_sprite_frame"):
        result = {"sprite": asset}
    else:
        payload, _resource = viewer.read_hqr_payload(Path(worker_catalog_root_path), asset["source"])
        sprite = (
            viewer.parse_raw_sprite_frame(payload)
            if semantic_layout == "raw_sprite_frame"
            else viewer.parse_lsp_sprite_frame(payload)
        )
        palette = worker_visual_server.palette
        result = {
            "sprite": asset,
            "frame": {
                "format": sprite["format"],
                "width": sprite["width"],
                "height": sprite["height"],
                "offset_x": sprite["offset_x"],
                "offset_y": sprite["offset_y"],
                "pixels": sprite["pixels"],
                "rgba": indexed_frame_rgba(sprite["pixels"], palette),
                "palette_available": palette is not None,
                "palette_source": "RESS.HQR:0 normal palette",
            },
        }
elif asset.get("kind") == "scene":
    stats = asset.get("stats") or {}
    background = ((stats.get("reconnaissance") or {}).get("background") or {})
    if not (
        type(background.get("resolved_gri_entry")) is int
        and type(background.get("resolved_bll_entry")) is int
    ):
        result = {"scene": asset}
    else:
        frames = worker_visual_server.render_scene_background_preview_frames(asset)
        enriched_asset = {
            **asset,
            "stats": {
                **stats,
                "background_preview": {
                    "format": "scene_background_preview_variants",
                    "variant_count": len(frames),
                    "variant_policy": "base plus each resolved GRM zone forced ON; no live script state guessed",
                    "source_provenance": "Scene background preview uses TabAllCube-selected GRI plus explicit GRILLE.CPP IncrustGrm variants.",
                },
            },
        }
        result = {"sprite": enriched_asset, "frame": frames[0] if frames else None, "frames": frames}
elif asset.get("kind") == "resource":
    import base64

    stats = asset.get("stats") or {}
    semantic_layout = stats.get("semantic_layout")
    if semantic_layout == "bkg_grid_map":
        payload, _resource = viewer.read_hqr_payload(Path(worker_catalog_root_path), asset["source"])
        composition = decode_bkg_grid_columns(payload, include_cells=True)
        preview = worker_visual_server.render_bkg_grid_preview(asset)
        enriched_asset = {
            **asset,
            "stats": {
                **stats,
                "composition_payload": {
                    "format": "bkg_grid_column_composition",
                    "cube_dimensions": composition["cube_dimensions"],
                    "cell_order": composition["cell_order"],
                    "cell_count": len(composition["flat_block_refs"]),
                    "flat_block_refs": composition["flat_block_refs"],
                    "flat_cell_slots_or_codes": composition["flat_cell_slots_or_codes"],
                    "occupied_block_cells": composition["nonzero_cells"],
                    "transparent_code_cells": composition["transparent_code_cells"],
                    "unique_block_refs": composition["unique_block_refs"],
                    "source_provenance": composition["source_provenance"],
                },
                "preview": {
                    "format": preview["format"],
                    "width": preview["width"],
                    "height": preview["height"],
                    "drawn_cells": preview["drawn_cells"],
                    "drawn_pixels": preview["drawn_pixels"],
                    "unique_bricks_loaded": preview["unique_bricks_loaded"],
                    "missing_bricks": preview["missing_bricks"],
                    "skipped_forbidden": preview["skipped_forbidden"],
                    "source_provenance": preview["render_source"],
                    "palette_source": preview["palette_source"],
                },
            },
        }
        result = {"sprite": enriched_asset, "frame": preview}
    elif semantic_layout == "screen_indexed_image_640x480":
        preview = worker_visual_server.screen_indexed_image_frame(asset)
        enriched_asset = {**asset, "stats": {**stats, "preview": {
            "format": preview["format"],
            "width": preview["width"],
            "height": preview["height"],
            "palette_source": preview["palette_source"],
        }}}
        result = {"sprite": enriched_asset, "frame": preview}
    elif semantic_layout in ("lba2_indexed_image_256", "lba2_texture_atlas_indexed"):
        preview = worker_visual_server.ress_indexed_image_frame(asset)
        enriched_asset = {**asset, "stats": {**stats, "preview": {
            "format": preview["format"],
            "width": preview["width"],
            "height": preview["height"],
            "palette_source": preview["palette_source"],
        }}}
        result = {"sprite": enriched_asset, "frame": preview}
    elif semantic_layout == "holomap_plan_image_640x480":
        preview = worker_visual_server.holomap_plan_image_frame(asset)
        enriched_asset = {**asset, "stats": {**stats, "preview": {
            "format": preview["format"],
            "width": preview["width"],
            "height": preview["height"],
            "palette_source": preview["palette_source"],
        }}}
        result = {"sprite": enriched_asset, "frame": preview}
    elif semantic_layout == "bkg_brick_graphic":
        payload, _resource = viewer.read_hqr_payload(Path(worker_catalog_root_path), asset["source"])
        brick = parse_bkg_brick_graphic(payload)
        palette = worker_visual_server.palette
        result = {
            "sprite": asset,
            "frame": {
                "format": brick["format"],
                "width": brick["width"],
                "height": brick["height"],
                "offset_x": brick["offset_x"],
                "offset_y": brick["offset_y"],
                "pixels": brick["pixels"],
                "rgba": indexed_frame_rgba(brick["pixels"], palette, brick["opaque_mask"]),
                "palette_available": palette is not None,
                "palette_source": "RESS.HQR:0 normal palette preview; gameplay BRK colors use the active PtrPal selected by ChoicePalette from XPL palettes.",
            },
        }
    elif semantic_layout == "sample_wave_audio":
        payload, _resource = viewer.read_hqr_payload(Path(worker_catalog_root_path), asset["source"])
        if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
            raise RuntimeError(f"sample asset is not decoded RIFF/WAVE audio: {asset.get('id')}")
        result = {
            "resource": asset,
            "audio": {
                "mimeType": "audio/wav",
                "base64": base64.b64encode(payload).decode("ascii"),
            },
        }
    else:
        result = {"resource": asset}
else:
    raise RuntimeError(f"unsupported catalog asset kind: {asset.get('kind')}")
result
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function searchCatalog(request: SearchCatalogRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('catalog_search_q', request.q);
  pyodide.globals.set('catalog_search_kind', request.kind);
  pyodide.globals.set('catalog_search_offset', request.offset);
  pyodide.globals.set('catalog_search_limit', request.limit);
  const result = pyodide.runPython(`
from lba2_lm2_viewer.server import catalog_search_rows

if "worker_catalog" not in globals():
    raise RuntimeError("no catalog loaded")
catalog_search_rows(
    worker_catalog,
    query=str(catalog_search_q or ""),
    kind=str(catalog_search_kind or "all"),
    offset=max(0, int(catalog_search_offset or 0)),
    limit=max(0, min(1000, int(catalog_search_limit or 260))),
)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadCatalogAssetDetail(request: CatalogAssetDetailRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('catalog_detail_asset_id', request.assetId);
  const result = pyodide.runPython(`
import copy

if "worker_catalog" not in globals():
    raise RuntimeError("no catalog loaded")
asset = next((item for item in worker_catalog.get("assets", []) if item.get("id") == catalog_detail_asset_id), None)
if asset is None:
    raise RuntimeError(f"catalog asset not found: {catalog_detail_asset_id}")
{"schema": "viewer.catalog_asset_detail.v0", "asset": copy.deepcopy(asset)}
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadCatalogGraphSelection(request: GraphSelectionRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('graph_stable_id', request.stableId);
  const result = pyodide.runPython(`
from lba2_lm2_viewer.catalog_graph import build_catalog_graph, query_selection

if "worker_catalog" not in globals():
    raise RuntimeError("no catalog loaded")
if globals().get("worker_graph") is None:
    worker_graph = build_catalog_graph(worker_catalog)
query_selection(worker_graph, graph_stable_id)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadCatalogGraphCompatible(request: GraphCompatibleRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('graph_model_id', request.modelId);
  const result = pyodide.runPython(`
from lba2_lm2_viewer.catalog_graph import build_catalog_graph, query_compatible

if "worker_catalog" not in globals():
    raise RuntimeError("no catalog loaded")
if globals().get("worker_graph") is None:
    worker_graph = build_catalog_graph(worker_catalog)
compatible = query_compatible(worker_graph, graph_model_id)
assets_by_id = {
    str(asset.get("id")): asset
    for asset in worker_catalog.get("assets", [])
    if isinstance(asset, dict) and asset.get("id")
}
edges_by_animation = {
    str(edge.get("from", "")).removeprefix("asset:"): edge
    for edge in compatible.get("edges") or []
}
animation_ids = compatible.get("compatibleAnimationIds") or []
{
    "schema": "catalog_graph.compatible_summary.v0",
    "modelId": graph_model_id,
    "compatibleAnimationIds": animation_ids,
    "animations": [
        assets_by_id[animation_id]
        for animation_id in animation_ids
        if animation_id in assets_by_id
    ],
    "compatibility": [
        {
            "animationId": animation_id,
            "compatibilityReason": (edges_by_animation.get(animation_id) or {}).get("compatibilityReason"),
            "proofScope": (edges_by_animation.get(animation_id) or {}).get("proofScope"),
            "evidenceStatus": (edges_by_animation.get(animation_id) or {}).get("evidenceStatus"),
            "sourceRule": (edges_by_animation.get(animation_id) or {}).get("sourceRule"),
            "sourceField": (edges_by_animation.get(animation_id) or {}).get("sourceField"),
            "indexRule": (edges_by_animation.get(animation_id) or {}).get("indexRule"),
        }
        for animation_id in animation_ids
    ],
}
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function poseAnimation(request: PoseAnimationRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('animation_body_id', request.bodyId);
  pyodide.globals.set('animation_asset_id', request.animationId);
  pyodide.globals.set('animation_sample_frame', request.sampleFrame);
  pyodide.globals.set('animation_elapsed_ms', request.elapsedMs);
  pyodide.globals.set('animation_previous_frame', request.previousFrame ?? -1);
  const result = pyodide.runPython(`
if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
worker_visual_server.pose_catalog_animation(
    str(animation_body_id),
    str(animation_asset_id),
    int(animation_sample_frame or 0),
    int(animation_elapsed_ms or 0),
    None if int(animation_previous_frame) < 0 else int(animation_previous_frame),
)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function loadAnimationSequence(request: LoadAnimationSequenceRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.globals.set('animation_sequence_body_id', request.bodyId);
  pyodide.globals.set('animation_sequence_asset_id', request.animationId);
  pyodide.globals.set('animation_sequence_step_ms', request.stepMs);
  const result = pyodide.runPython(`
if "worker_visual_server" not in globals():
    raise RuntimeError("no catalog loaded")
worker_visual_server.pose_catalog_animation_sequence(
    str(animation_sequence_body_id),
    str(animation_sequence_asset_id),
    int(animation_sequence_step_ms or 0),
)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
  }
}

async function decodeModelFile(request: DecodeRequest): Promise<unknown> {
  const pyodide = await pyodideRuntime();
  pyodide.FS.mkdirTree('/session');
  const modelPath = `/session/model-${request.id}.lm2`;
  pyodide.FS.writeFile(modelPath, new Uint8Array(request.buffer));
  pyodide.globals.set('source_name', request.fileName);
  pyodide.globals.set('model_path', modelPath);
  const result = pyodide.runPython(`
from pathlib import Path
from lba2_lm2_viewer import viewer

model = viewer.load_lm2_bytes(Path(model_path).read_bytes(), source_name)
model.to_viewer_json(source_name)
`);
  try {
    return result.toJs({ dict_converter: Object.fromEntries });
  } finally {
    result.destroy();
    try {
      pyodide.FS.unlink(modelPath);
    } catch {
      // The Python side may fail before the file is visible; cleanup is best effort.
    }
  }
}

async function pyodideRuntime(): Promise<PyodideInterface> {
  pyodidePromise ||= loadPyodide({
    indexURL: new URL(`${import.meta.env.BASE_URL}pyodide/`, self.location.origin).href,
    stdout: () => {},
    stderr: () => {},
  }).then(async (pyodide) => {
    await pyodide.loadPackage('msgspec');
    mountPythonSources(pyodide);
    return pyodide;
  });
  return pyodidePromise;
}

function mountPythonSources(pyodide: PyodideInterface): void {
  if (mounted) return;
  pyodide.FS.mkdirTree('/work');
  for (const [relativePath, text] of Object.entries(pythonSources)) {
    const target = `/work/${relativePath}`;
    const directory = target.slice(0, target.lastIndexOf('/'));
    pyodide.FS.mkdirTree(directory);
    pyodide.FS.writeFile(target, text);
  }
  pyodide.runPython('import sys; sys.path.insert(0, "/work")');
  mounted = true;
}

function setRuntimeSpriteGlobals(
  pyodide: PyodideInterface,
  request: ResolveRuntimeSpriteRequest | LoadRuntimeSpriteEntityWorkflowRequest,
): void {
  pyodide.globals.set('runtime_sprite_flags', request.flags);
  pyodide.globals.set('runtime_sprite_index', request.spriteIndex);
  pyodide.globals.set('runtime_sprite_body_num', request.bodyNum ?? -1);
  pyodide.globals.set('runtime_sprite_object_index', request.objectIndex ?? -1);
  pyodide.globals.set('runtime_sprite_label_track', request.labelTrack ?? -1);
}

function safeRelativePath(path: string): string {
  const parts = path.replaceAll('\\', '/').split('/').filter((part) => part && part !== '.' && part !== '..');
  return parts.join('/') || 'selected.HQR';
}
