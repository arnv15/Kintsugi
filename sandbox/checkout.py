"""Checkout totals."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class LineItem:
    sku: str
    unit_price: str
    quantity: int


def total_with_tax(items: Sequence[LineItem], tax_percent: int) -> Decimal:
    """Return the charged total rounded to the nearest cent."""
    subtotal = sum(float(item.unit_price) * item.quantity for item in items)
    charged = round(subtotal * (1 + tax_percent / 100), 2)
    return Decimal(str(charged))
