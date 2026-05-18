"""Flywheel write paths: memory, feedback, glossary, agent ops, prep apply."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import pandas as pd
from google.cloud import bigquery

from core import substrate, ca_api_client
import config as cfg


class Flywheel:
    def __init__(self):
        self.s = substrate.get()
        self.ca = ca_api_client.get()

    # --- feedback / memory --------------------------------------------------
    def record_feedback(self, query_id: str, thumbs: str, correction: Optional[str], user_id: str):
        """Update query log + write user memory if correction provided."""
        sql = f"""
        UPDATE {cfg.t('_flywheel_query_log')}
        SET thumbs=@thumbs, correction=@corr
        WHERE query_id=@qid
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("thumbs","STRING",thumbs),
            bigquery.ScalarQueryParameter("corr","STRING",correction or ""),
            bigquery.ScalarQueryParameter("qid","STRING",query_id),
        ])).result()
        if correction:
            key = self._guess_memory_key(correction)
            row = {
                "id": str(uuid.uuid4()), "user_id": user_id, "memory_type":"user",
                "key": key, "value": correction, "source_question": query_id,
                "promoted_to_semantic": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.s.bq.insert_rows_json(f"{cfg.PROJECT_ID}.{cfg.DATASET}._flywheel_memory", [row])

    def save_user_definition(self, term: str, definition: str, user_id: str, original_question: str):
        """Persist a definition the user gave inline for a missing glossary term."""
        from core.orchestrator import GLOSSARY_GUARD_TERMS
        key = GLOSSARY_GUARD_TERMS.get(term.lower(), self._guess_memory_key(definition))
        row = {
            "id": str(__import__('uuid').uuid4()), "user_id": user_id,
            "memory_type": "user", "key": key, "value": definition,
            "source_question": original_question, "promoted_to_semantic": False,
            "promotion_requested": False, "promoted_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.s.bq.insert_rows_json(f"{cfg.PROJECT_ID}.{cfg.DATASET}._flywheel_memory", [row])
        return key

    def request_memory_promotion(self, memory_key: str, user_id: str):
        """User clicks 'Promote to team'. Flag any of their memories with this key."""
        sql = f"""
        UPDATE {cfg.t('_flywheel_memory')}
        SET promotion_requested=TRUE, promoted_at=CURRENT_TIMESTAMP()
        WHERE user_id=@uid AND key=@k
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("uid","STRING",user_id),
            bigquery.ScalarQueryParameter("k","STRING",memory_key),
        ])).result()

    def list_promotion_requests(self) -> pd.DataFrame:
        sql = f"""
        SELECT key,
               COUNT(*) AS request_count,
               COUNT(DISTINCT user_id) AS distinct_users,
               ANY_VALUE(value) AS sample_value,
               ARRAY_AGG(DISTINCT user_id LIMIT 10) AS users
        FROM {cfg.t('_flywheel_memory')}
        WHERE promotion_requested = TRUE
          AND NOT promoted_to_semantic
        GROUP BY key
        ORDER BY distinct_users DESC, request_count DESC
        """
        return self.s.bq.query(sql).to_dataframe()

    def promote_memory_to_semantic(self, memory_key: str, term: str, definition: str):
        """Analyst-approved: copy memory into glossary, mark memory as promoted,
        and trigger agent update."""
        # 1. Write glossary
        row = {
            "term": term, "definition": definition, "synonyms": [],
            "linked_table": None, "linked_column": None, "filter_logic": None,
            "source": "promoted_from_memory",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.s.bq.insert_rows_json(f"{cfg.PROJECT_ID}.{cfg.DATASET}._flywheel_glossary", [row])
        # 2. Mark memories as promoted
        sql = f"""
        UPDATE {cfg.t('_flywheel_memory')}
        SET promoted_to_semantic=TRUE
        WHERE key=@k
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("k","STRING",memory_key),
        ])).result()
        # 3. Refresh substrate cache
        self.s.glossary.cache_clear() if hasattr(self.s.glossary, "cache_clear") else None

    # --- glossary CRUD ------------------------------------------------------
    def add_glossary_term(self, term: str, definition: str,
                          linked_table: Optional[str] = None,
                          linked_column: Optional[str] = None,
                          source: str = "manual"):
        row = {
            "term": term, "definition": definition, "synonyms": [],
            "linked_table": linked_table, "linked_column": linked_column,
            "filter_logic": None, "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.s.bq.insert_rows_json(f"{cfg.PROJECT_ID}.{cfg.DATASET}._flywheel_glossary", [row])

    # --- agent CRUD ---------------------------------------------------------
    def register_agent_locally(self, agent_id: str, name: str, description: str,
                                tables_in_scope: List[str], glossary_terms: List[str],
                                system_instruction: str, status: str = "published"):
        """Upsert via SQL INSERT (no streaming buffer). Caller is responsible for
        ensuring no prior row with this agent_id exists, or accepting duplicates."""
        sql = f"""
        INSERT INTO {cfg.t('_flywheel_agents')}
          (agent_id, name, description, tables_in_scope, glossary_terms,
           system_instruction, status, ca_api_synced, question_count, created_at)
        VALUES (@agent_id, @name, @description, @tables, @glossary,
                @sys_inst, @status, TRUE, 0, CURRENT_TIMESTAMP())
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("agent_id","STRING",agent_id),
            bigquery.ScalarQueryParameter("name","STRING",name),
            bigquery.ScalarQueryParameter("description","STRING",description),
            bigquery.ArrayQueryParameter("tables","STRING",tables_in_scope),
            bigquery.ArrayQueryParameter("glossary","STRING",glossary_terms),
            bigquery.ScalarQueryParameter("sys_inst","STRING",system_instruction),
            bigquery.ScalarQueryParameter("status","STRING",status),
        ])).result()

    def publish_agent(self, agent_id: str, name: str, description: str,
                      tables_in_scope: List[str], glossary_terms: List[str],
                      system_instruction: str) -> bool:
        """Create the agent in CA API + register locally."""
        ok = self.ca.ensure_agent(agent_id, tables_in_scope, system_instruction)
        self.register_agent_locally(agent_id, name, description, tables_in_scope,
                                    glossary_terms, system_instruction,
                                    status="published" if ok else "draft")
        return ok

    # --- recommendation engine (read-only views into substrate) --------------
    def session_question_count(self) -> int:
        """Count of questions asked since the app session started."""
        from core import session
        sql = f"""
        SELECT COUNT(*) AS n FROM {cfg.t('_flywheel_query_log')}
        WHERE created_at > TIMESTAMP(@start)
        """
        ts = session.start_timestamp().isoformat()
        return int(next(iter(self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("start","TIMESTAMP",ts)])).result())).n)

    def agent_proposals(self, only_session: bool = False, min_count: int = 5) -> List[Dict[str, Any]]:
        """Cluster of uncovered tables with question density >= min_count becomes a proposal.
        If only_session=True, only counts questions from this app-session (so recs appear
        progressively as the user asks)."""
        from core import session
        if only_session:
            ts = session.start_timestamp().isoformat()
            sql = f"""
            SELECT ARRAY_TO_STRING(ARRAY(SELECT DISTINCT x FROM UNNEST(tables_referenced) x ORDER BY x), ',') AS sig,
                   COUNT(*) AS n,
                   ANY_VALUE(tables_referenced) AS tables
            FROM {cfg.t('_flywheel_query_log')}
            WHERE ARRAY_LENGTH(tables_referenced) BETWEEN 1 AND 4
              AND created_at > TIMESTAMP(@start)
            GROUP BY 1 HAVING n >= {min_count}
            ORDER BY n DESC
            """
            clusters = self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("start","TIMESTAMP",ts)])).to_dataframe()
            agents = self.s.agents()
            covered = set()
            if not agents.empty:
                for scope in agents.loc[agents['status']=='published','tables_in_scope']:
                    if scope is not None:
                        covered |= set(list(scope))
            def uncovered(tbls):
                return not (set(list(tbls) if tbls is not None else []) & covered)
            clusters = clusters[clusters['tables'].apply(uncovered)].head(10).reset_index(drop=True)
        else:
            clusters = self.s.uncovered_table_clusters(min_count=min_count)
        proposals = []
        if clusters.empty: return proposals
        for _, c in clusters.iterrows():
            tables = list(c['tables'])
            # Guess domain
            name, desc, sys_inst, gloss = self._draft_agent(tables)
            proposals.append({
                "suggested_id": self._slugify(name),
                "name": name, "description": desc,
                "tables_in_scope": tables, "glossary_terms": gloss,
                "system_instruction": sys_inst,
                "evidence": f"{int(c['n'])} questions hit this table-set in the last 14 days",
                "evidence_count": int(c['n']),
            })
        return proposals

    def graph_edge_proposals(self) -> List[Dict[str, Any]]:
        pairs = self.s.table_cooccurrence(days=14)
        # Existing graph edges (hardcoded for v1)
        existing = {("purchase_edges","Customer-Product"), ("stocking_edges","Product-DC")}
        out = []
        for _, r in pairs.iterrows():
            if r['co_count'] < 4: continue
            out.append({
                "left": r['t1'], "right": r['t2'],
                "co_count": int(r['co_count']),
                "suggested_edge": f"{r['t1']}_{r['t2']}",
            })
        return out[:5]

    def description_prep_recs(self) -> List[Dict[str, Any]]:
        cov = self.s.description_coverage()
        pop = self.s.table_popularity()
        pop_map = dict(zip(pop['table_name'], pop['query_count']))
        recs = []
        for _, c in cov.iterrows():
            if c['coverage_pct'] >= 50 or c['table_name'].startswith('_flywheel'): continue
            q_count = int(pop_map.get(c['table_name'], 0))
            priority = (100 - c['coverage_pct']) * (1 + q_count / 5)
            recs.append({
                "rec_type": "add_description",
                "target_table": c['table_name'],
                "detail": f"{int(c['missing'])} of {int(c['total_columns'])} columns missing descriptions. Used in {q_count} queries.",
                "priority_score": float(round(priority,1)),
                "question_frequency": q_count,
            })
        recs.sort(key=lambda r: -r['priority_score'])
        return recs[:8]

    def glossary_prep_recs(self) -> List[Dict[str, Any]]:
        df = self.s.refused_for_undefined_terms()
        recs = []
        for _, r in df.iterrows():
            recs.append({
                "rec_type": "add_glossary_term",
                "term": r['term'],
                "detail": f"{int(r['refusals'])} questions refused because '{r['term']}' isn't defined. Examples: {', '.join(list(r['sample_questions'])[:2])}",
                "priority_score": float(int(r['refusals']) * 10),
            })
        return recs

    def verified_query_promotions(self) -> List[Dict[str, Any]]:
        """Freelance queries with thumbs_up >= 3 that aren't already verified."""
        sql = f"""
        SELECT question_text, COUNT(*) AS up_votes,
               ANY_VALUE(generated_sql) AS sql,
               ANY_VALUE(tables_referenced) AS tables
        FROM {cfg.t('_flywheel_query_log')}
        WHERE thumbs='up' AND generated_sql IS NOT NULL
        GROUP BY question_text HAVING up_votes >= 3
        ORDER BY up_votes DESC LIMIT 10
        """
        try:
            df = self.s.bq.query(sql).to_dataframe()
            return df.to_dict(orient='records')
        except Exception:
            return []

    # --- prep apply (writes BQ metadata) ------------------------------------
    def apply_description(self, table_name: str, column: Optional[str], description: str):
        if column:
            sql = (f"ALTER TABLE {cfg.t(table_name)} "
                   f"ALTER COLUMN {column} SET OPTIONS (description=@desc)")
        else:
            sql = f"ALTER TABLE {cfg.t(table_name)} SET OPTIONS (description=@desc)"
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("desc","STRING",description),
        ])).result()

    # --- helpers ------------------------------------------------------------
    def _guess_memory_key(self, text: str) -> str:
        t = text.lower()
        if "active" in t and "customer" in t: return "active_customer_definition"
        if "csat" in t: return "csat_definition"
        if "stockout" in t: return "stockout_definition"
        if "days of supply" in t or "dos" in t: return "days_of_supply"
        if "late" in t and "deliver" in t: return "late_delivery_definition"
        if "revenue" in t: return "revenue_definition"
        return "general_correction"

    def _slugify(self, s: str) -> str:
        import re
        return "cymbal_" + re.sub(r'[^a-z0-9]+','_', s.lower()).strip('_') + "_agent"

    def _draft_agent(self, tables: List[str]) -> tuple:
        """Generate a name, description, system instruction, glossary list from
        the table-set. Crude domain detection."""
        t = set(tables)
        if t & {"customer_reviews","marketplace_orders","marketplace_customers",
                "marketplace_sellers","customer_payments"}:
            name = "Customer Experience"
            desc = "Marketplace reviews, CSAT, late delivery and customer satisfaction analysis."
            sys_inst = ("You answer questions about Cymbal Retail customer experience. "
                        "Scores are 1-5 (Satisfied >= 4). Late = order_delivered_customer_date "
                        "> order_estimated_delivery_date. Reviews are in Portuguese — when "
                        "users search comments, search for Portuguese words (e.g., "
                        "'danificado' not 'damaged').")
            gloss = ["CSAT","Late Delivery","NPS Proxy"]
        elif t & {"inventory_snapshots","inventory_items","supplier_catalog",
                  "distribution_centers"}:
            name = "Supply Chain"
            desc = "Inventory, stockout risk, days of supply and supplier reliability."
            sys_inst = ("You answer questions about Cymbal Retail supply chain. "
                        "Use inventory_snapshots for current state. Days of supply = "
                        "qty_on_hand / avg_daily_demand. Stockout = qty_on_hand <= safety_stock.")
            gloss = ["Days of Supply","Stockout","Safety Stock"]
        elif t & {"support_tickets","support_ticket_docs","return_claims",
                  "return_evidence_docs"}:
            name = "Voice of Customer"
            desc = "Support tickets, return claims, unstructured customer evidence."
            sys_inst = ("You answer questions about Cymbal Retail voice-of-customer signals. "
                        "Use ObjectRef columns (doc_ref, evidence_ref, image_ref) for "
                        "unstructured content.")
            gloss = ["Open Ticket Rate","Escalation Rate"]
        else:
            name = "Sales Analytics"
            desc = "Direct ecommerce sales, customer base and product analytics."
            sys_inst = ("You answer questions about Cymbal Retail direct ecommerce. "
                        "Revenue = SUM(sale_price), exclude Cancelled/Returned. "
                        "cost is wholesale. department is Men/Women.")
            gloss = ["Net Revenue","Active Customer","AOV","Return Rate","Gross Margin"]
        return name, desc, sys_inst, gloss


_instance: Optional[Flywheel] = None
def get() -> Flywheel:
    global _instance
    if _instance is None:
        _instance = Flywheel()
    return _instance
