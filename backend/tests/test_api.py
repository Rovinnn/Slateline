"""API-level tests using FastAPI's TestClient — no network, but exercises
the real request/response cycle (JSON (de)serialization of the dataclasses,
routing, verify_rule wiring), not just the underlying Python functions.
"""

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from app.main import app
from app.seed_jurisdictions import GEORGIA

from .fixtures import make_budget

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


def test_seed_endpoint_returns_four_jurisdictions_with_recomputed_confidence():
    resp = client.get("/jurisdictions/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4
    assert {j["jurisdiction"] for j in body} == {"Georgia", "New Mexico", "Louisiana", "Texas"}


def test_search_endpoint_returns_501_without_credentials():
    resp = client.post("/jurisdictions/search", params={"jurisdiction": "Georgia"})
    assert resp.status_code == 501
