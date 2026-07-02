# discuss-mode

Read-only "brainstorm" mode for Claude Code, triggered by an inline `/discuss` marker.

## Behavior

- **`UserPromptSubmit` hook** — if the prompt contains `/discuss` as a whole token
  (`/discussion` does not count), it records a per-session marker and injects a read-only
  instruction into the turn.
- **`PreToolUse` hook** — while the marker is set, calls to `Write`, `Edit`, `MultiEdit`, and
  `NotebookEdit` are denied. Read-only tools and shell commands pass through.

The marker is keyed on `session_id` and cleared on the next prompt that doesn't use
`/discuss`, so the guard applies only to the discuss turn. Stale markers expire after 24h.

## Layout

- `hooks/hooks.json` — wires the two hooks to `hooks/run-hook.cmd`.
- `hooks/run-hook.cmd` — a polyglot launcher that picks the right Python interpreter on both
  Windows (`python` → `py`) and Unix (`python3` → `python`). Keep it LF-encoded.
- `scripts/discuss_mode.py` — the logic: marker read/write, `/discuss` detection, deny/allow.
- `scripts/user_prompt_submit.py`, `scripts/pre_tool_use.py` — thin hook entry points.

## State directory

Markers live under the OS temp dir (`claude-discuss-mode/discuss-turns/`) by default.
Override with the `DISCUSS_MODE_STATE_DIR` environment variable (also used by the tests).

## Tests

```
python -m unittest discover -s tests
```
