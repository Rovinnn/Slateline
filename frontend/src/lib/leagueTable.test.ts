import { describe, expect, it } from "vitest";
// Imported rather than read off disk: Vite resolves JSON natively, so this
// typechecks in the same build as the app and needs no @types/node.
import raw from "../../public/league-table.json";

/** The contract the file must satisfy, rather than the shape it happens to
 *  have today. Inferring from the JSON makes the tests brittle in the wrong
 *  direction: a run where nothing failed to price would erase `reason` from
 *  the inferred type and break the test that checks failures carry one. */
interface Row {
  jurisdiction: string;
  currency: string;
  advertised: number;
  computable: boolean;
  sources: string[];
  effective?: number;
  gap_points?: number;
  uplift_count?: number;
  advertised_is_stacked?: boolean;
  reason?: string;
}
const data = raw as unknown as {
  measured_at: string;
  reference_budget_label: string;
  reference_budget: { total: number };
  rows: Row[];
};

/**
 * The published dataset itself, checked as data.
 *
 * This file is a claim about the world that ships to users, so it's worth
 * asserting it stays internally consistent — a league table whose arithmetic
 * disagreed with the app that generated it would undermine both.
 */

describe("league-table.json", () => {
  it("says when it was measured and against what budget", () => {
    // Percentages move with the budget, so a table without its denominator on
    // screen is a number pretending to be a constant.
    expect(data.measured_at).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(data.reference_budget_label).toContain("$2M");
    expect(data.reference_budget.total).toBe(2_000_000);
  });

  it("has every priced row advertising more than it pays", () => {
    // The thesis, asserted against real measurements rather than assumed.
    const priced = data.rows.filter((r) => r.computable);
    expect(priced.length).toBeGreaterThan(4);
    for (const r of priced) {
      expect(r.effective).toBeLessThan(r.advertised);
      expect(r.gap_points).toBeGreaterThan(0);
    }
  });

  it("keeps the rows it could not price, with reasons", () => {
    // Dropping them would make the table advertising rather than measurement.
    const unpriceable = data.rows.filter((r) => !r.computable);
    for (const r of unpriceable) {
      expect(r.reason).toBeTruthy();
      expect(r.effective).toBeUndefined();
    }
  });

  it("is sorted with the widest gap first", () => {
    const gaps = data.rows.filter((r) => r.computable).map((r) => r.gap_points!);
    expect(gaps).toEqual([...gaps].sort((a: number, b: number) => b - a));
  });

  it("records sources for every row, priced or not", () => {
    for (const r of data.rows) expect(Array.isArray(r.sources)).toBe(true);
  });
});

describe("stacked uplifts", () => {
  it("flags a headline built by summing credits that can't all apply", () => {
    // British Columbia sums to 104.5% across federal, provincial, regional
    // and DAVE credits. That's what gets marketed, but no single production
    // combines them — unflagged it reads as a broken number rather than a
    // finding about how these programmes are advertised.
    const stacked = data.rows.filter((r) => r.advertised > 0.6);
    for (const r of stacked) {
      expect(r.advertised_is_stacked).toBe(true);
      expect(r.uplift_count).toBeGreaterThan(0);
    }
  });

  it("covers more than one continent, or it isn't measuring the world", () => {
    const names = data.rows.map((r) => r.jurisdiction);
    expect(names).toContain("Ireland");
    expect(names.some((n) => ["Hungary", "United Kingdom", "Colombia"].includes(n))).toBe(true);
  });

  it("prices non-USD programmes rather than refusing them", () => {
    const nonUsd = data.rows.filter((r) => r.currency !== "USD");
    expect(nonUsd.length).toBeGreaterThan(0);
    for (const r of nonUsd) expect(r.computable).toBe(true);
  });
});
