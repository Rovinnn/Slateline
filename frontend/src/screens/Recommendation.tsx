import { buildWaterfall, effectiveRate, explainWin, type Row } from "../lib/explain";
import { money, moneyShort } from "../lib/format";

/**
 * The two pieces that turn a ranking into a recommendation: the walk from
 * advertised rate down to cash, and an arithmetic account of why the winner
 * won. Both are derived from BenefitBreakdown subtractions — nothing here is
 * model-written, because an explanation of a number that doesn't come from
 * that number is decoration.
 */

/** Face value to bank balance, with every stage the number shrinks at. */
export function Waterfall({ row }: { row: Row }) {
  const steps = buildWaterfall(row);
  // Bars are scaled to the largest magnitude in the walk (usually qualifying
  // spend), so the credit reads as the small slice of the budget it actually is.
  const scale = Math.max(...steps.map((s) => Math.abs(s.value)), 1);

  return (
    <div className="flex flex-col gap-2">
      <div className="font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
        FROM ADVERTISED RATE TO CASH
      </div>
      {steps.map((step, i) => {
        const width = `${Math.max(1.5, (Math.abs(step.value) / scale) * 100)}%`;
        const isNet = i === steps.length - 1;
        return (
          <div key={`${step.label}-${i}`}>
            <div className="flex items-baseline justify-between gap-3">
              <span
                className={`font-sans text-[12.5px] ${
                  isNet ? "font-semibold text-ink" : step.kind === "deduction" ? "text-ink-2" : "text-[#3d3a34]"
                }`}
              >
                {step.label}
              </span>
              <span
                className={`shrink-0 font-mono ${
                  isNet ? "text-[15px] font-semibold text-ink" : "text-[12.5px] text-[#3d3a34]"
                }`}
              >
                {money(step.value)}
              </span>
            </div>
            <div className="mt-1 h-[3px] w-full bg-[#ecebe5]">
              <div
                className={`h-full ${
                  isNet ? "bg-ink" : step.kind === "deduction" ? "bg-amber" : "bg-teal"
                }`}
                style={{ width }}
              />
            </div>
            {step.note && <div className="mt-1 font-mono text-[10.5px] text-ink-3">{step.note}</div>}
          </div>
        );
      })}
    </div>
  );
}

/** Why the top pick beats the runner-up, in components that sum to the gap. */
export function WhyItWins({ winner, rival }: { winner: Row; rival: Row }) {
  const explanation = explainWin(winner, rival);
  if (explanation.deltas.length === 0) return null;

  return (
    <div className="border border-border-2 bg-card-2 p-4">
      <div className="mb-2.5 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
        WHY {explanation.winner.toUpperCase()} WINS
      </div>

      <div className="flex flex-col gap-2">
        {explanation.deltas.map((d, i) => (
          <div key={i} className="flex items-baseline justify-between gap-4">
            <div>
              <div className="font-sans text-[12.5px] text-ink">{d.label}</div>
              <div className="font-mono text-[10.5px] leading-relaxed text-ink-3">{d.detail}</div>
            </div>
            <span
              className={`shrink-0 font-mono text-[13px] font-medium ${d.delta > 0 ? "text-teal" : "text-red"}`}
            >
              {d.delta > 0 ? "+" : ""}
              {moneyShort(d.delta)}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-2.5 flex items-baseline justify-between gap-4 border-t border-border-2 pt-2.5">
        <span className="font-sans text-[12.5px] font-semibold text-ink">
          Net advantage over {explanation.rival}
        </span>
        <span className="shrink-0 font-mono text-[14px] font-semibold text-ink">
          {explanation.total > 0 ? "+" : ""}
          {moneyShort(explanation.total)}
        </span>
      </div>

      {explanation.context.length > 0 && (
        <ul className="mt-2.5 flex flex-col gap-1 border-t border-border-2 pt-2.5">
          {explanation.context.map((c, i) => (
            <li key={i} className="font-sans text-[12px] leading-relaxed text-ink-2">
              {c}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * The product's thesis, as two numbers side by side.
 *
 * Everything else on this card explains the *mechanism* by which an
 * advertised rate collapses. This states the collapse itself, which is the
 * part a producer feels without reading anything: Georgia is sold as 30% and
 * returns 8.8% of the budget.
 *
 * The gap is the product. Without it a reader has to divide the net benefit
 * by their own budget in their head to discover there was ever a story here.
 */
export function EffectiveRate({ row, totalBudget }: { row: Row; totalBudget: number }) {
  const rate = effectiveRate(row, totalBudget);
  if (!rate) return null;
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="print-block mb-5 flex flex-wrap items-end gap-x-8 gap-y-3 border-b border-[#eae8e1] pb-4">
      <div>
        <div className="mb-1 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
          {rate.advertisedIncludesUplifts ? "ADVERTISED AS UP TO" : "ADVERTISED RATE"}
        </div>
        <div className="font-mono text-[30px] font-semibold leading-none tracking-tight text-ink-3 line-through decoration-1">
          {pct(rate.advertised)}
        </div>
      </div>
      <div className="font-mono text-[20px] leading-none text-ink-4">→</div>
      <div>
        <div className="mb-1 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
          YOU ACTUALLY KEEP
        </div>
        <div
          className={`font-mono text-[30px] font-semibold leading-none tracking-tight ${
            rate.effective < 0 ? "text-red" : "text-ink"
          }`}
        >
          {pct(rate.effective)}
        </div>
      </div>
      <div className="max-w-70 font-sans text-[12px] leading-relaxed text-ink-2">
        of your total budget, after qualification rules, how the credit pays out, the wait to be
        paid{rate.effective < 0 ? "" : ","} and relocation.
        {rate.effective < 0 && " This jurisdiction costs more to reach than its credit is worth."}
      </div>
    </div>
  );
}
