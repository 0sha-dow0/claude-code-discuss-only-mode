#!/usr/bin/env python3
"""Hook helpers for the discuss-mode Claude Code plugin."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional


DISCUSS_MARKER_RE = re.compile(r"(?:^|\s)/discuss(?:\s|$)")
MARKER_TTL_SECONDS = 24 * 60 * 60
MUTATING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

GUIDANCE = (
    "The user used /discuss. This turn is brainstorm-only/read-only. Do not "
    "edit files, write files, apply patches, run codegen, formatters, "
    "migrations, or any command intended to change repo-tracked state. You may "
    "inspect, search, read files, run clearly non-mutating checks, and ask "
    "clarifying questions. If the user wants implementation, they can ask in a "
    "later turn without /discuss."
)

BLOCK_REASON = (
    "Blocked because this turn is in /discuss mode. The user wants "
    "brainstorming/read-only discussion only. Ask questions, inspect files, "
    "or propose a plan instead of modifying files."
)


def handle_user_prompt_submit(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    cleanup_old_markers()
    prompt = read_prompt(payload)
    if prompt is not None and is_discuss_prompt(prompt):
        write_marker(payload)
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": GUIDANCE,
            }
        }
    clear_marker(payload)
    return None


def handle_pre_tool_use(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    cleanup_old_markers()
    if not marker_exists(payload):
        return None
    if payload.get("tool_name") in MUTATING_TOOLS:
        return deny()
    return None


def read_prompt(payload: dict[str, Any]) -> Optional[str]:
    value = payload.get("user_prompt")
    if not isinstance(value, str):
        value = payload.get("prompt")
    return value if isinstance(value, str) else None


def is_discuss_prompt(prompt: str) -> bool:
    return DISCUSS_MARKER_RE.search(prompt) is not None


def deny() -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": BLOCK_REASON,
        }
    }


def write_marker(payload: dict[str, Any]) -> None:
    path = marker_path(payload)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        marker = {
            "session_id": session_id(payload),
            "created_at": int(time.time()),
        }
        path.write_text(json.dumps(marker, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def clear_marker(payload: dict[str, Any]) -> None:
    try:
        marker_path(payload).unlink()
    except OSError:
        pass


def marker_exists(payload: dict[str, Any]) -> bool:
    try:
        return marker_path(payload).is_file()
    except OSError:
        return False


def marker_path(payload: dict[str, Any]) -> Path:
    digest = hashlib.sha256(session_id(payload).encode("utf-8")).hexdigest()
    return state_dir() / f"{digest}.json"


def session_id(payload: dict[str, Any]) -> str:
    value = payload.get("session_id")
    return value if isinstance(value, str) and value else "_no_session_"


def state_dir() -> Path:
    explicit = os.environ.get("DISCUSS_MODE_STATE_DIR")
    if explicit:
        return Path(explicit)
    return Path(tempfile.gettempdir()) / "claude-discuss-mode" / "discuss-turns"


def cleanup_old_markers() -> None:
    root = state_dir()
    try:
        if not root.is_dir():
            return
        cutoff = time.time() - MARKER_TTL_SECONDS
        for path in root.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass
    except OSError:
        pass


def run_hook(handler: Callable[[dict[str, Any]], Optional[dict[str, Any]]]) -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        output = handler(payload)
        if output is not None:
            print(json.dumps(output, separators=(",", ":")))
    except Exception:
        return 0
    return 0
