import { beforeEach, describe, expect, it, vi } from "vitest";
import { computeBenefitBatch } from "./api";
import { scanBreakeven } from "./breakeven";
import { DEFAULT_RELOCATION_ASSUMPTIONS, type BenefitBreakdown, type BudgetVector, type JurisdictionRule } from "../types";

vi.mock("./api", () => ({ computeBenefitBatch: vi.fn() }));

/**
 * The crossover branch is unreachable with the current live jurisdictions —
 * Georgia/New Mexico/Louisiana are all flat-rate with no caps, so their
 * ranking is invariant to how much you spend and the scan always reports
 * "leads across the whole range". Mocked net-benefit curves are the only way
 * to exercise the branch that fires once a tiered or capped jurisdiction
 * enters the comparison, which is exactly the case the sparkline exists for.
 */

const ATL_BASE = 4_000_000; // -> hi = max(4M * 2.5, 4M) = 10M
const HI = 10_000_000;

function makeRule(jurisdiction: string): JurisdictionRule {
  return { jurisdiction } as JurisdictionRule;
}

function makeBudget(atl: number): BudgetVector {
  return {
    total: atl + 1_000_000,
    atl_cast: atl * 0.6,
    atl_noncast: atl * 0.4,
    btl_labor: 500_000,
    btl_nonlabor: 300_000,
    post_vfx: 200_000,
    shoot_days: 22,
    crew_headcount: 45,
    resident_labor_pct: 0.5,
    home_base: "Los Angeles, CA",
    constraints: [],
  };
}

function breakdown(net: number, computable = true): BenefitBreakdown {
  return {
    jurisdiction: "",
    qualifying_spend: 0,
    gross_credit: 0,
    caps_applied: [],
    distance_km: null,
    travel_time_hours: null,
    relocation_cost: 0,
    relocation_components: {},
    net_benefit: net,
    computable,
    non_computable_reason: null,
  };
}

/** Drives the mock from a per-jurisdiction net-benefit curve over ATL spend. */
function mockNetCurves(curves: Record<string, (atl: number) => BenefitBreakdown>) {
  vi.mocked(computeBenefitBatch).mockImplementation(async (budgets, rule) =>
    budgets.map((b) => curves[rule.jurisdiction](b.atl_cast + b.atl_noncast)),
  );
}

beforeEach(() => {
  vi.mocked(computeBenefitBatch).mockReset();
});

describe("scanBreakeven", () => {
  it("reports no crossover when the leader leads across the whole range", async () => {
    mockNetCurves({
      Alpha: (atl) => breakdown(atl * 0.3),
      Beta: (atl) => breakdown(atl * 0.2),
    });

    const result = await scanBreakeven(
      [makeRule("Alpha"), makeRule("Beta")],
      "Alpha",
      makeBudget(2_000_000),
      ATL_BASE,
      DEFAULT_RELOCATION_ASSUMPTIONS,
    );

    expect(result.crossAtl).toBeNull();
    expect(result.heroName).toBe("Alpha");
    expect(result.series).toHaveLength(49); // 48 steps, inclusive of both ends
    expect(result.hi).toBe(HI);
  });

  it("finds a crossover above current spend when the leader's credit is capped", async () => {
    // Alpha is the better deal now, but its credit plateaus at $1.5M while
    // Beta keeps scaling — so Beta wins above ~$6M of ATL spend.
    mockNetCurves({
      Alpha: (atl) => breakdown(Math.min(atl * 0.3, 1_500_000)),
      Beta: (atl) => breakdown(atl * 0.25),
    });

    const result = await scanBreakeven(
      [makeRule("Alpha"), makeRule("Beta")],
      "Alpha",
      makeBudget(2_000_000),
      ATL_BASE,
      DEFAULT_RELOCATION_ASSUMPTIONS,
    );

    expect(result.crossAtl).not.toBeNull();
    expect(result.above).toBe(true);
    expect(result.rivalName).toBe("Beta");
    expect(result.crossAtl).toBeGreaterThan(5_800_000);
    expect(result.crossAtl).toBeLessThan(6_400_000);
  });

  it("finds a crossover below current spend when a rival wins at small budgets", async () => {
    // Beta pays a flat $500k regardless of spend, so it only wins while the
    // production is small; Alpha overtakes it above $2M of ATL spend.
    mockNetCurves({
      Alpha: (atl) => breakdown(atl * 0.25),
      Beta: () => breakdown(500_000),
    });

    const result = await scanBreakeven(
      [makeRule("Alpha"), makeRule("Beta")],
      "Alpha",
      makeBudget(6_000_000),
      ATL_BASE,
      DEFAULT_RELOCATION_ASSUMPTIONS,
    );

    expect(result.crossAtl).not.toBeNull();
    expect(result.above).toBe(false);
    expect(result.rivalName).toBe("Beta");
    expect(result.crossAtl).toBeLessThan(2_100_000);
  });

  it("ignores non-computable jurisdictions when deciding who leads", async () => {
    // A discretionary program can carry a net_benefit of 0 (or anything) but
    // must never take the lead — it isn't in the ranking at all.
    mockNetCurves({
      Alpha: (atl) => breakdown(atl * 0.25),
      Gamma: () => breakdown(99_000_000, false),
    });

    const result = await scanBreakeven(
      [makeRule("Alpha"), makeRule("Gamma")],
      "Alpha",
      makeBudget(2_000_000),
      ATL_BASE,
      DEFAULT_RELOCATION_ASSUMPTIONS,
    );

    expect(result.crossAtl).toBeNull();
    for (const point of result.series) expect(point.nets.Gamma).toBeNull();
  });

  it("passes each jurisdiction's own cached distance into its compute call", async () => {
    // Relocation cost differs per jurisdiction, so the sweep must not reuse
    // one distance for all of them or compare against a distance-less curve.
    mockNetCurves({
      Alpha: (atl) => breakdown(atl * 0.3),
      Beta: (atl) => breakdown(atl * 0.2),
    });

    await scanBreakeven(
      [makeRule("Alpha"), makeRule("Beta")],
      "Alpha",
      makeBudget(2_000_000),
      ATL_BASE,
      DEFAULT_RELOCATION_ASSUMPTIONS,
      { Alpha: { distance_km: 100, travel_time_hours: 2 }, Beta: { distance_km: 3000, travel_time_hours: 30 } },
    );

    const calls = vi.mocked(computeBenefitBatch).mock.calls;
    const byJurisdiction = Object.fromEntries(calls.map(([, rule, opts]) => [rule.jurisdiction, opts]));
    expect(byJurisdiction.Alpha).toMatchObject({ distance_km: 100, travel_time_hours: 2 });
    expect(byJurisdiction.Beta).toMatchObject({ distance_km: 3000, travel_time_hours: 30 });
  });

  it("sweeps ATL spend while holding the rest of the budget constant", async () => {
    mockNetCurves({ Alpha: (atl) => breakdown(atl * 0.3) });

    await scanBreakeven(
      [makeRule("Alpha")],
      "Alpha",
      makeBudget(2_000_000),
      ATL_BASE,
      DEFAULT_RELOCATION_ASSUMPTIONS,
    );

    const [budgets] = vi.mocked(computeBenefitBatch).mock.calls[0];
    expect(budgets[0].atl_cast + budgets[0].atl_noncast).toBeCloseTo(0);
    expect(budgets.at(-1)!.atl_cast + budgets.at(-1)!.atl_noncast).toBeCloseTo(HI);
    // Non-ATL lines are untouched, and total tracks the ATL change.
    for (const b of budgets) {
      expect(b.btl_labor).toBe(500_000);
      expect(b.total).toBeCloseTo(b.atl_cast + b.atl_noncast + 500_000 + 300_000 + 200_000);
    }
  });
});
