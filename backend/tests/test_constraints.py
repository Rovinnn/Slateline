from datetime import date

from app.constraints import COASTAL_STATES, US_STATES_AND_DC, constraint_gaps_for

from .fixtures import make_rule


def test_landlocked_jurisdiction_gets_a_coastline_gap():
    rule = make_rule(jurisdiction="New Mexico")
    gaps = constraint_gaps_for(rule)
    assert "coastline" in gaps
    assert "New Mexico" in gaps["coastline"]


def test_coastal_jurisdiction_has_no_coastline_gap():
    rule = make_rule(jurisdiction="Louisiana")
    assert "coastline" not in constraint_gaps_for(rule)


def test_great_lakes_only_state_still_fails_ocean_coastline():
    # Illinois touches Lake Michigan but not an ocean/Gulf — the constraint
    # label is specifically "ocean coastline".
    rule = make_rule(jurisdiction="Illinois")
    assert "coastline" in constraint_gaps_for(rule)


def test_sunset_before_spring_2027_fails_spring_only():
    rule = make_rule(jurisdiction="Georgia", sunset_date=date(2026, 12, 31))
    gaps = constraint_gaps_for(rule)
    assert "spring_only" in gaps
    assert "2026-12-31" in gaps["spring_only"]


def test_closed_pool_fails_spring_only():
    rule = make_rule(jurisdiction="Georgia", pool_status="closed")
    assert "spring_only" in constraint_gaps_for(rule)


def test_open_pool_with_no_sunset_passes_spring_only():
    rule = make_rule(jurisdiction="Georgia", pool_status="open", sunset_date=None)
    assert "spring_only" not in constraint_gaps_for(rule)


def test_large_soundstage_is_never_asserted():
    # Deliberately unresolved for every jurisdiction — see constraints.py's
    # docstring for why guessing here would be worse than leaving it blank.
    for name in ["Georgia", "New Mexico", "Louisiana", "Texas", "Wyoming"]:
        assert "large_soundstage" not in constraint_gaps_for(make_rule(jurisdiction=name))


# ---------- non-US jurisdictions, where this module has no geography ----------


def test_a_non_us_jurisdiction_is_not_told_it_has_no_coastline():
    """Ireland is an island; saying otherwise is a falsehood, not a limitation.

    COASTAL_STATES is a list of US states, so absence from it means "not a
    coastal US state" — which for Ireland means we have no data, not that it's
    landlocked. This function's contract (see its docstring) is that an absent
    key means satisfies-it *or unknown*, never a guess, and asserting a
    negative from missing data broke exactly that.
    """
    ireland = make_rule(jurisdiction="Ireland")
    assert "coastline" not in constraint_gaps_for(ireland)

    for name in ("United Kingdom", "British Columbia", "New South Wales"):
        assert "coastline" not in constraint_gaps_for(make_rule(jurisdiction=name)), name


def test_us_states_still_get_a_coastline_verdict_in_both_directions():
    # The fix must not have turned the constraint off for the jurisdictions it
    # genuinely knows about.
    assert "coastline" in constraint_gaps_for(make_rule(jurisdiction="New Mexico"))
    assert "coastline" not in constraint_gaps_for(make_rule(jurisdiction="Georgia"))
    assert "coastline" in constraint_gaps_for(make_rule(jurisdiction="Arizona"))


def test_the_us_state_list_is_shared_with_canonicalisation_rather_than_retyped():
    # Two hand-maintained lists of US states would eventually disagree about
    # DC or a spelling, and the disagreement would be silent.
    from app.extraction.agent import US_STATE_ABBREVIATIONS

    assert US_STATES_AND_DC == frozenset(US_STATE_ABBREVIATIONS.values())
    assert "District of Columbia" in US_STATES_AND_DC
    assert COASTAL_STATES <= US_STATES_AND_DC
