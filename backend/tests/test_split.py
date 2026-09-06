"""Shoot in one jurisdiction, post in another.

Every incentive tool assumes a single destination, because a rate table has
one row per place. The answer isn't always one place, and the reason it isn't
is worth more than the extra dollars: minimum spend is a cliff, so dividing
the budget can drop either leg under its threshold and zero a credit that
would have been earned whole.

So most of this file is about splits that *lose*, and about saying why. A
feature that only reported the winning combination would be a slot machine;
the value is in explaining that shooting in Louisiana and posting in Georgia
throws away Georgia's entire credit because $250k of post is under its $500k
minimum.
"""

import pytest

from app.calculator import compute_benefit
from app.models import RelocationAssumptions
from app.seed_jurisdictions import GEORGIA, LOUISIANA, NEW_MEXICO, TEXAS
from app.split import analyse_splits, evaluate_plan

from .fixtures import make_budget, make_rule
from .test_seed_jurisdictions import INDIE_DRAMA_BUDGET, REAL_DISTANCES_KM

NO_RELOCATION = RelocationAssumptions(
    equipment_shipping_base=0, imported_crew_pct=0, per_diem_per_person_per_day=0, hotel_per_person_per_day=0
)


def analyse(budget=None, rules=None, **kw):
    return analyse_splits(
        budget or INDIE_DRAMA_BUDGET,
        rules or [GEORGIA, NEW_MEXICO, LOUISIANA],
        distances=REAL_DISTANCES_KM,
        **kw,
    )


# ---------- the result the feature exists to produce ----------


def test_splitting_can_beat_every_single_location():
    """The headline no rate table can produce.

    Shoot in Louisiana, post in New Mexico: $273,911 against $265,564 for the
    best single location. It wins because New Mexico has no minimum spend, so
    a $250k post budget still earns its full 25% refundable — while the shoot
    stays where the big spend is best treated.
    """
    a = analyse()
    assert a.splitting_wins is True
    assert (a.best.shoot_in, a.best.post_in) == ("Louisiana", "New Mexico")
    assert a.best.net_benefit == pytest.approx(273_911, abs=1)
    assert a.gain_over_single == pytest.approx(8_347, abs=1)


def test_the_best_single_location_is_still_reported():
    # The comparison is the point; a split figure alone means nothing.
    a = analyse()
    assert a.best_single.is_split is False
    assert a.best_single.shoot_in == "Louisiana"
    assert a.best_single.net_benefit == pytest.approx(265_564, abs=1)


def test_every_pairing_is_considered_including_the_losers():
    # 3 jurisdictions -> 3 single-location plans + 6 ordered splits.
    a = analyse()
    assert len(a.plans) == 9
    assert sum(1 for p in a.plans if p.is_split) == 6
    # Ranked best first, so a caller can show the runners-up honestly.
    assert a.plans == sorted(a.plans, key=lambda p: -p.net_benefit)


# ---------- the cliff, which is the actually interesting part ----------


def test_a_split_that_falls_off_a_minimum_spend_cliff_says_so():
    """Georgia's $500k minimum destroys a $250k post leg.

    The same $250k would have qualified as part of a $2M single-location
    shoot. That is a trap created by the decision under consideration, and
    nothing in a single-destination ranking could ever reveal it.
    """
    a = analyse()
    ga_post = next(p for p in a.plans if p.shoot_in == "Louisiana" and p.post_in == "Georgia")

    assert ga_post.warnings, "falling off a cliff must be explained, not just scored low"
    assert "below its minimum spend" in ga_post.warnings[0]
    assert "Georgia" in ga_post.warnings[0]
    assert ga_post.post_leg.gross_credit == 0


def test_no_warning_when_the_leg_was_never_going_to_earn_anything():
    """A jurisdiction that earns nothing regardless isn't a cliff.

    Blaming the split for a pre-existing limitation would be the same class of
    error as the challenge pass treating our own silence as a contradiction —
    a true-looking statement about the wrong cause.
    """
    worthless = make_rule(jurisdiction="Nowhere", base_rate=0.0, minimum_spend=None)
    plan = evaluate_plan(INDIE_DRAMA_BUDGET, GEORGIA, worthless, distances=REAL_DISTANCES_KM)
    assert plan is not None
    assert plan.warnings == []


def test_a_jurisdiction_with_no_minimum_is_what_makes_a_split_work():
    # The mechanism, isolated: give Georgia's post leg no minimum and the
    # cliff disappears.
    no_minimum_ga = make_rule(
        jurisdiction="Georgia-no-min", base_rate=0.20, minimum_spend=None, credit_type="transferable"
    )
    plan = evaluate_plan(INDIE_DRAMA_BUDGET, LOUISIANA, no_minimum_ga, distances=REAL_DISTANCES_KM)
    assert plan.post_leg.gross_credit > 0
    assert plan.warnings == []


# ---------- how the legs are priced ----------


def test_each_leg_is_priced_only_on_the_spend_that_happens_there():
    plan = evaluate_plan(INDIE_DRAMA_BUDGET, LOUISIANA, NEW_MEXICO, distances=REAL_DISTANCES_KM)
    # Post is $250k of a $2M budget; the shoot leg prices the other $1.75M.
    assert plan.post_leg.qualifying_spend <= INDIE_DRAMA_BUDGET.post_vfx
    assert plan.shoot_leg.qualifying_spend < INDIE_DRAMA_BUDGET.total


def test_relocation_is_charged_once_and_to_the_shoot_leg():
    """You move cast and crew to where you shoot, not to a post house.

    Charging it twice would make every split look worse than it is, and this
    module's most interesting output is the splits that *lose* — so the
    assumption has to be generous to splitting for that conclusion to mean
    anything.
    """
    plan = evaluate_plan(INDIE_DRAMA_BUDGET, LOUISIANA, NEW_MEXICO, distances=REAL_DISTANCES_KM)
    assert plan.shoot_leg.relocation_cost > 0
    assert plan.post_leg.relocation_cost == 0


def test_a_single_location_plan_prices_the_whole_budget_undivided():
    plan = evaluate_plan(INDIE_DRAMA_BUDGET, GEORGIA, GEORGIA, distances=REAL_DISTANCES_KM)
    direct = compute_benefit(
        INDIE_DRAMA_BUDGET, GEORGIA, distance_km=REAL_DISTANCES_KM["Georgia"]
    )
    assert plan.is_split is False
    assert plan.post_leg is None
    assert plan.net_benefit == pytest.approx(direct.net_benefit)


# ---------- refusing rather than guessing, same as everywhere else ----------


def test_a_jurisdiction_that_cannot_be_computed_produces_no_plans():
    # Texas is discretionary. It must not appear as a $0 option that merely
    # scores badly, which would read as "possible but poor".
    a = analyse(rules=[GEORGIA, NEW_MEXICO, TEXAS])
    named = {p.shoot_in for p in a.plans} | {p.post_in for p in a.plans}
    assert "Texas" not in named


def test_nothing_computable_returns_nothing_rather_than_an_empty_winner():
    assert analyse(rules=[TEXAS]) is None


def test_a_production_with_no_post_spend_has_nothing_to_split():
    """Zero post means every "split" is really a single location.

    Listing six identical-looking pairings would imply a choice that doesn't
    exist.
    """
    no_post = make_budget(post_vfx=0, total=1_750_000)
    a = analyse(budget=no_post)
    assert all(not p.is_split for p in a.plans)
    assert a.splitting_wins is False


def test_a_single_jurisdiction_still_analyses_without_a_split_to_offer():
    a = analyse(rules=[NEW_MEXICO])
    assert a.best.is_split is False
    assert a.gain_over_single == 0
