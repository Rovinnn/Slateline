"""FastAPI app.

/health and /compute are wired and testable today with zero credentials.
/jurisdictions/search and /distance need GOOGLE_CLOUD_PROJECT + PARALLEL_API_KEY
+ GOOGLE_MAPS_API_KEY — see build order steps 1, 3, 5 in BUILD_BRIEF.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Optional

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import cache
from .calculator import DEFAULT_TRANSFER_DISCOUNT, compute_benefit
from .constraints import constraint_gaps_for
from .extraction.agent import extract_jurisdiction_rule
from .extraction.challenge import ChallengeReport, apply_challenge, challenge_rule
from .extraction.budget_parser import MAX_PDF_BYTES, ParsedBudget, parse_budget_pdf
from .maps_client import DistanceResult, get_distance
from .jurisdictions import SUGGESTED, SuggestedJurisdiction, grouped
from .questions import OpenQuestion, open_questions
from .split import SplitPlan, analyse_splits
from .models import (
    BenefitBreakdown,
    BudgetVector,
    CreditTimingAssumptions,
    CurrencyAssumptions,
    JurisdictionRule,
    RelocationAssumptions,
)
from .verification import verify_rule


def _verify_and_annotate(rule: JurisdictionRule) -> JurisdictionRule:
    """verify_rule (Layer 3 confidence) plus constraint_gaps_for (Layer 3
    constraint check) — the two rule-derived, no-model-call passes every
    rule goes through before it reaches the frontend, seed or searched.
    """
    verified = verify_rule(rule)
    return replace(verified, constraint_gaps=constraint_gaps_for(verified))

@dataclass
class ChallengeResponse:
    """The annotated rule plus what the challenge actually found.

    Both halves matter: the rule carries any conflicts and the downgraded
    confidence, while the report says whether the pass had sources to read at
    all — "we checked and found nothing" and "we couldn't check" must never
    render as the same thing.
    """

    rule: JurisdictionRule
    report: ChallengeReport


app = FastAPI(title="Slateline API")

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
    # When the credit turns into money. Editable for the same reason
    # `assumptions` is: it changes the answer, so it can't be a hidden
    # constant (BUILD_BRIEF.md section 6).
    timing: Optional[CreditTimingAssumptions] = None,
    # Exchange rates, editable for the same reason: a production with its own
    # treasury rate should use it rather than ours.
    currency: Optional[CurrencyAssumptions] = None,
    # Both were computed but unreachable from any client. The transfer
    # discount decides what a transferable credit is worth, and cast_count
    # drives the per-person wage cap off an 8%-of-crew guess — consequential
    # assumptions have to be editable, per BUILD_BRIEF.md section 6.
    transfer_discount: float = Body(default=DEFAULT_TRANSFER_DISCOUNT),
    cast_count: Optional[int] = Body(default=None),
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
    return compute_benefit(
        budget,
        verified_rule,
        distance_km,
        travel_time_hours,
        assumptions,
        cast_count=cast_count,
        transfer_discount=transfer_discount,
        timing=timing,
        currency=currency,
    )


@app.post("/compute/batch", response_model=list[BenefitBreakdown])
def compute_batch(
    budgets: list[BudgetVector],
    rule: JurisdictionRule,
    distance_km: Optional[float] = Body(default=None),
    travel_time_hours: Optional[float] = Body(default=None),
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
    transfer_discount: float = Body(default=DEFAULT_TRANSFER_DISCOUNT),
    cast_count: Optional[int] = Body(default=None),
) -> list[BenefitBreakdown]:
    """compute_benefit over a list of budgets against one rule, in a single
    round trip. Used by the frontend's breakeven sparkline (BUILD_BRIEF.md
    section 7) to scan ATL spend across ~50 points without one HTTP call per
    point. Same pure function as /compute, just batched — no new arithmetic.
    """
    verified_rule = verify_rule(rule)
    return [
        compute_benefit(
            b,
            verified_rule,
            distance_km,
            travel_time_hours,
            assumptions,
            cast_count=cast_count,
            transfer_discount=transfer_discount,
            timing=timing,
        )
        for b in budgets
    ]


@app.post("/jurisdictions/search", response_model=JurisdictionRule)
def search_jurisdictions(jurisdiction: str, refresh: bool = False) -> JurisdictionRule:
    """Layer 1, live: Parallel search + a forced-function-call Gemini extraction
    (see app/extraction/agent.py), then Layer 3 verification. Any failure here
    is an external service (Parallel or Vertex), not a client error, so it
    surfaces as 502 with the underlying message rather than 500.

    Cached per jurisdiction (see app/cache.py) — a repeat search is instant
    and free rather than re-running 3 Parallel searches + a Gemini call.
    `refresh=true` bypasses the cache for an explicit re-check; the result's
    own `sources[].retrieved` date already tells the caller how fresh a
    cached rule is, so no separate cache-age field is needed.
    """
    if not refresh:
        cached = cache.get(jurisdiction)
        if cached is not None:
            return cached
    try:
        rule = extract_jurisdiction_rule(jurisdiction)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not extract a jurisdiction rule for {jurisdiction!r}: {exc}",
        ) from exc
    result = _verify_and_annotate(rule)
    cache.set(jurisdiction, result)
    return result


@dataclass
class SplitResponse:
    """Best plan, best single location, and everything considered.

    `splitting_wins` and `gain_over_single` are properties on SplitAnalysis and
    wouldn't survive serialisation, so they're materialised here — the client
    must not have to re-derive whether splitting helped by comparing two
    figures itself.
    """

    best: SplitPlan
    best_single: SplitPlan
    plans: list[SplitPlan]
    splitting_wins: bool
    gain_over_single: float


@app.get("/jurisdictions/suggested", response_model=list[SuggestedJurisdiction])
def suggested_jurisdictions() -> list[SuggestedJurisdiction]:
    """A curated starting set, grouped by region — not an allowlist.

    Extraction takes any name and searches for it, so this exists purely so
    the search box stops reading as "type one of the four things we hard-coded".
    Anything not on this list still works.
    """
    return [j for _, members in grouped() for j in members]


@app.post("/compute/questions", response_model=list[OpenQuestion])
def compute_questions(
    budget: BudgetVector,
    rule: JurisdictionRule,
    distance_km: Optional[float] = Body(default=None),
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
) -> list[OpenQuestion]:
    """What's still unresolved about this jurisdiction, priced and ranked.

    Layer 2 refuses to guess and leaves a note each time it does. Those notes
    are the highest-value phone calls a producer can make, and every figure
    here is a difference between two runs of the same compute_benefit that
    produced the number on screen — never an estimate of its own.

    Empty list for a jurisdiction that can't be ranked: there's no figure to
    protect or improve, and listing questions would imply it's a live option.
    """
    verified = verify_rule(rule)
    benefit = compute_benefit(
        budget, verified, distance_km=distance_km, assumptions=assumptions, timing=timing
    )
    return open_questions(
        budget, verified, benefit, distance_km=distance_km, assumptions=assumptions, timing=timing
    )


@app.post("/compute/split", response_model=SplitResponse)
def compute_split(
    budget: BudgetVector,
    rules: list[JurisdictionRule],
    distances: Optional[dict[str, float]] = Body(default=None),
    assumptions: Optional[RelocationAssumptions] = None,
    timing: Optional[CreditTimingAssumptions] = None,
) -> "SplitResponse":
    """Shoot in one jurisdiction, post in another — every pairing, ranked.

    The one question a rate table structurally cannot answer, because a table
    has one row per place and this needs combinations of them. Same pure
    calculator as /compute, called across pairings; no new arithmetic.

    404 when nothing at all could be computed, which is different from "no
    split helps" — that comes back 200 with splitting_wins false.
    """
    verified = [verify_rule(r) for r in rules]
    analysis = analyse_splits(
        budget, verified, distances=distances, assumptions=assumptions, timing=timing
    )
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="None of the jurisdictions supplied could be computed, so there is nothing to split.",
        )
    return SplitResponse(
        best=analysis.best,
        best_single=analysis.best_single,
        plans=analysis.plans,
        splitting_wins=analysis.splitting_wins,
        gain_over_single=analysis.gain_over_single,
    )


@app.post("/jurisdictions/challenge", response_model=ChallengeResponse)
def challenge_jurisdiction(rule: JurisdictionRule) -> "ChallengeResponse":
    """Layer 1b: search for evidence this rule is wrong, and report what turns up.

    A separate endpoint rather than part of /jurisdictions/search on purpose.
    It's a second Parallel + Gemini round trip, so folding it in would roughly
    double an already 30-60s first paint. Called after results render, it
    annotates them in place — the ranking appears fast, then each jurisdiction
    gains either a conflict or the (genuinely informative) note that we went
    looking and found nothing.

    Takes a whole rule rather than a name because the challenge is against
    specific held figures: the point is to disagree with what we're showing,
    not to run discovery a second time.
    """
    try:
        report = challenge_rule(rule)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not challenge the rule for {rule.jurisdiction!r}: {exc}",
        ) from exc
    # _verify_and_annotate, not verify_rule alone: a material contradiction
    # changes confidence, and the constraint gaps have to be recomputed on the
    # same object the caller receives.
    challenged = _verify_and_annotate(apply_challenge(rule, report))
    # Keep the cache consistent with what was just shown, so a later search
    # doesn't quietly hand back the unchallenged version.
    if cache.get(rule.jurisdiction) is not None:
        cache.set(rule.jurisdiction, challenged)
    return ChallengeResponse(rule=challenged, report=report)


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
