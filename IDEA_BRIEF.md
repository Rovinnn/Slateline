# Agentic Cinema Hackathon — rules + our project, for outside review

Written to be read cold. If you know nothing about this project, everything you
need to form an opinion is below. Skip to §3 for the idea and §5 for the
specific questions I want answered.

---

## 1. The hackathon, in brief

**Agentic Cinema Hackathon.** Build an AI agent that solves a real bottleneck
for filmmakers, screenwriters, studio crews, or fans.

| | |
|---|---|
| **Submission deadline** | 7 Sep 2026, 2:00 PM PT *(the site banner says 9 Sep, but 3 of 4 official references say the 7th — we're building to the 7th)* |
| **Judging** | 23 Sep – 7 Oct 2026 |
| **Prizes** | $7,500 / $4,500 / $3,000 — **per track**, 15 prizes total |
| **Field** | ~5,770 registered participants across 5 tracks |

### What every entry must be
- A functional, **production-ready AI agent** (or multi-agent network)
- Powered by **Gemini + Google Cloud Agent Builder**
- Integrating **exactly one partner's** product or MCP server (you pick a track)
- Runs on web, Android, or iOS
- **Newly created during the contest period** — not an extension of prior work

### The five partner tracks
**Parallel** (web search API) · **Replit** (must be built with Replit Agent and
deployed on replit.app) · **Grafana** (via their MCP server) · **ClickHouse**
(via MCP server) · **IBM** (must be built using IBM Bob)

You compete only against entries in your chosen track. Adding extra partners
earns nothing.

### Hard restriction on AI tooling
**Only Google Cloud AI tools plus your track partner's built-in AI features.**
No other AI models, agent frameworks, or AI APIs — explicitly including AWS,
Microsoft, OpenAI, Anthropic, and **LangChain**. Non-AI third-party services
(hosting, databases, web frameworks, charting) are unrestricted.

### Required deliverables
- Live hosted URL, judge-testable, **reachable logged-out**
- Public repo, all source, run instructions, **OSS license visible in the
  GitHub About section**
- Text description incl. features, tech, data sources, **findings and learnings**
- **Demo video ≤3 min**, public on YouTube/Vimeo — *"a demo showing your agent
  functioning as built, not a cinematic trailer"*
- One track selected

### How it's judged
Stage 1 is **pass/fail** on requirements. Stage 2 is four criteria at **25% each**:

| Criterion | The actual test |
|---|---|
| **Technological Implementation** | How well built; how effectively it uses Google Cloud *and* the partner |
| **Design** | A complete, coherent **product experience** — not a technical proof of concept |
| **Potential Impact** | Credible, specific real problem + real audience, **based on what's demonstrated** |
| **Quality of the Idea** | **Creative, non-obvious** use of the services; genuine understanding of the problem space |

Three things worth knowing about how those play out:
- **Design is where infra-heavy projects bleed.** A great engine behind an ugly
  chat box scores 25% on Design.
- **The video carries the Impact score**, not the README. Impact is scored on
  what you *demonstrate*, not what you claim.
- **A decorative partner integration loses points explicitly.** If your partner
  could be swapped for anything else, that's marked down under "non-obvious".

---

## 2. Our track: Parallel

Parallel is a web search API. The requirement is to **actively use Parallel's
Search API at runtime**. It's likely the smallest field (newest, least-known
partner) and has the lowest infrastructure burden of the five.

---

## 3. Our idea: **Incentive Verifier**

> **A producer with a finished budget is choosing which state to shoot in. The
> advertised tax-credit number is never the real number. This tool computes the
> real number, live, with receipts.**

### The problem

Every US state advertises a film tax incentive: *"Georgia 30%!"* Producers
choose shooting locations substantially on these numbers, and the decision is
worth 15–25% of a film's budget — often millions. But four things sit between
the advertised rate and money in the bank:

1. **Is the money actually there?** Most states cap their annual incentive pool.
   When it's exhausted you're in next year's queue. Programs sunset;
   legislatures suspend them mid-session. A 30% credit you can't access is 0%.
2. **How much of *your* budget qualifies?** "30%" means 30% *of qualified
   spend*, not your budget. Non-resident crew wages are often excluded
   entirely. Per-person wage caps chop star salaries. Minimum-spend thresholds
   are cliffs, not ramps. Two states both advertising 25% can differ by $200k
   on the same budget.
3. **What does it cost to be there?** A 30% credit somewhere you must fly and
   house 40 people for 10 weeks can lose to 20% somewhere you can drive to.
4. **What's the credit worth when it arrives?** A *refundable* credit is paid at
   face value. A *transferable* one must be sold to a taxpayer at 85–95 cents.
   Most comparisons treat these as identical. They aren't.

Today this takes a specialist two or three days across 40 badly-organised
government websites, or you hire an incentive consultant. Existing tools
(Entertainment Partners, Wrapbook, Cast & Crew) publish **manually curated
databases that lag legislative changes by weeks**.

### What it does

You give it a budget — pick a sample, type it in, or **upload a real budget PDF**
(Gemini reads the topsheet and pre-fills the form, annotating each figure with
the line it came from). Then, for each jurisdiction, it:

1. **Searches the live web** (Parallel) for the statute, the film office page,
   and recent legislative changes
2. **Has Gemini read and extract** the rules into a structured object —
   forced function calling, so the model can only *quote facts*, never compute
3. **Computes the benefit in deterministic, unit-tested Python** — qualification
   by category, wage caps, minimum-spend cliffs, tiers, fringes, payout
   mechanism
4. **Pulls real driving/flight distance** from Google Maps for relocation cost
5. **Ranks by net benefit** — with every figure traceable to a dated source
   link and the quoted statutory line, and anything it can't verify explicitly
   listed as "can't verify" rather than guessed

Plus: live sensitivity sliders, a breakeven analysis ("New Mexico leads until
ATL spend exceeds $11.1M"), constraint filters, a map view, and PDF export of
the whole memo.

### The core architectural bet

**The language model never does arithmetic.** It reads and quotes; all
computation happens in pure Python with 267 unit tests. This is enforced by
configuration (forced function calling), not by asking nicely.

### Why the partner integration is structurally necessary

This is our strongest argument, and it's the thing "Quality of Idea" rewards:

> **You physically cannot answer "is New Mexico's $140M pool exhausted right
> now?" from a frozen-weights model.** Incentive law changes by legislative
> session. A model trained six months ago is confidently wrong. Live search
> isn't decoration bolted on to satisfy a sponsor — it's the only mechanism
> that can answer the question at all.

Most entries' partner integration could be swapped for something else. Ours
can't be.

---

## 4. Honest weaknesses

Sanitised pitches get useless feedback, so:

- **It restates public information unless you look closely.** The headline rates
  are free on every film office site. Our value is in qualification, availability,
  monetisation and relocation — which is real, but less immediately visible than
  a flashy demo.
- **It's text and numbers.** The hackathon has a whole toolkit for image, music,
  and voice generation. A finance table may look thin beside submissions
  generating storyboards and scored soundtracks. Our mitigation is using
  multimodal on the *input* side (reading budget PDFs).
- **We've never verified the extracted numbers against actual statutes.** The
  machinery works; whether Gemini reads Georgia's tax code correctly is
  genuinely unverified.
- **Live extraction isn't deterministic.** The same jurisdiction can return
  slightly different results between runs — inherent to live retrieval.
- **First page load takes 30–60 seconds** (live search + extraction per
  jurisdiction). Fixable with caching, not yet fixed.
- **US-only in practice.** Non-US jurisdictions return figures in their own
  currency treated as dollars. Being fixed by refusing to rank them rather than
  guessing.
- **We use `google-genai` directly, not the ADK agent framework** the rules
  recommend. Probably not disqualifying, but likely costs points on
  Technological Implementation.

## 5. What I actually want to know

1. **Is the problem credible to you?** Would a real line producer or production
   accountant use this, or is it solving a problem that doesn't hurt enough?
2. **Does the "live search is structurally necessary" argument land**, or does
   it read as a rationalisation?
3. **Is a finance/workflow tool the wrong shape for a *cinema* hackathon?**
   Would judges rather see something visual and creative, even if shallower?
4. **Given ~1 day left**, is finishing this the right call, or is there a
   better idea that could genuinely ship in that time on the Parallel track?
5. **What would make the 3-minute video compelling?** The tool's insight is
   numerical, which is hard to make vivid quickly.

### For framing alternatives

The field is expected to flood with generative-media demos (storyboard
generators, AI trailers, script-to-voice). The counter-bet is that a boring,
expensive, real problem scores better on Impact and Quality of Idea precisely
because fewer people build it. **That's the bet we've made — the question is
whether it's the right one.**
