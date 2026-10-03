# Case B cart-discount contract

This is the complete requirement for `PHASE11_CASE_B_FRESH_ROOT`; paths are
repository-relative. Fixture root:
`tests/phase11-integrated-routing/fixtures/feature/`.

## Pre-feature scaffold (what is checked in now)

The checked-in standard-library-only scaffold has **not** implemented the
discount. In `domain.py`, the current result has only these two fields, in this
order:

```python
@dataclass(frozen=True)
class CartTotals:
    subtotal_cents: int
    total_cents: int
```

Current stable functions:

```python
calculate_cart(subtotal_cents: int, *, is_member: bool = False) -> CartTotals
calculate_total(subtotal_cents: int) -> int
```

`calculate_cart` currently validates subtotal and member input, then returns
subtotal unchanged as total. `calculate_total` is the legacy one-argument,
no-discount wrapper and returns subtotal unchanged, including at or above the
future threshold. Keep that signature and behavior after implementing the
feature. The pre-feature `presentation.py:render_totals(totals: CartTotals) ->
str` renders only subtotal and total, with no discount line.

For both the scaffold and feature API, `subtotal_cents` must be a built-in
integer (not a boolean or another numeric type); other types raise `TypeError`,
and a negative integer raises `ValueError`. `is_member` must be a boolean; any
other type raises `TypeError`.

## Required feature and material dependency

The feature must change **both** calculation (`domain.py`) and presentation
(`presentation.py`). The final result adds `discount_cents` **after the two
existing fields**, with a default, so existing two-argument construction remains
valid:

```python
@dataclass(frozen=True)
class CartTotals:
    subtotal_cents: int
    total_cents: int
    discount_cents: int = 0
```

The final field order is `subtotal_cents`, `total_cents`, `discount_cents`.
Use keyword arguments when constructing results with the new field; for example:
`CartTotals(subtotal_cents=10_001, total_cents=9_001, discount_cents=1_000)`.
The dependency is concrete: calculation first publishes the new
`discount_cents` value in `CartTotals`; `presentation.py:render_totals` then
consumes that field. Calculation exclusively owns membership eligibility,
discount, and total arithmetic. Presentation consumes supplied fields and never
recalculates. This small producer/consumer dependency needs no additional
architecture.

The function signatures remain:

```python
calculate_cart(subtotal_cents: int, *, is_member: bool = False) -> CartTotals
calculate_total(subtotal_cents: int) -> int
render_totals(totals: CartTotals) -> str
```

For valid inputs, apply exactly this rule:

- A guest receives discount `0`.
- A member with subtotal below 10,000 cents receives discount `0`.
- A member with subtotal at least 10,000 cents receives
  `subtotal_cents // 10` discount cents.
- `total_cents` is exactly `subtotal_cents - discount_cents`.
- `calculate_total(subtotal_cents)` stays the no-discount legacy API; it has no
  membership input and continues to return the subtotal unchanged.

After the field is added, presentation always renders subtotal and total and
renders `Discount: N cents` only when `discount_cents > 0`. Exact output lines
are `Subtotal: N cents`, `Discount: N cents`, and `Total: N cents`, joined by
`\n` with no trailing newline. Render integer cents directly; do not use
floating-point arithmetic, currency formatting, taxes, shipping, stacking, or
coupons.

## Required future acceptance tests

Before calling the feature done, **add and run** acceptance tests for every row
below and for all presentation cases. The current scaffold compatibility tests
are not feature acceptance tests.

| Input | Expected discount | Expected total |
| --- | ---: | ---: |
| guest, subtotal 12,000 cents | 0 | 12,000 |
| member, subtotal 9,999 cents (below threshold) | 0 | 9,999 |
| member, subtotal 10,000 cents (exact threshold) | 1,000 | 9,000 |
| member, subtotal 10,001 cents (above threshold) | 1,000 | 9,001 |
| any membership, subtotal -1 cent | raises `ValueError` | no result |

Use keyword arguments in presentation examples to make the field order clear:

- `CartTotals(subtotal_cents=12_000, total_cents=12_000, discount_cents=0)`
  renders exactly `Subtotal: 12000 cents\nTotal: 12000 cents`.
- `CartTotals(subtotal_cents=10_001, total_cents=9_001, discount_cents=1_000)`
  renders exactly
  `Subtotal: 10001 cents\nDiscount: 1000 cents\nTotal: 9001 cents`.
- The discriminating presentation-only result
  `CartTotals(subtotal_cents=12_345, total_cents=12_111, discount_cents=777)`
  renders exactly
  `Subtotal: 12345 cents\nDiscount: 777 cents\nTotal: 12111 cents`. This is a
  deliberately inconsistent synthetic rendering input: `777 != 12,345 // 10`
  (1,234), and `777 != 12,345 - 12,111` (234). Pass it directly to presentation
  and require the supplied `777` to be shown; presentation neither derives,
  validates, nor repairs these fields. It is **not** a valid result from
  `calculate_cart` or calculation acceptance data. Real calculation results
  must continue to obey the eligibility rule and exact total equation above.
  This test proves presentation has no discount calculation of its own.

The future acceptance tests must cover the result-field dependency by testing
the calculation output and presentation consumer, along with the legacy API.
No feature acceptance test is intentionally made pending/RED in this scaffold.
