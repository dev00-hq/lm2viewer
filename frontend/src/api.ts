import type { AnimationPayload, AnimationSequencePayload, Catalog, CatalogAsset, CatalogAssetDetailPayload, CatalogGraphCompatiblePayload, CatalogGraphSelectionPayload, CatalogSearchPayload, DecodeProgress, EntityWorkflowPayload, ErrorPayload, ExportPayload, KindFilter, Lm2Model, PolygonMode, PortPromotionPacketsPayload, ResourcePayload, RuntimeSpriteResolvePayload, ScenePayload, SpritePayload } from './types';

async function readJson<T extends object>(response: Response): Promise<T> {
  const payload = await response.json() as T | ErrorPayload;
  if (!response.ok || 'error' in payload) {
    throw new Error(('error' in payload && payload.error) || response.statusText);
  }
  return payload as T;
}

export async function fetchCatalog(): Promise<Catalog | null> {
  const response = await fetch('/catalog.json');
  const payload = await response.json() as Catalog | ErrorPayload;
  if (!response.ok || 'error' in payload) return null;
  return payload as Catalog;
}

export async function fetchInitialModel(): Promise<Lm2Model | null> {
  const response = await fetch('/model.json');
  const payload = await response.json() as Lm2Model | ErrorPayload;
  if (!response.ok || 'error' in payload) return null;
  return payload as Lm2Model;
}

export async function fetchDecodeProgress(): Promise<DecodeProgress> {
  return readJson<DecodeProgress>(await fetch('/api/decode/progress'));
}

export async function fetchPortPromotionPackets(): Promise<PortPromotionPacketsPayload> {
  return readJson<PortPromotionPacketsPayload>(await fetch('/api/port/promotion-packets', { method: 'POST' }));
}

export async function uploadModel(file: File): Promise<Lm2Model> {
  const form = new FormData();
  form.append('file', file, file.name);
  return readJson<Lm2Model>(await fetch('/api/upload', { method: 'POST', body: form }));
}

export async function loadPath(path: string): Promise<Lm2Model> {
  return readJson<Lm2Model>(await fetch('/api/path', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ path }),
  }));
}

export async function buildCatalog(assetRoot: string): Promise<Catalog> {
  return readJson<Catalog>(await fetch('/api/catalog/build', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ asset_root: assetRoot }),
  }));
}

export async function searchCatalog(q: string, kind: KindFilter = 'all', offset = 0, limit = 260): Promise<CatalogSearchPayload> {
  return readJson<CatalogSearchPayload>(await fetch('/api/catalog/search', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ q, kind, offset, limit }),
  }));
}

export async function loadCatalogAssetDetail(id: string): Promise<CatalogAsset> {
  const payload = await readJson<CatalogAssetDetailPayload>(await fetch('/api/catalog/asset', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id }),
  }));
  return payload.asset;
}

export async function pickCatalogFolder(): Promise<Catalog> {
  return readJson<Catalog>(await fetch('/api/catalog/pick', { method: 'POST' }));
}

export async function pickCatalogFiles(): Promise<Catalog> {
  return readJson<Catalog>(await fetch('/api/catalog/pick-files', { method: 'POST' }));
}

export async function loadCatalogAsset(asset: CatalogAsset): Promise<Lm2Model | AnimationPayload | SpritePayload | ScenePayload | ResourcePayload> {
  return readJson<Lm2Model | AnimationPayload | SpritePayload | ScenePayload | ResourcePayload>(await fetch('/api/catalog/load', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: asset.id }),
  }));
}

export async function loadCatalogGraphSelection(id: string): Promise<CatalogGraphSelectionPayload> {
  return readJson<CatalogGraphSelectionPayload>(await fetch('/api/catalog-graph/selection', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id }),
  }));
}

export async function loadCatalogGraphCompatible(modelId: string): Promise<CatalogGraphCompatiblePayload> {
  return readJson<CatalogGraphCompatiblePayload>(await fetch('/api/catalog-graph/compatible', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model_id: modelId }),
  }));
}

export async function resolveRuntimeSprite(request: {
  object_index?: number | null;
  flags: number;
  sprite_index: number;
  body_num?: number | null;
  label_track?: number | null;
}): Promise<RuntimeSpriteResolvePayload> {
  return readJson<RuntimeSpriteResolvePayload>(await fetch('/api/runtime/sprite-resolve', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(request),
  }));
}

export async function loadAssetEntityWorkflow(asset: CatalogAsset | string): Promise<EntityWorkflowPayload> {
  const id = typeof asset === 'string' ? asset : asset.id;
  return readJson<EntityWorkflowPayload>(await fetch('/api/entity/asset', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id }),
  }));
}

export async function loadSceneObjectEntityWorkflow(sceneAssetId: string, objectIndex: number): Promise<EntityWorkflowPayload> {
  return readJson<EntityWorkflowPayload>(await fetch('/api/entity/scene-object', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ scene_asset_id: sceneAssetId, object_index: objectIndex }),
  }));
}

export async function loadRuntimeSpriteEntityWorkflow(request: {
  object_index?: number | null;
  flags: number;
  sprite_index: number;
  body_num?: number | null;
  label_track?: number | null;
}): Promise<EntityWorkflowPayload> {
  return readJson<EntityWorkflowPayload>(await fetch('/api/entity/runtime-sprite', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(request),
  }));
}

export async function exportCatalogAsset(asset: CatalogAsset, polygonMode: PolygonMode, selectedEdgeId?: string): Promise<ExportPayload> {
  return readJson<ExportPayload>(await fetch('/api/catalog/export', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: asset.id, polygon_mode: polygonMode, selected_edge_id: selectedEdgeId }),
  }));
}

export function catalogAudioUrl(asset: CatalogAsset): string {
  return `/api/catalog/audio?id=${encodeURIComponent(asset.id)}`;
}

export async function poseAnimation(
  body: CatalogAsset,
  animation: CatalogAsset,
  sampleFrame: number,
  elapsedMs: number,
  previousFrame?: number,
): Promise<Lm2Model> {
  return readJson<Lm2Model>(await fetch('/api/animation/pose', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      body_id: body.id,
      animation_id: animation.id,
      sample_frame: sampleFrame,
      elapsed_ms: elapsedMs,
      previous_frame: previousFrame,
    }),
  }));
}

export async function loadAnimationSequence(
  body: CatalogAsset,
  animation: CatalogAsset,
  stepMs: number,
): Promise<AnimationSequencePayload> {
  return readJson<AnimationSequencePayload>(await fetch('/api/animation/sequence', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      body_id: body.id,
      animation_id: animation.id,
      step_ms: stepMs,
    }),
  }));
}
