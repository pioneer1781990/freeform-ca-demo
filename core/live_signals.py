"""Live signals derived from _flywheel_query_log (proxy for INFORMATION_SCHEMA.JOBS)
plus dataset metadata. Powers the Studio "Live signals" panel that renders at
startup, before any user has asked a question.

All functions are best-effort: on BQ failure we log a warning and return [].
All reads are SQL DML only (no streaming inserts; nothing here mutates state).
"""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
from typing import List, Dict, Any
import logging

from google.cloud import bigquery

import config as cfg
from core import substrate

log = logging.getLogger(__name__)


def _bq() -> bigquery.Client:
    return substrate.get().bq


# ---------------------------------------------------------------------------
# 1. Top tables by usage
# ---------------------------------------------------------------------------
def top_tables_by_usage(days: int = 14) -> List[Dict[str, Any]]:
    """Top 5 tables by query_count over the last `days` days, with unique users."""
    sql = f"""
    SELECT
      tbl AS table_name,
      COUNT(*) AS query_count,
      COUNT(DISTINCT user_id) AS unique_users
    FROM {cfg.t('_flywheel_query_log')}, UNNEST(tables_referenced) AS tbl
    WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND tbl IS NOT NULL
    GROUP BY tbl
    ORDER BY query_count DESC
    LIMIT 5
    """
    try:
        job = _bq().query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)]
        ))
        return [
            {"table": r["table_name"],
             "query_count": int(r["query_count"]),
             "unique_users": int(r["unique_users"])}
            for r in job.result()
        ]
    except Exception as e:
        log.warning("top_tables_by_usage failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# 2. Top table co-occurrence pairs
# ---------------------------------------------------------------------------
def top_table_pairs(days: int = 14) -> List[Dict[str, Any]]:
    """Top 5 pairs of tables that co-occur in the same analyst query."""
    sql = f"""
    WITH q AS (
      SELECT tables_referenced
      FROM {cfg.t('_flywheel_query_log')}
      WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        AND ARRAY_LENGTH(tables_referenced) >= 2
    )
    SELECT t1 AS left_table, t2 AS right_table, COUNT(*) AS co_count
    FROM q,
         UNNEST(tables_referenced) AS t1,
         UNNEST(tables_referenced) AS t2
    WHERE t1 < t2
    GROUP BY t1, t2
    ORDER BY co_count DESC
    LIMIT 5
    """
    try:
        job = _bq().query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)]
        ))
        return [
            {"left": r["left_table"],
             "right": r["right_table"],
             "co_count": int(r["co_count"])}
            for r in job.result()
        ]
    except Exception as e:
        log.warning("top_table_pairs failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# 3. Undefined-term refusals
# ---------------------------------------------------------------------------
def undefined_term_refusals() -> List[Dict[str, Any]]:
    """Mine refusals where the orchestrator rejected a question because a term
    wasn't in the glossary. Returns rows with the term, refusal count, and up
    to 3 sample questions."""
    sql = f"""
    WITH refused AS (
      SELECT
        COALESCE(
          REGEXP_EXTRACT(error_message, r"Term '([^']+)' not defined"),
          REGEXP_EXTRACT(error_message, r"'([^']+)' is not defined"),
          REGEXP_EXTRACT(error_message, r"([A-Za-z_][A-Za-z0-9_ -]*) is not defined")
        ) AS term,
        question_text
      FROM {cfg.t('_flywheel_query_log')}
      WHERE path_taken = 'refuse'
        AND error_message IS NOT NULL
        AND LOWER(error_message) LIKE '%not defined%'
    )
    SELECT
      term,
      COUNT(*) AS refusals,
      ARRAY_AGG(DISTINCT question_text IGNORE NULLS LIMIT 3) AS samples
    FROM refused
    WHERE term IS NOT NULL AND term <> ''
    GROUP BY term
    ORDER BY refusals DESC
    LIMIT 10
    """
    try:
        job = _bq().query(sql)
        return [
            {"term": r["term"],
             "refusals": int(r["refusals"]),
             "samples": list(r["samples"]) if r["samples"] is not None else []}
            for r in job.result()
        ]
    except Exception as e:
        log.warning("undefined_term_refusals failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# 4. Recent failed queries
# ---------------------------------------------------------------------------
def recent_failed_queries(limit: int = 5) -> List[Dict[str, Any]]:
    """Most recent unsuccessful analyst queries from the log."""
    sql = f"""
    SELECT
      question_text,
      error_message,
      tables_referenced,
      created_at
    FROM {cfg.t('_flywheel_query_log')}
    WHERE (NOT success OR path_taken IN ('refuse', 'error'))
      AND question_text IS NOT NULL
    ORDER BY created_at DESC
    LIMIT @lim
    """
    try:
        job = _bq().query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("lim", "INT64", limit)]
        ))
        out: List[Dict[str, Any]] = []
        for r in job.result():
            tbls = r["tables_referenced"]
            out.append({
                "question": r["question_text"],
                "error": r["error_message"] or "",
                "tables": list(tbls) if tbls is not None else [],
                "when": r["created_at"].isoformat() if r["created_at"] is not None else None,
            })
        return out
    except Exception as e:
        log.warning("recent_failed_queries failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# 5. Initial recommendations (derived from above signals)
# ---------------------------------------------------------------------------
def _description_coverage_by_table() -> Dict[str, float]:
    """Map of table_name -> coverage_pct (0..100). Best-effort."""
    sql = f"""
    SELECT
      table_name,
      ROUND(100.0 * COUNTIF(description IS NOT NULL AND description <> '') / COUNT(*), 1) AS coverage_pct
    FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
    WHERE NOT STARTS_WITH(table_name, '_flywheel')
    GROUP BY table_name
    """
    try:
        return {r["table_name"]: float(r["coverage_pct"] or 0.0)
                for r in _bq().query(sql).result()}
    except Exception as e:
        log.warning("_description_coverage_by_table failed: %s", e)
        return {}


def initial_recommendations() -> List[Dict[str, Any]]:
    """3-4 startup recommendations the Studio panel can render before the user
    has asked anything. Same shape as `studio_recommendations` entries in
    `core/answer_cache.py`.

    Derived purely from the live signals above — these are gaps the system has
    already noticed (refused undefined terms, popular tables with weak metadata,
    repeatedly joined table pairs).
    """
    recs: List[Dict[str, Any]] = []

    # (a) Undefined-term refusals -> define_glossary_term
    try:
        for row in undefined_term_refusals():
            term = row["term"]
            refusals = row["refusals"]
            samples = row.get("samples") or []
            sample_str = samples[0] if samples else ""
            recs.append({
                "kind": "define_glossary_term",
                "term": term,
                "title": f"Define glossary term: '{term}' ({refusals} historical refusal{'s' if refusals != 1 else ''})",
                "evidence": (
                    f"Analysts have been refused {refusals} time(s) because '{term}' is not in the glossary."
                    + (f" e.g. \"{sample_str}\"" if sample_str else "")
                ),
                "draft_definition": "",
            })
            if len(recs) >= 2:
                break
    except Exception as e:
        log.warning("initial_recommendations(define_glossary_term) failed: %s", e)

    # (b) Popular table with weak description coverage -> add_description (NEW kind)
    try:
        coverage = _description_coverage_by_table()
        for row in top_tables_by_usage():
            tbl = row["table"]
            qc = row["query_count"]
            cov = coverage.get(tbl)
            if cov is not None and cov < 50.0:
                recs.append({
                    "kind": "add_description",
                    "target_table": tbl,
                    "title": f"Add descriptions to {tbl} (queried {qc}x but has {cov:.0f}% column coverage)",
                    "evidence": (
                        f"{tbl} appears in {qc} analyst queries over the last 14 days "
                        f"but only {cov:.0f}% of its columns have descriptions. "
                        f"Filling these gaps would improve agent grounding."
                    ),
                    "coverage_pct": cov,
                    "query_count": qc,
                })
                break
    except Exception as e:
        log.warning("initial_recommendations(add_description) failed: %s", e)

    # (c) Top table-pair -> add_graph_edge
    try:
        pairs = top_table_pairs()
        if pairs:
            top = pairs[0]
            left, right, co = top["left"], top["right"], top["co_count"]
            recs.append({
                "kind": "add_graph_edge",
                "title": f"Promote graph edge: {left} <-> {right} (joined {co}x this week)",
                "evidence": (
                    f"{left} and {right} co-occur in {co} analyst queries over the last 14 days. "
                    f"Adding this edge to the property graph would let the agent answer "
                    f"join questions across these tables in a single traversal."
                ),
                "edges": [f"{left} <-> {right}"],
                "co_count": co,
            })
    except Exception as e:
        log.warning("initial_recommendations(add_graph_edge) failed: %s", e)

    # (d) Recent failures cluster -> if we still have fewer than 3, surface a
    # promote_verified_queries hint on the most-failed table.
    if len(recs) < 3:
        try:
            fails = recent_failed_queries(limit=10)
            tbl_freq: Dict[str, int] = {}
            for f in fails:
                for t in f.get("tables") or []:
                    tbl_freq[t] = tbl_freq.get(t, 0) + 1
            if tbl_freq:
                top_tbl, n = max(tbl_freq.items(), key=lambda kv: kv[1])
                recs.append({
                    "kind": "promote_verified_queries",
                    "title": f"Investigate repeated failures on {top_tbl} ({n} recent)",
                    "evidence": (
                        f"{n} of the most recent failed/refused queries touch {top_tbl}. "
                        f"A verified query template here would close the gap."
                    ),
                    "target_table": top_tbl,
                    "fail_count": n,
                })
        except Exception as e:
            log.warning("initial_recommendations(promote_verified_queries) failed: %s", e)

    return recs[:4]
