# discuss-mode

A Claude Code plugin that adds a read-only "think first" mode. Put `/discuss` anywhere in a
prompt and that turn becomes conversation-only: Claude can read, search, and reason about
your code, but it cannot change any files.

Handy when you want to review a design, weigh options, or scope a change before Claude starts
editing.

## How it works

The plugin is just two hooks — no slash command and nothing to configure:

- A `UserPromptSubmit` hook detects the `/discuss` marker and adds a read-only instruction for
  that turn.
- A `PreToolUse` hook denies the file-mutating tools (`Write`, `Edit`, `MultiEdit`,
  `NotebookEdit`) while `/discuss` is in effect.

The read-only state is tied to the current session turn and clears itself on your next normal
prompt — nothing to toggle off.

## Install

```
/plugin marketplace add 0sha-dow0/claude-code-discuss-only-mode
/plugin install discuss-mode@discuss-mode-marketplace
/reload-plugins
```

## Use

Add `/discuss` inline — after some text, not at the very start (a leading `/` is read as a
slash command):

```
Walk me through the trade-offs of these two schemas /discuss
```

Claude discusses; any attempt to edit a file is refused for that turn. Your next prompt
without `/discuss` behaves normally.

## What it guards — and what it doesn't

Blocked during a `/discuss` turn: `Write`, `Edit`, `MultiEdit`, `NotebookEdit`.

Not blocked: read-only tools (`Read`, `Grep`, `Glob`), `Bash`, and MCP tools. This is an
intent guardrail for Claude's normal edit path, not a sandbox — a shell command could still
change files, which is deliberate so you keep read-only shell inspection.

Also note: a prompt that *starts* with `/discuss` won't trigger it (Claude treats a leading
`/` as a command), so place the marker after some text.

## Requirements

- Python 3.8+ available as `python3` or `python` on your PATH.
- `sh` on your PATH — always present on macOS/Linux; on Windows install
  [Git for Windows](https://git-scm.com/download/win).

## License

MIT
