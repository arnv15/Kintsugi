import unittest

from inventory import last_n_orders


class LastNOrdersTests(unittest.TestCase):
    def test_keeps_the_most_recent_order(self) -> None:
        orders = ["order-1", "order-2", "order-3", "order-4"]

        self.assertEqual(["order-3", "order-4"], last_n_orders(orders, 2))


if __name__ == "__main__":
    unittest.main()
