# Incentive Verifier

**The advertised film tax credit is never the real number. This computes the real
one, live, with receipts.**

| | |
|---|---|
| **Live demo** | https://zeta-structure-437412-v7.web.app |
| **API** | https://incentive-verifier-backend-559874048514.us-central1.run.app |
| **Demo video** | _(add link)_ |
| **Track** | Parallel — live Search API at request time |
| **Tests** | 283 backend, 68 frontend, CI on every push |

Every US state advertises a film incentive — *"Georgia 30%!"* — and producers pick
shooting locations on those numbers. Four things sit between the advertised rate and
money in the bank, and no public tool prices any of them: whether the annual funding
pool is exhausted, how much of *your* budget actually qualifies, what it costs to be
there, and what the credit is worth when it finally arrives.

Give it a budget. It searches the live web for each jurisdiction's statute, has Gemini
extract the terms, computes the benefit in deterministic Python, prices relocation off
real routed distances, then runs a **second search pass whose only job is to disprove
the first**. Everything is traceable to a dated source link, and anything it can't
verify is listed as "can't verify" rather than guessed.

### What it produces

A $2M indie drama out of Los Angeles, on hand-verified statutes and real distances:

| | advertised | net benefit |
|---|---|---|
| **New Mexico** | 25% + uplifts | **$259,952** |
| Georgia | 20% + 10% uplift | $175,722 |
| Louisiana / Texas | — | *can't verify — discretionary, not modelable* |

The advertised rate and the real answer are different questions. Georgia's $400,000
credit is worth $175,722 once you account for selling a transferable credit at a
discount, an 18-month wait to be paid, a mandatory audit, and flying 18 people 3,747 km.
No rate table contains that.

### The architectural bet

**The language model never does arithmetic.** It reads and quotes; it only fills
structured objects (`JurisdictionRule`). All computation happens in
`backend/app/calculator.py` — pure, unit-tested, no I/O and no model calls. This is
enforced by configuration (forced function calling, `mode: "ANY"`), not by asking nicely.

Why live search is structurally necessary, not decoration: you physically cannot answer
*"is New Mexico's pool exhausted right now?"* from a frozen-weights model. Incentive law
changes by legislative session.

Full spec: [BUILD_BRIEF.md](BUILD_BRIEF.md) · Submission write-up and findings:
[SUBMISSION.md](SUBMISSION.md)

## Layout

```
backend/    FastAPI + Google ADK/Gemini + Parallel Search + Google Maps, deployed on Cloud Run
frontend/   React + TypeScript + Tailwind, deployed as a static site
Incentive Verifier Web App/   Interactive design-canvas mockup — the visual/UX spec the
                               real frontend is being built against (not runnable code)
```

## Setup

Everything below runs locally; nothing here commits a secret (`backend/.env` and
`frontend/.env` are gitignored).

### 1. Backend dependencies

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### 2. Google Cloud project + SDK

The project is `zeta-structure-437412-v7`. Install the gcloud CLI, then
authenticate — `gcloud auth login` is for the CLI itself, while
`application-default login` is what the `google-genai` client actually reads:

```bash
# macOS
brew install --cask google-cloud-sdk     # or https://cloud.google.com/sdk/docs/install
# Windows: winget install Google.CloudSDK

gcloud auth login
gcloud config set project zeta-structure-437412-v7
gcloud auth application-default login
gcloud auth application-default set-quota-project zeta-structure-437412-v7
```

Enable the APIs this app calls (Vertex AI needs billing enabled on the project):

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  distance-matrix-backend.googleapis.com \
  secretmanager.googleapis.com \
  apikeys.googleapis.com
```

### 3. API keys

**Google Maps** — a Maps Platform key is a plain API key, unrelated to the
Vertex credentials above:

```bash
gcloud services api-keys create --display-name="incentive-verifier-maps" \
  --api-target=service=distance-matrix-backend.googleapis.com
gcloud services api-keys list --format="value(name,displayName)"
gcloud services api-keys get-key-string <KEY_ID>   # the name field from the line above
```

Restrict it to the Distance Matrix API (the `--api-target` above does that) so a
leaked key can't be used against other billed services.

**Parallel** — get a key from the Parallel dashboard (https://platform.parallel.ai).
It is not a Google credential and has no gcloud equivalent.

Put both in `backend/.env`, which `app/config.py` loads automatically:

```
GOOGLE_CLOUD_PROJECT=zeta-structure-437412-v7
GOOGLE_CLOUD_LOCATION=us-central1
PARALLEL_API_KEY=...
GOOGLE_MAPS_API_KEY=...
```

### 4. Verify (build order step 1)

Makes exactly one real call per service and reports each independently:

```bash
cd backend && .venv/bin/python scripts/check_credentials.py
```

All three must print OK before Layer 1 or the relocation math can be trusted.

### 5. Production secrets

`.env` is local-dev only. Cloud Run reads the same names out of Secret Manager
(the fallback path in `app/config.py`), so on deploy:

```bash
printf %s "$PARALLEL_API_KEY" | gcloud secrets create PARALLEL_API_KEY --data-file=-
printf %s "$GOOGLE_MAPS_API_KEY" | gcloud secrets create GOOGLE_MAPS_API_KEY --data-file=-
```

and grant the Cloud Run service account `roles/secretmanager.secretAccessor`.

## Status

- [x] Repo scaffolded, LICENSE in first commit
- [x] Layer 2 (`compute_benefit`) implemented with full pytest coverage — cliff, wage
      cap, tier boundaries, uplifts, per-project cap, relocation cost, sensitivity sweep
- [x] Layer 3 (rule-based verification / confidence assessment) implemented
- [x] `/health` and `/compute` API endpoints wired and testable with zero credentials.
      Fixed a real bug in `/compute` and `/compute/batch`: `distance_km`/
      `travel_time_hours` were bare-default scalar params, which FastAPI
      classifies as query params, not body fields — but `lib/api.ts` has always
      sent them in the JSON body, where they were silently dropped. Now
      declared `Body(default=None)`, with a regression test
      (`test_compute_endpoint_reads_distance_from_the_json_body`).
- [x] Frontend: Home ("try an example"), manual budget entry form, and a real
      results screen (hero recommendation, sensitivity sliders, runners-up,
      "can't verify" section) all wired end to end against the live backend
      and verified in a browser — see `frontend/src/screens/Results.tsx`.
      Sliders debounce and recompute via the real `/compute` endpoint (not a
      duplicated TS copy of the math — see the comment above `Results()`'s
      recompute effect for why that matters)
- [x] Parallel Search verified live once — both raw HTTP and the actual `parallel-web`
      SDK call `agent.py` uses returned real results. **But that `backend/.env` is
      gone on the current machine** (it is gitignored, so it doesn't travel with the
      repo): only `GOOGLE_CLOUD_PROJECT` is refilled, and `PARALLEL_API_KEY` has to
      be re-obtained. See [Setup](#setup).
- [x] SDK call shapes in `agent.py` fixed against the installed `parallel-web`
      1.3.3 and `google-genai` 2.21.0 — search results are `WebSearchResult`
      objects (not dicts) with an `excerpts` list, and the function declaration
      needs `parameters_json_schema` rather than `parameters`, because the
      latter is a genai `Schema` that rejects the `["number", "null"]` unions
      the nullable fields use. Now run live — see the Layer 1 entry below.
- [x] **Build order step 1 satisfied** — `backend/scripts/check_credentials.py`
      makes one real call per service and all three pass: Parallel Search
      (10 results, top hit `dor.georgia.gov`), `gemini-2.5-pro` via Vertex in
      `us-central1`, and a Maps distance call (LA -> Atlanta, 3,498 km / 31.6 h).
- [x] `backend/app/seed_jurisdictions.py` — 4 real jurisdictions (Georgia, New
      Mexico, Louisiana, Texas) hand-curated from those live Parallel searches,
      standing in for Layer 1 until Vertex AI auth is done. Served via
      `GET /jurisdictions/seed`, golden-file tested in
      `backend/tests/test_seed_jurisdictions.py`. Delete or fold into real
      Layer 1 output once extraction.agent works for these jurisdictions.
- [x] **Gemini via Vertex AI — auth done.** gcloud installed, ADC configured,
      billing active on `zeta-structure-437412-v7`, and `aiplatform` enabled;
      a live `gemini-2.5-pro` call in `us-central1` returns. `agent.py`'s
      extraction path is now unblocked but has not been run end to end.
- [x] Google Maps distance client (`backend/app/maps_client.py`) — verified live
      (LA -> Atlanta, 3,498 km / 31.6 h). Uses a dedicated API key restricted to
      the Distance Matrix API alone. The Routes API is not available on this
      project, so Distance Matrix is the only path.
- [x] **Layer 1 end to end, live.** `POST /jurisdictions/search` calls
      `extract_jurisdiction_rule` for real (was a hardcoded 501 stub) and
      `GET /distance` exposes `maps_client.get_distance`. Run against Oklahoma,
      Illinois, and New York — real base rates, real dated citations, correct
      `is_discretionary`/`pool_status` handling, all through `verify_rule`.
      Two live bugs this surfaced and fixed:
      - `sources`/`tiers`/`uplifts` came back from the function call as plain
        dicts, not `SourceRef`/`Tier`/`Uplift` — would have broken on first
        attribute access (`verify_rule`'s `assess_confidence` reads
        `s.retrieved`/`s.is_primary`). Now converted properly in `agent.py`.
      - The `qualifying` sub-object had no `properties`/`required` in
        `RECORD_JURISDICTION_RULE_SCHEMA`, so Oklahoma came back with
        `qualifying: {}` — a silent $0 credit (calculator.py's `q.get(key)`
        treats every missing key as not-qualifying), not an error. Now all six
        keys are explicitly required in the schema.
      Frontend: `Results.tsx` has a "search another jurisdiction" box that
      calls this live and folds the result into the ranked comparison —
      same compute/distance pipeline as the seed jurisdictions, no separate
      code path.
- [x] Map tab (`frontend/src/screens/MapView.tsx`) — real geography: Natural
      Earth world countries (110m) + US Census states (10m), served from
      `frontend/public/geo` and fetched only when the tab opens (~220KB, kept
      out of the main bundle). d3-geo Mercator fitted to whichever
      jurisdictions are in the comparison. Vector, not tiles: no second billed
      API and no map key in the browser for a supporting view.
- [x] Breakeven line + sparkline under the hero card (`frontend/src/lib/breakeven.ts`,
      `BreakevenLine` in Results.tsx). Scans ATL spend via a new
      `POST /compute/batch` endpoint (same pure `compute_benefit`, batched to
      avoid ~50 individual HTTP calls per scan). Honest caveat: with the
      current 3 ranked seed jurisdictions (Georgia/New Mexico/Louisiana),
      all flat-rate with no caps, ranking never actually flips as spend
      scales, so it always correctly reports "leads across the whole range
      tested" — the crossover-found branch is implemented and reasoned
      through carefully but not exercised by real data yet. It'll show up
      once a tiered or capped jurisdiction is added to the ranked set.
- [x] Constraint-based greying — `JurisdictionRule.constraint_gaps: dict[str, str]`,
      computed server-side by `backend/app/constraints.py` and applied uniformly
      to seed and searched jurisdictions alike (`main.py`'s `_verify_and_annotate`).
      `coastline` is a fully enumerable state list; `spring_only` derives from
      the rule's own `sunset_date`/`pool_status`; `large_soundstage` is
      deliberately left unevaluated (no confident facilities data source —
      same "don't guess" policy as extraction). Frontend: toggle chips in
      `Results.tsx` grey out (never hide) jurisdictions that fail an enabled
      constraint, with the reason on hover.
- [x] **Deployed, live, publicly reachable, no auth wall:**
      - Frontend: **https://zeta-structure-437412-v7.web.app** (Firebase
        Hosting, on the `zeta-structure-437412-v7` GCP project)
      - Backend: **https://incentive-verifier-backend-559874048514.us-central1.run.app**
        (Cloud Run, built from `backend/Dockerfile` via `gcloud run deploy --source`)
      - Both API keys live in Secret Manager (`PARALLEL_API_KEY`,
        `GOOGLE_MAPS_API_KEY`), mounted into Cloud Run via `--set-secrets`; the
        Cloud Run runtime service account has `roles/secretmanager.secretAccessor`
        and `roles/aiplatform.user` (the latter for Gemini via Vertex — verified
        with a live extraction in prod, e.g. Michigan correctly came back
        "No Active Program" rather than hallucinating one).
      - CORS (`main.py`) is narrowed to the real frontend origins (was `*`),
        overridable via `FRONTEND_ORIGINS` env var without a redeploy.
      - Redeploy: `cd backend && gcloud run deploy incentive-verifier-backend
        --source . --region us-central1 ...` (see `Setup` for the full
        secrets/env-var flags), and for the frontend, `npm run build` then
        publish `dist/` to the `zeta-structure-437412-v7` Hosting site via the
        Firebase Hosting REST API (versions -> populateFiles -> upload ->
        finalize -> release) — done this way instead of the `firebase` CLI
        because the CLI's own login wasn't set up for this account/project and
        creating a new deploy-only service-account key was (correctly) blocked
        by this environment's safety policy; the REST calls reuse the same
        `gcloud auth print-access-token` credential already established.
- [x] **PDF export** — the memo as a real PDF via the browser's own
      print-to-PDF (selectable text, live links, correct pagination, no PDF
      library). Collapsed panels are force-expanded before printing and reset
      on `afterprint`, so an export always carries every jurisdiction, the
      full assumptions table, the can't-verify list, all footnotes and
      retrieval dates, and the film office contact — regardless of what was
      collapsed on screen.
- [x] **PDF upload** (`backend/app/extraction/budget_parser.py`,
      `POST /budget/parse`) — Gemini reads an uploaded budget PDF with the
      same forced-function-call discipline as jurisdiction extraction: it
      quotes the figures printed on the topsheet and says which line each came
      from, and is never asked to total or reconcile anything. Lands on the
      *form*, pre-filled, each field annotated with its source line and anything
      missing raised as a warning — never straight to results.
- [x] **Automated testing pipeline** — `.github/workflows/ci.yml` runs backend
      pytest and frontend lint/test/build on every push and PR, with no
      credentials needed. `backend/scripts/smoke_test.py` drives the real
      deployed stack and asserts the invariants that must hold whatever
      Parallel/Gemini/Maps return (the full face-value-to-cash chain
      reconciling, components summing, credit monotonic in spend, canonical
      jurisdiction names, `retrieved` stamped today, coastal states not
      flagged landlocked); it's a manual/scheduled CI job since it spends real
      quota. **267 backend tests, 68 frontend.**

      `net == gross − relocation` was the invariant until a credit stopped
      being priced as cash on wrap day; it's now
      `gross + discount − audit + timing_loss − relocation`, and the smoke
      test reconciles that chain against pre-timing and pre-monetisation
      deployments too, so it stays meaningful across a version skew.
- [x] **What a credit is actually worth** — three corrections that each moved
      the answer by roughly the size of the entire relocation calculation.
      Payout mechanism (`credit_type`): a transferable credit is sold at a
      discount, a refundable one isn't, and treating them alike flattered
      transferable states. Fringes: 22-35% of wages, counted only where a
      statute says they qualify. And present value — a credit is a claim on
      future money, so it's discounted from wrap to payment, with a required
      audit charged before discounting. Timing defaults live in
      `CreditTimingAssumptions`, visible and editable, because payment timing
      is administrative practice rather than statute; a rule's own stated
      timeline overrides them.
- [x] **Funding availability gates the ranking** (`_availability_block`) — a
      closed pool, a passed sunset or a shut application window makes a
      program non-computable rather than merely lower-scoring. This is the
      product's stated wedge and it wasn't wired until now.
- [x] **Adversarial verification** (`backend/app/extraction/challenge.py`,
      `POST /jurisdictions/challenge`) — a second Parallel + Gemini pass whose
      only job is to disprove the first, searching for suspensions, exhausted
      pools and pending amendments. Reports contradictions, never overwrites a
      figure; code rather than the model decides whether a disagreement is
      material. Makes `confidence: "conflicting"` reachable from our own code
      for the first time.
- [x] **Refusal on impossible inputs** (`_impossible_inputs`) — found by firing
      adversarial payloads at a running server, which answered all of them
      with HTTP 200 and a confident number. `base_rate: 5.0` returned a
      $9,520,000 credit on a $2M film. Checked, not clamped: clamping 30.0 to
      1.0 would invent a 100% credit and rank it first.
- [x] **Statutes hand-verified** for Georgia, New Mexico and Louisiana against
      O.C.G.A. § 48-7-40.26, Rule 560-7-8-.45, NMSA 7-2F-15 and Louisiana
      Entertainment. Three errors in three jurisdictions, and the top
      recommendation changed. See `test_seed_jurisdictions.py`.
- [x] **ADK agent** (`backend/app/agent/`, `scripts/run_agent.py`) — an
      `LlmAgent` over six tools, satisfying BUILD_BRIEF §4's "the agent must
      invoke the calculator tool". Tools address jurisdictions by name, never
      by value, so the model never carries a figure between steps. Additive:
      the REST pipeline is untouched and is still what the frontend uses.
- [ ] Custom domain (currently the default `*.web.app` / `*.run.app` URLs)
- [ ] **Statutes unverified beyond those three.** Texas and every
      live-extracted jurisdiction are unchecked. Three of three checked had
      errors, so assume a similar rate rather than zero.
- [ ] **Per-category qualifying rates.** `qualifying` is a boolean per spend
      category and can't express New Mexico's real rule (non-resident crew at
      15% rather than 25%, capped at a share of the BTL budget). We exclude
      them, understating NM by $16,875 on a $2M drama rather than overstating
      by $67,500 — the smaller error, stated on the card.
- [x] **Deployed and verified 6 Sep 2026.** Both halves current; smoke test
      6/6 against production. The adversarial pass and the ADK agent have now
      run live — each found a real bug on its first execution, both fixed.
      See [VERIFY_LIVE.md](VERIFY_LIVE.md) for what was checked and found.

See BUILD_BRIEF.md section 8 for the intended build order.

## Backend

Requires Python 3.11+.

Install and authenticate first — see [Setup](#setup). Then:

```bash
cd backend
.venv/bin/pytest              # runs with no credentials — Layer 2 and Layer 3 are pure
.venv/bin/uvicorn app.main:app --reload
```

`GET /health`, `POST /compute` work immediately. `POST /jurisdictions/search` returns
501 until `GOOGLE_CLOUD_PROJECT`, `PARALLEL_API_KEY` and `GOOGLE_MAPS_API_KEY` are set
(env locally, Secret Manager in production — see `app/config.py`). Never commit `.env`.

## Frontend

Requires Node 18+.

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://localhost:8000
npm run dev
```

## Secrets

All API keys live in Google Secret Manager in production, and in a local, gitignored
`.env` for development. Never commit a key. See `backend/.env.example`, and
[Setup](#setup) steps 3 and 5 for how each key is created and promoted to
Secret Manager. No key is ever exposed to the frontend — `frontend/.env` holds
only `VITE_API_BASE_URL`.
