import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { CONSTRAINTS } from "../data/constraints";
import { DEFAULT_JURISDICTIONS } from "../data/examples";
import { ApiError, computeBenefit, getDistance, searchJurisdiction, type DistanceInfo } from "../lib/api";
import { scanBreakeven, type BreakevenResult } from "../lib/breakeven";
import { hostOf, money, moneyShort } from "../lib/format";
import { DEFAULT_RELOCATION_ASSUMPTIONS } from "../types";
import type { BenefitBreakdown, BudgetVector, JurisdictionRule, PoolStatus, RelocationAssumptions } from "../types";
import { MapView } from "./MapView";

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
  const [tab, setTab] = useState<"memo" | "map">("memo");
  const [breakeven, setBreakeven] = useState<BreakevenResult | "loading" | "error" | null>(null);
  const [distances, setDistances] = useState<Record<string, DistanceInfo | null>>({});
  const [printing, setPrinting] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const fetchedDistancesRef = useRef<Set<string>>(new Set());

  // Fetched once on mount — DEFAULT_JURISDICTIONS is just a list of names to
  // look up, not data. Each one runs the real Layer 1 pipeline (Parallel
  // search + Gemini extraction, see backend/app/extraction/agent.py), same
  // path as JurisdictionSearch below, in parallel. allSettled (not all): one
  // jurisdiction's search failing (a transient Parallel/Vertex error) leaves
  // it out rather than blanking the whole screen — only surface the error
  // state if every one of them failed.
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled(DEFAULT_JURISDICTIONS.map((name) => searchJurisdiction(name))).then((results) => {
      if (cancelled) return;
      const rules = results.flatMap((r) => (r.status === "fulfilled" ? [r.value] : []));
      if (rules.length === 0) {
        const firstError = results.find(
          (r): r is PromiseRejectedResult => r.status === "rejected",
        )?.reason;
        const message =
          firstError instanceof ApiError
            ? `${firstError.message} (HTTP ${firstError.status})`
            : "Could not reach the backend.";
        setState({ status: "error", message });
        return;
      }
      setRules(rules);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // One Maps call per (home_base, jurisdiction) pair, cached here for the
  // life of the Results screen — home_base itself can't change without
  // remounting this screen (only `onEditInputs` changes it, which goes back
  // to the form). Deliberately NOT folded into /compute: that endpoint is
  // hit on every sensitivity-slider debounce tick, and a Maps round trip on
  // every drag tick would be real added latency and quota cost for a number
  // that never changes while dragging. fetchedDistancesRef (not `distances`
  // itself) gates what's already requested, so this doesn't loop on its own
  // setDistances update.
  useEffect(() => {
    if (!rules) return;
    const homeBase = initialBudget.home_base;
    const toFetch = rules.filter((r) => !fetchedDistancesRef.current.has(r.jurisdiction));
    if (toFetch.length === 0) return;
    for (const r of toFetch) fetchedDistancesRef.current.add(r.jurisdiction);
    let cancelled = false;
    Promise.all(
      toFetch.map(async (rule) => {
        try {
          return [rule.jurisdiction, await getDistance(homeBase, rule.centroid_lat, rule.centroid_lng)] as const;
        } catch {
          // Maps outage or an unroutable home_base string — leave this one
          // jurisdiction without a distance rather than failing the screen.
          return [rule.jurisdiction, null] as const;
        }
      }),
    ).then((results) => {
      if (cancelled) return;
      setDistances((prev) => {
        const next = { ...prev };
        for (const [name, info] of results) next[name] = info;
        return next;
      });
    });
    return () => {
      cancelled = true;
    };
  }, [rules, initialBudget.home_base]);

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
            rules.map(async (rule) => {
              const dist = distances[rule.jurisdiction];
              return {
                rule,
                benefit: await computeBenefit(liveBudget, rule, {
                  assumptions,
                  distance_km: dist?.distance_km,
                  travel_time_hours: dist?.travel_time_hours,
                }),
              };
            }),
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
  }, [rules, liveBudget, assumptions, distances]);

  // Scans ATL spend to find where the top pick stops leading — a second,
  // coarser sweep than the main recompute above, so it rides the same
  // debounced trigger (state.status flips to "ready" after each recompute)
  // rather than firing its own independent request storm on every drag tick.
  useEffect(() => {
    if (state.status !== "ready" || !rules) return;
    const computable = state.rows.filter((r) => r.benefit.computable);
    if (computable.length < 2) {
      setBreakeven(null);
      return;
    }
    const hero = computable.reduce((a, b) => (b.benefit.net_benefit > a.benefit.net_benefit ? b : a));
    const atlBase = initialBudget.atl_cast + initialBudget.atl_noncast;
    let cancelled = false;
    setBreakeven("loading");
    scanBreakeven(rules, hero.rule.jurisdiction, liveBudget, atlBase, assumptions, distances)
      .then((result) => !cancelled && setBreakeven(result))
      .catch(() => !cancelled && setBreakeven("error"));
    return () => {
      cancelled = true;
    };
    // Deliberately keyed on `state` (not liveBudget/assumptions directly) so
    // this rides the main recompute's debounce instead of double-firing.
  }, [state, rules, distances]);

  // Expanding and printing can't happen in one handler: the panels have to be
  // committed and painted first, so this flips state, prints a beat later, and
  // collapses again on `afterprint`. Resetting on a timer instead raced the
  // render — the assumptions panel closed before the print snapshot was taken,
  // dropping it from the exported PDF.
  useEffect(() => {
    if (!printing) return;
    const done = () => setPrinting(false);
    window.addEventListener("afterprint", done);
    const timer = setTimeout(() => window.print(), 60);
    return () => {
      window.removeEventListener("afterprint", done);
      clearTimeout(timer);
    };
  }, [printing]);

  function addRule(rule: JurisdictionRule) {
    setRules((prev) => {
      const base = prev ?? [];
      const i = base.findIndex((r) => r.jurisdiction.toLowerCase() === rule.jurisdiction.toLowerCase());
      if (i === -1) return [...base, rule];
      const next = [...base];
      next[i] = rule;
      return next;
    });
  }

  return (
    <div className="mx-auto max-w-[1320px] px-7 pb-20">
      <div className="flex flex-wrap items-center gap-5 pt-4">
        <div className="flex gap-0.5 print:hidden">
          <TabButton active={tab === "memo"} onClick={() => setTab("memo")}>MEMO</TabButton>
          <TabButton active={tab === "map"} onClick={() => setTab("map")}>MAP</TabButton>
        </div>
        <div className="font-sans text-[12.5px] text-ink-2">
          {moneyShort(liveBudget.total)} budget · {liveBudget.shoot_days} days · {liveBudget.crew_headcount} crew
        </div>
        {rules && (
          <div className="print:hidden">
            <JurisdictionSearch existing={rules.map((r) => r.jurisdiction)} onFound={addRule} />
          </div>
        )}
        <div className="ml-auto flex items-center gap-4 print:hidden">
          <button
            type="button"
            onClick={() => setPrinting(true)}
            disabled={state.status !== "ready" || printing}
            title="Opens your browser's print dialog — choose 'Save as PDF'"
            className="border border-border-2 bg-card px-3 py-1.5 font-mono text-[11px] font-medium tracking-wide text-ink transition-colors hover:border-ink disabled:opacity-40"
          >
            {printing ? "PREPARING…" : "EXPORT PDF"}
          </button>
          <button
            type="button"
            onClick={onEditInputs}
            className="font-mono text-[11.5px] text-teal underline decoration-1 underline-offset-2"
          >
            edit inputs
          </button>
        </div>
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

      {state.status === "ready" && tab === "memo" && (
        <ReadyResults
          rows={state.rows}
          liveBudget={liveBudget}
          initialBudget={initialBudget}
          onBudgetChange={setLiveBudget}
          assumptions={assumptions}
          onAssumptionsChange={setAssumptions}
          breakeven={breakeven}
          printing={printing}
          showAll={showAll}
          setShowAll={setShowAll}
          showUnverified={showUnverified}
          setShowUnverified={setShowUnverified}
        />
      )}

      {state.status === "ready" && tab === "map" && <MapView rows={state.rows} homeBaseLabel={liveBudget.home_base} />}
    </div>
  );
}

/**
 * Layer 1, live: calls /jurisdictions/search (Parallel + Gemini extraction,
 * see backend/app/extraction/agent.py), then folds the result into `rules`
 * via onFound so it flows through the same compute/distance pipeline as the
 * seed jurisdictions — no separate rendering path for a searched-up rule.
 */
function JurisdictionSearch({ existing, onFound }: { existing: string[]; onFound: (rule: JurisdictionRule) => void }) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const name = value.trim();
    if (!name || pending) return;
    if (existing.some((n) => n.toLowerCase() === name.toLowerCase())) {
      setError(`${name} is already in the comparison.`);
      return;
    }
    setPending(true);
    setError(null);
    try {
      onFound(await searchJurisdiction(name));
      setValue("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the backend.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="search another jurisdiction…"
        disabled={pending}
        className="w-[210px] border border-border-3 bg-card px-2.5 py-1 font-mono text-[11.5px] outline-none focus:border-ink disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={pending || !value.trim()}
        className="font-mono text-[11.5px] text-teal underline decoration-1 underline-offset-2 disabled:opacity-40 disabled:no-underline"
      >
        {pending ? "searching…" : "search"}
      </button>
      {error && <span className="font-mono text-[11px] text-red">{error}</span>}
    </form>
  );
}

/**
 * The reason `constraints` currently enabled on the budget disqualify this
 * rule, if any — backend/app/constraints.py fills rule.constraint_gaps for
 * every constraint key it can determine without guessing (not every key is
 * covered; see that module for which ones and why). Constraints never
 * remove a jurisdiction from the list, only grey it out with this reason.
 */
function failingConstraint(rule: JurisdictionRule, activeConstraints: string[]): string | null {
  for (const key of activeConstraints) {
    const reason = rule.constraint_gaps[key];
    if (reason) return reason;
  }
  return null;
}

function ReadyResults({
  rows,
  liveBudget,
  initialBudget,
  onBudgetChange,
  assumptions,
  onAssumptionsChange,
  breakeven,
  printing,
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
  breakeven: BreakevenResult | "loading" | "error" | null;
  printing: boolean;
  showAll: boolean;
  setShowAll: (v: boolean) => void;
  showUnverified: boolean;
  setShowUnverified: (v: boolean) => void;
}) {
  const computable = rows.filter((r) => r.benefit.computable).sort((a, b) => b.benefit.net_benefit - a.benefit.net_benefit);
  const unverified = rows.filter((r) => !r.benefit.computable);
  // An export has to stand on its own: every jurisdiction compared, every
  // assumption used, and the can't-verify list — not just whatever happened
  // to be expanded on screen when the button was pressed.
  const expandAll = printing || showAll;
  const expandUnverified = printing || showUnverified;

  if (computable.length === 0) {
    return (
      <div className="mt-6 border border-border-3 bg-card p-6 font-sans text-[13.5px] text-ink-2">
        None of the {rows.length} jurisdictions searched could be computed for this budget — see "Can't
        verify" below.
      </div>
    );
  }

  const [hero, ...rest] = computable;
  const runnerUps = expandAll ? rest : rest.slice(0, 3);

  return (
    <div className="pt-5">
      <div className="mb-2.5 font-mono text-[11px] font-medium tracking-wide text-ink-3">
        RECOMMENDATION · RANKED BY NET BENEFIT
      </div>

      <HeroCard row={hero} breakeven={breakeven} failing={failingConstraint(hero.rule, liveBudget.constraints)} />

      <SensitivityPanel liveBudget={liveBudget} initialBudget={initialBudget} onChange={onBudgetChange} />

      <ConstraintsPanel
        constraints={liveBudget.constraints}
        onChange={(constraints) => onBudgetChange({ ...liveBudget, constraints })}
      />

      <RelocationAssumptionsPanel assumptions={assumptions} onChange={onAssumptionsChange} forceOpen={printing} />

      {rest.length > 0 && (
        <>
          <div className="mb-2.5 mt-7 flex items-baseline gap-3.5">
            <div className="font-mono text-[11px] font-medium tracking-wide text-ink-3">RUNNERS-UP</div>
            <button
              type="button"
              onClick={() => setShowAll(!showAll)}
              className="font-mono text-[11.5px] text-teal underline decoration-1 underline-offset-2 print:hidden"
            >
              {showAll ? "show top 3 only" : `show all ${rest.length} compared`}
            </button>
          </div>
          <div className="flex flex-col gap-2.5">
            {runnerUps.map((row, i) => (
              <RunnerUpCard
                key={row.rule.jurisdiction}
                row={row}
                rank={i + 2}
                best={hero.benefit.net_benefit}
                failing={failingConstraint(row.rule, liveBudget.constraints)}
              />
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
            <span className="font-mono text-[11px] text-ink-3">{expandUnverified ? "−" : "+"}</span>
            <span className="font-sans text-[13.5px] font-semibold">
              Can't verify — {unverified.length} excluded from the ranking
            </span>
            <span className="font-sans text-[12.5px] text-ink-2">Discretionary or unverifiable programs. Not scored, not hidden.</span>
          </button>
          {expandUnverified && (
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
        added to the credit — confirm them with the film office. Relocation cost includes flights/ground
        transport when a Google Maps distance is available for that jurisdiction (see the note on a hero card
        if it isn't).
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2.5 font-mono text-[11.5px] font-medium tracking-wide ${
        active ? "border border-ink bg-ink text-paper" : "border border-border-2 bg-card text-ink-2"
      }`}
    >
      {children}
    </button>
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
            className="w-full accent-ink print:hidden"
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
            className="w-full accent-ink print:hidden"
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

/**
 * BUILD_BRIEF.md section 7 lists this among the results screen's "live
 * controls", alongside sensitivity — a second entry point besides the
 * initial form (ManualForm.tsx also has these toggles for the first run),
 * so a constraint can be added or dropped after seeing results without
 * going back to re-enter the whole budget.
 */
function ConstraintsPanel({ constraints, onChange }: { constraints: string[]; onChange: (c: string[]) => void }) {
  function toggle(key: string) {
    onChange(constraints.includes(key) ? constraints.filter((c) => c !== key) : [...constraints, key]);
  }

  return (
    <div className="mt-5 border border-border-3 bg-card">
      <div className="flex flex-wrap items-baseline gap-3.5 border-b border-[#eae8e1] bg-card-2 px-5.5 py-3.5">
        <div className="font-sans text-[13.5px] font-semibold">Constraints</div>
        <div className="font-sans text-[12.5px] text-ink-2">Enabling one greys out jurisdictions that can't meet it — never removes them.</div>
      </div>
      <div className="flex flex-wrap gap-2.5 p-5.5">
        {CONSTRAINTS.map((c) => {
          const on = constraints.includes(c.key);
          return (
            <button
              key={c.key}
              type="button"
              onClick={() => toggle(c.key)}
              className={`flex items-center gap-2 border px-3 py-2 font-sans text-[12.5px] transition-colors ${
                on ? "border-ink bg-card-2" : "border-border-2 bg-card"
              }`}
            >
              <span className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center border font-mono text-[9px] ${on ? "border-ink" : "border-[#bfbab1]"}`}>
                {on ? "■" : ""}
              </span>
              {c.label}
            </button>
          );
        })}
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
  forceOpen = false,
}: {
  assumptions: RelocationAssumptions;
  onChange: (a: RelocationAssumptions) => void;
  /** An export must show the assumptions behind its relocation figures, even
   *  if the reader had this panel collapsed on screen. */
  forceOpen?: boolean;
}) {
  const [userOpen, setUserOpen] = useState(false);
  const open = forceOpen || userOpen;
  const setOpen = setUserOpen;

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

function BreakevenLine({ breakeven }: { breakeven: BreakevenResult }) {
  const { series, hi, heroName, atlNow, crossAtl, above, rivalName } = breakeven;
  const W = 260;
  const H = 51;
  const heroYs = series.map((p) => p.nets[heroName] ?? null);
  const rivalYs = rivalName ? series.map((p) => p.nets[rivalName] ?? null) : series.map(() => null);
  const allVals = [...heroYs, ...rivalYs].filter((v): v is number => v != null);
  const lo = allVals.length ? Math.min(...allVals) : 0;
  const hiVal = allVals.length ? Math.max(...allVals) : 1;
  const x = (atl: number) => (atl / hi) * W;
  const y = (v: number) => H - ((v - lo) / (hiVal - lo || 1)) * (H - 4) - 2;

  const toPolyline = (ys: (number | null)[]) =>
    series
      .map((p, i) => (ys[i] != null ? `${x(p.atl).toFixed(1)},${y(ys[i] as number).toFixed(1)}` : null))
      .filter((v): v is string => v != null)
      .join(" ");

  const cx = crossAtl != null ? x(crossAtl) : W;
  const nearest = series.reduce((acc, p) => (Math.abs(p.atl - atlNow) < Math.abs(acc.atl - atlNow) ? p : acc), series[0]);
  const nearestNet = nearest.nets[heroName];
  const mx = x(nearest.atl);
  const my = nearestNet != null ? y(nearestNet) : H;

  let text: string;
  let note: string;
  if (crossAtl == null) {
    text = `${heroName} leads across the whole range tested, up to ${moneyShort(hi)} of ATL spend.`;
    note = `Crossover tested in ${series.length} steps at current resident-labor share.`;
  } else if (above) {
    text = `${heroName} leads until ATL spend exceeds ${moneyShort(crossAtl)} — you're at ${moneyShort(atlNow)}.`;
    note = `Above that, ${rivalName ?? "the runner-up"} takes the lead. Other lines held constant.`;
  } else {
    text = `${heroName} leads while ATL spend stays above ${moneyShort(crossAtl)} — you're at ${moneyShort(atlNow)}.`;
    note = `Below that, ${rivalName ?? "the runner-up"} takes the lead. Other lines held constant.`;
  }

  return (
    <div className="flex items-center gap-4.5 pt-4">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="shrink-0" style={{ overflow: "visible" }}>
        <line x1={0} y1={H - 1} x2={W} y2={H - 1} stroke="#D8DFE3" strokeWidth={1} />
        <polyline points={toPolyline(rivalYs)} fill="none" stroke="#919A9F" strokeWidth={1.4} />
        <polyline points={toPolyline(heroYs)} fill="none" stroke="#008687" strokeWidth={1.8} />
        <line x1={cx} y1={0} x2={cx} y2={H} stroke="#AE4538" strokeWidth={1} strokeDasharray="2 3" />
        <circle cx={mx} cy={my} r={3.2} fill="#008687" />
      </svg>
      <div>
        <div className="font-sans text-[13px] font-medium leading-relaxed text-ink">{text}</div>
        <div className="mt-0.5 font-mono text-[11px] text-ink-3">{note}</div>
      </div>
    </div>
  );
}

function HeroCard({
  row,
  breakeven,
  failing,
}: {
  row: Row;
  breakeven: BreakevenResult | "loading" | "error" | null;
  failing?: string | null;
}) {
  const { rule, benefit } = row;
  const src = rule.sources.find((s) => s.is_primary) ?? rule.sources[0];
  return (
    <div
      title={failing ?? undefined}
      className={`print-block border border-[#bdbab2] border-t-[3px] border-t-ink bg-card ${failing ? "opacity-55" : ""}`}
    >
      <div className="grid grid-cols-1 gap-8 p-7 lg:grid-cols-[1.25fr_1fr]">
        <div>
          <div className="mb-0.5 flex flex-wrap items-baseline gap-3">
            <h2 className="font-sans text-[27px] font-semibold tracking-tight">{rule.jurisdiction}</h2>
            <span className={`border px-1.5 py-1 font-mono text-[10.5px] font-medium uppercase tracking-wide ${POOL_STATUS_CLASS[rule.pool_status]}`}>
              {POOL_STATUS_LABEL[rule.pool_status]}
            </span>
          </div>
          <div className="mb-5 font-mono text-[12.5px] text-ink-2">{rule.program_name}</div>

          {failing && (
            <div className="mb-4 border border-amber/30 bg-amber-bg px-3 py-2 font-mono text-[11.5px] leading-relaxed text-amber">
              Doesn't meet a constraint: {failing}
            </div>
          )}

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

          {breakeven && breakeven !== "loading" && breakeven !== "error" && (
            <BreakevenLine breakeven={breakeven} />
          )}
        </div>

        <div className="border-l border-[#eae8e1] pl-7">
          <div className="flex flex-col gap-3.5">
            <Fact k="HEADLINE RATE" v={`${(rule.base_rate * 100).toFixed(1)}%`} />
            <Fact k="MINIMUM SPEND" v={rule.minimum_spend != null ? money(rule.minimum_spend) : "none"} />
            <Fact k="QUALIFIED SPEND USED" v={money(benefit.qualifying_spend)} />
            <Fact k="CONFIDENCE" v={rule.confidence.replace("_", " ")} />
            {/* BUILD_BRIEF.md section 7 requires film office contacts in the
                export; "not listed" is the honest answer when extraction
                didn't find one, rather than hiding the row. */}
            <Fact k="FILM OFFICE" v={rule.film_office_contact ?? "not listed in sources"} />
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

function RunnerUpCard({ row, rank, best, failing }: { row: Row; rank: number; best: number; failing?: string | null }) {
  const { rule, benefit } = row;
  const src = rule.sources.find((s) => s.is_primary) ?? rule.sources[0];
  return (
    <div title={failing ?? undefined} className={`print-block border border-border-3 bg-card ${failing ? "opacity-55" : ""}`}>
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
          {failing && <div className="mt-1 font-mono text-[11px] leading-relaxed text-amber">Doesn't meet: {failing}</div>}
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
