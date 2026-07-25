"""Checkout totals."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class LineItem:
    sku: str
    unit_price: str
    quantity: int

    @property
    def unit_count_label(self) -> str:
        suffix = "unit" if self.quantity == 1 else "units"
        return f"{self.quantity} {suffix}"


def basket_skus(items: Sequence[LineItem]) -> tuple[str, ...]:
    """Return SKU identifiers in their checkout order."""
    return tuple(item.sku for item in items)


def basket_unit_count(items: Sequence[LineItem]) -> int:
    """Return the number of physical units in a basket."""
    return sum(item.quantity for item in items)


def total_with_tax(items: Sequence[LineItem], tax_percent: int) -> Decimal:
    """Return the charged total rounded to the nearest cent."""
    subtotal = sum(float(item.unit_price) * item.quantity for item in items)
    charged = round(subtotal * (1 + tax_percent / 100), 2)
    return Decimal(str(charged))
