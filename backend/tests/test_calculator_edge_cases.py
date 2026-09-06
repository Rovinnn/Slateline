"""Boundary and degenerate-input tests for compute_benefit.

test_calculator.py covers the documented rules from BUILD_BRIEF.md section 6.
This file covers the inputs that arrive when something upstream is empty,
extreme, or exactly on a threshold — the cases where a wrong answer looks
plausible instead of crashing.
"""

import pytest

from app.calculator import assumed_cast_count, compute_benefit
from app.models import RelocationAssumptions, Tier, Uplift

from .fixtures import make_budget, make_rule

ASSUMPTIONS = RelocationAssumptions()


# ---------- degenerate budgets ----------

def test_all_zero_budget_yields_zero_credit_and_equipment_only_relocation():
    rule = make_rule(minimum_spend=None)
    budget = make_budget(
        total=0, atl_cast=0, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0,
        shoot_days=0, crew_headcount=0,
    )
    result = compute_benefit(budget, rule, distance_km=1000, assumptions=ASSUMPTIONS)
    assert result.qualifying_spend == 0
    assert result.gross_credit == 0
    # No crew to fly or house — only the flat equipment-shipping base remains.
    assert result.relocation_cost == pytest.approx(ASSUMPTIONS.equipment_shipping_base)
    assert result.net_benefit == pytest.approx(-ASSUMPTIONS.equipment_shipping_base)


def test_zero_crew_does_not_divide_by_zero_in_the_wage_cap():
    # assumed_cast_count clamps to a floor of 4, so the per-person division is
    # always safe even with a crew of zero.
    assert assumed_cast_count(0) == 4
    rule = make_rule(per_person_wage_cap=10_000, minimum_spend=None)
    budget = make_budget(crew_headcount=0, atl_cast=1_000_000)
    result = compute_benefit(budget, rule, assumptions=ASSUMPTIONS)
    assert any("wage cap" in note for note in result.caps_applied)


def test_zero_shoot_days_removes_lodging_but_keeps_transport():
    budget = make_budget(shoot_days=0, crew_headcount=45)
    result = compute_benefit(budget, make_rule(), distance_km=1000, assumptions=ASSUMPTIONS)
    assert result.relocation_components["lodging"] == 0
    assert result.relocation_components["transport"] > 0


@pytest.mark.parametrize("pct", [0.0, 1.0])
def test_resident_labor_share_at_both_extremes(pct):
    # Whichever side is excluded, the other side must carry the whole BTL
    # labor line — no double counting and nothing lost in the split.
    rule = make_rule(
        minimum_spend=None,
        qualifying={
            "atl_cast": False, "atl_noncast": False,
            "btl_labor_resident": True, "btl_labor_nonresident": False,
            "btl_nonlabor": False, "post_vfx": False,
        },
    )
    budget = make_budget(resident_labor_pct=pct, btl_labor=1_000_000)
    result = compute_benefit(budget, rule, assumptions=ASSUMPTIONS)
    assert result.qualifying_spend == pytest.approx(1_000_000 * pct)


def test_very_large_budget_still_respects_the_minimum_spend_cliff():
    # Float precision at 1e12 must not smear the comparison either way.
    rule = make_rule(minimum_spend=1_000_000_000_000)
    just_under = make_budget(
        atl_cast=999_999_999_999, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0,
    )
    assert compute_benefit(just_under, rule, assumptions=ASSUMPTIONS).gross_credit == 0
    at_threshold = make_budget(
        atl_cast=1_000_000_000_000, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0,
    )
    assert compute_benefit(at_threshold, rule, assumptions=ASSUMPTIONS).gross_credit > 0


# ---------- qualifying-map degeneracies (the Oklahoma failure mode) ----------

def test_empty_qualifying_map_zeroes_the_credit_without_crashing():
    # Documents — deliberately — that an empty map is silently $0, which is
    # why RECORD_JURISDICTION_RULE_SCHEMA now forces all six keys. See
    # test_extraction_schema.py; this is the downstream half of that bug.
    rule = make_rule(qualifying={}, minimum_spend=None)
    result = compute_benefit(make_budget(), rule, assumptions=ASSUMPTIONS)
    assert result.qualifying_spend == 0
    assert result.gross_credit == 0
    assert result.computable is True  # no error surfaces — that's the danger


def test_partial_qualifying_map_counts_only_the_keys_present_and_true():
    rule = make_rule(qualifying={"atl_cast": True}, minimum_spend=None)
    budget = make_budget(atl_cast=250_000)
    result = compute_benefit(budget, rule, assumptions=ASSUMPTIONS)
    assert result.qualifying_spend == pytest.approx(250_000)


# ---------- rate selection boundaries ----------

def test_tiers_supplied_out_of_order_still_select_the_highest_applicable():
    rule = make_rule(
        minimum_spend=None,
        base_rate=0.10,
        tiers=[Tier(threshold=20_000_000, rate=0.30), Tier(threshold=0, rate=0.20), Tier(threshold=5_000_000, rate=0.25)],
    )
    budget = make_budget(atl_cast=6_000_000, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0)
    result = compute_benefit(budget, rule, assumptions=ASSUMPTIONS)
    assert result.gross_credit == pytest.approx(6_000_000 * 0.25)


def test_spend_below_every_tier_threshold_falls_back_to_base_rate():
    rule = make_rule(minimum_spend=None, base_rate=0.10, tiers=[Tier(threshold=5_000_000, rate=0.30)])
    budget = make_budget(atl_cast=100_000, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0)
    result = compute_benefit(budget, rule, assumptions=ASSUMPTIONS)
    assert result.gross_credit == pytest.approx(100_000 * 0.10)


def test_zero_per_project_cap_floors_the_credit_at_zero():
    rule = make_rule(minimum_spend=None, per_project_cap=0)
    result = compute_benefit(make_budget(), rule, assumptions=ASSUMPTIONS)
    assert result.gross_credit == 0
    assert any("per-project cap" in note for note in result.caps_applied)


def test_zero_minimum_spend_never_cliffs():
    rule = make_rule(minimum_spend=0)
    result = compute_benefit(make_budget(), rule, assumptions=ASSUMPTIONS)
    assert result.gross_credit > 0
    assert not any("cliff" in note for note in result.caps_applied)


def test_multiple_machine_checkable_uplifts_stack():
    rule = make_rule(
        minimum_spend=None,
        base_rate=0.20,
        uplifts=[
            Uplift(condition="local hire > 30%", bonus_rate=0.05, machine_checkable=True),
            Uplift(condition="resident labor >= 50%", bonus_rate=0.05, machine_checkable=True),
        ],
    )
    budget = make_budget(resident_labor_pct=0.55)
    result = compute_benefit(budget, rule, assumptions=ASSUMPTIONS)
    # 2_000_000 qualifying at 20% + 5% + 5%
    assert result.gross_credit == pytest.approx(2_000_000 * 0.30)


# ---------- relocation boundaries ----------

def test_distance_exactly_at_the_flight_threshold_uses_ground_travel():
    # The rule is "flight if distance > threshold", so the threshold itself is
    # still a drive — asserting the boundary lands on the documented side.
    budget = make_budget(crew_headcount=45, shoot_days=10)
    at_threshold = compute_benefit(
        budget, make_rule(), distance_km=ASSUMPTIONS.flight_threshold_km, assumptions=ASSUMPTIONS
    )
    travelling = 45 * ASSUMPTIONS.imported_crew_pct
    expected_ground = travelling * ASSUMPTIONS.flight_threshold_km * ASSUMPTIONS.ground_cost_per_person_per_km
    assert at_threshold.relocation_components["transport"] == pytest.approx(expected_ground)

    just_over_km = ASSUMPTIONS.flight_threshold_km + 1
    just_over = compute_benefit(budget, make_rule(), distance_km=just_over_km, assumptions=ASSUMPTIONS)
    assert just_over.relocation_components["transport"] == pytest.approx(
        travelling * (ASSUMPTIONS.flight_cost_per_person + just_over_km * ASSUMPTIONS.flight_cost_per_person_per_km)
    )


def test_flying_further_costs_more_than_flying_less_far():
    """Airfare was flat above the threshold, so distance stopped mattering.

    Every jurisdiction beyond 800km priced identically — Albuquerque at
    1,266km cost exactly what Atlanta cost at 3,498km — which made the routed
    distance the app looks up and draws on its map incapable of changing any
    number. This is the assertion that keeps the Maps integration load-bearing
    rather than decorative.
    """
    budget = make_budget(crew_headcount=45, shoot_days=10)
    near = compute_benefit(budget, make_rule(), distance_km=1_266, assumptions=ASSUMPTIONS)
    far = compute_benefit(budget, make_rule(), distance_km=3_498, assumptions=ASSUMPTIONS)

    assert far.relocation_components["transport"] > near.relocation_components["transport"]
    assert far.net_benefit < near.net_benefit


def test_zero_distance_costs_nothing_to_travel():
    result = compute_benefit(make_budget(), make_rule(), distance_km=0, assumptions=ASSUMPTIONS)
    assert result.relocation_components["transport"] == 0


def test_relocation_can_exceed_the_credit_and_go_negative():
    expensive = RelocationAssumptions(equipment_shipping_base=10_000_000)
    result = compute_benefit(make_budget(), make_rule(), distance_km=1000, assumptions=expensive)
    assert result.net_benefit < 0
    assert result.computable is True  # a bad deal is still a computable one


# ---------- discretionary short-circuit ----------

def test_discretionary_short_circuits_regardless_of_other_fields():
    rule = make_rule(
        is_discretionary=True,
        base_rate=0.40,
        tiers=[Tier(threshold=0, rate=0.40)],
        uplifts=[Uplift(condition="local hire > 10%", bonus_rate=0.10, machine_checkable=True)],
        minimum_spend=None,
    )
    result = compute_benefit(make_budget(), rule, distance_km=5000, assumptions=ASSUMPTIONS)
    assert result.computable is False
    assert result.gross_credit == 0
    assert result.net_benefit == 0
    assert result.relocation_cost == 0  # nothing to net against, so nothing is claimed


# ---------- currency guard ----------

def test_non_usd_rule_is_not_computable_rather_than_silently_treated_as_usd():
    rule = make_rule(currency="EUR", base_rate=0.32, minimum_spend=None)
    result = compute_benefit(make_budget(atl_cast=1_000_000), rule, distance_km=1000, assumptions=ASSUMPTIONS)
    assert result.computable is False
    assert result.gross_credit == 0
    assert result.net_benefit == 0
    assert "EUR" in result.non_computable_reason


def test_usd_rule_is_unaffected_by_the_currency_guard():
    assert compute_benefit(make_budget(), make_rule(currency="USD"), assumptions=ASSUMPTIONS).computable is True
