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
        """Update query log + write user memory if correction provided.
        Uses the source question (looked up from query_log) plus the correction
        text to infer the right memory key."""
        # Look up the question text for key inference (best-effort)
        source_question = ""
        try:
            row = next(iter(self.s.bq.query(
                f"SELECT question_text FROM {cfg.t('_flywheel_query_log')} "
                f"WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR) "
                f"AND user_id=@uid ORDER BY created_at DESC LIMIT 1",
                job_config=bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("uid","STRING",user_id)
                ])).result()))
            source_question = row.question_text or ""
        except Exception:
            pass
        sql = f"""
        UPDATE {cfg.t('_flywheel_query_log')}
        SET thumbs=@thumbs, correction=@corr
        WHERE query_id=@qid
        """
        try:
            self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("thumbs","STRING",thumbs),
                bigquery.ScalarQueryParameter("corr","STRING",correction or ""),
                bigquery.ScalarQueryParameter("qid","STRING",query_id),
            ])).result()
        except Exception as e:
            print(f"[record_feedback] query_log update skipped: {str(e)[:100]}")
        if correction:
            key = self._guess_memory_key(f"{source_question} {correction}")
            sql_mem = f"""
            INSERT INTO {cfg.t('_flywheel_memory')}
              (id, user_id, memory_type, key, value, source_question,
               promoted_to_semantic, promotion_requested, promoted_at, created_at)
            VALUES (GENERATE_UUID(), @uid, 'user', @key, @val, @q,
                    FALSE, FALSE, NULL, CURRENT_TIMESTAMP())
            """
            self.s.bq.query(sql_mem, job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("uid","STRING",user_id),
                bigquery.ScalarQueryParameter("key","STRING",key),
                bigquery.ScalarQueryParameter("val","STRING",correction),
                bigquery.ScalarQueryParameter("q","STRING",query_id),
            ])).result()

    def save_user_definition(self, term: str, definition: str, user_id: str, original_question: str):
        """Persist a definition via SQL DML INSERT (NOT streaming insert) so the
        row lands in permanent storage and can be UPDATE'd by promote without
        the 30-min streaming-buffer lockout."""
        from core.orchestrator import GLOSSARY_GUARD_TERMS
        key = GLOSSARY_GUARD_TERMS.get(term.lower(), self._guess_memory_key(definition))
        sql = f"""
        INSERT INTO {cfg.t('_flywheel_memory')}
          (id, user_id, memory_type, key, value, source_question,
           promoted_to_semantic, promotion_requested, promoted_at, created_at)
        VALUES (GENERATE_UUID(), @uid, 'user', @key, @val, @q,
                FALSE, FALSE, NULL, CURRENT_TIMESTAMP())
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("uid","STRING",user_id),
            bigquery.ScalarQueryParameter("key","STRING",key),
            bigquery.ScalarQueryParameter("val","STRING",definition),
            bigquery.ScalarQueryParameter("q","STRING",original_question),
        ])).result()
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
        """Analyst-approved: copy memory into glossary, mark memory as promoted."""
        sql = f"""
        INSERT INTO {cfg.t('_flywheel_glossary')}
          (term, definition, synonyms, linked_table, linked_column, filter_logic, source, created_at)
        VALUES (@term, @def, [], NULL, NULL, NULL, 'promoted_from_memory', CURRENT_TIMESTAMP())
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("term","STRING",term),
            bigquery.ScalarQueryParameter("def","STRING",definition),
        ])).result()
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
        sql = f"""
        INSERT INTO {cfg.t('_flywheel_glossary')}
          (term, definition, synonyms, linked_table, linked_column, filter_logic, source, created_at)
        VALUES (@term, @def, [], @lt, @lc, NULL, @src, CURRENT_TIMESTAMP())
        """
        self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("term","STRING",term),
            bigquery.ScalarQueryParameter("def","STRING",definition),
            bigquery.ScalarQueryParameter("lt","STRING",linked_table),
            bigquery.ScalarQueryParameter("lc","STRING",linked_column),
            bigquery.ScalarQueryParameter("src","STRING",source),
        ])).result()

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
        """Create the agent in CA API + register locally. If the agent already
        exists in CA API with a stale scope, recreate it with the new scope."""
        ok = self.ca.ensure_agent(agent_id, tables_in_scope, system_instruction)
        if not ok:
            # Try delete + recreate to refresh scope
            try:
                self.ca.delete_agent(agent_id)
            except Exception:
                pass
            ok = self.ca.ensure_agent(agent_id, tables_in_scope, system_instruction)
        self.register_agent_locally(agent_id, name, description, tables_in_scope,
                                    glossary_terms, system_instruction,
                                    status="published" if ok else "draft")
        return ok

    # --- domain mapping for proposals --------------------------------------
    DOMAIN_TABLES = {
        "Customer Experience": {"customer_reviews","customer_payments","marketplace_orders",
                                "marketplace_customers","marketplace_sellers"},
        "Supply Chain":        {"inventory_items","inventory_snapshots","distribution_centers",
                                "supplier_catalog"},
        "Voice of Customer":   {"support_tickets","support_ticket_docs","return_claims",
                                "return_evidence_docs"},
        "Sales Analytics":     {"orders","order_items","products","users"},
    }

    def domain_proposals(self, only_session: bool = True, min_questions: int = 2) -> List[Dict[str, Any]]:
        """Detect that N+ questions touched tables from the same domain bundle,
        where that domain doesn't yet have a published agent."""
        from core import session
        if only_session:
            ts = session.start_timestamp().isoformat()
            where = "AND created_at > TIMESTAMP(@start)"
            params = [bigquery.ScalarQueryParameter("start","TIMESTAMP",ts)]
        else:
            where, params = "", []
        sql = f"""
        SELECT t AS tbl, COUNT(DISTINCT question_text) AS n_q
        FROM {cfg.t('_flywheel_query_log')}, UNNEST(tables_referenced) t
        WHERE ARRAY_LENGTH(tables_referenced) >= 1 {where}
        GROUP BY 1
        """
        df = self.s.bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).to_dataframe()
        tbl_count = dict(zip(df['tbl'], df['n_q'])) if not df.empty else {}

        # Which domains already have an agent?
        agents = self.s.agents()
        covered_tables = set()
        if not agents.empty:
            for scope in agents.loc[agents['status']=='published','tables_in_scope']:
                if scope is not None:
                    covered_tables |= set(list(scope))

        proposals = []
        for domain, dom_tables in self.DOMAIN_TABLES.items():
            # Skip if any table in the domain is already covered by an existing agent
            if dom_tables & covered_tables:
                continue
            # Count distinct questions that touched any table in this domain
            n_q = sum(tbl_count.get(t, 0) for t in dom_tables)
            if n_q < min_questions: continue
            # Agent scope = ENTIRE domain bundle, not just observed subset, so
            # follow-up questions on adjacent tables (e.g. customer_payments
            # for a CX agent) are also answerable.
            tables = sorted(dom_tables)
            name, desc, sys_inst, gloss = self._draft_agent(tables)
            proposals.append({
                "suggested_id": self._slugify(name),
                "name": name, "description": desc,
                "tables_in_scope": tables, "glossary_terms": gloss,
                "system_instruction": sys_inst,
                "evidence": f"{n_q} questions touched {domain} tables this session",
                "evidence_count": n_q,
            })
        proposals.sort(key=lambda p: -p['evidence_count'])
        return proposals

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
        """Slug + 4-char version suffix so re-publishing after a delete doesn't
        collide with the tombstoned ID in CA API (which is held for ~30 days)."""
        import re, time
        base = "cymbal_" + re.sub(r'[^a-z0-9]+','_', s.lower()).strip('_') + "_agent"
        # 4-char base36 from current time → changes per minute
        suffix = format(int(time.time()) % 1296000, 'x')[:4]
        return f"{base}_{suffix}"

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
