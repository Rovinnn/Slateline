/**
 * Mirrors backend/app/models.py exactly. If a field changes on one side,
 * change it here too — this is the API contract, not just UI convenience.
 */

export type Confidence = "primary_source" | "official_secondary" | "conflicting" | "stale" | "unverified";
export type PoolStatus = "open" | "capping_out" | "closed" | "unknown";
/** How a jurisdiction pays out — decides what the credit is worth in cash. */
export type CreditType = "refundable" | "transferable" | "rebate" | "non_refundable" | "unknown";

export interface SourceRef {
  url: string;
  retrieved: string; // ISO date
  published: string | null; // ISO date
  excerpt: string;
  is_primary: boolean;
}

export interface Tier {
  threshold: number;
  rate: number;
}

export interface Uplift {
  condition: string;
  bonus_rate: number;
  machine_checkable: boolean;
}

/** Keys of JurisdictionRule.qualifying — see backend/app/calculator.py QUALIFYING_KEYS. */
export interface QualifyingMap {
  atl_cast: boolean;
  atl_noncast: boolean;
  btl_labor_resident: boolean;
  btl_labor_nonresident: boolean;
  btl_nonlabor: boolean;
  post_vfx: boolean;
}

export interface JurisdictionRule {
  jurisdiction: string;
  program_name: string;
  base_rate: number;
  qualifying: QualifyingMap;
  per_person_wage_cap: number | null;
  minimum_spend: number | null;
  per_project_cap: number | null;
  tiers: Tier[];
  uplifts: Uplift[];
  annual_pool_total: number | null;
  annual_pool_remaining: number | null;
  pool_status: PoolStatus;
  application_deadline: string | null; // ISO date
  sunset_date: string | null; // ISO date
  under_review: boolean;
  is_discretionary: boolean;
  film_office_contact: string | null;
  centroid_lat: number;
  centroid_lng: number;
  sources: SourceRef[];
  confidence: Confidence;
  conflicts: string[];
  /** Keys matching BudgetVector.constraints; value is why this jurisdiction fails that constraint. */
  constraint_gaps: Record<string, string>;
  credit_type: CreditType;
  /** Whether employer-side payroll burden counts as qualified spend. Null = sources didn't say. */
  fringes_qualify: boolean | null;
}

export interface BudgetVector {
  total: number;
  atl_cast: number;
  atl_noncast: number;
  btl_labor: number;
  btl_nonlabor: number;
  post_vfx: number;
  shoot_days: number;
  crew_headcount: number;
  resident_labor_pct: number; // 0.0-1.0
  home_base: string;
  constraints: string[];
  /** Employer payroll burden as a fraction of wages; 0.28 is a typical union feature. */
  fringe_rate: number;
}

export interface RelocationAssumptions {
  flight_threshold_km: number;
  flight_cost_per_person: number;
  ground_cost_per_person_per_km: number;
  per_diem_per_person_per_day: number;
  hotel_per_person_per_day: number;
  equipment_shipping_base: number;
  imported_crew_pct: number;
}

export const DEFAULT_RELOCATION_ASSUMPTIONS: RelocationAssumptions = {
  flight_threshold_km: 800,
  flight_cost_per_person: 600,
  ground_cost_per_person_per_km: 0.35,
  per_diem_per_person_per_day: 85,
  hotel_per_person_per_day: 140,
  equipment_shipping_base: 15000,
  imported_crew_pct: 0.4,
};

export interface BenefitBreakdown {
  jurisdiction: string;
  qualifying_spend: number;
  gross_credit: number;
  caps_applied: string[];
  distance_km: number | null;
  travel_time_hours: number | null;
  relocation_cost: number;
  relocation_components: Record<string, number>;
  /** What the credit is worth in cash after monetisation — face value for a
   *  refundable credit, discounted for a transferable one. */
  realizable_credit: number;
  monetization_note: string | null;
  net_benefit: number;
  computable: boolean;
  non_computable_reason: string | null;
}

/** Result of parsing an uploaded budget PDF — see backend/app/extraction/budget_parser.py. */
export interface ParsedBudget {
  budget: BudgetVector;
  /** Field name -> where in the document that figure came from. */
  field_notes: Record<string, string>;
  /** Figures not found, ambiguous lines, anything the producer should check. */
  warnings: string[];
}
