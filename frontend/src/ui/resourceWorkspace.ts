import type { CatalogAsset, ResourceStats, SpriteFramePayload } from '../types';

export interface ResourceRecordEvidence {
  stableId: string;
  label: string;
  kind: string;
  summary: string;
  detail: string;
  rows: Array<[string, string]>;
}

export interface ResourceWorkspaceOptions {
  panel: HTMLElement;
  title: HTMLElement;
  meta: HTMLElement;
  facts: HTMLElement;
  records: HTMLElement;
  stage: HTMLElement;
  canvas: HTMLCanvasElement;
  audioWrap: HTMLElement;
  audio: HTMLAudioElement;
  audioMeta: HTMLElement;
  onRecordSelected?: (asset: CatalogAsset, record: ResourceRecordEvidence) => void;
}

export class ResourceWorkspace {
  private asset: CatalogAsset | null = null;
  private frame: SpriteFramePayload | null = null;
  private zoom = 1;
  private currentRecordId: string | null = null;

  constructor(private readonly options: ResourceWorkspaceOptions) {}

  setResource(asset: CatalogAsset, frame?: SpriteFramePayload, audioUrl?: string | null): void {
    this.asset = asset;
    this.frame = frame || null;
    this.zoom = 1;
    this.currentRecordId = null;
    this.options.title.textContent = asset.label;
    this.options.meta.textContent = resourceMeta(asset, this.frame);
    this.options.facts.replaceChildren(...resourceFacts(asset, this.frame).map(([label, value]) => factNode(label, value)));
    this.renderRecords(asset);
    if (this.frame) {
      this.renderFrame(this.frame);
      this.fit();
      this.options.stage.hidden = false;
    } else {
      this.clearCanvas();
      this.options.stage.hidden = true;
    }
    this.setAudio(asset, audioUrl || null);
  }

  clear(message = 'Select a resource asset from the explorer.'): void {
    this.asset = null;
    this.frame = null;
    this.currentRecordId = null;
    this.options.title.textContent = 'No resource selected';
    this.options.meta.textContent = message;
    this.options.facts.replaceChildren();
    this.options.records.textContent = 'No selectable resource records.';
    this.clearCanvas();
    this.options.stage.hidden = true;
    this.setAudio(null, null);
  }

  resize(): void {
    if (this.frame) this.fit();
  }

  setSelectedRecordId(recordId: string | null): void {
    if (this.currentRecordId === recordId) return;
    this.currentRecordId = recordId;
    if (this.asset) this.renderRecords(this.asset);
  }

  private setAudio(asset: CatalogAsset | null, audioUrl: string | null): void {
    this.options.audio.pause();
    this.options.audio.removeAttribute('src');
    this.options.audio.load();
    this.options.audioWrap.hidden = true;
    this.options.audioMeta.textContent = '';
    if (!asset || !audioUrl) return;
    const stats = asset.stats;
    if (!('semantic_layout' in stats) || stats.semantic_layout !== 'sample_wave_audio') return;
    const sample = stats as ResourceStats;
    this.options.audio.src = audioUrl;
    this.options.audioMeta.textContent = [
      `Sample ${sample.sample_runtime_index ?? asset.source.entry_index}`,
      sample.audio_format || 'audio',
      `${sample.fields?.sample_rate ?? '-'}Hz`,
      `${sample.fields?.channels ?? '-'}ch`,
      `${sample.duration_ms ?? '-'} ms`,
    ].join(' | ');
    this.options.audioWrap.hidden = false;
  }

  private renderRecords(asset: CatalogAsset): void {
    const records = resourceRecords(asset);
    if (records.length === 0) {
      this.options.records.textContent = 'No selectable resource records.';
      return;
    }
    this.options.records.replaceChildren(...records.map((record) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'resource-record-item';
      button.setAttribute('aria-current', String(record.stableId === this.currentRecordId));
      button.title = `${record.label} | ${record.summary} | ${record.detail}`;
      button.addEventListener('click', () => {
        this.currentRecordId = record.stableId;
        this.renderRecords(asset);
        this.options.onRecordSelected?.(asset, record);
      });
      const title = document.createElement('strong');
      title.textContent = record.label;
      const kind = document.createElement('span');
      kind.textContent = record.kind;
      const summary = document.createElement('span');
      summary.textContent = record.summary;
      const detail = document.createElement('span');
      detail.textContent = record.detail;
      button.append(title, kind, summary, detail);
      return button;
    }));
  }

  private renderFrame(frame: SpriteFramePayload): void {
    const { canvas } = this.options;
    canvas.width = frame.width;
    canvas.height = frame.height;
    const context = canvas.getContext('2d');
    if (!context) return;
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
    const context = this.options.canvas.getContext('2d');
    if (context) context.clearRect(0, 0, this.options.canvas.width, this.options.canvas.height);
    this.options.canvas.width = 1;
    this.options.canvas.height = 1;
    this.applyCanvasScale();
  }

  private fit(): void {
    const frame = this.frame;
    if (!frame) return;
    const rect = this.options.panel.getBoundingClientRect();
    const maxWidth = Math.max(1, rect.width - 40);
    const maxHeight = Math.max(1, rect.height - 190);
    const fitZoom = Math.min(maxWidth / frame.width, maxHeight / frame.height);
    this.zoom = Math.max(1, Math.floor(fitZoom));
    this.applyCanvasScale();
  }

  private applyCanvasScale(): void {
    const width = this.frame?.width || 1;
    const height = this.frame?.height || 1;
    this.options.canvas.style.width = `${Math.round(width * this.zoom)}px`;
    this.options.canvas.style.height = `${Math.round(height * this.zoom)}px`;
  }
}

function resourceMeta(asset: CatalogAsset, frame: SpriteFramePayload | null): string {
  const stats = asset.stats;
  const layout = 'semantic_layout' in stats ? stats.semantic_layout : asset.entry_type;
  const preview = frame
    ? `${frame.width}x${frame.height} ${frame.format}, ${frame.palette_source || 'palette context unknown'}`
    : 'no visual frame payload';
  return `${asset.source.hqr}[${asset.source.entry_index}] | ${layout} | ${preview}`;
}

function resourceFacts(asset: CatalogAsset, frame: SpriteFramePayload | null): Array<[string, string]> {
  const stats = asset.stats as ResourceStats;
  const facts: Array<[string, string]> = [
    ['Stable asset', asset.id],
    ['Layout', stats.semantic_layout || asset.entry_type],
    ['Evidence', stats.decode_note || '-'],
    ['Bytes', String(asset.decoded_bytes)],
  ];
  if (stats.width !== undefined || stats.height !== undefined) facts.push(['Dimensions', `${stats.width ?? '-'} x ${stats.height ?? '-'}`]);
  if (stats.record_count !== undefined) facts.push(['Records', String(stats.record_count)]);
  if (stats.color_count !== undefined) facts.push(['Palette colors', String(stats.color_count)]);
  if (stats.audio_format) facts.push(['Audio', `${stats.audio_format}, ${stats.fields?.sample_rate ?? '-'}Hz, ${stats.fields?.channels ?? '-'}ch`]);
  if (stats.runtime_table_name) facts.push(['Runtime table', stats.runtime_table_name]);
  if (frame?.drawn_cells !== undefined) facts.push(['Drawn cells', String(frame.drawn_cells)]);
  if (frame?.drawn_pixels !== undefined) facts.push(['Drawn pixels', String(frame.drawn_pixels)]);
  if (frame?.missing_bricks !== undefined) facts.push(['Missing BRKs', String(frame.missing_bricks)]);
  if (frame?.variant_label) facts.push(['Variant', frame.variant_label]);
  return facts;
}

function resourceRecords(asset: CatalogAsset): ResourceRecordEvidence[] {
  const stats = asset.stats as ResourceStats;
  const records: ResourceRecordEvidence[] = [];
  const paletteEntry = stats.palette_entry ? `${stats.palette_entry.hqr}:${stats.palette_entry.entry_index}` : null;
  if (
    paletteEntry
    || stats.source_provenance
    || stats.runtime_reference_status
    || stats.scene_palette_reference_count !== undefined
    || stats.screen_pair_base !== undefined
    || stats.paired_entry_index !== undefined
  ) {
    const pairedEntry = stats.paired_entry_index === undefined ? '-' : `${asset.source.hqr}:${stats.paired_entry_index}`;
    records.push({
      stableId: `${asset.id}#palette:${paletteEntry || pairedEntry}`,
      label: 'Palette Context',
      kind: 'palette_context',
      summary: paletteEntry || pairedEntry || stats.runtime_reference_status || 'palette context',
      detail: stats.source_provenance || stats.runtime_reference_status || stats.semantic_layout || 'decoded palette context',
      rows: [
        ['Palette source', paletteEntry || '-'],
        ['Source provenance', stats.source_provenance || '-'],
        ['Runtime reference', stats.runtime_reference_status || '-'],
        ['Scene palette refs', String(stats.scene_palette_reference_count ?? '-')],
        ['Screen pair base', String(stats.screen_pair_base ?? '-')],
        ['Paired entry', pairedEntry],
      ],
    });
  }
  for (const record of (stats.sampled_records || []).slice(0, 24)) {
    const label = record.backend ? `${record.backend} ${record.index}` : `Record ${record.index}`;
    records.push({
      stableId: `${asset.id}#record:${record.index}`,
      label,
      kind: stats.semantic_layout || 'sampled_record',
      summary: record.preview || record.preview_hex || record.sha256 || record.source ? formatRecordSummary(record) : formatRecordSummary(record),
      detail: record.offset === undefined ? `${record.byte_length ?? '-'} bytes` : `offset ${record.offset}, ${record.byte_length ?? '-'} bytes`,
      rows: recordRows(record),
    });
  }
  for (const [index, messageId] of (stats.sampled_message_ids || []).slice(0, 24).entries()) {
    records.push({
      stableId: `${asset.id}#message:${messageId}`,
      label: `Message ${messageId}`,
      kind: 'text_message_id',
      summary: stats.text_file_name || stats.language || 'sampled message id',
      detail: `sample ${index}`,
      rows: [
        ['Message ID', String(messageId)],
        ['Text file', stats.text_file_name || '-'],
        ['Language', stats.language || '-'],
        ['Sample index', String(index)],
      ],
    });
  }
  for (const [index, name] of (stats.sampled_names || []).slice(0, 24).entries()) {
    records.push({
      stableId: `${asset.id}#name:${index}`,
      label: `Name ${index}`,
      kind: 'name_record',
      summary: name,
      detail: stats.semantic_layout || 'sampled name',
      rows: [
        ['Index', String(index)],
        ['Name', name],
        ['Layout', stats.semantic_layout || '-'],
      ],
    });
  }
  for (const cell of (stats.sampled_cell_refs || []).slice(0, 24)) {
    records.push({
      stableId: `${asset.id}#cell:${cell.block}:${cell.cell}`,
      label: `Block ${cell.block} cell ${cell.cell}`,
      kind: 'background_cell_ref',
      summary: `brick ${cell.brick_ref} -> BRK ${cell.resolved_brk_entry}`,
      detail: `xyz ${cell.x},${cell.y},${cell.z}`,
      rows: [
        ['Block', String(cell.block)],
        ['Cell', String(cell.cell)],
        ['Position', `${cell.x}, ${cell.y}, ${cell.z}`],
        ['Brick ref', String(cell.brick_ref)],
        ['Resolved BRK', String(cell.resolved_brk_entry)],
        ['Collision', String(cell.collision)],
        ['Code', String(cell.code)],
        ['Forbidden brick', String(cell.is_forbidden_brick)],
      ],
    });
  }
  for (const cell of (stats.sampled_occupied_cells || []).slice(0, 24)) {
    records.push({
      stableId: `${asset.id}#occupied-cell:${cell.column}:${cell.cell_slot}`,
      label: `Column ${cell.column}`,
      kind: 'background_occupied_cell',
      summary: `block ${cell.block_ref} slot ${cell.cell_slot}`,
      detail: `xyz ${cell.x},${cell.y},${cell.z}`,
      rows: [
        ['Column', String(cell.column)],
        ['Position', `${cell.x}, ${cell.y}, ${cell.z}`],
        ['Word', String(cell.word)],
        ['Block ref', String(cell.block_ref)],
        ['Block index', String(cell.block_index)],
        ['Cell slot', String(cell.cell_slot)],
        ['Resolved BLL', cell.resolved_bll_entry === undefined ? '-' : String(cell.resolved_bll_entry)],
        ['Block ref valid', String(cell.block_ref_valid ?? '-')],
        ['Cell slot valid', String(cell.cell_slot_valid ?? '-')],
      ],
    });
  }
  return records;
}

function formatRecordSummary(record: NonNullable<ResourceStats['sampled_records']>[number]): string {
  if (record.preview) return record.preview;
  if (record.preview_hex) return record.preview_hex;
  if (record.hotspot) return `hotspot ${record.hotspot.x},${record.hotspot.y}`;
  if (record.bounds) return `bounds x ${record.bounds.min_x}..${record.bounds.max_x}`;
  if (record.values) return `values ${record.values.slice(0, 8).join(', ')}`;
  if (record.source) return `${record.source.hqr}:${record.source.entry_index}`;
  return `index ${record.index}`;
}

function recordRows(record: NonNullable<ResourceStats['sampled_records']>[number]): Array<[string, string]> {
  const rows: Array<[string, string]> = [['Index', String(record.index)]];
  if (record.backend) rows.push(['Backend', record.backend]);
  if (record.offset !== undefined) rows.push(['Offset', String(record.offset)]);
  if (record.byte_length !== undefined) rows.push(['Byte length', String(record.byte_length)]);
  if (record.flag !== undefined) rows.push(['Flag', String(record.flag)]);
  if (record.preview) rows.push(['Preview', record.preview]);
  if (record.preview_hex) rows.push(['Preview hex', record.preview_hex]);
  if (record.sha256) rows.push(['SHA-256', record.sha256]);
  if (record.values) rows.push(['Values', record.values.join(', ')]);
  if (record.source) rows.push(['Source', `${record.source.hqr}:${record.source.entry_index}`]);
  if (record.hotspot) rows.push(['Hotspot', `${record.hotspot.x}, ${record.hotspot.y}`]);
  if (record.bounds) rows.push(['Bounds', `x ${record.bounds.min_x}..${record.bounds.max_x}, y ${record.bounds.min_y}..${record.bounds.max_y}, z ${record.bounds.min_z}..${record.bounds.max_z}`]);
  if (record.message !== undefined) rows.push(['Message', String(record.message)]);
  if (record.objfix !== undefined) rows.push(['ObjFix', String(record.objfix)]);
  if (record.flag_holo !== undefined) rows.push(['Flag Holo', String(record.flag_holo)]);
  if (record.planet !== undefined) rows.push(['Planet', String(record.planet)]);
  if (record.island !== undefined) rows.push(['Island', String(record.island)]);
  if (record.resolved_gri_entry !== undefined) rows.push(['Resolved GRI', String(record.resolved_gri_entry)]);
  if (record.resolved_bll_entry !== undefined) rows.push(['Resolved BLL', String(record.resolved_bll_entry)]);
  if (record.resolved_grm_entry !== undefined) rows.push(['Resolved GRM', String(record.resolved_grm_entry)]);
  if (record.used_block_count !== undefined) rows.push(['Used blocks', String(record.used_block_count)]);
  return rows;
}

function factNode(label: string, value: string): HTMLElement {
  const node = document.createElement('div');
  node.className = 'resource-fact';
  const labelNode = document.createElement('span');
  labelNode.textContent = label;
  const valueNode = document.createElement('strong');
  valueNode.textContent = value;
  node.append(labelNode, valueNode);
  return node;
}
