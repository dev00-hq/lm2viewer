import type { Lm2Model } from '../types';

export function renderStats(container: HTMLElement, model: Lm2Model): void {
  const rows: HTMLElement[] = [];
  for (const [key, value] of Object.entries(model.stats)) {
    rows.push(statsCell(key), statsCell(String(value)));
  }
  rows.push(statsCell('version'), statsCell(String(model.header.version)));
  rows.push(statsCell('flags'), statsCell(`0x${model.header.flags.toString(16)}`));
  rows.push(statsCell('palette evidence'), statsCell(model.palette ? `RESS.HQR:0 normal palette (${model.palette.length} colors)` : 'synthetic diagnostic preview colors'));
  rows.push(statsCell('texture atlas evidence'), statsCell(model.texture_atlas ? `RESS.HQR:1 texture atlas (${model.texture_atlas.width}x${model.texture_atlas.height})` : 'texture atlas unavailable'));
  container.replaceChildren(...rows);
}

function statsCell(text: string): HTMLSpanElement {
  const cell = document.createElement('span');
  cell.textContent = text;
  return cell;
}
