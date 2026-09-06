import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { OpenQuestions } from "./OpenQuestions";
import type { OpenQuestion } from "../types";

const q = (question: string, worth: number, ask = "Georgia film office"): OpenQuestion => ({
  question, worth, ask, basis: "recomputed with the question answered the other way",
});

const text = (m: string) =>
  m.replace(/<[^>]*>/g, " ").replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();

describe("OpenQuestions", () => {
  const questions = [
    q("Is the annual funding pool still open?", -260_215, "New Mexico film office"),
    q("Does this production qualify for the rural uplift?", 148_437),
    q("Do employer payroll fringes count as qualified spend?", 51_025),
  ];

  it("shows what each unknown is worth, signed", () => {
    const body = text(renderToStaticMarkup(<OpenQuestions questions={questions} jurisdiction="New Mexico" />));
    expect(body).toContain("−$260k");
    expect(body).toContain("+$148k");
    expect(body).toContain("AT RISK");
    expect(body).toContain("IF CONFIRMED");
  });

  it("says who answers each one, because advice you can't act on isn't advice", () => {
    const body = text(renderToStaticMarkup(<OpenQuestions questions={questions} jurisdiction="New Mexico" />));
    expect(body).toContain("ask: New Mexico film office");
  });

  it("counts the risks separately in the header", () => {
    const body = text(renderToStaticMarkup(<OpenQuestions questions={questions} jurisdiction="New Mexico" />));
    expect(body).toContain("3 unresolved questions");
    expect(body).toContain("1 at risk");
  });

  it("states that the figures come from the calculator, not an estimate", () => {
    // These sit beside verified numbers, so the provenance has to be on screen
    // or a reader can't tell which kind of figure they're looking at.
    const body = text(renderToStaticMarkup(<OpenQuestions questions={questions} jurisdiction="New Mexico" />));
    expect(body).toContain("not an estimate");
  });

  it("renders nothing when there is nothing left to confirm", () => {
    // An empty "before you commit" box would imply the tool had stopped
    // checking rather than found everything settled.
    expect(renderToStaticMarkup(<OpenQuestions questions={[]} jurisdiction="Georgia" />)).toBe("");
  });

  it("uses singular wording for a single question", () => {
    const body = text(renderToStaticMarkup(<OpenQuestions questions={[questions[1]]} jurisdiction="Georgia" />));
    expect(body).toContain("1 unresolved question,");
    expect(body).not.toContain("at risk");
  });
});
