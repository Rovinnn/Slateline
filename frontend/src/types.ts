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
  /** ISO 4217 code the figures are stated in. The backend refuses to compute a
   *  non-USD rule rather than converting, so this arrives already reflected in
   *  `non_computable_reason` — declared here because the field is sent. */
  currency: string;
  /** Months from wrap to payment, only when a source states it. Null means the
   *  backend fell back to a CreditTimingAssumptions default. */
  months_to_payment: number | null;
  /** Whether a mandatory audit stands between wrap and payment. Null = unstated. */
  audit_required: boolean | null;
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

/** When the credit becomes money, and what waiting for it costs. Mirrors
 *  backend/app/models.py CreditTimingAssumptions. */
export interface CreditTimingAssumptions {
  discount_rate_annual: number;
  months_refundable: number;
  months_rebate: number;
  months_transferable: number;
  months_non_refundable: number;
  months_unknown: number;
  audit_cost: number;
}

export const DEFAULT_CREDIT_TIMING: CreditTimingAssumptions = {
  discount_rate_annual: 0.12,
  months_refundable: 12,
  months_rebate: 9,
  months_transferable: 18,
  months_non_refundable: 12,
  months_unknown: 15,
  audit_cost: 15000,
};

export interface RelocationAssumptions {
  flight_threshold_km: number;
  /** Base airfare, before distance. */
  flight_cost_per_person: number;
  /** Distance component of airfare. Without it, every jurisdiction past the
   *  flight threshold costs the same to reach and the routed distance we look
   *  up cannot affect the ranking. */
  flight_cost_per_person_per_km: number;
  ground_cost_per_person_per_km: number;
  per_diem_per_person_per_day: number;
  hotel_per_person_per_day: number;
  equipment_shipping_base: number;
  imported_crew_pct: number;
}

export const DEFAULT_RELOCATION_ASSUMPTIONS: RelocationAssumptions = {
  flight_threshold_km: 800,
  flight_cost_per_person: 250,
  flight_cost_per_person_per_km: 0.1,
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
  /** Cost of proving the spend to an auditor, where one is required. */
  audit_cost: number;
  /** Months actually used for discounting, and whether that was a source fact
   *  or our assumption — the UI must be able to say which. */
  months_to_payment: number;
  timing_is_assumed: boolean;
  /** What the credit is worth today. net_benefit nets this, not face value. */
  present_value: number;
  timing_note: string | null;
}

/** Something still unresolved about a jurisdiction, and what it's worth.
 *  Mirrors backend/app/questions.py OpenQuestion. */
export interface OpenQuestion {
  question: string;
  /** Signed dollars: positive is upside if confirmed, negative is at risk. */
  worth: number;
  /** How the figure was derived, so it can be argued with. */
  basis: string;
  /** Who actually answers this. */
  ask: string;
}

/** One way to run the production: single-location, or shoot here and post there.
 *  Mirrors backend/app/split.py SplitPlan. */
export interface SplitPlan {
  shoot_in: string;
  post_in: string;
  shoot_leg: BenefitBreakdown;
  /** Null for a single-location plan — there is no second leg. */
  post_leg: BenefitBreakdown | null;
  net_benefit: number;
  /** Why this plan is worth less than it looks, in the producer's words. */
  warnings: string[];
}

/** Response from POST /compute/split. */
export interface SplitResponse {
  best: SplitPlan;
  best_single: SplitPlan;
  plans: SplitPlan[];
  /** Materialised server-side so the client never re-derives it. */
  splitting_wins: boolean;
  gain_over_single: number;
}

/** One point where a challenge source disagrees with a held figure.
 *  Mirrors backend/app/extraction/challenge.py ChallengeFinding. */
export interface ChallengeFinding {
  field_name: string;
  current_value: string;
  source_says: string;
  url: string;
  excerpt: string;
  /** Code's judgement, not the model's: only "material" disagreements
   *  downgrade confidence. A wrong phone number is not a wrong tax rate. */
  severity: "material" | "minor";
}

/** What the falsification pass found — including finding nothing. */
export interface ChallengeReport {
  jurisdiction: string;
  findings: ChallengeFinding[];
  corroborated_fields: string[];
  /** Zero means the pass had nothing to read, which is not a clean result. */
  sources_checked: number;
}

/** Response from POST /jurisdictions/challenge. */
export interface ChallengeResponse {
  rule: JurisdictionRule;
  report: ChallengeReport;
}

/** Result of parsing an uploaded budget PDF — see backend/app/extraction/budget_parser.py. */
export interface ParsedBudget {
  budget: BudgetVector;
  /** Field name -> where in the document that figure came from. */
  field_notes: Record<string, string>;
  /** Figures not found, ambiguous lines, anything the producer should check. */
  warnings: string[];
}
