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
/**
 * The label that goes on a home-base-to-jurisdiction line, and how to orient it.
 *
 * Pulled out of the component because the component can't be rendered without
 * a browser: the map body is gated on a geography fetch that happens in an
 * effect, so static rendering only ever exercises the loading state. This is
 * the part with actual logic in it, and it's testable on its own.
 *
 * Returns null where there's nothing honest to say — no distance measured, or
 * a jurisdiction that isn't ranked at all.
 */
export function relocationLabel(
  km: number | null | undefined,
  relocation: number,
  excluded: boolean,
): string | null {
  if (excluded || km == null) return null;
  return `${Math.round(km).toLocaleString()} km · ${moneyShort(-relocation)}`;
}

/**
 * Degrees to rotate a label so it runs along its line and still reads
 * left-to-right. Without the flip, every westward line renders its text
 * upside down — which is most of them for a US production travelling east.
 */
export function labelAngle(dx: number, dy: number): number {
  // atan2 gives (-180, 180]. Fold the back half onto the front so the result
  // always lands in [-90, 90] and the text reads left-to-right.
  //
  // Adding 180 instead of subtracting it renders identically — rotate(315)
  // and rotate(-45) are the same picture — but returns values like 360 for a
  // due-west line, which is why this is a subtraction and why the test pins
  // the range rather than just eyeballing the output.
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
  if (angle > 90) return angle - 180;
  if (angle < -90) return angle + 180;
  return angle;
}

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
        relocation: r.benefit.relocation_cost,
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
        <div className="flex items-center gap-2 font-mono text-[11px] font-medium tracking-wide text-ink-3">
          <span aria-hidden className="h-2 w-2 shrink-0 bg-teal" />
          GEOGRAPHY · SUPPORTING VIEW
        </div>
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
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full"
            style={{ display: "block" }}
            aria-label={`Map of net benefit by jurisdiction relative to home base ${home.label}`}
          >
            <g aria-hidden>
              {geo.countries.map((f, i) => (
                <path key={`c${i}`} d={path(f) ?? undefined} fill="#F0EEEA" stroke="#DDDBD4" strokeWidth={0.7} />
              ))}
            </g>
            <g aria-hidden>
              {geo.states.map((f, i) => (
                <path key={`s${i}`} d={path(f) ?? undefined} fill="none" stroke="#DDDBD4" strokeWidth={0.5} />
              ))}
            </g>

            {points.map((p) => {
              const [x, y] = project(p.lat, p.lng);
              // Label the line with what the distance actually costs. Until
              // now this lived only in a hover tooltip, so the one number the
              // map exists to explain — relocation, one of the four
              // components of the net figure — was invisible unless you knew
              // to point at a pin. Nobody hovers during a demo.
              const label = relocationLabel(p.km, p.relocation, p.excluded);
              // Sit the text at the midpoint, rotated along the line, and
              // flipped where it would otherwise render upside down.
              const mx = (hx + x) / 2;
              const my = (hy + y) / 2;
              const angle = labelAngle(x - hx, y - hy);
              return (
                <g key={`line-${p.name}`}>
                  <line
                    aria-hidden
                    x1={hx}
                    y1={hy}
                    x2={x}
                    y2={y}
                    stroke={p.excluded ? "#C0BDB6" : netColor(p.net, lo, hi)}
                    strokeWidth={1}
                    strokeDasharray={p.excluded ? "3 3" : undefined}
                    opacity={0.7}
                  />
                  {label && (
                    <g transform={`translate(${mx},${my}) rotate(${angle})`}>
                      {/* Painted behind the text so it stays legible where a
                          line crosses a coastline or another route. */}
                      <text
                        y={-4}
                        textAnchor="middle"
                        fontFamily="'IBM Plex Mono',monospace"
                        fontSize={10}
                        stroke="#FBFAF7"
                        strokeWidth={3.5}
                        strokeLinejoin="round"
                      >
                        {label}
                      </text>
                      <text
                        y={-4}
                        textAnchor="middle"
                        fontFamily="'IBM Plex Mono',monospace"
                        fontSize={10}
                        fill="#57534C"
                      >
                        {label}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            <g transform={`translate(${hx},${hy})`}>
              <rect
                aria-hidden
                x={-6}
                y={-6}
                width={12}
                height={12}
                fill="#F7F5F1"
                stroke="#1a2630"
                strokeWidth={2}
                transform="rotate(45)"
              />
              <text y={-16} textAnchor="middle" fontFamily="'Public Sans',sans-serif" fontWeight={600} fontSize={12} fill="#1a2630">
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
              const pointLabel = `${p.name}${
                p.excluded
                  ? " — excluded from the ranking"
                  : ` — net ${moneyShort(p.net)}${p.km != null ? `, ${Math.round(p.km).toLocaleString()} km from ${home.label}` : ""}`
              }`;
              return (
                <g key={p.name} transform={`translate(${x},${y})`} tabIndex={0} role="img" aria-label={pointLabel}>
                  <title>{pointLabel}</title>
                  <circle
                    r={p.excluded ? 5 : 8}
                    fill={color}
                    stroke={p.excluded ? "#A7A49C" : "#F7F5F1"}
                    strokeWidth={1.6}
                  />
                  <text y={-14} textAnchor="middle" fontFamily="'Public Sans',sans-serif" fontWeight={500} fontSize={11.5} fill="#1a2630">
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
                <rect aria-hidden key={i} x={i * 26} y={0} width={26} height={7} fill={netColor(lo + ((hi - lo) * i) / 3, lo, hi)} />
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
