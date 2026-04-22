import type { Lm2Model } from '../types';

type PolygonEvidence = {
  polygon_index: number;
  material: {
    kind: 'texture' | 'palette';
    value: number;
    color_word: number;
    palette_index: number;
    intensity: number;
  };
  render_flags: {
    render_type: number;
    has_texture: boolean;
    has_extra: boolean;
    has_transparency: boolean;
  };
  vertices: number[];
  uv_group: null | {
    index: number;
    encoded: { x: number; y: number; w: number; h: number };
    sampled_region: { x: number; y: number; width: number; height: number } | null;
  };
  uv: Array<[number, number]> | null;
  sampled_atlas_points: Array<{ x: number; y: number; color: string }> | null;
  unknowns: Array<{ field: string; value: boolean | number | string; note: string }>;
};

type UiElements = {
  root: HTMLDivElement;
  polygon: HTMLSelectElement;
  atlas: HTMLCanvasElement;
  facts: HTMLDivElement;
  previous: HTMLButtonElement;
  next: HTMLButtonElement;
  copy: HTMLButtonElement;
  download: HTMLButtonElement;
  result: HTMLDivElement;
};

export class UvInspector {
  private model: Lm2Model | null = null;
  private selectedIndex = 0;
  private optionsModel: Lm2Model | null = null;

  constructor(private readonly elements: UiElements) {
    elements.polygon.addEventListener('change', () => {
      this.selectedIndex = Number(elements.polygon.value) || 0;
      this.render();
    });
    elements.previous.addEventListener('click', () => this.step(-1));
    elements.next.addEventListener('click', () => this.step(1));
    elements.copy.addEventListener('click', () => void this.copyEvidence());
    elements.download.addEventListener('click', () => this.downloadEvidence());
    this.render();
  }

  setModel(model: Lm2Model | null): void {
    this.model = model;
    this.selectedIndex = 0;
    this.optionsModel = null;
    this.elements.result.textContent = '';
    this.render();
  }

  private step(delta: number): void {
    if (!this.model || this.model.polygons.length === 0) return;
    this.selectedIndex = (this.selectedIndex + delta + this.model.polygons.length) % this.model.polygons.length;
    this.render();
  }

  private render(): void {
    const model = this.model;
    const hasPolygons = Boolean(model && model.polygons.length > 0);
    this.elements.root.hidden = !hasPolygons;
    this.elements.root.classList.toggle('empty', !hasPolygons);
    this.elements.polygon.disabled = !hasPolygons;
    this.elements.previous.disabled = !hasPolygons;
    this.elements.next.disabled = !hasPolygons;
    this.elements.copy.disabled = !hasPolygons;
    this.elements.download.disabled = !hasPolygons;

    if (!model || model.polygons.length === 0) {
      this.elements.polygon.replaceChildren();
      this.optionsModel = null;
      this.elements.facts.textContent = model ? 'Model has no polygons.' : 'No model loaded.';
      this.clearAtlas();
      return;
    }

    this.selectedIndex = Math.max(0, Math.min(model.polygons.length - 1, this.selectedIndex));
    if (this.optionsModel !== model) this.renderOptions(model);
    this.elements.polygon.value = String(this.selectedIndex);
    const evidence = polygonEvidence(model, this.selectedIndex);
    this.elements.facts.replaceChildren(...factNodes(evidence));
    this.drawAtlas(model, evidence);
  }

  private renderOptions(model: Lm2Model): void {
    const options = model.polygons.map((poly, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      const material = poly.has_texture && poly.texture !== null ? `texture ${poly.texture}` : `palette ${poly.palette_index}`;
      option.textContent = `Polygon ${index} - ${material}`;
      return option;
    });
    this.elements.polygon.replaceChildren(...options);
    this.elements.polygon.value = String(this.selectedIndex);
    this.optionsModel = model;
  }

  private clearAtlas(): void {
    const context = this.elements.atlas.getContext('2d');
    if (!context) return;
    context.clearRect(0, 0, this.elements.atlas.width, this.elements.atlas.height);
  }

  private drawAtlas(model: Lm2Model, evidence: PolygonEvidence): void {
    const canvas = this.elements.atlas;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!model.texture_atlas) {
      context.fillStyle = '#101315';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = '#aeb7c2';
      context.font = '12px sans-serif';
      context.fillText('No atlas', 12, 24);
      return;
    }

    const atlas = model.texture_atlas;
    canvas.width = atlas.width;
    canvas.height = atlas.height;
    const image = context.createImageData(atlas.width, atlas.height);
    for (let index = 0; index < atlas.width * atlas.height; index += 1) {
      const color = atlas.pixels[index] ?? 0;
      image.data[index * 4] = (color >> 16) & 0xff;
      image.data[index * 4 + 1] = (color >> 8) & 0xff;
      image.data[index * 4 + 2] = color & 0xff;
      image.data[index * 4 + 3] = 0xff;
    }
    context.putImageData(image, 0, 0);

    if (!evidence.uv_group) return;
    const region = evidence.uv_group.sampled_region;
    context.save();
    if (region) {
      context.strokeStyle = '#7ee2b8';
      context.lineWidth = 2;
      context.strokeRect(region.x + 0.5, region.y + 0.5, Math.max(1, region.width - 1), Math.max(1, region.height - 1));
    }

    const points = evidence.sampled_atlas_points || [];
    if (points.length > 0) {
      context.beginPath();
      for (const [index, point] of points.entries()) {
        if (index === 0) context.moveTo(point.x, point.y);
        else context.lineTo(point.x, point.y);
      }
      context.closePath();
      context.strokeStyle = '#ffffff';
      context.lineWidth = 1;
      context.stroke();
      context.fillStyle = '#ffcf66';
      for (const point of points) {
        context.beginPath();
        context.arc(point.x, point.y, 2.4, 0, Math.PI * 2);
        context.fill();
      }
    }
    context.restore();
  }

  private evidence(): PolygonEvidence | null {
    if (!this.model || this.model.polygons.length === 0) return null;
    return polygonEvidence(this.model, this.selectedIndex);
  }

  private async copyEvidence(): Promise<void> {
    const evidence = this.evidence();
    if (!evidence) return;
    const text = JSON.stringify(evidence, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      this.elements.result.textContent = `Copied polygon ${evidence.polygon_index} evidence`;
    } catch (error) {
      this.elements.result.textContent = error instanceof Error ? error.message : String(error);
    }
  }

  private downloadEvidence(): void {
    const evidence = this.evidence();
    if (!evidence) return;
    const blob = new Blob([JSON.stringify(evidence, null, 2) + '\n'], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `lm2-polygon-${evidence.polygon_index.toString().padStart(3, '0')}-uv-evidence.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    this.elements.result.textContent = `Downloaded polygon ${evidence.polygon_index} evidence`;
  }
}

function polygonEvidence(model: Lm2Model, polygonIndex: number): PolygonEvidence {
  const poly = model.polygons[polygonIndex];
  const uvGroup = poly.has_texture && poly.texture !== null ? model.uv_groups[poly.texture] : undefined;
  const sampledRegion = uvGroup ? sampledRegionForGroup(model, poly.texture!) : null;
  const sampledPoints = uvGroup && sampledRegion && poly.uv ? poly.uv.map((coord) => atlasPoint(model, poly.texture!, coord)) : null;
  const material =
    poly.has_texture && poly.texture !== null
      ? { kind: 'texture' as const, value: poly.texture, color_word: poly.color_word, palette_index: poly.palette_index, intensity: poly.intensity }
      : { kind: 'palette' as const, value: poly.palette_index, color_word: poly.color_word, palette_index: poly.palette_index, intensity: poly.intensity };
  return {
    polygon_index: polygonIndex,
    material,
    render_flags: {
      render_type: poly.render_type,
      has_texture: poly.has_texture,
      has_extra: poly.has_extra,
      has_transparency: poly.has_transparency,
    },
    vertices: [...poly.vertices],
    uv_group:
      uvGroup
        ? {
            index: poly.texture!,
            encoded: { x: uvGroup.x, y: uvGroup.y, w: uvGroup.w, h: uvGroup.h },
            sampled_region: sampledRegion,
          }
        : null,
    uv: poly.uv ? [...poly.uv] : null,
    sampled_atlas_points: sampledPoints,
    unknowns: unknownsForPolygon(poly),
  };
}

function sampledRegionForGroup(model: Lm2Model, textureIndex: number): { x: number; y: number; width: number; height: number } | null {
  const group = model.uv_groups[textureIndex];
  const atlas = model.texture_atlas;
  if (!group || !atlas) return null;
  if (group.w === 0xff && group.h === 0xff) {
    return { x: group.x, y: group.y, width: atlas.width, height: atlas.height };
  }
  return { x: group.x, y: group.y, width: group.w, height: group.h };
}

function atlasPoint(model: Lm2Model, textureIndex: number, coord: [number, number]): { x: number; y: number; color: string } {
  const group = model.uv_groups[textureIndex];
  const atlas = model.texture_atlas;
  if (!group || !atlas) return { x: coord[0], y: coord[1], color: '#000000' };
  const region = sampledRegionForGroup(model, textureIndex);
  const x = group.w === 0xff && group.h === 0xff ? group.x + coord[0] : group.x + coord[0];
  const y = group.w === 0xff && group.h === 0xff ? group.y + coord[1] : group.y + coord[1];
  const sampleX = Math.max(0, Math.min(atlas.width - 1, Math.round(x)));
  const sampleY = Math.max(0, Math.min(atlas.height - 1, Math.round(y)));
  const color = atlas.pixels[sampleY * atlas.width + sampleX] ?? 0;
  const maxX = region ? region.x + Math.max(0, region.width - 1) : x;
  const maxY = region ? region.y + Math.max(0, region.height - 1) : y;
  return {
    x: region ? Math.max(region.x, Math.min(maxX, x)) : x,
    y: region ? Math.max(region.y, Math.min(maxY, y)) : y,
    color: `#${color.toString(16).padStart(6, '0')}`,
  };
}

function unknownsForPolygon(poly: Lm2Model['polygons'][number]): PolygonEvidence['unknowns'] {
  const unknowns: PolygonEvidence['unknowns'] = [];
  if (poly.has_extra) {
    unknowns.push({
      field: 'render_type.has_extra',
      value: poly.has_extra,
      note: 'Flag is parsed but semantics are not decoded yet.',
    });
  }
  return unknowns;
}

function factNodes(evidence: PolygonEvidence): HTMLElement[] {
  return [
    fact('Polygon', String(evidence.polygon_index)),
    fact('Material', `${evidence.material.kind} ${evidence.material.value}`),
    fact('Render', `0x${evidence.render_flags.render_type.toString(16)}${evidence.render_flags.has_transparency ? ', transparent' : ''}${evidence.render_flags.has_extra ? ', extra' : ''}`),
    fact('Vertices', evidence.vertices.join(', ')),
    fact('UV group', uvGroupText(evidence)),
    fact('UV', evidence.uv ? evidence.uv.map(([u, v]) => `${formatNumber(u)},${formatNumber(v)}`).join(' | ') : 'none'),
    fact('Samples', evidence.sampled_atlas_points ? evidence.sampled_atlas_points.map((point) => `${formatNumber(point.x)},${formatNumber(point.y)} ${point.color}`).join(' | ') : 'none'),
    fact('Unknowns', evidence.unknowns.length ? evidence.unknowns.map((item) => `${item.field}=${item.value}`).join(', ') : 'none'),
  ];
}

function fact(label: string, value: string): HTMLElement {
  const row = document.createElement('div');
  const key = document.createElement('span');
  const val = document.createElement('span');
  key.textContent = label;
  val.textContent = value;
  row.append(key, val);
  return row;
}

function uvGroupText(evidence: PolygonEvidence): string {
  if (!evidence.uv_group) return 'none';
  const encoded = evidence.uv_group.encoded;
  if (!evidence.uv_group.sampled_region) {
    return `${evidence.uv_group.index} encoded ${encoded.x},${encoded.y} ${encoded.w}x${encoded.h}; no atlas`;
  }
  const region = evidence.uv_group.sampled_region;
  return `${evidence.uv_group.index} @ ${region.x},${region.y} ${region.width}x${region.height}`;
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}
