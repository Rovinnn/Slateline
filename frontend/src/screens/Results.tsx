import { useEffect, useRef, useState } from "react";
import { ApiError, computeBenefit, getSeedJurisdictions } from "../lib/api";
import { hostOf, money, moneyShort } from "../lib/format";
import { DEFAULT_RELOCATION_ASSUMPTIONS } from "../types";
import type { BenefitBreakdown, BudgetVector, JurisdictionRule, PoolStatus, RelocationAssumptions } from "../types";

interface Row {
  rule: JurisdictionRule;
  benefit: BenefitBreakdown;
}

type LoadState = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; rows: Row[] };

const POOL_STATUS_LABEL: Record<PoolStatus, string> = {
  open: "Funding open",
  capping_out: "Capping out",
  closed: "Closed",
  unknown: "Status unknown",
};

const POOL_STATUS_CLASS: Record<PoolStatus, string> = {
  open: "border-teal/20 bg-teal-bg text-teal",
  capping_out: "border-amber/20 bg-amber-bg text-amber",
  closed: "border-red/20 bg-red-bg text-red",
  unknown: "border-border-2 bg-card-2 text-ink-3",
};

const RECOMPUTE_DEBOUNCE_MS = 200;

export function Results({ budget: initialBudget, onEditInputs }: { budget: BudgetVector; onEditInputs: () => void }) {
  const [rules, setRules] = useState<JurisdictionRule[] | null>(null);
  const [liveBudget, setLiveBudget] = useState<BudgetVector>(initialBudget);
  const [assumptions, setAssumptions] = useState<RelocationAssumptions>(DEFAULT_RELOCATION_ASSUMPTIONS);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [showAll, setShowAll] = useState(false);
  const [showUnverified, setShowUnverified] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Fetched once — the seed jurisdiction list doesn't depend on the budget.
  useEffect(() => {
    let cancelled = false;
    getSeedJurisdictions()
      .then((r) => !cancelled && setRules(r))
      .catch((err) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError ? `${err.message} (HTTP ${err.status})` : "Could not reach the backend.";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Layer 2 is a pure function with no I/O of its own, so recomputing on every
  // slider tick still means "no model call" per BUILD_BRIEF.md section 7 — it
  // just goes through the real backend (single source of truth for the
  // arithmetic) rather than a second, TypeScript copy of compute_benefit that
  // could drift from it.
  useEffect(() => {
    if (!rules) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      let cancelled = false;
      (async () => {
        try {
          const rows = await Promise.all(
            rules.map(async (rule) => ({ rule, benefit: await computeBenefit(liveBudget, rule, { assumptions }) })),
          );
          if (!cancelled) setState({ status: "ready", rows });
        } catch (err) {
          if (cancelled) return;
          const message =
            err instanceof ApiError ? `${err.message} (HTTP ${err.status})` : "Could not reach the backend.";
          setState({ status: "error", message });
        }
      })();
      return () => {
        cancelled = true;
      };
    }, RECOMPUTE_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [rules, liveBudget, assumptions]);

  return (
    <div className="mx-auto max-w-[1320px] px-7 pb-20">
      <div className="flex items-center gap-5 pt-4">
        <div className="font-sans text-[12.5px] text-ink-2">
          {moneyShort(liveBudget.total)} budget · {liveBudget.shoot_days} days · {liveBudget.crew_headcount} crew
        </div>
        <button
          type="button"
          onClick={onEditInputs}
          className="ml-auto font-mono text-[11.5px] text-teal underline decoration-1 underline-offset-2"
        >
          edit inputs
        </button>
      </div>

      {state.status === "loading" && (
        <div className="flex items-center gap-3 py-24">
          <div className="h-4.5 w-4.5 animate-spin rounded-full border-2 border-border border-t-ink" />
          <div className="font-mono text-[12.5px] text-ink-2">Computing net benefit across jurisdictions…</div>
        </div>
      )}

      {state.status === "error" && (
        <div className="mt-6 border border-red/30 border-t-2 border-t-red bg-card p-6">
          <div className="mb-1.5 font-sans text-[15px] font-semibold text-red">Couldn't compute results</div>
          <p className="font-sans text-[13.5px] leading-relaxed text-[#57534c]">{state.message}</p>
        </div>
      )}

      {state.status === "ready" && (
        <ReadyResults
          rows={state.rows}
          liveBudget={liveBudget}
          initialBudget={initialBudget}
          onBudgetChange={setLiveBudget}
          assumptions={assumptions}
          onAssumptionsChange={setAssumptions}
          showAll={showAll}
          setShowAll={setShowAll}
          showUnverified={showUnverified}
          setShowUnverified={setShowUnverified}
        />
      )}
    </div>
  );
}

// Note: budget.constraints (e.g. "coastline") isn't used to grey out
// jurisdictions here yet. BUILD_BRIEF.md section 7 wants that, but
// JurisdictionRule (section 5) has no field saying whether a jurisdiction
// satisfies a given constraint — that needs a schema decision (e.g. a new
// `capabilities: dict` on JurisdictionRule, filled by Layer 1) before it can
// be built honestly rather than guessed.

function ReadyResults({
  rows,
  liveBudget,
  initialBudget,
  onBudgetChange,
  assumptions,
  onAssumptionsChange,
  showAll,
  setShowAll,
  showUnverified,
  setShowUnverified,
}: {
  rows: Row[];
  liveBudget: BudgetVector;
  initialBudget: BudgetVector;
  onBudgetChange: (b: BudgetVector) => void;
  assumptions: RelocationAssumptions;
  onAssumptionsChange: (a: RelocationAssumptions) => void;
  showAll: boolean;
  setShowAll: (v: boolean) => void;
  showUnverified: boolean;
  setShowUnverified: (v: boolean) => void;
}) {
  const computable = rows.filter((r) => r.benefit.computable).sort((a, b) => b.benefit.net_benefit - a.benefit.net_benefit);
  const unverified = rows.filter((r) => !r.benefit.computable);

  if (computable.length === 0) {
    return (
      <div className="mt-6 border border-border-3 bg-card p-6 font-sans text-[13.5px] text-ink-2">
        None of the {rows.length} jurisdictions in the seed set could be computed for this budget — see "Can't
        verify" below.
      </div>
    );
  }

  const [hero, ...rest] = computable;
  const runnerUps = showAll ? rest : rest.slice(0, 3);

  return (
    <div className="pt-5">
      <div className="mb-2.5 font-mono text-[11px] font-medium tracking-wide text-ink-3">
        RECOMMENDATION · RANKED BY NET BENEFIT
      </div>

      <HeroCard row={hero} />

      <SensitivityPanel liveBudget={liveBudget} initialBudget={initialBudget} onChange={onBudgetChange} />

      <RelocationAssumptionsPanel assumptions={assumptions} onChange={onAssumptionsChange} />

      {rest.length > 0 && (
        <>
          <div className="mb-2.5 mt-7 flex items-baseline gap-3.5">
            <div className="font-mono text-[11px] font-medium tracking-wide text-ink-3">RUNNERS-UP</div>
            <button
              type="button"
              onClick={() => setShowAll(!showAll)}
              className="font-mono text-[11.5px] text-teal underline decoration-1 underline-offset-2"
            >
              {showAll ? "show top 3 only" : `show all ${rest.length} compared`}
            </button>
          </div>
          <div className="flex flex-col gap-2.5">
            {runnerUps.map((row, i) => (
              <RunnerUpCard key={row.rule.jurisdiction} row={row} rank={i + 2} best={hero.benefit.net_benefit} />
            ))}
          </div>
        </>
      )}

      {unverified.length > 0 && (
        <div className="mt-6.5 border border-border bg-card">
          <button
            type="button"
            onClick={() => setShowUnverified(!showUnverified)}
            className="flex w-full items-center gap-3 bg-card-2 px-5 py-3.5 text-left"
          >
            <span className="font-mono text-[11px] text-ink-3">{showUnverified ? "−" : "+"}</span>
            <span className="font-sans text-[13.5px] font-semibold">
              Can't verify — {unverified.length} excluded from the ranking
            </span>
            <span className="font-sans text-[12.5px] text-ink-2">Discretionary or unverifiable programs. Not scored, not hidden.</span>
          </button>
          {showUnverified && (
            <div className="border-t border-[#eae8e1]">
              {unverified.map(({ rule, benefit }) => {
                const src = rule.sources.find((s) => s.is_primary) ?? rule.sources[0];
                return (
                  <div key={rule.jurisdiction} className="grid grid-cols-1 gap-3 border-b border-[#efede7] p-4 sm:grid-cols-[1.1fr_2fr_1.2fr]">
                    <div>
                      <div className="font-sans text-[13.5px] font-semibold">{rule.jurisdiction}</div>
                      <div className="mt-0.5 font-mono text-[11.5px] text-ink-4">{rule.program_name}</div>
                    </div>
                    <div className="font-sans text-[13px] leading-relaxed text-[#57534c]">
                      {benefit.non_computable_reason}
                    </div>
                    {src && (
                      <div className="flex items-baseline gap-1.5 font-mono text-[11.5px] text-ink-4">
                        <a href={src.url} target="_blank" rel="noopener" className="text-teal underline decoration-1 underline-offset-2">
                          {hostOf(src.url)}
                        </a>
                        <span>· retrieved {src.retrieved}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="mt-6 max-w-[820px] font-mono text-[11.5px] leading-relaxed text-ink-3">
        Figures are estimates for comparison, not tax advice. Non-machine-checkable uplifts are listed but not
        added to the credit — confirm them with the film office. Relocation cost excludes flights/ground
        transport until Google Maps distance is wired in (see caps_applied notes above where that applies).
      </div>
    </div>
  );
}

function num(raw: string): number {
  const n = parseFloat(raw);
  return Number.isNaN(n) ? 0 : n;
}

/**
 * BUILD_BRIEF.md section 7: "Sensitivity sliders for ATL spend and
 * resident-labor %... recompute on every change." The debounced /compute
 * round-trip in Results() above is what actually recomputes; this just
 * turns slider drags into BudgetVector edits.
 */
function SensitivityPanel({
  liveBudget,
  initialBudget,
  onChange,
}: {
  liveBudget: BudgetVector;
  initialBudget: BudgetVector;
  onChange: (b: BudgetVector) => void;
}) {
  const atlBase = initialBudget.atl_cast + initialBudget.atl_noncast;
  const atlMax = Math.max(atlBase * 2.5, 4_000_000);
  const atlNow = liveBudget.atl_cast + liveBudget.atl_noncast;
  const atlShare = atlNow > 0 ? liveBudget.atl_cast / atlNow : 0.65;

  function setAtlSpend(v: number) {
    onChange({
      ...liveBudget,
      atl_cast: v * atlShare,
      atl_noncast: v * (1 - atlShare),
      total: v + liveBudget.btl_labor + liveBudget.btl_nonlabor + liveBudget.post_vfx,
    });
  }

  function setResidentPct(pct: number) {
    onChange({ ...liveBudget, resident_labor_pct: Math.max(0, Math.min(100, pct)) / 100 });
  }

  return (
    <div className="mt-5 border border-border-3 bg-card">
      <div className="flex flex-wrap items-baseline gap-3.5 border-b border-[#eae8e1] bg-card-2 px-5.5 py-3.5">
        <div className="font-sans text-[13.5px] font-semibold">Sensitivity</div>
        <div className="font-sans text-[12.5px] text-ink-2">Drag to recompute. Ranking reorders live.</div>
      </div>

      <div className="grid grid-cols-1 gap-6 p-5.5 sm:grid-cols-2">
        <div>
          <div className="mb-0.5 flex items-baseline justify-between gap-3">
            <span className="font-sans text-[12.5px] font-medium text-[#3d3a34]">ATL spend (cast + non-cast)</span>
            <span className="font-mono text-[15px] font-semibold">{moneyShort(atlNow)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={Math.round(atlMax)}
            step={Math.max(10_000, Math.round(atlMax / 400))}
            value={Math.round(atlNow)}
            onChange={(e) => setAtlSpend(num(e.target.value))}
            className="w-full accent-ink"
          />
          <div className="flex justify-between font-mono text-[10.5px] text-ink-3">
            <span>$0</span>
            <span>{moneyShort(atlMax)}</span>
          </div>
        </div>

        <div>
          <div className="mb-0.5 flex items-baseline justify-between gap-3">
            <span className="font-sans text-[12.5px] font-medium text-[#3d3a34]">Resident labor share of BTL</span>
            <span className="font-mono text-[15px] font-semibold">{Math.round(liveBudget.resident_labor_pct * 100)}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round(liveBudget.resident_labor_pct * 100)}
            onChange={(e) => setResidentPct(num(e.target.value))}
            className="w-full accent-ink"
          />
          <div className="flex justify-between font-mono text-[10.5px] text-ink-3">
            <span>0%</span>
            <span>100%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface AssumptionField {
  key: keyof RelocationAssumptions;
  label: string;
  prefix?: string;
  suffix?: string;
  step: number;
  note: string;
  /** UI shows percent 0-100; state stores a 0-1 fraction. */
  isPercent?: boolean;
}

const ASSUMPTION_FIELDS: AssumptionField[] = [
  { key: "flight_threshold_km", label: "Flight threshold", suffix: "km", step: 10, note: "below this, ground travel only" },
  { key: "flight_cost_per_person", label: "Airfare base", prefix: "$", step: 10, note: "per traveller, round trip" },
  { key: "ground_cost_per_person_per_km", label: "Ground transport", prefix: "$", suffix: "/km", step: 0.01, note: "per traveller-km, under threshold" },
  { key: "per_diem_per_person_per_day", label: "Per diem", prefix: "$", step: 5, note: "per traveller, per shoot day" },
  { key: "hotel_per_person_per_day", label: "Hotel", prefix: "$", step: 5, note: "per traveller, per shoot day" },
  { key: "equipment_shipping_base", label: "Equipment shipping", prefix: "$", step: 500, note: "flat, per production" },
  { key: "imported_crew_pct", label: "Crew relocating", suffix: "%", step: 1, note: "fraction of crew_headcount that travels", isPercent: true },
];

/** BUILD_BRIEF.md section 6: "Every assumption must be visible and editable in the UI." */
function RelocationAssumptionsPanel({
  assumptions,
  onChange,
}: {
  assumptions: RelocationAssumptions;
  onChange: (a: RelocationAssumptions) => void;
}) {
  const [open, setOpen] = useState(false);

  function setField(key: keyof RelocationAssumptions, raw: string) {
    const parsed = num(raw);
    onChange({ ...assumptions, [key]: ASSUMPTION_FIELDS.find((f) => f.key === key)?.isPercent ? parsed / 100 : parsed });
  }

  return (
    <div className="mt-5 border border-border-3 bg-card">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2.5 bg-card-2 px-5.5 py-3.5 text-left"
      >
        <span className="font-mono text-[11px] text-ink-3">{open ? "−" : "+"}</span>
        <span className="font-sans text-[13.5px] font-semibold">Relocation cost assumptions</span>
        <span className="font-mono text-[11.5px] text-ink-2">
          flights over {Math.round(assumptions.flight_threshold_km)} km · ${Math.round(assumptions.per_diem_per_person_per_day + assumptions.hotel_per_person_per_day)}/day per traveller
        </span>
      </button>
      {open && (
        <div className="grid grid-cols-1 gap-4 p-5.5 sm:grid-cols-3 lg:grid-cols-4">
          {ASSUMPTION_FIELDS.map((f) => {
            const raw = f.isPercent ? assumptions[f.key] * 100 : assumptions[f.key];
            return (
              <label key={f.key} className="block">
                <div className="mb-1.5 font-sans text-[11.5px] font-medium text-[#3d3a34]">{f.label}</div>
                <div className="flex items-center border border-border-2 bg-card-2">
                  {f.prefix && <span className="pl-2 font-mono text-[12px] text-ink-3">{f.prefix}</span>}
                  <input
                    type="number"
                    step={f.step}
                    min={0}
                    value={raw}
                    onChange={(e) => setField(f.key, e.target.value)}
                    className="min-w-0 flex-1 bg-transparent px-2 py-2 text-right font-mono text-[13px] font-medium text-ink outline-none"
                  />
                  {f.suffix && <span className="pr-2 font-mono text-[12px] text-ink-3">{f.suffix}</span>}
                </div>
                <div className="mt-1 font-mono text-[10.5px] text-ink-3">{f.note}</div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function HeroCard({ row }: { row: Row }) {
  const { rule, benefit } = row;
  const src = rule.sources.find((s) => s.is_primary) ?? rule.sources[0];
  return (
    <div className="border border-[#bdbab2] border-t-[3px] border-t-ink bg-card">
      <div className="grid grid-cols-1 gap-8 p-7 lg:grid-cols-[1.25fr_1fr]">
        <div>
          <div className="mb-0.5 flex flex-wrap items-baseline gap-3">
            <h2 className="font-sans text-[27px] font-semibold tracking-tight">{rule.jurisdiction}</h2>
            <span className={`border px-1.5 py-1 font-mono text-[10.5px] font-medium uppercase tracking-wide ${POOL_STATUS_CLASS[rule.pool_status]}`}>
              {POOL_STATUS_LABEL[rule.pool_status]}
            </span>
          </div>
          <div className="mb-5 font-mono text-[12.5px] text-ink-2">{rule.program_name}</div>

          <div className="mb-1 font-mono text-[11px] font-medium tracking-wide text-ink-3">NET BENEFIT</div>
          <div className="mb-2.5 font-mono text-[48px] font-semibold leading-none tracking-tight">
            {moneyShort(benefit.net_benefit)}
          </div>
          <div className="border-b border-[#eae8e1] pb-4 font-mono text-[14px] text-[#3d3a34]">
            {money(benefit.gross_credit)} gross credit − {money(benefit.relocation_cost)} relocation = {money(benefit.net_benefit)}
          </div>

          {benefit.caps_applied.length > 0 && (
            <div className="flex flex-col gap-1.5 border-b border-[#eae8e1] py-4">
              {benefit.caps_applied.map((note, i) => (
                <div key={i} className="font-mono text-[11.5px] leading-relaxed text-ink-2">
                  {note}
                </div>
              ))}
            </div>
          )}

          {benefit.distance_km == null && (
            <div className="pt-3 font-mono text-[11px] text-ink-3">
              Distance from home base not available yet — Google Maps integration pending, so relocation cost
              above excludes flights/ground transport.
            </div>
          )}
        </div>

        <div className="border-l border-[#eae8e1] pl-7">
          <div className="flex flex-col gap-3.5">
            <Fact k="HEADLINE RATE" v={`${(rule.base_rate * 100).toFixed(1)}%`} />
            <Fact k="MINIMUM SPEND" v={rule.minimum_spend != null ? money(rule.minimum_spend) : "none"} />
            <Fact k="QUALIFIED SPEND USED" v={money(benefit.qualifying_spend)} />
            <Fact k="CONFIDENCE" v={rule.confidence.replace("_", " ")} />
          </div>
          {src && (
            <div className="mt-4.5 flex flex-wrap items-baseline gap-1.5 border-t border-[#eae8e1] pt-3.5 font-mono text-[11.5px] text-ink-4">
              <a href={src.url} target="_blank" rel="noopener" className="text-teal underline decoration-1 underline-offset-2">
                {hostOf(src.url)}
              </a>
              <span>· retrieved {src.retrieved}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Fact({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="mb-1 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">{k}</div>
      <div className="font-sans text-[13px] text-ink">{v}</div>
    </div>
  );
}

function RunnerUpCard({ row, rank, best }: { row: Row; rank: number; best: number }) {
  const { rule, benefit } = row;
  const src = rule.sources.find((s) => s.is_primary) ?? rule.sources[0];
  return (
    <div className="border border-border-3 bg-card">
      <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-[34px_1.6fr_1fr_1fr]">
        <div className="font-mono text-[13px] text-ink-3">{String(rank).padStart(2, "0")}</div>
        <div>
          <div className="flex flex-wrap items-baseline gap-2.5">
            <span className="font-sans text-[16px] font-semibold tracking-tight">{rule.jurisdiction}</span>
            <span className={`border px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide ${POOL_STATUS_CLASS[rule.pool_status]}`}>
              {POOL_STATUS_LABEL[rule.pool_status]}
            </span>
          </div>
          <div className="mt-1 font-mono text-[11.5px] text-ink-4">{(rule.base_rate * 100).toFixed(1)}% base rate</div>
        </div>
        <div>
          <div className="mb-1 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">QUALIFIED SPEND</div>
          <div className="font-mono text-[13px]">{money(benefit.qualifying_spend)}</div>
        </div>
        <div className="text-right">
          <div className="mb-1 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">NET BENEFIT</div>
          <div className="font-mono text-[20px] font-semibold tracking-tight">{moneyShort(benefit.net_benefit)}</div>
          <div className="mt-1 font-mono text-[11.5px] text-ink-4">{moneyShort(benefit.net_benefit - best)} vs top</div>
        </div>
      </div>
      {src && (
        <div className="flex items-baseline gap-1.5 border-t border-[#efede7] bg-card-2 px-4 py-2 font-mono text-[11.5px] text-ink-4">
          <a href={src.url} target="_blank" rel="noopener" className="text-teal underline decoration-1 underline-offset-2">
            {hostOf(src.url)}
          </a>
          <span>· retrieved {src.retrieved}</span>
        </div>
      )}
    </div>
  );
}
