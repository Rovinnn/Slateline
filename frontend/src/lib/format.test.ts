import { describe, expect, it } from "vitest";
import { hostOf, money, moneyShort } from "./format";

describe("money", () => {
  it("formats whole dollars with separators", () => {
    expect(money(1234567)).toBe("$1,234,567");
  });

  it("uses a real minus sign for negatives, not a hyphen", () => {
    // Negative net benefit is a headline number on the results card, so it
    // gets the typographic minus the rest of the memo uses.
    expect(money(-89100)).toBe("−$89,100");
  });

  it("rounds rather than truncating", () => {
    expect(money(0.6)).toBe("$1");
  });

  it("handles zero without a sign", () => {
    expect(money(0)).toBe("$0");
  });
});

describe("moneyShort", () => {
  it("abbreviates millions with two decimals below 10M", () => {
    expect(moneyShort(2_000_000)).toBe("$2.00M");
  });

  it("drops to one decimal at 10M and above, where the cents are noise", () => {
    expect(moneyShort(13_159_800)).toBe("$13.2M");
  });

  it("abbreviates thousands", () => {
    expect(moneyShort(385_100)).toBe("$385k");
  });

  it("falls back to full dollars under a thousand", () => {
    expect(moneyShort(250)).toBe("$250");
  });

  it("keeps the sign when abbreviating negatives", () => {
    expect(moneyShort(-89_100)).toBe("−$89k");
  });

  it("handles the exact 1M and 1k boundaries", () => {
    expect(moneyShort(1_000_000)).toBe("$1.00M");
    expect(moneyShort(1_000)).toBe("$1k");
    expect(moneyShort(999)).toBe("$999");
  });
});

describe("hostOf", () => {
  it("strips protocol, www and path down to the bare host", () => {
    expect(hostOf("https://www.georgia.org/industries/film")).toBe("georgia.org");
  });

  it("keeps meaningful subdomains", () => {
    expect(hostOf("https://dor.georgia.gov/film-tax-credits")).toBe("dor.georgia.gov");
  });

  it("returns the input unchanged when it isn't a parseable URL", () => {
    // Source URLs come from a model; a malformed one should render as-is in
    // the footnote rather than throwing and blanking the whole card.
    expect(hostOf("not a url")).toBe("not a url");
  });
});
