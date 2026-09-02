from datetime import date

from app.constraints import constraint_gaps_for

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
