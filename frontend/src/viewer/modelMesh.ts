import * as THREE from 'three';
import type { Lm2Model } from '../types';

const fallbackPalette = [
  0x1c1f23, 0x255f9e, 0x2d9f65, 0x35a7b8, 0xb33f4a, 0x8d62d9, 0xc98238, 0xc7cbd1,
  0x69727d, 0x61a8ff, 0x74d99f, 0x74e5e8, 0xff786f, 0xd6a1ff, 0xffd36f, 0xf7f7f2,
];

type TextureEntry = {
  texture: THREE.DataTexture;
  atlas: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  uvWidth: number;
  uvHeight: number;
};

type TexturedBucket = {
  entry: TextureEntry;
  positions: number[];
  uvs: number[];
};

function toThree(vertex: [number, number, number, number]): THREE.Vector3 {
  return new THREE.Vector3(vertex[0], vertex[1], vertex[2]);
}

function paletteIndexOf(primitive: { color: number; palette_index?: number }): number {
  return primitive.palette_index ?? primitive.color;
}

function colorFor(model: Lm2Model, paletteIndex: number): number {
  if (model.palette && paletteIndex >= 0 && paletteIndex < model.palette.length) {
    return model.palette[paletteIndex];
  }
  return fallbackPalette[Math.floor(paletteIndex / 16) % fallbackPalette.length];
}

export function buildModelRoot(model: Lm2Model): THREE.Group {
  const root = new THREE.Group();
  root.add(buildFaces(model));
  root.add(buildLines(model));
  root.add(buildSpheres(model));
  return root;
}

function buildFaces(model: Lm2Model): THREE.Group {
  const group = new THREE.Group();
  group.name = 'faces';
  const textureEntries = buildTextureEntries(model);
  const byColor = new Map<number, number[][]>();
  const byTexture = new Map<number, TexturedBucket>();

  for (const poly of model.polygons) {
    const entry = poly.texture === null ? undefined : textureEntries.get(poly.texture);
    if (poly.has_texture && entry && poly.uv && poly.uv.length === poly.vertices.length) {
      const bucket = byTexture.get(poly.texture!) ?? { entry, positions: [], uvs: [] };
      pushTexturedPolygon(model, poly.vertices, poly.uv, bucket, entry);
      byTexture.set(poly.texture!, bucket);
      continue;
    }

    const color = paletteIndexOf(poly);
    const bucket = byColor.get(color) ?? [];
    const vertices = poly.vertices;
    if (vertices.length === 3) bucket.push(vertices);
    if (vertices.length === 4) bucket.push([vertices[0], vertices[1], vertices[2]], [vertices[0], vertices[2], vertices[3]]);
    byColor.set(color, bucket);
  }
  for (const [color, triangles] of byColor.entries()) {
    const positions: number[] = [];
    for (const triangle of triangles) {
      for (const index of triangle) {
        const point = toThree(model.vertices[index]);
        positions.push(point.x, point.y, point.z);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.computeVertexNormals();
    const material = new THREE.MeshBasicMaterial({
      color: colorFor(model, color),
      side: THREE.DoubleSide,
      toneMapped: false,
    });
    group.add(new THREE.Mesh(geometry, material));
  }

  for (const bucket of byTexture.values()) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(bucket.positions, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(bucket.uvs, 2));
    geometry.computeVertexNormals();
    const material = new THREE.MeshLambertMaterial({
      map: bucket.entry.texture,
      color: 0xffffff,
      side: THREE.DoubleSide,
      toneMapped: false,
    });
    group.add(new THREE.Mesh(geometry, material));
  }
  return group;
}

function pushTexturedPolygon(
  model: Lm2Model,
  vertexIndices: number[],
  uvCoords: [number, number][],
  bucket: TexturedBucket,
  entry: TextureEntry,
): void {
  const triangles =
    vertexIndices.length === 4
      ? [
          [0, 1, 2],
          [0, 2, 3],
        ]
      : [[0, 1, 2]];

  for (const triangle of triangles) {
    for (const localIndex of triangle) {
      const point = toThree(model.vertices[vertexIndices[localIndex]]);
      const [u, v] = uvForEntry(uvCoords[localIndex], entry);
      bucket.positions.push(point.x, point.y, point.z);
      bucket.uvs.push(u, v);
    }
  }
}

function buildTextureEntries(model: Lm2Model): Map<number, TextureEntry> {
  const entries = new Map<number, TextureEntry>();
  const atlas = model.texture_atlas;
  if (!atlas) return entries;

  const usedTextureIndices = new Set<number>();
  for (const poly of model.polygons) {
    if (poly.has_texture && poly.texture !== null && poly.uv && poly.uv.length === poly.vertices.length) {
      usedTextureIndices.add(poly.texture);
    }
  }
  if (usedTextureIndices.size === 0) return entries;

  let fullAtlasTexture: THREE.DataTexture | null = null;
  for (const index of usedTextureIndices) {
    const group = model.uv_groups[index];
    if (!group) continue;
    if (group.w === 0xff && group.h === 0xff) {
      fullAtlasTexture ??= textureFromPixels(atlas.width, atlas.height, atlas.pixels);
      entries.set(index, {
        texture: fullAtlasTexture,
        atlas: true,
        x: group.x,
        y: group.y,
        width: atlas.width,
        height: atlas.height,
        uvWidth: atlas.width,
        uvHeight: atlas.height,
      });
      continue;
    }

    const width = group.w + 1;
    const height = group.h + 1;
    const pixels: number[] = [];
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const sourceX = group.x + x;
        const sourceY = group.y + y;
        if (sourceX >= atlas.width || sourceY >= atlas.height) {
          pixels.push(0);
          continue;
        }
        pixels.push(atlas.pixels[sourceY * atlas.width + sourceX]);
      }
    }
    entries.set(index, {
      texture: textureFromPixels(width, height, pixels),
      atlas: false,
      x: group.x,
      y: group.y,
      width,
      height,
      uvWidth: group.w,
      uvHeight: group.h,
    });
  }
  return entries;
}

function textureFromPixels(width: number, height: number, pixels: number[]): THREE.DataTexture {
  const data = new Uint8Array(width * height * 4);
  for (let index = 0; index < width * height; index += 1) {
    const color = pixels[index] ?? 0;
    data[index * 4] = (color >> 16) & 0xff;
    data[index * 4 + 1] = (color >> 8) & 0xff;
    data[index * 4 + 2] = color & 0xff;
    data[index * 4 + 3] = 0xff;
  }
  const texture = new THREE.DataTexture(data, width, height, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;
  return texture;
}

function uvForEntry(coord: [number, number], entry: TextureEntry): [number, number] {
  const [u, v] = coord;
  if (entry.atlas) {
    return [(entry.x + u) / entry.uvWidth, (entry.y + v) / entry.uvHeight];
  }
  return [u / entry.uvWidth, v / entry.uvHeight];
}

function buildLines(model: Lm2Model): THREE.Group {
  const group = new THREE.Group();
  group.name = 'lines';
  for (const line of model.lines) {
    const start = toThree(model.vertices[line.vertices[0]]);
    const end = toThree(model.vertices[line.vertices[1]]);
    const mesh = cylinderBetween(start, end, 0.35, colorFor(model, paletteIndexOf(line)));
    if (mesh) group.add(mesh);
  }
  return group;
}

function buildSpheres(model: Lm2Model): THREE.Group {
  const group = new THREE.Group();
  group.name = 'spheres';
  for (const sphere of model.spheres) {
    const position = toThree(model.vertices[sphere.vertex]);
    const geometry = new THREE.SphereGeometry(Math.max(0.35, sphere.size), 16, 12);
    const material = new THREE.MeshStandardMaterial({ color: colorFor(model, paletteIndexOf(sphere)), roughness: 0.75 });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(position);
    group.add(mesh);
  }
  return group;
}

function cylinderBetween(start: THREE.Vector3, end: THREE.Vector3, radius: number, color: number): THREE.Mesh | null {
  const delta = new THREE.Vector3().subVectors(end, start);
  const length = delta.length();
  if (length < 0.001) return null;
  const geometry = new THREE.CylinderGeometry(radius, radius, length, 6, 1);
  const material = new THREE.MeshStandardMaterial({ color, roughness: 0.8 });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(start).addScaledVector(delta, 0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize());
  return mesh;
}
