"""API-level tests using FastAPI's TestClient — no network, but exercises
the real request/response cycle (JSON (de)serialization of the dataclasses,
routing, verify_rule wiring), not just the underlying Python functions.
"""

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.maps_client import DistanceResult
from app.seed_jurisdictions import GEORGIA

from .fixtures import make_budget, make_rule

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_compute_endpoint_matches_direct_call():
    budget = make_budget()
    resp = client.post("/compute", json={"budget": jsonable_encoder(budget), "rule": jsonable_encoder(GEORGIA)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["jurisdiction"] == "Georgia"
    assert body["computable"] is True
    assert body["gross_credit"] > 0


def test_compute_endpoint_reads_distance_from_the_json_body():
    # Regression test: distance_km/travel_time_hours must be declared with
    # Body(...) in main.py, not a bare default — a bare default is classified
    # as a query param by FastAPI, so it silently reads as None when sent
    # this way (which is how lib/api.ts's computeBenefit has always sent it).
    budget = make_budget()
    no_distance = client.post(
        "/compute", json={"budget": jsonable_encoder(budget), "rule": jsonable_encoder(GEORGIA)}
    ).json()
    with_distance = client.post(
        "/compute",
        json={
            "budget": jsonable_encoder(budget),
            "rule": jsonable_encoder(GEORGIA),
            "distance_km": 3498.0,
            "travel_time_hours": 31.6,
        },
    ).json()
    assert with_distance["distance_km"] == 3498.0
    assert with_distance["relocation_cost"] > no_distance["relocation_cost"]


def test_compute_batch_scans_multiple_budgets_in_one_call():
    budgets = [make_budget(atl_cast=i * 100_000, atl_noncast=0) for i in range(3)]
    resp = client.post(
        "/compute/batch",
        json={"budgets": [jsonable_encoder(b) for b in budgets], "rule": jsonable_encoder(GEORGIA)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    credits = [r["gross_credit"] for r in body]
    assert credits == sorted(credits)  # monotonically increasing with atl_cast


def test_search_endpoint_calls_extraction_and_reverifies_confidence(monkeypatch):
    # Rule comes back from Layer 1 with a stale confidence label; the endpoint
    # must recompute it via verify_rule rather than trust what extraction set.
    unverified = make_rule(jurisdiction="Extractland", sources=[], confidence="primary_source")
    monkeypatch.setattr(main, "extract_jurisdiction_rule", lambda jurisdiction: unverified)

    resp = client.post("/jurisdictions/search", params={"jurisdiction": "Extractland"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["jurisdiction"] == "Extractland"
    assert body["confidence"] == "unverified"  # no sources -> verify_rule downgrades it


def test_search_endpoint_returns_502_on_extraction_failure(monkeypatch):
    def boom(jurisdiction):
        raise RuntimeError("Parallel search returned zero results")

    monkeypatch.setattr(main, "extract_jurisdiction_rule", boom)

    resp = client.post("/jurisdictions/search", params={"jurisdiction": "Nowhereland"})

    assert resp.status_code == 502
    assert "Nowhereland" in resp.json()["detail"]


def test_search_endpoint_caches_so_a_repeat_lookup_skips_extraction(monkeypatch):
    calls = []

    def record_and_extract(jurisdiction):
        calls.append(jurisdiction)
        return make_rule(jurisdiction="Cacheland", sources=[])

    monkeypatch.setattr(main, "extract_jurisdiction_rule", record_and_extract)

    first = client.post("/jurisdictions/search", params={"jurisdiction": "Cacheland"})
    second = client.post("/jurisdictions/search", params={"jurisdiction": "Cacheland"})

    assert first.status_code == second.status_code == 200
    assert calls == ["Cacheland"]  # extraction ran once, second call was a cache hit
    assert first.json() == second.json()


def test_search_endpoint_refresh_bypasses_the_cache(monkeypatch):
    calls = []

    def record_and_extract(jurisdiction):
        calls.append(jurisdiction)
        return make_rule(jurisdiction="Refreshland", sources=[])

    monkeypatch.setattr(main, "extract_jurisdiction_rule", record_and_extract)

    client.post("/jurisdictions/search", params={"jurisdiction": "Refreshland"})
    client.post("/jurisdictions/search", params={"jurisdiction": "Refreshland", "refresh": True})

    assert calls == ["Refreshland", "Refreshland"]  # refresh=true forced a second live call


def test_distance_endpoint_returns_maps_result(monkeypatch):
    monkeypatch.setattr(
        main, "get_distance", lambda origin, lat, lng: DistanceResult(distance_km=3498.0, travel_time_hours=31.6)
    )

    resp = client.get(
        "/distance", params={"origin": "Los Angeles, CA", "destination_lat": 33.749, "destination_lng": -84.388}
    )

    assert resp.status_code == 200
    assert resp.json() == {"distance_km": 3498.0, "travel_time_hours": 31.6}


def test_distance_endpoint_returns_502_on_maps_failure(monkeypatch):
    def boom(origin, lat, lng):
        raise RuntimeError("Distance Matrix returned ZERO_RESULTS")

    monkeypatch.setattr(main, "get_distance", boom)

    resp = client.get("/distance", params={"origin": "Nowhere", "destination_lat": 0, "destination_lng": 0})

    assert resp.status_code == 502


# ---------- budget PDF upload ----------

def test_budget_parse_returns_budget_and_provenance(monkeypatch):
    from app.extraction.budget_parser import ParsedBudget

    parsed = ParsedBudget(
        budget=make_budget(total=2_000_000),
        field_notes={"total": "page 1, topsheet total"},
        warnings=["crew headcount was not found in the document — enter it manually."],
    )
    monkeypatch.setattr(main, "parse_budget_pdf", lambda contents, **kw: parsed)

    resp = client.post("/budget/parse", files={"file": ("topsheet.pdf", b"%PDF-1.4 fake", "application/pdf")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["budget"]["total"] == 2_000_000
    assert body["field_notes"]["total"] == "page 1, topsheet total"
    assert body["warnings"]


def test_budget_parse_rejects_a_bad_file_as_400_not_500(monkeypatch):
    # A scanned, text-free topsheet is a user-actionable problem ("type the
    # numbers in"), not a server fault.
    def reject(contents, **kw):
        raise ValueError("That file isn't a PDF (no %PDF header)")

    monkeypatch.setattr(main, "parse_budget_pdf", reject)

    resp = client.post("/budget/parse", files={"file": ("scan.png", b"\x89PNG", "image/png")})

    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_budget_parse_surfaces_a_model_failure_as_502(monkeypatch):
    def boom(contents, **kw):
        raise RuntimeError("Vertex returned no function call")

    monkeypatch.setattr(main, "parse_budget_pdf", boom)

    resp = client.post("/budget/parse", files={"file": ("topsheet.pdf", b"%PDF-1.4 fake", "application/pdf")})

    assert resp.status_code == 502
