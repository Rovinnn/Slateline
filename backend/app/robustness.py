"""Does the ranking survive what we don't know?

The tool refuses to guess, and prices the unknowns it refuses to guess about.
This is the third act: saying whether the answer actually depends on them.

Louisiana beats New Mexico by $8,347 on a $2M budget. That gap is smaller
than the swing from a single uncertain input — the producer's own estimate of
local hire moves it further than that. A recommendation is worth very little
if the reader can't tell whether it's a real margin or noise, and until now
nothing here could tell them.

Two questions, answered separately because they are different questions:

- **Where does it flip?** One input varied at a time, the rest held at their
  assumed values, scanning for the point the winner changes. This produces
  something actionable — "the ranking flips if local hire drops below 42%,
  and you assumed 55%" — which is a thing to go and confirm.
- **How often does it hold?** Every combination of every uncertain input.
  This produces a confidence statement rather than a threshold, and catches
  interactions that one-at-a-time sweeps miss.

Only inputs that are genuinely uncertain *for this comparison* are swept. The
transfer discount is irrelevant if neither jurisdiction has a transferable
credit, and sweeping it anyway would pad the count with combinations that
differ in nothing.

Nothing here estimates. Every figure is compute_benefit run again with a
different input, which is the same discipline the priced unknowns use.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from itertools import product
from typing import Callable, Optional

from .calculator import DEFAULT_TRANSFER_DISCOUNT, compute_benefit
from .models import (
    BudgetVector,
    CreditTimingAssumptions,
    JurisdictionRule,
    RelocationAssumptions,
)

#: Points sampled per input. Five is enough to find a crossing and keep the
#: full grid at 5^n rather than something that takes a visible moment.
SAMPLES = 5


@dataclass
class UncertainInput:
    """One thing we don't know, and the range it plausibly falls in."""

    name: str
    assumed: str
    low_label: str
    high_label: str
    #: Why this is uncertain rather than merely variable.
    because: str


@dataclass
class FlipPoint:
    """An input value at which the recommendation changes."""

    input_name: str
    #: Human-readable threshold, e.g. "below 42% local hire".
    threshold: str
    new_winner: str
    because: str


@dataclass
class Robustness:
    winner: str
    runner_up: str
    margin: float
    #: Combinations where the current winner still wins.
    winner_holds_in: int
    combinations_tested: int
    flips: list[FlipPoint]
    inputs_swept: list[UncertainInput]

    @property
    def is_robust(self) -> bool:
        return self.combinations_tested > 0 and self.winner_holds_in == self.combinations_tested


def _span(assumed: float, spread: float, lo: float, hi: float) -> list[float]:
    """SAMPLES values around `assumed`, clamped to a sane range."""
    low, high = max(lo, assumed - spread), min(hi, assumed + spread)
    if high <= low:
        return [assumed]
    step = (high - low) / (SAMPLES - 1)
    return [low + step * i for i in range(SAMPLES)]


def analyse_robustness(
    budget: BudgetVector,
    winner: JurisdictionRule,
    runner_up: JurisdictionRule,
    *,
    distances: Optional[dict[str, float]] = None,
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
    transfer_discount: float = DEFAULT_TRANSFER_DISCOUNT,
    today: Optional[date] = None,
) -> Optional[Robustness]:
    """Whether the top two hold their order across what we're unsure about."""
    distances = distances or {}
    timing = timing or CreditTimingAssumptions()

    def net(rule: JurisdictionRule, b: BudgetVector, t: CreditTimingAssumptions, d: float) -> float:
        result = compute_benefit(
            b,
            rule,
            distance_km=distances.get(rule.jurisdiction),
            assumptions=assumptions,
            timing=t,
            transfer_discount=d,
            today=today,
        )
        return result.net_benefit if result.computable else float("-inf")

    base_margin = net(winner, budget, timing, transfer_discount) - net(
        runner_up, budget, timing, transfer_discount
    )
    if base_margin <= 0:
        # Caller passed them in the wrong order; nothing meaningful to say.
        return None

    # Each entry: the input, and how to apply a value to (budget, timing, discount).
    Variant = tuple[UncertainInput, list[float], Callable[[float], tuple[BudgetVector, CreditTimingAssumptions, float]]]
    variants: list[Variant] = []

    # The producer's own estimate, and the single most influential number in
    # the model — it decides how much labour qualifies at all.
    variants.append(
        (
            UncertainInput(
                name="Local hire",
                assumed=f"{budget.resident_labor_pct:.0%}",
                low_label="lower",
                high_label="higher",
                because="you estimated this; nothing verified it",
            ),
            _span(budget.resident_labor_pct, 0.15, 0.0, 1.0),
            lambda v: (replace(budget, resident_labor_pct=v), timing, transfer_discount),
        )
    )

    # Only worth sweeping where a statute left it open on at least one side.
    if winner.fringes_qualify is None or runner_up.fringes_qualify is None:
        variants.append(
            (
                UncertainInput(
                    name="Fringe rate",
                    assumed=f"{budget.fringe_rate:.0%}",
                    low_label="lower",
                    high_label="higher",
                    because="payroll burden runs 22-35% and varies by union status",
                ),
                _span(budget.fringe_rate, 0.07, 0.0, 1.0),
                lambda v: (replace(budget, fringe_rate=v), timing, transfer_discount),
            )
        )

    # Pointless unless something here is actually sold at a discount.
    if "transferable" in (winner.credit_type, runner_up.credit_type):
        variants.append(
            (
                UncertainInput(
                    name="Credit sale price",
                    assumed=f"{transfer_discount:.0%} of face",
                    low_label="a worse broker price",
                    high_label="a better one",
                    because="transferable credits sell at 85-95 cents depending on the market",
                ),
                _span(transfer_discount, 0.05, 0.5, 1.0),
                lambda v: (budget, timing, v),
            )
        )

    # Only if we assumed a timeline rather than reading one.
    if winner.months_to_payment is None or runner_up.months_to_payment is None:
        variants.append(
            (
                UncertainInput(
                    name="Cost of capital",
                    assumed=f"{timing.discount_rate_annual:.0%}/yr",
                    low_label="cheaper money",
                    high_label="dearer money",
                    because="payment timing is assumed, so what the wait costs is too",
                ),
                _span(timing.discount_rate_annual, 0.06, 0.0, 0.4),
                lambda v: (budget, replace(timing, discount_rate_annual=v), transfer_discount),
            )
        )

    # --- one at a time: where does it flip, and at what value ---
    flips: list[FlipPoint] = []
    for spec, values, apply in variants:
        for value in values:
            b, t, d = apply(value)
            if net(winner, b, t, d) - net(runner_up, b, t, d) <= 0:
                direction = "below" if value < values[len(values) // 2] else "above"
                shown = f"{value:.0%}" if value <= 1.5 else f"{value:.2f}"
                flips.append(
                    FlipPoint(
                        input_name=spec.name,
                        threshold=f"{direction} {shown}",
                        new_winner=runner_up.jurisdiction,
                        because=spec.because,
                    )
                )
                break

    # --- every combination: how often does the winner hold ---
    holds = 0
    total = 0
    for combo in product(*[values for _, values, _ in variants]):
        b, t, d = budget, timing, transfer_discount
        for value, (_, _, apply) in zip(combo, variants):
            b2, t2, d2 = apply(value)
            # Each applier changes exactly one dimension; carry the others.
            b = b2 if b2 is not budget else b
            t = t2 if t2 is not timing else t
            d = d2 if d2 != transfer_discount else d
        total += 1
        if net(winner, b, t, d) - net(runner_up, b, t, d) > 0:
            holds += 1

    return Robustness(
        winner=winner.jurisdiction,
        runner_up=runner_up.jurisdiction,
        margin=base_margin,
        winner_holds_in=holds,
        combinations_tested=total,
        flips=flips,
        inputs_swept=[spec for spec, _, _ in variants],
    )
