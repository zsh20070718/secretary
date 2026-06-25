from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from secretary.config import load_dotenv


class ConfigTest(unittest.TestCase):
    def test_load_dotenv_preserves_inner_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("CODEX_TUI_COMMAND=bash -ic 'exec codex'\n", encoding="utf-8")
            old = os.environ.pop("CODEX_TUI_COMMAND", None)
            try:
                load_dotenv(path)
                self.assertEqual(
                    os.environ["CODEX_TUI_COMMAND"],
                    "bash -ic 'exec codex'",
                )
            finally:
                if old is None:
                    os.environ.pop("CODEX_TUI_COMMAND", None)
                else:
                    os.environ["CODEX_TUI_COMMAND"] = old


if __name__ == "__main__":
    unittest.main()

