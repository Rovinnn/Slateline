"""The ADK agent: a planner over the pipeline, tested for what it must not do.

BUILD_BRIEF.md section 4 asks that "the agent must invoke the calculator
tool". The REST pipeline satisfied that only in spirit — it called
compute_benefit itself in a fixed order with no agent involved.

Most of this file guards the thing that makes an agent wrapper dangerous
rather than useful: the moment a tool signature takes a *figure* instead of a
*name*, the model has to reproduce that figure to call the tool, and a model
restating `base_rate: 0.20` can restate it as `0.30` with nothing downstream
able to tell. Forced function calling stops the model computing a number. It
does nothing to stop it transcribing one wrongly. So the tools address
everything by name and the values stay in session.py, and that is asserted
here rather than left as a convention someone breaks later.

The model itself is never called. What's under test is the tool layer and the
agent's declared shape.
"""

from unittest.mock import patch

import pytest
from google.adk.tools import FunctionTool

from app.agent import root_agent
from app.agent import session as session_store
from app.agent.tools import (
    AGENT_TOOLS,
    compare_jurisdictions,
    compute_benefit_for,
    search_jurisdiction,
    set_budget,
)
from app.seed_jurisdictions import GEORGIA, LOUISIANA, NEW_MEXICO, TEXAS

SESSION = "test-session"


@pytest.fixture(autouse=True)
def clean_session():
    session_store.clear()
    yield
    session_store.clear()


def record_budget():
    return set_budget(
        total=2_000_000, atl_cast=250_000, atl_noncast=200_000, btl_labor=750_000,
        btl_nonlabor=550_000, post_vfx=250_000, shoot_days=22, crew_headcount=45,
        resident_labor_pct=0.55, home_base="Los Angeles, CA", session_id=SESSION,
    )


def seed(*rules):
    """Put rules in the session as though search_jurisdiction had fetched them."""
    for rule in rules:
        session_store.get(SESSION).rules[rule.jurisdiction] = rule


# ---------- the declarations ADK actually sends to the model ----------


@pytest.mark.parametrize("fn", AGENT_TOOLS, ids=[f.__name__ for f in AGENT_TOOLS])
def test_every_tool_produces_a_usable_declaration(fn):
    """Guards a silent failure that nearly shipped.

    ADK puts the derived schema in `parameters_json_schema`, not `parameters`
    — the same split that bit extraction/agent.py. Reading the wrong field
    shows an empty parameter list for a perfectly good tool, and a tool
    genuinely declared with no parameters would be uncallable while looking
    fine everywhere else.
    """
    declaration = FunctionTool(fn)._get_declaration()
    schema = declaration.parameters_json_schema

    assert declaration.description, f"{fn.__name__} has no description for the model to read"
    assert schema and schema.get("properties"), f"{fn.__name__} declared no parameters"
    # session_id is plumbing with a default; it must never be demanded of the model.
    assert "session_id" not in (schema.get("required") or [])


def test_no_tool_asks_the_model_to_hand_back_a_figure():
    """The invariant the whole design rests on.

    Every parameter is a name, a plain scalar the producer stated, or a
    session id. Nothing takes a rate, a credit, a rule or a breakdown — those
    live in session.py precisely so the model never carries them.
    """
    producer_stated = {
        "total", "atl_cast", "atl_noncast", "btl_labor", "btl_nonlabor", "post_vfx",
        "shoot_days", "crew_headcount", "resident_labor_pct", "home_base",
    }
    allowed = producer_stated | {"jurisdiction", "session_id"}

    for fn in AGENT_TOOLS:
        schema = FunctionTool(fn)._get_declaration().parameters_json_schema
        for name in (schema.get("properties") or {}):
            assert name in allowed, (
                f"{fn.__name__} takes '{name}', which the model would have to reproduce. "
                "Pass a name and look the value up in session.py instead."
            )


def test_the_agent_declares_every_tool_including_the_calculator():
    names = {getattr(t, "name", getattr(t, "__name__", "")) for t in root_agent.tools}
    assert "compute_benefit_for" in names, "the brief's 'agent must invoke the calculator tool'"
    assert names == {f.__name__ for f in AGENT_TOOLS}


def test_the_instruction_forbids_the_model_doing_arithmetic():
    # The single most load-bearing sentence in the prompt, pinned so it can't
    # be softened by an unrelated edit.
    instruction = root_agent.instruction.lower()
    assert "never perform arithmetic" in instruction
    assert "compare_jurisdictions" in instruction


# ---------- the tools, against the real calculator ----------


def test_set_budget_reports_an_inconsistent_total_without_refusing_it():
    # `total` never enters the arithmetic, so a mismatch is worth flagging but
    # not worth blocking a comparison the tool can price perfectly well.
    result = set_budget(
        total=9_000_000, atl_cast=250_000, atl_noncast=200_000, btl_labor=750_000,
        btl_nonlabor=550_000, post_vfx=250_000, shoot_days=22, crew_headcount=45,
        resident_labor_pct=0.55, home_base="Los Angeles, CA", session_id=SESSION,
    )
    assert result["recorded"] is True
    assert "$2,000,000" in result["warning"]


def test_search_stores_the_rule_but_returns_only_a_readable_summary():
    with patch("app.agent.tools.extract_jurisdiction_rule", return_value=GEORGIA):
        summary = search_jurisdiction("Georgia", session_id=SESSION)

    assert summary["headline_rate"] == "20.0%"
    assert summary["payout_mechanism"] == "transferable"
    # The rule itself is kept server-side; the model gets nothing it could
    # transcribe a figure out of.
    assert "qualifying" not in summary
    assert session_store.get(SESSION).rule_for("georgia") is not None


def test_compute_returns_the_whole_walk_from_advertised_rate_to_cash():
    record_budget()
    seed(GEORGIA)
    result = compute_benefit_for("Georgia", session_id=SESSION)

    assert result["rankable"] is True
    assert result["gross_credit"] == "$400,000"
    assert result["realizable_after_monetisation"] == "$360,000"
    assert result["value_today"] == "$303,721"
    assert result["net_benefit"] == "$199,621"
    assert result["months_to_payment"] == 18
    assert result["timing_is_assumed"] is True


def test_figures_are_preformatted_so_the_model_cannot_lose_a_digit():
    record_budget()
    seed(GEORGIA)
    result = compute_benefit_for("Georgia", session_id=SESSION)
    # Strings, not floats: prose built from "$199,621" can't drop a decimal
    # place the way prose built from 199621.45 can.
    assert isinstance(result["net_benefit"], str)
    assert result["net_benefit"].startswith("$")


def test_an_unrankable_jurisdiction_is_reported_as_such_not_as_a_zero():
    record_budget()
    seed(TEXAS)
    result = compute_benefit_for("Texas", session_id=SESSION)

    assert result["rankable"] is False
    assert "iscretionary" in result["reason"]
    assert "net_benefit" not in result


def test_caveats_reach_the_model_rather_than_being_dropped():
    record_budget()
    seed(GEORGIA)
    result = compute_benefit_for("Georgia", session_id=SESSION)
    # Georgia's sources don't state whether fringes qualify; the producer has
    # to be told that, so it must survive into the tool result.
    assert any("payroll burden left out" in c for c in result["caveats"])


# ---------- ordering, which the model gets wrong if the tools don't say so ----------


def test_computing_before_a_budget_exists_says_what_to_do():
    seed(GEORGIA)
    assert "set_budget" in compute_benefit_for("Georgia", session_id=SESSION)["error"]


def test_computing_an_unsearched_jurisdiction_says_what_to_do():
    record_budget()
    assert "search_jurisdiction" in compute_benefit_for("Utah", session_id=SESSION)["error"]


def test_jurisdiction_lookup_is_case_insensitive():
    # The model types whatever the producer typed.
    record_budget()
    seed(NEW_MEXICO)
    assert compute_benefit_for("new mexico", session_id=SESSION)["rankable"] is True


# ---------- the ranking, computed here rather than by the model ----------


def test_compare_ranks_and_states_the_margin_so_the_model_need_not_subtract():
    record_budget()
    seed(GEORGIA, NEW_MEXICO, LOUISIANA, TEXAS)
    result = compare_jurisdictions(session_id=SESSION)

    # The hand-verified order (see test_seed_jurisdictions.py).
    assert [r["jurisdiction"] for r in result["ranking"]] == ["Louisiana", "New Mexico", "Georgia"]
    assert result["ranking"][0]["position"] == 1
    # $275,552 - $266,994, computed here so the model reports rather than subtracts.
    assert result["margin_over_runner_up"] == "$8,558"


def test_compare_separates_what_cannot_be_ranked_from_what_ranked_badly():
    record_budget()
    seed(GEORGIA, TEXAS)
    result = compare_jurisdictions(session_id=SESSION)

    assert [j["jurisdiction"] for j in result["cannot_be_ranked"]] == ["Texas"]
    assert "Texas" not in [r["jurisdiction"] for r in result["ranking"]]


def test_compare_with_a_single_jurisdiction_does_not_invent_a_margin():
    record_budget()
    seed(GEORGIA)
    assert "no runner-up" in compare_jurisdictions(session_id=SESSION)["margin_over_runner_up"]


def test_sessions_do_not_leak_into_each_other():
    record_budget()
    seed(GEORGIA)
    assert "set_budget" in compare_jurisdictions(session_id="a-different-conversation")["error"]


def test_the_agent_and_the_rest_api_agree_on_the_number():
    """Same calculator, so the two entry points cannot drift.

    If they ever disagree, one of them has grown its own arithmetic — which is
    the failure this whole project is arranged to prevent.
    """
    from app.calculator import compute_benefit
    from tests.test_seed_jurisdictions import INDIE_DRAMA_BUDGET

    record_budget()
    seed(LOUISIANA)
    via_agent = compare_jurisdictions(session_id=SESSION)["ranking"][0]["net_benefit"]
    direct = compute_benefit(INDIE_DRAMA_BUDGET, LOUISIANA, distance_km=None)

    assert via_agent == "$" + f"{direct.net_benefit:,.0f}"


# ---------- which Google product the agent actually talks to ----------


def test_the_agent_is_routed_through_vertex_not_the_developer_api():
    """Found by running the CLI, not by reading the docs.

    ADK builds its own genai client and defaults to the Gemini *Developer*
    API, so without this the agent fails with "No API key was provided" and a
    link to ai.google.dev — while the rest of Layer 1 authenticates to Vertex
    with application-default credentials and no API key anywhere.

    The failure reads like a missing secret when it's actually a missing
    setting, which is exactly the kind of thing that costs an hour at the
    wrong moment. Importing app.agent must be enough to fix it.
    """
    import os

    import app.agent  # noqa: F401  - imported for its import-time side effect

    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"].upper() == "TRUE"
    assert os.environ.get("GOOGLE_CLOUD_LOCATION")


def test_vertex_routing_does_not_override_an_explicit_deployment_setting():
    import os

    from app.agent.agent import _route_through_vertex

    previous = os.environ.get("GOOGLE_CLOUD_LOCATION")
    os.environ["GOOGLE_CLOUD_LOCATION"] = "europe-west4"
    try:
        _route_through_vertex()
        assert os.environ["GOOGLE_CLOUD_LOCATION"] == "europe-west4"
    finally:
        if previous is None:
            del os.environ["GOOGLE_CLOUD_LOCATION"]
        else:
            os.environ["GOOGLE_CLOUD_LOCATION"] = previous
