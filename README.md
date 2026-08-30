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

## Status

- [x] Repo scaffolded, LICENSE in first commit
- [x] Layer 2 (`compute_benefit`) implemented with full pytest coverage — cliff, wage
      cap, tier boundaries, uplifts, per-project cap, relocation cost, sensitivity sweep
- [x] Layer 3 (rule-based verification / confidence assessment) implemented
- [x] `/health` and `/compute` API endpoints wired and testable with zero credentials
- [x] Frontend: Home ("try an example"), manual budget entry form, and a real
      results screen (hero recommendation, sensitivity sliders, runners-up,
      "can't verify" section) all wired end to end against the live backend
      and verified in a browser — see `frontend/src/screens/Results.tsx`.
      Sliders debounce and recompute via the real `/compute` endpoint (not a
      duplicated TS copy of the math — see the comment above `Results()`'s
      recompute effect for why that matters)
- [x] `GOOGLE_CLOUD_PROJECT` and `PARALLEL_API_KEY` set in `backend/.env` (gitignored).
      Parallel Search verified live — both raw HTTP and the actual `parallel-web`
      SDK call `agent.py` uses returned real results
- [x] `backend/app/seed_jurisdictions.py` — 4 real jurisdictions (Georgia, New
      Mexico, Louisiana, Texas) hand-curated from those live Parallel searches,
      standing in for Layer 1 until Vertex AI auth is done. Served via
      `GET /jurisdictions/seed`, golden-file tested in
      `backend/tests/test_seed_jurisdictions.py`. Delete or fold into real
      Layer 1 output once extraction.agent works for these jurisdictions.
- [ ] **Gemini via Vertex AI — auth not yet done, this is the next real blocker.**
      `agent.py`'s extraction call needs GCP application-default credentials, which
      requires an interactive login only a human can complete:
      1. Install the gcloud CLI (`winget install Google.CloudSDK` on Windows, or
         https://cloud.google.com/sdk/docs/install)
      2. `gcloud auth application-default login` — opens a browser, sign in with
         the Google account tied to project `zeta-structure-437412-v7`
      3. `gcloud config set project zeta-structure-437412-v7`
      4. Then `backend/app/extraction/agent.py` should work — but its exact SDK
         call shapes (`google-genai` client construction, function-calling config,
         response parsing) are still unverified against a live call; expect to
         debug those once auth is in place.
- [ ] Google Maps distance client (`backend/app/maps_client.py`) — needs
      `GOOGLE_MAPS_API_KEY` in `backend/.env`; not yet obtained (billing/free-credit
      setup still pending on the GCP project as of this writing)
- [x] Map tab (`frontend/src/screens/MapView.tsx`) — deliberately lightweight:
      plain SVG, no D3/topojson/CDN fetch, no country boundaries (see its file
      docstring for why). Real jurisdiction centroids, schematic projection.
- [ ] Breakeven sparkline, constraint-based greying (needs a schema decision —
      JurisdictionRule has no field for "does this jurisdiction satisfy X
      constraint", see comment in Results.tsx), PDF upload, export
- [ ] Deployment to Cloud Run / a public URL

See BUILD_BRIEF.md section 8 for the intended build order.

## Backend

Requires Python 3.11+.

```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env   # fill in once you have GCP/Parallel/Maps credentials
pytest                 # runs today with no credentials — Layer 2 and Layer 3 are pure
uvicorn app.main:app --reload
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
`.env` for development. Never commit a key. See `backend/.env.example`.
