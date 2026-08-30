"""Data models shared by all three layers — copied verbatim from BUILD_BRIEF.md section 5.

Layer 1 (Gemini) only ever populates JurisdictionRule. Layer 2 (calculator.py)
only ever reads these and returns BenefitBreakdown. Nothing here does I/O.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

Confidence = Literal["primary_source", "official_secondary", "conflicting", "stale", "unverified"]
PoolStatus = Literal["open", "capping_out", "closed", "unknown"]


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
    constraints: list[str] = field(default_factory=list)  # "coastline", "large_soundstage", "spring_only"


@dataclass
class RelocationAssumptions:
    flight_threshold_km: float = 800.0
    flight_cost_per_person: float = 600.0
    ground_cost_per_person_per_km: float = 0.35
    per_diem_per_person_per_day: float = 85.0
    hotel_per_person_per_day: float = 140.0
    equipment_shipping_base: float = 15000.0
    imported_crew_pct: float = 0.4   # fraction of headcount that travels


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
    net_benefit: float
    computable: bool
    non_computable_reason: Optional[str]
