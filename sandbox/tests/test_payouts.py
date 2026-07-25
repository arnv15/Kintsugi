from decimal import Decimal
import unittest

from sandbox.payouts import PayoutInstruction, split_evenly


class PayoutAllocationTests(unittest.TestCase):
    def test_three_recipient_distribution_preserves_the_entire_fund(self) -> None:
        instruction = PayoutInstruction(
            gross_amount="100.00",
            recipient_ids=("artist", "venue", "promoter"),
        )

        allocations = split_evenly(instruction)

        self.assertEqual(Decimal("100.00"), sum(allocations.values()))


if __name__ == "__main__":
    unittest.main()
