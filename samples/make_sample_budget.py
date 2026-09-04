"""Generates samples/sample-budget-bluewater.pdf — a realistic feature-film
budget topsheet, for exercising the PDF upload path end to end.

Laid out the way a Movie Magic Budgeting topsheet actually prints: account
numbers in the standard ranges (1000s above-the-line, 2000-3400 production,
4000s post, 5000s indirect), department names a line producer would
recognise, and section subtotals above a grand total.

Two things are deliberate, because they're what makes this a real test
rather than a softball:

1. The categories don't sum to the grand total. $130,000 of indirect costs
   (insurance, legal, G&A) sit outside the five spend buckets BudgetVector
   models, so the form's sum check should report roughly that much
   unallocated. A parser that "helpfully" reconciles them is doing exactly
   the arithmetic budget_parser.py is written not to do.
2. Resident/local hire share is nowhere in the document, because it isn't a
   budget line — it's a staffing decision. The parse should warn rather than
   invent one.

Regenerate with:
    node samples/render_budget_pdf.mjs
(which renders sample_budget.html; this script writes that HTML)
"""

from __future__ import annotations

import pathlib

TITLE = "BLUEWATER"
SUBTITLE = "Feature Film — Production Budget"

HEADER_FIELDS = [
    ("Production No.", "BW-101"),
    ("Budget Version", "v7 (locked)"),
    ("Budget Date", "14 Aug 2026"),
    ("Director", "M. Okonkwo"),
    ("Producer", "R. Salazar"),
    ("Line Producer", "J. Feld"),
    ("Prep", "3 weeks"),
    ("Shoot", "24 days"),
    ("Post", "10 weeks"),
    ("Crew (est.)", "48"),
    ("Union Status", "SAG-AFTRA Modified Low Budget"),
    ("Currency", "USD"),
]

ABOVE_THE_LINE = [
    ("1100", "STORY & RIGHTS", 45_000),
    ("1200", "PRODUCERS UNIT", 180_000),
    ("1300", "DIRECTION", 145_000),
    ("1400", "CAST", 310_000),
    ("1500", "ATL TRAVEL & LIVING", 38_000),
]

PRODUCTION = [
    ("2000", "PRODUCTION STAFF", 268_000),
    ("2100", "EXTRA TALENT", 32_000),
    ("2200", "SET DESIGN", 41_000),
    ("2300", "SET CONSTRUCTION", 96_000),
    ("2400", "SET OPERATIONS", 78_000),
    ("2500", "SET DRESSING", 54_000),
    ("2600", "PROPERTY", 37_000),
    ("2700", "WARDROBE", 62_000),
    ("2800", "MAKEUP & HAIRDRESSING", 44_000),
    ("2900", "ELECTRICAL & GRIP", 149_000),
    ("3000", "CAMERA", 118_000),
    ("3100", "PRODUCTION SOUND", 39_000),
    ("3200", "TRANSPORTATION", 88_000),
    ("3300", "LOCATION EXPENSE", 134_000),
    ("3400", "PRODUCTION OFFICE", 46_000),
]

POST = [
    ("4000", "EDITORIAL", 142_000),
    ("4100", "MUSIC", 58_000),
    ("4200", "POST SOUND", 74_000),
    ("4300", "VISUAL EFFECTS", 96_000),
    ("4400", "TITLES & GRAPHICS", 18_000),
    ("4500", "DELIVERABLES & MASTERING", 32_000),
]

INDIRECT = [
    ("5000", "INSURANCE", 47_000),
    ("5100", "LEGAL & ACCOUNTING", 38_000),
    ("5200", "PUBLICITY & STILLS", 16_000),
    ("5300", "GENERAL & ADMINISTRATIVE", 29_000),
]

# The qualified-spend breakdown a production actually prepares for a film
# office. Splits the production total into wages vs everything else.
BTL_LABOR = 812_000
BTL_NON_LABOR = 474_000


def money(n: int) -> str:
    return f"{n:,}"


def rows(entries: list[tuple[str, str, int]]) -> str:
    return "\n".join(
        f'<tr><td class="acct">{acct}</td><td class="desc">{name}</td>'
        f'<td class="amt">{money(amount)}</td></tr>'
        for acct, name, amount in entries
    )


def subtotal(label: str, amount: int) -> str:
    return (
        f'<tr class="sub"><td class="acct"></td><td class="desc">{label}</td>'
        f'<td class="amt">{money(amount)}</td></tr>'
    )


def build_html() -> str:
    atl_total = sum(a for _, _, a in ABOVE_THE_LINE)
    prod_total = sum(a for _, _, a in PRODUCTION)
    post_total = sum(a for _, _, a in POST)
    indirect_total = sum(a for _, _, a in INDIRECT)
    grand_total = atl_total + prod_total + post_total + indirect_total

    assert BTL_LABOR + BTL_NON_LABOR == prod_total, "labor split must reconcile to the production total"

    header_html = "\n".join(
        f'<div class="field"><span class="k">{k}</span><span class="v">{v}</span></div>'
        for k, v in HEADER_FIELDS
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {{ size: Letter; margin: 14mm; }}
  body {{ font-family: "Courier New", monospace; font-size: 10pt; color: #111; }}
  h1 {{ font-size: 16pt; margin: 0; letter-spacing: 1px; }}
  .sub-title {{ font-size: 10pt; margin: 2px 0 10px; }}
  .rule {{ border-bottom: 2px solid #111; margin: 6px 0 10px; }}
  .thin {{ border-bottom: 1px solid #999; margin: 4px 0 8px; }}
  .header-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px 18px; margin-bottom: 12px; }}
  .field {{ display: flex; justify-content: space-between; border-bottom: 1px dotted #bbb; padding: 1px 0; }}
  .k {{ color: #444; }}
  .v {{ font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 4px; }}
  td {{ padding: 1.5px 0; }}
  .acct {{ width: 56px; }}
  .desc {{ }}
  .amt {{ text-align: right; width: 110px; }}
  tr.sub td {{ border-top: 1px solid #111; font-weight: bold; padding-top: 3px; }}
  .section {{ font-weight: bold; margin: 12px 0 4px; letter-spacing: 0.5px; }}
  .grand {{ border-top: 3px double #111; margin-top: 8px; padding-top: 6px;
            display: flex; justify-content: space-between; font-size: 12pt; font-weight: bold; }}
  .note {{ font-size: 8.5pt; color: #444; margin-top: 10px; line-height: 1.5; }}
  .qual td {{ padding: 2px 0; }}
</style></head><body>

<h1>{TITLE}</h1>
<div class="sub-title">{SUBTITLE}</div>
<div class="rule"></div>

<div class="header-grid">{header_html}</div>

<div class="section">ABOVE-THE-LINE</div>
<div class="thin"></div>
<table>{rows(ABOVE_THE_LINE)}
{subtotal("TOTAL ABOVE-THE-LINE", atl_total)}</table>

<div class="section">BELOW-THE-LINE — PRODUCTION</div>
<div class="thin"></div>
<table>{rows(PRODUCTION)}
{subtotal("TOTAL PRODUCTION", prod_total)}</table>

<div class="section">POST PRODUCTION</div>
<div class="thin"></div>
<table>{rows(POST)}
{subtotal("TOTAL POST PRODUCTION", post_total)}</table>

<div class="section">OTHER / INDIRECT COSTS</div>
<div class="thin"></div>
<table>{rows(INDIRECT)}
{subtotal("TOTAL OTHER / INDIRECT", indirect_total)}</table>

<div class="grand"><span>GRAND TOTAL</span><span>{money(grand_total)}</span></div>

<div class="section" style="margin-top:16px">QUALIFIED SPEND BREAKDOWN — PRODUCTION (for incentive estimation)</div>
<div class="thin"></div>
<table class="qual">
  <tr><td class="desc">Below-the-line labor (wages and fringes, accts 2000-3400)</td>
      <td class="amt">{money(BTL_LABOR)}</td></tr>
  <tr><td class="desc">Below-the-line non-labor (rentals, materials, services)</td>
      <td class="amt">{money(BTL_NON_LABOR)}</td></tr>
  <tr><td class="desc">Above-the-line cast (acct 1400)</td>
      <td class="amt">{money(310_000)}</td></tr>
  <tr><td class="desc">Above-the-line non-cast (accts 1100, 1200, 1300, 1500)</td>
      <td class="amt">{money(atl_total - 310_000)}</td></tr>
  <tr><td class="desc">Post production and visual effects (accts 4000-4500)</td>
      <td class="amt">{money(post_total)}</td></tr>
</table>

<div class="note">
  Prepared by production accounting. Figures are locked as of the budget date above and exclude
  completion bond, financing costs and contingency. Indirect costs (accts 5000-5300) are not
  allocated to a production spend category. Local/resident hire percentages are not determined at
  this stage and will follow department head hiring in prep.
</div>

</body></html>"""


if __name__ == "__main__":
    out = pathlib.Path(__file__).parent / "sample_budget.html"
    out.write_text(build_html(), encoding="utf-8")
    print(f"wrote {out}")
