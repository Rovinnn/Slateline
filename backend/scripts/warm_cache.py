"""Warm the deployed extraction cache before anyone watches.

    python scripts/warm_cache.py                       # the deployed backend
    python scripts/warm_cache.py http://localhost:8000 # a local uvicorn

A cold jurisdiction is a live Parallel search plus a Gemini extraction —
roughly 30-60 seconds. The results screen fires one per jurisdiction on mount,
so the first visitor after a cold start watches a spinner for most of a
minute. A judge opening forty submissions does not wait, and a demo video
recorded cold spends a quarter of its runtime on a loading state.

Run this immediately before recording, and again before judging opens.

Two things worth knowing about what this does and doesn't fix:

- The cache is **in-process** (app/cache.py), so it belongs to whichever Cloud
  Run instance answered. A scale-to-zero cold start or a second instance
  starts cold again. `--min-instances=1` on the service is the durable fix;
  this is the free one.
- It deliberately does **not** use `refresh=true`. The point is to populate
  the cache, and forcing a re-extraction of something already cached would
  spend quota to replace a good answer with an equivalent one.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DEFAULT_BASE = "https://incentive-verifier-backend-559874048514.us-central1.run.app"

#: What the results screen actually loads on mount. Warming anything else
#: spends quota on jurisdictions nobody is about to look at.
FRONT_PAGE = ("Georgia", "New Mexico", "Louisiana", "Texas")

#: Worth having warm for a demo that types into the search box. Kept short
#: on purpose — every extra name is another ~35 seconds of somebody's quota.
LIKELY_DEMO = ("Kentucky", "Illinois", "California", "Ireland")

OK, FAIL = "\033[32mOK\033[0m", "\033[31mFAIL\033[0m"


def warm(base: str, name: str) -> tuple[str, bool, float, str]:
    started = time.monotonic()
    req = urllib.request.Request(
        f"{base}/jurisdictions/search?jurisdiction={urllib.parse.quote(name)}",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            rule = json.loads(resp.read().decode("utf-8"))
        elapsed = time.monotonic() - started
        return name, True, elapsed, f"{rule['jurisdiction']} @ {rule['base_rate']:.0%}"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return name, False, time.monotonic() - started, str(exc)[:70]


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE).rstrip("/")
    names = FRONT_PAGE + LIKELY_DEMO
    print(f"warming {len(names)} jurisdictions on {base}\n")

    started = time.monotonic()
    # Concurrent because the backend already fans these out per request; doing
    # them serially would take five minutes for no reason.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: warm(base, n), names))

    for name, ok, elapsed, detail in results:
        print(f"  [{OK if ok else FAIL}] {name:<14} {elapsed:>5.1f}s  {detail}")

    failed = [r for r in results if not r[1]]
    print(f"\n  {len(results) - len(failed)}/{len(results)} warm in {time.monotonic() - started:.0f}s")
    if failed:
        print("  A failure here is not necessarily broken — a cold Cloud Run instance can")
        print("  exceed the timeout on its very first request. Re-run once before worrying.")
        return 1
    print("  Second load of the results screen should now be near-instant.")
    print("  Note: the cache is per-instance, so a cold start throws this away.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
