import type { BenefitBreakdown, BudgetVector, JurisdictionRule, RelocationAssumptions } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(detail || res.statusText, res.status);
  }
  return res.json();
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(detail || res.statusText, res.status);
  }
  return res.json();
}

/**
 * Hand-curated real jurisdictions (backend/app/seed_jurisdictions.py) — a
 * manual stand-in for live extraction until Layer 1 (Gemini + Parallel) has
 * GCP auth. See that file's docstring: every figure is sourced from a real
 * search, not fabricated, just not automated yet.
 */
export function getSeedJurisdictions(): Promise<JurisdictionRule[]> {
  return getJson<JurisdictionRule[]>("/jurisdictions/seed");
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
 * Layer 1, over the wire. Returns 501 until GOOGLE_CLOUD_PROJECT,
 * PARALLEL_API_KEY and GOOGLE_MAPS_API_KEY are configured on the backend —
 * see backend/app/extraction/agent.py.
 */
export function searchJurisdiction(jurisdiction: string): Promise<JurisdictionRule> {
  return postJson<JurisdictionRule>(`/jurisdictions/search?jurisdiction=${encodeURIComponent(jurisdiction)}`, {});
}
