import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RobustnessPanel } from "./RobustnessPanel";
import type { Robustness } from "../types";

const text = (m: string) =>
  m.replace(/<[^>]*>/g, " ").replace(/&#x27;/g, "'").replace(/&rarr;|&#x2192;/g, "→").replace(/\s+/g, " ").trim();

const base: Robustness = {
  winner: "Louisiana",
  runner_up: "New Mexico",
  margin: 5_349,
  winner_holds_in: 375,
  combinations_tested: 625,
  flips: [
    { input_name: "Local hire", threshold: "above 62%", new_winner: "New Mexico",
      because: "you estimated this; nothing verified it" },
  ],
  inputs_swept: [
    { name: "Local hire", assumed: "55%", low_label: "lower", high_label: "higher",
      because: "you estimated this; nothing verified it" },
  ],
};

describe("RobustnessPanel", () => {
  it("says plainly when a margin is narrower than the uncertainty", () => {
    // The whole point: $5,349 and $76,739 look identical as single figures,
    // and presenting them with equal confidence is the most misleading thing
    // this tool could do.
    const body = text(renderToStaticMarkup(<RobustnessPanel robustness={base} />));
    expect(body).toContain("wins in 60% of combinations");
    expect(body).toContain("narrower than what we don't know");
    expect(body).toContain("close rather than settled");
  });

  it("names the threshold that would change the answer", () => {
    // Actionable, unlike a probability: a producer can go confirm local hire.
    const body = text(renderToStaticMarkup(<RobustnessPanel robustness={base} />));
    expect(body).toContain("Local hire above 62%");
    expect(body).toContain("New Mexico wins instead");
  });

  it("states a robust result without hedging it", () => {
    const robust: Robustness = { ...base, margin: 76_739, winner_holds_in: 625, flips: [] };
    const body = text(renderToStaticMarkup(<RobustnessPanel robustness={robust} />));
    expect(body).toContain("wins in every combination tested");
    expect(body).toContain("wider than anything we're unsure about");
    expect(body).not.toContain("close rather than settled");
  });

  it("shows what was varied and why each thing is uncertain", () => {
    // A confidence figure with no visible basis is just a vibe.
    const body = text(renderToStaticMarkup(<RobustnessPanel robustness={base} />));
    expect(body).toContain("WHAT WAS VARIED");
    expect(body).toContain("assumed 55%");
    expect(body).toContain("nothing verified it");
  });

  it("renders nothing when there was nothing to vary", () => {
    expect(renderToStaticMarkup(
      <RobustnessPanel robustness={{ ...base, combinations_tested: 0, inputs_swept: [] }} />,
    )).toBe("");
  });
});
