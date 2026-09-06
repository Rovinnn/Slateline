"""Where the numbers live while an agent conversation is running.

The point of this module is what it keeps *away* from the model.

A naive ADK wrapper would give the agent tools like
`compute_benefit(budget: dict, rule: dict)`, and the model would have to emit
the whole budget and the whole extracted rule as JSON on every call. That
reintroduces precisely the failure the rest of this project is built to
prevent: a model restating `base_rate: 0.20` has an opportunity to restate it
as `0.30`, and nothing downstream could tell. Forced function calling stops
the model *computing* a number; it does nothing to stop it *transcribing* one
incorrectly.

So the tools in tools.py address everything by name. Budgets and extracted
rules are held here, keyed by session, and a tool call carries a jurisdiction
string — never a figure. The model chooses what to look up and in what order;
it never handles the values, which means the arithmetic path from budget to
recommendation is identical to the one the REST API uses, with the model
attached only as a planner.

In-process and per-session, like app/cache.py and for the same reasons: a
restart or a second Cloud Run instance costs one more extraction, never a
wrong answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models import BudgetVector, JurisdictionRule, RelocationAssumptions


@dataclass
class AgentSession:
    """One conversation's working state."""

    budget: Optional[BudgetVector] = None
    assumptions: RelocationAssumptions = field(default_factory=RelocationAssumptions)
    #: jurisdiction name (as canonicalised by Layer 1) -> extracted rule
    rules: dict[str, JurisdictionRule] = field(default_factory=dict)
    #: jurisdiction name -> routed distance in km, when Maps has been asked
    distances: dict[str, float] = field(default_factory=dict)

    def rule_for(self, jurisdiction: str) -> Optional[JurisdictionRule]:
        """Case-insensitive lookup, because the model types what the user typed."""
        wanted = jurisdiction.strip().lower()
        for name, rule in self.rules.items():
            if name.lower() == wanted:
                return rule
        return None


_sessions: dict[str, AgentSession] = {}


def get(session_id: str) -> AgentSession:
    """The session's state, created empty on first use."""
    return _sessions.setdefault(session_id, AgentSession())


def clear() -> None:
    """Test-only: module-level state needs a clean slate between runs."""
    _sessions.clear()
