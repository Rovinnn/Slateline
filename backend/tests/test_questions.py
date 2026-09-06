"""Pricing the things the calculator refused to guess at.

Layer 2 declines constantly, and every refusal left a note: an uplift it can't
machine-check, fringes no source addressed, a pool whose balance nobody
published. Honest, and completely inert — a flat list of caveats where nothing
distinguished a $2,000 unknown from a $200,000 one.

They're the highest-value phone calls available. This module prices them by
asking the calculator what the answer would be if the unknown resolved the
other way and subtracting, so every figure is a difference between two runs of
the same compute_benefit that produced the number on screen. Nothing here
estimates anything on its own, which is the only reason these figures can sit
next to the verified ones.
"""

import pytest

from app.calculator import compute_benefit
from app.models import Uplift
from app.questions import MATERIALITY, open_questions
from app.seed_jurisdictions import GEORGIA, NEW_MEXICO, TEXAS

from .fixtures import make_budget, make_rule
from .test_seed_jurisdictions import INDIE_DRAMA_BUDGET, REAL_DISTANCES_KM


def ask(rule, budget=None, **kw):
    budget = budget or INDIE_DRAMA_BUDGET
    km = REAL_DISTANCES_KM.get(rule.jurisdiction)
    benefit = compute_benefit(budget, rule, distance_km=km, **kw)
    return benefit, open_questions(budget, rule, benefit, distance_km=km, **kw)


def find(questions, needle):
    return next((q for q in questions if needle.lower() in q.question.lower()), None)


# ---------- upside ----------


def test_an_unverifiable_uplift_is_priced_rather_than_merely_noted():
    """Georgia's GEP uplift, which the calculator logs and refuses to apply.

    It is not a footnote. It is worth six figures, and it is a question with a
    yes/no answer that one phone call resolves.
    """
    _, qs = ask(GEORGIA)
    q = find(qs, "uplift")

    assert q is not None
    assert q.worth == pytest.approx(151_861, abs=1)
    assert "film office" in q.ask
    # The figure has to be arguable, so it says how it was reached.
    assert "carried through monetisation" in q.basis


def test_the_uplift_figure_is_the_whole_chain_not_just_the_extra_credit():
    """+10% of qualifying spend is not +10% of net benefit.

    A transferable credit is discounted and paid late, so the uplift arrives
    diminished the same way the base credit does. Quoting the gross figure
    would overstate what the phone call is worth by about a third.
    """
    benefit, qs = ask(GEORGIA)
    naive_gross_uplift = benefit.qualifying_spend * 0.10
    assert find(qs, "uplift").worth < naive_gross_uplift


def test_unstated_fringes_are_priced_from_the_budget_not_guessed():
    _, qs = ask(GEORGIA)
    q = find(qs, "fringes")

    assert q is not None
    assert q.worth > MATERIALITY
    assert "don't address it either way" in q.basis


def test_no_fringe_question_when_the_statute_actually_answered_it():
    # Nothing to confirm; asking anyway would train the reader to skim.
    settled = make_rule(minimum_spend=None, fringes_qualify=True)
    _, qs = ask(settled)
    assert find(qs, "fringes") is None


def test_no_fringe_question_when_the_budget_has_no_payroll_burden():
    _, qs = ask(make_rule(minimum_spend=None), budget=make_budget(fringe_rate=0))
    assert find(qs, "fringes") is None


# ---------- risk, which is the half that matters more ----------


def test_unconfirmed_funding_availability_puts_the_whole_benefit_at_risk():
    """The product's own wedge, priced.

    A 25% credit you can't be allocated is a 0% credit, so the exposure is not
    a fraction of the benefit — it is all of it.
    """
    benefit, qs = ask(NEW_MEXICO)
    q = find(qs, "funding pool")

    assert q is not None
    assert q.is_risk is True
    assert q.worth == pytest.approx(-benefit.net_benefit)


def test_risk_outranks_upside_when_it_is_larger():
    # Ordered by absolute value, because the point is what to do next — and
    # "the whole thing might be unavailable" beats "there might be more".
    _, qs = ask(NEW_MEXICO)
    assert qs[0].is_risk is True


def test_a_capping_out_pool_asks_whether_anything_is_left():
    _, qs = ask(make_rule(minimum_spend=None, pool_status="capping_out"))
    assert find(qs, "money left") is not None


def test_a_program_under_review_flags_its_whole_benefit():
    benefit, qs = ask(make_rule(minimum_spend=None, pool_status="open", under_review=True))
    q = find(qs, "legislative review")
    assert q is not None and q.worth == pytest.approx(-benefit.net_benefit)


def test_a_non_refundable_credit_asks_the_question_that_decides_its_value():
    """Worth face value with in-state liability, and close to nothing without.

    Which applies is a fact about the production company, not the statute, so
    the tool cannot resolve it — but it can say what turns on it.
    """
    benefit, qs = ask(make_rule(minimum_spend=None, credit_type="non_refundable"))
    q = find(qs, "in-state tax liability")

    assert q is not None
    assert q.worth == pytest.approx(-benefit.realizable_credit)
    assert q.ask == "your production accountant"


def test_an_unstated_payout_mechanism_is_priced_as_the_discount_at_stake():
    _, qs = ask(make_rule(minimum_spend=None, credit_type="unknown"))
    q = find(qs, "refundable, or does it have to be sold")
    assert q is not None
    assert q.is_risk is True


# ---------- restraint ----------


def test_immaterial_unknowns_are_not_raised_at_all():
    """A question worth $40 is noise that devalues the ones worth $200,000."""
    tiny = make_budget(
        atl_cast=100, atl_noncast=0, btl_labor=100, btl_nonlabor=0, post_vfx=0, total=200
    )
    rule = make_rule(
        minimum_spend=None,
        uplifts=[Uplift(condition="a trivial bonus", bonus_rate=0.01, machine_checkable=False)],
    )
    _, qs = ask(rule, budget=tiny)
    assert all(abs(q.worth) >= MATERIALITY for q in qs)


def test_a_machine_checkable_uplift_is_never_asked_about():
    # The calculator already decided it; asking would imply doubt it doesn't have.
    rule = make_rule(
        minimum_spend=None,
        uplifts=[Uplift(condition="local hire > 50%", bonus_rate=0.05, machine_checkable=True)],
    )
    _, qs = ask(rule)
    assert find(qs, "local hire") is None


def test_a_jurisdiction_that_cannot_be_ranked_produces_no_questions():
    # Texas is discretionary. There is no number to protect or improve, and
    # listing questions would imply it's a live option.
    _, qs = ask(TEXAS)
    assert qs == []


def test_every_question_says_who_answers_it():
    for rule in (GEORGIA, NEW_MEXICO):
        _, qs = ask(rule)
        assert qs, rule.jurisdiction
        for q in qs:
            assert q.ask, q.question
            assert q.basis, q.question
