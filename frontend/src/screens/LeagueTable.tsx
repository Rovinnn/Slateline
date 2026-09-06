import { useEffect, useState } from "react";
import { hostOf } from "../lib/format";

/**
 * How far every jurisdiction's advertised rate is from what it actually pays.
 *
 * The rest of the app answers "where should *this* production shoot". This
 * answers the question a sceptic asks first: does any of this generalise, or
 * did you tune it to four states? Every row is one live extraction priced
 * against a single shared budget, so the denominator is constant and the
 * comparison means something.
 *
 * Precomputed at build time (backend/scripts/build_league_table.py) because
 * it is ~35 seconds of live search per jurisdiction. That also makes it a
 * dated artefact rather than a figure that quietly changes under the reader —
 * the measurement date is on screen, next to the claim.
 *
 * Jurisdictions that couldn't be priced are listed with the reason rather
 * than dropped. A league table that hid its failures would be the advertising
 * this whole project argues against.
 */

interface LeagueRow {
  jurisdiction: string;
  program: string;
  currency: string;
  advertised: number;
  credit_type: string;
  confidence: string;
  computable: boolean;
  effective?: number;
  gap_points?: number;
  months_to_payment?: number;
  uplift_count?: number;
  advertised_is_stacked?: boolean;
  reason?: string;
  sources: string[];
}

interface LeagueData {
  measured_at: string;
  reference_budget_label: string;
  rows: LeagueRow[];
  note: string;
}

export function LeagueTable() {
  const [data, setData] = useState<LeagueData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${import.meta.env.BASE_URL}league-table.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: LeagueData) => !cancelled && setData(d))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <div className="mt-6 border border-border-3 bg-card p-6 font-sans text-[13.5px] text-ink-2">
        The measured comparison couldn't be loaded. Everything else on this page is unaffected.
      </div>
    );
  }
  if (!data) {
    return <div className="py-16 font-mono text-[12.5px] text-ink-2">Loading measurements…</div>;
  }

  const priced = data.rows.filter((r) => r.computable);
  const unpriceable = data.rows.filter((r) => !r.computable);
  const widest = Math.max(...priced.map((r) => r.advertised), 0.01);

  return (
    <div className="pt-5">
      <div className="mb-1 font-mono text-[11px] font-medium tracking-wide text-ink-3">
        ADVERTISED VS ACTUAL · MEASURED {data.measured_at}
      </div>
      <h2 className="mb-2 font-sans text-[22px] font-semibold tracking-tight">
        Every programme advertises more than it pays.
      </h2>
      <p className="mb-5 max-w-[760px] font-sans text-[13.5px] leading-relaxed text-ink-2">
        Each row is one live statute extraction, priced against the same budget —{" "}
        {data.reference_budget_label}. "Advertised" is the base rate plus every uplift the
        programme markets. "Actual" is what reaches the production, as a share of the whole
        budget.
      </p>

      <div className="border border-border-3 bg-card">
        <div className="grid grid-cols-[1.4fr_repeat(3,minmax(0,0.7fr))] gap-3 border-b border-[#eae8e1] bg-card-2 px-4 py-2.5 font-mono text-[10.5px] font-medium tracking-wide text-ink-3">
          <div>JURISDICTION</div>
          <div className="text-right">ADVERTISED</div>
          <div className="text-right">ACTUAL</div>
          <div className="text-right">GAP</div>
        </div>

        {priced.map((r) => (
          <div key={r.jurisdiction} className="border-b border-[#efede7] px-4 py-3 last:border-b-0">
            <div className="grid grid-cols-[1.4fr_repeat(3,minmax(0,0.7fr))] items-baseline gap-3">
              <div>
                <div className="font-sans text-[14px] font-semibold">{r.jurisdiction}</div>
                <div className="font-mono text-[10.5px] text-ink-4">
                  {r.credit_type.replace("_", "-")}
                  {r.currency !== "USD" && ` · converted from ${r.currency}`}
                  {r.months_to_payment ? ` · ~${r.months_to_payment}mo to pay` : ""}
                </div>
                {/* Some jurisdictions publish several regional and content
                    credits that stack on paper. Summing them is what gets
                    marketed, but one production is unlikely to combine them —
                    saying so keeps a 104% headline a finding rather than a
                    number that looks broken. */}
                {r.advertised_is_stacked && (
                  <div className="mt-0.5 font-mono text-[10px] leading-relaxed text-amber">
                    {r.uplift_count} separate uplifts summed — unlikely to all apply to one production
                  </div>
                )}
              </div>
              <div className="text-right font-mono text-[14px] text-ink-3 line-through decoration-1">
                {(r.advertised * 100).toFixed(1)}%
              </div>
              <div className="text-right font-mono text-[16px] font-semibold text-ink">
                {(r.effective! * 100).toFixed(1)}%
              </div>
              <div className="text-right font-mono text-[13px] text-red">
                −{r.gap_points!.toFixed(1)}pts
              </div>
            </div>
            {/* The bar is the argument: advertised in outline, actual filled. */}
            <div className="mt-2 h-[5px] w-full bg-[#ecebe5]">
              <div className="h-full bg-[#d8d4cb]" style={{ width: `${(r.advertised / widest) * 100}%` }}>
                <div
                  className="h-full bg-teal"
                  style={{ width: `${Math.max(0, (r.effective! / r.advertised) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {unpriceable.length > 0 && (
        <div className="mt-5 border border-border bg-card">
          <div className="border-b border-[#eae8e1] bg-card-2 px-4 py-2.5 font-sans text-[13px] font-semibold">
            {unpriceable.length} measured and found not priceable
          </div>
          {unpriceable.map((r) => (
            <div key={r.jurisdiction} className="border-b border-[#efede7] px-4 py-2.5 last:border-b-0">
              <span className="font-sans text-[13px] font-semibold">{r.jurisdiction}</span>{" "}
              <span className="font-sans text-[12.5px] text-ink-2">{r.reason}</span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 max-w-[760px] font-mono text-[11px] leading-relaxed text-ink-3">
        {data.note} Sources for every row are recorded in{" "}
        <span className="text-ink-2">league-table.json</span>
        {priced[0]?.sources[0] && <> — for example {hostOf(priced[0].sources[0])} for {priced[0].jurisdiction}</>}.
      </div>
    </div>
  );
}
