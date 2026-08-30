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
- [x] Frontend scaffolded (Vite + React + TS + Tailwind), Home screen ("try an
      example") built and verified in a browser
- [ ] Layer 1 (Gemini + Parallel extraction agent) — structural skeleton only in
      `backend/app/extraction/agent.py`, not yet run against real credentials
- [ ] Google Maps distance client — structural skeleton only in `backend/app/maps_client.py`
- [ ] Manual budget entry form, results memo, sensitivity sliders, map tab, PDF upload
- [ ] Deployment to Cloud Run / a public URL

See BUILD_BRIEF.md section 8 for the intended build order — the two model/search-
dependent pieces above are next once credentials are available.

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
