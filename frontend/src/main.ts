import './styles.css';
import { buildCatalog, exportCatalogAsset, fetchCatalog, fetchDecodeProgress, fetchInitialModel, loadCatalogAsset, loadPath, pickCatalogFiles, pickCatalogFolder, uploadModel } from './api';
import { requireElement } from './dom';
import type { Catalog, CatalogAsset, DecodeProgress, Lm2Model, ModelStats, PolygonMode } from './types';
import { AnimationController } from './ui/animationController';
import { CatalogUi } from './ui/catalog';
import { renderStats } from './ui/stats';
import { UvInspector } from './ui/uvInspector';
import { ViewerScene, type CanvasBackgroundMode, type VisibilityState } from './viewer/scene';

const canvas = requireElement('canvas', HTMLCanvasElement);
const scene = new ViewerScene({ canvas });

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
const animationPanel = requireElement('animationPanel', HTMLDivElement);
const animationPanelResize = requireElement('animationPanelResize', HTMLDivElement);
const canvasAnimationSelect = requireElement('canvasAnimationSelect', HTMLSelectElement);
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

const catalogUi = new CatalogUi({
  summary: requireElement('catalogSummary', HTMLDivElement),
  search: requireElement('catalogSearch', HTMLInputElement),
  filter: requireElement('kindFilter', HTMLSelectElement),
  list: requireElement('assetList', HTMLDivElement),
  detail: requireElement('assetDetail', HTMLDivElement),
  onSelect: selectCatalogAsset,
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

window.addEventListener('resize', () => scene.resize());
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
  if (catalog?.asset_root) assetRootInput.value = catalog.asset_root;
  updateCanvasAnimationSelect(animationController.selectedBodyAsset);
}

async function selectCatalogAsset(asset: CatalogAsset): Promise<void> {
  animationController.stop();
  await runAction(async () => {
    catalogUi.select(asset);
    const payload = await loadCatalogAsset(asset);
    if ('animation' in payload) {
      animationController.setAnimationAsset(payload.animation);
      updateCanvasAnimationSelect(animationController.selectedBodyAsset);
      uvInspector.setModel(null);
      catalogUi.renderDetail(payload.animation);
      overlay.textContent = `${payload.animation.label} selected`;
      return;
    }
    showModel(payload);
  }, { label: asset.kind === 'model' ? `Decoding ${asset.label}` : `Loading ${asset.label}` });
}

function showModel(model: Lm2Model): void {
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
    canvasAnimationSelect.append(new Option(animation.label, animation.id));
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

function animationMatchesModel(animation: CatalogAsset, model: CatalogAsset): boolean {
  if (animation.kind !== 'animation' || animation.entry_type !== 'animation') return false;
  if (!('keyframes' in animation.stats)) return false;
  const modelStats = model.stats as ModelStats;
  return animation.stats.boneframes === modelStats.bones;
}

function findCatalogAsset(id: string): CatalogAsset | null {
  return currentCatalog?.assets.find((asset) => asset.id === id) || null;
}

async function exportSelectedAsset(): Promise<void> {
  if (!selectedExportAsset) throw new Error('Select a catalog model before exporting.');
  exportResult.textContent = '';
  const polygonMode = selectedPolygonMode();
  const result = await exportCatalogAsset(selectedExportAsset, polygonMode);
  const fileCount = [
    result.manifest.files.obj,
    result.manifest.files.mtl,
    result.manifest.files.manifest,
    result.manifest.files.shared_atlas_png,
    ...(result.manifest.files.uv_group_pngs || []).map((entry) => entry.path),
  ].filter(Boolean).length;
  exportResult.textContent = `Wrote ${fileCount} files to ${result.output_dir}`;
  overlay.textContent = `Exported ${result.manifest.source.catalog_label || result.manifest.source.catalog_asset_id}`;
}

function updateExportControls(): void {
  exportAssetButton.disabled = selectedExportAsset === null;
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
  scene.setBackgroundMode(mode);
  document.body.dataset.canvasBackground = mode;
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
