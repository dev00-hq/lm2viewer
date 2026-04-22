# Bootstrap Prompt

You are working in `D:\repos\reverse\lba2-lm2-viewer`, an existing Python +
Vite/TypeScript/Three.js reverse-engineering viewer for Little Big Adventure 2
LM2 models and animations.

Read these first:

1. `docs/plans.md`
2. `docs/architecture.md`
3. `docs/documentation.md`
4. `docs/implement.md`
5. `AGENTS.md`

Treat `docs/plans.md` as the source of truth for milestones and decisions.
`frontend/PLAN.md` is older frontend-local context, not the main plan.

Hard requirements:

- Do not commit user-owned game assets or decoded real asset exports.
- Keep the viewer evidence-first and reverse-engineering focused.
- Preserve provenance, confidence, offsets, lengths, hashes, and unknown-field
  descriptors.
- Add tests for parser/decoder changes when a synthetic fixture can reproduce
  the rule.
- Avoid compatibility shims for old local states.
- Keep new reusable logic outside argparse and HTTP handlers.
- Use narrow staged extraction instead of broad rewrites.

Current commands:

```powershell
py -3 .\scripts\build.py
py -3 -m unittest discover -s tests -v
py -3 .\scripts\package.py
```

Current priorities:

1. Implement CLI-first, frontend-ready `OBJ + PNG + JSON` export probes.
2. Draft versioned model/entity contracts with JSON output and synthetic
   fixtures.
3. Add read-only texture/UV inspection.
4. Decode full ANIM records, then frame-step BODY + ANIM pairs before continuous
   playback.
5. Keep ANIM3DS cataloged and add deeper decode only with evidence.

Validation expectations:

- Run the smallest relevant test/build command for the change.
- For frontend or packaging changes, run the full build.
- For release script changes, run package validation.
- State any skipped validation explicitly.
