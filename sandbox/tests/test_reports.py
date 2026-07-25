from datetime import datetime
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

        elapsed_hours = shift_duration(overnight).total_seconds() / 3_600

        self.assertGreater(elapsed_hours, 8)


if __name__ == "__main__":
    unittest.main()
