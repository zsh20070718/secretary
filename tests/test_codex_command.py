from __future__ import annotations

import unittest
from dataclasses import dataclass
from threading import Event

from secretary.commands import codex as codex_command
from secretary.commands.codex import WORKING_REPLY, _send_to_codex, _with_bridge_context


@dataclass
class FakeContext:
    owner_id: str = "ou_test"
    receive_id_type: str = "open_id"
    receive_id: str = "ou_test"
    settings: object | None = None
    feishu: object | None = None


class CodexCommandTest(unittest.TestCase):
    def test_bridge_context_wraps_message(self) -> None:
        wrapped = _with_bridge_context(FakeContext(), "hello")
        self.assertIn("owner_id=ou_test", wrapped)
        self.assertIn("long-running Codex secretary", wrapped)
        self.assertIn("User message: hello", wrapped)

    def test_send_to_codex_returns_working_then_sends_final_reply(self) -> None:
        done = Event()
        feishu = FakeFeishu(done)
        ctx = FakeContext(settings=FakeSettings(), feishu=feishu)

        original_bridge = codex_command._bridge
        codex_command._bridge = lambda _: FakeBridge("done")
        try:
            self.assertEqual(_send_to_codex(ctx, "hello"), WORKING_REPLY)
            self.assertTrue(done.wait(1))
            self.assertEqual(feishu.sent, [("open_id", "ou_test", "done")])
        finally:
            codex_command._bridge = original_bridge

    def test_send_to_codex_returns_working_when_previous_task_is_busy(self) -> None:
        ctx = FakeContext(settings=FakeSettings(), feishu=FakeFeishu(Event()))
        self.assertTrue(codex_command._CODEX_TASK_LOCK.acquire(blocking=False))
        try:
            self.assertEqual(_send_to_codex(ctx, "hello"), WORKING_REPLY)
            self.assertEqual(ctx.feishu.sent, [])
        finally:
            codex_command._CODEX_TASK_LOCK.release()


@dataclass
class FakeSettings:
    allowed_open_ids: frozenset[str] = frozenset({"ou_test"})


class FakeBridge:
    def __init__(self, reply: str):
        self.reply = reply

    def send_message_and_capture(self, message: str) -> str:
        return self.reply


class FakeFeishu:
    def __init__(self, done: Event):
        self.done = done
        self.sent: list[tuple[str, str, str]] = []

    def send_text(self, receive_id_type: str, receive_id: str, text: str) -> None:
        self.sent.append((receive_id_type, receive_id, text))
        self.done.set()


if __name__ == "__main__":
    unittest.main()
