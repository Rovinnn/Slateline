# Demo video script — Slateline

Target runtime: **2:40–2:55** (hard cap 3:00). Screen-record the live app at
https://zeta-structure-437412-v7.web.app — do not use mockups or the design-canvas
file. No third-party logos/marks on screen (no Google, Gemini, or Parallel branding) —
name the technologies only in voiceover, since the brief disqualifies visible marks.

Record at 1920×1080, cursor visible, no browser chrome/bookmarks bar showing personal
info. Zoom to ~125% in the browser before recording so text is legible when the video
is compressed for YouTube.

Legend: **[VISUAL]** what's on screen · **VO** voiceover (read at a normal pace,
not rushed) · **on-screen text** = a lower-third caption to add in post, not narrated.

---

## 0:00–0:18 — Cold open, product already running

**[VISUAL]** Hard cut straight into the app: budget form pre-filled ($2,000,000 indie
drama, Los Angeles home base), cursor clicks **Compare**. No title card first — the
product must be visibly functioning before the 20-second mark.

**VO:**
> "This is Slateline. You give it a production budget — here, a two-million
> dollar indie drama shooting out of LA — and it tells you what a film tax incentive
> is actually worth. Not the advertised rate. The real number."

---

## 0:18–0:45 — Live search, not a lookup table

**[VISUAL]** Loading state: per-jurisdiction progress lines rendering in real time —
"Georgia — searching statute and film-office pages" → "— extracted", same for New
Mexico, Louisiana, Texas.

**VO:**
> "Every state advertises a headline percentage, and that's where most tools stop.
> This one runs a live web search against each jurisdiction's actual statute right
> now, has a language model extract the terms, and hands every number to plain
> Python to compute — the model never does arithmetic, it only reads and quotes."

**on-screen text:** *"Live search, not a static database"*

---

## 0:45–1:15 — The hero result and what it's made of

**[VISUAL]** Results screen loads. **Hold on the two figures at the top of the hero
card for a full beat before scrolling** — this is the strongest frame in the video and
it needs no narration to land:

```
ADVERTISED AS UP TO        YOU ACTUALLY KEEP
30.0%              →       8.8%
```

Then scroll to the waterfall beneath it, which walks that collapse stage by stage, and
the map strip showing LA → Albuquerque with the routed distance labelled on the line.

**VO:**
> "Every state advertises a number like thirty percent. This is what a producer
> actually keeps on a two-million-dollar film — and the gap isn't one deduction, it's
> five. How much of the budget qualifies. Whether the credit is paid in cash or has to
> be sold to a taxpayer at a discount. A mandatory audit. Eighteen months of waiting to
> be paid. And what it costs to fly and house the crew. The waterfall shows every one
> of them."

**on-screen text:** *"advertised rate → qualifying spend → monetisation → audit → the
wait → relocation → what you keep"*

> **Accuracy note:** don't say "gross minus relocation equals net" on screen. The real
> chain is `gross + monetisation discount − audit + timing loss − relocation`, and the
> waterfall renders exactly that. A simplified equation that doesn't match what's
> visible is the one thing a finance-literate judge will catch.

---

## 1:15–1:40 — The adversarial pass

**[VISUAL]** Scroll to / hover the confidence badge on a jurisdiction card — the
"checked against N sources, nothing contradicts it" state (or a "conflicting" state if
one is present in the current run).

**VO:**
> "After the first search finds the terms, a second, independent search pass runs
> whose only job is to disprove the first — looking for suspended programs, exhausted
> pools, and pending amendments the discovery pass would never think to look for. It
> reports contradictions instead of silently overwriting a number, and it never treats
> silence as a clean bill of health."

**on-screen text:** *"A second search pass tries to prove the first one wrong"*

---

## 1:40–2:00 — Honesty over confidence

**[VISUAL]** Scroll to the "Can't verify" section; show Louisiana/Texas listed as
excluded from the ranking with the reason (discretionary program, not modelable).

**VO:**
> "And when a program genuinely can't be modeled — a discretionary incentive with no
> published formula — it says so, instead of guessing a number that looks precise and
> isn't."

**on-screen text:** *"Can't verify — excluded from the ranking, not guessed"*

**[VISUAL]** Scroll up slightly to **"Before you commit to [jurisdiction]"** — the
priced unknowns, sorted with the risk at the top.

**VO:**
> "And where it can't be certain, it prices the uncertainty. These aren't disclaimers —
> they're the highest-value phone calls this producer can make, ranked by what turns on
> them. The funding pool question is worth the entire benefit, because a credit you
> can't be allocated is worth nothing. Each figure is the same calculation re-run with
> that question answered the other way. Nothing here is estimated."

**on-screen text:** *"−$260,215 at risk · +$151,861 if confirmed"*

---

## 2:00–2:25 — The non-obvious feature: splitting the production

**[VISUAL]** Scroll to the split-allocation panel; show "Splitting the production does
better" with principal photography in one jurisdiction and post/VFX in another, each
net figure.

**VO:**
> "Every rate-comparison tool assumes one destination, because a table only has one
> row per place. Real productions split constantly — shoot in one state, finish post
> and VFX in another, because incentive programs for post work exist specifically to
> capture that spend. This runs the same calculation for every jurisdiction pair and
> tells you when splitting beats staying in one place."

**on-screen text:** *"Solves an allocation problem, not a lookup"*

---

## 2:25–2:45 — Close on the architecture and the receipts

**[VISUAL]** Click through a source citation to show the dated statute link (e.g. a
retrieved-date stamp with a live source URL). Optional final half-second: a terminal
or test-runner shot showing the backend test suite passing (283 tests), no logos
visible.

**VO:**
> "Every figure traces back to a dated source link. If the model can't verify
> something, it says so instead of filling in a plausible-looking guess. That's the
> whole bet: a language model that reads and cites, and a deterministic calculator,
> tested independently of it, that does the actual math."

---

## 2:45–2:55 — End card

**[VISUAL]** Static end card: project name, one-line tagline, live URL.
No third-party logos.

**on-screen text:**
> Slateline
> The advertised film tax credit is never the real number. This computes the real one, live, with receipts.
> zeta-structure-437412-v7.web.app

**VO:** *(silence, or trail off previous line — do not add new narration here)*

---

## Shot checklist before recording

- [ ] Redeploy backend + frontend from current `master` first — the live URL must
      reflect everything through split allocation, present value, adversarial
      verification, and the map (see `NEXT_STEPS.md` §1.3 — a stale deploy is the
      single biggest risk to this video).
- [ ] Pre-warm the cache for the jurisdictions you're about to record (run the search
      once off-camera) if you want the loading-state shot to look intentional rather
      than slow; otherwise let the real 30–60s search run and cut it down in editing.
- [ ] Use a budget/home-base combination you've already sanity-checked so the numbers
      on screen are ones you can defend if a judge asks.
- [ ] No Google/Gemini/Parallel logos, wordmarks, or UI chrome from those products
      visible anywhere in frame — name them only in voiceover.
- [ ] Keep total runtime under 3:00 including the end card.
- [ ] Export and upload publicly to YouTube or Vimeo (unlisted is not sufficient —
      must be publicly viewable without a login) before linking it in the Devpost
      submission and in `README.md`'s "Demo video" row.
