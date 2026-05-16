import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { Worker } from 'node:worker_threads';

const repoRoot = path.resolve(import.meta.dirname, '..');
const packageRoot = path.join(repoRoot, 'lba2_lm2_viewer');
const workerPath = path.join(repoRoot, 'scripts', 'pyodide-spike-worker.mjs');
const reportPath = path.join(repoRoot, 'docs', 'pyodide-spike-results.json');

const sources = await collectPythonPackageSources(packageRoot);
const sourceBytes = Object.values(sources).reduce((total, text) => total + Buffer.byteLength(text, 'utf8'), 0);
const startedAt = performance.now();
const result = await runWorker({ sources });
const elapsedMs = performance.now() - startedAt;

const report = {
  schema: 'lba2_lm2_viewer.pyodide_spike.v1',
  generated_at: new Date().toISOString(),
  source_files: Object.keys(sources).length,
  source_bytes: sourceBytes,
  elapsed_ms: elapsedMs,
  ...result,
};

await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');

if (!result.ok) {
  console.error(result.error);
  process.exit(1);
}

console.log(JSON.stringify({
  ok: result.ok,
  startup_ms: Math.round(result.startupMs),
  operation_ms: Math.round(result.operationMs),
  source_files: report.source_files,
  source_bytes: report.source_bytes,
  msgspec: result.msgspec,
  payload: result.payload,
  report: path.relative(repoRoot, reportPath),
}, null, 2));

async function collectPythonPackageSources(root) {
  const sources = {};
  for await (const file of walk(root)) {
    if (!isPackagedRuntimeSource(root, file)) continue;
    const relativePath = path.relative(repoRoot, file).replaceAll(path.sep, '/');
    const text = await readFile(file, 'utf8');
    sources[relativePath] = browserRuntimeSource(relativePath, text);
  }
  return sources;
}

function isPackagedRuntimeSource(root, file) {
  const relative = path.relative(root, file).replaceAll(path.sep, '/');
  if (relative === 'body_metadata.json') return true;
  return relative.endsWith('.py') && !relative.startsWith('frontend/');
}

function browserRuntimeSource(relativePath, text) {
  if (relativePath === 'lba2_lm2_viewer/server.py') return browserRuntimeServerSource(text);
  if (relativePath === 'lba2_lm2_viewer/viewer.py') return browserRuntimeViewerSource(text);
  return text;
}

function browserRuntimeServerSource(text) {
  const handlerMarker = '\n    def handler_class(self) -> type[BaseHTTPRequestHandler]:';
  const handlerIndex = text.indexOf(handlerMarker);
  if (handlerIndex === -1) {
    throw new Error('Could not find HTTP handler marker while preparing browser runtime server source.');
  }
  let runtime = text.slice(0, handlerIndex);
  for (const pattern of [
    /^import mimetypes\r?\n/m,
    /^import sys\r?\n/m,
    /^import urllib\.parse\r?\n/m,
    /^import webbrowser\r?\n/m,
    /^from http\.server import BaseHTTPRequestHandler, ThreadingHTTPServer\r?\n/m,
    /^    DEFAULT_HOST,\r?\n/m,
    /^    DEFAULT_PORT,\r?\n/m,
    /^    FRONTEND_DIST,\r?\n/m,
    /^    parse_multipart_upload,\r?\n/m,
    /^    pick_directory_dialog,\r?\n/m,
    /^    pick_hqr_files_dialog,\r?\n/m,
  ]) {
    runtime = runtime.replace(pattern, '');
  }
  if (/\/api\//.test(runtime) || /BaseHTTPRequestHandler|ThreadingHTTPServer/.test(runtime)) {
    throw new Error('Browser runtime server source still contains retired HTTP API markers.');
  }
  return `${runtime}\n`;
}

function browserRuntimeViewerSource(text) {
  const pickerMarker = 'def pick_directory_dialog() -> Path:';
  const pickerIndex = text.indexOf(pickerMarker);
  if (pickerIndex === -1) {
    throw new Error('Could not find picker marker while preparing browser runtime viewer source.');
  }
  const runtime = text.slice(0, pickerIndex);
  if (/pick_directory_dialog|pick_hqr_files_dialog|pick_export_directory_dialog/.test(runtime)) {
    throw new Error('Browser runtime viewer source still contains local picker markers.');
  }
  return `${runtime}\n`;
}

async function runWorker(workerData) {
  return await new Promise((resolve, reject) => {
    const worker = new Worker(workerPath, { workerData });
    worker.once('message', resolve);
    worker.once('error', reject);
    worker.once('exit', (code) => {
      if (code !== 0) reject(new Error(`Pyodide spike worker exited with code ${code}`));
    });
  });
}

async function* walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else if (entry.isFile()) {
      yield fullPath;
    }
  }
}
