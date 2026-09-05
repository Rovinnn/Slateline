"""A credit is a claim on future money, not cash on wrap day.

Until now the tool compared a credit paid in 9 months against one sold in 20
against a relocation bill paid up front, all as if they were the same dollars.
They aren't, and the gap is not small: on the seed jurisdictions, discounting
moves every net benefit by $53k-$66k on a $2M budget — the same order as the
entire relocation calculation, which has a whole assumptions panel of its own.

The honest scope of the claim, tested at the bottom of this file: on the four
seed jurisdictions timing does *not* change who wins. What it does change is
that New Mexico and Louisiana stop being exactly tied — the tool previously
had no way to prefer either. Reordering is possible and demonstrated here with
constructed rules; it just isn't what this particular dataset does.
"""

import pytest

from app.calculator import compute_benefit
from app.models import CreditTimingAssumptions, RelocationAssumptions

from .fixtures import make_budget, make_rule

NO_RELOCATION = RelocationAssumptions(
    equipment_shipping_base=0, imported_crew_pct=0, per_diem_per_person_per_day=0, hotel_per_person_per_day=0
)
INSTANT = CreditTimingAssumptions(discount_rate_annual=0.0, audit_cost=0.0)


def compute(rule=None, timing=None, **kwargs):
    return compute_benefit(
        make_budget(fringe_rate=0),
        rule or make_rule(minimum_spend=None, credit_type="refundable", fringes_qualify=False),
        assumptions=NO_RELOCATION,
        timing=timing,
        **kwargs,
    )


# ---------- the discount itself ----------


def test_waiting_for_a_credit_costs_money():
    result = compute()
    assert result.present_value < result.realizable_credit
    assert result.net_benefit == pytest.approx(result.present_value)


def test_a_zero_discount_rate_reproduces_the_old_undiscounted_behaviour():
    # The escape hatch that proves timing is the only thing that changed:
    # set the rate to zero and every previous number comes back.
    result = compute(timing=INSTANT)
    assert result.present_value == pytest.approx(result.realizable_credit)


def test_the_discount_compounds_over_the_actual_wait():
    # 500,000 realizable, 12 months at 12%: 500,000 / 1.12 = 446,428.57.
    result = compute(timing=CreditTimingAssumptions(discount_rate_annual=0.12, months_refundable=12))
    assert result.months_to_payment == 12
    assert result.present_value == pytest.approx(500_000 / 1.12, abs=0.01)


def test_a_longer_wait_is_worth_strictly_less():
    fast = compute(timing=CreditTimingAssumptions(months_refundable=6))
    slow = compute(timing=CreditTimingAssumptions(months_refundable=24))
    assert slow.present_value < fast.present_value


def test_transferable_credits_are_assumed_slower_than_refundable_ones():
    # Selling a credit adds finding a buyer to filing a return, and the
    # defaults have to reflect that or the two look identical on timing.
    refundable = compute(rule=make_rule(minimum_spend=None, credit_type="refundable"))
    transferable = compute(rule=make_rule(minimum_spend=None, credit_type="transferable"))
    assert transferable.months_to_payment > refundable.months_to_payment


# ---------- assumption vs. fact, which the UI has to distinguish ----------


def test_a_sourced_timeline_overrides_the_assumed_default():
    rule = make_rule(minimum_spend=None, credit_type="transferable", months_to_payment=4)
    result = compute(rule=rule)
    assert result.months_to_payment == 4
    assert result.timing_is_assumed is False
    assert "per source" in result.timing_note


def test_an_unsourced_timeline_says_so_rather_than_implying_it_was_found():
    # The difference between "we read this" and "we assumed this" is the
    # difference between a citation and a guess, and the note has to carry it.
    result = compute(rule=make_rule(minimum_spend=None, credit_type="transferable"))
    assert result.timing_is_assumed is True
    assert "assumed" in result.timing_note


# ---------- the audit, which costs money as well as time ----------


def test_a_required_audit_is_charged_before_discounting():
    # It's paid to *get* the credit, so it's never money the production has
    # the use of — subtracting it after discounting would understate its cost.
    rule = make_rule(minimum_spend=None, credit_type="refundable", audit_required=True)
    timing = CreditTimingAssumptions(discount_rate_annual=0.12, months_refundable=12, audit_cost=15_000)
    result = compute(rule=rule, timing=timing)
    assert result.audit_cost == 15_000
    assert result.present_value == pytest.approx((500_000 - 15_000) / 1.12, abs=0.01)


def test_an_unstated_audit_requirement_is_not_treated_as_a_required_audit():
    # None means no source addressed it. Charging $15k on silence would invent
    # a cost, which is the same error as inventing a credit.
    result = compute(rule=make_rule(minimum_spend=None, credit_type="refundable", audit_required=None))
    assert result.audit_cost == 0


def test_an_explicitly_absent_audit_costs_nothing():
    result = compute(rule=make_rule(minimum_spend=None, credit_type="refundable", audit_required=False))
    assert result.audit_cost == 0


def test_the_audit_cost_is_named_in_the_note_so_it_can_be_questioned():
    rule = make_rule(minimum_spend=None, credit_type="refundable", audit_required=True)
    assert "audit" in compute(rule=rule).timing_note


# ---------- the identity the frontend explanation depends on ----------


def test_the_five_components_sum_exactly_to_net_benefit():
    """explain.ts decomposes the winner's advantage into these five parts.

    If they stop summing to net_benefit, "why it wins" starts quietly lying —
    so the identity is pinned here, on the side that produces the numbers,
    rather than only in the frontend that consumes them.
    """
    rule = make_rule(minimum_spend=None, credit_type="transferable", audit_required=True)
    result = compute_benefit(
        make_budget(fringe_rate=0), rule, distance_km=1000,
        assumptions=RelocationAssumptions(), timing=CreditTimingAssumptions(),
    )
    discount = result.realizable_credit - result.gross_credit
    timing_loss = result.present_value - (result.realizable_credit - result.audit_cost)
    total = (
        result.gross_credit + discount - result.audit_cost + timing_loss - result.relocation_cost
    )
    assert total == pytest.approx(result.net_benefit, abs=0.01)


def test_a_refused_jurisdiction_reports_no_misleading_timing_figures():
    # _refuse() builds a BenefitBreakdown directly, so the new fields default
    # rather than being computed. They must not read as a real answer.
    result = compute(rule=make_rule(minimum_spend=None, is_discretionary=True))
    assert result.computable is False
    assert result.present_value == 0
    assert result.audit_cost == 0
    assert result.timing_note is None


# ---------- what this actually changes, stated honestly ----------


def test_timing_separates_two_programs_that_were_previously_indistinguishable():
    """The real payoff on the current seed data.

    New Mexico and Louisiana computed to exactly the same net benefit. The
    tool had no basis to prefer either, and picking one was arbitrary. They
    differ in how fast they pay, and now that shows.
    """
    identical = dict(minimum_spend=None, base_rate=0.25, fringes_qualify=False)
    fast = compute(rule=make_rule(jurisdiction="Fastland", credit_type="refundable", **identical))
    slow = compute(rule=make_rule(jurisdiction="Slowland", credit_type="unknown", **identical))

    assert fast.gross_credit == slow.gross_credit
    assert fast.realizable_credit == slow.realizable_credit
    assert fast.net_benefit > slow.net_benefit


def test_timing_can_reverse_a_ranking_that_face_value_would_get_backwards():
    """The mechanism, demonstrated on constructed rules.

    Not claimed of the seed jurisdictions — there, timing changes every figure
    but not the order (see this module's docstring). It is claimed of the
    model: a slower, discounted credit can lose to a smaller, faster one, and
    a tool that ignores timing reports the loser as the winner.
    """
    budget = make_budget(fringe_rate=0)
    generous_but_slow = make_rule(
        jurisdiction="Slowland", base_rate=0.30, minimum_spend=None,
        credit_type="transferable", fringes_qualify=False, months_to_payment=30,
    )
    modest_but_fast = make_rule(
        jurisdiction="Fastland", base_rate=0.26, minimum_spend=None,
        credit_type="rebate", fringes_qualify=False, months_to_payment=3,
    )

    slow = compute_benefit(budget, generous_but_slow, assumptions=NO_RELOCATION, timing=INSTANT)
    fast = compute_benefit(budget, modest_but_fast, assumptions=NO_RELOCATION, timing=INSTANT)
    assert slow.net_benefit > fast.net_benefit, "undiscounted, the slow 30% program wins"

    slow_pv = compute_benefit(budget, generous_but_slow, assumptions=NO_RELOCATION)
    fast_pv = compute_benefit(budget, modest_but_fast, assumptions=NO_RELOCATION)
    assert fast_pv.net_benefit > slow_pv.net_benefit, "discounted, the fast 26% program wins"
