"""Dataplex Catalog write helpers.

Best-effort writes of glossary terms into Dataplex so they show up in the GCP
console. Failures are logged but never raised — the caller (flywheel) must
always be able to fall back to the BQ-only path.
"""
from __future__ import annotations
import re
from typing import Optional

from google.api_core import client_options as _client_options_lib
from google.api_core import exceptions as gcp_exceptions
from google.cloud import dataplex_v1

import config as cfg


# Defaults for the Cymbal Retail demo.
DATAPLEX_LOCATION = "us-central1"
GLOSSARY_ID = "cymbal-retail-glossary"


def _client() -> dataplex_v1.BusinessGlossaryServiceClient:
    """Build a regional Dataplex business-glossary client."""
    endpoint = f"{DATAPLEX_LOCATION}-dataplex.googleapis.com"
    return dataplex_v1.BusinessGlossaryServiceClient(
        client_options=_client_options_lib.ClientOptions(api_endpoint=endpoint)
    )


def _glossary_parent() -> str:
    return (
        f"projects/{cfg.PROJECT_ID}/locations/{DATAPLEX_LOCATION}"
        f"/glossaries/{GLOSSARY_ID}"
    )


def _term_id_for(term: str) -> str:
    """Dataplex term IDs must be lowercase alphanumeric + hyphens.

    Keep it deterministic so re-promoting the same term collides (caller
    treats AlreadyExists as success).
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", term.lower()).strip("-")
    if not slug:
        slug = "term"
    # Dataplex term IDs are limited (<=63 chars in practice).
    return slug[:63]


def write_glossary_term(term: str, definition: str) -> Optional[str]:
    """Create a glossary term in Dataplex. Returns the full resource name on
    success, or None if the write failed (including AlreadyExists — the row
    is already present, so caller can treat it as a no-op success).

    Never raises. Logs to stdout on error.
    """
    try:
        client = _client()
        parent = _glossary_parent()
        term_id = _term_id_for(term)
        gt = dataplex_v1.GlossaryTerm(
            display_name=term[:255] if term else term_id,
            description=(definition or "")[:1024],
            parent=parent,
        )
        resp = client.create_glossary_term(
            parent=parent, term=gt, term_id=term_id,
        )
        return resp.name
    except gcp_exceptions.AlreadyExists:
        # Term already exists — return the deterministic name.
        return f"{_glossary_parent()}/terms/{_term_id_for(term)}"
    except Exception as e:
        print(f"[dataplex_ops.write_glossary_term] best-effort write failed "
              f"for {term!r}: {type(e).__name__}: {str(e)[:200]}")
        return None


def delete_glossary_term(term: str) -> bool:
    """Delete a glossary term by its deterministic ID. Returns True on success
    (or NotFound). Never raises.
    """
    try:
        client = _client()
        name = f"{_glossary_parent()}/terms/{_term_id_for(term)}"
        client.delete_glossary_term(name=name)
        return True
    except gcp_exceptions.NotFound:
        return True
    except Exception as e:
        print(f"[dataplex_ops.delete_glossary_term] failed for {term!r}: "
              f"{type(e).__name__}: {str(e)[:200]}")
        return False
