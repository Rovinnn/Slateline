# Handoff — final push to submission

**Deadline: Mon 7 Sep 2026, 2:00 PM PT.** Written 6 Sep.

Everything below is blocked on Google Cloud credentials that only exist on a
teammate's machine. The code is done and tested; none of it is live.

**DEPLOYED 6 Sep 2026.** Both halves are live and current:

- Backend — Cloud Run revision `incentive-verifier-backend-00008-rpm`
  (rollback points: `00007`, `00006-cs9`, `00005-gqt`, `00004-rfw`). Smoke
  test **6/6**.
- Frontend — Firebase Hosting release `1788708772764000`, bundle
  `index-B46yLlPn.js`. Carries the cinematic UI refresh, the Slateline
  rebrand, and the reconciled split-location-allocation feature
  (`app/split.py`).

Verified end to end against production: four jurisdictions extracted live,
real Maps distances, New Mexico ranked first at $259,952 over Georgia at
$175,722, discretionary programs correctly refused rather than ranked, and the
adversarial pass running on the winner.

What remains is entirely **items 4-6 below** — repo public, video, Devpost.
Those are pass/fail gates and none of them are code.

---

## Order of operations

| # | Item | Time | Blocks |
|---|---|---|---|
| 1 | Authenticate gcloud | 2 min | everything below |
| 2 | Deploy backend + frontend | ~20 min | 3, 5 |
| 3 | Verify (smoke test + browser) | ~10 min | — |
| 4 | ~~Repo public, license in About~~ ✅ done 6 Sep, MIT detected | — | Stage 1 pass/fail |
| 5 | Demo video ≤3 min | — | 25% of the grade |
| 6 | Devpost submission — see [DEVPOST.md](DEVPOST.md) | — | Stage 1 pass/fail |

Items 4 and 6 are pass/fail gates. The submission fails outright without them,
regardless of how good the product is.

---

## 1. Authenticate

**Status as of 6 Sep: ADC is done, the CLI login is NOT.**
`gcloud auth application-default login` has been run — that's what
`google-genai` reads, and Parallel, Gemini and Maps all verify OK. But
`gcloud auth list` reports no credentialed accounts, so **`gcloud run deploy`
will fail** until someone runs the CLI login. They are separate credentials
and both are needed.

```bash
gcloud auth login          # <- this is the one still missing
gcloud config set project zeta-structure-437412-v7
```

```bash
gcloud auth login
gcloud config set project zeta-structure-437412-v7
gcloud auth application-default login
gcloud auth application-default set-quota-project zeta-structure-437412-v7
```

Then create `backend/.env` (gitignored — never commit it):

```
GOOGLE_CLOUD_PROJECT=zeta-structure-437412-v7
GOOGLE_CLOUD_LOCATION=us-central1
PARALLEL_API_KEY=<from platform.parallel.ai>
GOOGLE_MAPS_API_KEY=<see README §3 to mint one, restricted to Distance Matrix>
```

Confirm all three services answer before going further — this makes exactly
one real call per service and reports each independently:

```bash
cd backend && python scripts/check_credentials.py
```

All three print OK as of 6 Sep — Parallel, Gemini via Vertex, and Maps
(LA → Atlanta, 3,498 km). Re-run it if anything downstream misbehaves.

---

## 2. Deploy

### Backend (Cloud Run)

The service already exists and is correctly configured — secrets in Secret
Manager, service account with `roles/secretmanager.secretAccessor` and
`roles/aiplatform.user`. **`gcloud run deploy` on an existing service
preserves its env vars, secrets and IAM**, so the minimal command is also the
safest, because it can't accidentally drop a flag nobody wrote down:

```bash
cd backend
gcloud run deploy incentive-verifier-backend --source . --region us-central1
```

> The original deploy's full flag list was never recorded in the README (it's
> elided as `...`). Do not reconstruct it from memory and pass it explicitly —
> that risks overwriting working configuration. Let the existing service
> config carry forward.

`app/config.py` reads `PARALLEL_API_KEY` and `GOOGLE_MAPS_API_KEY` from Secret
Manager itself whenever `GOOGLE_CLOUD_PROJECT` is set, so no `--set-secrets`
flag is strictly required. The secrets already exist — **do not re-run
`gcloud secrets create`**, it will fail on an existing secret.

### Frontend (Firebase Hosting)

**There is no `firebase.json` in this repo.** The frontend was published via
the Firebase Hosting REST API, not the CLI, because the CLI's login wasn't set
up for this account and minting a deploy-only service-account key was blocked.

```bash
cd frontend
npm ci
npm run build     # tsc -b && vite build — this is the real typecheck
```

Then publish `dist/` to the `zeta-structure-437412-v7` Hosting site by either:

- **`firebase` CLI** — needs `firebase login` and `firebase init hosting`
  first (public dir `dist`, single-page app: yes). Simplest if the login
  works for this account.
- **Hosting REST API** — the path used previously: `versions.create` →
  `populateFiles` → upload → `finalize` → `releases.create`, authenticated
  with `gcloud auth print-access-token`.

`frontend/.env` already points `VITE_API_BASE_URL` at the deployed Cloud Run
backend, so no change is needed there.

---

## 3. Verify

### Automated

```bash
cd backend && python scripts/smoke_test.py
```

Six checks against the real deployed stack. **All six should pass after
deploying.** Before deploying it reports 5/6, failing on
`expected canonical 'Georgia', got 'GA'` — that failure is *purely* the stale
deployment; local code canonicalises correctly and there is a test for it. If
it still fails after a deploy, the deploy didn't take.

### In a browser, and against the live pipeline

**→ Work through [VERIFY_LIVE.md](VERIFY_LIVE.md).** It's the full checklist,
with expected values, severities, and what to do when something fails.

The four things on it that matter most:

1. **The adversarial challenge pass has never run against real Parallel and
   Gemini** — only mocked responses, because nobody could authenticate. Its
   first live execution will be in production. If it invents conflicts, remove
   the `challengeJurisdiction` effect from `Results.tsx` and redeploy; the
   ranking doesn't depend on it.
2. **Live extraction can now be graded, not just inspected.** Georgia, New
   Mexico and Louisiana were hand-verified against the statutes on 6 Sep, so
   they're a correctness oracle. Compare what the live pipeline extracts
   against the tables in VERIFY_LIVE.md §2.
3. **Nobody has ever opened this UI.** It's verified by types, tests and a
   build only. Bars could overflow, panels could be broken, and every check
   here would still be green.
4. **No key may appear in the browser.** The map is vector data with no tile
   API, so there should be no Maps key client-side at all.

---

## 4. Repo public

Currently private (returns 404 unauthenticated). Required by Stage 1, along
with the OSS license being **detectable in the GitHub About section**. `MIT`
`LICENSE` is already at the repo root, so GitHub should pick it up
automatically once the repo is public — confirm the About sidebar shows "MIT
license" rather than nothing.

---

## 5. Demo video (≤3 min, public on YouTube/Vimeo)

The brief is explicit: *"a demo showing your agent functioning as built, not a
cinematic trailer."* Impact is scored on what's demonstrated, not claimed.

**Open on the payoff, not on setup.** The strongest shot is the ranking for a
$2M indie drama, because the advertised order and the real order disagree:

| | advertised | net benefit |
|---|---|---|
| **Louisiana** | 25% + 15% = up to **40%** | **$265,564** |
| New Mexico | 25% + 20% = up to **45%** | $260,215 |
| Georgia | 20% + 10% = up to **30%** | $188,825 |

New Mexico advertises the biggest number and loses. Louisiana and New Mexico
advertise the *same* 25% base and differ by $5,350 — because New Mexico's
credit excludes non-resident below-the-line crew and Louisiana's pays three
months later at 90% of face. No rate table contains that.

Then open the winner's card: the waterfall walks the advertised rate down to
cash, and "why it wins" splits the gap into components that sum exactly to it.

> These figures are the **hand-verified seed set** as of 6 Sep. The deployed
> app ranks off *live* extraction, so re-check the on-screen numbers before
> recording and use whatever it actually shows — do not narrate these from
> memory.

Suggested beats: that screen (20s) → sliders reordering the ranking live
(20s) → click a source link and the retrieved date (20s) → the challenge badge
finding or clearing a conflict (20s) → "can't verify" list, showing it refuses
rather than guesses (20s) → PDF export (10s).

No third-party logos or marks.

---

## 6. Devpost submission

Draft copy is in [SUBMISSION.md](SUBMISSION.md) — features, tech, data
sources, and the required *"findings and learnings"*, which is where this
project is unusually strong because the interesting failures were real and
recorded as they happened.

Checklist for the form:
- [ ] Live hosted URL, **verified logged-out from a different network**
- [ ] Public repo link, license visible in About
- [ ] Description incl. findings and learnings
- [ ] Video link, public
- [ ] **Parallel** selected as the one track
- [ ] Numbers in the description still match the deployed site

---

## Gotchas

- **`npm run build` is the real typecheck**, not `npx tsc --noEmit` — the root
  tsconfig doesn't actually check, and has silently passed genuine errors.
- **Don't re-create Secret Manager secrets**; they exist.
- **First load on a cold jurisdiction takes 30–60s** (live search + extraction
  per jurisdiction, cached after). If the video opens on a cold load, warm it
  first by visiting the page once.
- **Cache is process-local.** A Cloud Run cold start or a second instance
  means one more live search — never a wrong answer.
- **`backend/.env` is gitignored.** Never commit a key; the repo is about to
  be public.

---

## What is deliberately not being done before submission

Recorded so it isn't re-litigated under time pressure:

- **Statute hand-verification.** The golden values were produced by running
  our own code and recording its output — a regression test, not a correctness
  test. It's the deepest gap in the project, it's disclosed honestly in
  `SUBMISSION.md`, and it cannot be finished responsibly in the time left.
- **ADK agent wrapper.** `google-adk` is in `pyproject.toml` and imported
  nowhere. Costs points on Technological Implementation; very unlikely to be a
  Stage 1 failure.
- **Uncertainty / ranking robustness**, the next feature in the plan. Scoped
  in `NEXT_STEPS.md`, deliberately not started.
