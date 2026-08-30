export interface ConstraintDef {
  key: string;
  label: string;
}

/** Matches BudgetVector.constraints strings — see backend/app/models.py. */
export const CONSTRAINTS: ConstraintDef[] = [
  { key: "coastline", label: "Needs ocean coastline" },
  { key: "large_soundstage", label: "Needs a soundstage above 20,000 sq ft" },
  { key: "spring_only", label: "Cast available spring 2027 only" },
];
