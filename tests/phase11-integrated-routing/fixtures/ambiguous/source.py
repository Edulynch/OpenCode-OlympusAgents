"""Unresolved subtotal/shipping sample: intentionally left unrepaired.

Observed sample: subtotal=100, shipping=10, displayed total=110. Competing
hypotheses: (1) input/configuration already folded shipping into subtotal, so
the display adds it twice; (2) the domain contract says subtotal excludes
shipping, so 110 is correct and the upstream observation is misinterpreted.
The fixture supplies no discriminating provenance; do not pick a cause or patch.
"""


SAMPLE_INPUT = {"subtotal": 100, "shipping": 10}


def candidate_display_total(subtotal: int, shipping: int) -> int:
    """Candidate behavior only; the sample is evidence, not a proposed repair."""
    return subtotal + shipping


OBSERVED_DISPLAY_TOTAL = 110
