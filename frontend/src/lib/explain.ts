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
 * The decomposition is exact. Writing `discount = realizable − gross` (≤ 0)
 * and `timingLoss = presentValue − (realizable − audit)` (≤ 0), the backend
 * computes `net = gross + discount − audit + timingLoss − relocation`
 * (pinned on that side by test_present_value.py), so:
 *
 *     (gross_w − gross_r) + (discount_w − discount_r) + (audit_r − audit_w)
 *   + (timingLoss_w − timingLoss_r) + (reloc_r − reloc_w)
 *   = net_w − net_r
 *
 * and the five deltas always sum to the headline advantage. Qualifying spend
 * and headline rate multiply rather than add, so they're reported as context
 * rather than folded into the sum — claiming a clean split there would be a
 * lie about arithmetic the rest of this project refuses to tell.
 */
export function explainWin(winner: Row, rival: Row): WinExplanation {
  const creditDelta = winner.benefit.gross_credit - rival.benefit.gross_credit;
  const monetizationDelta = discountOf(winner) - discountOf(rival);
  const auditDelta = auditOf(rival) - auditOf(winner);
  const timingDelta = timingLossOf(winner) - timingLossOf(rival);
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

  if (Math.abs(auditDelta) >= 1) {
    deltas.push({
      label: auditDelta > 0 ? "Lower compliance cost" : "Higher compliance cost",
      detail: `${money(auditOf(winner))} vs ${money(auditOf(rival))} to have the spend audited before payment`,
      delta: auditDelta,
    });
  }

  if (Math.abs(timingDelta) >= 1) {
    deltas.push({
      label: timingDelta > 0 ? "Pays out sooner" : "Pays out later",
      detail: `${monthsOf(winner)} vs ${monthsOf(rival)} months from wrap to money in hand`,
      delta: timingDelta,
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

/* The stages of the walk from face value to cash, each with the fallback a
 * backend deployed before that stage existed makes necessary. The frontend
 * and backend deploy separately, so "the field isn't there" is a normal
 * runtime state, not a bug — and every fallback below is the value that
 * reproduces the older behaviour exactly. */

/** What the credit is worth after a broker's cut. Face value if none. */
function realizableOf(row: Row): number {
  return row.benefit.realizable_credit ?? row.benefit.gross_credit;
}

/** The broker's cut itself, as a non-positive number. */
function discountOf(row: Row): number {
  return realizableOf(row) - row.benefit.gross_credit;
}

/** Cost of the audit standing between wrap and payment. */
function auditOf(row: Row): number {
  return row.benefit.audit_cost ?? 0;
}

/** What the wait costs, as a non-positive number. Zero on an older backend,
 *  which reproduces its undiscounted arithmetic exactly. */
function timingLossOf(row: Row): number {
  const pv = row.benefit.present_value ?? realizableOf(row) - auditOf(row);
  return pv - (realizableOf(row) - auditOf(row));
}

function monthsOf(row: Row): number {
  return row.benefit.months_to_payment ?? 0;
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
  const realizable = realizableOf(row);
  const discount = discountOf(row);
  const audit = auditOf(row);
  const timingLoss = timingLossOf(row);

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

  if (audit >= 1) {
    steps.push({
      label: "Audit and compliance",
      value: -audit,
      kind: "deduction",
      note: "a required audit is paid to earn the credit, not out of it",
    });
  }

  // The stage the tool was missing entirely: a credit is a claim on future
  // money, and the wait is a real cost even when nobody discounts the face
  // value. Omitted when timing was never applied, so a pre-timing backend
  // still renders a coherent walk.
  if (timingLoss <= -1) {
    const months = monthsOf(row);
    steps.push({
      label: `Waiting ${months} months to be paid`,
      value: timingLoss,
      kind: "deduction",
      note: benefit.timing_is_assumed === false ? "timeline stated by a source" : "typical wait, assumed",
    });
    steps.push({ label: "Worth today", value: benefit.present_value ?? realizable, kind: "total" });
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

/** The advertised headline against what actually reaches the production. */
export interface EffectiveRate {
  /** Base rate plus every uplift — the "up to X%" a film office markets. */
  advertised: number;
  /** Net benefit as a share of the whole budget. Can be negative. */
  effective: number;
  /** Percentage points lost between the two. */
  gapPoints: number;
  /** True when the advertised figure includes uplifts we could not verify. */
  advertisedIncludesUplifts: boolean;
}

/**
 * The product's thesis, as a single number.
 *
 * Everything else here explains the *mechanism* by which an advertised rate
 * collapses — qualification, monetisation, the wait, relocation. This states
 * the collapse itself, which is the part a producer feels immediately:
 * Georgia advertises up to 30% and returns 8.8% of the budget.
 *
 * Denominated in total budget, not qualifying spend, and that choice matters.
 * Against qualifying spend the figure flatters every jurisdiction, because
 * qualifying spend is already the subset that survived the rules. A producer
 * asks "what do I get back on the money I'm spending", and the money they're
 * spending is the whole budget.
 *
 * `advertised` sums the uplifts because that is what gets marketed — Georgia
 * is sold as "30%", which is 20% base plus a 10% uplift contingent on
 * commercial distribution within five years. Comparing against the base rate
 * alone would understate the gap and let the tool off the hook.
 */
export function effectiveRate(row: Row, totalBudget: number): EffectiveRate | null {
  if (!(totalBudget > 0)) return null;
  const uplifts = row.rule.uplifts?.reduce((sum, u) => sum + u.bonus_rate, 0) ?? 0;
  const advertised = row.rule.base_rate + uplifts;
  const effective = row.benefit.net_benefit / totalBudget;
  return {
    advertised,
    effective,
    gapPoints: (advertised - effective) * 100,
    advertisedIncludesUplifts: uplifts > 0,
  };
}
