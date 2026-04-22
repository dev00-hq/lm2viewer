# Symphony Service

This repository includes a Python implementation of the draft OpenAI Symphony
service specification:

`https://github.com/openai/symphony/blob/main/SPEC.md`

The implementation is intentionally stdlib-only and lives in the `symphony/`
package.

## Implemented Surface

- `symphony` console script and `py -3 -m symphony` module entry point.
- `WORKFLOW.md` loader with YAML-front-matter subset and Markdown prompt body.
- Typed config layer with defaults and `$VAR` resolution.
- Strict prompt rendering for `issue` and `attempt`.
- Linear-compatible issue tracker client and normalized issue model.
- Workspace manager with deterministic sanitized issue paths.
- Workspace lifecycle hooks: `after_create`, `before_run`, `after_run`, and
  `before_remove`.
- Polling orchestrator with in-memory state, bounded concurrency, blocker
  eligibility, reconciliation, retry scheduling, and structured logs.
- Codex app-server subprocess client for `initialize`, `initialized`,
  `thread/start`, and `turn/start`.

Not implemented yet:

- Optional HTTP status/control server.
- Optional `linear_graphql` client-side tool extension.
- Persistent retry/session state across process restarts.
- Tracker write APIs.
- Non-Linear tracker adapters.

## Usage

This repository includes a checked-in `WORKFLOW.md` for the Linear `LM2 Viewer`
project:

- Linear project: `https://linear.app/lm2viewer/project/lm2-viewer-c96825883574`
- Workspace root: `.symphony-workspaces`
- Tracker credential: `LINEAR_API_KEY`

The Codex Linear connector can manage issues interactively, but the Symphony
service itself runs outside connector auth and reads Linear through
`LINEAR_API_KEY`.

For another project, create or edit a `WORKFLOW.md`:

```md
---
tracker:
  kind: linear
  api_key: $LINEAR_API_KEY
  project_slug: YOUR_PROJECT
workspace:
  root: .symphony-workspaces
agent:
  max_concurrent_agents: 2
codex:
  command: codex app-server
---
Work on {{ issue.identifier }}: {{ issue.title }}.

Description:
{{ issue.description }}
```

Run one scheduler tick:

```powershell
symphony .\WORKFLOW.md --once
```

Run continuously:

```powershell
symphony .\WORKFLOW.md
```

If the console script is not on `PATH`:

```powershell
py -3 -m symphony .\WORKFLOW.md
```

## Trust And Safety Posture

Symphony is an orchestrator. It reads eligible Linear issues, creates or reuses
per-issue workspaces, runs configured hooks, and launches a coding-agent
app-server process in the issue workspace.

This implementation does not add a sandbox beyond:

- per-issue workspace path creation and containment checks
- running hooks with the workspace as current directory
- launching the app-server with the workspace as current directory
- passing configured Codex approval and sandbox settings through to the
  app-server payload

Operators are responsible for choosing safe `WORKFLOW.md` hooks, Codex sandbox
settings, workspace roots, credentials, and host permissions. The Linear API key
and coding-agent credentials available in the host environment are reachable by
the service and by configured hooks/agent processes.

Do not run untrusted workflow files.

## Validation

The core implementation is covered by unit tests for:

- workflow/config parsing and strict templates
- workspace path handling and cleanup
- Linear query/normalization behavior
- orchestrator dispatch eligibility

Run:

```powershell
py -3 -m unittest discover -s tests -v
```
