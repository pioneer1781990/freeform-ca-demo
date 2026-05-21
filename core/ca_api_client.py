"""Wraps Conversational Analytics (CA) API + Claude fallback for SQL gen."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
from typing import List, Optional, Dict, Any
import json, re, time
import pandas as pd
from google.cloud import bigquery
import anthropic

import config as cfg

# --- CA SDK import is optional; fall back gracefully -----------------------
try:
    from google.cloud import geminidataanalytics as gda
    HAS_CA_SDK = True
except Exception:
    HAS_CA_SDK = False


class CAClient:
    def __init__(self):
        self.bq = bigquery.Client(project=cfg.PROJECT_ID, location=cfg.BQ_LOCATION)
        self.claude = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY) if cfg.ANTHROPIC_API_KEY else None
        self.agent_svc = gda.DataAgentServiceClient() if HAS_CA_SDK else None
        self.chat_svc  = gda.DataChatServiceClient()  if HAS_CA_SDK else None

    # --- agent lifecycle ----------------------------------------------------
    def ensure_agent(self, agent_id: str, tables: List[str], system_instruction: str) -> bool:
        if not HAS_CA_SDK:
            return False
        try:
            table_refs = []
            for t in tables:
                ref = gda.BigQueryTableReference()
                ref.project_id = cfg.PROJECT_ID
                ref.dataset_id = cfg.DATASET
                ref.table_id   = t
                table_refs.append(ref)

            ds = gda.DatasourceReferences()
            ds.bq = gda.BigQueryTableReferences()
            ds.bq.table_references = table_refs

            ctx = gda.Context()
            ctx.system_instruction = system_instruction
            ctx.datasource_references = ds

            analytics = gda.DataAnalyticsAgent()
            analytics.published_context = ctx
            analytics.staging_context = ctx

            agent = gda.DataAgent()
            agent.data_analytics_agent = analytics
            agent.display_name = agent_id
            agent.description = f"Cymbal Retail agent over {', '.join(tables)}"

            req = gda.CreateDataAgentRequest(
                parent=f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}",
                data_agent_id=agent_id,
                data_agent=agent,
            )
            self.agent_svc.create_data_agent(request=req)
            return True
        except Exception as e:
            if "ALREADY_EXISTS" in str(e) or "already exists" in str(e).lower():
                return True
            print(f"[ca_api] create_agent({agent_id}) failed: {e}")
            return False

    def update_agent_instruction(self, agent_id: str, system_instruction: str) -> bool:
        if not HAS_CA_SDK:
            return False
        try:
            name = f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}/dataAgents/{agent_id}"
            existing = self.agent_svc.get_data_agent(name=name)
            existing.data_analytics_agent.published_context.system_instruction = system_instruction
            existing.data_analytics_agent.staging_context.system_instruction = system_instruction
            req = gda.UpdateDataAgentRequest(data_agent=existing)
            self.agent_svc.update_data_agent(request=req)
            return True
        except Exception as e:
            print(f"[ca_api] update_instruction failed: {e}")
            return False

    def list_agents(self) -> List[str]:
        if not HAS_CA_SDK:
            return []
        try:
            parent = f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}"
            return [a.name.split('/')[-1] for a in self.agent_svc.list_data_agents(parent=parent)]
        except Exception:
            return []

    def delete_agent(self, agent_id: str) -> bool:
        if not HAS_CA_SDK:
            return False
        try:
            name = f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}/dataAgents/{agent_id}"
            self.agent_svc.delete_data_agent(name=name)
            return True
        except Exception as e:
            print(f"[ca_api] delete_agent({agent_id}) failed: {e}")
            return False

    # --- chat ---------------------------------------------------------------
    def chat_with_agent(self, agent_id: str, question: str) -> Dict[str, Any]:
        """Send a question to a published agent. Returns dict with sql, narrative, rows."""
        if not HAS_CA_SDK:
            return {"error": "CA SDK not installed", "narrative": "", "sql": None, "rows": None}
        try:
            agent_ctx = gda.DataAgentContext()
            agent_ctx.data_agent = (
                f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}/dataAgents/{agent_id}")

            msg = gda.Message()
            msg.user_message = gda.UserMessage(text=question)

            req = gda.ChatRequest(
                parent=f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}",
                messages=[msg],
                data_agent_context=agent_ctx,
                thinking_mode=gda.ChatRequest.ThinkingMode.FAST if hasattr(gda.ChatRequest,'ThinkingMode') else 1,
            )
            sql_text, all_text_events = None, []
            for resp in self.chat_svc.chat(request=req):
                sys_msg = resp.system_message
                if sys_msg.text and sys_msg.text.parts:
                    all_text_events.append("\n".join(sys_msg.text.parts).strip())
                if sys_msg.data and sys_msg.data.generated_sql:
                    sql_text = sys_msg.data.generated_sql
            # Heuristic: the LAST text event (after data has been produced) is the
            # final narrative. Earlier ones are progress / thinking.
            narrative = all_text_events[-1] if all_text_events else ""
            thinking  = "\n\n".join(all_text_events[:-1]) if len(all_text_events) > 1 else None
            rows = self._execute_if_sql(sql_text) if sql_text else None
            return {"narrative": narrative, "sql": sql_text, "rows": rows, "thinking": thinking}
        except Exception as e:
            return {"error": str(e), "narrative": "", "sql": None, "rows": None}

    # --- freelance via Claude (no agent) ------------------------------------
    def freelance_with_claude(self, question: str, schemas: str, glossary: str,
                              verified_queries: str, memory: str,
                              extra_instruction: str = "") -> Dict[str, Any]:
        if not self.claude:
            return {"error": "ANTHROPIC_API_KEY not set", "narrative": "", "sql": None, "rows": None}
        sys_prompt = f"""You are a data analyst answering questions on Cymbal Retail's BigQuery dataset `{cfg.PROJECT_ID}.{cfg.DATASET}`.

You MUST:
- Generate one valid BigQuery Standard SQL query that answers the question.
- Fully-qualify all table names as `{cfg.PROJECT_ID}.{cfg.DATASET}.<table>`.
- For TIMESTAMP columns (orders.created_at, order_items.created_at, support_tickets.created_at, etc.), ALWAYS use TIMESTAMP_TRUNC and TIMESTAMP_SUB — NEVER DATE_TRUNC or DATE_SUB, anywhere in the query (not in SELECT, not in WHERE, not in GROUP BY). Comparing or truncating TIMESTAMP with DATE functions fails in BigQuery.
  Example SELECT: SELECT TIMESTAMP_TRUNC(created_at, MONTH) AS month, SUM(sale_price) FROM ... GROUP BY 1
  Example WHERE: WHERE created_at >= TIMESTAMP_TRUNC(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), DAY)
- Every non-aggregated column in SELECT must appear in GROUP BY. If you compute COUNTIF/SUM/AVG, do NOT also SELECT the raw column unless you're grouping by it. For a simple ratio like CSAT, write:
    SELECT ROUND(COUNTIF(review_score >= 4) / COUNT(*) * 100, 2) AS csat_pct
    FROM `{cfg.PROJECT_ID}.{cfg.DATASET}.customer_reviews`
  — no GROUP BY needed.
- TIMESTAMP_ADD / TIMESTAMP_SUB only support sub-day intervals (MICROSECOND..DAY). For MONTH/QUARTER/YEAR offsets, use DATE_ADD/DATE_SUB on a DATE expression, or use DATETIME_ADD/DATETIME_SUB on a DATETIME, then CAST back. Simplest pattern for "this month so far":
    WHERE review_creation_date >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH)
  No upper bound needed — CURRENT_TIMESTAMP() handles it.
- If the narrative gives a specific number, that number MUST come from the SQL result. NEVER invent or estimate a number in the narrative — write narrative AFTER seeing what columns the SQL returns, in terms of those columns (e.g. "CSAT for this month is shown in the csat_pct column").
- Be honest about ambiguity: if a key term ("revenue", "active", "stockout") is not defined in the glossary, hedge in the narrative and lean on table descriptions or your own definition with explicit caveat.
- If the question cannot be answered without an undefined business term, return SQL=null and explain.

TABLE SCHEMAS:
{schemas}

GLOSSARY:
{glossary if glossary.strip() else '(empty — no terms defined yet)'}

VERIFIED QUERIES (templates you can adapt when relevant):
{verified_queries if verified_queries.strip() else '(none)'}

USER MEMORY (apply if relevant):
{memory if memory.strip() else '(none)'}

{extra_instruction}

Return JSON with keys: narrative (string), sql (string or null), thinking (1-2 short sentences on what you did)."""
        try:
            resp = self.claude.messages.create(
                model=cfg.CLAUDE_MODEL,
                max_tokens=1500,
                system=sys_prompt,
                messages=[{"role": "user", "content": question}],
            )
            text = resp.content[0].text
            payload = self._extract_json(text)
            sql_text = payload.get("sql")
            rows, final_sql = (None, sql_text)
            if sql_text:
                rows, final_sql = self._execute_with_retry(
                    sql_text, schemas=schemas, glossary=glossary,
                    verified_queries=verified_queries, memory=memory,
                    question=question, extra_instruction=extra_instruction)
            narrative = payload.get("narrative","")
            if sql_text and rows is None:
                narrative = ("I tried to compute this but my generated SQL didn't run successfully. "
                             "An analyst can fix the query in the Studio. The intent was: " + (narrative or ""))
            return {"narrative": narrative, "sql": final_sql,
                    "rows": rows, "thinking": payload.get("thinking")}
        except Exception as e:
            return {"error": str(e), "narrative": "", "sql": None, "rows": None}

    # --- helpers ------------------------------------------------------------
    def _execute_if_sql(self, sql: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        if not sql: return None
        try:
            df = self.bq.query(sql, location=cfg.BQ_LOCATION).to_dataframe()
            return df.head(200).to_dict(orient="records")
        except Exception as e:
            print(f"[ca_api] sql exec failed: {e}\nSQL was:\n{sql}")
            return None

    def _execute_with_retry(self, sql: Optional[str], *, schemas: str, glossary: str,
                            verified_queries: str, memory: str, question: str,
                            extra_instruction: str = "", max_retries: int = 1):
        """Execute SQL; on failure, ask Claude to fix it once with the error."""
        if not sql: return None, None
        try:
            df = self.bq.query(sql, location=cfg.BQ_LOCATION).to_dataframe()
            return df.head(200).to_dict(orient="records"), sql
        except Exception as e:
            err = str(e).splitlines()[0][:200]
            print(f"[ca_api] sql failed, retrying once: {err}")
        if not self.claude or max_retries <= 0:
            return None, sql
        # Retry: feed error back to Claude
        retry_sys = f"""Previous SQL you wrote failed. Fix it.

PREVIOUS SQL:
{sql}

ERROR:
{err}

TABLE SCHEMAS:
{schemas}

GLOSSARY:
{glossary}

USER MEMORY:
{memory}

{extra_instruction}

Return JSON with keys: narrative (string describing what you computed), sql (fixed SQL string), thinking (1 sentence)."""
        try:
            resp = self.claude.messages.create(
                model=cfg.CLAUDE_MODEL, max_tokens=1200,
                system=retry_sys,
                messages=[{"role":"user","content":question}],
            )
            payload = self._extract_json(resp.content[0].text)
            fixed_sql = payload.get("sql")
            if fixed_sql:
                try:
                    df = self.bq.query(fixed_sql, location=cfg.BQ_LOCATION).to_dataframe()
                    return df.head(200).to_dict(orient="records"), fixed_sql
                except Exception as e2:
                    print(f"[ca_api] retry also failed: {e2}")
        except Exception as e:
            print(f"[ca_api] retry call failed: {e}")
        return None, sql

    def _extract_json(self, text: str) -> Dict[str, Any]:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m: return {"narrative": text, "sql": None}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {"narrative": text, "sql": None}


_instance: Optional[CAClient] = None
def get() -> CAClient:
    global _instance
    if _instance is None:
        _instance = CAClient()
    return _instance
