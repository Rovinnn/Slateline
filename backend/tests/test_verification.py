"""Layer 3 confidence assessment — the precedence order between states, and
the staleness boundary.

Confidence is a trust signal shown directly to the user next to a dollar
figure, so the failure that matters is a rule being labelled more trustworthy
than its sources justify (or a fresh rule being written off as stale, which
is what the model-stated `retrieved` date bug caused — see agent.py).
"""

from dataclasses import replace
from datetime import date, timedelta

from app.verification import STALE_AFTER_DAYS, assess_confidence, verify_rule

from .fixtures import PRIMARY_SOURCE, make_rule

TODAY = date(2026, 9, 3)


def _source(days_old: int, *, is_primary: bool = True):
    return replace(PRIMARY_SOURCE, retrieved=TODAY - timedelta(days=days_old), is_primary=is_primary)


def test_source_exactly_at_the_staleness_boundary_is_not_yet_stale():
    # The rule is "> STALE_AFTER_DAYS", so the boundary day itself still counts as current.
    rule = make_rule(sources=[_source(STALE_AFTER_DAYS)])
    assert assess_confidence(rule, today=TODAY) == "primary_source"


def test_one_day_past_the_boundary_is_stale():
    rule = make_rule(sources=[_source(STALE_AFTER_DAYS + 1)])
    assert assess_confidence(rule, today=TODAY) == "stale"


def test_a_single_stale_source_makes_the_whole_rule_stale():
    # Deliberate: a rule is only as current as its oldest supporting source,
    # so one stale citation downgrades it even alongside fresh ones.
    rule = make_rule(sources=[_source(1), _source(STALE_AFTER_DAYS + 100)])
    assert assess_confidence(rule, today=TODAY) == "stale"


def test_conflicts_outrank_every_other_signal():
    # Even impeccable, fresh, primary sourcing is reported as conflicting if
    # the sources disagree — the user needs to see the disagreement first.
    rule = make_rule(sources=[_source(0)], conflicts=["Two sources give different base rates."])
    assert assess_confidence(rule, today=TODAY) == "conflicting"


def test_no_sources_is_unverified():
    assert assess_confidence(make_rule(sources=[]), today=TODAY) == "unverified"


def test_official_secondary_when_no_source_is_primary():
    rule = make_rule(sources=[_source(0, is_primary=False)])
    assert assess_confidence(rule, today=TODAY) == "official_secondary"


def test_one_primary_among_secondaries_is_enough():
    rule = make_rule(sources=[_source(0, is_primary=False), _source(0, is_primary=True)])
    assert assess_confidence(rule, today=TODAY) == "primary_source"


def test_verify_rule_recomputes_confidence_rather_than_trusting_the_input():
    # Layer 1 sets confidence to a placeholder; a rule arriving with an
    # over-claimed label must be corrected, not honoured.
    overclaimed = make_rule(sources=[], confidence="primary_source")
    assert verify_rule(overclaimed, today=TODAY).confidence == "unverified"


def test_verify_rule_changes_nothing_but_the_confidence_field():
    before = make_rule(sources=[_source(0)], constraint_gaps={"coastline": "landlocked"})
    after = verify_rule(before, today=TODAY)
    assert after == replace(before, confidence=after.confidence)
