# Slateline — Build Brief

You are building a production-ready web application for a hackathon submission. Read this entire brief before writing code. Ask me before deviating from any hard constraint.

---

## 1. What we're building and why

**Slateline** tells film producers not just what a jurisdiction's film tax incentive rate is, but whether the funding is still available right now, and what the incentive actually nets after the cost of relocating cast and crew there.

**The problem.** Incentive comparison tools already exist (Entertainment Partners, Wrapbook, GreenSlate, Cast & Crew). They share three weaknesses:
1. Manually curated databases lag legislative changes.
2. They report the *rate* but not whether the annual funding pool is exhausted, the application window has closed, or the program is sunsetting. A 30% credit you can't access is a 0% credit.
3. They ignore relocation cost, so a high rate in a remote jurisdiction can look better than it is.

**Our wedge.** Live retrieval with dated citations, funding-availability checking, and net-of-relocation math. The one existing AI competitor is a frozen fine-tuned model shipped with its own hallucination disclaimer and no citations — we do the opposite.

**Core architectural principle: the language model never does arithmetic.** It reads sources and fills structured objects. All computation happens in deterministic, unit-tested Python. This is enforced by configuration (forced function calling), not by prompt instruction. This principle is the project's main credibility claim — do not compromise it for convenience anywhere.

---

## 2. Hard constraints — violating any of these fails the submission

**AI tooling.** Only Google Cloud AI tools and Parallel's built-in AI features. No other AI models, agent frameworks, or AI APIs from any vendor. **This explicitly includes LangChain — do not import it, do not use it, even though some official Google notebooks use it.** If you need grounding, use Vertex AI Search data stores.

**Non-AI third-party services are unrestricted** — hosting, databases, web frameworks, charting libraries, UI libraries are all fine.

**Required at runtime, imported and actually called (not just named in the README):**
- A Google Cloud SDK: `google-adk`, `google-genai`, `google-generativeai`, or `google-cloud-aiplatform`
- Parallel's Search API via the official `parallel-web` SDK (Python)

**Google Maps Platform is permitted** — it's Google, and it isn't an AI service. An official Maps + ADK agent tutorial is listed in the hackathon resources.

**Repository:** public, all source and assets, run instructions, OSS license file at repo root so it renders in the GitHub About section.

**Secrets:** all API keys in Google Secret Manager. The repo is public. Never commit a key, never put one in a `.env` that gets committed, never hardcode one in a notebook.

**Deployment:** live hosted URL, reachable logged-out, no authentication wall.

**Originality:** all code written new during the contest period. Commit frequently — history is the evidence.

**Deadline:** 2:00 PM PT, September 9, 2026.

---

## 3. Stack

- **Agent:** Google ADK (`pip install "google-cloud-aiplatform[agent_engines,adk]>=1.101.0"`)
- **Model:** Gemini via Vertex AI
- **Search:** `parallel-web` Python SDK
- **Distance:** Google Maps Platform (Distance Matrix or Routes API)
- **Document parsing:** Gemini multimodal / Document Processing
- **Backend:** Python (FastAPI), deployed on Cloud Run
- **Frontend:** React + TypeScript, Tailwind
- **Secrets:** Google Secret Manager
- **Testing:** pytest

---

## 4. Architecture — three strictly separated layers

### Layer 1: Extraction (Gemini + Parallel)
Given a jurisdiction name, search for its film incentive program and populate a `JurisdictionRule` object. The model's only job is reading and quoting. It never computes a benefit.

Search targets, in priority order: primary statute or regulation text, official film office pages, recent legislative updates and news for cap/sunset changes.

### Layer 2: Calculation (pure Python, no model)
```python
def compute_benefit(budget: BudgetVector, rule: JurisdictionRule) -> BenefitBreakdown:
    """Pure function. No I/O, no model calls, fully deterministic."""
```
Sensitivity analysis is this same function called in a loop across a parameter range. Nothing more sophisticated is needed.

### Layer 3: Verification (rule-based)
Cross-checks values across retrieved sources, assigns a confidence state, and marks programs it cannot compute rather than guessing at them.

**Enforce the separation with forced function calling** so the agent must invoke the calculator tool and cannot emit a benefit figure from its own reasoning.

---

## 5. Data models

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

Confidence = Literal["primary_source", "official_secondary", "conflicting", "stale", "unverified"]
PoolStatus = Literal["open", "capping_out", "closed", "unknown"]

@dataclass
class SourceRef:
    url: str
    retrieved: date
    published: Optional[date]
    excerpt: str          # short supporting quote, for the footnote
    is_primary: bool      # statute/regulation vs commentary

@dataclass
class Tier:
    threshold: float      # spend level at which this rate begins
    rate: float

@dataclass
class Uplift:
    condition: str        # "shot outside metro area", "local hire > 50%"
    bonus_rate: float
    machine_checkable: bool   # can we evaluate this from the budget object?

@dataclass
class JurisdictionRule:
    jurisdiction: str
    program_name: str
    base_rate: float
    qualifying: dict          # {"atl_resident": True, "atl_nonresident": False, ...}
    per_person_wage_cap: Optional[float]
    minimum_spend: Optional[float]
    per_project_cap: Optional[float]
    tiers: list[Tier]
    uplifts: list[Uplift]
    annual_pool_total: Optional[float]
    annual_pool_remaining: Optional[float]
    pool_status: PoolStatus
    application_deadline: Optional[date]
    sunset_date: Optional[date]
    under_review: bool
    is_discretionary: bool    # jury/committee allocated -> non-modelable
    film_office_contact: Optional[str]
    centroid_lat: float
    centroid_lng: float
    sources: list[SourceRef]
    confidence: Confidence
    conflicts: list[str]      # human-readable notes on disagreeing sources

@dataclass
class BudgetVector:
    total: float
    atl_cast: float
    atl_noncast: float
    btl_labor: float
    btl_nonlabor: float
    post_vfx: float
    shoot_days: int
    crew_headcount: int
    resident_labor_pct: float      # 0.0-1.0, user estimate
    home_base: str                 # city, for relocation distance
    constraints: list[str]         # "coastline", "large_soundstage", "spring_only"

@dataclass
class RelocationAssumptions:
    flight_threshold_km: float = 800.0
    flight_cost_per_person: float = 600.0
    ground_cost_per_person_per_km: float = 0.35
    per_diem_per_person_per_day: float = 85.0
    hotel_per_person_per_day: float = 140.0
    equipment_shipping_base: float = 15000.0
    imported_crew_pct: float = 0.4   # fraction of headcount that travels

@dataclass
class BenefitBreakdown:
    jurisdiction: str
    qualifying_spend: float
    gross_credit: float
    caps_applied: list[str]        # human-readable: "per-person wage cap reduced qualifying ATL by $2.1M"
    distance_km: Optional[float]
    travel_time_hours: Optional[float]
    relocation_cost: float
    relocation_components: dict    # itemised, for display
    net_benefit: float
    computable: bool
    non_computable_reason: Optional[str]
```

---

## 6. Calculation rules

Apply in this order, and record every cap that bites in `caps_applied`:

1. Determine qualifying spend by category using `rule.qualifying`. Non-qualifying categories contribute zero.
2. Apply `per_person_wage_cap` to ATL cast. Approximate per-person allocation from `crew_headcount` and a configurable assumed cast count; document the assumption in the UI.
3. Apply `resident_labor_pct` to split BTL labor into resident and non-resident portions, and include each according to `rule.qualifying`.
4. If total qualifying spend < `minimum_spend`, benefit is **zero**. This is a cliff, not a proportional reduction. Getting this wrong invalidates the whole tool.
5. Select the rate from `tiers` if present, otherwise `base_rate`.
6. Add machine-checkable uplifts only. Uplifts you cannot evaluate go into `caps_applied` as an unquantified note.
7. Apply `per_project_cap` as a ceiling on gross credit.
8. Compute relocation cost, subtract, produce `net_benefit`.

If `rule.is_discretionary` is true, set `computable = False` with a reason and exclude it from the ranking — do not fabricate a number.

**Relocation cost model.** Keep it simple and transparent:
```
travelling_crew = crew_headcount * imported_crew_pct
transport = travelling_crew * (flight_cost if distance > threshold else distance * ground_rate)
lodging = travelling_crew * shoot_days * (per_diem + hotel)
relocation_cost = transport + lodging + equipment_shipping_base
```
Every assumption must be visible and editable in the UI. This is an estimate and must be labelled as one.

---

## 7. Frontend

### Home screen — three equally weighted entry points
1. **Try an example** — three cards (Indie Drama $2M, Streaming Series $18M, Studio Film $60M). One click loads a full `BudgetVector`. **Build this first.** A judge opening the live URL has no budget file; if the first thing they see is an upload box, we lose the Design score.
2. **Enter budget manually** — short form matching `BudgetVector`, sensible defaults, inline help on ATL/BTL.
3. **Upload budget PDF** — drag-and-drop, then return to the same form pre-filled, each parsed field annotated with where it came from, all fields editable before running. Never jump straight from upload to results.

### Results screen — a memo, not a leaderboard
- Top recommendation with **net** benefit prominent, and directly beneath it the arithmetic in one readable line: gross credit − relocation cost = net.
- Runner-up jurisdictions below in the same layout, less emphasis.
- Each card: rate, caps in plain language, distance and travel time from home base, a status pill (Funding open / Capping out / Program under review), and a footnote row with source link and "retrieved [date]".
- Breakeven line under the top pick — "Leads until ATL spend exceeds $11.1M; you're at $9.8M" — with a small inline sparkline of the crossover.
- Collapsed **"Can't verify"** section listing discretionary or unverifiable programs with one-line reasons. This section is a feature, not an apology.

### Live controls — the centrepiece, give them real estate
- Sensitivity sliders for ATL spend and resident-labor %. Dragging reorders the list in real time with smooth transitions. Since Layer 2 is a pure function, recompute on every change — no model call, no network round trip for the recompute.
- Constraint toggle chips; enabling one greys out failing jurisdictions with a hover reason.
- An expandable "relocation assumptions" row exposing `RelocationAssumptions` for editing.

### Map view
Secondary tab. Jurisdiction pins coloured by net benefit, home base marked, distance lines. Supporting view, not the hero.

### Export
PDF of the memo including all footnotes, retrieval dates, assumptions used, and film office contacts.

### Design tone
A serious financial and legal workflow tool for production accountants and line producers. Think due-diligence report, not AI demo. Dense but legible tables, muted palette, no gradients or glow effects, strong typographic hierarchy so the recommendation is scannable in two seconds. Sourcing and verification states should read as the product, not as disclaimers. Build empty, loading, and error states for the upload, search, and map flows.

---

## 8. Build order

Do not proceed to the next stage until the current one runs end to end.

1. **Verify access.** One real `parallel-web` search call returning results. One Gemini call via Vertex. One Maps distance call. Repo created with LICENSE in the first commit.
2. **Layer 2 first, alone.** `compute_benefit` with hand-written `JurisdictionRule` fixtures and full pytest coverage — especially the minimum-spend cliff, the wage cap, and tier boundaries. No model involved. This is the foundation everything else rests on.
3. **Layer 1.** Extraction agent producing populated `JurisdictionRule` objects from live search for 5–8 real jurisdictions. Verify a few by hand against the actual statutes.
4. **Wire together.** Terminal path: hardcoded `BudgetVector` → search → compute → ranked output with citations.
5. **Relocation cost** via Maps, folded into `net_benefit`.
6. **Frontend.** Examples path first, then manual form, then results screen, then sliders. Deploy to a public URL as soon as anything renders and keep it live from then on.
7. **PDF upload** last. It's the most impressive path and the least essential — if parsing eats time, the product still works without it.
8. **Layer 3 polish.** Conflict detection, confidence states, "Can't verify" section.
9. **Export, empty/error states, map tab.**

---

## 9. Testing

- `compute_benefit` unit tests are non-negotiable — this is what lets us claim the math is trustworthy.
- Golden-file tests: a handful of jurisdictions with hand-verified expected benefits for a known budget.
- Cliff tests: assert that spending one dollar under `minimum_spend` yields exactly zero.
- Sensitivity test: assert a known crossover point occurs where expected.
- Snapshot test on extraction schema conformance so a malformed model response fails loudly rather than silently producing wrong numbers.

---

## 10. Do not build

Avoid, regardless of how tempting: image generation, music generation, text-to-speech, video transcription, sentiment analysis, chat interfaces, uplift-zone boundary polygons, drive-time isochrones, user accounts, saved sessions, multi-currency support.

Every one of these is an afternoon that turns a workflow tool into a demo reel. If a feature isn't in this brief, ask before building it.
