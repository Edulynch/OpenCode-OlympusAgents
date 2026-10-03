"""Calculation scaffold for the Phase 11 Case B cart feature."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CartTotals:
    """Pre-feature calculation output in integer cents."""

    subtotal_cents: int
    total_cents: int


def _validate_subtotal(subtotal_cents: int) -> None:
    if type(subtotal_cents) is not int:
        raise TypeError("subtotal_cents must be a built-in integer")
    if subtotal_cents < 0:
        raise ValueError("subtotal_cents cannot be negative")


def calculate_cart(subtotal_cents: int, *, is_member: bool = False) -> CartTotals:
    """Return the pre-feature no-discount scaffold result.

    Membership is part of the stable future API, but discount eligibility,
    discount arithmetic, and the future result field are not implemented yet.
    """
    _validate_subtotal(subtotal_cents)
    if type(is_member) is not bool:
        raise TypeError("is_member must be a boolean")
    return CartTotals(
        subtotal_cents=subtotal_cents,
        total_cents=subtotal_cents,
    )


def calculate_total(subtotal_cents: int) -> int:
    """Preserve the legacy, no-discount checkout API."""
    return calculate_cart(subtotal_cents).total_cents
