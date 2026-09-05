"""Layer 2 refusing to compute on inputs that can't describe reality.

Layer 2 is trustworthy because no model does its arithmetic. But its inputs
come from a model, and arithmetic on a hallucinated input is exactly as wrong
as arithmetic by a hallucination — it just looks more credible, because it
arrives wrapped in a breakdown with sources attached.

Every case here was found by firing adversarial payloads at a running server,
not imagined. Before this guard existed the API answered all of them with
HTTP 200 and a confident number:

    base_rate 5.0        -> $9,520,000 credit on a $2M film
    resident_labor_pct 3 -> $4,256,000 qualifying spend on a $2M budget
    transfer_discount 5  -> realizable credit 5x its own face value
    distance_km -100     -> *higher* net benefit than the correct distance

The last one is the sharpest illustration of why clamping is the wrong fix:
the more impossible the input, the more profitable the jurisdiction looked.
"""

from datetime import date

import pytest

from app.calculator import compute_benefit
from app.models import RelocationAssumptions, Tier, Uplift

from .fixtures import make_budget, make_rule

TODAY = date(2026, 9, 5)
NO_RELOCATION = RelocationAssumptions(
    equipment_shipping_base=0, imported_crew_pct=0, per_diem_per_person_per_day=0, hotel_per_person_per_day=0
)


def compute(budget=None, rule=None, **kwargs):
    return compute_benefit(
        budget or make_budget(),
        rule or make_rule(minimum_spend=None),
        assumptions=NO_RELOCATION,
        today=TODAY,
        **kwargs,
    )


def assert_refused(result, *, mentioning: str):
    """Refusal is a specific contract, not just a falsy flag.

    Nothing may be ranked, and the producer has to be told why — a silent zero
    is the failure mode this whole file exists to prevent.
    """
    assert result.computable is False
    assert result.gross_credit == 0
    assert result.realizable_credit == 0
    assert result.net_benefit == 0
    assert mentioning in result.non_computable_reason.lower()
    assert result.caps_applied, "a refusal must still say something in the caps list"


# ---------- the percentage-as-whole-number bug, the likeliest live failure ----------


@pytest.mark.parametrize("bad_rate", [5.0, 30.0, 1.01, -0.3])
def test_a_base_rate_outside_zero_to_one_is_refused(bad_rate):
    assert_refused(compute(rule=make_rule(base_rate=bad_rate, minimum_spend=None)), mentioning="percentage")


def test_the_refusal_names_the_likely_cause_rather_than_just_failing():
    # "30 rather than 0.30" is the actual bug a reader needs to go check for
    # in the source, so the message has to say it.
    result = compute(rule=make_rule(base_rate=30.0, minimum_spend=None))
    assert "30 rather than 0.30" in result.non_computable_reason


def test_a_bad_rate_is_refused_not_clamped_to_a_plausible_number():
    # Clamping 30.0 to 1.0 would invent a 100% credit and rank it first —
    # a wrong answer that looks more authoritative than the honest gap.
    result = compute(rule=make_rule(base_rate=30.0, minimum_spend=None))
    assert result.gross_credit == 0
    assert result.computable is False


def test_boundary_rates_of_zero_and_one_are_allowed():
    # 0% is a real (if useless) program and 100% is not physically impossible;
    # this guard filters the impossible, not the implausible.
    assert compute(rule=make_rule(base_rate=0.0, minimum_spend=None)).computable is True
    assert compute(rule=make_rule(base_rate=1.0, minimum_spend=None)).computable is True


def test_a_bad_tier_rate_is_caught_even_when_the_base_rate_is_fine():
    rule = make_rule(base_rate=0.25, minimum_spend=None, tiers=[Tier(threshold=1_000_000, rate=40.0)])
    assert_refused(compute(rule=rule), mentioning="percentage")


def test_a_bad_uplift_rate_is_caught_even_when_the_base_rate_is_fine():
    rule = make_rule(
        base_rate=0.25,
        minimum_spend=None,
        uplifts=[Uplift(condition="rural shoot", bonus_rate=10.0, machine_checkable=False)],
    )
    assert_refused(compute(rule=rule), mentioning="percentage")


# ---------- shares that silently exceed the budget they're a share of ----------


@pytest.mark.parametrize("bad_pct", [3.0, -1.0, 1.5])
def test_a_resident_labor_share_outside_zero_to_one_is_refused(bad_pct):
    # At 3.0 this produced $4.26M of qualifying spend on a $2M budget: more of
    # the budget qualified than existed, and nothing said so.
    assert_refused(compute(budget=make_budget(resident_labor_pct=bad_pct)), mentioning="resident labor share")


@pytest.mark.parametrize("bad_rate", [10.0, -0.5])
def test_a_fringe_rate_outside_zero_to_one_is_refused(bad_rate):
    assert_refused(compute(budget=make_budget(fringe_rate=bad_rate)), mentioning="fringe rate")


@pytest.mark.parametrize("bad_discount", [5.0, -0.1])
def test_a_transfer_discount_outside_zero_to_one_is_refused(bad_discount):
    # Above 1.0 the credit sells for more than its face value, so
    # realizable_credit exceeded gross_credit — arithmetically impossible.
    assert_refused(compute(transfer_discount=bad_discount), mentioning="sale price")


def test_a_transfer_discount_of_zero_is_allowed_because_worthless_is_a_real_answer():
    # Only a transferable credit is sold, so the discount has to be exercised
    # against one — an "unknown" credit type is shown at face value.
    transferable = make_rule(minimum_spend=None, credit_type="transferable")
    result = compute(rule=transferable, transfer_discount=0.0)
    assert result.computable is True
    assert result.gross_credit > 0
    assert result.realizable_credit == 0


# ---------- budgets and geography that can't be real ----------


@pytest.mark.parametrize(
    "field,label",
    [
        ("atl_cast", "above-the-line cast"),
        ("btl_labor", "below-the-line labor"),
        ("post_vfx", "post and VFX"),
    ],
)
def test_negative_spend_on_any_line_is_refused(field, label):
    result = compute(budget=make_budget(**{field: -500_000}))
    assert_refused(result, mentioning=label.lower())


def test_negative_shoot_days_or_crew_are_refused():
    assert_refused(compute(budget=make_budget(shoot_days=-5)), mentioning="negative shoot-day")
    assert_refused(compute(budget=make_budget(crew_headcount=-10)), mentioning="negative shoot-day")


def test_a_negative_distance_is_refused_rather_than_paying_the_production_to_travel():
    # The important one: a negative distance subtracts a negative relocation
    # cost, so the *more* impossible the input, the better the jurisdiction
    # scored. Clamping to zero would still quietly reward a broken Maps reply.
    result = compute(distance_km=-100)
    assert_refused(result, mentioning="negative")
    assert result.relocation_cost == 0


def test_a_negative_travel_time_is_refused():
    assert_refused(compute(travel_time_hours=-4), mentioning="negative")


def test_a_negative_statutory_cap_is_refused():
    assert_refused(compute(rule=make_rule(per_person_wage_cap=-1000, minimum_spend=None)), mentioning="negative")


# ---------- the guard must not fire on anything legitimate ----------


def test_an_ordinary_production_still_computes():
    # The whole suite is worthless if the guard is over-eager; this is the
    # canary for that.
    result = compute()
    assert result.computable is True
    assert result.gross_credit > 0


def test_a_zero_budget_is_allowed_because_empty_is_not_impossible():
    # Distinct from negative: a producer who hasn't filled the form in yet
    # should see zeros, not an accusation that their budget is malformed.
    budget = make_budget(atl_cast=0, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0, total=0)
    result = compute(budget=budget)
    assert result.computable is True
    assert result.qualifying_spend == 0


def test_a_very_large_but_possible_budget_still_computes():
    # A $500M tentpole is unusual, not impossible. Nothing here is a
    # plausibility filter.
    result = compute(budget=make_budget(btl_labor=500_000_000, total=502_000_000))
    assert result.computable is True
    assert result.gross_credit > 0


def test_the_boundary_values_zero_and_one_pass_for_every_share():
    for budget in (make_budget(resident_labor_pct=0.0), make_budget(resident_labor_pct=1.0),
                   make_budget(fringe_rate=0.0), make_budget(fringe_rate=1.0)):
        assert compute(budget=budget).computable is True
    assert compute(transfer_discount=1.0).computable is True
