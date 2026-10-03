"""Green compatibility checks for the Case B pre-feature scaffold only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


FEATURE_ROOT = Path(__file__).resolve().parent
CASE_ROOT = FEATURE_ROOT.parents[1]
if str(CASE_ROOT) not in sys.path:
    sys.path.insert(0, str(CASE_ROOT))

from fixtures.feature.domain import CartTotals, calculate_cart, calculate_total
from fixtures.feature.presentation import render_totals


class ScaffoldCompatibilityTests(unittest.TestCase):
    def test_legacy_checkout_above_discount_threshold_remains_no_discount(self) -> None:
        self.assertEqual(12000, calculate_total(12000))
        self.assertEqual(CartTotals(subtotal_cents=12000, total_cents=12000), calculate_cart(12000))

    def test_below_threshold_and_negative_subtotals(self) -> None:
        self.assertEqual(
            CartTotals(subtotal_cents=9999, total_cents=9999),
            calculate_cart(9999, is_member=True),
        )
        with self.assertRaises(ValueError):
            calculate_cart(-1)

    def test_invalid_member_type_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            calculate_cart(9999, is_member="member")

    def test_presentation_renders_only_current_fields(self) -> None:
        no_discount = CartTotals(subtotal_cents=12000, total_cents=12000)
        self.assertEqual(
            "Subtotal: 12000 cents\nTotal: 12000 cents",
            render_totals(no_discount),
        )


if __name__ == "__main__":
    unittest.main()
