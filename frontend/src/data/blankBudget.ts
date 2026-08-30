import type { BudgetVector } from "../types";
import { HOME_BASES } from "./examples";

/** "Blank lines are treated as zero" — matches the design canvas's manual-entry default. */
export function makeBlankBudget(): BudgetVector {
  return {
    total: 0,
    atl_cast: 0,
    atl_noncast: 0,
    btl_labor: 0,
    btl_nonlabor: 0,
    post_vfx: 0,
    shoot_days: 1,
    crew_headcount: 1,
    resident_labor_pct: 0,
    home_base: HOME_BASES[0].label,
    constraints: [],
  };
}
