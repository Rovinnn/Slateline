"""Fringes and credit monetisation — the two things that separate a credit's
advertised face value from what a production actually banks.

Both were absent until now, and both are large: payroll burden runs 22-35% of
wages, and a transferable credit sells at a broker discount. On a $2.5M
budget the pair move the answer by roughly $100k, the same order as the
entire relocation calculation the product was already built around.
"""

import pytest

from app.calculator import DEFAULT_TRANSFER_DISCOUNT, compute_benefit
from app.models import RelocationAssumptions

from .fixtures import make_budget, make_rule

# Strips relocation out so these tests isolate credit value.
NO_RELOCATION = RelocationAssumptions(
    equipment_shipping_base=0,
    imported_crew_pct=0,
    per_diem_per_person_per_day=0,
    hotel_per_person_per_day=0,
)


# ---------- fringes ----------

def test_fringes_are_added_to_qualifying_spend_when_the_statute_allows_them():
    rule = make_rule(minimum_spend=None, fringes_qualify=True, base_rate=0.25)
    # Labor only, so the fringe base is unambiguous.
    budget = make_budget(
        atl_cast=0, atl_noncast=0, btl_labor=1_000_000, btl_nonlabor=0, post_vfx=0,
        resident_labor_pct=1.0, fringe_rate=0.30,
    )
    result = compute_benefit(budget, rule, assumptions=NO_RELOCATION)
    assert result.qualifying_spend == pytest.approx(1_300_000)
    assert result.gross_credit == pytest.approx(325_000)
    assert any("fringes qualify" in note for note in result.caps_applied)


def test_fringes_are_excluded_when_the_statute_says_so():
    rule = make_rule(minimum_spend=None, fringes_qualify=False, base_rate=0.25)
    budget = make_budget(
        atl_cast=0, atl_noncast=0, btl_labor=1_000_000, btl_nonlabor=0, post_vfx=0,
        resident_labor_pct=1.0, fringe_rate=0.30,
    )
    result = compute_benefit(budget, rule, assumptions=NO_RELOCATION)
    assert result.qualifying_spend == pytest.approx(1_000_000)
    assert any("fringes excluded" in note for note in result.caps_applied)


def test_unknown_fringe_treatment_excludes_them_but_says_so():
    # Conservative direction, but silence would understate the credit with no
    # explanation — the producer needs to know to ask the film office.
    rule = make_rule(minimum_spend=None, fringes_qualify=None, base_rate=0.25)
    budget = make_budget(
        atl_cast=0, atl_noncast=0, btl_labor=1_000_000, btl_nonlabor=0, post_vfx=0,
        resident_labor_pct=1.0, fringe_rate=0.30,
    )
    result = compute_benefit(budget, rule, assumptions=NO_RELOCATION)
    assert result.qualifying_spend == pytest.approx(1_000_000)
    assert any("whether fringes qualify" in note for note in result.caps_applied)


def test_fringes_never_attach_to_non_labor_spend():
    # Rentals and post services carry no payroll burden; only wages do.
    rule = make_rule(minimum_spend=None, fringes_qualify=True, base_rate=0.25)
    budget = make_budget(
        atl_cast=0, atl_noncast=0, btl_labor=0, btl_nonlabor=1_000_000, post_vfx=0, fringe_rate=0.30,
    )
    result = compute_benefit(budget, rule, assumptions=NO_RELOCATION)
    assert result.qualifying_spend == pytest.approx(1_000_000)


def test_fringes_only_accrue_on_labor_that_itself_qualifies():
    # A state that excludes non-resident labor excludes the burden on it too.
    rule = make_rule(
        minimum_spend=None,
        fringes_qualify=True,
        base_rate=0.25,
        qualifying={
            "atl_cast": False, "atl_noncast": False,
            "btl_labor_resident": True, "btl_labor_nonresident": False,
            "btl_nonlabor": False, "post_vfx": False,
        },
    )
    budget = make_budget(
        atl_cast=0, atl_noncast=0, btl_labor=1_000_000, btl_nonlabor=0, post_vfx=0,
        resident_labor_pct=0.5, fringe_rate=0.30,
    )
    result = compute_benefit(budget, rule, assumptions=NO_RELOCATION)
    # 500k of resident labor qualifies, plus 30% fringes on that 500k alone.
    assert result.qualifying_spend == pytest.approx(650_000)


def test_a_zero_fringe_rate_produces_no_fringe_note_at_all():
    rule = make_rule(minimum_spend=None, fringes_qualify=None)
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION)
    assert not any("fringe" in note for note in result.caps_applied)


# ---------- monetisation ----------

def test_refundable_credit_is_worth_face_value():
    rule = make_rule(minimum_spend=None, credit_type="refundable", fringes_qualify=False)
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION)
    assert result.realizable_credit == pytest.approx(result.gross_credit)
    assert result.net_benefit == pytest.approx(result.gross_credit)
    assert "face value" in (result.monetization_note or "")


def test_transferable_credit_is_discounted_to_what_a_broker_pays():
    rule = make_rule(minimum_spend=None, credit_type="transferable", fringes_qualify=False)
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION)
    assert result.gross_credit == pytest.approx(500_000)
    assert result.realizable_credit == pytest.approx(500_000 * DEFAULT_TRANSFER_DISCOUNT)
    assert "transferable" in (result.monetization_note or "")


def test_the_broker_discount_is_an_editable_assumption():
    rule = make_rule(minimum_spend=None, credit_type="transferable", fringes_qualify=False)
    result = compute_benefit(
        make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION, transfer_discount=0.80
    )
    assert result.realizable_credit == pytest.approx(400_000)


def test_two_identical_rates_rank_differently_once_payout_is_modelled():
    # The bias this fixes: a transferable 25% and a refundable 25% were ranked
    # equal, when the transferable one is worth about 10% less in cash.
    budget = make_budget(fringe_rate=0)
    refundable = compute_benefit(
        budget,
        make_rule(minimum_spend=None, credit_type="refundable", fringes_qualify=False),
        assumptions=NO_RELOCATION,
    )
    transferable = compute_benefit(
        budget,
        make_rule(minimum_spend=None, credit_type="transferable", fringes_qualify=False),
        assumptions=NO_RELOCATION,
    )
    assert refundable.gross_credit == pytest.approx(transferable.gross_credit)
    assert refundable.net_benefit > transferable.net_benefit


def test_non_refundable_is_flagged_rather_than_silently_zeroed_or_accepted():
    # Worth face value to a production with in-state liability, near nothing to
    # one without — a fact about the company, not the statute, so it's flagged.
    rule = make_rule(minimum_spend=None, credit_type="non_refundable", fringes_qualify=False)
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION)
    assert result.realizable_credit == pytest.approx(result.gross_credit)
    assert "in-state tax liability" in (result.monetization_note or "")


def test_unknown_payout_mechanism_is_shown_at_face_value_and_said_so():
    rule = make_rule(minimum_spend=None, credit_type="unknown", fringes_qualify=False)
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION)
    assert result.realizable_credit == pytest.approx(result.gross_credit)
    assert "not stated" in (result.monetization_note or "")


def test_a_zero_credit_carries_no_monetisation_note():
    # Nothing to monetise below the cliff; a broker note there would be noise
    # on top of the cliff explanation.
    rule = make_rule(minimum_spend=10_000_000, credit_type="transferable")
    result = compute_benefit(make_budget(fringe_rate=0), rule, assumptions=NO_RELOCATION)
    assert result.gross_credit == 0
    assert result.monetization_note is None
