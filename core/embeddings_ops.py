"""Vector embeddings ops for customer reviews.

Creates a BQ remote text-embedding model, generates embeddings for review
comments, stores them (denormalized with the review text) in
`cymbal_retail.review_embeddings`, optionally builds a vector index, and
exposes a `vector_search_reviews` helper for semantic search.

All operations are best-effort: if a required permission or feature is
missing we log and return safely instead of crashing the Streamlit app.
Artifacts created here are tracked in `cymbal_retail._demo_provenance`
so a demo reset can drop them cleanly.
"""
from __future__ import annotations

import logging
import warnings
from typing import List, Dict, Any

warnings.filterwarnings("ignore")

from google.cloud import bigquery
from google.api_core import exceptions as gax_exceptions

import config as cfg

log = logging.getLogger(__name__)

# --- artifact names ---------------------------------------------------------
EMBED_MODEL_NAME   = "gemini_text_embed"
EMBED_TABLE_NAME   = "review_embeddings"
EMBED_INDEX_NAME   = "review_embeddings_idx"
PROVENANCE_TABLE   = "_demo_provenance"

# Endpoints to try in order. text-embedding-005 is the GA model; the large
# experimental one is a fallback if 005 is unavailable in this project.
EMBED_ENDPOINTS = ["text-embedding-005", "text-embedding-large-exp-03-07"]

# Cap rows for demo speed.
MAX_REVIEW_ROWS = 500


def _client() -> bigquery.Client:
    return bigquery.Client(project=cfg.PROJECT_ID, location=cfg.BQ_LOCATION)


def _ensure_provenance_table(bq: bigquery.Client) -> None:
    """Lazily create the small provenance table used to track demo artifacts.

    NOTE: shared schema across all demo provenance writers — columns are
    (kind, identifier, created_at). Earlier this module used (artifact_kind,
    artifact_name, ...) — now aligned with the canonical schema.
    """
    sql = f"""
    CREATE TABLE IF NOT EXISTS {cfg.t(PROVENANCE_TABLE)} (
      kind STRING NOT NULL,
      identifier STRING NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
    )
    """
    try:
        bq.query(sql).result()
    except Exception as e:
        log.warning("Could not ensure provenance table: %s", e)


def _record_provenance(bq: bigquery.Client, kind: str, name: str) -> None:
    try:
        sql = f"""
        INSERT INTO {cfg.t(PROVENANCE_TABLE)} (kind, identifier, created_at)
        VALUES (@kind, @name, CURRENT_TIMESTAMP())
        """
        bq.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("kind", "STRING", kind),
                    bigquery.ScalarQueryParameter("name", "STRING", name),
                ]
            ),
        ).result()
    except Exception as e:
        log.warning("Could not record provenance for %s/%s: %s", kind, name, e)


def _create_embedding_model(bq: bigquery.Client) -> str | None:
    """Try each candidate endpoint until one creates successfully. Returns
    the endpoint that worked, or None."""
    for endpoint in EMBED_ENDPOINTS:
        sql = f"""
        CREATE OR REPLACE MODEL {cfg.t(EMBED_MODEL_NAME)}
        REMOTE WITH CONNECTION `{cfg.CONNECTION_ID}`
        OPTIONS (ENDPOINT = '{endpoint}')
        """
        try:
            bq.query(sql).result()
            log.info("Created embedding model with endpoint=%s", endpoint)
            _record_provenance(bq, "model", EMBED_MODEL_NAME)
            return endpoint
        except Exception as e:
            log.warning("Endpoint %s failed: %s", endpoint, e)
            continue
    return None


def create_review_embeddings() -> bool:
    """Create the embedding model, generate embeddings for up to
    MAX_REVIEW_ROWS customer reviews, and store them denormalized in
    `cymbal_retail.review_embeddings`.

    Returns True on success, False on any failure (no exception raised).
    """
    try:
        bq = _client()
    except Exception as e:
        log.error("Could not init BQ client: %s", e)
        return False

    _ensure_provenance_table(bq)

    endpoint = _create_embedding_model(bq)
    if endpoint is None:
        log.error("No text-embedding endpoint succeeded; aborting.")
        return False

    # Build the embeddings table denormalized with review text so vector
    # search can return everything without an extra join.
    build_sql = f"""
    CREATE OR REPLACE TABLE {cfg.t(EMBED_TABLE_NAME)} AS
    SELECT
      review_id,
      content AS review_comment_message,
      ml_generate_embedding_result AS embedding
    FROM ML.GENERATE_EMBEDDING(
      MODEL {cfg.t(EMBED_MODEL_NAME)},
      (
        SELECT
          review_id,
          review_comment_message AS content
        FROM {cfg.t('customer_reviews')}
        WHERE review_comment_message IS NOT NULL
          AND LENGTH(TRIM(review_comment_message)) > 0
        LIMIT {MAX_REVIEW_ROWS}
      ),
      STRUCT(TRUE AS flatten_json_output)
    )
    WHERE ARRAY_LENGTH(ml_generate_embedding_result) > 0
    """
    try:
        job = bq.query(build_sql)
        job.result(timeout=120)  # generous; ML.GENERATE can be slow
    except gax_exceptions.GoogleAPIError as e:
        log.error("ML.GENERATE_EMBEDDING failed: %s", e)
        return False
    except Exception as e:
        log.error("Unexpected error building embeddings: %s", e)
        return False

    _record_provenance(bq, "table", EMBED_TABLE_NAME)

    # Best-effort vector index. Small tables may refuse — that's fine,
    # VECTOR_SEARCH still works via brute force.
    idx_sql = f"""
    CREATE OR REPLACE VECTOR INDEX {EMBED_INDEX_NAME}
    ON {cfg.t(EMBED_TABLE_NAME)}(embedding)
    OPTIONS (distance_type='COSINE', index_type='IVF')
    """
    try:
        bq.query(idx_sql).result(timeout=60)
        _record_provenance(bq, "index", EMBED_INDEX_NAME)
        log.info("Created vector index %s", EMBED_INDEX_NAME)
    except Exception as e:
        log.info("Vector index skipped (often expected for small tables): %s", e)

    return True


def vector_search_reviews(query_text: str, k: int = 50) -> List[Dict[str, Any]]:
    """Embed `query_text` and return the top-k semantically similar reviews.

    Each result dict contains: review_id, review_comment_message, distance.
    Returns [] on any failure.
    """
    if not query_text or not query_text.strip():
        return []

    try:
        bq = _client()
    except Exception as e:
        log.error("Could not init BQ client: %s", e)
        return []

    sql = f"""
    SELECT
      base.review_id            AS review_id,
      base.review_comment_message AS review_comment_message,
      distance                  AS distance
    FROM VECTOR_SEARCH(
      TABLE {cfg.t(EMBED_TABLE_NAME)}, 'embedding',
      (
        SELECT ml_generate_embedding_result AS embedding
        FROM ML.GENERATE_EMBEDDING(
          MODEL {cfg.t(EMBED_MODEL_NAME)},
          (SELECT @query_text AS content),
          STRUCT(TRUE AS flatten_json_output)
        )
      ),
      top_k => @k,
      options => '{{"fraction_lists_to_search": 1.0}}'
    )
    ORDER BY distance ASC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("query_text", "STRING", query_text),
            bigquery.ScalarQueryParameter("k", "INT64", int(k)),
        ]
    )

    try:
        rows = list(bq.query(sql, job_config=job_config).result(timeout=60))
    except gax_exceptions.GoogleAPIError as e:
        # Retry without the options arg — required only when an index exists.
        log.warning("VECTOR_SEARCH with options failed (%s); retrying without.", e)
        sql_noopt = sql.replace(
            ",\n      options => '{\"fraction_lists_to_search\": 1.0}'", ""
        )
        try:
            rows = list(bq.query(sql_noopt, job_config=job_config).result(timeout=60))
        except Exception as e2:
            log.error("VECTOR_SEARCH failed: %s", e2)
            return []
    except Exception as e:
        log.error("Unexpected error in VECTOR_SEARCH: %s", e)
        return []

    return [
        {
            "review_id": r["review_id"],
            "review_comment_message": r["review_comment_message"],
            "distance": float(r["distance"]) if r["distance"] is not None else None,
        }
        for r in rows
    ]
