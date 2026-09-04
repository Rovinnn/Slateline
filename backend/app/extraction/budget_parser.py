"""Parses an uploaded budget PDF into a BudgetVector — BUILD_BRIEF.md
section 7's third entry point.

Same discipline as jurisdiction extraction (agent.py): the model reads and
quotes, it never computes. It is asked for the figures printed on the
topsheet and for a short note saying where each one came from; it is not
asked to total anything. If the PDF's own total doesn't equal the sum of
its categories, that discrepancy is the user's to see and resolve — the
form's existing sum check surfaces it — rather than something the model
silently reconciles.

The result deliberately goes back to the *form*, pre-filled and fully
editable, never straight to results: a parsed number the producer hasn't
looked at is exactly the kind of figure this whole tool exists to stop
people from trusting blindly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from ..config import settings
from ..models import BudgetVector

MAX_PDF_BYTES = 25 * 1024 * 1024  # matches the 25 MB the upload card advertises

# Money lines the model is asked to find. Kept in one place so the schema,
# the defaults and the tests can't drift apart.
MONEY_FIELDS = ("total", "atl_cast", "atl_noncast", "btl_labor", "btl_nonlabor", "post_vfx")
COUNT_FIELDS = ("shoot_days", "crew_headcount")

RECORD_BUDGET_SCHEMA: dict[str, Any] = {
    "name": "record_budget",
    "description": (
        "Record the production budget figures printed in this document. Report only figures the "
        "document actually states. Do not add, subtract, or reconcile any numbers — if a line isn't "
        "shown, leave it null and say so in warnings."
    ),
    "parameters": {
        "type": "object",
        # Nothing is required: a topsheet that omits crew headcount is a
        # normal document, not a malformed one. Absent -> null -> the form
        # shows an empty field with a warning, which the producer fills in.
        "properties": {
            **{
                name: {
                    "type": ["number", "null"],
                    "description": f"{name.replace('_', ' ')} in dollars, as printed",
                }
                for name in MONEY_FIELDS
            },
            **{name: {"type": ["integer", "null"]} for name in COUNT_FIELDS},
            "resident_labor_pct": {
                "type": ["number", "null"],
                "description": "Share of below-the-line labor that is local/resident hire, 0-1. Usually absent from a budget; leave null unless stated.",
            },
            "field_notes": {
                "type": "object",
                "description": (
                    "For each field you filled, where in the document it came from — e.g. "
                    "'page 1, topsheet total' or 'accounts 2000-3900'. Keys must match the field names."
                ),
                "additionalProperties": {"type": "string"},
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Anything a reader should check: fields not found, ambiguous line items, figures that appear to be in another currency.",
            },
        },
    },
}


@dataclass
class ParsedBudget:
    """A BudgetVector plus the provenance the brief requires the form to show
    ("each parsed field annotated with where it came from")."""

    budget: BudgetVector
    field_notes: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _extract_with_forced_function_call(pdf_bytes: bytes) -> dict:
    client = genai.Client(
        vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location
    )
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            (
                "This is a film production budget. Record the figures it states using record_budget. "
                "Quote what is printed; never total, derive, or reconcile figures yourself. Leave a "
                "field null if the document doesn't state it."
            ),
        ],
        config={
            "tools": [
                {
                    "function_declarations": [
                        {
                            "name": RECORD_BUDGET_SCHEMA["name"],
                            "description": RECORD_BUDGET_SCHEMA["description"],
                            # See agent.py: `parameters` is a genai Schema that
                            # rejects the ["number", "null"] unions used above.
                            "parameters_json_schema": RECORD_BUDGET_SCHEMA["parameters"],
                        }
                    ]
                }
            ],
            "tool_config": {
                "function_calling_config": {"mode": "ANY", "allowed_function_names": ["record_budget"]}
            },
        },
    )
    for part in response.candidates[0].content.parts:
        if part.function_call is not None:
            return dict(part.function_call.args)
    raise RuntimeError(
        f"Gemini returned no function call despite mode=ANY; response text was: {response.text!r}"
    )


def _number(raw: Any) -> float:
    """Absent or unparseable -> 0.0, which the form renders as an empty-ish
    field for the user to correct. Never a guess at what it should have been.
    """
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def parse_budget_pdf(pdf_bytes: bytes, *, home_base: str = "Los Angeles, CA") -> ParsedBudget:
    """PDF bytes in, a pre-filled (and explicitly annotated) BudgetVector out."""
    if not pdf_bytes:
        raise ValueError("Empty file")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"File is larger than the {MAX_PDF_BYTES // (1024 * 1024)} MB limit")
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("That file isn't a PDF (no %PDF header)")

    raw = _extract_with_forced_function_call(pdf_bytes)

    warnings = [str(w) for w in raw.get("warnings", [])]
    notes = {str(k): str(v) for k, v in (raw.get("field_notes") or {}).items()}

    for name in (*MONEY_FIELDS, *COUNT_FIELDS):
        if raw.get(name) is None:
            warnings.append(f"{name.replace('_', ' ')} was not found in the document — enter it manually.")

    # Home base and constraints are production decisions, not budget lines;
    # they're never in the PDF, so they keep their defaults for the user to set.
    budget = BudgetVector(
        total=_number(raw.get("total")),
        atl_cast=_number(raw.get("atl_cast")),
        atl_noncast=_number(raw.get("atl_noncast")),
        btl_labor=_number(raw.get("btl_labor")),
        btl_nonlabor=_number(raw.get("btl_nonlabor")),
        post_vfx=_number(raw.get("post_vfx")),
        shoot_days=int(_number(raw.get("shoot_days"))) or 1,
        crew_headcount=int(_number(raw.get("crew_headcount"))) or 1,
        resident_labor_pct=min(max(_number(raw.get("resident_labor_pct")), 0.0), 1.0),
        home_base=home_base,
        constraints=[],
    )

    if raw.get("resident_labor_pct") is None:
        warnings.append(
            "Resident labor share isn't a budget line — set it yourself; it materially changes the ranking."
        )

    return ParsedBudget(budget=budget, field_notes=notes, warnings=warnings)
