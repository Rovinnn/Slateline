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


def test_a_non_us_two_letter_code_now_resolves_to_its_country():
    # This used to assert "UK" passed through untouched, which was right while
    # the tool only handled US states. Now that it covers 122 jurisdictions in
    # 59 currencies, a bare country code is the same problem "GA" always was,
    # and leaving it alone breaks dedup and display the same way.
    assert canonicalize_jurisdiction("UK") == "United Kingdom"


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


def test_bare_country_codes_canonicalise_like_state_codes_do():
    """Hungary came back as "HU" from a live league-table run.

    Same inconsistency US states show — the model returns a code sometimes and
    a name others — just outside the postal-code table, so it went unnoticed
    until the tool started covering countries.
    """
    assert canonicalize_jurisdiction("HU") == "Hungary"
    assert canonicalize_jurisdiction("IE") == "Ireland"
    assert canonicalize_jurisdiction("jp") == "Japan"


def test_us_state_codes_still_win_where_the_two_tables_could_disagree():
    # "GA" is Georgia the US state here, not any country. US is this tool's
    # centre of gravity and the lookup order encodes that.
    assert canonicalize_jurisdiction("GA") == "Georgia"
    assert canonicalize_jurisdiction("IN") == "Indiana"


def test_an_unknown_two_letter_code_passes_through_untouched():
    # Better a bare code the user can see than a wrong country name.
    assert canonicalize_jurisdiction("ZZ") == "ZZ"


# --- retrieval ranking -------------------------------------------------------
#
# Retrieval, not the model, was the source of this pipeline's
# irreproducibility: the same jurisdiction came back with 5, 10, 12 and 25
# sources on different runs, and the tail was cross-state commentary.


def test_statute_outranks_agency_outranks_commentary():
    from app.extraction.agent import _authority

    assert _authority("https://law.justia.com/codes/texas/") == 2
    assert _authority("https://revenue.louisiana.gov/whatever") == 2
    assert _authority("https://www.legis.la.gov/law.aspx") == 2
    assert _authority("https://gov.texas.gov/film/page") == 2
    assert _authority("https://www.georgia.org/film-office") == 0
    assert _authority("https://nmfilm.com/incentives") == 1
    assert _authority("https://ontariocreates.ca/tax-credits") == 1
    assert _authority("https://someblog.com/best-film-tax-credits-2026") == 0


def test_ranking_is_total_and_deterministic():
    # Same set in any order must produce the same list out, or the input to
    # the model still drifts between runs.
    from app.extraction.agent import _authority

    urls = [
        "https://someblog.com/z",
        "https://law.justia.com/a",
        "https://nmfilm.com/b",
        "https://someblog.com/a",
        "https://revenue.state.gov/c",
    ]
    key = lambda u: (-_authority(u), u)
    assert sorted(urls, key=key) == sorted(reversed(urls), key=key)
    assert sorted(urls, key=key)[0].startswith("https://law.justia.com")
    assert sorted(urls, key=key)[-1] == "https://someblog.com/z"


def test_government_hosts_are_matched_structurally_not_by_country_list():
    # A tool advertising six regions cannot recognise only Anglophone
    # governments: an earlier version scored every Spanish, French, Korean and
    # Colombian source 0, silently dropping "statute first" for most of the
    # 122 supported jurisdictions.
    from app.extraction.agent import _authority

    for url in (
        "https://www.boe.gob.es/x",       # Spain
        "https://www.legifrance.gouv.fr/x",  # France
        "https://www.law.go.kr/x",        # Korea
        "https://www.dian.gov.co/x",      # Colombia
        "https://www.canada.gc.ca/x",     # Canada
        "https://www.screenaustralia.gov.au/x",
    ):
        assert _authority(url) == 2, url


# --- grant confirmation ------------------------------------------------------


def _rule(credit_type, discretionary):
    from tests.fixtures import make_rule

    return make_rule(credit_type=credit_type, is_discretionary=discretionary)


def test_a_tax_credit_is_not_re_extracted():
    # The common path must stay one call: a statutory claim needs no second
    # opinion, and most of the 122 jurisdictions are credits.
    from unittest.mock import patch

    from app.extraction.agent import extract_jurisdiction_rule_confirmed

    with patch("app.extraction.agent.extract_jurisdiction_rule") as ex:
        ex.return_value = _rule("transferable", False)
        extract_jurisdiction_rule_confirmed("Anywhere")
        assert ex.call_count == 1


def test_a_grant_already_identified_is_not_re_extracted():
    from unittest.mock import patch

    from app.extraction.agent import extract_jurisdiction_rule_confirmed

    with patch("app.extraction.agent.extract_jurisdiction_rule") as ex:
        ex.return_value = _rule("rebate", True)
        assert extract_jurisdiction_rule_confirmed("Anywhere").is_discretionary is True
        assert ex.call_count == 1


def test_disagreement_refuses_rather_than_votes():
    # THE case: Texas returned True, False, False across three runs. A
    # majority vote answers False, which is wrong. One retrieval calling it a
    # grant is enough not to present the money as bankable.
    from unittest.mock import patch

    from app.extraction.agent import extract_jurisdiction_rule_confirmed

    with patch("app.extraction.agent.extract_jurisdiction_rule") as ex:
        ex.side_effect = [_rule("rebate", False), _rule("rebate", True)]
        assert extract_jurisdiction_rule_confirmed("Anywhere").is_discretionary is True
        assert ex.call_count == 2


def test_two_agreeing_retrievals_let_a_rebate_rank():
    # A by-right rebate must not be refused just for being a rebate.
    from unittest.mock import patch

    from app.extraction.agent import extract_jurisdiction_rule_confirmed

    with patch("app.extraction.agent.extract_jurisdiction_rule") as ex:
        ex.side_effect = [_rule("rebate", False), _rule("rebate", False)]
        assert extract_jurisdiction_rule_confirmed("Anywhere").is_discretionary is False
        assert ex.call_count == 2
