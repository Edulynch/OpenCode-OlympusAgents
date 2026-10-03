"""Expected contract test for the intentionally incorrect cart fixture.

Do not run this expecting a pass before a future live qualification repairs the
fixture in a disposable copy. The offline Phase 11 suite deliberately excludes
this test.
"""

from cart import calculate_total


def test_total_is_price_times_quantity() -> None:
    assert calculate_total(12, 7) == 12 * 7
