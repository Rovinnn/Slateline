# Live verification checklist

Everything that can only be checked against the **deployed** app with real
credentials. Written 6 Sep 2026. Work top to bottom — later sections assume
earlier ones passed.

Two URLs, deployed separately, so they can be different versions:

- Frontend — https://zeta-structure-437412-v7.web.app
- Backend — https://incentive-verifier-backend-559874048514.us-central1.run.app

**Severity used below:**
🔴 **blocker** — do not submit without fixing or disabling
🟡 **note** — record it in the Devpost "learnings" rather than scrambling
🟢 **info** — good to know, no action

---

## 0. Pre-flight

- [ ] `curl https://incentive-verifier-backend-559874048514.us-central1.run.app/health`
      returns `{"status":"ok"}`
- [ ] Frontend loads in a **private/incognito window** — judges must reach it
      logged out. 🔴 if it demands any auth.
- [ ] Browser devtools console shows **no CORS errors** on first load. 🔴
      If it does, `FRONTEND_ORIGINS` on Cloud Run needs the frontend origin
      (it's an env var, no code change or redeploy of the frontend needed).
- [ ] Confirm the backend is actually the new build:
      `curl -s .../openapi.json | grep -c jurisdictions/challenge` → must be
      **≥ 1**. If it's 0, the deploy didn't take — the challenge endpoint only
      exists in the new code. 🔴

---

## 1. Automated smoke test

```bash
cd backend && python scripts/smoke_test.py
```

Six checks. **All six must pass after a successful deploy.**

| check | what it proves |
|---|---|
| `health` | service is up |
| `maps distance` | Google Maps key works in prod (LA→Atlanta ≈ 3,498 km) |
| `layer 1 live` | Parallel + Gemini extraction works, names canonicalised |
| `constraint gaps` | Layer 3 annotation runs |
| `compute math` | the full face-value→cash chain reconciles |
| `batch monotonic` | more spend never yields a smaller credit |

- [ ] 6/6 pass. 🔴 if not.

> Before deploying this reports 5/6, failing `layer 1 live` with
> `expected canonical 'Georgia', got 'GA'`. That failure is **purely the stale
> deployment** — local code canonicalises correctly and has a test for it. If
> it still fails *after* deploying, the deploy didn't take.

---

## 2. Does live extraction match the verified statutes? — ✅ RUN 6 Sep

**Already done, and it found two things. Re-run only to confirm the deploy
carried the fixes; the expected values below are still the oracle.**

Results on 6 Sep, against local code with live Parallel + Gemini:

- **Georgia 6/6.** Including `per_person_wage_cap: 500000`, which our
  hand-curated seed data had missing — extraction beat hand-curation there.
- **New Mexico initially failed** on `qualifying.btl_labor_nonresident`
  exactly as predicted below. Root cause was our schema asking "is this
  qualifying spend" when the calculator needs "does this count at the base
  rate". Each key now says so, and after the fix New Mexico returns `false`
  and Georgia still returns `true`.

**This is the most valuable check on the page.**

On 6 Sep we hand-verified Georgia, New Mexico and Louisiana against the
actual statutes and found three errors. That makes those three a **correctness
oracle**: we now know the right answers, so live extraction can be graded
against them rather than just inspected.

Run each and compare. In the UI, search the jurisdiction and open its card;
or hit the API directly:

```bash
curl -s -X POST "$BACKEND/jurisdictions/search?jurisdiction=Georgia" \
  -H 'Content-Type: application/json' -d '{}' | python -m json.tool
```

### Georgia — verified truth

| field | expected | notes |
|---|---|---|
| `base_rate` | `0.20` | **not** 0.30 — the extra 10% is an uplift, not the base |
| `per_person_wage_cap` | `500000` | O.C.G.A. § 48-7-40.26 "total aggregate payroll" |
| `minimum_spend` | `500000` | |
| `credit_type` | `"transferable"` | |
| `qualifying.btl_labor_nonresident` | `true` | GA's test is territorial, not residency |
| `currency` | `"USD"` | |

- [ ] 🟡 If `base_rate` comes back `0.30`, the model folded the uplift into the
      base. Record it — it's a good "learnings" example.
- [ ] 🟡 If `per_person_wage_cap` is `null`, the model missed the cap we found
      by hand. Expected, honestly — record it.

### New Mexico — verified truth

| field | expected | notes |
|---|---|---|
| `base_rate` | `0.25` | |
| `credit_type` | `"refundable"` | |
| `qualifying.btl_labor_nonresident` | **`false`** | NMSA 7-2F-15: separate 15% credit, capped |
| `minimum_spend` | `null` | no minimum |

- [ ] 🟡 **Most likely miss.** If this comes back `true`, live extraction is
      making exactly the error we found and fixed by hand, and New Mexico will
      be over-ranked on the live site the same way it was in the seed data.
      This is the single most interesting result on this page either way —
      record what actually happens.

### Louisiana — verified truth

| field | expected | notes |
|---|---|---|
| `base_rate` | `0.25` | |
| `credit_type` | `"transferable"` | transfers back to the state at 90% of face |

- [ ] 🟡 If `credit_type` is `"unknown"`, note it — "unknown" is scored at face
      value, so it *flatters* the jurisdiction rather than penalising it.

> **Do not "fix" the live extraction by editing seed data.** The seed set is
> the oracle; the live pipeline is what's being graded. A disagreement is a
> finding to write down, not a bug to paper over before submitting.

---

## 3. Code paths that have NEVER run live

These were written and unit-tested with mocked model responses, because nobody
could authenticate. **Their first real execution will be on the deployed
site.**

### 3a. The adversarial challenge pass — ✅ RUN 6 Sep, bug found and fixed

**The predicted failure happened.** First live run reported four "material
contradictions" for Georgia, all of the form "we have: not stated" versus a
source saying "no cap" — sources that agree. It was treating our own missing
value as a contradictable position. Fixed with a code guard: a contradiction
needs a concrete held value to disagree with.

After the fix: Georgia 4 findings → 1 (`under_review`, citing a real source),
New Mexico 7 → 2 (annual pool reported as $140M by us, $100M and $130M
elsewhere — a genuine funding-availability disagreement).

Re-run against the deployment to confirm, using the recipe below.

### 3a-bis. Original instructions

```bash
curl -s -X POST "$BACKEND/jurisdictions/challenge" \
  -H 'Content-Type: application/json' \
  -d "$(curl -s -X POST "$BACKEND/jurisdictions/search?jurisdiction=Georgia" \
        -H 'Content-Type: application/json' -d '{}')" | python -m json.tool
```

Response has `rule` (annotated) and `report`
(`jurisdiction`, `findings`, `corroborated_fields`, `sources_checked`).

- [ ] `sources_checked` > 0. If it's 0, the falsification search returned
      nothing and the badge will correctly read "couldn't re-check".
- [ ] **Read every entry in `findings` and judge whether it is a real
      contradiction.** Each has `field_name`, `current_value`, `source_says`,
      `url`, `excerpt`, `severity`.
- [ ] 🔴 **The failure mode to watch for: invented conflicts.** The prompt
      forbids treating a source's *silence* as contradiction, but that
      behaviour has never been observed. Signs it's misbehaving:
      - a `finding` whose `excerpt` doesn't actually contradict `current_value`
      - contradictions reported on nearly every jurisdiction
      - `source_says` that paraphrases rather than quotes
- [ ] 🔴 **If it produces nonsense, the fix is to stop calling it** — remove
      the `challengeJurisdiction` effect from `frontend/src/screens/Results.tsx`
      and redeploy the frontend. **The ranking does not depend on it.** A
      wrong conflict flag makes the product look less trustworthy, not more,
      which is the opposite of what the feature is for.

### 3b. The ADK agent — ✅ RUN 6 Sep, bug found and fixed

Ran end to end. Correct tool order (`set_budget` → `search_jurisdiction` ×2 →
`get_travel_distance` ×2 → `compare_jurisdictions` → `challenge_jurisdiction`
→ `compute_benefit_for`), and **every figure in its answer came from a tool
result** — the instruction held.

It also caught a real bug by doing so: New Mexico's extraction returned a
per-project cap that zeroed a $415,625 credit, giving it a negative net
benefit and handing the ranking to Georgia. A $0 cap is now refused. Re-run
after deploying and confirm the ranking is sane.

Original note: never run against live Vertex — no credentials existed on the machine it was
written on. Its tools are tested against the real calculator and the CLI is
verified up to the credential boundary, but the model's actual tool-selection
behaviour is unobserved.

```bash
cd backend && python scripts/run_agent.py   "We have a $2M drama shooting 22 days out of LA with 45 crew. Georgia or New Mexico?"
```

Every tool call prints as it happens.

- [ ] It calls `set_budget` first, then `search_jurisdiction` per jurisdiction,
      then `compare_jurisdictions`.
- [ ] 🔴 **Read the final answer against the tool output printed above it.**
      Every figure the agent states must appear verbatim in a tool result. If
      it states a number that isn't there — a percentage it worked out, a
      difference it subtracted — the instruction in `agent.py` has failed.
      That's the one failure that would matter, because it's the claim the
      whole project rests on.
- [ ] 🟢 This is additive. `app/main.py` and the deployed frontend don't use
      it, so a problem here doesn't block submitting.

### 3c. New extraction fields

`months_to_payment`, `audit_required`, `currency`, `credit_type` and
`fringes_qualify` are in the schema; some have never been extracted live.

- [ ] `months_to_payment` is `null` for most jurisdictions. 🟢 **This is
      correct, not a bug** — payment timing is rarely in statute, and the
      schema explicitly tells the model to return null rather than estimate.
      The UI should then say "typical wait, assumed".
- [ ] 🟡 If `months_to_payment` comes back populated for *every* jurisdiction
      with suspiciously round numbers, the model is inventing them despite
      being told not to. Record it.

### 3d. Input validation against real extraction

- [ ] 🟢 Watch for any jurisdiction landing in "can't verify" with a message
      about a rate being "outside the possible 0-100% range". That means the
      model returned e.g. `30` instead of `0.30` and the guard caught it —
      **working as designed, and a great thing to show in the video.**

---

## 4. The UI, which nobody has opened

Verified by types, tests and a build only. Render tests cover the two
recommendation components, but **nothing has checked what it looks like** —
spacing, overflow, whether bars are visible.

Open the live site and check:

**Hero card**
- [ ] A **waterfall** walks: qualifying spend → credit at X% → monetisation
      discount → realizable → audit → waiting N months → worth today →
      relocation → net benefit. Stages only appear when they apply.
- [ ] Bars are visible and none overflow their row. 🔴 if a bar runs past the
      card edge.
- [ ] **"Why it wins"** lists components that visibly sum to the stated net
      advantage. Add them up by hand once. 🔴 if they don't reconcile.
- [ ] Components working *against* the winner show as negative (red), not
      hidden.

**Per-jurisdiction**
- [ ] **Challenge badge** shows one of: "re-checked against N sources —
      nothing contradicts it" (teal) / a conflict (red) / "couldn't re-check"
      (grey) / "re-checking…" while in flight.
- [ ] 🔴 A **grey** badge on every jurisdiction means the challenge endpoint is
      erroring — check Cloud Run logs. It must never render teal in that case.
- [ ] Source links open, and each shows a `retrieved` date of **today**.
      🔴 if dates are months/years old — that was a real bug once.
- [ ] "refresh" link re-runs a live extraction for that one jurisdiction.

**Panels and tabs**
- [ ] Sensitivity sliders reorder the ranking live.
- [ ] **"When the credit becomes money"** panel opens and its fields are
      editable. Setting the rate to `0` should make present value equal
      realizable — the whole timing feature switches off cleanly.
- [ ] Relocation assumptions panel opens and edits recompute.
- [ ] **COMPARE** tab renders a table.
- [ ] **MAP** tab renders real coastlines with the home base and jurisdictions
      marked.
- [ ] "Can't verify" section lists excluded jurisdictions with reasons.

**Form**
- [ ] Type a **negative** number into any budget line → RUN COMPARISON greys
      out and a red message names the offending field.
- [ ] Upload a budget PDF (`samples/sample-budget-bluewater.pdf`) → form
      pre-fills with per-field provenance notes.

**Export**
- [ ] **EXPORT PDF** → print dialog → "Save as PDF" produces a memo with
      *every* panel expanded, all jurisdictions, assumptions, and the
      can't-verify list — regardless of what was collapsed on screen.
- [ ] Nothing overflows horizontally at laptop width.

---

## 5. The judge's experience

- [ ] Cold load time, measured. 🟡 30–60s is expected on a cold jurisdiction
      (live search + extraction each). **Warm it by loading the page once
      before recording the video or before judging opens.**
- [ ] Second load is fast (cache hit).
- [ ] 🟢 A Cloud Run cold start or a second instance means one more live
      search — never a wrong answer. Cache is process-local by design.
- [ ] No key or secret appears anywhere in the page source or network tab. 🔴
      The map is vector data with no tile API, so there should be no Maps key
      in the browser at all.

---

## 6. Version skew

Frontend and backend deploy separately and can end up different versions.

- [ ] Deploy **backend first**, then frontend.
- [ ] 🟢 An older backend is handled deliberately: the frontend falls back to
      values that reproduce the older arithmetic exactly, so the page renders
      a coherent (if older) answer rather than `undefined`. If the waterfall
      is missing its audit/timing stages, that's the fallback working — the
      backend is stale, not the page broken.

---

## What to record

For each 🟡 above, write down what actually happened. Those go straight into
the Devpost **"findings and learnings"** section, which is where this project
is strongest — see [SUBMISSION.md](SUBMISSION.md). A live extraction getting
New Mexico's non-resident crew rule wrong is a *better* submission story than
one that quietly worked, because it's evidence the hand-verification mattered.
