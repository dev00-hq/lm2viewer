import type {
  AnimationPayload,
  AnimationSequencePayload,
  Catalog,
  CatalogAsset,
  CatalogGraphCompatiblePayload,
  CatalogGraphSelectionPayload,
  CatalogSearchPayload,
  EntityWorkflowPayload,
  KindFilter,
  Lm2Model,
  PolygonMode,
  PortPromotionPacketsPayload,
  ResourcePayload,
  RuntimeSpriteResolvePayload,
  ScenePayload,
  SpritePayload,
} from '../types';

export interface RuntimeSpriteRequest {
  object_index?: number | null;
  flags: number;
  sprite_index: number;
  body_num?: number | null;
  label_track?: number | null;
}

export interface ViewerService {
  loadInitialCatalog(): Promise<Catalog | null>;
  loadInitialModel(): Promise<Lm2Model | null>;
  loadPortPromotionPackets(): Promise<PortPromotionPacketsPayload | null>;
  decodeModelFile(file: File): Promise<Lm2Model>;
  buildCatalogFromFiles(files: readonly File[]): Promise<Catalog>;
  searchCatalog(q: string, kind?: KindFilter, offset?: number, limit?: number): Promise<CatalogSearchPayload>;
  loadCatalogAssetDetail(id: string): Promise<CatalogAsset>;
  loadCatalogAsset(asset: CatalogAsset): Promise<Lm2Model | AnimationPayload | SpritePayload | ScenePayload | ResourcePayload>;
  loadCatalogGraphSelection(id: string): Promise<CatalogGraphSelectionPayload>;
  loadCatalogGraphCompatible(modelId: string): Promise<CatalogGraphCompatiblePayload>;
  resolveRuntimeSprite(request: RuntimeSpriteRequest): Promise<RuntimeSpriteResolvePayload>;
  loadAssetEntityWorkflow(asset: CatalogAsset | string): Promise<EntityWorkflowPayload>;
  loadSceneObjectEntityWorkflow(sceneAssetId: string, objectIndex: number): Promise<EntityWorkflowPayload>;
  loadRuntimeSpriteEntityWorkflow(request: RuntimeSpriteRequest): Promise<EntityWorkflowPayload>;
  exportCatalogAsset(asset: CatalogAsset, polygonMode: PolygonMode, selectedEdgeId?: string): Promise<ExportPayload>;
  catalogAudioUrl(asset: CatalogAsset): string;
  poseAnimation(
    body: CatalogAsset,
    animation: CatalogAsset,
    sampleFrame: number,
    elapsedMs: number,
    previousFrame?: number,
  ): Promise<Lm2Model>;
  loadAnimationSequence(body: CatalogAsset, animation: CatalogAsset, stepMs: number): Promise<AnimationSequencePayload>;
}

type ExportPayload = import('../types').ExportPayload;

type WorkerResponse =
  | { id: number; ok: true; payload: unknown }
  | { id: number; ok: false; error: string };

type WorkerCatalogFile = {
  name: string;
  relativePath: string;
  buffer: ArrayBuffer;
};

type RuntimeSpriteWorkerPayload = {
  flags: number;
  spriteIndex: number;
  bodyNum: number | null;
  objectIndex: number | null;
  labelTrack: number | null;
};

let decoderWorker: Worker | null = null;
let nextWorkerRequestId = 1;
let currentCatalog: Catalog | null = null;
const catalogAudioObjectUrls = new Map<string, string>();
const animationSequenceCache = new Map<string, AnimationSequencePayload>();
const pendingWorkerRequests = new Map<number, {
  resolve: (payload: unknown) => void;
  reject: (error: Error) => void;
}>();

export const viewerService: ViewerService = {
  async loadInitialCatalog() {
    return null;
  },
  async loadInitialModel() {
    return null;
  },
  async loadPortPromotionPackets() {
    return null;
  },
  async decodeModelFile(file) {
    return await requestDecoderWorker<Lm2Model>('decodeModelFile', {
      fileName: file.name,
      buffer: await file.arrayBuffer(),
    });
  },
  async buildCatalogFromFiles(files) {
    const hqrFiles = files.filter((file) => file.name.toLowerCase().endsWith('.hqr'));
    if (hqrFiles.length === 0) throw new Error('Select one or more local HQR files first.');
    const workerFiles: WorkerCatalogFile[] = await Promise.all(hqrFiles.map(async (file) => ({
      name: file.name,
      relativePath: file.webkitRelativePath || file.name,
      buffer: await file.arrayBuffer(),
    })));
    currentCatalog = await requestDecoderWorker<Catalog>('buildCatalogFromFiles', { files: workerFiles });
    revokeCatalogObjectUrls();
    animationSequenceCache.clear();
    return currentCatalog;
  },
  async searchCatalog(q, kind = 'all', offset = 0, limit = 260) {
    return await requestDecoderWorker<CatalogSearchPayload>('searchCatalog', { q, kind, offset, limit });
  },
  async loadCatalogAssetDetail(id) {
    const payload = await requestDecoderWorker<{ asset: CatalogAsset }>('loadCatalogAssetDetail', { assetId: id });
    return payload.asset;
  },
  async loadCatalogAsset(asset) {
    const payload = await requestDecoderWorker<unknown>('loadCatalogAsset', { assetId: asset.id });
    if (isResourceAudioPayload(payload)) {
      cacheCatalogAudioUrl(payload.resource.id, payload.audio);
      return { resource: payload.resource };
    }
    return payload as Lm2Model | AnimationPayload | SpritePayload | ScenePayload | ResourcePayload;
  },
  async loadCatalogGraphSelection(id) {
    return await requestDecoderWorker<CatalogGraphSelectionPayload>('loadCatalogGraphSelection', { stableId: id });
  },
  async loadCatalogGraphCompatible(modelId) {
    return await requestDecoderWorker<CatalogGraphCompatiblePayload>('loadCatalogGraphCompatible', { modelId });
  },
  async resolveRuntimeSprite(request) {
    return await requestDecoderWorker<RuntimeSpriteResolvePayload>('resolveRuntimeSprite', {
      flags: request.flags,
      spriteIndex: request.sprite_index,
      bodyNum: request.body_num ?? null,
      objectIndex: request.object_index ?? null,
      labelTrack: request.label_track ?? null,
    });
  },
  async loadAssetEntityWorkflow(asset) {
    return await requestDecoderWorker<EntityWorkflowPayload>('loadAssetEntityWorkflow', {
      assetId: typeof asset === 'string' ? asset : asset.id,
    });
  },
  async loadSceneObjectEntityWorkflow(sceneAssetId, objectIndex) {
    return await requestDecoderWorker<EntityWorkflowPayload>('loadSceneObjectEntityWorkflow', {
      sceneAssetId,
      objectIndex,
    });
  },
  async loadRuntimeSpriteEntityWorkflow(request) {
    return await requestDecoderWorker<EntityWorkflowPayload>('loadRuntimeSpriteEntityWorkflow', {
      flags: request.flags,
      spriteIndex: request.sprite_index,
      bodyNum: request.body_num ?? null,
      objectIndex: request.object_index ?? null,
      labelTrack: request.label_track ?? null,
    });
  },
  async exportCatalogAsset(asset, polygonMode, selectedEdgeId) {
    return await requestDecoderWorker<ExportPayload>('exportCatalogAsset', {
      assetId: asset.id,
      polygonMode,
      selectedEdgeId: selectedEdgeId ?? null,
    });
  },
  catalogAudioUrl(asset) {
    return catalogAudioObjectUrls.get(asset.id) || '';
  },
  async poseAnimation(body, animation, sampleFrame, elapsedMs, previousFrame) {
    return await requestDecoderWorker<Lm2Model>('poseAnimation', {
      bodyId: body.id,
      animationId: animation.id,
      sampleFrame,
      elapsedMs,
      previousFrame: previousFrame ?? null,
    });
  },
  async loadAnimationSequence(body, animation, stepMs) {
    const cacheKey = `${body.id}\0${animation.id}\0${stepMs}`;
    const cached = animationSequenceCache.get(cacheKey);
    if (cached) return cached;
    const sequence = await requestDecoderWorker<AnimationSequencePayload>('loadAnimationSequence', {
      bodyId: body.id,
      animationId: animation.id,
      stepMs,
    });
    animationSequenceCache.set(cacheKey, sequence);
    return sequence;
  },
};

async function requestDecoderWorker<T>(
  type: 'decodeModelFile',
  payload: { fileName: string; buffer: ArrayBuffer },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'buildCatalogFromFiles',
  payload: { files: WorkerCatalogFile[] },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadCatalogGraphSelection',
  payload: { stableId: string },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadCatalogGraphCompatible',
  payload: { modelId: string },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadCatalogAsset',
  payload: { assetId: string },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'searchCatalog',
  payload: { q: string; kind: KindFilter; offset: number; limit: number },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadCatalogAssetDetail',
  payload: { assetId: string },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'poseAnimation',
  payload: { bodyId: string; animationId: string; sampleFrame: number; elapsedMs: number; previousFrame: number | null },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadAnimationSequence',
  payload: { bodyId: string; animationId: string; stepMs: number },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'exportCatalogAsset',
  payload: { assetId: string; polygonMode: PolygonMode; selectedEdgeId: string | null },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'resolveRuntimeSprite',
  payload: RuntimeSpriteWorkerPayload,
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadAssetEntityWorkflow',
  payload: { assetId: string },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadSceneObjectEntityWorkflow',
  payload: { sceneAssetId: string; objectIndex: number },
): Promise<T>;
async function requestDecoderWorker<T>(
  type: 'loadRuntimeSpriteEntityWorkflow',
  payload: RuntimeSpriteWorkerPayload,
): Promise<T>;
async function requestDecoderWorker<T>(
  type:
    | 'decodeModelFile'
    | 'buildCatalogFromFiles'
    | 'loadCatalogGraphSelection'
    | 'loadCatalogGraphCompatible'
    | 'loadCatalogAsset'
    | 'searchCatalog'
    | 'loadCatalogAssetDetail'
    | 'poseAnimation'
    | 'loadAnimationSequence'
    | 'exportCatalogAsset'
    | 'resolveRuntimeSprite'
    | 'loadAssetEntityWorkflow'
    | 'loadSceneObjectEntityWorkflow'
    | 'loadRuntimeSpriteEntityWorkflow',
  payload:
    | { fileName: string; buffer: ArrayBuffer }
    | { files: WorkerCatalogFile[] }
    | { stableId: string }
    | { modelId: string }
    | { assetId: string }
    | { q: string; kind: KindFilter; offset: number; limit: number }
    | { bodyId: string; animationId: string; sampleFrame: number; elapsedMs: number; previousFrame: number | null }
    | { bodyId: string; animationId: string; stepMs: number }
    | { assetId: string; polygonMode: PolygonMode; selectedEdgeId: string | null }
    | RuntimeSpriteWorkerPayload
    | { sceneAssetId: string; objectIndex: number },
): Promise<T> {
  const worker = ensureDecoderWorker();
  const id = nextWorkerRequestId;
  nextWorkerRequestId += 1;
  const promise = new Promise<T>((resolve, reject) => {
    pendingWorkerRequests.set(id, {
      resolve: (value) => resolve(value as T),
      reject,
    });
  });
  const transfer = 'buffer' in payload
    ? [payload.buffer]
    : 'files' in payload
      ? payload.files.map((file) => file.buffer)
      : [];
  worker.postMessage({ id, type, ...payload }, transfer);
  return await promise;
}

function ensureDecoderWorker(): Worker {
  if (decoderWorker) return decoderWorker;
  decoderWorker = new Worker(new URL('./decoder.worker.ts', import.meta.url), { type: 'module' });
  decoderWorker.addEventListener('message', (event: MessageEvent<WorkerResponse>) => {
    const pending = pendingWorkerRequests.get(event.data.id);
    if (!pending) return;
    pendingWorkerRequests.delete(event.data.id);
    if (event.data.ok) {
      pending.resolve(event.data.payload);
    } else {
      pending.reject(new Error(event.data.error));
    }
  });
  decoderWorker.addEventListener('error', (event) => {
    rejectAllPending(new Error(event.message || 'Decoder worker failed.'));
  });
  return decoderWorker;
}

function rejectAllPending(error: Error): void {
  for (const pending of pendingWorkerRequests.values()) pending.reject(error);
  pendingWorkerRequests.clear();
}

function cacheCatalogAudioUrl(assetId: string, audio: { mimeType: string; base64: string }): void {
  const existing = catalogAudioObjectUrls.get(assetId);
  if (existing) URL.revokeObjectURL(existing);
  const binary = atob(audio.base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  catalogAudioObjectUrls.set(assetId, URL.createObjectURL(new Blob([bytes], { type: audio.mimeType })));
}

function revokeCatalogObjectUrls(): void {
  for (const url of catalogAudioObjectUrls.values()) URL.revokeObjectURL(url);
  catalogAudioObjectUrls.clear();
}

function isResourceAudioPayload(payload: unknown): payload is { resource: CatalogAsset; audio: { mimeType: string; base64: string } } {
  if (!payload || typeof payload !== 'object') return false;
  const candidate = payload as {
    resource?: unknown;
    audio?: { mimeType?: unknown; base64?: unknown };
  };
  return Boolean(candidate.resource)
    && Boolean(candidate.audio)
    && typeof candidate.audio?.mimeType === 'string'
    && typeof candidate.audio?.base64 === 'string';
}
