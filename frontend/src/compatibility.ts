import type { AnimationStats, CatalogAsset, ModelStats } from './types';

export function animationMatchesModel(animation: CatalogAsset, model: CatalogAsset): boolean {
  const compatibility = animationCompatibility(animation, model);
  return compatibility.status === 'compatible' || compatibility.status === 'fallback';
}

export interface AnimationCompatibility {
  status: 'compatible' | 'fallback' | 'not-decoded-animation' | 'bone-count-mismatch' | 'file3d-body-mismatch';
}

export function animationCompatibility(
  animation: CatalogAsset,
  model: CatalogAsset,
): AnimationCompatibility {
  if (animation.kind !== 'animation' || animation.entry_type !== 'animation' || !('keyframes' in animation.stats)) {
    return { status: 'not-decoded-animation' };
  }

  const animationStats = animation.stats as AnimationStats;
  const modelStats = model.stats as ModelStats;
  if (animationStats.boneframes !== modelStats.bones) {
    return { status: 'bone-count-mismatch' };
  }

  const compatibleBodyIds = animation.animation_metadata?.compatible_body_ids || [];
  if (
    model.source.hqr === 'BODY.HQR' &&
    compatibleBodyIds.length > 0 &&
    !compatibleBodyIds.includes(model.source.entry_index)
  ) {
    return { status: 'file3d-body-mismatch' };
  }

  return { status: compatibleBodyIds.length > 0 ? 'compatible' : 'fallback' };
}

export function animationCompatibilityReason(
  animation: CatalogAsset,
  model: CatalogAsset,
): AnimationCompatibility['status'] {
  return animationCompatibility(animation, model).status;
}

export function animationCompatibilityPrefix(animation: CatalogAsset, model: CatalogAsset): string {
  return animationCompatibility(animation, model).status === 'fallback' ? '[fb] ' : '';
}

export function animationCompatibilityLabel(animation: CatalogAsset, model: CatalogAsset): string {
  const reason = animationCompatibilityReason(animation, model);
  if (reason === 'compatible') return 'compatible with selected model';
  if (reason === 'fallback') return 'fallback match: bone count only';
  if (reason === 'bone-count-mismatch') return 'bone count does not match selected model';
  if (reason === 'file3d-body-mismatch') return 'File3D body set does not include selected model';
  return 'not a decoded animation';
}
