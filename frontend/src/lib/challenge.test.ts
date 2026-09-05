import { describe, expect, it } from "vitest";
import { challengeState, minorFindings } from "./challenge";
import type { ChallengeFinding, ChallengeReport } from "../types";

function finding(severity: ChallengeFinding["severity"], field_name = "base_rate"): ChallengeFinding {
  return {
    field_name,
    current_value: "30.0%",
    source_says: "20%",
    url: "https://example.gov/hb1001",
    excerpt: "reduced to 20%",
    severity,
  };
}

function report(over: Partial<ChallengeReport> = {}): ChallengeReport {
  return {
    jurisdiction: "Georgia",
    findings: [],
    corroborated_fields: [],
    sources_checked: 4,
    ...over,
  };
}

describe("challengeState", () => {
  it("reports a material contradiction", () => {
    const state = challengeState(report({ findings: [finding("material")] }));
    expect(state.status).toBe("contradicted");
    expect(state).toMatchObject({ count: 1 });
  });

  it("counts multiple contradictions rather than only flagging one", () => {
    const state = challengeState(report({ findings: [finding("material"), finding("material", "pool_status")] }));
    expect(state).toMatchObject({ status: "contradicted", count: 2 });
    expect(state.status === "contradicted" && state.label).toContain("2 sources");
  });

  it("does not treat a minor disagreement as a contradiction", () => {
    // A wrong phone number is not a wrong tax rate, and flagging the whole
    // jurisdiction over one trains a reader to ignore the flag.
    const state = challengeState(report({ findings: [finding("minor", "film_office_contact")] }));
    expect(state.status).toBe("corroborated");
  });

  it("distinguishes 'we checked and found nothing' from 'we couldn't check'", () => {
    // The most important distinction in this module: rendering these the
    // same way turns a failed check into a clean bill of health.
    const checked = challengeState(report({ sources_checked: 4 }));
    const nothingToRead = challengeState(report({ sources_checked: 0 }));

    expect(checked.status).toBe("corroborated");
    expect(nothingToRead.status).toBe("unchecked");
  });

  it("says how many sources backed a clean result, so it can be judged", () => {
    const state = challengeState(report({ sources_checked: 7 }));
    expect(state.status === "corroborated" && state.label).toContain("7 sources");
  });

  it("treats a failed pass as unchecked, never as clean", () => {
    expect(challengeState("failed").status).toBe("unchecked");
  });

  it("is checking while in flight and before it has started", () => {
    expect(challengeState("checking").status).toBe("checking");
    expect(challengeState(undefined).status).toBe("checking");
  });
});

describe("minorFindings", () => {
  it("returns only the minor ones, which are recorded but never downgrade", () => {
    const r = report({ findings: [finding("material"), finding("minor", "program_name")] });
    expect(minorFindings(r).map((f) => f.field_name)).toEqual(["program_name"]);
  });

  it("returns nothing for a pass that never produced a report", () => {
    expect(minorFindings("failed")).toEqual([]);
    expect(minorFindings(undefined)).toEqual([]);
  });
});
