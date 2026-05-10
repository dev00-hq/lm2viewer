import type { PolygonEvidence } from './ui/uvInspector';
import type { ResourceRecordEvidence } from './ui/resourceWorkspace';
import type { AnimationSequenceFrame, AnimationSequencePayload, CatalogAsset, CatalogGraphSelectionProjection, EntityContract, EntityWorkflowPayload, Lm2Model, ResourceStats, RuntimeSpriteResolvePayload, SceneAssetUsage, SpritePayload } from './types';

export type SelectionKind =
  | 'asset'
  | 'scene_usage'
  | 'runtime_resolution'
  | 'sprite_frame'
  | 'animation_sample'
  | 'model_surface'
  | 'resource_record'
  | 'evidence_artifact'
  | 'scene_object'
  | 'runtime_sprite_state'
  | 'file3d_resolution'
  | 'anim3ds_range_state'
  | 'render_contract'
  | 'palette_context';

export type EvidenceStatus =
  | 'source_backed'
  | 'decoded_only'
  | 'render_only'
  | 'live_confirmed'
  | 'port_implied'
  | 'unknown'
  | 'intentionally_deferred'
  | 'preview_only'
  | 'live_positive'
  | 'live_negative'
  | 'approved_exception';

export type EntityFacetSelectionKind =
  | 'runtime_sprite_state'
  | 'file3d_resolution'
  | 'anim3ds_range_state'
  | 'render_contract';

export interface SelectionSource {
  archive?: string;
  entryIndex?: number;
  classicIndex?: number;
  rawSha256?: string;
  decodedSha256?: string;
  relativePath?: string;
}

export interface SelectionLink {
  kind: SelectionKind | 'asset';
  stableId: string;
  label: string;
  proofScope?: string;
  evidenceStatus?: string;
  sourceRule?: string;
  sourceField?: string;
  indexRule?: string;
}

export interface SelectionAction {
  id: string;
  label: string;
  targetAssetId?: string;
}

export interface AppSelection {
  kind: SelectionKind;
  stableId: string;
  label: string;
  source?: SelectionSource;
  provenance: string;
  evidenceStatus: EvidenceStatus;
  links: SelectionLink[];
  unknowns: string[];
  previewActions: SelectionAction[];
  exportActions: SelectionAction[];
  compatibilityStatus?: string;
  workspaceSuggestion?: 'model' | 'sprite' | 'entity' | 'resource';
  inspectorRoute?: string;
  exportCapability?: {
    exportable: boolean;
    source?: string;
  };
  facets?: Record<string, string | number | boolean | null | undefined>;
  evidence?: {
    entityContract?: EntityContract;
    entityWorkflow?: EntityWorkflowPayload;
    animation?: CatalogAsset;
    animationBody?: CatalogAsset;
    animationFrame?: AnimationSequenceFrame;
    animationSequence?: AnimationSequencePayload;
    model?: Lm2Model;
    polygon?: PolygonEvidence;
    resourceAsset?: CatalogAsset;
    resourceRecord?: ResourceRecordEvidence;
    usageAsset?: CatalogAsset;
    sceneUsage?: SceneAssetUsage;
  };
}
type SelectionListener = (selection: AppSelection | null) => void;

export class AppSelectionStore {
  private selection: AppSelection | null = null;
  private listeners = new Set<SelectionListener>();

  get current(): AppSelection | null {
    return this.selection;
  }

  set(selection: AppSelection | null): void {
    this.selection = selection;
    for (const listener of this.listeners) listener(selection);
  }

  update(update: Partial<AppSelection>): void {
    if (!this.selection) return;
    this.set({ ...this.selection, ...update });
  }

  subscribe(listener: SelectionListener): () => void {
    this.listeners.add(listener);
    listener(this.selection);
    return () => this.listeners.delete(listener);
  }
}

export function selectionFromCatalogAsset(
  asset: CatalogAsset,
  options: {
    exportable?: boolean;
    workspaceSuggestion?: AppSelection['workspaceSuggestion'];
    compatibilityStatus?: string;
    graphSelection?: CatalogGraphSelectionProjection;
  } = {},
): AppSelection {
  if (options.graphSelection) {
    return selectionFromGraphProjection(options.graphSelection, options);
  }
  if (asset.kind === 'model' || asset.kind === 'resource') {
    throw new Error(`Missing graph selection projection for migrated ${asset.kind} asset ${asset.id}`);
  }
  return {
    kind: 'asset',
    stableId: asset.id,
    label: asset.label,
    source: sourceFromAsset(asset),
    provenance: provenanceForAsset(asset),
    evidenceStatus: evidenceStatusForAsset(asset),
    links: linksForAsset(asset),
    unknowns: unknownsForAsset(asset),
    previewActions: previewActionsForAsset(asset),
    exportActions: options.exportable ? [{ id: 'export_catalog_asset', label: 'Export evidence bundle', targetAssetId: asset.id }] : [],
    compatibilityStatus: options.compatibilityStatus,
    workspaceSuggestion: options.workspaceSuggestion ?? workspaceForAsset(asset),
    facets: facetsForAsset(asset),
  };
}
function selectionFromGraphProjection(
  projection: CatalogGraphSelectionProjection,
  options: {
    workspaceSuggestion?: AppSelection['workspaceSuggestion'];
    compatibilityStatus?: string;
  },
): AppSelection {
  return {
    kind: projection.kind as SelectionKind,
    stableId: projection.stableId,
    label: projection.label,
    source: projection.source,
    provenance: projection.provenance,
    evidenceStatus: projection.evidenceStatus as EvidenceStatus,
    links: projection.links.map((link) => ({
      kind: link.kind as SelectionKind | 'asset',
      stableId: link.stableId,
      label: link.label,
      proofScope: link.proofScope,
      evidenceStatus: link.evidenceStatus,
      sourceRule: link.sourceRule,
      sourceField: link.sourceField,
      indexRule: link.indexRule,
    })),
    unknowns: projection.unknowns,
    previewActions: projection.previewActions,
    exportActions: projection.exportActions,
    exportCapability: projection.exportCapability,
    inspectorRoute: projection.inspectorRoute,
    compatibilityStatus: options.compatibilityStatus || projection.compatibilityStatus,
    workspaceSuggestion: options.workspaceSuggestion || projection.workspaceSuggestion,
    facets: {
      ...projection.facets,
      graphNodeId: projection.facets?.graphNodeId || projection.nodeId,
    },
  };
}

function parentGraphLinks(
  asset: CatalogAsset | undefined,
  graphSelection?: CatalogGraphSelectionProjection,
): SelectionLink[] {
  const links: SelectionLink[] = asset ? [{ kind: 'asset', stableId: asset.id, label: asset.label }] : [];
  for (const link of graphSelection?.links || []) {
    if (links.some((existing) => existing.kind === link.kind && existing.stableId === link.stableId)) continue;
    links.push({
      kind: link.kind as SelectionKind | 'asset',
      stableId: link.stableId,
      label: link.label,
      proofScope: link.proofScope,
      evidenceStatus: link.evidenceStatus,
      sourceRule: link.sourceRule,
      sourceField: link.sourceField,
      indexRule: link.indexRule,
    });
  }
  return links;
}

export function selectionFromRuntimeResolution(payload: RuntimeSpriteResolvePayload): AppSelection {
  const resolution = payload.resolution;
  const stableId = [
    `runtime_sprite_state:flags=0x${payload.flags.toString(16).toUpperCase()}`,
    `sprite=${payload.sprite_index}`,
    payload.object_index === null || payload.object_index === undefined ? null : `object=${payload.object_index}`,
    payload.body_num === null || payload.body_num === undefined ? null : `body_num=${payload.body_num}`,
    payload.label_track === null || payload.label_track === undefined ? null : `label_track=${payload.label_track}`,
  ].filter(Boolean).join(';');
  return {
    kind: 'runtime_resolution',
    stableId,
    label: resolution.resolved ? `Runtime sprite -> ${resolution.asset_id || 'unresolved asset'}` : 'Runtime sprite unresolved',
    provenance: resolution.index_rule,
    evidenceStatus: resolution.resolved ? 'source_backed' : 'unknown',
    links: resolution.asset_id ? [{ kind: 'asset', stableId: resolution.asset_id, label: resolution.asset_id }] : [],
    unknowns: resolution.resolved ? [] : ['Runtime sprite did not resolve to a catalog-backed asset.'],
    previewActions: resolution.asset_id ? [{ id: 'open_resolved_asset', label: 'Open resolved asset', targetAssetId: resolution.asset_id }] : [],
    exportActions: [],
    workspaceSuggestion: 'entity',
    facets: {
      backend: resolution.backend,
      archive: resolution.archive,
      runtimeSpriteIndex: resolution.runtime_sprite_index,
      spriteIndex: payload.sprite_index,
      objectIndex: payload.object_index,
      bodyNum: payload.body_num,
      labelTrack: payload.label_track,
    },
  };
}

export function selectionFromSpriteFrame(
  asset: CatalogAsset,
  payload: SpritePayload,
  options: { graphSelection?: CatalogGraphSelectionProjection } = {},
): AppSelection {
  const frame = payload.frame;
  const stats = asset.stats;
  const runtime = 'semantic_layout' in stats && (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame')
    ? stats.runtime
    : undefined;
  const baseSelection = selectionFromCatalogAsset(asset, {
    graphSelection: options.graphSelection,
    workspaceSuggestion: 'sprite',
  });
  return {
    ...baseSelection,
    kind: 'sprite_frame',
    stableId: frame?.variant ? `${asset.id}#frame:${frame.variant}` : `${asset.id}#frame:${asset.source.entry_index}`,
    label: frame?.variant_label ? `${asset.label} ${frame.variant_label}` : asset.label,
    provenance: frame?.render_source || frame?.palette_source || provenanceForAsset(asset),
    evidenceStatus: frame?.format === 'bkg_grid_preview' || frame?.format === 'bkg_affgraph' ? 'render_only' : evidenceStatusForAsset(asset),
    links: [
      ...parentGraphLinks(asset, options.graphSelection),
      ...(runtime?.asset_id && runtime.asset_id !== asset.id ? [{ kind: 'asset' as const, stableId: runtime.asset_id, label: runtime.asset_id }] : []),
    ],
    facets: {
      frameVariant: frame?.variant,
      frameVariantLabel: frame?.variant_label,
      frameFormat: frame?.format,
      width: frame?.width,
      height: frame?.height,
      offsetX: frame?.offset_x,
      offsetY: frame?.offset_y,
      paletteSource: frame?.palette_source,
      backend: runtime?.backend,
      runtimeSpriteIndex: runtime?.runtime_sprite_index,
      graphNodeId: baseSelection.facets?.graphNodeId || options.graphSelection?.nodeId,
      relationshipLinkCount: baseSelection.facets?.relationshipLinkCount,
    },
    evidence: {
      usageAsset: asset,
    },
  };
}

export function selectionFromEntityWorkflow(workflow: EntityWorkflowPayload): AppSelection | null {
  const entity = workflow.selected_entity;
  if (!entity) return null;
  const unknowns = [
    ...workflow.unknowns.map((unknown) => `${unknown.field}: ${unknown.status} - ${unknown.note}`),
    ...entity.unknowns.map((unknown) => `${unknown.field}: ${unknown.status} - ${unknown.note}`),
  ];
  const linkedVisuals = entity.linked_visual_assets.map((link) => ({
    kind: 'asset' as const,
    stableId: link.asset_id,
    label: `${link.role}: ${link.asset_id}`,
  }));
  const resolvedAssetLink = workflow.resolved_asset && !linkedVisuals.some((link) => link.stableId === workflow.resolved_asset?.id)
    ? [{ kind: 'asset' as const, stableId: workflow.resolved_asset.id, label: `entrypoint: ${workflow.resolved_asset.id}` }]
    : [];
  const sourceAsset = entity.provenance.scene_asset;
  return {
    kind: 'scene_object',
    stableId: entity.entity_id,
    label: entity.label,
    source: {
      archive: sourceAsset?.source.hqr || 'SCENE.HQR',
      entryIndex: entity.scene_entry_index,
      classicIndex: sourceAsset?.source.classic_index,
    },
    provenance: entity.provenance.resolution_rule || entity.provenance.usage_class || entity.object_sample_status,
    evidenceStatus: entity.confidence === 'evidence' ? 'source_backed' : 'decoded_only',
    links: [
      { kind: 'asset', stableId: entity.scene_asset_id, label: entity.scene_asset_id },
      ...resolvedAssetLink,
      ...linkedVisuals,
    ],
    unknowns: Array.from(new Set(unknowns)),
    previewActions: entity.linked_visual_assets
      .filter((link) => link.asset_available !== false)
      .map((link) => ({ id: 'open_linked_visual_asset', label: `Open ${link.role}`, targetAssetId: link.asset_id })),
    exportActions: [],
    workspaceSuggestion: 'entity',
    compatibilityStatus: entity.confidence,
    facets: {
      sceneAssetId: entity.scene_asset_id,
      sceneIndex: entity.scene_index,
      objectIndex: entity.object_index,
      renderBackend: entity.render_backend,
      objectSampleStatus: entity.object_sample_status,
      usageKind: entity.provenance.usage_kind,
      usageClass: entity.provenance.usage_class,
      entrypointKind: workflow.entrypoint.kind,
      resolvedAssetId: workflow.resolved_asset?.id,
    },
    evidence: {
      entityContract: entity,
      entityWorkflow: workflow,
    },
  };
}

export function selectionFromModelSurface(
  model: Lm2Model,
  polygon: PolygonEvidence,
  options: { graphSelection?: CatalogGraphSelectionProjection } = {},
): AppSelection {
  const asset = model.catalog_asset;
  const assetId = asset?.id || model.source || 'uploaded_model';
  const material = `${polygon.material.kind} ${polygon.material.value}`;
  const graphExportActions = options.graphSelection?.exportActions || [];
  return {
    kind: 'model_surface',
    stableId: `${assetId}#polygon:${polygon.polygon_index}`,
    label: `${asset?.label || model.source || 'Model'} polygon ${polygon.polygon_index}`,
    source: asset ? sourceFromAsset(asset) : undefined,
    provenance: asset ? provenanceForAsset(asset) : model.source,
    evidenceStatus: asset ? evidenceStatusForAsset(asset) : 'decoded_only',
    links: parentGraphLinks(asset, options.graphSelection),
    unknowns: polygon.unknowns.map((unknown) => `${unknown.field}: ${unknown.note}`),
    previewActions: [],
    exportActions: graphExportActions,
    exportCapability: options.graphSelection?.exportCapability,
    workspaceSuggestion: 'model',
    facets: {
      assetId,
      polygonIndex: polygon.polygon_index,
      material,
      uvGroup: polygon.uv_group?.index,
      renderType: polygon.render_flags.render_type,
      hasTexture: polygon.render_flags.has_texture,
      hasTransparency: polygon.render_flags.has_transparency,
      vertexCount: polygon.vertices.length,
      graphNodeId: options.graphSelection?.facets?.graphNodeId || options.graphSelection?.nodeId,
      relationshipLinkCount: options.graphSelection?.facets?.relationshipLinkCount,
    },
    evidence: {
      model,
      polygon,
    },
  };
}

export function selectionFromAnimationSample(
  body: CatalogAsset,
  animation: CatalogAsset,
  sequence: AnimationSequencePayload,
  frame: AnimationSequenceFrame,
  loopCycle = 0,
  options: { graphSelection?: CatalogGraphSelectionProjection } = {},
): AppSelection {
  const stableId = `${body.id}+${animation.id}#sample:${frame.sequence_index};frame=${frame.frame};elapsed=${frame.elapsed_ms}`;
  const rootMotion = frame.root_motion;
  const graphExportActions = options.graphSelection?.exportActions || [];
  return {
    kind: 'animation_sample',
    stableId,
    label: `${body.label} + ${animation.label} sample ${frame.sequence_index}`,
    source: sourceFromAsset(animation),
    provenance: `BODY ${body.id} posed by ANIM ${animation.id} through decoded playback sequence`,
    evidenceStatus: 'decoded_only',
    links: [
      ...parentGraphLinks(body, options.graphSelection),
      { kind: 'asset', stableId: animation.id, label: animation.label },
    ],
    unknowns: [],
    previewActions: [],
    exportActions: graphExportActions,
    exportCapability: options.graphSelection?.exportCapability,
    workspaceSuggestion: 'model',
    facets: {
      bodyAssetId: body.id,
      animationAssetId: animation.id,
      sequenceIndex: frame.sequence_index,
      segment: frame.segment,
      frame: frame.frame,
      previousFrame: frame.previous_frame,
      nextFrame: frame.next_frame,
      elapsedMs: frame.elapsed_ms,
      timelineMs: frame.timeline_ms,
      durationMs: frame.duration_ms,
      loopCycle,
      loopIndex: sequence.loop_index,
      playbackEndIndex: sequence.playback_end_index,
      rootMotionX: rootMotion?.[0],
      rootMotionY: rootMotion?.[1],
      rootMotionZ: rootMotion?.[2],
      graphNodeId: options.graphSelection?.facets?.graphNodeId || options.graphSelection?.nodeId,
      relationshipLinkCount: options.graphSelection?.facets?.relationshipLinkCount,
    },
    evidence: {
      animation,
      animationBody: body,
      animationFrame: frame,
      animationSequence: sequence,
    },
  };
}

export function selectionFromAnimationPose(
  body: CatalogAsset,
  animation: CatalogAsset,
  model: Lm2Model,
  options: { graphSelection?: CatalogGraphSelectionProjection } = {},
): AppSelection | null {
  const pose = model.pose;
  if (!pose) return null;
  const sample = pose.sample;
  const rootMotion = sample.root_delta;
  const graphExportActions = options.graphSelection?.exportActions || [];
  return {
    kind: 'animation_sample',
    stableId: `${body.id}+${animation.id}#pose:frame=${sample.target_frame_index};previous=${sample.previous_frame_index};elapsed=${sample.elapsed_ms}`,
    label: `${body.label} + ${animation.label} posed frame ${sample.target_frame_index}`,
    source: sourceFromAsset(animation),
    provenance: `BODY ${body.id} posed by ANIM ${animation.id} through decoded pose sample`,
    evidenceStatus: 'decoded_only',
    links: [
      ...parentGraphLinks(body, options.graphSelection),
      { kind: 'asset', stableId: animation.id, label: animation.label },
    ],
    unknowns: [],
    previewActions: [],
    exportActions: graphExportActions,
    exportCapability: options.graphSelection?.exportCapability,
    workspaceSuggestion: 'model',
    facets: {
      bodyAssetId: body.id,
      animationAssetId: animation.id,
      frame: sample.target_frame_index,
      previousFrame: sample.previous_frame_index,
      nextFrame: sample.next_frame_index,
      elapsedMs: sample.elapsed_ms,
      durationMs: sample.duration_ms,
      complete: sample.complete,
      boneCount: sample.bone_count,
      rootMotionX: rootMotion?.[0],
      rootMotionY: rootMotion?.[1],
      rootMotionZ: rootMotion?.[2],
      graphNodeId: options.graphSelection?.facets?.graphNodeId || options.graphSelection?.nodeId,
      relationshipLinkCount: options.graphSelection?.facets?.relationshipLinkCount,
    },
    evidence: {
      animation,
      animationBody: body,
      model,
    },
  };
}

export function selectionFromResourceRecord(
  asset: CatalogAsset,
  record: ResourceRecordEvidence,
  options: { graphSelection?: CatalogGraphSelectionProjection } = {},
): AppSelection {
  const exportActions = options.graphSelection?.exportActions || [];
  return {
    kind: 'resource_record',
    stableId: record.stableId,
    label: record.label,
    source: sourceFromAsset(asset),
    provenance: `${asset.id} ${record.kind} sampled decoded resource evidence`,
    evidenceStatus: evidenceStatusForAsset(asset),
    links: parentGraphLinks(asset, options.graphSelection),
    unknowns: unknownsForAsset(asset),
    previewActions: [],
    exportActions,
    exportCapability: options.graphSelection?.exportCapability,
    workspaceSuggestion: 'resource',
    facets: {
      assetId: asset.id,
      graphNodeId: options.graphSelection?.facets?.graphNodeId,
      relationshipLinkCount: options.graphSelection?.facets?.relationshipLinkCount,
      recordKind: record.kind,
      summary: record.summary,
      detail: record.detail,
    },
    evidence: {
      resourceAsset: asset,
      resourceRecord: record,
    },
  };
}

export function selectionFromResourcePaletteContext(
  asset: CatalogAsset,
  record?: ResourceRecordEvidence,
  options: { graphSelection?: CatalogGraphSelectionProjection } = {},
): AppSelection | null {
  if (asset.kind !== 'resource') return null;
  const stats = asset.stats as ResourceStats;
  const paletteEntry = stats.palette_entry ? `${stats.palette_entry.hqr}:${stats.palette_entry.entry_index}` : null;
  const hasPaletteContext = Boolean(
    paletteEntry
      || stats.source_provenance
      || stats.runtime_reference_status
      || stats.scene_palette_reference_count !== undefined
      || stats.screen_pair_base !== undefined
      || stats.paired_entry_index !== undefined,
  );
  if (!hasPaletteContext) return null;
  const pairedEntry = stats.paired_entry_index === undefined ? null : `${asset.source.hqr}:${stats.paired_entry_index}`;
  const paletteStablePart = paletteEntry || pairedEntry || 'unknown';
  return {
    kind: 'palette_context',
    stableId: `${asset.id}#palette:${paletteStablePart}`,
    label: `${asset.label} palette context`,
    source: sourceFromAsset(asset),
    provenance: stats.source_provenance || stats.runtime_reference_status || `${asset.id} palette context`,
    evidenceStatus: stats.source_provenance || stats.runtime_reference_status ? 'source_backed' : 'decoded_only',
    links: [
      ...parentGraphLinks(asset, options.graphSelection),
      ...(paletteEntry ? [{ kind: 'asset' as const, stableId: paletteEntry, label: `Palette ${paletteEntry}` }] : []),
    ],
    unknowns: paletteEntry || pairedEntry ? [] : ['Palette source is not resolved for this resource.'],
    previewActions: paletteEntry ? [{ id: 'open_palette_asset', label: `Open ${paletteEntry}`, targetAssetId: paletteEntry }] : [],
    exportActions: options.graphSelection?.exportActions || [],
    exportCapability: options.graphSelection?.exportCapability,
    workspaceSuggestion: 'resource',
    facets: {
      assetId: asset.id,
      graphNodeId: options.graphSelection?.facets?.graphNodeId,
      relationshipLinkCount: options.graphSelection?.facets?.relationshipLinkCount,
      layout: stats.semantic_layout,
      paletteSource: paletteEntry,
      sourceProvenance: stats.source_provenance,
      runtimeReference: stats.runtime_reference_status,
      scenePaletteReferences: stats.scene_palette_reference_count,
      screenPairBase: stats.screen_pair_base,
      pairedEntry,
      recordStableId: record?.stableId,
    },
    evidence: {
      resourceAsset: asset,
      resourceRecord: record,
    },
  };
}

export function selectionFromSceneUsage(asset: CatalogAsset, usage: SceneAssetUsage): AppSelection {
  const stableId = sceneUsageStableId(asset, usage);
  const label = usage.label || `${usage.scene_label} object ${usage.object_index}`;
  return {
    kind: 'scene_usage',
    stableId,
    label,
    source: {
      archive: 'SCENE.HQR',
      entryIndex: usage.scene_entry_index,
    },
    provenance: usage.sourceRule || usage.resolution_rule || usage.indexRule || usage.index_rule || usage.reference_key || `${asset.id} catalog graph usage record`,
    evidenceStatus: usage.resolution_rule || usage.index_rule ? 'source_backed' : 'decoded_only',
    links: [
      { kind: 'asset', stableId: asset.id, label: asset.label },
      { kind: 'asset', stableId: usage.scene_asset_id, label: usage.scene_asset_id },
      {
        kind: usage.proofScope === 'scene_object_state' ? 'scene_object' : 'scene_usage',
        stableId: usage.graphLinkStableId || `${usage.scene_asset_id}#object:${usage.object_index}`,
        label,
        proofScope: usage.proofScope,
        evidenceStatus: usage.evidenceStatus,
        sourceRule: usage.sourceRule || usage.resolution_rule,
        sourceField: usage.sourceField,
        indexRule: usage.indexRule || usage.index_rule,
      },
    ],
    unknowns: [],
    previewActions: [],
    exportActions: [],
    workspaceSuggestion: 'entity',
    facets: {
      assetId: asset.id,
      usageKind: usage.kind,
      sceneAssetId: usage.scene_asset_id,
      sceneIndex: usage.scene_index,
      objectIndex: usage.object_index,
      targetAssetId: usage.target_asset_id,
      scriptKind: usage.script_kind,
      referenceKey: usage.reference_key,
      referenceValue: usage.reference_value,
      backend: usage.backend,
      runtimeSpriteIndex: usage.runtime_sprite_index,
    },
    evidence: {
      usageAsset: asset,
      sceneUsage: usage,
    },
  };
}

export function selectionFromEntityFacet(workflow: EntityWorkflowPayload, kind: EntityFacetSelectionKind): AppSelection | null {
  const entity = workflow.selected_entity;
  if (!entity) return null;
  const state = entity.initial_state;
  const sourceAsset = entity.provenance.scene_asset;
  const base = {
    source: {
      archive: sourceAsset?.source.hqr || 'SCENE.HQR',
      entryIndex: entity.scene_entry_index,
      classicIndex: sourceAsset?.source.classic_index,
    },
    links: [{ kind: 'scene_object' as const, stableId: entity.entity_id, label: entity.label }],
    previewActions: [] as SelectionAction[],
    exportActions: [] as SelectionAction[],
    workspaceSuggestion: 'entity' as const,
    evidence: {
      entityContract: entity,
      entityWorkflow: workflow,
    },
  };
  if (kind === 'runtime_sprite_state') {
    return {
      kind,
      stableId: `${entity.entity_id}#runtime_sprite_state`,
      label: `${entity.label} runtime sprite state`,
      provenance: entity.provenance.resolution_rule || entity.object_sample_status,
      evidenceStatus: entity.confidence === 'evidence' ? 'source_backed' : 'decoded_only',
      unknowns: [],
      facets: {
        flags: state.flags as string | number | boolean | null | undefined,
        sprite: state.sprite as string | number | boolean | null | undefined,
        bodyNum: state.gen_body as string | number | boolean | null | undefined,
        genAnim: state.gen_anim as string | number | boolean | null | undefined,
        backend: entity.render_backend,
        objectIndex: entity.object_index,
      },
      ...base,
    };
  }
  if (kind === 'file3d_resolution') {
    const file3d = state.file3d_index as string | number | boolean | null | undefined;
    return {
      kind,
      stableId: `${entity.entity_id}#file3d:${file3d ?? 'unknown'}`,
      label: `${entity.label} File3D resolution`,
      provenance: entity.provenance.resolution_rule || 'scene object File3D state',
      evidenceStatus: entity.linked_visual_assets.some((link) => link.role === 'body' && link.asset_available !== false) ? 'source_backed' : 'unknown',
      links: [
        ...base.links,
        ...entity.linked_visual_assets
          .filter((link) => link.role === 'body' && link.asset_available !== false)
          .map((link) => ({ kind: 'asset' as const, stableId: link.asset_id, label: link.asset_id })),
      ],
      unknowns: entity.linked_visual_assets.some((link) => link.role === 'body')
        ? []
        : ['No body visual link is attached to this File3D state.'],
      previewActions: entity.linked_visual_assets
        .filter((link) => link.role === 'body' && link.asset_available !== false)
        .map((link) => ({ id: 'open_file3d_asset', label: `Open ${link.asset_id}`, targetAssetId: link.asset_id })),
      exportActions: [],
      workspaceSuggestion: 'entity',
      facets: {
        file3dIndex: file3d,
        genBody: state.gen_body as string | number | boolean | null | undefined,
        genAnim: state.gen_anim as string | number | boolean | null | undefined,
        objectIndex: entity.object_index,
        resolutionRule: entity.provenance.resolution_rule,
      },
      evidence: base.evidence,
      source: base.source,
    };
  }
  if (kind === 'anim3ds_range_state') {
    const range = state.anim3ds_range as Record<string, unknown> | null | undefined;
    if (!range) return null;
    const spriteLink = entity.linked_visual_assets.find((link) => link.role === 'sprite' && link.asset_available !== false);
    const animationNumber = range.animation_number as string | number | boolean | null | undefined;
    const rangeMatchesSprite = range.range_matches_sprite as string | number | boolean | null | undefined;
    return {
      kind,
      stableId: `${entity.entity_id}#anim3ds:${animationNumber ?? 'unknown'}`,
      label: `${entity.label} ANIM3DS range`,
      provenance: entity.provenance.resolution_rule || 'scene object ANIM3DS range state',
      evidenceStatus: rangeMatchesSprite === false ? 'decoded_only' : 'source_backed',
      links: [
        ...base.links,
        ...(spriteLink ? [{ kind: 'asset' as const, stableId: spriteLink.asset_id, label: spriteLink.asset_id }] : []),
      ],
      unknowns: rangeMatchesSprite === false ? ['ANIM3DS range does not exactly match the scene object sprite frame.'] : [],
      previewActions: spriteLink ? [{ id: 'open_anim3ds_asset', label: `Open ${spriteLink.asset_id}`, targetAssetId: spriteLink.asset_id }] : [],
      exportActions: [],
      workspaceSuggestion: 'entity',
      facets: {
        animationNumber,
        name: range.name as string | number | boolean | null | undefined,
        startFrame: range.start_frame as string | number | boolean | null | undefined,
        endFrame: range.end_frame as string | number | boolean | null | undefined,
        frameCount: range.frame_count as string | number | boolean | null | undefined,
        relativeFrame: range.relative_frame as string | number | boolean | null | undefined,
        rangeMatchesSprite,
        framesPerSecond: range.frames_per_second as string | number | boolean | null | undefined,
        sizeSHit: range.size_s_hit as string | number | boolean | null | undefined,
        sprite: state.sprite as string | number | boolean | null | undefined,
        backend: entity.render_backend,
        objectIndex: entity.object_index,
      },
      evidence: base.evidence,
      source: base.source,
    };
  }
  return {
    kind,
    stableId: `${entity.entity_id}#render_contract`,
    label: `${entity.label} render contract`,
    provenance: entity.render_contract.source || entity.provenance.resolution_rule || 'scene object render contract',
    evidenceStatus: entity.render_contract.source ? 'source_backed' : 'decoded_only',
    unknowns: [],
    facets: {
      backend: entity.render_backend,
      drawPath: entity.render_contract.draw_path,
      sortedInsertion: entity.render_contract.sort_key,
      recoveryPath: entity.render_contract.recovery_path,
      steps: entity.render_contract.contract_steps.join(', '),
      renderPhase: renderPhaseSummary(entity.render_contract.render_phase),
      redrawContract: redrawContractSummary(entity.render_contract.redraw_contract),
    },
    ...base,
  };
}

function renderPhaseSummary(phase?: Record<string, unknown>): string | undefined {
  if (!phase) return undefined;
  const parts = [
    textPart('Scene redraw setup', phase.scene_redraw_setup),
    textPart('Background object skip', phase.object_only_background_skip_rule),
    textPart('Invisible/bodyless skip', phase.invisible_or_bodyless_skip_before_tree),
    textPart('Camera preclip', phase.camera_preclip_before_tree),
    textPart('Tree insert', phase.tree_insert),
    textPart('Shadow', phase.shadow),
  ].filter(Boolean);
  return parts.join(' | ') || undefined;
}

function redrawContractSummary(contract?: Record<string, unknown>): string | undefined {
  if (!contract) return undefined;
  const parts = [
    textPart('Method', contract.method),
    textPart('Anchor', contract.anchor),
    boolPart('Moving box', contract.moving_box),
    boolPart('Draw over brick cage', contract.draw_over_brick_cage),
    boolPart('Z-buffer/water flag', contract.zbuffer_or_water_flag_present),
    boolPart('Z-buffer/water effective', contract.zbuffer_or_water_effective),
    boolPart('Sprite clip info rect', contract.sprite_clip_info_rect),
    boolPart('Camera recenter on full mask', contract.camera_recenter_on_full_mask),
  ].filter(Boolean);
  return parts.join(' | ') || undefined;
}

function textPart(label: string, value: unknown): string | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  return `${label}: ${String(value)}`;
}

function boolPart(label: string, value: unknown): string | undefined {
  if (typeof value !== 'boolean') return textPart(label, value);
  return `${label}: ${value ? 'yes' : 'no'}`;
}

export function selectionFromSceneUsageFacet(asset: CatalogAsset, usage: SceneAssetUsage, kind: EntityFacetSelectionKind): AppSelection | null {
  if (kind === 'render_contract') return null;
  if (kind === 'anim3ds_range_state' && !usage.anim3ds_range) return null;
  if (kind === 'runtime_sprite_state' && usage.runtime_sprite_index === undefined && !usage.backend) return null;
  const usageId = sceneUsageStableId(asset, usage);
  const baseLinks: SelectionLink[] = [
    { kind: 'scene_usage', stableId: usageId, label: usage.label || `${usage.scene_label} object ${usage.object_index}` },
    { kind: 'asset', stableId: asset.id, label: asset.label },
    { kind: 'asset', stableId: usage.scene_asset_id, label: usage.scene_asset_id },
  ];
  if (kind === 'anim3ds_range_state') {
    const range = usage.anim3ds_range;
    return {
      kind,
      stableId: `${usageId}#anim3ds:${range?.animation_number ?? 'unknown'}`,
      label: `${usage.label || asset.label} ANIM3DS range`,
      source: { archive: 'SCENE.HQR', entryIndex: usage.scene_entry_index },
      provenance: usage.index_rule || usage.resolution_rule || 'scene ANIM3DS runtime range',
      evidenceStatus: range?.range_matches_sprite ? 'source_backed' : 'decoded_only',
      links: baseLinks,
      unknowns: range?.range_matches_sprite === false ? ['ANIM3DS range does not exactly match the sprite runtime reference.'] : [],
      previewActions: [],
      exportActions: [],
      workspaceSuggestion: 'entity',
      facets: {
        animationNumber: range?.animation_number,
        name: range?.name,
        startFrame: range?.start_frame,
        endFrame: range?.end_frame,
        frameCount: range?.frame_count,
        relativeFrame: range?.relative_frame,
        rangeMatchesSprite: range?.range_matches_sprite,
        framesPerSecond: range?.frames_per_second,
      },
      evidence: { usageAsset: asset, sceneUsage: usage },
    };
  }
  if (kind === 'runtime_sprite_state') {
    return {
      kind,
      stableId: `${usageId}#runtime_sprite:${usage.runtime_sprite_index ?? usage.sprite}`,
      label: `${usage.label || asset.label} runtime sprite state`,
      source: { archive: 'SCENE.HQR', entryIndex: usage.scene_entry_index },
      provenance: usage.index_rule || usage.resolution_rule || 'scene runtime sprite state',
      evidenceStatus: usage.runtime_sprite_index === undefined ? 'decoded_only' : 'source_backed',
      links: baseLinks,
      unknowns: [],
      previewActions: [],
      exportActions: [],
      workspaceSuggestion: 'entity',
      facets: {
        flags: usage.flags,
        sprite: usage.sprite,
        runtimeSpriteIndex: usage.runtime_sprite_index,
        backend: usage.backend,
        bodyNum: usage.gen_body,
        objectIndex: usage.object_index,
      },
      evidence: { usageAsset: asset, sceneUsage: usage },
    };
  }
  return {
    kind,
    stableId: `${usageId}#file3d:${usage.file3d_index}`,
    label: `${usage.label || asset.label} File3D resolution`,
    source: { archive: 'SCENE.HQR', entryIndex: usage.scene_entry_index },
    provenance: usage.resolution_rule || usage.index_rule || 'scene File3D resolution',
    evidenceStatus: usage.resolution_rule || usage.index_rule ? 'source_backed' : 'decoded_only',
    links: baseLinks,
    unknowns: [],
    previewActions: [{ id: 'open_file3d_asset', label: `Open ${asset.id}`, targetAssetId: asset.id }],
    exportActions: [],
    workspaceSuggestion: 'entity',
    facets: {
      file3dIndex: usage.file3d_index,
      genBody: usage.gen_body,
      genAnim: usage.gen_anim,
      targetAssetId: usage.target_asset_id,
      genericId: usage.generic_id,
      genericName: usage.generic_name,
      bodyIndex: usage.body_index,
      animationIndex: usage.animation_index,
    },
    evidence: { usageAsset: asset, sceneUsage: usage },
  };
}

export function sceneUsageStableId(asset: CatalogAsset, usage: SceneAssetUsage): string {
  const parts = [
    `${usage.scene_asset_id}#object:${usage.object_index}`,
    usage.script_kind ? `script=${usage.script_kind}` : null,
    usage.reference_key ? `${usage.reference_key}=${usage.reference_value ?? ''}` : null,
    usage.zone_index === undefined ? null : `zone=${usage.zone_index}`,
    usage.record_index === undefined ? null : `record=${usage.record_index}`,
  ].filter(Boolean);
  return `${asset.id}#usage:${parts.join(';')}`;
}

function sourceFromAsset(asset: CatalogAsset): SelectionSource {
  return {
    archive: asset.source.hqr,
    entryIndex: asset.source.entry_index,
    classicIndex: asset.source.classic_index,
    rawSha256: asset.source.raw_sha256,
    decodedSha256: asset.decoded_sha256,
    relativePath: asset.relative_path,
  };
}

function provenanceForAsset(asset: CatalogAsset): string {
  const stats = asset.stats;
  if ('source_provenance' in stats && stats.source_provenance) return stats.source_provenance;
  if ('runtime_reference_status' in stats && stats.runtime_reference_status) return stats.runtime_reference_status;
  if ('decode_note' in stats && stats.decode_note) return stats.decode_note;
  return `${asset.source.hqr}[${asset.source.entry_index}]`;
}

function evidenceStatusForAsset(asset: CatalogAsset): EvidenceStatus {
  const stats = asset.stats;
  if ('source_provenance' in stats && stats.source_provenance) return 'source_backed';
  if ('runtime_reference_status' in stats && stats.runtime_reference_status === 'source-backed') return 'source_backed';
  if ('parse_status' in stats && stats.parse_status === 'raw') return 'intentionally_deferred';
  if ('decode_status' in stats && stats.decode_status === 'decoded') return 'decoded_only';
  if ('decode_status' in stats && stats.decode_status === 'partial') return 'decoded_only';
  if (asset.kind === 'model' || (asset.kind === 'animation' && asset.entry_type === 'animation')) return 'decoded_only';
  return 'unknown';
}

function linksForAsset(asset: CatalogAsset): SelectionLink[] {
  void asset;
  return [];
}

function unknownsForAsset(asset: CatalogAsset): string[] {
  const stats = asset.stats;
  if ('unknown_descriptors' in stats && stats.unknown_descriptors.length > 0) {
    return stats.unknown_descriptors.slice(0, 8).map((descriptor) => `${descriptor.section}: ${descriptor.note}`);
  }
  if ('decode_status' in stats && stats.decode_status !== 'decoded') return [`${stats.decode_status}: ${stats.decode_note}`];
  return [];
}

function previewActionsForAsset(asset: CatalogAsset): SelectionAction[] {
  if (asset.kind === 'model' || asset.kind === 'sprite' || asset.kind === 'scene' || asset.kind === 'resource') {
    return [{ id: 'open_workspace', label: `Open ${workspaceForAsset(asset) || asset.kind} workspace`, targetAssetId: asset.id }];
  }
  return [];
}

function workspaceForAsset(asset: CatalogAsset): AppSelection['workspaceSuggestion'] {
  if (asset.kind === 'model' || asset.kind === 'animation') return 'model';
  if (asset.kind === 'sprite') return 'sprite';
  if (asset.kind === 'scene') return 'entity';
  if (asset.kind === 'resource') return 'resource';
  return undefined;
}

function facetsForAsset(asset: CatalogAsset): AppSelection['facets'] {
  const stats = asset.stats;
  return {
    archive: asset.source.hqr,
    entryIndex: asset.source.entry_index,
    kind: asset.kind,
    entryType: asset.entry_type,
    semanticLayout: 'semantic_layout' in stats ? stats.semantic_layout : undefined,
    decodedBytes: asset.decoded_bytes,
    sceneUsageCount: undefined,
  };
}
