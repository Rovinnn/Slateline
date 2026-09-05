"""Layer 1b: a second pass whose only job is to disprove the first.

BUILD_BRIEF.md section 4 says Layer 3 "cross-checks values across retrieved
sources" and build order step 8 lists conflict detection. Neither existed:
`conflicts` was only ever `setdefault("conflicts", [])`, which made the
`"conflicting"` confidence state unreachable from our own code. Everything
downstream trusted a single extraction pass with no adversary.

The asymmetry this fixes is the whole point. The discovery pass asks *"what
is Georgia's rate?"* and is rewarded for finding an answer — a search that
returns the statute and stops looks successful whether or not a bill amending
it passed last month. This pass asks *"what would prove that answer wrong?"*
and searches somewhere different for it: trade coverage, legislative
trackers, film-office notices, pool-exhaustion announcements. Falsification
is a structurally different query pattern from discovery, not the same search
run twice, and it's the one a frozen-weights model provably cannot do.

Three rules hold it honest:

1. **Silence is not contradiction.** A source that simply doesn't mention the
   sunset date disproves nothing. The model is told this explicitly, because
   a model rewarded for finding problems will find them.
2. **It reports, never overwrites.** A contradiction annotates the rule and
   downgrades its confidence; it never silently replaces a figure. Which of
   two disagreeing sources is right is a judgement call, and this tool's
   entire position is that it surfaces those rather than making them quietly.
3. **Code decides what matters.** The model reports what a source says; this
   module decides whether a disagreement is material, from the field it lands
   on. A wrong phone number is not a wrong tax rate.

Finding nothing is a *result*, not a failure — corroborations are recorded
too, because "we went looking for contradictions and found none" is real
evidence about a number, and considerably stronger than never having asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal, Optional

from google import genai
from parallel import Parallel
from parallel.types import WebSearchResult

from ..config import settings
from ..models import JurisdictionRule, SourceRef

Severity = Literal["material", "minor"]

# Deliberately aimed away from where the discovery pass already looked. A
# statute page restates the statute; these are the places a change shows up
# first, and the places a rate that is no longer true stops being repeated.
CHALLENGE_TARGETS = (
    "program suspended, repealed, paused or allowed to sunset",
    "annual funding cap exhausted, fully allocated, or applications waitlisted",
    "pending legislation amending the credit rate, cap or eligibility",
    "trade press reporting changes to the incentive program",
)

# Which disagreements change a decision. A contradicted base_rate or
# pool_status can invert a ranking; a contradicted program name or phone
# number cannot, and flagging the whole jurisdiction "conflicting" over one
# would train a reader to ignore the flag — which costs more than the
# information is worth.
MATERIAL_FIELDS = frozenset({
    "base_rate",
    "pool_status",
    "annual_pool_remaining",
    "annual_pool_total",
    "sunset_date",
    "application_deadline",
    "minimum_spend",
    "per_project_cap",
    "per_person_wage_cap",
    "credit_type",
    "is_discretionary",
    "under_review",
    "months_to_payment",
    "currency",
})

# Fields the model is allowed to report on at all. Constrained so a
# contradiction can always be attributed to something Layer 2 actually reads,
# rather than arriving as free-text commentary nothing can act on.
CHALLENGEABLE_FIELDS = sorted(MATERIAL_FIELDS | {"program_name", "film_office_contact", "fringes_qualify"})

RECORD_CHALLENGE_SCHEMA: dict[str, Any] = {
    "name": "record_challenge_result",
    "description": (
        "Record every point where the challenge sources explicitly contradict, or explicitly "
        "confirm, the incentive figures currently held. Report a contradiction ONLY when a source "
        "states something different — never when a source is merely silent on a field."
    ),
    "parameters": {
        "type": "object",
        "required": ["contradictions", "corroborations"],
        "properties": {
            "contradictions": {
                "type": "array",
                "description": (
                    "Points where a source states something different from the current figure. "
                    "Empty array if the sources contradict nothing — that is a valid and common result."
                ),
                "items": {
                    "type": "object",
                    "required": ["field", "current_value", "source_says", "url", "excerpt"],
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": CHALLENGEABLE_FIELDS,
                            "description": "Which held figure this source disagrees with.",
                        },
                        "current_value": {
                            "type": "string",
                            "description": "The currently held value, restated as given to you.",
                        },
                        "source_says": {
                            "type": "string",
                            "description": "What this source states instead, quoted or closely paraphrased.",
                        },
                        "url": {"type": "string", "description": "The contradicting source's URL."},
                        "excerpt": {
                            "type": "string",
                            "description": "The sentence from the source that carries the contradiction.",
                        },
                        "published": {
                            "type": ["string", "null"],
                            "description": "Publication date as YYYY-MM-DD if the source states one, else null.",
                        },
                    },
                },
            },
            "corroborations": {
                "type": "array",
                "description": (
                    "Points where a source independently confirms the current figure. Evidence the "
                    "extraction holds up, so it is worth recording rather than discarding."
                ),
                "items": {
                    "type": "object",
                    "required": ["field", "url", "excerpt"],
                    "properties": {
                        "field": {"type": "string", "enum": CHALLENGEABLE_FIELDS},
                        "url": {"type": "string"},
                        "excerpt": {"type": "string"},
                    },
                },
            },
        },
    },
}


@dataclass
class ChallengeFinding:
    """One point of disagreement between a challenge source and the held rule."""

    field_name: str
    current_value: str
    source_says: str
    url: str
    excerpt: str
    severity: Severity

    def describe(self) -> str:
        """The line a producer reads. Names both figures and the source, so the
        disagreement can be adjudicated rather than merely worried about."""
        return (
            f"{self.field_name}: we have {self.current_value}, but {self.url} states "
            f"{self.source_says}"
        )


@dataclass
class ChallengeReport:
    """What the falsification pass found — including finding nothing."""

    jurisdiction: str
    findings: list[ChallengeFinding] = field(default_factory=list)
    corroborated_fields: list[str] = field(default_factory=list)
    sources_checked: int = 0

    @property
    def material_findings(self) -> list[ChallengeFinding]:
        return [f for f in self.findings if f.severity == "material"]

    @property
    def challenged_cleanly(self) -> bool:
        """True when the pass ran against real sources and found nothing material.

        Distinct from a pass that found nothing because it had nothing to read
        — which is not evidence of anything and must not read as a clean bill
        of health.
        """
        return self.sources_checked > 0 and not self.material_findings


def _severity_of(field_name: str) -> Severity:
    return "material" if field_name in MATERIAL_FIELDS else "minor"


def _challenge_search(rule: JurisdictionRule) -> list[WebSearchResult]:
    """Search for what would prove this rule wrong."""
    client = Parallel(api_key=settings.parallel_api_key)
    results: list[WebSearchResult] = []
    for target in CHALLENGE_TARGETS:
        response = client.search(
            objective=(
                f"Find evidence that {rule.jurisdiction}'s {rule.program_name} has changed or is no "
                f"longer as described — specifically: {target}"
            ),
            search_queries=[f"{rule.jurisdiction} film tax credit {target}"],
        )
        results.extend(response.results)
    return results


def _held_values(rule: JurisdictionRule) -> str:
    """The figures under challenge, stated plainly for the model to check.

    Only the challengeable fields: handing over the whole object would invite
    commentary on things nothing downstream can act on.
    """
    values = {
        "base_rate": f"{rule.base_rate:.1%}",
        "program_name": rule.program_name,
        "credit_type": rule.credit_type,
        "pool_status": rule.pool_status,
        "annual_pool_total": rule.annual_pool_total,
        "annual_pool_remaining": rule.annual_pool_remaining,
        "minimum_spend": rule.minimum_spend,
        "per_project_cap": rule.per_project_cap,
        "per_person_wage_cap": rule.per_person_wage_cap,
        "sunset_date": rule.sunset_date.isoformat() if rule.sunset_date else None,
        "application_deadline": (
            rule.application_deadline.isoformat() if rule.application_deadline else None
        ),
        "under_review": rule.under_review,
        "is_discretionary": rule.is_discretionary,
        "months_to_payment": rule.months_to_payment,
        "fringes_qualify": rule.fringes_qualify,
        "film_office_contact": rule.film_office_contact,
        "currency": rule.currency,
    }
    return "\n".join(f"- {k}: {'not stated' if v is None else v}" for k, v in values.items())


def _challenge_with_forced_function_call(
    rule: JurisdictionRule, search_results: list[WebSearchResult]
) -> dict:
    """Single Gemini call, forced to call record_challenge_result."""
    client = genai.Client(
        vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location
    )
    sources_text = "\n\n".join(f"URL: {r.url}\n" + "\n".join(r.excerpts or []) for r in search_results)

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=(
            f"You are checking whether the following figures for {rule.jurisdiction}'s film incentive "
            f"program are still correct. Your job is to find where the sources below DISAGREE with "
            f"them.\n\nCurrently held figures:\n{_held_values(rule)}\n\n"
            "Rules you must follow:\n"
            "- Report a contradiction ONLY when a source explicitly states a different value. A "
            "source that does not mention a field contradicts nothing.\n"
            "- Do not report a contradiction because a figure seems unusual, outdated or surprising. "
            "Only what a source actually says counts.\n"
            "- A proposed or pending bill that has not passed is not a contradiction of the current "
            "rate; report it under under_review instead.\n"
            "- Finding no contradictions is a normal and useful result. Return an empty list rather "
            "than reaching for something to report.\n\n"
            f"Sources to check against:\n{sources_text}"
        ),
        config={
            "tools": [
                {
                    "function_declarations": [
                        {
                            "name": RECORD_CHALLENGE_SCHEMA["name"],
                            "description": RECORD_CHALLENGE_SCHEMA["description"],
                            "parameters_json_schema": RECORD_CHALLENGE_SCHEMA["parameters"],
                        }
                    ]
                }
            ],
            # Same mode=ANY discipline as the discovery pass: the model reports
            # observations into a fixed shape and cannot substitute prose, let
            # alone a revised figure of its own.
            "tool_config": {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": ["record_challenge_result"],
                }
            },
        },
    )
    for part in response.candidates[0].content.parts:
        if part.function_call is not None:
            return dict(part.function_call.args)
    raise RuntimeError(
        f"Gemini returned no function call for the {rule.jurisdiction} challenge despite mode=ANY; "
        f"response text was: {response.text!r}"
    )


def challenge_rule(rule: JurisdictionRule) -> ChallengeReport:
    """Search for evidence this rule is wrong, and report what turns up.

    Returns the report rather than a modified rule — deciding what to do with
    a contradiction is the caller's, and `apply_challenge` below is the only
    thing that touches the rule.
    """
    search_results = _challenge_search(rule)
    raw = _challenge_with_forced_function_call(rule, search_results)

    findings = []
    for item in raw.get("contradictions", []):
        field_name = item.get("field", "")
        # An enum-constrained field can still arrive as something unexpected —
        # mode=ANY forces the call, not the contents (the same gap that let
        # qualifying={} through the discovery pass). Skip rather than record a
        # finding nothing can be attributed to.
        if field_name not in CHALLENGEABLE_FIELDS:
            continue
        findings.append(
            ChallengeFinding(
                field_name=field_name,
                current_value=str(item.get("current_value", "")),
                source_says=str(item.get("source_says", "")),
                url=str(item.get("url", "")),
                excerpt=str(item.get("excerpt", "")),
                severity=_severity_of(field_name),
            )
        )

    corroborated = [
        c["field"]
        for c in raw.get("corroborations", [])
        if c.get("field") in CHALLENGEABLE_FIELDS
    ]

    return ChallengeReport(
        jurisdiction=rule.jurisdiction,
        findings=findings,
        corroborated_fields=sorted(set(corroborated)),
        sources_checked=len(search_results),
    )


def apply_challenge(
    rule: JurisdictionRule, report: ChallengeReport, *, today: Optional[date] = None
) -> JurisdictionRule:
    """Annotate a rule with what the challenge found. Never changes a figure.

    Material contradictions become `conflicts` entries, which is what makes
    verification.assess_confidence return "conflicting" — a state that was
    unreachable from our own code until this pass existed. Minor ones are
    deliberately left out: flagging a whole jurisdiction because a phone
    number disagrees teaches a reader to ignore the flag.

    Contradicting sources are appended to `sources` so the disagreement is
    citable, not just assertable. They are marked non-primary: a trade article
    reporting that a pool closed is evidence, but it is not the statute.
    """
    material = report.material_findings
    if not material:
        return rule

    today = today or date.today()
    conflicts = list(rule.conflicts) + [f.describe() for f in material]

    known_urls = {s.url for s in rule.sources}
    new_sources = [
        SourceRef(
            url=f.url,
            retrieved=today,  # our clock, never the model's — see agent.py bug (4)
            published=None,
            excerpt=f.excerpt,
            is_primary=False,
        )
        for f in material
        if f.url and f.url not in known_urls
    ]

    return replace(rule, conflicts=conflicts, sources=list(rule.sources) + new_sources)
