import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

test('static runtime decodes local HQR files without retired HTTP routes', async ({ page }, testInfo) => {
  const retiredRequests: string[] = [];
  const consoleErrors: string[] = [];
  page.on('request', (request) => {
    const url = request.url();
    if (/\/(api|catalog\.json|model\.json)(?:\/|$|\?)/.test(url)) retiredRequests.push(url);
  });
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));

  const assetRoot = writeStaticFixture(testInfo.outputPath('static-assets'));
  await page.goto('/');
  await page.locator('#hqrFiles').setInputFiles([
    'BODY.HQR',
    'ANIM.HQR',
    'SPRITES.HQR',
    'LBA_BKG.HQR',
    'RESS.HQR',
    'SAMPLES.HQR',
  ].map((name) => path.join(assetRoot, name)));

  await expect(page.locator('#catalogSummary')).toContainText('across 6 HQR files');
  await expect(page.locator('#catalogSummary')).toContainText('Sample archive: 1/1 decoded audio');

  await page.locator('#assetList button.asset-button').filter({ hasText: 'Twinsen without tunic model' }).click();
  await expect(page.locator('#overlay')).toContainText('Twinsen without tunic model');
  await expect(page.locator('#exportAsset')).toBeEnabled();
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#exportAsset').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^BODY\.HQR_\d+_export\.zip$/);
  const zipPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(zipPath);
  const zipBytes = readFileSync(zipPath);
  expect(zipBytes.subarray(0, 2).toString('ascii')).toBe('PK');
  const zipText = zipBytes.toString('utf8');
  expect(zipText).toContain('manifest.json');
  expect(zipText).toContain('BODY.HQR');
  expect(zipText).not.toContain('/session/');
  await expect(page.locator('#exportResult')).toContainText('Downloaded');
  await expect(page.locator('#exportResult')).toContainText('.zip');
  await expect(page.locator('#overlay')).toContainText('Exported Twinsen without tunic model');

  await expect(page.locator('#canvasAnimationSelect')).toBeEnabled();
  await page.locator('#canvasAnimationSelect').selectOption('ANIM.HQR:1');
  await expect(page.locator('#animationPose')).toBeEnabled();
  await page.locator('#animationPose').click();
  await expect(page.locator('#animationResult')).toContainText('Frame 0');
  await page.locator('#animationPlay').click();
  await expect(page.locator('#animationSequenceStrip')).toContainText('Sample 0');
  if (await page.locator('#animationPlay').getAttribute('aria-pressed') === 'true') {
    await page.locator('#animationPlay').click();
  }

  await page.locator('#assetList button.asset-button').filter({ hasText: 'Runtime sprite 0' }).click();
  await expect(page.locator('#spriteMeta')).toContainText('4x2');
  await expect(page.locator('#spriteMeta')).toContainText('RESS.HQR:0 normal palette');
  await expect(page.locator('#spriteCanvas')).toHaveJSProperty('width', 4);
  await expect(page.locator('#spriteCanvas')).toHaveJSProperty('height', 2);

  await page.locator('#entityViewTab').click();
  await page.locator('#runtimeSpriteResolve').click();
  await expect(page.locator('#runtimeSpriteResult')).toContainText('SPRITES.HQR:127');
  await expect(page.locator('#runtimeSpriteOpen')).toBeEnabled();

  await page.locator('#assetList button.asset-button').filter({ hasText: 'Background brick graphic 0' }).click();
  await expect(page.locator('#resourceMeta')).toContainText('bkg_affgraph');
  await expect(page.locator('#resourceMeta')).toContainText('ChoicePalette');
  await expect(page.locator('#resourceCanvas')).toHaveJSProperty('width', 4);
  await expect(page.locator('#resourceCanvas')).toHaveJSProperty('height', 2);

  await page.locator('#assetList button.asset-button').filter({ hasText: 'Background grid map 0' }).click();
  await expect(page.locator('#resourceMeta')).toContainText('bkg_grid_preview');
  await expect(page.locator('#resourceCanvas')).toHaveJSProperty('width', 640);
  await expect(page.locator('#resourceCanvas')).toHaveJSProperty('height', 480);

  await page.locator('#assetList button.asset-button').filter({ hasText: 'Sample 0 pcm' }).click();
  await expect(page.locator('#resourceAudio')).toBeVisible();
  await expect(page.locator('#resourceAudioMeta')).toContainText('11025Hz');
  const firstAudioSrc = await page.locator('#resourceAudioPlayer').getAttribute('src');
  expect(firstAudioSrc).toMatch(/^blob:/);

  await page.locator('#hqrFiles').setInputFiles([
    'BODY.HQR',
    'ANIM.HQR',
    'SPRITES.HQR',
    'LBA_BKG.HQR',
    'RESS.HQR',
    'SAMPLES.HQR',
  ].map((name) => path.join(assetRoot, name)));
  await expect(page.locator('#catalogSummary')).toContainText('across 6 HQR files');
  await page.locator('#assetList button.asset-button').filter({ hasText: 'Sample 0 pcm' }).click();
  await expect.poll(async () => page.locator('#resourceAudioPlayer').getAttribute('src')).not.toBe(firstAudioSrc);

  expect(retiredRequests).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test('static runtime decodes a standalone local model file', async ({ page }, testInfo) => {
  const retiredRequests: string[] = [];
  const consoleErrors: string[] = [];
  page.on('request', (request) => {
    const url = request.url();
    if (/\/(api|catalog\.json|model\.json)(?:\/|$|\?)/.test(url)) retiredRequests.push(url);
  });
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));

  const modelPath = testInfo.outputPath('standalone.lm2');
  writeFileSync(modelPath, texturedTriangleLm2());
  await page.goto('/');
  await page.locator('#file').setInputFiles(modelPath);
  await expect(page.locator('#overlay')).toContainText('standalone.lm2');
  await expect(page.locator('#stats')).toContainText('vertices');
  await expect(page.locator('#stats')).toContainText('polygons');

  expect(retiredRequests).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

function writeStaticFixture(root: string): string {
  mkdirSync(root, { recursive: true });
  writeFileSync(path.join(root, 'BODY.HQR'), classicHqr([
    resourceEntry(texturedTriangleLm2()),
    resourceEntry(texturedTriangleLm2()),
  ]));
  writeFileSync(path.join(root, 'ANIM.HQR'), hqr([resourceEntry(animationPayload())]));
  const spriteEntries = Array.from({ length: 128 }, () => Buffer.alloc(0));
  spriteEntries[0] = resourceEntry(lspSpritePayload());
  spriteEntries[127] = resourceEntry(lspSpritePayload());
  writeFileSync(path.join(root, 'SPRITES.HQR'), classicHqr(spriteEntries));
  writeFileSync(path.join(root, 'LBA_BKG.HQR'), classicHqr([
    resourceEntry(bkgHeader()),
    resourceEntry(bkgGridPayload()),
    resourceEntry(Buffer.concat([Buffer.from([1, 1, 1]), u16(0x0102)])),
    resourceEntry(Buffer.concat([u32(4), Buffer.from([1, 1, 1, 2, 0x10]), u16(1)])),
    resourceEntry(bkgAffgraphPayload()),
    resourceEntry(Buffer.alloc(512)),
  ]));
  writeFileSync(path.join(root, 'RESS.HQR'), classicHqr([
    resourceEntry(grayscalePalette()),
    Buffer.alloc(0),
    Buffer.alloc(0),
    Buffer.alloc(0),
    Buffer.alloc(0),
    Buffer.alloc(0),
    resourceEntry(textureAtlas()),
  ]));
  writeFileSync(path.join(root, 'SAMPLES.HQR'), hqr([resourceEntry(wavePayload())]));
  return root;
}

function resourceEntry(payload: Buffer): Buffer {
  return Buffer.concat([u32(payload.length), u32(payload.length), u16(0), payload]);
}

function hqr(entries: Buffer[]): Buffer {
  const tableEnd = (entries.length + 1) * 4;
  const offsets: Buffer[] = [];
  const payloads: Buffer[] = [];
  let cursor = tableEnd;
  for (const payload of entries) {
    offsets.push(u32(payload.length ? cursor : 0));
    payloads.push(payload);
    cursor += payload.length;
  }
  return Buffer.concat([u32(tableEnd), ...offsets, ...payloads]);
}

function classicHqr(entries: Buffer[]): Buffer {
  const tableEnd = entries.length * 4;
  const offsets: Buffer[] = [];
  const payloads: Buffer[] = [];
  let cursor = tableEnd;
  for (const payload of entries) {
    offsets.push(u32(payload.length ? cursor : 0));
    payloads.push(payload);
    cursor += payload.length;
  }
  return Buffer.concat([...offsets, ...payloads]);
}

function texturedTriangleLm2(): Buffer {
  const bonesOffset = 0x60;
  const verticesOffset = 0x68;
  const normalsOffset = 0x80;
  const polygonsOffset = 0x80;
  const linesOffset = 0xa0;
  const uvGroupsOffset = 0xa0;
  const header = pack('<ii6i16I',
    1, 0, 0, 10, 0, 10, 0, 0,
    1, bonesOffset,
    3, verticesOffset,
    0, normalsOffset,
    0, normalsOffset,
    0x20, polygonsOffset,
    0, linesOffset,
    0, linesOffset,
    1, uvGroupsOffset,
  );
  const bone = pack('<HHHH', 1001, 0, 0, 0);
  const vertices = Buffer.concat([
    pack('<hhhH', 0, 0, 0, 0),
    pack('<hhhH', 10, 0, 0, 0),
    pack('<hhhH', 0, 10, 0, 0),
  ]);
  const sectionHeader = pack('<HHHH', 8, 1, 0x20, 0);
  const polygon = Buffer.concat([
    pack('<HHH', 0, 1, 2),
    u16(0),
    u16(12),
    i16(0),
    Buffer.from([0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 4]),
  ]);
  return Buffer.concat([header, bone, vertices, sectionHeader, polygon, Buffer.from([0, 0, 4, 4])]);
}

function animationPayload(): Buffer {
  return pack('<HHHHHhhh hhhh Hhhh hhhh',
    2, 1, 1, 0,
    100, 0, 0, 0, 0, 0, 0, 0,
    100, 10, 0, 0, 0, 0, 0, 0,
  );
}

function lspSpritePayload(): Buffer {
  return Buffer.concat([
    Buffer.alloc(8),
    Buffer.from([4, 2, 1, 2]),
    Buffer.from([3, 0x00, 0x81, 7, 0x40, 8]),
    Buffer.from([1, 0xc3, 1, 2, 0, 3]),
  ]);
}

function bkgHeader(): Buffer {
  return pack('<HHHHHHIIII', 1, 2, 3, 4, 1, 1, 4096, 9000, 512, 256);
}

function bkgGridPayload(): Buffer {
  const columnCount = 64 * 64;
  const offsetTableBytes = columnCount * 2;
  const offsets = Buffer.alloc(offsetTableBytes);
  for (let index = 0; index < columnCount; index += 1) offsets.writeUInt16LE(offsetTableBytes, index * 2);
  return Buffer.concat([
    Buffer.from([0, 0]),
    Buffer.from([0x40]),
    Buffer.alloc(31),
    offsets,
    Buffer.from([2, 0x80]),
    u16(0x0001),
    Buffer.from([0x17]),
  ]);
}

function bkgAffgraphPayload(): Buffer {
  return Buffer.concat([
    Buffer.from([4, 2, 1, 0xfe]),
    Buffer.from([3, 0x00, 0x81, 7, 0x40, 8]),
    Buffer.from([1, 0x43, 1, 2, 0, 3]),
  ]);
}

function grayscalePalette(): Buffer {
  const palette = Buffer.alloc(256 * 3);
  for (let index = 0; index < 256; index += 1) {
    palette[index * 3] = index;
    palette[index * 3 + 1] = index;
    palette[index * 3 + 2] = index;
  }
  return palette;
}

function textureAtlas(): Buffer {
  const texture = Buffer.alloc(256 * 256);
  for (let index = 0; index < texture.length; index += 1) texture[index] = index % 4;
  return texture;
}

function wavePayload(): Buffer {
  const data = Buffer.from([0x80, 0x81, 0x82, 0x83]);
  const sampleRate = 11025;
  const channels = 1;
  const bitsPerSample = 8;
  const blockAlign = channels * Math.max(1, bitsPerSample / 8);
  const byteRate = sampleRate * blockAlign;
  const fmt = pack('<HHIIHH', 1, channels, sampleRate, byteRate, blockAlign, bitsPerSample);
  const body = Buffer.concat([
    Buffer.from('WAVEfmt ', 'ascii'),
    u32(fmt.length),
    fmt,
    Buffer.from('data', 'ascii'),
    u32(data.length),
    data,
  ]);
  return Buffer.concat([Buffer.from('RIFF', 'ascii'), u32(body.length), body]);
}

function pack(format: string, ...values: number[]): Buffer {
  const bytes: Buffer[] = [];
  let valueIndex = 0;
  let repeat = '';
  for (const token of format.replace('<', '')) {
    if (/\d/.test(token)) {
      repeat += token;
      continue;
    }
    if (!'iIhH'.includes(token)) continue;
    const count = repeat ? Number(repeat) : 1;
    repeat = '';
    for (let index = 0; index < count; index += 1) {
      const value = values[valueIndex];
      valueIndex += 1;
      if (token === 'i') bytes.push(i32(value));
      if (token === 'I') bytes.push(u32(value));
      if (token === 'h') bytes.push(i16(value));
      if (token === 'H') bytes.push(u16(value));
    }
  }
  return Buffer.concat(bytes);
}

function u32(value: number): Buffer {
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32LE(value >>> 0);
  return buffer;
}

function i32(value: number): Buffer {
  const buffer = Buffer.alloc(4);
  buffer.writeInt32LE(value);
  return buffer;
}

function u16(value: number): Buffer {
  const buffer = Buffer.alloc(2);
  buffer.writeUInt16LE(value & 0xffff);
  return buffer;
}

function i16(value: number): Buffer {
  const buffer = Buffer.alloc(2);
  buffer.writeInt16LE(value);
  return buffer;
}
