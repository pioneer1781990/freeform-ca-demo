"""Dataplex BusinessGlossary term writes via direct REST.

The python SDK's BusinessGlossaryServiceClient sends requests in a shape
the regional endpoint returns 404 for. Direct REST calls work cleanly
and surface terms in the GCP Dataplex console.

All writes are best-effort: failures log and return None so the caller
(flywheel) can still write to BQ unconditionally.
"""
from __future__ import annotations
import re
from typing import Optional

import requests
import google.auth
import google.auth.transport.requests as _gauth_req

import config as cfg

DATAPLEX_LOCATION = "us-central1"
GLOSSARY_ID = "cymbal-retail-glossary"
_API_BASE = "https://dataplex.googleapis.com/v1"


def _token() -> Optional[str]:
    try:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(_gauth_req.Request())
        return creds.token
    except Exception as e:
        print(f"[dataplex_ops._token] auth failed: {e}")
        return None


def _glossary_parent() -> str:
    return (f"projects/{cfg.PROJECT_ID}/locations/{DATAPLEX_LOCATION}"
            f"/glossaries/{GLOSSARY_ID}")


def _term_id_for(term: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", term.lower()).strip("-") or "term"
    return slug[:63]


def write_glossary_term(term: str, definition: str) -> Optional[str]:
    """Create a glossary term via REST. Returns full resource name on success,
    or None on failure. Idempotent: AlreadyExists is treated as success."""
    tok = _token()
    if not tok:
        return None
    parent = _glossary_parent()
    term_id = _term_id_for(term)
    url = f"{_API_BASE}/{parent}/terms?termId={term_id}"
    body = {
        "parent": parent,
        "displayName": (term or term_id)[:255],
        "description": (definition or "")[:1024],
    }
    headers = {"Authorization": f"Bearer {tok}",
               "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("name", f"{parent}/terms/{term_id}")
        if r.status_code == 409:
            # Already exists — treat as success
            return f"{parent}/terms/{term_id}"
        print(f"[dataplex_ops.write_glossary_term] {term!r} HTTP {r.status_code}: "
              f"{r.text[:200]}")
        return None
    except Exception as e:
        print(f"[dataplex_ops.write_glossary_term] {term!r} request failed: {e}")
        return None


def delete_glossary_term(term_or_full_name: str) -> bool:
    """Delete a glossary term. Accepts either bare term display name (will
    slugify) or full resource name. Returns True on success or NotFound."""
    tok = _token()
    if not tok:
        return False
    if term_or_full_name.startswith("projects/"):
        name = term_or_full_name
    else:
        name = f"{_glossary_parent()}/terms/{_term_id_for(term_or_full_name)}"
    headers = {"Authorization": f"Bearer {tok}"}
    try:
        r = requests.delete(f"{_API_BASE}/{name}", headers=headers, timeout=10)
        if r.status_code in (200, 404):
            return True
        print(f"[dataplex_ops.delete_glossary_term] HTTP {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[dataplex_ops.delete_glossary_term] request failed: {e}")
        return False
