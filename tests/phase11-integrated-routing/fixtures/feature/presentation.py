"""Rendering-only boundary for precomputed cart totals."""

from .domain import CartTotals


def render_totals(totals: CartTotals) -> str:
    """Render the current pre-feature subtotal and total only."""
    return (
        f"Subtotal: {totals.subtotal_cents} cents\n"
        f"Total: {totals.total_cents} cents"
    )
