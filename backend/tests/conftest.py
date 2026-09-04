import pytest

from app import cache


@pytest.fixture(autouse=True)
def _clear_jurisdiction_cache():
    """app.cache is module-level state (see its docstring for why) — tests
    that search the same jurisdiction name would otherwise see a cache hit
    left over from an earlier test."""
    cache.clear()
    yield
    cache.clear()
