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
    # ---- United States ----
    SuggestedJurisdiction("Alabama", "United States", "USD", "25-35%"),
    SuggestedJurisdiction("Arizona", "United States", "USD", "15-22.5%"),
    SuggestedJurisdiction("Arkansas", "United States", "USD", "25-30%"),
    SuggestedJurisdiction("California", "United States", "USD", "20-25%"),
    SuggestedJurisdiction("Colorado", "United States", "USD", "20%"),
    SuggestedJurisdiction("Connecticut", "United States", "USD", "10-30%"),
    SuggestedJurisdiction("District of Columbia", "United States", "USD", "21-35%"),
    SuggestedJurisdiction("Georgia", "United States", "USD", "20% + 10% uplift"),
    SuggestedJurisdiction("Hawaii", "United States", "USD", "22-27%"),
    SuggestedJurisdiction("Illinois", "United States", "USD", "30-45%"),
    SuggestedJurisdiction("Kentucky", "United States", "USD", "30-35%"),
    SuggestedJurisdiction("Louisiana", "United States", "USD", "25-40%"),
    SuggestedJurisdiction("Maine", "United States", "USD", "5-12%"),
    SuggestedJurisdiction("Maryland", "United States", "USD", "25-28%"),
    SuggestedJurisdiction("Massachusetts", "United States", "USD", "25%"),
    SuggestedJurisdiction("Minnesota", "United States", "USD", "20-25%"),
    SuggestedJurisdiction("Mississippi", "United States", "USD", "25-35%"),
    SuggestedJurisdiction("Missouri", "United States", "USD", "20-42%"),
    SuggestedJurisdiction("Montana", "United States", "USD", "20-35%"),
    SuggestedJurisdiction("Nevada", "United States", "USD", "15-25%"),
    SuggestedJurisdiction("New Jersey", "United States", "USD", "30-37%"),
    SuggestedJurisdiction("New Mexico", "United States", "USD", "25-40%"),
    SuggestedJurisdiction("New York", "United States", "USD", "30%"),
    SuggestedJurisdiction("North Carolina", "United States", "USD", "25%"),
    SuggestedJurisdiction("Ohio", "United States", "USD", "30%"),
    SuggestedJurisdiction("Oklahoma", "United States", "USD", "20-30%"),
    SuggestedJurisdiction("Oregon", "United States", "USD", "20-25%"),
    SuggestedJurisdiction("Pennsylvania", "United States", "USD", "25-30%"),
    SuggestedJurisdiction("Rhode Island", "United States", "USD", "30%"),
    SuggestedJurisdiction("South Carolina", "United States", "USD", "20-30%"),
    SuggestedJurisdiction("Tennessee", "United States", "USD", "25%"),
    SuggestedJurisdiction("Texas", "United States", "USD", "grant programme"),
    SuggestedJurisdiction("Utah", "United States", "USD", "20-25%"),
    SuggestedJurisdiction("Virginia", "United States", "USD", "15-20%"),
    SuggestedJurisdiction("Washington", "United States", "USD", "30-35%"),
    SuggestedJurisdiction("West Virginia", "United States", "USD", "27-31%"),
    # ---- Canada ----
    SuggestedJurisdiction("British Columbia", "Canada", "CAD", "28-35%"),
    SuggestedJurisdiction("Ontario", "Canada", "CAD", "21.5-35%"),
    SuggestedJurisdiction("Quebec", "Canada", "CAD", "25-40%"),
    SuggestedJurisdiction("Alberta", "Canada", "CAD", "22-30%"),
    SuggestedJurisdiction("Manitoba", "Canada", "CAD", "30-65%"),
    SuggestedJurisdiction("Saskatchewan", "Canada", "CAD", "grant programme"),
    SuggestedJurisdiction("Nova Scotia", "Canada", "CAD", "25-32%"),
    SuggestedJurisdiction("Newfoundland and Labrador", "Canada", "CAD", "40%"),
    SuggestedJurisdiction("New Brunswick", "Canada", "CAD", "25-30%"),
    SuggestedJurisdiction("Prince Edward Island", "Canada", "CAD", "grant programme"),
    SuggestedJurisdiction("Yukon", "Canada", "CAD", "25-35%"),
    # ---- Latin America ----
    SuggestedJurisdiction("Colombia", "Latin America", "COP", "35-40%"),
    SuggestedJurisdiction("Dominican Republic", "Latin America", "DOP", "25%"),
    SuggestedJurisdiction("Brazil", "Latin America", "BRL", "programme published"),
    SuggestedJurisdiction("Chile", "Latin America", "CLP", "30%"),
    SuggestedJurisdiction("Uruguay", "Latin America", "UYU", "20-25%"),
    SuggestedJurisdiction("Panama", "Latin America", "PAB", "15-25%"),
    SuggestedJurisdiction("Mexico", "Latin America", "MXN", "programme published"),
    SuggestedJurisdiction("Argentina", "Latin America", "ARS", "programme published"),
    SuggestedJurisdiction("Peru", "Latin America", "PEN", "programme published"),
    SuggestedJurisdiction("Jamaica", "Latin America", "JMD", "programme published"),
    SuggestedJurisdiction("Trinidad and Tobago", "Latin America", "TTD", "12.5-35%"),
    # ---- Europe ----
    SuggestedJurisdiction("Ireland", "Europe", "EUR", "32-40%"),
    SuggestedJurisdiction("United Kingdom", "Europe", "GBP", "25.5-39%"),
    SuggestedJurisdiction("France", "Europe", "EUR", "30-40%"),
    SuggestedJurisdiction("Germany", "Europe", "EUR", "20-30%"),
    SuggestedJurisdiction("Italy", "Europe", "EUR", "40%"),
    SuggestedJurisdiction("Spain", "Europe", "EUR", "25-54%"),
    SuggestedJurisdiction("Portugal", "Europe", "EUR", "25-30%"),
    SuggestedJurisdiction("Belgium", "Europe", "EUR", "tax shelter"),
    SuggestedJurisdiction("Netherlands", "Europe", "EUR", "35%"),
    SuggestedJurisdiction("Luxembourg", "Europe", "EUR", "grant programme"),
    SuggestedJurisdiction("Austria", "Europe", "EUR", "30-35%"),
    SuggestedJurisdiction("Switzerland", "Europe", "CHF", "20%"),
    SuggestedJurisdiction("Denmark", "Europe", "DKK", "grant programme"),
    SuggestedJurisdiction("Sweden", "Europe", "SEK", "25%"),
    SuggestedJurisdiction("Norway", "Europe", "NOK", "25%"),
    SuggestedJurisdiction("Finland", "Europe", "EUR", "25%"),
    SuggestedJurisdiction("Iceland", "Europe", "ISK", "25-35%"),
    SuggestedJurisdiction("Estonia", "Europe", "EUR", "20-30%"),
    SuggestedJurisdiction("Latvia", "Europe", "EUR", "20-25%"),
    SuggestedJurisdiction("Lithuania", "Europe", "EUR", "30%"),
    SuggestedJurisdiction("Poland", "Europe", "PLN", "30%"),
    SuggestedJurisdiction("Czech Republic", "Europe", "CZK", "20-25%"),
    SuggestedJurisdiction("Slovakia", "Europe", "EUR", "33%"),
    SuggestedJurisdiction("Hungary", "Europe", "HUF", "30%"),
    SuggestedJurisdiction("Romania", "Europe", "RON", "programme published"),
    SuggestedJurisdiction("Bulgaria", "Europe", "BGN", "25%"),
    SuggestedJurisdiction("Croatia", "Europe", "EUR", "25-30%"),
    SuggestedJurisdiction("Serbia", "Europe", "RSD", "20-25%"),
    SuggestedJurisdiction("Greece", "Europe", "EUR", "40%"),
    SuggestedJurisdiction("Cyprus", "Europe", "EUR", "35-45%"),
    SuggestedJurisdiction("Malta", "Europe", "EUR", "40%"),
    SuggestedJurisdiction("North Macedonia", "Europe", "MKD", "20%"),
    SuggestedJurisdiction("Montenegro", "Europe", "EUR", "25%"),
    SuggestedJurisdiction("Albania", "Europe", "ALL", "programme published"),
    SuggestedJurisdiction("Turkey", "Europe", "TRY", "programme published"),
    SuggestedJurisdiction("Georgia (country)", "Europe", "GEL", "20-25%"),
    # ---- Asia-Pacific ----
    SuggestedJurisdiction("Australia", "Asia-Pacific", "AUD", "30-40%"),
    SuggestedJurisdiction("New Zealand", "Asia-Pacific", "NZD", "20-25%"),
    SuggestedJurisdiction("Fiji", "Asia-Pacific", "FJD", "20-75%"),
    SuggestedJurisdiction("Thailand", "Asia-Pacific", "THB", "15-30%"),
    SuggestedJurisdiction("Malaysia", "Asia-Pacific", "MYR", "30%"),
    SuggestedJurisdiction("Singapore", "Asia-Pacific", "SGD", "grant programme"),
    SuggestedJurisdiction("Philippines", "Asia-Pacific", "PHP", "programme published"),
    SuggestedJurisdiction("South Korea", "Asia-Pacific", "KRW", "20-30%"),
    SuggestedJurisdiction("Japan", "Asia-Pacific", "JPY", "grant programme"),
    SuggestedJurisdiction("Taiwan", "Asia-Pacific", "TWD", "programme published"),
    SuggestedJurisdiction("India", "Asia-Pacific", "INR", "programme published"),
    SuggestedJurisdiction("Indonesia", "Asia-Pacific", "IDR", "programme published"),
    SuggestedJurisdiction("Mongolia", "Asia-Pacific", "USD", "30%"),
    SuggestedJurisdiction("Sri Lanka", "Asia-Pacific", "LKR", "programme published"),
    # ---- Africa & Middle East ----
    SuggestedJurisdiction("South Africa", "Africa & Middle East", "ZAR", "20-25%"),
    SuggestedJurisdiction("Morocco", "Africa & Middle East", "MAD", "20-30%"),
    SuggestedJurisdiction("Jordan", "Africa & Middle East", "JOD", "10-25%"),
    SuggestedJurisdiction("Abu Dhabi", "Africa & Middle East", "AED", "30-50%"),
    SuggestedJurisdiction("Saudi Arabia", "Africa & Middle East", "SAR", "up to 40%"),
    SuggestedJurisdiction("Israel", "Africa & Middle East", "ILS", "programme published"),
    SuggestedJurisdiction("Qatar", "Africa & Middle East", "QAR", "programme published"),
    SuggestedJurisdiction("Egypt", "Africa & Middle East", "EGP", "programme published"),
    SuggestedJurisdiction("Kenya", "Africa & Middle East", "KES", "programme published"),
    SuggestedJurisdiction("Nigeria", "Africa & Middle East", "NGN", "programme published"),
    SuggestedJurisdiction("Rwanda", "Africa & Middle East", "RWF", "programme published"),
    SuggestedJurisdiction("Ghana", "Africa & Middle East", "GHS", "programme published"),
    SuggestedJurisdiction("Tunisia", "Africa & Middle East", "TND", "programme published"),
    SuggestedJurisdiction("Mauritius", "Africa & Middle East", "MUR", "30-40%"),
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
