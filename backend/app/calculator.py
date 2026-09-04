"""Layer 2: deterministic benefit calculation. No I/O, no model calls.

The language model (Layer 1) only ever populates JurisdictionRule objects.
This module is the only place a benefit figure is ever computed, and it is
the project's main credibility claim — see BUILD_BRIEF.md section 1 and 6.

Two deliberate departures from the brief's illustrative sketch, both flagged
here rather than made silently:

1. compute_benefit() takes distance_km / travel_time_hours / assumptions as
   plain-data parameters instead of the two-argument sketch in section 4.
   Distance comes from the Maps API (I/O), which has to happen *before* this
   function runs to keep the function itself pure — the brief's own build
   order (step 5, "relocation cost via Maps, folded into net_benefit") implies
   the same thing.
2. rule.qualifying uses category keys (atl_cast / atl_noncast /
   btl_labor_resident / btl_labor_nonresident / btl_nonlabor / post_vfx)
   rather than the brief's illustrative "atl_resident"/"atl_nonresident"
   example — BudgetVector has no per-person resident flag on ATL, only a
   resident_labor_pct split on BTL labor, so the qualifying dict is keyed to
   the categories BudgetVector actually has.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Optional

from .models import BenefitBreakdown, BudgetVector, JurisdictionRule, RelocationAssumptions

QUALIFYING_KEYS = (
    "atl_cast",
    "atl_noncast",
    "btl_labor_resident",
    "btl_labor_nonresident",
    "btl_nonlabor",
    "post_vfx",
)


def assumed_cast_count(crew_headcount: int) -> int:
    """BudgetVector carries no cast-headcount field, so the per-person wage
    cap needs a stand-in ratio to divide atl_cast by. 8% of crew, clamped to
    4-24, matches the design prototype's heuristic. Must stay visible/editable
    in the UI per the brief ("document the assumption in the UI").
    """
    return max(4, min(24, round(crew_headcount * 0.08)))


def _apply_wage_cap(atl_cast: float, cap: Optional[float], cast_count: int) -> tuple[float, Optional[str]]:
    if cap is None or cast_count <= 0:
        return atl_cast, None
    per_person = atl_cast / cast_count
    if per_person <= cap:
        return atl_cast, None
    capped_total = cap * cast_count
    reduction = atl_cast - capped_total
    note = (
        f"per-person wage cap (${cap:,.0f}) reduced qualifying ATL cast by "
        f"${reduction:,.0f} (assumed {cast_count} cast members from crew size)"
    )
    return capped_total, note


def _select_rate(qualifying_spend: float, rule: JurisdictionRule) -> tuple[float, Optional[str]]:
    if not rule.tiers:
        return rule.base_rate, None
    applicable = [t for t in rule.tiers if t.threshold <= qualifying_spend]
    if not applicable:
        return rule.base_rate, None
    tier = max(applicable, key=lambda t: t.threshold)
    return tier.rate, f"tier rate {tier.rate:.1%} applies above ${tier.threshold:,.0f} qualifying spend"


_PCT_CONDITION_RE = re.compile(r"(local hire|resident)[^%\d]*?(>=|>|<=|<)\s*(\d+)\s*%", re.IGNORECASE)


def _evaluate_uplift_condition(condition: str, budget: BudgetVector) -> Optional[bool]:
    """Tiny grammar for the one condition type BudgetVector can actually
    answer: a resident/local-hire percentage threshold. Anything else returns
    None (unknown) even when Layer 1 flagged it machine_checkable — the
    extraction schema has no structured field to check other condition types
    against, so those still land as an unquantified note rather than being
    silently skipped or silently applied.
    """
    m = _PCT_CONDITION_RE.search(condition)
    if not m:
        return None
    op, threshold = m.group(2), float(m.group(3))
    pct = budget.resident_labor_pct * 100
    if op == ">":
        return pct > threshold
    if op == ">=":
        return pct >= threshold
    if op == "<":
        return pct < threshold
    return pct <= threshold  # "<="


# Transferable credits are sold to a taxpayer with in-state liability, at a
# broker discount. Market clearing is roughly 88-95 cents on the dollar, with
# 88-91 typical after broker fees for a clean audited credit. This is market
# data, not a statutory fact, so it's an editable assumption rather than
# something the model is asked to state.
DEFAULT_TRANSFER_DISCOUNT = 0.90


def _monetize(
    gross_credit: float, credit_type: str, transfer_discount: float
) -> tuple[float, Optional[str]]:
    """Face value -> what the production can actually bank.

    The distinction the tool got wrong until now: a $400k refundable credit
    and a $400k transferable one are not the same asset, and ranking them as
    equal systematically favours transferable states.
    """
    if gross_credit <= 0:
        return gross_credit, None

    if credit_type in ("refundable", "rebate"):
        return gross_credit, "paid at face value — no broker discount"

    if credit_type == "transferable":
        realizable = gross_credit * transfer_discount
        return realizable, (
            f"transferable credit — sold at about {transfer_discount:.0%} of face, "
            f"costing ${gross_credit - realizable:,.0f}"
        )

    if credit_type == "non_refundable":
        # Deliberately not zeroed: it's worth face value to a production with
        # in-state liability and close to nothing to one without, and which
        # applies is a fact about the production company, not the statute.
        # Flag it rather than guess.
        return gross_credit, (
            "non-refundable — only worth this much against in-state tax liability; "
            "an out-of-state production may realise far less"
        )

    return gross_credit, "payout mechanism not stated in sources — shown at face value"


def compute_benefit(
    budget: BudgetVector,
    rule: JurisdictionRule,
    distance_km: Optional[float] = None,
    travel_time_hours: Optional[float] = None,
    assumptions: Optional[RelocationAssumptions] = None,
    cast_count: Optional[int] = None,
    transfer_discount: float = DEFAULT_TRANSFER_DISCOUNT,
) -> BenefitBreakdown:
    """Pure function. No I/O, no model calls, fully deterministic.

    Applies the calculation rules in BUILD_BRIEF.md section 6, in order, and
    records every cap that bites in the returned caps_applied list.
    """
    assumptions = assumptions or RelocationAssumptions()
    caps_applied: list[str] = []

    if rule.is_discretionary:
        return BenefitBreakdown(
            jurisdiction=rule.jurisdiction,
            qualifying_spend=0.0,
            gross_credit=0.0,
            caps_applied=["discretionary allocation — no statutory rate to compute"],
            distance_km=distance_km,
            travel_time_hours=travel_time_hours,
            relocation_cost=0.0,
            relocation_components={},
            realizable_credit=0.0,
            monetization_note=None,
            net_benefit=0.0,
            computable=False,
            non_computable_reason="Discretionary/jury-allocated program; benefit is not modelable.",
        )

    q = rule.qualifying
    cast_count = cast_count if cast_count is not None else assumed_cast_count(budget.crew_headcount)

    atl_cast_capped, wage_note = _apply_wage_cap(budget.atl_cast, rule.per_person_wage_cap, cast_count)
    if wage_note:
        caps_applied.append(wage_note)

    resident_btl = budget.btl_labor * budget.resident_labor_pct
    nonresident_btl = budget.btl_labor * (1 - budget.resident_labor_pct)

    # Split labor from non-labor: payroll burden attaches to wages only, never
    # to rentals, materials or post services.
    qualifying_labor = (
        (atl_cast_capped if q.get("atl_cast") else 0.0)
        + (budget.atl_noncast if q.get("atl_noncast") else 0.0)
        + (resident_btl if q.get("btl_labor_resident") else 0.0)
        + (nonresident_btl if q.get("btl_labor_nonresident") else 0.0)
    )
    qualifying_non_labor = (
        (budget.btl_nonlabor if q.get("btl_nonlabor") else 0.0)
        + (budget.post_vfx if q.get("post_vfx") else 0.0)
    )

    # Fringes are computed on the labor that already qualifies — burden on
    # excluded wages can't itself qualify.
    fringes = qualifying_labor * max(0.0, budget.fringe_rate)
    if rule.fringes_qualify is True:
        qualifying_spend = qualifying_labor + qualifying_non_labor + fringes
        caps_applied.append(
            f"fringes qualify — ${fringes:,.0f} of payroll burden included "
            f"at {budget.fringe_rate:.0%} of qualifying wages"
        )
    else:
        qualifying_spend = qualifying_labor + qualifying_non_labor
        if fringes > 0:
            if rule.fringes_qualify is False:
                caps_applied.append(
                    f"fringes excluded — ${fringes:,.0f} of payroll burden doesn't qualify here"
                )
            else:
                # Unknown is treated as excluded — the conservative direction —
                # but doing that silently would understate the credit with no
                # explanation. Say so instead.
                caps_applied.append(
                    f"unquantified: sources don't state whether fringes qualify — "
                    f"${fringes:,.0f} of payroll burden left out; confirm with the film office"
                )

    if rule.minimum_spend is not None and qualifying_spend < rule.minimum_spend:
        # Cliff, not a proportional reduction — getting this wrong invalidates the tool.
        caps_applied.append(
            f"qualifying spend ${qualifying_spend:,.0f} is below the ${rule.minimum_spend:,.0f} minimum "
            "— credit is $0 (cliff, not prorated)"
        )
        gross_credit = 0.0
    else:
        rate, tier_note = _select_rate(qualifying_spend, rule)
        if tier_note:
            caps_applied.append(tier_note)
        gross_credit = qualifying_spend * rate

        for uplift in rule.uplifts:
            if not uplift.machine_checkable:
                caps_applied.append(
                    f'unquantified: uplift "{uplift.condition}" (+{uplift.bonus_rate:.1%}) '
                    "requires manual confirmation, not machine-checkable"
                )
                continue
            met = _evaluate_uplift_condition(uplift.condition, budget)
            if met is None:
                caps_applied.append(
                    f'unquantified: uplift "{uplift.condition}" (+{uplift.bonus_rate:.1%}) '
                    "flagged machine-checkable but condition text isn't in a recognized form"
                )
            elif met:
                gross_credit += qualifying_spend * uplift.bonus_rate

        if rule.per_project_cap is not None and gross_credit > rule.per_project_cap:
            caps_applied.append(
                f"per-project cap of ${rule.per_project_cap:,.0f} reduced gross credit by "
                f"${gross_credit - rule.per_project_cap:,.0f}"
            )
            gross_credit = rule.per_project_cap

    travelling_crew = budget.crew_headcount * assumptions.imported_crew_pct
    if distance_km is not None and distance_km > assumptions.flight_threshold_km:
        transport = travelling_crew * assumptions.flight_cost_per_person
    elif distance_km is not None:
        transport = travelling_crew * distance_km * assumptions.ground_cost_per_person_per_km
    else:
        transport = 0.0
    lodging = travelling_crew * budget.shoot_days * (
        assumptions.per_diem_per_person_per_day + assumptions.hotel_per_person_per_day
    )
    relocation_cost = transport + lodging + assumptions.equipment_shipping_base

    realizable_credit, monetization_note = _monetize(gross_credit, rule.credit_type, transfer_discount)

    return BenefitBreakdown(
        jurisdiction=rule.jurisdiction,
        qualifying_spend=qualifying_spend,
        gross_credit=gross_credit,
        caps_applied=caps_applied,
        distance_km=distance_km,
        travel_time_hours=travel_time_hours,
        relocation_cost=relocation_cost,
        relocation_components={
            "transport": transport,
            "lodging": lodging,
            "equipment_shipping": assumptions.equipment_shipping_base,
        },
        realizable_credit=realizable_credit,
        monetization_note=monetization_note,
        # Nets the realizable figure, not face value: that's the money that
        # actually reaches the production.
        net_benefit=realizable_credit - relocation_cost,
        computable=True,
        non_computable_reason=None,
    )


def sensitivity_sweep(
    budget: BudgetVector,
    rule: JurisdictionRule,
    field_name: str,
    values: list[float],
    distance_km: Optional[float] = None,
    travel_time_hours: Optional[float] = None,
    assumptions: Optional[RelocationAssumptions] = None,
) -> list[BenefitBreakdown]:
    """Sensitivity analysis is compute_benefit called in a loop across a
    parameter range on BudgetVector. Nothing more sophisticated is needed.
    """
    results = []
    for value in values:
        swept_budget = replace(budget, **{field_name: value})
        results.append(
            compute_benefit(swept_budget, rule, distance_km, travel_time_hours, assumptions)
        )
    return results
