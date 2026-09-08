"""Whether the recommendation survives what we don't know.

The tool refuses to guess, and prices the unknowns it refuses to guess about.
This is the part that says whether the answer actually depends on them — and
on the hand-verified data, it often does.

Louisiana beats New Mexico by $5,349 on a $2M budget, and that margin holds in
only 375 of 625 combinations of the inputs nobody has verified. Three separate
things flip it. A recommendation with a margin smaller than its own uncertainty
is worth stating differently from one that holds everywhere, and until this
existed the two rendered identically.
"""

import pytest

from app.models import CreditTimingAssumptions
from app.robustness import SAMPLES, analyse_robustness
from app.seed_jurisdictions import GEORGIA, LOUISIANA, NEW_MEXICO

from .fixtures import make_budget, make_rule
from .test_seed_jurisdictions import INDIE_DRAMA_BUDGET, REAL_DISTANCES_KM


def analyse(winner, runner_up, budget=None, **kw):
    return analyse_robustness(
        budget or INDIE_DRAMA_BUDGET, winner, runner_up, distances=REAL_DISTANCES_KM, **kw
    )


# ---------- the finding this exists to produce ----------


def test_a_narrow_margin_is_reported_as_fragile():
    """Louisiana's win over New Mexico is smaller than its own uncertainty.

    $5,349 on a $2M budget, holding in 375 of 625 combinations. Presenting
    that with the same confidence as a $76,739 margin would be the most
    misleading thing this tool could do, because both look identical as a
    single number.
    """
    r = analyse(LOUISIANA, NEW_MEXICO)

    assert r.is_robust is False
    assert r.winner_holds_in < r.combinations_tested
    assert r.margin == pytest.approx(5_349, abs=5)


def test_a_wide_margin_holds_everywhere():
    r = analyse(LOUISIANA, GEORGIA)
    assert r.is_robust is True
    assert r.winner_holds_in == r.combinations_tested


def test_it_names_what_would_change_the_answer_and_at_what_value():
    """A threshold is actionable; a probability is not.

    "Flips if local hire rises above 62%, and you assumed 55%" is something a
    producer can go and confirm before committing.
    """
    r = analyse(LOUISIANA, NEW_MEXICO)
    names = {f.input_name for f in r.flips}

    assert "Local hire" in names
    flip = next(f for f in r.flips if f.input_name == "Local hire")
    assert "%" in flip.threshold
    assert flip.new_winner == "New Mexico"
    assert flip.because  # why it's uncertain, not just that it is


def test_a_robust_ranking_names_no_flips_at_all():
    assert analyse(LOUISIANA, GEORGIA).flips == []


# ---------- only sweeping what is genuinely uncertain here ----------


def test_the_credit_sale_price_is_swept_only_when_something_is_sold():
    """Sweeping it against two refundable credits would pad the count with
    combinations that differ in nothing, inflating a confidence statement."""
    refundable_pair = analyse(
        make_rule(jurisdiction="A", base_rate=0.30, minimum_spend=None, credit_type="refundable"),
        make_rule(jurisdiction="B", base_rate=0.25, minimum_spend=None, credit_type="refundable"),
    )
    assert "Credit sale price" not in {i.name for i in refundable_pair.inputs_swept}

    with_transferable = analyse(
        make_rule(jurisdiction="A", base_rate=0.30, minimum_spend=None, credit_type="transferable"),
        make_rule(jurisdiction="B", base_rate=0.25, minimum_spend=None, credit_type="refundable"),
    )
    assert "Credit sale price" in {i.name for i in with_transferable.inputs_swept}


def test_fringes_are_swept_only_where_a_statute_left_them_open():
    settled = analyse(
        make_rule(jurisdiction="A", base_rate=0.30, minimum_spend=None, fringes_qualify=True),
        make_rule(jurisdiction="B", base_rate=0.25, minimum_spend=None, fringes_qualify=False),
    )
    assert "Fringe rate" not in {i.name for i in settled.inputs_swept}


def test_local_hire_is_always_swept_because_the_user_invented_it():
    # Every other input has a source somewhere. This one is the producer's own
    # estimate, and it drives how much labour qualifies at all.
    r = analyse(LOUISIANA, NEW_MEXICO)
    assert "Local hire" in {i.name for i in r.inputs_swept}
    assert "estimated" in next(i for i in r.inputs_swept if i.name == "Local hire").because


def test_the_grid_is_every_combination_of_what_was_swept():
    r = analyse(LOUISIANA, NEW_MEXICO)
    assert r.combinations_tested == SAMPLES ** len(r.inputs_swept)


# ---------- refusing to say something meaningless ----------


def test_two_jurisdictions_in_the_wrong_order_produce_nothing():
    # There is no margin to defend, so any statement about robustness would
    # be about a comparison that doesn't exist.
    assert analyse(GEORGIA, LOUISIANA) is None


def test_every_swept_input_states_why_it_is_uncertain():
    for spec in analyse(LOUISIANA, NEW_MEXICO).inputs_swept:
        assert spec.because, spec.name
        assert spec.assumed, spec.name


def test_a_sourced_payment_timeline_removes_the_cost_of_capital_sweep():
    """If both timelines were read rather than assumed, what the wait costs
    is no longer one of the things we're guessing at."""
    sourced = analyse(
        make_rule(jurisdiction="A", base_rate=0.30, minimum_spend=None,
                  fringes_qualify=True, months_to_payment=6),
        make_rule(jurisdiction="B", base_rate=0.25, minimum_spend=None,
                  fringes_qualify=True, months_to_payment=9),
    )
    assert "Cost of capital" not in {i.name for i in sourced.inputs_swept}


def test_a_custom_timing_assumption_is_respected_as_the_centre_of_the_sweep():
    patient = CreditTimingAssumptions(discount_rate_annual=0.04)
    r = analyse(LOUISIANA, NEW_MEXICO, timing=patient)
    spec = next((i for i in r.inputs_swept if i.name == "Cost of capital"), None)
    assert spec is not None and spec.assumed == "4%/yr"
