"""Runtime configuration. Reads secrets from the environment first (local
dev, .env — never committed); falls back to Google Secret Manager when
GOOGLE_CLOUD_PROJECT is set. Never hardcode a key here or in any committed
file — see BUILD_BRIEF.md section 2.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


@lru_cache
def _secret_manager_client():
    from google.cloud import secretmanager  # imported lazily so local dev without the package still works

    return secretmanager.SecretManagerServiceClient()


def get_secret(name: str, *, required: bool = True) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        try:
            client = _secret_manager_client()
            resource = f"projects/{project}/secrets/{name}/versions/latest"
            response = client.access_secret_version(name=resource)
            return response.payload.data.decode("utf-8")
        except Exception:
            pass
    if required:
        raise RuntimeError(f"Missing required secret: {name} (set env var locally, or Secret Manager in prod)")
    return None


class Settings:
    google_cloud_project: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    google_cloud_location: str = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    @property
    def parallel_api_key(self) -> str:
        return get_secret("PARALLEL_API_KEY")

    @property
    def google_maps_api_key(self) -> str:
        return get_secret("GOOGLE_MAPS_API_KEY")


settings = Settings()
