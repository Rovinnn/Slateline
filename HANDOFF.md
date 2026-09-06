# Handoff — final push to submission

**Deadline: Mon 7 Sep 2026, 2:00 PM PT.** Written 6 Sep.

Everything below is blocked on Google Cloud credentials that only exist on a
teammate's machine. The code is done and tested; none of it is live.

**The single most important fact:** the deployed URL judges will open is
running code from **17 commits ago**. It predates funding-availability
gating, credit monetisation, fringes, evidence display, the map, PDF export,
present value, the adversarial verification pass, and input validation. A
judge opening the live link today is scoring the weakest version of this
product while the good one sits on `master`.

Deploying is worth more than any remaining feature work.

---

## Order of operations

| # | Item | Time | Blocks |
|---|---|---|---|
| 1 | Authenticate gcloud | 2 min | everything below |
| 2 | Deploy backend + frontend | ~20 min | 3, 5 |
| 3 | Verify (smoke test + browser) | ~10 min | — |
| 4 | Repo public, license in About | 1 min | Stage 1 pass/fail |
| 5 | Demo video ≤3 min | — | 25% of the grade |
| 6 | Devpost submission | — | Stage 1 pass/fail |

Items 4 and 6 are pass/fail gates. The submission fails outright without them,
regardless of how good the product is.

---

## 1. Authenticate

`gcloud auth login` authenticates the CLI. `application-default login` is what
the `google-genai` client actually reads — both are needed.

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

All three must print OK. As of 6 Sep, Parallel passes and the other two fail
purely because no one has authenticated on this machine.

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

### In a browser — do not skip this

Nobody has opened this UI during the last two days of work. It is verified by
types, tests and a build only. Components have render tests, but **nothing has
checked what it looks like** — spacing, overflow, whether a bar is visible.

Open the live URL logged out (or in a private window — judges must reach it
with no auth) and check:

- [ ] Results load, and the hero card shows a **waterfall** walking qualifying
      spend → credit → discount → audit → wait → relocation → net.
- [ ] A **"why it wins"** block lists components that sum to the stated
      advantage.
- [ ] Each jurisdiction gets a **challenge badge** — either "re-checked
      against N sources — nothing contradicts it" (teal) or a conflict (red).
      Grey "couldn't re-check" means the challenge pass is erroring; check
      Cloud Run logs.
- [ ] The **MAP** and **COMPARE** tabs render.
- [ ] **EXPORT PDF** produces a memo with every panel expanded.
- [ ] Nothing overflows horizontally on a laptop screen.

> The adversarial verification pass has **never run against real Parallel +
> Gemini** — it's only ever been exercised with mocked model responses,
> because no one could authenticate. Its first live run will be on the
> deployed site. Watch specifically for it inventing conflicts: the prompt
> forbids treating silence as contradiction, but that behaviour is unobserved.
> If it produces nonsense, the honest fix is to stop calling the endpoint from
> `Results.tsx` — the ranking does not depend on it.

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
| **Louisiana** | 25% + 15% = up to **40%** | **$275,552** |
| New Mexico | 25% + 20% = up to **45%** | $266,994 |
| Georgia | 20% + 10% = up to **30%** | $199,621 |

New Mexico advertises the biggest number and loses. Louisiana and New Mexico
advertise the *same* 25% base and differ by $8,558 — because New Mexico's
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
