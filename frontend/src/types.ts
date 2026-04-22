export type AssetKind = 'model' | 'animation';
export type KindFilter = AssetKind | 'all';

export interface Catalog {
  schema: string;
  asset_root: string;
  source_mode?: 'folder' | 'files';
  selected_files?: string[];
  output_root?: string;
  summary: {
    hqr_files: number;
    assets: number;
    models: number;
    animations: number;
  };
  hqr_files: HqrFileSummary[];
  assets: CatalogAsset[];
}

export interface HqrFileSummary {
  path: string;
  indexing?: string;
  entry_count: number;
  non_empty_entries: number;
  models: number;
  animations: number;
  recognized: number;
  bytes: number;
}

export interface CatalogAsset {
  id: string;
  kind: AssetKind;
  label: string;
  entry_type: string;
  source: {
    hqr: string;
    entry_index: number;
    classic_index?: number;
    offset: number;
    raw_bytes: number;
    raw_sha256: string;
    resource?: {
      size_file: number;
      compressed_size_file: number;
      compress_method: number;
    } | null;
  };
  path: string;
  relative_path: string;
  decoded_bytes: number;
  decoded_sha256: string;
  stats: ModelStats | AnimationStats | RawAnimationStats;
  features?: Record<string, boolean | number | string>;
}

export interface ModelStats {
  bones: number;
  vertices: number;
  normals: number;
  polygons: number;
  lines: number;
  spheres: number;
  uv_groups: number;
}

export interface AnimationStats {
  keyframes: number;
  boneframes: number;
  loop_frame: number;
  total_duration: number;
  translated_boneframes: number;
  can_fall: boolean;
  byte_length: number;
}

export interface RawAnimationStats {
  decoded_bytes: number;
  header_words: number[];
  parse_status: 'raw';
  parse_error: string;
}

export interface Lm2Model {
  format: 'lm2';
  source: string;
  header: {
    flags: number;
    version: number;
    has_animation: boolean;
    no_sort: boolean;
    has_transparency: boolean;
    bounds: number[];
  };
  stats: ModelStats;
  palette: number[] | null;
  texture_atlas: {
    width: number;
    height: number;
    pixels: number[];
  } | null;
  vertices: [number, number, number, number][];
  uv_groups: Array<{
    x: number;
    y: number;
    w: number;
    h: number;
  }>;
  polygons: Array<{
    render_type: number;
    vertices: number[];
    color: number;
    color_word: number;
    palette_index: number;
    intensity: number;
    has_texture: boolean;
    has_extra: boolean;
    has_transparency: boolean;
    texture: number | null;
    uv: [number, number][] | null;
  }>;
  lines: Array<{
    color: number;
    color_word: number;
    palette_index: number;
    vertices: [number, number];
  }>;
  spheres: Array<{
    color: number;
    color_word: number;
    palette_index: number;
    vertex: number;
    size: number;
  }>;
  catalog_asset?: CatalogAsset;
}

export interface ErrorPayload {
  error: string;
}

export interface DecodeProgress {
  active: boolean;
  phase: 'idle' | 'waiting' | 'scanning' | 'decoding' | 'finalizing' | 'complete' | 'error';
  label: string;
  current: number;
  total: number;
  percent: number | null;
  elapsed_seconds: number;
  error: string | null;
  summary?: {
    hqr_files?: number;
    assets?: number;
    models?: number;
    animations?: number;
  } | null;
}

export interface AnimationPayload {
  animation: CatalogAsset;
}
