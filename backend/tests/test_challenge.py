"""The second pass, whose only job is to disprove the first.

Most of this file is about restraint rather than detection. A model asked to
find problems will find them, and a conflict-detection pass that cries wolf is
worse than none: it trains a reader to ignore the one flag that mattered. So
the tests that matter most here are the ones asserting it stays quiet —
silence in a source is not contradiction, a surprising figure is not
contradiction, and a disagreeing phone number is not a reason to mark a whole
jurisdiction unreliable.

The model is mocked throughout. What's under test is the machinery around it:
what gets recorded, what gets ignored, what reaches the rule, and — the part
that was unreachable from our own code until this pass existed — that a
material contradiction actually drives confidence to "conflicting".
"""

from datetime import date
from unittest.mock import patch

import pytest

from app.extraction.challenge import (
    CHALLENGEABLE_FIELDS,
    MATERIAL_FIELDS,
    RECORD_CHALLENGE_SCHEMA,
    ChallengeFinding,
    ChallengeReport,
    apply_challenge,
    challenge_rule,
)
from app.verification import verify_rule

from .fixtures import make_rule

TODAY = date(2026, 9, 5)


def fake_search(count=4):
    return [object()] * count


def run_challenge(raw, rule=None, sources=4):
    """Drive challenge_rule with a canned model response."""
    rule = rule or make_rule(jurisdiction="Georgia", base_rate=0.30)
    with (
        patch("app.extraction.challenge._challenge_search", return_value=fake_search(sources)),
        patch("app.extraction.challenge._challenge_with_forced_function_call", return_value=raw),
    ):
        return challenge_rule(rule)


def contradiction(field_name, **over):
    base = {
        "field": field_name,
        "current_value": "30.0%",
        "source_says": "20% as of HB 1001",
        "url": "https://example.gov/hb1001",
        "excerpt": "The credit is reduced to 20% for tax years beginning 2027.",
    }
    base.update(over)
    return base


# ---------- recording what the pass found ----------


def test_a_material_contradiction_is_recorded_with_both_figures():
    # The line has to name what we hold *and* what the source says, or a
    # reader can't adjudicate it — only worry about it.
    report = run_challenge({"contradictions": [contradiction("base_rate")], "corroborations": []})

    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.severity == "material"
    assert "30.0%" in finding.describe()
    assert "20% as of HB 1001" in finding.describe()
    assert "example.gov" in finding.describe()


def test_corroborations_are_kept_because_finding_nothing_is_evidence():
    report = run_challenge(
        {
            "contradictions": [],
            "corroborations": [
                {"field": "base_rate", "url": "https://x.gov", "excerpt": "still 30%"},
                {"field": "base_rate", "url": "https://y.gov", "excerpt": "30 percent"},
            ],
        }
    )
    assert report.corroborated_fields == ["base_rate"]
    assert report.challenged_cleanly is True


def test_a_clean_challenge_requires_having_actually_read_something():
    """Nothing found because nothing was checked is not a clean bill of health.

    This distinction is the difference between "we looked and it holds up"
    and "we couldn't look" — which must never render as the same thing.
    """
    checked = run_challenge({"contradictions": [], "corroborations": []}, sources=4)
    unchecked = run_challenge({"contradictions": [], "corroborations": []}, sources=0)

    assert checked.challenged_cleanly is True
    assert unchecked.challenged_cleanly is False


def test_an_unrecognised_field_is_dropped_rather_than_recorded_unattributably():
    # mode=ANY forces the call, not its contents — the same gap that let
    # qualifying={} through the discovery pass.
    report = run_challenge(
        {"contradictions": [contradiction("vibes"), contradiction("base_rate")], "corroborations": []}
    )
    assert [f.field_name for f in report.findings] == ["base_rate"]


# ---------- severity: code's judgement, not the model's ----------


def test_a_disagreeing_phone_number_does_not_condemn_the_whole_jurisdiction():
    report = run_challenge(
        {"contradictions": [contradiction("film_office_contact")], "corroborations": []}
    )
    assert report.findings[0].severity == "minor"
    assert report.material_findings == []
    assert report.challenged_cleanly is True


@pytest.mark.parametrize("field_name", sorted(MATERIAL_FIELDS))
def test_every_material_field_is_treated_as_material(field_name):
    # Guards the list itself: a field added to the rule and to
    # CHALLENGEABLE_FIELDS but forgotten here would downgrade nothing.
    report = run_challenge({"contradictions": [contradiction(field_name)], "corroborations": []})
    assert report.findings[0].severity == "material"


def test_the_schema_only_offers_fields_the_calculator_can_act_on():
    enum = RECORD_CHALLENGE_SCHEMA["parameters"]["properties"]["contradictions"]["items"]["properties"]["field"]["enum"]
    assert enum == CHALLENGEABLE_FIELDS
    assert MATERIAL_FIELDS <= set(CHALLENGEABLE_FIELDS)


def test_the_schema_tells_the_model_that_silence_is_not_contradiction():
    # The single most important instruction in the whole pass, so it's pinned
    # rather than left to survive an incidental edit.
    assert "merely silent" in RECORD_CHALLENGE_SCHEMA["description"]


# ---------- applying it to the rule ----------


def report_with(*findings, jurisdiction="Georgia"):
    return ChallengeReport(jurisdiction=jurisdiction, findings=list(findings), sources_checked=4)


def material(field_name="base_rate", url="https://example.gov/hb1001"):
    return ChallengeFinding(
        field_name=field_name,
        current_value="30.0%",
        source_says="20%",
        url=url,
        excerpt="reduced to 20%",
        severity="material",
    )


def test_a_material_contradiction_makes_the_rule_conflicting():
    """The state that was unreachable from our own code until now.

    verification.assess_confidence has always returned "conflicting" when
    `conflicts` is non-empty. Nothing ever populated it.
    """
    rule = make_rule(jurisdiction="Georgia")
    assert verify_rule(rule, today=TODAY).confidence != "conflicting"

    challenged = apply_challenge(rule, report_with(material()), today=TODAY)
    assert verify_rule(challenged, today=TODAY).confidence == "conflicting"


def test_applying_a_challenge_never_changes_a_figure():
    # The tool's position is that it surfaces disagreements rather than
    # resolving them quietly. Which of two sources is right is a judgement,
    # and making it silently is the thing this product exists not to do.
    rule = make_rule(jurisdiction="Georgia", base_rate=0.30)
    challenged = apply_challenge(rule, report_with(material()), today=TODAY)

    assert challenged.base_rate == 0.30
    assert challenged.pool_status == rule.pool_status
    assert challenged.minimum_spend == rule.minimum_spend


def test_the_contradicting_source_is_added_so_the_conflict_is_citable():
    rule = make_rule(jurisdiction="Georgia")
    challenged = apply_challenge(rule, report_with(material()), today=TODAY)

    added = [s for s in challenged.sources if s.url == "https://example.gov/hb1001"]
    assert len(added) == 1
    assert added[0].excerpt == "reduced to 20%"
    # Evidence, but not the statute: trade coverage that a pool closed should
    # never promote a rule to primary_source confidence.
    assert added[0].is_primary is False
    assert added[0].retrieved == TODAY


def test_a_source_already_cited_is_not_added_twice():
    rule = make_rule(jurisdiction="Georgia")
    existing = rule.sources[0].url
    challenged = apply_challenge(rule, report_with(material(url=existing)), today=TODAY)

    assert len(challenged.sources) == len(rule.sources)


def test_minor_findings_do_not_reach_the_rule_at_all():
    rule = make_rule(jurisdiction="Georgia")
    minor = ChallengeFinding(
        field_name="film_office_contact",
        current_value="404-555-0100",
        source_says="404-555-0199",
        url="https://example.gov/contact",
        excerpt="call 404-555-0199",
        severity="minor",
    )
    challenged = apply_challenge(rule, report_with(minor), today=TODAY)

    assert challenged.conflicts == rule.conflicts
    assert verify_rule(challenged, today=TODAY).confidence != "conflicting"


def test_a_clean_challenge_leaves_the_rule_untouched():
    rule = make_rule(jurisdiction="Georgia")
    assert apply_challenge(rule, report_with(), today=TODAY) is rule


def test_existing_conflicts_are_added_to_rather_than_replaced():
    rule = make_rule(jurisdiction="Georgia", conflicts=["an earlier disagreement"])
    challenged = apply_challenge(rule, report_with(material()), today=TODAY)

    assert challenged.conflicts[0] == "an earlier disagreement"
    assert len(challenged.conflicts) == 2


def test_two_challenges_in_a_row_do_not_duplicate_the_same_source():
    # The endpoint is re-runnable, and a user pressing refresh twice should
    # not accumulate the same citation.
    rule = make_rule(jurisdiction="Georgia")
    once = apply_challenge(rule, report_with(material()), today=TODAY)
    twice = apply_challenge(once, report_with(material()), today=TODAY)

    assert len(twice.sources) == len(once.sources)


# ---------- absence is not a position a source can contradict ----------
#
# Every case below came from the first live run. Georgia produced four
# "material contradictions", all of the shape "we have: not stated" against a
# source saying "no cap" / "None" / "no sunset clause" — sources that agree.
# It would have rendered "4 sources disagree with this program's terms" on the
# strength of four sources confirming it.


@pytest.mark.parametrize(
    "current,says",
    [
        ("not stated", "no cap"),
        ("not stated", "None"),
        ("not stated", "no sunset clause"),
        ("not stated", "$130M"),
        ("None", "no annual cap"),
    ],
)
def test_a_source_filling_a_gap_is_not_a_source_disagreeing(current, says):
    report = run_challenge(
        {"contradictions": [contradiction("annual_pool_total", current_value=current, source_says=says)],
         "corroborations": []}
    )
    assert report.material_findings == []
    assert report.challenged_cleanly is True


def test_the_information_is_kept_rather_than_silently_dropped():
    # A source supplying a value we lack is useful — New Mexico's "payouts
    # typically arrive 6 to 18 months" is exactly what months_to_payment
    # wants. It just isn't a conflict.
    report = run_challenge(
        {"contradictions": [contradiction("months_to_payment", current_value="not stated",
                                          source_says="6 to 18 months")],
         "corroborations": []}
    )
    assert "months_to_payment" in report.corroborated_fields


def test_a_real_disagreement_between_two_stated_values_still_lands():
    # The one genuine finding from the live run: New Mexico's pool reported as
    # $140M by us, $130M and $120M by two other sources.
    report = run_challenge(
        {"contradictions": [contradiction("annual_pool_total", current_value="140000000",
                                          source_says="$130M")],
         "corroborations": []}
    )
    assert len(report.material_findings) == 1
    assert report.challenged_cleanly is False


def test_both_sides_saying_nothing_in_different_words_is_agreement():
    report = run_challenge(
        {"contradictions": [contradiction("sunset_date", current_value="not stated", source_says="None")],
         "corroborations": []}
    )
    assert report.material_findings == []
