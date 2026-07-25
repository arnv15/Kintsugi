from decimal import Decimal
import unittest

from sandbox.checkout import LineItem, total_with_tax


class CheckoutTotalTests(unittest.TestCase):
    def test_half_cent_tax_rounds_up_on_the_customer_charge(self) -> None:
        basket = [
            LineItem(sku="washer", unit_price="0.01", quantity=1),
            LineItem(sku="fastener", unit_price="0.09", quantity=1),
        ]

        amount_charged = total_with_tax(basket, tax_percent=5)

        self.assertEqual(Decimal("0.11"), amount_charged)


if __name__ == "__main__":
    unittest.main()
