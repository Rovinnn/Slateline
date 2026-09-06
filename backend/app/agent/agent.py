"""The ADK agent. A planner over the existing pipeline, not a replacement for it.

BUILD_BRIEF.md section 4 asks that "the agent must invoke the calculator
tool". The REST pipeline satisfied that only in spirit — it called
compute_benefit itself, in a fixed order, with no agent involved. That fixed
order is also its limitation: it searches four jurisdictions, computes all
four, ranks them, done. It cannot decide that a jurisdiction is worth
challenging, or that relocation matters here and not there, or answer "what
if we hired more locally" without the user moving a slider.

This module adds that judgement without moving a single arithmetic decision
into the model. The agent chooses which tool to call and in what order; every
number it reports came out of calculator.compute_benefit, the same function
the REST API uses, with the same 242 tests behind it.

Deliberately additive. app/main.py and the three-layer pipeline are untouched
and remain the path the deployed frontend uses, so nothing here can break the
working product.

**Verified with mocked model calls only.** The tools are exercised against
real code in tests; the agent's own planning has never run against live Vertex
because no credentials were available on the machine this was written on. That
limitation is recorded in SUBMISSION.md rather than glossed.
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent

from ..config import settings
from .tools import AGENT_TOOLS

MODEL = "gemini-2.5-pro"


def _route_through_vertex() -> None:
    """Point ADK at Vertex AI, which is where this project's credentials are.

    Found by running the CLI rather than by reading the docs: ADK defaults to
    the Gemini *Developer* API, so without this it fails with "No API key was
    provided" and a link to ai.google.dev — while the rest of Layer 1 is
    happily authenticating to Vertex with application-default credentials and
    no API key anywhere. Two different Google products, one library, and a
    failure mode that reads like a missing secret rather than a missing
    setting.

    extraction/agent.py says the same thing in code, by constructing
    genai.Client(vertexai=True, ...) explicitly. ADK builds its own client, so
    the only place to say it is the environment.

    setdefault throughout: a deployment that has already configured these
    keeps whatever it chose.
    """
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    if settings.google_cloud_project:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)


_route_through_vertex()

INSTRUCTION = """\
You help film producers decide where to shoot by comparing what each
jurisdiction's tax incentive is actually worth to their specific budget.

THE ONE RULE THAT MATTERS: you must never perform arithmetic. Not addition,
not percentages, not comparisons of magnitude. Every figure you state must
have come verbatim from a tool result. If you find yourself wanting to work
out what 25% of a budget is, or how much bigger one net benefit is than
another, call compute_benefit_for or compare_jurisdictions instead. The
calculator is deterministic and tested; your estimate is neither, and a
producer may commit millions of dollars on the basis of what you say.

How to work:

1. Call set_budget first. You need the producer's figures before anything
   else is meaningful. If they have not given you a full budget, ask for the
   missing lines rather than assuming them.
2. Call search_jurisdiction once per jurisdiction they are considering. It is
   slow and costs quota, so do not repeat it for a jurisdiction already
   fetched.
3. Call get_travel_distance for each one before computing, otherwise
   relocation cost is left out and the comparison flatters distant places.
4. Call compare_jurisdictions to rank them. Report its ordering and its
   margin figure as given; do not restate a difference you worked out
   yourself.
5. Call challenge_jurisdiction on the leader before recommending it. It looks
   for evidence the program has changed or closed. "Nothing contradicts it,
   checked against N sources" is worth telling the producer.

How to talk about the results:

- The headline rate is not the answer. Say what the credit is worth after
  qualification, monetisation, the wait to be paid, and relocation — the tool
  gives you each of those stages.
- Report every caveat the calculator returns. They exist because something in
  the statute could not be verified, and a producer needs to know which parts
  of the number are solid.
- If a jurisdiction cannot be ranked, say so and say why. A program whose
  funding pool has closed is not a low-scoring option, it is an unavailable
  one, and presenting it as merely worse would be misleading.
- Never present these figures as tax advice. They are estimates for comparing
  jurisdictions, and the producer should confirm with the film office.
"""

root_agent = LlmAgent(
    name="incentive_verifier",
    model=MODEL,
    description=(
        "Compares film production tax incentives across jurisdictions using live "
        "web search, statutory extraction, and a deterministic calculator."
    ),
    instruction=INSTRUCTION,
    tools=list(AGENT_TOOLS),
)
