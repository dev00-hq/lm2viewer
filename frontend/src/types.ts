export type AssetKind = 'model' | 'animation';
export type KindFilter = AssetKind | 'all';
export type PolygonMode = 'original' | 'triangulated';

export interface Catalog {
  schema: string;
  asset_root: string;
  source_mode?: 'folder' | 'files';
  selected_files?: string[];
  output_root?: string;
  metadata?: {
    file3d_animation_labels?: boolean;
  };
  summary: {
    hqr_files: number;
    assets: number;
    models: number;
    animations: number;
    decoded_animations: number;
    raw_animations: number;
    animation_assets: number;
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
  decoded_animations: number;
  raw_animations: number;
  recognized: number;
  bytes: number;
}

export interface CatalogAsset {
  id: string;
  kind: AssetKind;
  label: string;
  entry_type: string;
  animation_state?: 'decoded' | 'raw';
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
  animation_metadata?: {
    generic_ids: number[];
    generic_names: string[];
    labels: string[];
    file3d_objects: number[];
    compatible_body_ids: number[];
  };
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
  decoded_sha256: string;
  header_words: number[];
  header_word_count: number;
  parse_status: 'raw';
  decode_status: 'deferred' | 'parse_failed';
  decode_note: string;
  parse_error?: string;
  semantic_layout: 'unknown';
  unknown_descriptors: Array<{
    section: string;
    offset: number;
    length: number;
    sha256: string;
    confidence: string;
    note: string;
    related_decoded_fields?: string[];
  }>;
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
  pose?: {
    body_asset_id: string;
    animation_asset_id: string;
    sample: {
      target_frame_index: number;
      previous_frame_index: number;
      next_frame_index: number;
      elapsed_ms: number;
      duration_ms: number;
      complete: boolean;
      root_delta?: [number, number, number];
      bone_count: number;
    };
    transform?: {
      translation_scale?: number;
    };
  };
  catalog_asset?: CatalogAsset;
}

export interface AnimationSequenceFrame {
  sequence_index: number;
  segment: 'intro' | 'loop';
  frame: number;
  previous_frame: number;
  next_frame: number;
  elapsed_ms: number;
  timeline_ms: number;
  duration_ms: number;
  root_motion?: [number, number, number];
  vertices: [number, number, number, number][];
  pose: NonNullable<Lm2Model['pose']>;
}

export interface AnimationSequencePayload {
  body_asset_id: string;
  animation_asset_id: string;
  step_ms: number;
  keyframes: number;
  loop_frame: number;
  loop_index: number;
  playback_end_index: number;
  loop_cycle_root_delta: [number, number, number];
  frames: AnimationSequenceFrame[];
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
    decoded_animations?: number;
    raw_animations?: number;
    animation_assets?: number;
  } | null;
}

export interface AnimationPayload {
  animation: CatalogAsset;
}

export interface ExportPayload {
  output_dir: string;
  manifest: {
    schema_version: string;
    source: {
      catalog_asset_id: string;
      catalog_label?: string;
    };
    options: {
      polygon_mode: PolygonMode;
      coordinate_space: string;
    };
    files: {
      obj: string;
      mtl: string;
      manifest: string;
      shared_atlas_png?: string;
      uv_group_pngs?: Array<{ uv_group: number; path: string }>;
    };
    warnings?: string[];
  };
}
