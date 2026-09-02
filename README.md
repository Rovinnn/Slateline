# Incentive Verifier

Tells film producers not just what a jurisdiction's film tax incentive rate is, but
whether the funding is still available right now, and what the incentive nets after
the cost of relocating cast and crew there. Full spec: [BUILD_BRIEF.md](BUILD_BRIEF.md).

The language model never does arithmetic — it only fills structured objects
(`JurisdictionRule`). All computation happens in `backend/app/calculator.py`, a pure,
unit-tested Python function with no I/O and no model calls.

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
- [x] Map tab (`frontend/src/screens/MapView.tsx`) — deliberately lightweight:
      plain SVG, no D3/topojson/CDN fetch, no country boundaries (see its file
      docstring for why). Real jurisdiction centroids, schematic projection.
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
- [ ] PDF upload, export
- [ ] Custom domain (currently the default `*.web.app` / `*.run.app` URLs)

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
