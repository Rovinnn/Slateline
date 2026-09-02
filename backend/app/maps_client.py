"""Relocation distance via Google Maps Platform. Requires GOOGLE_MAPS_API_KEY.

STATUS: verified live. Build order step 1's "one Maps distance call" passes —
Los Angeles -> Atlanta returns 3,498 km / 31.6 h via scripts/check_credentials.py.
Note that routes.googleapis.com is not offered on this project, so the Routes
API is not an available fallback; Distance Matrix is the path.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import settings


@dataclass
class DistanceResult:
    distance_km: float
    travel_time_hours: float


def get_distance(origin: str, destination_lat: float, destination_lng: float) -> DistanceResult:
    """Hub-to-hub distance and travel time from a home-base string (e.g. "Los
    Angeles, CA") to a jurisdiction's centroid.
    """
    params = {
        "origins": origin,
        "destinations": f"{destination_lat},{destination_lng}",
        "key": settings.google_maps_api_key,
    }
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/distancematrix/json", params=params, timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    element = data["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise RuntimeError(
            f"Distance Matrix returned {element['status']} for {origin} -> "
            f"{destination_lat},{destination_lng}"
        )
    return DistanceResult(
        distance_km=element["distance"]["value"] / 1000,
        travel_time_hours=element["duration"]["value"] / 3600,
    )
