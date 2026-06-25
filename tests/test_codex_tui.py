from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from secretary.codex_tui import (
    CodexTuiBridge,
    CodexTuiConfig,
    clean_terminal_text,
    extract_delta_capture,
)


class CodexTuiTest(unittest.TestCase):
    def test_clean_terminal_text_removes_ansi_and_controls(self) -> None:
        raw = "\x1b[31mhello\x1b[0m\x07\nworld   \n"
        self.assertEqual(clean_terminal_text(raw), "hello\nworld")

    def test_extract_delta_capture_returns_only_new_output(self) -> None:
        before = "old answer\n\n  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        after = (
            before
            + "\n\n"
            + "\u203a [Feishu secretary bridge] owner_id=ou_test; User message: ping\n\n"
            + "DELTA_OK"
        )

        self.assertEqual(
            extract_delta_capture(
                before,
                after,
                submitted_text="[Feishu secretary bridge] owner_id=ou_test; User message: ping",
            ),
                "DELTA_OK",
        )

    def test_extract_delta_capture_ignores_prompt_echo_without_answer(self) -> None:
        before = "old answer\n\n  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        after = (
            before
            + "\n\n"
            + "\u203a [Feishu secretary bridge] owner_id=ou_test; User message: ping\n\n"
            + "\u203a Write tests for @filename\n"
            + "  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        )

        self.assertEqual(extract_delta_capture(before, after), "")

    def test_extract_delta_capture_removes_trailing_prompt_suggestion(self) -> None:
        before = "old answer\n\n  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        after = (
            before
            + "\n\n"
            + "\u203a [Feishu secretary bridge] owner_id=ou_test; User message: ping\n\n"
            + "new answer\n\n"
            + "\u203a Write tests for @filename\n"
            + "  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        )

        self.assertEqual(extract_delta_capture(before, after), "new answer")

    def test_extract_delta_capture_does_not_anchor_on_repeated_prompt_suggestion(self) -> None:
        before = (
            "old answer\n\n"
            "\u203a Write tests for @filename\n"
            "  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        )
        after = (
            "old answer\n\n"
            "\u203a Reply exactly DELTA_FIX_OK\n\n"
            "DELTA_FIX_OK\n\n"
            "\u203a Write tests for @filename\n"
            "  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        )

        self.assertEqual(
            extract_delta_capture(
                before,
                after,
                submitted_text="Reply exactly DELTA_FIX_OK",
            ),
            "DELTA_FIX_OK",
        )

    def test_extract_delta_capture_handles_scrolled_tmux_capture(self) -> None:
        before = "\n".join(f"line {i}" for i in range(1, 7))
        after = "\n".join(
            [
                "line 4",
                "line 5",
                "line 6",
                "\u203a [Feishu secretary bridge] owner_id=ou_test; User message: ping",
                "",
                "new answer",
            ]
        )

        self.assertEqual(extract_delta_capture(before, after), "new answer")

    def test_extract_delta_capture_ignores_stable_footer(self) -> None:
        before = "old answer\n  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        after = (
            "old answer\n"
            "\u203a [Feishu secretary bridge] owner_id=ou_test; User message: ping\n"
            "new answer\n"
            "  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        )

        self.assertEqual(extract_delta_capture(before, after), "new answer")

    def test_extract_delta_capture_falls_back_when_no_overlap_exists(self) -> None:
        self.assertEqual(extract_delta_capture("unrelated", "fresh answer"), "fresh answer")

    def test_wait_for_response_does_not_return_prompt_echo(self) -> None:
        before = "old answer\n  gpt-5.5 xhigh \u00b7 ~/secretary/codex-workspace"
        prompt_only = (
            before
            + "\n\n"
            + "\u203a [Feishu secretary bridge] owner_id=ou_test; User message: ping\n"
            + "\u203a Write tests for @filename"
        )
        answered = prompt_only + "\n\nnew answer"
        bridge = _FakeCaptureBridge([prompt_only, prompt_only, answered, answered])

        with patch("secretary.codex_tui.time.sleep", lambda _: None):
            self.assertEqual(bridge._wait_for_response(before, "ping"), answered)

    def test_ensure_persona_file_writes_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = CodexTuiBridge(
                CodexTuiConfig(
                    command="codex",
                    workdir=Path(tmp),
                    session="test-session",
                    capture_lines=20,
                    response_timeout_seconds=1,
                    stable_seconds=1,
                    max_reply_chars=1000,
                )
            )
            bridge.ensure_persona_file()
            content = (Path(tmp) / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("long-running Codex secretary", content)
            self.assertIn("Feishu bot bridge", content)


class _FakeCaptureBridge(CodexTuiBridge):
    def __init__(self, captures: list[str]):
        super().__init__(
            CodexTuiConfig(
                command="codex",
                workdir=Path("."),
                session="test-session",
                capture_lines=20,
                response_timeout_seconds=2,
                stable_seconds=0,
                max_reply_chars=1000,
            )
        )
        self._captures = captures

    def capture(self) -> str:
        if len(self._captures) > 1:
            return self._captures.pop(0)
        return self._captures[0]


if __name__ == "__main__":
    unittest.main()
