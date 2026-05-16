import { viewerService } from '../runtime/viewerService';
import type { Catalog, RuntimeSpriteResolvePayload } from '../types';

export interface RuntimeSpriteResolverOptions {
  root: HTMLElement;
  flags: HTMLInputElement;
  sprite: HTMLInputElement;
  bodyNum: HTMLInputElement;
  objectIndex: HTMLInputElement;
  labelTrack: HTMLInputElement;
  resolve: HTMLButtonElement;
  open: HTMLButtonElement;
  result: HTMLElement;
  openAsset: (assetId: string) => void;
  openWorkflow?: (request: RuntimeSpriteRequest) => void;
  onResolved?: (payload: RuntimeSpriteResolvePayload) => void;
  setError: (message: string) => void;
}

export interface RuntimeSpriteRequest {
  object_index?: number | null;
  flags: number;
  sprite_index: number;
  body_num?: number | null;
  label_track?: number | null;
}

export class RuntimeSpriteResolver {
  private catalog: Catalog | null = null;
  private lastAssetId: string | null = null;

  constructor(private readonly options: RuntimeSpriteResolverOptions) {
    options.resolve.addEventListener('click', () => void this.resolve());
    options.open.addEventListener('click', () => {
      if (this.lastAssetId) this.options.openAsset(this.lastAssetId);
    });
  }

  setCatalog(catalog: Catalog | null): void {
    this.catalog = catalog;
    this.renderRuntimeModelHint();
  }

  async resolve(): Promise<void> {
    this.options.setError('');
    this.options.result.textContent = 'Resolving...';
    this.setOpenAsset(null);
    let payload: RuntimeSpriteResolvePayload;
    try {
      const request = this.requestFromInputs();
      payload = await viewerService.resolveRuntimeSprite(request);
      this.options.openWorkflow?.(request);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.options.result.textContent = message;
      this.options.setError(message);
      return;
    }
    this.options.onResolved?.(payload);
    this.renderResult(payload);
  }

  private requestFromInputs(): RuntimeSpriteRequest {
    return {
      flags: parseInteger(this.options.flags.value, 'Flags'),
      sprite_index: parseInteger(this.options.sprite.value, 'Sprite'),
      body_num: optionalInteger(this.options.bodyNum.value, 'Body.Num'),
      object_index: optionalInteger(this.options.objectIndex.value, 'Object'),
      label_track: optionalInteger(this.options.labelTrack.value, 'LabelTrack'),
    };
  }

  private renderResult(payload: RuntimeSpriteResolvePayload): void {
    const resolution = payload.resolution;
    if (!resolution.resolved) {
      this.options.result.textContent = resolution.index_rule;
      return;
    }

    const facts: Array<[string, string]> = [
      ['Backend', String(resolution.backend)],
      ['Asset', String(resolution.asset_id)],
      ['Flags', `0x${payload.flags.toString(16).toUpperCase()}`],
      ['SPRITE_3D', resolution.flags_decoded.SPRITE_3D ? 'set' : 'clear'],
      ['ANIM_3DS', resolution.flags_decoded.ANIM_3DS ? 'set' : 'clear'],
    ];
    if (payload.object_index !== null && payload.object_index !== undefined) {
      facts.push(['Object', String(payload.object_index)]);
    }
    if (payload.label_track !== null && payload.label_track !== undefined) {
      facts.push(['LabelTrack', String(payload.label_track)]);
    }
    if (payload.body_num !== null && payload.body_num !== undefined) {
      facts.push(['Body.Num', String(payload.body_num)]);
      facts.push(['Mirror', payload.body_num_matches_sprite ? 'matches Sprite' : 'differs']);
    }
    if (resolution.hotspot) facts.push(['Hotspot', `${resolution.hotspot.x}, ${resolution.hotspot.y}`]);
    if (resolution.bounds) {
      facts.push([
        'Bounds',
        `x ${resolution.bounds.min_x}..${resolution.bounds.max_x}, y ${resolution.bounds.min_y}..${resolution.bounds.max_y}, z ${resolution.bounds.min_z}..${resolution.bounds.max_z}`,
      ]);
    }

    const rows = facts.map(([label, value]) => runtimeFact(label, value));
    const note = document.createElement('div');
    note.className = 'runtime-note';
    note.textContent = payload.body_num_note || resolution.index_rule;
    rows.push(note);
    this.options.result.replaceChildren(...rows);
    this.setOpenAsset(payload.catalog_asset_available ? resolution.asset_id : null);
  }

  private setOpenAsset(assetId: string | null): void {
    this.lastAssetId = assetId;
    this.options.open.disabled = assetId === null;
  }

  private renderRuntimeModelHint(): void {
    if (!this.catalog?.metadata?.sprite_runtime_model) return;
    const flags = this.catalog.metadata.sprite_runtime_model.flags;
    this.options.flags.title = `SPRITE_3D=0x${flags.SPRITE_3D.toString(16).toUpperCase()}, ANIM_3DS=0x${flags.ANIM_3DS.toString(16).toUpperCase()}`;
  }
}

function parseInteger(value: string, label: string): number {
  const trimmed = value.trim();
  const parsed = /^[-+]?0x/i.test(trimmed)
    ? Number.parseInt(trimmed, 16)
    : Number.parseInt(trimmed, 10);
  if (!Number.isFinite(parsed)) throw new Error(`${label} must be an integer.`);
  return parsed;
}

function optionalInteger(value: string, label: string): number | null {
  if (value.trim() === '') return null;
  return parseInteger(value, label);
}

function runtimeFact(label: string, value: string): HTMLElement {
  const row = document.createElement('div');
  row.className = 'runtime-fact';
  const key = document.createElement('span');
  key.textContent = label;
  const val = document.createElement('strong');
  val.textContent = value;
  row.append(key, val);
  return row;
}
