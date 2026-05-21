"""Main decision engine. answer(question, user_id) -> Answer."""
from __future__ import annotations
import re, time, uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import pandas as pd

from core import substrate, ca_api_client, confidence
from core.output_contract import Answer, Citation
import config as cfg


GLOSSARY_GUARD_TERMS = {
    "active customer": "active_customer_definition",
    "active customers": "active_customer_definition",
    "csat": "csat_definition",
    "stockout": "stockout_definition",
    "stockouts": "stockout_definition",
    "days of supply": "days_of_supply_definition",
    "net revenue": "net_revenue_definition",
    "return rate": "return_rate_definition",
    "gross margin": "gross_margin_definition",
    "aov": "aov_definition",
    "average order value": "aov_definition",
    "late delivery": "late_delivery_definition",
    "nps": "nps_definition",
}


class Orchestrator:
    def __init__(self):
        self.s = substrate.get()
        self.ca = ca_api_client.get()

    # ---------- scope ------------------------------------------------------
    def _scope_violation(self, question: str) -> Optional[str]:
        """Return non-agent-ready table name if the question hits one."""
        ql = question.lower()
        for tbl in self.s.non_agent_ready_tables():
            if tbl in ql:
                return tbl
        return None

    # ---------- intent / agent routing ------------------------------------
    def _route_to_agent(self, question: str) -> Optional[Dict[str, Any]]:
        agents = self.s.agents()
        if agents.empty: return None
        published = agents[agents['status'] == 'published']
        if published.empty: return None
        # Dedupe by agent_id (keep newest row) — streaming buffer prevents DB-level dedupe
        published = (published.sort_values('created_at', ascending=False)
                              .drop_duplicates(subset='agent_id', keep='first'))
        ql = question.lower()
        scored = []
        for _, a in published.iterrows():
            score_val = 0
            tbls = a['tables_in_scope']
            tbls = list(tbls) if tbls is not None else []
            for tbl in tbls:
                # crude keyword routing: table name appearing in question
                if tbl.replace('_', ' ') in ql or tbl in ql:
                    score_val += 2
            # domain keywords
            if a['agent_id'].startswith('cymbal_sales') and any(w in ql for w in
                ['revenue','sale','order','customer','product','aov','margin','department']):
                score_val += 1
            if a['agent_id'].startswith('cymbal_cx') and any(w in ql for w in
                ['review','csat','delivery','satisfaction','seller','complaint','rating']):
                score_val += 1
            scored.append((score_val, a))
        scored.sort(key=lambda x: -x[0])
        if scored and scored[0][0] >= 1:
            return scored[0][1].to_dict()
        return None

    # ---------- glossary gap detection ------------------------------------
    def _glossary_gaps(self, question: str) -> List[str]:
        """Detect business terms in the question that have no glossary definition.

        Handles synonyms (plural/singular) via GLOSSARY_GUARD_TERMS mapping
        each surface form to a canonical key. A term is "defined" if ANY
        glossary entry maps to its canonical key — so 'Active Customer' in
        the glossary covers both 'active customer' and 'active customers' in
        the question."""
        ql = question.lower()
        glossary = self.s.glossary()
        defined_keys = set()
        if not glossary.empty:
            for term in glossary['term'].astype(str).str.lower():
                key = GLOSSARY_GUARD_TERMS.get(term)
                if key:
                    defined_keys.add(key)
                # Also: an undefined-in-guard-list term in the glossary just covers itself
                defined_keys.add(term)
        gaps = []
        seen_keys = set()
        for surface, key in GLOSSARY_GUARD_TERMS.items():
            if surface in ql and key not in defined_keys and key not in seen_keys:
                gaps.append(surface)
                seen_keys.add(key)
        return gaps

    # ---------- look up user's personal definition for a term -----------
    def _lookup_user_definition(self, term: str, user_id: str) -> Optional[str]:
        key = GLOSSARY_GUARD_TERMS.get(term.lower())
        if not key: return None
        mem = self.s.memory(user_id=user_id)
        if mem.empty: return None
        hit = mem[mem['key'] == key]
        return hit.iloc[0]['value'] if not hit.empty else None

    # ---------- table guess for freelance --------------------------------
    def _guess_tables(self, question: str) -> List[str]:
        ql = question.lower()
        candidates = self.s.agent_ready_tables()
        ranked = []
        for t in candidates:
            score_val = 0
            t_clean = t.replace('_', ' ')
            if t in ql or t_clean in ql:
                score_val += 5
            for w in t_clean.split():
                if len(w) > 3 and w in ql:
                    score_val += 1
            # domain keyword nudges
            if 'revenue' in ql or 'sale' in ql or 'order' in ql:
                if t in ('order_items','orders','products','users'): score_val += 1
            if 'review' in ql or 'csat' in ql or 'rating' in ql:
                if t == 'customer_reviews': score_val += 2
            if 'delivery' in ql or 'late' in ql:
                if t == 'marketplace_orders': score_val += 2
            if 'inventory' in ql or 'stock' in ql or 'supply' in ql:
                if t in ('inventory_snapshots','inventory_items','supplier_catalog'): score_val += 1
            if 'support' in ql or 'ticket' in ql:
                if t == 'support_tickets': score_val += 2
            if score_val > 0:
                ranked.append((score_val, t))
        ranked.sort(key=lambda x: -x[0])
        return [t for _, t in ranked[:5]] or ['orders','order_items','products','users']

    # ---------- verified query lookup ------------------------------------
    def _verified_match(self, question: str) -> Optional[pd.Series]:
        vq = self.s.verified_queries()
        if vq.empty: return None
        ql = question.lower()
        for _, row in vq.iterrows():
            nl = row['nl_question'].lower()
            common = len(set(nl.split()) & set(ql.split()))
            if common >= 3 or (nl in ql or ql in nl):
                return row
        return None

    # ---------- main entry ------------------------------------------------
    def answer(self, question: str, user_id: str = "demo_user") -> Answer:
        t0 = time.time()

        # Step 0 — scope check
        bad = self._scope_violation(question)
        if bad:
            ans = Answer(
                question=question,
                path_taken="refuse",
                narrative=(f"Table **`{bad}`** is not labeled `agent_ready` and is excluded from Freeform's scope. "
                           f"This is a development/staging table. Ask a data admin to register it for analytics, "
                           f"or rephrase your question to use a production table."),
                tables_used=[bad],
                confidence=0.0,
            )
            self._log(ans, user_id)
            return ans

        # Step 1 — glossary gap → ask the user inline (Change 1)
        # Guard-term ambiguity is louder than any verified-query match:
        # we always ask for the user's definition first if the term has
        # no glossary entry and no personal memory.
        gaps = self._glossary_gaps(question)
        if gaps:
            # If user has a personal memory for this term, fall through and use it
            personal_def = self._lookup_user_definition(gaps[0], user_id)
            if personal_def is None:
                # Don't route to an agent for an undefined business term —
                # the agent doesn't know either.
                term = gaps[0]
                ans = Answer(
                    question=question,
                    path_taken="needs_definition",
                    narrative=(f"I don't know what **{term}** means yet. Can you tell me — what should it be?\n\n"
                               f"_Your definition stays with you. You can choose to share it with your team afterwards._"),
                    confidence=0.0,
                    needs_definition=term,
                )
                self._log(ans, user_id)
                return ans

        # Step 2 — try agent route first
        routed = self._route_to_agent(question)
        if routed:
            ans = self._answer_via_agent(question, routed, user_id, t0)
            self._maybe_suggest_promote(ans, gaps, user_id)
            return ans

        # Step 3 — freelance via Claude
        ans = self._answer_freelance(question, user_id, t0)
        self._maybe_suggest_promote(ans, gaps, user_id)
        return ans

    def _maybe_suggest_promote(self, ans: Answer, gaps: List[str], user_id: str):
        """If we used a user's personal definition for a gap term, offer promotion."""
        for term in gaps:
            key = GLOSSARY_GUARD_TERMS.get(term.lower())
            if not key: continue
            mem = self.s.memory(user_id=user_id)
            if mem.empty: continue
            hit = mem[(mem['key'] == key) & (mem['promoted_to_semantic'] != True)]
            if hit.empty: continue
            # Add a memory citation marking it as promotable
            ans.citations.insert(0, Citation(
                kind="memory",
                label=f"Your definition of {term}",
                detail=hit.iloc[0]['value'],
                extra={"key": key, "promotable": True}))
            ans.suggest_promote_key = key
            return

    # ---------- agent route -----------------------------------------------
    def _answer_via_agent(self, question: str, agent_row: Dict[str, Any],
                          user_id: str, t0: float) -> Answer:
        result = self.ca.chat_with_agent(agent_row['agent_id'], question)
        if result.get("error"):
            # Fall back to freelance with the agent's instruction
            return self._answer_freelance(question, user_id, t0, extra_instruction=agent_row.get('system_instruction',''))
        tables_used = self._tables_from_sql(result.get("sql"))
        cit: List[Citation] = []
        sql_lower = (result.get("sql") or "").lower()
        ql = question.lower()
        # Agent rule — only cite the agent name, brief
        scope_tbls = agent_row.get('tables_in_scope')
        scope_list = list(scope_tbls) if scope_tbls is not None else []
        cover_list = tables_used if tables_used else scope_list[:3]
        cit.append(Citation(kind="agent_rule",
            label=agent_row['name'] + " agent",
            detail=f"Routed to this agent (covers {', '.join(cover_list)}).",
            extra={"agent_id": agent_row['agent_id']}))
        # Cite ONLY glossary terms that appear in the question OR the SQL
        gt = agent_row.get("glossary_terms")
        gt_list = list(gt) if gt is not None else []
        for term_id in gt_list:
            tl = term_id.lower()
            mentioned = (tl in ql) or any(w in sql_lower for w in tl.split())
            if not mentioned: continue
            g = self.s.glossary()
            row = g[g['term'].str.lower() == tl]
            if not row.empty:
                cit.append(Citation(kind="glossary", label=row.iloc[0]['term'],
                    detail=row.iloc[0]['definition']))
        for tbl in tables_used:
            cit.append(Citation(kind="table", label=tbl,
                detail=f"`{cfg.PROJECT_ID}.{cfg.DATASET}.{tbl}`"))
        vq = self._verified_match(question)
        if vq is not None:
            cit.append(Citation(kind="verified_query", label=vq['nl_question'],
                detail=f"Verified by {vq['created_by']}, reused {int(vq.get('usage_count') or 0)} times."))
        rows = result.get("rows") or []
        cols = list(rows[0].keys()) if rows else None
        conf = confidence.score(
            path_taken="agent_route", tables_used=tables_used,
            glossary_terms_used=len([c for c in cit if c.kind=="glossary"]),
            glossary_gaps=0, description_coverage=1.0,
            verified_query_match=(vq is not None),
            memory_used=0, had_error=False)
        ans = Answer(
            question=question, path_taken="agent_route",
            narrative=result.get("narrative","").strip() or "(agent returned no narrative)",
            sql=result.get("sql"), rows=rows, row_count=len(rows), columns=cols,
            confidence=conf, agent_used=agent_row['agent_id'],
            citations=cit, tables_used=tables_used,
            thinking=result.get("thinking"),
            latency_ms=int((time.time()-t0)*1000))
        self._log(ans, user_id)
        return ans

    # ---------- freelance -------------------------------------------------
    def _answer_freelance(self, question: str, user_id: str, t0: float,
                          extra_instruction: str = "") -> Answer:
        tables = self._guess_tables(question)
        schemas = self.s.get_schemas_as_text(tables)
        gl = self.s.glossary()
        glossary_text = ""
        terms_used_count = 0
        if not gl.empty:
            ql = question.lower()
            relevant = gl[gl['term'].str.lower().apply(lambda t: t in ql)]
            terms_used_count = len(relevant)
            glossary_text = "\n".join(f"- {r['term']}: {r['definition']}" for _, r in (relevant if not relevant.empty else gl).iterrows())
        vq_df = self.s.verified_queries()
        vq_match = self._verified_match(question)
        vq_text = ""
        if vq_match is not None:
            vq_text = f"- {vq_match['nl_question']}:\n```sql\n{vq_match['sql_query']}\n```"
        # User memory + cross-user same-key memories
        mem = self.s.memory(user_id=user_id)
        mem_text = ""
        memory_citations: List[Citation] = []
        if not mem.empty:
            for _, m in mem.iterrows():
                if m['key'] and any(part in question.lower() for part in m['key'].lower().split('_')):
                    mem_text += f"- {m['value']}\n"
                    memory_citations.append(Citation(
                        kind="memory", label="Your note",
                        detail=m['value'],
                        extra={"created": str(m['created_at']), "key": m['key']}))
        # Cross-user convergence for relevant keys
        all_mem = self.s.memory()
        convergence_extra: Dict[str, Any] = {}
        if not all_mem.empty:
            for key in all_mem['key'].unique():
                if key and any(p in question.lower() for p in key.lower().split('_')):
                    users_with_same = all_mem[all_mem['key']==key]['user_id'].nunique()
                    if users_with_same >= 3:
                        convergence_extra[key] = users_with_same
        result = self.ca.freelance_with_claude(
            question=question, schemas=schemas, glossary=glossary_text,
            verified_queries=vq_text, memory=mem_text, extra_instruction=extra_instruction,
        )
        if result.get("error"):
            ans = Answer(question=question, path_taken="freelance",
                         narrative=f"Could not generate an answer: {result['error']}",
                         tables_used=tables, error=result['error'],
                         latency_ms=int((time.time()-t0)*1000))
            self._log(ans, user_id)
            return ans
        rows = result.get("rows") or []
        cols = list(rows[0].keys()) if rows else None
        tables_used = self._tables_from_sql(result.get("sql")) or tables
        # description coverage on tables_used
        cov_df = self.s.description_coverage()
        cov_map = dict(zip(cov_df['table_name'], cov_df['coverage_pct']))
        avg_cov = (sum(cov_map.get(t,0) for t in tables_used) / max(1,len(tables_used))) / 100.0
        cit: List[Citation] = []
        cit.extend(memory_citations)
        for key, n in convergence_extra.items():
            cit.append(Citation(kind="memory",
                label=f"👉 {n} people share a correction on this",
                detail=f"Memory key: {key}. Click 'Promote to team' below to send for analyst review.",
                extra={"convergence_count": n, "key": key, "promotable": True}))
        if not gl.empty:
            for _, r in gl[gl['term'].str.lower().apply(lambda t: t in question.lower())].iterrows():
                cit.append(Citation(kind="glossary", label=r['term'], detail=r['definition']))
        for tbl in tables_used:
            cit.append(Citation(kind="table", label=tbl,
                detail=f"`{cfg.PROJECT_ID}.{cfg.DATASET}.{tbl}`"))
        if vq_match is not None:
            cit.append(Citation(kind="verified_query", label=vq_match['nl_question'],
                detail=f"id={vq_match['id']} used_by={vq_match['created_by']}"))
        conf = confidence.score(
            path_taken="freelance", tables_used=tables_used,
            glossary_terms_used=terms_used_count, glossary_gaps=0,
            description_coverage=avg_cov, verified_query_match=(vq_match is not None),
            memory_used=len(memory_citations), had_error=False)
        ans = Answer(
            question=question, path_taken="freelance",
            narrative=result.get("narrative","").strip(),
            sql=result.get("sql"), rows=rows, row_count=len(rows), columns=cols,
            confidence=conf, citations=cit, tables_used=tables_used,
            thinking=result.get("thinking"),
            latency_ms=int((time.time()-t0)*1000))
        self._log(ans, user_id)
        return ans

    # ---------- helpers ---------------------------------------------------
    def _tables_from_sql(self, sql: Optional[str]) -> List[str]:
        if not sql: return []
        pattern = re.compile(r'`?' + re.escape(cfg.PROJECT_ID) + r'`?\.' +
                             re.escape(cfg.DATASET) + r'\.([a-zA-Z_][a-zA-Z0-9_]*)')
        return list(dict.fromkeys(pattern.findall(sql)))

    def _log(self, ans: Answer, user_id: str):
        """Append to _flywheel_query_log via SQL DML (not streaming insert)."""
        try:
            from google.cloud import bigquery as bq2
            sql = f"""
            INSERT INTO {cfg.t('_flywheel_query_log')}
              (query_id, user_id, question_text, generated_sql, tables_referenced,
               path_taken, agent_used, confidence_score, success, error_message,
               thumbs, correction, created_at)
            VALUES (GENERATE_UUID(), @uid, @q, @sql, @tbls, @path, @agent,
                    @conf, @success, @err, NULL, NULL, CURRENT_TIMESTAMP())
            """
            self.s.bq.query(sql, job_config=bq2.QueryJobConfig(query_parameters=[
                bq2.ScalarQueryParameter("uid","STRING",user_id),
                bq2.ScalarQueryParameter("q","STRING",ans.question),
                bq2.ScalarQueryParameter("sql","STRING",ans.sql),
                bq2.ArrayQueryParameter("tbls","STRING",ans.tables_used or []),
                bq2.ScalarQueryParameter("path","STRING",ans.path_taken),
                bq2.ScalarQueryParameter("agent","STRING",ans.agent_used),
                bq2.ScalarQueryParameter("conf","FLOAT64",ans.confidence),
                bq2.ScalarQueryParameter("success","BOOL",
                    ans.error is None and ans.path_taken != "refuse"),
                bq2.ScalarQueryParameter("err","STRING",ans.error),
            ])).result()
        except Exception as e:
            print(f"[log] insert failed: {e}")


_instance: Optional[Orchestrator] = None
def get() -> Orchestrator:
    global _instance
    if _instance is None:
        _instance = Orchestrator()
    return _instance
