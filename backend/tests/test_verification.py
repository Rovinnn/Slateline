"""Layer 3 confidence assessment — the precedence order between states, and
the staleness boundary.

Confidence is a trust signal shown directly to the user next to a dollar
figure, so the failure that matters is a rule being labelled more trustworthy
than its sources justify (or a fresh rule being written off as stale, which
is what the model-stated `retrieved` date bug caused — see agent.py).
"""

from dataclasses import replace
from datetime import date, timedelta

import pytest

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


# --- is_discretionary cross-check -------------------------------------------
#
# The live pipeline reported Louisiana — a statutory transferable credit — as
# discretionary on every run, which dropped the seed set's top-ranked
# jurisdiction out of the deployed ranking entirely. Describing the field to
# the model failed twice and broke Texas the second time, so the correction
# lives here.


@pytest.mark.parametrize("mechanism", ["refundable", "transferable", "non_refundable"])
def test_discretionary_is_cleared_for_entitlement_mechanisms(mechanism):
    # You claim a tax credit because a statute allows it; nobody decides
    # whether you may have one.
    claimed = make_rule(credit_type=mechanism, is_discretionary=True)
    assert verify_rule(claimed, today=TODAY).is_discretionary is False


@pytest.mark.parametrize("mechanism", ["rebate", "unknown"])
def test_discretionary_survives_for_grant_like_mechanisms(mechanism):
    # Texas's TMIIIP is a competitive grant and genuinely is not modelable.
    # The guard must not rehabilitate it into the ranking.
    claimed = make_rule(credit_type=mechanism, is_discretionary=True)
    assert verify_rule(claimed, today=TODAY).is_discretionary is True


def test_guard_never_invents_discretion():
    # It only ever clears a claim, never adds one.
    for mechanism in ("refundable", "transferable", "non_refundable", "rebate", "unknown"):
        rule = make_rule(credit_type=mechanism, is_discretionary=False)
        assert verify_rule(rule, today=TODAY).is_discretionary is False


def test_louisiana_computes_whichever_way_its_mechanism_lands():
    # Louisiana's credit_type alternates between "refundable" and
    # "transferable" across extraction runs. Both are entitlements, so the
    # guard has to fire either way or the bug returns intermittently.
    for mechanism in ("refundable", "transferable"):
        rule = make_rule(jurisdiction="Louisiana", credit_type=mechanism, is_discretionary=True)
        assert verify_rule(rule, today=TODAY).is_discretionary is False


# --- discretion read from the retrieved sources -----------------------------
#
# Layer 1 is not stable on this boolean (Texas: True, False, False over three
# consecutive live runs), so Layer 3 decides it from the text Layer 1 quoted.
# These fixtures use the language the real sources actually used.


def _sourced(excerpt: str, **kw):
    return make_rule(sources=[replace(PRIMARY_SOURCE, excerpt=excerpt)], **kw)


def test_a_cash_grant_is_not_modelable_however_the_model_classified_it():
    # Texas's own sources: "TMIIIP is a grant program", "cash grant up to 31%".
    for claimed in (True, False):
        rule = _sourced(
            "The Texas Moving Image Industry Incentive program is a grant program. "
            "Qualifying projects are eligible to receive a cash grant up to 31%.",
            credit_type="rebate",
            is_discretionary=claimed,
        )
        assert verify_rule(rule, today=TODAY).is_discretionary is True


def test_a_tax_credit_is_an_entitlement_however_the_model_classified_it():
    # Louisiana, Georgia and New Mexico all describe themselves this way.
    for claimed in (True, False):
        for excerpt in (
            "Louisiana's Motion Picture Production Tax Credit offers 25-40% transferable tax credits.",
            "The Film Tax Credit is a 20% based transferable tax credit.",
            'The tax credit created by this section may be referred to as the "new film production tax credit".',
        ):
            rule = _sourced(excerpt, credit_type="transferable", is_discretionary=claimed)
            assert verify_rule(rule, today=TODAY).is_discretionary is False


def test_entitlement_language_wins_when_both_appear():
    # A credit that merely mentions an adjacent grant fund is still a credit;
    # wrongly refusing one costs a jurisdiction its place in the ranking.
    rule = _sourced(
        "The state offers a transferable tax credit. A separate cash grant program exists for post.",
        credit_type="transferable",
        is_discretionary=True,
    )
    assert verify_rule(rule, today=TODAY).is_discretionary is False


def test_silent_sources_fall_back_to_the_payout_mechanism():
    # No marker either way: a statutory mechanism still can't be discretionary,
    # and a rebate keeps whatever Layer 1 said.
    quiet = "Productions must apply within 60 days of the end of principal photography."
    assert verify_rule(
        _sourced(quiet, credit_type="refundable", is_discretionary=True), today=TODAY
    ).is_discretionary is False
    assert verify_rule(
        _sourced(quiet, credit_type="rebate", is_discretionary=True), today=TODAY
    ).is_discretionary is True


def test_classification_never_reads_the_jurisdiction_name():
    # The guard must not become a lookup table wearing a disguise: the same
    # sources must produce the same answer under any jurisdiction name.
    excerpt = "The program is a grant program paying a cash grant on qualified spend."
    a = _sourced(excerpt, jurisdiction="Texas", credit_type="rebate", is_discretionary=False)
    b = _sourced(excerpt, jurisdiction="Mongolia", credit_type="rebate", is_discretionary=False)
    assert (
        verify_rule(a, today=TODAY).is_discretionary
        == verify_rule(b, today=TODAY).is_discretionary
        is True
    )


def test_classification_reads_the_program_name_too():
    # Some sources only name the thing: "... Film Production Grant Program".
    rule = make_rule(
        program_name="State Film Production Grant Program",
        credit_type="rebate",
        is_discretionary=False,
        sources=[replace(PRIMARY_SOURCE, excerpt="Applications open annually.")],
    )
    assert verify_rule(rule, today=TODAY).is_discretionary is True


def test_discretion_classification_touches_no_figure():
    before = _sourced("a cash grant program", credit_type="rebate", is_discretionary=False)
    after = verify_rule(before, today=TODAY)
    assert after == replace(before, confidence=after.confidence, is_discretionary=True)


def test_a_grant_is_not_rescued_by_other_states_credits_in_its_sources():
    # This shipped: a search for Texas returns think-pieces comparing every
    # state, so "tax credit" appeared in the source set of a cash-grant
    # program with no tax credit, and it ranked FIRST at $277,658. The
    # mechanism is extracted about this program; the excerpts are not.
    rule = _sourced(
        "TMIIIP is a grant program paying a cash grant on Texas spend. "
        "Georgia by contrast offers a 20% transferable tax credit and Louisiana "
        "offers 25-40% transferable tax credits against tax liability.",
        credit_type="rebate",
        is_discretionary=False,
    )
    assert verify_rule(rule, today=TODAY).is_discretionary is True


def test_mechanism_settles_a_tax_credit_without_consulting_excerpts():
    # A statutory credit stays rankable even if its sources are full of grant
    # talk about neighbouring programs.
    rule = _sourced(
        "The state also runs a separate cash grant program at the discretion of the film office.",
        credit_type="transferable",
        is_discretionary=True,
    )
    assert verify_rule(rule, today=TODAY).is_discretionary is False
