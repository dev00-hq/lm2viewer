import './styles.css';
import { buildCatalog, exportCatalogAsset, fetchCatalog, fetchDecodeProgress, fetchInitialModel, loadAnimationSequence, loadCatalogAsset, loadPath, pickCatalogFiles, pickCatalogFolder, poseAnimation, uploadModel } from './api';
import { requireElement } from './dom';
import type { AnimationSequenceFrame, AnimationSequencePayload, CatalogAsset, DecodeProgress, Lm2Model, PolygonMode } from './types';
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
const animationSelection = requireElement('animationSelection', HTMLDivElement);
const animationPlaybackState = requireElement('animationPlaybackState', HTMLDivElement);
const animationTimeCurrent = requireElement('animationTimeCurrent', HTMLSpanElement);
const animationTimeTotal = requireElement('animationTimeTotal', HTMLSpanElement);
const animationScrub = requireElement('animationScrub', HTMLInputElement);
const animationFrame = requireElement('animationFrame', HTMLInputElement);
const animationElapsed = requireElement('animationElapsed', HTMLInputElement);
const animationPrevious = requireElement('animationPrevious', HTMLButtonElement);
const animationPlay = requireElement('animationPlay', HTMLButtonElement);
const animationRepeat = requireElement('animationRepeat', HTMLButtonElement);
const animationPose = requireElement('animationPose', HTMLButtonElement);
const animationNext = requireElement('animationNext', HTMLButtonElement);
const animationResult = requireElement('animationResult', HTMLDivElement);
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
let selectedBodyAsset: CatalogAsset | null = null;
let selectedAnimationAsset: CatalogAsset | null = null;
let animationBusy = false;
let animationPlaying = false;
let animationPlaybackToken = 0;
let animationPlaybackFrame: number | undefined;
let animationPlaybackResolve: (() => void) | undefined;
let animationSequence: AnimationSequencePayload | null = null;
let currentAnimationFrame: AnimationSequenceFrame | null = null;
let lastAnimationUiUpdateAt = 0;
let animationRepeatEnabled = true;
let pendingAnimationSeekIndex: number | null = null;
let progressInterval: number | undefined;
let progressHideTimer: number | undefined;
let progressStartedAt = 0;

const playbackStepMs = 33;
const animationUiUpdateIntervalMs = 125;

const catalogUi = new CatalogUi({
  summary: requireElement('catalogSummary', HTMLDivElement),
  search: requireElement('catalogSearch', HTMLInputElement),
  filter: requireElement('kindFilter', HTMLSelectElement),
  list: requireElement('assetList', HTMLDivElement),
  detail: requireElement('assetDetail', HTMLDivElement),
  onSelect: selectCatalogAsset,
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
animationPose.addEventListener('click', () => runAction(async () => { await applyAnimationPose(); }, { label: 'Posing animation frame' }));
animationPrevious.addEventListener('click', () => runAction(() => stepAnimationFrame(-1), { label: 'Posing previous frame' }));
animationNext.addEventListener('click', () => runAction(() => stepAnimationFrame(1), { label: 'Posing next frame' }));
animationPlay.addEventListener('click', () => {
  if (animationPlaying) {
    stopAnimationPlayback();
  } else {
    void startAnimationPlayback();
  }
});
animationRepeat.addEventListener('click', () => {
  animationRepeatEnabled = !animationRepeatEnabled;
  updateAnimationControls();
});
animationScrub.addEventListener('input', () => {
  void seekAnimationTo(Number(animationScrub.value)).catch((error) => {
    errorBox.textContent = error instanceof Error ? error.message : String(error);
  });
});
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
  catalogUi.setCatalog(catalog);
  if (catalog?.asset_root) assetRootInput.value = catalog.asset_root;
}

async function selectCatalogAsset(asset: CatalogAsset): Promise<void> {
  stopAnimationPlayback();
  await runAction(async () => {
    catalogUi.select(asset);
    const payload = await loadCatalogAsset(asset);
    if ('animation' in payload) {
      setSelectedAnimationAsset(payload.animation);
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
  setSelectedBodyAsset(catalogBodyAsset || (model.pose ? selectedBodyAsset : null));
  updateExportControls();
  updateAnimationControls();
  if (model.catalog_asset) catalogUi.select(model.catalog_asset);
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

function updateAnimationControls(): void {
  const stats = selectedAnimationStats();
  const hasPair = selectedBodyAsset !== null && stats !== null;
  const disabled = animationBusy || animationPlaying;
  const totalDuration = stats?.total_duration ?? 0;
  animationPose.disabled = disabled;
  animationPrevious.disabled = disabled;
  animationNext.disabled = disabled;
  animationPlay.disabled = animationBusy && !animationPlaying;
  animationPlay.textContent = animationPlaying ? 'Pause' : 'Play';
  animationPlay.setAttribute('aria-pressed', String(animationPlaying));
  animationPlay.title = hasPair ? 'Play animation' : 'Select a model and decoded ANIM entry first';
  animationRepeat.textContent = animationRepeatEnabled ? 'Repeat On' : 'Repeat Off';
  animationRepeat.setAttribute('aria-pressed', String(animationRepeatEnabled));
  animationRepeat.disabled = animationBusy;
  animationScrub.disabled = !hasPair || animationBusy;
  animationScrub.max = String(Math.max(0, totalDuration));
  animationFrame.disabled = animationBusy || animationPlaying;
  animationElapsed.disabled = animationBusy || animationPlaying;
  if (stats) {
    animationFrame.max = String(Math.max(0, stats.keyframes - 1));
  } else {
    animationFrame.removeAttribute('max');
  }
  animationTimeTotal.textContent = formatAnimationTime(totalDuration);
  animationPlaybackState.textContent = animationBusy ? 'Loading' : animationPlaying ? 'Playing' : hasPair ? 'Ready' : 'Idle';
  animationPlaybackState.classList.toggle('active', animationPlaying);
  animationPlaybackState.classList.toggle('busy', animationBusy);
  const body = selectedBodyAsset?.label || 'No model';
  const anim = selectedAnimationAsset?.label || 'No animation';
  animationSelection.textContent = `${body} + ${anim}`;
}

function setSelectedExportAsset(asset: CatalogAsset | null): void {
  if (selectedExportAsset?.id !== asset?.id) {
    exportResult.textContent = '';
  }
  selectedExportAsset = asset;
}

function setSelectedBodyAsset(asset: CatalogAsset | null): void {
  if (selectedBodyAsset?.id !== asset?.id) {
    stopAnimationPlayback();
    animationSequence = null;
    currentAnimationFrame = null;
    animationResult.textContent = '';
    updateAnimationTimelineReadout(0);
  }
  selectedBodyAsset = asset;
}

function setSelectedAnimationAsset(asset: CatalogAsset): void {
  if (selectedAnimationAsset?.id !== asset.id) {
    stopAnimationPlayback();
    animationSequence = null;
    currentAnimationFrame = null;
    animationResult.textContent = '';
    animationFrame.value = '0';
    animationElapsed.value = '0';
    updateAnimationTimelineReadout(0);
  }
  selectedAnimationAsset = asset;
  updateAnimationControls();
}

async function applyAnimationPose(previousFrame?: number): Promise<Lm2Model> {
  const bodyAsset = selectedBodyAsset;
  const animationAsset = selectedAnimationAsset;
  if (!bodyAsset) throw new Error('Select a catalog model before posing animation.');
  if (!animationAsset || animationAsset.entry_type !== 'animation') {
    throw new Error('Select a decoded ANIM entry before posing animation.');
  }
  if (animationBusy) throw new Error('Animation pose is already running.');
  const frame = numericInput(animationFrame, 'frame');
  validateAnimationFrame(frame, animationAsset);
  const elapsedMs = numericInput(animationElapsed, 'elapsed milliseconds');
  animationBusy = true;
  updateAnimationControls();
  try {
    const model = await poseAnimation(bodyAsset, animationAsset, frame, elapsedMs, previousFrame);
    showModel(model);
    const sample = model.pose?.sample;
    animationResult.textContent = sample
      ? `Frame ${sample.target_frame_index}, previous ${sample.previous_frame_index}, next ${sample.next_frame_index}, ${sample.duration_ms} ms duration`
      : 'Posed frame loaded';
    overlay.textContent = `${bodyAsset.label} posed with ${animationAsset.label}`;
    return model;
  } finally {
    animationBusy = false;
    updateAnimationControls();
  }
}

async function startAnimationPlayback(): Promise<void> {
  if (!selectedBodyAsset || !selectedAnimationAsset || !selectedAnimationStats()) {
    errorBox.textContent = 'Select a catalog model and decoded ANIM entry before playback.';
    return;
  }
  errorBox.textContent = '';
  const token = ++animationPlaybackToken;
  animationBusy = true;
  animationPlay.textContent = 'Loading';
  updateAnimationControls();
  try {
    const sequence = await getAnimationSequence();
    if (token !== animationPlaybackToken) return;
    const sequenceIndex = sequenceIndexFor(sequence, numericInput(animationFrame, 'frame'), numericInput(animationElapsed, 'elapsed milliseconds'));
    animationBusy = false;
    animationPlaying = true;
    currentAnimationFrame = null;
    lastAnimationUiUpdateAt = 0;
    updateAnimationControls();
    await runAnimationPlayback(sequence, sequenceIndex, token);
  } catch (error) {
    errorBox.textContent = error instanceof Error ? error.message : String(error);
  } finally {
    animationBusy = false;
    if (token === animationPlaybackToken) {
      animationPlaying = false;
      updateAnimationControls();
    }
  }
}

async function getAnimationSequence(): Promise<AnimationSequencePayload> {
  const bodyAsset = selectedBodyAsset;
  const animationAsset = selectedAnimationAsset;
  if (!bodyAsset || !animationAsset || !selectedAnimationStats()) {
    throw new Error('Select a catalog model and decoded ANIM entry before playback.');
  }
  if (
    !animationSequence ||
    animationSequence.body_asset_id !== bodyAsset.id ||
    animationSequence.animation_asset_id !== animationAsset.id ||
    animationSequence.step_ms !== playbackStepMs
  ) {
    animationSequence = await loadAnimationSequence(bodyAsset, animationAsset, playbackStepMs);
  }
  if (animationSequence.frames.length === 0) {
    throw new Error('Selected animation produced no playback frames.');
  }
  return animationSequence;
}

function renderAnimationSequenceFrame(frame: AnimationSequenceFrame): void {
  const baseModel = scene.model;
  const bodyAsset = selectedBodyAsset;
  if (!baseModel || !bodyAsset || !selectedAnimationAsset) {
    throw new Error('Select a catalog model and decoded ANIM entry before playback.');
  }
  scene.updateModelVertices(frame.vertices, frame.pose, bodyAsset);
  currentAnimationFrame = frame;
}

function updateAnimationReadout(frame: AnimationSequenceFrame): void {
  const bodyAsset = selectedBodyAsset;
  const animationAsset = selectedAnimationAsset;
  if (!bodyAsset || !animationAsset) return;
  animationFrame.value = String(frame.frame);
  animationElapsed.value = String(frame.elapsed_ms);
  updateAnimationTimelineReadout(animationTimelineMs(frame));
  animationResult.textContent = `Frame ${frame.frame}, previous ${frame.previous_frame}, next ${frame.next_frame}, ${frame.duration_ms} ms duration`;
  overlay.textContent = `${bodyAsset.label} playing ${animationAsset.label}`;
}

function sequenceIndexFor(sequence: AnimationSequencePayload, frame: number, elapsedMs: number): number {
  validateAnimationFrame(frame, selectedAnimationAsset!);
  let bestIndex = -1;
  let bestElapsed = -1;
  for (let index = 0; index < sequence.frames.length; index += 1) {
    const item = sequence.frames[index];
    if (item.frame !== frame || item.elapsed_ms > elapsedMs) continue;
    if (item.elapsed_ms >= bestElapsed) {
      bestIndex = index;
      bestElapsed = item.elapsed_ms;
    }
  }
  if (bestIndex >= 0) return bestIndex;
  return sequence.frames.findIndex((item) => item.frame === frame) || 0;
}

function loopSequenceIndex(sequence: AnimationSequencePayload): number {
  const index = sequence.frames.findIndex((frame) => frame.frame === sequence.loop_frame && frame.elapsed_ms === 0);
  return index >= 0 ? index : 0;
}

async function seekAnimationTo(timelineMs: number): Promise<void> {
  const sequence = await getAnimationSequence();
  const index = sequenceIndexAtTimeline(sequence, timelineMs);
  pendingAnimationSeekIndex = index;
  const frame = sequence.frames[index];
  renderAnimationSequenceFrame(frame);
  updateAnimationReadout(frame);
}

function sequenceIndexAtTimeline(sequence: AnimationSequencePayload, timelineMs: number): number {
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let index = 0; index < sequence.frames.length; index += 1) {
    const distance = Math.abs(animationTimelineMs(sequence.frames[index]) - timelineMs);
    if (distance < bestDistance) {
      bestIndex = index;
      bestDistance = distance;
    }
  }
  return bestIndex;
}

function animationTimelineMs(frame: AnimationSequenceFrame): number {
  return frameStartMs(frame.frame) + frame.elapsed_ms;
}

function frameStartMs(frame: number): number {
  const stats = selectedAnimationStats();
  if (!stats) return 0;
  let total = 0;
  const sequence = animationSequence;
  for (let index = 0; index < frame; index += 1) {
    const sequenceFrame = sequence?.frames.find((item) => item.frame === index);
    total += sequenceFrame?.duration_ms ?? 0;
  }
  return total;
}

function updateAnimationTimelineReadout(timelineMs: number): void {
  const stats = selectedAnimationStats();
  const total = Math.max(0, stats?.total_duration ?? 0);
  const clamped = Math.max(0, Math.min(total, timelineMs));
  animationScrub.max = String(total);
  animationScrub.value = String(Math.round(clamped));
  animationTimeCurrent.textContent = formatAnimationTime(clamped);
  animationTimeTotal.textContent = formatAnimationTime(total);
}

function stopAnimationPlayback(): void {
  if (!animationPlaying && animationPlaybackFrame === undefined) return;
  animationPlaying = false;
  animationPlaybackToken += 1;
  if (animationPlaybackFrame !== undefined) {
    window.cancelAnimationFrame(animationPlaybackFrame);
    animationPlaybackFrame = undefined;
  }
  if (currentAnimationFrame) updateAnimationReadout(currentAnimationFrame);
  animationPlaybackResolve?.();
  animationPlaybackResolve = undefined;
  updateAnimationControls();
}

function runAnimationPlayback(sequence: AnimationSequencePayload, startIndex: number, token: number): Promise<void> {
  return new Promise((resolve) => {
    animationPlaybackResolve = () => {
      if (currentAnimationFrame) updateAnimationReadout(currentAnimationFrame);
      animationPlaybackFrame = undefined;
      animationPlaybackResolve = undefined;
      resolve();
    };
    let sequenceIndex = startIndex;
    let nextFrameAt = performance.now();
    const tick = (now: number) => {
      animationPlaybackFrame = undefined;
      if (!animationPlaying || token !== animationPlaybackToken) {
        animationPlaybackResolve?.();
        return;
      }
      if (pendingAnimationSeekIndex !== null) {
        sequenceIndex = pendingAnimationSeekIndex;
        pendingAnimationSeekIndex = null;
        nextFrameAt = now;
      }
      let frame: AnimationSequenceFrame | null = null;
      while (now >= nextFrameAt) {
        frame = sequence.frames[sequenceIndex];
        sequenceIndex += 1;
        if (sequenceIndex >= sequence.frames.length) {
          if (animationRepeatEnabled) {
            sequenceIndex = loopSequenceIndex(sequence);
          } else {
            animationPlaying = false;
            break;
          }
        }
        nextFrameAt += sequence.step_ms;
      }
      if (frame) {
        renderAnimationSequenceFrame(frame);
        if (now - lastAnimationUiUpdateAt >= animationUiUpdateIntervalMs) {
          updateAnimationReadout(frame);
          lastAnimationUiUpdateAt = now;
        }
      }
      if (!animationPlaying) {
        animationPlaybackResolve?.();
        return;
      }
      animationPlaybackFrame = window.requestAnimationFrame(tick);
    };
    animationPlaybackFrame = window.requestAnimationFrame(tick);
  });
}

async function stepAnimationFrame(direction: -1 | 1): Promise<void> {
  if (!selectedAnimationAsset || !selectedAnimationStats()) {
    throw new Error('Select a decoded ANIM entry before stepping.');
  }
  const stats = selectedAnimationStats()!;
  const current = numericInput(animationFrame, 'frame');
  validateAnimationFrame(current, selectedAnimationAsset);
  const previousFrame = current;
  let next = current + direction;
  if (direction > 0 && next >= stats.keyframes) next = stats.loop_frame;
  if (direction < 0 && next < 0) next = Math.max(0, stats.keyframes - 1);
  const previousFrameValue = animationFrame.value;
  const previousElapsedValue = animationElapsed.value;
  animationFrame.value = String(next);
  animationElapsed.value = '0';
  try {
    await applyAnimationPose(previousFrame);
  } catch (error) {
    animationFrame.value = previousFrameValue;
    animationElapsed.value = previousElapsedValue;
    throw error;
  }
}

function numericInput(input: HTMLInputElement, label: string): number {
  if (input.value.trim() === '') {
    throw new Error(`Animation ${label} is required.`);
  }
  const value = Number(input.value);
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`Animation ${label} must be a non-negative integer.`);
  }
  return value;
}

function validateAnimationFrame(frame: number, animationAsset: CatalogAsset): void {
  if (!('keyframes' in animationAsset.stats)) {
    throw new Error('Selected animation is not decoded.');
  }
  if (frame >= animationAsset.stats.keyframes) {
    throw new Error(`Animation frame must be less than ${animationAsset.stats.keyframes}.`);
  }
}

function selectedAnimationStats(): { keyframes: number; loop_frame: number; total_duration: number } | null {
  if (!selectedAnimationAsset || selectedAnimationAsset.entry_type !== 'animation') return null;
  if (!('keyframes' in selectedAnimationAsset.stats)) return null;
  return selectedAnimationAsset.stats;
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

function formatAnimationTime(milliseconds: number): string {
  const safeMs = Math.max(0, Math.round(milliseconds));
  const minutes = Math.floor(safeMs / 60000);
  const seconds = Math.floor((safeMs % 60000) / 1000);
  const millis = safeMs % 1000;
  return `${minutes}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
}

function tick(): void {
  scene.tick();
  requestAnimationFrame(tick);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;
}
