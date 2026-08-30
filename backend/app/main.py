"""FastAPI app.

/health and /compute are wired and testable today with zero credentials.
/jurisdictions/search needs GOOGLE_CLOUD_PROJECT + PARALLEL_API_KEY +
GOOGLE_MAPS_API_KEY before it does anything real — see build order steps 1, 3, 5
in BUILD_BRIEF.md.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .calculator import compute_benefit
from .models import BenefitBreakdown, BudgetVector, JurisdictionRule, RelocationAssumptions
from .seed_jurisdictions import SEED_JURISDICTIONS
from .verification import verify_rule

app = FastAPI(title="Incentive Verifier API")

# TODO: narrow allow_origins to the deployed frontend URL before shipping.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/compute", response_model=BenefitBreakdown)
def compute(
    budget: BudgetVector,
    rule: JurisdictionRule,
    distance_km: Optional[float] = None,
    travel_time_hours: Optional[float] = None,
    assumptions: Optional[RelocationAssumptions] = None,
) -> BenefitBreakdown:
    """Layer 2, exposed directly. Given an already-extracted rule (or a
    hand-written fixture, for now) and a distance, returns the net benefit.
    The frontend's sensitivity sliders and relocation-assumptions panel both
    debounce and hit this endpoint on every change, rather than porting
    compute_benefit to TypeScript — "no network round trip for the recompute"
    in the brief means no model call, not no HTTP call; duplicating the
    arithmetic into a second language would undermine the "one deterministic
    Python place" credibility claim in section 4.
    """
    verified_rule = verify_rule(rule)
    return compute_benefit(budget, verified_rule, distance_km, travel_time_hours, assumptions)


@app.post("/compute/batch", response_model=list[BenefitBreakdown])
def compute_batch(
    budgets: list[BudgetVector],
    rule: JurisdictionRule,
    distance_km: Optional[float] = None,
    travel_time_hours: Optional[float] = None,
    assumptions: Optional[RelocationAssumptions] = None,
) -> list[BenefitBreakdown]:
    """compute_benefit over a list of budgets against one rule, in a single
    round trip. Used by the frontend's breakeven sparkline (BUILD_BRIEF.md
    section 7) to scan ATL spend across ~50 points without one HTTP call per
    point. Same pure function as /compute, just batched — no new arithmetic.
    """
    verified_rule = verify_rule(rule)
    return [compute_benefit(b, verified_rule, distance_km, travel_time_hours, assumptions) for b in budgets]


@app.post("/jurisdictions/search")
def search_jurisdictions(jurisdiction: str):
    raise HTTPException(
        status_code=501,
        detail=(
            "Layer 1 extraction not wired yet — needs GOOGLE_CLOUD_PROJECT, "
            "PARALLEL_API_KEY and GOOGLE_MAPS_API_KEY. See app/extraction/agent.py."
        ),
    )


@app.get("/jurisdictions/seed", response_model=list[JurisdictionRule])
def list_seed_jurisdictions() -> list[JurisdictionRule]:
    """Hand-curated real jurisdictions (see app/seed_jurisdictions.py) — a
    manual stand-in for /jurisdictions/search until Layer 1 extraction is
    live. Confidence is recomputed here, same as /compute does for a
    caller-supplied rule.
    """
    return [verify_rule(rule) for rule in SEED_JURISDICTIONS]
