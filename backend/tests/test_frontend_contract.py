"""The backend/frontend type contract, enforced instead of hoped for.

frontend/src/types.ts opens by claiming it "mirrors backend/app/models.py
exactly". Nothing checked that, and the two halves deploy independently — a
field added to a dataclass reaches production in the API response days before
(or after) the frontend that reads it. Drift here doesn't raise; it renders
`undefined`.

This is the same idea as test_extraction_schema.py, which pins the dataclasses
against the schema Gemini is forced to fill. That one guards the model-facing
edge of JurisdictionRule; this one guards the browser-facing edge. Between
them, a field can't be added to models.py and quietly forgotten at either end.

Written the first time it caught something: `currency` had been added to
JurisdictionRule for the non-USD guard and was missing from types.ts.

Parsing TypeScript with regex is normally a bad idea. It's the right call here
because the alternative is a build-time codegen step for one file, and because
types.ts is hand-written in a deliberately boring subset — flat interfaces of
`name: type;`. If that stops being true, this test fails loudly rather than
silently passing, which is the correct direction to fail in.
"""

from __future__ import annotations

import re
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Literal, get_args

import pytest

from app import models
from app.calculator import QUALIFYING_KEYS

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types.ts"


@pytest.fixture(scope="module")
def ts_source() -> str:
    if not TYPES_TS.exists():  # pragma: no cover - only if the repo layout moves
        pytest.skip(f"frontend types not found at {TYPES_TS}")
    return _strip_comments(TYPES_TS.read_text(encoding="utf-8"))


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", src)


def _interface_fields(src: str, name: str) -> set[str]:
    """Field names declared on `export interface <name>`.

    Matches to the first closing brace at column 0, which is what makes the
    flat-interface assumption in the module docstring load-bearing.
    """
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", src, flags=re.DOTALL)
    assert match, f"types.ts has no `export interface {name}`"
    return set(re.findall(r"^\s*(\w+)\??\s*:", match.group(1), flags=re.MULTILINE))


def _union_members(src: str, name: str) -> set[str]:
    """String literals of `export type <name> = "a" | "b";`."""
    match = re.search(rf"export type {name} =([^;]*);", src, flags=re.DOTALL)
    assert match, f"types.ts has no `export type {name}`"
    return set(re.findall(r'"([^"]*)"', match.group(1)))


def _dataclass_fields(cls) -> set[str]:
    return {f.name for f in fields(cls)}


# ---------- field-for-field parity on every shared model ----------

# Named individually rather than discovered, so adding a dataclass to models.py
# that the frontend genuinely doesn't need doesn't fail the build.
SHARED_MODELS = [
    ("SourceRef", models.SourceRef),
    ("Tier", models.Tier),
    ("Uplift", models.Uplift),
    ("JurisdictionRule", models.JurisdictionRule),
    ("BudgetVector", models.BudgetVector),
    ("RelocationAssumptions", models.RelocationAssumptions),
    ("CreditTimingAssumptions", models.CreditTimingAssumptions),
    ("BenefitBreakdown", models.BenefitBreakdown),
]


@pytest.mark.parametrize("ts_name,dataclass", SHARED_MODELS, ids=[n for n, _ in SHARED_MODELS])
def test_every_shared_model_has_identical_fields_on_both_sides(ts_source, ts_name, dataclass):
    backend = _dataclass_fields(dataclass)
    frontend = _interface_fields(ts_source, ts_name)

    missing_in_ts = backend - frontend
    extra_in_ts = frontend - backend
    assert not missing_in_ts, (
        f"{ts_name}: backend sends {sorted(missing_in_ts)}, which types.ts doesn't declare — "
        "the frontend can't read a field it doesn't know about"
    )
    assert not extra_in_ts, (
        f"{ts_name}: types.ts declares {sorted(extra_in_ts)}, which the backend never sends — "
        "reads of it are undefined at runtime, whatever TypeScript thinks"
    )


# ---------- the enums, where a missing member is a silently unstyled badge ----------


@pytest.mark.parametrize(
    "ts_name,literal",
    [("Confidence", models.Confidence), ("PoolStatus", models.PoolStatus), ("CreditType", models.CreditType)],
)
def test_literal_unions_match(ts_source, ts_name, literal):
    # Results.tsx keys POOL_STATUS_LABEL/CLASS off these by exact string. A
    # member the frontend doesn't list isn't a type error there — it's an
    # undefined lookup and an unstyled badge.
    assert _union_members(ts_source, ts_name) == set(get_args(literal))


def test_qualifying_map_matches_the_calculator_key_set(ts_source):
    # JurisdictionRule.qualifying is an untyped dict on the backend, so this is
    # the only place the six keys are pinned across the boundary.
    assert _interface_fields(ts_source, "QualifyingMap") == set(QUALIFYING_KEYS)


# ---------- defaults, which the frontend sends back as real values ----------


@pytest.mark.parametrize(
    "const_name,ts_type,dataclass",
    [
        ("DEFAULT_RELOCATION_ASSUMPTIONS", "RelocationAssumptions", models.RelocationAssumptions),
        ("DEFAULT_CREDIT_TIMING", "CreditTimingAssumptions", models.CreditTimingAssumptions),
    ],
)
def test_frontend_assumption_defaults_equal_the_python_defaults(ts_source, const_name, ts_type, dataclass):
    """These constants are sent on every /compute call.

    So a drifted default isn't a cosmetic mismatch — the deployed app would
    silently price against different assumptions than the test suite, the
    smoke test, and every golden number in the repo. Timing is the worse of
    the two to drift: the discount rate compounds over a wait of a year or
    more, so a small difference moves the ranking, not just a figure.
    """
    match = re.search(
        rf"export const {const_name}: {ts_type} = " + r"\{(.*?)\n\};",
        ts_source,
        flags=re.DOTALL,
    )
    assert match, f"types.ts has no {const_name}"
    declared = {k: float(v) for k, v in re.findall(r"^\s*(\w+)\s*:\s*([\d.]+)", match.group(1), flags=re.MULTILINE)}

    python_defaults = {f.name: f.default for f in fields(dataclass) if f.default is not MISSING}
    assert declared == pytest.approx(python_defaults)


def test_parsed_budget_shape_is_declared(ts_source):
    # Not a dataclass in models.py (it lives in extraction/budget_parser.py),
    # but it crosses the same boundary via /budget/parse.
    from app.extraction.budget_parser import ParsedBudget

    assert _interface_fields(ts_source, "ParsedBudget") == _dataclass_fields(ParsedBudget)


@pytest.mark.parametrize("ts_name", ["ChallengeFinding", "ChallengeReport"])
def test_challenge_shapes_are_declared(ts_name):
    # Same boundary, via /jurisdictions/challenge. These live in
    # extraction/challenge.py rather than models.py, so they'd otherwise sit
    # outside every parity check in this file.
    from app.extraction import challenge

    src = _strip_comments(TYPES_TS.read_text(encoding="utf-8"))
    assert _interface_fields(src, ts_name) == _dataclass_fields(getattr(challenge, ts_name))


def test_the_challenge_severity_union_matches_the_backend(ts_source):
    from app.extraction.challenge import Severity

    match = re.search(r'severity:\s*([^;]+);', ts_source)
    assert match, "ChallengeFinding declares no severity"
    assert set(re.findall(r'"([^"]*)"', match.group(1))) == set(get_args(Severity))


# ---------- the parser's own assumptions, so a silent pass is impossible ----------


def test_the_parser_actually_finds_fields_rather_than_vacuously_passing(ts_source):
    """Guards the tests above.

    Every parity assertion is `set == set`. If the regex quietly matched
    nothing, empty-vs-empty would pass and the whole file would go green while
    checking nothing.
    """
    assert len(_interface_fields(ts_source, "JurisdictionRule")) > 20
    assert len(_union_members(ts_source, "PoolStatus")) == 4


def test_comment_stripping_does_not_eat_declarations():
    # `//` inside a doc comment URL, and a field right after a doc comment,
    # are the two ways a naive strip loses a real field.
    src = _strip_comments(
        'export interface X {\n'
        '  /** see https://example.com/a */\n'
        '  kept: string;\n'
        '  // trailing note\n'
        '  also_kept: number;\n'
        '}\n'
    )
    assert _interface_fields(src, "X") == {"kept", "also_kept"}
