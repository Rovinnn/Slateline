"""In-process cache for Layer 1 extractions, keyed by the jurisdiction name
the caller searched for.

Every Results-screen load fires one live extraction per jurisdiction — 3
Parallel searches plus a Gemini call, each. Four jurisdictions means 30-60s
before anything renders, on *every* visit, not just the first, plus real
quota cost. Caching means a repeat lookup is instant and free; the age is
still visible (each rule's sources carry the pipeline's own `retrieved`
stamp — see extraction/agent.py), and an explicit refresh opts back into a
live call, which is more honest than a silent cache, not less.

Process-local by design: a restart or a second Cloud Run instance just means
one more live search for that jurisdiction, never a wrong answer, so this
doesn't need Redis/Firestore for what it's doing.
"""

from __future__ import annotations

from .models import JurisdictionRule

_cache: dict[str, JurisdictionRule] = {}


def _key(jurisdiction: str) -> str:
    return jurisdiction.strip().lower()


def get(jurisdiction: str) -> JurisdictionRule | None:
    return _cache.get(_key(jurisdiction))


def set(jurisdiction: str, rule: JurisdictionRule) -> None:
    _cache[_key(jurisdiction)] = rule


def clear() -> None:
    """Test-only: the cache is module-level state, so tests that search the
    same jurisdiction name need a clean slate between runs."""
    _cache.clear()
