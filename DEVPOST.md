# Devpost submission — fill-in sheet

Every field the form asks for, with the answer ready to paste. Written 6 Sep
2026, after deployment. Longer prose for the description lives in
[SUBMISSION.md](SUBMISSION.md); this is the short-answer sheet.

---

## Links

| field | value |
|---|---|
| **Live URL** | https://zeta-structure-437412-v7.web.app |
| **Repo** | https://github.com/claudekootam-ship-it/incentive-verifier |
| **API** | https://incentive-verifier-backend-559874048514.us-central1.run.app |
| **Video** | _(paste once uploaded — must be public on YouTube/Vimeo)_ |
| **Track** | **Parallel** (select exactly one) |

## Tagline

> The advertised film tax credit is never the real number. This computes the
> real one, live, with receipts.

## Elevator pitch (Devpost's short field)

> Producers choose shooting locations on advertised tax-credit rates, and the
> advertised rate is never what you bank. Slateline searches each
> jurisdiction's statute live, extracts the terms with Gemini, and computes
> what the credit is actually worth after qualification rules, funding
> availability, payout mechanism, the wait to be paid, and relocation cost —
> then runs a second search pass whose only job is to disprove the first.

## Built with

`google-gemini` · `google-cloud-vertex-ai` · `google-adk` · `parallel-search-api`
· `google-maps` · `cloud-run` · `firebase-hosting` · `fastapi` · `python`
· `react` · `typescript` · `vite` · `tailwindcss` · `d3`

## Description

Paste §"The problem" through §"Data sources" from [SUBMISSION.md](SUBMISSION.md).

## Findings and learnings — **required, and our strongest section**

Paste the numbered findings from [SUBMISSION.md](SUBMISSION.md). Thirteen of
them, each with the number attached. The four that land hardest:

- Forced function calling returned a schema-valid `qualifying: {}` that
  computed a $0 credit with no error anywhere. Constraining shape is not
  constraining truth.
- Hand-verifying three statutes found three errors and **changed which
  jurisdiction the tool recommends** — after all of it had passed the full
  test suite. Testing your own output is not testing the world.
- The ADK agent recommended the wrong state with flawless reasoning, because
  one extracted input was wrong. Everything downstream of a bad input is
  impeccable, which is exactly what makes it persuasive.
- Google Maps was live, correct, and decorative: airfare was flat above a
  distance threshold, so the routed distance we fetched and drew on the map
  could not change any number.

---

## Stage 1 checklist — pass/fail

- [x] Functional, deployed, reachable **logged out** (verified in a private window)
- [x] Powered by Gemini + Google Cloud (Vertex AI, ADK agent, Cloud Run)
- [x] Exactly one partner integrated — **Parallel**, at runtime, on every request
- [x] Runs on web
- [x] Public repo, all source
- [x] **MIT license detected by GitHub** (confirmed via the API: `"license": "MIT"`)
- [x] Run instructions in [README.md](README.md) §Setup
- [x] Description incl. features, tech, data sources, findings and learnings
- [ ] **Demo video ≤3 min, public** ← the only remaining blocker
- [ ] **Devpost form submitted**
- [ ] One track selected on the form

## GitHub About sidebar — ✅ done 6 Sep

Set via the API and verified from an unauthenticated view:

- **description** — "Computes what a film tax incentive is actually worth — live
  statute search, deterministic maths, and a second pass that tries to disprove
  the first."
- **homepage** — https://zeta-structure-437412-v7.web.app
- **topics** — 10, incl. `gemini` `google-cloud` `parallel-search` `adk` `vertex-ai`
- **license** — MIT, detected by GitHub

---

## Video — the shot to open on

Not a trailer. *"A demo showing your agent functioning as built."* Impact is
scored on what you demonstrate.

Open on the ranking, because the advertised order and the real order disagree:

| | advertised | net benefit |
|---|---|---|
| **New Mexico** | 25% + uplifts | **$259,952** |
| Georgia | 20% + 10% | $175,722 |
| Louisiana / Texas | — | can't verify — discretionary |

Georgia's $400,000 credit is worth $175,722 after selling a transferable
credit at a discount, an 18-month wait, a mandatory audit and flying 18 people
3,747 km. Then open the winner's card and let the waterfall walk it down.

**Two beats now compete for strongest.** The effective rate — "advertised up
to 30%, you actually keep 8.8%" — states the entire thesis in one frame with
no narration. And the priced unknowns: "-$260,215 at risk: is the funding pool
still open?" turns the tool from analysis into a to-do list.

**The strongest single beat is the split panel** — "shoot in Louisiana, post
in New Mexico, $8,347 more than either alone", and beneath it the split that
*destroys* a credit by dropping post under Georgia's minimum. No competing
tool can produce either statement.

Suggested beats: that ranking (20s) → the split recommendation (25s) → the
waterfall (20s) → sliders reordering
live (20s) → click a source link and its retrieved date (20s) → the challenge
badge finding New Mexico's pool reported three different ways (20s) → the
"can't verify" list, refusing rather than guessing (20s) → PDF export (10s).

**Warm the site first** — a cold jurisdiction takes 30–60s to extract. Load the
page once before recording.

No third-party logos or marks.
