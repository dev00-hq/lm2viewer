import { animationMatchesModel } from '../compatibility';
import type { AnimationStats, Anim3dsInfoStats, Catalog, CatalogAsset, KindFilter, ModelStats, RawAnimationStats, ResourceStats, SceneAssetUsage, SceneStats, SpriteFrameStats } from '../types';

export interface CatalogUiOptions {
  summary: HTMLElement;
  search: HTMLInputElement;
  filter: HTMLSelectElement;
  list: HTMLElement;
  onSelect: (asset: CatalogAsset) => void;
}

export class CatalogUi {
  private catalog: Catalog | null = null;
  private highlightedAssetId: string | null = null;
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
    this.setHighlightedAssetId(asset.id);
  }

  setHighlightedAssetId(assetId: string | null): void {
    this.highlightedAssetId = assetId;
    this.render();
  }

  setSelectedModel(asset: CatalogAsset | null): void {
    this.selectedModel = asset;
    this.render();
  }

  private render(): void {
    if (!this.catalog) return;
    const summary = this.catalog.summary || {};
    const query = this.options.search.value.trim().toLowerCase();
    const kind = this.options.filter.value as KindFilter;
    let assets = this.catalog.assets || [];
    assets = assets.filter((asset) => {
      if (kind !== 'all' && asset.kind !== kind) return false;
      if (kind === 'animation' && this.selectedModel && !animationMatchesModel(this.catalog, asset, this.selectedModel)) return false;
      if (!query) return true;
      return searchableText(asset).includes(query);
    });
    assets.sort((a, b) => scoreAsset(b, query) - scoreAsset(a, query) || assetSortKey(a).localeCompare(assetSortKey(b)));
    const visible = assets.slice(0, 260);
    this.options.summary.textContent =
      `${summary.models || 0} models, ${summary.decoded_animations || 0} decoded animations, ${summary.raw_animations || 0} raw animation entries, ${summary.sprite_assets || 0} sprite assets, ${summary.scene_assets || 0} scenes, ${summary.resource_assets || 0} resources across ${summary.hqr_files || 0} HQR files. ` +
      `Scene object links: ${summary.scene_linked_body_refs || 0} body, ${summary.scene_linked_animation_refs || 0} animation, ${summary.scene_linked_sprite_refs || 0} sprite. ` +
      `Scene script links: ${summary.scene_script_linked_body_refs || 0} body, ${summary.scene_script_linked_animation_refs || 0} animation, ${summary.scene_script_linked_sprite_refs || 0} sprite. ` +
      `Scene text links: ${summary.scene_script_linked_text_refs || 0} script, ${summary.scene_zone_linked_text_refs || 0} zone. ` +
      `Holomap text links: ${summary.holomap_linked_text_refs || 0} messages. ` +
      `Scene sample links: ${summary.scene_script_linked_sample_refs || 0} script, ${summary.scene_ambience_linked_sample_refs || 0} ambience. ` +
      `Scene video links: ${summary.scene_script_linked_video_refs || 0} script. ` +
      `${this.sampleAuditSummary()}` +
      `Scene background links: ${summary.scene_background_cube_links || 0} cube, ${summary.scene_grm_fragment_links || 0} GRM fragments. ` +
      `Reverse usage: ${summary.scene_usage_refs || 0} refs across ${summary.scene_used_assets || 0} assets. ` +
      `${this.filterContext(kind)}Showing ${visible.length} of ${assets.length} matching entries.`;
    this.options.list.replaceChildren(...visible.map((asset) => this.assetButton(asset)));
  }

  private filterContext(kind: KindFilter): string {
    if (kind !== 'animation' || !this.selectedModel) return '';
    const stats = this.selectedModel.stats as ModelStats;
    return `Filtered to compatible decoded animations with ${stats.bones || 0} boneframes for ${this.selectedModel.label}. `;
  }

  private sampleAuditSummary(): string {
    const links = this.catalog?.metadata?.scene_sample_links;
    if (!links?.sample_archive) return '';
    const missing = links.missing_sample_ids?.length || 0;
    const missingCounts = formatCounts(links.missing_sample_status_counts || {});
    const missingText = missingCounts ? ` (${missingCounts})` : '';
    return `Sample archive: ${links.sample_archive.decoded_audio_entries || 0}/${links.sample_archive.entry_count || 0} decoded audio, ${missing} referenced missing ids${missingText}. `;
  }

  private assetButton(asset: CatalogAsset): HTMLButtonElement {
    const button = document.createElement('button');
    button.className = 'asset-button' + (asset.id === this.highlightedAssetId ? ' active' : '');
    button.type = 'button';

    const title = document.createElement('div');
    title.className = 'asset-title';
    const name = document.createElement('strong');
    name.textContent = asset.label;
    const pill = document.createElement('span');
    pill.className = 'pill';
    pill.textContent = assetPillText(asset);
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
    asset.animation_state,
    asset.label,
    asset.entry_type,
    animationMetadataText(asset),
    asset.source?.hqr,
    asset.source?.entry_index,
    sceneUsageSearchText(asset.scene_usages || []),
    statsSearchText(asset.stats),
  ].join(' ').toLowerCase();
}

function statsSearchText(stats: CatalogAsset['stats']): string {
  if ('vertices' in stats && 'polygons' in stats && 'bones' in stats) {
    const model = stats as ModelStats;
    return [
      model.vertices,
      model.polygons,
      model.bones,
      model.runtime_reference_status,
      ...(model.direct_code_references || []).flatMap((reference) => [
        reference.symbol,
        reference.purpose,
        reference.source,
      ]),
    ].join(' ');
  }
  if (
    'parse_status' in stats
    && stats.parse_status === 'raw'
    && (!('semantic_layout' in stats) || stats.semantic_layout !== 'scene_runtime_layout_partial')
  ) {
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
  if ('semantic_layout' in stats && stats.semantic_layout === 'scene_runtime_layout_partial') {
    const recon = stats.reconnaissance || {};
    return [
      stats.parse_status,
      stats.decode_status,
      stats.decode_note,
      stats.semantic_layout,
      recon.world?.island,
      recon.world?.cube_x,
      recon.world?.cube_y,
      recon.world?.shadow_level,
      recon.world?.labyrinth_mode,
      recon.world?.cube_mode,
      recon.world?.runtime_environment ? Object.values(recon.world.runtime_environment).join(' ') : '',
      recon.ambience?.alpha_light,
      recon.ambience?.beta_light,
      recon.ambience?.cube_jingle,
      recon.ambience?.runtime_audio_lighting ? Object.values(recon.ambience.runtime_audio_lighting).join(' ') : '',
      recon.background?.runtime_cube,
      recon.background?.resolved_gri_entry,
      recon.background?.resolved_bll_entry,
      recon.background?.resolved_grm_entry,
      recon.background?.palette?.resolved_palette_entry,
      recon.background?.palette?.resolved_palette_name,
      recon.object_count,
      recon.sprite_object_count,
      recon.anim3ds_object_count,
      recon.zone_count,
      formatCounts(recon.zone_type_counts),
      formatCounts(recon.grm_fragment_link_counts),
      recon.track_count,
      recon.patch_count,
      formatCounts(recon.patch_size_counts),
      formatCounts(recon.patch_target_counts),
      recon.hero?.track_script_analysis?.unique_opcodes.map((opcode) => opcode.mnemonic).join(' '),
      recon.hero?.life_script_analysis?.unique_opcodes.map((opcode) => opcode.mnemonic).join(' '),
      (recon.sampled_zones || [])
        .map((zone) => `${zone.index} ${zone.type_name} ${zone.value} ${zone.start.x} ${zone.start.y} ${zone.start.z} ${zone.end.x} ${zone.end.y} ${zone.end.z}`)
        .join(' '),
      (recon.grm_fragment_links || [])
        .map((link) => `${link.zone_index} ${link.zone_value} ${link.grm_index} ${link.resolved_grm_entry ?? ''} ${link.asset_id ?? ''}`)
        .join(' '),
      (recon.sampled_tracks || [])
        .map((track) => `${track.index} ${track.position.x} ${track.position.y} ${track.position.z}`)
        .join(' '),
      (recon.sampled_patches || [])
        .map((patch) => `${patch.index} ${patch.size} ${patch.target_offset} ${patch.target.kind} ${patch.target.owner || ''}`)
        .join(' '),
      (recon.sampled_objects || [])
        .map((object) => `${object.index} ${object.file3d_index} ${object.gen_body} ${object.gen_anim} ${object.sprite} ` +
          `${object.track_script_analysis?.unique_opcodes.map((opcode) => opcode.mnemonic).join(' ') || ''} ` +
          `${object.life_script_analysis?.unique_opcodes.map((opcode) => opcode.mnemonic).join(' ') || ''}`)
        .join(' '),
    ].join(' ');
  }
  if ('semantic_layout' in stats && (
    stats.semantic_layout === 'lba2_palette'
    || stats.semantic_layout === 'lba2_texture_atlas_indexed'
    || stats.semantic_layout === 'lba2_indexed_image_256'
    || stats.semantic_layout === 'screen_palette'
    || stats.semantic_layout === 'screen_indexed_image_640x480'
    || stats.semantic_layout === 'holomap_globe_uv_map'
    || stats.semantic_layout === 'holomap_globe_altitude_map'
    || stats.semantic_layout === 'holomap_globe_texture_map'
    || stats.semantic_layout === 'holomap_arrow_table'
    || stats.semantic_layout === 'holomap_plan_image_640x480'
    || stats.semantic_layout === 'holomap_plan_view_params'
    || stats.semantic_layout === 'bkg_header'
    || stats.semantic_layout === 'bkg_grid_map'
    || stats.semantic_layout === 'bkg_grm_fragment'
    || stats.semantic_layout === 'bkg_block_table'
    || stats.semantic_layout === 'bkg_brick_graphic'
    || stats.semantic_layout === 'bkg_cube_map'
    || stats.semantic_layout === 'text_order_table'
    || stats.semantic_layout === 'text_payload_bank'
    || stats.semantic_layout === 'sample_wave_audio'
    || stats.semantic_layout === 'smacker_video'
    || stats.semantic_layout === 'file3d_table'
    || stats.semantic_layout === 'sprite_zv_table'
    || stats.semantic_layout === 'ress_offset_record_table'
    || stats.semantic_layout === 'ress_fixed_s16x8_table'
    || stats.semantic_layout === 'ress_ext_size_info'
    || stats.semantic_layout === 'xpl_palette_bundle'
    || stats.semantic_layout === 'acf_name_list'
    || stats.semantic_layout === 'ress_unclassified_payload'
  )) {
    const resource = stats as ResourceStats;
    return [
      resource.parse_status,
      resource.decode_status,
      resource.decode_note,
      resource.semantic_layout,
      resource.color_count,
      resource.width,
      resource.height,
      resource.offset_x,
      resource.offset_y,
      resource.opaque_pixels,
      resource.transparent_pixels,
      resource.encoded_bytes_consumed,
      resource.trailing_bytes,
      formatCounts(resource.run_type_counts),
      resource.max_row_run_count,
      (resource.palette_indices || []).join(' '),
      resource.object_count,
      resource.body_reference_count,
      resource.animation_reference_count,
      resource.backend,
      resource.bkg_entry_role,
      resource.bkg_relative_index,
      resource.language,
      resource.text_file_name,
      resource.preview_codepage,
      resource.sample_runtime_index,
      resource.audio_format,
      resource.sample_frames,
      resource.duration_ms,
      (resource.chunk_ids || []).join(' '),
      resource.depth,
      resource.record_count,
      resource.record_bytes,
      resource.offset_table_bytes,
      formatCounts(resource.record_length_counts),
      formatCounts(resource.type_counts),
      resource.max_size_list_decors,
      resource.max_size_body_decors,
      resource.max_size_tex_def,
      resource.max_total_body_decors,
      resource.xpl_name,
      resource.runtime_table_name,
      resource.runtime_buffer,
      resource.runtime_purpose,
      resource.runtime_reference_status,
      resource.source_provenance,
      resource.scene_palette_reference_count,
      resource.holomap_name,
      resource.plan_variant ? Object.entries(resource.plan_variant).map(([key, value]) => `${key} ${value}`).join(' ') : '',
      resource.screen_name,
      ...(resource.direct_code_references || []).flatMap((reference) => [
        reference.symbol,
        reference.purpose,
        reference.source,
      ]),
      resource.header ? Object.entries(resource.header).map(([key, value]) => `${key} ${value}`).join(' ') : '',
      resource.fields ? Object.entries(resource.fields).map(([key, value]) => `${key} ${value}`).join(' ') : '',
      resource.composition ? Object.entries(resource.composition).map(([key, value]) => `${key} ${searchValue(value)}`).join(' ') : '',
      formatCounts(resource.text_link_counts),
      (resource.text_links || []).map((link) => `${link.message_id} ${link.text_file_name} ${link.arrow_indices.join(' ')} ${link.localized_links.map((localized) => `${localized.language || ''} ${localized.preview || ''}`).join(' ')}`).join(' '),
      (resource.sampled_block_indices || []).join(' '),
      (resource.sampled_cell_refs || []).map((cell) => `block ${cell.block} cell ${cell.cell} brick ${cell.brick_ref} brk ${cell.resolved_brk_entry} ${cell.x} ${cell.y} ${cell.z} code ${cell.code} collision ${cell.collision}`).join(' '),
      (resource.sampled_message_ids || []).join(' '),
      (resource.sampled_names || []).join(' '),
      (resource.sampled_records || []).map((record) => `${record.index} ${record.flag ?? ''} ${record.preview || ''} ${record.resolved_gri_entry ?? ''} ${record.resolved_bll_entry ?? ''} ${record.resolved_grm_entry ?? ''} ${record.used_block_count ?? ''}`).join(' '),
      resource.preview_hex,
      (resource.unknown_descriptors || [])
        .map((descriptor) => `${descriptor.section} ${descriptor.offset} ${descriptor.length} ${descriptor.confidence} ${descriptor.note}`)
        .join(' '),
    ].join(' ');
  }
  if ('semantic_layout' in stats && (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame')) {
    return [
      stats.parse_status,
      stats.decode_status,
      stats.decode_note,
      stats.semantic_layout,
      stats.width,
      stats.height,
      stats.offset_x,
      stats.offset_y,
      stats.palette_indices.join(' '),
      stats.anim3ds_info?.name,
      stats.runtime?.backend,
      stats.runtime?.archive,
      stats.runtime?.runtime_sprite_index,
      stats.runtime?.index_rule,
      ...(stats.direct_code_references || []).flatMap((reference) => [
        reference.symbol,
        reference.purpose,
        reference.source,
      ]),
    ].join(' ');
  }
  if ('semantic_layout' in stats && stats.semantic_layout === 'anim3ds_frame_ranges') {
    return [
      stats.parse_status,
      stats.decode_status,
      stats.decode_note,
      stats.semantic_layout,
      stats.entry_count,
      stats.frame_min,
      stats.frame_max,
      stats.runtime_reference_status,
      stats.source_provenance,
      stats.runtime_playback?.timing_source,
      stats.runtime_playback?.advance_rule,
      stats.runtime_playback?.scene_initialization,
      stats.runtime_playback ? Object.entries(stats.runtime_playback.track_controls).map(([key, value]) => `${key} ${value}`).join(' ') : '',
      stats.entries.map((entry) => `${entry.name} ${entry.start_frame} ${entry.end_frame}`).join(' '),
    ].join(' ');
  }
  return Object.values(stats || {}).join(' ');
}

function searchValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(searchValue).join(' ');
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entry]) => `${key} ${searchValue(entry)}`)
      .join(' ');
  }
  return String(value);
}

function scoreAsset(asset: CatalogAsset, query: string): number {
  let score = 0;
  if (asset.kind === 'model') score += 1000;
  if (asset.kind === 'scene') score += 140;
  if (asset.kind === 'resource') score += 130;
  if (asset.kind === 'sprite') score += 100;
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
  const usage = sceneUsageMeta(asset.scene_usages || []);
  if (asset.kind === 'model') {
    const stats = asset.stats as ModelStats;
    const direct = stats.direct_reference_count ? `, ${stats.direct_reference_count} direct refs` : '';
    return `${source} - ${stats.vertices || 0} verts, ${stats.polygons || 0} polys, ${stats.bones || 0} bones${direct}${usage}`;
  }
  if (asset.kind === 'scene') {
    const scene = asset.stats as SceneStats;
    const recon = scene.reconnaissance || {};
    return `${source} - ${recon.object_count ?? '-'} objects, ${recon.zone_count ?? '-'} zones, ${recon.track_count ?? '-'} waypoints`;
  }
  if (asset.kind === 'resource') {
    const resource = asset.stats as ResourceStats;
    if (resource.semantic_layout === 'lba2_palette') return `${source} - ${resource.color_count ?? '-'} palette colors`;
    if (resource.semantic_layout === 'screen_palette') return `${source} - ${resource.screen_name ?? 'screen'} palette`;
    if (resource.semantic_layout === 'lba2_texture_atlas_indexed') return `${source} - ${resource.width ?? '-'}x${resource.height ?? '-'} indexed atlas`;
    if (resource.semantic_layout === 'lba2_indexed_image_256') return `${source} - ${resource.width ?? '-'}x${resource.height ?? '-'} indexed image`;
    if (resource.semantic_layout === 'screen_indexed_image_640x480') return `${source} - ${resource.width ?? '-'}x${resource.height ?? '-'} screen image`;
    if (resource.semantic_layout === 'holomap_globe_uv_map') return `${source} - ${resource.record_count ?? '-'} globe UV pairs`;
    if (resource.semantic_layout === 'holomap_globe_altitude_map') return `${source} - ${resource.holomap_name ?? 'globe'} altitude map`;
    if (resource.semantic_layout === 'holomap_globe_texture_map') return `${source} - ${resource.width ?? '-'}x${resource.height ?? '-'} globe texture`;
    if (resource.semantic_layout === 'holomap_arrow_table') return `${source} - ${resource.record_count ?? '-'} holomap arrows`;
    if (resource.semantic_layout === 'holomap_plan_image_640x480') return `${source} - ${resource.width ?? '-'}x${resource.height ?? '-'} plan image`;
    if (resource.semantic_layout === 'holomap_plan_view_params') return `${source} - plan view parameters`;
    if (resource.semantic_layout === 'bkg_header') return `${source} - background archive ranges`;
    if (resource.semantic_layout === 'bkg_grid_map') return `${source} - grid map ${resource.bkg_relative_index ?? '-'}, ${resource.fields?.used_block_count ?? '-'} used blocks`;
    if (resource.semantic_layout === 'bkg_grm_fragment') return `${source} - GRM ${resource.bkg_relative_index ?? '-'} ${resource.width ?? '-'}x${resource.height ?? '-'}x${resource.depth ?? '-'}`;
    if (resource.semantic_layout === 'bkg_block_table') return `${source} - block table ${resource.bkg_relative_index ?? '-'}, ${resource.record_count ?? '-'} blocks`;
    if (resource.semantic_layout === 'bkg_brick_graphic') return `${source} - brick graph ${resource.bkg_relative_index ?? '-'} ${resource.width ?? '-'}x${resource.height ?? '-'}`;
    if (resource.semantic_layout === 'bkg_cube_map') return `${source} - ${resource.record_count ?? '-'} cube indirection records`;
    if (resource.semantic_layout === 'text_order_table') return `${source} - ${resource.language ?? 'language'} ${resource.text_file_name ?? '-'} order, ${resource.record_count ?? '-'} message ids`;
    if (resource.semantic_layout === 'text_payload_bank') return `${source} - ${resource.language ?? 'language'} ${resource.text_file_name ?? '-'} text, ${resource.record_count ?? '-'} records`;
    if (resource.semantic_layout === 'sample_wave_audio') return `${source} - sample ${resource.sample_runtime_index ?? '-'} ${resource.audio_format ?? 'audio'} ${resource.fields?.channels ?? '-'}ch ${resource.fields?.bits_per_sample ?? '-'}-bit ${resource.fields?.sample_rate ?? '-'}Hz`;
    if (resource.semantic_layout === 'smacker_video') return `${source} - movie ${resource.acf_name ?? '-'} ${resource.width ?? '-'}x${resource.height ?? '-'} ${resource.frame_count ?? '-'} frames`;
    if (resource.semantic_layout === 'file3d_table') return `${source} - ${resource.object_count ?? '-'} File3D objects`;
    if (resource.semantic_layout === 'sprite_zv_table') return `${source} - ${resource.record_count ?? '-'} ${resource.backend ?? 'sprite'} bounds`;
    if (resource.semantic_layout === 'ress_offset_record_table') return `${source} - ${resource.runtime_table_name ?? 'RESS'} ${resource.record_count ?? '-'} offset records`;
    if (resource.semantic_layout === 'ress_fixed_s16x8_table') return `${source} - ${resource.runtime_table_name ?? 'RESS'} ${resource.record_count ?? '-'} signed-word records`;
    if (resource.semantic_layout === 'ress_ext_size_info') return `${source} - exterior memory sizing`;
    if (resource.semantic_layout === 'xpl_palette_bundle') return `${source} - ${resource.xpl_name ?? 'XPL'} palette bundle`;
    if (resource.semantic_layout === 'acf_name_list') return `${source} - ${resource.entry_count ?? '-'} SMK names`;
    return `${source} - ${asset.decoded_bytes} resource bytes`;
  }
  if ('parse_status' in asset.stats && asset.stats.parse_status === 'raw') {
    const raw = asset.stats as RawAnimationStats;
    if (raw.anim3ds_info) {
      return `${source} - ${asset.decoded_bytes} bytes, ${raw.anim3ds_info.name} frame ${raw.anim3ds_info.relative_frame}`;
    }
    return `${source} - ${asset.decoded_bytes} bytes, ${asset.kind === 'sprite' ? 'raw sprite frame evidence' : 'raw animation evidence'}${usage}`;
  }
  if ('semantic_layout' in asset.stats && (asset.stats.semantic_layout === 'lsp_sprite_frame' || asset.stats.semantic_layout === 'raw_sprite_frame')) {
    const sprite = asset.stats as SpriteFrameStats;
    const range = sprite.anim3ds_info ? `, ${sprite.anim3ds_info.name} frame ${sprite.anim3ds_info.relative_frame}` : '';
    const backend = sprite.runtime?.backend ? `, ${sprite.runtime.backend}` : '';
    const format = sprite.semantic_layout === 'raw_sprite_frame' ? 'raw sprite' : 'LSP sprite';
    return `${source} - ${sprite.width}x${sprite.height} ${format}${backend}${range}${usage}`;
  }
  if ('semantic_layout' in asset.stats && asset.stats.semantic_layout === 'anim3ds_frame_ranges') {
    const anim3ds = asset.stats as Anim3dsInfoStats;
    return `${source} - ${anim3ds.entry_count} ANIM3DS ranges, frames ${anim3ds.frame_min}..${anim3ds.frame_max}`;
  }
  const animation = asset.stats as AnimationStats;
  const metadata = animationMetadataText(asset);
  const prefix = metadata ? `${metadata} - ` : '';
  return `${source} - ${prefix}${animation.keyframes || 0} keyframes, ${animation.boneframes || 0} bones, loop ${animation.loop_frame ?? '-'}${usage}`;
}

function assetPillText(asset: CatalogAsset): string {
  if (asset.animation_state) return `${asset.kind} ${asset.animation_state}`;
  const stats = asset.stats;
  if (asset.kind === 'scene') return 'scene partial';
  if (asset.kind === 'resource') return 'resource';
  if (asset.kind === 'sprite' && 'semantic_layout' in stats && (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame')) {
    return `${stats.runtime?.backend || 'sprite'} sprite`;
  }
  return asset.kind;
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

function sceneUsageMeta(usages: SceneAssetUsage[]): string {
  if (usages.length === 0) return '';
  const sceneCount = new Set(usages.map((usage) => usage.scene_asset_id)).size;
  return `, used by ${usages.length} scene object${usages.length === 1 ? '' : 's'} in ${sceneCount} scene${sceneCount === 1 ? '' : 's'}`;
}

function sceneUsageSearchText(usages: SceneAssetUsage[]): string {
  return usages
    .map((usage) => [
      usage.kind,
      usage.scene_asset_id,
      usage.scene_label,
      usage.scene_index,
      usage.object_index,
      usage.file3d_index,
      usage.gen_body,
      usage.gen_anim,
      usage.sprite,
      usage.generic_id,
      usage.generic_name,
      usage.label,
      usage.backend,
      usage.runtime_sprite_index,
      usage.script_kind,
      usage.reference_key,
      usage.reference_value,
      usage.zone_index,
      usage.text_id,
      usage.text_file_index,
      usage.text_file_name,
      usage.language,
      usage.record_index,
      usage.preview,
      usage.sample_id,
      usage.slot_index,
      usage.audio_format,
      usage.sample_rate,
      usage.bits_per_sample,
      usage.channels,
      usage.duration_ms,
      usage.acf_name,
      usage.acf_index,
      usage.frame_count,
      usage.anim3ds_range?.animation_number,
      usage.anim3ds_range?.name,
      usage.anim3ds_range?.start_frame,
      usage.anim3ds_range?.end_frame,
      usage.resolution_rule,
    ].join(' '))
    .join(' ');
}

function formatCounts(counts?: Record<string, number>): string {
  return Object.entries(counts || {})
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}:${value}`)
    .join(', ');
}
