export type AssetKind = 'model' | 'animation' | 'sprite' | 'scene' | 'resource';
export type KindFilter = AssetKind | 'all';
export type PolygonMode = 'original' | 'triangulated';

export interface Catalog {
  schema: string;
  asset_root: string;
  source_mode?: 'folder' | 'files';
  selected_files?: string[];
  output_root?: string;
  graph?: CatalogGraphProjection;
  metadata?: {
    file3d_animation_labels?: boolean;
    sprite_runtime_model?: {
      source: string;
      flags: {
        SPRITE_3D: number;
        ANIM_3DS: number;
      };
      rules: RuntimeSpriteResolution[];
    };
    scene_runtime_links?: {
      source: string;
      file3d_objects: number;
      body_refs: number;
      animation_refs: number;
      sprite_refs: number;
      missing_asset_ids: string[];
    };
    scene_script_links?: {
      source: string;
      body_refs: number;
      animation_refs: number;
      sprite_refs: number;
      missing_asset_ids: string[];
    };
    scene_text_links?: {
      source: string;
      script_logical_refs: number;
      script_localized_refs: number;
      script_missing_refs: number;
      zone_logical_refs: number;
      zone_localized_refs: number;
      zone_missing_refs: number;
      missing_text_ids: string[];
    };
    holomap_text_links?: {
      source: string;
      arrow_message_refs: number;
      unique_message_ids: number;
      linked_unique_message_ids: number;
      localized_text_records: number;
      missing_message_ids: number[];
      text_file_index: number;
      text_file_name: string;
    };
    scene_sample_links?: {
      source: string;
      script_logical_refs: number;
      script_linked_refs: number;
      script_missing_refs: number;
      ambience_logical_refs: number;
      ambience_linked_refs: number;
      ambience_missing_refs: number;
      missing_sample_ids: number[];
      missing_sample_id_details?: Array<{
        sample_id: number;
        hqr_table_index: number;
        status: string;
        reason: string;
      }>;
      missing_sample_status_counts?: Record<string, number>;
      observed_sample_id_max?: number | null;
      sample_archive?: {
        archive: string;
        entry_count: number;
        non_empty_entries: number;
        decoded_audio_entries: number;
        highest_decoded_sample_id: number | null;
        highest_runtime_sample_id?: number | null;
        runtime_id_rule: string;
      } | null;
    };
    scene_video_links?: {
      source: string;
      script_logical_refs: number;
      script_linked_refs: number;
      script_missing_refs: number;
      missing_acf_names: string[];
      missing_acf_details?: Array<{
        acf_name: string;
        acf_basename: string;
        acf_name_hex: string;
      }>;
      video_asset_count?: number;
    };
    scene_grm_links?: {
      source: string;
      scenes_with_grm_zones: number;
      fragment_zones: number;
      linked_grm_fragments: number;
      missing_grm_fragments: number;
      dimension_mismatches: number;
      out_of_cube_bounds: number;
      column_y_overflow_cells: number;
    };
  };
  summary: {
    hqr_files: number;
    assets: number;
    models: number;
    animations: number;
    decoded_animations: number;
    raw_animations: number;
    animation_assets: number;
    sprite_assets?: number;
    sprite_frames?: number;
    sprite_metadata?: number;
    scene_assets?: number;
    resource_assets?: number;
    scene_linked_body_refs?: number;
    scene_linked_animation_refs?: number;
    scene_linked_sprite_refs?: number;
    scene_script_linked_body_refs?: number;
    scene_script_linked_animation_refs?: number;
    scene_script_linked_sprite_refs?: number;
    scene_script_linked_text_refs?: number;
    scene_zone_linked_text_refs?: number;
    holomap_linked_text_refs?: number;
    scene_script_linked_sample_refs?: number;
    scene_script_linked_video_refs?: number;
    scene_ambience_linked_sample_refs?: number;
    scene_background_cube_links?: number;
    scene_grm_fragment_links?: number;
    scene_usage_refs?: number;
    scene_used_assets?: number;
  };
  hqr_files: HqrFileSummary[];
  coverage?: HqrCoverageMatrix;
  assets: CatalogAsset[];
}

export interface CatalogGraphProjection {
  schema: 'catalog_graph.catalog_projection.v0' | string;
  indexes: {
    compatibleAnimationsByModelId?: Record<string, string[]>;
  };
  compatibilityByModelId?: Record<string, CatalogGraphCompatibility[]>;
}

export interface CatalogGraphCompatibility {
  animationId: string;
  compatibilityReason?: 'file3d_allowlist' | 'bone_count_only' | string;
  proofScope?: string;
  evidenceStatus?: string;
  sourceRule?: string;
  sourceField?: string;
  indexRule?: string;
}

export interface PortPromotionPacketsPayload {
  schema: 'viewer_port_promotion_packets.v0';
  port_root: string;
  manifest: string;
  packets: PortPromotionPacket[];
}

export interface PortPromotionPacket {
  id: string;
  status: 'decode_only' | 'live_negative' | 'live_positive' | 'approved_exception' | string;
  evidence_class: string;
  canonical_runtime: boolean;
  runtime_contracts: string[];
  packet: string;
  fixture: string | null;
  fixture_available: boolean;
  fixture_source?: {
    scene?: number;
    background?: number;
    active_cube?: number;
    zone_index?: number;
    save?: string;
    save_lane?: string;
    [key: string]: unknown;
  } | null;
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
  sprites?: number;
  sprite_frames?: number;
  sprite_metadata?: number;
  scenes?: number;
  raw_scenes?: number;
  resources?: number;
  resource_formats?: string[];
  linked_body_refs?: number;
  linked_animation_refs?: number;
  linked_sprite_refs?: number;
  script_linked_body_refs?: number;
  script_linked_animation_refs?: number;
  script_linked_sprite_refs?: number;
  script_linked_text_refs?: number;
  zone_linked_text_refs?: number;
  linked_text_refs?: number;
  script_linked_sample_refs?: number;
  script_linked_video_refs?: number;
  ambience_linked_sample_refs?: number;
  grm_fragment_links?: number;
  missing_asset_links?: number;
  recognized: number;
  bytes: number;
}

export interface HqrCoverageMatrix {
  schema: 'lba2-hqr-coverage-v1';
  archive_count: number;
  statuses: Record<string, number>;
  archives: Array<{
    path: string;
    archive: string;
    entry_count: number;
    non_empty_entries: number;
    cataloged_entries: number;
    unknown_entries: number;
    semantic_unknown_entries: number;
    recognized_formats: string[];
    unknown_formats: string[];
    runtime_purpose: string;
    parser_support: string;
    viewer_support: string;
    export_support: string;
    coverage_status: 'covered' | 'partial' | 'deferred' | 'empty' | 'unknown' | string;
    next_required_evidence: string;
  }>;
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
  stats: ModelStats | AnimationStats | RawAnimationStats | SpriteFrameStats | Anim3dsInfoStats | SceneStats | ResourceStats;
  features?: Record<string, boolean | number | string>;
  scene_usages?: SceneAssetUsage[];
  animation_metadata?: {
    generic_ids: number[];
    generic_names: string[];
    labels: string[];
    file3d_objects: number[];
    compatible_body_ids: number[];
  };
}

export interface SceneAssetUsage {
  kind: 'body' | 'animation' | 'sprite' | string;
  scene_asset_id: string;
  scene_label: string;
  scene_entry_index: number;
  scene_index: number | null;
  object_index: number;
  position?: { x: number; y: number; z: number };
  file3d_index: number;
  gen_body: number;
  gen_anim: number;
  sprite: number;
  flags: number;
  target_asset_id: string;
  resolution_rule?: string;
  script_kind?: 'track' | 'life' | string;
  reference_key?: string;
  reference_value?: number;
  generic_id?: number;
  generic_name?: string;
  label?: string;
  body_index?: number;
  animation_index?: number;
  backend?: string;
  runtime_sprite_index?: number;
  index_rule?: string;
  anim3ds_range?: Anim3dsSceneRange;
  zone_index?: number;
  text_id?: number;
  text_file_index?: number;
  text_file_name?: string;
  language?: string;
  record_index?: number;
  record_flag?: number;
  preview?: string;
  facing_direction?: string;
  sample_id?: number;
  slot_index?: number;
  repeat?: number;
  random?: number;
  frequency?: number;
  volume?: number;
  audio_format?: string;
  sample_rate?: number;
  bits_per_sample?: number;
  channels?: number;
  duration_ms?: number | null;
  acf_name?: string;
  acf_index?: number;
  frame_count?: number;
  grm_index?: number;
  resolved_grm_entry?: number;
  target_cell_start?: { x: number; y: number; z: number };
  fragment_dimensions?: { x: number | null; y: number | null; z: number | null };
}

export interface Anim3dsSceneRange {
  animation_number: number;
  name: string | null;
  start_frame: number | null;
  end_frame: number | null;
  frame_count: number | null;
  relative_frame: number | null;
  range_matches_sprite: boolean;
  size_s_hit?: number | null;
  frames_per_second?: number | null;
}

export interface ModelStats {
  bones: number;
  vertices: number;
  normals: number;
  polygons: number;
  lines: number;
  spheres: number;
  uv_groups: number;
  direct_code_references?: DirectCodeReference[];
  direct_reference_count?: number;
  runtime_reference_status?: string;
}

export interface DirectCodeReference {
  symbol: string;
  purpose: string;
  source: string;
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
  anim3ds_info?: {
    animation_index: number;
    name: string;
    start_frame: number;
    end_frame: number;
    relative_frame: number;
  };
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

export interface SpriteFrameStats {
  decoded_bytes: number;
  decoded_sha256: string;
  parse_status: 'decoded';
  decode_status: 'decoded';
  decode_note: string;
  semantic_layout: 'lsp_sprite_frame' | 'raw_sprite_frame';
  sprite_backend?: 'anim3ds' | 'sprites' | 'spriraw' | string;
  runtime?: {
    flags?: number;
    sprite_index?: number;
    resolved?: boolean;
    backend: 'anim3ds' | 'sprites' | 'spriraw' | string;
    archive: string;
    asset_id?: string;
    flags_decoded?: {
      SPRITE_3D: boolean;
      ANIM_3DS: boolean;
    };
    runtime_sprite_index: number;
    index_rule: string;
    hotspot?: { x: number; y: number };
    bounds?: {
      min_x: number;
      max_x: number;
      min_y: number;
      max_y: number;
      min_z: number;
      max_z: number;
    };
    bounds_source?: {
      hqr: string;
      entry_index: number;
    };
  };
  width: number;
  height: number;
  offset_x: number;
  offset_y: number;
  direct_code_references?: DirectCodeReference[];
  direct_reference_count?: number;
  encoded_bytes_consumed: number;
  trailing_bytes: number;
  opaque_pixels: number;
  transparent_pixels: number;
  color_count: number;
  palette_indices: number[];
  anim3ds_info?: RawAnimationStats['anim3ds_info'];
  unknown_descriptors: RawAnimationStats['unknown_descriptors'];
}

export interface Anim3dsInfoStats {
  decoded_bytes: number;
  decoded_sha256: string;
  parse_status: 'metadata';
  decode_status: 'decoded';
  decode_note: string;
  semantic_layout: 'anim3ds_frame_ranges';
  entry_count: number;
  frame_min: number;
  frame_max: number;
  frame_total: number;
  runtime_reference_status?: string;
  source_provenance?: string;
  runtime_playback?: {
    range_table_source: string;
    range_record_layout: string;
    scene_initialization: string;
    advance_rule: string;
    reverse_rule: string;
    track_controls: Record<string, string>;
    timing_source: string;
  };
  range_warnings: Array<{
    animation_index: number;
    name: string;
    missing_frames: number[];
    note: string;
  }>;
  entries: Array<{
    index: number;
    name: string;
    name_bytes: number[];
    start_frame: number;
    end_frame: number;
    frame_count: number;
  }>;
}

export interface SceneStats {
  decoded_bytes: number;
  decoded_sha256: string;
  parse_status: 'partial' | 'raw';
  decode_status: 'partial' | 'parse_failed';
  decode_note: string;
  semantic_layout: 'scene_runtime_layout_partial';
  reconnaissance: {
    world?: {
      island: number;
      cube_x: number;
      cube_y: number;
      shadow_level: number;
      labyrinth_mode: number;
      cube_mode: number;
      unknown_world_byte: number;
      runtime_environment?: {
        source_provenance: string;
        island_effect: string;
        cube_coordinate_effect: string;
        shadow_effect: string;
        labyrinth_effect: string;
        cube_mode_effect: string;
        post_cube_mode_byte: number;
        post_cube_mode_byte_status: string;
      };
    };
    background?: {
      runtime_cube: number;
      scene_entry_index: number;
      cube_map_record_found: boolean;
      cube_record_type?: number;
      cube_record_num?: number;
      resolved_gri_entry?: number;
      resolved_bll_entry?: number;
      resolved_grm_entry?: number;
      used_block_count?: number;
      source_provenance?: string;
      palette?: {
        source: string;
        rule: string;
        island?: number;
        cube_mode?: number;
        resolved_palette_entry?: number;
        resolved_palette_name?: string;
        alternate_palette_entry?: number;
        alternate_palette_name?: string;
        alternate_condition?: string;
        confidence: string;
      };
    };
    ambience?: {
      alpha_light: number;
      beta_light: number;
      cube_jingle: number;
      runtime_audio_lighting?: {
        source_provenance: string;
        lighting_effect: string;
        ambient_sample_rule: string;
        ambient_timer_rule: string;
        music_rule: string;
      };
    };
    hero?: {
      start: { x: number; y: number; z: number };
      track_script_bytes: number;
      track_script_sha256?: string;
      track_script_analysis?: SceneScriptAnalysis;
      life_script_bytes: number;
      life_script_sha256?: string;
      life_script_analysis?: SceneScriptAnalysis;
    };
    object_count?: number;
    scene_frame_render_contract?: {
      source: string;
      scene_object_records: number;
      hqr_backed_sources: string[];
      runtime_dynamic_sources: string[];
      runtime_dynamic_source_details?: Array<{
        name: string;
        runtime_owner: string;
        source: string;
        insertion_stage: string;
        sorted_tree_types: string[];
        asset_backing: string;
        preview_status: string;
      }>;
      aff_scene_phases: string[];
      sorted_tree_sources: string[];
      recovery_paths: Record<string, string>;
      preview_limitations: string[];
    };
    sampled_object_count?: number;
    catalog_sampled_object_limit?: number;
    object_render_type_counts?: Record<string, number>;
    object_render_pipeline_counts?: Record<string, number>;
    object_render_contract_counts?: Record<string, number>;
    object_redraw_method_counts?: Record<string, number>;
    object_collision_counts?: Record<string, number>;
    object_srot_conversion_counts?: Record<string, number>;
    object_combat_counts?: Record<string, number>;
    object_move_counts?: Record<string, number>;
    object_flag_counts?: Record<string, number>;
    object_option_flag_counts?: Record<string, number>;
    object_movement_reference_counts?: Record<string, number>;
    object_movement_missing_reference_counts?: Record<string, number>;
    object_movement_state_counts?: Record<string, number>;
    script_behavior_counts?: Record<string, number>;
    script_control_flow_counts?: Record<string, number>;
    script_control_flow_target_status_counts?: Record<string, number>;
    script_runtime_state_counts?: Record<string, number>;
    script_runtime_instruction_state_counts?: Record<string, number>;
    script_execution_contract_counts?: Record<string, number>;
    script_condition_function_counts?: Record<string, number>;
    script_condition_return_type_counts?: Record<string, number>;
    script_condition_comparator_counts?: Record<string, number>;
    script_skipped_byte_counts?: Record<string, number>;
    script_cross_link_counts?: Record<string, number>;
    script_cross_link_target_status_counts?: Record<string, number>;
    script_local_link_counts?: Record<string, number>;
    text_file_index?: number;
    text_link_counts?: Record<string, number>;
    sample_link_counts?: Record<string, number>;
    video_link_counts?: Record<string, number>;
    sample_ambience_links?: Array<Record<string, unknown>>;
    sample_ambience_missing_links?: Array<Record<string, unknown>>;
    missing_sample_links?: Array<Record<string, unknown>>;
    sprite_object_count?: number;
    anim3ds_object_count?: number;
    message_camera_links?: Array<Record<string, unknown>>;
    message_camera_link_counts?: Record<string, number>;
    zone_count?: number;
    zone_type_counts?: Record<string, number>;
    zone_effect_counts?: Record<string, number>;
    zone_runtime_contract_counts?: Record<string, number>;
    sampled_zones?: Array<{
      index: number;
      offset: number;
      start: { x: number; y: number; z: number };
      end: { x: number; y: number; z: number };
      info: number[];
      type: number;
      type_name: string;
      value: number;
      load_rules: Record<string, boolean>;
      runtime?: SceneZoneRuntimeSemantics;
    }>;
    text_zone_links?: Array<Record<string, unknown>>;
    text_message_zones?: Array<Record<string, unknown>>;
    grm_fragment_zones?: Array<Record<string, unknown>>;
    grm_fragment_links?: Array<SceneGrmFragmentLink>;
    grm_fragment_link_counts?: Record<string, number>;
    track_count?: number;
    sampled_tracks?: Array<{
      index: number;
      offset: number;
      position: { x: number; y: number; z: number };
    }>;
    patch_count?: number;
    patch_size_counts?: Record<string, number>;
    patch_target_counts?: Record<string, number>;
    patch_instruction_counts?: Record<string, number>;
    patch_instruction_byte_counts?: Record<string, number>;
    patch_field_counts?: Record<string, number>;
    patch_field_source_counts?: Record<string, number>;
    patch_instruction_field_counts?: Record<string, number>;
    sampled_patches?: Array<{
      index: number;
      offset: number;
      size: number;
      target_offset: number;
      target: {
        kind: string;
        owner: string | null;
        script_relative_offset: number | null;
        instruction_found?: boolean;
        instruction_offset?: number;
        instruction_relative_offset?: number;
        instruction_opcode?: string;
        instruction_behavior_category?: string;
        hits_opcode_byte?: boolean;
        operand_relative_offset?: number;
        patched_field?: string;
        patched_field_offset?: number;
        patched_field_size?: number;
        patched_field_byte_offset?: number;
        patched_field_source?: string;
      };
    }>;
    trailing_patch_bytes?: number;
    sampled_objects?: Array<{
      index: number;
      flags: number;
      file3d_index: number;
      gen_body: number;
      gen_anim: number;
      sprite: number;
      position: { x: number; y: number; z: number };
      hit_force?: number;
      option_flags?: number;
      beta?: number;
      srot?: number;
      move?: number;
      info?: number[];
      bonus_count?: number;
      color?: number;
      armor?: number;
      life_points?: number;
      runtime?: SceneObjectRuntimeSemantics;
      track_script_bytes: number;
      track_script_sha256?: string;
      track_script_analysis?: SceneScriptAnalysis;
      life_script_bytes: number;
      life_script_sha256?: string;
      life_script_analysis?: SceneScriptAnalysis;
      links?: {
        file3d_index: number;
        file3d_available: boolean;
        body?: {
          generic_id: number;
          body_index: number;
          asset_id?: string | null;
          asset_available?: boolean;
          resolution_rule?: string;
        } | null;
        animation?: {
          generic_id: number;
          generic_name: string;
          label: string;
          animation_index: number;
          asset_id?: string | null;
          asset_available?: boolean;
          resolution_rule?: string;
        } | null;
        sprite?: (RuntimeSpriteResolution & {
          asset_available?: boolean;
          anim3ds_range?: Anim3dsSceneRange;
        }) | null;
        missing_asset_ids: string[];
      };
    }>;
    linked_body_refs?: number;
    linked_animation_refs?: number;
    linked_sprite_refs?: number;
    script_linked_body_refs?: number;
    script_linked_animation_refs?: number;
    script_linked_sprite_refs?: number;
  };
  unknown_descriptors: RawAnimationStats['unknown_descriptors'];
}

export interface SceneObjectRuntimeSemantics {
  source: string;
  render_type: string;
  render_pipeline?: {
    source: string;
    draw_path: string;
    sort_key: string;
    recovery_path: string;
    effect_flags: string[];
    contract_steps: string[];
    aff_scene_policy: {
      scene_redraw_setup: string;
      object_only_background_skip: boolean;
      object_only_background_skip_rule: string;
      invisible_or_bodyless_skip_before_tree: boolean;
      camera_preclip_before_tree: string;
      tree_insert: string;
      shadow: string;
    };
    redraw_contract: {
      method: string;
      anchor: string;
      moving_box: boolean;
      draw_over_brick_cage: boolean;
      zbuffer_or_water_flag_present: boolean;
      zbuffer_or_water_effective: boolean;
      sprite_clip_info_rect: boolean;
      camera_recenter_on_full_mask: boolean;
    };
    background_copy: {
      enabled: boolean;
      trigger_opcodes: string[];
      all_scene_flip_copy: boolean;
      object_only_flip_skip: boolean;
      copy_source: string;
      copy_destination: string;
    };
    decor_order_notes: string[];
    invisible_skips_draw: boolean;
    background_incrust_once: boolean;
    background_toggle_opcodes: string[];
    zbuffer_or_water: boolean;
    uses_zbuffer: boolean;
    in_water: boolean;
    uses_moving_box_instead_of_recover: boolean;
    sprite_clip_fixed_zone: boolean;
    sprite_clip_uses_info_rect: boolean;
    no_pre_clip: boolean;
    casts_shadow: boolean;
    shadow_toggle_opcode: string;
    notes: string[];
  };
  flags: string[];
  option_flags: string[];
  collision: {
    object: boolean;
    brick: boolean;
    zone: boolean;
    code_jeu: boolean;
    only_floor: boolean;
  };
  movement: {
    mode: number;
    mode_name: string;
    initial_beta: number;
    srot_scene_value: number;
    srot_runtime_value: number;
    srot_conversion: string;
    references?: Array<{
      field: string;
      field_index: number;
      role: string;
      kind: string;
      value: number;
      target: string;
      target_found: boolean;
      source: string;
    }>;
    state_fields?: Array<{
      field: string;
      field_index: number | null;
      role: string;
      initial_value: number | null;
      load_rule: string;
      source: string;
    }>;
  };
  combat: {
    hit_force: number;
    armor: number;
    life_points: number;
  };
  bonus: {
    count: number;
    options: string[];
  };
}

export interface SceneZoneRuntimeSemantics {
  source: string;
  type: string;
  trigger: string;
  bounds_rule: string;
  effect: string;
  fields: Record<string, unknown>;
  load_state?: Record<string, unknown>;
  camera_application?: Record<string, unknown>;
  change_cube_application?: Record<string, unknown>;
  message_application?: Record<string, unknown>;
  bonus_application?: Record<string, unknown>;
  hit_application?: Record<string, unknown>;
  ladder_application?: Record<string, unknown>;
  escalator_application?: Record<string, unknown>;
  rail_application?: Record<string, unknown>;
  grm_application?: Record<string, unknown>;
  scenario_application?: Record<string, unknown>;
  script_controls: Array<{
    opcode: string;
    match_field: string;
    match_value: number;
    action: string;
  }>;
  runtime_readers: string[];
}

export interface SceneGrmFragmentLink {
  kind: 'grm_fragment';
  zone_index: number;
  zone_value: number;
  grm_index: number;
  initial_runtime_state: number;
  background_grm_base_entry: number | null;
  resolved_grm_entry: number | null;
  asset_id: string | null;
  asset_available: boolean;
  target_cell_start: { x: number; y: number; z: number };
  zone_cell_span: { x: number; y: number; z: number };
  fragment_dimensions: { x: number | null; y: number | null; z: number | null };
  dimensions_match_zone_bounds: boolean;
  out_of_cube_bounds: boolean;
  column_y_overflow_cells: number;
  script_control: string;
  source_provenance: string;
}

export interface SceneScriptAnalysis {
  kind: 'track' | 'life' | string;
  byte_length: number;
  sha256: string;
  instruction_count: number;
  decoded_bytes: number;
  status: string;
  catalog_truncated_lists?: Record<string, { total: number; sampled: number }>;
  control_flow_links_total?: number;
  cross_script_links_total?: number;
  local_links_total?: number;
  asset_links_total?: number;
  first_instructions_total?: number;
  unique_opcodes_total?: number;
  runtime_state_fields_total?: number;
  execution_contracts_total?: number;
  condition_functions_total?: number;
  label_definitions_total?: number;
  unique_opcodes: Array<{
    opcode: number;
    mnemonic: string;
    count: number;
  }>;
  behavior_categories: Array<{
    category: string;
    count: number;
  }>;
  first_instructions: Array<{
    offset: number;
    opcode: number;
    mnemonic: string;
    byte_length: number;
    operand_layout: string;
    operand_hex: string;
    operand_semantics: Record<string, unknown>;
    behavior_category: string;
    behavior_effect: string;
  }>;
  control_flow_links?: Array<{
    source_offset: number;
    source_opcode: string;
    source_behavior_category: string;
    target_field: string;
    target_script_kind: string;
    target_offset: number;
    target_found: boolean;
    target_status?: string;
    target_decoded_bytes?: number;
    target_script_bytes?: number;
    target_containing_offset?: number;
    target_containing_opcode?: string;
    target_containing_behavior_category?: string;
    target_containing_byte_length?: number;
    target_instruction_relative_offset?: number;
    target_byte_role?: string;
    target_previous_decoded_offset?: number;
    target_previous_decoded_opcode?: string;
    target_opcode?: string;
    target_behavior_category?: string;
  }>;
  label_definitions?: Array<{
    label: number;
    offset: number;
    opcode: string;
  }>;
  runtime_state_fields?: Array<{
    source_offset: number;
    opcode: string;
    behavior_category: string;
    field: string;
    instruction_relative_offset: number;
    operand_offset: number;
    size: number;
    initial_hex: string;
    initial_value?: number | boolean;
    source: string;
  }>;
  execution_contracts?: Array<{
    contract: string;
    count: number;
    source: string;
    effect: string;
    mnemonics: string[];
  }>;
  condition_functions?: Array<{
    function: string;
    function_id?: number;
    count: number;
    return_type: string;
    opcodes: string[];
  }>;
  condition_comparators?: Array<{
    comparator: string;
    count: number;
    opcodes: string[];
    functions: string[];
  }>;
  cross_script_links?: Array<{
    source_owner: string;
    source_script_kind: string;
    source_offset: number;
    source_opcode: string;
    source_behavior_category: string;
    target_field: string;
    target_owner: string;
    target_object_index: number;
    target_owner_found: boolean;
    target_script_kind: string;
    target_offset: number;
    target_found: boolean;
    target_status?: string;
    target_decoded_bytes?: number;
    target_script_bytes?: number;
    target_containing_offset?: number;
    target_containing_opcode?: string;
    target_containing_behavior_category?: string;
    target_containing_byte_length?: number;
    target_instruction_relative_offset?: number;
    target_byte_role?: string;
    target_previous_decoded_offset?: number;
    target_previous_decoded_opcode?: string;
    target_opcode?: string;
    target_behavior_category?: string;
  }>;
  asset_links?: Array<{
    kind: 'body' | 'animation' | 'sprite' | string;
    source: string;
    reference_key: string;
    reference_value: number | string;
    file3d_index?: number;
    asset_id?: string | null;
    asset_available?: boolean;
    resolution_rule?: string;
    generic_id?: number;
    generic_name?: string;
    label?: string;
    body_index?: number;
    animation_index?: number;
    backend?: string;
    runtime_sprite_index?: number;
    index_rule?: string;
    anim3ds_range?: Anim3dsSceneRange;
    sample_id?: number;
    audio_format?: string;
    sample_rate?: number;
    bits_per_sample?: number;
    channels?: number;
    duration_ms?: number | null;
    acf_name?: string;
    acf_index?: number;
    frame_count?: number;
    width?: number;
    height?: number;
  }>;
  cinematic_refs?: Array<{
    script_kind: 'track' | 'life' | string;
    offset: number;
    opcode: string;
    behavior_category: string;
    acf_name: string;
    cinematic_action: string;
  }>;
  video_links?: Array<Record<string, unknown>>;
  local_links?: Array<{
    kind: 'object' | 'waypoint' | 'zone' | string;
    reference_key: string;
    reference_value: number;
    target: string;
    target_available: boolean;
    object_index?: number;
    waypoint_index?: number;
    zone_index?: number;
    position?: { x: number; y: number; z: number };
    file3d_index?: number;
    gen_body?: number;
    gen_anim?: number;
    sprite?: number;
    type?: number;
    type_name?: string;
    expected_type?: number;
    type_matches_reference?: boolean;
    value?: number;
    runtime_effect?: string;
  }>;
  references: {
    body: number[];
    animation: number[];
    sprite: number[];
    waypoint: number[];
    script_offset: number[];
    track_label: number[];
    object: number[];
    text: number[];
    var_cube: number[];
    var_game: number[];
    inventory: number[];
    sample: number[];
    music: number[];
    behavior: number[];
    palette: number[];
    pcx: number[];
    holomap: number[];
    buggy: number[];
    camera_zone: number[];
    ladder_zone: number[];
    grm_zone: number[];
    rail_zone: number[];
    hit_zone: number[];
    escalator_zone: number[];
    change_cube_control: number[];
    cube: number[];
    [key: string]: number[];
  };
  failure?: {
    offset: number;
    opcode?: number;
    mnemonic?: string;
  };
}

export interface ResourceStats {
  decoded_bytes: number;
  decoded_sha256: string;
  parse_status: 'decoded';
  decode_status: 'decoded';
  decode_note: string;
  semantic_layout: 'lba2_palette' | 'lba2_texture_atlas_indexed' | 'lba2_indexed_image_256' | 'screen_palette' | 'screen_indexed_image_640x480' | 'holomap_globe_uv_map' | 'holomap_globe_altitude_map' | 'holomap_globe_texture_map' | 'holomap_arrow_table' | 'holomap_plan_image_640x480' | 'holomap_plan_view_params' | 'bkg_header' | 'bkg_grid_map' | 'bkg_grm_fragment' | 'bkg_block_table' | 'bkg_brick_graphic' | 'bkg_cube_map' | 'text_order_table' | 'text_payload_bank' | 'sample_wave_audio' | 'smacker_video' | 'file3d_table' | 'sprite_zv_table' | 'ress_offset_record_table' | 'ress_fixed_s16x8_table' | 'ress_ext_size_info' | 'xpl_palette_bundle' | 'acf_name_list' | 'ress_unclassified_payload';
  color_count?: number;
  transparent_index?: number;
  sample_colors?: number[];
  width?: number;
  height?: number;
  offset_x?: number;
  offset_y?: number;
  pixel_count?: number;
  opaque_pixels?: number;
  transparent_pixels?: number;
  unique_palette_indices?: number;
  palette_indices?: number[];
  encoded_bytes_consumed?: number;
  trailing_bytes?: number;
  run_type_counts?: Record<string, number>;
  max_row_run_count?: number;
  format?: string;
  palette_entry?: { hqr: string; entry_index: number };
  object_count?: number;
  offset_table_bytes?: number;
  record_bytes?: number;
  record_length_counts?: Record<string, number>;
  type_counts?: Record<string, number>;
  preview_hex?: string;
  max_size_list_decors?: number;
  max_size_body_decors?: number;
  max_size_tex_def?: number;
  max_total_body_decors?: number;
  xpl_name?: string;
  header?: Record<string, number | string | null>;
  entry_count?: number;
  sampled_names?: string[];
  source_provenance?: string;
  runtime_reference_status?: string;
  runtime_table_name?: string;
  runtime_buffer?: string;
  runtime_purpose?: string;
  direct_code_references?: DirectCodeReference[];
  direct_reference_count?: number;
  scene_palette_reference_count?: number;
  sample_runtime_index?: number;
  acf_index?: number;
  acf_name?: string;
  acf_basename?: string;
  name_source?: string;
  frame_count?: number;
  frames_per_second?: number | null;
  audio_format?: string;
  chunk_ids?: string[];
  sample_frames?: number | null;
  duration_ms?: number | null;
  samples_per_block?: number | null;
  fact_sample_frames?: number | null;
  resource_header?: Record<string, number>;
  holomap_name?: string;
  plan_variant?: {
    variant_index: number;
    plan_name: string;
    selected_island: number;
    selection_condition: string;
    image_entry_index: number;
    params_entry_index: number;
    entry_role: 'image' | 'params' | string;
    selection_rule: string;
    render_path: string;
  };
  screen_name?: string;
  screen_pair_base?: number;
  paired_entry_index?: number;
  fields?: Record<string, number>;
  composition?: {
    active_columns?: number;
    empty_columns?: number;
    nonzero_cells?: number;
    transparent_code_cells: number;
    unique_block_ref_count: number;
    unique_block_refs?: number[];
    max_y?: number;
    run_type_counts?: Record<string, number>;
    max_column_entities?: number;
    max_column_stream_bytes?: number;
    dimensions?: { x: number; y: number; z: number };
    cell_count?: number;
    occupied_block_cells?: number;
    cell_order?: string;
  };
  composition_payload?: {
    format: 'bkg_grid_column_composition';
    cube_dimensions: { x: number; y: number; z: number };
    cell_order: string;
    cell_count: number;
    flat_block_refs: number[];
    flat_cell_slots_or_codes: number[];
    occupied_block_cells: number;
    transparent_code_cells: number;
    unique_block_refs: number[];
    source_provenance: string;
  };
  preview?: {
    format: 'bkg_grid_preview';
    width: number;
    height: number;
    drawn_cells: number;
    drawn_pixels: number;
    unique_bricks_loaded: number;
    missing_bricks: number;
    skipped_forbidden: number;
    source_provenance: string;
    palette_source: string;
  };
  bkg_entry_role?: string;
  bkg_relative_index?: number;
  language_index?: number;
  language?: string;
  text_file_index?: number;
  text_file_name?: string;
  preview_codepage?: string;
  sampled_message_ids?: number[];
  message_ids?: number[];
  depth?: number;
  used_block_indices?: number[];
  sampled_block_indices?: number[];
  referenced_block_refs_without_used_bit?: number[];
  used_block_refs_without_column_refs?: number[];
  sampled_occupied_cells?: Array<{
    column: number;
    x: number;
    y: number;
    z: number;
    word: number;
    block_ref: number;
    block_index: number;
    cell_slot: number;
    resolved_bll_entry?: number;
    block_ref_valid?: boolean;
    bll_cell_count?: number;
    cell_slot_valid?: boolean;
  }>;
  sampled_transparent_code_cells?: Array<{
    column: number;
    x: number;
    y: number;
    z: number;
    code: number;
  }>;
  invalid_composition_block_refs?: number[];
  invalid_composition_cell_slots?: Array<{
    block_ref: number;
    max_cell_slot: number;
    bll_cell_count: number;
  }>;
  missing_grid_entries?: number[];
  sampled_cell_refs?: Array<{
    block: number;
    cell: number;
    x: number;
    y: number;
    z: number;
    collision: number;
    code: number;
    code_raw: number;
    brick_ref: number;
    resolved_brk_index: number;
    resolved_brk_entry: number;
    is_forbidden_brick: boolean;
  }>;
  active_count?: number;
  exterior_count?: number;
  message_count?: number;
  unique_message_ids?: number[];
  body_reference_count?: number;
  animation_reference_count?: number;
  sampled_objects?: Array<{
    index: number;
    body_records: unknown[];
    animation_records: unknown[];
    command_count: number;
  }>;
  backend?: string;
  record_count?: number;
  sampled_records?: Array<{
    backend?: string;
    index: number;
    offset?: number;
    byte_length?: number;
    dx?: number;
    dy?: number;
    dz?: number;
    cell_count?: number;
    nonzero_brick_refs?: number;
    max_brick_ref?: number;
    unique_brick_refs?: number;
    sampled_cell_refs?: ResourceStats['sampled_cell_refs'];
    code_counts?: Record<string, number>;
    collision_counts?: Record<string, number>;
    type?: number;
    num?: number;
    resolved_gri_entry?: number;
    resolved_bll_entry?: number;
    resolved_grm_entry?: number;
    used_block_count?: number;
    flag?: number;
    text_bytes?: number;
    preview?: string;
    terminates_with_nul?: boolean;
    page_break_count?: number;
    preview_hex?: string;
    sha256?: string;
    values?: number[];
    source?: { hqr: string; entry_index: number };
    hotspot?: { x: number; y: number };
    bounds?: {
      min_x: number;
      max_x: number;
      min_y: number;
      max_y: number;
      min_z: number;
      max_z: number;
    };
    message?: number;
    objfix?: number;
    flag_holo?: number;
    planet?: number;
    island?: number;
  }>;
  text_link_counts?: Record<string, number>;
  text_links?: Array<{
    kind: 'holomap_text';
    message_id: number;
    text_file_index: number;
    text_file_name: string;
    arrow_indices: number[];
    arrow_count: number;
    localized_records: number;
    localized_links: Array<{
      language?: string;
      text_file_name?: string;
      asset_id?: string;
      record_index?: number;
      preview?: string;
      resolution_rule?: string;
    }>;
  }>;
  unknown_descriptors: RawAnimationStats['unknown_descriptors'];
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
    sprite_assets?: number;
    sprite_frames?: number;
    sprite_metadata?: number;
    scene_assets?: number;
    scene_linked_body_refs?: number;
    scene_linked_animation_refs?: number;
    scene_linked_sprite_refs?: number;
    scene_script_linked_body_refs?: number;
    scene_script_linked_animation_refs?: number;
    scene_script_linked_sprite_refs?: number;
  } | null;
}

export interface AnimationPayload {
  animation: CatalogAsset;
}

export interface SpritePayload {
  sprite: CatalogAsset;
  frame?: SpriteFramePayload;
  frames?: SpriteFramePayload[];
}

export interface SpriteFramePayload {
    format: 'lsp_sprite' | 'bkg_affgraph' | 'bkg_grid_preview';
    width: number;
    height: number;
    offset_x: number;
    offset_y: number;
    pixels: number[];
    rgba: number[] | null;
    palette_available: boolean;
    palette_source?: string;
    render_source?: string;
    drawn_cells?: number;
    drawn_pixels?: number;
    unique_bricks_loaded?: number;
    missing_bricks?: number;
    skipped_forbidden?: number;
    variant?: string;
    variant_label?: string;
    variant_index?: number;
    variant_count?: number;
    variant_policy?: string;
    grm_zone_index?: number | null;
    grm_zone_value?: number | null;
    resolved_grm_entry?: number | null;
    changed_cells?: number | null;
    column_y_overflow_cells?: number | null;
    scene_background?: {
      runtime_cube?: number;
      resolved_gri_entry?: number;
      resolved_bll_entry?: number;
      resolved_grm_entry?: number;
    };
}

export interface ScenePayload {
  scene: CatalogAsset;
}

export interface ResourcePayload {
  resource: CatalogAsset;
}

export interface RuntimeSpriteResolution {
  flags: number;
  sprite_index: number;
  flags_decoded: {
    SPRITE_3D: boolean;
    ANIM_3DS: boolean;
  };
  resolved: boolean;
  backend: string | null;
  archive: string | null;
  asset_id: string | null;
  bounds_source: {
    hqr: string;
    entry_index: number;
  } | null;
  index_rule: string;
  runtime_sprite_index?: number;
  hotspot?: { x: number; y: number } | null;
  bounds?: {
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    min_z: number;
    max_z: number;
  } | null;
}

export interface RuntimeSpriteResolvePayload {
  object_index?: number | null;
  flags: number;
  sprite_index: number;
  body_num?: number | null;
  label_track?: number | null;
  body_num_matches_sprite?: boolean;
  body_num_note?: string;
  resolution: RuntimeSpriteResolution;
  catalog_asset: CatalogAsset | null;
  catalog_asset_available: boolean;
}

export interface EntityWorkflowPayload {
  schema: 'lba2_entity_workflow.v0';
  entrypoint: {
    kind: 'asset' | 'runtime_sprite' | string;
    asset_id?: string;
    label?: string;
    flags?: number;
    sprite_index?: number;
    object_index?: number | null;
    body_num?: number | null;
    label_track?: number | null;
    resolution_rule?: string;
  };
  resolved_asset: EntityCompactAsset | null;
  runtime_resolution?: RuntimeSpriteResolution;
  usage_groups: EntityUsageGroup[];
  selected_entity: EntityContract | null;
  evidence_trail: Array<{
    step: string;
    label: string;
    asset_id?: string;
    usage_class?: string;
    render_backend?: string;
  }>;
  unknowns: EntityUnknown[];
}

export interface EntityCompactAsset {
  id: string;
  kind: AssetKind | string;
  label: string;
  entry_type: string;
  source: {
    hqr?: string;
    entry_index?: number;
    classic_index?: number;
  };
  features?: Record<string, boolean | number | string>;
}

export interface EntityUsageGroup {
  scene_asset_id: string;
  scene_label: string;
  scene_index: number | null;
  object_index: number | null;
  entity_id: string | null;
  usage_classes: string[];
  usages: Array<SceneAssetUsage & { usage_class: string }>;
}

export interface EntityContract {
  schema: 'lba2_entity_contract.v0';
  entity_id: string;
  scene_asset_id: string;
  scene_entry_index: number;
  scene_index: number | null;
  object_index: number | null;
  object_sample_status: string;
  label: string;
  position?: { x: number; y: number; z: number } | null;
  render_backend: string;
  linked_visual_assets: Array<{
    role: string;
    asset_id: string;
    asset_available?: boolean;
    resolution_rule?: string;
  }>;
  initial_state: Record<string, unknown>;
  script_driven_links: Array<Record<string, unknown>>;
  local_links: Array<Record<string, unknown>>;
  cross_script_links: Array<Record<string, unknown>>;
  render_contract: {
    draw_path?: string;
    sort_key?: string;
    recovery_path?: string;
    contract_steps: string[];
    redraw_contract?: Record<string, unknown>;
    render_phase?: Record<string, unknown>;
    source?: string;
  };
  port_implications: Array<{
    area: string;
    claim: string;
    evidence: string;
  }>;
  provenance: {
    scene_asset: EntityCompactAsset | null;
    usage_kind?: string;
    usage_class?: string;
    resolution_rule?: string;
  };
  confidence: string;
  unknowns: EntityUnknown[];
}

export interface EntityUnknown {
  field: string;
  status: string;
  note: string;
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
      polygon_mode?: PolygonMode;
      coordinate_space?: string;
      format?: string;
      cell_order?: string;
      variant_policy?: string;
    };
    files: {
      obj?: string;
      mtl?: string;
      manifest: string;
      composition_json?: string;
      preview_png?: string;
      sprite_png?: string;
      sheet_png?: string;
      wav?: string;
      shared_atlas_png?: string;
      uv_group_pngs?: Array<{ uv_group: number; path: string }>;
      frames?: Array<{
        asset_id: string;
        label?: string;
        entry_index: number;
        png: string;
        sheet_x: number;
        sheet_y: number;
        width: number;
        height: number;
        offset_x: number;
        offset_y: number;
        runtime_sprite_index?: number | null;
        anim3ds_range?: Anim3dsSceneRange | null;
      }>;
      variants?: Array<{
        variant: string;
        composition_json: string;
        preview_png: string;
        [key: string]: unknown;
      }>;
    };
    warnings?: string[];
  };
}
