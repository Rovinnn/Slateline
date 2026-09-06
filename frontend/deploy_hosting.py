"""Publish dist/ to Firebase Hosting via the REST API.

    python deploy_hosting.py [--site SITE] [--dry-run]

There is no firebase.json in this repo and no Firebase CLI login for this
account — see HANDOFF.md. The REST flow reuses the gcloud credential that is
already established, which is why this exists instead of `firebase deploy`.

Flow, per Firebase Hosting v1beta1:
  versions.create -> populateFiles -> upload each required file -> finalize
  -> releases.create

Two details that are easy to get wrong and silently produce a broken site:

- Every file must be **gzipped**, and the hash Firebase matches on is the
  SHA-256 of the *gzipped* bytes, not the original. A hash of the raw file
  uploads fine and then never matches, so the version finalizes with missing
  files.
- The rewrite to /index.html is what makes a single-page app work. Without it
  every route except / returns 404, which looks like a broken deploy rather
  than a missing config.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://firebasehosting.googleapis.com/v1beta1"
DIST = Path(__file__).resolve().parent / "dist"


def access_token() -> str:
    """Reuse the credential gcloud already holds.

    shell=True because on Windows `gcloud` is a .cmd shim rather than an
    executable, and CreateProcess can't run it directly — the failure is a
    bare "The system cannot find the file specified", which reads like gcloud
    isn't installed when it is.
    """
    out = subprocess.run(
        "gcloud auth print-access-token", shell=True, capture_output=True, text=True
    )
    token = out.stdout.strip()
    if not token:
        raise SystemExit(
            "could not get an access token from gcloud"
            + (f": {out.stderr.strip()[:300]}" if out.stderr.strip() else "")
        )
    return token


#: Sent on every call. A `gcloud auth print-access-token` credential is a
#: *user* credential, and Firebase Hosting refuses those without an explicit
#: billing/quota project — the rejection is a 403 SERVICE_DISABLED, which
#: reads like the API is turned off rather than like a missing header.
PROJECT = "zeta-structure-437412-v7"


def call(method: str, url: str, token: str, body=None, raw: bytes | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT}
    if raw is not None:
        data, headers["Content-Type"] = raw, "application/octet-stream"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = resp.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {url}\n  HTTP {e.code}: {e.read().decode()[:600]}") from e


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="zeta-structure-437412-v7")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DIST.is_dir():
        raise SystemExit(f"no build output at {DIST} — run `npm run build` first")

    # Hash of the gzipped bytes, keyed by the site-absolute path Firebase serves.
    payloads: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for path in sorted(p for p in DIST.rglob("*") if p.is_file()):
        route = "/" + path.relative_to(DIST).as_posix()
        blob = gzip.compress(path.read_bytes(), mtime=0)
        payloads[route] = blob
        hashes[route] = hashlib.sha256(blob).hexdigest()
    print(f"{len(hashes)} files to publish to site '{args.site}'")
    for route in hashes:
        print(f"  {route}")
    if args.dry_run:
        return 0

    token = access_token()

    version = call(
        "POST",
        f"{API}/sites/{args.site}/versions",
        token,
        {
            "config": {
                # Single-page app: every unmatched route serves index.html so
                # client-side navigation and deep links work.
                "rewrites": [{"glob": "**", "path": "/index.html"}],
                "headers": [
                    {
                        "glob": "/assets/**",
                        "headers": {"Cache-Control": "public, max-age=31536000, immutable"},
                    }
                ],
            }
        },
    )
    version_name = version["name"]
    print(f"\ncreated {version_name}")

    populated = call("POST", f"{API}/{version_name}:populateFiles", token, {"files": hashes})
    required = populated.get("uploadRequiredHashes") or []
    upload_url = populated.get("uploadUrl", "").rstrip("/")
    print(f"{len(required)} of {len(hashes)} files need uploading")

    by_hash = {h: payloads[route] for route, h in hashes.items()}
    for i, digest in enumerate(required, 1):
        call("POST", f"{upload_url}/{digest}", token, raw=by_hash[digest])
        print(f"  uploaded {i}/{len(required)}")

    call("PATCH", f"{API}/{version_name}?update_mask=status", token, {"status": "FINALIZED"})
    release = call("POST", f"{API}/sites/{args.site}/releases?versionName={version_name}", token)
    print(f"\nreleased: {release.get('name', '(no name returned)')}")
    print(f"live at https://{args.site}.web.app")
    return 0


if __name__ == "__main__":
    sys.exit(main())
