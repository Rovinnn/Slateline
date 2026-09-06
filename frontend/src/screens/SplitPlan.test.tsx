import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SplitRecommendation } from "./SplitPlan";
import type { BenefitBreakdown, SplitPlan, SplitResponse } from "../types";

const leg = (spend: number, net: number, gross = net) =>
  ({ qualifying_spend: spend, gross_credit: gross, net_benefit: net, computable: true,
     caps_applied: [], relocation_cost: 0, present_value: net } as unknown as BenefitBreakdown);

const plan = (shoot: string, post: string, net: number, warnings: string[] = []): SplitPlan => ({
  shoot_in: shoot, post_in: post, shoot_leg: leg(1_750_000, net), post_leg: shoot === post ? null : leg(250_000, 0),
  net_benefit: net, warnings,
});

/** Strip tags and decode the entities React escapes, so assertions can be
 *  written the way the text actually reads rather than as &#x27; soup. */
const text = (m: string) =>
  m
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();

describe("SplitRecommendation", () => {
  const winning: SplitResponse = {
    best: plan("Louisiana", "New Mexico", 273_911),
    best_single: plan("Louisiana", "Louisiana", 265_564),
    plans: [
      plan("Louisiana", "New Mexico", 273_911),
      plan("Louisiana", "Georgia", 218_107, [
        "Splitting drops post and VFX in Georgia below its minimum spend, so that leg earns nothing.",
      ]),
    ],
    splitting_wins: true,
    gain_over_single: 8_347,
  };

  it("names both jurisdictions and what the split is worth", () => {
    const body = text(renderToStaticMarkup(<SplitRecommendation split={winning} />));
    expect(body).toContain("Shoot in Louisiana, post in New Mexico");
    expect(body).toContain("$8k more than Louisiana alone");
    expect(body).toContain("$273,911");
    expect(body).toContain("$265,564");
  });

  it("warns about splits that destroy a credit, not just ones that score low", () => {
    // The trap a single-destination ranking can never reveal.
    const body = text(renderToStaticMarkup(<SplitRecommendation split={winning} />));
    expect(body).toContain("SPLITS THAT DESTROY A CREDIT");
    expect(body).toContain("below its minimum spend");
  });

  it("says plainly when splitting is the wrong move", () => {
    // A panel that only appeared on a win would teach nothing on the runs it
    // stayed silent. "Don't split, and here's why" is the more common answer.
    const losing: SplitResponse = { ...winning, best: winning.best_single, splitting_wins: false, gain_over_single: 0 };
    const body = text(renderToStaticMarkup(<SplitRecommendation split={losing} />));
    expect(body).toContain("Don't split");
    expect(body).toContain("Louisiana alone is the best plan");
  });

  it("renders a single-location best plan without inventing a second leg", () => {
    const single: SplitResponse = {
      best: plan("Georgia", "Georgia", 188_825), best_single: plan("Georgia", "Georgia", 188_825),
      plans: [plan("Georgia", "Georgia", 188_825)], splitting_wins: false, gain_over_single: 0,
    };
    expect(() => renderToStaticMarkup(<SplitRecommendation split={single} />)).not.toThrow();
  });
});
