import { money, moneyShort } from "../lib/format";
import type { SplitResponse } from "../types";

/**
 * Shoot in one jurisdiction, post in another.
 *
 * The one recommendation no rate table can produce, because a table has one
 * row per place and this needs combinations of them.
 *
 * Deliberately renders in both directions. A panel that only appeared when
 * splitting won would be a slot machine — you'd learn nothing on the runs
 * where it stayed silent. The more useful answer is often "don't split, and
 * here is the specific reason": minimum spend is a cliff, so dividing the
 * budget can drop a leg under its threshold and destroy a credit that would
 * have been earned whole.
 */
export function SplitRecommendation({ split }: { split: SplitResponse }) {
  const { best, best_single, splitting_wins, gain_over_single } = split;

  // Losing splits are worth showing when they lost for an interesting reason.
  // A plan that merely scored low teaches nothing; one that fell off a cliff
  // is a trap the producer would otherwise walk into.
  // `is_split` is a Python @property, so it never crosses the wire — derive it.
  const cliffPlans = split.plans.filter((p) => p.shoot_in !== p.post_in && p.warnings.length > 0).slice(0, 2);

  return (
    <div
      className={`print-block mt-5 border bg-card ${
        splitting_wins ? "border-teal/40 border-l-[3px] border-l-teal" : "border-border-3"
      }`}
    >
      <div className="flex flex-wrap items-baseline gap-3 border-b border-[#eae8e1] bg-card-2 px-5.5 py-3.5">
        <div className="font-sans text-[13.5px] font-semibold">Splitting the production</div>
        <div className="font-sans text-[12.5px] text-ink-2">
          Principal photography in one jurisdiction, post and VFX in another.
        </div>
      </div>

      <div className="p-5.5">
        {splitting_wins ? (
          <>
            <div className="font-sans text-[15px] font-semibold leading-relaxed text-ink">
              Shoot in {best.shoot_in}, post in {best.post_in} — {moneyShort(gain_over_single)} more
              than {best_single.shoot_in} alone.
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Leg
                label={`Principal photography · ${best.shoot_in}`}
                spend={best.shoot_leg.qualifying_spend}
                net={best.shoot_leg.net_benefit}
                note="includes relocating cast and crew"
              />
              {best.post_leg && (
                <Leg
                  label={`Post and VFX · ${best.post_in}`}
                  spend={best.post_leg.qualifying_spend}
                  net={best.post_leg.net_benefit}
                  note="vendor work — nobody relocates"
                />
              )}
            </div>
            <div className="mt-3.5 border-t border-[#eae8e1] pt-3 font-mono text-[11.5px] leading-relaxed text-ink-2">
              Combined {money(best.net_benefit)} against {money(best_single.net_benefit)} for the best
              single location. Both legs must independently clear their own minimum spend — the
              figures above already account for that.
            </div>
          </>
        ) : (
          <>
            <div className="font-sans text-[14px] font-medium leading-relaxed text-ink">
              Don't split — {best_single.shoot_in} alone is the best plan at{" "}
              {money(best_single.net_benefit)}.
            </div>
            <p className="mt-2 font-sans text-[13px] leading-relaxed text-[#57534c]">
              Every shoot/post pairing was priced and none beat keeping the production in one place.
            </p>
          </>
        )}

        {cliffPlans.length > 0 && (
          <div className="mt-4 border border-amber/30 bg-amber-bg px-3.5 py-3">
            <div className="mb-1.5 font-mono text-[10.5px] font-medium tracking-wide text-amber">
              SPLITS THAT DESTROY A CREDIT
            </div>
            <div className="flex flex-col gap-1.5">
              {cliffPlans.map((p, i) => (
                <div key={i} className="font-sans text-[12.5px] leading-relaxed text-[#7d5a29]">
                  <span className="font-medium">
                    Shoot {p.shoot_in}, post {p.post_in}:
                  </span>{" "}
                  {p.warnings[0]}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Leg({
  label,
  spend,
  net,
  note,
}: {
  label: string;
  spend: number;
  net: number;
  note: string;
}) {
  return (
    <div className="border border-border-2 bg-card-2 px-3.5 py-3">
      <div className="mb-1 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
        {label.toUpperCase()}
      </div>
      <div className="font-mono text-[17px] font-semibold tracking-tight text-ink">{money(net)}</div>
      <div className="mt-1 font-mono text-[11px] text-ink-3">
        on {money(spend)} qualifying · {note}
      </div>
    </div>
  );
}
