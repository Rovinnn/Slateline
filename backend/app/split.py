"""Shoot in one jurisdiction, post in another, and solve for the best pairing.

Every incentive comparison tool assumes a single destination, because a rate
table has one row per place. Real productions split constantly — post-only
and VFX-specific credits exist precisely to attract that spend separately —
and the answer to "where should we shoot" is not always one place.

The interesting part is not that splitting can win. It's that splitting can
*lose in a way nobody expects*. Minimum spend is a cliff, not a ramp, so
moving post out of your shoot jurisdiction lowers the spend in both places,
and either leg can drop under its threshold and zero out a credit you would
otherwise have earned whole. A tool that only ranked single destinations
could never show you that, and a producer who split on instinct would find
out at audit.

Modelling choices, stated because they're judgement calls rather than
statute:

- The split is **principal photography vs post/VFX**, not an arbitrary
  fraction. That is how productions actually divide, and how the post-only
  credits that motivate this are written.
- Each jurisdiction counts only the spend that physically happens there, so
  each leg is priced against a budget with the other leg's lines zeroed. This
  is the same rule every statute applies (see Georgia's "work or services not
  conducted or rendered in Georgia").
- **Relocation is charged once, to the shoot leg.** You move cast and crew to
  the location you shoot at; you do not fly 18 people to a post house. Post is
  vendor work, so its leg carries no travel, lodging or equipment shipping.
  This is the assumption most likely to be wrong for a production doing post
  with its own staff, and it is deliberately generous to splitting — so where
  this module says splitting *loses*, that conclusion is robust.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Optional

from .calculator import compute_benefit
from .models import (
    BenefitBreakdown,
    BudgetVector,
    CreditTimingAssumptions,
    JurisdictionRule,
    RelocationAssumptions,
)

#: Post is bought from a vendor in its jurisdiction, so the post leg moves
#: nobody and ships nothing. See the module docstring.
NO_RELOCATION = RelocationAssumptions(
    flight_cost_per_person=0.0,
    flight_cost_per_person_per_km=0.0,
    ground_cost_per_person_per_km=0.0,
    per_diem_per_person_per_day=0.0,
    hotel_per_person_per_day=0.0,
    equipment_shipping_base=0.0,
    imported_crew_pct=0.0,
)


@dataclass
class SplitPlan:
    """One way to run the production, single-location or split."""

    shoot_in: str
    post_in: str
    shoot_leg: BenefitBreakdown
    post_leg: Optional[BenefitBreakdown]
    net_benefit: float
    #: Why this plan is worth less than it looks, in the producer's words.
    warnings: list[str]

    @property
    def is_split(self) -> bool:
        return self.post_in != self.shoot_in


@dataclass
class SplitAnalysis:
    """The best plan found, and what it beats."""

    best: SplitPlan
    best_single: SplitPlan
    #: Every plan considered, best first — including the ones that lose.
    plans: list[SplitPlan]

    @property
    def gain_over_single(self) -> float:
        return self.best.net_benefit - self.best_single.net_benefit

    @property
    def splitting_wins(self) -> bool:
        return self.best.is_split and self.gain_over_single > 0


def _shoot_budget(budget: BudgetVector) -> BudgetVector:
    """The production minus its post, priced where the camera rolls."""
    return replace(budget, post_vfx=0.0, total=budget.total - budget.post_vfx)


def _post_budget(budget: BudgetVector) -> BudgetVector:
    """Post alone. No crew travel: shoot_days and headcount go to zero so
    nothing downstream computes lodging for people who never went."""
    return replace(
        budget,
        atl_cast=0.0,
        atl_noncast=0.0,
        btl_labor=0.0,
        btl_nonlabor=0.0,
        total=budget.post_vfx,
        shoot_days=0,
        crew_headcount=0,
    )


def _cliff_warning(leg: BenefitBreakdown, whole: BenefitBreakdown, label: str, place: str) -> Optional[str]:
    """The trap this module exists to surface.

    A leg that earns nothing *because splitting pushed it under a minimum* is
    a different failure from a leg that was never going to earn anything, and
    only the first is caused by the decision being considered.
    """
    if leg.gross_credit > 0 or whole.gross_credit <= 0:
        return None
    if any("cliff" in note for note in leg.caps_applied):
        return (
            f"Splitting drops {label} in {place} below its minimum spend, so that leg earns "
            f"nothing — it would have qualified as part of a single-location shoot."
        )
    return None


def evaluate_plan(
    budget: BudgetVector,
    shoot_rule: JurisdictionRule,
    post_rule: JurisdictionRule,
    *,
    distances: Optional[dict[str, float]] = None,
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
    today: Optional[date] = None,
) -> Optional[SplitPlan]:
    """Price one shoot/post pairing. None if the shoot leg can't be computed."""
    distances = distances or {}
    kwargs = dict(assumptions=assumptions, timing=timing, today=today)

    if shoot_rule.jurisdiction == post_rule.jurisdiction:
        whole = compute_benefit(
            budget, shoot_rule, distance_km=distances.get(shoot_rule.jurisdiction), **kwargs
        )
        if not whole.computable:
            return None
        return SplitPlan(shoot_rule.jurisdiction, shoot_rule.jurisdiction, whole, None,
                         whole.net_benefit, [])

    shoot = compute_benefit(
        _shoot_budget(budget), shoot_rule, distance_km=distances.get(shoot_rule.jurisdiction), **kwargs
    )
    post = compute_benefit(
        _post_budget(budget), post_rule, distance_km=None,
        assumptions=NO_RELOCATION, timing=timing, today=today,
    )
    if not shoot.computable or not post.computable:
        return None

    # Compare each leg against what it would have earned undivided, so a
    # warning names the cost of *this decision* rather than a pre-existing
    # limitation of the jurisdiction.
    whole_shoot = compute_benefit(
        budget, shoot_rule, distance_km=distances.get(shoot_rule.jurisdiction), **kwargs
    )
    whole_post = compute_benefit(
        budget, post_rule, distance_km=distances.get(post_rule.jurisdiction), **kwargs
    )
    warnings = [
        w
        for w in (
            _cliff_warning(shoot, whole_shoot, "principal photography", shoot_rule.jurisdiction),
            _cliff_warning(post, whole_post, "post and VFX", post_rule.jurisdiction),
        )
        if w
    ]
    return SplitPlan(
        shoot_rule.jurisdiction,
        post_rule.jurisdiction,
        shoot,
        post,
        shoot.net_benefit + post.net_benefit,
        warnings,
    )


def analyse_splits(
    budget: BudgetVector,
    rules: list[JurisdictionRule],
    *,
    distances: Optional[dict[str, float]] = None,
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
    today: Optional[date] = None,
) -> Optional[SplitAnalysis]:
    """Every shoot/post pairing plus every single-location plan, ranked.

    Returns None when nothing can be computed at all. A production with no
    post spend has nothing to split, so only single-location plans appear —
    correctly, rather than as a pile of identical-looking pairings.
    """
    kwargs = dict(distances=distances, assumptions=assumptions, timing=timing, today=today)
    plans: list[SplitPlan] = []
    for shoot_rule in rules:
        for post_rule in rules:
            if post_rule.jurisdiction != shoot_rule.jurisdiction and budget.post_vfx <= 0:
                continue
            plan = evaluate_plan(budget, shoot_rule, post_rule, **kwargs)
            if plan is not None:
                plans.append(plan)

    singles = [p for p in plans if not p.is_split]
    if not singles:
        return None
    plans.sort(key=lambda p: -p.net_benefit)
    return SplitAnalysis(
        best=plans[0], best_single=max(singles, key=lambda p: p.net_benefit), plans=plans
    )
