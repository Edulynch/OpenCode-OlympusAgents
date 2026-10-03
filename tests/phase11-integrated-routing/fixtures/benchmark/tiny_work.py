"""Tiny deterministic callable reserved for future explicit measurement."""


def square_sum(limit: int) -> int:
    """Return the sum of squares in [0, limit); no I/O or mutable state."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    return sum(value * value for value in range(limit))
