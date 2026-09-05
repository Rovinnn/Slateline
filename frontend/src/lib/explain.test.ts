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
  },
): Row {
  const gross = opts.gross ?? 0;
  const realizable = opts.realizable ?? gross;
  const relocation = opts.relocation ?? 0;
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
      net_benefit: realizable - relocation,
      computable: true,
    } as BenefitBreakdown,
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
