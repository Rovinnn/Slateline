"""The tools an ADK agent may call. Every one of them is a thin wrapper.

BUILD_BRIEF.md section 4 says "the agent must invoke the calculator tool",
which the REST pipeline satisfied only in spirit: it called compute_benefit
itself, in a fixed order, with no agent involved. These functions close that
gap without moving a single arithmetic decision into the model.

Two rules shape every signature below:

1. **Parameters are names and plain scalars, never figures the model would
   have to reproduce.** `compute_benefit_for("Georgia")` rather than
   `compute_benefit(budget={...}, rule={...})`. The values live in
   session.py; see that module for why this matters more than it looks.

2. **Return values are formatted for reading, not for re-entry.** A tool
   returns strings like "$199,621" alongside the raw number, because whatever
   the model says next is prose — and prose built from a pre-formatted string
   can't quietly lose a digit the way prose built from `199621.45` can.

The arithmetic itself is the same calculator.compute_benefit the REST API
calls, with the same tests behind it. The agent decides *what* to compute and
in what order. It never decides *what the answer is*.
"""

from __future__ import annotations

from ..calculator import compute_benefit
from ..constraints import constraint_gaps_for
from ..extraction.agent import extract_jurisdiction_rule
from ..extraction.challenge import apply_challenge, challenge_rule
from ..maps_client import get_distance
from ..models import BudgetVector
from ..verification import verify_rule
from . import session as session_store

#: Tools take this rather than an implicit global so a server can run several
#: conversations at once. The ADK agent passes it through from its own state.
DEFAULT_SESSION = "default"


def _money(value: float) -> str:
    return ("-$" if value < 0 else "$") + f"{abs(value):,.0f}"


def set_budget(
    total: float,
    atl_cast: float,
    atl_noncast: float,
    btl_labor: float,
    btl_nonlabor: float,
    post_vfx: float,
    shoot_days: int,
    crew_headcount: int,
    resident_labor_pct: float,
    home_base: str,
    session_id: str = DEFAULT_SESSION,
) -> dict:
    """Record the production's budget before any jurisdiction is compared.

    These are the producer's own figures, transcribed from what they said.
    Call this first; every other tool reads the budget from the session rather
    than taking it as an argument.

    Args:
        total: Total production budget in USD.
        atl_cast: Above-the-line cast salaries.
        atl_noncast: Above-the-line non-cast (director, producers, writers).
        btl_labor: Below-the-line crew wages.
        btl_nonlabor: Below-the-line non-labour spend (rentals, materials).
        post_vfx: Post-production and visual effects.
        shoot_days: Number of principal photography days.
        crew_headcount: Total crew size.
        resident_labor_pct: Share of below-the-line labour hired locally, 0.0 to 1.0.
        home_base: City the production is travelling from, e.g. "Los Angeles, CA".
        session_id: Conversation identifier.

    Returns:
        A confirmation of what was recorded, and any inconsistency worth raising.
    """
    state = session_store.get(session_id)
    state.budget = BudgetVector(
        total=total,
        atl_cast=atl_cast,
        atl_noncast=atl_noncast,
        btl_labor=btl_labor,
        btl_nonlabor=btl_nonlabor,
        post_vfx=post_vfx,
        shoot_days=shoot_days,
        crew_headcount=crew_headcount,
        resident_labor_pct=resident_labor_pct,
        home_base=home_base,
    )
    category_sum = atl_cast + atl_noncast + btl_labor + btl_nonlabor + post_vfx
    warning = ""
    if abs(total - category_sum) >= 1:
        # Reported, not corrected. `total` never enters the arithmetic — the
        # credit is computed from the category lines — so a mismatch is worth
        # flagging to the producer without blocking the comparison.
        warning = (
            f"the category lines sum to {_money(category_sum)}, not {_money(total)}; "
            "the credit is computed from the category lines"
        )
    return {
        "recorded": True,
        "category_sum": _money(category_sum),
        "home_base": home_base,
        "warning": warning,
    }


def search_jurisdiction(jurisdiction: str, session_id: str = DEFAULT_SESSION) -> dict:
    """Find and read a jurisdiction's film incentive program from live sources.

    Runs a live web search and extracts the statutory terms. Slow (roughly 30
    seconds) and costs quota, so call it once per jurisdiction — the result is
    kept for the rest of the conversation.

    Args:
        jurisdiction: State, province or country name, e.g. "Georgia".
        session_id: Conversation identifier.

    Returns:
        What the sources say about the program. Figures are summarised for
        reading; the full extracted rule stays in the session for the
        calculator to use.
    """
    rule = verify_rule(extract_jurisdiction_rule(jurisdiction))
    state = session_store.get(session_id)
    state.rules[rule.jurisdiction] = rule
    return {
        "jurisdiction": rule.jurisdiction,
        "program_name": rule.program_name,
        "headline_rate": f"{rule.base_rate:.1%}",
        "payout_mechanism": rule.credit_type,
        "funding_status": rule.pool_status,
        "minimum_spend": _money(rule.minimum_spend) if rule.minimum_spend else "none",
        "confidence": rule.confidence,
        "source_count": len(rule.sources),
        "primary_source": next((s.url for s in rule.sources if s.is_primary), ""),
    }


def compute_benefit_for(jurisdiction: str, session_id: str = DEFAULT_SESSION) -> dict:
    """Calculate what this jurisdiction's incentive is actually worth.

    This is the calculator. Do not attempt the arithmetic yourself — call this
    and report what it returns. It applies qualification by spend category,
    per-person wage caps, minimum-spend cliffs, payout mechanism, the discount
    from wrap to cash, and relocation cost.

    Args:
        jurisdiction: A jurisdiction already fetched with search_jurisdiction.
        session_id: Conversation identifier.

    Returns:
        The full walk from advertised rate to net benefit, or an explanation
        of why this program cannot be ranked.
    """
    state = session_store.get(session_id)
    if state.budget is None:
        return {"error": "No budget recorded yet — call set_budget first."}
    rule = state.rule_for(jurisdiction)
    if rule is None:
        return {"error": f"{jurisdiction} has not been searched yet — call search_jurisdiction first."}

    result = compute_benefit(
        state.budget,
        rule,
        distance_km=state.distances.get(rule.jurisdiction),
        assumptions=state.assumptions,
    )
    if not result.computable:
        return {
            "jurisdiction": rule.jurisdiction,
            "rankable": False,
            "reason": result.non_computable_reason,
        }
    return {
        "jurisdiction": rule.jurisdiction,
        "rankable": True,
        "qualifying_spend": _money(result.qualifying_spend),
        "gross_credit": _money(result.gross_credit),
        "realizable_after_monetisation": _money(result.realizable_credit),
        "months_to_payment": result.months_to_payment,
        "timing_is_assumed": result.timing_is_assumed,
        "value_today": _money(result.present_value),
        "relocation_cost": _money(result.relocation_cost),
        "net_benefit": _money(result.net_benefit),
        "caveats": result.caps_applied,
        "constraint_gaps": list(constraint_gaps_for(rule).values()),
    }


def compare_jurisdictions(session_id: str = DEFAULT_SESSION) -> dict:
    """Rank every jurisdiction searched so far by net benefit.

    Use this to answer "where should we shoot" rather than comparing the
    individual results yourself — the ordering is computed here.

    Args:
        session_id: Conversation identifier.

    Returns:
        The ranking, plus any jurisdictions that could not be ranked and why.
    """
    state = session_store.get(session_id)
    if state.budget is None:
        return {"error": "No budget recorded yet — call set_budget first."}
    if not state.rules:
        return {"error": "No jurisdictions searched yet — call search_jurisdiction first."}

    ranked, unrankable = [], []
    for rule in state.rules.values():
        result = compute_benefit(
            state.budget,
            rule,
            distance_km=state.distances.get(rule.jurisdiction),
            assumptions=state.assumptions,
        )
        if result.computable:
            ranked.append((result.net_benefit, rule, result))
        else:
            unrankable.append({"jurisdiction": rule.jurisdiction, "reason": result.non_computable_reason})

    ranked.sort(key=lambda t: -t[0])
    return {
        "ranking": [
            {
                "position": i,
                "jurisdiction": rule.jurisdiction,
                "headline_rate": f"{rule.base_rate:.1%}",
                "net_benefit": _money(result.net_benefit),
            }
            for i, (_, rule, result) in enumerate(ranked, 1)
        ],
        # Stated explicitly so the model reports the comparison rather than
        # recomputing a difference of its own from the strings above.
        "margin_over_runner_up": (
            _money(ranked[0][0] - ranked[1][0]) if len(ranked) >= 2 else "no runner-up to compare against"
        ),
        "cannot_be_ranked": unrankable,
    }


def get_travel_distance(jurisdiction: str, session_id: str = DEFAULT_SESSION) -> dict:
    """Look up real routed distance from the production's home base.

    Relocation cost is only included in a jurisdiction's net benefit once this
    has been called for it. Without it the comparison still works, but flights
    and ground transport are left out.

    Args:
        jurisdiction: A jurisdiction already fetched with search_jurisdiction.
        session_id: Conversation identifier.

    Returns:
        Routed distance and travel time from the home base.
    """
    state = session_store.get(session_id)
    if state.budget is None:
        return {"error": "No budget recorded yet — call set_budget first."}
    rule = state.rule_for(jurisdiction)
    if rule is None:
        return {"error": f"{jurisdiction} has not been searched yet — call search_jurisdiction first."}

    distance = get_distance(state.budget.home_base, rule.centroid_lat, rule.centroid_lng)
    state.distances[rule.jurisdiction] = distance.distance_km
    return {
        "jurisdiction": rule.jurisdiction,
        "from": state.budget.home_base,
        "distance_km": round(distance.distance_km),
        "travel_time_hours": round(distance.travel_time_hours, 1),
    }


def challenge_jurisdiction(jurisdiction: str, session_id: str = DEFAULT_SESSION) -> dict:
    """Search for evidence that what we found about a jurisdiction is wrong.

    A second, adversarial pass: it looks for suspensions, exhausted funding
    pools and pending amendments rather than for the program's terms. Finding
    nothing is a useful result and should be reported as such.

    Args:
        jurisdiction: A jurisdiction already fetched with search_jurisdiction.
        session_id: Conversation identifier.

    Returns:
        Contradictions found, or confirmation that none were.
    """
    state = session_store.get(session_id)
    rule = state.rule_for(jurisdiction)
    if rule is None:
        return {"error": f"{jurisdiction} has not been searched yet — call search_jurisdiction first."}

    report = challenge_rule(rule)
    challenged = verify_rule(apply_challenge(rule, report))
    state.rules[challenged.jurisdiction] = challenged
    return {
        "jurisdiction": rule.jurisdiction,
        "sources_checked": report.sources_checked,
        # The distinction the UI makes too: nothing found because nothing
        # contradicted it, versus nothing found because nothing was read.
        "verdict": (
            "contradicted" if report.material_findings
            else "corroborated" if report.challenged_cleanly
            else "could not be checked"
        ),
        "contradictions": [f.describe() for f in report.material_findings],
        "confidence_now": challenged.confidence,
    }


#: Everything the agent may do. Ordered as a conversation naturally runs.
AGENT_TOOLS = [
    set_budget,
    search_jurisdiction,
    get_travel_distance,
    compute_benefit_for,
    compare_jurisdictions,
    challenge_jurisdiction,
]
