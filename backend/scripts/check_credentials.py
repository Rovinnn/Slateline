"""Build order step 1: prove every credential works before anything depends on it.

    cd backend && .venv/bin/python scripts/check_credentials.py

Makes exactly one real call per service — a Parallel search, a Gemini call via
Vertex, a Maps distance lookup — and reports each independently so a missing
key for one service doesn't hide a working one elsewhere. Reads keys through
app.config, so it exercises the same .env / Secret Manager path the app uses.
"""

from __future__ import annotations

import sys
import traceback

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

OK, FAIL = "\033[32mOK\033[0m", "\033[31mFAIL\033[0m"


def check(label: str, fn) -> bool:
    try:
        detail = fn()
    except Exception as exc:  # noqa: BLE001 — this script's whole job is reporting failures
        print(f"[{FAIL}] {label}: {type(exc).__name__}: {exc}")
        if "-v" in sys.argv:
            traceback.print_exc()
        return False
    print(f"[{OK}] {label}: {detail}")
    return True


def check_parallel() -> str:
    from parallel import Parallel

    client = Parallel(api_key=settings.parallel_api_key)
    response = client.search(
        objective="Georgia film production tax incentive — primary statute text",
        search_queries=["Georgia film tax credit statute"],
        mode="fast",  # this is a liveness check, not a real extraction — keep it cheap
    )
    if not response.results:
        raise RuntimeError("search returned zero results")
    return f"{len(response.results)} results, first: {response.results[0].url}"


def check_vertex() -> str:
    from google import genai

    if not settings.google_cloud_project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is unset")
    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents="Reply with the single word: ready",
    )
    return f"gemini-2.5-pro in {settings.google_cloud_location} said {response.text.strip()!r}"


def check_maps() -> str:
    from app.maps_client import get_distance

    # Los Angeles -> Atlanta, GA centroid. Roughly 3,400 km by road.
    result = get_distance("Los Angeles, CA", 33.749, -84.388)
    return f"LA -> Atlanta {result.distance_km:,.0f} km / {result.travel_time_hours:.1f} h"


def main() -> int:
    print("Checking credentials (one real call per service)\n")
    results = [
        check("Parallel Search   (PARALLEL_API_KEY)", check_parallel),
        check("Gemini via Vertex (GOOGLE_CLOUD_PROJECT + ADC)", check_vertex),
        check("Maps distance     (GOOGLE_MAPS_API_KEY)", check_maps),
    ]
    print()
    if all(results):
        print("All three verified — build order step 1 is satisfied.")
        return 0
    print("Fix the failures above before building on them. Re-run with -v for tracebacks.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
