import type { EntityContract, EntityUsageGroup, EntityWorkflowPayload } from '../types';

export interface EntityViewOptions {
  panel: HTMLElement;
  title: HTMLElement;
  trail: HTMLElement;
  usages: HTMLElement;
  detail: HTMLElement;
  visualLinks: HTMLElement;
  openAsset: (assetId: string) => void;
}

export class EntityView {
  private workflow: EntityWorkflowPayload | null = null;

  constructor(private readonly options: EntityViewOptions) {}

  setWorkflow(workflow: EntityWorkflowPayload | null): void {
    this.workflow = workflow;
    this.render();
  }

  private render(): void {
    if (!this.workflow) {
      this.options.title.textContent = 'No entity selected';
      this.options.trail.replaceChildren();
      this.options.usages.textContent = 'Select a catalog asset or resolve a runtime sprite.';
      this.options.detail.replaceChildren();
      this.options.visualLinks.replaceChildren();
      return;
    }

    const workflow = this.workflow;
    const entity = workflow.selected_entity;
    this.options.title.textContent = entity?.label || workflow.resolved_asset?.label || 'Evidence workflow';
    this.renderTrail(workflow);
    this.renderUsages(workflow.usage_groups);
    this.renderEntity(entity, workflow);
    this.renderVisualLinks(entity);
  }

  private renderTrail(workflow: EntityWorkflowPayload): void {
    const nodes = workflow.evidence_trail.map((step, index) => {
      const node = document.createElement('div');
      node.className = 'entity-trail-node';
      const label = document.createElement('strong');
      label.textContent = step.label;
      const meta = document.createElement('span');
      meta.textContent = [step.step, step.usage_class, step.render_backend].filter(Boolean).join(' | ');
      node.append(label, meta);
      if (index === 0) return node;
      const wrapper = document.createElement('div');
      wrapper.className = 'entity-trail-step';
      const arrow = document.createElement('span');
      arrow.className = 'entity-trail-arrow';
      arrow.textContent = '>';
      wrapper.append(arrow, node);
      return wrapper;
    });
    this.options.trail.replaceChildren(...nodes);
  }

  private renderUsages(groups: EntityUsageGroup[]): void {
    if (!groups.length) {
      this.options.usages.textContent = 'No scene usage is known for this entry.';
      return;
    }
    this.options.usages.replaceChildren(...groups.slice(0, 24).map((group) => {
      const row = document.createElement('div');
      row.className = 'entity-usage-row';
      const head = document.createElement('div');
      head.className = 'entity-usage-head';
      head.textContent = `${sceneLabel(group.scene_index, group.scene_asset_id)} object ${group.object_index ?? '-'} (${group.usages.length})`;
      const classes = document.createElement('div');
      classes.className = 'entity-usage-classes';
      classes.textContent = group.usage_classes.join(', ');
      const detail = document.createElement('div');
      detail.className = 'entity-usage-detail';
      detail.textContent = group.usages
        .slice(0, 4)
        .map((usage) => `${usage.kind}: ${usage.reference_key || usage.resolution_rule || usage.index_rule || usage.target_asset_id || ''}`)
        .join(' | ');
      row.append(head, classes, detail);
      return row;
    }));
  }

  private renderEntity(entity: EntityContract | null, workflow: EntityWorkflowPayload): void {
    if (!entity) {
      const empty = document.createElement('div');
      empty.className = 'entity-empty';
      empty.textContent = 'No entity contract could be built from this evidence.';
      this.options.detail.replaceChildren(empty, ...workflow.unknowns.map(renderUnknown));
      return;
    }

    const facts = document.createElement('div');
    facts.className = 'entity-facts';
    facts.append(
      fact('Entity', entity.entity_id),
      fact('Backend', entity.render_backend),
      fact('Confidence', entity.confidence),
      fact('Usage', `${entity.provenance.usage_kind || '-'} / ${entity.provenance.usage_class || '-'}`),
      fact('Position', formatPosition(entity.position)),
      fact('Resolution', entity.provenance.resolution_rule || '-'),
    );

    const contract = document.createElement('section');
    contract.className = 'entity-section';
    contract.append(sectionTitle('Render Contract'));
    contract.append(
      fact('Draw', entity.render_contract.draw_path || '-'),
      fact('Sort', entity.render_contract.sort_key || '-'),
      fact('Recover', entity.render_contract.recovery_path || '-'),
      fact('Steps', entity.render_contract.contract_steps.join(', ') || '-'),
      fact('Source', entity.render_contract.source || '-'),
    );

    const implications = document.createElement('section');
    implications.className = 'entity-section';
    implications.append(sectionTitle('Port Implications'));
    for (const implication of entity.port_implications) {
      const item = document.createElement('div');
      item.className = 'entity-implication';
      item.textContent = `${implication.area}: ${implication.claim} (${implication.evidence})`;
      implications.append(item);
    }

    const script = document.createElement('section');
    script.className = 'entity-section';
    script.append(sectionTitle('Script And Local Links'));
    script.append(
      fact('Asset links', String(entity.script_driven_links.length)),
      fact('Local links', String(entity.local_links.length)),
      fact('Cross-script links', String(entity.cross_script_links.length)),
    );

    const unknowns = document.createElement('section');
    unknowns.className = 'entity-section';
    unknowns.append(sectionTitle('Unknowns'));
    if (entity.unknowns.length) {
      unknowns.append(...entity.unknowns.map(renderUnknown));
    } else {
      unknowns.append(fact('Status', 'No explicit unknowns on this compact entity.'));
    }

    this.options.detail.replaceChildren(facts, contract, implications, script, unknowns);
  }

  private renderVisualLinks(entity: EntityContract | null): void {
    this.options.visualLinks.replaceChildren();
    if (!entity?.linked_visual_assets.length) {
      this.options.visualLinks.textContent = 'No linked visual assets.';
      return;
    }
    for (const link of entity.linked_visual_assets) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'entity-link-button';
      button.disabled = link.asset_available === false;
      button.textContent = `${link.role}: ${link.asset_id}`;
      button.title = link.resolution_rule || `Open ${link.asset_id}`;
      button.addEventListener('click', () => this.options.openAsset(link.asset_id));
      this.options.visualLinks.append(button);
    }
  }
}

function fact(label: string, value: string): HTMLElement {
  const row = document.createElement('div');
  row.className = 'entity-fact';
  const key = document.createElement('span');
  key.textContent = label;
  const val = document.createElement('strong');
  val.textContent = value;
  row.append(key, val);
  return row;
}

function sectionTitle(text: string): HTMLElement {
  const title = document.createElement('h3');
  title.textContent = text;
  return title;
}

function renderUnknown(unknown: { field: string; status: string; note: string }): HTMLElement {
  const row = document.createElement('div');
  row.className = 'entity-unknown';
  row.textContent = `${unknown.field}: ${unknown.status} - ${unknown.note}`;
  return row;
}

function sceneLabel(sceneIndex: number | null, fallback: string): string {
  return sceneIndex === null ? fallback : `Scene ${sceneIndex}`;
}

function formatPosition(position: EntityContract['position']): string {
  if (!position) return '-';
  return `${position.x}, ${position.y}, ${position.z}`;
}
