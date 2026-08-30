"""Layer 2 unit tests. Non-negotiable per BUILD_BRIEF.md section 9 —
especially the minimum-spend cliff, the wage cap, and tier boundaries.

Monetary assertions use pytest.approx: several inputs (resident_labor_pct,
imported_crew_pct, ground_cost_per_person_per_km, ...) are binary-imprecise
decimals like 0.55 or 0.35, so exact `==` on a value derived from them is one
rounding hair away from a flaky failure. Assertions on integers (qualifying
category flags, list lengths, plain sums of whole-dollar inputs) stay exact.
"""

import pytest

from app.calculator import assumed_cast_count, compute_benefit, sensitivity_sweep
from app.models import RelocationAssumptions, Uplift

from .fixtures import CAPPED_RULE, DISCRETIONARY_RULE, FLAT_RATE_RULE, TIERED_RULE, make_budget, make_rule


# ---------- assumed_cast_count ----------

def test_assumed_cast_count_clamps_low():
    assert assumed_cast_count(10) == 4


def test_assumed_cast_count_clamps_high():
    assert assumed_cast_count(500) == 24


def test_assumed_cast_count_in_range():
    assert assumed_cast_count(200) == 16


# ---------- minimum spend cliff ----------

def test_minimum_spend_cliff_one_dollar_under_yields_zero():
    rule = make_rule(minimum_spend=500_000, base_rate=0.25)
    budget = make_budget(atl_cast=100_000, atl_noncast=50_000, btl_labor=200_000, btl_nonlabor=100_000, post_vfx=49_999)
    result = compute_benefit(budget, rule)
    assert result.qualifying_spend == pytest.approx(499_999)
    assert result.gross_credit == 0
    assert any("cliff" in note for note in result.caps_applied)


def test_minimum_spend_at_exact_threshold_is_not_a_cliff():
    rule = make_rule(minimum_spend=500_000, base_rate=0.25)
    budget = make_budget(atl_cast=100_000, atl_noncast=50_000, btl_labor=200_000, btl_nonlabor=100_000, post_vfx=50_000)
    result = compute_benefit(budget, rule)
    assert result.qualifying_spend == pytest.approx(500_000)
    assert result.gross_credit == pytest.approx(125_000)


# ---------- wage cap ----------

def test_wage_cap_reduces_qualifying_spend_when_it_bites():
    rule = make_rule(per_person_wage_cap=100_000, minimum_spend=None, base_rate=0.25)
    budget = make_budget(atl_cast=1_000_000, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0, crew_headcount=45)
    result = compute_benefit(budget, rule)
    # assumed_cast_count(45) == 4 -> cap allows 100_000 * 4 = 400_000 of the 1_000_000 ATL cast spend
    assert result.qualifying_spend == pytest.approx(400_000)
    assert result.gross_credit == pytest.approx(100_000)
    assert any("wage cap" in note for note in result.caps_applied)


def test_wage_cap_not_applied_when_under_cap():
    rule = make_rule(per_person_wage_cap=100_000, minimum_spend=None, base_rate=0.25)
    budget = make_budget(atl_cast=200_000, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0, crew_headcount=45)
    result = compute_benefit(budget, rule)
    assert result.qualifying_spend == pytest.approx(200_000)
    assert result.gross_credit == pytest.approx(50_000)
    assert result.caps_applied == []


# ---------- tier boundaries ----------

def test_tier_selects_rate_at_exact_lower_boundary():
    budget = make_budget(atl_cast=1_000_000, atl_noncast=1_000_000, btl_labor=1_000_000, btl_nonlabor=1_000_000, post_vfx=1_000_000)
    result = compute_benefit(budget, TIERED_RULE)
    assert result.qualifying_spend == pytest.approx(5_000_000)
    assert result.gross_credit == pytest.approx(1_250_000)  # 5_000_000 * 0.25 tier
    assert any("tier rate" in note for note in result.caps_applied)


def test_tier_just_below_boundary_keeps_previous_rate():
    budget = make_budget(atl_cast=4_000_000, atl_noncast=4_000_000, btl_labor=4_000_000, btl_nonlabor=4_000_000, post_vfx=3_999_999)
    result = compute_benefit(budget, TIERED_RULE)
    assert result.qualifying_spend == pytest.approx(19_999_999)
    assert result.gross_credit == pytest.approx(19_999_999 * 0.25)


def test_tier_at_top_boundary_uses_top_rate():
    budget = make_budget(atl_cast=4_000_000, atl_noncast=4_000_000, btl_labor=4_000_000, btl_nonlabor=4_000_000, post_vfx=4_000_000)
    result = compute_benefit(budget, TIERED_RULE)
    assert result.qualifying_spend == pytest.approx(20_000_000)
    assert result.gross_credit == pytest.approx(6_000_000)  # 20_000_000 * 0.30 tier


# ---------- discretionary programs ----------

def test_discretionary_program_is_not_computable():
    result = compute_benefit(make_budget(), DISCRETIONARY_RULE)
    assert result.computable is False
    assert result.non_computable_reason
    assert result.gross_credit == 0
    assert result.net_benefit == 0


# ---------- uplifts ----------

def test_machine_checkable_uplift_applied_when_condition_met():
    rule = make_rule(minimum_spend=None, uplifts=[Uplift(condition="local hire > 50%", bonus_rate=0.05, machine_checkable=True)])
    budget = make_budget(resident_labor_pct=0.6)
    result = compute_benefit(budget, rule)
    assert result.qualifying_spend == pytest.approx(2_000_000)
    assert result.gross_credit == pytest.approx(600_000)  # 500_000 base + 100_000 uplift
    assert result.caps_applied == []


def test_machine_checkable_uplift_not_applied_when_condition_unmet():
    rule = make_rule(minimum_spend=None, uplifts=[Uplift(condition="local hire > 50%", bonus_rate=0.05, machine_checkable=True)])
    budget = make_budget(resident_labor_pct=0.4)
    result = compute_benefit(budget, rule)
    assert result.gross_credit == pytest.approx(500_000)
    assert result.caps_applied == []


def test_non_machine_checkable_uplift_logged_but_not_applied():
    rule = make_rule(uplifts=[
        Uplift(condition="local hire > 50%", bonus_rate=0.05, machine_checkable=True),
        Uplift(condition="shot outside metro area", bonus_rate=0.03, machine_checkable=False),
    ])
    budget = make_budget(resident_labor_pct=0.55)
    result = compute_benefit(budget, rule)
    assert result.gross_credit == pytest.approx(600_000)  # only the machine-checkable uplift applied
    assert len(result.caps_applied) == 1
    assert "shot outside metro area" in result.caps_applied[0]
    assert "unquantified" in result.caps_applied[0]


def test_machine_checkable_uplift_with_unrecognized_condition_is_logged_not_guessed():
    rule = make_rule(minimum_spend=None, uplifts=[Uplift(condition="shot outside metro area", bonus_rate=0.03, machine_checkable=True)])
    budget = make_budget()
    result = compute_benefit(budget, rule)
    assert result.gross_credit == pytest.approx(500_000)
    assert len(result.caps_applied) == 1
    assert "recognized form" in result.caps_applied[0]


# ---------- per-project cap ----------

def test_per_project_cap_ceilings_gross_credit():
    budget = make_budget(atl_cast=2_000_000, atl_noncast=2_000_000, btl_labor=2_000_000, btl_nonlabor=2_000_000, post_vfx=2_000_000)
    result = compute_benefit(budget, CAPPED_RULE)
    assert result.qualifying_spend == pytest.approx(10_000_000)
    assert result.gross_credit == pytest.approx(1_000_000)
    assert any("per-project cap" in note for note in result.caps_applied)


# ---------- relocation cost ----------

def test_relocation_cost_uses_flights_over_threshold():
    assumptions = RelocationAssumptions()
    budget = make_budget(crew_headcount=45, shoot_days=22)
    result = compute_benefit(budget, FLAT_RATE_RULE, distance_km=1000, assumptions=assumptions)
    # travelling_crew = 45 * 0.4 = 18; transport = 18 * 600 = 10_800
    # lodging = 18 * 22 * (85 + 140) = 89_100; + 15_000 equipment
    assert result.relocation_components["transport"] == pytest.approx(10_800)
    assert result.relocation_components["lodging"] == pytest.approx(89_100)
    assert result.relocation_cost == pytest.approx(114_900)
    assert result.gross_credit == pytest.approx(500_000)
    assert result.net_benefit == pytest.approx(385_100)


def test_relocation_cost_uses_ground_under_threshold():
    budget = make_budget(crew_headcount=45, shoot_days=22)
    result = compute_benefit(budget, FLAT_RATE_RULE, distance_km=500)
    # transport = 18 * 500 * 0.35 = 3_150
    assert result.relocation_components["transport"] == pytest.approx(3_150)
    assert result.relocation_cost == pytest.approx(107_250)


def test_relocation_cost_zero_transport_without_distance():
    budget = make_budget(crew_headcount=45, shoot_days=22)
    result = compute_benefit(budget, FLAT_RATE_RULE, distance_km=None)
    assert result.relocation_components["transport"] == 0
    assert result.distance_km is None


# ---------- sensitivity sweep ----------

def test_sensitivity_sweep_varies_field_and_recomputes():
    budget = make_budget()
    results = sensitivity_sweep(budget, FLAT_RATE_RULE, "atl_cast", [0, 1_000_000, 2_000_000])
    assert [r.gross_credit for r in results] == pytest.approx([437_500, 687_500, 937_500])


# ---------- category qualification ----------

def test_non_qualifying_categories_contribute_zero():
    rule = make_rule(
        minimum_spend=None,
        qualifying={
            "atl_cast": True, "atl_noncast": False,
            "btl_labor_resident": True, "btl_labor_nonresident": False,
            "btl_nonlabor": False, "post_vfx": False,
        },
    )
    budget = make_budget(resident_labor_pct=0.5)
    result = compute_benefit(budget, rule)
    # atl_cast 250_000 + resident BTL labor half of 750_000 = 375_000
    assert result.qualifying_spend == pytest.approx(625_000)
    assert result.gross_credit == pytest.approx(156_250)
