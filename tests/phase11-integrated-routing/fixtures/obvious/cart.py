"""Disposable, intentionally defective functional-bug routing fixture."""


def calculate_total(price: int, quantity: int) -> int:
    """The contract is price multiplied by quantity; the defect is obvious."""
    return price - quantity
