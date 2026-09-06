import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ComparisonTable } from "./ComparisonTable";
import { FundingAvailability, SourceEvidence } from "./Evidence";
import { MapView, labelAngle, relocationLabel } from "./MapView";
import type { Row } from "../lib/explain";
import type { BenefitBreakdown, JurisdictionRule, SourceRef } from "../types";

/**
 * Render coverage for the screens that had none.
 *
 * Recommendation.tsx got render tests first because it's newest; these four
 * are older and were equally unexecuted by any check in this project — a
 * crash on first render would pass tsc, vitest and vite build alike.
 *
 * The data below is the real hand-verified seed set as computed by the live
 * /compute endpoint on 6 Sep, not invented numbers, so these also pin what
 * the screens do with the shapes they actually receive: a discretionary
 * jurisdiction that can't be ranked, a transferable credit, a refundable one,
 * and a rule with no sources at all.
 */

function rule(over: Partial<JurisdictionRule> = {}): JurisdictionRule {
  return {
    jurisdiction: "Georgia",
    program_name: "Georgia Entertainment Industry Investment Act",
    base_rate: 0.2,
    credit_type: "transferable",
    pool_status: "open",
    confidence: "primary_source",
    conflicts: [],
    sources: [],
    constraint_gaps: {},
    minimum_spend: 500_000,
    per_person_wage_cap: 500_000,
    annual_pool_total: null,
    annual_pool_remaining: null,
    application_deadline: null,
    sunset_date: null,
    under_review: false,
    is_discretionary: false,
    film_office_contact: null,
    centroid_lat: 33.749,
    centroid_lng: -84.388,
    uplifts: [],
    tiers: [],
    currency: "USD",
    ...over,
  } as JurisdictionRule;
}

function benefit(over: Partial<BenefitBreakdown> = {}): BenefitBreakdown {
  return {
    jurisdiction: "Georgia",
    qualifying_spend: 2_000_000,
    gross_credit: 400_000,
    realizable_credit: 360_000,
    caps_applied: [],
    distance_km: null,
    travel_time_hours: null,
    relocation_cost: 104_100,
    relocation_components: {},
    audit_cost: 0,
    months_to_payment: 18,
    timing_is_assumed: true,
    present_value: 303_721,
    timing_note: null,
    monetization_note: null,
    net_benefit: 199_621,
    computable: true,
    non_computable_reason: null,
    ...over,
  } as BenefitBreakdown;
}

/** The real ranking, hand-verified against the statutes on 6 Sep 2026. */
const ROWS: Row[] = [
  {
    rule: rule({ jurisdiction: "Louisiana", base_rate: 0.25, centroid_lat: 30.451, centroid_lng: -91.187 }),
    benefit: benefit({ jurisdiction: "Louisiana", gross_credit: 500_000, realizable_credit: 450_000,
      present_value: 379_652, months_to_payment: 15, net_benefit: 275_552 }),
  },
  {
    rule: rule({ jurisdiction: "New Mexico", base_rate: 0.25, credit_type: "refundable",
      centroid_lat: 35.084, centroid_lng: -106.651 }),
    benefit: benefit({ jurisdiction: "New Mexico", qualifying_spend: 1_662_500, gross_credit: 415_625,
      realizable_credit: 415_625, present_value: 371_094, months_to_payment: 12, net_benefit: 266_994 }),
  },
  { rule: rule(), benefit: benefit() },
  {
    rule: rule({ jurisdiction: "Texas", is_discretionary: true, centroid_lat: 30.267, centroid_lng: -97.743 }),
    benefit: benefit({ jurisdiction: "Texas", qualifying_spend: 0, gross_credit: 0, realizable_credit: 0,
      present_value: 0, relocation_cost: 0, net_benefit: 0, computable: false,
      non_computable_reason: "Discretionary/jury-allocated program; benefit is not modelable." }),
  },
];

const text = (m: string) => m.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();

describe("ComparisonTable", () => {
  it("renders every ranked jurisdiction and separates the unrankable one", () => {
    const body = text(renderToStaticMarkup(<ComparisonTable rows={ROWS} failingFor={() => null} />));

    for (const name of ["Louisiana", "New Mexico", "Georgia", "Texas"]) {
      expect(body).toContain(name);
    }
    // Texas can't be ranked, so its reason has to appear rather than a $0 row
    // sitting silently at the bottom of the table as if it lost on merit.
    expect(body).toContain("Discretionary");
  });

  it("surfaces a failing constraint instead of dropping the jurisdiction", () => {
    const body = text(
      renderToStaticMarkup(
        <ComparisonTable
          rows={ROWS}
          failingFor={(r) => (r.jurisdiction === "New Mexico" ? "New Mexico has no ocean coastline." : null)}
        />,
      ),
    );
    expect(body).toContain("New Mexico");
    expect(body).toContain("coastline");
  });

  it("renders with no rows at all rather than throwing", () => {
    expect(() => renderToStaticMarkup(<ComparisonTable rows={[]} failingFor={() => null} />)).not.toThrow();
  });
});

describe("Evidence", () => {
  const source: SourceRef = {
    url: "https://law.justia.com/codes/georgia/title-48/chapter-7/article-2/section-48-7-40-26/",
    retrieved: "2026-09-06",
    published: null,
    excerpt: "a tax credit equal to 20 percent of the base investment in this state",
    is_primary: true,
  };

  it("shows the source host, its retrieved date and the quoted excerpt", () => {
    const body = text(renderToStaticMarkup(<SourceEvidence rule={rule({ sources: [source] })} />));
    expect(body).toContain("law.justia.com");
    // Cinematic UI pass: the retrieved date renders as a timecode badge
    // (dots, not dashes) — see Evidence.tsx's RetrievedBadge.
    expect(body).toContain("2026·09·06");
    expect(body).toContain("20 percent");
  });

  it("handles a source with an empty excerpt rather than rendering a blank quote", () => {
    const body = text(renderToStaticMarkup(<SourceEvidence rule={rule({ sources: [{ ...source, excerpt: "" }] })} />));
    expect(body).toContain("law.justia.com");
  });

  it("renders a rule with no sources at all", () => {
    // Extraction can legitimately return none, and "unverified" confidence is
    // the honest result — it must not be a crash.
    expect(() => renderToStaticMarkup(<SourceEvidence rule={rule({ sources: [] })} />)).not.toThrow();
  });

  it("states funding availability for each pool status", () => {
    for (const status of ["open", "capping_out", "closed", "unknown"] as const) {
      const body = text(renderToStaticMarkup(<FundingAvailability rule={rule({ pool_status: status })} />));
      expect(body.length).toBeGreaterThan(0);
    }
  });

  it("states the pool figures rather than the status, which the badge carries", () => {
    // Division of responsibility, asserted because it isn't obvious: this
    // panel lists funding *facts* (pool size, deadlines, sunset, review) and
    // the status pill beside the jurisdiction name carries open/capping
    // out/closed. A closed pool never reaches this panel at all — the
    // availability gate makes it non-computable, so it renders in the
    // "can't verify" section with its reason instead.
    const withFigures = text(
      renderToStaticMarkup(
        <FundingAvailability rule={rule({ annual_pool_total: 150_000_000, annual_pool_remaining: 12_000_000 })} />,
      ),
    );
    expect(withFigures).toContain("$12,000,000 left of a $150,000,000 annual pool");
  });

  it("says an uncapped program is uncapped instead of rendering nothing", () => {
    // Georgia genuinely has no annual cap, and "no cap found" is the answer,
    // not a gap in the data.
    const body = text(renderToStaticMarkup(<FundingAvailability rule={rule({ pool_status: "open" })} />));
    expect(body).toContain("no annual cap found in sources");
  });

  it("surfaces a deadline, a sunset and legislative review together", () => {
    const body = text(
      renderToStaticMarkup(
        <FundingAvailability
          rule={rule({ application_deadline: "2027-01-15", sunset_date: "2028-06-30", under_review: true })}
        />,
      ),
    );
    expect(body).toContain("2027-01-15");
    expect(body).toContain("2028-06-30");
    expect(body).toContain("under legislative review");
  });
});

describe("MapView", () => {
  it("renders before the geography files have loaded", () => {
    // Geo is fetched in an effect, which never runs under static rendering —
    // so this is exactly the first-paint state a real browser shows too, and
    // it must not throw or render an empty frame.
    const markup = renderToStaticMarkup(<MapView rows={ROWS} homeBaseLabel="Los Angeles, CA" />);
    expect(markup.length).toBeGreaterThan(0);
  });

  it("does not crash on an unrecognised home base", () => {
    // home_base is a free-text field on BudgetVector; anything not in
    // HOME_BASES has to fall back rather than dereference undefined.
    expect(() => renderToStaticMarkup(<MapView rows={ROWS} homeBaseLabel="Reykjavik" />)).not.toThrow();
  });

  it("does not crash with no jurisdictions to plot", () => {
    expect(() => renderToStaticMarkup(<MapView rows={[]} homeBaseLabel="Los Angeles, CA" />)).not.toThrow();
  });
});

describe("map line labels", () => {
  // What the distance actually costs, put on the line rather than left in a
  // hover tooltip. Google Maps returned real routed distances from the start,
  // but until airfare scaled with distance they changed no number, and even
  // after that the figure was only visible if you knew to point at a pin.
  // Nobody hovers during a demo.

  it("states the distance and what it costs, in one string", () => {
    expect(relocationLabel(3747, 115_344, false)).toBe("3,747 km · −$115k");
    expect(relocationLabel(1412, 111_142, false)).toBe("1,412 km · −$111k");
  });

  it("says nothing when there is nothing honest to say", () => {
    // No Maps result for this jurisdiction: relocation excludes travel
    // entirely, so a label would imply a measurement we don't have.
    expect(relocationLabel(null, 104_100, false)).toBeNull();
    // Not ranked at all — labelling its travel cost invites comparison with
    // jurisdictions that were actually computed.
    expect(relocationLabel(3747, 115_344, true)).toBeNull();
  });

  it("keeps labels upright on lines running in any direction", () => {
    // The flip matters: for a US production travelling east, most lines run
    // right-to-left on screen, and without it every one renders upside down.
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [-3, -2], [2, -5], [-4, 3]]) {
      const a = labelAngle(dx, dy);
      expect(a).toBeGreaterThanOrEqual(-90);
      expect(a).toBeLessThanOrEqual(90);
    }
  });

  it("orients a due-east line flat and a due-west line flat too", () => {
    expect(labelAngle(1, 0)).toBe(0);
    expect(labelAngle(-1, 0)).toBe(0);
  });
});
