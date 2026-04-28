import type { AnimationStats, Catalog, CatalogAsset, KindFilter, ModelStats, RawAnimationStats } from '../types';

export interface CatalogUiOptions {
  summary: HTMLElement;
  search: HTMLInputElement;
  filter: HTMLSelectElement;
  list: HTMLElement;
  detail: HTMLElement;
  onSelect: (asset: CatalogAsset) => void;
}

export class CatalogUi {
  private catalog: Catalog | null = null;
  private selectedAssetId: string | null = null;
  private selectedModel: CatalogAsset | null = null;

  constructor(private readonly options: CatalogUiOptions) {
    options.search.addEventListener('input', () => this.render());
    options.filter.addEventListener('change', () => this.render());
  }

  setCatalog(catalog: Catalog | null): void {
    this.catalog = catalog;
    if (!catalog) {
      this.options.summary.textContent = 'Choose the folder containing your LBA2 HQR files to enable exploration.';
      this.options.list.replaceChildren();
      return;
    }
    this.render();
  }

  select(asset: CatalogAsset): void {
    this.selectedAssetId = asset.id;
    this.renderDetail(asset);
    this.render();
  }

  setSelectedModel(asset: CatalogAsset | null): void {
    this.selectedModel = asset;
    this.render();
  }

  renderDetail(asset: CatalogAsset): void {
    const stats = asset.stats;
    if (asset.kind === 'model') {
      const modelStats = stats as ModelStats;
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `${modelStats.vertices || 0} vertices, ${modelStats.polygons || 0} polygons, ${modelStats.bones || 0} bones<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    if ('parse_status' in stats && stats.parse_status === 'raw') {
      const raw = stats as RawAnimationStats;
      const descriptors = raw.unknown_descriptors || [];
      const parseError = raw.parse_error ? `<br>parse error: ${escapeHtml(raw.parse_error)}` : '';
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `raw animation evidence, ${asset.decoded_bytes} bytes<br>` +
        `decode status: ${escapeHtml(raw.decode_status)} - ${escapeHtml(raw.decode_note)}${parseError}<br>` +
        `header words: ${escapeHtml((raw.header_words || []).join(', '))}<br>` +
        `unknown descriptors: ${descriptors.length}<br>` +
        `${renderUnknownDescriptors(descriptors)}` +
        `sha256: ${escapeHtml(asset.decoded_sha256)}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    const animation = stats as AnimationStats;
    const compatibility = this.selectedModel
      ? `${animationMatchesModel(asset, this.selectedModel) ? 'compatible with selected model' : 'bone count does not match selected model'}<br>`
      : '';
    const metadata = animationMetadataText(asset);
    const metadataDetail = metadata ? `${escapeHtml(metadata)}<br>` : '';
    this.options.detail.innerHTML =
      `<strong>${escapeHtml(asset.label)}</strong><br>` +
      `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
      metadataDetail +
      `${animation.keyframes || 0} keyframes, ${animation.boneframes || 0} boneframes, loop frame ${animation.loop_frame ?? '-'}<br>` +
      `${animation.can_fall ? 'contains translation/fall frames' : 'rotation-only frames'}<br>` +
      `${compatibility}` +
      `${escapeHtml(asset.relative_path || '')}`;
  }

  private render(): void {
    if (!this.catalog) return;
    const summary = this.catalog.summary || {};
    const query = this.options.search.value.trim().toLowerCase();
    const kind = this.options.filter.value as KindFilter;
    let assets = this.catalog.assets || [];
    assets = assets.filter((asset) => {
      if (kind !== 'all' && asset.kind !== kind) return false;
      if (kind === 'animation' && this.selectedModel && !animationMatchesModel(asset, this.selectedModel)) return false;
      if (!query) return true;
      return searchableText(asset).includes(query);
    });
    assets.sort((a, b) => scoreAsset(b, query) - scoreAsset(a, query) || assetSortKey(a).localeCompare(assetSortKey(b)));
    const visible = assets.slice(0, 260);
    this.options.summary.textContent =
      `${summary.models || 0} models, ${summary.decoded_animations || 0} decoded animations, ${summary.raw_animations || 0} raw animation entries across ${summary.hqr_files || 0} HQR files. ` +
      `${this.filterContext(kind)}Showing ${visible.length} of ${assets.length} matching entries.`;
    this.options.list.replaceChildren(...visible.map((asset) => this.assetButton(asset)));
  }

  private filterContext(kind: KindFilter): string {
    if (kind !== 'animation' || !this.selectedModel) return '';
    const stats = this.selectedModel.stats as ModelStats;
    return `Filtered to decoded animations with ${stats.bones || 0} boneframes for ${this.selectedModel.label}. `;
  }

  private assetButton(asset: CatalogAsset): HTMLButtonElement {
    const button = document.createElement('button');
    button.className = 'asset-button' + (asset.id === this.selectedAssetId ? ' active' : '');
    button.type = 'button';

    const title = document.createElement('div');
    title.className = 'asset-title';
    const name = document.createElement('strong');
    name.textContent = asset.label;
    const pill = document.createElement('span');
    pill.className = 'pill';
    pill.textContent = asset.animation_state ? `${asset.kind} ${asset.animation_state}` : asset.kind;
    title.append(name, pill);

    const meta = document.createElement('div');
    meta.className = 'asset-meta';
    meta.textContent = assetMeta(asset);

    button.append(title, meta);
    button.addEventListener('click', () => this.options.onSelect(asset));
    return button;
  }
}

function animationMatchesModel(animation: CatalogAsset, model: CatalogAsset): boolean {
  if (animation.kind !== 'animation' || animation.entry_type !== 'animation') return false;
  if (!('keyframes' in animation.stats)) return false;
  const modelStats = model.stats as ModelStats;
  return animation.stats.boneframes === modelStats.bones;
}

function searchableText(asset: CatalogAsset): string {
  return [
    asset.id,
    asset.kind,
    asset.animation_state,
    asset.label,
    asset.entry_type,
    animationMetadataText(asset),
    asset.source?.hqr,
    asset.source?.entry_index,
    statsSearchText(asset.stats),
  ].join(' ').toLowerCase();
}

function statsSearchText(stats: CatalogAsset['stats']): string {
  if ('parse_status' in stats && stats.parse_status === 'raw') {
    const descriptors = stats.unknown_descriptors || [];
    return [
      stats.parse_status,
      stats.decode_status,
      stats.decode_note,
      stats.parse_error,
      stats.semantic_layout,
      (stats.header_words || []).join(' '),
      descriptors
        .map((descriptor) =>
          [
            descriptor.section,
            descriptor.offset,
            descriptor.length,
            descriptor.sha256,
            descriptor.confidence,
            descriptor.note,
            descriptor.related_decoded_fields?.join(' '),
          ].join(' '),
        )
        .join(' '),
    ].join(' ');
  }
  return Object.values(stats || {}).join(' ');
}

function scoreAsset(asset: CatalogAsset, query: string): number {
  let score = 0;
  if (asset.kind === 'model') score += 1000;
  if (asset.source?.hqr === 'BODY.HQR') score += 300;
  if (asset.label && !asset.label.endsWith(`entry ${asset.source?.entry_index}`)) score += 120;
  if (query && asset.label?.toLowerCase().includes(query)) score += 500;
  if (query && asset.id?.toLowerCase().includes(query)) score += 260;
  return score;
}

function assetSortKey(asset: CatalogAsset): string {
  return `${asset.kind === 'model' ? '0' : '1'}:${asset.source?.hqr || ''}:${String(asset.source?.entry_index || 0).padStart(5, '0')}`;
}

function assetMeta(asset: CatalogAsset): string {
  const source = `${asset.source?.hqr}[${asset.source?.entry_index}]`;
  if (asset.kind === 'model') {
    const stats = asset.stats as ModelStats;
    return `${source} - ${stats.vertices || 0} verts, ${stats.polygons || 0} polys, ${stats.bones || 0} bones`;
  }
  if ('parse_status' in asset.stats && asset.stats.parse_status === 'raw') {
    return `${source} - ${asset.decoded_bytes} bytes, raw animation evidence`;
  }
  const animation = asset.stats as AnimationStats;
  const metadata = animationMetadataText(asset);
  const prefix = metadata ? `${metadata} - ` : '';
  return `${source} - ${prefix}${animation.keyframes || 0} keyframes, ${animation.boneframes || 0} bones, loop ${animation.loop_frame ?? '-'}`;
}

function animationMetadataText(asset: CatalogAsset): string {
  const metadata = asset.animation_metadata;
  if (!metadata) return '';
  const labels = metadata.labels || [];
  const names = metadata.generic_names || [];
  const parts: string[] = [];
  if (labels.length > 0) parts.push(labels.join(', '));
  if (names.length > 0) parts.push(names.join(', '));
  if (metadata.compatible_body_ids?.length) {
    const preview = metadata.compatible_body_ids.slice(0, 6).map((id) => `BODY.HQR:${id}`).join(', ');
    const extra = metadata.compatible_body_ids.length > 6 ? ` +${metadata.compatible_body_ids.length - 6}` : '';
    parts.push(`File3D bodies ${preview}${extra}`);
  }
  return parts.join(' | ');
}

function renderUnknownDescriptors(descriptors: RawAnimationStats['unknown_descriptors']): string {
  if (descriptors.length === 0) return '';
  const rows = descriptors
    .map(
      (descriptor) =>
        `<div class="unknown-descriptor">` +
        `<span>${escapeHtml(descriptor.section)}</span>` +
        `<span>offset ${escapeHtml(descriptor.offset)}, length ${escapeHtml(descriptor.length)}</span>` +
        `<span>${escapeHtml(descriptor.confidence)}</span>` +
        `<span>${escapeHtml(descriptor.sha256)}</span>` +
        `<span>${escapeHtml(descriptor.note)}</span>` +
        `</div>`,
    )
    .join('');
  return `<div class="unknown-descriptors">${rows}</div>`;
}

function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char] as string);
}
