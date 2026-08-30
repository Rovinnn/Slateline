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
    Recompute-on-slider-drag on the frontend should hit this endpoint, or
    port compute_benefit to the frontend in TypeScript for a zero-latency
    slider per the brief's "no network round trip for the recompute" note —
    decide once the frontend sensitivity sliders are being built.
    """
    verified_rule = verify_rule(rule)
    return compute_benefit(budget, verified_rule, distance_km, travel_time_hours, assumptions)


@app.post("/jurisdictions/search")
def search_jurisdictions(jurisdiction: str):
    raise HTTPException(
        status_code=501,
        detail=(
            "Layer 1 extraction not wired yet — needs GOOGLE_CLOUD_PROJECT, "
            "PARALLEL_API_KEY and GOOGLE_MAPS_API_KEY. See app/extraction/agent.py."
        ),
    )
