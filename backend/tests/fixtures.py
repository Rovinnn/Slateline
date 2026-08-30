"""Hand-written fixtures for calculator tests.

These are SYNTHETIC placeholder figures for exercising compute_benefit's
logic (cliffs, caps, tiers, uplifts) — not verified against any real
statute. Build order step 3 ("verify a few by hand against the actual
statutes") should add real, hand-checked jurisdictions alongside these once
Layer 1 extraction is live; don't cite these numbers as real incentive rates.
"""

from datetime import date

from app.models import BudgetVector, JurisdictionRule, RelocationAssumptions, SourceRef, Tier, Uplift

ALL_QUALIFYING = {
    "atl_cast": True,
    "atl_noncast": True,
    "btl_labor_resident": True,
    "btl_labor_nonresident": True,
    "btl_nonlabor": True,
    "post_vfx": True,
}

PRIMARY_SOURCE = SourceRef(
    url="https://example.gov/film-incentive",
    retrieved=date(2026, 8, 1),
    published=date(2026, 1, 1),
    excerpt="Qualifying productions receive a base credit of 25% of qualified spend.",
    is_primary=True,
)


def make_rule(**overrides) -> JurisdictionRule:
    defaults = dict(
        jurisdiction="Testland",
        program_name="Testland Film Incentive",
        base_rate=0.25,
        qualifying=dict(ALL_QUALIFYING),
        per_person_wage_cap=None,
        minimum_spend=500_000,
        per_project_cap=None,
        tiers=[],
        uplifts=[],
        annual_pool_total=None,
        annual_pool_remaining=None,
        pool_status="open",
        application_deadline=None,
        sunset_date=None,
        under_review=False,
        is_discretionary=False,
        film_office_contact=None,
        centroid_lat=0.0,
        centroid_lng=0.0,
        sources=[PRIMARY_SOURCE],
        confidence="primary_source",
        conflicts=[],
    )
    defaults.update(overrides)
    return JurisdictionRule(**defaults)


FLAT_RATE_RULE = make_rule()

WAGE_CAP_RULE = make_rule(jurisdiction="Capland", per_person_wage_cap=100_000)

TIERED_RULE = make_rule(
    jurisdiction="Tierland",
    base_rate=0.20,
    tiers=[Tier(threshold=0, rate=0.20), Tier(threshold=5_000_000, rate=0.25), Tier(threshold=20_000_000, rate=0.30)],
)

UPLIFT_RULE = make_rule(
    jurisdiction="Upland",
    uplifts=[
        Uplift(condition="local hire > 50%", bonus_rate=0.05, machine_checkable=True),
        Uplift(condition="shot outside metro area", bonus_rate=0.03, machine_checkable=False),
    ],
)

CAPPED_RULE = make_rule(jurisdiction="Capitalcity", per_project_cap=1_000_000)

DISCRETIONARY_RULE = make_rule(jurisdiction="Grantstate", is_discretionary=True)


def make_budget(**overrides) -> BudgetVector:
    defaults = dict(
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
    defaults.update(overrides)
    return BudgetVector(**defaults)


DEFAULT_ASSUMPTIONS = RelocationAssumptions()
