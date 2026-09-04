"""BUILD_BRIEF.md section 9: "Snapshot test on extraction schema conformance
so a malformed model response fails loudly rather than silently producing
wrong numbers."

The dangerous failure mode here isn't a crash — it's silence. A live run
against Oklahoma once returned `qualifying: {}`, which satisfied the schema
(the key was present), passed dataclass construction, and then computed a
$0 credit because calculator.py reads it with `.get()`. Nothing errored;
the answer was just wrong. So these tests assert two things:

1. The schema and the dataclass can't drift apart — add a field to
   JurisdictionRule and forget RECORD_JURISDICTION_RULE_SCHEMA, and this
   fails, rather than Layer 1 quietly never populating it.
2. A malformed model response raises, rather than constructing a
   half-populated rule that computes a plausible-looking wrong number.
"""

from dataclasses import fields

import pytest

from app.calculator import QUALIFYING_KEYS
from app.extraction.agent import RECORD_JURISDICTION_RULE_SCHEMA
from app.models import JurisdictionRule, SourceRef, Tier, Uplift

PARAMS = RECORD_JURISDICTION_RULE_SCHEMA["parameters"]
PROPERTIES = PARAMS["properties"]

# Filled by Layer 3 (verification.verify_rule / constraints.constraint_gaps_for),
# never by the model — see those modules for why. Everything else on the
# dataclass is Layer 1's job and must appear in the schema.
LAYER_3_OWNED = {"confidence", "constraint_gaps"}


def test_schema_covers_every_field_layer_1_is_responsible_for():
    dataclass_fields = {f.name for f in fields(JurisdictionRule)}
    missing = dataclass_fields - set(PROPERTIES) - LAYER_3_OWNED
    assert not missing, (
        f"JurisdictionRule fields absent from RECORD_JURISDICTION_RULE_SCHEMA: {sorted(missing)}. "
        "Add them to the schema (so the model populates them) or to LAYER_3_OWNED (if they're derived)."
    )


def test_schema_declares_no_field_the_dataclass_lacks():
    # A typo'd or stale property means the model is asked for something that
    # then blows up JurisdictionRule(**raw) with an unexpected keyword.
    dataclass_fields = {f.name for f in fields(JurisdictionRule)}
    extra = set(PROPERTIES) - dataclass_fields
    assert not extra, f"Schema declares properties JurisdictionRule doesn't have: {sorted(extra)}"


def test_required_list_is_a_subset_of_declared_properties():
    assert set(PARAMS["required"]) <= set(PROPERTIES)


def test_qualifying_requires_exactly_the_keys_the_calculator_reads():
    # The Oklahoma `qualifying: {}` bug: calculator.py treats every absent key
    # as not-qualifying, so a partial object silently zeroes the credit.
    qualifying = PROPERTIES["qualifying"]
    assert set(qualifying["required"]) == set(QUALIFYING_KEYS)
    assert set(qualifying["properties"]) == set(QUALIFYING_KEYS)


def test_sources_schema_does_not_ask_the_model_for_retrieved():
    # `retrieved` is when this pipeline fetched the page — a fact the model
    # cannot know. agent.py stamps it with date.today(); asking the model
    # invited the stale-date bug it caused. See agent.py's docstring, bug (4).
    source_props = PROPERTIES["sources"]["items"]["properties"]
    assert "retrieved" not in source_props


def test_sources_schema_matches_sourceref_minus_retrieved():
    source_props = set(PROPERTIES["sources"]["items"]["properties"])
    assert source_props == {f.name for f in fields(SourceRef)} - {"retrieved"}


def test_tier_and_uplift_schemas_match_their_dataclasses():
    assert set(PROPERTIES["tiers"]["items"]["properties"]) == {f.name for f in fields(Tier)}
    assert set(PROPERTIES["uplifts"]["items"]["properties"]) == {f.name for f in fields(Uplift)}


def test_every_schema_required_field_is_one_the_model_can_answer_without_guessing():
    # Guard against someone "fixing" a null-heavy response by making a policy
    # figure required — that pressures the model to invent one, which is the
    # exact failure the whole design is built to avoid. Only identity,
    # quotable facts, geography and the has-an-"unknown"-option enum qualify.
    allowed_required = {
        "jurisdiction",
        "program_name",
        "base_rate",
        "qualifying",
        "sources",
        "centroid_lat",
        "centroid_lng",
        "pool_status",
    }
    assert set(PARAMS["required"]) <= allowed_required, (
        "A figure the model might not find in its sources became required — "
        "leave it optional so 'not stated' stays representable as null."
    )
    assert "unknown" in PROPERTIES["pool_status"]["enum"]


# ---------- behavioural: malformed responses must raise, not limp on ----------

def _minimal_raw() -> dict:
    """The smallest response agent.py's post-processing can turn into a rule."""
    return {
        "jurisdiction": "Testland",
        "program_name": "Test Program",
        "base_rate": 0.25,
        "qualifying": dict.fromkeys(QUALIFYING_KEYS, True),
        "per_person_wage_cap": None,
        "minimum_spend": None,
        "per_project_cap": None,
        "tiers": [],
        "uplifts": [],
        "annual_pool_total": None,
        "annual_pool_remaining": None,
        "pool_status": "unknown",
        "application_deadline": None,
        "sunset_date": None,
        "under_review": False,
        "is_discretionary": False,
        "film_office_contact": None,
        "centroid_lat": 0.0,
        "centroid_lng": 0.0,
        "sources": [],
        "confidence": "unverified",
        "conflicts": [],
    }


def test_minimal_raw_response_constructs_a_rule():
    # Sanity: the negative cases below fail for the reason stated, not because
    # this baseline was already broken.
    assert JurisdictionRule(**_minimal_raw()).jurisdiction == "Testland"


@pytest.mark.parametrize("dropped", ["jurisdiction", "program_name", "base_rate", "pool_status"])
def test_missing_required_field_raises_rather_than_defaulting(dropped):
    raw = _minimal_raw()
    del raw[dropped]
    with pytest.raises(TypeError):
        JurisdictionRule(**raw)


def test_hallucinated_extra_field_raises():
    raw = _minimal_raw()
    raw["estimated_benefit"] = 1_000_000  # the model must never send a computed figure
    with pytest.raises(TypeError):
        JurisdictionRule(**raw)
