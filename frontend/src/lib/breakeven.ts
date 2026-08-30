import { computeBenefitBatch } from "./api";
import type { BudgetVector, JurisdictionRule, RelocationAssumptions } from "../types";

export interface BreakevenPoint {
  atl: number;
  nets: Record<string, number | null>; // jurisdiction name -> net_benefit, null if not computable at that point
}

export interface BreakevenResult {
  series: BreakevenPoint[];
  hi: number;
  heroName: string;
  atlNow: number;
  /** ATL spend where the leader changes, or null if the hero leads across the whole tested range. */
  crossAtl: number | null;
  /** true if the crossover is above the current ATL spend, false if below. */
  above: boolean;
  rivalName: string | null;
}

const STEPS = 48;

function leaderAt(point: BreakevenPoint): string | null {
  let best: string | null = null;
  let bestVal = -Infinity;
  for (const [name, v] of Object.entries(point.nets)) {
    if (v != null && v > bestVal) {
      bestVal = v;
      best = name;
    }
  }
  return best;
}

/**
 * Scans ATL spend (cast+non-cast, split in the current ratio — same
 * construction the sensitivity slider uses) across a range, via one
 * /compute/batch call per jurisdiction, and finds where the current leader
 * stops leading. Powers BUILD_BRIEF.md section 7's "breakeven line... with a
 * small inline sparkline of the crossover."
 */
export async function scanBreakeven(
  rules: JurisdictionRule[],
  heroName: string,
  liveBudget: BudgetVector,
  atlBase: number,
  assumptions: RelocationAssumptions,
): Promise<BreakevenResult> {
  const hi = Math.max(atlBase * 2.5, 4_000_000);
  const atlNow = liveBudget.atl_cast + liveBudget.atl_noncast;
  const atlShare = atlNow > 0 ? liveBudget.atl_cast / atlNow : 0.65;

  const atlValues = Array.from({ length: STEPS + 1 }, (_, s) => (hi / STEPS) * s);
  const sweptBudgets = atlValues.map((atl) => ({
    ...liveBudget,
    atl_cast: atl * atlShare,
    atl_noncast: atl * (1 - atlShare),
    total: atl + liveBudget.btl_labor + liveBudget.btl_nonlabor + liveBudget.post_vfx,
  }));

  const perRule = await Promise.all(
    rules.map(async (rule) => ({
      name: rule.jurisdiction,
      results: await computeBenefitBatch(sweptBudgets, rule, { assumptions }),
    })),
  );

  const series: BreakevenPoint[] = atlValues.map((atl, i) => {
    const nets: Record<string, number | null> = {};
    for (const r of perRule) nets[r.name] = r.results[i].computable ? r.results[i].net_benefit : null;
    return { atl, nets };
  });

  const currentIndex = Math.max(0, Math.min(STEPS, Math.round((atlNow / hi) * STEPS)));

  let crossIndex: number | null = null;
  let above = true;
  for (let d = 1; d <= STEPS; d++) {
    const upIdx = currentIndex + d;
    const downIdx = currentIndex - d;
    if (upIdx <= STEPS && leaderAt(series[upIdx]) !== heroName) {
      crossIndex = upIdx;
      above = true;
      break;
    }
    if (downIdx >= 0 && leaderAt(series[downIdx]) !== heroName) {
      crossIndex = downIdx;
      above = false;
      break;
    }
  }

  const rivalName =
    (crossIndex != null ? leaderAt(series[crossIndex]) : null) ??
    (() => {
      let best: string | null = null;
      let bestVal = -Infinity;
      for (const [name, v] of Object.entries(series[currentIndex].nets)) {
        if (name === heroName) continue;
        if (v != null && v > bestVal) {
          bestVal = v;
          best = name;
        }
      }
      return best;
    })();

  return {
    series,
    hi,
    heroName,
    atlNow,
    crossAtl: crossIndex != null ? series[crossIndex].atl : null,
    above,
    rivalName,
  };
}
