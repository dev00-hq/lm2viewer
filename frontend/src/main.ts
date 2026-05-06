import './styles.css';
import { buildCatalog, catalogAudioUrl, exportCatalogAsset, fetchCatalog, fetchDecodeProgress, fetchInitialModel, fetchPortPromotionPackets, loadAssetEntityWorkflow, loadCatalogAsset, loadPath, loadRuntimeSpriteEntityWorkflow, loadSceneObjectEntityWorkflow, pickCatalogFiles, pickCatalogFolder, uploadModel } from './api';
import { animationCompatibilityPrefix, animationMatchesModel } from './compatibility';
import { requireElement } from './dom';
import { InspectorRenderer, anim3dsRangeInspectorSections, animationInspectorSections, animationSampleInspectorSections, backgroundInspectorSections, entityFacetInspectorSections, evidenceArtifactInspectorSections, holomapInspectorSections, modelInspectorSections, modelSurfaceInspectorSections, paletteImageInspectorSections, rawAnimationInspectorSections, resourceRecordInspectorSections, runtimeTableInspectorSections, sampleAudioInspectorSections, sceneInspectorSections, sceneObjectInspectorSections, sceneUsageInspectorSections, smackerVideoInspectorSections, spriteFrameInspectorSections, textOrderInspectorSections, textPayloadInspectorSections, unclassifiedResourceInspectorSections } from './inspector';
import { AppSelectionStore, sceneUsageStableId, selectionFromAnimationPose, selectionFromAnimationSample, selectionFromCatalogAsset, selectionFromEntityFacet, selectionFromEntityWorkflow, selectionFromModelSurface, selectionFromResourcePaletteContext, selectionFromResourceRecord, selectionFromRuntimeResolution, selectionFromSceneUsage, selectionFromSceneUsageFacet, selectionFromSpriteFrame, type AppSelection, type EntityFacetSelectionKind } from './selection';
import type { Catalog, CatalogAsset, DecodeProgress, Lm2Model, PolygonMode, PortPromotionPacketsPayload, SceneScriptAnalysis, SceneStats, SpritePayload } from './types';
import { AnimationController } from './ui/animationController';
import { CatalogUi } from './ui/catalog';
import { EntityView } from './ui/entityView';
import { ResourceWorkspace } from './ui/resourceWorkspace';
import { RuntimeSpriteResolver } from './ui/runtimeSpriteResolver';
import { SpriteViewer } from './ui/spriteViewer';
import { renderStats } from './ui/stats';
import { UvInspector } from './ui/uvInspector';
import {
  DEFAULT_CANVAS_BACKGROUND_SHADE,
  ViewerScene,
  canvasBackgroundColor,
  canvasBackgroundSliderStops,
  type CanvasBackgroundMode,
  type CanvasBackgroundShade,
  type VisibilityState,
} from './viewer/scene';

const canvas = requireElement('canvas', HTMLCanvasElement);
const scene = new ViewerScene({ canvas });

type MainView = 'model' | 'sprite' | 'entity' | 'resource';
type DockSide = 'explorer' | 'inspector';
type InspectorTab = 'details' | 'uv';

const app = requireElement('app', HTMLDivElement);
const stats = requireElement('stats', HTMLDivElement);
const errorBox = requireElement('error', HTMLDivElement);
const overlay = requireElement('overlay', HTMLDivElement);
const horizonIndicator = requireElement('horizonIndicator', HTMLDivElement);
const horizonLockToggle = requireElement('horizonLockToggle', HTMLButtonElement);
const viewControlsToggle = requireElement('viewControlsToggle', HTMLButtonElement);
const viewControlsPopover = requireElement('viewControlsPopover', HTMLDivElement);
const explorerDockToggle = requireElement('explorerDockToggle', HTMLButtonElement);
const inspectorDockToggle = requireElement('inspectorDockToggle', HTMLButtonElement);
const showFaces = requireElement('showFaces', HTMLInputElement);
const showLines = requireElement('showLines', HTMLInputElement);
const showSpheres = requireElement('showSpheres', HTMLInputElement);
const wireframe = requireElement('wireframe', HTMLInputElement);
const showGrid = requireElement('showGrid', HTMLInputElement);
const lightCanvas = requireElement('lightCanvas', HTMLInputElement);
const canvasBackgroundToggle = requireElement('canvasBackgroundToggle', HTMLButtonElement);
const canvasBackgroundShade = requireElement('canvasBackgroundShade', HTMLButtonElement);
const canvasBackgroundShadePicker = requireElement('canvasBackgroundShadePicker', HTMLDivElement);
const lockHorizon = requireElement('lockHorizon', HTMLInputElement);
const assetRootInput = requireElement('assetRoot', HTMLInputElement);
const pathInput = requireElement('path', HTMLInputElement);
const fileInput = requireElement('file', HTMLInputElement);
const drop = requireElement('drop', HTMLDivElement);
const progressPanel = requireElement('decodeProgress', HTMLDivElement);
const progressText = requireElement('progressText', HTMLSpanElement);
const progressMeta = requireElement('progressMeta', HTMLSpanElement);
const progressBar = requireElement('progressBar', HTMLDivElement);
const progressFill = requireElement('progressFill', HTMLDivElement);
const activeSelectionPanel = requireElement('activeSelection', HTMLDivElement);
const exportAssetButton = requireElement('exportAsset', HTMLButtonElement);
const exportPolygonMode = requireElement('exportPolygonMode', HTMLSelectElement);
const exportResult = requireElement('exportResult', HTMLDivElement);
const sceneUsageStrip = requireElement('sceneUsageStrip', HTMLElement);
const sceneObjectTable = requireElement('sceneObjectTable', HTMLElement);
const sceneLocalTable = requireElement('sceneLocalTable', HTMLElement);
const portEvidenceTable = requireElement('portEvidenceTable', HTMLElement);
const scriptEvidenceTable = requireElement('scriptEvidenceTable', HTMLElement);
const rawDescriptorTable = requireElement('rawDescriptorTable', HTMLElement);
const animationPanel = requireElement('animationPanel', HTMLDivElement);
const animationPanelResize = requireElement('animationPanelResize', HTMLDivElement);
const canvasAnimationSelect = requireElement('canvasAnimationSelect', HTMLSelectElement);
const mainViews: Record<MainView, { tab: HTMLButtonElement; panel: HTMLElement }> = {
  model: {
    tab: requireElement('modelViewTab', HTMLButtonElement),
    panel: requireElement('modelViewPanel', HTMLElement),
  },
  sprite: {
    tab: requireElement('spriteViewTab', HTMLButtonElement),
    panel: requireElement('spriteViewPanel', HTMLElement),
  },
  entity: {
    tab: requireElement('entityViewTab', HTMLButtonElement),
    panel: requireElement('entityViewPanel', HTMLElement),
  },
  resource: {
    tab: requireElement('resourceViewTab', HTMLButtonElement),
    panel: requireElement('resourceViewPanel', HTMLElement),
  },
};
const inspectorTabs: Record<InspectorTab, { tab: HTMLButtonElement; panel: HTMLElement }> = {
  details: {
    tab: requireElement('inspectorDetailsTab', HTMLButtonElement),
    panel: requireElement('inspectorDetailsPanel', HTMLElement),
  },
  uv: {
    tab: requireElement('inspectorUvTab', HTMLButtonElement),
    panel: requireElement('inspectorUvPanel', HTMLElement),
  },
};
const uvInspector = new UvInspector({
  root: requireElement('uvInspector', HTMLDivElement),
  polygon: requireElement('uvPolygon', HTMLSelectElement),
  atlas: requireElement('uvAtlas', HTMLCanvasElement),
  facts: requireElement('uvFacts', HTMLDivElement),
  previous: requireElement('uvPrevious', HTMLButtonElement),
  next: requireElement('uvNext', HTMLButtonElement),
  copy: requireElement('uvCopy', HTMLButtonElement),
  download: requireElement('uvDownload', HTMLButtonElement),
  result: requireElement('uvResult', HTMLDivElement),
}, {
  onSurfaceSelected: (model, evidence) => {
    selectionStore.set(selectionFromModelSurface(model, evidence));
  },
});
let currentCatalog: Catalog | null = null;
let portPromotionPackets: PortPromotionPacketsPayload | null = null;
let portPromotionError: string | null = null;
let progressInterval: number | undefined;
let progressHideTimer: number | undefined;
let progressStartedAt = 0;
let catalogSelectionRequestId = 0;
let selectedCanvasBackgroundShade: CanvasBackgroundShade = DEFAULT_CANVAS_BACKGROUND_SHADE;

const backgroundStorageKeys = {
  mode: 'lba2-lm2-viewer.canvasBackgroundMode',
  shade: 'lba2-lm2-viewer.canvasBackgroundShade',
};

const catalogUi = new CatalogUi({
  summary: requireElement('catalogSummary', HTMLDivElement),
  search: requireElement('catalogSearch', HTMLInputElement),
  filter: requireElement('kindFilter', HTMLSelectElement),
  list: requireElement('assetList', HTMLDivElement),
  onSelect: selectCatalogAsset,
});
const inspector = new InspectorRenderer(
  requireElement('assetDetail', HTMLDivElement),
  requireElement('inspectorSearch', HTMLInputElement),
);
const selectionStore = new AppSelectionStore();
const spriteViewer = new SpriteViewer({
  panel: requireElement('spriteViewPanel', HTMLElement),
  canvas: requireElement('spriteCanvas', HTMLCanvasElement),
  title: requireElement('spriteTitle', HTMLDivElement),
  meta: requireElement('spriteMeta', HTMLDivElement),
  facts: requireElement('spriteFacts', HTMLDivElement),
  zoomIn: requireElement('spriteZoomIn', HTMLButtonElement),
  zoomOut: requireElement('spriteZoomOut', HTMLButtonElement),
  fit: requireElement('spriteFit', HTMLButtonElement),
  previous: requireElement('spritePrevious', HTMLButtonElement),
  play: requireElement('spritePlay', HTMLButtonElement),
  next: requireElement('spriteNext', HTMLButtonElement),
  scrub: requireElement('spriteScrub', HTMLInputElement),
  frameLabel: requireElement('spriteFrameLabel', HTMLDivElement),
  strip: requireElement('spriteFrameStrip', HTMLElement),
  loadFrame: loadSpriteFrame,
  onFrameLoaded: (asset, payload) => {
    selectionStore.set(selectionFromSpriteFrame(asset, payload));
  },
  onPixelPicked: (asset, payload, pixel) => {
    const current = selectionStore.current;
    const frameSelection = selectionFromSpriteFrame(asset, payload);
    if (!current || current.kind !== 'sprite_frame' || current.stableId !== frameSelection.stableId) return;
    selectionStore.update({
      facets: {
        ...(current.facets || {}),
        pickedPixelX: pixel.x,
        pickedPixelY: pixel.y,
        pickedPaletteIndex: pixel.paletteIndex,
        pickedRgba: pixel.rgba.join(','),
      },
    });
  },
});
const entityView = new EntityView({
  panel: requireElement('entityViewPanel', HTMLElement),
  title: requireElement('entityTitle', HTMLDivElement),
  trail: requireElement('entityTrail', HTMLDivElement),
  usages: requireElement('entityUsages', HTMLDivElement),
  detail: requireElement('entityDetail', HTMLDivElement),
  visualLinks: requireElement('entityVisualLinks', HTMLDivElement),
  openAsset: (assetId) => {
    void openLinkedVisualAsset(assetId);
  },
  selectEntityFacet: (workflow, kind) => {
    const selection = selectionFromEntityFacet(workflow, kind);
    if (selection) selectionStore.set(selection);
  },
  selectUsageFacet: (usage, kind) => {
    const asset = findCatalogAsset(usage.target_asset_id);
    const selection = asset ? selectionFromSceneUsageFacet(asset, usage, kind) : null;
    if (selection) selectionStore.set(selection);
  },
});
const resourceWorkspace = new ResourceWorkspace({
  panel: requireElement('resourceViewPanel', HTMLElement),
  title: requireElement('resourceTitle', HTMLDivElement),
  meta: requireElement('resourceMeta', HTMLDivElement),
  facts: requireElement('resourceFacts', HTMLDivElement),
  records: requireElement('resourceRecords', HTMLDivElement),
  stage: requireElement('resourceStage', HTMLElement),
  emptyState: requireElement('resourceEmptyState', HTMLElement),
  canvas: requireElement('resourceCanvas', HTMLCanvasElement),
  audioWrap: requireElement('resourceAudio', HTMLElement),
  audio: requireElement('resourceAudioPlayer', HTMLAudioElement),
  audioMeta: requireElement('resourceAudioMeta', HTMLDivElement),
  onRecordSelected: (asset, record) => {
    if (record.kind === 'palette_context') {
      const selection = selectionFromResourcePaletteContext(asset, record);
      if (selection) selectionStore.set(selection);
      return;
    }
    selectionStore.set(selectionFromResourceRecord(asset, record));
  },
});
const runtimeSpriteResolver = new RuntimeSpriteResolver({
  root: requireElement('runtimeSpriteResolver', HTMLElement),
  flags: requireElement('runtimeSpriteFlags', HTMLInputElement),
  sprite: requireElement('runtimeSpriteIndex', HTMLInputElement),
  bodyNum: requireElement('runtimeSpriteBodyNum', HTMLInputElement),
  objectIndex: requireElement('runtimeSpriteObjectIndex', HTMLInputElement),
  labelTrack: requireElement('runtimeSpriteLabelTrack', HTMLInputElement),
  resolve: requireElement('runtimeSpriteResolve', HTMLButtonElement),
  open: requireElement('runtimeSpriteOpen', HTMLButtonElement),
  result: requireElement('runtimeSpriteResult', HTMLDivElement),
  openAsset: (assetId) => {
    void openLinkedVisualAsset(assetId);
  },
  openWorkflow: (request) => {
    void runAction(async () => {
      const workflow = await loadRuntimeSpriteEntityWorkflow(request);
      entityView.setWorkflow(workflow);
      const entitySelection = selectionFromEntityWorkflow(workflow);
      if (entitySelection) selectionStore.set(entitySelection);
      setMainView('entity');
      overlay.textContent = workflow.selected_entity?.entity_id || workflow.resolved_asset?.id || 'Runtime sprite evidence';
    }, { label: 'Loading entity workflow' });
  },
  onResolved: (payload) => {
    selectionStore.set(selectionFromRuntimeResolution(payload));
  },
  setError: (message) => {
    errorBox.textContent = message;
  },
});
const animationController = new AnimationController({
  elements: {
    root: animationPanel,
    selection: requireElement('animationSelection', HTMLDivElement),
    playbackState: requireElement('animationPlaybackState', HTMLDivElement),
    timeCurrent: requireElement('animationTimeCurrent', HTMLSpanElement),
    timeTotal: requireElement('animationTimeTotal', HTMLSpanElement),
    scrub: requireElement('animationScrub', HTMLInputElement),
    frame: requireElement('animationFrame', HTMLInputElement),
    elapsed: requireElement('animationElapsed', HTMLInputElement),
    previous: requireElement('animationPrevious', HTMLButtonElement),
    play: requireElement('animationPlay', HTMLButtonElement),
    repeat: requireElement('animationRepeat', HTMLButtonElement),
    pose: requireElement('animationPose', HTMLButtonElement),
    mode: requireElement('animationPlaybackMode', HTMLSelectElement),
    next: requireElement('animationNext', HTMLButtonElement),
    result: requireElement('animationResult', HTMLDivElement),
    strip: requireElement('animationSequenceStrip', HTMLElement),
  },
  scene,
  showModel,
  setError: (message: string) => {
    errorBox.textContent = message;
  },
  setOverlay: (message: string) => {
    overlay.textContent = message;
  },
  runAction,
  onSampleSelected: (body, animation, sequence, frame, loopCycle) => {
    selectionStore.set(selectionFromAnimationSample(body, animation, sequence, frame, loopCycle));
  },
  onPoseSelected: (body, animation, model) => {
    const selection = selectionFromAnimationPose(body, animation, model);
    if (selection) selectionStore.set(selection);
  },
});

selectionStore.subscribe((selection) => {
  renderActiveSelection(selection);
  catalogUi.setHighlightedAssetId(selection?.kind === 'asset' ? selection.stableId : selection?.source?.archive ? selection.stableId.split('#')[0] : null);
  resourceWorkspace.setSelectedRecordId(resourceRecordIdForSelection(selection));
  renderSelectionInspector(selection);
  updateExportControls();
  renderSceneUsageStrip(selection);
  renderSceneObjectTable(selection);
  renderSceneLocalTable(selection);
  renderPortEvidenceTable(selection);
  renderScriptEvidenceTable(selection);
  renderRawDescriptorTable(selection);
});

Object.assign(globalThis, { lm2Viewer: { camera: scene.camera, controls: scene.controls, scene: scene.scene, get currentModel() { return scene.model; }, get backgroundMode() { return scene.backgroundMode; } } });

for (const element of [showFaces, showLines, showSpheres, wireframe, showGrid]) {
  element.addEventListener('change', refreshVisibility);
}
lockHorizon.addEventListener('change', refreshHorizonLock);
lightCanvas.addEventListener('change', refreshCanvasBackground);
canvasBackgroundToggle.addEventListener('click', () => {
  lightCanvas.checked = !lightCanvas.checked;
  refreshCanvasBackground();
  if (!canvasBackgroundShadePicker.hidden) renderBackgroundShadePicker();
});
canvasBackgroundShade.addEventListener('click', () => {
  renderBackgroundShadePicker();
  canvasBackgroundShadePicker.hidden = !canvasBackgroundShadePicker.hidden;
  canvasBackgroundShade.setAttribute('aria-expanded', String(!canvasBackgroundShadePicker.hidden));
  if (!canvasBackgroundShadePicker.hidden) {
    canvasBackgroundShadePicker.querySelector<HTMLInputElement>('#canvasBackgroundShadeSlider')?.focus();
  }
});
document.addEventListener('pointerdown', (event) => {
  const target = event.target;
  if (!(target instanceof Node)) return;
  if (!canvasBackgroundShadePicker.hidden
    && !canvasBackgroundShade.contains(target)
    && !canvasBackgroundShadePicker.contains(target)) {
    hideBackgroundShadePicker();
  }
  if (!viewControlsPopover.hidden
    && !viewControlsToggle.contains(target)
    && !viewControlsPopover.contains(target)) {
    hideViewControlsPopover();
  }
});
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    hideBackgroundShadePicker();
    hideViewControlsPopover();
  }
});
requireElement('resetView', HTMLButtonElement).addEventListener('click', () => scene.resetView());
requireElement('zoomIn', HTMLButtonElement).addEventListener('click', () => scene.zoomBy(0.72));
requireElement('zoomOut', HTMLButtonElement).addEventListener('click', () => scene.zoomBy(1.38));
horizonLockToggle.addEventListener('click', () => {
  lockHorizon.checked = !lockHorizon.checked;
  refreshHorizonLock();
});
viewControlsToggle.addEventListener('click', () => {
  viewControlsPopover.hidden = !viewControlsPopover.hidden;
  viewControlsToggle.setAttribute('aria-expanded', String(!viewControlsPopover.hidden));
});
inspectorTabs.details.tab.addEventListener('click', () => setInspectorTab('details'));
inspectorTabs.uv.tab.addEventListener('click', () => setInspectorTab('uv'));
explorerDockToggle.addEventListener('click', () => setDockCollapsed('explorer', !app.classList.contains('explorer-collapsed')));
inspectorDockToggle.addEventListener('click', () => setDockCollapsed('inspector', !app.classList.contains('inspector-collapsed')));
requireElement('loadAssetRoot', HTMLButtonElement).addEventListener('click', () => runAction(
  async () => setCatalog(await buildCatalog(assetRootInput.value)),
  { label: 'Indexing HQR folder', pollServer: true },
));
requireElement('pickAssetRoot', HTMLButtonElement).addEventListener('click', () => runAction(
  async () => setCatalog(await pickCatalogFolder()),
  { label: 'Choose a folder to index', pollServer: true },
));
requireElement('pickHqrFiles', HTMLButtonElement).addEventListener('click', () => runAction(
  async () => setCatalog(await pickCatalogFiles()),
  { label: 'Choose HQR files to index', pollServer: true },
));
requireElement('loadPath', HTMLButtonElement).addEventListener('click', () => runAction(
  async () => showModel(await loadPath(pathInput.value)),
  { label: 'Decoding model' },
));
exportAssetButton.addEventListener('click', () => runAction(exportSelectedAsset, { label: 'Exporting evidence probe' }));
setupAnimationPanelResize();
mainViews.model.tab.addEventListener('click', () => setMainView('model'));
mainViews.sprite.tab.addEventListener('click', () => setMainView('sprite'));
mainViews.entity.tab.addEventListener('click', () => setMainView('entity'));
mainViews.resource.tab.addEventListener('click', () => setMainView('resource'));
canvasAnimationSelect.addEventListener('change', selectCanvasAnimation);
fileInput.addEventListener('change', () => {
  const file = fileInput.files?.[0];
  if (file) void runAction(async () => showModel(await uploadModel(file)), { label: `Decoding ${file.name}` });
});

drop.addEventListener('dragover', (event) => {
  event.preventDefault();
  drop.classList.add('active');
});
drop.addEventListener('dragleave', () => drop.classList.remove('active'));
drop.addEventListener('drop', (event) => {
  event.preventDefault();
  drop.classList.remove('active');
  const file = event.dataTransfer?.files?.[0];
  if (file) void runAction(async () => showModel(await uploadModel(file)), { label: `Decoding ${file.name}` });
});

window.addEventListener('resize', () => {
  scene.resize();
  spriteViewer.resize();
  resourceWorkspace.resize();
});
window.addEventListener('keydown', (event) => {
  if (event.defaultPrevented || isEditableTarget(event.target)) return;
  if (event.key.toLowerCase() === 'l') {
    event.preventDefault();
    lockHorizon.checked = !lockHorizon.checked;
    refreshHorizonLock();
  } else if (event.key.toLowerCase() === 'r') {
    event.preventDefault();
    scene.resetView();
  }
});

restoreCanvasBackgroundPreference();
void initialLoad();
refreshCanvasBackground();
refreshHorizonLock();
tick();

async function initialLoad(): Promise<void> {
  setCatalog(await fetchCatalog());
  await loadPortPromotionEvidence();
  const initialSelectionVersion = catalogSelectionRequestId;
  const model = await fetchInitialModel();
  if (model && !selectionStore.current && catalogSelectionRequestId === initialSelectionVersion) showModel(model);
}

async function loadPortPromotionEvidence(): Promise<void> {
  try {
    portPromotionPackets = await fetchPortPromotionPackets();
    portPromotionError = null;
  } catch (error) {
    portPromotionPackets = null;
    portPromotionError = error instanceof Error ? error.message : String(error);
  }
  renderPortEvidenceTable(selectionStore.current);
}

function setCatalog(catalog: Awaited<ReturnType<typeof fetchCatalog>>): void {
  currentCatalog = catalog;
  catalogUi.setCatalog(catalog);
  runtimeSpriteResolver.setCatalog(catalog);
  if (catalog?.asset_root) assetRootInput.value = catalog.asset_root;
  updateCanvasAnimationSelect(animationController.selectedBodyAsset);
}

async function selectCatalogAsset(
  asset: CatalogAsset,
  options: { preserveSelection?: boolean; preserveEntityWorkflow?: boolean } = {},
): Promise<void> {
  const requestId = ++catalogSelectionRequestId;
  animationController.stop();
  spriteViewer.stop();
  if (!options.preserveSelection) selectionStore.set(selectionFromCatalogAsset(asset));
  await runAction(async () => {
    const payload = await loadCatalogAsset(asset);
    if (requestId !== catalogSelectionRequestId) return;
    if ('animation' in payload) {
      resourceWorkspace.clear();
      uvInspector.setModel(null);
      const rawAnimation = isRawAnimationInspectorAsset(payload.animation);
      if (!rawAnimation) {
        animationController.setAnimationAsset(payload.animation);
        updateCanvasAnimationSelect(animationController.selectedBodyAsset);
      }
      if (!options.preserveSelection) {
        selectionStore.set(selectionFromCatalogAsset(payload.animation, {
          workspaceSuggestion: 'model',
          compatibilityStatus: !rawAnimation && animationController.selectedBodyAsset
            ? animationCompatibilityPrefix(payload.animation, animationController.selectedBodyAsset).trim() || undefined
            : undefined,
        }));
      }
      if (!options.preserveEntityWorkflow) await showAssetEntityWorkflow(payload.animation, hasSceneUsages(payload.animation));
      overlay.textContent = `${payload.animation.label} selected`;
      return;
    }
    if ('sprite' in payload) {
      uvInspector.setModel(null);
      const exportable = isExportableCatalogAsset(payload.sprite);
      const sceneAsset = payload.sprite.kind === 'scene';
      const resourceAsset = payload.sprite.kind === 'resource';
      if (sceneAsset) {
        resourceWorkspace.clear();
        spriteViewer.setSprite(payload, []);
        if (!options.preserveSelection) {
          selectionStore.set(selectionFromCatalogAsset(payload.sprite, {
            exportable,
            workspaceSuggestion: 'entity',
          }));
        }
        if (!options.preserveEntityWorkflow) await showAssetEntityWorkflow(payload.sprite, false);
        setMainView('entity');
        overlay.textContent = `${payload.sprite.label} selected`;
        return;
      }
      if (!options.preserveSelection) {
        selectionStore.set(
          payload.frame && !resourceAsset
            ? selectionFromSpriteFrame(payload.sprite, payload)
            : selectionFromCatalogAsset(payload.sprite, {
              exportable,
              workspaceSuggestion: resourceAsset ? 'resource' : 'sprite',
            }),
        );
      }
      if (!options.preserveEntityWorkflow) await showAssetEntityWorkflow(payload.sprite, false);
      if (resourceAsset) {
        resourceWorkspace.setResource(payload.sprite, payload.frame);
        setMainView('resource');
      } else {
        resourceWorkspace.clear();
        spriteViewer.setSprite(payload, spriteRangeAssets(payload.sprite));
        setMainView('sprite');
      }
      overlay.textContent = `${payload.sprite.label} selected`;
      return;
    }
    if ('scene' in payload) {
      resourceWorkspace.clear();
      uvInspector.setModel(null);
      if (!options.preserveSelection) {
        selectionStore.set(selectionFromCatalogAsset(payload.scene, {
          exportable: isExportableCatalogAsset(payload.scene),
          workspaceSuggestion: 'entity',
        }));
      }
      if (!options.preserveEntityWorkflow) await showAssetEntityWorkflow(payload.scene, false);
      setMainView('entity');
      overlay.textContent = `${payload.scene.label} selected`;
      return;
    }
    if ('resource' in payload) {
      uvInspector.setModel(null);
      if (!options.preserveSelection) {
        selectionStore.set(selectionFromCatalogAsset(payload.resource, {
          exportable: isExportableCatalogAsset(payload.resource),
          workspaceSuggestion: 'resource',
        }));
      }
      if (!options.preserveEntityWorkflow) await showAssetEntityWorkflow(payload.resource, false);
      const stats = payload.resource.stats;
      const audioUrl = 'semantic_layout' in stats && stats.semantic_layout === 'sample_wave_audio'
        ? catalogAudioUrl(payload.resource)
        : null;
      resourceWorkspace.setResource(payload.resource, undefined, audioUrl);
      setMainView('resource');
      overlay.textContent = `${payload.resource.label} selected`;
      return;
    }
    showModel(payload, { preserveSelection: options.preserveSelection });
    if (payload.catalog_asset && !options.preserveEntityWorkflow) await showAssetEntityWorkflow(payload.catalog_asset, hasSceneUsages(payload.catalog_asset));
  }, { label: asset.kind === 'model' ? `Decoding ${asset.label}` : `Loading ${asset.label}` });
}

async function openLinkedVisualAsset(assetId: string): Promise<void> {
  const asset = findCatalogAsset(assetId);
  if (!asset) {
    errorBox.textContent = `Catalog asset not found: ${assetId}`;
    return;
  }
  await selectCatalogAsset(asset, { preserveSelection: true, preserveEntityWorkflow: true });
}

async function showAssetEntityWorkflow(asset: CatalogAsset, activate: boolean): Promise<void> {
  try {
    const workflow = await loadAssetEntityWorkflow(asset);
    entityView.setWorkflow(workflow);
    if (activate) {
      const entitySelection = selectionFromEntityWorkflow(workflow);
      if (entitySelection) selectionStore.set(entitySelection);
      setMainView('entity');
    }
  } catch {
    entityView.setWorkflow(null);
  }
}

function hasSceneUsages(asset: CatalogAsset): boolean {
  return (asset.scene_usages?.length || 0) > 0;
}

async function loadSpriteFrame(asset: CatalogAsset): Promise<SpritePayload> {
  const payload = await loadCatalogAsset(asset);
  if (!('sprite' in payload)) throw new Error(`Catalog asset is not a sprite frame: ${asset.id}`);
  return payload;
}

function spriteRangeAssets(spriteAsset: CatalogAsset): CatalogAsset[] {
  const stats = spriteAsset.stats;
  if (!currentCatalog || !('semantic_layout' in stats) || stats.semantic_layout !== 'lsp_sprite_frame' || !stats.anim3ds_info) {
    return [spriteAsset];
  }
  const range = stats.anim3ds_info;
  const assets = currentCatalog.assets.filter((asset) => {
    if (asset.kind !== 'sprite' || asset.entry_type !== 'anim3ds-frame') return false;
    const assetStats = asset.stats;
    if (!('semantic_layout' in assetStats) || assetStats.semantic_layout !== 'lsp_sprite_frame' || !assetStats.anim3ds_info) return false;
    return assetStats.anim3ds_info.name === range.name
      && assetStats.anim3ds_info.start_frame === range.start_frame
      && assetStats.anim3ds_info.end_frame === range.end_frame;
  });
  assets.sort((a, b) => {
    const aStats = a.stats;
    const bStats = b.stats;
    const aFrame = 'semantic_layout' in aStats && aStats.semantic_layout === 'lsp_sprite_frame'
      ? aStats.anim3ds_info?.relative_frame ?? a.source.entry_index
      : a.source.entry_index;
    const bFrame = 'semantic_layout' in bStats && bStats.semantic_layout === 'lsp_sprite_frame'
      ? bStats.anim3ds_info?.relative_frame ?? b.source.entry_index
      : b.source.entry_index;
    return aFrame - bFrame || a.source.entry_index - b.source.entry_index;
  });
  return assets.length > 0 ? assets : [spriteAsset];
}

function showModel(model: Lm2Model, options: { preserveSelection?: boolean } = {}): void {
  resourceWorkspace.clear();
  setMainView('model');
  scene.loadModel(model);
  renderStats(stats, model);
  uvInspector.setModel(model);
  overlay.textContent = model.source || 'Uploaded model';
  if (model.catalog_asset && !options.preserveSelection) {
    selectionStore.set(selectionFromCatalogAsset(model.catalog_asset, {
      exportable: model.catalog_asset.kind === 'model',
      workspaceSuggestion: 'model',
    }));
  }
  const catalogBodyAsset = model.catalog_asset?.kind === 'model' ? model.catalog_asset : null;
  catalogUi.setSelectedModel(catalogBodyAsset);
  animationController.setBodyAsset(catalogBodyAsset || (model.pose ? animationController.selectedBodyAsset : null));
  updateCanvasAnimationSelect(animationController.selectedBodyAsset);
  animationController.updateControls();
}

function setMainView(view: MainView): void {
  for (const [key, entry] of Object.entries(mainViews) as Array<[MainView, typeof mainViews[MainView]]>) {
    const active = key === view;
    entry.panel.hidden = !active;
    entry.panel.classList.toggle('active', active);
    entry.tab.classList.toggle('active', active);
    entry.tab.setAttribute('aria-pressed', String(active));
  }
  if (view === 'model') {
    overlay.hidden = false;
    scene.resize();
  } else if (view === 'sprite') {
    overlay.hidden = true;
    spriteViewer.resize();
  } else if (view === 'resource') {
    overlay.hidden = true;
    resourceWorkspace.resize();
  } else {
    overlay.hidden = true;
  }
}

function selectCanvasAnimation(): void {
  const asset = findCatalogAsset(canvasAnimationSelect.value);
  if (!asset || asset.kind !== 'animation' || asset.entry_type !== 'animation') return;
  animationController.setAnimationAsset(asset);
  selectionStore.set(selectionFromCatalogAsset(asset, {
    workspaceSuggestion: 'model',
    compatibilityStatus: animationController.selectedBodyAsset
      ? animationCompatibilityPrefix(asset, animationController.selectedBodyAsset).trim() || undefined
      : undefined,
  }));
  overlay.textContent = `${asset.label} selected`;
  updateCanvasAnimationSelect(animationController.selectedBodyAsset);
}

function updateCanvasAnimationSelect(modelAsset: CatalogAsset | null): void {
  canvasAnimationSelect.replaceChildren();
  if (!currentCatalog || !modelAsset) {
    canvasAnimationSelect.append(new Option('No model selected', ''));
    canvasAnimationSelect.disabled = true;
    return;
  }

  const animations = compatibleAnimations(modelAsset);
  if (animations.length === 0) {
    canvasAnimationSelect.append(new Option('No compatible animations', ''));
    canvasAnimationSelect.disabled = true;
    return;
  }

  canvasAnimationSelect.append(new Option(`${animations.length} compatible animations`, ''));
  for (const animation of animations) {
    canvasAnimationSelect.append(new Option(`${animationCompatibilityPrefix(animation, modelAsset)}${animation.label}`, animation.id));
  }
  canvasAnimationSelect.disabled = false;
  const selectedAnimation = animationController.selectedAnimationAsset;
  canvasAnimationSelect.value = selectedAnimation && animations.some((animation) => animation.id === selectedAnimation.id)
    ? selectedAnimation.id
    : '';
}

function compatibleAnimations(modelAsset: CatalogAsset): CatalogAsset[] {
  return (currentCatalog?.assets || [])
    .filter((asset) => animationMatchesModel(asset, modelAsset))
    .sort((a, b) => a.source.entry_index - b.source.entry_index || a.label.localeCompare(b.label));
}

function findCatalogAsset(id: string): CatalogAsset | null {
  return currentCatalog?.assets.find((asset) => asset.id === id) || null;
}

function resourceRecordIdForSelection(selection: AppSelection | null): string | null {
  if (selection?.kind !== 'resource_record' && selection?.kind !== 'palette_context') return null;
  return selection.evidence?.resourceRecord?.stableId || selection.stableId;
}

function assetForUsageStrip(selection: AppSelection | null): CatalogAsset | null {
  if (!selection) return null;
  if (selection.kind === 'scene_usage') return selection.evidence?.usageAsset || null;
  if (selection.kind === 'resource_record') return selection.evidence?.resourceAsset || null;
  if (selection.kind === 'sprite_frame') return findCatalogAsset(selection.stableId.split('#')[0]);
  if (selection.kind !== 'asset') return null;
  return findCatalogAsset(selection.stableId);
}

function renderSceneUsageStrip(selection: AppSelection | null): void {
  const asset = assetForUsageStrip(selection);
  const usages = asset?.scene_usages || [];
  if (!asset || usages.length === 0) {
    sceneUsageStrip.textContent = 'No selected usage strip.';
    return;
  }
  const activeUsageId = selection?.kind === 'scene_usage' ? selection.stableId : '';
  sceneUsageStrip.replaceChildren(...usages.slice(0, 48).map((usage) => {
    const stableId = sceneUsageStableId(asset, usage);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'scene-usage-item';
    button.setAttribute('aria-current', String(stableId === activeUsageId));
    button.title = `${usage.scene_label} object ${usage.object_index} | ${usage.kind} | ${usage.resolution_rule || usage.reference_key || usage.index_rule || 'decoded usage'}`;
    button.addEventListener('click', () => {
      selectionStore.set(selectionFromSceneUsage(asset, usage));
    });
    const title = document.createElement('strong');
    title.textContent = usage.scene_label;
    const object = document.createElement('span');
    object.textContent = `object ${usage.object_index} ${usage.kind}`;
    const target = document.createElement('span');
    target.textContent = usage.target_asset_id;
    const detail = document.createElement('span');
    detail.textContent = usage.script_kind
      ? `${usage.script_kind} ${usage.reference_key || ''} ${usage.reference_value ?? ''}`.trim()
      : usage.backend || usage.resolution_rule || usage.index_rule || 'scene object';
    button.append(title, object, target, detail);
    return button;
  }));
}

function sceneAssetForObjectTable(selection: AppSelection | null): CatalogAsset | null {
  if (!selection) return null;
  if (selection.kind === 'asset') {
    const asset = findCatalogAsset(selection.stableId);
    return asset?.kind === 'scene' ? asset : null;
  }
  if (selection.kind === 'scene_object') {
    return findCatalogAsset(selection.evidence?.entityContract?.scene_asset_id || '');
  }
  if (selection.kind === 'scene_usage') {
    return findCatalogAsset(selection.evidence?.sceneUsage?.scene_asset_id || '');
  }
  if (selection.kind === 'sprite_frame') {
    const asset = findCatalogAsset(selection.stableId.split('#')[0]);
    return asset?.kind === 'scene' ? asset : null;
  }
  return null;
}

function renderSceneObjectTable(selection: AppSelection | null): void {
  const asset = sceneAssetForObjectTable(selection);
  const recon = sceneReconnaissance(asset);
  if (!asset || !recon) {
    sceneObjectTable.textContent = 'No scene object evidence.';
    return;
  }
  const objects: SceneObjectEvidenceRow[] = [
    ...(recon.hero ? [{ index: 0, position: recon.hero.start }] : []),
    ...(recon.sampled_objects || []).filter((object) => object.index !== 0),
  ];
  if (objects.length === 0) {
    sceneObjectTable.textContent = 'No sampled scene objects.';
    return;
  }
  const activeObjectId = selection?.kind === 'scene_object' ? selection.stableId : '';
  const rows = objects.slice(0, 24).map((object) => {
    const links = object.links;
    const body = links?.body?.asset_id || `body ${object.gen_body ?? '-'}`;
    const animation = links?.animation?.asset_id || `anim ${object.gen_anim ?? '-'}`;
    const sprite = links?.sprite?.asset_id || `sprite ${object.sprite ?? '-'}`;
    const render = object.runtime?.render_type || '-';
    const stableId = `${asset.id}#object:${object.index}`;
    return {
      stableId,
      index: String(object.index),
      flags: object.flags === undefined ? '-' : `0x${object.flags.toString(16).toUpperCase()}`,
      file3d: String(object.file3d_index ?? '-'),
      position: object.position ? `${object.position.x},${object.position.y},${object.position.z}` : '-',
      visuals: [body, animation, sprite].join(' | '),
      render,
    };
  });

  const summary = document.createElement('div');
  const total = recon.sampled_object_count ?? objects.length;
  summary.textContent = total > rows.length
    ? `${total} scene object records; showing first ${rows.length}.`
    : `${rows.length} scene object records.`;
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of ['Stable ID', 'Object', 'Flags', 'File3D', 'Position', 'Visuals', 'Render', 'Open']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const object of rows) {
    const row = document.createElement('tr');
    row.setAttribute('aria-current', String(object.stableId === activeObjectId));
    appendCopyableTextCell(row, object.stableId, 'Copy scene object ID');
    appendTextCell(row, object.index);
    appendTextCell(row, object.flags);
    appendTextCell(row, object.file3d);
    appendTextCell(row, object.position);
    appendTextCell(row, object.visuals);
    appendTextCell(row, object.render);
    const openCell = document.createElement('td');
    const open = document.createElement('button');
    open.type = 'button';
    open.textContent = 'Open';
    open.title = `Open ${object.stableId}`;
    open.addEventListener('click', () => {
      void openSceneObject(asset.id, Number(object.index));
    });
    openCell.append(open);
    row.append(openCell);
    body.append(row);
  }
  table.append(head, body);
  sceneObjectTable.replaceChildren(summary, table);
}

async function openSceneObject(sceneAssetId: string, objectIndex: number): Promise<void> {
  catalogSelectionRequestId += 1;
  await runAction(async () => {
    const workflow = await loadSceneObjectEntityWorkflow(sceneAssetId, objectIndex);
    entityView.setWorkflow(workflow);
    const entitySelection = selectionFromEntityWorkflow(workflow);
    if (entitySelection) selectionStore.set(entitySelection);
    setMainView('entity');
  }, { label: `Opening ${sceneAssetId} object ${objectIndex}` });
}

type SceneLocalEvidenceRow = {
  stableId: string;
  kind: string;
  index: string;
  offset: string;
  location: string;
  contract: string;
  target: string;
};

function renderSceneLocalTable(selection: AppSelection | null): void {
  const asset = sceneAssetForObjectTable(selection);
  const recon = sceneReconnaissance(asset);
  if (!asset || !recon) {
    sceneLocalTable.textContent = 'No scene local evidence.';
    return;
  }

  const rows: SceneLocalEvidenceRow[] = [
    ...(recon.sampled_zones || []).slice(0, 12).map((zone) => ({
      stableId: `${asset.id}#zone:${zone.index}`,
      kind: 'Zone',
      index: String(zone.index),
      offset: String(zone.offset),
      location: `${zone.start.x},${zone.start.y},${zone.start.z} -> ${zone.end.x},${zone.end.y},${zone.end.z}`,
      contract: `${zone.type_name} value ${zone.value}; ${zone.runtime?.effect || 'effect unknown'}`,
      target: zone.runtime?.script_controls?.length
        ? zone.runtime.script_controls.map((control) => `${control.opcode}:${control.action}`).join(', ')
        : '-',
    })),
    ...(recon.sampled_tracks || []).slice(0, 12).map((track) => ({
      stableId: `${asset.id}#waypoint:${track.index}`,
      kind: 'Waypoint',
      index: String(track.index),
      offset: String(track.offset),
      location: `${track.position.x},${track.position.y},${track.position.z}`,
      contract: 'track target position',
      target: '-',
    })),
    ...(recon.grm_fragment_links || []).slice(0, 8).map((link) => ({
      stableId: `${asset.id}#zone:${link.zone_index}#grm:${link.grm_index}`,
      kind: 'GRM',
      index: `${link.zone_index}/${link.grm_index}`,
      offset: '-',
      location: `cell ${link.target_cell_start.x},${link.target_cell_start.y},${link.target_cell_start.z}; span ${link.zone_cell_span.x},${link.zone_cell_span.y},${link.zone_cell_span.z}`,
      contract: link.script_control || 'GRM fragment runtime state',
      target: link.asset_id || `LBA_BKG.HQR:${link.resolved_grm_entry ?? '-'}`,
    })),
    ...(recon.sampled_patches || []).slice(0, 12).map((patch) => {
      const target = patch.target;
      const instruction = target.instruction_opcode
        ? `${target.instruction_opcode}${target.patched_field ? `.${target.patched_field}` : ''}`
        : `${target.kind}${target.script_relative_offset === null ? '' : `@${target.script_relative_offset}`}`;
      return {
        stableId: `${asset.id}#patch:${patch.index}`,
        kind: 'Patch',
        index: String(patch.index),
        offset: String(patch.offset),
        location: `target ${patch.target_offset}`,
        contract: `${patch.size} bytes -> ${instruction}`,
        target: `${target.owner || '-'} ${target.instruction_found === false ? 'missing instruction' : target.patched_field_source || target.kind}`,
      };
    }),
  ];

  if (rows.length === 0) {
    sceneLocalTable.textContent = 'No sampled zones, waypoints, GRM links, or patches.';
    return;
  }

  const summary = document.createElement('div');
  summary.textContent = [
    `${recon.zone_count ?? 0} zones`,
    `${recon.track_count ?? 0} waypoints`,
    `${recon.grm_fragment_links?.length ?? 0} GRM links`,
    `${recon.patch_count ?? 0} patches`,
  ].join('; ');
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of ['Stable ID', 'Kind', 'Index', 'Offset', 'Location', 'Runtime Contract', 'Target']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const rowData of rows) {
    const row = document.createElement('tr');
    appendCopyableTextCell(row, rowData.stableId, 'Copy scene local ID');
    appendTextCell(row, rowData.kind);
    appendTextCell(row, rowData.index);
    appendTextCell(row, rowData.offset);
    appendTextCell(row, rowData.location);
    appendTextCell(row, rowData.contract);
    appendTextCell(row, rowData.target);
    body.append(row);
  }
  table.append(head, body);
  sceneLocalTable.replaceChildren(summary, table);
}

function renderPortEvidenceTable(selection: AppSelection | null): void {
  if (portPromotionError) {
    portEvidenceTable.textContent = `Port evidence unavailable: ${portPromotionError}`;
    return;
  }
  if (!portPromotionPackets) {
    portEvidenceTable.textContent = 'Port evidence not loaded.';
    return;
  }
  const target = portEvidenceTarget(selection);
  if (!target) {
    portEvidenceTable.textContent = `No port promotion packet target for this selection. Manifest: ${portPromotionPackets.manifest}.`;
    return;
  }
  const packets = portPromotionPackets.packets.filter((packet) => packet.fixture_source?.scene === target.sceneIndex);
  const summary = document.createElement('div');
  summary.textContent = packets.length
    ? `${packets.length} promotion packet${packets.length === 1 ? '' : 's'} for scene ${target.sceneIndex}. Canonical runtime is copied only from live-positive or approved-exception packets.`
    : `Scene ${target.sceneIndex} has no matching promotion packet; canonical_runtime is unknown/unpromoted. viewer_loadable and preview success are admission hints only.`;
  if (packets.length === 0) {
    portEvidenceTable.replaceChildren(summary);
    return;
  }

  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of ['Packet ID', 'Evidence Class', 'Status', 'Canonical Runtime', 'Runtime Contracts', 'Fixture', 'Source Doc']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const packet of packets) {
    const row = document.createElement('tr');
    appendCopyableTextCell(row, packet.id, 'Copy packet ID');
    appendTextCell(row, packet.evidence_class);
    const statusCell = document.createElement('td');
    const status = document.createElement('span');
    status.className = 'evidence-status';
    status.dataset.status = packet.status;
    status.textContent = packet.status;
    statusCell.append(status);
    row.append(statusCell);
    appendTextCell(row, packet.canonical_runtime && (packet.status === 'live_positive' || packet.status === 'approved_exception') ? 'true' : 'false');
    appendTextCell(row, packet.runtime_contracts.length ? packet.runtime_contracts.join(', ') : '-');
    appendTextCell(row, packet.fixture || '-');
    appendTextCell(row, packet.packet);
    body.append(row);
  }
  table.append(head, body);
  portEvidenceTable.replaceChildren(summary, table);
}

function appendTextCell(row: HTMLTableRowElement, value: string): void {
  const cell = document.createElement('td');
  cell.textContent = value;
  cell.title = value;
  row.append(cell);
}

function appendCopyableTextCell(row: HTMLTableRowElement, value: string, label: string): void {
  const cell = document.createElement('td');
  cell.className = 'copyable-cell';
  const code = document.createElement('code');
  code.textContent = value;
  code.title = value;
  const copy = document.createElement('button');
  copy.type = 'button';
  copy.textContent = 'Copy';
  copy.title = `${label}: ${value}`;
  copy.addEventListener('click', () => {
    void copyText(value);
  });
  cell.append(code, copy);
  row.append(cell);
}

function portEvidenceTarget(selection: AppSelection | null): { sceneAssetId: string; sceneIndex: number } | null {
  if (!selection) return null;
  const scriptTarget = scriptTargetForSelection(selection);
  if (scriptTarget) {
    const asset = findCatalogAsset(scriptTarget.sceneAssetId);
    const sceneIndex = sceneIndexForAsset(asset);
    return asset && sceneIndex !== null ? { sceneAssetId: asset.id, sceneIndex } : null;
  }
  if (selection.kind === 'asset') {
    const asset = findCatalogAsset(selection.stableId);
    const sceneIndex = sceneIndexForAsset(asset);
    return asset?.kind === 'scene' && sceneIndex !== null ? { sceneAssetId: asset.id, sceneIndex } : null;
  }
  return null;
}

function sceneIndexForAsset(asset: CatalogAsset | null): number | null {
  if (!asset || asset.kind !== 'scene') return null;
  return typeof asset.source.entry_index === 'number' ? asset.source.entry_index - 1 : null;
}

function renderRawDescriptorTable(selection: AppSelection | null): void {
  const asset = assetForUsageStrip(selection);
  const stats = asset?.stats;
  const descriptors = stats && 'unknown_descriptors' in stats ? stats.unknown_descriptors : [];
  if (!asset || descriptors.length === 0) {
    rawDescriptorTable.textContent = 'No raw descriptors.';
    return;
  }

  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of ['Stable ID', 'Section', 'Offset', 'Length', 'Confidence', 'Note', 'SHA-256']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);

  const body = document.createElement('tbody');
  for (const descriptor of descriptors.slice(0, 24)) {
    const row = document.createElement('tr');
    appendCopyableTextCell(row, `${asset.id}#descriptor:${descriptor.section}@${descriptor.offset}`, 'Copy descriptor ID');
    for (const value of [
      descriptor.section,
      String(descriptor.offset),
      String(descriptor.length),
      descriptor.confidence,
      descriptor.note,
      descriptor.sha256,
    ]) {
      const cell = document.createElement('td');
      cell.textContent = value;
      cell.title = value;
      row.append(cell);
    }
    body.append(row);
  }
  table.append(head, body);

  const summary = document.createElement('div');
  summary.textContent = descriptors.length > 24
    ? `${descriptors.length} descriptors; showing first 24 for ${asset.id}.`
    : `${descriptors.length} descriptors for ${asset.id}.`;
  rawDescriptorTable.replaceChildren(summary, table);
}

type ScriptEvidence = {
  ownerStableId: string;
  scriptKind: 'track' | 'life';
  analysis: SceneScriptAnalysis;
};

type ScriptOwner = {
  track_script_analysis?: SceneScriptAnalysis;
  life_script_analysis?: SceneScriptAnalysis;
};

type SceneObjectEvidenceRow = {
  index: number;
  flags?: number;
  file3d_index?: number;
  gen_body?: number;
  gen_anim?: number;
  sprite?: number;
  position?: { x: number; y: number; z: number };
  runtime?: { render_type?: string };
  links?: {
    body?: { asset_id?: string | null } | null;
    animation?: { asset_id?: string | null } | null;
    sprite?: { asset_id?: string | null } | null;
  };
};

function renderScriptEvidenceTable(selection: AppSelection | null): void {
  const scripts = scriptEvidenceForSelection(selection);
  if (scripts.length === 0) {
    scriptEvidenceTable.textContent = 'No script/control-flow evidence.';
    return;
  }

  const instructionRows = scripts.flatMap((script) =>
    script.analysis.first_instructions.slice(0, 12).map((instruction) => ({
      stableId: `${script.ownerStableId}#script:${script.scriptKind}@${instruction.offset}`,
      script,
      offset: instruction.offset,
      opcode: instruction.mnemonic,
      bytes: instruction.byte_length,
      category: instruction.behavior_category,
      effect: instruction.behavior_effect,
    })),
  ).slice(0, 24);

  const controlRows = scripts.flatMap((script) =>
    (script.analysis.control_flow_links || []).slice(0, 12).map((link) => ({
      stableId: `${script.ownerStableId}#script:${script.scriptKind}@${link.source_offset}->${link.target_script_kind}:${link.target_offset}`,
      script,
      source: `${link.source_offset} ${link.source_opcode}`,
      target: `${link.target_script_kind} ${link.target_offset}`,
      found: link.target_found ? 'found' : 'missing',
      status: link.target_status || '-',
      targetOpcode: link.target_opcode || link.target_containing_opcode || link.target_previous_decoded_opcode || '-',
    })),
  ).slice(0, 24);

  const summary = document.createElement('div');
  const instructionCount = scripts.reduce((total, script) => total + script.analysis.instruction_count, 0);
  const controlCount = scripts.reduce((total, script) => total + (script.analysis.control_flow_links_total ?? script.analysis.control_flow_links?.length ?? 0), 0);
  summary.textContent = `${scripts.length} decoded scripts, ${instructionCount} instructions, ${controlCount} control-flow links.`;

  const nodes: HTMLElement[] = [summary];
  nodes.push(renderEvidenceTable('Instruction Samples', ['Stable ID', 'Script', 'Offset', 'Opcode', 'Bytes', 'Category', 'Effect'], instructionRows.map((row) => [
    row.stableId,
    row.script.scriptKind,
    String(row.offset),
    row.opcode,
    String(row.bytes),
    row.category,
    row.effect,
  ])));
  nodes.push(renderEvidenceTable('Control Flow', ['Stable ID', 'Script', 'Source', 'Target', 'Found', 'Status', 'Target Opcode'], controlRows.map((row) => [
    row.stableId,
    row.script.scriptKind,
    row.source,
    row.target,
    row.found,
    row.status,
    row.targetOpcode,
  ])));
  scriptEvidenceTable.replaceChildren(...nodes);
}

function renderEvidenceTable(titleText: string, headers: string[], rows: string[][]): HTMLElement {
  const wrapper = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = titleText;
  wrapper.append(title);
  if (rows.length === 0) {
    const empty = document.createElement('div');
    empty.textContent = 'No sampled rows.';
    wrapper.append(empty);
    return wrapper;
  }
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const header of headers) {
    const cell = document.createElement('th');
    cell.textContent = header;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const values of rows) {
    const row = document.createElement('tr');
    for (const [index, value] of values.entries()) {
      const cell = document.createElement('td');
      if (headers[index] === 'Stable ID') {
        cell.className = 'copyable-cell';
        const code = document.createElement('code');
        code.textContent = value;
        code.title = value;
        const copy = document.createElement('button');
        copy.type = 'button';
        copy.textContent = 'Copy';
        copy.title = `Copy stable ID: ${value}`;
        copy.addEventListener('click', () => {
          void copyText(value);
        });
        cell.append(code, copy);
      } else {
        cell.textContent = value;
        cell.title = value;
      }
      row.append(cell);
    }
    body.append(row);
  }
  table.append(head, body);
  wrapper.append(table);
  return wrapper;
}

function scriptEvidenceForSelection(selection: AppSelection | null): ScriptEvidence[] {
  if (!selection) return [];
  const target = scriptTargetForSelection(selection);
  if (!target) return [];
  const asset = findCatalogAsset(target.sceneAssetId);
  const recon = sceneReconnaissance(asset);
  if (!recon) return [];
  const owner = findScriptOwner(recon, target.objectIndex);
  if (!owner) return [];
  return ([
    ['track', owner.track_script_analysis],
    ['life', owner.life_script_analysis],
  ] as const)
    .filter((entry): entry is readonly ['track' | 'life', SceneScriptAnalysis] => Boolean(entry[1]))
    .map(([scriptKind, analysis]) => ({
      ownerStableId: target.ownerStableId,
      scriptKind,
      analysis,
    }));
}

function scriptTargetForSelection(selection: AppSelection): { sceneAssetId: string; objectIndex: number; ownerStableId: string } | null {
  if (selection.kind === 'scene_object') {
    const entity = selection.evidence?.entityContract;
    return entity?.scene_asset_id && entity.object_index !== null
      ? { sceneAssetId: entity.scene_asset_id, objectIndex: entity.object_index, ownerStableId: entity.entity_id }
      : null;
  }
  if (selection.kind === 'scene_usage') {
    const usage = selection.evidence?.sceneUsage;
    return usage?.scene_asset_id && usage.object_index !== null
      ? { sceneAssetId: usage.scene_asset_id, objectIndex: usage.object_index, ownerStableId: `${usage.scene_asset_id}#object:${usage.object_index}` }
      : null;
  }
  if (selection.kind === 'asset') {
    const asset = findCatalogAsset(selection.stableId);
    return asset?.kind === 'scene'
      ? { sceneAssetId: asset.id, objectIndex: 0, ownerStableId: `${asset.id}#object:0` }
      : null;
  }
  if (selection.kind === 'sprite_frame') {
    const asset = findCatalogAsset(selection.stableId.split('#')[0]);
    return asset?.kind === 'scene'
      ? { sceneAssetId: asset.id, objectIndex: 0, ownerStableId: `${asset.id}#object:0` }
      : null;
  }
  return null;
}

function sceneReconnaissance(asset: CatalogAsset | null): SceneStats['reconnaissance'] | null {
  const stats = asset?.stats as Partial<SceneStats> | undefined;
  return stats?.semantic_layout === 'scene_runtime_layout_partial' && stats.reconnaissance ? stats.reconnaissance : null;
}

function findScriptOwner(recon: SceneStats['reconnaissance'], objectIndex: number): ScriptOwner | null {
  if (objectIndex === 0 && recon.hero) return recon.hero;
  return (recon.sampled_objects || []).find((object) => object.index === objectIndex) || null;
}

function renderSelectionInspector(selection: AppSelection | null): void {
  if (!selection) {
    inspector.clear('Select a catalog entry to inspect it.');
    return;
  }
  if (selection.kind === 'evidence_artifact') {
    inspector.setSections(evidenceArtifactInspectorSections(selection));
    return;
  }
  if (selection.kind === 'scene_object') {
    const sections = sceneObjectInspectorSections(selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (selection.kind === 'model_surface') {
    const sections = modelSurfaceInspectorSections(selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (selection.kind === 'animation_sample') {
    const sections = animationSampleInspectorSections(selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (selection.kind === 'resource_record') {
    const sections = resourceRecordInspectorSections(selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (selection.kind === 'scene_usage') {
    const sections = sceneUsageInspectorSections(selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (isEntityFacetSelection(selection.kind)) {
    const sections = entityFacetInspectorSections(selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (selection.kind !== 'asset' && selection.kind !== 'sprite_frame') return;
  const asset = findCatalogAsset(selection.kind === 'sprite_frame' ? selection.stableId.split('#')[0] : selection.stableId);
  if (!asset) return;
  if (asset.kind === 'model') {
    inspector.setSections(modelInspectorSections(asset, selection));
    return;
  }
  const rawAnimationSections = rawAnimationInspectorSections(asset, selection);
  if (rawAnimationSections.length > 0) {
    inspector.setSections(rawAnimationSections);
    return;
  }
  if (asset.kind === 'animation' && asset.entry_type === 'animation') {
    inspector.setSections(animationInspectorSections(asset, selection));
    return;
  }
  if (asset.kind === 'scene') {
    const sections = sceneInspectorSections(asset, selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  const anim3dsRangeSections = anim3dsRangeInspectorSections(asset, selection);
  if (anim3dsRangeSections.length > 0) {
    inspector.setSections(anim3dsRangeSections);
    return;
  }
  if (asset.kind === 'sprite') {
    const sections = spriteFrameInspectorSections(asset, selection);
    if (sections.length > 0) inspector.setSections(sections);
    return;
  }
  if (asset.kind === 'resource') {
    const sections = [
      ...sampleAudioInspectorSections(asset, selection),
      ...smackerVideoInspectorSections(asset, selection),
      ...textOrderInspectorSections(asset, selection),
      ...textPayloadInspectorSections(asset, selection),
      ...paletteImageInspectorSections(asset, selection),
      ...runtimeTableInspectorSections(asset, selection),
      ...holomapInspectorSections(asset, selection),
      ...backgroundInspectorSections(asset, selection),
      ...unclassifiedResourceInspectorSections(asset, selection),
    ];
    if (sections.length > 0) inspector.setSections(sections);
  }
}

function isEntityFacetSelection(kind: AppSelection['kind']): kind is EntityFacetSelectionKind | 'palette_context' {
  return kind === 'runtime_sprite_state'
    || kind === 'file3d_resolution'
    || kind === 'anim3ds_range_state'
    || kind === 'render_contract'
    || kind === 'palette_context';
}

function isRawAnimationInspectorAsset(asset: CatalogAsset): boolean {
  const stats = asset.stats;
  return (asset.kind === 'animation' || asset.kind === 'sprite')
    && 'parse_status' in stats
    && stats.parse_status === 'raw'
    && 'semantic_layout' in stats
    && stats.semantic_layout === 'unknown';
}

function isExportableCatalogAsset(asset: CatalogAsset): boolean {
  if (asset.kind === 'model') return true;
  const stats = asset.stats;
  if (!('semantic_layout' in stats)) return false;
  return (
    (asset.kind === 'sprite' && (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame'))
    || (
      asset.kind === 'resource'
      && (
        stats.semantic_layout === 'bkg_grid_map'
        || stats.semantic_layout === 'screen_indexed_image_640x480'
        || stats.semantic_layout === 'lba2_indexed_image_256'
        || stats.semantic_layout === 'lba2_texture_atlas_indexed'
        || stats.semantic_layout === 'holomap_plan_image_640x480'
        || stats.semantic_layout === 'sample_wave_audio'
        || stats.semantic_layout === 'text_payload_bank'
        || stats.semantic_layout === 'smacker_video'
      )
    )
    || (asset.kind === 'scene' && stats.semantic_layout === 'scene_runtime_layout_partial' && stats.reconnaissance.background?.resolved_gri_entry !== undefined)
  );
}

async function exportSelectedAsset(): Promise<void> {
  const exportAction = selectionStore.current?.exportActions[0];
  const exportAssetId = exportAction?.targetAssetId;
  const exportAsset = exportAssetId ? findCatalogAsset(exportAssetId) : null;
  if (!exportAsset) throw new Error('Select an exportable catalog model, sprite frame, sample, indexed image, background grid, or scene background before exporting.');
  exportResult.textContent = '';
  const polygonMode = selectedPolygonMode();
  const result = await exportCatalogAsset(exportAsset, polygonMode);
  const fileEntries = collectManifestFiles(result.manifest.files);
  const fileCount = fileEntries.filter(Boolean).length;
  exportResult.textContent = `Wrote ${fileCount} files to ${result.output_dir}`;
  overlay.textContent = `Exported ${result.manifest.source.catalog_label || result.manifest.source.catalog_asset_id}`;
  selectionStore.set({
    kind: 'evidence_artifact',
    stableId: `${result.manifest.source.catalog_asset_id}#export:${result.manifest.files.manifest}`,
    label: `Export manifest for ${result.manifest.source.catalog_label || result.manifest.source.catalog_asset_id}`,
    provenance: result.output_dir,
    evidenceStatus: 'decoded_only',
    links: [{ kind: 'asset', stableId: result.manifest.source.catalog_asset_id, label: result.manifest.source.catalog_label || result.manifest.source.catalog_asset_id }],
    unknowns: result.manifest.warnings || [],
    previewActions: [],
    exportActions: [],
    facets: {
      outputDir: result.output_dir,
      fileCount,
      polygonMode: result.manifest.options.polygon_mode,
      manifest: result.manifest.files.manifest,
      generatedFiles: fileEntries.filter(Boolean).join(', '),
      sourceAssetId: result.manifest.source.catalog_asset_id,
      sourceLabel: result.manifest.source.catalog_label || result.manifest.source.catalog_asset_id,
    },
  });
}

function collectManifestFiles(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap((entry) => collectManifestFiles(entry));
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (typeof record.path === 'string') return [record.path];
    return Object.values(record).flatMap((entry) => collectManifestFiles(entry));
  }
  return [];
}

function renderActiveSelection(selection: AppSelection | null): void {
  activeSelectionPanel.replaceChildren();
  if (!selection) {
    activeSelectionPanel.textContent = 'No active selection.';
    return;
  }

  const heading = document.createElement('div');
  heading.className = 'selection-heading';
  const title = document.createElement('strong');
  title.textContent = selection.label;
  const kind = document.createElement('span');
  kind.className = 'selection-kind';
  kind.textContent = selection.kind;
  heading.append(title, kind);

  const status = document.createElement('span');
  status.className = 'evidence-status';
  status.dataset.status = selection.evidenceStatus;
  status.textContent = selection.evidenceStatus;

  const actions = document.createElement('div');
  actions.className = 'selection-actions';
  const copy = document.createElement('button');
  copy.type = 'button';
  copy.textContent = 'Copy ID';
  copy.addEventListener('click', () => {
    void copyText(selection.stableId);
  });
  actions.append(copy);
  for (const action of selection.previewActions) {
    const actionButton = document.createElement('button');
    actionButton.type = 'button';
    actionButton.textContent = action.label;
    actionButton.addEventListener('click', () => {
      void handleSelectionPreviewAction(action);
    });
    actions.append(actionButton);
  }
  if (selection.exportActions.length) {
    const exportLabel = document.createElement('button');
    exportLabel.type = 'button';
    exportLabel.textContent = selection.exportActions[0].label;
    exportLabel.addEventListener('click', () => {
      void runAction(exportSelectedAsset, { label: 'Exporting evidence probe' });
    });
    actions.append(exportLabel);
  }

  const rows = [
    selectionRow('Stable ID', selection.stableId),
    selection.source?.archive !== undefined ? selectionRow('Source', `${selection.source.archive}[${selection.source.entryIndex ?? '-'}]`) : null,
    selectionRow('Status', status),
    selectionRow('Provenance', selection.provenance),
    selection.compatibilityStatus ? selectionRow('Compat', selection.compatibilityStatus) : null,
    selection.workspaceSuggestion ? selectionRow('Workspace', selection.workspaceSuggestion) : null,
    selection.links.length ? selectionRow('Links', selection.links.map((link) => link.stableId).join(', ')) : null,
    selection.unknowns.length ? selectionRow('Unknowns', selection.unknowns.join(' | ')) : null,
  ].filter((row): row is HTMLElement => row !== null);

  activeSelectionPanel.append(heading, ...rows, actions);
}

async function handleSelectionPreviewAction(action: AppSelection['previewActions'][number]): Promise<void> {
  if (!action.targetAssetId) return;
  await openLinkedVisualAsset(action.targetAssetId);
}

function selectionRow(label: string, value: string | HTMLElement): HTMLElement {
  const row = document.createElement('div');
  row.className = 'selection-row';
  const key = document.createElement('span');
  key.textContent = label;
  const val = document.createElement('strong');
  if (typeof value === 'string') {
    val.textContent = value;
  } else {
    val.append(value);
  }
  row.append(key, val);
  return row;
}

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    exportResult.textContent = `Copied ${text}`;
  } catch {
    exportResult.textContent = text;
  }
}

function updateExportControls(): void {
  exportAssetButton.disabled = selectionStore.current?.exportActions.length !== 1;
}

function selectedPolygonMode(): PolygonMode {
  if (exportPolygonMode.value === 'original' || exportPolygonMode.value === 'triangulated') {
    return exportPolygonMode.value;
  }
  throw new Error(`Unsupported polygon mode: ${exportPolygonMode.value}`);
}

function refreshVisibility(): void {
  const visibility: VisibilityState = {
    faces: showFaces.checked,
    lines: showLines.checked,
    spheres: showSpheres.checked,
    wireframe: wireframe.checked,
    grid: showGrid.checked,
  };
  scene.applyVisibility(visibility);
}

function refreshHorizonLock(): void {
  scene.setLockHorizon(lockHorizon.checked);
  horizonIndicator.classList.toggle('locked', lockHorizon.checked);
  const label = lockHorizon.checked ? 'Horizon locked' : 'Horizon free';
  const actionLabel = lockHorizon.checked ? 'Unlock horizon' : 'Lock horizon';
  horizonIndicator.setAttribute('aria-label', label);
  horizonIndicator.title = label;
  horizonLockToggle.setAttribute('aria-pressed', String(lockHorizon.checked));
  horizonLockToggle.setAttribute('aria-label', actionLabel);
  horizonLockToggle.title = actionLabel;
}

function setDockCollapsed(side: DockSide, collapsed: boolean): void {
  const className = `${side}-collapsed`;
  const toggle = side === 'explorer' ? explorerDockToggle : inspectorDockToggle;
  const label = collapsed
    ? `Expand ${side} sidebar`
    : `Collapse ${side} sidebar`;
  app.classList.toggle(className, collapsed);
  toggle.setAttribute('aria-expanded', String(!collapsed));
  toggle.setAttribute('aria-label', label);
  toggle.title = label;
  requestAnimationFrame(() => {
    scene.resize();
    spriteViewer.resize();
    resourceWorkspace.resize();
  });
}

function setInspectorTab(tab: InspectorTab): void {
  for (const [key, entry] of Object.entries(inspectorTabs) as Array<[InspectorTab, typeof inspectorTabs[InspectorTab]]>) {
    const active = key === tab;
    entry.panel.hidden = !active;
    entry.panel.classList.toggle('active', active);
    entry.tab.classList.toggle('active', active);
    entry.tab.setAttribute('aria-selected', String(active));
  }
}

function refreshCanvasBackground(): void {
  const mode: CanvasBackgroundMode = lightCanvas.checked ? 'light' : 'dark';
  scene.setBackground(mode, selectedCanvasBackgroundShade);
  document.body.dataset.canvasBackground = mode;
  document.body.dataset.canvasBackgroundShade = String(selectedCanvasBackgroundShade);
  canvasBackgroundToggle.textContent = '';
  canvasBackgroundToggle.setAttribute('aria-pressed', String(mode === 'light'));
  canvasBackgroundToggle.title = mode === 'light' ? 'Switch to dark canvas background' : 'Switch to light canvas background';
  canvasBackgroundToggle.setAttribute('aria-label', canvasBackgroundToggle.title);
  const shadeColor = canvasBackgroundColor(mode, selectedCanvasBackgroundShade);
  canvasBackgroundShade.style.setProperty('--shade-color', shadeColor);
  canvasBackgroundShade.textContent = '';
  canvasBackgroundShade.title = `Choose ${mode} canvas background shade`;
  canvasBackgroundShade.setAttribute('aria-label', `${mode} canvas background shade ${selectedCanvasBackgroundShade}`);
  localStorage.setItem(backgroundStorageKeys.mode, mode);
  localStorage.setItem(backgroundStorageKeys.shade, String(selectedCanvasBackgroundShade));
}

function restoreCanvasBackgroundPreference(): void {
  const storedMode = localStorage.getItem(backgroundStorageKeys.mode);
  const storedShade = localStorage.getItem(backgroundStorageKeys.shade);
  lightCanvas.checked = storedMode === 'light';
  selectedCanvasBackgroundShade = storedCanvasBackgroundShade(storedShade);
}

function renderBackgroundShadePicker(): void {
  const mode: CanvasBackgroundMode = lightCanvas.checked ? 'light' : 'dark';
  const [start, end] = canvasBackgroundSliderStops(mode);
  const slider = document.createElement('input');
  slider.id = 'canvasBackgroundShadeSlider';
  slider.className = 'shade-slider';
  slider.type = 'range';
  slider.min = '0';
  slider.max = '100';
  slider.step = '1';
  slider.value = String(selectedCanvasBackgroundShade);
  slider.setAttribute('aria-label', `${mode} canvas background shade`);
  slider.style.setProperty('--slider-start', start);
  slider.style.setProperty('--slider-end', end);
  slider.addEventListener('input', () => {
    selectedCanvasBackgroundShade = Number(slider.value);
    refreshCanvasBackground();
  });
  canvasBackgroundShadePicker.replaceChildren(slider);
}

function hideBackgroundShadePicker(): void {
  canvasBackgroundShadePicker.hidden = true;
  canvasBackgroundShade.setAttribute('aria-expanded', 'false');
}

function hideViewControlsPopover(): void {
  viewControlsPopover.hidden = true;
  viewControlsToggle.setAttribute('aria-expanded', 'false');
}

function storedCanvasBackgroundShade(value: string | null): CanvasBackgroundShade {
  const shade = Number(value);
  if (!Number.isFinite(shade)) return selectedCanvasBackgroundShade;
  return Math.max(0, Math.min(100, Math.round(shade)));
}

async function runAction(action: () => Promise<void>, progress?: { label: string; pollServer?: boolean }): Promise<void> {
  errorBox.textContent = '';
  if (progress) beginProgress(progress);
  try {
    await action();
    if (progress) endProgress(true);
  } catch (error) {
    errorBox.textContent = error instanceof Error ? error.message : String(error);
    if (progress) endProgress(false);
  }
}

function beginProgress({ label, pollServer = false }: { label: string; pollServer?: boolean }): void {
  clearProgressTimers();
  if (progressHideTimer !== undefined) {
    window.clearTimeout(progressHideTimer);
    progressHideTimer = undefined;
  }
  progressStartedAt = performance.now();
  progressPanel.hidden = false;
  progressBar.classList.toggle('indeterminate', !pollServer);
  progressBar.classList.remove('error');
  progressText.textContent = label;
  progressMeta.textContent = '0.0s';
  progressFill.style.width = pollServer ? '0%' : '42%';
  progressBar.setAttribute('aria-valuenow', '0');
  progressInterval = window.setInterval(() => {
    if (pollServer) {
      void updateServerProgress(label);
    } else {
      updateLocalProgress(label);
    }
  }, 150);
  if (pollServer) {
    void updateServerProgress(label);
  } else {
    updateLocalProgress(label);
  }
}

function updateLocalProgress(label: string): void {
  progressText.textContent = label;
  progressMeta.textContent = formatElapsed((performance.now() - progressStartedAt) / 1000);
  progressBar.classList.add('indeterminate');
  progressBar.removeAttribute('aria-valuenow');
}

async function updateServerProgress(localLabel: string): Promise<void> {
  try {
    renderProgress(await fetchDecodeProgress(), localLabel);
  } catch {
    updateLocalProgress(localLabel);
  }
}

function renderProgress(progress: DecodeProgress, localLabel: string): void {
  progressText.textContent = progress.label || localLabel;
  progressMeta.textContent = formatProgressMeta(progress);

  if (progress.total > 0 && progress.percent !== null) {
    const percent = Math.max(0, Math.min(100, progress.percent * 100));
    progressBar.classList.remove('indeterminate');
    progressFill.style.width = `${percent}%`;
    progressBar.setAttribute('aria-valuenow', String(Math.round(percent)));
  } else {
    progressBar.classList.add('indeterminate');
    progressBar.removeAttribute('aria-valuenow');
  }

  progressBar.classList.toggle('error', progress.phase === 'error');
}

function formatProgressMeta(progress: DecodeProgress): string {
  const elapsed = formatElapsed(progress.elapsed_seconds);
  if (progress.total > 0) {
    return `${progress.current}/${progress.total} entries, ${elapsed}`;
  }
  return elapsed;
}

function endProgress(success: boolean): void {
  clearProgressTimers();
  progressBar.classList.remove('indeterminate');
  progressBar.classList.toggle('error', !success);
  progressFill.style.width = '100%';
  progressBar.setAttribute('aria-valuenow', success ? '100' : '0');
  progressText.textContent = success ? 'Decode complete' : 'Decode failed';
  progressMeta.textContent = formatElapsed((performance.now() - progressStartedAt) / 1000);
  if (success) {
    progressHideTimer = window.setTimeout(() => {
      progressPanel.hidden = true;
      progressHideTimer = undefined;
    }, 650);
  }
}

function clearProgressTimers(): void {
  if (progressInterval !== undefined) {
    window.clearInterval(progressInterval);
    progressInterval = undefined;
  }
}

function formatElapsed(seconds: number): string {
  return `${seconds.toFixed(1)}s`;
}

function setupAnimationPanelResize(): void {
  const minWidth = 170;
  const maxWidth = 360;
  animationPanelResize.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = animationPanel.getBoundingClientRect().width;
    const parentWidth = animationPanel.parentElement?.getBoundingClientRect().width ?? maxWidth;
    const widthLimit = Math.min(maxWidth, Math.max(minWidth, parentWidth - 28));
    animationPanelResize.setPointerCapture(event.pointerId);

    const drag = (moveEvent: PointerEvent) => {
      const width = Math.max(minWidth, Math.min(widthLimit, startWidth + moveEvent.clientX - startX));
      animationPanel.style.width = `${Math.round(width)}px`;
    };
    const stop = () => {
      animationPanelResize.removeEventListener('pointermove', drag);
      animationPanelResize.removeEventListener('pointerup', stop);
      animationPanelResize.removeEventListener('pointercancel', stop);
    };

    animationPanelResize.addEventListener('pointermove', drag);
    animationPanelResize.addEventListener('pointerup', stop);
    animationPanelResize.addEventListener('pointercancel', stop);
  });
}

function tick(): void {
  scene.tick();
  requestAnimationFrame(tick);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;
}
