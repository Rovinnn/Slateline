import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LeagueTable } from "./LeagueTable";

const text = (m: string) => m.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();

describe("LeagueTable", () => {
  it("renders a loading state before the measurements arrive", () => {
    // The fetch lives in an effect, which never runs under static rendering —
    // so this is exactly the first paint a real browser shows.
    expect(text(renderToStaticMarkup(<LeagueTable />))).toContain("Loading measurements");
  });

  it("does not throw when the measurements file is missing", () => {
    expect(() => renderToStaticMarkup(<LeagueTable />)).not.toThrow();
  });
});
