import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { EffectiveRate, Waterfall, WhyItWins } from "./Recommendation";
import type { Row } from "../lib/explain";
import type { BenefitBreakdown, JurisdictionRule } from "../types";

/**
 * Render tests for the two components carrying the recommendation.
 *
 * Every other test in this project checks pure functions, which left all six
 * screens with no coverage at all: a component could throw on its first
 * render and `tsc`, `vitest` and `vite build` would all stay green, because
 * none of them execute it. That gap is worth closing here first — the
 * waterfall and "why it wins" are the newest UI and the two the whole memo
 * rests on.
 *
 * react-dom/server rather than a testing library: this needs to answer "does
 * it render, with the right numbers in it", not "what happens when a user
 * clicks". Static markup answers that with no new dependency and no DOM.
 *
 * What this cannot check is what it looks like — spacing, overflow, whether
 * a bar is visible. Those still need a browser.
 */

function rule(over: Partial<JurisdictionRule> = {}): JurisdictionRule {
  return {
    jurisdiction: "New Mexico",
    base_rate: 0.25,
    credit_type: "refundable",
    ...over,
  } as JurisdictionRule;
}

function benefit(over: Partial<BenefitBreakdown> = {}): BenefitBreakdown {
  const base = {
    qualifying_spend: 2_000_000,
    gross_credit: 500_000,
    realizable_credit: 500_000,
    relocation_cost: 114_900,
    caps_applied: [],
    distance_km: 1000,
    monetization_note: null,
    audit_cost: 0,
    months_to_payment: 12,
    timing_is_assumed: true,
    present_value: 446_429,
    timing_note: null,
    computable: true,
  };
  return { ...base, ...over } as BenefitBreakdown;
}

function row(r: Partial<JurisdictionRule> = {}, b: Partial<BenefitBreakdown> = {}): Row {
  const built = benefit(b);
  return { rule: rule(r), benefit: { ...built, net_benefit: built.present_value - built.relocation_cost } };
}

/** Markup with tags stripped, for asserting on what a reader actually sees. */
function text(markup: string): string {
  return markup.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

describe("Waterfall", () => {
  it("renders every stage from qualifying spend down to net benefit", () => {
    const body = text(renderToStaticMarkup(<Waterfall row={row()} />));

    expect(body).toContain("Qualifying spend");
    expect(body).toContain("Credit at 25.0%");
    expect(body).toContain("Relocation cost");
    expect(body).toContain("Net benefit");
    expect(body).toContain("$331,529"); // 446,429 - 114,900
  });

  it("shows the full walk for a discounted, audited, slow-paying credit", () => {
    const markup = renderToStaticMarkup(
      <Waterfall
        row={row(
          { jurisdiction: "Georgia", base_rate: 0.3, credit_type: "transferable" },
          {
            gross_credit: 600_000,
            realizable_credit: 540_000,
            audit_cost: 15_000,
            months_to_payment: 18,
            present_value: 439_000,
            monetization_note: "sold at about 90% of face",
          },
        )}
      />,
    );
    const body = text(markup);

    expect(body).toContain("Monetisation discount");
    expect(body).toContain("Audit and compliance");
    expect(body).toContain("Waiting 18 months to be paid");
    expect(body).toContain("Worth today");
    // The note explaining the discount has to survive into the markup, not
    // just exist on the step object.
    expect(body).toContain("sold at about 90% of face");
  });

  it("renders bar widths as percentages that stay inside the container", () => {
    // A bar wider than 100% silently overflows its row — invisible to every
    // other check in this project, and the kind of thing only rendering finds.
    const markup = renderToStaticMarkup(
      <Waterfall row={row({}, { qualifying_spend: 2_000_000, gross_credit: 500_000 })} />,
    );
    const widths = [...markup.matchAll(/width:\s*([\d.]+)%/g)].map((m) => parseFloat(m[1]));

    expect(widths.length).toBeGreaterThan(3);
    for (const w of widths) {
      expect(w).toBeGreaterThan(0);
      expect(w).toBeLessThanOrEqual(100);
    }
  });

  it("survives a jurisdiction with no credit at all", () => {
    // The refusal paths produce exactly this shape, and the hero still has to
    // render it rather than throwing on a zero.
    const markup = renderToStaticMarkup(
      <Waterfall
        row={row({}, { qualifying_spend: 0, gross_credit: 0, realizable_credit: 0, present_value: 0, relocation_cost: 0 })}
      />,
    );
    expect(text(markup)).toContain("Net benefit");
  });

  it("says whether a payment timeline was sourced or assumed", () => {
    const sourced = text(
      renderToStaticMarkup(
        <Waterfall row={row({}, { months_to_payment: 4, present_value: 480_000, timing_is_assumed: false })} />,
      ),
    );
    expect(sourced).toContain("stated by a source");
  });
});

describe("WhyItWins", () => {
  const winner = row({ jurisdiction: "New Mexico", base_rate: 0.25, credit_type: "refundable" });
  const rival = row(
    { jurisdiction: "Georgia", base_rate: 0.3, credit_type: "transferable" },
    { gross_credit: 600_000, realizable_credit: 540_000, present_value: 439_000, relocation_cost: 130_000 },
  );

  it("names the winner and accounts for the gap", () => {
    const body = text(renderToStaticMarkup(<WhyItWins winner={winner} rival={rival} />));

    expect(body).toContain("WHY NEW MEXICO WINS");
    expect(body).toContain("Net advantage over Georgia");
  });

  it("states the thesis when the winner has the lower headline rate", () => {
    const body = text(renderToStaticMarkup(<WhyItWins winner={winner} rival={rival} />));
    expect(body).toContain("lower headline rate");
  });

  it("renders components working against the winner rather than hiding them", () => {
    // The honesty requirement, checked at the rendering layer and not only in
    // the logic that produces it.
    const costlier = row(
      { jurisdiction: "New Mexico", credit_type: "refundable" },
      { relocation_cost: 200_000, present_value: 446_429 },
    );
    const body = text(renderToStaticMarkup(<WhyItWins winner={costlier} rival={rival} />));

    expect(body).toContain("More expensive to relocate to");
    expect(body).toMatch(/−\$\d/);
  });

  it("renders nothing at all when two jurisdictions are identical", () => {
    // No deltas means no explanation to give; an empty bordered box would be
    // worse than absence.
    const markup = renderToStaticMarkup(<WhyItWins winner={winner} rival={row()} />);
    expect(markup).toBe("");
  });
});

describe("EffectiveRate", () => {
  it("puts the advertised rate next to what actually arrives", () => {
    // Georgia: marketed as 30%, returning $175,722 on a $2M budget.
    const georgia = {
      rule: {
        jurisdiction: "Georgia", base_rate: 0.2, credit_type: "transferable",
        uplifts: [{ condition: "GEP logo", bonus_rate: 0.1, machine_checkable: false }],
      },
      benefit: benefit({ net_benefit: 175_722, present_value: 291_066, relocation_cost: 115_344 }),
    } as unknown as Row;

    const body = text(renderToStaticMarkup(<EffectiveRate row={georgia} totalBudget={2_000_000} />));
    expect(body).toContain("30.0%");
    expect(body).toContain("8.8%");
    expect(body).toContain("ADVERTISED AS UP TO");
    expect(body).toContain("YOU ACTUALLY KEEP");
  });

  it("labels the advertised figure honestly when there are no uplifts to add", () => {
    const body = text(renderToStaticMarkup(<EffectiveRate row={row()} totalBudget={2_000_000} />));
    expect(body).toContain("ADVERTISED RATE");
    expect(body).not.toContain("UP TO");
  });

  it("shows a negative return and says what it means", () => {
    // The only case where the honest answer is "don't go" — clamping it to
    // zero would hide that entirely.
    const costly = row({}, { net_benefit: -40_000, present_value: 60_000, relocation_cost: 100_000 });
    const body = text(renderToStaticMarkup(<EffectiveRate row={costly} totalBudget={2_000_000} />));
    expect(body).toContain("-2.0%");
    expect(body).toContain("costs more to reach than its credit is worth");
  });

  it("renders nothing rather than dividing by a budget of zero", () => {
    expect(renderToStaticMarkup(<EffectiveRate row={row()} totalBudget={0} />)).toBe("");
  });
});
