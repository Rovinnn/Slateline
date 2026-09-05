import type { ChallengeReport } from "../types";

/**
 * How a jurisdiction's falsification pass reads on screen.
 *
 * Four states, and the distinction that matters most is between the last two:
 * a pass that found nothing because it read four sources and none disagreed
 * is real evidence, while a pass that found nothing because it had nothing to
 * read is evidence of nothing at all. Rendering those identically would turn
 * a failed check into a clean bill of health, which is the most damaging
 * thing this feature could do.
 */
export type ChallengeState =
  /** Still running — the ranking renders first, this annotates it after. */
  | { status: "checking" }
  /** A source explicitly disagrees with a figure the ranking depends on. */
  | { status: "contradicted"; count: number; label: string }
  /** Checked against real sources; nothing material disagreed. */
  | { status: "corroborated"; label: string }
  /** Ran, but had nothing to check against, or couldn't run at all. */
  | { status: "unchecked"; label: string };

export function challengeState(report: ChallengeReport | "checking" | "failed" | undefined): ChallengeState {
  if (report === undefined || report === "checking") return { status: "checking" };
  if (report === "failed") {
    return { status: "unchecked", label: "couldn't re-check this program" };
  }

  const material = report.findings.filter((f) => f.severity === "material");
  if (material.length > 0) {
    return {
      status: "contradicted",
      count: material.length,
      label:
        material.length === 1
          ? "a source disagrees with this program's terms"
          : `${material.length} sources disagree with this program's terms`,
    };
  }

  // Zero sources read is not a clean result, however encouraging the empty
  // findings list looks.
  if (report.sources_checked === 0) {
    return { status: "unchecked", label: "no sources found to re-check against" };
  }

  return {
    status: "corroborated",
    label: `re-checked against ${report.sources_checked} sources — nothing contradicts it`,
  };
}

/** Minor disagreements, which are recorded but never downgrade confidence. */
export function minorFindings(report: ChallengeReport | "checking" | "failed" | undefined) {
  if (!report || report === "checking" || report === "failed") return [];
  return report.findings.filter((f) => f.severity === "minor");
}
