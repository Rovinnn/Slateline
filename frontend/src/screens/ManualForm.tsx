import { useState } from "react";
import { CONSTRAINTS } from "../data/constraints";
import { HOME_BASES } from "../data/examples";
import type { BudgetVector } from "../types";

interface MoneyField {
  key: "total" | "atl_cast" | "atl_noncast" | "btl_labor" | "btl_nonlabor" | "post_vfx";
  label: string;
}

const MONEY_FIELDS: MoneyField[] = [
  { key: "total", label: "Total budget" },
  { key: "atl_cast", label: "ATL — cast" },
  { key: "atl_noncast", label: "ATL — non-cast" },
  { key: "btl_labor", label: "BTL — labor" },
  { key: "btl_nonlabor", label: "BTL — non-labor" },
  { key: "post_vfx", label: "Post / VFX" },
];

function parseNumber(raw: string): number {
  const n = parseFloat(raw.replace(/[^0-9.-]/g, ""));
  return Number.isNaN(n) ? 0 : n;
}

function formatMoney(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

function describedBy(...ids: (string | undefined | false)[]): string | undefined {
  const joined = ids.filter(Boolean).join(" ");
  return joined || undefined;
}

export function ManualForm({
  initial,
  onBack,
  onSubmit,
  fieldNotes,
  warnings,
  sourceLabel,
}: {
  initial: BudgetVector;
  onBack: () => void;
  onSubmit: (budget: BudgetVector) => void;
  /** Field name -> where an uploaded PDF's figure came from. BUILD_BRIEF.md
   *  section 7: "each parsed field annotated with where it came from". */
  fieldNotes?: Record<string, string>;
  /** Figures the parse couldn't find, or anything else worth checking. */
  warnings?: string[];
  /** Filename an upload came from, shown so it's clear these are parsed values. */
  sourceLabel?: string;
}) {
  const [budget, setBudget] = useState<BudgetVector>(initial);
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
    Object.fromEntries(MONEY_FIELDS.map((f) => [f.key, formatMoney(initial[f.key])])),
  );

  function setMoneyField(key: MoneyField["key"], raw: string) {
    setDrafts((d) => ({ ...d, [key]: raw }));
    setBudget((b) => ({ ...b, [key]: parseNumber(raw) }));
  }

  function blurMoneyField(key: MoneyField["key"]) {
    setDrafts((d) => ({ ...d, [key]: formatMoney(budget[key]) }));
  }

  function toggleConstraint(key: string) {
    setBudget((b) => ({
      ...b,
      constraints: b.constraints.includes(key) ? b.constraints.filter((c) => c !== key) : [...b.constraints, key],
    }));
  }

  const categorySum = budget.atl_cast + budget.atl_noncast + budget.btl_labor + budget.btl_nonlabor + budget.post_vfx;
  const diff = budget.total - categorySum;
  const reconciles = Math.abs(diff) < 1;

  // Two different kinds of wrong, treated differently on purpose.
  //
  // A negative budget line is impossible, and the backend now refuses to
  // compute against one (see calculator._impossible_inputs). Left unblocked,
  // the producer would submit and get "can't verify" on every jurisdiction
  // at once with no hint that one typo upstream caused it — so it's caught
  // here, where the offending field is on screen.
  //
  // An unreconciled total is merely inconsistent. `total` never enters the
  // arithmetic — qualifying spend is built from the category lines — so
  // blocking on it would refuse a budget the tool can price perfectly well.
  // It stays a warning.
  const negativeFields = MONEY_FIELDS.filter((f) => budget[f.key] < 0);
  const blocked = negativeFields.length > 0;

  return (
    <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="mb-1.5 font-sans text-[22px] font-semibold tracking-tight">
            Budget and production parameters
          </h1>
          <p className="font-sans text-[13.5px] text-ink-2">
            {sourceLabel
              ? `Figures read from ${sourceLabel}. Each carries the line it came from — correct anything before continuing.`
              : "Enter what you have. Blank lines are treated as zero and flagged in the sum check."}
          </p>
        </div>
        <div className="flex gap-2.5">
          <button
            type="button"
            onClick={onBack}
            className="border border-border-2 bg-card px-4 py-2.5 font-mono text-[12px] font-medium tracking-wide text-ink transition-colors hover:border-ink"
          >
            BACK
          </button>
          <button
            type="button"
            onClick={() => onSubmit(budget)}
            disabled={blocked}
            title={blocked ? `Negative spend on ${negativeFields.map((f) => f.label).join(", ")}` : undefined}
            className="bg-ink px-5 py-2.5 font-mono text-[12px] font-medium tracking-wide text-paper transition-all hover:-translate-y-px hover:bg-[var(--color-ink-deep)] hover:shadow-md disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:bg-ink disabled:hover:shadow-none"
          >
            RUN COMPARISON
          </button>
        </div>
      </div>

      {warnings && warnings.length > 0 && (
        <div className="mb-5 border border-amber/30 bg-amber-bg px-4 py-3">
          <div className="mb-1.5 font-mono text-[11px] font-medium tracking-wide text-amber">
            CHECK THESE — {warnings.length} {warnings.length === 1 ? "ITEM" : "ITEMS"}
          </div>
          <ul className="flex flex-col gap-1">
            {warnings.map((w, i) => (
              <li key={i} className="font-sans text-[12.5px] leading-relaxed text-[var(--color-text-muted-2)]">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.55fr_1fr]">
        <section className="border border-border bg-card p-5.5">
          <div className="mb-4 font-mono text-[11px] font-medium tracking-wide text-ink-3">BUDGET LINES</div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {MONEY_FIELDS.map((f) => (
              <label key={f.key} className="block">
                <div className="mb-1.5 flex items-baseline justify-between gap-2">
                  <span className="font-sans text-[12.5px] font-medium text-[var(--color-text-muted)]">{f.label}</span>
                  <span className="font-mono text-[10.5px] text-ink-3">USD</span>
                </div>
                <div className="flex items-center border border-border-2 bg-card-2">
                  <span className="px-2 font-mono text-[12.5px] text-ink-3">$</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={drafts[f.key]}
                    onChange={(e) => setMoneyField(f.key, e.target.value)}
                    onBlur={() => blurMoneyField(f.key)}
                    aria-invalid={budget[f.key] < 0}
                    aria-describedby={describedBy(
                      fieldNotes?.[f.key] && `${f.key}-note`,
                      budget[f.key] < 0 && "budget-error",
                    )}
                    className="min-w-0 flex-1 bg-transparent py-2.5 pr-2.5 text-right font-mono text-[13.5px] font-medium text-ink outline-none"
                  />
                </div>
                {fieldNotes?.[f.key] && (
                  <div id={`${f.key}-note`} className="mt-1 font-mono text-[10.5px] text-ink-4">
                    read from {fieldNotes[f.key]}
                  </div>
                )}
              </label>
            ))}

            <label className="block">
              <div className="mb-1.5 flex items-baseline justify-between gap-2">
                <span className="font-sans text-[12.5px] font-medium text-[var(--color-text-muted)]">Shoot days</span>
                <span className="font-mono text-[10.5px] text-ink-3">days</span>
              </div>
              <div className="flex items-center border border-border-2 bg-card-2">
                <input
                  type="number"
                  min={1}
                  value={budget.shoot_days}
                  onChange={(e) => setBudget((b) => ({ ...b, shoot_days: parseNumber(e.target.value) }))}
                  className="min-w-0 flex-1 bg-transparent px-2.5 py-2.5 text-right font-mono text-[13.5px] font-medium text-ink outline-none"
                />
              </div>
            </label>

            <label className="block">
              <div className="mb-1.5 flex items-baseline justify-between gap-2">
                <span className="font-sans text-[12.5px] font-medium text-[var(--color-text-muted)]">Crew headcount</span>
                <span className="font-mono text-[10.5px] text-ink-3">people</span>
              </div>
              <div className="flex items-center border border-border-2 bg-card-2">
                <input
                  type="number"
                  min={1}
                  value={budget.crew_headcount}
                  onChange={(e) => setBudget((b) => ({ ...b, crew_headcount: parseNumber(e.target.value) }))}
                  className="min-w-0 flex-1 bg-transparent px-2.5 py-2.5 text-right font-mono text-[13.5px] font-medium text-ink outline-none"
                />
              </div>
            </label>

            <label className="block">
              <div className="mb-1.5 flex items-baseline justify-between gap-2">
                <span className="font-sans text-[12.5px] font-medium text-[var(--color-text-muted)]">Fringes / payroll burden</span>
                <span className="font-mono text-[10.5px] text-ink-3">% of wages</span>
              </div>
              <div className="flex items-center border border-border-2 bg-card-2">
                <input
                  type="number"
                  min={0}
                  max={60}
                  value={Math.round(budget.fringe_rate * 100)}
                  onChange={(e) =>
                    setBudget((b) => ({
                      ...b,
                      fringe_rate: Math.max(0, Math.min(60, parseNumber(e.target.value))) / 100,
                    }))
                  }
                  className="min-w-0 flex-1 bg-transparent px-2.5 py-2.5 text-right font-mono text-[13.5px] font-medium text-ink outline-none"
                />
                <span className="pr-2.5 font-mono text-[12.5px] text-ink-3">%</span>
              </div>
              <div className="mt-1 font-mono text-[10.5px] text-ink-4">
                employer taxes, union pension/health, workers' comp — 28% is typical on a union feature
              </div>
            </label>

            <label className="block">
              <div className="mb-1.5 flex items-baseline justify-between gap-2">
                <span className="font-sans text-[12.5px] font-medium text-[var(--color-text-muted)]">Resident labor share</span>
                <span className="font-mono text-[10.5px] text-ink-3">% of BTL labor</span>
              </div>
              <div className="flex items-center border border-border-2 bg-card-2">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={Math.round(budget.resident_labor_pct * 100)}
                  onChange={(e) =>
                    setBudget((b) => ({ ...b, resident_labor_pct: Math.max(0, Math.min(100, parseNumber(e.target.value))) / 100 }))
                  }
                  className="min-w-0 flex-1 bg-transparent px-2.5 py-2.5 text-right font-mono text-[13.5px] font-medium text-ink outline-none"
                />
                <span className="pr-2.5 font-mono text-[12.5px] text-ink-3">%</span>
              </div>
            </label>
          </div>

          {blocked && (
            <div
              id="budget-error"
              className="mt-4.5 border border-red/30 bg-red-bg px-3 py-2.5 font-mono text-[11.5px] leading-relaxed text-red"
            >
              {negativeFields.map((f) => f.label).join(" and ")}{" "}
              {negativeFields.length > 1 ? "are" : "is"} negative. A budget line can't be below zero, and no
              credit can be computed against one — correct it to continue.
            </div>
          )}

          <div className="mt-4.5 flex justify-between gap-3.5 border-t border-[var(--color-hairline)] pt-3.5">
            <div className="font-mono text-[12px] text-ink-2">CATEGORY SUM</div>
            <div className={`font-mono text-[12px] font-medium ${reconciles ? "text-teal" : "text-amber"}`}>
              {reconciles
                ? `$${formatMoney(categorySum)} · reconciles to total`
                : `$${formatMoney(categorySum)} · $${formatMoney(Math.abs(diff))} ${diff > 0 ? "unallocated" : "over total"}`}
            </div>
          </div>
        </section>

        <div className="flex flex-col gap-5">
          <section className="border border-border bg-card p-5.5">
            <label htmlFor="home-base-select" className="mb-3.5 block font-mono text-[11px] font-medium tracking-wide text-ink-3">
              HOME BASE
            </label>
            <select
              id="home-base-select"
              value={budget.home_base}
              onChange={(e) => setBudget((b) => ({ ...b, home_base: e.target.value }))}
              className="w-full border border-border-2 bg-card-2 px-2.5 py-2.5 font-mono text-[13px] font-medium text-ink outline-none"
            >
              {HOME_BASES.map((h) => (
                <option key={h.id} value={h.label}>
                  {h.label}
                </option>
              ))}
            </select>
            <div className="mt-2 font-mono text-[10.5px] text-ink-2">
              Distances and travel time are measured hub to hub from {budget.home_base}.
            </div>
          </section>

          <section className="border border-border bg-card p-5.5">
            <div className="mb-1.5 font-mono text-[11px] font-medium tracking-wide text-ink-3">CONSTRAINTS · OPTIONAL</div>
            <p className="mb-3.5 font-sans text-[12.5px] leading-[1.45] text-ink-2">
              Constraints never delete a jurisdiction. They grey it out and state why.
            </p>
            <div className="flex flex-col gap-2.5">
              {CONSTRAINTS.map((c) => {
                const on = budget.constraints.includes(c.key);
                return (
                  <button
                    key={c.key}
                    type="button"
                    onClick={() => toggleConstraint(c.key)}
                    aria-pressed={on}
                    className={`flex w-full items-center gap-2.5 border px-3 py-2.5 text-left font-sans text-[12.5px] transition-all hover:-translate-y-px ${
                      on ? "border-ink bg-card-2" : "border-border-2 bg-card hover:border-ink"
                    }`}
                  >
                    <span
                      className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center border font-mono text-[9px] ${
                        on ? "border-ink" : "border-[var(--color-checkbox-border)]"
                      }`}
                    >
                      {on ? "■" : ""}
                    </span>
                    {c.label}
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
