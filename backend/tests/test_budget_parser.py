"""Budget PDF parsing (BUILD_BRIEF.md section 7's upload path).

Gemini's multimodal call is mocked — these cover the contract around it:
that a rejected file is rejected before any model call is made, that absent
figures become visible warnings instead of invented numbers, and that the
model is never asked to total anything.
"""

from unittest.mock import patch

import pytest

from app.extraction.budget_parser import (
    MAX_PDF_BYTES,
    MONEY_FIELDS,
    RECORD_BUDGET_SCHEMA,
    parse_budget_pdf,
)

MINIMAL_PDF = b"%PDF-1.4\n%fake bytes for tests\n"


def _canned(**overrides) -> dict:
    raw = {
        "total": 2_000_000,
        "atl_cast": 250_000,
        "atl_noncast": 200_000,
        "btl_labor": 750_000,
        "btl_nonlabor": 550_000,
        "post_vfx": 250_000,
        "shoot_days": 22,
        "crew_headcount": 45,
        "resident_labor_pct": None,
        "field_notes": {"total": "page 1, topsheet total", "atl_cast": "account 1200"},
        "warnings": [],
    }
    raw.update(overrides)
    return raw


# ---------- files rejected before any model call ----------

@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_empty_file_is_rejected_without_calling_the_model(mock_extract):
    with pytest.raises(ValueError, match="Empty file"):
        parse_budget_pdf(b"")
    mock_extract.assert_not_called()


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_non_pdf_is_rejected_without_calling_the_model(mock_extract):
    with pytest.raises(ValueError, match="isn't a PDF"):
        parse_budget_pdf(b"PK\x03\x04 this is a zip")
    mock_extract.assert_not_called()


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_oversized_file_is_rejected_without_calling_the_model(mock_extract):
    with pytest.raises(ValueError, match="larger than"):
        parse_budget_pdf(b"%PDF" + b"x" * MAX_PDF_BYTES)
    mock_extract.assert_not_called()


# ---------- normal parse ----------

@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_parses_a_topsheet_into_a_budget_vector(mock_extract):
    mock_extract.return_value = _canned()
    parsed = parse_budget_pdf(MINIMAL_PDF)

    assert parsed.budget.total == 2_000_000
    assert parsed.budget.atl_cast == 250_000
    assert parsed.budget.shoot_days == 22
    assert parsed.budget.crew_headcount == 45
    assert parsed.field_notes["total"] == "page 1, topsheet total"


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_home_base_and_constraints_are_not_taken_from_the_pdf(mock_extract):
    # They're production decisions, never budget lines — the form collects them.
    mock_extract.return_value = _canned()
    parsed = parse_budget_pdf(MINIMAL_PDF, home_base="New York, NY")
    assert parsed.budget.home_base == "New York, NY"
    assert parsed.budget.constraints == []


# ---------- missing figures surface, they don't get invented ----------

@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_absent_figures_become_zero_and_a_warning_not_a_guess(mock_extract):
    mock_extract.return_value = _canned(btl_nonlabor=None, post_vfx=None)
    parsed = parse_budget_pdf(MINIMAL_PDF)

    assert parsed.budget.btl_nonlabor == 0
    assert parsed.budget.post_vfx == 0
    assert any("btl nonlabor" in w for w in parsed.warnings)
    assert any("post vfx" in w for w in parsed.warnings)


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_a_missing_total_is_not_reconstructed_from_the_categories(mock_extract):
    # Summing here would be this module doing the arithmetic the brief keeps
    # in calculator.py, and would paper over a topsheet that doesn't add up.
    mock_extract.return_value = _canned(total=None)
    parsed = parse_budget_pdf(MINIMAL_PDF)
    assert parsed.budget.total == 0
    assert any("total" in w for w in parsed.warnings)


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_missing_resident_labor_share_warns_because_it_moves_the_ranking(mock_extract):
    mock_extract.return_value = _canned(resident_labor_pct=None)
    parsed = parse_budget_pdf(MINIMAL_PDF)
    assert parsed.budget.resident_labor_pct == 0.0
    assert any("Resident labor share" in w for w in parsed.warnings)


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_out_of_range_resident_share_is_clamped(mock_extract):
    mock_extract.return_value = _canned(resident_labor_pct=55)  # 55 read as a percent, not a fraction
    parsed = parse_budget_pdf(MINIMAL_PDF)
    assert parsed.budget.resident_labor_pct == 1.0


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_unparseable_figure_falls_back_to_zero_rather_than_raising(mock_extract):
    mock_extract.return_value = _canned(atl_cast="two hundred fifty thousand")
    parsed = parse_budget_pdf(MINIMAL_PDF)
    assert parsed.budget.atl_cast == 0


@patch("app.extraction.budget_parser._extract_with_forced_function_call")
def test_zero_counts_become_one_so_the_form_stays_valid(mock_extract):
    # shoot_days/crew_headcount of 0 would divide badly downstream; 1 is the
    # smallest honest placeholder and the form makes the user correct it.
    mock_extract.return_value = _canned(shoot_days=0, crew_headcount=0)
    parsed = parse_budget_pdf(MINIMAL_PDF)
    assert parsed.budget.shoot_days == 1
    assert parsed.budget.crew_headcount == 1


# ---------- schema shape ----------

def test_schema_asks_for_every_money_line_the_form_shows():
    props = RECORD_BUDGET_SCHEMA["parameters"]["properties"]
    for name in MONEY_FIELDS:
        assert name in props


def test_schema_requires_nothing_so_an_incomplete_topsheet_is_still_readable():
    # A budget that omits a line is a normal document; forcing the model to
    # supply one invites an invented figure.
    assert "required" not in RECORD_BUDGET_SCHEMA["parameters"]


def test_schema_never_asks_the_model_for_a_derived_figure():
    props = set(RECORD_BUDGET_SCHEMA["parameters"]["properties"])
    for derived in ("net_benefit", "gross_credit", "qualifying_spend", "sum", "subtotal"):
        assert derived not in props
