from __future__ import annotations

import unittest
from datetime import UTC, timedelta, timezone

from secretary.timeutils import format_utc, parse_datetime_to_utc, parse_duration


class TimeUtilsTest(unittest.TestCase):
    def test_parse_z_timestamp(self) -> None:
        parsed = parse_datetime_to_utc(
            "2026-06-25T06:30:00Z",
            timezone(timedelta(hours=8)),
        )
        self.assertEqual(format_utc(parsed), "2026-06-25T06:30:00Z")
        self.assertIs(parsed.tzinfo, UTC)

    def test_parse_offset_timestamp(self) -> None:
        parsed = parse_datetime_to_utc(
            "2026-06-25T14:30:00+08:00",
            timezone(timedelta(hours=8)),
        )
        self.assertEqual(format_utc(parsed), "2026-06-25T06:30:00Z")

    def test_parse_naive_timestamp_with_default_timezone(self) -> None:
        parsed = parse_datetime_to_utc(
            "2026-06-25T14:30:00",
            timezone(timedelta(hours=8)),
        )
        self.assertEqual(format_utc(parsed), "2026-06-25T06:30:00Z")

    def test_parse_duration(self) -> None:
        self.assertEqual(parse_duration("10m"), timedelta(minutes=10))
        self.assertEqual(parse_duration("2h"), timedelta(hours=2))
        self.assertEqual(parse_duration("1d"), timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
