export interface ConstraintDef {
  key: string;
  label: string;
  /** Shown under the chip when toggled on. For a constraint the backend can't
   * actually evaluate (see backend/app/constraints.py's docstring on why
   * large_soundstage has no lookup table) — without this, greying nothing
   * out reads as the feature being broken rather than as "no evidence yet". */
  note?: string;
}

/** Matches BudgetVector.constraints strings — see backend/app/models.py. */
export const CONSTRAINTS: ConstraintDef[] = [
  { key: "coastline", label: "Needs ocean coastline" },
  {
    key: "large_soundstage",
    label: "Needs a soundstage above 20,000 sq ft",
    note: "Not yet evaluated — no reliable facilities data source, so this never greys out a jurisdiction.",
  },
  { key: "spring_only", label: "Cast available spring 2027 only" },
];
