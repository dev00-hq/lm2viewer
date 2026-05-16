import * as THREE from "three";
import { TrackballControls } from "three/examples/jsm/controls/TrackballControls.js";
import type { Lm2Model } from "../types";
import { buildModelRoot, updateModelRootVertices } from "./modelMesh";

export interface ViewerSceneOptions {
  canvas: HTMLCanvasElement;
}

export interface VisibilityState {
  faces: boolean;
  lines: boolean;
  spheres: boolean;
  wireframe: boolean;
  grid: boolean;
}

export type CanvasBackgroundMode = "dark" | "light";
export type CanvasBackgroundShade = number;
export type PlaybackMode = "world" | "treadmill" | "pose";
const GRID_CELL_SIZE = 10;
const GRID_SIZE = 1350;
const GRID_DIVISIONS = 135;
export const DEFAULT_CANVAS_BACKGROUND_SHADE: CanvasBackgroundShade = 20;

type BackgroundPalette = { clear: number; gridCenter: number; grid: number };
type BackgroundGradient = {
  clear: [number, number];
  gridCenter: [number, number];
  grid: [number, number];
};

const backgroundGradients: Record<CanvasBackgroundMode, BackgroundGradient> = {
  dark: {
    clear: [0x000000, 0x747e86],
    gridCenter: [0x28323a, 0x9aa6af],
    grid: [0x11161a, 0x68737c],
  },
  light: {
    clear: [0xffffff, 0x8f989f],
    gridCenter: [0xa8b2bb, 0x55616b],
    grid: [0xe1e7eb, 0x707b84],
  },
};

export function canvasBackgroundColor(
  mode: CanvasBackgroundMode,
  shade: CanvasBackgroundShade,
): string {
  return `#${mixColor(backgroundGradients[mode].clear, shade).toString(16).padStart(6, "0")}`;
}

export function canvasBackgroundSliderStops(
  mode: CanvasBackgroundMode,
): [string, string] {
  const gradient = backgroundGradients[mode].clear;
  return [
    `#${gradient[0].toString(16).padStart(6, "0")}`,
    `#${gradient[1].toString(16).padStart(6, "0")}`,
  ];
}

export class ViewerScene {
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: TrackballControls;
  readonly scene: THREE.Scene;

  private readonly canvas: HTMLCanvasElement;
  private readonly renderer: THREE.WebGLRenderer;
  private grid: THREE.GridHelper;
  private readonly modelRoot = new THREE.Group();
  private readonly worldUp = new THREE.Vector3(0, 1, 0);
  private playbackMode: PlaybackMode = "world";
  private currentModel: Lm2Model | null = null;
  private currentRootMotion: [number, number, number] | null = null;
  private worldFollowTarget: THREE.Vector3 | null = null;
  private cameraFollowPaused = false;
  private lockHorizon = false;
  private canvasBackgroundMode: CanvasBackgroundMode = "dark";
  private canvasBackgroundShade: CanvasBackgroundShade =
    DEFAULT_CANVAS_BACKGROUND_SHADE;
  private visibility: VisibilityState = {
    faces: true,
    lines: true,
    spheres: true,
    wireframe: false,
    grid: true,
  };

  constructor(options: ViewerSceneOptions) {
    this.canvas = options.canvas;
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(this.backgroundPalette().clear);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100000);
    this.camera.position.set(0, 80, 160);
    this.controls = new TrackballControls(
      this.camera,
      this.renderer.domElement,
    );
    this.controls.rotateSpeed = 2.24;
    this.controls.zoomSpeed = 1.2;
    this.controls.panSpeed = 0.1;
    this.controls.dynamicDampingFactor = 0.12;
    this.controls.addEventListener("start", () => {
      this.cameraFollowPaused = true;
    });

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x39424a, 2.8));
    const directional = new THREE.DirectionalLight(0xffffff, 2.2);
    directional.position.set(80, 120, 80);
    this.scene.add(directional);
    this.grid = this.createGrid();
    this.scene.add(this.grid);
    this.scene.add(new THREE.AxesHelper(40));
    this.scene.add(this.modelRoot);
    this.resize();
  }

  get model(): Lm2Model | null {
    return this.currentModel;
  }

  get backgroundMode(): CanvasBackgroundMode {
    return this.canvasBackgroundMode;
  }

  get backgroundShade(): CanvasBackgroundShade {
    return this.canvasBackgroundShade;
  }

  loadModel(model: Lm2Model, options: { frame?: boolean } = {}): void {
    this.disposeModelRoot();
    this.currentModel = model;
    this.currentRootMotion = null;
    this.worldFollowTarget = null;
    this.cameraFollowPaused = false;
    this.modelRoot.clear();
    this.modelRoot.position.set(0, 0, 0);
    this.modelRoot.add(...buildModelRoot(model).children);
    this.applyVisibility(this.visibility);
    this.applyPlaybackTransform();
    if (options.frame !== false) this.frameModel();
  }

  updateModelVertices(
    vertices: Lm2Model["vertices"],
    pose?: Lm2Model["pose"],
    catalogAsset?: Lm2Model["catalog_asset"],
    rootMotion?: [number, number, number],
  ): void {
    if (this.currentModel) {
      this.currentModel = {
        ...this.currentModel,
        vertices,
        pose,
        catalog_asset: catalogAsset ?? this.currentModel.catalog_asset,
      };
    }
    this.currentRootMotion = rootMotion ?? null;
    updateModelRootVertices(this.modelRoot, vertices);
    this.applyPlaybackTransform();
  }

  setPlaybackMode(mode: string): void {
    if (!isPlaybackMode(mode) || this.playbackMode === mode) return;
    this.playbackMode = mode;
    this.cameraFollowPaused = false;
    this.applyPlaybackTransform();
  }

  applyVisibility(visibility: VisibilityState): void {
    this.visibility = visibility;
    const faces = this.modelRoot.getObjectByName("faces");
    const lines = this.modelRoot.getObjectByName("lines");
    const spheres = this.modelRoot.getObjectByName("spheres");
    if (faces) {
      faces.visible = visibility.faces;
      faces.traverse((object) => {
        const mesh = object as THREE.Mesh;
        const material = mesh.material as
          | THREE.Material
          | THREE.Material[]
          | undefined;
        if (Array.isArray(material)) {
          for (const item of material) {
            if ("wireframe" in item) item.wireframe = visibility.wireframe;
          }
        } else if (material && "wireframe" in material) {
          material.wireframe = visibility.wireframe;
        }
      });
    }
    if (lines) lines.visible = visibility.lines;
    if (spheres) spheres.visible = visibility.spheres;
    this.grid.visible = visibility.grid;
  }

  frameModel(): void {
    if (!this.currentModel || this.modelRoot.children.length === 0) return;
    this.cameraFollowPaused = false;
    this.worldFollowTarget = null;
    const box = new THREE.Box3().setFromObject(this.modelRoot);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z, 1);
    this.controls.target.copy(center);
    this.camera.up.copy(this.worldUp);
    this.camera.near = Math.max(0.01, radius / 1000);
    this.camera.far = radius * 1000;
    this.camera.position
      .copy(center)
      .add(new THREE.Vector3(radius * 0.7, radius * 0.55, radius * 1.35));
    this.camera.updateProjectionMatrix();
    this.controls.handleResize();
    this.controls.update();
    this.applyHorizonLock();
  }

  resetView(): void {
    this.frameModel();
  }

  setLockHorizon(lockHorizon: boolean): void {
    this.lockHorizon = lockHorizon;
    this.applyHorizonLock();
  }

  setBackground(
    mode: CanvasBackgroundMode,
    shade: CanvasBackgroundShade,
  ): void {
    if (
      this.canvasBackgroundMode === mode &&
      this.canvasBackgroundShade === shade
    )
      return;
    this.canvasBackgroundMode = mode;
    this.canvasBackgroundShade = shade;
    this.renderer.setClearColor(this.backgroundPalette().clear);

    const wasVisible = this.grid.visible;
    this.scene.remove(this.grid);
    this.disposeGrid(this.grid);
    this.grid = this.createGrid();
    this.grid.visible = wasVisible;
    this.scene.add(this.grid);
  }

  zoomBy(factor: number): void {
    if (!this.currentModel) return;
    const offset = new THREE.Vector3().subVectors(
      this.camera.position,
      this.controls.target,
    );
    if (offset.lengthSq() < 0.000001) return;
    this.camera.position
      .copy(this.controls.target)
      .add(offset.multiplyScalar(factor));
    this.controls.handleResize();
    this.controls.update();
    this.applyHorizonLock();
  }

  resize(): void {
    const rect = this.canvas.getBoundingClientRect();
    if (!rect) return;
    this.renderer.setSize(rect.width, rect.height, false);
    this.camera.aspect = rect.width / Math.max(1, rect.height);
    this.camera.updateProjectionMatrix();
    this.controls.handleResize();
  }

  tick(): void {
    this.controls.update();
    this.applyHorizonLock();
    this.renderer.render(this.scene, this.camera);
  }

  private applyHorizonLock(): void {
    if (!this.lockHorizon) return;
    const offset = new THREE.Vector3().subVectors(
      this.camera.position,
      this.controls.target,
    );
    if (offset.lengthSq() < 0.000001) return;
    const spherical = new THREE.Spherical().setFromVector3(offset);
    spherical.phi = THREE.MathUtils.clamp(spherical.phi, 0.02, Math.PI - 0.02);
    offset.setFromSpherical(spherical);
    this.camera.position.copy(this.controls.target).add(offset);
    this.camera.up.copy(this.worldUp);
    this.camera.lookAt(this.controls.target);
  }

  private createGrid(): THREE.GridHelper {
    const palette = this.backgroundPalette();
    return new THREE.GridHelper(
      GRID_SIZE,
      GRID_DIVISIONS,
      palette.gridCenter,
      palette.grid,
    );
  }

  private backgroundPalette(): BackgroundPalette {
    const gradient = backgroundGradients[this.canvasBackgroundMode];
    return {
      clear: mixColor(gradient.clear, this.canvasBackgroundShade),
      gridCenter: mixColor(gradient.gridCenter, this.canvasBackgroundShade),
      grid: mixColor(gradient.grid, this.canvasBackgroundShade),
    };
  }

  private applyPlaybackTransform(): void {
    const root = this.poseRootOffset();
    const motion = this.rootMotionOffset(root);
    const actorPosition = new THREE.Vector3(
      motion.x - root.x,
      motion.y - root.y,
      motion.z - root.z,
    );
    if (this.playbackMode === "world") {
      this.modelRoot.position.copy(actorPosition);
      this.followWorldTarget(actorPosition);
      this.grid.position.set(0, 0, 0);
      return;
    }
    this.worldFollowTarget = null;
    if (this.playbackMode === "treadmill") {
      this.modelRoot.position.set(-root.x, 0, -root.z);
      this.grid.position.set(
        wrappedGridOffset(-motion.x),
        0,
        wrappedGridOffset(-motion.z),
      );
      return;
    }
    this.modelRoot.position.set(-root.x, -root.y, -root.z);
    this.grid.position.set(0, 0, 0);
  }

  private followWorldTarget(nextTarget: THREE.Vector3): void {
    if (this.cameraFollowPaused) {
      this.worldFollowTarget = nextTarget.clone();
      return;
    }
    if (!this.worldFollowTarget) {
      this.worldFollowTarget = nextTarget.clone();
      return;
    }
    const delta = new THREE.Vector3().subVectors(
      nextTarget,
      this.worldFollowTarget,
    );
    this.worldFollowTarget.copy(nextTarget);
    if (delta.lengthSq() < 0.000001) return;
    this.controls.target.add(delta);
    this.camera.position.add(delta);
  }

  private poseRootOffset(): THREE.Vector3 {
    const sampleRoot = this.currentModel?.pose?.sample.root_delta;
    const scale = this.currentModel?.pose?.transform?.translation_scale ?? 1;
    if (!sampleRoot) return new THREE.Vector3();
    return new THREE.Vector3(
      sampleRoot[0] * scale,
      sampleRoot[1] * scale,
      sampleRoot[2] * scale,
    );
  }

  private rootMotionOffset(baseOffset: THREE.Vector3): THREE.Vector3 {
    const scale = this.currentModel?.pose?.transform?.translation_scale ?? 1;
    if (!this.currentRootMotion) return baseOffset.clone();
    return new THREE.Vector3(
      this.currentRootMotion[0] * scale,
      this.currentRootMotion[1] * scale,
      this.currentRootMotion[2] * scale,
    );
  }

  private disposeGrid(grid: THREE.GridHelper): void {
    grid.geometry.dispose();
    if (Array.isArray(grid.material)) {
      for (const material of grid.material) material.dispose();
    } else {
      grid.material.dispose();
    }
  }

  private disposeModelRoot(): void {
    const geometries = new Set<THREE.BufferGeometry>();
    const materials = new Set<THREE.Material>();
    const textures = new Set<THREE.Texture>();

    this.modelRoot.traverse((object) => {
      const mesh = object as THREE.Mesh;
      if (mesh.geometry) geometries.add(mesh.geometry);

      const material = mesh.material as
        | THREE.Material
        | THREE.Material[]
        | undefined;
      if (Array.isArray(material)) {
        for (const item of material) materials.add(item);
      } else if (material) {
        materials.add(material);
      }
    });

    for (const material of materials) {
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) {
          textures.add(value);
        }
      }
      material.dispose();
    }
    for (const geometry of geometries) geometry.dispose();
    for (const texture of textures) texture.dispose();
  }
}

function isPlaybackMode(mode: string): mode is PlaybackMode {
  return mode === "world" || mode === "treadmill" || mode === "pose";
}

function mixColor(
  [start, end]: [number, number],
  shade: CanvasBackgroundShade,
): number {
  const t = Math.max(0, Math.min(100, shade)) / 100;
  const red = mixChannel((start >> 16) & 0xff, (end >> 16) & 0xff, t);
  const green = mixChannel((start >> 8) & 0xff, (end >> 8) & 0xff, t);
  const blue = mixChannel(start & 0xff, end & 0xff, t);
  return (red << 16) | (green << 8) | blue;
}

function mixChannel(start: number, end: number, t: number): number {
  return Math.round(start + (end - start) * t);
}

function wrappedGridOffset(value: number): number {
  return ((value % GRID_CELL_SIZE) + GRID_CELL_SIZE) % GRID_CELL_SIZE;
}
