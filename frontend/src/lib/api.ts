import type {
  ChallengeResponse,
  CreditTimingAssumptions,
  SplitResponse,
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

// Layer 1 search is normally 30-60s (Parallel + Gemini extraction, see
// searchJurisdiction below); this gives headroom above that before treating
// a hung request as failed rather than leaving the UI waiting forever.
const DEFAULT_TIMEOUT_MS = 90_000;

function withTimeout(ms = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, cleanup: () => clearTimeout(id) };
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const { signal, cleanup } = withTimeout();
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok) throw new ApiError(await errorDetail(res), res.status);
    return res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Timed out waiting for the server — try again.", 408);
    }
    throw err;
  } finally {
    cleanup();
  }
}

async function getJson<T>(path: string): Promise<T> {
  const { signal, cleanup } = withTimeout();
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { signal });
    if (!res.ok) throw new ApiError(await errorDetail(res), res.status);
    return res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Timed out waiting for the server — try again.", 408);
    }
    throw err;
  } finally {
    cleanup();
  }
}

/** Layer 2, over the wire. Works today with zero credentials — see backend/app/main.py. */
export function computeBenefit(
  budget: BudgetVector,
  rule: JurisdictionRule,
  opts?: {
    distance_km?: number;
    travel_time_hours?: number;
    assumptions?: RelocationAssumptions;
    timing?: CreditTimingAssumptions;
  },
): Promise<BenefitBreakdown> {
  return postJson<BenefitBreakdown>("/compute", {
    budget,
    rule,
    distance_km: opts?.distance_km ?? null,
    travel_time_hours: opts?.travel_time_hours ?? null,
    assumptions: opts?.assumptions ?? null,
    // Null lets the backend apply its own defaults, which is what an older
    // frontend does implicitly — so sending it explicitly changes nothing
    // except making the assumptions editable.
    timing: opts?.timing ?? null,
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
  opts?: {
    distance_km?: number;
    travel_time_hours?: number;
    assumptions?: RelocationAssumptions;
    timing?: CreditTimingAssumptions;
  },
): Promise<BenefitBreakdown[]> {
  return postJson<BenefitBreakdown[]>("/compute/batch", {
    budgets,
    rule,
    distance_km: opts?.distance_km ?? null,
    travel_time_hours: opts?.travel_time_hours ?? null,
    assumptions: opts?.assumptions ?? null,
    // Null lets the backend apply its own defaults, which is what an older
    // frontend does implicitly — so sending it explicitly changes nothing
    // except making the assumptions editable.
    timing: opts?.timing ?? null,
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

/**
 * Shoot in one jurisdiction, post in another — every pairing, ranked.
 *
 * The question a rate table structurally cannot answer, because a table has
 * one row per place and this needs combinations of them. Throws ApiError(404)
 * when nothing could be computed at all, which is different from "no split
 * helps" — that returns 200 with splitting_wins false.
 */
export function computeSplit(
  budget: BudgetVector,
  rules: JurisdictionRule[],
  opts?: {
    distances?: Record<string, number>;
    assumptions?: RelocationAssumptions;
    timing?: CreditTimingAssumptions;
  },
): Promise<SplitResponse> {
  return postJson<SplitResponse>("/compute/split", {
    budget,
    rules,
    distances: opts?.distances ?? null,
    assumptions: opts?.assumptions ?? null,
    timing: opts?.timing ?? null,
  });
}

/**
 * Layer 1b: ask whether this rule is wrong.
 *
 * A separate call from searchJurisdiction on purpose — it's a second Parallel
 * + Gemini round trip, so folding it into the initial load would roughly
 * double an already slow first paint. Called after results render, it
 * annotates them in place: the ranking appears fast, then each jurisdiction
 * gains either a conflict or the note that we went looking and found nothing.
 *
 * Sends the whole rule, not a name: the point is to disagree with the figures
 * currently on screen, not to run discovery again.
 */
export function challengeJurisdiction(rule: JurisdictionRule): Promise<ChallengeResponse> {
  return postJson<ChallengeResponse>("/jurisdictions/challenge", rule);
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
