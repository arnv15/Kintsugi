"""Recipient payout allocation."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PayoutInstruction:
    gross_amount: str
    recipient_ids: tuple[str, ...]


def split_evenly(instruction: PayoutInstruction) -> dict[str, Decimal]:
    """Allocate every cent of a payout across its recipients."""
    if not instruction.recipient_ids:
        raise ValueError("at least one recipient is required")

    share = round(float(instruction.gross_amount) / len(instruction.recipient_ids), 2)
    return {
        recipient_id: Decimal(str(share))
        for recipient_id in instruction.recipient_ids
    }
