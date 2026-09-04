# Progress report — 2026-08-30

> **Superseded.** This is a historical snapshot. For current status and the
> live task list see [NEXT_STEPS.md](NEXT_STEPS.md); much of what's listed
> below as missing (Layer 1, Maps, deployment, PDF upload/export, the map tab)
> has since been built.

Snapshot of where this repo stands against [BUILD_BRIEF.md](BUILD_BRIEF.md), written before
pushing to a new GitHub account. `README.md` has a live, terser checklist; this is the
fuller point-in-time writeup, section-by-section against the brief.

Deadline: 2026-09-09, 2:00 PM PT — **10 days out as of this report.**

---

## Hard constraints (brief section 2) — submission gates

These explicitly "fail the submission" if unmet. Being direct about where each stands:

| Constraint | Status |
|---|---|
| Google Cloud AI SDK imported *and actually called* at runtime | **Not met.** `backend/app/extraction/agent.py` is a structural skeleton — never executed against real Gemini/Vertex. |
| Parallel Search SDK imported *and actually called* at runtime | **Met.** Real calls made both via raw HTTP and via the exact `parallel-web` SDK shape `agent.py` uses; results are in `backend/app/seed_jurisdictions.py`. |
| Public repository, LICENSE at root | **Not met.** LICENSE (MIT) is at root and in the first commit, but this repo has **no git remote** — it has only ever existed on this machine. Nothing has been pushed anywhere. |
| Secrets in Google Secret Manager | **Not met for production.** `backend/app/config.py` has the Secret Manager fallback code ready; today, secrets live only in a local, gitignored `backend/.env`. |
| Live hosted URL, reachable logged out | **Not met.** No Cloud Run service, no deployment of any kind exists yet. |
| Originality / frequent commits | **On track.** 7 commits this session, all new code, one coherent feature per commit. |

## Architecture (brief section 4)

- **Layer 1 (Extraction)** — ~15-20% done. `backend/app/extraction/agent.py` has the forced-function-calling shape sketched out (search via Parallel, extraction via Gemini), but the Gemini half has never run — it needs `gcloud auth application-default login` against project `zeta-structure-437412-v7`, which only you can do interactively. The Parallel-search half of this layer is proven for real.
- **Layer 2 (Calculation)** — **done.** `backend/app/calculator.py`, pure, no I/O. 32 tests passing (`backend/tests/test_calculator.py`, `test_seed_jurisdictions.py`, `test_api.py`) covering the minimum-spend cliff, wage cap, tier boundaries, uplifts, per-project cap, the relocation formula, and sensitivity sweeps. This is the brief's "main credibility claim" and it's solid.
- **Layer 3 (Verification)** — **done** for what's specified. `backend/app/verification.py` assigns confidence (`primary_source` / `official_secondary` / `conflicting` / `stale` / `unverified`) from sources, conflicts, and staleness.

## Data model & calculation rules (brief sections 5-6)

Implemented verbatim in `backend/app/models.py`. Two deliberate, documented departures from the
brief's illustrative sketches (both flagged in `calculator.py`'s module docstring, not silently
made):
1. `compute_benefit()` takes `distance_km` / `travel_time_hours` / `assumptions` as plain-data
   parameters (fetched via Maps upstream) rather than the brief's two-argument sketch, so the
   function itself stays I/O-free.
2. `JurisdictionRule.qualifying` is keyed to the categories `BudgetVector` actually has
   (`atl_cast`, `atl_noncast`, `btl_labor_resident`, `btl_labor_nonresident`, `btl_nonlabor`,
   `post_vfx`), not the brief's illustrative `"atl_resident"/"atl_nonresident"` example.

## Frontend (brief section 7)

| Piece | Status |
|---|---|
| Home / "try an example" | **Done**, verified in a browser |
| Manual budget entry form | **Done** — sum reconciliation, constraint toggles, home base select |
| Upload budget PDF | **Not started.** Home screen shows an inert drop-zone placeholder only; a real version needs Gemini document parsing |
| Results memo (hero, runners-up, "can't verify") | **Done**, calling the real backend for every jurisdiction |
| Sensitivity sliders (ATL spend, resident-labor %) | **Done**, debounced recompute through the real `/compute` endpoint |
| Relocation assumptions, editable | **Done** — all 7 fields |
| Breakeven line + sparkline | **Done**, via a new `/compute/batch` endpoint. Caveat: the 3 real ranked seed jurisdictions are all flat-rate with no caps, so ranking never actually flips with spend in practice yet — the crossover-found code path is implemented but unexercised by real data |
| Constraint-based greying (chips actually excluding jurisdictions) | **Not started** — `JurisdictionRule` has no field for "does this jurisdiction satisfy constraint X." Needs a schema decision, not something to invent silently |
| Map tab | **Done**, deliberately simplified: plain SVG, real jurisdiction centroids, no D3/topojson/country-boundary data |
| Export | **Not started** |

## Testing (brief section 9)

`compute_benefit` unit tests, golden-file tests (against 4 real hand-curated jurisdictions),
cliff tests, and a sensitivity-sweep test are all done. The one item not done: a snapshot test
on extraction schema conformance — there's no live extraction output yet to snapshot.

## Build order (brief section 8) — step by step

1. **Verify access** — Parallel: done for real. Gemini: not done. Maps: not done. Repo with
   LICENSE in the first commit: done locally, **not public.**
2. **Layer 2 alone** — done.
3. **Layer 1 for 5-8 real jurisdictions** — partial. 4 real jurisdictions (Georgia, New Mexico,
   Louisiana, Texas) hand-curated from live Parallel searches and manually structured into
   `JurisdictionRule` — i.e. a human doing what the automated agent will do once it has
   credentials. Not yet automated.
4. **Wire together, terminal path** — partial. Done via the hand-curated seed data through the
   real API; not yet via the live search → extract pipeline.
5. **Relocation cost via Maps** — not done. `distance_km` is always `null` today; relocation
   cost everywhere currently omits flights/ground transport (honestly labeled in the UI, not
   hidden).
6. **Frontend** — mostly done (see table above).
7. **PDF upload** — not done.
8. **Layer 3 polish** — mostly done.
9. **Export, empty/error states, map tab** — map done; loading/error states exist on the results
   screen; export not done.

---

## Overall

Roughly **40-45% of the way to a submittable hackathon entry.** Everything buildable without
GCP credentials — the calculation engine, verification, and nearly the full frontend — is in
solid, tested shape. But three of the hard "fails the submission" constraints are still at
zero, and none of them can be finished without action outside this codebase: a real Gemini
call, a public repository, and a live deployment.

## What's left, in priority order

1. Push this repo to the new GitHub account (public; LICENSE is already at root).
2. `gcloud auth application-default login` against `zeta-structure-437412-v7`, then verify and
   fix `backend/app/extraction/agent.py`'s SDK calls against a real Gemini response.
3. Get the Google Maps API key into `backend/.env`, then verify and fix
   `backend/app/maps_client.py` against a real Distance Matrix call.
4. Run Layer 1 for real across 5-8 jurisdictions; hand-verify a few against the actual statutes
   per the brief's own instruction.
5. Fold real Maps distance into the compute calls that currently pass `distance_km=null`.
6. Move secrets to Google Secret Manager; narrow `main.py`'s CORS `allow_origins` off `"*"`.
7. Deploy the backend to Cloud Run and the frontend to a static host; confirm the URL is
   reachable logged out.
8. Lower priority, once the above is done: PDF export, the real PDF upload flow, and
   constraint-based greying (needs the schema decision noted above first).
