import { useEffect, useState } from "react";
import { ApiError, computeBenefit, getSeedJurisdictions } from "../lib/api";
import { hostOf, money, moneyShort } from "../lib/format";
import type { BenefitBreakdown, BudgetVector, JurisdictionRule, PoolStatus } from "../types";

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

export function Results({ budget, onEditInputs }: { budget: BudgetVector; onEditInputs: () => void }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [showAll, setShowAll] = useState(false);
  const [showUnverified, setShowUnverified] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    (async () => {
      try {
        const rules = await getSeedJurisdictions();
        const rows = await Promise.all(
          rules.map(async (rule) => ({ rule, benefit: await computeBenefit(budget, rule) })),
        );
        if (!cancelled) setState({ status: "ready", rows });
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? `${err.message} (HTTP ${err.status})`
            : "Could not reach the backend. Is it running at the configured VITE_API_BASE_URL?";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [budget]);

  return (
    <div className="mx-auto max-w-[1320px] px-7 pb-20">
      <div className="flex items-center gap-5 pt-4">
        <div className="font-sans text-[12.5px] text-ink-2">
          {moneyShort(budget.total)} budget · {budget.shoot_days} days · {budget.crew_headcount} crew
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
        <ReadyResults rows={state.rows} showAll={showAll} setShowAll={setShowAll} showUnverified={showUnverified} setShowUnverified={setShowUnverified} />
      )}
    </div>
  );
}

function ReadyResults({
  rows,
  showAll,
  setShowAll,
  showUnverified,
  setShowUnverified,
}: {
  rows: Row[];
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
