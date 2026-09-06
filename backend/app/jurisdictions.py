"""Which places this tool can be pointed at.

There is no allowlist in the pipeline — extraction takes a name and searches
for it, so anywhere with a published film incentive can be looked up, and
plenty that can't will simply come back unverifiable. That is honest but it
makes the product look narrower than it is: a search box with no suggestions
reads as "type one of the four things we hard-coded".

So this is a *curated starting set*, not a limit. Everything here has a real
programme worth extracting; typing something not on the list still works.

Grouped because a producer thinks regionally, and marked with the currency
each programme publishes in — non-USD ones convert against a stated rate (see
CurrencyAssumptions) rather than being refused, which is new.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuggestedJurisdiction:
    name: str
    region: str
    #: What the programme publishes its figures in. Non-USD converts.
    currency: str
    #: Roughly what the programme advertises, for a suggestion list only —
    #: never used in any calculation, which always uses extracted values.
    advertised_hint: str


SUGGESTED: tuple[SuggestedJurisdiction, ...] = (
    # United States — the deepest incentive market, and where the seed data
    # and hand-verified statutes live.
    SuggestedJurisdiction("Georgia", "United States", "USD", "20% + 10% uplift"),
    SuggestedJurisdiction("New Mexico", "United States", "USD", "25-40%"),
    SuggestedJurisdiction("Louisiana", "United States", "USD", "25-40%"),
    SuggestedJurisdiction("California", "United States", "USD", "20-25%"),
    SuggestedJurisdiction("New York", "United States", "USD", "30%"),
    SuggestedJurisdiction("Illinois", "United States", "USD", "30-45%"),
    SuggestedJurisdiction("Kentucky", "United States", "USD", "30-35%"),
    SuggestedJurisdiction("New Jersey", "United States", "USD", "30-37%"),
    SuggestedJurisdiction("Massachusetts", "United States", "USD", "25%"),
    SuggestedJurisdiction("Pennsylvania", "United States", "USD", "25-30%"),
    SuggestedJurisdiction("Ohio", "United States", "USD", "30%"),
    SuggestedJurisdiction("Texas", "United States", "USD", "grant programme"),
    SuggestedJurisdiction("Oklahoma", "United States", "USD", "20-30%"),
    SuggestedJurisdiction("Utah", "United States", "USD", "20-25%"),
    SuggestedJurisdiction("Hawaii", "United States", "USD", "22-27%"),
    # Canada — federal plus provincial, and a long-standing destination for
    # US productions.
    SuggestedJurisdiction("British Columbia", "Canada", "CAD", "28-35%"),
    SuggestedJurisdiction("Ontario", "Canada", "CAD", "21.5-35%"),
    SuggestedJurisdiction("Quebec", "Canada", "CAD", "25-40%"),
    # Europe.
    SuggestedJurisdiction("Ireland", "Europe", "EUR", "32-40%"),
    SuggestedJurisdiction("United Kingdom", "Europe", "GBP", "25.5-39%"),
    SuggestedJurisdiction("Hungary", "Europe", "HUF", "30%"),
    SuggestedJurisdiction("Czech Republic", "Europe", "CZK", "20-25%"),
    SuggestedJurisdiction("Spain", "Europe", "EUR", "25-54%"),
    SuggestedJurisdiction("Italy", "Europe", "EUR", "40%"),
    SuggestedJurisdiction("Iceland", "Europe", "EUR", "25-35%"),
    SuggestedJurisdiction("Malta", "Europe", "EUR", "40%"),
    # Asia-Pacific.
    SuggestedJurisdiction("Australia", "Asia-Pacific", "AUD", "30-40%"),
    SuggestedJurisdiction("New Zealand", "Asia-Pacific", "NZD", "20-25%"),
    SuggestedJurisdiction("Thailand", "Asia-Pacific", "THB", "15-30%"),
    SuggestedJurisdiction("South Korea", "Asia-Pacific", "KRW", "20-30%"),
    SuggestedJurisdiction("Japan", "Asia-Pacific", "JPY", "grant programme"),
    SuggestedJurisdiction("Mongolia", "Asia-Pacific", "USD", "30%"),
    # Rest of world.
    SuggestedJurisdiction("South Africa", "Africa & Middle East", "ZAR", "20-25%"),
    SuggestedJurisdiction("Morocco", "Africa & Middle East", "USD", "20-30%"),
    SuggestedJurisdiction("Jordan", "Africa & Middle East", "USD", "10-25%"),
    SuggestedJurisdiction("Colombia", "Latin America", "COP", "35-40%"),
    SuggestedJurisdiction("Dominican Republic", "Latin America", "DOP", "25%"),
)

#: Region order for display. Not alphabetical: a US-based production reads
#: down from home, and most of this tool's users are US-based.
REGION_ORDER: tuple[str, ...] = (
    "United States",
    "Canada",
    "Latin America",
    "Europe",
    "Asia-Pacific",
    "Africa & Middle East",
)


def grouped() -> list[tuple[str, list[SuggestedJurisdiction]]]:
    """Suggestions by region, in reading order, skipping empty regions."""
    out = []
    for region in REGION_ORDER:
        members = [j for j in SUGGESTED if j.region == region]
        if members:
            out.append((region, members))
    return out
