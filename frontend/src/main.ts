import './styles.css';
import { buildCatalog, catalogAudioUrl, exportCatalogAsset, fetchCatalog, fetchDecodeProgress, fetchInitialModel, loadAssetEntityWorkflow, loadCatalogAsset, loadPath, loadRuntimeSpriteEntityWorkflow, pickCatalogFiles, pickCatalogFolder, uploadModel } from './api';
import { animationCompatibilityPrefix, animationMatchesModel } from './compatibility';
import { requireElement } from './dom';
import type { Catalog, CatalogAsset, DecodeProgress, Lm2Model, PolygonMode, SpritePayload } from './types';
import { AnimationController } from './ui/animationController';
import { CatalogUi } from './ui/catalog';
import { EntityView } from './ui/entityView';
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

type MainView = 'model' | 'sprite' | 'entity';

const stats = requireElement('stats', HTMLDivElement);
const errorBox = requireElement('error', HTMLDivElement);
const overlay = requireElement('overlay', HTMLDivElement);
const horizonIndicator = requireElement('horizonIndicator', HTMLDivElement);
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
const exportAssetButton = requireElement('exportAsset', HTMLButtonElement);
const exportPolygonMode = requireElement('exportPolygonMode', HTMLSelectElement);
const exportResult = requireElement('exportResult', HTMLDivElement);
const samplePreview = requireElement('samplePreview', HTMLDivElement);
const sampleAudio = requireElement('sampleAudio', HTMLAudioElement);
const samplePreviewMeta = requireElement('samplePreviewMeta', HTMLDivElement);
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
});
let selectedExportAsset: CatalogAsset | null = null;
let currentCatalog: Catalog | null = null;
let progressInterval: number | undefined;
let progressHideTimer: number | undefined;
let progressStartedAt = 0;
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
  detail: requireElement('assetDetail', HTMLDivElement),
  onSelect: selectCatalogAsset,
});
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
  loadFrame: loadSpriteFrame,
  onFrameLoaded: (asset, payload) => {
    catalogUi.select(asset);
    catalogUi.renderDetail(payload.sprite);
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
    const asset = findCatalogAsset(assetId);
    if (!asset) {
      errorBox.textContent = `Catalog asset not found: ${assetId}`;
      return;
    }
    void selectCatalogAsset(asset);
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
    const asset = findCatalogAsset(assetId);
    if (!asset) {
      errorBox.textContent = `Catalog asset not found: ${assetId}`;
      return;
    }
    void selectCatalogAsset(asset);
  },
  openWorkflow: (request) => {
    void runAction(async () => {
      const workflow = await loadRuntimeSpriteEntityWorkflow(request);
      entityView.setWorkflow(workflow);
      setMainView('entity');
      overlay.textContent = workflow.selected_entity?.entity_id || workflow.resolved_asset?.id || 'Runtime sprite evidence';
    }, { label: 'Loading entity workflow' });
  },
  setError: (message) => {
    errorBox.textContent = message;
  },
});
const animationController = new AnimationController({
  elements: {
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
  if (canvasBackgroundShadePicker.hidden) return;
  const target = event.target;
  if (!(target instanceof Node)) return;
  if (canvasBackgroundShade.contains(target) || canvasBackgroundShadePicker.contains(target)) return;
  hideBackgroundShadePicker();
});
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') hideBackgroundShadePicker();
});
requireElement('resetView', HTMLButtonElement).addEventListener('click', () => scene.resetView());
requireElement('zoomIn', HTMLButtonElement).addEventListener('click', () => scene.zoomBy(0.72));
requireElement('zoomOut', HTMLButtonElement).addEventListener('click', () => scene.zoomBy(1.38));
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
  const model = await fetchInitialModel();
  if (model) showModel(model);
}

function setCatalog(catalog: Awaited<ReturnType<typeof fetchCatalog>>): void {
  currentCatalog = catalog;
  catalogUi.setCatalog(catalog);
  runtimeSpriteResolver.setCatalog(catalog);
  if (catalog?.asset_root) assetRootInput.value = catalog.asset_root;
  updateCanvasAnimationSelect(animationController.selectedBodyAsset);
}

async function selectCatalogAsset(asset: CatalogAsset): Promise<void> {
  animationController.stop();
  spriteViewer.stop();
  await runAction(async () => {
    catalogUi.select(asset);
    const payload = await loadCatalogAsset(asset);
    if ('animation' in payload) {
      setSamplePreview(null);
      animationController.setAnimationAsset(payload.animation);
      updateCanvasAnimationSelect(animationController.selectedBodyAsset);
      uvInspector.setModel(null);
      catalogUi.renderDetail(payload.animation);
      await showAssetEntityWorkflow(payload.animation, hasSceneUsages(payload.animation));
      overlay.textContent = `${payload.animation.label} selected`;
      return;
    }
    if ('sprite' in payload) {
      setSamplePreview(null);
      uvInspector.setModel(null);
      catalogUi.renderDetail(payload.sprite);
      await showAssetEntityWorkflow(payload.sprite, hasSceneUsages(payload.sprite));
      spriteViewer.setSprite(payload, spriteRangeAssets(payload.sprite));
      if (!hasSceneUsages(payload.sprite)) setMainView('sprite');
      overlay.textContent = `${payload.sprite.label} selected`;
      const stats = payload.sprite.stats;
      setSelectedExportAsset(
        'semantic_layout' in stats
          && (
            (payload.sprite.kind === 'sprite' && (stats.semantic_layout === 'lsp_sprite_frame' || stats.semantic_layout === 'raw_sprite_frame'))
            || (
              payload.sprite.kind === 'resource'
              && (
                stats.semantic_layout === 'bkg_grid_map'
                || stats.semantic_layout === 'screen_indexed_image_640x480'
                || stats.semantic_layout === 'lba2_indexed_image_256'
                || stats.semantic_layout === 'lba2_texture_atlas_indexed'
                || stats.semantic_layout === 'holomap_plan_image_640x480'
              )
            )
            || (payload.sprite.kind === 'scene' && stats.semantic_layout === 'scene_runtime_layout_partial')
          )
          ? payload.sprite
          : null,
      );
      updateExportControls();
      return;
    }
    if ('scene' in payload) {
      setSamplePreview(null);
      uvInspector.setModel(null);
      catalogUi.renderDetail(payload.scene);
      await showAssetEntityWorkflow(payload.scene, false);
      setMainView('model');
      overlay.textContent = `${payload.scene.label} selected`;
      const stats = payload.scene.stats;
      const background = 'reconnaissance' in stats ? stats.reconnaissance.background : null;
      setSelectedExportAsset(background?.resolved_gri_entry !== undefined ? payload.scene : null);
      updateExportControls();
      return;
    }
    if ('resource' in payload) {
      setSamplePreview(null);
      uvInspector.setModel(null);
      catalogUi.renderDetail(payload.resource);
      await showAssetEntityWorkflow(payload.resource, hasSceneUsages(payload.resource));
      setMainView('model');
      overlay.textContent = `${payload.resource.label} selected`;
      const stats = payload.resource.stats;
      setSelectedExportAsset(
        'semantic_layout' in stats && stats.semantic_layout === 'bkg_grid_map'
          ? payload.resource
          : 'semantic_layout' in stats && stats.semantic_layout === 'sample_wave_audio'
            ? payload.resource
          : 'semantic_layout' in stats && stats.semantic_layout === 'text_payload_bank'
            ? payload.resource
          : 'semantic_layout' in stats && stats.semantic_layout === 'smacker_video'
            ? payload.resource
          : null,
      );
      setSamplePreview(
        'semantic_layout' in stats && stats.semantic_layout === 'sample_wave_audio'
          ? payload.resource
          : null,
      );
      updateExportControls();
      if (hasSceneUsages(payload.resource)) setMainView('entity');
      return;
    }
    showModel(payload);
    if (payload.catalog_asset) await showAssetEntityWorkflow(payload.catalog_asset, hasSceneUsages(payload.catalog_asset));
  }, { label: asset.kind === 'model' ? `Decoding ${asset.label}` : `Loading ${asset.label}` });
}

async function showAssetEntityWorkflow(asset: CatalogAsset, activate: boolean): Promise<void> {
  try {
    const workflow = await loadAssetEntityWorkflow(asset);
    entityView.setWorkflow(workflow);
    if (activate) setMainView('entity');
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

function showModel(model: Lm2Model): void {
  setSamplePreview(null);
  setMainView('model');
  scene.loadModel(model);
  renderStats(stats, model);
  uvInspector.setModel(model);
  overlay.textContent = model.source || 'Uploaded model';
  setSelectedExportAsset(model.catalog_asset?.kind === 'model' ? model.catalog_asset : null);
  const catalogBodyAsset = model.catalog_asset?.kind === 'model' ? model.catalog_asset : null;
  catalogUi.setSelectedModel(catalogBodyAsset);
  animationController.setBodyAsset(catalogBodyAsset || (model.pose ? animationController.selectedBodyAsset : null));
  updateCanvasAnimationSelect(animationController.selectedBodyAsset);
  updateExportControls();
  animationController.updateControls();
  if (model.catalog_asset) catalogUi.select(model.catalog_asset);
}

function setMainView(view: MainView): void {
  for (const [key, entry] of Object.entries(mainViews) as Array<[MainView, typeof mainViews[MainView]]>) {
    const active = key === view;
    entry.panel.hidden = !active;
    entry.panel.classList.toggle('active', active);
    entry.tab.classList.toggle('active', active);
    entry.tab.setAttribute('aria-selected', String(active));
  }
  if (view === 'model') {
    overlay.hidden = false;
    scene.resize();
  } else if (view === 'sprite') {
    overlay.hidden = true;
    spriteViewer.resize();
  } else {
    overlay.hidden = true;
  }
}

function selectCanvasAnimation(): void {
  const asset = findCatalogAsset(canvasAnimationSelect.value);
  if (!asset || asset.kind !== 'animation' || asset.entry_type !== 'animation') return;
  animationController.setAnimationAsset(asset);
  catalogUi.select(asset);
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

async function exportSelectedAsset(): Promise<void> {
  if (!selectedExportAsset) throw new Error('Select an exportable catalog model, sprite frame, sample, indexed image, background grid, or scene background before exporting.');
  exportResult.textContent = '';
  const polygonMode = selectedPolygonMode();
  const result = await exportCatalogAsset(selectedExportAsset, polygonMode);
  const fileEntries = collectManifestFiles(result.manifest.files);
  const fileCount = fileEntries.filter(Boolean).length;
  exportResult.textContent = `Wrote ${fileCount} files to ${result.output_dir}`;
  overlay.textContent = `Exported ${result.manifest.source.catalog_label || result.manifest.source.catalog_asset_id}`;
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

function updateExportControls(): void {
  exportAssetButton.disabled = selectedExportAsset === null;
}

function setSamplePreview(asset: CatalogAsset | null): void {
  sampleAudio.pause();
  sampleAudio.removeAttribute('src');
  sampleAudio.load();
  samplePreview.hidden = asset === null;
  samplePreviewMeta.textContent = '';
  if (!asset) return;
  const stats = asset.stats;
  if (!('semantic_layout' in stats) || stats.semantic_layout !== 'sample_wave_audio') return;
  sampleAudio.src = catalogAudioUrl(asset);
  const fields = stats.fields || {};
  samplePreviewMeta.textContent = [
    `Sample ${stats.sample_runtime_index ?? asset.source.entry_index}`,
    stats.audio_format || 'audio',
    `${fields.sample_rate ?? '-'}Hz`,
    `${fields.channels ?? '-'}ch`,
    `${stats.duration_ms ?? '-'} ms`,
  ].join(' | ');
}

function setSelectedExportAsset(asset: CatalogAsset | null): void {
  if (selectedExportAsset?.id !== asset?.id) {
    exportResult.textContent = '';
  }
  selectedExportAsset = asset;
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
  horizonIndicator.textContent = lockHorizon.checked ? 'HORIZON LOCKED' : 'HORIZON FREE';
}

function refreshCanvasBackground(): void {
  const mode: CanvasBackgroundMode = lightCanvas.checked ? 'light' : 'dark';
  scene.setBackground(mode, selectedCanvasBackgroundShade);
  document.body.dataset.canvasBackground = mode;
  document.body.dataset.canvasBackgroundShade = String(selectedCanvasBackgroundShade);
  canvasBackgroundToggle.textContent = mode === 'light' ? 'Light' : 'Dark';
  canvasBackgroundToggle.setAttribute('aria-pressed', String(mode === 'light'));
  canvasBackgroundToggle.title = mode === 'light' ? 'Switch to dark canvas background' : 'Switch to light canvas background';
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

async function updateServerProgress(fallbackLabel: string): Promise<void> {
  try {
    renderProgress(await fetchDecodeProgress(), fallbackLabel);
  } catch {
    updateLocalProgress(fallbackLabel);
  }
}

function renderProgress(progress: DecodeProgress, fallbackLabel: string): void {
  progressText.textContent = progress.label || fallbackLabel;
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
