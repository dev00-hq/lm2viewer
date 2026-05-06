import type { AppSelection } from './selection';
import type { AnimationStats, Anim3dsInfoStats, CatalogAsset, DirectCodeReference, EntityContract, EntityWorkflowPayload, ModelStats, RawAnimationStats, ResourceStats, SceneAssetUsage, SceneScriptAnalysis, SceneStats, SpriteFrameStats } from './types';

export interface InspectorRow {
  label: string;
  value: string;
  status?: string;
  copyValue?: string;
}

export interface InspectorAction {
  id: string;
  label: string;
  copyValue?: string;
}

export interface InspectorSection {
  id: string;
  title: string;
  status?: string;
  rows: InspectorRow[];
  actions?: InspectorAction[];
  defaultOpen: boolean;
  searchText: string;
}

export function modelInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'model') return [];
  const stats = asset.stats as ModelStats;
  const sceneUsageCount = asset.scene_usages?.length || 0;
  const directReferences = stats.direct_code_references || [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'model' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Compatibility', value: selection.compatibilityStatus || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'geometry',
      title: 'Geometry',
      rows: [
        { label: 'Vertices', value: String(stats.vertices || 0) },
        { label: 'Polygons', value: String(stats.polygons || 0) },
        { label: 'Bones', value: String(stats.bones || 0) },
        { label: 'Lines', value: String(stats.lines || 0) },
        { label: 'Spheres', value: String(stats.spheres || 0) },
        { label: 'UV groups', value: String(stats.uv_groups || 0) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'runtime',
      title: 'Runtime',
      rows: [
        { label: 'Reference status', value: stats.runtime_reference_status || 'No direct runtime reference attached to this catalog model.' },
        { label: 'Scene usages', value: String(sceneUsageCount) },
      ],
      defaultOpen: sceneUsageCount > 0 || Boolean(stats.runtime_reference_status),
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if (directReferences.length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(directReferences),
      defaultOpen: directReferences.length <= 4,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function animationInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'animation' || asset.entry_type !== 'animation') return [];
  const stats = asset.stats as AnimationStats;
  if ('parse_status' in stats && stats.parse_status === 'raw') return [];
  const genericIds = asset.animation_metadata?.generic_ids || [];
  const genericNames = asset.animation_metadata?.generic_names || [];
  const compatibleBodies = asset.animation_metadata?.compatible_body_ids || [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'model' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Compatibility', value: selection.compatibilityStatus || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'animation',
      title: 'Animation',
      rows: [
        { label: 'Keyframes', value: String(stats.keyframes || 0) },
        { label: 'Boneframes', value: String(stats.boneframes || 0) },
        { label: 'Loop frame', value: String(stats.loop_frame ?? '-') },
        { label: 'Duration', value: `${stats.total_duration || 0} ms` },
        { label: 'Motion', value: stats.can_fall ? 'contains translation/fall frames' : 'rotation-only frames' },
        { label: 'Translated bones', value: String(stats.translated_boneframes || 0) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'runtime',
      title: 'Runtime',
      rows: [
        { label: 'Generic IDs', value: genericIds.length ? genericIds.join(', ') : '-' },
        { label: 'Generic names', value: genericNames.length ? genericNames.join(', ') : '-' },
        { label: 'Compatible BODY ids', value: compatibleBodies.length ? compatibleBodies.join(', ') : '-' },
      ],
      defaultOpen: genericIds.length > 0 || compatibleBodies.length > 0,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function rawAnimationInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  const stats = asset.stats;
  if (!('parse_status' in stats) || stats.parse_status !== 'raw') return [];
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'unknown') return [];
  if (asset.kind !== 'animation' && asset.kind !== 'sprite') return [];
  const raw = stats as RawAnimationStats;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || (asset.kind === 'sprite' ? 'sprite' : 'model') },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode status', value: raw.decode_status },
        { label: 'Decode note', value: raw.decode_note || '-' },
        { label: 'Parse error', value: raw.parse_error || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'raw_payload',
      title: 'Raw Payload',
      rows: [
        { label: 'Semantic layout', value: raw.semantic_layout },
        { label: 'Decoded bytes', value: String(raw.decoded_bytes ?? asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: raw.decoded_sha256 || asset.decoded_sha256 || '-', copyValue: raw.decoded_sha256 || asset.decoded_sha256 },
        { label: 'Descriptor count', value: String(raw.unknown_descriptors?.length || 0) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'header_words',
      title: 'Header Words',
      rows: [
        { label: 'Header word count', value: String(raw.header_word_count) },
        { label: 'Header words', value: raw.header_words.length > 0 ? raw.header_words.join(', ') : '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if (raw.anim3ds_info) {
    sections.splice(5, 0, {
      id: 'anim3ds_range',
      title: 'ANIM3DS Range',
      rows: [
        { label: 'Animation index', value: String(raw.anim3ds_info.animation_index) },
        { label: 'Name', value: raw.anim3ds_info.name },
        { label: 'Relative frame', value: String(raw.anim3ds_info.relative_frame) },
        { label: 'Range', value: `${raw.anim3ds_info.start_frame}..${raw.anim3ds_info.end_frame}` },
      ],
      defaultOpen: true,
      searchText: '',
    });
  }

  if (raw.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(raw.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function spriteFrameInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'sprite') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || (stats.semantic_layout !== 'lsp_sprite_frame' && stats.semantic_layout !== 'raw_sprite_frame')) return [];
  const sprite = stats as SpriteFrameStats;
  const format = sprite.semantic_layout === 'raw_sprite_frame' ? 'Raw sprite frame' : 'LSP sprite frame';
  const runtime = sprite.runtime;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Format', value: format },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'sprite' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: sprite.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'frame',
      title: 'Frame',
      rows: [
        { label: 'Dimensions', value: `${sprite.width} x ${sprite.height}` },
        { label: 'Offset', value: `${sprite.offset_x}, ${sprite.offset_y}` },
        { label: 'Opaque pixels', value: String(sprite.opaque_pixels) },
        { label: 'Transparent pixels', value: String(sprite.transparent_pixels) },
        { label: 'Palette colors', value: String(sprite.color_count) },
        ...pickedPixelRows(selection),
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'runtime',
      title: 'Runtime',
      rows: spriteRuntimeRows(sprite),
      defaultOpen: Boolean(runtime),
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
        { label: 'Encoded bytes consumed', value: String(sprite.encoded_bytes_consumed) },
        { label: 'Trailing bytes', value: String(sprite.trailing_bytes) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if (sprite.anim3ds_info) {
    sections.splice(5, 0, {
      id: 'anim3ds_range',
      title: 'ANIM3DS Range',
      rows: [
        { label: 'Animation index', value: String(sprite.anim3ds_info.animation_index) },
        { label: 'Name', value: sprite.anim3ds_info.name },
        { label: 'Relative frame', value: String(sprite.anim3ds_info.relative_frame) },
        { label: 'Range', value: `${sprite.anim3ds_info.start_frame}..${sprite.anim3ds_info.end_frame}` },
      ],
      defaultOpen: true,
      searchText: '',
    });
  }

  if ((sprite.direct_code_references || []).length > 0) {
    sections.splice(sprite.anim3ds_info ? 6 : 5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(sprite.direct_code_references || []),
      defaultOpen: (sprite.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (sprite.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(sprite.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function anim3dsRangeInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'anim3ds_frame_ranges') return [];
  const anim3ds = stats as Anim3dsInfoStats;
  const playback = anim3ds.runtime_playback;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'sprite' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: anim3ds.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'ranges',
      title: 'Ranges',
      rows: [
        { label: 'Range entries', value: String(anim3ds.entry_count) },
        { label: 'Frame min', value: String(anim3ds.frame_min) },
        { label: 'Frame max', value: String(anim3ds.frame_max) },
        { label: 'Referenced frames', value: String(anim3ds.frame_total) },
        ...anim3ds.entries.slice(0, 12).map((entry) => ({
          label: `${entry.index}: ${entry.name}`,
          value: `frames ${entry.start_frame}..${entry.end_frame}, ${entry.frame_count} frames`,
        })),
        ...(anim3ds.entries.length > 12
          ? [{ label: 'Folded ranges', value: `${anim3ds.entries.length - 12} additional ranges remain in catalog evidence.` }]
          : []),
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'runtime_playback',
      title: 'Runtime Playback',
      rows: playback
        ? [
          { label: 'Reference status', value: anim3ds.runtime_reference_status || '-' },
          { label: 'Timing source', value: playback.timing_source },
          { label: 'Advance rule', value: playback.advance_rule },
          { label: 'Reverse rule', value: playback.reverse_rule },
          { label: 'Range table source', value: playback.range_table_source },
          { label: 'Range record layout', value: playback.range_record_layout },
          { label: 'Scene initialization', value: playback.scene_initialization },
          { label: 'Track controls', value: Object.keys(playback.track_controls).join(', ') || '-' },
        ]
        : [{ label: 'Runtime playback', value: 'No runtime playback evidence is attached to this range table.' }],
      defaultOpen: Boolean(playback),
      searchText: '',
    },
    {
      id: 'warnings',
      title: 'Warnings',
      rows: anim3ds.range_warnings.length
        ? anim3ds.range_warnings.map((warning) => ({
          label: `${warning.animation_index}: ${warning.name}`,
          value: `${warning.missing_frames.length} missing frames | ${warning.note}`,
          copyValue: warning.missing_frames.join(', '),
        }))
        : [{ label: 'Range warnings', value: 'No missing range frames were reported.' }],
      defaultOpen: anim3ds.range_warnings.length > 0,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function sampleAudioInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'sample_wave_audio') return [];
  const sample = stats as ResourceStats;
  const fields = sample.fields || {};
  const resourceHeader = sample.resource_header || {};
  const chunks = sample.chunk_ids || [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: sample.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'audio',
      title: 'Audio',
      rows: [
        { label: 'Runtime sample', value: String(sample.sample_runtime_index ?? '-') },
        { label: 'Format', value: sample.audio_format || '-' },
        { label: 'Channels', value: String(fields.channels ?? '-') },
        { label: 'Sample rate', value: `${fields.sample_rate ?? '-'} Hz` },
        { label: 'Bits per sample', value: String(fields.bits_per_sample ?? '-') },
        { label: 'Sample frames', value: String(sample.sample_frames ?? '-') },
        { label: 'Duration', value: `${sample.duration_ms ?? '-'} ms` },
        { label: 'Data bytes', value: String(fields.data_bytes ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'wave_container',
      title: 'Wave Container',
      rows: [
        { label: 'Chunks', value: chunks.length ? chunks.join(', ') : '-' },
        { label: 'Block align', value: String(fields.block_align ?? '-') },
        { label: 'Samples per block', value: String(sample.samples_per_block ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
        { label: 'HQR method', value: String(resourceHeader.compress_method ?? '-') },
        { label: 'HQR decoded size', value: String(resourceHeader.size_file ?? '-') },
        { label: 'HQR compressed size', value: String(resourceHeader.compressed_size_file ?? '-') },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((sample.direct_code_references || []).length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(sample.direct_code_references || []),
      defaultOpen: (sample.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (sample.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(sample.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function smackerVideoInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'smacker_video') return [];
  const video = stats as ResourceStats;
  const resourceHeader = video.resource_header || {};
  const smackerHeader = video.header || {};
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: video.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'video',
      title: 'Video',
      rows: [
        { label: 'Runtime ACF', value: String(video.acf_index ?? '-') },
        { label: 'Name', value: video.acf_name || '-' },
        { label: 'Key', value: video.acf_basename || '-' },
        { label: 'Dimensions', value: `${video.width ?? '-'} x ${video.height ?? '-'}` },
        { label: 'Frames', value: String(video.frame_count ?? '-') },
        { label: 'FPS', value: String(video.frames_per_second ?? '-') },
        { label: 'Duration', value: `${video.duration_ms ?? '-'} ms` },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'smacker_container',
      title: 'Smacker Container',
      rows: [
        { label: 'Magic', value: String(smackerHeader.magic ?? '-') },
        { label: 'Flags', value: String(smackerHeader.flags ?? '-') },
        { label: 'Tree bytes', value: String(smackerHeader.tree_size ?? '-') },
        { label: 'Name source', value: video.name_source || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
        { label: 'HQR method', value: String(resourceHeader.compress_method ?? '-') },
        { label: 'HQR decoded size', value: String(resourceHeader.size_file ?? '-') },
        { label: 'HQR compressed size', value: String(resourceHeader.compressed_size_file ?? '-') },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((video.direct_code_references || []).length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(video.direct_code_references || []),
      defaultOpen: (video.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (video.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(video.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function textPayloadInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'text_payload_bank') return [];
  const text = stats as ResourceStats;
  const fields = text.fields || {};
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: text.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'text_bank',
      title: 'Text Bank',
      rows: [
        { label: 'Language', value: text.language || '-' },
        { label: 'Text file', value: text.text_file_name || String(text.text_file_index ?? '-') },
        { label: 'Records', value: String(text.record_count ?? '-') },
        { label: 'Paired order table', value: text.paired_entry_index === undefined ? '-' : `${asset.source.hqr}:${text.paired_entry_index}` },
        { label: 'Offset table bytes', value: String(text.offset_table_bytes ?? '-') },
        { label: 'Codepage', value: text.preview_codepage || '-' },
        { label: 'Flag counts', value: formatCounts(text.type_counts) || '-' },
        { label: 'Page breaks', value: String(fields.page_break_markers ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'sampled_records',
      title: 'Sampled Records',
      rows: sampledTextRecordRows(text),
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((text.direct_code_references || []).length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(text.direct_code_references || []),
      defaultOpen: (text.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (text.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(text.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function textOrderInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'text_order_table') return [];
  const text = stats as ResourceStats;
  const fields = text.fields || {};
  const sampledIds = text.sampled_message_ids || [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: text.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'text_order',
      title: 'Text Order',
      rows: [
        { label: 'Language', value: text.language || '-' },
        { label: 'Text file', value: text.text_file_name || String(text.text_file_index ?? '-') },
        { label: 'Message ids', value: String(text.record_count ?? '-') },
        { label: 'Paired text bank', value: text.paired_entry_index === undefined ? '-' : `${asset.source.hqr}:${text.paired_entry_index}` },
        { label: 'Min message id', value: String(fields.min_message_id ?? '-') },
        { label: 'Max message id', value: String(fields.max_message_id ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'sampled_message_ids',
      title: 'Sampled Message IDs',
      rows: [
        { label: 'Sampled ids', value: sampledIds.length ? sampledIds.slice(0, 40).join(', ') : '-' },
        ...(sampledIds.length > 40 ? [{ label: 'Folded ids', value: `${sampledIds.length - 40} additional sampled ids remain in catalog evidence.` }] : []),
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((text.direct_code_references || []).length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(text.direct_code_references || []),
      defaultOpen: (text.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (text.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(text.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function paletteImageInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || !isPaletteImageLayout(stats.semantic_layout)) return [];
  const resource = stats as ResourceStats;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: resource.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    paletteImagePrimarySection(resource),
    paletteContextSection(asset, resource),
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
        { label: 'Encoded bytes consumed', value: String(resource.encoded_bytes_consumed ?? '-') },
        { label: 'Trailing bytes', value: String(resource.trailing_bytes ?? '-') },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((resource.direct_code_references || []).length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(resource.direct_code_references || []),
      defaultOpen: (resource.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (resource.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(resource.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function runtimeTableInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || !isRuntimeTableLayout(stats.semantic_layout)) return [];
  const resource = stats as ResourceStats;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: resource.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    runtimeTablePrimarySection(resource),
    {
      id: 'sampled_records',
      title: 'Sampled Records',
      rows: runtimeTableSampleRows(resource),
      defaultOpen: resource.semantic_layout !== 'acf_name_list' && resource.semantic_layout !== 'ress_ext_size_info',
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
        { label: 'Preview hex', value: resource.preview_hex || '-' },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((resource.direct_code_references || []).length > 0) {
    sections.splice(5, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(resource.direct_code_references || []),
      defaultOpen: (resource.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (resource.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(resource.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function holomapInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || !isHolomapLayout(stats.semantic_layout)) return [];
  const resource = stats as ResourceStats;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: resource.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    holomapPrimarySection(resource, asset),
    {
      id: 'sampled_records',
      title: 'Sampled Records',
      rows: holomapSampleRows(resource),
      defaultOpen: resource.semantic_layout === 'holomap_globe_uv_map' || resource.semantic_layout === 'holomap_arrow_table',
      searchText: '',
    },
    {
      id: 'text_links',
      title: 'Text Links',
      rows: holomapTextLinkRows(resource),
      defaultOpen: (resource.text_links || []).length > 0,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((resource.direct_code_references || []).length > 0) {
    sections.splice(6, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(resource.direct_code_references || []),
      defaultOpen: (resource.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (resource.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(resource.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function backgroundInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || !isBackgroundLayout(stats.semantic_layout)) return [];
  const resource = stats as ResourceStats;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: resource.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    backgroundPrimarySection(resource),
    {
      id: 'composition',
      title: 'Composition',
      rows: backgroundCompositionRows(resource),
      defaultOpen: resource.semantic_layout === 'bkg_grid_map' || resource.semantic_layout === 'bkg_grm_fragment',
      searchText: '',
    },
    {
      id: 'sampled_records',
      title: 'Sampled Records',
      rows: backgroundSampleRows(resource),
      defaultOpen: resource.semantic_layout === 'bkg_block_table' || resource.semantic_layout === 'bkg_cube_map',
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
        { label: 'Preview hex', value: resource.preview_hex || '-' },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((resource.direct_code_references || []).length > 0) {
    sections.splice(6, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(resource.direct_code_references || []),
      defaultOpen: (resource.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (resource.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(resource.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function sceneInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  const stats = asset.stats;
  if (asset.kind !== 'scene' || !('semantic_layout' in stats) || stats.semantic_layout !== 'scene_runtime_layout_partial') return [];
  const scene = stats as SceneStats;
  const recon = scene.reconnaissance || {};
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.kind === 'sprite_frame' ? selection.label : asset.label },
        { label: 'Kind', value: selection.kind === 'sprite_frame' ? selection.kind : asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'entity' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: scene.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'world',
      title: 'World',
      rows: sceneWorldRows(scene),
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'background',
      title: 'Background',
      rows: sceneBackgroundRows(scene),
      defaultOpen: Boolean(recon.background),
      searchText: '',
    },
    {
      id: 'hero_scripts',
      title: 'Hero Scripts',
      rows: sceneHeroRows(scene),
      defaultOpen: Boolean(recon.hero),
      searchText: '',
    },
    {
      id: 'runtime_links',
      title: 'Runtime Links',
      rows: sceneRuntimeLinkRows(scene),
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'render_contract',
      title: 'Render Contract',
      rows: sceneRenderContractRows(scene),
      defaultOpen: Boolean(recon.scene_frame_render_contract),
      searchText: '',
    },
    {
      id: 'sampled_objects',
      title: 'Sampled Objects',
      rows: sceneSampledObjectRows(scene),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'zones_tracks_patches',
      title: 'Zones Tracks Patches',
      rows: sceneZoneTrackPatchRows(scene),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if (selection.kind === 'sprite_frame') {
    sections.splice(3, 0, {
      id: 'frame',
      title: 'Frame',
      rows: [
        { label: 'Variant', value: String(selection.facets?.frameVariant || '-') },
        { label: 'Variant label', value: String(selection.facets?.frameVariantLabel || '-') },
        { label: 'Format', value: String(selection.facets?.frameFormat || '-') },
        { label: 'Dimensions', value: `${selection.facets?.width ?? '-'} x ${selection.facets?.height ?? '-'}` },
        { label: 'Offset', value: `${selection.facets?.offsetX ?? '-'}, ${selection.facets?.offsetY ?? '-'}` },
        { label: 'Palette source', value: String(selection.facets?.paletteSource || '-') },
        ...pickedPixelRows(selection),
      ],
      defaultOpen: true,
      searchText: '',
    });
  }

  if (scene.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(scene.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function unclassifiedResourceInspectorSections(asset: CatalogAsset, selection: AppSelection): InspectorSection[] {
  if (asset.kind !== 'resource') return [];
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'ress_unclassified_payload') return [];
  const resource = stats as ResourceStats;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: asset.label },
        { label: 'Kind', value: asset.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: asset.source.hqr },
        { label: 'Entry', value: String(asset.source.entry_index), copyValue: `${asset.source.hqr}:${asset.source.entry_index}` },
        { label: 'Classic index', value: asset.source.classic_index === undefined ? '-' : String(asset.source.classic_index) },
        { label: 'Relative path', value: asset.relative_path || '-' },
        { label: 'Raw SHA-256', value: asset.source.raw_sha256 || '-', copyValue: asset.source.raw_sha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Decode note', value: resource.decode_note || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'resource_payload',
      title: 'Resource Payload',
      rows: [
        { label: 'Layout', value: resource.semantic_layout },
        { label: 'Decode status', value: resource.decode_status },
        { label: 'Decoded bytes', value: String(resource.decoded_bytes) },
        { label: 'Preview hex', value: resource.preview_hex || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'scene_usages',
      title: 'Scene Usages',
      rows: usageRows(asset.scene_usages || []),
      defaultOpen: false,
      searchText: '',
    },
    {
      id: 'raw_evidence',
      title: 'Raw Evidence',
      rows: [
        { label: 'Decoded bytes', value: String(asset.decoded_bytes) },
        { label: 'Decoded SHA-256', value: asset.decoded_sha256 || '-', copyValue: asset.decoded_sha256 },
        { label: 'Raw bytes', value: String(asset.source.raw_bytes) },
        { label: 'Archive offset', value: String(asset.source.offset) },
      ],
      defaultOpen: false,
      searchText: '',
    },
  ];

  if ((resource.direct_code_references || []).length > 0) {
    sections.splice(4, 0, {
      id: 'source_references',
      title: 'Source References',
      rows: directReferenceRows(resource.direct_code_references || []),
      defaultOpen: (resource.direct_code_references || []).length <= 4,
      searchText: '',
    });
  }

  if (resource.unknown_descriptors.length > 0) {
    sections.splice(sections.length - 1, 0, {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: unknownDescriptorRows(resource.unknown_descriptors),
      defaultOpen: false,
      searchText: '',
    });
  }

  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function evidenceArtifactInspectorSections(selection: AppSelection): InspectorSection[] {
  if (selection.kind !== 'evidence_artifact') return [];
  const facets = selection.facets || {};
  const warnings = selection.unknowns || [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Output dir', value: stringFacet(facets.outputDir), copyValue: stringFacet(facets.outputDir) },
        { label: 'Manifest', value: stringFacet(facets.manifest), copyValue: stringFacet(facets.manifest) },
        { label: 'Files', value: stringFacet(facets.fileCount) },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Proof scope', value: 'viewer export artifact; not canonical runtime proof' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Source asset', value: stringFacet(facets.sourceAssetId), copyValue: stringFacet(facets.sourceAssetId) },
        { label: 'Source label', value: stringFacet(facets.sourceLabel) },
        { label: 'Polygon mode', value: stringFacet(facets.polygonMode) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'export',
      title: 'Export',
      rows: [
        { label: 'Generated files', value: stringFacet(facets.generatedFiles) },
        { label: 'Warnings', value: warnings.length ? String(warnings.length) : '0' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: warnings.length ? warnings.map((warning, index) => ({ label: `Warning ${index + 1}`, value: warning })) : [{ label: 'Warnings', value: 'none' }],
      defaultOpen: warnings.length > 0,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function sceneObjectInspectorSections(selection: AppSelection): InspectorSection[] {
  if (selection.kind !== 'scene_object') return [];
  const entity = selection.evidence?.entityContract;
  const workflow = selection.evidence?.entityWorkflow;
  if (!entity) return [];
  const state = entity.initial_state;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'entity' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Scene asset', value: entity.scene_asset_id, copyValue: entity.scene_asset_id },
        { label: 'Scene entry', value: String(entity.scene_entry_index) },
        { label: 'Scene index', value: formatNullable(entity.scene_index) },
        { label: 'Object index', value: formatNullable(entity.object_index), copyValue: entity.object_index === null ? undefined : selection.stableId },
        { label: 'Sample status', value: entity.object_sample_status },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Confidence', value: entity.confidence },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Resolution rule', value: entity.provenance.resolution_rule || '-' },
        { label: 'Entrypoint', value: workflowEntrypoint(workflow) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'runtime_state',
      title: 'Runtime State',
      rows: [
        { label: 'Flags', value: formatHexNumber(state.flags) },
        { label: 'File3D', value: formatNullable(state.file3d_index) },
        { label: 'GenBody', value: formatNullable(state.gen_body) },
        { label: 'GenAnim', value: formatNullable(state.gen_anim) },
        { label: 'Sprite', value: formatNullable(state.sprite) },
        { label: 'Position', value: formatPosition(entity.position) },
        { label: 'Movement', value: compactJson(state.movement) },
        { label: 'Collision', value: compactJson(state.collision) },
        { label: 'Combat', value: compactJson(state.combat) },
        { label: 'Bonus', value: compactJson(state.bonus) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'render_contract',
      title: 'Render Contract',
      rows: renderContractRows(entity),
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'visual_links',
      title: 'Visual Links',
      rows: entity.linked_visual_assets.length
        ? entity.linked_visual_assets.map((link) => ({
          label: link.role,
          value: `${link.asset_id} | ${link.asset_available === false ? 'unavailable' : 'available'} | ${link.resolution_rule || '-'}`,
          copyValue: link.asset_id,
        }))
        : [{ label: 'Visual links', value: 'No linked visual asset evidence is attached.' }],
      defaultOpen: entity.linked_visual_assets.length > 0,
      searchText: '',
    },
    {
      id: 'script_links',
      title: 'Script Links',
      rows: [
        { label: 'Asset links', value: String(entity.script_driven_links.length) },
        { label: 'Local links', value: String(entity.local_links.length) },
        { label: 'Cross-script links', value: String(entity.cross_script_links.length) },
        ...scriptLinkRows('Asset', entity.script_driven_links),
        ...scriptLinkRows('Local', entity.local_links),
        ...scriptLinkRows('Cross-script', entity.cross_script_links),
      ],
      defaultOpen: entity.script_driven_links.length > 0,
      searchText: '',
    },
    {
      id: 'port_implications',
      title: 'Port Implications',
      rows: entity.port_implications.length
        ? entity.port_implications.map((implication) => ({
          label: implication.area,
          value: `${implication.claim} | ${implication.evidence}`,
        }))
        : [{ label: 'Port implications', value: 'No source-backed port implication is attached.' }],
      defaultOpen: entity.port_implications.length > 0,
      searchText: '',
    },
    {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: sceneObjectUnknownRows(entity, workflow),
      defaultOpen: entity.unknowns.length > 0 || (workflow?.unknowns.length || 0) > 0,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function modelSurfaceInspectorSections(selection: AppSelection): InspectorSection[] {
  if (selection.kind !== 'model_surface') return [];
  const polygon = selection.evidence?.polygon;
  if (!polygon) return [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'model' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Archive', value: selection.source?.archive || '-' },
        { label: 'Entry', value: formatNullable(selection.source?.entryIndex) },
        { label: 'Classic index', value: formatNullable(selection.source?.classicIndex) },
        { label: 'Raw SHA-256', value: selection.source?.rawSha256 || '-', copyValue: selection.source?.rawSha256 },
        { label: 'Decoded SHA-256', value: selection.source?.decodedSha256 || '-', copyValue: selection.source?.decodedSha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Surface evidence', value: 'decoded polygon and UV atlas evidence; not runtime picking proof' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'surface',
      title: 'Surface',
      rows: [
        { label: 'Polygon', value: String(polygon.polygon_index) },
        { label: 'Material', value: `${polygon.material.kind} ${polygon.material.value}` },
        { label: 'Color word', value: formatHexNumber(polygon.material.color_word) },
        { label: 'Palette index', value: String(polygon.material.palette_index) },
        { label: 'Intensity', value: String(polygon.material.intensity) },
        { label: 'Vertices', value: polygon.vertices.join(', ') },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'render_flags',
      title: 'Render Flags',
      rows: [
        { label: 'Render type', value: formatHexNumber(polygon.render_flags.render_type) },
        { label: 'Has texture', value: String(polygon.render_flags.has_texture) },
        { label: 'Has transparency', value: String(polygon.render_flags.has_transparency) },
        { label: 'Has extra', value: String(polygon.render_flags.has_extra) },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'uv',
      title: 'UV Evidence',
      rows: uvEvidenceRows(polygon),
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: polygon.unknowns.length
        ? polygon.unknowns.map((unknown) => ({
          label: unknown.field,
          value: `${unknown.value}: ${unknown.note}`,
        }))
        : [{ label: 'Unknowns', value: 'No explicit unknowns on this polygon evidence.' }],
      defaultOpen: polygon.unknowns.length > 0,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function animationSampleInspectorSections(selection: AppSelection): InspectorSection[] {
  if (selection.kind !== 'animation_sample') return [];
  const body = selection.evidence?.animationBody;
  const animation = selection.evidence?.animation;
  const frame = selection.evidence?.animationFrame;
  const sequence = selection.evidence?.animationSequence;
  const pose = frame?.pose || selection.evidence?.model?.pose;
  if (!body || !animation || !pose) return [];
  const sample = pose.sample;
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'model' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Body asset', value: body.id, copyValue: body.id },
        { label: 'Animation asset', value: animation.id, copyValue: animation.id },
        { label: 'Archive', value: selection.source?.archive || '-' },
        { label: 'Entry', value: formatNullable(selection.source?.entryIndex) },
        { label: 'Classic index', value: formatNullable(selection.source?.classicIndex) },
        { label: 'Decoded SHA-256', value: selection.source?.decodedSha256 || '-', copyValue: selection.source?.decodedSha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Proof scope', value: 'decoded BODY+ANIM pose sample; not live runtime writer proof' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'animation_sample',
      title: 'Animation Sample',
      rows: [
        { label: 'Sequence index', value: frame ? String(frame.sequence_index) : 'manual pose sample' },
        { label: 'Segment', value: frame?.segment || 'pose' },
        { label: 'Frame', value: String(frame?.frame ?? sample.target_frame_index) },
        { label: 'Previous frame', value: String(frame?.previous_frame ?? sample.previous_frame_index) },
        { label: 'Next frame', value: String(frame?.next_frame ?? sample.next_frame_index) },
        { label: 'Elapsed', value: `${frame?.elapsed_ms ?? sample.elapsed_ms} ms` },
        { label: 'Timeline', value: frame ? `${frame.timeline_ms} ms` : 'not sequenced' },
        { label: 'Duration', value: `${frame?.duration_ms ?? sample.duration_ms} ms` },
      ],
      defaultOpen: true,
      searchText: '',
    },
    ...(sequence ? [{
      id: 'playback_sequence',
      title: 'Playback Sequence',
      rows: [
        { label: 'Step', value: `${sequence.step_ms} ms` },
        { label: 'Keyframes', value: String(sequence.keyframes) },
        { label: 'Loop frame', value: String(sequence.loop_frame) },
        { label: 'Loop index', value: String(sequence.loop_index) },
        { label: 'Playback end index', value: String(sequence.playback_end_index) },
        { label: 'Frame samples', value: String(sequence.frames.length) },
      ],
      defaultOpen: true,
      searchText: '',
    }] : []),
    {
      id: 'pose',
      title: 'Pose',
      rows: [
        { label: 'Target frame', value: String(sample.target_frame_index) },
        { label: 'Previous frame', value: String(sample.previous_frame_index) },
        { label: 'Next frame', value: String(sample.next_frame_index) },
        { label: 'Sample elapsed', value: `${sample.elapsed_ms} ms` },
        { label: 'Sample duration', value: `${sample.duration_ms} ms` },
        { label: 'Complete', value: String(sample.complete) },
        { label: 'Bone count', value: String(sample.bone_count) },
        { label: 'Root delta', value: sample.root_delta ? sample.root_delta.map(formatNumber).join(', ') : '-' },
        { label: 'Root motion', value: frame?.root_motion ? frame.root_motion.map(formatNumber).join(', ') : '-' },
      ],
      defaultOpen: true,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function resourceRecordInspectorSections(selection: AppSelection): InspectorSection[] {
  if (selection.kind !== 'resource_record') return [];
  const asset = selection.evidence?.resourceAsset;
  const record = selection.evidence?.resourceRecord;
  if (!asset || !record) return [];
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'resource' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Resource asset', value: asset.id, copyValue: asset.id },
        { label: 'Archive', value: selection.source?.archive || '-' },
        { label: 'Entry', value: formatNullable(selection.source?.entryIndex) },
        { label: 'Classic index', value: formatNullable(selection.source?.classicIndex) },
        { label: 'Raw SHA-256', value: selection.source?.rawSha256 || '-', copyValue: selection.source?.rawSha256 },
        { label: 'Decoded SHA-256', value: selection.source?.decodedSha256 || '-', copyValue: selection.source?.decodedSha256 },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Proof scope', value: 'decoded resource subrecord evidence; not live runtime proof' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'resource_record',
      title: 'Resource Record',
      rows: [
        { label: 'Record kind', value: record.kind },
        { label: 'Summary', value: record.summary },
        { label: 'Detail', value: record.detail },
        ...record.rows.map(([label, value]) => ({ label, value })),
      ],
      defaultOpen: true,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function sceneUsageInspectorSections(selection: AppSelection): InspectorSection[] {
  if (selection.kind !== 'scene_usage') return [];
  const asset = selection.evidence?.usageAsset;
  const usage = selection.evidence?.sceneUsage;
  if (!asset || !usage) return [];
  const rows: InspectorRow[] = [
    { label: 'Usage kind', value: usage.kind },
    { label: 'Target asset', value: usage.target_asset_id, copyValue: usage.target_asset_id },
    { label: 'Scene asset', value: usage.scene_asset_id, copyValue: usage.scene_asset_id },
    { label: 'Scene index', value: formatNullable(usage.scene_index) },
    { label: 'Object index', value: String(usage.object_index) },
    { label: 'Position', value: usage.position ? `${usage.position.x}, ${usage.position.y}, ${usage.position.z}` : '-' },
    { label: 'File3D', value: String(usage.file3d_index) },
    { label: 'GenBody', value: String(usage.gen_body) },
    { label: 'GenAnim', value: String(usage.gen_anim) },
    { label: 'Sprite', value: String(usage.sprite) },
    { label: 'Flags', value: formatHexNumber(usage.flags) },
  ];
  if (usage.script_kind) rows.push({ label: 'Script kind', value: usage.script_kind });
  if (usage.reference_key) rows.push({ label: 'Reference', value: `${usage.reference_key} ${usage.reference_value ?? '-'}` });
  if (usage.generic_id !== undefined) rows.push({ label: 'Generic', value: `${usage.generic_name || '-'} (${usage.generic_id})` });
  if (usage.backend) rows.push({ label: 'Backend', value: usage.backend });
  if (usage.runtime_sprite_index !== undefined) rows.push({ label: 'Runtime sprite', value: String(usage.runtime_sprite_index) });
  if (usage.anim3ds_range) rows.push({ label: 'ANIM3DS range', value: `animation ${usage.anim3ds_range.animation_number} frame ${usage.anim3ds_range.start_frame}..${usage.anim3ds_range.end_frame}` });
  if (usage.text_id !== undefined) rows.push({ label: 'Text', value: `${usage.text_file_name || '-'} message ${usage.text_id}` });
  if (usage.preview) rows.push({ label: 'Preview', value: usage.preview });
  if (usage.sample_id !== undefined) rows.push({ label: 'Sample', value: `${usage.sample_id} ${usage.audio_format || ''} ${usage.sample_rate ?? '-'}Hz`.trim() });
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'entity' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'source',
      title: 'Source',
      rows: [
        { label: 'Selected asset', value: asset.id, copyValue: asset.id },
        { label: 'Archive', value: selection.source?.archive || '-' },
        { label: 'Entry', value: formatNullable(selection.source?.entryIndex) },
        { label: 'Target asset', value: usage.target_asset_id, copyValue: usage.target_asset_id },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Proof scope', value: 'reverse catalog usage evidence; not live runtime proof' },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'scene_usage',
      title: 'Scene Usage',
      rows,
      defaultOpen: true,
      searchText: '',
    },
  ];
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

export function entityFacetInspectorSections(selection: AppSelection): InspectorSection[] {
  if (
    selection.kind !== 'runtime_sprite_state'
    && selection.kind !== 'file3d_resolution'
    && selection.kind !== 'anim3ds_range_state'
    && selection.kind !== 'render_contract'
    && selection.kind !== 'palette_context'
  ) return [];
  const facets = selection.facets || {};
  const facetRows = Object.entries(facets)
    .filter(([, value]) => value !== undefined)
    .map(([label, value]) => ({
      label: label.replace(/([A-Z])/g, ' $1').replace(/^./, (char) => char.toUpperCase()),
      value: stringFacet(value),
      copyValue: typeof value === 'string' || typeof value === 'number' ? String(value) : undefined,
    }));
  const sections: InspectorSection[] = [
    {
      id: 'summary',
      title: 'Summary',
      rows: [
        { label: 'Stable ID', value: selection.stableId, copyValue: selection.stableId },
        { label: 'Label', value: selection.label },
        { label: 'Kind', value: selection.kind },
        { label: 'Workspace', value: selection.workspaceSuggestion || 'entity' },
      ],
      actions: [{ id: 'copy_stable_id', label: 'Copy Stable ID', copyValue: selection.stableId }],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'evidence_status',
      title: 'Evidence Status',
      status: selection.evidenceStatus,
      rows: [
        { label: 'Status', value: selection.evidenceStatus, status: selection.evidenceStatus },
        { label: 'Provenance', value: selection.provenance },
        { label: 'Source', value: selection.source?.archive === undefined ? '-' : `${selection.source.archive}[${selection.source.entryIndex ?? '-'}]` },
      ],
      defaultOpen: true,
      searchText: '',
    },
    {
      id: 'facet',
      title: facetTitle(selection.kind),
      rows: facetRows.length ? facetRows : [{ label: 'Facet', value: 'No facet fields attached.' }],
      defaultOpen: true,
      searchText: '',
    },
  ];
  if (selection.unknowns.length > 0) {
    sections.push({
      id: 'unknown_descriptors',
      title: 'Unknown Descriptors',
      rows: selection.unknowns.map((unknown, index) => ({ label: `Unknown ${index + 1}`, value: unknown })),
      defaultOpen: true,
      searchText: '',
    });
  }
  return sections.map((section) => ({
    ...section,
    searchText: sectionSearchText(section),
  }));
}

function stringFacet(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
}

function pickedPixelRows(selection: AppSelection): InspectorRow[] {
  const facets = selection.facets || {};
  if (facets.pickedPixelX === undefined || facets.pickedPixelY === undefined) return [];
  const xy = `${facets.pickedPixelX}, ${facets.pickedPixelY}`;
  return [
    { label: 'Picked pixel', value: xy, copyValue: xy },
    { label: 'Picked palette index', value: String(facets.pickedPaletteIndex ?? '-') },
    { label: 'Picked RGBA', value: String(facets.pickedRgba || '-') },
  ];
}

function sceneWorldRows(scene: SceneStats): InspectorRow[] {
  const recon = scene.reconnaissance || {};
  const world = recon.world;
  const ambience = recon.ambience;
  if (!world && !ambience) return [{ label: 'World header', value: 'No world or ambience header was decoded.' }];
  const rows: InspectorRow[] = [];
  if (world) {
    rows.push(
      { label: 'Island', value: String(world.island) },
      { label: 'Cube', value: `${world.cube_x}, ${world.cube_y}` },
      { label: 'Cube mode', value: String(world.cube_mode) },
      { label: 'Shadow level', value: String(world.shadow_level) },
      { label: 'Labyrinth mode', value: String(world.labyrinth_mode) },
      { label: 'Post-cube byte', value: String(world.unknown_world_byte) },
    );
    if (world.runtime_environment) {
      rows.push(
        { label: 'Environment provenance', value: world.runtime_environment.source_provenance },
        { label: 'Island effect', value: world.runtime_environment.island_effect },
        { label: 'Cube coordinate effect', value: world.runtime_environment.cube_coordinate_effect },
        { label: 'Cube mode effect', value: world.runtime_environment.cube_mode_effect },
        { label: 'Post-cube status', value: world.runtime_environment.post_cube_mode_byte_status },
      );
    }
  }
  if (ambience) {
    rows.push(
      { label: 'Light', value: `${ambience.alpha_light}, ${ambience.beta_light}` },
      { label: 'Cube jingle', value: String(ambience.cube_jingle) },
    );
    if (ambience.runtime_audio_lighting) {
      rows.push(
        { label: 'Audio provenance', value: ambience.runtime_audio_lighting.source_provenance },
        { label: 'Lighting effect', value: ambience.runtime_audio_lighting.lighting_effect },
        { label: 'Ambient sample rule', value: ambience.runtime_audio_lighting.ambient_sample_rule },
        { label: 'Ambient timer rule', value: ambience.runtime_audio_lighting.ambient_timer_rule },
        { label: 'Music rule', value: ambience.runtime_audio_lighting.music_rule },
      );
    }
  }
  return rows;
}

function sceneBackgroundRows(scene: SceneStats): InspectorRow[] {
  const background = scene.reconnaissance?.background;
  if (!background) return [{ label: 'Background', value: 'No background runtime cube evidence was decoded.' }];
  const palette = background.palette;
  const rows: InspectorRow[] = [
    { label: 'Runtime cube', value: String(background.runtime_cube) },
    { label: 'Scene entry index', value: String(background.scene_entry_index) },
    { label: 'Cube map record', value: background.cube_map_record_found ? 'found' : 'missing' },
    { label: 'Cube record', value: `${background.cube_record_type ?? '-'} / ${background.cube_record_num ?? '-'}` },
    { label: 'Resolved GRI', value: background.resolved_gri_entry === undefined ? '-' : `LBA_BKG.HQR:${background.resolved_gri_entry}`, copyValue: background.resolved_gri_entry === undefined ? undefined : `LBA_BKG.HQR:${background.resolved_gri_entry}` },
    { label: 'Resolved BLL', value: background.resolved_bll_entry === undefined ? '-' : `LBA_BKG.HQR:${background.resolved_bll_entry}`, copyValue: background.resolved_bll_entry === undefined ? undefined : `LBA_BKG.HQR:${background.resolved_bll_entry}` },
    { label: 'Resolved GRM', value: background.resolved_grm_entry === undefined ? '-' : `LBA_BKG.HQR:${background.resolved_grm_entry}`, copyValue: background.resolved_grm_entry === undefined ? undefined : `LBA_BKG.HQR:${background.resolved_grm_entry}` },
    { label: 'Used blocks', value: String(background.used_block_count ?? '-') },
    { label: 'Source provenance', value: background.source_provenance || '-' },
  ];
  if (palette) {
    rows.push(
      { label: 'Palette source', value: palette.source },
      { label: 'Palette rule', value: palette.rule },
      { label: 'Resolved palette', value: palette.resolved_palette_entry === undefined ? '-' : `RESS.HQR:${palette.resolved_palette_entry} ${palette.resolved_palette_name || ''}`.trim(), copyValue: palette.resolved_palette_entry === undefined ? undefined : `RESS.HQR:${palette.resolved_palette_entry}` },
      { label: 'Alternate palette', value: palette.alternate_palette_entry === undefined ? '-' : `RESS.HQR:${palette.alternate_palette_entry} ${palette.alternate_palette_name || ''}`.trim() },
      { label: 'Alternate condition', value: palette.alternate_condition || '-' },
      { label: 'Palette confidence', value: palette.confidence },
    );
  }
  return rows;
}

function sceneHeroRows(scene: SceneStats): InspectorRow[] {
  const hero = scene.reconnaissance?.hero;
  if (!hero) return [{ label: 'Hero', value: 'No hero start or script evidence was decoded.' }];
  return [
    { label: 'Start', value: `${hero.start.x}, ${hero.start.y}, ${hero.start.z}` },
    { label: 'Track script bytes', value: String(hero.track_script_bytes) },
    { label: 'Track SHA-256', value: hero.track_script_sha256 || '-', copyValue: hero.track_script_sha256 },
    { label: 'Track opcodes', value: scriptOpcodeSummary(hero.track_script_analysis) },
    { label: 'Track behavior', value: scriptBehaviorSummary(hero.track_script_analysis) },
    { label: 'Life script bytes', value: String(hero.life_script_bytes) },
    { label: 'Life SHA-256', value: hero.life_script_sha256 || '-', copyValue: hero.life_script_sha256 },
    { label: 'Life opcodes', value: scriptOpcodeSummary(hero.life_script_analysis) },
    { label: 'Life behavior', value: scriptBehaviorSummary(hero.life_script_analysis) },
  ];
}

function sceneRuntimeLinkRows(scene: SceneStats): InspectorRow[] {
  const recon = scene.reconnaissance || {};
  return [
    { label: 'Objects', value: `${recon.object_count ?? '-'} total, ${recon.sprite_object_count ?? 0} sprite, ${recon.anim3ds_object_count ?? 0} ANIM3DS` },
    { label: 'Object links', value: `${recon.linked_body_refs ?? 0} body, ${recon.linked_animation_refs ?? 0} animation, ${recon.linked_sprite_refs ?? 0} sprite` },
    { label: 'Script asset links', value: `${recon.script_linked_body_refs ?? 0} body, ${recon.script_linked_animation_refs ?? 0} animation, ${recon.script_linked_sprite_refs ?? 0} sprite` },
    { label: 'Text links', value: `${recon.text_link_counts?.script_logical_refs ?? 0} script refs, ${recon.text_link_counts?.zone_logical_refs ?? 0} zone refs, file ${recon.text_file_index ?? '-'}` },
    { label: 'Sample links', value: `${recon.sample_link_counts?.script_linked_refs ?? 0} script refs, ${recon.sample_link_counts?.ambience_linked_refs ?? 0} ambience refs, ${(recon.sample_link_counts?.script_missing_refs ?? 0) + (recon.sample_link_counts?.ambience_missing_refs ?? 0)} missing` },
    { label: 'Video links', value: `${recon.video_link_counts?.script_linked_refs ?? 0}/${recon.video_link_counts?.script_logical_refs ?? 0} script refs` },
    { label: 'Local script links', value: `${recon.script_local_link_counts?.object ?? 0} objects, ${recon.script_local_link_counts?.waypoint ?? 0} waypoints, ${recon.script_local_link_counts?.zone ?? 0} zones` },
    { label: 'Control flow', value: `${recon.script_control_flow_counts?.found ?? 0}/${recon.script_control_flow_counts?.links ?? 0} resolved targets, ${recon.script_control_flow_counts?.labels ?? 0} labels; ${formatCounts(recon.script_control_flow_target_status_counts) || '-'}` },
    { label: 'Cross-script targets', value: `${recon.script_cross_link_counts?.found ?? 0}/${recon.script_cross_link_counts?.links ?? 0} resolved, ${recon.script_cross_link_counts?.track ?? 0} track, ${recon.script_cross_link_counts?.life ?? 0} life; ${formatCounts(recon.script_cross_link_target_status_counts) || '-'}` },
  ];
}

function sceneRenderContractRows(scene: SceneStats): InspectorRow[] {
  const recon = scene.reconnaissance || {};
  const contract = recon.scene_frame_render_contract;
  const rows: InspectorRow[] = [
    { label: 'Render types', value: formatCounts(recon.object_render_type_counts) || '-' },
    { label: 'Render pipeline', value: formatCounts(recon.object_render_pipeline_counts) || '-' },
    { label: 'Render contracts', value: formatCounts(recon.object_render_contract_counts) || '-' },
    { label: 'Redraw methods', value: formatCounts(recon.object_redraw_method_counts) || '-' },
    { label: 'Movement states', value: formatCounts(recon.object_movement_state_counts) || '-' },
    { label: 'Script behavior', value: formatCounts(recon.script_behavior_counts) || '-' },
    { label: 'Execution contracts', value: formatCounts(recon.script_execution_contract_counts) || '-' },
  ];
  if (contract) {
    rows.push(
      { label: 'Source', value: contract.source },
      { label: 'Scene object records', value: String(contract.scene_object_records) },
      { label: 'HQR-backed sources', value: contract.hqr_backed_sources.join(', ') || '-' },
      { label: 'Runtime dynamic sources', value: contract.runtime_dynamic_sources.join(', ') || '-' },
      { label: 'AFF scene phases', value: contract.aff_scene_phases.join(', ') || '-' },
      { label: 'Sorted tree sources', value: contract.sorted_tree_sources.join(', ') || '-' },
      { label: 'Recovery paths', value: Object.entries(contract.recovery_paths).map(([key, value]) => `${key}:${value}`).join(', ') || '-' },
      { label: 'Preview limitations', value: contract.preview_limitations.join(' ') || '-' },
    );
    for (const source of (contract.runtime_dynamic_source_details || []).slice(0, 6)) {
      rows.push({ label: `Dynamic source ${source.name}`, value: `${source.runtime_owner} | ${source.insertion_stage} | ${source.sorted_tree_types.join(', ') || 'direct draw'} | ${source.asset_backing} | ${source.preview_status}` });
    }
  }
  return rows;
}

function sceneSampledObjectRows(scene: SceneStats): InspectorRow[] {
  const recon = scene.reconnaissance || {};
  const objects = recon.sampled_objects || [];
  if (objects.length === 0) return [{ label: 'Sampled objects', value: 'No sampled scene objects are available.' }];
  const rows: InspectorRow[] = objects.slice(0, 12).map((object) => {
    const links = object.links;
    const linked = [
      links?.body?.asset_id ? `body ${links.body.asset_id}` : `gen body ${object.gen_body}`,
      links?.animation?.asset_id ? `anim ${links.animation.asset_id}` : `gen anim ${object.gen_anim}`,
      links?.sprite?.asset_id ? `sprite ${links.sprite.asset_id}` : `sprite ${object.sprite}`,
    ].join(' | ');
    const runtime = object.runtime ? ` | ${object.runtime.render_type}${object.runtime.render_pipeline ? ` ${object.runtime.render_pipeline.draw_path}` : ''}` : '';
    return {
      label: `Object ${object.index}`,
      value: `File3D ${object.file3d_index} | flags 0x${object.flags.toString(16).toUpperCase()} | ${object.position.x},${object.position.y},${object.position.z} | ${linked}${runtime}`,
      copyValue: `${scene.semantic_layout}:object:${object.index}`,
    };
  });
  const total = recon.sampled_object_count ?? objects.length;
  if (total > rows.length) rows.push({ label: 'Folded objects', value: `${total - rows.length} additional sampled objects remain in catalog evidence.` });
  return rows;
}

function sceneZoneTrackPatchRows(scene: SceneStats): InspectorRow[] {
  const recon = scene.reconnaissance || {};
  const rows: InspectorRow[] = [
    { label: 'Zones', value: `${recon.zone_count ?? 0}; types ${formatCounts(recon.zone_type_counts) || '-'}` },
    { label: 'Zone runtime contracts', value: formatCounts(recon.zone_runtime_contract_counts) || '-' },
    { label: 'GRM fragment links', value: formatCounts(recon.grm_fragment_link_counts) || '-' },
    { label: 'Tracks', value: String(recon.track_count ?? 0) },
    { label: 'Patches', value: `${recon.patch_count ?? 0}; sizes ${formatCounts(recon.patch_size_counts) || '-'}` },
    { label: 'Patch targets', value: formatCounts(recon.patch_target_counts) || '-' },
  ];
  for (const zone of (recon.sampled_zones || []).slice(0, 6)) {
    rows.push({ label: `Zone ${zone.index}`, value: `${zone.type_name} value ${zone.value}, ${zone.start.x},${zone.start.y},${zone.start.z} -> ${zone.end.x},${zone.end.y},${zone.end.z}` });
  }
  for (const link of (recon.grm_fragment_links || []).slice(0, 6)) {
    rows.push({ label: `GRM zone ${link.zone_index}`, value: `value ${link.zone_value}, GRM ${link.grm_index}, asset ${link.asset_id || '-'}`, copyValue: link.asset_id || undefined });
  }
  for (const track of (recon.sampled_tracks || []).slice(0, 6)) {
    rows.push({ label: `Track ${track.index}`, value: `${track.position.x},${track.position.y},${track.position.z}` });
  }
  return rows;
}

function scriptOpcodeSummary(script?: SceneScriptAnalysis): string {
  const opcodes = script?.unique_opcodes || [];
  if (opcodes.length === 0) return '-';
  return opcodes.slice(0, 10).map((opcode) => opcode.mnemonic).join(', ') + (opcodes.length > 10 ? `, +${opcodes.length - 10}` : '');
}

function scriptBehaviorSummary(script?: SceneScriptAnalysis): string {
  const categories = script?.behavior_categories || [];
  if (categories.length === 0) return '-';
  return categories.slice(0, 8).map((item) => `${item.category}:${item.count}`).join(', ') + (categories.length > 8 ? `, +${categories.length - 8}` : '');
}

export class InspectorRenderer {
  private sections: InspectorSection[] = [];

  constructor(
    private readonly container: HTMLElement,
    private readonly search: HTMLInputElement,
  ) {
    this.search.addEventListener('input', () => this.render());
  }

  setSections(sections: InspectorSection[]): void {
    this.sections = sections;
    this.render();
  }

  clear(message: string): void {
    this.sections = [];
    this.container.textContent = message;
  }

  private render(): void {
    const query = this.search.value.trim().toLowerCase();
    const matchingSections = query
      ? this.sections.filter((section) => section.searchText.includes(query))
      : this.sections;
    if (this.sections.length === 0) {
      this.container.textContent = 'Select a catalog entry to inspect it.';
      return;
    }
    if (matchingSections.length === 0) {
      this.container.textContent = `No inspector rows match "${this.search.value.trim()}".`;
      return;
    }

    const summary = document.createElement('div');
    summary.className = 'inspector-match-summary';
    summary.textContent = query
      ? `Showing ${matchingSections.length} of ${this.sections.length} sections matching "${this.search.value.trim()}".`
      : `${this.sections.length} structured inspector sections.`;
    this.container.replaceChildren(summary, ...matchingSections.map((section) => renderSection(section, query)));
  }
}

function renderSection(section: InspectorSection, query: string): HTMLElement {
  const details = document.createElement('details');
  details.className = 'inspector-section';
  details.open = query.length > 0 || section.defaultOpen;
  details.dataset.sectionId = section.id;
  const summary = document.createElement('summary');
  const title = document.createElement('strong');
  title.textContent = section.title;
  summary.append(title);
  if (section.status) summary.append(statusPill(section.status));
  details.append(summary);

  const rows = document.createElement('div');
  rows.className = 'inspector-rows';
  rows.replaceChildren(...section.rows.map(renderRow));
  details.append(rows);

  if (section.actions?.length) {
    const actions = document.createElement('div');
    actions.className = 'inspector-actions';
    actions.replaceChildren(...section.actions.map(renderAction));
    details.append(actions);
  }
  return details;
}

function renderRow(row: InspectorRow): HTMLElement {
  const item = document.createElement('div');
  item.className = 'inspector-row';
  const label = document.createElement('span');
  label.textContent = row.label;
  const value = document.createElement('strong');
  if (row.status) {
    value.append(statusPill(row.status));
  } else {
    value.textContent = row.value;
  }
  item.append(label, value);
  if (row.copyValue) {
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'inspector-copy';
    copy.textContent = 'Copy';
    copy.addEventListener('click', () => void copyText(row.copyValue || row.value));
    item.append(copy);
  }
  return item;
}

function renderAction(action: InspectorAction): HTMLElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = action.label;
  if (action.copyValue) button.addEventListener('click', () => void copyText(action.copyValue || ''));
  return button;
}

function statusPill(status: string): HTMLElement {
  const pill = document.createElement('span');
  pill.className = 'evidence-status';
  pill.dataset.status = status;
  pill.textContent = status;
  return pill;
}

function usageRows(usages: SceneAssetUsage[]): InspectorRow[] {
  if (usages.length === 0) {
    return [{ label: 'Known usages', value: 'No scene usage is known for this model.' }];
  }
  const rows: InspectorRow[] = usages.slice(0, 12).map((usage) => ({
    label: `${usage.scene_label} object ${usage.object_index}`,
    value: [
      usage.kind,
      usage.resolution_rule,
      usage.generic_name,
      usage.position ? `${usage.position.x},${usage.position.y},${usage.position.z}` : '',
    ].filter(Boolean).join(' | '),
    copyValue: `${usage.scene_asset_id}#object:${usage.object_index}`,
  }));
  if (usages.length > rows.length) {
    rows.push({ label: 'Folded usages', value: `${usages.length - rows.length} additional scene usages remain in catalog evidence.` });
  }
  return rows;
}

function directReferenceRows(references: DirectCodeReference[]): InspectorRow[] {
  const rows: InspectorRow[] = references.slice(0, 8).map((reference) => ({
    label: reference.symbol,
    value: `${reference.purpose} | ${reference.source}`,
    copyValue: reference.symbol,
  }));
  if (references.length > rows.length) {
    rows.push({ label: 'Folded references', value: `${references.length - rows.length} additional source references are folded.` });
  }
  return rows;
}

function spriteRuntimeRows(sprite: SpriteFrameStats): InspectorRow[] {
  const runtime = sprite.runtime;
  if (!runtime) return [{ label: 'Runtime reference', value: 'No runtime sprite reference is attached to this frame.' }];
  const rows: InspectorRow[] = [
    { label: 'Backend', value: runtime.backend },
    { label: 'Archive', value: runtime.archive },
    { label: 'Runtime sprite index', value: String(runtime.runtime_sprite_index) },
    { label: 'Index rule', value: runtime.index_rule },
    { label: 'Resolved asset', value: runtime.asset_id || '-', copyValue: runtime.asset_id },
  ];
  if (runtime.flags !== undefined) rows.push({ label: 'Flags', value: `0x${runtime.flags.toString(16).toUpperCase()}` });
  if (runtime.sprite_index !== undefined) rows.push({ label: 'Sprite index', value: String(runtime.sprite_index) });
  if (runtime.flags_decoded) {
    rows.push({ label: 'Flags decoded', value: Object.entries(runtime.flags_decoded).map(([key, enabled]) => `${key}:${enabled}`).join(', ') });
  }
  if (runtime.hotspot) rows.push({ label: 'Hotspot', value: `${runtime.hotspot.x}, ${runtime.hotspot.y}` });
  if (runtime.bounds) {
    rows.push({
      label: 'Bounds',
      value: `x ${runtime.bounds.min_x}..${runtime.bounds.max_x}, y ${runtime.bounds.min_y}..${runtime.bounds.max_y}, z ${runtime.bounds.min_z}..${runtime.bounds.max_z}`,
    });
  }
  if (runtime.bounds_source) rows.push({ label: 'Bounds source', value: `${runtime.bounds_source.hqr}:${runtime.bounds_source.entry_index}` });
  return rows;
}

function unknownDescriptorRows(descriptors: RawAnimationStats['unknown_descriptors']): InspectorRow[] {
  return descriptors.map((descriptor) => ({
    label: `${descriptor.section} @ ${descriptor.offset}`,
    value: `${descriptor.length} bytes | ${descriptor.confidence} | ${descriptor.note}`,
    copyValue: descriptor.sha256,
  }));
}

function sampledTextRecordRows(resource: ResourceStats): InspectorRow[] {
  const records = resource.sampled_records || [];
  if (records.length === 0) return [{ label: 'Sampled records', value: 'No sampled text records are available.' }];
  const rows: InspectorRow[] = records.slice(0, 12).map((record) => ({
    label: `Record ${record.index}`,
    value: [
      `flag ${record.flag ?? '-'}`,
      `offset ${record.offset ?? '-'}`,
      `${record.byte_length ?? '-'} bytes`,
      record.page_break_count === undefined ? '' : `${record.page_break_count} page breaks`,
      record.preview || '',
    ].filter(Boolean).join(' | '),
  }));
  if (records.length > rows.length) {
    rows.push({ label: 'Folded records', value: `${records.length - rows.length} additional sampled records remain in catalog evidence.` });
  }
  return rows;
}

function isPaletteImageLayout(layout: string): boolean {
  return layout === 'lba2_palette'
    || layout === 'screen_palette'
    || layout === 'xpl_palette_bundle'
    || layout === 'lba2_texture_atlas_indexed'
    || layout === 'lba2_indexed_image_256'
    || layout === 'screen_indexed_image_640x480';
}

function paletteImagePrimarySection(resource: ResourceStats): InspectorSection {
  if (resource.semantic_layout === 'lba2_palette' || resource.semantic_layout === 'screen_palette' || resource.semantic_layout === 'xpl_palette_bundle') {
    const header = resource.header || {};
    const rows: InspectorRow[] = [
      { label: 'Layout', value: resource.semantic_layout },
      { label: 'Colors', value: String(resource.color_count ?? '-') },
      { label: 'Transparent index', value: String(resource.transparent_index ?? '-') },
      { label: 'Sample colors', value: formatColorSample(resource.sample_colors) || '-' },
    ];
    if (resource.semantic_layout === 'screen_palette') {
      rows.push(
        { label: 'Screen', value: resource.screen_name || '-' },
        { label: 'Pair base', value: String(resource.screen_pair_base ?? '-') },
        { label: 'Paired image entry', value: String(resource.paired_entry_index ?? '-') },
      );
    }
    if (resource.semantic_layout === 'xpl_palette_bundle') {
      rows.push(
        { label: 'XPL name', value: resource.xpl_name || '-' },
        { label: 'Palette offset', value: String(header.offset_palette ?? '-') },
        { label: 'Fog offset', value: String(header.offset_fog ?? '-') },
        { label: 'Transparency offset', value: String(header.offset_transparency ?? '-') },
        { label: 'Shade range', value: `${header.shade_start_percent ?? '-'}..${header.shade_end_percent ?? '-'}` },
        { label: 'Shade normal', value: String(header.shade_normal_level ?? '-') },
        { label: 'Fog color', value: String(header.fog_color ?? '-') },
      );
    }
    return {
      id: 'palette',
      title: 'Palette',
      rows,
      defaultOpen: true,
      searchText: '',
    };
  }

  return {
    id: 'indexed_image',
    title: 'Indexed Image',
    rows: [
      { label: 'Layout', value: resource.semantic_layout },
      { label: 'Dimensions', value: `${resource.width ?? '-'}x${resource.height ?? '-'}` },
      { label: 'Offset', value: `${resource.offset_x ?? '-'}, ${resource.offset_y ?? '-'}` },
      { label: 'Pixel count', value: String(resource.pixel_count ?? '-') },
      { label: 'Opaque pixels', value: String(resource.opaque_pixels ?? '-') },
      { label: 'Transparent pixels', value: String(resource.transparent_pixels ?? '-') },
      { label: 'Unique palette indices', value: String(resource.unique_palette_indices ?? '-') },
      { label: 'Format', value: resource.format || '-' },
      { label: 'Run type counts', value: formatCounts(resource.run_type_counts) || '-' },
      { label: 'Max row run count', value: String(resource.max_row_run_count ?? '-') },
      { label: 'Palette index sample', value: (resource.palette_indices || []).slice(0, 32).join(', ') || '-' },
    ],
    defaultOpen: true,
    searchText: '',
  };
}

function paletteContextSection(asset: CatalogAsset, resource: ResourceStats): InspectorSection {
  const paletteEntry = resource.palette_entry ? `${resource.palette_entry.hqr}:${resource.palette_entry.entry_index}` : '-';
  return {
    id: 'palette_context',
    title: 'Palette Context',
    rows: [
      { label: 'Palette source', value: paletteEntry, copyValue: resource.palette_entry ? paletteEntry : undefined },
      { label: 'Source provenance', value: resource.source_provenance || '-' },
      { label: 'Runtime reference', value: resource.runtime_reference_status || '-' },
      { label: 'Scene palette references', value: String(resource.scene_palette_reference_count ?? '-') },
      { label: 'Screen pair base', value: String(resource.screen_pair_base ?? '-') },
      { label: 'Paired entry', value: resource.paired_entry_index === undefined ? '-' : `${asset.source.hqr}:${resource.paired_entry_index}` },
    ],
    defaultOpen: Boolean(resource.palette_entry || resource.source_provenance || resource.runtime_reference_status || resource.scene_palette_reference_count),
    searchText: '',
  };
}

function formatColorSample(colors?: number[]): string {
  return (colors || [])
    .slice(0, 24)
    .map((color) => `#${Number(color).toString(16).padStart(6, '0')}`)
    .join(', ');
}

function isRuntimeTableLayout(layout: string): boolean {
  return layout === 'file3d_table'
    || layout === 'sprite_zv_table'
    || layout === 'ress_offset_record_table'
    || layout === 'ress_fixed_s16x8_table'
    || layout === 'ress_ext_size_info'
    || layout === 'acf_name_list';
}

function runtimeTablePrimarySection(resource: ResourceStats): InspectorSection {
  if (resource.semantic_layout === 'file3d_table') {
    return {
      id: 'file3d_table',
      title: 'File3D Table',
      rows: [
        { label: 'Objects', value: String(resource.object_count ?? '-') },
        { label: 'Body references', value: String(resource.body_reference_count ?? '-') },
        { label: 'Animation references', value: String(resource.animation_reference_count ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    };
  }
  if (resource.semantic_layout === 'sprite_zv_table') {
    return {
      id: 'sprite_zv_table',
      title: 'Sprite Bounds Table',
      rows: [
        { label: 'Backend', value: resource.backend || '-' },
        { label: 'Records', value: String(resource.record_count ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    };
  }
  if (resource.semantic_layout === 'ress_ext_size_info') {
    return {
      id: 'exterior_size_info',
      title: 'Exterior Size Info',
      rows: [
        { label: 'List decors max', value: String(resource.max_size_list_decors ?? '-') },
        { label: 'Body decors max', value: String(resource.max_size_body_decors ?? '-') },
        { label: 'Texture defs max', value: String(resource.max_size_tex_def ?? '-') },
        { label: 'Total body decors max', value: String(resource.max_total_body_decors ?? '-') },
      ],
      defaultOpen: true,
      searchText: '',
    };
  }
  if (resource.semantic_layout === 'acf_name_list') {
    return {
      id: 'acf_name_list',
      title: 'ACF Name List',
      rows: [
        { label: 'Names', value: String(resource.entry_count ?? '-') },
        { label: 'Sampled names', value: (resource.sampled_names || []).slice(0, 16).join(', ') || '-' },
      ],
      defaultOpen: true,
      searchText: '',
    };
  }
  return {
    id: 'runtime_table',
    title: 'Runtime Table',
    rows: [
      { label: 'Layout', value: resource.semantic_layout },
      { label: 'Table name', value: resource.runtime_table_name || '-' },
      { label: 'Runtime buffer', value: resource.runtime_buffer || '-' },
      { label: 'Purpose', value: resource.runtime_purpose || '-' },
      { label: 'Source provenance', value: resource.source_provenance || '-' },
      { label: 'Runtime reference', value: resource.runtime_reference_status || '-' },
      { label: 'Records', value: String(resource.record_count ?? '-') },
      { label: 'Record bytes', value: String(resource.record_bytes ?? '-') },
      { label: 'Offset table bytes', value: String(resource.offset_table_bytes ?? '-') },
      { label: 'Record length counts', value: formatCounts(resource.record_length_counts) || '-' },
    ],
    defaultOpen: true,
    searchText: '',
  };
}

function runtimeTableSampleRows(resource: ResourceStats): InspectorRow[] {
  if (resource.semantic_layout === 'file3d_table') {
    const objects = resource.sampled_objects || [];
    if (objects.length === 0) return [{ label: 'Sampled objects', value: 'No sampled File3D objects are available.' }];
    return objects.slice(0, 12).map((object) => ({
      label: `File3D ${object.index}`,
      value: `${object.body_records.length} body records | ${object.animation_records.length} animation records | ${object.command_count} commands`,
    }));
  }
  if (resource.semantic_layout === 'acf_name_list') {
    const names = resource.sampled_names || [];
    if (names.length === 0) return [{ label: 'Sampled names', value: 'No sampled ACF names are available.' }];
    return names.slice(0, 16).map((name, index) => ({
      label: `Name ${index}`,
      value: name,
    }));
  }
  if (resource.semantic_layout === 'ress_ext_size_info') {
    return [{ label: 'Sampled records', value: 'Exterior size info is a fixed four-field record.' }];
  }
  const records = resource.sampled_records || [];
  if (records.length === 0) return [{ label: 'Sampled records', value: 'No sampled records are available.' }];
  const rows: InspectorRow[] = records.slice(0, 12).map((record) => ({
    label: record.backend ? `${record.backend} ${record.index}` : `Record ${record.index}`,
    value: runtimeTableRecordValue(record),
    copyValue: record.sha256,
  }));
  if (records.length > rows.length) {
    rows.push({ label: 'Folded records', value: `${records.length - rows.length} additional sampled records remain in catalog evidence.` });
  }
  return rows;
}

function runtimeTableRecordValue(record: NonNullable<ResourceStats['sampled_records']>[number]): string {
  const parts = [
    record.offset === undefined ? '' : `offset ${record.offset}`,
    record.byte_length === undefined ? '' : `${record.byte_length} bytes`,
    record.hotspot ? `hotspot ${record.hotspot.x},${record.hotspot.y}` : '',
    record.bounds ? `bounds x ${record.bounds.min_x}..${record.bounds.max_x}, y ${record.bounds.min_y}..${record.bounds.max_y}, z ${record.bounds.min_z}..${record.bounds.max_z}` : '',
    record.values ? `values ${record.values.join(', ')}` : '',
    record.preview_hex ? `hex ${record.preview_hex}` : '',
  ].filter(Boolean);
  return parts.join(' | ') || '-';
}

function isHolomapLayout(layout: string): boolean {
  return layout === 'holomap_globe_uv_map'
    || layout === 'holomap_globe_altitude_map'
    || layout === 'holomap_globe_texture_map'
    || layout === 'holomap_arrow_table'
    || layout === 'holomap_plan_image_640x480'
    || layout === 'holomap_plan_view_params';
}

function holomapPrimarySection(resource: ResourceStats, asset: CatalogAsset): InspectorSection {
  const variant = resource.plan_variant;
  const rows: InspectorRow[] = [
    { label: 'Layout', value: resource.semantic_layout },
    { label: 'Holomap', value: resource.holomap_name || '-' },
    { label: 'Source provenance', value: resource.source_provenance || '-' },
  ];
  if (resource.width !== undefined || resource.height !== undefined) rows.push({ label: 'Dimensions', value: `${resource.width ?? '-'}x${resource.height ?? '-'}` });
  if (resource.pixel_count !== undefined) rows.push({ label: 'Samples', value: String(resource.pixel_count) });
  if (resource.record_count !== undefined) rows.push({ label: 'Records', value: String(resource.record_count) });
  if (resource.record_bytes !== undefined) rows.push({ label: 'Record bytes', value: String(resource.record_bytes) });
  if (resource.unique_palette_indices !== undefined) rows.push({ label: 'Unique values/indices', value: String(resource.unique_palette_indices) });
  if (resource.active_count !== undefined) rows.push({ label: 'Active arrows', value: String(resource.active_count) });
  if (resource.exterior_count !== undefined) rows.push({ label: 'Exterior arrows', value: String(resource.exterior_count) });
  if (resource.message_count !== undefined) rows.push({ label: 'Messages', value: String(resource.message_count) });
  if (resource.text_link_counts) rows.push({ label: 'Text link counts', value: formatCounts(resource.text_link_counts) || '-' });
  if (resource.paired_entry_index !== undefined) rows.push({ label: 'Paired entry', value: `${asset.source.hqr}:${resource.paired_entry_index}` });
  if (variant) {
    rows.push(
      { label: 'Plan variant', value: String(variant.variant_index) },
      { label: 'Selected island', value: String(variant.selected_island) },
      { label: 'Selection condition', value: variant.selection_condition },
      { label: 'Selection rule', value: variant.selection_rule },
      { label: 'Entry role', value: variant.entry_role },
      { label: 'Render path', value: variant.render_path },
      { label: 'Image entry', value: `${asset.source.hqr}:${variant.image_entry_index}` },
      { label: 'Params entry', value: `${asset.source.hqr}:${variant.params_entry_index}` },
    );
  }
  if (resource.fields) {
    for (const [key, value] of Object.entries(resource.fields).slice(0, 12)) {
      rows.push({ label: key, value: String(value) });
    }
  }
  return {
    id: 'holomap',
    title: 'Holomap',
    rows,
    defaultOpen: true,
    searchText: '',
  };
}

function holomapSampleRows(resource: ResourceStats): InspectorRow[] {
  const records = resource.sampled_records || [];
  if (records.length === 0) return [{ label: 'Sampled records', value: 'No sampled holomap records are available.' }];
  const rows: InspectorRow[] = records.slice(0, 12).map((record) => ({
    label: `Record ${record.index}`,
    value: [
      record.message === undefined ? '' : `message ${record.message}`,
      record.objfix === undefined ? '' : `objfix ${record.objfix}`,
      record.flag_holo === undefined ? '' : `flag ${record.flag_holo}`,
      record.planet === undefined ? '' : `planet ${record.planet}`,
      record.island === undefined ? '' : `island ${record.island}`,
      record.offset === undefined ? '' : `offset ${record.offset}`,
      record.values ? `values ${record.values.join(', ')}` : '',
    ].filter(Boolean).join(' | ') || compactJson(record),
  }));
  if (records.length > rows.length) {
    rows.push({ label: 'Folded records', value: `${records.length - rows.length} additional sampled records remain in catalog evidence.` });
  }
  return rows;
}

function holomapTextLinkRows(resource: ResourceStats): InspectorRow[] {
  const links = resource.text_links || [];
  if (links.length === 0) return [{ label: 'Text links', value: 'No holomap text links are attached.' }];
  const rows: InspectorRow[] = links.slice(0, 8).map((link) => ({
    label: `Message ${link.message_id}`,
    value: [
      `file ${link.text_file_name}`,
      `arrows ${link.arrow_indices.slice(0, 8).join(', ')}`,
      `${link.localized_records} localized records`,
      ...link.localized_links.slice(0, 2).map((localized) => `${localized.language || '-'}: ${localized.preview || ''}`),
    ].join(' | '),
    copyValue: String(link.message_id),
  }));
  if (links.length > rows.length) {
    rows.push({ label: 'Folded links', value: `${links.length - rows.length} additional holomap text links remain in catalog evidence.` });
  }
  return rows;
}

function isBackgroundLayout(layout: string): boolean {
  return layout === 'bkg_header'
    || layout === 'bkg_grid_map'
    || layout === 'bkg_grm_fragment'
    || layout === 'bkg_block_table'
    || layout === 'bkg_brick_graphic'
    || layout === 'bkg_cube_map';
}

function backgroundPrimarySection(resource: ResourceStats): InspectorSection {
  const rows: InspectorRow[] = [
    { label: 'Layout', value: resource.semantic_layout },
    { label: 'Role', value: resource.bkg_entry_role || '-' },
    { label: 'Relative index', value: String(resource.bkg_relative_index ?? '-') },
    { label: 'Source provenance', value: resource.source_provenance || '-' },
  ];
  if (resource.width !== undefined || resource.height !== undefined || resource.depth !== undefined) {
    rows.push({ label: 'Dimensions', value: `${resource.width ?? '-'}x${resource.height ?? '-'}x${resource.depth ?? '-'}` });
  }
  if (resource.record_count !== undefined) rows.push({ label: 'Records', value: String(resource.record_count) });
  if (resource.record_bytes !== undefined) rows.push({ label: 'Record bytes', value: String(resource.record_bytes) });
  if (resource.offset_table_bytes !== undefined) rows.push({ label: 'Offset table bytes', value: String(resource.offset_table_bytes) });
  if (resource.encoded_bytes_consumed !== undefined) rows.push({ label: 'Encoded bytes consumed', value: String(resource.encoded_bytes_consumed) });
  if (resource.opaque_pixels !== undefined) rows.push({ label: 'Opaque pixels', value: String(resource.opaque_pixels) });
  if (resource.transparent_pixels !== undefined) rows.push({ label: 'Transparent pixels', value: String(resource.transparent_pixels) });
  if (resource.color_count !== undefined) rows.push({ label: 'Palette indices', value: String(resource.color_count) });
  if (resource.run_type_counts) rows.push({ label: 'Run type counts', value: formatCounts(resource.run_type_counts) || '-' });
  if (resource.type_counts) rows.push({ label: 'Type counts', value: formatCounts(resource.type_counts) || '-' });
  if (resource.fields) {
    for (const [key, value] of Object.entries(resource.fields).slice(0, 16)) {
      rows.push({ label: key, value: String(value) });
    }
  }
  return {
    id: 'background',
    title: 'Background',
    rows,
    defaultOpen: true,
    searchText: '',
  };
}

function backgroundCompositionRows(resource: ResourceStats): InspectorRow[] {
  const rows: InspectorRow[] = [];
  const composition = resource.composition;
  if (composition) {
    if (composition.dimensions) rows.push({ label: 'Cube dimensions', value: `${composition.dimensions.x}x${composition.dimensions.y}x${composition.dimensions.z}` });
    if (composition.cell_count !== undefined) rows.push({ label: 'Cells', value: String(composition.cell_count) });
    if (composition.occupied_block_cells !== undefined) rows.push({ label: 'Occupied block cells', value: String(composition.occupied_block_cells) });
    if (composition.transparent_code_cells !== undefined) rows.push({ label: 'Transparent code cells', value: String(composition.transparent_code_cells) });
    if (composition.unique_block_ref_count !== undefined) rows.push({ label: 'Unique block refs', value: String(composition.unique_block_ref_count) });
    if (composition.active_columns !== undefined) rows.push({ label: 'Active columns', value: String(composition.active_columns) });
    if (composition.empty_columns !== undefined) rows.push({ label: 'Empty columns', value: String(composition.empty_columns) });
    if (composition.run_type_counts) rows.push({ label: 'Column run types', value: formatCounts(composition.run_type_counts) || '-' });
    if (composition.max_column_entities !== undefined) rows.push({ label: 'Max column entities', value: String(composition.max_column_entities) });
    if (composition.max_column_stream_bytes !== undefined) rows.push({ label: 'Max column stream bytes', value: String(composition.max_column_stream_bytes) });
  }
  if (resource.composition_payload) {
    const payload = resource.composition_payload;
    rows.push(
      { label: 'Payload format', value: payload.format },
      { label: 'Payload cells', value: String(payload.cell_count) },
      { label: 'Payload order', value: payload.cell_order },
      { label: 'Payload provenance', value: payload.source_provenance },
    );
  }
  if (resource.preview) {
    const preview = resource.preview;
    rows.push(
      { label: 'Preview', value: `${preview.width}x${preview.height}` },
      { label: 'Preview evidence', value: `${preview.drawn_cells} cells | ${preview.drawn_pixels} pixels | ${preview.unique_bricks_loaded} BRKs` },
      { label: 'Preview misses', value: `missing ${preview.missing_bricks}, skipped forbidden ${preview.skipped_forbidden}` },
      { label: 'Preview palette', value: preview.palette_source },
      { label: 'Preview provenance', value: preview.source_provenance },
    );
  }
  if (rows.length === 0) return [{ label: 'Composition', value: 'No composition payload is attached to this background resource.' }];
  return rows;
}

function backgroundSampleRows(resource: ResourceStats): InspectorRow[] {
  if ((resource.sampled_occupied_cells || []).length > 0) {
    return (resource.sampled_occupied_cells || []).slice(0, 12).map((cell) => ({
      label: `Column ${cell.column}`,
      value: `xyz ${cell.x},${cell.y},${cell.z} | block ${cell.block_ref} slot ${cell.cell_slot} | BLL ${cell.resolved_bll_entry ?? '-'} | valid ${cell.block_ref_valid ?? '-'} / ${cell.cell_slot_valid ?? '-'}`,
    }));
  }
  if ((resource.sampled_cell_refs || []).length > 0) {
    return (resource.sampled_cell_refs || []).slice(0, 12).map((cell) => ({
      label: `Block ${cell.block} cell ${cell.cell}`,
      value: `xyz ${cell.x},${cell.y},${cell.z} | brick ${cell.brick_ref} -> BRK ${cell.resolved_brk_entry} | collision ${cell.collision} code ${cell.code} raw ${cell.code_raw}`,
    }));
  }
  const records = resource.sampled_records || [];
  if (records.length === 0) return [{ label: 'Sampled records', value: 'No sampled background records are available.' }];
  const rows: InspectorRow[] = records.slice(0, 12).map((record) => ({
    label: `Record ${record.index}`,
    value: [
      record.dx === undefined ? '' : `${record.dx}x${record.dy ?? '-'}x${record.dz ?? '-'}`,
      record.cell_count === undefined ? '' : `${record.cell_count} cells`,
      record.nonzero_brick_refs === undefined ? '' : `${record.nonzero_brick_refs} brick refs`,
      record.max_brick_ref === undefined ? '' : `max brick ${record.max_brick_ref}`,
      record.type === undefined ? '' : `type ${record.type}`,
      record.num === undefined ? '' : `num ${record.num}`,
      record.resolved_gri_entry === undefined ? '' : `GRI ${record.resolved_gri_entry}`,
      record.resolved_bll_entry === undefined ? '' : `BLL ${record.resolved_bll_entry}`,
      record.resolved_grm_entry === undefined ? '' : `GRM ${record.resolved_grm_entry}`,
      record.used_block_count === undefined ? '' : `used blocks ${record.used_block_count}`,
    ].filter(Boolean).join(' | ') || '-',
  }));
  if (records.length > rows.length) {
    rows.push({ label: 'Folded records', value: `${records.length - rows.length} additional sampled records remain in catalog evidence.` });
  }
  return rows;
}

function workflowEntrypoint(workflow?: EntityWorkflowPayload): string {
  if (!workflow) return '-';
  const entrypoint = workflow.entrypoint;
  if (entrypoint.kind === 'runtime_sprite') {
    return [
      'runtime_sprite',
      entrypoint.flags === undefined ? null : `flags 0x${entrypoint.flags.toString(16).toUpperCase()}`,
      entrypoint.sprite_index === undefined ? null : `sprite ${entrypoint.sprite_index}`,
      entrypoint.object_index === undefined || entrypoint.object_index === null ? null : `object ${entrypoint.object_index}`,
      entrypoint.body_num === undefined || entrypoint.body_num === null ? null : `Body.Num ${entrypoint.body_num}`,
    ].filter(Boolean).join(' | ');
  }
  return [entrypoint.kind, entrypoint.asset_id, entrypoint.label].filter(Boolean).join(' | ') || '-';
}

function renderContractRows(entity: EntityContract): InspectorRow[] {
  const contract = entity.render_contract;
  const rows: InspectorRow[] = [
    { label: 'Backend', value: entity.render_backend },
    { label: 'Draw path', value: contract.draw_path || '-' },
    { label: 'Sorted insertion', value: contract.sort_key || '-' },
    { label: 'Recovery path', value: contract.recovery_path || '-' },
    { label: 'Steps', value: contract.contract_steps.join(', ') || '-' },
    { label: 'Source', value: contract.source || '-' },
  ];
  if (contract.render_phase) rows.push({ label: 'Render phase', value: renderPhaseSummary(contract.render_phase) });
  if (contract.redraw_contract) rows.push({ label: 'Redraw contract', value: redrawContractSummary(contract.redraw_contract) });
  return rows;
}

function renderPhaseSummary(phase: Record<string, unknown>): string {
  return [
    textPart('Scene redraw setup', phase.scene_redraw_setup),
    textPart('Background object skip', phase.object_only_background_skip_rule),
    textPart('Invisible/bodyless skip', phase.invisible_or_bodyless_skip_before_tree),
    textPart('Camera preclip', phase.camera_preclip_before_tree),
    textPart('Tree insert', phase.tree_insert),
    textPart('Shadow', phase.shadow),
  ].filter(Boolean).join(' | ') || '-';
}

function redrawContractSummary(contract: Record<string, unknown>): string {
  return [
    textPart('Method', contract.method),
    textPart('Anchor', contract.anchor),
    boolPart('Moving box', contract.moving_box),
    boolPart('Draw over brick cage', contract.draw_over_brick_cage),
    boolPart('Z-buffer/water flag', contract.zbuffer_or_water_flag_present),
    boolPart('Z-buffer/water effective', contract.zbuffer_or_water_effective),
    boolPart('Sprite clip info rect', contract.sprite_clip_info_rect),
    boolPart('Camera recenter on full mask', contract.camera_recenter_on_full_mask),
  ].filter(Boolean).join(' | ') || '-';
}

function textPart(label: string, value: unknown): string | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  return `${label}: ${String(value)}`;
}

function boolPart(label: string, value: unknown): string | undefined {
  if (typeof value !== 'boolean') return textPart(label, value);
  return `${label}: ${value ? 'yes' : 'no'}`;
}

function facetTitle(kind: AppSelection['kind']): string {
  if (kind === 'runtime_sprite_state') return 'Runtime Sprite State';
  if (kind === 'file3d_resolution') return 'File3D Resolution';
  if (kind === 'anim3ds_range_state') return 'ANIM3DS Range State';
  if (kind === 'render_contract') return 'Render Contract';
  if (kind === 'palette_context') return 'Palette Context';
  return 'Facet';
}

function scriptLinkRows(prefix: string, links: Array<Record<string, unknown>>): InspectorRow[] {
  return links.slice(0, 6).map((link, index) => ({
    label: `${prefix} ${index + 1}`,
    value: compactJson(link),
    copyValue: typeof link.asset_id === 'string' ? link.asset_id : undefined,
  }));
}

function sceneObjectUnknownRows(entity: EntityContract, workflow?: EntityWorkflowPayload): InspectorRow[] {
  const rows: InspectorRow[] = [
    ...(workflow?.unknowns || []).map((unknown) => ({
      label: `Workflow ${unknown.field}`,
      value: `${unknown.status}: ${unknown.note}`,
    })),
    ...entity.unknowns.map((unknown) => ({
      label: unknown.field,
      value: `${unknown.status}: ${unknown.note}`,
    })),
  ];
  return rows.length ? rows : [{ label: 'Unknowns', value: 'No explicit unknowns on this scene object evidence.' }];
}

function uvEvidenceRows(polygon: NonNullable<AppSelection['evidence']>['polygon']): InspectorRow[] {
  if (!polygon) return [{ label: 'UV', value: 'No polygon evidence is attached.' }];
  const rows: InspectorRow[] = [];
  if (polygon.uv_group) {
    const group = polygon.uv_group;
    rows.push(
      { label: 'UV group', value: String(group.index) },
      { label: 'Encoded', value: `${group.encoded.x},${group.encoded.y} ${group.encoded.w}x${group.encoded.h}` },
      { label: 'Sampled region', value: group.sampled_region ? `${group.sampled_region.x},${group.sampled_region.y} ${group.sampled_region.width}x${group.sampled_region.height}` : '-' },
    );
  } else {
    rows.push({ label: 'UV group', value: 'none' });
  }
  rows.push(
    { label: 'UV coordinates', value: polygon.uv ? polygon.uv.map(([u, v]) => `${formatNumber(u)},${formatNumber(v)}`).join(' | ') : 'none' },
    { label: 'Atlas samples', value: polygon.sampled_atlas_points ? polygon.sampled_atlas_points.map((point) => `${formatNumber(point.x)},${formatNumber(point.y)} ${point.color}`).join(' | ') : 'none' },
  );
  return rows;
}

function formatPosition(position: EntityContract['position']): string {
  if (!position) return '-';
  return `${position.x}, ${position.y}, ${position.z}`;
}

function formatNullable(value: unknown): string {
  return value === null || value === undefined || value === '' ? '-' : String(value);
}

function formatHexNumber(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) ? `0x${value.toString(16).toUpperCase()}` : formatNullable(value);
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

function compactJson(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => compactJson(item)).join(', ');
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entry]) => `${key}: ${compactJson(entry)}`)
      .join(' | ') || '-';
  }
  return String(value);
}

function formatCounts(counts?: Record<string, number>): string {
  return Object.entries(counts || {})
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}:${value}`)
    .join(', ');
}

function sectionSearchText(section: InspectorSection): string {
  return [
    section.id,
    section.title,
    section.status,
    ...section.rows.flatMap((row) => [row.label, row.value, row.status]),
    ...(section.actions || []).map((action) => action.label),
  ].filter(Boolean).join(' ').toLowerCase();
}

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard can be unavailable on non-secure origins; visible IDs remain selectable.
  }
}
