# Next steps — 2026-09-04

Written at the end of a working session, for whoever picks this up (including
future me). Supersedes the forward-looking half of [PROGRESS.md](PROGRESS.md),
which is now a historical snapshot from Aug 30.

**Deadline reality check.** `BUILD_BRIEF.md` says 9 Sep; the track map says
**7 Sep, 2:00 PM PT**, notes three of four official references agree on the
7th, and recommends **submitting on the 5th** with the 6th–7th held as buffer
"for the failure you haven't had yet". Treat the 5th as the date. That means
roughly **one working day**, which should dominate every priority call below.

---

## 1. Blocking — submission fails without these

> **See [HANDOFF.md](HANDOFF.md) for the executable version of this section**
> — exact commands, verification steps and gotchas, written 6 Sep for whoever
> has the Google Cloud credentials. The table below is the summary; that file
> is what to actually work from.

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | **Make the repo public** | teammate | Currently private. The checklist requires "repo public; license detectable in the About section". MIT LICENSE is already at repo root, so this is a settings toggle. Stage 1 is pass/fail. |
| 2 | **Demo video, ≤3 min, public on YouTube/Vimeo** | teammate | Not started. The track map is explicit that *"the video carries the impact score, not the README"* — it's load-bearing for 25% of the grade. Show the product working in the first 20 seconds; no third-party logos or marks. |
| 3 | **Redeploy backend + frontend** | needs gcloud | Everything from `d8f0cc3` onward is on master and **not live**: name canonicalisation, pipeline-stamped `retrieved` dates, PDF upload/export, the real map, the compare tab, evidence display, funding availability, fringes and credit monetisation. A judge opening the live URL today sees none of it. |
| 4 | **Devpost submission** | teammate | Description needs features, tech, data sources, and explicitly *"findings and learnings"*. Verify the hosted URL logged-out from a different network. |

`backend/scripts/smoke_test.py` run against production is the fastest way to
confirm #3 worked — it currently reports 4/6, and the two failures are exactly
the bugs already fixed in the repo.

---

## 2. Product work, in priority order

Each of these is scoped and understood; none is speculative.

### 2.1 Currency guard — ~1 hour, do this first — ✅ done
Searching "Ireland" today returns Section 481 with `base_rate: 0.32` and a
`per_project_cap` of 125,000,000 — **euros, silently compared as dollars.**
There is no currency field anywhere in the codebase.

The brief forbids multi-currency support, so the fix isn't FX rates — it's the
brief's *own* existing pattern: detect a non-USD jurisdiction, set
`computable = False` with a reason, and let it land in the "Can't verify"
section saying so. That converts a confidently wrong number into an honest
one, which is the whole thesis of the product.

Done: `JurisdictionRule.currency` (required in the extraction schema, same
tier as `base_rate` — see `models.py`/`agent.py`), and `calculator.py` returns
`computable=False` with the currency named in `non_computable_reason` for
anything not stated in USD.

### 2.2 Cache extractions — ~2 hours, and it's a demo risk — ✅ done
Every results load fires 4 live Layer 1 extractions: 12 Parallel searches plus
4 Gemini 2.5 Pro calls. **First paint is 30–60 seconds.** A judge opens the
link, watches a spinner, and forms an opinion before anything renders.

Cache per jurisdiction with the retrieval date shown and an explicit "refresh"
control. Faster, far cheaper in quota, and *more* honest rather than less,
because the date becomes visible instead of implied.

Done: `app/cache.py`, an in-process per-jurisdiction cache; `/jurisdictions/search`
serves a cached rule instantly unless `refresh=true`. The frontend exposes a
"refresh" link next to every jurisdiction's retrieved-date citation (hero,
runner-up, and Can't-verify cards), and the initial load now shows
per-jurisdiction progress ("Georgia — searching statute and film-office
pages" → "— extracted") instead of one generic spinner.

### 2.3 Statute hand-verification — ~half a day
Build order step 3 says *"verify a few by hand against the actual statutes"*
and section 9 wants *"hand-verified"* golden values. **This has never been
done.** Our golden numbers were produced by running our own code and recording
its output — that's a regression test, not a correctness test.

There is already evidence the extraction is shaky: names alternate between
"New Mexico" and "USA-NM" between runs, Louisiana flipped from computable to
discretionary between runs, and one run returned source `retrieved` dates two
years stale. Read O.C.G.A. § 48-7-40.26, NMSA 7-2F and Louisiana's program
rules, compare field by field, fix what's wrong, and record genuinely verified
golden values. This is the work most likely to expose real bugs.

### 2.4 ADK agent wrapper — ~half a day
Universal requirements say *"Powered by Gemini **and Google Cloud Agent
Builder**"*, and track map §4 is titled *"Build on ADK, Not Wrapper
Libraries"*. We call `google-genai` directly; `google-adk` is in
`pyproject.toml` but **imported nowhere**.

The disqualification checklist accepts `google-genai`, so this probably isn't
a Stage 1 failure — but Technological Implementation (25%) explicitly rewards
*"ADK agent, multi-step tool use"*. Wrapping the three existing tools
(`parallel_search`, `compute_benefit`, `get_distance`) as ADK tools would also
satisfy the brief's own *"the agent must invoke the calculator tool"* line,
which we skipped by building a pipeline instead.

### 2.5 Conflict detection — ✅ done (via §6.3)
Brief section 4 says Layer 3 *"**cross-checks values across retrieved
sources**"*, and build order step 8 lists *"conflict detection"*. We assign
confidence and mark non-computable programs, but **nothing compares source A
against source B.** `conflicts` is only ever `setdefault("conflicts", [])`,
which makes the `"conflicting"` confidence state effectively unreachable from
our own code (the model does occasionally populate it directly).

Needs 2+ sources per field to compare, so it's the most work for the least
visible payoff. Last of the five.

**Done**, but not the way this described. Rather than diffing the discovery
pass's own sources against each other, the adversarial pass in §6.3 goes and
*finds* contradicting sources — which is strictly better, because the
discovery pass tends to return sources that agree (they're all restating the
same statute). `conflicts` is now populated by `apply_challenge`, so
`confidence: "conflicting"` is reachable from our own code for the first
time.

---

## 3. UI and design suggestions

Design is 25% of the score and the track map warns it's *"where infra-heavy
projects bleed"*. Ours is a genuine strength — a real workflow tool, not a
chat box — so these are refinements, not rescues.

### 3.1 Map in the hero — worth doing, with one condition

Proposed: put the map into the hero card so the results screen feels more
alive and interactive.

**My honest read: do it, but as an *explanatory* element, not decoration.**
The risk is real — the brief calls the map *"a supporting view, not the
hero"*, and the critique this project has already had once is that it looks
like a concept with surface but no substance. A decorative map makes that
worse, and "non-obvious use" is scored explicitly.

The version that earns its place: a **small inline map strip inside the hero
card** showing home base → the winning jurisdiction, with the real routed
distance and travel time labelled on the line. That isn't ornament — it
*explains the relocation line item*, which is one of the four components of
the net number, and it turns an abstract "−$114,900 relocation" into
something a producer can see. Click it to open the full MAP tab.

Concretely:
- Reuse `MapView` with a `compact` variant (fixed ~260×120, two points only,
  no legend, no labels beyond the distance).
- Place it directly beside or beneath the `gross − relocation = net` line,
  where it's visually attached to the number it explains.
- Keep the full MAP tab as-is for the multi-jurisdiction view.

What I'd avoid: making the hero map the primary interaction, animating it, or
adding hotel/POI pins. That drifts straight back into decorating the weakest
pillar.

### 3.2 "What would change this" panel — ~2 hours, high value
Under the winner: *"New Mexico leads until ATL exceeds $11.1M. Hire 60% local
instead of 40% and Georgia wins instead."* The sweep behind this is **already
computed** for the breakeven sparkline — this is presentation, not new maths.
It's the difference between a ranking and advice, and it's the single best
line to have on screen during the video.

### 3.3 Smaller polish
- **Loading state is too silent.** ✅ done — During the 30–60s extraction, say
  what's happening ("searching Georgia… reading statute…"), per jurisdiction.
  Cheap, and it makes the wait feel like work rather than a hang.
- **`large_soundstage` constraint is a no-op.** ✅ done — It never flags
  anything by design (no reliable facilities data — see `constraints.py`),
  but the chip gives no hint of that. Add a "not yet evaluated" note so it
  doesn't read as broken.
- **Runner-up cards duplicate the COMPARE tab.** Consider trimming the memo's
  runner-up list now that the table exists.

---

## 4. Deliberately not doing — recorded so it isn't re-litigated

- **Hotel / commute price lookups.** Productions negotiate block rates; a
  live nightly rate would be more precise-looking and less accurate. If
  relocation fidelity ever becomes the priority, the right source is the
  [GSA per-diem API](https://open.gsa.gov/api/perdiem/) — free, authoritative,
  county-level, seasonal — not a hotel scraper. Deferred because relocation is
  the *least* defensible pillar and the one least likely to flip a decision on
  a large budget.
- **Drive-time isochrones.** Explicitly on the brief's "do not build" list,
  and rightly — they'd look impressive and change no decision.
- **Multi-currency.** Forbidden by the brief. See §2.1 for the honest
  alternative.
- **Tile maps (Google Maps JS, Mapbox).** Another billed API and a key exposed
  in the browser, for a supporting view. Vector boundaries already give real
  coastlines with no key.

---

## 5. Known limitations to disclose in the write-up

The Devpost description asks for *"findings and learnings"*. These are honest
and worth stating rather than hiding — they're also the most interesting part
of the build:

1. **Live extraction is not deterministic.** The same jurisdiction returns
   different names, and occasionally different computability, between runs.
   That's inherent to live retrieval against a frozen-weights model, and it's
   the strongest argument for why hand-verification and conflict detection
   matter.
2. **Forced function calling doesn't prevent silent wrongness.** A live run
   returned `qualifying: {}` — schema-valid, dataclass-valid, and it computed
   a $0 credit with no error. Fixed by requiring all six keys explicitly; the
   lesson is that schema validity is not answer validity.
3. **The model shouldn't be asked facts about our own pipeline.** Asking it
   for a `retrieved` date produced dates two years stale for pages fetched
   that second, which silently downgraded fresh data to `stale` confidence.
   System-time facts belong to the code.
4. **The breakeven crossover branch is unreachable with real data.** All three
   ranked jurisdictions are flat-rate with no caps, so ranking is invariant to
   spend. It's covered by tests using mocked curves, and will surface once a
   tiered or capped jurisdiction enters the set.
5. **Fringes and payout mechanism moved the answer by ~$100k on a $2.5M
   budget** — the same order as the entire relocation calculation. Georgia's
   net fell from $295,900 to $255,900 once its credit was correctly treated as
   transferable rather than face value.

---

## 6. Proposed next features — not yet scoped/started

### 6.1 Present value — ✅ done
**Outcome:** `CreditTimingAssumptions` (visible and editable, like relocation
assumptions), `months_to_payment` and `audit_required` on the rule (extracted
only where a source states them, null otherwise), and `present_value` /
`audit_cost` / `timing_note` on the breakdown. `net_benefit` now nets the
present value.

**What it actually changed:** on the four seed jurisdictions it moved every
net benefit by $53k-$66k on a $2M budget — the same order as the entire
relocation calculation — but it did **not** change who wins. What it did
change is that New Mexico and Louisiana stopped being exactly tied at
$395,900; they now differ by $12,471 on payout speed alone, which the tool
previously had no basis to distinguish. Reordering is demonstrated on
constructed rules in `test_present_value.py`, not claimed of this dataset.

**What:** Stop treating a credit as cash today. Chain it: face value →
monetization type → transfer discount → months to payment → discount rate →
present value. Add interim financing cost if you borrow against it in the
meantime.

**Why it's first:** The Georgia card already says "credit is transferable"
and then quietly counts it at 100 cents. That's the one factually soft claim
in an otherwise rigorous product. A refundable credit paid in six months and
a transferable credit sold at 88 cents paid in twenty months are different
instruments with identical headline rates — and the gap between them can
exceed the gap between two jurisdictions' rates entirely. So this can
reorder rankings, which makes it load-bearing rather than cosmetic.

**Cost:** Three fields on `JurisdictionRule`, one chained calculation, one
display line. Half a day. Best value-per-hour on this list by a wide margin.

### 6.2 Split-location allocation
**What:** Stop assuming one answer. Principal photography in one
jurisdiction, post and VFX in another. Solve for the allocation subject to
each program's minimum spend and qualifying rules.

**Why:** The genuinely non-obvious one. Every comparison tool in existence
assumes a single destination, because a table has one row per place. Real
productions split constantly — post-only and VFX-specific incentives exist
precisely to attract that spend separately. Turning the sort into a small
optimization produces answers no incumbent can produce, and it hits
"creative, non-obvious use" harder than anything else here.

**Watch out:** minimum spend is a cliff, so splitting can drop you below a
threshold and zero out a credit you'd otherwise have earned. That
interaction is the interesting part — surface it rather than hiding it.

**Cost:** A day, maybe two. The calculator already handles the
per-jurisdiction math; this is a search over combinations of it.

### 6.3 Adversarial verification — ✅ done
**Outcome:** `app/extraction/challenge.py` — a second Parallel + Gemini pass
searching for suspensions, exhausted pools, pending amendments and trade
coverage, forced (mode=ANY) into `record_challenge_result`. Exposed as
`POST /jurisdictions/challenge`, called *after* results render so it annotates
rather than delaying an already slow first paint.

Three rules keep it honest, each with tests: silence in a source is not a
contradiction (a model rewarded for finding problems will find them); it
reports and never overwrites a figure; and code, not the model, decides
whether a disagreement is material — a wrong phone number does not condemn a
jurisdiction. Finding nothing is recorded as a result, and "checked against 4
sources, nothing contradicts it" is rendered distinctly from "couldn't
check", which must never read as a clean bill of health.

**What:** A second agent pass whose only job is to disprove the first. It
searches for amendments, pending bills, pool exhaustion notices, and trade
coverage contradicting what the extraction pass found — then reports the
conflict rather than silently overwriting.

**Why:** It makes the agent architecture the interesting thing, not just the
plumbing around a search API. It's the honest answer to "how do I know your
extraction is right," and it's a real multi-agent structure that the problem
actually justifies. It also deepens the Parallel integration, since
falsification search is a structurally different query pattern from
discovery search.

**Cost:** A day. Reuses existing search tooling and the existing `conflicts`
field.

### 6.4 Crew depth
**What:** Replace the user's `resident_labor_pct` guess with a sourced
default from film office crew directories, union local rosters, and hub
listings — shown with a citation like every other number.

**Why:** The biggest hole in the model, and easy to miss. Resident labor
share drives qualifying spend, which drives the credit, which drives the
ranking. Right now the single most influential input is a number the user
made up. Everything else in the product is sourced and dated; this one
isn't, and it's the one that matters most.

It also fixes something subtle: crew depth and distance are correlated.
Remote jurisdictions have thinner crews, so more people get imported, so
more labor fails to qualify and relocation cost rises. Two existing
penalties compound, and right now the model can't see it.

**Cost:** A day. Search quality varies by jurisdiction, so fall back to the
user's estimate with lower confidence where it can't be sourced.
