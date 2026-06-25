from __future__ import annotations

import unittest
from dataclasses import dataclass

from secretary.commands.codex import _with_bridge_context


@dataclass
class FakeContext:
    owner_id: str = "ou_test"


class CodexCommandTest(unittest.TestCase):
    def test_bridge_context_wraps_message(self) -> None:
        wrapped = _with_bridge_context(FakeContext(), "hello")
        self.assertIn("owner_id=ou_test", wrapped)
        self.assertIn("long-running Codex secretary", wrapped)
        self.assertIn("User message: hello", wrapped)


if __name__ == "__main__":
    unittest.main()
