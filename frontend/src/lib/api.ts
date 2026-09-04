import type {
  BenefitBreakdown,
  BudgetVector,
  JurisdictionRule,
  ParsedBudget,
  RelocationAssumptions,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** FastAPI's HTTPException serializes as {"detail": "..."} — unwrap it so
 * ApiError.message is the human-readable string, not raw JSON. */
async function errorDetail(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {
    // not JSON — fall through to raw text
  }
  return text || res.statusText;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(await errorDetail(res), res.status);
  return res.json();
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new ApiError(await errorDetail(res), res.status);
  return res.json();
}

/** Layer 2, over the wire. Works today with zero credentials — see backend/app/main.py. */
export function computeBenefit(
  budget: BudgetVector,
  rule: JurisdictionRule,
  opts?: { distance_km?: number; travel_time_hours?: number; assumptions?: RelocationAssumptions },
): Promise<BenefitBreakdown> {
  return postJson<BenefitBreakdown>("/compute", {
    budget,
    rule,
    distance_km: opts?.distance_km ?? null,
    travel_time_hours: opts?.travel_time_hours ?? null,
    assumptions: opts?.assumptions ?? null,
  });
}

/**
 * compute_benefit over several budgets against one rule, in a single round
 * trip — used for the breakeven sparkline's ATL-spend scan so it doesn't
 * need one HTTP call per sample point.
 */
export function computeBenefitBatch(
  budgets: BudgetVector[],
  rule: JurisdictionRule,
  opts?: { distance_km?: number; travel_time_hours?: number; assumptions?: RelocationAssumptions },
): Promise<BenefitBreakdown[]> {
  return postJson<BenefitBreakdown[]>("/compute/batch", {
    budgets,
    rule,
    distance_km: opts?.distance_km ?? null,
    travel_time_hours: opts?.travel_time_hours ?? null,
    assumptions: opts?.assumptions ?? null,
  });
}

/**
 * Layer 1, over the wire — Parallel search + a forced-function-call Gemini
 * extraction (see backend/app/extraction/agent.py), verified the same way
 * the seed jurisdictions are. Throws ApiError(502) on extraction failure.
 *
 * The backend caches this per jurisdiction (app/cache.py) so a repeat call
 * is instant and free — pass `refresh: true` to force a live re-extraction
 * (e.g. a user-facing "refresh" control), bypassing that cache.
 */
export function searchJurisdiction(jurisdiction: string, opts?: { refresh?: boolean }): Promise<JurisdictionRule> {
  const params = new URLSearchParams({ jurisdiction });
  if (opts?.refresh) params.set("refresh", "true");
  return postJson<JurisdictionRule>(`/jurisdictions/search?${params.toString()}`, {});
}

export interface DistanceInfo {
  distance_km: number;
  travel_time_hours: number;
}

/**
 * Hub-to-hub distance/time via Google Maps (backend/app/maps_client.py).
 * Callers fetch this once per (home_base, jurisdiction) pair and cache it —
 * see the comment on Results.tsx's distance-fetch effect for why this isn't
 * folded into every /compute call instead.
 */
export function getDistance(origin: string, destinationLat: number, destinationLng: number): Promise<DistanceInfo> {
  const params = new URLSearchParams({
    origin,
    destination_lat: String(destinationLat),
    destination_lng: String(destinationLng),
  });
  return getJson<DistanceInfo>(`/distance?${params.toString()}`);
}

/**
 * Uploads a budget PDF for Gemini to read (backend/app/extraction/budget_parser.py).
 * Returns a pre-filled BudgetVector plus per-field provenance — the caller
 * takes the user to the form to check it, never straight to results.
 */
export async function parseBudgetPdf(file: File): Promise<ParsedBudget> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE_URL}/budget/parse`, { method: "POST", body: form });
  if (!res.ok) throw new ApiError(await errorDetail(res), res.status);
  return res.json();
}
