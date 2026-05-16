import { loadPyodide, type PyodideInterface } from 'pyodide';

export interface PyodideSpikeRequest {
  sources: Record<string, string>;
  program: string;
}

export interface PyodideSpikeSuccess {
  ok: true;
  startupMs: number;
  operationMs: number;
  result: unknown;
}

export interface PyodideSpikeFailure {
  ok: false;
  error: string;
}

export type PyodideSpikeResponse = PyodideSpikeSuccess | PyodideSpikeFailure;

let pyodidePromise: Promise<PyodideInterface> | null = null;

self.addEventListener('message', (event: MessageEvent<PyodideSpikeRequest>) => {
  void runSpike(event.data).then((message) => {
    self.postMessage(message);
  });
});

async function runSpike(request: PyodideSpikeRequest): Promise<PyodideSpikeResponse> {
  const startedAt = performance.now();
  try {
    const pyodide = await pyodideRuntime();
    const startupMs = performance.now() - startedAt;
    mountSources(pyodide, request.sources);
    const operationStartedAt = performance.now();
    const result = pyodide.runPython(request.program);
    return {
      ok: true,
      startupMs,
      operationMs: performance.now() - operationStartedAt,
      result: result?.toJs ? result.toJs({ dict_converter: Object.fromEntries }) : result,
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function pyodideRuntime(): Promise<PyodideInterface> {
  pyodidePromise ||= loadPyodide();
  return pyodidePromise;
}

function mountSources(pyodide: PyodideInterface, sources: Record<string, string>): void {
  pyodide.FS.mkdirTree('/work');
  for (const [relativePath, text] of Object.entries(sources)) {
    const target = `/work/${relativePath.replaceAll('\\', '/')}`;
    const directory = target.slice(0, target.lastIndexOf('/'));
    pyodide.FS.mkdirTree(directory);
    pyodide.FS.writeFile(target, text);
  }
}
