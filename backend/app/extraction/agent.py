"""Layer 1: extraction. Searches for a jurisdiction's film incentive program
and populates a JurisdictionRule. The model's only job is reading and
quoting — it never computes a benefit (enforced by forced function calling
below: the model must call `record_jurisdiction_rule`, it cannot just answer
in prose).

STATUS: structural skeleton, not yet run against real credentials. This is
build order step 3 and depends on step 1 ("one real parallel-web search
call... one Gemini call via Vertex") having been verified first. Treat every
SDK call shape below as a draft to confirm against the current `google-genai`
and `parallel-web` docs once GOOGLE_CLOUD_PROJECT / PARALLEL_API_KEY exist —
both SDKs move fast enough that exact method names may have shifted.

Hard constraint reminder (BUILD_BRIEF.md section 2): Google Cloud AI tools
and Parallel's AI features only. No LangChain, no other agent framework.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from parallel import Parallel  # parallel-web SDK — TODO: confirm import path/client name against current docs
from google import genai  # google-genai SDK — TODO: confirm Vertex-mode client construction against current docs

from ..config import settings
from ..models import JurisdictionRule

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
        "required": ["jurisdiction", "program_name", "base_rate", "qualifying", "sources"],
        "properties": {
            "jurisdiction": {"type": "string"},
            "program_name": {"type": "string"},
            "base_rate": {"type": "number"},
            "qualifying": {
                "type": "object",
                "description": "atl_cast, atl_noncast, btl_labor_resident, btl_labor_nonresident, btl_nonlabor, post_vfx -> bool",
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


def _search(jurisdiction: str) -> list[dict]:
    """Parallel Search for the jurisdiction's film incentive program, ordered
    by SEARCH_TARGETS_PRIORITY.
    """
    client = Parallel(api_key=settings.parallel_api_key)
    results = []
    for target in SEARCH_TARGETS_PRIORITY:
        response = client.search(
            objective=f"{jurisdiction} film production tax incentive — {target}",
            search_queries=[f"{jurisdiction} film tax incentive {target}"],
        )
        results.extend(response.results)  # TODO: confirm attribute name on the search response object
    return results


def _extract_with_forced_function_call(jurisdiction: str, search_results: list[dict]) -> dict:
    """Single Gemini call via Vertex, forced to call record_jurisdiction_rule."""
    client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)
    sources_text = "\n\n".join(f"URL: {r.get('url')}\n{r.get('excerpt', r.get('content', ''))}" for r in search_results)

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=(
            f"Extract the film production tax incentive program for {jurisdiction} from the sources below. "
            "Quote figures exactly as stated; leave a field null rather than inferring a value that isn't "
            "in the text.\n\n" + sources_text
        ),
        config={
            "tools": [{"function_declarations": [RECORD_JURISDICTION_RULE_SCHEMA]}],
            # Forced function calling: the model MUST call record_jurisdiction_rule — it cannot
            # respond with prose instead, which is what keeps arithmetic out of its hands.
            "tool_config": {"function_calling_config": {"mode": "ANY", "allowed_function_names": ["record_jurisdiction_rule"]}},
        },
    )
    call = response.candidates[0].content.parts[0].function_call  # TODO: confirm response shape against current SDK
    return dict(call.args)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def extract_jurisdiction_rule(jurisdiction: str) -> JurisdictionRule:
    """Layer 1 entry point: jurisdiction name in, populated JurisdictionRule
    out. Layer 3 (verification.verify_rule) should run on the result before
    it reaches Layer 2.
    """
    search_results = _search(jurisdiction)
    raw = _extract_with_forced_function_call(jurisdiction, search_results)

    raw = dict(raw)
    raw["application_deadline"] = _parse_date(raw.get("application_deadline"))
    raw["sunset_date"] = _parse_date(raw.get("sunset_date"))
    for source in raw.get("sources", []):
        source["retrieved"] = _parse_date(source.get("retrieved")) or date.today()
        source["published"] = _parse_date(source.get("published"))
    raw.setdefault("confidence", "unverified")  # Layer 3 recomputes this properly

    return JurisdictionRule(**raw)
