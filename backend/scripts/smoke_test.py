"""End-to-end smoke test against a running deployment.

    python scripts/smoke_test.py                      # the deployed Cloud Run backend
    python scripts/smoke_test.py http://localhost:8000  # a local uvicorn

Unlike the pytest suite (which mocks every network call and needs no
credentials), this drives the *real* stack — Parallel search, Gemini
extraction, Google Maps, Cloud Run — and asserts the invariants that must
hold no matter what those services return. It's the check that catches "all
the unit tests pass but the deployed thing is broken", so it's wired to CI
as a manual/scheduled job rather than running on every push (it spends real
API quota, and a Layer 1 search takes ~30s per jurisdiction).

Each check reports independently: a Maps outage shouldn't hide the fact that
extraction is fine, or vice versa.
"""

from __future__ import annotations

import sys
import traceback
from datetime import date, datetime, timezone

import requests

DEFAULT_BASE_URL = "https://incentive-verifier-backend-559874048514.us-central1.run.app"
TIMEOUT = 120  # a live Layer 1 extraction (Parallel + Gemini) is genuinely slow

OK, FAIL = "\033[32mOK\033[0m", "\033[31mFAIL\033[0m"

VALID_CONFIDENCE = {"primary_source", "official_secondary", "conflicting", "stale", "unverified"}
VALID_POOL_STATUS = {"open", "capping_out", "closed", "unknown"}

BUDGET = {
    "total": 2_000_000,
    "atl_cast": 250_000,
    "atl_noncast": 200_000,
    "btl_labor": 750_000,
    "btl_nonlabor": 550_000,
    "post_vfx": 250_000,
    "shoot_days": 22,
    "crew_headcount": 45,
    "resident_labor_pct": 0.55,
    "home_base": "Los Angeles, CA",
    "constraints": [],
}


class SmokeFailure(AssertionError):
    """Raised by a check when an invariant doesn't hold."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def check(label: str, fn) -> bool:
    try:
        detail = fn()
    except Exception as exc:  # noqa: BLE001 — reporting failures is this script's job
        print(f"[{FAIL}] {label}: {type(exc).__name__}: {exc}")
        if "-v" in sys.argv:
            traceback.print_exc()
        return False
    print(f"[{OK}] {label}: {detail}")
    return True


# ---------- individual checks ----------

def check_health(base: str) -> str:
    resp = requests.get(f"{base}/health", timeout=TIMEOUT)
    resp.raise_for_status()
    require(resp.json() == {"status": "ok"}, f"unexpected body {resp.json()!r}")
    return "reachable"


def check_distance(base: str) -> str:
    resp = requests.get(
        f"{base}/distance",
        params={"origin": "Los Angeles, CA", "destination_lat": 33.749, "destination_lng": -84.388},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    km, hours = body["distance_km"], body["travel_time_hours"]
    # LA -> Atlanta by road is ~3,500 km / ~31 h. Wide bounds: this asserts
    # "Maps returned a real route", not a specific routing result.
    require(2_500 < km < 5_000, f"implausible distance {km} km")
    require(15 < hours < 60, f"implausible duration {hours} h")
    return f"LA -> Atlanta {km:,.0f} km / {hours:.1f} h"


def _search(base: str, jurisdiction: str) -> dict:
    resp = requests.post(f"{base}/jurisdictions/search", params={"jurisdiction": jurisdiction}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def check_extraction(base: str) -> str:
    """Layer 1 live, plus the two invariants that a past live run violated."""
    rule = _search(base, "Georgia")

    require(rule["jurisdiction"] == "Georgia", f"expected canonical 'Georgia', got {rule['jurisdiction']!r}")
    require(0 < rule["base_rate"] <= 1, f"base_rate {rule['base_rate']} outside (0, 1]")
    require(bool(rule["sources"]), "no sources returned")
    require(rule["confidence"] in VALID_CONFIDENCE, f"bad confidence {rule['confidence']!r}")
    require(rule["pool_status"] in VALID_POOL_STATUS, f"bad pool_status {rule['pool_status']!r}")

    # `retrieved` is stamped by the pipeline, never taken from the model — a
    # live run once returned a date ~800 days stale for a page fetched that
    # same second, which silently downgrades confidence to "stale".
    today = date.today().isoformat()
    for source in rule["sources"]:
        require(
            source["retrieved"] == today,
            f"source retrieved={source['retrieved']!r}, expected today ({today}) — "
            "the model's date is being trusted again",
        )
        require(source["url"].startswith("http"), f"bad source url {source['url']!r}")

    return f"Georgia @ {rule['base_rate']:.0%}, {len(rule['sources'])} sources, confidence={rule['confidence']}"


def check_constraint_gaps(base: str) -> str:
    """Coastline gaps must key off canonical names, not postal abbreviations."""
    landlocked = _search(base, "New Mexico")
    coastal = _search(base, "Georgia")

    require(
        "coastline" in landlocked["constraint_gaps"],
        f"{landlocked['jurisdiction']} is landlocked but has no coastline gap",
    )
    require(
        "coastline" not in coastal["constraint_gaps"],
        f"{coastal['jurisdiction']} has an Atlantic coast but was flagged as failing 'coastline' — "
        "abbreviated jurisdiction names are breaking the COASTAL_STATES lookup again",
    )
    return "New Mexico flagged landlocked, Georgia not flagged"


def check_compute_arithmetic(base: str) -> str:
    """The product's core claim: the walk from face value to cash reconciles.

    Once a credit is treated as a claim on future money, `net == gross -
    relocation` is no longer the identity — a credit paid in 18 months is
    worth less than its face value, and this deliberately asserts the fuller
    chain rather than the old shortcut:

        net = gross + discount - audit + timing_loss - relocation

    A deployment predating any of those stages omits the fields, and the
    fallbacks below collapse the chain back to exactly the old arithmetic —
    so this check is meaningful against either version rather than reporting
    a false failure the first time it meets an older one.
    """
    rule = _search(base, "Georgia")
    resp = requests.post(
        f"{base}/compute",
        json={"budget": BUDGET, "rule": rule, "distance_km": 3498.0, "travel_time_hours": 31.6},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()

    gross = body["gross_credit"]
    realizable = body.get("realizable_credit", gross)
    audit = body.get("audit_cost", 0.0)
    present_value = body.get("present_value", realizable - audit)
    relocation = body["relocation_cost"]

    discount = realizable - gross
    timing_loss = present_value - (realizable - audit)
    expected_net = gross + discount - audit + timing_loss - relocation
    require(
        abs(body["net_benefit"] - expected_net) < 0.01,
        f"net {body['net_benefit']} != gross {gross} + discount {discount} - audit {audit} "
        f"+ timing {timing_loss} - relocation {relocation}",
    )
    require(
        present_value <= realizable - audit + 0.01,
        f"present value {present_value} exceeds the {realizable - audit} it discounts — money cannot "
        "be worth more for arriving later",
    )
    components = body["relocation_components"]
    require(
        abs(sum(components.values()) - relocation) < 0.01,
        f"relocation components {components} don't sum to {relocation}",
    )
    require(body["distance_km"] == 3498.0, "distance_km sent in the body was dropped by the endpoint")
    months = body.get("months_to_payment", 0)
    return (
        f"net {body['net_benefit']:,.0f} = gross {gross:,.0f} - {gross - realizable:,.0f} discount "
        f"- {audit:,.0f} audit - {-timing_loss:,.0f} for {months}mo wait - {relocation:,.0f} reloc"
    )


def check_batch_monotonicity(base: str) -> str:
    """More qualifying spend can never produce a smaller credit."""
    rule = _search(base, "Georgia")
    budgets = [dict(BUDGET, atl_cast=cast) for cast in (0, 500_000, 5_000_000)]
    resp = requests.post(
        f"{base}/compute/batch", json={"budgets": budgets, "rule": rule}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    credits = [r["gross_credit"] for r in resp.json()]
    require(credits == sorted(credits), f"gross credit not monotonic in ATL spend: {credits}")
    return f"credits rise with spend: {[f'{c:,.0f}' for c in credits]}"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    base = (args[0] if args else DEFAULT_BASE_URL).rstrip("/")
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Smoke testing {base}\nstarted {started}\n")

    results = [
        check("health          ", lambda: check_health(base)),
        check("maps distance   ", lambda: check_distance(base)),
        check("layer 1 live    ", lambda: check_extraction(base)),
        check("constraint gaps ", lambda: check_constraint_gaps(base)),
        check("compute math    ", lambda: check_compute_arithmetic(base)),
        check("batch monotonic ", lambda: check_batch_monotonicity(base)),
    ]

    print()
    if all(results):
        print(f"All {len(results)} checks passed against {base}.")
        return 0
    print(f"{results.count(False)} of {len(results)} checks failed. Re-run with -v for tracebacks.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
