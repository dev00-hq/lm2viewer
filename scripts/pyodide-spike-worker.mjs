import { parentPort, workerData } from 'node:worker_threads';
import { loadPyodide } from '../frontend/node_modules/pyodide/pyodide.mjs';

const SPIKE_PROGRAM = String.raw`
import json
import struct
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/work")

from lba2_lm2_viewer import lba_hqr, viewer
from lba2_lm2_viewer.animation import parse_lba2_animation_records

def resource_entry(payload, compress_method=0, compressed_size=None):
    if compressed_size is None:
        compressed_size = len(payload)
    return struct.pack("<IIH", len(payload), compressed_size, compress_method) + payload

def hqr(entries):
    table_end = (len(entries) + 1) * 4
    offsets = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return struct.pack("<I", table_end) + b"".join(struct.pack("<I", offset) for offset in offsets) + payloads

def classic_hqr(entries):
    table_end = len(entries) * 4
    offsets = []
    cursor = table_end
    payloads = bytearray()
    for payload in entries:
        offsets.append(cursor if payload else 0)
        payloads.extend(payload)
        cursor += len(payload)
    return struct.pack("<I", table_end) + b"".join(struct.pack("<I", offset) for offset in offsets[1:]) + payloads

def minimal_lm2():
    header = struct.pack(
        "<ii6i16I",
        1, 0,
        0, 0, 0, 0, 0, 0,
        1, 0x60,
        1, 0x68,
        0, 0x70,
        0, 0x70,
        0, 0x70,
        0, 0x70,
        0, 0x70,
        0, 0x70,
    )
    bone = struct.pack("<HHHH", 1001, 0, 0, 0)
    vertex = struct.pack("<hhhH", 10, 20, -30, 0)
    return header + bone + vertex

def anim_payload(frames, loop_start=0, reserved=0):
    bone_count = len(frames[0][2]) if frames else 0
    payload = bytearray(struct.pack("<HHHH", len(frames), bone_count, loop_start, reserved))
    for duration, root, bones in frames:
        payload.extend(struct.pack("<Hhhh", duration, *root))
        for bone in bones:
            payload.extend(struct.pack("<hhhh", *bone))
    return bytes(payload)

results = {}

start = time.perf_counter()
regular_entries = lba_hqr.parse_table(hqr([resource_entry(b"model-bytes")]))
classic_entries = lba_hqr.parse_classic_table(classic_hqr([resource_entry(b"body-bytes"), b"", resource_entry(b"sprite-bytes")]))
results["hqr"] = {
    "ms": (time.perf_counter() - start) * 1000,
    "regular": {"count": len(regular_entries), "first_index": regular_entries[0].index, "first_length": regular_entries[0].byte_length},
    "classic": {"count": len(classic_entries), "indexes": [entry.index for entry in classic_entries if entry.byte_length]},
}

start = time.perf_counter()
model = viewer.load_lm2_bytes(minimal_lm2(), "synthetic.ldc")
model_json = model.to_viewer_json("synthetic.ldc")
results["lm2"] = {
    "ms": (time.perf_counter() - start) * 1000,
    "vertices": model_json["stats"]["vertices"],
    "bones": model_json["stats"]["bones"],
    "first_vertex": model_json["vertices"][0],
}

start = time.perf_counter()
animation = parse_lba2_animation_records(anim_payload([
    (100, (0, 0, 0), [(0, 0, 0, 0)]),
    (100, (10, 0, 0), [(0, 0, 0, 0)]),
], loop_start=1))
posed, pose = viewer.pose_lm2_model(model, animation, sample_frame=1, previous_frame=0, elapsed_ms=50)
results["animation"] = {
    "ms": (time.perf_counter() - start) * 1000,
    "keyframes": animation.keyframe_count,
    "sample_target": pose["sample"]["target_frame_index"],
    "posed_first_vertex": posed.to_viewer_json("posed.ldc", pose=pose)["vertices"][0],
}

start = time.perf_counter()
with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    body_path = root / "BODY.HQR"
    body_path.write_bytes(classic_hqr([resource_entry(minimal_lm2())]))
    catalog = viewer.build_catalog(root, selected_files=[body_path])
results["catalog"] = {
    "ms": (time.perf_counter() - start) * 1000,
    "source_mode": catalog["source_mode"],
    "asset_count": len(catalog["assets"]),
    "first_asset": catalog["assets"][0]["id"],
    "models": catalog["summary"]["models"],
}

results
`;

const startedAt = performance.now();

try {
  const pyodide = await loadPyodide({ stdout: () => {}, stderr: () => {} });
  const startupMs = performance.now() - startedAt;
  mountSources(pyodide, workerData.sources);

  const msgspec = await probeMsgspec(pyodide);
  const operationStartedAt = performance.now();
  const payload = pyodide.runPython(SPIKE_PROGRAM);
  const operationMs = performance.now() - operationStartedAt;

  parentPort?.postMessage({
    ok: true,
    startupMs,
    operationMs,
    msgspec,
    payload: payload.toJs({ dict_converter: Object.fromEntries }),
    memory: process.memoryUsage(),
  });
} catch (error) {
  parentPort?.postMessage({
    ok: false,
    error: error instanceof Error ? error.stack || error.message : String(error),
    memory: process.memoryUsage(),
  });
}

function mountSources(pyodide, sources) {
  pyodide.FS.mkdirTree('/work');
  for (const [relativePath, text] of Object.entries(sources)) {
    const target = `/work/${relativePath.replaceAll('\\', '/')}`;
    const directory = target.slice(0, target.lastIndexOf('/'));
    pyodide.FS.mkdirTree(directory);
    pyodide.FS.writeFile(target, text, { encoding: 'utf8' });
  }
}

async function probeMsgspec(pyodide) {
  const started = performance.now();
  try {
    await pyodide.loadPackage('micropip');
    const micropip = pyodide.pyimport('micropip');
    await micropip.install('msgspec');
    const version = pyodide.runPython('import msgspec; msgspec.__version__');
    return { ok: true, version, ms: performance.now() - started };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      ms: performance.now() - started,
    };
  }
}
