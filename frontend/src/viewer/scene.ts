import * as THREE from 'three';
import { TrackballControls } from 'three/examples/jsm/controls/TrackballControls.js';
import type { Lm2Model } from '../types';
import { buildModelRoot } from './modelMesh';

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

export class ViewerScene {
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: TrackballControls;
  readonly scene: THREE.Scene;

  private readonly canvas: HTMLCanvasElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly grid: THREE.GridHelper;
  private readonly modelRoot = new THREE.Group();
  private readonly worldUp = new THREE.Vector3(0, 1, 0);
  private currentModel: Lm2Model | null = null;
  private lockHorizon = false;
  private visibility: VisibilityState = {
    faces: true,
    lines: true,
    spheres: true,
    wireframe: false,
    grid: true,
  };

  constructor(options: ViewerSceneOptions) {
    this.canvas = options.canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x151719);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100000);
    this.camera.position.set(0, 80, 160);
    this.controls = new TrackballControls(this.camera, this.renderer.domElement);
    this.controls.rotateSpeed = 3.2;
    this.controls.zoomSpeed = 1.2;
    this.controls.panSpeed = 0.8;
    this.controls.dynamicDampingFactor = 0.12;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x39424a, 2.8));
    const directional = new THREE.DirectionalLight(0xffffff, 2.2);
    directional.position.set(80, 120, 80);
    this.scene.add(directional);
    this.grid = new THREE.GridHelper(200, 20, 0x46515c, 0x2a3035);
    this.scene.add(this.grid);
    this.scene.add(new THREE.AxesHelper(40));
    this.scene.add(this.modelRoot);
  }

  get model(): Lm2Model | null {
    return this.currentModel;
  }

  loadModel(model: Lm2Model): void {
    this.disposeModelRoot();
    this.currentModel = model;
    this.modelRoot.clear();
    this.modelRoot.add(...buildModelRoot(model).children);
    this.applyVisibility(this.visibility);
    this.frameModel();
  }

  applyVisibility(visibility: VisibilityState): void {
    this.visibility = visibility;
    const faces = this.modelRoot.getObjectByName('faces');
    const lines = this.modelRoot.getObjectByName('lines');
    const spheres = this.modelRoot.getObjectByName('spheres');
    if (faces) {
      faces.visible = visibility.faces;
      faces.traverse((object) => {
        const mesh = object as THREE.Mesh;
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) {
          for (const item of material) {
            if ('wireframe' in item) item.wireframe = visibility.wireframe;
          }
        } else if (material && 'wireframe' in material) {
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
    const box = new THREE.Box3().setFromObject(this.modelRoot);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z, 1);
    this.controls.target.copy(center);
    this.camera.up.copy(this.worldUp);
    this.camera.near = Math.max(0.01, radius / 1000);
    this.camera.far = radius * 1000;
    this.camera.position.copy(center).add(new THREE.Vector3(radius * 0.7, radius * 0.55, radius * 1.35));
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

  zoomBy(factor: number): void {
    if (!this.currentModel) return;
    const offset = new THREE.Vector3().subVectors(this.camera.position, this.controls.target);
    if (offset.lengthSq() < 0.000001) return;
    this.camera.position.copy(this.controls.target).add(offset.multiplyScalar(factor));
    this.controls.handleResize();
    this.controls.update();
    this.applyHorizonLock();
  }

  resize(): void {
    const rect = this.canvas.parentElement?.getBoundingClientRect();
    if (!rect) return;
    this.renderer.setSize(rect.width, rect.height, false);
    this.camera.aspect = rect.width / Math.max(1, rect.height);
    this.camera.updateProjectionMatrix();
    this.controls.handleResize();
  }

  tick(): void {
    this.resize();
    this.controls.update();
    this.applyHorizonLock();
    this.renderer.render(this.scene, this.camera);
  }

  private applyHorizonLock(): void {
    if (!this.lockHorizon) return;
    const offset = new THREE.Vector3().subVectors(this.camera.position, this.controls.target);
    if (offset.lengthSq() < 0.000001) return;
    const spherical = new THREE.Spherical().setFromVector3(offset);
    spherical.phi = THREE.MathUtils.clamp(spherical.phi, 0.02, Math.PI - 0.02);
    offset.setFromSpherical(spherical);
    this.camera.position.copy(this.controls.target).add(offset);
    this.camera.up.copy(this.worldUp);
    this.camera.lookAt(this.controls.target);
  }

  private disposeModelRoot(): void {
    const geometries = new Set<THREE.BufferGeometry>();
    const materials = new Set<THREE.Material>();
    const textures = new Set<THREE.Texture>();

    this.modelRoot.traverse((object) => {
      const mesh = object as THREE.Mesh;
      if (mesh.geometry) geometries.add(mesh.geometry);

      const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
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
