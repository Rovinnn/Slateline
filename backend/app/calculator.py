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
from datetime import date
from typing import Optional

from .models import (
    BenefitBreakdown,
    BudgetVector,
    CreditTimingAssumptions,
    JurisdictionRule,
    RelocationAssumptions,
)

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


def _time_to_cash(
    realizable_credit: float,
    rule: JurisdictionRule,
    timing: CreditTimingAssumptions,
) -> tuple[float, float, int, bool, Optional[str]]:
    """What the credit is worth today, given when it actually arrives.

    Returns (present_value, audit_cost, months_used, months_were_assumed, note).

    The tool priced a credit as if it were cash on wrap day. It isn't: it's a
    claim realised after a return is filed, after an auditor signs off, and —
    for a transferable credit — after a buyer is found. Two programs with the
    same rate and the same payout mechanism can still differ by six figures on
    timing alone, which is enough to change which one wins.

    Discounted at an annual rate compounded over the wait, because that is
    what the money would earn (or what borrowing against the credit costs —
    productions routinely do exactly that rather than wait).

    The audit cost is subtracted before discounting: it is paid to *get* the
    credit, so it isn't money the production ever has the use of.
    """
    if realizable_credit <= 0:
        return realizable_credit, 0.0, 0, True, None

    months = rule.months_to_payment
    assumed = months is None
    if months is None:
        months = {
            "refundable": timing.months_refundable,
            "rebate": timing.months_rebate,
            "transferable": timing.months_transferable,
            "non_refundable": timing.months_non_refundable,
        }.get(rule.credit_type, timing.months_unknown)

    # None means no source addressed it, which is not the same as "no audit".
    audit_cost = timing.audit_cost if rule.audit_required else 0.0

    after_audit = realizable_credit - audit_cost
    discount_factor = (1.0 + timing.discount_rate_annual) ** (-months / 12.0)
    present_value = after_audit * discount_factor
    waiting_cost = after_audit - present_value

    source = "assumed for a " + (rule.credit_type or "unknown") + " credit" if assumed else "per source"
    note = (
        f"paid about {months} months after wrap ({source}) — waiting costs "
        f"${waiting_cost:,.0f} at {timing.discount_rate_annual:.0%} a year"
    )
    if audit_cost > 0:
        note += f", and a required audit costs ${audit_cost:,.0f}"

    return present_value, audit_cost, months, assumed, note


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


def _availability_block(rule: JurisdictionRule, today: date) -> Optional[str]:
    """Why this program's money can't actually be accessed, if it can't.

    BUILD_BRIEF.md section 1 is built on this: "they report the rate but not
    whether the annual funding pool is exhausted, the application window has
    closed, or the program is sunsetting. A 30% credit you can't access is a
    0% credit." Until now compute_benefit read none of these fields, so a
    closed program computed a full credit and could rank first — the exact
    failure the product exists to prevent.
    """
    if rule.pool_status == "closed":
        return (
            f"{rule.program_name}'s funding pool is closed — the credit cannot be claimed for "
            "this production regardless of rate."
        )
    if rule.sunset_date is not None and rule.sunset_date < today:
        return f"{rule.program_name} sunset on {rule.sunset_date.isoformat()} and is no longer available."
    if rule.application_deadline is not None and rule.application_deadline < today:
        return (
            f"{rule.program_name}'s application window closed on "
            f"{rule.application_deadline.isoformat()}."
        )
    return None


def _availability_warnings(rule: JurisdictionRule) -> list[str]:
    """Conditions that don't block a claim but qualify the recommendation."""
    notes = []
    if rule.pool_status == "capping_out":
        notes.append(
            "funding is capping out — the pool may be exhausted before this production applies; "
            "confirm remaining allocation with the film office"
        )
    elif rule.pool_status == "unknown":
        notes.append(
            "funding availability not confirmed in sources — this figure assumes the program can "
            "still be accessed"
        )
    if rule.under_review:
        notes.append("program is under legislative review; terms may change before you apply")
    return notes


def _impossible_inputs(
    budget: BudgetVector,
    rule: JurisdictionRule,
    distance_km: Optional[float],
    travel_time_hours: Optional[float],
    transfer_discount: float,
) -> Optional[tuple[str, str]]:
    """Inputs that cannot describe a real production or a real statute.

    Layer 2 is trusted precisely because a model never touches its arithmetic.
    But it still consumes numbers a model extracted, and arithmetic on a
    hallucinated input is just as wrong as arithmetic by a hallucination — it
    only looks more credible. The dangerous case is real: a statute saying
    "30%" read out as `base_rate: 30` computes a $57M credit on a $2M film and
    reports it with the same confidence as a correct answer.

    So these are checked, not clamped. Clamping 30 to 1.0 would silently
    invent a 100% credit; correcting it to 0.30 would guess at what the source
    meant. Refusing shows the producer a jurisdiction that couldn't be read
    and why, which is the honest outcome and the one the rest of this module
    already takes for currency, discretion and closed pools.

    Returns (reason, note) or None. Bounds are deliberately generous: this is
    a filter for the impossible, not a plausibility judgement.
    """
    rate_fields: list[tuple[str, float]] = [("base rate", rule.base_rate)]
    rate_fields += [(f"tier rate at ${t.threshold:,.0f}", t.rate) for t in rule.tiers]
    rate_fields += [(f'uplift "{u.condition}"', u.bonus_rate) for u in rule.uplifts]
    for label, rate in rate_fields:
        if not 0.0 <= rate <= 1.0:
            return (
                f"The extracted {label} is {rate:.1%}, which no incentive program offers. This "
                "usually means a percentage was recorded as a whole number (30 rather than 0.30) "
                "when the source was read. Rather than guess which was meant, this program is "
                "left out of the ranking — check the source link and re-run.",
                f"{label} of {rate:.1%} is outside the possible 0-100% range",
            )

    negative_caps = [
        (name, value)
        for name, value in (
            ("per-person wage cap", rule.per_person_wage_cap),
            ("minimum spend", rule.minimum_spend),
            ("per-project cap", rule.per_project_cap),
        )
        if value is not None and value < 0
    ]
    if negative_caps:
        name, value = negative_caps[0]
        return (
            f"The extracted {name} is negative (${value:,.0f}), which isn't a meaningful statutory "
            "limit. This program is left out of the ranking rather than computed against it.",
            f"negative {name} (${value:,.0f}) in the extracted rule",
        )

    spend_lines = {
        "above-the-line cast": budget.atl_cast,
        "above-the-line non-cast": budget.atl_noncast,
        "below-the-line labor": budget.btl_labor,
        "below-the-line non-labor": budget.btl_nonlabor,
        "post and VFX": budget.post_vfx,
    }
    negative_lines = [name for name, value in spend_lines.items() if value < 0]
    if negative_lines:
        return (
            f"The budget has negative spend on {negative_lines[0]}. A credit computed against it "
            "would be meaningless, so no figure is offered for this run.",
            f"negative {negative_lines[0]} spend in the budget",
        )

    # Shares, not amounts: outside [0,1] these silently produce a qualifying
    # spend larger than the entire budget, which reads as a plausible number.
    for label, share in (
        ("resident labor share", budget.resident_labor_pct),
        ("fringe rate", budget.fringe_rate),
        ("transferable-credit sale price", transfer_discount),
    ):
        if not 0.0 <= share <= 1.0:
            return (
                f"The {label} is {share:.1%}, outside the 0-100% range it has to fall in. "
                "Left out of the ranking rather than computed from it.",
                f"{label} of {share:.1%} is outside 0-100%",
            )

    if budget.shoot_days < 0 or budget.crew_headcount < 0:
        return (
            "The budget has a negative shoot-day count or crew headcount, so relocation cost "
            "can't be computed. Left out of the ranking.",
            "negative shoot days or crew headcount",
        )

    # A negative distance doesn't just look wrong — it subtracts a negative
    # relocation cost, making the jurisdiction appear *more* profitable the
    # more impossible the input is.
    for label, value in (("distance", distance_km), ("travel time", travel_time_hours)):
        if value is not None and value < 0:
            return (
                f"The {label} from home base came back negative ({value:,.1f}), which can't be "
                "true. Left out of the ranking rather than credited with a negative relocation cost.",
                f"negative {label} from home base ({value:,.1f})",
            )

    return None


def _refuse(
    rule: JurisdictionRule,
    reason: str,
    note: str,
    distance_km: Optional[float],
    travel_time_hours: Optional[float],
) -> BenefitBreakdown:
    """A jurisdiction this layer declines to compute.

    Refusing is a first-class outcome here, not an error path: the tool's
    whole claim is that its numbers are trustworthy, and a confidently wrong
    figure costs more than a visible gap. Every refusal carries `note` for the
    caps list and `reason` for the "can't verify" panel, which is where these
    land in the UI — listed, never silently dropped.
    """
    return BenefitBreakdown(
        jurisdiction=rule.jurisdiction,
        qualifying_spend=0.0,
        gross_credit=0.0,
        caps_applied=[note],
        distance_km=distance_km,
        travel_time_hours=travel_time_hours,
        relocation_cost=0.0,
        relocation_components={},
        realizable_credit=0.0,
        monetization_note=None,
        net_benefit=0.0,
        computable=False,
        non_computable_reason=reason,
    )


def compute_benefit(
    budget: BudgetVector,
    rule: JurisdictionRule,
    distance_km: Optional[float] = None,
    travel_time_hours: Optional[float] = None,
    assumptions: Optional[RelocationAssumptions] = None,
    cast_count: Optional[int] = None,
    transfer_discount: float = DEFAULT_TRANSFER_DISCOUNT,
    timing: Optional[CreditTimingAssumptions] = None,
    today: Optional[date] = None,
) -> BenefitBreakdown:
    """No I/O, no model calls. Deterministic given its arguments — pass
    `today` explicitly to pin the sunset/deadline comparisons; it defaults to
    the current date purely as a convenience, the same concession
    verification.assess_confidence makes.

    Applies the calculation rules in BUILD_BRIEF.md section 6, in order, and
    records every cap that bites in the returned caps_applied list.
    """
    assumptions = assumptions or RelocationAssumptions()
    timing = timing or CreditTimingAssumptions()
    today = today or date.today()
    caps_applied: list[str] = []

    impossible = _impossible_inputs(budget, rule, distance_km, travel_time_hours, transfer_discount)
    if impossible:
        reason, note = impossible
        return _refuse(rule, reason, note, distance_km, travel_time_hours)

    if rule.is_discretionary:
        return _refuse(
            rule,
            "Discretionary/jury-allocated program; benefit is not modelable.",
            "discretionary allocation — no statutory rate to compute",
            distance_km,
            travel_time_hours,
        )

    # The brief forbids FX conversion, so the honest move for a non-USD rule
    # isn't to convert — it's to refuse. Comparing e.g. Ireland's EUR figures
    # against USD ones as if they were the same currency (which every field
    # below silently would, with no unit anywhere to catch it) would be a
    # confidently wrong number, exactly what this tool exists to avoid.
    if rule.currency != "USD":
        return _refuse(
            rule,
            f"This program's figures are stated in {rule.currency}, not USD, and this tool "
            "doesn't convert currencies — comparing them directly against USD-denominated "
            "jurisdictions would be misleading. Confirm the USD-equivalent value with the film office.",
            f"figures are denominated in {rule.currency}, not USD",
            distance_km,
            travel_time_hours,
        )

    unavailable = _availability_block(rule, today)
    if unavailable:
        return _refuse(rule, unavailable, unavailable, distance_km, travel_time_hours)

    q = rule.qualifying
    cast_count = cast_count if cast_count is not None else assumed_cast_count(budget.crew_headcount)
    caps_applied.extend(_availability_warnings(rule))

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
    present_value, audit_cost, months_used, timing_assumed, timing_note = _time_to_cash(
        realizable_credit, rule, timing
    )

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
        audit_cost=audit_cost,
        months_to_payment=months_used,
        timing_is_assumed=timing_assumed,
        present_value=present_value,
        timing_note=timing_note,
        # Nets the present value, not face value and not even the realizable
        # figure: money arriving in 18 months is worth less than money now,
        # and relocation is spent up front in today's dollars. Comparing the
        # two without discounting would flatter slow-paying programs.
        net_benefit=present_value - relocation_cost,
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
