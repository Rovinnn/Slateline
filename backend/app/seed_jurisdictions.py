"""Hand-curated real jurisdictions, sourced from live Parallel Search calls
made 2026-08-30 (see git log for that session) and manually structured into
JurisdictionRule — i.e. a human doing exactly what Layer 1 (extraction.agent)
will do automatically once Vertex AI auth is set up (see README.md). This is
NOT fabricated data: every rate, cap and uplift below is quoted from a real
source fetched that day, with the real URL and excerpt kept in `sources`.

It exists to unblock building and testing the results screen against real
compute_benefit output while Gemini/Vertex auth is pending. Delete this file
once extraction.agent.extract_jurisdiction_rule is live for these
jurisdictions (or keep it as a golden-file fixture for regression tests —
brief section 9 wants hand-verified golden files anyway).

Known gaps, deliberately left None rather than guessed:
- No source in this pass gave a live annual_pool_remaining figure (only
  annual_pool_total / program-wide caps), so pool_status is "unknown" except
  Georgia, which is explicitly uncapped.
- application_deadline, sunset_date, film_office_contact: not found in the
  sources fetched.
"""

from datetime import date

from .models import JurisdictionRule, SourceRef, Tier, Uplift

_RETRIEVED = date(2026, 8, 30)
_ALL_QUALIFYING = {
    "atl_cast": True,
    "atl_noncast": True,
    "btl_labor_resident": True,
    "btl_labor_nonresident": True,
    "btl_nonlabor": True,
    "post_vfx": True,
}

GEORGIA = JurisdictionRule(
    jurisdiction="Georgia",
    program_name="Georgia Entertainment Industry Investment Act",
    base_rate=0.20,
    # Non-resident crew DO qualify here, unlike New Mexico below: the
    # regulation's exclusion is "any expenditure for work or services not
    # conducted or rendered in Georgia" (560-7-8-.45(6)(c)1.(ii)) — a test of
    # where the work happened, not of where the worker lives.
    qualifying=dict(_ALL_QUALIFYING),
    # O.C.G.A. § 48-7-40.26, definition of "total aggregate payroll": "with
    # respect to a single employee, the portion of any salary which exceeds
    # $500,000.00 for a single production shall not be included when
    # calculating total aggregate payroll, and all payments to a single
    # employee and any legal entity in which the employee has any direct or
    # indirect ownership interest shall be considered as having been paid to
    # the employee and shall be aggregated regardless of the means of payment
    # or distribution."
    #
    # Found by hand-verification on 2026-09-06; it had been None since this
    # file was written, which silently overstated Georgia for any production
    # paying an individual more than $500k. The aggregation clause is the
    # part worth reading twice — routing a star's fee through a loan-out does
    # not escape the cap.
    per_person_wage_cap=500_000,
    minimum_spend=500_000,
    per_project_cap=None,
    tiers=[],
    uplifts=[
        Uplift(
            condition="production includes an approved Georgia promotional logo in end credits (Georgia Entertainment Promotion uplift)",
            bonus_rate=0.10,
            machine_checkable=False,
        ),
    ],
    annual_pool_total=None,
    annual_pool_remaining=None,
    pool_status="open",  # source: "no annual cap... no sunset clause on the program"
    application_deadline=None,
    sunset_date=None,
    under_review=False,
    is_discretionary=False,
    # "a 20% based transferable tax credit" — quoted in the georgia.org source
    # below. Georgia doesn't pay cash; the credit is sold to a GA taxpayer.
    credit_type="transferable",
    film_office_contact=None,
    centroid_lat=33.749,
    centroid_lng=-84.388,  # Atlanta hub
    sources=[
        SourceRef(
            url="https://law.justia.com/codes/georgia/title-48/chapter-7/article-2/section-48-7-40-26/",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "the tax credit under this subsection shall be allowed if the base investment in this "
                "state equals or exceeds $500,000.00... The production company... shall be allowed a tax "
                "credit equal to 20 percent of the base investment in this state"
            ),
            is_primary=True,
        ),
        SourceRef(
            url="https://www.georgia.org/industries/film-entertainment/georgia-film-tv-production/production-incentives",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "The Film Tax Credit is a 20% based transferable tax credit, with an additional 10% uplift "
                "for providing promotional value to the state... there is no limit on the amount of tax "
                "credits that can be earned in a given year, and there is no sunset clause on the program."
            ),
            is_primary=False,
        ),
    ],
    confidence="unverified",  # recomputed by verify_rule() before serving
    conflicts=[],
)

NEW_MEXICO = JurisdictionRule(
    jurisdiction="New Mexico",
    program_name="New Mexico Film Production Tax Credit",
    base_rate=0.25,
    # NOT _ALL_QUALIFYING, and this is the correction that mattered most.
    #
    # New Mexico's base 25% covers non-payroll spend, resident labour and
    # non-resident performing artists. Non-resident BELOW-THE-LINE crew are a
    # separate, much narrower credit (NMSA 7-2F-15): 15% rather than 25%,
    # claimable on at most 15% of the total BTL budget, across a capped number
    # of positions (5-20 by budget size), and subject to a 2.5% giveback.
    #
    # This field is a boolean, so it can express "qualifies" or "doesn't" and
    # nothing in between. On the $2M indie drama the two errors are not
    # symmetric: treating these wages as fully qualifying overstates the
    # credit by $67,500, while treating them as non-qualifying understates it
    # by $16,875. For a tool whose whole claim is that it would rather show a
    # gap than a confident wrong number, understating by a quarter as much is
    # the only defensible way to round.
    #
    # Modelling the real rule needs per-category rates, which the schema
    # doesn't have. Logged in NEXT_STEPS.md rather than bodged in here.
    qualifying={**_ALL_QUALIFYING, "btl_labor_nonresident": False},
    # The $5,000,000 per-production ceiling on non-resident performing artists
    # is a per-production aggregate, not the per-person cap this field means,
    # so it stays None rather than being forced into the wrong shape.
    per_person_wage_cap=None,
    minimum_spend=None,  # source: "no minimum spend requirement"
    per_project_cap=None,
    tiers=[],
    uplifts=[
        Uplift(condition="production shot 60+ miles from Albuquerque or Santa Fe (rural)", bonus_rate=0.10, machine_checkable=False),
        Uplift(condition="TV pilot or television series", bonus_rate=0.05, machine_checkable=False),
        Uplift(condition="production uses a qualified production facility", bonus_rate=0.05, machine_checkable=False),
    ],
    # FY27 (began 1 July 2026, so this is the year in force as of Sept 2026);
    # the $140M figure this file previously carried was the FY26 cap, correct
    # when it was written and stale now. Scheduled to rise to $160M in FY28.
    annual_pool_total=150_000_000,
    annual_pool_remaining=None,
    pool_status="unknown",  # total cap found, live remaining balance was not
    application_deadline=None,
    sunset_date=None,
    under_review=False,
    is_discretionary=False,
    # "Program Type: Refundable Tax Credit" — the state pays face value, so
    # there's no broker discount, which is why NM can beat a higher headline
    # rate elsewhere.
    credit_type="refundable",
    film_office_contact=None,
    centroid_lat=35.084,
    centroid_lng=-106.651,  # Albuquerque hub
    sources=[
        SourceRef(
            url="https://www.tax.newmexico.gov/tax-professionals/tax-credits-overview-forms/film-production-tax-credit",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "New Mexico offers a film production tax credit for film production companies that have "
                "direct production and direct post-production expenditures... The Allowable Fiscal Year "
                "2026 Film Fund Cap is $140,000,000.00."
            ),
            is_primary=False,
        ),
        SourceRef(
            url="https://www.shamelstudio.com/tools/film-tax-incentives/new-mexico",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "New Mexico's base rate is 25% on qualified production spend, with stackable uplifts of "
                "10% for rural filming (60+ miles from Albuquerque or Santa Fe), 5% for TV pilots and "
                "series, and 5% for qualified-facility usage... no minimum spend requirement"
            ),
            is_primary=False,
        ),
    ],
    confidence="unverified",
    conflicts=[],
)

LOUISIANA = JurisdictionRule(
    jurisdiction="Louisiana",
    program_name="Louisiana Motion Picture Production Tax Credit",
    base_rate=0.25,
    qualifying=dict(_ALL_QUALIFYING),
    per_person_wage_cap=None,  # source: per-person wage limit was removed
    minimum_spend=None,
    per_project_cap=None,  # source: per-project cap was removed
    tiers=[],
    uplifts=[
        Uplift(
            condition="screenplay written by a Louisiana resident, production budget $50,000-$5,000,000",
            bonus_rate=0.10,
            machine_checkable=False,
        ),
        Uplift(
            condition="production office base and 60%+ of principal photography outside the New Orleans metro area",
            bonus_rate=0.05,
            machine_checkable=False,
        ),
    ],
    annual_pool_total=125_000_000,  # reduced from $150M effective 2025-07-01
    annual_pool_remaining=None,
    pool_status="unknown",
    application_deadline=None,
    sunset_date=None,
    under_review=False,
    is_discretionary=False,
    # Was "unknown" until hand-verification on 2026-09-06, on the grounds that
    # the retrieved excerpt only established credits "may be used to offset
    # personal or corporate income tax liability in Louisiana". That refusal
    # to guess was right at the time, but it left the field unresolved on what
    # is now the top-ranked jurisdiction, and "unknown" is scored at face
    # value — so the caution flattered Louisiana rather than penalising it.
    #
    # Louisiana Entertainment states credits may be transferred back to the
    # State for 90% of face value, less a 2% transfer fee (88% net). That is a
    # transfer at a discount, which is what this enum means, even though the
    # counterparty is the state rather than a broker. The default 90% discount
    # is very close to the real 88%; the residual 2% is not worth a per-rule
    # override the schema doesn't have.
    credit_type="transferable",
    film_office_contact=None,
    centroid_lat=29.951,
    centroid_lng=-90.072,  # New Orleans hub
    sources=[
        SourceRef(
            url="https://www.louisianaentertainment.gov/film/motion-picture-production-program",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "Louisiana's Motion Picture Production Program... provides motion picture productions up "
                "to a 40% tax credit on total qualified in-state production expenditures, including "
                "resident and non-resident... 25% base credit on qualified in-state production expenditures"
            ),
            is_primary=False,
        ),
        SourceRef(
            url="https://www.thegreenshot.io/uncategorized/louisiana-film-tax-credit",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "A major change removes spending caps on projects, companies, and individuals. The program "
                "keeps its annual funding cap at $125 million."
            ),
            is_primary=False,
        ),
    ],
    confidence="unverified",
    conflicts=[],
)

TEXAS = JurisdictionRule(
    jurisdiction="Texas",
    program_name="Texas Moving Image Industry Incentive Program (TMIIIP)",
    base_rate=0.05,  # lowest published tier; unused by compute_benefit since is_discretionary short-circuits
    qualifying=dict(_ALL_QUALIFYING),
    per_person_wage_cap=1_000_000,
    minimum_spend=250_000,
    per_project_cap=None,
    tiers=[
        Tier(threshold=250_000, rate=0.05),
        Tier(threshold=1_000_000, rate=0.10),
        Tier(threshold=1_500_000, rate=0.25),
    ],
    uplifts=[
        Uplift(condition="Texas Film Commission discretionary additional grant award (published range 1-2.5%)", bonus_rate=0.025, machine_checkable=False),
    ],
    annual_pool_total=300_000_000,  # per biennium, not annual — see note below
    annual_pool_remaining=None,
    pool_status="unknown",
    application_deadline=None,
    sunset_date=None,
    under_review=False,
    is_discretionary=True,
    # JurisdictionRule has no free-text "why non-computable" field of its own —
    # compute_benefit() supplies a generic reason when is_discretionary is True.
    # The jurisdiction-specific detail (TMIIIP is a competitive grant requiring
    # a Texas Film Commission application and an eligibility review — >=35%
    # Texas-resident cast/crew, >=60% of principal photography in Texas — that
    # can't be checked from BudgetVector, and its $300M allocation is biennial,
    # not annual, despite the annual_pool_total field name) lives in `conflicts`
    # below instead.
    # "receive a cash grant based on a percentage of a project's eligible Texas
    # expenditures" — a grant, paid in cash, hence rebate rather than a credit.
    credit_type="rebate",
    film_office_contact=None,
    centroid_lat=30.267,
    centroid_lng=-97.743,  # Austin hub
    sources=[
        SourceRef(
            url="https://gov.texas.gov/film/page/tmiiip",
            retrieved=_RETRIEVED,
            published=None,
            excerpt=(
                "TMIIIP provides qualifying film... productions the opportunity to receive a cash grant "
                "based on a percentage of a project's eligible Texas expenditures... Base Incentive Rate "
                "5% - 25%... Additional Grant Awards 1 - 2.5%... Per Project Cap: None"
            ),
            is_primary=True,
        ),
        SourceRef(
            url="https://www.houstonpublicmedia.org/articles/arts-culture/2026/04/15/549128/austin-texas-film-movies-industry-incentives/",
            retrieved=_RETRIEVED,
            published=date(2026, 4, 15),
            excerpt=(
                "The program will allocate $300 million to these productions every two years. For "
                "qualifying film projects, 35% of paid crew and cast members must be Texas residents, and "
                "60% of production must be completed in Texas."
            ),
            is_primary=False,
        ),
    ],
    confidence="unverified",
    # Not a source disagreement (both sources agree), so this deliberately isn't in
    # `conflicts` — that field drives assess_confidence()'s "conflicting" state, which
    # would misreport this as disputed data. It's is_discretionary=True instead; see
    # the comment above for why. compute_benefit()'s non_computable_reason on the
    # result stays a generic string either way — JurisdictionRule has no per-program
    # free-text field for this, and adding one is a schema change, not a seed-data fix.
    conflicts=[],
)

SEED_JURISDICTIONS: list[JurisdictionRule] = [GEORGIA, NEW_MEXICO, LOUISIANA, TEXAS]
