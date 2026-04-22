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
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `raw animation payload, ${asset.decoded_bytes || raw.decoded_bytes || 0} bytes<br>` +
        `header words: ${escapeHtml((raw.header_words || []).join(', '))}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    const animation = stats as AnimationStats;
    this.options.detail.innerHTML =
      `<strong>${escapeHtml(asset.label)}</strong><br>` +
      `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
      `${animation.keyframes || 0} keyframes, ${animation.boneframes || 0} boneframes, loop frame ${animation.loop_frame ?? '-'}<br>` +
      `${animation.can_fall ? 'contains translation/fall frames' : 'rotation-only frames'}<br>` +
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
      if (!query) return true;
      return searchableText(asset).includes(query);
    });
    assets.sort((a, b) => scoreAsset(b, query) - scoreAsset(a, query) || assetSortKey(a).localeCompare(assetSortKey(b)));
    const visible = assets.slice(0, 260);
    this.options.summary.textContent =
      `${summary.models || 0} models, ${summary.animations || 0} animations across ${summary.hqr_files || 0} HQR files. ` +
      `Showing ${visible.length} of ${assets.length} matching entries.`;
    this.options.list.replaceChildren(...visible.map((asset) => this.assetButton(asset)));
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
    pill.textContent = asset.kind;
    title.append(name, pill);

    const meta = document.createElement('div');
    meta.className = 'asset-meta';
    meta.textContent = assetMeta(asset);

    button.append(title, meta);
    button.addEventListener('click', () => this.options.onSelect(asset));
    return button;
  }
}

function searchableText(asset: CatalogAsset): string {
  return [
    asset.id,
    asset.kind,
    asset.label,
    asset.entry_type,
    asset.source?.hqr,
    asset.source?.entry_index,
    Object.values(asset.stats || {}).join(' '),
  ].join(' ').toLowerCase();
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
    return `${source} - ${asset.decoded_bytes || asset.stats.decoded_bytes || 0} bytes, ${asset.entry_type}`;
  }
  const animation = asset.stats as AnimationStats;
  return `${source} - ${animation.keyframes || 0} keyframes, ${animation.boneframes || 0} bones, loop ${animation.loop_frame ?? '-'}`;
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
