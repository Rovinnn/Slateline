"""The unknowns, priced — so a producer knows which call to make first.

Layer 2 already refuses to guess. Every time it declines, it leaves a note:
an uplift it can't machine-check, fringes the sources never addressed, a
funding pool whose remaining balance nobody published. Those notes were
honest and completely inert — a list of caveats at the bottom of a card,
indistinguishable from each other, none of them telling the reader whether
the unknown was worth $2,000 or $200,000.

They are not caveats. They are **the highest-value phone calls available**,
and the tool can price every one of them.

The method is deliberately dull: for each unknown, ask the calculator what the
answer would be if it resolved the other way, and subtract. No new arithmetic,
no estimate of its own — `worth` is a difference between two runs of the same
`compute_benefit` that produced the figure on screen. A question that turns
out not to move the number doesn't get asked.

Upside and risk are both included and signed. "Confirm the uplift, it's worth
+$200,000" and "confirm the pool is open, or the whole $175,722 goes" are the
same kind of fact, and a producer needs the second one more.
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

#: Below this, an unknown isn't worth a producer's afternoon.
MATERIALITY = 1_000.0


@dataclass
class OpenQuestion:
    """One thing worth confirming, and what it's worth."""

    question: str
    #: Signed dollars. Positive is upside if confirmed; negative is what's at
    #: risk if the assumption turns out to be wrong.
    worth: float
    #: How the figure was derived, so it can be argued with.
    basis: str
    #: Who actually answers this.
    ask: str

    @property
    def is_risk(self) -> bool:
        return self.worth < 0


def open_questions(
    budget: BudgetVector,
    rule: JurisdictionRule,
    benefit: BenefitBreakdown,
    *,
    distance_km: Optional[float] = None,
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
    today: Optional[date] = None,
) -> list[OpenQuestion]:
    """Everything unresolved about this jurisdiction, priced and ranked.

    Ordered by absolute value, because the point is what to do next.
    """
    if not benefit.computable:
        return []

    kwargs = dict(
        distance_km=distance_km, assumptions=assumptions, timing=timing, today=today
    )

    def net_if(**changes) -> float:
        """What the net benefit would be under a different reading of the rule."""
        return compute_benefit(budget, replace(rule, **changes), **kwargs).net_benefit

    base = benefit.net_benefit
    questions: list[OpenQuestion] = []

    # --- uplifts the calculator logged but refused to apply ---
    for uplift in rule.uplifts:
        if uplift.machine_checkable:
            continue
        gain = net_if(base_rate=rule.base_rate + uplift.bonus_rate, uplifts=[]) - base
        if gain >= MATERIALITY:
            questions.append(
                OpenQuestion(
                    question=f'Does this production qualify for the "{uplift.condition}" uplift?',
                    worth=gain,
                    basis=(
                        f"+{uplift.bonus_rate:.0%} on qualifying spend, carried through monetisation, "
                        "the wait to be paid and relocation"
                    ),
                    ask=f"{rule.jurisdiction} film office",
                )
            )

    # --- fringes: 22-35% of wages, and nobody said whether they count ---
    if rule.fringes_qualify is None and budget.fringe_rate > 0:
        gain = net_if(fringes_qualify=True) - base
        if gain >= MATERIALITY:
            questions.append(
                OpenQuestion(
                    question="Do employer payroll fringes count as qualified spend?",
                    worth=gain,
                    basis=(
                        f"payroll burden at {budget.fringe_rate:.0%} of qualifying wages; the sources "
                        "retrieved don't address it either way, so it's currently left out"
                    ),
                    ask=f"{rule.jurisdiction} film office or your production accountant",
                )
            )

    # --- how the credit pays out, when nobody stated it ---
    if rule.credit_type == "unknown":
        downside = net_if(credit_type="transferable") - base
        if abs(downside) >= MATERIALITY:
            questions.append(
                OpenQuestion(
                    question="Is this credit refundable, or does it have to be sold at a discount?",
                    worth=downside,
                    basis=(
                        "currently valued at face. If it's transferable you sell it to a taxpayer at "
                        "a broker discount, and this is what that costs"
                    ),
                    ask=f"{rule.jurisdiction} film office",
                )
            )

    # --- a non-refundable credit is worth nothing without in-state liability ---
    if rule.credit_type == "non_refundable":
        questions.append(
            OpenQuestion(
                question="Does your company have in-state tax liability to offset?",
                worth=-benefit.realizable_credit,
                basis=(
                    "a non-refundable credit only offsets tax you already owe in the jurisdiction. "
                    "An out-of-state production usually owes none, in which case this is worth nothing"
                ),
                ask="your production accountant",
            )
        )

    # --- availability: the product's own wedge, priced ---
    if rule.pool_status in ("unknown", "capping_out"):
        phrasing = (
            "Is there still money left in this year's allocation?"
            if rule.pool_status == "capping_out"
            else "Is the annual funding pool still open?"
        )
        questions.append(
            OpenQuestion(
                question=phrasing,
                worth=-base,
                basis=(
                    "a credit you can't be allocated is worth nothing, whatever the rate. This is the "
                    "entire net benefit, at risk until someone confirms availability"
                ),
                ask=f"{rule.jurisdiction} film office",
            )
        )

    if rule.under_review:
        questions.append(
            OpenQuestion(
                question="Has the program survived its current legislative review unchanged?",
                worth=-base,
                basis="sources indicate the program is under review; terms can change mid-session",
                ask=f"{rule.jurisdiction} film office",
            )
        )

    # --- timing we assumed rather than read ---
    if benefit.timing_is_assumed and timing is not None or benefit.timing_is_assumed:
        faster = compute_benefit(
            budget,
            replace(rule, months_to_payment=max(1, benefit.months_to_payment // 2)),
            **kwargs,
        ).net_benefit
        gain = faster - base
        if gain >= MATERIALITY:
            questions.append(
                OpenQuestion(
                    question=f"How long does payment actually take? We assumed {benefit.months_to_payment} months.",
                    worth=gain,
                    basis=(
                        f"worth this much if it pays in half the time. Statutes rarely state a "
                        "timeline, so this is an assumption rather than something we read"
                    ),
                    ask=f"{rule.jurisdiction} film office or a production accountant who has claimed there",
                )
            )

    questions.sort(key=lambda q: -abs(q.worth))
    return questions
