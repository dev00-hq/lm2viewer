import type { AnimationPayload, Catalog, CatalogAsset, DecodeProgress, ErrorPayload, Lm2Model } from './types';

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

export async function pickCatalogFolder(): Promise<Catalog> {
  return readJson<Catalog>(await fetch('/api/catalog/pick', { method: 'POST' }));
}

export async function loadCatalogAsset(asset: CatalogAsset): Promise<Lm2Model | AnimationPayload> {
  return readJson<Lm2Model | AnimationPayload>(await fetch('/api/catalog/load', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: asset.id }),
  }));
}
