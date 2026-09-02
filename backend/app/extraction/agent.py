"""Layer 1: extraction. Searches for a jurisdiction's film incentive program
and populates a JurisdictionRule. The model's only job is reading and
quoting — it never computes a benefit (enforced by forced function calling
below: the model must call `record_jurisdiction_rule`, it cannot just answer
in prose).

STATUS: run live against a real jurisdiction (Oklahoma). Two bugs surfaced and
are fixed: (1) the model left several dataclass-required fields (centroid_lat/
lng, pool_status) off its function call entirely, since RECORD_JURISDICTION_RULE_SCHEMA's
`required` list didn't force them — now it does, since a centroid and a
pool_status of "unknown" are things the model can always state without
guessing a figure; (2) `sources`/`tiers`/`uplifts` were left as plain dicts
from the function-call args instead of being converted to SourceRef/Tier/
Uplift, which would have broken the first attribute access downstream
(verify_rule's assess_confidence reads `s.retrieved`/`s.is_primary`).

Hard constraint reminder (BUILD_BRIEF.md section 2): Google Cloud AI tools
and Parallel's AI features only. No LangChain, no other agent framework.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from parallel import Parallel
from parallel.types import WebSearchResult
from google import genai

from ..config import settings
from ..models import JurisdictionRule, SourceRef, Tier, Uplift

SEARCH_TARGETS_PRIORITY = (
    "primary statute or regulation text",
    "official film office pages",
    "recent legislative updates and news for cap/sunset changes",
)

# JSON schema mirroring JurisdictionRule, for forced function calling — Gemini
# must call this function to respond, so it structurally cannot emit a
# benefit figure of its own instead of populating fields for Layer 2 to use.
RECORD_JURISDICTION_RULE_SCHEMA: dict[str, Any] = {
    "name": "record_jurisdiction_rule",
    "description": (
        "Record the extracted film incentive rule for one jurisdiction. "
        "Only report what sources state; leave a field null rather than guessing."
    ),
    "parameters": {
        "type": "object",
        # Only fields the model can state without guessing a figure: facts it
        # must quote/know (jurisdiction, rate, sources), plus centroid_lat/lng
        # (world knowledge, not a policy figure) and pool_status (its enum
        # includes "unknown", so "don't know" is a legitimate required answer,
        # unlike e.g. annual_pool_remaining which stays optional).
        "required": [
            "jurisdiction",
            "program_name",
            "base_rate",
            "qualifying",
            "sources",
            "centroid_lat",
            "centroid_lng",
            "pool_status",
        ],
        "properties": {
            "jurisdiction": {"type": "string"},
            "program_name": {"type": "string"},
            "base_rate": {"type": "number"},
            "qualifying": {
                "type": "object",
                "description": "Whether each budget category is qualifying spend under this program's statute.",
                # Without explicit properties+required here, a live run against
                # Oklahoma came back with qualifying={} — an empty object still
                # satisfies "qualifying" being a required top-level key, and
                # calculator.py's q.get(key) treats every missing key as
                # not-qualifying, so the credit silently computes to $0 instead
                # of erroring. Naming the six keys forces the model to state
                # each one.
                "required": [
                    "atl_cast",
                    "atl_noncast",
                    "btl_labor_resident",
                    "btl_labor_nonresident",
                    "btl_nonlabor",
                    "post_vfx",
                ],
                "properties": {
                    "atl_cast": {"type": "boolean"},
                    "atl_noncast": {"type": "boolean"},
                    "btl_labor_resident": {"type": "boolean"},
                    "btl_labor_nonresident": {"type": "boolean"},
                    "btl_nonlabor": {"type": "boolean"},
                    "post_vfx": {"type": "boolean"},
                },
            },
            "per_person_wage_cap": {"type": ["number", "null"]},
            "minimum_spend": {"type": ["number", "null"]},
            "per_project_cap": {"type": ["number", "null"]},
            "tiers": {
                "type": "array",
                "items": {"type": "object", "properties": {"threshold": {"type": "number"}, "rate": {"type": "number"}}},
            },
            "uplifts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string"},
                        "bonus_rate": {"type": "number"},
                        "machine_checkable": {"type": "boolean"},
                    },
                },
            },
            "annual_pool_total": {"type": ["number", "null"]},
            "annual_pool_remaining": {"type": ["number", "null"]},
            "pool_status": {"type": "string", "enum": ["open", "capping_out", "closed", "unknown"]},
            "application_deadline": {"type": ["string", "null"], "description": "ISO date"},
            "sunset_date": {"type": ["string", "null"], "description": "ISO date"},
            "under_review": {"type": "boolean"},
            "is_discretionary": {"type": "boolean"},
            "film_office_contact": {"type": ["string", "null"]},
            "centroid_lat": {"type": "number"},
            "centroid_lng": {"type": "number"},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "retrieved": {"type": "string", "description": "ISO date"},
                        "published": {"type": ["string", "null"], "description": "ISO date"},
                        "excerpt": {"type": "string"},
                        "is_primary": {"type": "boolean"},
                    },
                },
            },
            "conflicts": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def _search(jurisdiction: str) -> list[WebSearchResult]:
    """Parallel Search for the jurisdiction's film incentive program, ordered
    by SEARCH_TARGETS_PRIORITY.
    """
    client = Parallel(api_key=settings.parallel_api_key)
    results: list[WebSearchResult] = []
    for target in SEARCH_TARGETS_PRIORITY:
        response = client.search(
            objective=f"{jurisdiction} film production tax incentive — {target}",
            search_queries=[f"{jurisdiction} film tax incentive {target}"],
        )
        results.extend(response.results)
    return results


def _extract_with_forced_function_call(jurisdiction: str, search_results: list[WebSearchResult]) -> dict:
    """Single Gemini call via Vertex, forced to call record_jurisdiction_rule."""
    client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)
    sources_text = "\n\n".join(
        f"URL: {r.url}\n" + "\n".join(r.excerpts or []) for r in search_results
    )

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=(
            f"Extract the film production tax incentive program for {jurisdiction} from the sources below. "
            "Quote figures exactly as stated; leave a field null rather than inferring a value that isn't "
            "in the text.\n\n" + sources_text
        ),
        config={
            "tools": [
                {
                    "function_declarations": [
                        {
                            "name": RECORD_JURISDICTION_RULE_SCHEMA["name"],
                            "description": RECORD_JURISDICTION_RULE_SCHEMA["description"],
                            # parameters_json_schema, not parameters: the `parameters` field is a
                            # genai Schema whose `type` is a single enum, so it rejects the
                            # ["number", "null"] unions the nullable fields below rely on.
                            "parameters_json_schema": RECORD_JURISDICTION_RULE_SCHEMA["parameters"],
                        }
                    ]
                }
            ],
            # Forced function calling: the model MUST call record_jurisdiction_rule — it cannot
            # respond with prose instead, which is what keeps arithmetic out of its hands.
            "tool_config": {"function_calling_config": {"mode": "ANY", "allowed_function_names": ["record_jurisdiction_rule"]}},
        },
    )
    for part in response.candidates[0].content.parts:
        if part.function_call is not None:
            return dict(part.function_call.args)
    raise RuntimeError(
        f"Gemini returned no function call for {jurisdiction} despite mode=ANY; "
        f"response text was: {response.text!r}"
    )


def _parse_date(value: str | None) -> date | None:
    # Gemini is told to quote figures exactly, and for a recurring deadline
    # (e.g. "the 10th of every month") the exact quote isn't an ISO date —
    # there's no single date to parse, so null is the correct value, same as
    # if the field had been left out entirely. Only date.fromisoformat's
    # ValueError is expected here; anything else should still surface.
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def extract_jurisdiction_rule(jurisdiction: str) -> JurisdictionRule:
    """Layer 1 entry point: jurisdiction name in, populated JurisdictionRule
    out. Layer 3 (verification.verify_rule) should run on the result before
    it reaches Layer 2.
    """
    search_results = _search(jurisdiction)
    raw = dict(_extract_with_forced_function_call(jurisdiction, search_results))

    raw["application_deadline"] = _parse_date(raw.get("application_deadline"))
    raw["sunset_date"] = _parse_date(raw.get("sunset_date"))

    # The function-call args come back as plain dicts; JurisdictionRule's
    # fields are typed as the actual dataclasses, and code downstream (e.g.
    # verify_rule's assess_confidence, calculator's tier/uplift handling)
    # accesses them as attributes, not dict keys.
    raw["sources"] = [
        SourceRef(
            url=s.get("url", ""),
            retrieved=_parse_date(s.get("retrieved")) or date.today(),
            published=_parse_date(s.get("published")),
            excerpt=s.get("excerpt", ""),
            is_primary=bool(s.get("is_primary", False)),
        )
        for s in raw.get("sources", [])
    ]
    raw["tiers"] = [Tier(threshold=t["threshold"], rate=t["rate"]) for t in raw.get("tiers", [])]
    raw["uplifts"] = [
        Uplift(
            condition=u["condition"],
            bonus_rate=u["bonus_rate"],
            machine_checkable=bool(u.get("machine_checkable", False)),
        )
        for u in raw.get("uplifts", [])
    ]

    # Structural fields RECORD_JURISDICTION_RULE_SCHEMA doesn't force the
    # model to restate every call (only the fields in its `required` list
    # are guaranteed present) — fill in the dataclass-mandated defaults for
    # the rest rather than erroring on an absent "no tiers" / "not under
    # review" the model had no reason to mention.
    raw.setdefault("per_person_wage_cap", None)
    raw.setdefault("minimum_spend", None)
    raw.setdefault("per_project_cap", None)
    raw.setdefault("annual_pool_total", None)
    raw.setdefault("annual_pool_remaining", None)
    raw.setdefault("under_review", False)
    raw.setdefault("is_discretionary", False)
    raw.setdefault("film_office_contact", None)
    raw.setdefault("conflicts", [])
    raw.setdefault("confidence", "unverified")  # Layer 3 recomputes this properly

    return JurisdictionRule(**raw)
