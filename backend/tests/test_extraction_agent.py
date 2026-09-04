"""Regression tests for two bugs a live extraction run surfaced (see
app/extraction/agent.py's module docstring): the model returning a US state
as a postal abbreviation instead of a full name, and the model's own
"retrieved" date being trusted instead of stamped by the pipeline's clock.

_search and _extract_with_forced_function_call are mocked — they're the only
two functions that make real network/SDK calls, and both are network calls
this test suite intentionally never makes (Layer 2/3 tests run with zero
credentials; this one shouldn't need them either to prove the plumbing
around a canned model response is correct).
"""

from datetime import date, timedelta
from unittest.mock import patch

from app.extraction.agent import canonicalize_jurisdiction, extract_jurisdiction_rule


def test_canonicalize_jurisdiction_expands_known_abbreviations():
    assert canonicalize_jurisdiction("NM") == "New Mexico"
    assert canonicalize_jurisdiction("GA") == "Georgia"
    assert canonicalize_jurisdiction("ny") == "New York"  # case-insensitive


def test_canonicalize_jurisdiction_leaves_full_names_alone():
    assert canonicalize_jurisdiction("New Mexico") == "New Mexico"
    assert canonicalize_jurisdiction("Louisiana") == "Louisiana"


def test_canonicalize_jurisdiction_leaves_non_us_two_letter_names_alone():
    # Not a US postal code, so passed through rather than mangled.
    assert canonicalize_jurisdiction("UK") == "UK"


def test_canonicalize_jurisdiction_strips_country_prefixes():
    # "USA-NM" is a form a live run actually returned — the 2-letter fix
    # alone missed it, and it still broke the COASTAL_STATES lookup.
    assert canonicalize_jurisdiction("USA-NM") == "New Mexico"
    assert canonicalize_jurisdiction("US-GA") == "Georgia"
    assert canonicalize_jurisdiction("USA Texas") == "Texas"


def test_canonicalize_jurisdiction_strips_country_suffixes():
    assert canonicalize_jurisdiction("New Mexico, USA") == "New Mexico"
    assert canonicalize_jurisdiction("Georgia, United States") == "Georgia"


def test_canonicalize_jurisdiction_normalizes_casing_of_full_names():
    assert canonicalize_jurisdiction("NEW MEXICO") == "New Mexico"
    assert canonicalize_jurisdiction("louisiana") == "Louisiana"


def test_canonicalize_jurisdiction_does_not_mangle_non_us_jurisdictions():
    # "Georgia" the country vs Georgia the state is genuinely ambiguous, but
    # these must not be touched by the US prefix/suffix stripping at all.
    assert canonicalize_jurisdiction("Ireland") == "Ireland"
    assert canonicalize_jurisdiction("British Columbia") == "British Columbia"
    assert canonicalize_jurisdiction("United Kingdom") == "United Kingdom"


def _canned_raw_response(jurisdiction: str, retrieved: str) -> dict:
    return {
        "jurisdiction": jurisdiction,
        "program_name": "Test Program",
        "base_rate": 0.25,
        "qualifying": {
            "atl_cast": True, "atl_noncast": True,
            "btl_labor_resident": True, "btl_labor_nonresident": True,
            "btl_nonlabor": True, "post_vfx": True,
        },
        "sources": [
            {
                "url": "https://example.gov/incentive",
                "retrieved": retrieved,  # the model's own claim — must be ignored
                "published": None,
                "excerpt": "25% base credit.",
                "is_primary": True,
            }
        ],
        "centroid_lat": 35.0,
        "centroid_lng": -106.0,
        "pool_status": "unknown",
        "tiers": [],
        "uplifts": [],
        "conflicts": [],
    }


@patch("app.extraction.agent._search", return_value=[])
@patch("app.extraction.agent._extract_with_forced_function_call")
def test_extract_jurisdiction_rule_canonicalizes_the_jurisdiction_field(mock_extract, mock_search):
    mock_extract.return_value = _canned_raw_response("NM", "2020-01-01")
    rule = extract_jurisdiction_rule("New Mexico")
    assert rule.jurisdiction == "New Mexico"


@patch("app.extraction.agent._search", return_value=[])
@patch("app.extraction.agent._extract_with_forced_function_call")
def test_extract_jurisdiction_rule_ignores_the_models_stated_retrieved_date(mock_extract, mock_search):
    # A stale date years in the past, as a live run against a real
    # jurisdiction actually returned for a page fetched that same day.
    stale_claim = (date.today() - timedelta(days=800)).isoformat()
    mock_extract.return_value = _canned_raw_response("Georgia", stale_claim)
    rule = extract_jurisdiction_rule("Georgia")
    assert rule.sources[0].retrieved == date.today()
