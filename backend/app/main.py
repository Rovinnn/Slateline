"""FastAPI app.

/health and /compute are wired and testable today with zero credentials.
/jurisdictions/search and /distance need GOOGLE_CLOUD_PROJECT + PARALLEL_API_KEY
+ GOOGLE_MAPS_API_KEY — see build order steps 1, 3, 5 in BUILD_BRIEF.md.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Optional

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .calculator import compute_benefit
from .constraints import constraint_gaps_for
from .extraction.agent import extract_jurisdiction_rule
from .extraction.budget_parser import MAX_PDF_BYTES, ParsedBudget, parse_budget_pdf
from .maps_client import DistanceResult, get_distance
from .models import BenefitBreakdown, BudgetVector, JurisdictionRule, RelocationAssumptions
from .verification import verify_rule


def _verify_and_annotate(rule: JurisdictionRule) -> JurisdictionRule:
    """verify_rule (Layer 3 confidence) plus constraint_gaps_for (Layer 3
    constraint check) — the two rule-derived, no-model-call passes every
    rule goes through before it reaches the frontend, seed or searched.
    """
    verified = verify_rule(rule)
    return replace(verified, constraint_gaps=constraint_gaps_for(verified))

app = FastAPI(title="Incentive Verifier API")

# Firebase Hosting serves the deployed frontend on both domains below; local
# dev (`npm run dev`) needs its own origin too. FRONTEND_ORIGINS lets a
# redeploy add an origin (e.g. a custom domain) without editing code.
_default_origins = [
    "https://zeta-structure-437412-v7.web.app",
    "https://zeta-structure-437412-v7.firebaseapp.com",
    "http://localhost:5173",
]
allow_origins = os.environ.get("FRONTEND_ORIGINS", ",".join(_default_origins)).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
    # Body(...), not a bare default: a bare `float | None = None` on a POST
    # handler is classified as a QUERY parameter by FastAPI, not a body
    # field, since only Pydantic-model/dataclass-typed params are inferred
    # as body by default. The frontend has always sent these two inside the
    # JSON body (see lib/api.ts's computeBenefit), so without Body(...) here
    # they silently read as None on every call — distance_km looked wired
    # end to end (it's in the OpenAPI schema, curl with ?distance_km=...
    # works) but the actual app never sent it that way.
    distance_km: Optional[float] = Body(default=None),
    travel_time_hours: Optional[float] = Body(default=None),
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
    distance_km: Optional[float] = Body(default=None),
    travel_time_hours: Optional[float] = Body(default=None),
    assumptions: Optional[RelocationAssumptions] = None,
) -> list[BenefitBreakdown]:
    """compute_benefit over a list of budgets against one rule, in a single
    round trip. Used by the frontend's breakeven sparkline (BUILD_BRIEF.md
    section 7) to scan ATL spend across ~50 points without one HTTP call per
    point. Same pure function as /compute, just batched — no new arithmetic.
    """
    verified_rule = verify_rule(rule)
    return [compute_benefit(b, verified_rule, distance_km, travel_time_hours, assumptions) for b in budgets]


@app.post("/jurisdictions/search", response_model=JurisdictionRule)
def search_jurisdictions(jurisdiction: str) -> JurisdictionRule:
    """Layer 1, live: Parallel search + a forced-function-call Gemini extraction
    (see app/extraction/agent.py), then Layer 3 verification. Any failure here
    is an external service (Parallel or Vertex), not a client error, so it
    surfaces as 502 with the underlying message rather than 500.
    """
    try:
        rule = extract_jurisdiction_rule(jurisdiction)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not extract a jurisdiction rule for {jurisdiction!r}: {exc}",
        ) from exc
    return _verify_and_annotate(rule)


@app.post("/budget/parse", response_model=ParsedBudget)
async def parse_budget(file: UploadFile = File(...)) -> ParsedBudget:
    """Reads an uploaded budget PDF into a pre-filled BudgetVector plus the
    provenance note for each figure (see extraction/budget_parser.py).

    A bad file is the caller's problem (400); a Gemini failure is ours (502).
    Collapsing both into 500 would tell a producer with a scanned, text-free
    topsheet that the server broke, when the actionable answer is "this PDF
    has no text layer — type the numbers in instead".
    """
    contents = await file.read()
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB limit.")
    try:
        return parse_budget_pdf(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read that budget: {exc}") from exc


@app.get("/distance", response_model=DistanceResult)
def distance(origin: str, destination_lat: float, destination_lng: float) -> DistanceResult:
    """Hub-to-hub distance/time via Google Maps (app/maps_client.py), for the
    frontend to fetch once per (home_base, jurisdiction) pair and cache,
    rather than /compute calling Maps itself on every sensitivity-slider
    recompute — that would add an external network round trip (and quota
    cost) on every drag tick, which is exactly what BUILD_BRIEF.md section 7's
    "no network round trip for the recompute" is about.
    """
    try:
        return get_distance(origin, destination_lat, destination_lng)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Maps distance lookup failed: {exc}") from exc
