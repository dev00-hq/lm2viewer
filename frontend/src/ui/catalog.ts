import { animationCompatibilityLabel, animationMatchesModel } from '../compatibility';
import type { AnimationStats, Anim3dsInfoStats, Catalog, CatalogAsset, KindFilter, ModelStats, RawAnimationStats, ResourceStats, SceneAssetUsage, SceneScriptAnalysis, SceneStats, SpriteFrameStats } from '../types';

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
        `${modelStats.runtime_reference_status ? `runtime: ${escapeHtml(modelStats.runtime_reference_status)}<br>` : ''}` +
        `${renderDirectCodeReferences(modelStats.direct_code_references || [])}` +
        `${renderSceneUsages(asset.scene_usages || [])}` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    if ('semantic_layout' in stats && stats.semantic_layout === 'anim3ds_frame_ranges') {
      const anim3ds = stats as Anim3dsInfoStats;
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `ANIM3DS sprite animation metadata, ${anim3ds.entry_count} ranges<br>` +
        `frames ${anim3ds.frame_min}..${anim3ds.frame_max}, ${anim3ds.frame_total} referenced frames<br>` +
        `${renderAnim3dsPlayback(anim3ds)}` +
        `${renderAnim3dsWarnings(anim3ds.range_warnings)} ` +
        `${renderAnim3dsRanges(anim3ds.entries)}<br>` +
        `sha256: ${escapeHtml(asset.decoded_sha256)}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    if ('semantic_layout' in stats && (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame')) {
      const sprite = stats as SpriteFrameStats;
      const format = sprite.semantic_layout === 'raw_sprite_frame' ? 'raw sprite frame' : 'LSP sprite frame';
      const anim3dsInfo = sprite.anim3ds_info
        ? `<br>ANIM3DS range: ${escapeHtml(sprite.anim3ds_info.name)} frame ${escapeHtml(sprite.anim3ds_info.relative_frame)} ` +
          `(${escapeHtml(sprite.anim3ds_info.start_frame)}..${escapeHtml(sprite.anim3ds_info.end_frame)})`
        : '';
      const runtime = renderSpriteRuntime(sprite);
      const runtimeRule = sprite.runtime?.index_rule
        ? `rule: ${escapeHtml(sprite.runtime.index_rule)}<br>`
        : '';
      const directReferences = renderDirectCodeReferences(sprite.direct_code_references || []);
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `decoded ${format}, ${escapeHtml(sprite.width)}x${escapeHtml(sprite.height)}, offset ${escapeHtml(sprite.offset_x)},${escapeHtml(sprite.offset_y)}${anim3dsInfo}<br>` +
        `${runtime}` +
        `${runtimeRule}` +
        `${directReferences}` +
        `${escapeHtml(sprite.opaque_pixels)} opaque pixels, ${escapeHtml(sprite.transparent_pixels)} transparent, ${escapeHtml(sprite.color_count)} palette colors<br>` +
        `encoded bytes consumed: ${escapeHtml(sprite.encoded_bytes_consumed)}, trailing bytes: ${escapeHtml(sprite.trailing_bytes)}<br>` +
        `${renderUnknownDescriptors(sprite.unknown_descriptors || [])}` +
        `${renderSceneUsages(asset.scene_usages || [])}` +
        `sha256: ${escapeHtml(asset.decoded_sha256)}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    if ('semantic_layout' in stats && stats.semantic_layout === 'scene_runtime_layout_partial') {
      const scene = stats as SceneStats;
      const recon = scene.reconnaissance || {};
      const world = recon.world;
      const hero = recon.hero;
      const worldText = world
        ? `island ${escapeHtml(world.island)}, cube ${escapeHtml(world.cube_x)},${escapeHtml(world.cube_y)}, mode ${escapeHtml(world.cube_mode)}`
        : 'world header unavailable';
      const backgroundText = renderSceneBackground(recon.background);
      const heroText = hero
        ? `hero start ${escapeHtml(hero.start.x)},${escapeHtml(hero.start.y)},${escapeHtml(hero.start.z)}, scripts ${escapeHtml(hero.track_script_bytes)}/${escapeHtml(hero.life_script_bytes)} bytes`
        : 'hero start unavailable';
      const heroScripts = hero
        ? `${renderSceneScriptSummary('hero track', hero.track_script_analysis)}${renderSceneScriptSummary('hero life', hero.life_script_analysis)}`
        : '';
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `SCENE top-level reconnaissance, ${escapeHtml(scene.decoded_bytes)} bytes<br>` +
        `${worldText}<br>` +
        `${renderSceneEnvironment(world, recon.ambience)}` +
        `${backgroundText}` +
        `${heroText}<br>` +
        `${heroScripts}` +
        `objects: ${escapeHtml(recon.object_count ?? '-')}, sprite objects: ${escapeHtml(recon.sprite_object_count ?? '-')}, ANIM3DS objects: ${escapeHtml(recon.anim3ds_object_count ?? '-')}<br>` +
        `object links: ${escapeHtml(recon.linked_body_refs ?? 0)} body, ${escapeHtml(recon.linked_animation_refs ?? 0)} animation, ${escapeHtml(recon.linked_sprite_refs ?? 0)} sprite<br>` +
        `script links: ${escapeHtml(recon.script_linked_body_refs ?? 0)} body, ${escapeHtml(recon.script_linked_animation_refs ?? 0)} animation, ${escapeHtml(recon.script_linked_sprite_refs ?? 0)} sprite<br>` +
        `text links: ${escapeHtml(recon.text_link_counts?.script_logical_refs ?? 0)} script refs, ${escapeHtml(recon.text_link_counts?.zone_logical_refs ?? 0)} zone refs, file ${escapeHtml(recon.text_file_index ?? '-')}<br>` +
        `sample links: ${escapeHtml(recon.sample_link_counts?.script_linked_refs ?? 0)} script refs, ${escapeHtml(recon.sample_link_counts?.ambience_linked_refs ?? 0)} ambience refs, ` +
          `${escapeHtml((recon.sample_link_counts?.script_missing_refs ?? 0) + (recon.sample_link_counts?.ambience_missing_refs ?? 0))} missing${renderSceneSampleMissing(recon)}` +
        `video links: ${escapeHtml(recon.video_link_counts?.script_linked_refs ?? 0)}/${escapeHtml(recon.video_link_counts?.script_logical_refs ?? 0)} script refs<br>` +
        `local script links: ${escapeHtml(recon.script_local_link_counts?.object ?? 0)} objects, ${escapeHtml(recon.script_local_link_counts?.waypoint ?? 0)} waypoints, ${escapeHtml(recon.script_local_link_counts?.zone ?? 0)} zones<br>` +
        `script control flow: ${escapeHtml(recon.script_control_flow_counts?.found ?? 0)}/${escapeHtml(recon.script_control_flow_counts?.links ?? 0)} resolved targets, ${escapeHtml(recon.script_control_flow_counts?.labels ?? 0)} track labels; target statuses ${escapeHtml(formatCounts(recon.script_control_flow_target_status_counts) || '-')}<br>` +
        `cross-script targets: ${escapeHtml(recon.script_cross_link_counts?.found ?? 0)}/${escapeHtml(recon.script_cross_link_counts?.links ?? 0)} resolved, ${escapeHtml(recon.script_cross_link_counts?.track ?? 0)} track, ${escapeHtml(recon.script_cross_link_counts?.life ?? 0)} life; target statuses ${escapeHtml(formatCounts(recon.script_cross_link_target_status_counts) || '-')}<br>` +
        `zones: ${escapeHtml(recon.zone_count ?? '-')}, waypoints: ${escapeHtml(recon.track_count ?? '-')}, patches: ${escapeHtml(recon.patch_count ?? '-')}<br>` +
        `${renderSceneMechanics(recon)}` +
        `decode status: ${escapeHtml(scene.decode_status)} - ${escapeHtml(scene.decode_note)}<br>` +
        `${renderSceneObjects(recon.sampled_objects || [], recon.sampled_object_count)}` +
        `${renderUnknownDescriptors(scene.unknown_descriptors || [])}` +
        `sha256: ${escapeHtml(asset.decoded_sha256)}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    if (asset.kind === 'resource') {
      const resource = stats as ResourceStats;
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `${escapeHtml(resource.semantic_layout)}, ${escapeHtml(resource.decoded_bytes)} bytes<br>` +
        `decode status: ${escapeHtml(resource.decode_status)} - ${escapeHtml(resource.decode_note)}<br>` +
        `${renderResourceDetail(resource)}` +
        `${renderDirectCodeReferences(resource.direct_code_references || [])}` +
        `${renderUnknownDescriptors(resource.unknown_descriptors || [])}` +
        `${renderSceneUsages(asset.scene_usages || [])}` +
        `sha256: ${escapeHtml(asset.decoded_sha256)}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    if ('parse_status' in stats && stats.parse_status === 'raw') {
      const raw = stats as RawAnimationStats;
      const descriptors = raw.unknown_descriptors || [];
      const parseError = raw.parse_error ? `<br>parse error: ${escapeHtml(raw.parse_error)}` : '';
      const anim3dsInfo = raw.anim3ds_info
        ? `<br>ANIM3DS range: ${escapeHtml(raw.anim3ds_info.name)} frame ${escapeHtml(raw.anim3ds_info.relative_frame)} ` +
          `(${escapeHtml(raw.anim3ds_info.start_frame)}..${escapeHtml(raw.anim3ds_info.end_frame)})`
        : '';
      this.options.detail.innerHTML =
        `<strong>${escapeHtml(asset.label)}</strong><br>` +
        `${escapeHtml(asset.source.hqr)}[${asset.source.entry_index}]<br>` +
        `${asset.kind === 'sprite' ? 'raw sprite frame evidence' : 'raw animation evidence'}, ${asset.decoded_bytes} bytes<br>` +
        `decode status: ${escapeHtml(raw.decode_status)} - ${escapeHtml(raw.decode_note)}${parseError}${anim3dsInfo}<br>` +
        `header words: ${escapeHtml((raw.header_words || []).join(', '))}<br>` +
        `unknown descriptors: ${descriptors.length}<br>` +
        `${renderUnknownDescriptors(descriptors)}` +
        `${renderSceneUsages(asset.scene_usages || [])}` +
        `sha256: ${escapeHtml(asset.decoded_sha256)}<br>` +
        `${escapeHtml(asset.relative_path || '')}`;
      return;
    }

    const animation = stats as AnimationStats;
    const compatibility = this.selectedModel
      ? `${animationCompatibilityLabel(asset, this.selectedModel)}<br>`
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
      `${renderSceneUsages(asset.scene_usages || [])}` +
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
    button.className = 'asset-button' + (asset.id === this.selectedAssetId ? ' active' : '');
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
      resource.composition ? Object.entries(resource.composition).map(([key, value]) => `${key} ${JSON.stringify(value)}`).join(' ') : '',
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

function renderResourceDetail(resource: ResourceStats): string {
  if (resource.semantic_layout === 'lba2_palette') {
    const colors = (resource.sample_colors || [])
      .map((color) => `#${Number(color).toString(16).padStart(6, '0')}`)
      .join(', ');
    return `colors: ${escapeHtml(resource.color_count ?? '-')}, transparent index ${escapeHtml(resource.transparent_index ?? '-')}<br>` +
      `sample: ${escapeHtml(colors)}<br>`;
  }
  if (resource.semantic_layout === 'lba2_texture_atlas_indexed' || resource.semantic_layout === 'lba2_indexed_image_256') {
    const label = resource.semantic_layout === 'lba2_texture_atlas_indexed' ? 'atlas' : 'image';
    return `${label}: ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')}, ` +
      `${escapeHtml(resource.unique_palette_indices ?? '-')} palette indices<br>` +
      `palette source: ${escapeHtml(resource.palette_entry?.hqr || '-')}:${escapeHtml(resource.palette_entry?.entry_index ?? '-')}<br>`;
  }
  if (resource.semantic_layout === 'file3d_table') {
    const rows = (resource.sampled_objects || []).slice(0, 12).map((object) =>
      `<div class="unknown-descriptor">` +
      `<span>File3D ${escapeHtml(object.index)}</span>` +
      `<span>${escapeHtml(object.body_records.length)} body records</span>` +
      `<span>${escapeHtml(object.animation_records.length)} animation records</span>` +
      `<span>${escapeHtml(object.command_count)} commands</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    return `objects: ${escapeHtml(resource.object_count ?? '-')}, body refs ${escapeHtml(resource.body_reference_count ?? '-')}, animation refs ${escapeHtml(resource.animation_reference_count ?? '-')}<br>${table}`;
  }
  if (resource.semantic_layout === 'sprite_zv_table') {
    const rows = (resource.sampled_records || []).slice(0, 12).map((record) =>
      `<div class="unknown-descriptor">` +
      `<span>${escapeHtml(record.backend)} ${escapeHtml(record.index)}</span>` +
      `<span>hotspot ${escapeHtml(record.hotspot?.x ?? '-')},${escapeHtml(record.hotspot?.y ?? '-')}</span>` +
      `<span>x ${escapeHtml(record.bounds?.min_x ?? '-')}..${escapeHtml(record.bounds?.max_x ?? '-')}</span>` +
      `<span>y ${escapeHtml(record.bounds?.min_y ?? '-')}..${escapeHtml(record.bounds?.max_y ?? '-')}</span>` +
      `<span>z ${escapeHtml(record.bounds?.min_z ?? '-')}..${escapeHtml(record.bounds?.max_z ?? '-')}</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    return `backend: ${escapeHtml(resource.backend || '-')}, records ${escapeHtml(resource.record_count ?? '-')}<br>${table}`;
  }
  if (resource.semantic_layout === 'ress_offset_record_table') {
    const rows = (resource.sampled_records || []).slice(0, 12).map((record) =>
      `<div class="unknown-descriptor">` +
      `<span>record ${escapeHtml(record.index)}</span>` +
      `<span>offset ${escapeHtml(record.offset ?? '-')}, length ${escapeHtml(record.byte_length ?? '-')}</span>` +
      `<span>${escapeHtml(record.preview_hex || '')}</span>` +
      `<span>${escapeHtml(record.sha256 || '')}</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    return renderRuntimeTableInfo(resource) +
      `records: ${escapeHtml(resource.record_count ?? '-')}, offset table bytes ${escapeHtml(resource.offset_table_bytes ?? '-')}<br>` +
      `record lengths: ${escapeHtml(formatCounts(resource.record_length_counts))}<br>${table}`;
  }
  if (resource.semantic_layout === 'ress_fixed_s16x8_table') {
    const rows = (resource.sampled_records || []).slice(0, 12).map((record) =>
      `<div class="unknown-descriptor">` +
      `<span>record ${escapeHtml(record.index)}</span>` +
      `<span>offset ${escapeHtml(record.offset ?? '-')}</span>` +
      `<span>${escapeHtml((record.values || []).join(', '))}</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    return renderRuntimeTableInfo(resource) +
      `records: ${escapeHtml(resource.record_count ?? '-')}, record bytes ${escapeHtml(resource.record_bytes ?? '-')}<br>${table}`;
  }
  if (resource.semantic_layout === 'ress_ext_size_info') {
    return `list decors max: ${escapeHtml(resource.max_size_list_decors ?? '-')}, ` +
      `body decors max: ${escapeHtml(resource.max_size_body_decors ?? '-')}, ` +
      `tex defs max: ${escapeHtml(resource.max_size_tex_def ?? '-')}, ` +
      `total body decors max: ${escapeHtml(resource.max_total_body_decors ?? '-')}<br>`;
  }
  if (resource.semantic_layout === 'xpl_palette_bundle') {
    const header = resource.header || {};
    const colors = (resource.sample_colors || [])
      .map((color) => `#${Number(color).toString(16).padStart(6, '0')}`)
      .join(', ');
    return `xpl: ${escapeHtml(resource.xpl_name || '-')}, palette colors ${escapeHtml(resource.color_count ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}, runtime: ${escapeHtml(resource.runtime_reference_status || '-')}, scene refs ${escapeHtml(resource.scene_palette_reference_count ?? 0)}<br>` +
      `offsets: palette ${escapeHtml(header.offset_palette ?? '-')}, fog ${escapeHtml(header.offset_fog ?? '-')}, transparency ${escapeHtml(header.offset_transparency ?? '-')}<br>` +
      `shade: ${escapeHtml(header.shade_start_percent ?? '-')}..${escapeHtml(header.shade_end_percent ?? '-')} normal ${escapeHtml(header.shade_normal_level ?? '-')}, fog color ${escapeHtml(header.fog_color ?? '-')}<br>` +
      `sample: ${escapeHtml(colors)}<br>`;
  }
  if (resource.semantic_layout === 'screen_palette') {
    return `screen: ${escapeHtml(resource.screen_name || '-')}, palette colors ${escapeHtml(resource.color_count ?? '-')}<br>` +
      `pair base: ${escapeHtml(resource.screen_pair_base ?? '-')}, paired entry ${escapeHtml(resource.paired_entry_index ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}, runtime: ${escapeHtml(resource.runtime_reference_status || '-')}<br>`;
  }
  if (resource.semantic_layout === 'screen_indexed_image_640x480') {
    return `screen: ${escapeHtml(resource.screen_name || '-')}, ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')} indexed pixels<br>` +
      `pair base: ${escapeHtml(resource.screen_pair_base ?? '-')}, palette ${escapeHtml(resource.palette_entry ? `${resource.palette_entry.hqr}:${resource.palette_entry.entry_index}` : '-')}<br>` +
      `unique palette indices: ${escapeHtml(resource.unique_palette_indices ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}, runtime: ${escapeHtml(resource.runtime_reference_status || '-')}<br>`;
  }
  if (resource.semantic_layout === 'holomap_globe_uv_map') {
    return `records: ${escapeHtml(resource.record_count ?? '-')}, record bytes ${escapeHtml(resource.record_bytes ?? '-')}<br>` +
      `sample: ${escapeHtml(JSON.stringify(resource.sampled_records || []))}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'holomap_globe_altitude_map') {
    return `holomap: ${escapeHtml(resource.holomap_name || '-')}, altitude samples ${escapeHtml(resource.pixel_count ?? '-')}<br>` +
      `unique values: ${escapeHtml(resource.unique_palette_indices ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'holomap_globe_texture_map') {
    return `holomap: ${escapeHtml(resource.holomap_name || '-')}, ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')} indexed texture<br>` +
      `unique palette indices: ${escapeHtml(resource.unique_palette_indices ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'holomap_arrow_table') {
    const linkRows = (resource.text_links || []).slice(0, 8).map((link) => {
      const previews = link.localized_links.slice(0, 2).map((localized) => `${localized.language || '-'}: ${localized.preview || ''}`).join(' | ');
      return `<div class="unknown-descriptor">` +
        `<span>message ${escapeHtml(link.message_id)}</span>` +
        `<span>arrows ${escapeHtml(link.arrow_indices.slice(0, 6).join(', '))}${link.arrow_indices.length > 6 ? ' +' + escapeHtml(link.arrow_indices.length - 6) : ''}</span>` +
        `<span>${escapeHtml(link.localized_records)} localized records</span>` +
        `<span>${escapeHtml(previews)}</span>` +
        `</div>`;
    }).join('');
    const linkTable = linkRows ? `<div class="unknown-descriptors">${linkRows}</div>` : '';
    const counts = resource.text_link_counts ? `; text ${formatCounts(resource.text_link_counts)}` : '';
    return `records: ${escapeHtml(resource.record_count ?? '-')}, active ${escapeHtml(resource.active_count ?? '-')}, exterior ${escapeHtml(resource.exterior_count ?? '-')}, messages ${escapeHtml(resource.message_count ?? '-')}${escapeHtml(counts)}<br>` +
      `sample: ${escapeHtml(JSON.stringify((resource.sampled_records || []).slice(0, 6)))}<br>` +
      `${linkTable}` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'holomap_plan_image_640x480') {
    const variant = resource.plan_variant;
    const selection = variant ? `variant ${variant.variant_index}, island ${variant.selected_island}, ${variant.selection_condition}` : '-';
    return `holomap: ${escapeHtml(resource.holomap_name || '-')}, ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')} indexed plan image<br>` +
      `paired params: ${escapeHtml(resource.paired_entry_index ?? '-')}, unique palette indices ${escapeHtml(resource.unique_palette_indices ?? '-')}<br>` +
      `selection: ${escapeHtml(selection)}<br>` +
      `render path: ${escapeHtml(variant?.render_path || resource.source_provenance || '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'holomap_plan_view_params') {
    const variant = resource.plan_variant;
    const selection = variant ? `variant ${variant.variant_index}, island ${variant.selected_island}, ${variant.selection_condition}` : '-';
    return `holomap: ${escapeHtml(resource.holomap_name || '-')}, paired image ${escapeHtml(resource.paired_entry_index ?? '-')}<br>` +
      `selection: ${escapeHtml(selection)}<br>` +
      `fields: ${escapeHtml(JSON.stringify(resource.fields || {}))}<br>` +
      `render path: ${escapeHtml(variant?.render_path || resource.source_provenance || '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'bkg_header') {
    return `ranges: GRI ${escapeHtml(resource.fields?.gri_start ?? '-')}..${escapeHtml((resource.fields?.grm_start ?? 0) - 1)}, ` +
      `GRM ${escapeHtml(resource.fields?.grm_start ?? '-')}..${escapeHtml((resource.fields?.bll_start ?? 0) - 1)}, ` +
      `BLL ${escapeHtml(resource.fields?.bll_start ?? '-')}..${escapeHtml((resource.fields?.brk_start ?? 0) - 1)}, ` +
      `BRK ${escapeHtml(resource.fields?.brk_start ?? '-')}..${escapeHtml((resource.fields?.cube_map_entry_index ?? 0) - 1)}<br>` +
      `cube map entry: ${escapeHtml(resource.fields?.cube_map_entry_index ?? '-')}, forbidden brick ${escapeHtml(resource.fields?.forbiden_brick ?? '-')}<br>` +
      `max sizes: GRI ${escapeHtml(resource.fields?.max_size_gri ?? '-')}, BLL ${escapeHtml(resource.fields?.max_size_bll ?? '-')}, brick cube ${escapeHtml(resource.fields?.max_size_brick_cube ?? '-')}, mask ${escapeHtml(resource.fields?.max_size_mask_brick_cube ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'bkg_grid_map') {
    const cellRows = (resource.sampled_occupied_cells || []).slice(0, 10).map((cell) =>
      `<div class="unknown-descriptor">` +
      `<span>column ${escapeHtml(cell.column)} xyz ${escapeHtml(cell.x)},${escapeHtml(cell.y)},${escapeHtml(cell.z)}</span>` +
      `<span>block ${escapeHtml(cell.block_ref)} slot ${escapeHtml(cell.cell_slot)}</span>` +
      `<span>BLL ${escapeHtml(cell.resolved_bll_entry ?? '-')}</span>` +
      `<span>valid ${escapeHtml(cell.block_ref_valid ?? '-')} / ${escapeHtml(cell.cell_slot_valid ?? '-')}</span>` +
      `</div>`,
    ).join('');
    const cellTable = cellRows ? `<div class="unknown-descriptors">${cellRows}</div>` : '';
    return `grid: ${escapeHtml(resource.bkg_relative_index ?? '-')}, BLL ${escapeHtml(resource.fields?.resolved_bll_entry ?? '-')}, GRM ${escapeHtml(resource.fields?.resolved_grm_entry ?? '-')}<br>` +
      `columns: ${escapeHtml(resource.record_count ?? '-')}, offset table ${escapeHtml(resource.offset_table_bytes ?? '-')} bytes, stream ${escapeHtml(resource.fields?.column_stream_bytes ?? '-')} bytes<br>` +
      `used blocks: ${escapeHtml(resource.fields?.used_block_count ?? '-')}, sample ${escapeHtml((resource.sampled_block_indices || []).join(', '))}<br>` +
      `composition: ${escapeHtml(resource.fields?.active_columns ?? '-')} active columns, ${escapeHtml(resource.fields?.nonzero_cells ?? '-')} occupied block cells, ${escapeHtml(resource.fields?.transparent_code_cells ?? '-')} transparent code cells, ${escapeHtml(resource.fields?.unique_column_block_refs ?? '-')} unique block refs<br>` +
      `composition links: BLL found ${escapeHtml(resource.fields?.composition_bll_link_found ?? '-')}, invalid blocks ${escapeHtml(resource.fields?.composition_invalid_block_ref_count ?? '-')}, invalid sampled slots ${escapeHtml(resource.fields?.composition_invalid_sampled_cell_slot_count ?? '-')}<br>` +
      `column runs: ${escapeHtml(formatCounts(resource.composition?.run_type_counts))}, max entities ${escapeHtml(resource.composition?.max_column_entities ?? '-')}<br>` +
      `${renderBkgCompositionPayload(resource)}` +
      `${renderBkgGridPreview(resource)}` +
      `${cellTable}provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'bkg_grm_fragment') {
    const composition = resource.composition;
    return `fragment: ${escapeHtml(resource.bkg_relative_index ?? '-')}, ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')}x${escapeHtml(resource.depth ?? '-')} cells<br>` +
      `records: ${escapeHtml(resource.record_count ?? '-')}, record bytes ${escapeHtml(resource.record_bytes ?? '-')}<br>` +
      `composition: ${escapeHtml(composition?.occupied_block_cells ?? '-')} occupied, ${escapeHtml(composition?.transparent_code_cells ?? '-')} transparent-code, ${escapeHtml(composition?.unique_block_ref_count ?? '-')} unique block refs<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'bkg_block_table') {
    const rows = (resource.sampled_records || []).slice(0, 10).map((record) =>
      `<div class="unknown-descriptor">` +
      `<span>block ${escapeHtml(record.index)}</span>` +
      `<span>${escapeHtml(record.dx ?? '-')}x${escapeHtml(record.dy ?? '-')}x${escapeHtml(record.dz ?? '-')}</span>` +
      `<span>${escapeHtml(record.cell_count ?? '-')} cells</span>` +
      `<span>${escapeHtml(record.nonzero_brick_refs ?? '-')} brick refs, ${escapeHtml(record.unique_brick_refs ?? '-')} unique, max ${escapeHtml(record.max_brick_ref ?? '-')}</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    const cellRows = (resource.sampled_cell_refs || []).slice(0, 12).map((cell) =>
      `<div class="unknown-descriptor">` +
      `<span>block ${escapeHtml(cell.block)} cell ${escapeHtml(cell.cell)}</span>` +
      `<span>xyz ${escapeHtml(cell.x)},${escapeHtml(cell.y)},${escapeHtml(cell.z)}</span>` +
      `<span>brick ref ${escapeHtml(cell.brick_ref)} -> BRK ${escapeHtml(cell.resolved_brk_entry)}</span>` +
      `<span>col ${escapeHtml(cell.collision)} code ${escapeHtml(cell.code)} raw ${escapeHtml(cell.code_raw)}</span>` +
      `</div>`,
    ).join('');
    const cellTable = cellRows ? `<div class="unknown-descriptors">${cellRows}</div>` : '';
    return `blocks: ${escapeHtml(resource.record_count ?? '-')}, offset table ${escapeHtml(resource.offset_table_bytes ?? '-')} bytes<br>` +
      `max cells: ${escapeHtml(resource.fields?.max_cell_count ?? '-')}, brick refs ${escapeHtml(resource.fields?.nonzero_cell_refs ?? '-')} cells / ${escapeHtml(resource.fields?.unique_brick_ref_count ?? '-')} unique<br>` +
      `BRK entry span: ${escapeHtml(resource.fields?.min_resolved_brk_entry ?? '-')}..${escapeHtml(resource.fields?.max_resolved_brk_entry ?? '-')}, invalid ${escapeHtml(resource.fields?.invalid_brick_ref_count ?? '-')}, forbidden ${escapeHtml(resource.fields?.forbidden_brick_ref_count ?? '-')}<br>` +
      `${table}${cellTable}provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'bkg_brick_graphic') {
    return `brick graph: ${escapeHtml(resource.bkg_relative_index ?? '-')}, ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')}, hot ${escapeHtml(resource.offset_x ?? '-')},${escapeHtml(resource.offset_y ?? '-')}<br>` +
      `pixels: ${escapeHtml(resource.opaque_pixels ?? '-')} opaque, ${escapeHtml(resource.transparent_pixels ?? '-')} transparent, ${escapeHtml(resource.color_count ?? '-')} palette indices<br>` +
      `commands: ${escapeHtml(resource.encoded_bytes_consumed ?? '-')} consumed of ${escapeHtml(resource.fields?.encoded_bytes ?? '-')} bytes, max row runs ${escapeHtml(resource.max_row_run_count ?? '-')}, run types ${escapeHtml(formatCounts(resource.run_type_counts))}<br>` +
      `preview: ${escapeHtml(resource.preview_hex || '')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'bkg_cube_map') {
    const rows = (resource.sampled_records || []).slice(0, 12).map((record) =>
      `<div class="unknown-descriptor">` +
      `<span>cube ${escapeHtml(record.index)}</span>` +
      `<span>type ${escapeHtml(record.type ?? '-')} num ${escapeHtml(record.num ?? '-')}</span>` +
      `<span>GRI ${escapeHtml(record.resolved_gri_entry ?? '-')}</span>` +
      `<span>BLL ${escapeHtml(record.resolved_bll_entry ?? '-')} GRM ${escapeHtml(record.resolved_grm_entry ?? '-')}</span>` +
      `<span>used blocks ${escapeHtml(record.used_block_count ?? '-')}</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    return `records: ${escapeHtml(resource.record_count ?? '-')}, record bytes ${escapeHtml(resource.record_bytes ?? '-')}<br>` +
      `grid links: ${escapeHtml(resource.fields?.linked_grid_records ?? '-')} linked, ${escapeHtml(resource.fields?.missing_grid_records ?? '-')} missing${resource.missing_grid_entries?.length ? ` (${escapeHtml(resource.missing_grid_entries.join(', '))})` : ''}<br>` +
      `type counts: ${escapeHtml(formatCounts(resource.type_counts))}<br>` +
      `${table}` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'text_order_table') {
    return `language/file: ${escapeHtml(resource.language || '-')}/${escapeHtml(resource.text_file_name || '-')}, messages ${escapeHtml(resource.record_count ?? '-')}<br>` +
      `paired text bank: ${escapeHtml(resource.paired_entry_index ?? '-')}, id range ${escapeHtml(resource.fields?.min_message_id ?? '-')}..${escapeHtml(resource.fields?.max_message_id ?? '-')}<br>` +
      `sample ids: ${escapeHtml((resource.sampled_message_ids || []).slice(0, 24).join(', '))}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'text_payload_bank') {
    const rows = (resource.sampled_records || []).slice(0, 10).map((record) =>
      `<div class="unknown-descriptor">` +
      `<span>record ${escapeHtml(record.index)}</span>` +
      `<span>flag ${escapeHtml(record.flag ?? '-')}</span>` +
      `<span>offset ${escapeHtml(record.offset ?? '-')}, bytes ${escapeHtml(record.byte_length ?? '-')}</span>` +
      `<span>${escapeHtml(record.preview || '')}</span>` +
      `</div>`,
    ).join('');
    const table = rows ? `<div class="unknown-descriptors">${rows}</div>` : '';
    return `language/file: ${escapeHtml(resource.language || '-')}/${escapeHtml(resource.text_file_name || '-')}, text records ${escapeHtml(resource.record_count ?? '-')}<br>` +
      `paired order table: ${escapeHtml(resource.paired_entry_index ?? '-')}, offset table ${escapeHtml(resource.offset_table_bytes ?? '-')} bytes, codepage ${escapeHtml(resource.preview_codepage || '-')}<br>` +
      `flag counts: ${escapeHtml(formatCounts(resource.type_counts))}, page breaks ${escapeHtml(resource.fields?.page_break_markers ?? '-')}<br>` +
      `${table}provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'sample_wave_audio') {
    const header = resource.resource_header || {};
    const chunks = (resource.chunk_ids || []).join(', ');
    return `runtime sample: ${escapeHtml(resource.sample_runtime_index ?? '-')}, format ${escapeHtml(resource.audio_format || '-')}, ` +
      `${escapeHtml(resource.fields?.channels ?? '-')}ch ${escapeHtml(resource.fields?.bits_per_sample ?? '-')}-bit ${escapeHtml(resource.fields?.sample_rate ?? '-')}Hz<br>` +
      `frames: ${escapeHtml(resource.sample_frames ?? '-')}, duration ${escapeHtml(resource.duration_ms ?? '-')} ms, data ${escapeHtml(resource.fields?.data_bytes ?? '-')} bytes<br>` +
      `HQR resource: method ${escapeHtml(header.compress_method ?? '-')}, decoded ${escapeHtml(header.size_file ?? '-')}, compressed ${escapeHtml(header.compressed_size_file ?? '-')} bytes<br>` +
      `chunks: ${escapeHtml(chunks || '-')}, block align ${escapeHtml(resource.fields?.block_align ?? '-')}, samples/block ${escapeHtml(resource.samples_per_block ?? '-')}<br>` +
      `provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'smacker_video') {
    const header = resource.resource_header || {};
    const smk = resource.header || {};
    return `runtime ACF: ${escapeHtml(resource.acf_index ?? '-')}, name ${escapeHtml(resource.acf_name || '-')}, key ${escapeHtml(resource.acf_basename || '-')}<br>` +
      `video: ${escapeHtml(resource.width ?? '-')}x${escapeHtml(resource.height ?? '-')}, ${escapeHtml(resource.frame_count ?? '-')} frames, ${escapeHtml(resource.frames_per_second ?? '-')} fps, duration ${escapeHtml(resource.duration_ms ?? '-')} ms<br>` +
      `Smacker: ${escapeHtml(String(smk.magic ?? '-'))}, flags ${escapeHtml(smk.flags ?? '-')}, tree bytes ${escapeHtml(smk.tree_size ?? '-')}<br>` +
      `HQR resource: method ${escapeHtml(header.compress_method ?? '-')}, decoded ${escapeHtml(header.size_file ?? '-')}, compressed ${escapeHtml(header.compressed_size_file ?? '-')} bytes<br>` +
      `name source: ${escapeHtml(resource.name_source || '-')}; provenance: ${escapeHtml(resource.source_provenance || '-')}<br>`;
  }
  if (resource.semantic_layout === 'acf_name_list') {
    return `names: ${escapeHtml(resource.entry_count ?? '-')}<br>` +
      `sample: ${escapeHtml((resource.sampled_names || []).join(', '))}<br>`;
  }
  if (resource.semantic_layout === 'ress_unclassified_payload') {
    return `preview: ${escapeHtml(resource.preview_hex || '')}<br>`;
  }
  return '';
}

function renderRuntimeTableInfo(resource: ResourceStats): string {
  if (!resource.runtime_table_name && !resource.runtime_buffer && !resource.runtime_purpose) return '';
  return `runtime table: ${escapeHtml(resource.runtime_table_name || '-')}, buffer ${escapeHtml(resource.runtime_buffer || '-')}<br>` +
    `purpose: ${escapeHtml(resource.runtime_purpose || '-')}<br>` +
    `provenance: ${escapeHtml(resource.source_provenance || '-')}, runtime: ${escapeHtml(resource.runtime_reference_status || '-')}<br>`;
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

function renderSceneUsages(usages: SceneAssetUsage[]): string {
  if (usages.length === 0) return '';
  const rows = usages
    .slice(0, 16)
    .map((usage) => {
      const sceneName = usage.scene_index === null ? usage.scene_asset_id : `Scene ${usage.scene_index}`;
      const position = usage.position
        ? `pos ${usage.position.x},${usage.position.y},${usage.position.z}`
        : 'pos -';
      return `<div class="unknown-descriptor">` +
        `<span>${escapeHtml(sceneName)}</span>` +
        `<span>obj ${escapeHtml(usage.object_index)} ${escapeHtml(usage.kind)}</span>` +
        `<span>${escapeHtml(sceneUsageDetail(usage))}</span>` +
        `<span>${escapeHtml(position)}</span>` +
        `</div>`;
    })
    .join('');
  const remaining = usages.length > 16 ? `<div class="asset-meta">Showing 16 of ${escapeHtml(usages.length)} scene usage refs.</div>` : '';
  return `<br>scene usage: ${escapeHtml(usages.length)} refs<br><div class="unknown-descriptors">${rows}</div>${remaining}`;
}

function sceneUsageDetail(usage: SceneAssetUsage): string {
  if (usage.kind === 'ambience_sample') {
    return `ambience slot ${usage.slot_index ?? '-'} sample ${usage.sample_id ?? usage.reference_value}; ${usage.audio_format || 'audio'} ${usage.sample_rate ?? '-'}Hz vol ${usage.volume ?? '-'}`;
  }
  if (usage.kind === 'zone_text') {
    return `${usage.language || 'text'} ${usage.text_file_name || usage.text_file_index} id ${usage.text_id ?? usage.reference_value} record ${usage.record_index ?? '-'}; ${usage.preview || ''}`;
  }
  if (usage.kind.startsWith('script_')) {
    if (usage.kind === 'script_sample') {
      return `${usage.script_kind || 'script'} sample ${usage.sample_id ?? usage.reference_value}; ${usage.audio_format || 'audio'} ${usage.sample_rate ?? '-'}Hz`;
    }
    if (usage.kind === 'script_text') {
      return `${usage.script_kind || 'script'} ${usage.language || 'text'} ${usage.text_file_name || usage.text_file_index} id ${usage.text_id ?? usage.reference_value} record ${usage.record_index ?? '-'}; ${usage.preview || ''}`;
    }
    if (usage.kind === 'script_video') {
      return `${usage.script_kind || 'script'} movie ${usage.acf_name ?? usage.reference_value}; ${usage.frame_count ?? '-'} frames`;
    }
    const baseKind = usage.kind.replace(/^script_/, '');
    const ref = `${usage.reference_key || baseKind} ${usage.reference_value ?? '-'}`;
    return `${usage.script_kind || 'script'} ${ref}; ${usage.resolution_rule || ''}`;
  }
  if (usage.kind === 'animation') {
    const label = usage.label || usage.generic_name || `generic ${usage.generic_id ?? '-'}`;
    return `${label}; file3d ${usage.file3d_index}; gen ${usage.gen_anim}`;
  }
  if (usage.kind === 'body') {
    return `body ${usage.body_index ?? '-'}; file3d ${usage.file3d_index}; gen ${usage.gen_body}`;
  }
  if (usage.kind === 'sprite') {
    if (usage.backend === 'anim3ds' && usage.anim3ds_range) {
      const range = usage.anim3ds_range;
      const name = range.name || `anim ${range.animation_number}`;
      const frames = range.start_frame === null || range.end_frame === null
        ? 'frames -'
        : `frames ${range.start_frame}..${range.end_frame}`;
      const relative = range.relative_frame === null ? '' : ` frame +${range.relative_frame}`;
      const match = range.range_matches_sprite ? '' : ' range mismatch';
      return `ANIM3DS ${name}${relative}; ${frames}; fps ${range.frames_per_second ?? range.size_s_hit ?? '-'}${match}`;
    }
    return `${usage.backend || 'sprite'} ${usage.runtime_sprite_index ?? usage.sprite}; ${usage.index_rule || usage.resolution_rule || ''}`;
  }
  if (usage.kind === 'grm_fragment') {
    return `GRM ${usage.resolved_grm_entry ?? '-'}; zone ${usage.zone_index ?? '-'} value ${usage.reference_value ?? '-'}; ${usage.resolution_rule || ''}`;
  }
  return usage.resolution_rule || '';
}

function renderSceneBackground(background: SceneStats['reconnaissance']['background']): string {
  if (!background) return '';
  const grid = background.cube_map_record_found
    ? `cube ${escapeHtml(background.runtime_cube)} -> GRI ${escapeHtml(background.resolved_gri_entry ?? '-')}, BLL ${escapeHtml(background.resolved_bll_entry ?? '-')}, GRM ${escapeHtml(background.resolved_grm_entry ?? '-')}, used blocks ${escapeHtml(background.used_block_count ?? '-')}`
    : `cube ${escapeHtml(background.runtime_cube)} has no decoded TabAllCube record`;
  const palette = background.palette;
  const alternate = palette?.alternate_palette_entry !== undefined
    ? `; alternate ${escapeHtml(palette.alternate_palette_entry)} ${escapeHtml(palette.alternate_palette_name || '')} when ${escapeHtml(palette.alternate_condition || 'runtime condition')}`
    : '';
  const paletteText = palette
    ? `palette ${escapeHtml(palette.resolved_palette_entry ?? '-')} ${escapeHtml(palette.resolved_palette_name || '')} (${escapeHtml(palette.confidence)})${alternate}`
    : 'palette unresolved';
  return `background: ${grid}; ${paletteText}<br>`;
}

function renderSceneEnvironment(
  world: SceneStats['reconnaissance']['world'],
  ambience: SceneStats['reconnaissance']['ambience'],
): string {
  if (!world && !ambience) return '';
  const env = world?.runtime_environment;
  const audio = ambience?.runtime_audio_lighting;
  const parts: string[] = [];
  if (world) {
    parts.push(
      `environment: shadow ${escapeHtml(world.shadow_level)}, labyrinth ${escapeHtml(world.labyrinth_mode)}, post-cube byte ${escapeHtml(world.unknown_world_byte)}; ${escapeHtml(env?.post_cube_mode_byte_status || '-')}`,
    );
  }
  if (ambience) {
    parts.push(
      `ambience: light ${escapeHtml(ambience.alpha_light)},${escapeHtml(ambience.beta_light)}, cube jingle ${escapeHtml(ambience.cube_jingle)}; ${escapeHtml(audio?.ambient_timer_rule || '-')}`,
    );
  }
  return parts.map((part) => `${part}<br>`).join('');
}

function renderSceneSampleMissing(recon: SceneStats['reconnaissance']): string {
  const missing = recon?.missing_sample_links || [];
  if (!missing.length) return '<br>';
  const statusCounts = missing.reduce<Record<string, number>>((counts, link) => {
    const status = typeof link.status === 'string' ? link.status : 'unknown';
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {});
  const examples = missing
    .slice(0, 4)
    .map((link) => {
      const sampleId = typeof link.sample_id === 'number' ? link.sample_id : '-';
      const status = typeof link.status === 'string' ? link.status : 'unknown';
      return `${sampleId}:${status}`;
    })
    .join(', ');
  return `; missing reasons ${escapeHtml(formatCounts(statusCounts))}; examples ${escapeHtml(examples)}<br>`;
}

function renderBkgCompositionPayload(resource: ResourceStats): string {
  const payload = resource.composition_payload;
  if (!payload) return '';
  const dims = payload.cube_dimensions;
  return `full composition payload: ${escapeHtml(payload.cell_count)} cells (${escapeHtml(dims.x)}x${escapeHtml(dims.y)}x${escapeHtml(dims.z)}), ` +
    `${escapeHtml(payload.occupied_block_cells)} occupied, ${escapeHtml(payload.transparent_code_cells)} transparent-code; order ${escapeHtml(payload.cell_order)}<br>`;
}

function renderBkgGridPreview(resource: ResourceStats): string {
  const preview = resource.preview;
  if (!preview) return '';
  return `background preview: ${escapeHtml(preview.width)}x${escapeHtml(preview.height)}, ` +
    `${escapeHtml(preview.drawn_cells)} cells, ${escapeHtml(preview.drawn_pixels)} pixels, ${escapeHtml(preview.unique_bricks_loaded)} BRKs loaded; ` +
    `missing ${escapeHtml(preview.missing_bricks)}, forbidden skipped ${escapeHtml(preview.skipped_forbidden)}<br>`;
}

function renderSceneMechanics(recon: SceneStats['reconnaissance']): string {
  const rows: string[] = [];
  const scriptBehavior = formatCounts(recon.script_behavior_counts);
  if (scriptBehavior) rows.push(`<div class="asset-meta">Script behavior: ${escapeHtml(scriptBehavior)}</div>`);
  const frameContract = recon.scene_frame_render_contract;
  if (frameContract) {
    const runtimeSources = frameContract.runtime_dynamic_sources.slice(0, 4).join(', ');
    const previewLimits = frameContract.preview_limitations.slice(0, 2).join(' ');
    rows.push(
      `<div class="asset-meta">Scene frame contract: ${escapeHtml(frameContract.scene_object_records)} HQR scene objects enter the classic draw pass; runtime dynamic sources ${escapeHtml(runtimeSources || '-')}; preview limit ${escapeHtml(previewLimits || '-')}</div>`,
    );
    const dynamicDetails = (frameContract.runtime_dynamic_source_details || []).slice(0, 4).map((source) =>
      `<div class="unknown-descriptor">` +
      `<span>${escapeHtml(source.name)}: ${escapeHtml(source.runtime_owner)}</span>` +
      `<span>${escapeHtml(source.insertion_stage)}</span>` +
      `<span>${escapeHtml(source.sorted_tree_types.join(', ') || 'direct draw')}</span>` +
      `<span>${escapeHtml(source.asset_backing)}</span>` +
      `<span>${escapeHtml(source.preview_status)}</span>` +
      `</div>`,
    ).join('');
    if (dynamicDetails) {
      rows.push(`<div class="unknown-descriptors">${dynamicDetails}</div>`);
    }
  }
  const objectRenderTypes = formatCounts(recon.object_render_type_counts);
  const objectRenderPipeline = formatCounts(recon.object_render_pipeline_counts);
  const objectRenderContract = formatCounts(recon.object_render_contract_counts);
  const objectRedrawMethods = formatCounts(recon.object_redraw_method_counts);
  const objectMoves = formatCounts(recon.object_move_counts);
  const objectCollisions = formatCounts(recon.object_collision_counts);
  const objectSrotConversions = formatCounts(recon.object_srot_conversion_counts);
  const objectCombat = formatCounts(recon.object_combat_counts);
  const objectFlags = formatCounts(recon.object_flag_counts);
  const objectOptions = formatCounts(recon.object_option_flag_counts);
  const objectMovementRefs = formatCounts(recon.object_movement_reference_counts);
  const objectMovementMissingRefs = formatCounts(recon.object_movement_missing_reference_counts);
  const objectMovementState = formatCounts(recon.object_movement_state_counts);
  if (objectRenderTypes || objectMoves || objectFlags || objectOptions) {
    rows.push(
      `<div class="asset-meta">Object runtime: render ${escapeHtml(objectRenderTypes || '-')}; moves ${escapeHtml(objectMoves || '-')}; flags ${escapeHtml(objectFlags || '-')}; options ${escapeHtml(objectOptions || '-')}</div>`,
    );
  }
  if (objectRenderPipeline) {
    rows.push(
      `<div class="asset-meta">Object render pipeline: ${escapeHtml(objectRenderPipeline)}</div>`,
    );
  }
  if (objectRenderContract) {
    rows.push(
      `<div class="asset-meta">Object render contract: ${escapeHtml(objectRenderContract)}</div>`,
    );
  }
  if (objectRedrawMethods) {
    rows.push(
      `<div class="asset-meta">Object redraw methods: ${escapeHtml(objectRedrawMethods)}</div>`,
    );
  }
  if (objectMovementRefs || objectMovementState || objectMovementMissingRefs) {
    rows.push(
      `<div class="asset-meta">Object movement info: refs ${escapeHtml(objectMovementRefs || '-')}; state ${escapeHtml(objectMovementState || '-')}; missing refs ${escapeHtml(objectMovementMissingRefs || '-')}</div>`,
    );
  }
  if (objectCollisions || objectSrotConversions || objectCombat) {
    rows.push(
      `<div class="asset-meta">Object collision/rotation/combat: collisions ${escapeHtml(objectCollisions || '-')}; srot ${escapeHtml(objectSrotConversions || '-')}; combat ${escapeHtml(objectCombat || '-')}</div>`,
    );
  }
  const scriptRuntimeState = formatCounts(recon.script_runtime_state_counts);
  const scriptRuntimeInstructionState = formatCounts(recon.script_runtime_instruction_state_counts);
  if (scriptRuntimeState || scriptRuntimeInstructionState) {
    rows.push(
      `<div class="asset-meta">Script runtime state: ${escapeHtml(scriptRuntimeState || '-')}; instruction fields: ${escapeHtml(scriptRuntimeInstructionState || '-')}</div>`,
    );
  }
  const scriptExecutionContracts = formatCounts(recon.script_execution_contract_counts);
  if (scriptExecutionContracts) {
    rows.push(`<div class="asset-meta">Script execution contracts: ${escapeHtml(scriptExecutionContracts)}</div>`);
  }
  const scriptConditionFunctions = formatCounts(recon.script_condition_function_counts);
  const scriptConditionReturns = formatCounts(recon.script_condition_return_type_counts);
  const scriptConditionComparators = formatCounts(recon.script_condition_comparator_counts);
  if (scriptConditionFunctions || scriptConditionReturns || scriptConditionComparators) {
    rows.push(
      `<div class="asset-meta">Script condition functions: ${escapeHtml(scriptConditionFunctions || '-')}; returns ${escapeHtml(scriptConditionReturns || '-')}; comparators ${escapeHtml(scriptConditionComparators || '-')}</div>`,
    );
  }
  const scriptSkippedBytes = formatCounts(recon.script_skipped_byte_counts);
  if (scriptSkippedBytes) {
    rows.push(`<div class="asset-meta">Script skipped byte islands: ${escapeHtml(scriptSkippedBytes)}</div>`);
  }
  const zoneCounts = formatCounts(recon.zone_type_counts);
  if (zoneCounts) rows.push(`<div class="asset-meta">Zone types: ${escapeHtml(zoneCounts)}</div>`);
  const zoneEffects = formatCounts(recon.zone_effect_counts);
  if (zoneEffects) rows.push(`<div class="asset-meta">Zone effects: ${escapeHtml(zoneEffects)}</div>`);
  const zoneContracts = formatCounts(recon.zone_runtime_contract_counts);
  if (zoneContracts) rows.push(`<div class="asset-meta">Zone contracts: ${escapeHtml(zoneContracts)}</div>`);
  const messageCameraCounts = formatCounts(recon.message_camera_link_counts);
  if (messageCameraCounts) {
    rows.push(`<div class="asset-meta">Message camera links: ${escapeHtml(messageCameraCounts)}</div>`);
  }
  rows.push(
    ...(recon.message_camera_links || []).slice(0, 8).map((link) => {
      const target = link.target_available
        ? `camera zone ${link.target_zone_index ?? '-'} value ${link.target_zone_value ?? '-'}`
        : `missing camera Num ${link.associated_camera_zone ?? '-'}`;
      return `<div class="unknown-descriptor">` +
        `<span>message zone ${escapeHtml(link.zone_index ?? '-')} id ${escapeHtml(link.message_id ?? '-')}</span>` +
        `<span>${escapeHtml(target)}</span>` +
        `<span>${escapeHtml(link.source_provenance ?? '')}</span>` +
        `</div>`;
    }),
  );
  const grmCounts = formatCounts(recon.grm_fragment_link_counts);
  if (grmCounts) rows.push(`<div class="asset-meta">GRM links: ${escapeHtml(grmCounts)}</div>`);
  rows.push(
    ...(recon.grm_fragment_links || []).slice(0, 8).map((link) => {
      const start = link.target_cell_start;
      const dims = link.fragment_dimensions;
      return `<div class="unknown-descriptor">` +
        `<span>GRM zone ${escapeHtml(link.zone_index)} value ${escapeHtml(link.zone_value)}</span>` +
        `<span>Info0 ${escapeHtml(link.grm_index)} -> LBA_BKG ${escapeHtml(link.resolved_grm_entry ?? '-')}</span>` +
        `<span>start ${escapeHtml(start.x)},${escapeHtml(start.y)},${escapeHtml(start.z)} dims ${escapeHtml(dims.x ?? '-')},${escapeHtml(dims.y ?? '-')},${escapeHtml(dims.z ?? '-')}</span>` +
        `<span>${escapeHtml(link.asset_available ? link.asset_id || 'asset linked' : 'missing fragment')}</span>` +
        `<span>match ${escapeHtml(link.dimensions_match_zone_bounds)}, bounds ${escapeHtml(!link.out_of_cube_bounds)}, y spill ${escapeHtml(link.column_y_overflow_cells)}</span>` +
        `</div>`;
    }),
  );
  if ((recon.grm_fragment_links || []).length > 8) {
    rows.push(`<div class="asset-meta">Showing 8 of ${escapeHtml((recon.grm_fragment_links || []).length)} GRM fragment links.</div>`);
  }
  rows.push(
    ...(recon.sampled_zones || []).slice(0, 12).map(
      (zone) => {
        const rules = formatEnabledRules(zone.load_rules);
        const runtime = zone.runtime
          ? `<span>${escapeHtml(zone.runtime.effect)} via ${escapeHtml(zone.runtime.trigger)}</span>` +
            `<span>${escapeHtml(renderZoneRuntimeFields(zone.runtime.fields))}</span>` +
            `<span>post-load ${escapeHtml(renderZoneRuntimeFields(zone.runtime.load_state || {}))}</span>` +
            `${zone.runtime.camera_application ? `<span>camera ${escapeHtml(renderZoneRuntimeFields(zone.runtime.camera_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.change_cube_application ? `<span>change-cube ${escapeHtml(renderZoneRuntimeFields(zone.runtime.change_cube_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.message_application ? `<span>message ${escapeHtml(renderZoneRuntimeFields(zone.runtime.message_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.bonus_application ? `<span>bonus ${escapeHtml(renderZoneRuntimeFields(zone.runtime.bonus_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.hit_application ? `<span>hit ${escapeHtml(renderZoneRuntimeFields(zone.runtime.hit_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.ladder_application ? `<span>ladder ${escapeHtml(renderZoneRuntimeFields(zone.runtime.ladder_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.escalator_application ? `<span>escalator ${escapeHtml(renderZoneRuntimeFields(zone.runtime.escalator_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.rail_application ? `<span>rail ${escapeHtml(renderZoneRuntimeFields(zone.runtime.rail_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.grm_application ? `<span>grm ${escapeHtml(renderZoneRuntimeFields(zone.runtime.grm_application as Record<string, unknown>))}</span>` : ''}` +
            `${zone.runtime.scenario_application ? `<span>scenario ${escapeHtml(renderZoneRuntimeFields(zone.runtime.scenario_application as Record<string, unknown>))}</span>` : ''}` +
            `<span>${escapeHtml(zone.runtime.script_controls.map((control) => control.opcode).join(', ') || zone.runtime.runtime_readers.join(', ') || zone.runtime.source)}</span>`
          : '';
        return `<div class="unknown-descriptor">` +
          `<span>zone ${escapeHtml(zone.index)}</span>` +
          `<span>${escapeHtml(zone.type_name)} value ${escapeHtml(zone.value)}</span>` +
          `<span>${escapeHtml(zone.start.x)},${escapeHtml(zone.start.y)},${escapeHtml(zone.start.z)} to ${escapeHtml(zone.end.x)},${escapeHtml(zone.end.y)},${escapeHtml(zone.end.z)}</span>` +
          `<span>info ${escapeHtml(zone.info.join(','))}</span>` +
          `<span>${escapeHtml(rules || 'no load rule')}</span>` +
          runtime +
          `</div>`;
      },
    ),
  );
  if ((recon.sampled_zones || []).length > 12) {
    rows.push(`<div class="asset-meta">Showing 12 of ${escapeHtml((recon.sampled_zones || []).length)} parsed zones.</div>`);
  }

  rows.push(
    ...(recon.sampled_tracks || []).slice(0, 8).map(
      (track) =>
        `<div class="unknown-descriptor">` +
        `<span>waypoint ${escapeHtml(track.index)}</span>` +
        `<span>pos ${escapeHtml(track.position.x)},${escapeHtml(track.position.y)},${escapeHtml(track.position.z)}</span>` +
        `<span>offset ${escapeHtml(track.offset)}</span>` +
        `</div>`,
    ),
  );
  if ((recon.sampled_tracks || []).length > 8) {
    rows.push(`<div class="asset-meta">Showing 8 of ${escapeHtml((recon.sampled_tracks || []).length)} parsed waypoints.</div>`);
  }

  const patchSizes = formatCounts(recon.patch_size_counts);
  const patchTargets = formatCounts(recon.patch_target_counts);
  const patchInstructions = formatCounts(recon.patch_instruction_counts);
  const patchInstructionBytes = formatCounts(recon.patch_instruction_byte_counts);
  const patchFields = formatCounts(recon.patch_field_counts);
  const patchFieldSources = formatCounts(recon.patch_field_source_counts);
  const patchInstructionFields = formatCounts(recon.patch_instruction_field_counts);
  if (patchSizes || patchTargets || patchInstructions || patchInstructionBytes || patchFields || patchFieldSources || patchInstructionFields) {
    rows.push(
      `<div class="asset-meta">Patch sizes: ${escapeHtml(patchSizes || '-')}; targets: ${escapeHtml(patchTargets || '-')}; instructions: ${escapeHtml(patchInstructions || '-')}; bytes: ${escapeHtml(patchInstructionBytes || '-')}; fields: ${escapeHtml(patchFields || '-')}; instruction fields: ${escapeHtml(patchInstructionFields || '-')}; sources: ${escapeHtml(patchFieldSources || '-')}</div>`,
    );
  }
  rows.push(
    ...(recon.sampled_patches || []).slice(0, 16).map(
      (patch) => {
        const instruction = patch.target.instruction_found
          ? `${patch.target.instruction_opcode} +${patch.target.instruction_relative_offset}${patch.target.hits_opcode_byte ? ' opcode' : ` operand +${patch.target.operand_relative_offset ?? '-'}`}`
          : 'instruction unresolved';
        const field = patch.target.patched_field
          ? `field ${patch.target.patched_field} +${patch.target.patched_field_byte_offset ?? 0}/${patch.target.patched_field_size ?? '-'}`
          : 'field unresolved';
        return `<div class="unknown-descriptor">` +
        `<span>patch ${escapeHtml(patch.index)}</span>` +
        `<span>size ${escapeHtml(patch.size)}, target offset ${escapeHtml(patch.target_offset)}</span>` +
        `<span>${escapeHtml(patch.target.kind)} ${escapeHtml(patch.target.owner || 'unknown')}</span>` +
        `<span>script +${escapeHtml(patch.target.script_relative_offset ?? '-')}</span>` +
        `<span>${escapeHtml(instruction)}</span>` +
        `<span>${escapeHtml(field)}</span>` +
        `</div>`;
      },
    ),
  );
  if ((recon.sampled_patches || []).length > 16) {
    rows.push(`<div class="asset-meta">Showing 16 of ${escapeHtml((recon.sampled_patches || []).length)} parsed patches.</div>`);
  }

  return rows.length ? `<div class="unknown-descriptors">${rows.join('')}</div>` : '';
}

function renderSceneObjects(objects: NonNullable<SceneStats['reconnaissance']['sampled_objects']>, totalCount?: number): string {
  if (objects.length === 0) return '';
  const rows = objects
    .slice(0, 24)
    .map(
      (object) => {
        const link = sceneObjectLinkText(object);
        const runtime = sceneObjectRuntimeText(object);
        return `<div class="unknown-descriptor">` +
        `<span>obj ${escapeHtml(object.index)}</span>` +
        `<span>body ${escapeHtml(object.gen_body)}, anim ${escapeHtml(object.gen_anim)}, sprite ${escapeHtml(object.sprite)}</span>` +
        `<span>file3d ${escapeHtml(object.file3d_index)}</span>` +
        `<span>pos ${escapeHtml(object.position.x)},${escapeHtml(object.position.y)},${escapeHtml(object.position.z)}</span>` +
        `<span>${escapeHtml(runtime)}</span>` +
        `<span>scripts ${escapeHtml(object.track_script_bytes)}/${escapeHtml(object.life_script_bytes)} bytes; ` +
        `${escapeHtml(sceneScriptCompact(object.track_script_analysis))}; ${escapeHtml(sceneScriptCompact(object.life_script_analysis))}${link}</span>` +
        `</div>`;
      },
    )
    .join('');
  const total = totalCount ?? objects.length;
  const remaining = total > objects.length ? `<div class="asset-meta">Showing ${escapeHtml(objects.length)} of ${escapeHtml(total)} parsed scene objects.</div>` : '';
  return `<div class="unknown-descriptors">${rows}</div>${remaining}`;
}

function sceneObjectRuntimeText(object: NonNullable<SceneStats['reconnaissance']['sampled_objects']>[number]): string {
  const runtime = object.runtime;
  if (!runtime) return 'runtime unknown';
  const flags = runtime.flags.slice(0, 4).join(',');
  const flagSuffix = runtime.flags.length > 4 ? ` +${runtime.flags.length - 4}` : '';
  const options = runtime.option_flags.length ? ` options ${runtime.option_flags.join(',')}` : '';
  const movement = runtime.movement;
  const combat = runtime.combat;
  const pipeline = runtime.render_pipeline;
  const pipelineFlags = pipeline?.effect_flags?.slice(0, 3).join(',');
  const pipelineSuffix = pipelineFlags
    ? `; pipeline ${pipelineFlags}${(pipeline?.effect_flags?.length || 0) > 3 ? ` +${(pipeline?.effect_flags?.length || 0) - 3}` : ''}`
    : '';
  const contract = pipeline?.contract_steps?.slice(0, 2).join(',');
  const contractSuffix = contract
    ? `; contract ${contract}${(pipeline?.contract_steps?.length || 0) > 2 ? ` +${(pipeline?.contract_steps?.length || 0) - 2}` : ''}`
    : '';
  const redraw = pipeline?.redraw_contract
    ? `; redraw ${pipeline.redraw_contract.method}${pipeline.redraw_contract.moving_box ? ' moving-box' : ''}`
    : '';
  const refs = (movement.references || [])
    .slice(0, 2)
    .map((ref) => `${ref.field} ${ref.role}=${ref.value}${ref.target_found ? '' : ' missing'}`)
    .join(', ');
  const refSuffix = refs ? `; refs ${refs}` : '';
  const state = (movement.state_fields || [])
    .slice(0, 3)
    .map((field) => `${field.field} ${field.role}`)
    .join(', ');
  const stateSuffix = state ? `; state ${state}` : '';
  return `${runtime.render_type} ${movement.mode_name} beta ${movement.initial_beta} srot ${movement.srot_scene_value}->${movement.srot_runtime_value}; hp ${combat.life_points} hit ${combat.hit_force}; flags ${flags || '-'}${flagSuffix}${pipelineSuffix}${contractSuffix}${redraw}${options}${refSuffix}${stateSuffix}`;
}

function sceneObjectLinkText(object: NonNullable<SceneStats['reconnaissance']['sampled_objects']>[number]): string {
  const links = object.links;
  const parts: string[] = [];
  if (links?.body?.asset_id) parts.push(`body ${links.body.asset_id}${links.body.asset_available ? '' : ' missing'}`);
  if (links?.animation?.asset_id) parts.push(`anim ${links.animation.asset_id}${links.animation.asset_available ? '' : ' missing'}`);
  if (links?.sprite?.asset_id) {
    const range = links.sprite.anim3ds_range;
    const suffix = range?.name ? ` ${range.name}` : '';
    parts.push(`sprite ${links.sprite.asset_id}${suffix}${links.sprite.asset_available ? '' : ' missing'}`);
  }
  const scriptLinks = [
    ...(object.track_script_analysis?.asset_links || []),
    ...(object.life_script_analysis?.asset_links || []),
  ];
  if (scriptLinks.length) {
    const scriptTargets = scriptLinks
      .slice(0, 4)
      .map((link) => `${link.kind} ${link.asset_id || link.reference_value}${link.asset_available === false ? ' missing' : ''}`);
    const suffix = scriptLinks.length > scriptTargets.length ? ` +${scriptLinks.length - scriptTargets.length}` : '';
    parts.push(`script ${scriptTargets.join(', ')}${suffix}`);
  }
  const localLinks = [
    ...(object.track_script_analysis?.local_links || []),
    ...(object.life_script_analysis?.local_links || []),
  ];
  if (localLinks.length) {
    const localTargets = localLinks
      .slice(0, 4)
      .map((link) => `${link.kind} ${link.object_index ?? link.waypoint_index ?? link.zone_index ?? link.reference_value}`);
    const suffix = localLinks.length > localTargets.length ? ` +${localLinks.length - localTargets.length}` : '';
    parts.push(`local ${localTargets.join(', ')}${suffix}`);
  }
  const crossLinks = [
    ...(object.track_script_analysis?.cross_script_links || []),
    ...(object.life_script_analysis?.cross_script_links || []),
  ];
  if (crossLinks.length) {
    const crossTargets = crossLinks
      .slice(0, 4)
      .map((link) => `${link.target_owner} ${link.target_script_kind}@${link.target_offset}${link.target_found ? '' : ' missing'}`);
    const suffix = crossLinks.length > crossTargets.length ? ` +${crossLinks.length - crossTargets.length}` : '';
    parts.push(`cross ${crossTargets.join(', ')}${suffix}`);
  }
  return parts.length ? ` | ${parts.map(escapeHtml).join(', ')}` : '';
}

function renderSceneScriptSummary(label: string, script?: SceneScriptAnalysis): string {
  if (!script) return '';
  const opcodes = script.unique_opcodes.slice(0, 8).map((opcode) => opcode.mnemonic).join(', ') || '-';
  const behavior = formatScriptBehavior(script);
  const refs = sceneScriptReferences(script);
  const links = sceneScriptAssetLinks(script);
  const localLinks = sceneScriptLocalLinks(script);
  const crossLinks = sceneScriptCrossLinks(script);
  const flowLinks = sceneScriptControlFlowLinks(script);
  const runtimeState = sceneScriptRuntimeState(script);
  const operands = sceneScriptSemanticPreview(script);
  return `${escapeHtml(label)} script: ${escapeHtml(script.status)}, ${escapeHtml(script.instruction_count)} commands, ` +
    `${escapeHtml(script.decoded_bytes)}/${escapeHtml(script.byte_length)} bytes, opcodes ${escapeHtml(opcodes)}, behavior ${escapeHtml(behavior)}${refs}${links}${localLinks}${crossLinks}${flowLinks}${runtimeState}${operands}<br>`;
}

function sceneScriptCompact(script?: SceneScriptAnalysis): string {
  if (!script) return 'script unavailable';
  const opcodes = script.unique_opcodes.slice(0, 4).map((opcode) => opcode.mnemonic).join('/');
  const behavior = script.behavior_categories?.slice(0, 3).map((item) => item.category).join('/');
  const flow = scriptControlFlowSummary(script);
  const cross = scriptCrossLinkSummary(script);
  const runtime = scriptRuntimeStateSummary(script);
  return `${script.kind} ${script.status} ${script.instruction_count} cmd${opcodes ? ` ${opcodes}` : ''}${behavior ? ` ${behavior}` : ''}${flow ? ` ${flow}` : ''}${cross ? ` ${cross}` : ''}${runtime ? ` ${runtime}` : ''}`;
}

function formatScriptBehavior(script: SceneScriptAnalysis): string {
  return (script.behavior_categories || [])
    .slice(0, 6)
    .map((item) => `${item.category}:${item.count}`)
    .join(', ') || '-';
}

function sceneScriptReferences(script: SceneScriptAnalysis): string {
  const labels: Record<string, string> = {
    animation: 'anim',
    behavior: 'behavior',
    buggy: 'buggy',
    camera_zone: 'camera zone',
    change_cube_control: 'change-cube control',
    escalator_zone: 'escalator zone',
    grm_zone: 'grm zone',
    hit_zone: 'hit zone',
    holomap: 'holomap',
    ladder_zone: 'ladder zone',
    music: 'music',
    palette: 'palette',
    pcx: 'pcx',
    rail_zone: 'rail zone',
    sample: 'sample',
    script_offset: 'script offset',
    track_label: 'track label',
    var_cube: 'var cube',
    var_game: 'var game',
  };
  const order = [
    'body',
    'animation',
    'sprite',
    'waypoint',
    'script_offset',
    'track_label',
    'object',
    'text',
    'var_cube',
    'var_game',
    'inventory',
    'sample',
    'music',
    'behavior',
    'palette',
    'pcx',
    'holomap',
    'buggy',
    'camera_zone',
    'ladder_zone',
    'grm_zone',
    'rail_zone',
    'hit_zone',
    'escalator_zone',
    'change_cube_control',
    'cube',
  ];
  const refs = order.flatMap((key) => {
    const values = script.references[key] || [];
    return values.length ? [`${labels[key] || key} ${values.slice(0, 6).join(',')}`] : [];
  });
  return refs.length ? `, refs ${escapeHtml(refs.join(' | '))}` : '';
}

function sceneScriptAssetLinks(script: SceneScriptAnalysis): string {
  const links = script.asset_links || [];
  if (!links.length) return '';
  const parts = links.slice(0, 6).map((link) => {
    const target = link.asset_id || `${link.kind}:${link.reference_value}`;
    return `${link.kind} ${target}${link.asset_available === false ? ' missing' : ''}`;
  });
  const suffix = links.length > parts.length ? ` +${links.length - parts.length}` : '';
  return `, asset links ${escapeHtml(parts.join(' | '))}${suffix}`;
}

function sceneScriptLocalLinks(script: SceneScriptAnalysis): string {
  const links = script.local_links || [];
  if (!links.length) return '';
  const parts = links.slice(0, 6).map((link) => {
    if (link.kind === 'object') return `object ${link.object_index ?? link.reference_value}`;
    if (link.kind === 'waypoint') return `waypoint ${link.waypoint_index ?? link.reference_value}`;
    if (link.kind === 'zone') {
      const mismatch = link.type_matches_reference === false ? ' mismatch' : '';
      return `${link.reference_key} zone ${link.zone_index ?? link.reference_value}${mismatch}`;
    }
    return `${link.kind} ${link.reference_value}`;
  });
  const suffix = links.length > parts.length ? ` +${links.length - parts.length}` : '';
  return `, local links ${escapeHtml(parts.join(' | '))}${suffix}`;
}

function sceneScriptCrossLinks(script: SceneScriptAnalysis): string {
  const links = script.cross_script_links || [];
  if (!links.length) return '';
  const parts = links.slice(0, 6).map((link) => {
    const target = link.target_found && link.target_opcode
      ? `${link.target_owner} ${link.target_script_kind}@${link.target_offset}:${link.target_opcode}`
      : `${link.target_owner} ${link.target_script_kind}@${link.target_offset}:${link.target_status || 'missing'}`;
    return `${link.source_offset}:${link.source_opcode}->${target}`;
  });
  const suffix = links.length > parts.length ? ` +${links.length - parts.length}` : '';
  return `, cross links ${escapeHtml(parts.join(' | '))}${suffix}`;
}

function sceneScriptControlFlowLinks(script: SceneScriptAnalysis): string {
  const links = script.control_flow_links || [];
  const labels = script.label_definitions || [];
  if (!links.length && !labels.length) return '';
  const parts: string[] = [];
  if (links.length) {
    const found = links.filter((link) => link.target_found).length;
    const examples = links.slice(0, 4).map((link) => {
      const target = link.target_found && link.target_opcode
        ? `${link.target_offset}:${link.target_opcode}`
        : `${link.target_offset}:${link.target_status || 'missing'}`;
      return `${link.source_offset}:${link.source_opcode}->${target}`;
    });
    const suffix = links.length > examples.length ? ` +${links.length - examples.length}` : '';
    parts.push(`flow ${found}/${links.length} targets ${examples.join(' | ')}${suffix}`);
  }
  if (labels.length) {
    const examples = labels.slice(0, 4).map((label) => `${label.label}@${label.offset}`);
    const suffix = labels.length > examples.length ? ` +${labels.length - examples.length}` : '';
    parts.push(`labels ${examples.join(', ')}${suffix}`);
  }
  return `, ${escapeHtml(parts.join('; '))}`;
}

function sceneScriptRuntimeState(script: SceneScriptAnalysis): string {
  const fields = script.runtime_state_fields || [];
  if (!fields.length) return '';
  const examples = fields.slice(0, 6).map((field) => {
    const value = field.initial_value === undefined ? field.initial_hex : formatRuntimeFieldValue(field.initial_value);
    return `${field.source_offset}:${field.opcode}.${field.field}+${field.operand_offset}/${field.size}=${value}`;
  });
  const suffix = fields.length > examples.length ? ` +${fields.length - examples.length}` : '';
  return `, runtime state ${escapeHtml(examples.join(' | '))}${suffix}`;
}

function scriptControlFlowSummary(script: SceneScriptAnalysis): string {
  const links = script.control_flow_links || [];
  if (!links.length) return '';
  const found = links.filter((link) => link.target_found).length;
  return `flow ${found}/${links.length}`;
}

function scriptRuntimeStateSummary(script: SceneScriptAnalysis): string {
  const fields = script.runtime_state_fields || [];
  if (!fields.length) return '';
  return `state ${fields.length}`;
}

function scriptCrossLinkSummary(script: SceneScriptAnalysis): string {
  const links = script.cross_script_links || [];
  if (!links.length) return '';
  const found = links.filter((link) => link.target_found).length;
  return `cross ${found}/${links.length}`;
}

function sceneScriptSemanticPreview(script: SceneScriptAnalysis): string {
  const parts = script.first_instructions
    .map((instruction) => {
      const semantics = Object.entries(instruction.operand_semantics || {});
      if (!semantics.length) return '';
      const fields = semantics.map(([key, value]) => `${key}=${formatRuntimeFieldValue(value)}`).join(' ');
      return `${instruction.mnemonic} ${fields}`;
    })
    .filter(Boolean)
    .slice(0, 4);
  return parts.length ? `, operands ${escapeHtml(parts.join(' | '))}` : '';
}

function formatCounts(counts?: Record<string, number>): string {
  return Object.entries(counts || {})
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}:${value}`)
    .join(', ');
}

function formatEnabledRules(rules?: Record<string, boolean>): string {
  return Object.entries(rules || {})
    .filter(([, enabled]) => enabled)
    .map(([key]) => key)
    .join(', ');
}

function renderZoneRuntimeFields(fields: Record<string, unknown>): string {
  return Object.entries(fields)
    .map(([key, value]) => `${key}=${formatRuntimeFieldValue(value)}`)
    .join(', ');
}

function formatRuntimeFieldValue(value: unknown): string {
  if (value === null || typeof value === 'number' || typeof value === 'boolean' || typeof value === 'string') {
    return String(value);
  }
  return JSON.stringify(value);
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

function renderAnim3dsRanges(entries: Anim3dsInfoStats['entries']): string {
  const rows = entries
    .map(
      (entry) =>
        `<div class="unknown-descriptor">` +
        `<span>${escapeHtml(entry.index)}</span>` +
        `<span>${escapeHtml(entry.name)}</span>` +
        `<span>frames ${escapeHtml(entry.start_frame)}..${escapeHtml(entry.end_frame)}</span>` +
        `<span>${escapeHtml(entry.frame_count)} frames</span>` +
        `</div>`,
    )
    .join('');
  return `<div class="unknown-descriptors">${rows}</div>`;
}

function renderAnim3dsPlayback(stats: Anim3dsInfoStats): string {
  const playback = stats.runtime_playback;
  if (!playback) return '';
  return `runtime: ${escapeHtml(stats.runtime_reference_status || '-')}<br>` +
    `timing: ${escapeHtml(playback.timing_source)}<br>` +
    `advance: ${escapeHtml(playback.advance_rule)}<br>` +
    `track controls: TM_START_ANIM_3DS, TM_STOP_ANIM_3DS, TM_WAIT_ANIM_3DS, TM_WAIT_FRAME_3DS<br>` +
    `provenance: ${escapeHtml(stats.source_provenance || '-')}<br>`;
}

function renderAnim3dsWarnings(warnings: Anim3dsInfoStats['range_warnings']): string {
  if (warnings.length === 0) return '';
  const rows = warnings
    .map(
      (warning) =>
        `<div class="unknown-descriptor">` +
        `<span>${escapeHtml(warning.name)}</span>` +
        `<span>missing ${escapeHtml(warning.missing_frames.length)} frames</span>` +
        `<span>${escapeHtml(warning.missing_frames.join(', '))}</span>` +
        `<span>${escapeHtml(warning.note)}</span>` +
        `</div>`,
    )
    .join('');
  return `<div class="unknown-descriptors">${rows}</div>`;
}

function renderSpriteRuntime(sprite: SpriteFrameStats): string {
  const runtime = sprite.runtime;
  if (!runtime) return '';
  const hotspot = runtime.hotspot
    ? `, hotspot ${escapeHtml(runtime.hotspot.x)},${escapeHtml(runtime.hotspot.y)}`
    : '';
  const bounds = runtime.bounds
    ? `, bounds x ${escapeHtml(runtime.bounds.min_x)}..${escapeHtml(runtime.bounds.max_x)}, ` +
      `y ${escapeHtml(runtime.bounds.min_y)}..${escapeHtml(runtime.bounds.max_y)}, ` +
      `z ${escapeHtml(runtime.bounds.min_z)}..${escapeHtml(runtime.bounds.max_z)}`
    : '';
  const source = runtime.bounds_source
    ? ` (${escapeHtml(runtime.bounds_source.hqr)}:${escapeHtml(runtime.bounds_source.entry_index)})`
    : '';
  return `runtime backend: ${escapeHtml(runtime.backend)}, runtime Sprite ${escapeHtml(runtime.runtime_sprite_index)}${hotspot}${bounds}${source}<br>`;
}

function renderDirectCodeReferences(references: NonNullable<ModelStats['direct_code_references']>): string {
  if (references.length === 0) return '';
  const rows = references.slice(0, 8).map((reference) =>
    `<div class="unknown-descriptor">` +
    `<span>${escapeHtml(reference.symbol)}</span>` +
    `<span>${escapeHtml(reference.purpose)}</span>` +
    `<span>${escapeHtml(reference.source)}</span>` +
    `</div>`,
  ).join('');
  const suffix = references.length > 8
    ? `<div class="asset-meta">+${escapeHtml(references.length - 8)} more direct references</div>`
    : '';
  return `<div class="asset-meta">Direct code references: ${escapeHtml(references.length)}</div>` +
    `<div class="unknown-descriptors">${rows}</div>${suffix}`;
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
