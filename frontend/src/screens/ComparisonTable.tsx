import { Fragment, useState } from "react";
import { hostOf, money, moneyShort } from "../lib/format";
import type { BenefitBreakdown, JurisdictionRule, PoolStatus } from "../types";
import { FundingAvailability, SourceEvidence } from "./Evidence";

interface Row {
  rule: JurisdictionRule;
  benefit: BenefitBreakdown;
}

/**
 * Every jurisdiction, every number that decides the ranking, on one screen.
 *
 * The memo tab answers "what should I do" — one recommendation, argued. This
 * answers "show me the working": the same rows side by side so a producer can
 * see *why* the winner wins, and check the losing cases rather than take the
 * ranking on faith. BUILD_BRIEF.md asks for a memo rather than a leaderboard,
 * and the memo stays the default; this is the audit view behind it.
 *
 * Every column is a figure that actually moves the ranking. Nothing here is
 * decorative — headline rate alone is exactly the misleading number the whole
 * product exists to go past, so it sits next to what it's worth after
 * qualification and relocation.
 */

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

type SortKey = "net" | "credit" | "realizable" | "rate" | "relocation" | "qualified";

const COLUMNS: { key: SortKey; label: string; hint: string }[] = [
  { key: "rate", label: "HEADLINE RATE", hint: "what the state advertises" },
  { key: "qualified", label: "QUALIFIED SPEND", hint: "how much of your budget actually counts" },
  { key: "credit", label: "CREDIT (FACE)", hint: "rate applied to qualified spend, after caps" },
  { key: "realizable", label: "REALIZABLE", hint: "what it's worth in cash — transferable credits sell at a discount" },
  { key: "relocation", label: "RELOCATION", hint: "cost of getting your crew there" },
  { key: "net", label: "NET BENEFIT", hint: "credit minus relocation — the real number" },
];

function valueFor(row: Row, key: SortKey): number {
  switch (key) {
    case "rate":
      return row.rule.base_rate;
    case "qualified":
      return row.benefit.qualifying_spend;
    case "credit":
      return row.benefit.gross_credit;
    case "realizable":
      return row.benefit.realizable_credit ?? row.benefit.gross_credit;
    case "relocation":
      return row.benefit.relocation_cost;
    case "net":
      return row.benefit.net_benefit;
  }
}

export function ComparisonTable({
  rows,
  failingFor,
}: {
  rows: Row[];
  /** Reason this jurisdiction fails an active constraint, if any. */
  failingFor: (rule: JurisdictionRule) => string | null;
}) {
  const [sort, setSort] = useState<SortKey>("net");
  const [expanded, setExpanded] = useState<string | null>(null);

  const computable = rows.filter((r) => r.benefit.computable);
  const unverified = rows.filter((r) => !r.benefit.computable);
  // Relocation is a cost, so smallest-first is the useful order there.
  const sorted = [...computable].sort((a, b) =>
    sort === "relocation" ? valueFor(a, sort) - valueFor(b, sort) : valueFor(b, sort) - valueFor(a, sort),
  );
  const best = sorted.length ? Math.max(...computable.map((r) => r.benefit.net_benefit)) : 0;

  return (
    <div className="pt-5">
      <div className="mb-2.5 flex flex-wrap items-baseline gap-3.5">
        <div className="font-mono text-[11px] font-medium tracking-wide text-ink-3">
          ALL JURISDICTIONS · SORTED BY {COLUMNS.find((c) => c.key === sort)?.label}
        </div>
        <div className="font-sans text-[12.5px] text-ink-2">
          Click a column to re-sort, or a row for the sources behind it.
        </div>
      </div>

      <div className="mb-1.5 font-mono text-[10px] text-ink-3 print:hidden">scroll for more columns →</div>
      <div className="overflow-x-auto border border-border-3 bg-card">
        <table className="w-full min-w-180 border-collapse">
          <thead>
            <tr className="border-b border-[#eae8e1] bg-card-2">
              <th className="px-4 py-2.5 text-left font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
                JURISDICTION
              </th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-2.5 text-right"
                  aria-sort={sort !== col.key ? "none" : col.key === "relocation" ? "ascending" : "descending"}
                >
                  <button
                    type="button"
                    onClick={() => setSort(col.key)}
                    title={col.hint}
                    className={`font-mono text-[10.5px] font-medium tracking-wide ${
                      sort === col.key ? "text-ink underline decoration-1 underline-offset-2" : "text-ink-3"
                    }`}
                  >
                    {col.label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => {
              const { rule, benefit } = row;
              const failing = failingFor(rule);
              const isBest = benefit.net_benefit === best;
              const open = expanded === rule.jurisdiction;
              return (
                <Fragment key={rule.jurisdiction}>
                  <tr
                    onClick={() => setExpanded(open ? null : rule.jurisdiction)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setExpanded(open ? null : rule.jurisdiction);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    aria-expanded={open}
                    title={failing ?? "Click for sources"}
                    className={`cursor-pointer border-b border-[#efede7] transition-colors hover:bg-card-2 ${
                      failing ? "opacity-55" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="font-mono text-[11px] text-ink-3">{String(i + 1).padStart(2, "0")}</span>
                        <span className="font-sans text-[14px] font-semibold">{rule.jurisdiction}</span>
                        {isBest && (
                          <span className="border border-ink px-1.5 py-0.5 font-mono text-[9.5px] font-medium tracking-wide">
                            BEST NET
                          </span>
                        )}
                        <span
                          className={`border px-1.5 py-0.5 font-mono text-[9.5px] font-medium uppercase tracking-wide ${POOL_STATUS_CLASS[rule.pool_status]}`}
                        >
                          {POOL_STATUS_LABEL[rule.pool_status]}
                        </span>
                      </div>
                      <div className="mt-0.5 font-mono text-[11px] text-ink-4">
                        {rule.program_name} · {rule.confidence.replace("_", " ")}
                      </div>
                      {failing && <div className="mt-1 font-mono text-[11px] text-amber">Doesn't meet: {failing}</div>}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[13px]">
                      {(rule.base_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[13px]">{money(benefit.qualifying_spend)}</td>
                    <td className="px-4 py-3 text-right font-mono text-[13px]">{money(benefit.gross_credit)}</td>
                    <td
                      className="px-4 py-3 text-right font-mono text-[13px]"
                      title={benefit.monetization_note ?? undefined}
                    >
                      {money(benefit.realizable_credit ?? benefit.gross_credit)}
                      {(benefit.realizable_credit ?? benefit.gross_credit) !== benefit.gross_credit && (
                        <div className="font-mono text-[10.5px] text-amber">after discount</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[13px] text-ink-2">
                      −{money(benefit.relocation_cost)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-mono text-[16px] font-semibold tracking-tight">
                        {moneyShort(benefit.net_benefit)}
                      </div>
                      {!isBest && (
                        <div className="font-mono text-[11px] text-ink-4">
                          {moneyShort(benefit.net_benefit - best)} vs best
                        </div>
                      )}
                    </td>
                  </tr>
                  {open && (
                    <tr className="border-b border-[#efede7] bg-card-2">
                      <td colSpan={7} className="px-4 py-4">
                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.4fr]">
                          <div className="flex flex-col gap-3">
                            <FundingAvailability rule={rule} />
                            {benefit.caps_applied.length > 0 && (
                              <div>
                                <div className="mb-1 font-mono text-[10px] font-medium tracking-wide text-ink-3">
                                  WHAT LIMITED THIS
                                </div>
                                <ul className="flex flex-col gap-1">
                                  {benefit.caps_applied.map((note, n) => (
                                    <li key={n} className="font-mono text-[11px] leading-relaxed text-ink-2">
                                      {note}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                          <div>
                            <div className="mb-1.5 font-mono text-[10px] font-medium tracking-wide text-ink-3">
                              EVIDENCE
                            </div>
                            <SourceEvidence rule={rule} />
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {unverified.length > 0 && (
        <div className="mt-4 border border-border bg-card">
          <div className="border-b border-[#eae8e1] bg-card-2 px-4 py-2.5">
            <span className="font-sans text-[13px] font-semibold">
              Not ranked — {unverified.length} {unverified.length === 1 ? "program" : "programs"} we won't guess at
            </span>
          </div>
          {unverified.map(({ rule, benefit }) => {
            const src = rule.sources.find((s) => s.is_primary) ?? rule.sources[0];
            return (
              <div key={rule.jurisdiction} className="border-b border-[#efede7] px-4 py-3 last:border-b-0">
                <div className="flex flex-wrap items-baseline gap-2.5">
                  <span className="font-sans text-[13.5px] font-semibold">{rule.jurisdiction}</span>
                  <span className="font-mono text-[11px] text-ink-4">{rule.program_name}</span>
                </div>
                <div className="mt-1 font-sans text-[12.5px] leading-relaxed text-[#57534c]">
                  {benefit.non_computable_reason}
                </div>
                {src && (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener"
                    className="mt-1 inline-block font-mono text-[11px] text-teal underline decoration-1 underline-offset-2"
                  >
                    {hostOf(src.url)}
                    <span className="sr-only"> (opens in new tab)</span>
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
