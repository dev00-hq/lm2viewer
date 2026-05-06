import type { EntityFacetSelectionKind } from '../selection';
import type { EntityContract, EntityUsageGroup, EntityWorkflowPayload, SceneAssetUsage } from '../types';

export interface EntityViewOptions {
  panel: HTMLElement;
  title: HTMLElement;
  trail: HTMLElement;
  usages: HTMLElement;
  detail: HTMLElement;
  visualLinks: HTMLElement;
  openAsset: (assetId: string) => void;
  selectEntityFacet: (workflow: EntityWorkflowPayload, kind: EntityFacetSelectionKind) => void;
  selectUsageFacet: (usage: SceneAssetUsage, kind: EntityFacetSelectionKind) => void;
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
    this.renderEntitySummary(entity, workflow);
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
      const actions = usageFacetActions(group.usages);
      if (actions.length > 0) {
        const buttons = document.createElement('div');
        buttons.className = 'entity-evidence-actions';
        for (const action of actions) {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = action.label;
          button.title = action.title;
          button.addEventListener('click', () => this.options.selectUsageFacet(action.usage, action.kind));
          buttons.append(button);
        }
        row.append(buttons);
      }
      return row;
    }));
  }

  private renderEntitySummary(entity: EntityContract | null, workflow: EntityWorkflowPayload): void {
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
      fact('Visual links', String(entity.linked_visual_assets.length)),
      fact('Port implications', String(entity.port_implications.length)),
      fact('Unknowns', String(entity.unknowns.length)),
    );

    const targets = document.createElement('section');
    targets.className = 'entity-section';
    const heading = document.createElement('h3');
    heading.textContent = 'Evidence Targets';
    const actions = document.createElement('div');
    actions.className = 'entity-evidence-actions';
    for (const target of entityFacetTargets(entity)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = target.label;
      button.title = target.title;
      button.addEventListener('click', () => this.options.selectEntityFacet(workflow, target.kind));
      actions.append(button);
    }
    targets.append(heading, actions);

    this.options.detail.replaceChildren(facts, targets);
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

function entityFacetTargets(entity: EntityContract): Array<{ kind: EntityFacetSelectionKind; label: string; title: string }> {
  const targets: Array<{ kind: EntityFacetSelectionKind; label: string; title: string }> = [
    { kind: 'runtime_sprite_state', label: 'Runtime State', title: 'Promote object flags, Sprite, Body.Num, and animation state to the active selection.' },
    { kind: 'render_contract', label: 'Render Contract', title: 'Promote draw path, sorted insertion, and recovery contract to the active selection.' },
  ];
  if (entity.initial_state.file3d_index !== undefined || entity.linked_visual_assets.some((link) => link.role === 'body')) {
    targets.splice(1, 0, { kind: 'file3d_resolution', label: 'File3D', title: 'Promote File3D/body resolution to the active selection.' });
  }
  if (entity.initial_state.anim3ds_range) {
    targets.splice(1, 0, { kind: 'anim3ds_range_state', label: 'ANIM3DS', title: 'Promote ANIM3DS frame range evidence to the active selection.' });
  }
  return targets;
}

function usageFacetActions(usages: Array<SceneAssetUsage & { usage_class?: string }>): Array<{ usage: SceneAssetUsage; kind: EntityFacetSelectionKind; label: string; title: string }> {
  const actions: Array<{ usage: SceneAssetUsage; kind: EntityFacetSelectionKind; label: string; title: string }> = [];
  const file3d = usages.find((usage) => usage.file3d_index !== undefined);
  if (file3d) {
    actions.push({ usage: file3d, kind: 'file3d_resolution', label: 'File3D', title: 'Promote this usage File3D resolver to the active selection.' });
  }
  const runtimeSprite = usages.find((usage) => usage.runtime_sprite_index !== undefined || usage.backend);
  if (runtimeSprite) {
    actions.push({ usage: runtimeSprite, kind: 'runtime_sprite_state', label: 'Runtime Sprite', title: 'Promote this usage runtime sprite resolver to the active selection.' });
  }
  const anim3ds = usages.find((usage) => usage.anim3ds_range);
  if (anim3ds) {
    actions.push({ usage: anim3ds, kind: 'anim3ds_range_state', label: 'ANIM3DS', title: 'Promote this usage ANIM3DS frame range to the active selection.' });
  }
  return actions;
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

function renderUnknown(unknown: { field: string; status: string; note: string }): HTMLElement {
  const row = document.createElement('div');
  row.className = 'entity-unknown';
  row.textContent = `${unknown.field}: ${unknown.status} - ${unknown.note}`;
  return row;
}

function sceneLabel(sceneIndex: number | null, sceneAssetId: string): string {
  return sceneIndex === null ? sceneAssetId : `Scene ${sceneIndex}`;
}

function formatPosition(position: EntityContract['position']): string {
  if (!position) return '-';
  return `${position.x}, ${position.y}, ${position.z}`;
}
