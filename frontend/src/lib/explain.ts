import type { BenefitBreakdown, JurisdictionRule } from "../types";

export interface Row {
  rule: JurisdictionRule;
  benefit: BenefitBreakdown;
}

/** One component of the winner's advantage, in signed dollars. */
export interface WinDelta {
  label: string;
  detail: string;
  /** Positive helps the winner, negative works against it. */
  delta: number;
}

export interface WinExplanation {
  winner: string;
  rival: string;
  /** Deltas sum exactly to `total` — see the decomposition note below. */
  deltas: WinDelta[];
  total: number;
  /** Non-additive colour: the things that *caused* the credit difference. */
  context: string[];
}

/**
 * Why the top pick beats the runner-up, derived arithmetically.
 *
 * Deliberately not model-generated prose: this is a decision memo, and an
 * explanation of a number has to come from that number or it's decoration.
 * Everything here is a subtraction between two BenefitBreakdowns.
 *
 * The decomposition is exact. With `net = realizable − relocation` and
 * `discount = realizable − gross` (≤ 0):
 *
 *     (gross_w − gross_r) + (discount_w − discount_r) + (reloc_r − reloc_w)
 *   = (realizable_w − reloc_w) − (realizable_r − reloc_r)
 *   = net_w − net_r
 *
 * so the three deltas always sum to the headline advantage. Qualifying spend
 * and headline rate multiply rather than add, so they're reported as context
 * rather than folded into the sum — claiming a clean split there would be a
 * lie about arithmetic the rest of this project refuses to tell.
 */
export function explainWin(winner: Row, rival: Row): WinExplanation {
  const realizableOf = (r: Row) => r.benefit.realizable_credit ?? r.benefit.gross_credit;
  const discountOf = (r: Row) => realizableOf(r) - r.benefit.gross_credit;

  const creditDelta = winner.benefit.gross_credit - rival.benefit.gross_credit;
  const monetizationDelta = discountOf(winner) - discountOf(rival);
  const relocationDelta = rival.benefit.relocation_cost - winner.benefit.relocation_cost;

  const deltas: WinDelta[] = [];

  if (Math.abs(creditDelta) >= 1) {
    deltas.push({
      label: creditDelta > 0 ? "Larger gross credit" : "Smaller gross credit",
      detail: `${pct(winner.rule.base_rate)} on ${money(winner.benefit.qualifying_spend)} qualifying vs ${pct(
        rival.rule.base_rate,
      )} on ${money(rival.benefit.qualifying_spend)}`,
      delta: creditDelta,
    });
  }

  if (Math.abs(monetizationDelta) >= 1) {
    deltas.push({
      label: monetizationDelta > 0 ? "Credit keeps more of its face value" : "Credit loses more to monetisation",
      detail: `${payoutPhrase(winner)} vs ${payoutPhrase(rival)}`,
      delta: monetizationDelta,
    });
  }

  if (Math.abs(relocationDelta) >= 1) {
    deltas.push({
      label: relocationDelta > 0 ? "Cheaper to relocate to" : "More expensive to relocate to",
      detail: `${money(winner.benefit.relocation_cost)} vs ${money(rival.benefit.relocation_cost)} to move cast and crew`,
      delta: relocationDelta,
    });
  }

  const context: string[] = [];
  const spendGap = winner.benefit.qualifying_spend - rival.benefit.qualifying_spend;
  if (Math.abs(spendGap) >= 1) {
    context.push(
      spendGap > 0
        ? `${money(spendGap)} more of the budget qualifies in ${winner.rule.jurisdiction}`
        : `${money(-spendGap)} less of the budget qualifies in ${winner.rule.jurisdiction}`,
    );
  }
  if (winner.rule.base_rate < rival.rule.base_rate) {
    // The product's whole thesis, stated whenever the data demonstrates it.
    context.push(
      `${winner.rule.jurisdiction} wins on a lower headline rate (${pct(winner.rule.base_rate)} vs ${pct(
        rival.rule.base_rate,
      )})`,
    );
  }

  return {
    winner: winner.rule.jurisdiction,
    rival: rival.rule.jurisdiction,
    deltas,
    total: winner.benefit.net_benefit - rival.benefit.net_benefit,
    context,
  };
}

function payoutPhrase(row: Row): string {
  const type = row.rule.credit_type ?? "unknown";
  const phrases: Record<string, string> = {
    refundable: "refundable (paid at face value)",
    rebate: "cash rebate (paid at face value)",
    transferable: "transferable (sold at a discount)",
    non_refundable: "non-refundable (needs in-state liability)",
    unknown: "payout mechanism unstated",
  };
  return `${row.rule.jurisdiction} ${phrases[type] ?? phrases.unknown}`;
}

function pct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function money(v: number): string {
  return (v < 0 ? "−$" : "$") + Math.round(Math.abs(v)).toLocaleString("en-US");
}

/** A stage in the face-value-to-cash walk shown under the recommendation. */
export interface WaterfallStep {
  label: string;
  value: number;
  /** Subtractions render differently from the running totals they reduce. */
  kind: "base" | "deduction" | "total";
  note?: string;
}

/**
 * The credit's journey from advertised rate to money in the bank — the one
 * picture that carries the product's entire argument, since every stage is a
 * place the advertised number quietly shrinks.
 */
export function buildWaterfall(row: Row): WaterfallStep[] {
  const { rule, benefit } = row;
  const realizable = benefit.realizable_credit ?? benefit.gross_credit;
  const discount = realizable - benefit.gross_credit;

  const steps: WaterfallStep[] = [
    {
      label: "Qualifying spend",
      value: benefit.qualifying_spend,
      kind: "base",
      note: "the part of your budget this program actually counts",
    },
    {
      label: `Credit at ${pct(rule.base_rate)}`,
      value: benefit.gross_credit,
      kind: "total",
      note: benefit.caps_applied.length ? `${benefit.caps_applied.length} cap/uplift note(s) applied` : undefined,
    },
  ];

  if (Math.abs(discount) >= 1) {
    steps.push({
      label: "Monetisation discount",
      value: discount,
      kind: "deduction",
      note: benefit.monetization_note ?? undefined,
    });
    steps.push({ label: "Realizable in cash", value: realizable, kind: "total" });
  }

  if (benefit.relocation_cost > 0) {
    steps.push({
      label: "Relocation cost",
      value: -benefit.relocation_cost,
      kind: "deduction",
      note: benefit.distance_km != null ? `${Math.round(benefit.distance_km).toLocaleString()} km from home base` : undefined,
    });
  }

  steps.push({ label: "Net benefit", value: benefit.net_benefit, kind: "total" });
  return steps;
}
