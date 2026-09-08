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
      fringe_rate: 0.28,
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
      fringe_rate: 0.28,
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
      fringe_rate: 0.28,
    },
  },
];

/** Jurisdictions searched live (Parallel + Gemini, backend/app/extraction/agent.py)
 * when the Results screen first loads — every run hits the real pipeline,
 * there's no static/canned jurisdiction data left in the app. */
export const DEFAULT_JURISDICTIONS = ["Georgia", "New Mexico", "Louisiana", "Texas"];

export interface HomeBase {
  id: string;
  label: string;
  region: string;
  lat: number;
  lng: number;
}

export const HOME_BASES: HomeBase[] = [
  { id: "lax", label: "Los Angeles, CA", region: "United States", lat: 34.052, lng: -118.244 },
  { id: "nyc", label: "New York, NY", region: "United States", lat: 40.713, lng: -74.006 },
  { id: "atl", label: "Atlanta, GA", region: "United States", lat: 33.749, lng: -84.388 },
  { id: "tor", label: "Toronto, Canada", region: "Canada & Mexico", lat: 43.6532, lng: -79.3832 },
  { id: "yvr", label: "Vancouver, Canada", region: "Canada & Mexico", lat: 49.2827, lng: -123.1207 },
  { id: "mex", label: "Mexico City, Mexico", region: "Canada & Mexico", lat: 19.4326, lng: -99.1332 },
  { id: "ldn", label: "London, UK", region: "Europe", lat: 51.507, lng: -0.128 },
  { id: "par", label: "Paris, France", region: "Europe", lat: 48.8566, lng: 2.3522 },
  { id: "ber", label: "Berlin, Germany", region: "Europe", lat: 52.52, lng: 13.405 },
  { id: "mad", label: "Madrid, Spain", region: "Europe", lat: 40.4168, lng: -3.7038 },
  { id: "rom", label: "Rome, Italy", region: "Europe", lat: 41.9028, lng: 12.4964 },
  { id: "prg", label: "Prague, Czechia", region: "Europe", lat: 50.0755, lng: 14.4378 },
  { id: "bud", label: "Budapest, Hungary", region: "Europe", lat: 47.4979, lng: 19.0402 },
  { id: "dxb", label: "Dubai, UAE", region: "Middle East", lat: 25.2048, lng: 55.2708 },
  { id: "auh", label: "Abu Dhabi, UAE", region: "Middle East", lat: 24.4539, lng: 54.3773 },
  { id: "bom", label: "Mumbai, India", region: "Asia", lat: 19.076, lng: 72.8777 },
  { id: "sel", label: "Seoul, South Korea", region: "Asia", lat: 37.5665, lng: 126.978 },
  { id: "tyo", label: "Tokyo, Japan", region: "Asia", lat: 35.6762, lng: 139.6503 },
  { id: "bkk", label: "Bangkok, Thailand", region: "Asia", lat: 13.7563, lng: 100.5018 },
  { id: "syd", label: "Sydney, Australia", region: "Oceania", lat: -33.8688, lng: 151.2093 },
  { id: "mel", label: "Melbourne, Australia", region: "Oceania", lat: -37.8136, lng: 144.9631 },
  { id: "akl", label: "Auckland, New Zealand", region: "Oceania", lat: -36.8509, lng: 174.7645 },
  { id: "cpt", label: "Cape Town, South Africa", region: "Africa", lat: -33.9249, lng: 18.4241 },
  { id: "jnb", label: "Johannesburg, South Africa", region: "Africa", lat: -26.2041, lng: 28.0473 },
  { id: "sao", label: "São Paulo, Brazil", region: "South America", lat: -23.5505, lng: -46.6333 },
  { id: "bue", label: "Buenos Aires, Argentina", region: "South America", lat: -34.6037, lng: -58.3816 },
];
