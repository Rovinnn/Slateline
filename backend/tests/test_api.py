"""API-level tests using FastAPI's TestClient — no network, but exercises
the real request/response cycle (JSON (de)serialization of the dataclasses,
routing, verify_rule wiring), not just the underlying Python functions.
"""

import pytest
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


def test_compute_accepts_an_editable_transfer_discount():
    # A transferable credit's cash value turns on the broker discount, so the
    # client has to be able to change it — it was a backend-only default.
    from app.models import JurisdictionRule
    from dataclasses import replace as dc_replace

    transferable = dc_replace(GEORGIA, minimum_spend=None, credit_type="transferable")
    body = {"budget": jsonable_encoder(make_budget()), "rule": jsonable_encoder(transferable)}

    default = client.post("/compute", json=body).json()
    steep = client.post("/compute", json={**body, "transfer_discount": 0.5}).json()

    assert isinstance(transferable, JurisdictionRule)
    assert steep["realizable_credit"] < default["realizable_credit"]
    assert steep["realizable_credit"] == pytest.approx(default["gross_credit"] * 0.5)


def test_compute_accepts_an_explicit_cast_count():
    # The wage cap otherwise divides ATL cast by a guess (8% of crew).
    from dataclasses import replace as dc_replace

    capped = dc_replace(GEORGIA, per_person_wage_cap=50_000, minimum_spend=None)
    budget = make_budget(atl_cast=1_000_000, crew_headcount=45)
    body = {"budget": jsonable_encoder(budget), "rule": jsonable_encoder(capped)}

    guessed = client.post("/compute", json=body).json()
    stated = client.post("/compute", json={**body, "cast_count": 20}).json()

    # 20 cast at a $50k cap admits far more than the guessed 4 would.
    assert stated["qualifying_spend"] > guessed["qualifying_spend"]


# ---------- Layer 1b: the challenge endpoint ----------

def _challenge_raw(contradictions=(), corroborations=()):
    return {"contradictions": list(contradictions), "corroborations": list(corroborations)}


def _rate_contradiction(url="https://example.gov/hb1001"):
    return {
        "field": "base_rate",
        "current_value": "30.0%",
        "source_says": "20% from tax year 2027",
        "url": url,
        "excerpt": "The credit is reduced to 20%.",
    }


def _patch_challenge(monkeypatch, raw, sources=4):
    monkeypatch.setattr("app.extraction.challenge._challenge_search", lambda rule: [object()] * sources)
    monkeypatch.setattr("app.extraction.challenge._challenge_with_forced_function_call", lambda rule, r: raw)


def test_challenge_endpoint_downgrades_confidence_on_a_material_contradiction(monkeypatch):
    _patch_challenge(monkeypatch, _challenge_raw([_rate_contradiction()]))
    rule = make_rule(jurisdiction="Georgia", base_rate=0.30)

    resp = client.post("/jurisdictions/challenge", json=jsonable_encoder(rule))
    assert resp.status_code == 200
    body = resp.json()

    assert body["rule"]["confidence"] == "conflicting"
    assert len(body["rule"]["conflicts"]) == 1
    # The figure itself is never rewritten — the disagreement is surfaced, not resolved.
    assert body["rule"]["base_rate"] == 0.30
    assert body["report"]["findings"][0]["severity"] == "material"


def test_challenge_endpoint_reports_a_clean_result_distinctly_from_no_result(monkeypatch):
    # "We looked and found nothing" is evidence; "we couldn't look" is not,
    # and the response has to let the caller tell them apart.
    _patch_challenge(monkeypatch, _challenge_raw(), sources=4)
    rule = make_rule(jurisdiction="Georgia")
    checked = client.post("/jurisdictions/challenge", json=jsonable_encoder(rule)).json()

    _patch_challenge(monkeypatch, _challenge_raw(), sources=0)
    unchecked = client.post("/jurisdictions/challenge", json=jsonable_encoder(rule)).json()

    assert checked["report"]["sources_checked"] == 4
    assert checked["report"]["findings"] == []
    assert unchecked["report"]["sources_checked"] == 0
    assert checked["rule"]["confidence"] != "conflicting"


def test_challenge_endpoint_returns_502_when_the_challenge_pass_fails(monkeypatch):
    def boom(rule):
        raise RuntimeError("Parallel timed out")

    monkeypatch.setattr("app.main.challenge_rule", boom)
    resp = client.post("/jurisdictions/challenge", json=jsonable_encoder(make_rule(jurisdiction="Georgia")))
    assert resp.status_code == 502
    assert "Parallel timed out" in resp.json()["detail"]


def test_challenge_endpoint_updates_the_cache_so_a_later_search_is_not_stale(monkeypatch):
    """A cached rule must not outlive the challenge that contradicted it.

    Otherwise the next /jurisdictions/search hands back the unchallenged
    version and the conflict silently disappears — the exact failure this
    whole pass exists to prevent, reintroduced by the cache.
    """
    from app import cache

    cache.clear()
    rule = make_rule(jurisdiction="Georgia", base_rate=0.30)
    cache.set("Georgia", rule)
    assert cache.get("Georgia").conflicts == []

    _patch_challenge(monkeypatch, _challenge_raw([_rate_contradiction()]))
    client.post("/jurisdictions/challenge", json=jsonable_encoder(rule))

    assert cache.get("Georgia").conflicts != []
    cache.clear()


def test_challenge_endpoint_does_not_populate_the_cache_for_an_unsearched_rule(monkeypatch):
    # A hand-supplied or seed rule was never cached; caching it here would
    # make a rule the user pasted in look like a live extraction.
    from app import cache

    cache.clear()
    _patch_challenge(monkeypatch, _challenge_raw([_rate_contradiction()]))
    client.post("/jurisdictions/challenge", json=jsonable_encoder(make_rule(jurisdiction="Nowhere")))

    assert cache.get("Nowhere") is None


# ---------- the suggestion list ----------

def test_suggested_jurisdictions_are_grouped_and_global():
    resp = client.get("/jurisdictions/suggested")
    assert resp.status_code == 200
    body = resp.json()

    regions = {j["region"] for j in body}
    # A US-only list would misrepresent what the tool can now do, since
    # non-USD programmes convert rather than being refused.
    assert "United States" in regions
    assert len(regions) >= 4
    assert any(j["currency"] != "USD" for j in body)
    # Hand-verified jurisdictions must be offered, since they're the ones
    # whose figures we can actually vouch for.
    names = {j["name"] for j in body}
    assert {"Georgia", "New Mexico", "Louisiana"} <= names


def test_every_suggestion_carries_what_a_reader_needs_to_choose():
    for j in client.get("/jurisdictions/suggested").json():
        assert j["name"] and j["region"] and j["currency"] and j["advertised_hint"]
