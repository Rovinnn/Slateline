import { moneyShort } from "../lib/format";
import type { OpenQuestion } from "../types";

/**
 * The unknowns, priced — what to actually go and do.
 *
 * Everywhere else this tool declines to guess, it leaves a note. Those notes
 * were honest and inert: a flat list of caveats where nothing distinguished a
 * $2,000 unknown from a $200,000 one, so a reader skimmed all of them equally.
 *
 * Priced and sorted, they stop being caveats and become the highest-value
 * phone calls available. That is the difference between a tool that analyses
 * and one a producer opens on a Tuesday morning.
 *
 * Risk and upside are shown together and signed, because "confirm the uplift,
 * it's worth +$152k" and "confirm the pool is open, or the whole $260k goes"
 * are the same kind of fact — and the second one is the one that gets someone
 * fired.
 */
export function OpenQuestions({ questions, jurisdiction }: { questions: OpenQuestion[]; jurisdiction: string }) {
  if (questions.length === 0) return null;
  const risks = questions.filter((q) => q.worth < 0);

  return (
    <div className="print-block mt-5 border border-border-3 bg-card">
      <div className="flex flex-wrap items-baseline gap-3.5 border-b border-[var(--color-hairline)] bg-card-2 px-5.5 py-3.5">
        <div className="font-sans text-[13.5px] font-semibold">Before you commit to {jurisdiction}</div>
        <div className="font-sans text-[12.5px] text-ink-2">
          {questions.length} unresolved {questions.length === 1 ? "question" : "questions"}, ranked by
          what turns on {questions.length === 1 ? "it" : "them"}
          {risks.length > 0 && ` · ${risks.length} at risk`}
        </div>
      </div>

      <div className="flex flex-col">
        {questions.map((q, i) => (
          <div
            key={i}
            className="grid grid-cols-1 gap-2 border-b border-[var(--color-hairline-2)] px-5.5 py-3.5 last:border-b-0 sm:grid-cols-[1fr_auto]"
          >
            <div>
              <div className="font-sans text-[13.5px] font-medium leading-relaxed text-ink">
                {q.question}
              </div>
              <div className="mt-1 font-mono text-[11px] leading-relaxed text-ink-3">{q.basis}</div>
              <div className="mt-1 font-mono text-[11px] text-ink-4">ask: {q.ask}</div>
            </div>
            <div className="text-left sm:text-right">
              <div
                className={`font-mono text-[17px] font-semibold tracking-tight ${
                  q.worth < 0 ? "text-red" : "text-teal"
                }`}
              >
                {q.worth > 0 ? "+" : ""}
                {moneyShort(q.worth)}
              </div>
              <div className="font-mono text-[10px] tracking-wide text-ink-3">
                {q.worth < 0 ? "AT RISK" : "IF CONFIRMED"}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-[var(--color-hairline)] bg-card-2 px-5.5 py-3 font-mono text-[10.5px] leading-relaxed text-ink-3">
        Each figure is this jurisdiction's net benefit recomputed with the question answered the other
        way, so it's a difference between two runs of the same calculator — not an estimate.
      </div>
    </div>
  );
}
