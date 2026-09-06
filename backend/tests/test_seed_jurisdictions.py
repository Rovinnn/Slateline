"""Golden-file tests (BUILD_BRIEF.md section 9) against the hand-curated real
jurisdictions in app/seed_jurisdictions.py. Expected values below were
computed by running the real /compute endpoint against these rules on
2026-08-30 and hand-checked against the arithmetic in that response — see
git log for that session. If a seed jurisdiction's sourced figures change,
update both the fixture and these numbers together, not just one.
"""

import pytest

from app.calculator import compute_benefit
from app.models import BudgetVector
from app.seed_jurisdictions import GEORGIA, LOUISIANA, NEW_MEXICO, TEXAS
from app.verification import verify_rule

INDIE_DRAMA_BUDGET = BudgetVector(
    total=2_000_000,
    atl_cast=250_000,
    atl_noncast=200_000,
    btl_labor=750_000,
    btl_nonlabor=550_000,
    post_vfx=250_000,
    shoot_days=22,
    crew_headcount=45,
    resident_labor_pct=0.55,
    home_base="Los Angeles, CA",
    constraints=[],
)


def test_georgia_confidence_is_primary_source():
    # Has a real statute-text source (law.justia.com) plus an official secondary one.
    assert verify_rule(GEORGIA).confidence == "primary_source"


def test_new_mexico_and_louisiana_confidence_is_official_secondary():
    # Best sources found were official government pages, not statute text itself.
    assert verify_rule(NEW_MEXICO).confidence == "official_secondary"
    assert verify_rule(LOUISIANA).confidence == "official_secondary"


def test_texas_is_discretionary_despite_a_primary_source():
    # Well-sourced (gov.texas.gov is the program's own official page) but still
    # not computable — confidence and computability are independent axes.
    verified = verify_rule(TEXAS)
    assert verified.confidence == "primary_source"
    assert verified.is_discretionary is True


def test_georgia_indie_drama_golden_value():
    result = compute_benefit(INDIE_DRAMA_BUDGET, GEORGIA, distance_km=None)
    # 20% base rate on the full $2.0M (no category exclusions found in sourcing) —
    # the 10% GEP logo uplift is not machine-checkable, so it's logged, not applied.
    assert result.qualifying_spend == pytest.approx(2_000_000)
    assert result.gross_credit == pytest.approx(400_000)
    assert any("Georgia Entertainment Promotion" in note for note in result.caps_applied)
    # Georgia's sources don't state whether fringes qualify, so they're left
    # out — and said so, rather than silently understating the credit.
    assert any("payroll burden left out" in note for note in result.caps_applied)
    # Georgia's credit is transferable — the state pays nothing, you sell the
    # credit to a Georgia taxpayer at a broker discount. $400k of face value is
    # worth $360k in cash at the default 90%, and netting the face value (as
    # this test asserted before credit_type existed) overstated Georgia by
    # $40k and flattered it against refundable states like New Mexico.
    assert result.realizable_credit == pytest.approx(360_000)
    assert "transferable" in (result.monetization_note or "")
    # No distance passed here -> relocation is lodging + equipment only.
    assert result.relocation_cost == pytest.approx(104_100)
    # And $360k of Georgia credit is not $360k of money today. A transferable
    # credit has to be sold, which happens after wrap and after the return is
    # filed — 18 months by default, discounted at 12%/yr:
    #   360,000 / 1.12^(18/12) = 303,721.
    # Relocation, meanwhile, is spent up front in today's dollars, so netting
    # the two undiscounted (as this asserted before timing existed) overstated
    # Georgia by a further $56k on top of the $40k the transfer discount
    # already cost it. Two corrections, same direction, same root cause:
    # treating a claim on future money as if it were cash on wrap day.
    assert result.months_to_payment == 18
    assert result.timing_is_assumed is True
    assert result.present_value == pytest.approx(303_721.45, abs=0.01)
    assert result.net_benefit == pytest.approx(199_621.45, abs=0.01)


def test_texas_indie_drama_is_not_computable():
    result = compute_benefit(INDIE_DRAMA_BUDGET, TEXAS, distance_km=None)
    assert result.computable is False
    assert result.gross_credit == 0
    assert result.net_benefit == 0


def test_new_mexico_indie_drama_no_minimum_spend_cliff():
    # New Mexico has no minimum spend — even a $1 qualifying budget should still
    # produce a (tiny) credit rather than hitting a cliff that doesn't exist here.
    tiny_budget = BudgetVector(
        total=1, atl_cast=1, atl_noncast=0, btl_labor=0, btl_nonlabor=0, post_vfx=0,
        shoot_days=1, crew_headcount=1, resident_labor_pct=0.0, home_base="Los Angeles, CA", constraints=[],
    )
    result = compute_benefit(tiny_budget, NEW_MEXICO, distance_km=None)
    assert result.gross_credit == pytest.approx(0.25)


# ---------- hand-verified against the statutes, 2026-09-06 ----------
#
# Everything above this line was a regression test: the expected values were
# produced by running our own code and recording its output. These were
# checked field by field against the statute and the state's own regulation,
# and two of them changed the answer.


def test_new_mexico_indie_drama_golden_value():
    """The golden test whose absence let a real error through.

    New Mexico was the top recommendation and had no value assertion at all —
    only a no-minimum-spend edge case. So when its qualifying rules turned out
    to be wrong, all 235 tests still passed and the ranking silently changed.
    A winner with no golden value is the worst thing to leave untested.
    """
    result = compute_benefit(INDIE_DRAMA_BUDGET, NEW_MEXICO, distance_km=None)

    # $2M budget less the $337,500 of non-resident BTL wages that don't
    # qualify at the base rate (see below).
    assert result.qualifying_spend == pytest.approx(1_662_500)
    assert result.gross_credit == pytest.approx(415_625)
    # Refundable, so no broker discount — the whole face value is realizable.
    assert result.realizable_credit == pytest.approx(415_625)
    assert result.months_to_payment == 12
    assert result.net_benefit == pytest.approx(266_993.75, abs=0.01)


def test_new_mexico_excludes_nonresident_below_the_line_crew():
    """NMSA 7-2F-15 makes these a separate, much narrower credit.

    Non-resident BTL crew get 15% rather than the base 25%, on at most 15% of
    the BTL budget, across a capped number of positions. Treating them as
    ordinary qualifying spend overstated New Mexico by $67,500 on this budget
    and put it top of the ranking; excluding them understates by $16,875.
    """
    assert NEW_MEXICO.qualifying["btl_labor_nonresident"] is False
    assert NEW_MEXICO.qualifying["btl_labor_resident"] is True
    # Non-payroll spend and post are unaffected by the residency rule.
    assert NEW_MEXICO.qualifying["btl_nonlabor"] is True
    assert NEW_MEXICO.qualifying["post_vfx"] is True


def test_georgia_qualifies_nonresident_crew_where_new_mexico_does_not():
    """Two states, opposite answers, and the difference decides the ranking.

    Georgia's exclusion is territorial — "work or services not conducted or
    rendered in Georgia" (Rule 560-7-8-.45(6)(c)1.(ii)) — so a non-resident
    gaffer working in Atlanta qualifies. New Mexico's test is residency. This
    contrast is the reason a per-jurisdiction qualifying map exists at all,
    and it's worth asserting so neither side drifts to match the other.
    """
    assert GEORGIA.qualifying["btl_labor_nonresident"] is True
    assert NEW_MEXICO.qualifying["btl_labor_nonresident"] is False


def test_georgia_caps_qualifying_salary_at_500k_per_person():
    """O.C.G.A. § 48-7-40.26's "total aggregate payroll" definition.

    Doesn't bite on a $2M indie drama, which is exactly why it went unnoticed:
    the cap was None and every seeded test budget was too small to reveal it.
    """
    assert GEORGIA.per_person_wage_cap == 500_000

    # A budget where it does bite: cast_count is assumed at 4 for a small
    # crew, so the ceiling is 4 x $500k = $2M against $3M of cast salary.
    star_vehicle = BudgetVector(
        total=6_000_000, atl_cast=3_000_000, atl_noncast=500_000, btl_labor=1_500_000,
        btl_nonlabor=750_000, post_vfx=250_000, shoot_days=30, crew_headcount=50,
        resident_labor_pct=0.6, home_base="Los Angeles, CA", constraints=[],
    )
    capped = compute_benefit(star_vehicle, GEORGIA, distance_km=None)
    assert any("wage cap" in note.lower() for note in capped.caps_applied)
    assert capped.qualifying_spend < 6_000_000
