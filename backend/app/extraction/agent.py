"""Layer 1: extraction. Searches for a jurisdiction's film incentive program
and populates a JurisdictionRule. The model's only job is reading and
quoting — it never computes a benefit (enforced by forced function calling
below: the model must call `record_jurisdiction_rule`, it cannot just answer
in prose).

STATUS: run live against several real jurisdictions. Bugs surfaced and fixed:
(1) the model left several dataclass-required fields (centroid_lat/lng,
pool_status) off its function call entirely, since RECORD_JURISDICTION_RULE_SCHEMA's
`required` list didn't force them — now it does, since a centroid and a
pool_status of "unknown" are things the model can always state without
guessing a figure; (2) `sources`/`tiers`/`uplifts` were left as plain dicts
from the function-call args instead of being converted to SourceRef/Tier/
Uplift, which would have broken the first attribute access downstream
(verify_rule's assess_confidence reads `s.retrieved`/`s.is_primary`);
(3) the model returned `jurisdiction` as a 2-letter postal abbreviation
("NM", "GA") rather than a full name, inconsistently even within one
session — silently broke constraints.py's COASTAL_STATES lookup (a real
coastal state showed as failing "needs ocean coastline" because "GA" isn't
in a set of full names), so extraction now canonicalizes it; (4) `sources[].retrieved`
was read from the model's own stated date, which it has no real way to
know precisely — a live run came back with a source "retrieved" two years
in the past for a page fetched that same day, which risks silently
mislabeling fresh data as `stale` in verify_rule. `retrieved` is a fact
about when *this pipeline* fetched the page, not a document fact, so it's
no longer asked of the model at all — always stamped by code.

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
            "credit_type",
            "currency",
        ],
        "properties": {
            "jurisdiction": {"type": "string"},
            "program_name": {"type": "string"},
            "base_rate": {"type": "number"},
            # Required, not optional-with-a-default: a US-jurisdiction default
            # would silently mislabel a euro or pound figure as USD the one
            # time it matters. The source text itself carries this (a currency
            # symbol or an explicit statement next to every dollar figure), so
            # it's exactly as knowable as base_rate — not something to guess.
            "currency": {
                "type": "string",
                "description": (
                    "ISO 4217 code the monetary figures above are denominated in (USD, EUR, GBP, CAD, "
                    "...), per the source text's own currency symbols/statements. USD for US states."
                ),
            },
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
            # What the credit is worth in cash turns on how it pays out, and
            # statutes state this plainly. "unknown" keeps "not stated"
            # representable, same as pool_status.
            "credit_type": {
                "type": "string",
                "enum": ["refundable", "transferable", "rebate", "non_refundable", "unknown"],
                "description": (
                    "How the credit pays out: refundable (state pays face value), transferable "
                    "(must be sold to a taxpayer, at a discount), rebate (cash grant), "
                    "non_refundable (only offsets in-state liability), or unknown."
                ),
            },
            # Timing is administrative practice, not usually statute, so this
            # is null far more often than not — and that's the point. Null
            # means "no source said", and calculator.CreditTimingAssumptions
            # supplies a visible, editable per-credit-type default instead.
            # Letting the model fill a plausible number here would put an
            # invented figure behind the most consequential input to present
            # value, which is exactly the failure this schema exists to stop.
            "months_to_payment": {
                "type": ["integer", "null"],
                "description": (
                    "Months from end of principal photography until the production actually "
                    "receives the money, ONLY if a source states a timeline or statutory "
                    "deadline. Null if no source addresses it — do not estimate."
                ),
            },
            # Distinct from null: an audit that a source confirms is mandatory
            # both delays payment and costs real money.
            "audit_required": {
                "type": ["boolean", "null"],
                "description": (
                    "True if a source states a CPA or state audit is mandatory before the "
                    "credit is paid or transferred, false if a source states none is "
                    "required, null if unaddressed."
                ),
            },
            # Payroll burden is 22-35% of wages and whether it qualifies varies
            # by statute. Null when the sources don't say — never assumed.
            "fringes_qualify": {
                "type": ["boolean", "null"],
                "description": (
                    "Whether employer-side fringes (payroll taxes, union pension/health, workers' "
                    "comp) count as qualified spend. Null if the sources don't state it."
                ),
            },
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
                    # No "retrieved" field: that's when *this pipeline* fetched the
                    # page, a fact the model has no way to know, not something to
                    # extract from the page — see the module docstring's bug (4).
                    # extract_jurisdiction_rule() stamps it with date.today().
                    "properties": {
                        "url": {"type": "string"},
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


# USPS 2-letter codes -> full name. The model isn't asked to use one form or
# the other (BUILD_BRIEF.md doesn't specify it, and constraining every field's
# exact string format isn't worth the schema complexity), so it's returned
# either way, inconsistently — canonicalize rather than get every consumer
# (constraints.py's COASTAL_STATES, the frontend's dedup-by-name) to handle
# both forms. Only US states/DC: this app's jurisdictions can also be
# countries or provinces ("Ireland", "British Columbia"), and none of those
# collide with a 2-letter code, so non-US names simply pass through unchanged.
US_STATE_ABBREVIATIONS: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}


# Forms observed in live runs, all for the same four states: "GA", "TX",
# "USA-NM", "Louisiana". The model is consistent within a response and
# inconsistent across them, so every shape below has to collapse to the
# canonical full name.
_US_PREFIXES = ("usa-", "us-", "usa ", "us ")
_US_SUFFIXES = (", usa", ", us", ", united states", " (usa)", " (us)")


def canonicalize_jurisdiction(name: str) -> str:
    """Collapses the ways the model names a US state — "GA", "USA-NM",
    "New Mexico, USA" — to the full state name. Non-US jurisdictions
    ("Ireland", "British Columbia") pass through unchanged.
    """
    stripped = name.strip()
    lowered = stripped.lower()

    for prefix in _US_PREFIXES:
        if lowered.startswith(prefix):
            stripped = stripped[len(prefix) :].strip()
            lowered = stripped.lower()
            break
    for suffix in _US_SUFFIXES:
        if lowered.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
            lowered = stripped.lower()
            break

    if len(stripped) == 2:
        return US_STATE_ABBREVIATIONS.get(stripped.upper(), stripped)

    # A full name that survived prefix/suffix stripping, but possibly cased
    # oddly ("NEW MEXICO"). Match case-insensitively against the known set so
    # COASTAL_STATES and the frontend's dedup both see one spelling.
    for full_name in US_STATE_ABBREVIATIONS.values():
        if lowered == full_name.lower():
            return full_name
    return stripped


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

    raw["jurisdiction"] = canonicalize_jurisdiction(raw["jurisdiction"])
    # setdefault + normalize rather than trust the required field blindly:
    # mode=ANY forces a function call but not that every required property
    # actually lands in it (the same gap that let qualifying={} through
    # before that field got explicit required sub-keys).
    raw["currency"] = str(raw.get("currency") or "USD").strip().upper()
    raw["application_deadline"] = _parse_date(raw.get("application_deadline"))
    raw["sunset_date"] = _parse_date(raw.get("sunset_date"))

    # The function-call args come back as plain dicts; JurisdictionRule's
    # fields are typed as the actual dataclasses, and code downstream (e.g.
    # verify_rule's assess_confidence, calculator's tier/uplift handling)
    # accesses them as attributes, not dict keys.
    today = date.today()
    raw["sources"] = [
        SourceRef(
            url=s.get("url", ""),
            retrieved=today,  # code's own clock, not the model's — see module docstring bug (4)
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
