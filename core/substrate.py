"""Reads from BQ: dataset metadata, flywheel state, INFORMATION_SCHEMA signals."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
from functools import lru_cache
from typing import List, Dict, Any, Optional
import pandas as pd
from google.cloud import bigquery

import config as cfg


class Substrate:
    def __init__(self):
        self.bq = bigquery.Client(project=cfg.PROJECT_ID, location=cfg.BQ_LOCATION)

    # --- table & label discovery --------------------------------------------
    @lru_cache(maxsize=1)
    def agent_ready_tables(self) -> List[str]:
        sql = f"""
        SELECT table_name FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.TABLE_OPTIONS`
        WHERE option_name = 'labels'
          AND CONTAINS_SUBSTR(option_value, '"agent_ready", "true"')
        ORDER BY table_name
        """
        return [r.table_name for r in self.bq.query(sql).result()]

    @lru_cache(maxsize=1)
    def non_agent_ready_tables(self) -> List[str]:
        sql = f"""
        SELECT table_name FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.TABLE_OPTIONS`
        WHERE option_name = 'labels'
          AND CONTAINS_SUBSTR(option_value, '"agent_ready", "false"')
        ORDER BY table_name
        """
        return [r.table_name for r in self.bq.query(sql).result()]

    def list_tables_with_descriptions(self) -> pd.DataFrame:
        sql = f"""
        SELECT t.table_name,
               opt.option_value AS labels_raw,
               (SELECT option_value FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.TABLE_OPTIONS`
                WHERE table_name = t.table_name AND option_name='description') AS description
        FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.TABLES` t
        LEFT JOIN `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.TABLE_OPTIONS` opt
          ON t.table_name = opt.table_name AND opt.option_name='labels'
        WHERE t.table_type = 'BASE TABLE'
        ORDER BY t.table_name
        """
        return self.bq.query(sql).to_dataframe()

    def get_schemas_as_text(self, tables: List[str]) -> str:
        """Return BQ schemas formatted for the LLM (one table per block)."""
        if not tables: return ""
        in_clause = ",".join(f"'{t}'" for t in tables)
        sql = f"""
        SELECT table_name, column_name, data_type, description
        FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
        WHERE table_name IN ({in_clause})
        ORDER BY table_name, column_name
        """
        rows = list(self.bq.query(sql).result())
        out = []
        for tbl in tables:
            cols = [r for r in rows if r.table_name == tbl]
            if not cols: continue
            lines = [f"TABLE `{cfg.PROJECT_ID}.{cfg.DATASET}.{tbl}`:"]
            for c in cols:
                desc = f"  -- {c.description}" if c.description else ""
                lines.append(f"  {c.column_name} {c.data_type}{desc}")
            out.append("\n".join(lines))
        return "\n\n".join(out)

    def get_column_descriptions(self, table_name: str) -> pd.DataFrame:
        sql = f"""
        SELECT column_name, data_type, description
        FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
        WHERE table_name = @t
        ORDER BY column_name
        """
        job = self.bq.query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("t","STRING",table_name)]))
        return job.to_dataframe()

    # --- flywheel state -----------------------------------------------------
    def glossary(self) -> pd.DataFrame:
        return self.bq.query(f"SELECT * FROM {cfg.t('_flywheel_glossary')} ORDER BY term").to_dataframe()

    def verified_queries(self) -> pd.DataFrame:
        return self.bq.query(f"SELECT * FROM {cfg.t('_flywheel_verified_queries')} ORDER BY id").to_dataframe()

    def agents(self) -> pd.DataFrame:
        return self.bq.query(f"SELECT * FROM {cfg.t('_flywheel_agents')} ORDER BY created_at").to_dataframe()

    def memory(self, user_id: Optional[str] = None) -> pd.DataFrame:
        where = f"WHERE user_id = '{user_id}'" if user_id else ""
        return self.bq.query(
            f"SELECT * FROM {cfg.t('_flywheel_memory')} {where} ORDER BY created_at DESC"
        ).to_dataframe()

    def query_log(self, limit: int = 200) -> pd.DataFrame:
        return self.bq.query(
            f"SELECT * FROM {cfg.t('_flywheel_query_log')} ORDER BY created_at DESC LIMIT {limit}"
        ).to_dataframe()

    def prep_recs(self) -> pd.DataFrame:
        return self.bq.query(
            f"SELECT * FROM {cfg.t('_flywheel_prep_recs')} WHERE status='open' ORDER BY priority_score DESC"
        ).to_dataframe()

    # --- INFORMATION_SCHEMA signals ----------------------------------------
    def table_cooccurrence(self, days: int = 14) -> pd.DataFrame:
        """Pair-count of tables joined together. Includes seeded query log
        so demo has signal without depending on JOBS_BY_PROJECT permissions."""
        sql = f"""
        WITH q AS (
          SELECT tables_referenced FROM {cfg.t('_flywheel_query_log')}
          WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            AND ARRAY_LENGTH(tables_referenced) >= 2
        ),
        pairs AS (
          SELECT t1, t2, COUNT(*) AS co_count
          FROM q, UNNEST(tables_referenced) AS t1, UNNEST(tables_referenced) AS t2
          WHERE t1 < t2
          GROUP BY 1,2
        )
        SELECT * FROM pairs ORDER BY co_count DESC LIMIT 20
        """
        return self.bq.query(sql).to_dataframe()

    def failed_questions(self, days: int = 14) -> pd.DataFrame:
        sql = f"""
        SELECT question_text, error_message, tables_referenced, created_at
        FROM {cfg.t('_flywheel_query_log')}
        WHERE NOT success
          AND created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        ORDER BY created_at DESC LIMIT 50
        """
        return self.bq.query(sql).to_dataframe()

    def refused_for_undefined_terms(self, days: int = 14) -> pd.DataFrame:
        sql = f"""
        SELECT
          REGEXP_EXTRACT(error_message, r"Term '([^']+)' not defined") AS term,
          COUNT(*) AS refusals,
          ARRAY_AGG(DISTINCT question_text LIMIT 3) AS sample_questions
        FROM {cfg.t('_flywheel_query_log')}
        WHERE path_taken='refuse'
          AND error_message LIKE '%not defined in glossary%'
          AND created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        GROUP BY 1 HAVING term IS NOT NULL
        ORDER BY refusals DESC
        """
        return self.bq.query(sql).to_dataframe()

    def table_popularity(self, days: int = 14) -> pd.DataFrame:
        sql = f"""
        SELECT tbl AS table_name, COUNT(*) AS query_count
        FROM {cfg.t('_flywheel_query_log')}, UNNEST(tables_referenced) AS tbl
        WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20
        """
        return self.bq.query(sql).to_dataframe()

    def description_coverage(self) -> pd.DataFrame:
        sql = f"""
        SELECT table_name,
               COUNT(*) AS total_columns,
               COUNTIF(description IS NULL OR description='') AS missing,
               ROUND(100.0 * COUNTIF(description IS NOT NULL AND description <> '') / COUNT(*), 1) AS coverage_pct
        FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
        WHERE NOT STARTS_WITH(table_name, '_flywheel')
        GROUP BY 1 ORDER BY coverage_pct ASC
        """
        return self.bq.query(sql).to_dataframe()

    # --- question-cluster signals (used to propose agents) ------------------
    def uncovered_table_clusters(self, min_count: int = 5) -> pd.DataFrame:
        """Find table-sets that co-appear frequently in queries but aren't yet
        covered by any agent. Filter is done in Python to avoid correlated-subquery
        limitations of BQ."""
        sql = f"""
        SELECT ARRAY_TO_STRING(ARRAY(SELECT DISTINCT x FROM UNNEST(tables_referenced) x ORDER BY x), ',') AS sig,
               COUNT(*) AS n,
               ANY_VALUE(tables_referenced) AS tables
        FROM {cfg.t('_flywheel_query_log')}
        WHERE ARRAY_LENGTH(tables_referenced) BETWEEN 1 AND 4
        GROUP BY 1 HAVING n >= {min_count}
        ORDER BY n DESC
        """
        clusters = self.bq.query(sql).to_dataframe()
        agents = self.agents()
        covered: set = set()
        if not agents.empty and 'tables_in_scope' in agents.columns:
            for scope in agents.loc[agents['status']=='published','tables_in_scope']:
                if scope is not None:
                    covered |= set(scope)
        def is_uncovered(tbls):
            return not (set(list(tbls) if tbls is not None else []) & covered)
        return clusters[clusters['tables'].apply(is_uncovered)].head(10).reset_index(drop=True)


_instance: Optional[Substrate] = None
def get() -> Substrate:
    global _instance
    if _instance is None:
        _instance = Substrate()
    return _instance
