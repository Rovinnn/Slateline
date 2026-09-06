# Devpost submission — Incentive Verifier

Draft copy for the submission form. Sections map to the required fields:
features, tech, data sources, and "findings and learnings". Numbers here are
real outputs from the deployed pipeline — replace any that move before you
submit, rather than rounding them off.

---

## Tagline

**The advertised film tax credit is never the real number. This computes the
real one, live, with receipts.**

---

## The problem

Every US state advertises a film incentive: *"Georgia 30%!"* Producers pick
shooting locations substantially on those numbers, and the decision is worth
15–25% of a film's budget. Four things sit between the advertised rate and
money in the bank, and no public tool prices any of them:

1. **Is the money actually there?** Most states cap their annual pool. When
   it's exhausted you're in next year's queue. Programs sunset; legislatures
   suspend them mid-session. A 30% credit you can't access is 0%.
2. **How much of *your* budget qualifies?** "30%" means 30% of *qualified*
   spend. Non-resident wages are often excluded entirely, per-person caps chop
   star salaries, and minimum spend is a cliff rather than a ramp.
3. **What does being there cost?** A 30% credit somewhere you must fly and
   house 40 people for ten weeks can lose to 20% somewhere you can drive to.
4. **What's the credit worth when it arrives?** A refundable credit is paid at
   face value. A transferable one must be sold at 85–95 cents — and neither
   arrives on wrap day. A credit is a claim on future money.

Today this takes a specialist two or three days across 40 badly organised
government websites, or an incentive consultant. The existing tools publish
manually curated databases that lag legislative changes by weeks.

## What it does

Give it a budget — pick a sample, type it in, or upload a real budget PDF
(Gemini reads the topsheet and pre-fills the form, annotating each figure with
the line it came from). For each jurisdiction it then:

1. **Searches the live web** (Parallel) for the statute, film office pages,
   and recent legislative changes.
2. **Has Gemini read and extract** the rules into a structured object via
   forced function calling — the model can only quote facts, never compute.
3. **Computes the benefit in deterministic Python** — qualification by
   category, wage caps, minimum-spend cliffs, tiers, fringes, payout
   mechanism, and the discount from wrap to cash.
4. **Pulls real driving/flight distance** from Google Maps for relocation cost.
5. **Runs a second search pass whose only job is to disprove the first** —
   looking for suspensions, exhausted pools and pending amendments, and
   reporting contradictions rather than silently overwriting.
6. **Ranks by net benefit**, with every figure traceable to a dated source
   link, and anything unverifiable listed as "can't verify" rather than
   guessed.

Plus live sensitivity sliders, breakeven analysis, constraint filters, a real
vector map, and PDF export of the whole memo.

### The result it exists to produce

Three jurisdictions, a $2M indie drama, and figures hand-verified against the
statutes and state regulations rather than taken from a rate table:

| | advertised | net benefit | why |
|---|---|---|---|
| **Louisiana** | 25% + 15% = up to **40%** | **$275,552** | transferable at 90% of face, 15-month wait |
| New Mexico | 25% + 20% = up to **45%** | $266,994 | refundable and fastest, but non-resident crew don't qualify |
| Georgia | 20% + 10% = up to **30%** | $199,621 | transferable, 18-month wait, mandatory audit |

**The advertised order and the real order are not the same.** New Mexico
advertises the highest headline number and does not win. And Louisiana and New
Mexico advertise the *same* 25% base rate yet differ by $8,558, for reasons no
rate table contains: New Mexico's credit excludes non-resident below-the-line
crew (NMSA 7-2F-15 makes them a separate 15% credit capped at 15% of the BTL
budget), while Louisiana's is transferred back to the state at 90% of face and
arrives three months later.

The tool shows that reasoning as a walk from advertised rate to cash, and
decomposes the gap between any two jurisdictions into components that sum
exactly to it — gross credit, monetisation, compliance cost, payout speed and
relocation. Nothing in that explanation is written by a model; every line is a
subtraction between two computed breakdowns.

## The core architectural bet

**The language model never does arithmetic.** It reads and quotes; all
computation happens in pure Python. This is enforced by configuration —
forced function calling with `mode: "ANY"` — not by asking nicely.

## Why the partner integration is structurally necessary

You physically cannot answer *"is New Mexico's pool exhausted right now?"*
from a frozen-weights model. Incentive law changes by legislative session; a
model trained six months ago is confidently wrong. Live search isn't
decoration bolted on to satisfy a sponsor — it's the only mechanism that can
answer the question at all.

The adversarial pass sharpens this. Discovery search asks *"what is Georgia's
rate?"* and is rewarded for finding an answer. Falsification search asks
*"what would prove that wrong?"* and looks somewhere different — trade
coverage, legislative trackers, film office notices. Two structurally
different query patterns against a live index, neither of which a static model
can perform.

## Tech

- **Google Cloud / Gemini** — Gemini 2.5 Pro via Vertex AI, forced function
  calling for both extraction and the challenge pass; multimodal PDF reading
  for budget upload.
- **Parallel Search API** — three discovery queries plus four falsification
  queries per jurisdiction.
- **Google Maps Distance Matrix** — real routed distance and travel time.
- **Backend** — FastAPI on Cloud Run, stdlib dataclasses as the wire contract,
  keys in Secret Manager.
- **Frontend** — React 19 + Vite + TypeScript + Tailwind v4 on Firebase
  Hosting; d3-geo + TopoJSON vector map (no tile API, no key in the browser).
- **Tests** — 235 backend, 55 frontend, run in CI on every push.

## Data sources

State statutes and regulations, state film office pages, revenue department
guidance, and legislative trackers — all retrieved live at request time via
Parallel, never from a bundled database. Every figure on screen carries its
source URL and the date it was retrieved.

---

## Findings and learnings

The interesting failures were real, and they are the most useful thing we can
hand another team.

**1. Schema validity is not answer validity.** Forced function calling
guarantees the model returns a well-formed object. It does not guarantee the
object means anything. A live run returned `qualifying: {}` — schema-valid,
dataclass-valid — and computed a $0 credit with no error anywhere. Fixed by
requiring all six keys explicitly. The lesson generalises: constraining shape
is not constraining truth.

**2. Never ask a model a fact about your own pipeline.** We asked Gemini for
each source's `retrieved` date. It returned dates up to two years stale for
pages fetched that second, which silently downgraded fresh data to "stale"
confidence. System-time facts belong to the code that did the fetching.

**3. Arithmetic on a hallucinated input is still a hallucination.** Keeping
the model away from arithmetic protects less than it appears to, because the
*inputs* still come from a model. Firing adversarial payloads at the running
server found `base_rate: 5.0` returning a $9,520,000 credit on a $2M film with
HTTP 200 — the exact signature of a statute reading "30%" extracted as `30`.
We now refuse rather than clamp: clamping 30.0 to 1.0 would invent a 100%
credit and rank it first, which is worse than an honest gap. A negative
distance made a jurisdiction look *more* profitable, which is the sharpest
argument against silently correcting bad inputs.

**4. Two corrections, one root cause, ~$96k.** Treating Georgia's transferable
credit at face value overstated it by $40k on a $2M budget. Treating it as
cash on wrap day overstated it by a further $56k. Both came from the same
mistake: pricing a *claim on future money* as if it were money. That is the
same order as the entire relocation calculation, which had a whole assumptions
panel while timing had nothing.

**5. A conflict detector that cries wolf is worse than none.** A model asked
to find problems will find them. The adversarial pass is mostly instructions
about restraint — silence in a source is not contradiction, a surprising
figure is not contradiction — and code, not the model, decides whether a
disagreement is material. A wrong phone number must not condemn a
jurisdiction, or readers learn to ignore the flag that mattered.

**6. "We checked and found nothing" and "we couldn't check" must never render
the same.** The most dangerous state in a verification feature is the one that
looks reassuring because it's empty.

**7. Hand-verifying the statutes changed which jurisdiction wins.** Every
number had passed 235 tests, because those tests recorded our own output — a
regression test, not a correctness test. Reading O.C.G.A. § 48-7-40.26, its
implementing regulation 560-7-8-.45, and NMSA 7-2F-15 directly turned up three
real errors in a day: Georgia's $500,000 per-person salary cap was missing;
New Mexico's exclusion of non-resident below-the-line crew was not modelled,
overstating it by $67,500; and Louisiana's payout mechanism was recorded as
"unknown", which is scored at face value, so the caution *flattered* it. The
first correction moved the top recommendation from New Mexico to Louisiana.
The lesson is uncomfortable and worth stating: a well-tested pipeline computing
from unverified inputs is a confident wrong answer, and no amount of testing
the arithmetic finds it.

**8. Live extraction is not deterministic.** The same jurisdiction returns
different names between runs ("New Mexico", "USA-NM", "NM"), and occasionally
different computability. Inherent to live retrieval, and the strongest
argument for why hand-verification and conflict detection matter.

### Known limitations, stated plainly

- **Only three jurisdictions have been hand-verified** (Georgia, New Mexico,
  Louisiana, on 6 Sep 2026, against the statutes and regulations cited in
  `seed_jurisdictions.py`). Every other jurisdiction the tool can search is
  live-extracted and unchecked, and the three that were checked yielded three
  real errors — so the base rate for errors in the unchecked ones should be
  assumed to be similar, not zero.
- **The qualifying model is a boolean per spend category**, which cannot
  express New Mexico's real rule (non-resident crew at a *different rate*,
  capped at a share of the budget). We exclude them, which understates New
  Mexico by $16,875 on a $2M drama rather than overstating it by $67,500.
  Rounding toward the smaller error is a choice, and it is stated on the card.
- **Timing defaults are assumptions, not sourced facts** — the discount rate
  and per-mechanism waits are ours. They're visible and editable in the UI for
  exactly that reason, and a rule's own stated timeline overrides them.
- **First load takes 30–60 seconds** on a cold jurisdiction. Cached after.
- **US-only in practice** — non-USD programs are refused rather than converted.
- **We use `google-genai` directly, not the ADK agent framework.**

Not tax advice. Figures are estimates for comparison, and the tool says so.
