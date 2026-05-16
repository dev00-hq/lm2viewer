import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const repoRoot = path.resolve(import.meta.dirname, '..');
const frontendSrc = path.join(repoRoot, 'frontend', 'src');

const forbidden = [
  {
    label: 'retired API import',
    pattern: /(?:from\s+|import\s*\(\s*)['"](?:\.\.?\/)*api(?:\.[tj]s)?['"]/,
  },
  {
    label: 'retired static startup fetch',
    pattern: /fetch\s*\(\s*(['"`])\/(?:catalog|model)\.json\1/,
  },
  {
    label: 'retired API fetch',
    pattern: /fetch\s*\(\s*(['"`])\/api(?:\/|\?|['"`])/,
  },
  {
    label: 'retired API URL literal',
    pattern: /(['"`])\/api(?:\/|\?)\S*\1/,
  },
  {
    label: 'retired startup URL literal',
    pattern: /(['"`])\/(?:catalog|model)\.json\1/,
  },
];

const checkedExtensions = new Set(['.ts', '.tsx']);
const failures = [];

for await (const file of walk(frontendSrc)) {
  if (!checkedExtensions.has(path.extname(file))) continue;
  if (path.basename(file) === 'pythonSources.generated.ts') continue;
  const text = await readFile(file, 'utf8');
  for (const rule of forbidden) {
    if (!rule.pattern.test(text)) continue;
    failures.push(`${path.relative(repoRoot, file)}: ${rule.label}`);
  }
}

if (failures.length) {
  console.error('Static boundary check failed. Production frontend code must use runtime/viewerService, not retired local server routes.');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
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
