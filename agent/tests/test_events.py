from __future__ import annotations

import unittest

from kintsugi_agent.events import InvalidEvent, validate_event


class EventSchemaTests(unittest.TestCase):
    def test_strategy_event_without_citations_is_invalid(self) -> None:
        with self.assertRaises(InvalidEvent):
            validate_event(
                {
                    "ts": "2026-07-25T20:00:00.000Z",
                    "run_id": "run-1",
                    "seq": 2,
                    "type": "strategy_recorded",
                    "text": "Apply a correction.",
                    "sources": [],
                }
            )

    def test_event_fields_must_have_the_schema_types(self) -> None:
        with self.assertRaises(InvalidEvent):
            validate_event(
                {
                    "ts": "2026-07-25T20:00:00.000Z",
                    "run_id": "run-1",
                    "seq": "first",
                    "type": "tests_run",
                    "passed": "one",
                    "failed": 0,
                    "output_tail": "OK",
                }
            )


if __name__ == "__main__":
    unittest.main()
