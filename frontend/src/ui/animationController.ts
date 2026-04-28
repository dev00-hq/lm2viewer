import { loadAnimationSequence, poseAnimation } from '../api';
import type { AnimationSequenceFrame, AnimationSequencePayload, CatalogAsset, Lm2Model } from '../types';
import type { ViewerScene } from '../viewer/scene';

type RunAction = (action: () => Promise<void>, progress?: { label: string; pollServer?: boolean }) => Promise<void>;

export interface AnimationControllerElements {
  selection: HTMLDivElement;
  playbackState: HTMLDivElement;
  timeCurrent: HTMLSpanElement;
  timeTotal: HTMLSpanElement;
  scrub: HTMLInputElement;
  frame: HTMLInputElement;
  elapsed: HTMLInputElement;
  previous: HTMLButtonElement;
  play: HTMLButtonElement;
  repeat: HTMLButtonElement;
  pose: HTMLButtonElement;
  mode: HTMLSelectElement;
  next: HTMLButtonElement;
  result: HTMLDivElement;
}

export interface AnimationControllerOptions {
  elements: AnimationControllerElements;
  scene: ViewerScene;
  showModel: (model: Lm2Model) => void;
  setError: (message: string) => void;
  setOverlay: (message: string) => void;
  runAction: RunAction;
}

interface AnimationStats {
  keyframes: number;
  loop_frame: number;
  total_duration: number;
}

const playbackStepMs = 33;
const uiUpdateIntervalMs = 125;

export class AnimationController {
  private bodyAsset: CatalogAsset | null = null;
  private animationAsset: CatalogAsset | null = null;
  private busy = false;
  private playing = false;
  private playbackToken = 0;
  private playbackFrame: number | undefined;
  private playbackResolve: (() => void) | undefined;
  private sequence: AnimationSequencePayload | null = null;
  private currentFrame: AnimationSequenceFrame | null = null;
  private currentSequenceIndex: number | null = null;
  private currentLoopCycle = 0;
  private lastUiUpdateAt = 0;
  private repeatEnabled = true;
  private pendingSeekIndex: number | null = null;

  constructor(private readonly options: AnimationControllerOptions) {
    const { elements } = options;
    elements.pose.addEventListener('click', () => options.runAction(
      async () => { await this.applyPose(); },
      { label: 'Posing animation frame' },
    ));
    elements.previous.addEventListener('click', () => options.runAction(
      () => this.stepFrame(-1),
      { label: 'Posing previous frame' },
    ));
    elements.next.addEventListener('click', () => options.runAction(
      () => this.stepFrame(1),
      { label: 'Posing next frame' },
    ));
    elements.play.addEventListener('click', () => {
      if (this.playing) {
        this.stop();
      } else {
        void this.startPlayback();
      }
    });
    elements.repeat.addEventListener('click', () => {
      this.repeatEnabled = !this.repeatEnabled;
      this.updateControls();
    });
    elements.mode.addEventListener('change', () => {
      options.scene.setPlaybackMode(elements.mode.value);
      if (this.currentFrame) this.renderFrame(this.currentFrame);
    });
    elements.scrub.addEventListener('input', () => {
      void this.seekTo(Number(elements.scrub.value)).catch((error) => {
        options.setError(error instanceof Error ? error.message : String(error));
      });
    });
    this.updateControls();
  }

  get selectedBodyAsset(): CatalogAsset | null {
    return this.bodyAsset;
  }

  get selectedAnimationAsset(): CatalogAsset | null {
    return this.animationAsset;
  }

  setBodyAsset(asset: CatalogAsset | null): void {
    if (this.bodyAsset?.id !== asset?.id) {
      this.clearPlaybackState();
    }
    this.bodyAsset = asset;
    this.updateControls();
  }

  setAnimationAsset(asset: CatalogAsset): void {
    if (this.animationAsset?.id !== asset.id) {
      this.clearPlaybackState();
      this.options.elements.frame.value = '0';
      this.options.elements.elapsed.value = '0';
      this.updateTimelineReadout(0);
    }
    this.animationAsset = asset;
    this.updateControls();
  }

  updateControls(): void {
    const stats = this.selectedStats();
    const hasPair = this.bodyAsset !== null && stats !== null;
    const disabled = this.busy || this.playing;
    const totalDuration = stats?.total_duration ?? 0;
    const { elements } = this.options;

    elements.pose.disabled = disabled;
    elements.previous.disabled = disabled;
    elements.next.disabled = disabled;
    elements.play.disabled = this.busy && !this.playing;
    elements.play.textContent = this.playing ? '||' : '>';
    elements.play.setAttribute('aria-pressed', String(this.playing));
    elements.play.title = hasPair ? (this.playing ? 'Pause animation' : 'Play animation') : 'Select a model and decoded ANIM entry first';
    elements.repeat.textContent = '↻';
    elements.repeat.setAttribute('aria-pressed', String(this.repeatEnabled));
    elements.repeat.title = this.repeatEnabled ? 'Repeat playback enabled' : 'Repeat playback disabled';
    elements.repeat.disabled = this.busy;
    elements.mode.disabled = this.busy;
    elements.scrub.disabled = !hasPair || this.busy;
    elements.scrub.max = String(Math.max(0, totalDuration));
    elements.frame.disabled = this.busy || this.playing;
    elements.elapsed.disabled = this.busy || this.playing;
    if (stats) {
      elements.frame.max = String(Math.max(0, stats.keyframes - 1));
    } else {
      elements.frame.removeAttribute('max');
    }
    elements.timeTotal.textContent = formatAnimationTime(totalDuration);
    elements.playbackState.textContent = this.busy ? 'Loading' : this.playing ? 'Playing' : hasPair ? 'Ready' : 'Idle';
    elements.playbackState.classList.toggle('active', this.playing);
    elements.playbackState.classList.toggle('busy', this.busy);
    const selectionText = `${this.bodyAsset?.label || 'No model'} + ${this.animationAsset?.label || 'No animation'}`;
    elements.selection.textContent = selectionText;
    elements.selection.title = selectionText;
  }

  stop(): void {
    if (!this.playing && this.playbackFrame === undefined) return;
    this.playing = false;
    this.playbackToken += 1;
    if (this.playbackFrame !== undefined) {
      window.cancelAnimationFrame(this.playbackFrame);
      this.playbackFrame = undefined;
    }
    if (this.currentFrame) this.updateReadout(this.currentFrame);
    this.playbackResolve?.();
    this.playbackResolve = undefined;
    this.updateControls();
  }

  private clearPlaybackState(): void {
    this.stop();
    this.sequence = null;
    this.currentFrame = null;
    this.currentSequenceIndex = null;
    this.currentLoopCycle = 0;
    this.options.elements.result.textContent = '';
    this.updateTimelineReadout(0);
  }

  private async applyPose(previousFrame?: number): Promise<Lm2Model> {
    const bodyAsset = this.bodyAsset;
    const animationAsset = this.animationAsset;
    if (!bodyAsset) throw new Error('Select a catalog model before posing animation.');
    if (!animationAsset || animationAsset.entry_type !== 'animation') {
      throw new Error('Select a decoded ANIM entry before posing animation.');
    }
    if (this.busy) throw new Error('Animation pose is already running.');

    const frame = numericInput(this.options.elements.frame, 'frame');
    validateAnimationFrame(frame, animationAsset);
    const elapsedMs = numericInput(this.options.elements.elapsed, 'elapsed milliseconds');
    this.busy = true;
    this.updateControls();
    try {
      const model = await poseAnimation(bodyAsset, animationAsset, frame, elapsedMs, previousFrame);
      this.options.showModel(model);
      const sample = model.pose?.sample;
      this.options.elements.result.textContent = sample
        ? `Frame ${sample.target_frame_index}, previous ${sample.previous_frame_index}, next ${sample.next_frame_index}, ${sample.duration_ms} ms duration`
        : 'Posed frame loaded';
      this.options.setOverlay(`${bodyAsset.label} posed with ${animationAsset.label}`);
      return model;
    } finally {
      this.busy = false;
      this.updateControls();
    }
  }

  private async startPlayback(): Promise<void> {
    if (!this.bodyAsset || !this.animationAsset || !this.selectedStats()) {
      this.options.setError('Select a catalog model and decoded ANIM entry before playback.');
      return;
    }
    this.options.setError('');
    const token = ++this.playbackToken;
    this.busy = true;
    this.options.elements.play.textContent = '...';
    this.updateControls();
    try {
      const sequence = await this.getSequence();
      if (token !== this.playbackToken) return;
      const inputFrame = numericInput(this.options.elements.frame, 'frame');
      const inputElapsedMs = numericInput(this.options.elements.elapsed, 'elapsed milliseconds');
      const startIndex = this.resumeIndexFor(sequence, inputFrame, inputElapsedMs);
      this.busy = false;
      this.playing = true;
      this.lastUiUpdateAt = 0;
      this.updateControls();
      await this.runPlayback(sequence, startIndex, token);
    } catch (error) {
      this.options.setError(error instanceof Error ? error.message : String(error));
    } finally {
      this.busy = false;
      if (token === this.playbackToken) {
        this.playing = false;
        this.updateControls();
      }
    }
  }

  private async getSequence(): Promise<AnimationSequencePayload> {
    const bodyAsset = this.bodyAsset;
    const animationAsset = this.animationAsset;
    if (!bodyAsset || !animationAsset || !this.selectedStats()) {
      throw new Error('Select a catalog model and decoded ANIM entry before playback.');
    }
    if (
      !this.sequence ||
      this.sequence.body_asset_id !== bodyAsset.id ||
      this.sequence.animation_asset_id !== animationAsset.id ||
      this.sequence.step_ms !== playbackStepMs
    ) {
      this.sequence = await loadAnimationSequence(bodyAsset, animationAsset, playbackStepMs);
      this.validateSequence(this.sequence);
    }
    if (this.sequence.frames.length === 0) {
      throw new Error('Selected animation produced no playback frames.');
    }
    return this.sequence;
  }

  private validateSequence(sequence: AnimationSequencePayload): void {
    const invalidLoopIndex = sequence.loop_index < 0 || sequence.loop_index >= sequence.frames.length;
    const invalidPlaybackEnd = sequence.playback_end_index < 0 || sequence.playback_end_index > sequence.frames.length;
    if (invalidLoopIndex || invalidPlaybackEnd || sequence.playback_end_index > sequence.frames.length) {
      throw new Error('Animation sequence payload contains invalid playback indexes.');
    }
    for (let index = 0; index < sequence.frames.length; index += 1) {
      if (sequence.frames[index].sequence_index !== index) {
        throw new Error('Animation sequence payload contains non-contiguous sequence indexes.');
      }
    }
  }

  private renderFrame(frame: AnimationSequenceFrame, loopCycle = this.currentLoopCycle): void {
    if (!this.options.scene.model || !this.bodyAsset || !this.animationAsset) {
      throw new Error('Select a catalog model and decoded ANIM entry before playback.');
    }
    const rootMotion = this.rootMotionFor(frame, loopCycle);
    this.options.scene.updateModelVertices(frame.vertices, frame.pose, this.bodyAsset, rootMotion);
    this.currentFrame = frame;
    this.currentSequenceIndex = frame.sequence_index;
    this.currentLoopCycle = loopCycle;
  }

  private rootMotionFor(frame: AnimationSequenceFrame, loopCycle: number): [number, number, number] | undefined {
    if (!frame.root_motion) return undefined;
    const sequence = this.sequence;
    if (!sequence || frame.sequence_index < sequence.loop_index || loopCycle <= 0) {
      return frame.root_motion;
    }
    return [
      frame.root_motion[0] + sequence.loop_cycle_root_delta[0] * loopCycle,
      frame.root_motion[1] + sequence.loop_cycle_root_delta[1] * loopCycle,
      frame.root_motion[2] + sequence.loop_cycle_root_delta[2] * loopCycle,
    ];
  }

  private updateReadout(frame: AnimationSequenceFrame): void {
    if (!this.bodyAsset || !this.animationAsset) return;
    const { elements } = this.options;
    elements.frame.value = String(frame.frame);
    elements.elapsed.value = String(frame.elapsed_ms);
    this.updateTimelineReadout(this.timelineMs(frame));
    const segment = frame.segment === 'loop' ? 'loop' : 'intro';
    elements.result.textContent = `Frame ${frame.frame}, previous ${frame.previous_frame}, next ${frame.next_frame}, ${frame.duration_ms} ms duration, ${segment} sample ${frame.sequence_index}`;
    this.options.setOverlay(`${this.bodyAsset.label} playing ${this.animationAsset.label}`);
  }

  private resumeIndexFor(sequence: AnimationSequencePayload, frame: number, elapsedMs: number): number {
    if (
      this.currentFrame &&
      this.currentSequenceIndex !== null &&
      this.currentFrame.frame === frame &&
      this.currentFrame.elapsed_ms === elapsedMs &&
      this.currentSequenceIndex >= 0 &&
      this.currentSequenceIndex < sequence.frames.length
    ) {
      return this.currentSequenceIndex;
    }
    this.currentLoopCycle = 0;
    return this.sequenceIndexFor(sequence, frame, elapsedMs);
  }

  private sequenceIndexFor(sequence: AnimationSequencePayload, frame: number, elapsedMs: number): number {
    if (this.animationAsset) validateAnimationFrame(frame, this.animationAsset);
    let bestIndex = -1;
    let bestElapsed = -1;
    const endIndex = this.playbackEndIndex(sequence);
    for (let index = 0; index < endIndex; index += 1) {
      const item = sequence.frames[index];
      if (item.frame !== frame || item.elapsed_ms > elapsedMs) continue;
      if (item.elapsed_ms > bestElapsed) {
        bestIndex = index;
        bestElapsed = item.elapsed_ms;
      }
    }
    if (bestIndex >= 0) return bestIndex;
    const fallback = sequence.frames.findIndex((item, index) => index < endIndex && item.frame === frame);
    return fallback >= 0 ? fallback : 0;
  }

  private loopIndex(sequence: AnimationSequencePayload): number {
    if (sequence.loop_index < 0 || sequence.loop_index >= sequence.frames.length) {
      throw new Error('Animation sequence payload contains an invalid loop index.');
    }
    return sequence.loop_index;
  }

  private playbackEndIndex(sequence: AnimationSequencePayload): number {
    if (sequence.playback_end_index < 0 || sequence.playback_end_index > sequence.frames.length) {
      throw new Error('Animation sequence payload contains an invalid playback end index.');
    }
    return sequence.playback_end_index;
  }

  private async seekTo(timelineMs: number): Promise<void> {
    const sequence = await this.getSequence();
    const index = this.sequenceIndexAtTimeline(sequence, timelineMs);
    this.pendingSeekIndex = index;
    this.currentLoopCycle = 0;
    const frame = sequence.frames[index];
    this.renderFrame(frame, 0);
    this.updateReadout(frame);
  }

  private sequenceIndexAtTimeline(sequence: AnimationSequencePayload, timelineMs: number): number {
    let bestIndex = 0;
    let bestDistance = Number.POSITIVE_INFINITY;
    const endIndex = this.playbackEndIndex(sequence);
    for (let index = 0; index < endIndex; index += 1) {
      const distance = Math.abs(this.timelineMs(sequence.frames[index]) - timelineMs);
      if (distance < bestDistance) {
        bestIndex = index;
        bestDistance = distance;
      }
    }
    return bestIndex;
  }

  private timelineMs(frame: AnimationSequenceFrame): number {
    return frame.timeline_ms;
  }

  private updateTimelineReadout(timelineMs: number): void {
    const total = Math.max(0, this.selectedStats()?.total_duration ?? 0);
    const clamped = Math.max(0, Math.min(total, timelineMs));
    const { elements } = this.options;
    elements.scrub.max = String(total);
    elements.scrub.value = String(Math.round(clamped));
    elements.timeCurrent.textContent = formatAnimationTime(clamped);
    elements.timeTotal.textContent = formatAnimationTime(total);
  }

  private runPlayback(sequence: AnimationSequencePayload, startIndex: number, token: number): Promise<void> {
    return new Promise((resolve) => {
      this.playbackResolve = () => {
        if (this.currentFrame) this.updateReadout(this.currentFrame);
        this.playbackFrame = undefined;
        this.playbackResolve = undefined;
        resolve();
      };
      let sequenceIndex = startIndex;
      let loopCycle = this.currentLoopCycle;
      let nextFrameAt = performance.now();
      const tick = (now: number) => {
        this.playbackFrame = undefined;
        if (!this.playing || token !== this.playbackToken) {
          this.playbackResolve?.();
          return;
        }
        if (this.pendingSeekIndex !== null) {
          sequenceIndex = this.pendingSeekIndex;
          this.pendingSeekIndex = null;
          loopCycle = 0;
          nextFrameAt = now;
        }
        const frame = this.advanceSequence(sequence, now, nextFrameAt, sequenceIndex, loopCycle);
        sequenceIndex = frame.nextIndex;
        loopCycle = frame.loopCycle;
        nextFrameAt = frame.nextFrameAt;
        if (frame.item) {
          this.renderFrame(frame.item, frame.itemLoopCycle);
          if (now - this.lastUiUpdateAt >= uiUpdateIntervalMs) {
            this.updateReadout(frame.item);
            this.lastUiUpdateAt = now;
          }
        }
        if (!this.playing) {
          this.playbackResolve?.();
          return;
        }
        this.playbackFrame = window.requestAnimationFrame(tick);
      };
      this.playbackFrame = window.requestAnimationFrame(tick);
    });
  }

  private advanceSequence(
    sequence: AnimationSequencePayload,
    now: number,
    nextFrameAt: number,
    startIndex: number,
    startLoopCycle: number,
  ): { item: AnimationSequenceFrame | null; itemLoopCycle: number; nextIndex: number; loopCycle: number; nextFrameAt: number } {
    let item: AnimationSequenceFrame | null = null;
    let itemLoopCycle = startLoopCycle;
    let index = startIndex;
    let loopCycle = startLoopCycle;
    let dueAt = nextFrameAt;
    const endIndex = this.repeatEnabled ? sequence.frames.length : this.playbackEndIndex(sequence);
    while (now >= dueAt) {
      if (index >= endIndex) {
        this.playing = false;
        break;
      }
      item = sequence.frames[index];
      itemLoopCycle = loopCycle;
      index += 1;
      if (index >= sequence.frames.length) {
        if (this.repeatEnabled) {
          index = this.loopIndex(sequence);
          loopCycle += 1;
        } else {
          this.playing = false;
          break;
        }
      }
      dueAt += sequence.step_ms;
    }
    return { item, itemLoopCycle, nextIndex: index, loopCycle, nextFrameAt: dueAt };
  }

  private async stepFrame(direction: -1 | 1): Promise<void> {
    if (!this.animationAsset || !this.selectedStats()) {
      throw new Error('Select a decoded ANIM entry before stepping.');
    }
    const stats = this.selectedStats()!;
    const current = numericInput(this.options.elements.frame, 'frame');
    validateAnimationFrame(current, this.animationAsset);
    const previousFrame = current;
    let next = current + direction;
    if (direction > 0 && next >= stats.keyframes) next = stats.loop_frame;
    if (direction < 0 && next < 0) next = Math.max(0, stats.keyframes - 1);
    const previousFrameValue = this.options.elements.frame.value;
    const previousElapsedValue = this.options.elements.elapsed.value;
    this.options.elements.frame.value = String(next);
    this.options.elements.elapsed.value = '0';
    try {
      await this.applyPose(previousFrame);
    } catch (error) {
      this.options.elements.frame.value = previousFrameValue;
      this.options.elements.elapsed.value = previousElapsedValue;
      throw error;
    }
  }

  private selectedStats(): AnimationStats | null {
    if (!this.animationAsset || this.animationAsset.entry_type !== 'animation') return null;
    if (!('keyframes' in this.animationAsset.stats)) return null;
    return this.animationAsset.stats;
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

function formatAnimationTime(milliseconds: number): string {
  const safeMs = Math.max(0, Math.round(milliseconds));
  const minutes = Math.floor(safeMs / 60000);
  const seconds = Math.floor((safeMs % 60000) / 1000);
  const millis = safeMs % 1000;
  return `${minutes}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
}
