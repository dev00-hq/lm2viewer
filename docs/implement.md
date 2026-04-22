# LBA2 LM2 Viewer Implementation Contract

## Source Of Truth

Use these files before implementing:

1. `docs/plans.md` for milestones, scope, and decisions.
2. `docs/architecture.md` for subsystem boundaries.
3. `docs/documentation.md` for current commands and repo facts.
4. `AGENTS.md` for project-specific agent rules.
5. `frontend/PLAN.md` only as historical/frontend-local context.

Do not treat `frontend/PLAN.md` as the main plan after this docs pack.

## Non-Negotiable Constraints

- Do not commit game assets, decoded real asset payloads, real texture exports,
  or real animation exports.
- Keep the viewer as a reverse-engineering instrument until core semantics are
  trustworthy.
- Do not add compatibility shims for old local states unless explicitly asked.
- Prefer one canonical current-state implementation.
- Parser and decoder behavior must be backed by tests or concrete evidence.
- Frontend render payloads and export manifests may differ, but parser logic
  must not fork.
- New export or contract code must be callable outside argparse and HTTP routing.
- Narrow module extraction is encouraged when adding capabilities; broad rewrites
  are not.

## Working Rules

When a question can be answered by inspecting code or local references, inspect
them before deciding.

When using real LBA2 assets for manual evidence:

- document archive name and entry id
- document source path only as local evidence context
- do not copy decoded output into this repo

When a parser bug is fixed:

- add or update a synthetic fixture/test when feasible
- include offsets, lengths, hashes, and confidence when describing unknowns
- preserve unknown-field descriptors rather than dropping data silently

When adding dependencies:

- update `pyproject.toml`
- update `requirements.txt`
- update README/docs if install behavior changes
- validate packaging

## Feature Execution Pattern

For a new capability:

1. Identify evidence source and current code path.
2. Add or update parser/data structures.
3. Add synthetic tests for the format rule.
4. Expose a deterministic backend/service function.
5. Add CLI or HTTP/UI surface using that service.
6. Validate with tests and the relevant build command.
7. Update docs if behavior, commands, dependencies, or scope changed.

## Export Probe Rules

First export target:

- OBJ mesh
- MTL material file
- shared atlas PNG when available
- per-UV-group PNGs when available
- JSON evidence manifest

Default choices:

- raw decoded/source coordinates
- original polygon mode
- optional triangulated mode
- JSON manifest as authority

Do not make OBJ, MTL, or PNG files the semantic contract. They are external-tool
carriers.

## Contract Rules

When model/entity contracts land:

- use versioned `msgspec.Struct` types in the package
- emit plain JSON as the stable artifact
- include schema version
- include provenance and confidence
- preserve unknown descriptors
- commit tiny synthetic fixtures only

If a JSON Schema is generated or maintained, keep it aligned with the msgspec
types and fixture expectations.

## Animation Rules

Animation playback is allowed as a near-term target only after structured decode
and frame stepping are validated.

Implementation order:

1. Decode full records.
2. Test header, keyframe, boneframe, loop, and interpolation behavior.
3. Export evidence JSON.
4. Add frame stepping for selected BODY + ANIM pairs.
5. Add continuous playback.

Use updated MBN model viewer decompilation as reference for:

- header layout
- keyframe records
- boneframe records
- case/mode handling
- 12-bit wrapped rotation interpolation
- linear interpolation
- body transform application

Do not add visual playback from guessed semantics.

## Validation Matrix

| Change type | Required validation |
| --- | --- |
| Parser/backend only | `py -3 -m unittest discover -s tests -v` |
| Frontend code | `py -3 .\scripts\build.py` |
| Packaging/build scripts | `py -3 .\scripts\build.py` and `py -3 .\scripts\package.py` |
| Dependency changes | build, tests, package, docs review |
| Export/contract changes | tests plus synthetic fixture review |

If validation cannot run, say why in the final handoff.

## Completion Criteria

A change is complete when:

- behavior is implemented in the canonical path
- relevant tests or evidence exist
- generated files are not accidentally tracked
- docs are updated when contracts, commands, or scope change
- `git status --short` has only intentional changes
