from __future__ import annotations

import unittest

from secretary.message import parse_text_content, strip_bot_mention


class MessageTest(unittest.TestCase):
    def test_parse_feishu_text_content(self) -> None:
        self.assertEqual(
            parse_text_content('{"text": "/help"}'),
            "/help",
        )

    def test_parse_plain_text_content(self) -> None:
        self.assertEqual(parse_text_content("/help"), "/help")

    def test_strip_bot_mention(self) -> None:
        text = '<at user_id="ou_xxx">秘书</at> /help'
        self.assertEqual(strip_bot_mention(text), "/help")


if __name__ == "__main__":
    unittest.main()

