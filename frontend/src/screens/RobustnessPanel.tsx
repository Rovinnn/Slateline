import { moneyShort } from "../lib/format";
import type { Robustness } from "../types";

/**
 * Does the recommendation survive what nobody has verified?
 *
 * The tool refuses to guess, and prices the unknowns it refuses to guess
 * about. This is the third act: saying whether the answer depends on them.
 *
 * A margin and a confidence are different facts and this renders them as
 * such. Louisiana beating New Mexico by $5,349 while holding in 375 of 625
 * combinations is a materially different recommendation from beating Georgia
 * by $76,739 in all 625 — and as a single dollar figure the two look
 * identical, which is the most misleading thing this tool could do.
 *
 * Where it's fragile, the flips are the useful part: a threshold is something
 * a producer can go and confirm, where a probability is not.
 */
export function RobustnessPanel({ robustness }: { robustness: Robustness }) {
  const { winner, runner_up, margin, winner_holds_in, combinations_tested, flips, inputs_swept } =
    robustness;
  if (combinations_tested === 0) return null;

  const robust = winner_holds_in === combinations_tested;
  const share = Math.round((winner_holds_in / combinations_tested) * 100);

  return (
    <div
      className={`print-block mt-5 border bg-card ${
        robust ? "border-border-3" : "border-amber/40 border-l-[3px] border-l-amber"
      }`}
    >
      <div className="flex flex-wrap items-baseline gap-3.5 border-b border-[var(--color-hairline)] bg-card-2 px-5.5 py-3.5">
        <div className="font-sans text-[13.5px] font-semibold">
          Does this recommendation hold up?
        </div>
        <div className="font-sans text-[12.5px] text-ink-2">
          {combinations_tested} combinations of the {inputs_swept.length} inputs nobody has verified
        </div>
      </div>

      <div className="p-5.5">
        {robust ? (
          <div className="font-sans text-[14.5px] font-medium leading-relaxed text-ink">
            {winner} wins in every combination tested. The {moneyShort(margin)} margin over{" "}
            {runner_up} is wider than anything we're unsure about.
          </div>
        ) : (
          <>
            <div className="font-sans text-[14.5px] font-medium leading-relaxed text-ink">
              {winner} wins in {share}% of combinations — the {moneyShort(margin)} margin over{" "}
              {runner_up} is narrower than what we don't know.
            </div>
            <p className="mt-1.5 font-sans text-[12.5px] leading-relaxed text-ink-2">
              Treat this as close rather than settled. Any one of these would change the answer:
            </p>
            <div className="mt-3 flex flex-col gap-2">
              {flips.map((f, i) => (
                <div key={i} className="border border-amber/25 bg-amber-bg px-3.5 py-2.5">
                  <div className="font-sans text-[13px] font-medium text-[#7d5a29]">
                    {f.input_name} {f.threshold} → {f.new_winner} wins instead
                  </div>
                  <div className="mt-0.5 font-mono text-[10.5px] leading-relaxed text-[#8a6733]">
                    {f.because}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="mt-4 border-t border-[var(--color-hairline)] pt-3">
          <div className="mb-1.5 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
            WHAT WAS VARIED
          </div>
          <div className="flex flex-col gap-1">
            {inputs_swept.map((input, i) => (
              <div key={i} className="font-mono text-[11px] leading-relaxed text-ink-3">
                <span className="text-ink-2">{input.name}</span> — assumed {input.assumed};{" "}
                {input.because}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
