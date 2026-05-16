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
  interval_ms: 5000
workspace:
  root: .symphony-workspaces
agent:
  max_concurrent_agents: 1
  max_retry_backoff_ms: 300000
  max_turns: 20
codex:
  command: codex --config shell_environment_policy.inherit=all --config model_reasoning_effort=high --model gpt-5.4 app-server
  approval_policy: never
  thread_sandbox: workspace-write
  turn_sandbox_policy:
    type: workspaceWrite
hooks:
  timeout_ms: 60000
  after_create: |
    git clone --depth 1 https://github.com/dev00-hq/lm2viewer.git .
    py -3 -m pip install -e .
  before_run: |
    git status --short
---
You are working in the LBA2 LM2 Viewer repository on Linear issue {{ issue.identifier }}.

Retry attempt: {{ attempt }}

Issue context:
- Identifier: {{ issue.identifier }}
- Title: {{ issue.title }}
- Current Linear state: {{ issue.state }}
- URL: {{ issue.url }}
- Labels:{% for label in issue.labels %} {{ label }}{% endfor %}

Description:
{{ issue.description }}

Operating rules:
1. This is an unattended orchestration session. Do not ask a human for routine follow-up actions.
2. Work only in this issue workspace. Do not touch paths outside the provided repository copy.
3. Read AGENTS.md, docs/implement.md, and docs/plans.md before editing.
4. Treat docs/plans.md as the milestone source of truth and run `symphony docs-sync .\WORKFLOW.md` when docs or Linear state changes should be reconciled.
5. Keep the viewer evidence-first and reverse-engineering focused.
6. Do not commit game assets or decoded real asset exports.
7. Preserve raw evidence by descriptor, not committed copyrighted raw dumps.
8. Add focused tests for parser, export, contract, orchestration, or docs-sync changes.
9. Reproduce or identify the current signal before changing code when the issue is a bug or behavior change.
10. If you discover meaningful out-of-scope work, record it as a follow-up Linear issue instead of expanding the current issue.
11. Run the smallest relevant validation command before finishing and report the command and result.
12. Commit the completed work in the issue workspace. Do not push unless the issue explicitly asks for a push or PR.
13. Final response must report completed actions, validation, commit hash if any, and blockers only. Do not include "next steps for the user" unless blocked.

State policy:
- Backlog: do not work on the issue.
- Todo: start implementation in this workspace.
- In Progress: continue from current workspace state and avoid repeating completed investigation.
- In Review: do not make changes unless the issue description explicitly asks for review/rework handling.
- Done, Canceled, Duplicate: terminal; do not work on the issue.
