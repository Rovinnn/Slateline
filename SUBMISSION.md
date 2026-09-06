# Devpost submission — Slateline

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
| **Louisiana** | 25% + 15% = up to **40%** | **$265,564** | transferable at 90% of face, 15-month wait, 3,049 km away |
| New Mexico | 25% + 20% = up to **45%** | $260,215 | refundable, fastest, closest — but non-resident crew don't qualify |
| Georgia | 20% + 10% = up to **30%** | $188,825 | transferable, 18-month wait, mandatory audit, furthest away |

Figures use real Google Maps routed distances from Los Angeles.

**The advertised order and the real order are not the same.** New Mexico
advertises the highest headline number and does not win. And Louisiana and New
Mexico advertise the *same* 25% base rate yet differ by $5,350, for reasons no
rate table contains: New Mexico's credit excludes non-resident below-the-line
crew (NMSA 7-2F-15 makes them a separate 15% credit capped at 15% of the BTL
budget), while Louisiana's is transferred back to the state at 90% of face and
arrives three months later. New Mexico claws part of the gap back by being
1,783 km closer to Los Angeles — which the model only registers because
airfare scales with distance rather than being flat.

The tool shows that reasoning as a walk from advertised rate to cash, and
decomposes the gap between any two jurisdictions into components that sum
exactly to it — gross credit, monetisation, compliance cost, payout speed and
relocation. Nothing in that explanation is written by a model; every line is a
subtraction between two computed breakdowns.

### From analysis to advice

Two numbers open the recommendation, because the collapse is the product:

```
ADVERTISED AS UP TO        YOU ACTUALLY KEEP
30.0%              ->      8.8%
```

And every time the calculator refuses to guess, it leaves an unknown. Those
used to be a flat list of caveats where nothing separated a $2,000 question
from a $200,000 one. They're now priced and ranked — because they are the
highest-value phone calls a producer can make:

| | |
|---|---|
| **−$260,215** at risk | Is New Mexico's annual funding pool still open? |
| **+$151,861** if confirmed | Does the Georgia promotional-logo uplift apply? |
| **+$148,437** if confirmed | Is the shoot 60+ miles outside Albuquerque? |
| **+$51,025** if confirmed | Do employer fringes count as qualified spend? |

Each figure is that jurisdiction's net benefit recomputed with the question
answered the other way — a difference between two runs of the same calculator,
never an estimate. That's the only reason they can sit beside the verified
numbers.

### The thing no rate table can answer

**Shoot in one jurisdiction, post in another.** Every incentive comparison
tool assumes a single destination, because a table has one row per place and
this needs combinations of them. Real productions split constantly — post-only
and VFX-specific credits exist precisely to attract that spend separately.

On the hand-verified seed set: **shoot in Louisiana, post in New Mexico —
$273,911, or $8,347 more than any single location.** It works because New
Mexico has no minimum spend, so a $250k post budget still earns its full 25%
refundable.

The more interesting output is when splitting *loses*. Minimum spend is a
cliff, not a ramp, so dividing the budget can drop a leg under its threshold
and destroy a credit that would have been earned whole:

> Shoot Louisiana, post Georgia: splitting drops post and VFX in Georgia below
> its minimum spend, so that leg earns nothing — it would have qualified as
> part of a single-location shoot.

That trap is invisible to any single-destination ranking, and a producer who
split on instinct would discover it at audit. The panel renders in both
directions on purpose: one that only appeared when splitting won would teach
nothing on the runs it stayed silent.

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
- **Google Cloud Agent Builder / ADK** — an `LlmAgent` over six tools
  (`set_budget`, `search_jurisdiction`, `get_travel_distance`,
  `compute_benefit_for`, `compare_jurisdictions`, `challenge_jurisdiction`),
  routed through Vertex. Tools address jurisdictions **by name**: the model
  chooses what to compute and in what order, and never carries a figure
  between steps, so its planning cannot corrupt a number in transit.
- **Backend** — FastAPI on Cloud Run, stdlib dataclasses as the wire contract,
  keys in Secret Manager.
- **Frontend** — React 19 + Vite + TypeScript + Tailwind v4 on Firebase
  Hosting; d3-geo + TopoJSON vector map (no tile API, no key in the browser).
- **Tests** — 313 backend, 92 frontend, run in CI on every push.

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
number had passed the entire test suite, because those tests recorded our own output — a
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

**8. One library, two Google products, one confusing error.** ADK builds its
own genai client and defaults to the Gemini *Developer* API, so the agent
failed with "No API key was provided" and a link to ai.google.dev — while
every other part of Layer 1 was authenticating to Vertex with
application-default credentials and no API key anywhere. The fix is one
environment variable (`GOOGLE_GENAI_USE_VERTEXAI`), but the failure reads like
a missing secret rather than a missing setting, and we only found it by
running the thing rather than by reading about it.

**9. An integration can be live, correct, and still decorative.** Google Maps
returned real routed distances from day one, and they were drawn on the map
and shown on the memo. But airfare above the 800 km flight threshold was a
flat per-person figure, so every jurisdiction beyond it cost exactly the same
to reach: New Mexico at 1,266 km priced identically to Georgia at 3,498 km,
$114,900 of relocation for both. The distance was fetched, displayed, and
changed no number in the ranking. Found only by running real distances through
the model rather than fixtures. Airfare now has a distance component, and
there's a test asserting that flying further costs more — which sounds too
obvious to need testing, and wasn't true for months.

**10. The model beat us on one field, and we had asked it the wrong question
on another.** Grading live extraction against the hand-verified statutes:
Georgia came back 6/6 — including the $500,000 per-person wage cap our own
hand-curated seed data had missing. New Mexico failed on one field, and it
turned out we had posed the question badly. The schema asked "is this category
qualifying spend", and New Mexico's non-resident crew *do* get a credit — a
separate one, at 15% instead of 25%, capped at a share of the budget. Under
that reading the model's answer was defensible. Rewriting the field to ask
what the calculator actually needs — "does this count toward the base the base
rate multiplies?" — fixed it, and Georgia stayed correct, which is the control
that mattered: a prompt that merely frightened the model into saying no
everywhere would have broken it.

**11. A conflict detector's hardest job is staying quiet.** The adversarial
pass's first live run reported four "material contradictions" for Georgia,
every one of the form "we have: not stated" against a source saying "no cap"
or "no sunset clause" — sources that *agree*. It hadn't disobeyed the
instruction not to treat silence as contradiction; it had treated *our own*
missing value as a position a source could contradict, which the instruction
never covered. Fixed in code rather than prompt, because prompting had already
demonstrated its limits here. Georgia went 4 findings to 1, New Mexico 7 to 2,
and the survivors are real — New Mexico's annual pool is reported as $140M by
us and $100M and $130M by others, a genuine disagreement about funding
availability, which is the whole wedge.

**12. Everything downstream of a bad input is impeccable, which is the
problem.** The ADK agent's first live run recommended Georgia over New Mexico.
The reasoning was flawless: New Mexico's extraction had returned a per-project
cap that reduced a $415,625 credit to $0, the production still paid to
relocate, so its net benefit went negative. Every step after the bad input was
computed correctly from it, which is exactly what made the wrong answer
persuasive. A $0 ceiling describes no real program — it is "no cap" misread —
and is now refused. The same lesson as finding 3, arriving from a completely
different direction: keeping a model away from arithmetic protects nothing if
it supplies the arithmetic's inputs.

**13. Live extraction is not deterministic.** The same jurisdiction returns
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
- **US-only in practice, by refusal rather than by omission.** Any
  jurisdiction can be searched and extracted — Ireland's Section 481 comes
  back correctly at 32% in EUR — but the calculator refuses to rank a non-USD
  program rather than converting it, because comparing euros against dollars
  with no unit anywhere would be a confidently wrong number. Non-USD programs
  land in "can't verify" with the currency named. Supporting them properly
  means FX rates and a per-jurisdiction currency on every figure, not a
  one-line change.
- **US-specific constraint data.** The "ocean coastline" filter knows US state
  geography and nothing else, so it makes no claim either way about a non-US
  jurisdiction rather than guessing.
- **The ADK agent's own planning has never run against live Vertex.** Its
  tools are tested against the real calculator, its declarations are checked,
  and the CLI wiring is verified up to the credential boundary — but nobody
  could authenticate on the machine it was written on, so the model's actual
  tool-selection behaviour is unobserved. The REST pipeline, which is what the
  deployed frontend uses, is unaffected by this and unchanged.

Not tax advice. Figures are estimates for comparison, and the tool says so.
