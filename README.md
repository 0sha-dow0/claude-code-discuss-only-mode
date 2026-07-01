# Claude Discuss Mode

A public [Claude Code](https://code.claude.com) plugin marketplace containing `discuss-mode`,
a lightweight hook bundle for `/discuss` turns.

When a prompt contains `/discuss`, the plugin injects read-only brainstorming guidance for the
current turn and blocks Claude's file-mutating tools (`Write`, `Edit`, `NotebookEdit`). Shell
commands (`Bash`) are not classified or blocked.

This is a Claude Code port of the Codex `discuss-mode` plugin.

## Install

Add this marketplace:

```
/plugin marketplace add 0sha-dow0/claude-discuss-mode
```

Install the plugin:

```
/plugin install discuss-mode@discuss-mode-marketplace
/reload-plugins
```

### Requirements

- Python 3.8+ available as either `python3` or `python` on your PATH (the hooks try
  `python3` first, then fall back to `python`).
- `sh` on your PATH. macOS and Linux always have it; on **Windows** install
  [Git for Windows](https://git-scm.com/download/win) (which Claude Code already recommends).

## Usage

Include `/discuss` as an inline marker in your prompt. Avoid placing it at the very start,
because Claude Code reserves leading `/...` input for slash commands:

```text
Review this design /discuss before we implement it.
```

The marker is case-sensitive and applies only to the current turn.

## Why this exists

Default mode is optimized for execution. Sometimes you want to brainstorm, clarify, or review
a design without letting Claude immediately edit files. `/discuss` marks the current turn as
read-only brainstorming and blocks Claude's edit path (`Write`/`Edit`/`NotebookEdit`) with
feedback telling the model not to mutate and to continue the discussion instead.

## Scope and limitations (read before relying on it)

What is **hard-blocked** during a `/discuss` turn: `Write`, `Edit`, `MultiEdit`, `NotebookEdit`.
Those calls are denied at the `PreToolUse` hook and cannot proceed.

What is **not** blocked (by design — this is an intent guardrail, not a sandbox):

- `Bash` — a shell command can still write files (`echo > f`, `sed -i`, `rm`, …). Not blocked,
  because `/discuss` explicitly allows read-only shell inspection (`grep`, `cat`, `ls`).
- MCP tools that write files or call external services. Only the built-in edit tools are matched.

Also note: put `/discuss` **after** some leading text, not at the very start of the prompt.
A message beginning with `/` is treated by Claude Code as a slash command, so a leading
`/discuss` will not reach the hook. `Review this /discuss` works; `/discuss review this` may not.

## License

MIT
