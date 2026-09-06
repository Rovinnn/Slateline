"""Data models shared by all three layers — copied verbatim from BUILD_BRIEF.md section 5.

Layer 1 (Gemini) only ever populates JurisdictionRule. Layer 2 (calculator.py)
only ever reads these and returns BenefitBreakdown. Nothing here does I/O.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

Confidence = Literal["primary_source", "official_secondary", "conflicting", "stale", "unverified"]
PoolStatus = Literal["open", "capping_out", "closed", "unknown"]

# How a jurisdiction actually pays out, which decides what a credit is worth in
# cash. A refundable credit is paid at face value; a transferable one has to be
# sold to a taxpayer with liability, at a broker discount; a non-refundable one
# is worth nothing unless the production has in-state tax liability to offset,
# which an out-of-state production usually doesn't. Treating all three as face
# value — as this did until now — systematically flatters transferable states.
CreditType = Literal["refundable", "transferable", "rebate", "non_refundable", "unknown"]


@dataclass
class SourceRef:
    url: str
    retrieved: date
    published: Optional[date]
    excerpt: str          # short supporting quote, for the footnote
    is_primary: bool      # statute/regulation vs commentary


@dataclass
class Tier:
    threshold: float      # spend level at which this rate begins
    rate: float


@dataclass
class Uplift:
    condition: str        # "shot outside metro area", "local hire > 50%"
    bonus_rate: float
    machine_checkable: bool   # can we evaluate this from the budget object?


@dataclass
class JurisdictionRule:
    jurisdiction: str
    program_name: str
    base_rate: float
    qualifying: dict          # see calculator.py QUALIFYING_KEYS for the exact key set
    per_person_wage_cap: Optional[float]
    minimum_spend: Optional[float]
    per_project_cap: Optional[float]
    tiers: list[Tier]
    uplifts: list[Uplift]
    annual_pool_total: Optional[float]
    annual_pool_remaining: Optional[float]
    pool_status: PoolStatus
    application_deadline: Optional[date]
    sunset_date: Optional[date]
    under_review: bool
    is_discretionary: bool    # jury/committee allocated -> non-modelable
    film_office_contact: Optional[str]
    centroid_lat: float
    centroid_lng: float
    sources: list[SourceRef]
    confidence: Confidence
    conflicts: list[str]      # human-readable notes on disagreeing sources
    # Keys matching BudgetVector.constraints; value is why THIS jurisdiction
    # fails that constraint. Absent key = satisfies it, or unknown — never a
    # guess. Filled by constraints.constraint_gaps_for(), not by Layer 1: see
    # that module's docstring for why this isn't extracted like base_rate is.
    constraint_gaps: dict[str, str] = field(default_factory=dict)
    # How the credit actually pays out — decides what it's worth in cash.
    credit_type: CreditType = "unknown"
    # Payroll burden (employer taxes, union pension/health, workers' comp) runs
    # 22-35% on top of wages and is a real part of what a production spends.
    # Whether it counts as qualified spend varies by statute — California
    # excludes federal fringes, Kentucky allows them — so it can't be assumed
    # either way. None means the sources didn't say.
    fringes_qualify: Optional[bool] = None
    # ISO 4217 code the figures above are denominated in. The brief forbids
    # FX conversion, so this isn't used to convert anything — calculator.py
    # uses it only to refuse to compute a non-USD rule as if it were USD
    # (see its currency guard). Defaults to USD for the seed/fixture data
    # that predates this field; real extractions always state it explicitly.
    currency: str = "USD"
    # Months from wrap until the production actually has the money. Statutes
    # rarely state this — it's administrative practice — so it stays None
    # unless a source says otherwise, and CreditTimingAssumptions supplies a
    # per-credit-type default. Extracting a number nobody published would be
    # inventing the most consequential input to present value.
    months_to_payment: Optional[int] = None
    # Whether a CPA audit stands between wrap and payment. Georgia's is
    # mandatory and both delays and costs money; several states have none.
    audit_required: Optional[bool] = None


@dataclass
class BudgetVector:
    total: float
    atl_cast: float
    atl_noncast: float
    btl_labor: float
    btl_nonlabor: float
    post_vfx: float
    shoot_days: int
    crew_headcount: int
    resident_labor_pct: float      # 0.0-1.0, user estimate
    home_base: str                 # city, for relocation distance
    # Employer-side payroll burden as a fraction of gross wages. 0.28 is a
    # typical blended union feature rate; non-union sits lower. Applied only to
    # labor lines, never to rentals or materials.
    fringe_rate: float = 0.28
    constraints: list[str] = field(default_factory=list)  # "coastline", "large_soundstage", "spring_only"


@dataclass
class RelocationAssumptions:
    flight_threshold_km: float = 800.0
    # Base airfare, before distance. Was a *flat* 600 until real Maps
    # distances went through the model and every jurisdiction beyond the
    # threshold priced identically: Albuquerque at 1,266 km cost exactly what
    # Atlanta cost at 3,498 km. That made the routed distance we look up
    # decorative — it appeared on the map and changed no number.
    flight_cost_per_person: float = 250.0
    # The distance component. Airfare doesn't scale linearly with distance,
    # but it isn't flat either, and base + per-km lands close to real US
    # domestic round trips across the range that matters here (~$377 LA to
    # Albuquerque, ~$600 LA to Atlanta).
    flight_cost_per_person_per_km: float = 0.10
    ground_cost_per_person_per_km: float = 0.35
    per_diem_per_person_per_day: float = 85.0
    hotel_per_person_per_day: float = 140.0
    equipment_shipping_base: float = 15000.0
    imported_crew_pct: float = 0.4   # fraction of headcount that travels


@dataclass
class CreditTimingAssumptions:
    """When the credit turns into money, and what waiting for it costs.

    A credit is not cash: it's a claim realised after wrap, after an audit,
    sometimes two years out. A refundable credit paid at face in 9 months and
    a transferable one sold at 88c in 20 months are different instruments with
    identical headline rates, and the gap between them can exceed the gap
    between two jurisdictions' rates — so timing can reorder the ranking.

    These are assumptions, not extracted facts, and they live here for the
    same reason RelocationAssumptions does: BUILD_BRIEF.md section 6 requires
    every assumption to be visible and editable rather than buried in a
    constant. JurisdictionRule.months_to_payment overrides the default below
    whenever a source actually states a timeline.
    """

    # Opportunity cost of capital tied up waiting. Productions frequently
    # borrow against credits rather than wait, and this doubles as a proxy for
    # that interim financing rate.
    discount_rate_annual: float = 0.12
    # Typical waits by payout mechanism. Refundable and rebate programs pay on
    # a filed return or claim; transferable credits add finding a buyer.
    months_refundable: int = 12
    months_rebate: int = 9
    months_transferable: int = 18
    months_non_refundable: int = 12
    months_unknown: int = 15
    # A mandatory audit is a real, quotable line item, not a rounding error on
    # an indie budget.
    audit_cost: float = 15000.0


@dataclass
class CurrencyAssumptions:
    """Exchange rates, treated as an assumption rather than a fact.

    The tool refused non-USD jurisdictions entirely until now, on the correct
    grounds that comparing euros against dollars with no unit anywhere would
    be a confidently wrong number. But refusing is only the right answer while
    there is no honest way to convert, and there is one: state the rate, date
    it, put it on screen, and let the producer change it.

    That is the same treatment relocation and payment timing already get. The
    figures below are *defaults to be checked*, not live rates — this tool has
    no FX feed and does not pretend to. A production committing millions on a
    cross-border shoot will have a treasury rate of its own, and the panel
    exists so they can enter it.

    A currency with no rate here is still refused, with a message saying so.
    That keeps the original guarantee intact: nothing is ever compared across
    currencies without a stated, visible conversion.
    """

    #: Units of USD per 1 unit of the foreign currency.
    rates_to_usd: dict[str, float] = field(
        default_factory=lambda: {
            "USD": 1.0,
            # Americas
            "CAD": 0.74, "MXN": 0.058, "BRL": 0.18, "CLP": 0.0011, "COP": 0.00025,
            "UYU": 0.025, "ARS": 0.0010, "PEN": 0.27, "DOP": 0.017, "PAB": 1.0,
            "TTD": 0.15, "JMD": 0.0064,
            # Europe
            "EUR": 1.08, "GBP": 1.27, "CHF": 1.13, "DKK": 0.145, "SEK": 0.096,
            "NOK": 0.094, "ISK": 0.0073, "PLN": 0.25, "CZK": 0.043, "HUF": 0.0028,
            "RON": 0.217, "BGN": 0.552, "RSD": 0.0092, "MKD": 0.0175, "ALL": 0.0108,
            "TRY": 0.029, "UAH": 0.024, "GEL": 0.37,
            # Asia-Pacific
            "AUD": 0.66, "NZD": 0.61, "FJD": 0.44, "JPY": 0.0067, "KRW": 0.00075,
            "TWD": 0.031, "THB": 0.029, "MYR": 0.225, "SGD": 0.74, "PHP": 0.0175,
            "IDR": 0.000062, "INR": 0.012, "MNT": 0.00029, "LKR": 0.0034,
            # Africa & Middle East
            "ZAR": 0.055, "MAD": 0.10, "EGP": 0.021, "JOD": 1.41, "AED": 0.272,
            "SAR": 0.267, "ILS": 0.27, "QAR": 0.275, "KES": 0.0077, "NGN": 0.00065,
            "RWF": 0.00077, "GHS": 0.065, "TND": 0.32, "MUR": 0.022,
        }
    )
    #: When these were last reviewed. Shown next to every converted figure so
    #: a stale rate is visible rather than implied.
    as_of: str = "2026-09-06"


@dataclass
class BenefitBreakdown:
    jurisdiction: str
    qualifying_spend: float
    gross_credit: float
    caps_applied: list[str]        # human-readable: "per-person wage cap reduced qualifying ATL by $2.1M"
    distance_km: Optional[float]
    travel_time_hours: Optional[float]
    relocation_cost: float
    relocation_components: dict    # itemised, for display
    # gross_credit is the credit's face value. realizable_credit is what it's
    # worth in cash after monetisation — identical for a refundable credit,
    # discounted for a transferable one. net_benefit nets the realizable
    # figure, because that's the money the production actually sees.
    realizable_credit: float
    monetization_note: Optional[str]
    net_benefit: float
    computable: bool
    non_computable_reason: Optional[str]
    # Cost of proving the spend to an auditor, where one is required.
    audit_cost: float = 0.0
    # Months actually used for discounting, and whether that came from a
    # source or from CreditTimingAssumptions — the UI has to be able to say
    # which, because one is a fact and the other is our guess.
    months_to_payment: int = 0
    timing_is_assumed: bool = True
    # present_value <= realizable_credit - audit_cost. The difference is what
    # waiting costs, reported separately so it can be shown as its own stage.
    present_value: float = 0.0
    timing_note: Optional[str] = None
