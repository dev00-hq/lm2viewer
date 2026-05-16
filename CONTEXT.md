# LBA2 LM2 Viewer Context

This context defines the project language for turning the viewer from a reverse-engineering workbench into the evidence layer of a remastering pipeline.

## Language

**Remaster Evidence Pipeline**:
The canonical system that decodes retail assets, builds graph-backed provenance, exports evidence artifacts, and emits stable port/remaster contracts.
_Avoid_: Remastering pipeline, final asset pipeline, production asset pipeline

**Final Asset Build Pipeline**:
The future system that emits shippable remastered assets or game-ready packages.
_Avoid_: Evidence pipeline, viewer export

**Port Asset Contract**:
A stable JSON artifact that selects graph-backed decoded facts, provenance, proof status, missing targets, and unknowns for a port or remaster consumer.
_Avoid_: Export format, viewer payload, frontend selection

**Model Port Asset Contract**:
The first **Port Asset Contract** slice for `BODY.HQR` and `OBJFIX.HQR` models, including decoded model facts and graph-backed relationship context.
_Avoid_: Model export probe, OBJ export, viewer model JSON

**Contract Consumer**:
A minimal downstream program that reads a **Port Asset Contract** and proves that a port/remaster consumer can use it without viewer internals.
_Avoid_: Manual JSON inspection, snapshot test, frontend view

**Contract Consumer Harness**:
The first automated **Contract Consumer**, used to validate a contract boundary with deterministic reports instead of creative tooling.
_Avoid_: Blender adapter, renderer, importer

**Blender Remaster Adapter**:
A future creative **Contract Consumer** that imports contract-linked model evidence into Blender for actual remastering work.
_Avoid_: First contract test, CI harness, proof of schema completeness

**Non-Claim**:
An explicit statement of what a **Port Asset Contract** does not prove and what a consumer must not infer.
_Avoid_: Limitation hidden in prose, missing field, implicit caveat

## Relationships

- A **Remaster Evidence Pipeline** precedes a **Final Asset Build Pipeline**.
- A **Final Asset Build Pipeline** may consume outputs from the **Remaster Evidence Pipeline**, but the viewer does not own final asset packaging yet.
- A **Remaster Evidence Pipeline** emits one or more **Port Asset Contracts**.
- A **Port Asset Contract** excludes viewer-only UI state such as workspace suggestions, inspector routes, preview actions, and local selection state.
- A **Port Asset Contract** carries **Non-Claims** so consumers cannot infer live runtime behavior, renderer parity, collision semantics, attachment points, remastered art, or Blender import fidelity from decoded evidence alone.
- A **Model Port Asset Contract** is the first narrow slice of a **Port Asset Contract**.
- A **Contract Consumer** is required before a **Port Asset Contract** can be considered end-to-end validated.
- A **Contract Consumer Harness** validates a **Port Asset Contract** before a **Blender Remaster Adapter** depends on it.
- A **Blender Remaster Adapter** consumes the same **Port Asset Contract** and linked evidence artifacts as the **Contract Consumer Harness**.
- The first **Contract Consumer Harness** lives in this repository but must behave like an external consumer by avoiding viewer parser, server, and catalog-graph internals.
## Example Dialogue

> **Dev:** "Is the viewer ready to become the remastering pipeline?"
> **Domain expert:** "It is ready to become the **Remaster Evidence Pipeline**, but not the **Final Asset Build Pipeline** until port contracts and runtime proof exist."

> **Dev:** "Can the frontend export payload become the contract?"
> **Domain expert:** "No — the **Port Asset Contract** must be graph-backed and stable, while frontend payloads can stay optimized for inspection."

> **Dev:** "Should scenes be the first contract slice?"
> **Domain expert:** "No — start with a **Model Port Asset Contract** because model decode, export probes, and graph relationship context are already mature enough to prove the boundary."

> **Dev:** "Can we call the contract done once the JSON validates?"
> **Domain expert:** "No — a **Contract Consumer** must read it and prove the port-facing shape works without importing viewer internals."

> **Dev:** "Should Blender be the first consumer?"
> **Domain expert:** "No — prove the boundary with a **Contract Consumer Harness** first, then build a **Blender Remaster Adapter** once the contract is stable."

> **Dev:** "Can the harness import the viewer to resolve missing details?"
> **Domain expert:** "No — the **Contract Consumer Harness** must use only the contract and linked artifacts, or the contract has not proved its boundary."

> **Dev:** "The model contract has bounds; can the port treat those as collision semantics?"
> **Domain expert:** "No — collision behavior is a **Non-Claim** unless the contract carries source-backed collision evidence."

## Flagged Ambiguities

- "Pipeline" was used to mean both evidence extraction and final shippable asset production; resolved: this roadmap targets the **Remaster Evidence Pipeline** first.
