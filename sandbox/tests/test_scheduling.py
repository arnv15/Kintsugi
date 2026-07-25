from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from sandbox.scheduling import next_run_at


class RecurringScheduleTests(unittest.TestCase):
    def test_daily_run_keeps_its_local_appointment_after_spring_forward(self) -> None:
        los_angeles = ZoneInfo("America/Los_Angeles")
        saturday_run = datetime(2026, 3, 7, 9, 30, tzinfo=los_angeles)

        sunday_run = next_run_at(saturday_run)

        self.assertEqual(
            datetime(2026, 3, 8, 9, 30, tzinfo=los_angeles),
            sunday_run,
        )


if __name__ == "__main__":
    unittest.main()
