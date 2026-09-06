import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

/**
 * The published dataset itself, checked as data.
 *
 * This file is a claim about the world that ships to users, so it's worth
 * asserting it stays internally consistent — a league table whose arithmetic
 * disagreed with the app that generated it would undermine both.
 */
const data = JSON.parse(readFileSync("public/league-table.json", "utf-8"));

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
    const priced = data.rows.filter((r: { computable: boolean }) => r.computable);
    expect(priced.length).toBeGreaterThan(4);
    for (const r of priced) {
      expect(r.effective).toBeLessThan(r.advertised);
      expect(r.gap_points).toBeGreaterThan(0);
    }
  });

  it("keeps the rows it could not price, with reasons", () => {
    // Dropping them would make the table advertising rather than measurement.
    const unpriceable = data.rows.filter((r: { computable: boolean }) => !r.computable);
    for (const r of unpriceable) {
      expect(r.reason).toBeTruthy();
      expect(r.effective).toBeUndefined();
    }
  });

  it("is sorted with the widest gap first", () => {
    const gaps = data.rows.filter((r: { computable: boolean }) => r.computable).map((r: { gap_points: number }) => r.gap_points);
    expect(gaps).toEqual([...gaps].sort((a: number, b: number) => b - a));
  });

  it("records sources for every row, priced or not", () => {
    for (const r of data.rows) expect(Array.isArray(r.sources)).toBe(true);
  });
});
