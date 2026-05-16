import type { CatalogAsset, SpritePayload } from '../types';

export interface SpritePixelEvidence {
  x: number;
  y: number;
  paletteIndex: number;
  rgba: number[];
}

type SpriteStripState = 'decoded' | 'load_on_select' | 'missing';

interface SpriteStripItem {
  index: number;
  title: string;
  backend: string;
  palette: string;
  timing: string;
  state: SpriteStripState;
  frame?: NonNullable<SpritePayload['frame']>;
}

export interface SpriteViewerOptions {
  panel: HTMLElement;
  canvas: HTMLCanvasElement;
  title: HTMLElement;
  meta: HTMLElement;
  facts: HTMLElement;
  zoomIn: HTMLButtonElement;
  zoomOut: HTMLButtonElement;
  fit: HTMLButtonElement;
  previous: HTMLButtonElement;
  play: HTMLButtonElement;
  next: HTMLButtonElement;
  scrub: HTMLInputElement;
  frameLabel: HTMLElement;
  strip: HTMLElement;
  loadFrame: (asset: CatalogAsset) => Promise<SpritePayload>;
  onFrameLoaded: (asset: CatalogAsset, payload: SpritePayload) => void;
  onPixelPicked?: (asset: CatalogAsset, payload: SpritePayload, pixel: SpritePixelEvidence) => void;
}

export class SpriteViewer {
  private payload: SpritePayload | null = null;
  private sequence: CatalogAsset[] = [];
  private frameVariants: NonNullable<SpritePayload['frames']> = [];
  private sequenceIndex = 0;
  private zoom = 1;
  private loadingToken = 0;
  private playbackTimer: number | undefined;
  private hoverPixel: SpritePixelEvidence | null = null;
  private pickedPixel: SpritePixelEvidence | null = null;

  constructor(private readonly options: SpriteViewerOptions) {
    options.zoomIn.addEventListener('click', () => this.setZoom(this.zoom * 1.25));
    options.zoomOut.addEventListener('click', () => this.setZoom(this.zoom / 1.25));
    options.fit.addEventListener('click', () => this.fit());
    options.previous.addEventListener('click', () => void this.step(-1));
    options.next.addEventListener('click', () => void this.step(1));
    options.play.addEventListener('click', () => this.togglePlayback());
    options.scrub.addEventListener('input', () => void this.loadSequenceIndex(Number(options.scrub.value)));
    options.canvas.addEventListener('pointermove', (event) => this.updateHover(event));
    options.canvas.addEventListener('pointerdown', (event) => this.pickPixel(event));
    options.canvas.addEventListener('pointerleave', () => {
      this.hoverPixel = null;
      this.renderMeta();
    });
  }

  setSprite(payload: SpritePayload, sequence: CatalogAsset[] = []): void {
    this.stopPlayback();
    this.payload = payload;
    this.frameVariants = payload.frames || [];
    this.sequence = this.frameVariants.length > 0 ? [] : sequence;
    this.sequenceIndex = this.frameVariants.length > 0
      ? Math.max(0, this.frameVariants.findIndex((frame) => frame.variant === payload.frame?.variant))
      : Math.max(0, this.sequence.findIndex((asset) => asset.id === payload.sprite.id));
    if (this.sequenceIndex < 0) this.sequenceIndex = 0;
    this.options.title.textContent = payload.sprite.label;
    this.hoverPixel = null;
    this.pickedPixel = null;
    this.updateControls();
    this.updateScrub();
    this.renderStrip();
    if (payload.frame) {
      this.renderFrame(payload.frame);
      this.fit();
    } else {
      this.clearCanvas();
      this.zoom = 1;
      this.applyCanvasScale();
    }
    this.renderMeta();
    this.renderFacts();
  }

  stop(): void {
    this.stopPlayback();
    this.payload = null;
    this.sequence = [];
    this.frameVariants = [];
    this.sequenceIndex = 0;
    this.hoverPixel = null;
    this.pickedPixel = null;
    this.options.strip.textContent = 'No sprite frame strip.';
  }

  resize(): void {
    if (this.payload?.frame) this.fit();
  }

  private renderFrame(frame: NonNullable<SpritePayload['frame']>): void {
    const { canvas } = this.options;
    canvas.width = frame.width;
    canvas.height = frame.height;
    const context = canvas.getContext('2d');
    if (!context) return;
    this.paintFrame(context, frame);
  }

  private paintFrame(context: CanvasRenderingContext2D, frame: NonNullable<SpritePayload['frame']>): void {
    const image = context.createImageData(frame.width, frame.height);
    if (frame.rgba && frame.rgba.length === image.data.length) {
      image.data.set(frame.rgba);
    } else {
      const pixelCount = Math.min(frame.pixels.length, frame.width * frame.height);
      for (let index = 0; index < pixelCount; index += 1) {
        const color = frame.pixels[index];
        const offset = index * 4;
        image.data[offset] = color;
        image.data[offset + 1] = color;
        image.data[offset + 2] = color;
        image.data[offset + 3] = color === 0 ? 0 : 255;
      }
    }
    context.putImageData(image, 0, 0);
  }

  private clearCanvas(): void {
    const { canvas } = this.options;
    const context = canvas.getContext('2d');
    if (context) context.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = 1;
    canvas.height = 1;
  }

  private fit(): void {
    const frame = this.payload?.frame;
    if (!frame) return;
    const rect = this.options.panel.getBoundingClientRect();
    const maxWidth = Math.max(1, rect.width - 36);
    const maxHeight = Math.max(1, rect.height - 112);
    const fitZoom = Math.min(maxWidth / frame.width, maxHeight / frame.height);
    this.setZoom(Math.max(1, Math.floor(fitZoom)));
  }

  private setZoom(value: number): void {
    this.zoom = Math.max(1, Math.min(32, Number.isFinite(value) ? value : 1));
    this.applyCanvasScale();
    this.renderMeta();
  }

  private updateControls(): void {
    const hasFrame = Boolean(this.payload?.frame);
    const hasSequence = this.sequence.length > 1 || this.frameVariants.length > 1;
    this.options.zoomIn.disabled = !hasFrame;
    this.options.zoomOut.disabled = !hasFrame;
    this.options.fit.disabled = !hasFrame;
    this.options.previous.disabled = !hasSequence;
    this.options.next.disabled = !hasSequence;
    this.options.play.disabled = !hasSequence;
    this.options.scrub.disabled = !hasSequence;
  }

  private updateScrub(): void {
    const frameCount = this.frameVariants.length || this.sequence.length;
    const max = Math.max(0, frameCount - 1);
    this.options.scrub.max = String(max);
    this.options.scrub.value = String(Math.min(this.sequenceIndex, max));
    this.options.frameLabel.textContent = frameCount > 0
      ? `${this.sequenceIndex + 1} / ${frameCount}`
      : '0 / 0';
  }

  private renderStrip(): void {
    const items = this.stripItems();
    if (items.length === 0) {
      this.options.strip.textContent = 'No sprite frame strip.';
      return;
    }
    this.options.strip.replaceChildren(...items.map((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'sprite-frame-item';
      button.setAttribute('aria-current', String(item.index === this.sequenceIndex));
      button.dataset.state = item.state;
      button.title = `${item.title} | ${item.backend} | ${item.palette} | ${item.timing}`;
      button.addEventListener('click', () => void this.loadSequenceIndex(item.index));
      const thumbnail = this.renderStripThumbnail(item);
      thumbnail.setAttribute('aria-hidden', 'true');
      const details = document.createElement('span');
      details.className = 'sprite-frame-details';
      const title = document.createElement('strong');
      title.textContent = item.title;
      const backend = document.createElement('span');
      backend.textContent = item.backend;
      const palette = document.createElement('span');
      palette.textContent = item.palette;
      const timing = document.createElement('span');
      timing.textContent = item.timing;
      details.append(title, backend, palette, timing);
      button.append(thumbnail, details);
      return button;
    }));
  }

  private renderStripThumbnail(item: SpriteStripItem): HTMLElement {
    const thumbnail = document.createElement('span');
    thumbnail.className = 'sprite-frame-thumb';
    if (!item.frame) {
      thumbnail.classList.add(`sprite-frame-thumb-${item.state}`);
      thumbnail.textContent = item.state === 'missing' ? 'missing' : 'load';
      return thumbnail;
    }

    const canvas = document.createElement('canvas');
    canvas.width = item.frame.width;
    canvas.height = item.frame.height;
    const context = canvas.getContext('2d');
    if (context) this.paintFrame(context, item.frame);
    thumbnail.append(canvas);
    return thumbnail;
  }

  private stripItems(): SpriteStripItem[] {
    if (!this.payload) return [];
    if (this.frameVariants.length > 0) {
      return this.frameVariants.map((frame, index) => ({
        index,
        title: frame.variant_label || frame.variant || `Variant ${index + 1}`,
        backend: frame.format,
        palette: frame.palette_source || (frame.palette_available ? 'palette source attached' : 'preview grayscale'),
        timing: frameTimingLabel(this.payload!.sprite, frame),
        state: 'decoded',
        frame,
      }));
    }
    if (this.sequence.length > 0) {
      return this.sequence.map((asset, index) => ({
        index,
        title: stripFrameTitle(asset, index),
        backend: stripBackendLabel(asset),
        palette: stripPaletteLabel(asset),
        timing: stripTimingLabel(asset),
        state: index === this.sequenceIndex && this.payload?.frame ? 'decoded' : stripState(asset),
        frame: index === this.sequenceIndex ? this.payload?.frame : undefined,
      }));
    }
    const frame = this.payload.frame;
    return frame ? [{
      index: 0,
      title: stripFrameTitle(this.payload.sprite, 0),
      backend: stripBackendLabel(this.payload.sprite),
      palette: frame.palette_source || stripPaletteLabel(this.payload.sprite),
      timing: frameTimingLabel(this.payload.sprite, frame),
      state: 'decoded',
      frame,
    }] : [];
  }

  private async step(direction: -1 | 1): Promise<void> {
    const frameCount = this.frameVariants.length || this.sequence.length;
    if (frameCount < 2) return;
    const nextIndex = (this.sequenceIndex + direction + frameCount) % frameCount;
    await this.loadSequenceIndex(nextIndex);
  }

  private togglePlayback(): void {
    if (this.playbackTimer === undefined) {
      this.options.play.textContent = '||';
      this.options.play.setAttribute('aria-pressed', 'true');
      this.playbackTimer = window.setInterval(() => {
        void this.step(1);
      }, 120);
      return;
    }
    this.stopPlayback();
  }

  private stopPlayback(): void {
    if (this.playbackTimer !== undefined) {
      window.clearInterval(this.playbackTimer);
      this.playbackTimer = undefined;
    }
    this.options.play.textContent = '>';
    this.options.play.setAttribute('aria-pressed', 'false');
  }

  private async loadSequenceIndex(index: number): Promise<void> {
    if (this.frameVariants.length > 0) {
      const boundedIndex = Math.max(0, Math.min(this.frameVariants.length - 1, Math.round(index)));
      const frame = this.frameVariants[boundedIndex];
      if (!frame || !this.payload) return;
      this.sequenceIndex = boundedIndex;
      this.payload = { ...this.payload, frame };
      this.hoverPixel = null;
      this.pickedPixel = null;
      this.options.title.textContent = `${this.payload.sprite.label} - ${frame.variant_label || frame.variant || `variant ${boundedIndex + 1}`}`;
      this.renderFrame(frame);
      this.applyCanvasScale();
      this.updateControls();
      this.updateScrub();
      this.renderStrip();
      this.renderMeta();
      this.renderFacts();
      this.options.onFrameLoaded(this.payload.sprite, this.payload);
      return;
    }
    if (this.sequence.length === 0) return;
    const boundedIndex = Math.max(0, Math.min(this.sequence.length - 1, Math.round(index)));
    const asset = this.sequence[boundedIndex];
    if (!asset) return;
    const token = ++this.loadingToken;
    this.sequenceIndex = boundedIndex;
    this.options.title.textContent = asset.label;
    this.options.meta.textContent = `Loading ${asset.label}...`;
    this.updateScrub();
    let payload: SpritePayload;
    try {
      payload = await this.options.loadFrame(asset);
    } catch (error) {
      if (token !== this.loadingToken) return;
      this.stopPlayback();
      this.options.meta.textContent = error instanceof Error ? error.message : String(error);
      return;
    }
    if (token !== this.loadingToken) return;
    this.payload = payload;
    this.hoverPixel = null;
    this.pickedPixel = null;
    this.options.title.textContent = payload.sprite.label;
    if (payload.frame) {
      this.renderFrame(payload.frame);
      this.applyCanvasScale();
    } else {
      this.clearCanvas();
    }
    this.updateControls();
    this.renderMeta();
    this.renderFacts();
    this.renderStrip();
    this.options.onFrameLoaded(asset, payload);
  }

  private applyCanvasScale(): void {
    const frame = this.payload?.frame;
    const width = frame?.width || 1;
    const height = frame?.height || 1;
    this.options.canvas.style.width = `${Math.round(width * this.zoom)}px`;
    this.options.canvas.style.height = `${Math.round(height * this.zoom)}px`;
  }

  private updateHover(event: PointerEvent): void {
    this.hoverPixel = this.pixelEvidenceFromEvent(event);
    this.renderMeta();
  }

  private pickPixel(event: PointerEvent): void {
    this.pickedPixel = this.pixelEvidenceFromEvent(event);
    this.renderMeta();
    this.renderFacts();
    if (this.pickedPixel && this.payload) {
      this.options.onPixelPicked?.(this.payload.sprite, this.payload, this.pickedPixel);
    }
  }

  private pixelEvidenceFromEvent(event: PointerEvent): SpritePixelEvidence | null {
    const frame = this.payload?.frame;
    if (!frame) return null;
    const rect = this.options.canvas.getBoundingClientRect();
    const x = Math.floor(((event.clientX - rect.left) / rect.width) * frame.width);
    const y = Math.floor(((event.clientY - rect.top) / rect.height) * frame.height);
    if (x < 0 || y < 0 || x >= frame.width || y >= frame.height) {
      return null;
    }
    const pixelOffset = y * frame.width + x;
    const paletteIndex = frame.pixels[pixelOffset];
    const rgbaOffset = pixelOffset * 4;
    const rgba = frame.rgba && rgbaOffset + 3 < frame.rgba.length
      ? [frame.rgba[rgbaOffset], frame.rgba[rgbaOffset + 1], frame.rgba[rgbaOffset + 2], frame.rgba[rgbaOffset + 3]]
      : [paletteIndex, paletteIndex, paletteIndex, paletteIndex === 0 ? 0 : 255];
    return { x, y, paletteIndex, rgba };
  }

  private renderMeta(): void {
    const frame = this.payload?.frame;
    if (!this.payload) {
      this.options.meta.textContent = 'Select a sprite asset from the catalog.';
      return;
    }
    if (!frame) {
      this.options.meta.textContent = `${this.payload.sprite.source.hqr}[${this.payload.sprite.source.entry_index}] - no decoded sprite frame payload`;
      return;
    }
    const alpha = frame.palette_available ? 'palette RGBA' : 'palette-index grayscale';
    const range = spriteRangeLabel(this.payload.sprite);
    const runtime = spriteRuntimeLabel(this.payload.sprite);
    const timing = frameTimingLabel(this.payload.sprite, frame);
    const palette = frame.palette_source ? `, ${frame.palette_source}` : '';
    const hover = this.hoverPixel ? ` - hover ${pixelEvidenceText(this.hoverPixel)}` : '';
    const picked = this.pickedPixel ? ` - picked ${pixelEvidenceText(this.pickedPixel)}` : '';
    this.options.meta.textContent =
      `${range}${runtime}${frame.width}x${frame.height}, offset ${frame.offset_x},${frame.offset_y}, ${alpha}${palette}, ${this.zoom.toFixed(this.zoom % 1 === 0 ? 0 : 1)}x, ${timing}${hover}${picked}`;
  }

  private renderFacts(): void {
    const sprite = this.payload?.sprite;
    const stats = sprite?.stats;
    if (!sprite || !stats || !('semantic_layout' in stats)) {
      this.options.facts.replaceChildren();
      return;
    }
    if (stats.semantic_layout === 'bkg_brick_graphic') {
      const facts: Array<[string, string]> = [
        ['Backend', 'LBA_BKG BRK AffGraph'],
        ['Asset', sprite.id],
        ['Opaque', String(stats.opaque_pixels ?? '-')],
        ['Palette', `${stats.color_count ?? '-'} indices`],
        ['Hot point', `${stats.offset_x ?? '-'}, ${stats.offset_y ?? '-'}`],
      ];
      this.options.facts.replaceChildren(...facts.map(([label, value]) => spriteFact(label, value)));
      return;
    }
    if (stats.semantic_layout === 'bkg_grid_map') {
      const preview = stats.preview;
      const facts: Array<[string, string]> = [
        ['Backend', 'LBA_BKG GRI/BLL/BRK evidence render'],
        ['Asset', sprite.id],
        ['Cells', String(preview?.drawn_cells ?? stats.fields?.nonzero_cells ?? '-')],
        ['Pixels', String(preview?.drawn_pixels ?? '-')],
        ['BRKs', String(preview?.unique_bricks_loaded ?? '-')],
      ];
      this.options.facts.replaceChildren(...facts.map(([label, value]) => spriteFact(label, value)));
      return;
    }
    if (stats.semantic_layout === 'scene_runtime_layout_partial') {
      const frame = this.payload?.frame;
      const facts: Array<[string, string]> = [
        ['Backend', 'SCENE background GRI/GRM evidence render'],
        ['Asset', sprite.id],
        ['Variant', frame?.variant_label || frame?.variant || '-'],
        ['Policy', frame?.variant_policy || 'base plus explicit GRM-on variants'],
        ['Cube', String(frame?.scene_background?.runtime_cube ?? '-')],
        ['GRI/BLL/GRM', `${frame?.scene_background?.resolved_gri_entry ?? '-'}/${frame?.scene_background?.resolved_bll_entry ?? '-'}/${frame?.scene_background?.resolved_grm_entry ?? '-'}`],
        ['Changed cells', String(frame?.changed_cells ?? '-')],
        ['Y spill', String(frame?.column_y_overflow_cells ?? '-')],
      ];
      this.options.facts.replaceChildren(...facts.map(([label, value]) => spriteFact(label, value)));
      return;
    }
    if (stats.semantic_layout !== 'lsp_sprite_frame' && stats.semantic_layout !== 'raw_sprite_frame') {
      this.options.facts.replaceChildren();
      return;
    }
    const runtime = stats.runtime;
    const facts: Array<[string, string]> = [
      ['Backend', runtime?.backend || 'unknown'],
      ['Asset', runtime?.asset_id || sprite.id],
      ['Opaque', String(stats.opaque_pixels)],
      ['Palette', `${stats.color_count} colors`],
    ];
    if (this.pickedPixel) facts.push(['Picked pixel', pixelEvidenceText(this.pickedPixel)]);
    if (runtime?.hotspot) facts.push(['Hotspot', `${runtime.hotspot.x}, ${runtime.hotspot.y}`]);
    if (runtime?.bounds) {
      facts.push([
        'Bounds',
        `x ${runtime.bounds.min_x}..${runtime.bounds.max_x}, y ${runtime.bounds.min_y}..${runtime.bounds.max_y}, z ${runtime.bounds.min_z}..${runtime.bounds.max_z}`,
      ]);
    }
    if (stats.direct_code_references?.length) {
      const first = stats.direct_code_references[0];
      const suffix = stats.direct_code_references.length > 1 ? ` +${stats.direct_code_references.length - 1}` : '';
      facts.push(['Direct ref', `${first.symbol}: ${first.purpose}${suffix}`]);
    }
    this.options.facts.replaceChildren(...facts.map(([label, value]) => spriteFact(label, value)));
  }

}

function spriteRangeLabel(asset: CatalogAsset): string {
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'lsp_sprite_frame' || !stats.anim3ds_info) return '';
  return `${stats.anim3ds_info.name} frame ${stats.anim3ds_info.relative_frame} - `;
}

function spriteRuntimeLabel(asset: CatalogAsset): string {
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || (stats.semantic_layout !== 'lsp_sprite_frame' && stats.semantic_layout !== 'raw_sprite_frame') || !stats.runtime) return '';
  return `${stats.runtime.backend} Sprite ${stats.runtime.runtime_sprite_index} - `;
}

function stripFrameTitle(asset: CatalogAsset, frameIndex: number): string {
  const stats = asset.stats;
  if ('semantic_layout' in stats && stats.semantic_layout === 'lsp_sprite_frame' && stats.anim3ds_info) {
    return `${stats.anim3ds_info.name} frame ${stats.anim3ds_info.relative_frame}`;
  }
  return `${asset.id} frame ${frameIndex + 1}`;
}

function stripBackendLabel(asset: CatalogAsset): string {
  const stats = asset.stats;
  if (!('semantic_layout' in stats)) return asset.kind;
  if (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame') {
    const runtime = stats.runtime;
    if (!runtime) return stats.sprite_backend || 'decoded-only';
    if (runtime.backend === 'anim3ds') return 'ANIM3DS';
    if (runtime.backend === 'sprites') return 'SPRITES';
    if (runtime.backend === 'spriraw') return 'SPRIRAW';
    return runtime.backend || 'unresolved';
  }
  if (stats.semantic_layout === 'bkg_brick_graphic') return 'BRK AffGraph';
  if (stats.semantic_layout === 'bkg_grid_map') return 'GRI/BLL/BRK preview';
  if (stats.semantic_layout === 'scene_runtime_layout_partial') return 'SCENE background preview';
  return stats.semantic_layout;
}

function stripPaletteLabel(asset: CatalogAsset): string {
  const stats = asset.stats;
  if (!('semantic_layout' in stats)) return 'palette unknown';
  if (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame') {
    return 'normal RESS.HQR:0 preview palette';
  }
  if (stats.semantic_layout === 'bkg_brick_graphic' || stats.semantic_layout === 'bkg_grid_map') {
    return 'preview palette';
  }
  if (stats.semantic_layout === 'scene_runtime_layout_partial') {
    const palette = stats.reconnaissance.background?.palette;
    return palette?.resolved_palette_entry === undefined
      ? 'background palette unknown'
      : `active runtime palette RESS.HQR:${palette.resolved_palette_entry}`;
  }
  return 'palette unknown';
}

function stripTimingLabel(asset: CatalogAsset): string {
  const stats = asset.stats;
  if ('semantic_layout' in stats && stats.semantic_layout === 'lsp_sprite_frame' && stats.anim3ds_info) {
    return 'decoded ANIM3DS range order; FPS needs scene object evidence';
  }
  return 'timing unknown';
}

function stripState(asset: CatalogAsset): SpriteStripState {
  const stats = asset.stats;
  if (!('semantic_layout' in stats)) return 'missing';
  if (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame') return 'load_on_select';
  if (
    stats.semantic_layout === 'bkg_brick_graphic'
    || stats.semantic_layout === 'bkg_grid_map'
    || stats.semantic_layout === 'scene_runtime_layout_partial'
  ) {
    return 'load_on_select';
  }
  return 'missing';
}

function frameTimingLabel(asset: CatalogAsset, frame: NonNullable<SpritePayload['frame']>): string {
  if (frame.format === 'bkg_affgraph') return 'static BRK graph';
  if (frame.format === 'bkg_grid_preview') return frame.variant_label ? `scene background ${frame.variant_label}` : 'static background evidence render';
  return stripTimingLabel(asset);
}

function pixelEvidenceText(pixel: SpritePixelEvidence): string {
  return `${pixel.x},${pixel.y} palette ${pixel.paletteIndex} rgba ${pixel.rgba.join(',')}`;
}

function spriteFact(label: string, value: string): HTMLElement {
  const fact = document.createElement('div');
  fact.className = 'sprite-fact';
  const factLabel = document.createElement('span');
  factLabel.textContent = label;
  const factValue = document.createElement('strong');
  factValue.textContent = value;
  fact.append(factLabel, factValue);
  return fact;
}
