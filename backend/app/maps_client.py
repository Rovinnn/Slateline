"""Relocation distance via Google Maps Platform. Requires GOOGLE_MAPS_API_KEY.

STATUS: stub — not verified against a real call yet. Build order step 1
("one Maps distance call") and step 5 ("relocation cost via Maps") both
depend on this. Fill in / verify once GOOGLE_MAPS_API_KEY is available;
consider switching to the Routes API if Distance Matrix pricing/quota
doesn't fit (both return distance + duration, shape differs slightly).
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
