"""Funding availability as a ranking gate.

BUILD_BRIEF.md section 1 names this as the product's whole wedge: other tools
"report the rate but not whether the annual funding pool is exhausted, the
application window has closed, or the program is sunsetting. A 30% credit you
can't access is a 0% credit."

Until these tests existed, compute_benefit read none of pool_status,
sunset_date or application_deadline — a closed program computed a full credit
and could be returned as the top recommendation. That is precisely the failure
the product claims to prevent, so it's worth a file of its own.
"""

from datetime import date

import pytest

from app.calculator import compute_benefit
from app.models import RelocationAssumptions

from .fixtures import make_budget, make_rule

TODAY = date(2026, 9, 5)
NO_RELOCATION = RelocationAssumptions(
    equipment_shipping_base=0, imported_crew_pct=0, per_diem_per_person_per_day=0, hotel_per_person_per_day=0
)


# ---------- hard blocks: the money cannot be accessed ----------

def test_a_closed_pool_is_not_ranked_however_good_the_rate():
    # A 40% credit you can't claim loses to a 20% credit you can.
    rule = make_rule(base_rate=0.40, minimum_spend=None, pool_status="closed")
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is False
    assert result.gross_credit == 0
    assert result.net_benefit == 0
    assert "closed" in result.non_computable_reason


def test_a_program_past_its_sunset_date_is_not_ranked():
    rule = make_rule(minimum_spend=None, sunset_date=date(2026, 6, 30))
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is False
    assert "sunset" in result.non_computable_reason
    assert "2026-06-30" in result.non_computable_reason


def test_a_sunset_date_still_in_the_future_does_not_block():
    rule = make_rule(minimum_spend=None, sunset_date=date(2027, 6, 30))
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is True
    assert result.gross_credit > 0


def test_a_closed_application_window_is_not_ranked():
    rule = make_rule(minimum_spend=None, application_deadline=date(2026, 8, 1))
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is False
    assert "application window closed" in result.non_computable_reason


def test_an_open_application_window_does_not_block():
    rule = make_rule(minimum_spend=None, application_deadline=date(2027, 1, 15))
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is True


def test_today_is_injectable_so_the_gate_is_deterministic():
    # The same rule reads differently either side of its sunset, and a test
    # asserting that must not depend on the wall clock.
    rule = make_rule(minimum_spend=None, sunset_date=date(2026, 9, 4))
    assert compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=date(2026, 9, 3)).computable
    assert not compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=date(2026, 9, 5)).computable


# ---------- soft warnings: claimable, but qualified ----------

def test_capping_out_still_ranks_but_carries_a_warning():
    # Still claimable today, so excluding it would be its own kind of wrong —
    # but recommending it silently would be worse.
    rule = make_rule(minimum_spend=None, pool_status="capping_out")
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is True
    assert result.gross_credit > 0
    assert any("capping out" in note for note in result.caps_applied)


def test_unknown_availability_ranks_but_says_the_assumption_out_loud():
    rule = make_rule(minimum_spend=None, pool_status="unknown")
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is True
    assert any("availability not confirmed" in note for note in result.caps_applied)


def test_under_review_is_flagged_on_an_otherwise_open_program():
    rule = make_rule(minimum_spend=None, pool_status="open", under_review=True)
    result = compute_benefit(make_budget(), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert result.computable is True
    assert any("legislative review" in note for note in result.caps_applied)


def test_an_open_confirmed_program_carries_no_availability_noise():
    rule = make_rule(minimum_spend=None, pool_status="open", under_review=False, fringes_qualify=False)
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION, today=TODAY)
    assert not any("availability" in note or "review" in note for note in result.caps_applied)


# ---------- the ranking consequence ----------

def test_a_closed_high_rate_program_loses_to_an_open_low_rate_one():
    # The scenario the whole wedge is about, asserted end to end.
    budget = make_budget(fringe_rate=0)
    closed_but_generous = compute_benefit(
        budget,
        make_rule(jurisdiction="Closedland", base_rate=0.40, minimum_spend=None, pool_status="closed"),
        assumptions=NO_RELOCATION,
        today=TODAY,
    )
    open_but_modest = compute_benefit(
        budget,
        make_rule(jurisdiction="Openland", base_rate=0.20, minimum_spend=None, pool_status="open",
                  credit_type="refundable", fringes_qualify=False),
        assumptions=NO_RELOCATION,
        today=TODAY,
    )
    assert closed_but_generous.computable is False
    assert open_but_modest.computable is True
    assert open_but_modest.net_benefit > closed_but_generous.net_benefit
