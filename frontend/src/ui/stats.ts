import type { Lm2Model } from '../types';

export function renderStats(container: HTMLElement, model: Lm2Model): void {
  const rows = Object.entries(model.stats).flatMap(([key, value]) => [`<span>${key}</span>`, `<span>${value}</span>`]);
  rows.push('<span>version</span>', `<span>${model.header.version}</span>`);
  rows.push('<span>flags</span>', `<span>0x${model.header.flags.toString(16)}</span>`);
  container.innerHTML = rows.join('');
}
