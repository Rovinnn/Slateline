import type { BudgetVector } from "../types";

/**
 * The three example budgets required by BUILD_BRIEF.md section 7 ("Try an
 * example"). Figures match the design canvas prototype
 * (../../Incentive Verifier Web App/Incentive Verifier.dc.html) so the real
 * app's numbers agree with the approved visual spec.
 */
export interface Example {
  id: string;
  name: string;
  budgetLabel: string;
  meta: string;
  budget: BudgetVector;
}

export const EXAMPLES: Example[] = [
  {
    id: "indie",
    name: "Indie Drama",
    budgetLabel: "$2.0M",
    meta: "22 days · 45 crew · 55% resident",
    budget: {
      total: 2_000_000,
      atl_cast: 250_000,
      atl_noncast: 200_000,
      btl_labor: 750_000,
      btl_nonlabor: 550_000,
      post_vfx: 250_000,
      shoot_days: 22,
      crew_headcount: 45,
      resident_labor_pct: 0.55,
      home_base: "Los Angeles, CA",
      constraints: ["coastline"],
    },
  },
  {
    id: "series",
    name: "Streaming Series",
    budgetLabel: "$18.0M",
    meta: "62 days · 140 crew · 40% resident",
    budget: {
      total: 18_000_000,
      atl_cast: 6_400_000,
      atl_noncast: 3_400_000,
      btl_labor: 4_600_000,
      btl_nonlabor: 2_400_000,
      post_vfx: 1_200_000,
      shoot_days: 62,
      crew_headcount: 140,
      resident_labor_pct: 0.4,
      home_base: "Los Angeles, CA",
      constraints: ["large_soundstage"],
    },
  },
  {
    id: "studio",
    name: "Studio Film",
    budgetLabel: "$60.0M",
    meta: "78 days · 260 crew · 35% resident",
    budget: {
      total: 60_000_000,
      atl_cast: 18_000_000,
      atl_noncast: 9_000_000,
      btl_labor: 16_000_000,
      btl_nonlabor: 11_000_000,
      post_vfx: 6_000_000,
      shoot_days: 78,
      crew_headcount: 260,
      resident_labor_pct: 0.35,
      home_base: "Los Angeles, CA",
      constraints: ["coastline", "large_soundstage"],
    },
  },
];

export interface HomeBase {
  id: string;
  label: string;
  lat: number;
  lng: number;
}

export const HOME_BASES: HomeBase[] = [
  { id: "lax", label: "Los Angeles, CA", lat: 34.052, lng: -118.244 },
  { id: "nyc", label: "New York, NY", lat: 40.713, lng: -74.006 },
  { id: "atl", label: "Atlanta, GA", lat: 33.749, lng: -84.388 },
  { id: "ldn", label: "London, UK", lat: 51.507, lng: -0.128 },
];
