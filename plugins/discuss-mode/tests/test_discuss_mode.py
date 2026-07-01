#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from discuss_mode import BLOCK_REASON  # noqa: E402
from discuss_mode import GUIDANCE  # noqa: E402
from discuss_mode import handle_pre_tool_use  # noqa: E402
from discuss_mode import handle_user_prompt_submit  # noqa: E402
from discuss_mode import is_discuss_prompt  # noqa: E402
from discuss_mode import run_hook  # noqa: E402


class DiscussModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.previous_state_dir = os.environ.get("DISCUSS_MODE_STATE_DIR")
        os.environ["DISCUSS_MODE_STATE_DIR"] = self.temp_dir.name

    def tearDown(self) -> None:
        if self.previous_state_dir is None:
            os.environ.pop("DISCUSS_MODE_STATE_DIR", None)
        else:
            os.environ["DISCUSS_MODE_STATE_DIR"] = self.previous_state_dir

    # --- marker detection ---------------------------------------------------

    def test_discuss_injects_guidance(self) -> None:
        output = handle_user_prompt_submit(user_prompt("review this /discuss please"))
        self.assertEqual(output, guidance_output())

    def test_discuss_at_start_of_prompt(self) -> None:
        self.assertEqual(
            handle_user_prompt_submit(user_prompt("/discuss review this")),
            guidance_output(),
        )

    def test_discuss_at_end_of_prompt(self) -> None:
        self.assertEqual(
            handle_user_prompt_submit(user_prompt("review this /discuss")),
            guidance_output(),
        )

    def test_discuss_surrounded_by_newlines(self) -> None:
        self.assertEqual(
            handle_user_prompt_submit(user_prompt("line one\n/discuss\nline two")),
            guidance_output(),
        )

    def test_discuss_tab_separated(self) -> None:
        self.assertEqual(
            handle_user_prompt_submit(user_prompt("review\t/discuss\tthis")),
            guidance_output(),
        )

    def test_marker_does_not_match_larger_token(self) -> None:
        self.assertIsNone(handle_user_prompt_submit(user_prompt("review /discussion please")))

    def test_marker_requires_whitespace_boundary_before(self) -> None:
        self.assertIsNone(handle_user_prompt_submit(user_prompt("path/discuss please")))

    def test_marker_is_case_sensitive(self) -> None:
        self.assertIsNone(handle_user_prompt_submit(user_prompt("review /Discuss please")))

    def test_regular_prompt_does_not_inject_guidance(self) -> None:
        self.assertIsNone(handle_user_prompt_submit(user_prompt("review this")))

    def test_is_discuss_prompt_unit(self) -> None:
        self.assertTrue(is_discuss_prompt("/discuss"))
        self.assertTrue(is_discuss_prompt("a /discuss b"))
        self.assertFalse(is_discuss_prompt("/discussion"))
        self.assertFalse(is_discuss_prompt("undiscuss"))
        self.assertFalse(is_discuss_prompt(""))

    # --- blocking behaviour -------------------------------------------------

    def test_discuss_blocks_every_mutating_tool(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss review this"))
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.assertEqual(handle_pre_tool_use(pre_tool_use(tool)), deny_output())

    def test_discuss_allows_read_and_shell_tools(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss review this"))
        for tool in ("Bash", "Read", "Grep", "Glob", "WebFetch", "Task"):
            with self.subTest(tool=tool):
                self.assertIsNone(handle_pre_tool_use(pre_tool_use(tool)))

    def test_no_block_without_discuss(self) -> None:
        handle_user_prompt_submit(user_prompt("please just edit the file"))
        self.assertIsNone(handle_pre_tool_use(pre_tool_use("Edit")))

    def test_block_persists_across_multiple_tools_in_same_turn(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss look at this"))
        self.assertEqual(handle_pre_tool_use(pre_tool_use("Read")), None)
        self.assertEqual(handle_pre_tool_use(pre_tool_use("Edit")), deny_output())
        self.assertEqual(handle_pre_tool_use(pre_tool_use("Write")), deny_output())

    def test_next_non_discuss_prompt_clears_the_block(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss review this"))
        blocked = handle_pre_tool_use(pre_tool_use("Edit"))
        handle_user_prompt_submit(user_prompt("now implement it"))
        allowed = handle_pre_tool_use(pre_tool_use("Edit"))
        self.assertEqual(blocked, deny_output())
        self.assertIsNone(allowed)

    def test_second_discuss_turn_reactivates_block(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss one"))
        handle_user_prompt_submit(user_prompt("go implement"))
        handle_user_prompt_submit(user_prompt("/discuss two"))
        self.assertEqual(handle_pre_tool_use(pre_tool_use("Edit")), deny_output())

    def test_sessions_are_isolated(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss review", session="A"))
        self.assertEqual(handle_pre_tool_use(pre_tool_use("Edit", session="A")), deny_output())
        self.assertIsNone(handle_pre_tool_use(pre_tool_use("Edit", session="B")))

    def test_pretooluse_does_not_need_prompt_id(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss review this", session="S"))
        payload = {
            "session_id": "S",
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {},
        }
        self.assertEqual(handle_pre_tool_use(payload), deny_output())

    # --- robustness / no-crash ---------------------------------------------

    def test_missing_prompt_field(self) -> None:
        self.assertIsNone(handle_user_prompt_submit({"session_id": "s"}))

    def test_non_string_prompt(self) -> None:
        self.assertIsNone(handle_user_prompt_submit({"session_id": "s", "user_prompt": 123}))

    def test_missing_tool_name(self) -> None:
        handle_user_prompt_submit(user_prompt("/discuss review"))
        self.assertIsNone(handle_pre_tool_use({"session_id": "session-1"}))

    def test_missing_session_id_is_handled(self) -> None:
        self.assertEqual(
            handle_user_prompt_submit({"user_prompt": "/discuss hi"}),
            guidance_output(),
        )
        self.assertEqual(
            handle_pre_tool_use({"tool_name": "Edit"}),
            deny_output(),
        )

    def test_legacy_prompt_and_turn_fields_still_read(self) -> None:
        self.assertEqual(
            handle_user_prompt_submit({"session_id": "s", "prompt": "/discuss hi"}),
            guidance_output(),
        )

    def test_run_hook_on_empty_stdin_does_not_crash(self) -> None:
        code, out = capture_run_hook(handle_pre_tool_use, "")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_run_hook_on_malformed_json_does_not_crash(self) -> None:
        code, out = capture_run_hook(handle_pre_tool_use, "{not json")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_run_hook_on_non_object_json_does_not_crash(self) -> None:
        code, out = capture_run_hook(handle_user_prompt_submit, "[1, 2, 3]")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_run_hook_emits_compact_json(self) -> None:
        payload = json.dumps(user_prompt("/discuss hi"))
        code, out = capture_run_hook(handle_user_prompt_submit, payload)
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed, guidance_output())
        self.assertNotIn(" ", out.split("additionalContext")[0])


def user_prompt(prompt: str, *, session: str = "session-1") -> dict[str, object]:
    return {
        "session_id": session,
        "prompt_id": "turn-1",
        "hook_event_name": "UserPromptSubmit",
        "user_prompt": prompt,
    }


def pre_tool_use(tool_name: str, *, session: str = "session-1") -> dict[str, object]:
    return {
        "session_id": session,
        "prompt_id": "turn-1",
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {},
        "tool_use_id": "tool-1",
    }


def guidance_output() -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": GUIDANCE,
        }
    }


def deny_output() -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": BLOCK_REASON,
        }
    }


def capture_run_hook(handler, stdin_text: str) -> tuple[int, str]:
    previous_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_text)
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            code = run_hook(handler)
    finally:
        sys.stdin = previous_stdin
    return code, buffer.getvalue().strip()


if __name__ == "__main__":
    unittest.main()
