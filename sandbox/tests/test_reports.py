from datetime import datetime, timedelta
import unittest
from zoneinfo import ZoneInfo

from sandbox.reports import ShiftWindow, shift_duration


class WorkedTimeReportTests(unittest.TestCase):
    def test_overnight_fallback_shift_counts_the_repeated_hour(self) -> None:
        los_angeles = ZoneInfo("America/Los_Angeles")
        overnight = ShiftWindow(
            started_at=datetime(2026, 11, 1, 0, 30, tzinfo=los_angeles),
            ended_at=datetime(2026, 11, 1, 8, 30, tzinfo=los_angeles),
        )

        elapsed = shift_duration(overnight)

        self.assertEqual(timedelta(hours=9), elapsed)


if __name__ == "__main__":
    unittest.main()
