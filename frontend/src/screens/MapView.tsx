import { geoMercator, geoPath } from "d3-geo";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import { useEffect, useMemo, useState } from "react";
import type { Topology } from "topojson-specification";
import { feature } from "topojson-client";
import { HOME_BASES } from "../data/examples";
import { moneyShort } from "../lib/format";
import type { BenefitBreakdown, JurisdictionRule } from "../types";

interface Row {
  rule: JurisdictionRule;
  benefit: BenefitBreakdown;
}

/**
 * Real geography, drawn from TopoJSON served out of public/geo as static
 * assets: Natural Earth world countries (110m) plus US Census state
 * boundaries (10m), both public domain, ~220KB combined and fetched only
 * when this tab is opened rather than bundled into the main chunk.
 *
 * Deliberately not a tile map (Google Maps JS, Mapbox): tiles would mean
 * another billed API surface and a key exposed to the browser, for a view
 * BUILD_BRIEF.md section 7 calls "a supporting view, not the hero". Vector
 * boundaries give real coastlines and borders with no key and no runtime
 * dependency on anyone else's uptime.
 *
 * Pin positions use each JurisdictionRule's real centroid_lat/lng. The
 * connecting lines are straight lines on the projection, not routes — the
 * actual routed distance behind relocation cost comes from the Maps
 * Distance Matrix call in maps_client.py, shown on the memo tab.
 */
export function MapView({ rows, homeBaseLabel }: { rows: Row[]; homeBaseLabel: string }) {
  const home = HOME_BASES.find((h) => h.label === homeBaseLabel) ?? HOME_BASES[0];
  const [geo, setGeo] = useState<{ countries: Feature<Geometry>[]; states: Feature<Geometry>[] } | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.BASE_URL;

    async function load(path: string, objectName: string): Promise<Feature<Geometry>[]> {
      const res = await fetch(`${base}geo/${path}`);
      if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
      const topology = (await res.json()) as Topology;
      const collection = feature(topology, topology.objects[objectName]) as FeatureCollection<Geometry>;
      return collection.features;
    }

    Promise.all([load("countries-110m.json", "countries"), load("states-10m.json", "states")])
      .then(([countries, states]) => {
        if (!cancelled) setGeo({ countries, states });
      })
      .catch((err) => {
        if (!cancelled) setGeoError(err instanceof Error ? err.message : String(err));
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const points = useMemo(
    () =>
      rows.map((r) => ({
        name: r.rule.jurisdiction,
        lat: r.rule.centroid_lat,
        lng: r.rule.centroid_lng,
        net: r.benefit.net_benefit,
        excluded: !r.benefit.computable,
        km: r.benefit.distance_km,
      })),
    [rows],
  );

  const W = 900;
  const H = 500;

  // Fit to the jurisdictions actually being compared, padded so no pin sits
  // on the edge — a US-only comparison zooms to the US, adding Ireland pulls
  // it out to the Atlantic, with no per-case special handling.
  const projection = useMemo(() => {
    const lats = [...points.map((p) => p.lat), home.lat];
    const lngs = [...points.map((p) => p.lng), home.lng];
    const pad = 6;
    const box: Feature<Geometry> = {
      type: "Feature",
      properties: {},
      geometry: {
        type: "MultiPoint",
        coordinates: [
          [Math.min(...lngs) - pad, Math.min(...lats) - pad],
          [Math.max(...lngs) + pad, Math.max(...lats) + pad],
        ],
      },
    };
    return geoMercator().fitExtent(
      [
        [24, 24],
        [W - 24, H - 56],
      ],
      box,
    );
  }, [points, home]);

  const path = useMemo(() => geoPath(projection), [projection]);
  const project = (lat: number, lng: number) => projection([lng, lat]) ?? [0, 0];

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
        {geoError && (
          <div className="flex h-[400px] flex-col items-center justify-center gap-2 px-8 text-center">
            <div className="font-sans text-[14px] font-semibold text-red">Map could not be drawn</div>
            <div className="max-w-[380px] font-sans text-[13px] leading-relaxed text-ink-2">
              {geoError}. Jurisdiction rankings on the memo tab are unaffected — the map is a supporting view only.
            </div>
          </div>
        )}

        {!geo && !geoError && (
          <div className="flex h-[400px] flex-col items-center justify-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-ink" />
            <div className="font-mono text-[12px] tracking-wide text-ink-2">LOADING BOUNDARY DATA</div>
          </div>
        )}

        {geo && (
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ display: "block" }}>
            <g>
              {geo.countries.map((f, i) => (
                <path key={`c${i}`} d={path(f) ?? undefined} fill="#F0EEEA" stroke="#DDDBD4" strokeWidth={0.7} />
              ))}
            </g>
            <g>
              {geo.states.map((f, i) => (
                <path key={`s${i}`} d={path(f) ?? undefined} fill="none" stroke="#DDDBD4" strokeWidth={0.5} />
              ))}
            </g>

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
                  opacity={0.7}
                />
              );
            })}

            <g transform={`translate(${hx},${hy})`}>
              <rect
                x={-6}
                y={-6}
                width={12}
                height={12}
                fill="#F7F5F1"
                stroke="#131F25"
                strokeWidth={2}
                transform="rotate(45)"
              />
              <text y={-16} textAnchor="middle" fontFamily="'Public Sans',sans-serif" fontWeight={600} fontSize={12} fill="#131F25">
                {home.label}
              </text>
              <text
                y={24}
                textAnchor="middle"
                fontFamily="'IBM Plex Mono',monospace"
                fontWeight={500}
                fontSize={10}
                letterSpacing="0.06em"
                fill="#4E5A60"
              >
                HOME BASE
              </text>
            </g>

            {points.map((p) => {
              const [x, y] = project(p.lat, p.lng);
              const color = p.excluded ? "#F7F5F1" : netColor(p.net, lo, hi);
              return (
                <g key={p.name} transform={`translate(${x},${y})`}>
                  <title>
                    {p.name}
                    {p.excluded
                      ? " — excluded from the ranking"
                      : ` — net ${moneyShort(p.net)}${p.km != null ? `, ${Math.round(p.km).toLocaleString()} km from ${home.label}` : ""}`}
                  </title>
                  <circle
                    r={p.excluded ? 5 : 8}
                    fill={color}
                    stroke={p.excluded ? "#A7A49C" : "#F7F5F1"}
                    strokeWidth={1.6}
                  />
                  <text y={-14} textAnchor="middle" fontFamily="'Public Sans',sans-serif" fontWeight={500} fontSize={11.5} fill="#131F25">
                    {p.name}
                  </text>
                  <text
                    y={22}
                    textAnchor="middle"
                    fontFamily="'IBM Plex Mono',monospace"
                    fontWeight={500}
                    fontSize={11}
                    fill={p.excluded ? "#879196" : "#4E5A60"}
                  >
                    {p.excluded ? "excluded" : moneyShort(p.net)}
                  </text>
                </g>
              );
            })}

            <g transform={`translate(24,${H - 26})`}>
              <text
                y={-10}
                fontFamily="'IBM Plex Mono',monospace"
                fontWeight={500}
                fontSize={10.5}
                letterSpacing="0.06em"
                fill="#4E5A60"
              >
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
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-6 font-mono text-[11.5px] text-ink-2">
        <span>boundaries: Natural Earth 110m + US Census 10m (public domain)</span>
        <span>lines are straight, not routes — routed distance is on the memo tab</span>
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

export function netColor(v: number, lo: number, hi: number): string {
  if (hi <= lo) return `rgb(${TEAL.join(",")})`;
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
  return t < 0.5 ? lerp(RED, AMBER, t * 2) : lerp(AMBER, TEAL, (t - 0.5) * 2);
}
