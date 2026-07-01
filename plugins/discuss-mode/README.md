# discuss-mode

A lightweight `/discuss` mode for Claude Code. When the current prompt contains the inline
marker `/discuss`, this plugin:

1. Injects read-only brainstorming guidance into the turn (via a `UserPromptSubmit` hook), and
2. Blocks Claude's file-mutating tools — `Write`, `Edit`, `NotebookEdit` — for that turn
   (via a `PreToolUse` hook that returns `permissionDecision: "deny"`).

Shell commands (`Bash`) and read-only tools (`Read`, `Grep`, `Glob`) are not blocked. This is an
intent guardrail, not a sandbox.

## How it works

- `hooks/hooks.json` wires two hooks to Python scripts under `scripts/`, using
  `${CLAUDE_PLUGIN_ROOT}` to locate them.
- `scripts/discuss_mode.py` holds the logic. On a `/discuss` prompt it writes a per-turn marker
  file keyed by `sha256(session_id:prompt_id)`; the `PreToolUse` hook denies mutating tools only
  while that marker exists. Markers auto-expire after 24h.
- The `/discuss` match is whole-token (`/discussion` does not trigger it).

## Turn scoping

The marker is keyed by Claude Code's per-turn `prompt_id`, so the guardrail applies only to the
turn that used `/discuss`. The next turn (without `/discuss`) is unrestricted.

## State directory

Marker files live under the OS temp dir (`claude-discuss-mode/discuss-turns/`) by default.
Override with the `DISCUSS_MODE_STATE_DIR` environment variable (also used by the tests).

## Tests

```
python -m unittest discover -s tests
```
