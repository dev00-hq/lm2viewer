---
tracker:
  kind: linear
  api_key: $LINEAR_API_KEY
  project_slug: lm2-viewer-c96825883574
  active_states:
    - Todo
    - In Progress
  terminal_states:
    - Done
    - Canceled
    - Duplicate
polling:
  interval_ms: 30000
workspace:
  root: .symphony-workspaces
agent:
  max_concurrent_agents: 1
  max_retry_backoff_ms: 300000
  max_turns: 3
codex:
  command: codex app-server
hooks:
  timeout_ms: 60000
  before_run: |
    git status --short
---
You are working in the LBA2 LM2 Viewer repository on Linear issue {{ issue.identifier }}.

Issue title:
{{ issue.title }}

Issue description:
{{ issue.description }}

Rules:
- Read AGENTS.md and docs/implement.md before editing.
- Treat docs/plans.md as the source of truth for roadmap and scope.
- Keep the viewer evidence-first and reverse-engineering focused.
- Do not commit game assets or decoded real asset exports.
- Add focused tests for parser, export, contract, or orchestration changes.
- Run the smallest relevant validation command before finishing and report it.
