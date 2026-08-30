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
    assert len(result.caps_applied) == 1
    assert "Georgia Entertainment Promotion" in result.caps_applied[0]
    # No distance yet (Maps not wired) -> relocation is lodging + equipment only.
    assert result.relocation_cost == pytest.approx(104_100)
    assert result.net_benefit == pytest.approx(295_900)


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
