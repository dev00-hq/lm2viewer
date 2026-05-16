import type { Catalog, CatalogAsset, CatalogGraphCompatibility } from './types';

export type AnimationCompatibilityStatus =
  'compatible'
  | 'bone-count-only'
  | 'not-graph-compatible';

export interface AnimationCompatibility {
  status: AnimationCompatibilityStatus;
  edge?: CatalogGraphCompatibility;
}

export function compatibleAnimationIds(catalog: Catalog | null, model: CatalogAsset): string[] {
  return catalog?.graph?.indexes.compatibleAnimationsByModelId?.[model.id] || [];
}

export function animationCompatibility(
  catalog: Catalog | null,
  animation: CatalogAsset,
  model: CatalogAsset,
): AnimationCompatibility {
  const edge = catalog?.graph?.compatibilityByModelId?.[model.id]?.find(
    (candidate) => candidate.animationId === animation.id,
  );
  if (!edge) return { status: 'not-graph-compatible' };
  return {
    status: edge.compatibilityReason === 'file3d_allowlist' ? 'compatible' : 'bone-count-only',
    edge,
  };
}

export function animationMatchesModel(catalog: Catalog | null, animation: CatalogAsset, model: CatalogAsset): boolean {
  return animationCompatibility(catalog, animation, model).status !== 'not-graph-compatible';
}

export function animationCompatibilityReason(
  catalog: Catalog | null,
  animation: CatalogAsset,
  model: CatalogAsset,
): AnimationCompatibilityStatus {
  return animationCompatibility(catalog, animation, model).status;
}

export function animationCompatibilityPrefix(catalog: Catalog | null, animation: CatalogAsset, model: CatalogAsset): string {
  return animationCompatibilityReason(catalog, animation, model) === 'bone-count-only' ? '[bones] ' : '';
}

export function animationCompatibilityLabel(catalog: Catalog | null, animation: CatalogAsset, model: CatalogAsset): string {
  const compatibility = animationCompatibility(catalog, animation, model);
  if (compatibility.status === 'compatible') return 'compatible with selected model';
  if (compatibility.status === 'bone-count-only') return 'compatible by bone count only';
  return 'not graph-compatible with selected model';
}
