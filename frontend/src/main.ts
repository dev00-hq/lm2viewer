import './styles.css';
import { buildCatalog, fetchCatalog, fetchDecodeProgress, fetchInitialModel, loadCatalogAsset, loadPath, pickCatalogFiles, pickCatalogFolder, uploadModel } from './api';
import { requireElement } from './dom';
import type { CatalogAsset, DecodeProgress, Lm2Model } from './types';
import { CatalogUi } from './ui/catalog';
import { renderStats } from './ui/stats';
import { ViewerScene, type VisibilityState } from './viewer/scene';

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

Object.assign(globalThis, { lm2Viewer: { camera: scene.camera, controls: scene.controls, scene: scene.scene, get currentModel() { return scene.model; } } });

for (const element of [showFaces, showLines, showSpheres, wireframe, showGrid]) {
  element.addEventListener('change', refreshVisibility);
}
lockHorizon.addEventListener('change', refreshHorizonLock);
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
refreshHorizonLock();
tick();

async function initialLoad(): Promise<void> {
  setCatalog(await fetchCatalog());
  const model = await fetchInitialModel();
  if (model) showModel(model);
}

function setCatalog(catalog: Awaited<ReturnType<typeof fetchCatalog>>): void {
  catalogUi.setCatalog(catalog);
  if (catalog?.asset_root) assetRootInput.value = catalog.asset_root;
}

async function selectCatalogAsset(asset: CatalogAsset): Promise<void> {
  await runAction(async () => {
    catalogUi.select(asset);
    const payload = await loadCatalogAsset(asset);
    if ('animation' in payload) {
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
  overlay.textContent = model.source || 'Uploaded model';
  if (model.catalog_asset) catalogUi.select(model.catalog_asset);
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

function tick(): void {
  scene.tick();
  requestAnimationFrame(tick);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;
}
