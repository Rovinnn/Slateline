import { useMemo } from "react";
import { HOME_BASES } from "../data/examples";
import { moneyShort } from "../lib/format";
import type { BenefitBreakdown, JurisdictionRule } from "../types";

interface Row {
  rule: JurisdictionRule;
  benefit: BenefitBreakdown;
}

/**
 * A lighter-weight stand-in for the design canvas's D3 + topojson world map
 * (../../Incentive Verifier Web App/map-view.js): plain SVG, a simple
 * equirectangular-style projection (no cos(lat) correction), and no country
 * boundary polygons or CDN fetch. BUILD_BRIEF.md section 7 calls the map tab
 * a "supporting view, not the hero," so this trades cartographic accuracy
 * for zero extra dependencies — good enough to show relative position and
 * net benefit at a glance, not for measuring anything.
 *
 * Pin positions use each JurisdictionRule's real centroid_lat/lng (sourced,
 * not fabricated). The connecting lines are illustrative only — actual
 * distance still comes from distance_km on BenefitBreakdown, which is null
 * until Google Maps is wired in (see the note this panel shows for that).
 */
export function MapView({ rows, homeBaseLabel }: { rows: Row[]; homeBaseLabel: string }) {
  const home = HOME_BASES.find((h) => h.label === homeBaseLabel) ?? HOME_BASES[0];

  const points = useMemo(
    () =>
      rows.map((r) => ({
        name: r.rule.jurisdiction,
        lat: r.rule.centroid_lat,
        lng: r.rule.centroid_lng,
        net: r.benefit.net_benefit,
        excluded: !r.benefit.computable,
      })),
    [rows],
  );

  const W = 900;
  const H = 480;
  const PAD = 60;

  const allLats = [...points.map((p) => p.lat), home.lat];
  const allLngs = [...points.map((p) => p.lng), home.lng];
  const minLat = Math.min(...allLats) - 4;
  const maxLat = Math.max(...allLats) + 4;
  const minLng = Math.min(...allLngs) - 4;
  const maxLng = Math.max(...allLngs) + 4;

  function project(lat: number, lng: number): [number, number] {
    const x = PAD + ((lng - minLng) / (maxLng - minLng || 1)) * (W - 2 * PAD);
    const y = PAD + ((maxLat - lat) / (maxLat - minLat || 1)) * (H - 2 * PAD);
    return [x, y];
  }

  const computableNets = points.filter((p) => !p.excluded).map((p) => p.net);
  const lo = computableNets.length ? Math.min(...computableNets) : 0;
  const hi = computableNets.length ? Math.max(...computableNets) : 1;

  const [hx, hy] = project(home.lat, home.lng);

  return (
    <div className="mt-5">
      <div className="mb-3 flex flex-wrap items-baseline gap-4">
        <div className="font-mono text-[11px] font-medium tracking-wide text-ink-3">GEOGRAPHY · SUPPORTING VIEW</div>
        <div className="font-sans text-[12.5px] text-ink-2">
          Ranking is unchanged by this view — see the memo tab for net benefit.
        </div>
      </div>

      <div className="border border-border-3 bg-card">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ display: "block" }}>
          {points.map((p) => {
            const [x, y] = project(p.lat, p.lng);
            return (
              <line
                key={`line-${p.name}`}
                x1={hx}
                y1={hy}
                x2={x}
                y2={y}
                stroke={p.excluded ? "#C0BDB6" : netColor(p.net, lo, hi)}
                strokeWidth={1}
                strokeDasharray={p.excluded ? "3 3" : undefined}
                opacity={0.6}
              />
            );
          })}

          {/* home base */}
          <g transform={`translate(${hx},${hy})`}>
            <rect x={-6} y={-6} width={12} height={12} fill="#F7F5F1" stroke="#131F25" strokeWidth={2} transform="rotate(45)" />
            <text y={-16} textAnchor="middle" fontFamily="'Public Sans',sans-serif" fontWeight={600} fontSize={12} fill="#131F25">
              {home.label}
            </text>
            <text y={24} textAnchor="middle" fontFamily="'IBM Plex Mono',monospace" fontWeight={500} fontSize={10} letterSpacing="0.06em" fill="#4E5A60">
              HOME BASE
            </text>
          </g>

          {points.map((p) => {
            const [x, y] = project(p.lat, p.lng);
            const color = p.excluded ? "#F7F5F1" : netColor(p.net, lo, hi);
            return (
              <g key={p.name} transform={`translate(${x},${y})`}>
                <circle r={p.excluded ? 5 : 8} fill={color} stroke={p.excluded ? "#A7A49C" : "#F7F5F1"} strokeWidth={1.6} />
                <text y={-14} textAnchor="middle" fontFamily="'Public Sans',sans-serif" fontWeight={500} fontSize={11.5} fill="#131F25">
                  {p.name}
                </text>
                <text y={22} textAnchor="middle" fontFamily="'IBM Plex Mono',monospace" fontWeight={500} fontSize={11} fill={p.excluded ? "#879196" : "#4E5A60"}>
                  {p.excluded ? "excluded" : moneyShort(p.net)}
                </text>
              </g>
            );
          })}

          <g transform={`translate(${PAD},${H - 26})`}>
            <text y={-10} fontFamily="'IBM Plex Mono',monospace" fontWeight={500} fontSize={10.5} letterSpacing="0.06em" fill="#4E5A60">
              NET BENEFIT
            </text>
            {[0, 1, 2, 3].map((i) => (
              <rect key={i} x={i * 26} y={0} width={26} height={7} fill={netColor(lo + ((hi - lo) * i) / 3, lo, hi)} />
            ))}
            <text x={0} y={20} fontFamily="'IBM Plex Mono',monospace" fontSize={10.5} fill="#879196">
              lower
            </text>
            <text x={104} y={20} textAnchor="end" fontFamily="'IBM Plex Mono',monospace" fontSize={10.5} fill="#879196">
              higher
            </text>
          </g>
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap gap-6 font-mono text-[11.5px] text-ink-2">
        <span>projection: schematic equirectangular (no boundary data)</span>
        <span>distances: illustrative only — see memo tab for computed relocation cost</span>
        <span>home base: {home.label}</span>
      </div>
    </div>
  );
}

const RED = [174, 69, 56];
const AMBER = [170, 106, 0];
const TEAL = [0, 134, 135];

function lerp(a: number[], b: number[], t: number): string {
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bl = Math.round(a[2] + (b[2] - a[2]) * t);
  return `rgb(${r},${g},${bl})`;
}

function netColor(v: number, lo: number, hi: number): string {
  if (hi <= lo) return `rgb(${TEAL.join(",")})`;
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
  return t < 0.5 ? lerp(RED, AMBER, t * 2) : lerp(AMBER, TEAL, (t - 0.5) * 2);
}
