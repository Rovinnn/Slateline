import { describe, expect, it } from "vitest";
import { buildWaterfall, explainWin, type Row } from "./explain";
import type { BenefitBreakdown, JurisdictionRule } from "../types";

function row(
  jurisdiction: string,
  opts: {
    rate?: number;
    creditType?: JurisdictionRule["credit_type"];
    qualifying?: number;
    gross?: number;
    realizable?: number;
    relocation?: number;
    distanceKm?: number | null;
    caps?: string[];
    monetizationNote?: string | null;
    audit?: number;
    months?: number;
    timingAssumed?: boolean;
    /** Omit to derive an undiscounted present value (the pre-timing shape). */
    presentValue?: number;
  },
): Row {
  const gross = opts.gross ?? 0;
  const realizable = opts.realizable ?? gross;
  const relocation = opts.relocation ?? 0;
  const audit = opts.audit ?? 0;
  const presentValue = opts.presentValue ?? realizable - audit;
  return {
    rule: {
      jurisdiction,
      base_rate: opts.rate ?? 0.25,
      credit_type: opts.creditType ?? "refundable",
    } as JurisdictionRule,
    benefit: {
      qualifying_spend: opts.qualifying ?? 0,
      gross_credit: gross,
      realizable_credit: realizable,
      relocation_cost: relocation,
      monetization_note: opts.monetizationNote ?? null,
      caps_applied: opts.caps ?? [],
      distance_km: opts.distanceKm ?? null,
      audit_cost: audit,
      months_to_payment: opts.months ?? 0,
      timing_is_assumed: opts.timingAssumed ?? true,
      present_value: presentValue,
      net_benefit: presentValue - relocation,
      computable: true,
    } as BenefitBreakdown,
  };
}

/** A row shaped like a backend deployed before timing existed. The two halves
 *  deploy separately, so this is a normal runtime state, not a broken one. */
function legacyRow(jurisdiction: string, gross: number, realizable: number, relocation: number): Row {
  return {
    rule: { jurisdiction, base_rate: 0.25, credit_type: "refundable" } as JurisdictionRule,
    benefit: {
      qualifying_spend: 0,
      gross_credit: gross,
      realizable_credit: realizable,
      relocation_cost: relocation,
      caps_applied: [],
      distance_km: null,
      net_benefit: realizable - relocation,
      computable: true,
      // Deliberately cast through `unknown`: BenefitBreakdown declares the
      // timing fields as required, and the point of this fixture is that a
      // separately-deployed older backend doesn't send them. The type
      // describes the current contract; the wire can carry an older one.
    } as unknown as BenefitBreakdown,
  };
}

describe("explainWin", () => {
  it("decomposes the advantage into parts that sum exactly to it", () => {
    // The guarantee that makes this an explanation rather than a vibe: if the
    // parts don't add up to the headline, the memo is lying.
    const winner = row("New Mexico", {
      rate: 0.25, creditType: "refundable", qualifying: 2_000_000, gross: 500_000, relocation: 90_000,
    });
    const rival = row("Georgia", {
      rate: 0.3, creditType: "transferable", qualifying: 2_000_000, gross: 600_000, realizable: 540_000, relocation: 120_000,
    });

    const result = explainWin(winner, rival);
    const summed = result.deltas.reduce((acc, d) => acc + d.delta, 0);

    expect(summed).toBeCloseTo(result.total, 6);
    expect(result.total).toBeCloseTo(winner.benefit.net_benefit - rival.benefit.net_benefit, 6);
  });

  it("credits monetisation when a refundable credit beats a discounted one", () => {
    const winner = row("New Mexico", { creditType: "refundable", gross: 500_000 });
    const rival = row("Georgia", { creditType: "transferable", gross: 500_000, realizable: 450_000 });

    const result = explainWin(winner, rival);
    const monetisation = result.deltas.find((d) => d.label.includes("face value"));

    expect(monetisation?.delta).toBeCloseTo(50_000);
    expect(monetisation?.detail).toContain("refundable");
    expect(monetisation?.detail).toContain("transferable");
  });

  it("attributes a relocation advantage to the cheaper destination", () => {
    const winner = row("New Mexico", { gross: 500_000, relocation: 80_000 });
    const rival = row("Georgia", { gross: 500_000, relocation: 130_000 });

    const result = explainWin(winner, rival);
    const reloc = result.deltas.find((d) => d.label.includes("Cheaper to relocate"));

    expect(reloc?.delta).toBeCloseTo(50_000);
  });

  it("reports components that work against the winner as negative", () => {
    // A winner can lead overall while losing on one line; hiding that would
    // make the explanation a sales pitch.
    const winner = row("New Mexico", { creditType: "refundable", gross: 500_000, relocation: 140_000 });
    const rival = row("Georgia", { creditType: "transferable", gross: 600_000, realizable: 540_000, relocation: 120_000 });

    const result = explainWin(winner, rival);
    expect(result.deltas.find((d) => d.label === "Smaller gross credit")?.delta).toBeCloseTo(-100_000);
    expect(result.deltas.find((d) => d.label.includes("More expensive to relocate"))?.delta).toBeCloseTo(-20_000);
    expect(result.deltas.reduce((a, d) => a + d.delta, 0)).toBeCloseTo(result.total, 6);
  });

  it("calls out the thesis case: winning on a lower headline rate", () => {
    const winner = row("New Mexico", { rate: 0.25, creditType: "refundable", gross: 500_000, relocation: 80_000 });
    const rival = row("Georgia", { rate: 0.3, creditType: "transferable", gross: 520_000, realizable: 468_000, relocation: 130_000 });

    const result = explainWin(winner, rival);
    expect(result.context.some((c) => c.includes("lower headline rate"))).toBe(true);
  });

  it("omits components that are identical rather than listing zero rows", () => {
    const winner = row("A", { gross: 500_000, relocation: 100_000 });
    const rival = row("B", { gross: 400_000, relocation: 100_000 });

    const result = explainWin(winner, rival);
    expect(result.deltas).toHaveLength(1);
    expect(result.deltas[0].label).toBe("Larger gross credit");
  });
});

describe("buildWaterfall", () => {
  it("walks qualifying spend through to net benefit", () => {
    const steps = buildWaterfall(
      row("New Mexico", { rate: 0.25, qualifying: 2_000_000, gross: 500_000, relocation: 114_900 }),
    );
    const labels = steps.map((s) => s.label);

    expect(labels[0]).toBe("Qualifying spend");
    expect(labels).toContain("Credit at 25.0%");
    expect(labels).toContain("Relocation cost");
    expect(steps.at(-1)).toMatchObject({ label: "Net benefit", value: 385_100 });
  });

  it("shows a monetisation stage only when the credit is actually discounted", () => {
    const refundable = buildWaterfall(row("NM", { creditType: "refundable", gross: 500_000, relocation: 50_000 }));
    expect(refundable.some((s) => s.label === "Monetisation discount")).toBe(false);

    const transferable = buildWaterfall(
      row("GA", { creditType: "transferable", gross: 500_000, realizable: 450_000, relocation: 50_000 }),
    );
    const discount = transferable.find((s) => s.label === "Monetisation discount");
    expect(discount?.value).toBeCloseTo(-50_000);
    expect(transferable.some((s) => s.label === "Realizable in cash")).toBe(true);
  });

  it("renders deductions as negative so the walk reads as subtraction", () => {
    const steps = buildWaterfall(row("NM", { gross: 500_000, relocation: 114_900 }));
    const reloc = steps.find((s) => s.label === "Relocation cost");
    expect(reloc?.value).toBeLessThan(0);
    expect(reloc?.kind).toBe("deduction");
  });

  it("omits relocation entirely when there is none to charge", () => {
    const steps = buildWaterfall(row("NM", { gross: 500_000, relocation: 0 }));
    expect(steps.some((s) => s.label === "Relocation cost")).toBe(false);
  });
});

describe("timing, once a credit is treated as a claim on future money", () => {
  it("keeps the five-way decomposition summing exactly to the advantage", () => {
    // The guarantee the whole explanation rests on, now that there are five
    // moving parts instead of three. If these stop reconciling, "why it wins"
    // is inventing a number.
    const winner = row("New Mexico", {
      rate: 0.25, creditType: "refundable", qualifying: 2_000_000,
      gross: 500_000, audit: 0, months: 12, presentValue: 446_429, relocation: 90_000,
    });
    const rival = row("Georgia", {
      rate: 0.3, creditType: "transferable", qualifying: 2_000_000,
      gross: 600_000, realizable: 540_000, audit: 15_000, months: 18,
      presentValue: 439_000, relocation: 120_000,
    });

    const result = explainWin(winner, rival);
    const summed = result.deltas.reduce((acc, d) => acc + d.delta, 0);

    expect(summed).toBeCloseTo(result.total, 6);
    expect(result.total).toBeCloseTo(winner.benefit.net_benefit - rival.benefit.net_benefit, 6);
  });

  it("attributes an advantage to paying out sooner", () => {
    const winner = row("Fastland", { gross: 500_000, months: 6, presentValue: 480_000 });
    const rival = row("Slowland", { gross: 500_000, months: 24, presentValue: 400_000 });

    const sooner = explainWin(winner, rival).deltas.find((d) => d.label === "Pays out sooner");
    expect(sooner?.delta).toBeCloseTo(80_000);
    expect(sooner?.detail).toContain("6 vs 24 months");
  });

  it("charges a required audit to the jurisdiction that requires it", () => {
    const winner = row("New Mexico", { gross: 500_000, audit: 0 });
    const rival = row("Georgia", { gross: 500_000, audit: 15_000 });

    const compliance = explainWin(winner, rival).deltas.find((d) => d.label === "Lower compliance cost");
    expect(compliance?.delta).toBeCloseTo(15_000);
  });

  it("walks through audit and waiting before reaching net benefit", () => {
    const steps = buildWaterfall(
      row("Georgia", {
        rate: 0.3, creditType: "transferable", qualifying: 2_000_000, gross: 600_000,
        realizable: 540_000, audit: 15_000, months: 18, presentValue: 421_059, relocation: 114_900,
      }),
    );
    const labels = steps.map((s) => s.label);

    expect(labels).toContain("Monetisation discount");
    expect(labels).toContain("Audit and compliance");
    expect(labels).toContain("Waiting 18 months to be paid");
    expect(labels).toContain("Worth today");
    expect(labels.indexOf("Audit and compliance")).toBeLessThan(labels.indexOf("Waiting 18 months to be paid"));
    expect(steps.at(-1)).toMatchObject({ label: "Net benefit", value: 306_159 });
  });

  it("says whether a payment timeline was sourced or assumed", () => {
    const sourced = buildWaterfall(row("X", { gross: 500_000, months: 4, presentValue: 480_000, timingAssumed: false }));
    expect(sourced.find((s) => s.label.startsWith("Waiting"))?.note).toContain("stated by a source");

    const assumed = buildWaterfall(row("Y", { gross: 500_000, months: 4, presentValue: 480_000, timingAssumed: true }));
    expect(assumed.find((s) => s.label.startsWith("Waiting"))?.note).toContain("assumed");
  });

  it("omits the waiting stage when nothing was discounted", () => {
    const steps = buildWaterfall(row("Z", { gross: 500_000, months: 12 }));
    expect(steps.some((s) => s.label.startsWith("Waiting"))).toBe(false);
  });
});

describe("a backend deployed before timing existed", () => {
  // The two halves deploy independently, so the frontend has to render a
  // response missing these fields — and render the *old* answer, not a
  // corrupted one.
  it("still decomposes exactly, with no timing rows invented", () => {
    const winner = legacyRow("New Mexico", 500_000, 500_000, 90_000);
    const rival = legacyRow("Georgia", 600_000, 540_000, 120_000);

    const result = explainWin(winner, rival);
    expect(result.deltas.some((d) => d.label.includes("Pays out"))).toBe(false);
    expect(result.deltas.some((d) => d.label.includes("compliance"))).toBe(false);
    expect(result.deltas.reduce((a, d) => a + d.delta, 0)).toBeCloseTo(result.total, 6);
  });

  it("builds a waterfall that ends at the undiscounted net it actually sent", () => {
    const steps = buildWaterfall(legacyRow("Georgia", 600_000, 540_000, 120_000));
    expect(steps.some((s) => s.label.startsWith("Waiting"))).toBe(false);
    expect(steps.some((s) => s.label === "Audit and compliance")).toBe(false);
    expect(steps.at(-1)).toMatchObject({ label: "Net benefit", value: 420_000 });
  });
});
