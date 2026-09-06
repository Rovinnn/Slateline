"""Measure the gap between what each jurisdiction advertises and what it pays.

    python scripts/build_league_table.py [--limit N] [--out PATH]

Runs the full pipeline over the suggested jurisdictions against one reference
budget and records, for each, the advertised headline against the share of
that budget a producer actually keeps.

Why this exists as a build step rather than a live screen: it is ~35 seconds
of live search and extraction per jurisdiction, so doing it on page load would
be twenty minutes of spinner. Precomputing makes it instant, and — more
importantly — makes it a *dated artefact* rather than a number that quietly
changes under the reader. Every row carries the date it was measured.

The output is a claim about the world, so it is deliberately falsifiable: the
reference budget is stated in the file, every row records its sources, and
anything that could not be computed is listed with the reason rather than
dropped. A league table that silently omitted its failures would be
advertising, which is the thing this project is arguing against.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.calculator import compute_benefit  # noqa: E402
from app.extraction.agent import extract_jurisdiction_rule  # noqa: E402
from app.jurisdictions import SUGGESTED  # noqa: E402
from app.models import BudgetVector  # noqa: E402
from app.verification import verify_rule  # noqa: E402

#: One budget for every jurisdiction, because a league table only means
#: anything if the denominator is held constant. Stated in the output so a
#: reader can see what these percentages are a percentage *of*.
REFERENCE_BUDGET = BudgetVector(
    total=2_000_000,
    atl_cast=250_000,
    atl_noncast=200_000,
    btl_labor=750_000,
    btl_nonlabor=550_000,
    post_vfx=250_000,
    shoot_days=22,
    crew_headcount=45,
    resident_labor_pct=0.55,
    home_base="Los Angeles, CA",
)
REFERENCE_LABEL = "$2M independent drama, 22 shoot days, 45 crew, 55% local hire, based in Los Angeles"

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "league-table.json"


def measure(name: str) -> dict:
    """One jurisdiction, extracted live and priced against the reference budget."""
    rule = verify_rule(extract_jurisdiction_rule(name))
    benefit = compute_benefit(REFERENCE_BUDGET, rule, distance_km=None)
    advertised = rule.base_rate + sum(u.bonus_rate for u in rule.uplifts)

    row = {
        "jurisdiction": rule.jurisdiction,
        "program": rule.program_name,
        "currency": rule.currency,
        "advertised": advertised,
        "base_rate": rule.base_rate,
        "credit_type": rule.credit_type,
        "confidence": rule.confidence,
        "computable": benefit.computable,
        "sources": [s.url for s in rule.sources[:3]],
    }
    if benefit.computable:
        row.update(
            {
                "effective": benefit.net_benefit / REFERENCE_BUDGET.total,
                "net_benefit": benefit.net_benefit,
                "gap_points": (advertised - benefit.net_benefit / REFERENCE_BUDGET.total) * 100,
                "months_to_payment": benefit.months_to_payment,
            }
        )
    else:
        # Kept, not dropped. A table that hid what it couldn't price would be
        # the advertising this project argues against.
        row["reason"] = benefit.non_computable_reason
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=len(SUGGESTED))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    names = [j.name for j in SUGGESTED][: args.limit]
    print(f"measuring {len(names)} jurisdictions against the reference budget\n")

    rows, failures = [], []
    for i, name in enumerate(names, 1):
        try:
            row = measure(name)
            rows.append(row)
            if row["computable"]:
                print(
                    f"  [{i:>2}/{len(names)}] {row['jurisdiction']:<22} "
                    f"{row['advertised']:>6.1%} advertised -> {row['effective']:>6.1%} actual"
                )
            else:
                print(f"  [{i:>2}/{len(names)}] {row['jurisdiction']:<22} not priceable: {row['reason'][:44]}")
        except Exception as exc:  # noqa: BLE001 - one bad jurisdiction must not lose the run
            failures.append({"jurisdiction": name, "error": f"{type(exc).__name__}: {exc}"[:200]})
            print(f"  [{i:>2}/{len(names)}] {name:<22} EXTRACTION FAILED")

    priced = [r for r in rows if r["computable"]]
    priced.sort(key=lambda r: -r["gap_points"])

    payload = {
        "measured_at": datetime.now(timezone.utc).date().isoformat(),
        "reference_budget_label": REFERENCE_LABEL,
        "reference_budget": asdict(REFERENCE_BUDGET),
        "rows": priced + [r for r in rows if not r["computable"]],
        "extraction_failures": failures,
        "note": (
            "Each row is one live extraction priced against the same budget. 'Advertised' is the "
            "base rate plus every uplift the programme markets; 'actual' is net benefit as a share "
            "of total budget, after qualification rules, payout mechanism, the wait to be paid and "
            "relocation from Los Angeles. Percentages move with the budget — these are not "
            "universal constants."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n  {len(priced)} priced, {len(rows) - len(priced)} not priceable, {len(failures)} failed")
    if priced:
        widest = priced[0]
        print(f"  widest gap: {widest['jurisdiction']} "
              f"{widest['advertised']:.1%} -> {widest['effective']:.1%}")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
