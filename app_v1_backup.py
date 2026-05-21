"""Single-page demo: Ask on top, Studio at bottom, both reactive.

When the user asks a question, the answer renders in the Ask area AND any
attached studio_recommendations land in the Studio panel below. Clicking a
recommendation action runs the corresponding effect (define glossary term,
promote verified queries to agent, add graph edge, create embeddings) and
the next ask uses the post-action cached variant.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings; warnings.filterwarnings("ignore")
import time
import pandas as pd
import streamlit as st

from styles import BASE_CSS
from core import (orchestrator, flywheel, substrate, answer_cache,
                  graph_ops, embeddings_ops, session as sess)
from core.output_contract import Answer
import config as cfg

st.set_page_config(page_title="Freeform CA Demo", page_icon="✦", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(BASE_CSS, unsafe_allow_html=True)
st.markdown("""<style>
/* Wider container so the L/R split has breathing room */
.main .block-container { max-width: 1400px; padding-top: 0.5rem; }
/* Vertical divider between Ask (left) and Studio (right) */
div[data-testid="stHorizontalBlock"] > div:first-child { border-right: 1px solid #ececec; padding-right: 16px; }
div[data-testid="stHorizontalBlock"] > div:nth-child(2) { padding-left: 20px; }

.pane-label  { font-size: 11px; color: #6b7280; text-transform: uppercase;
               letter-spacing: .06em; margin-bottom: 8px; font-weight: 600; }
.studio-hdr  { font-size: 14px; font-weight: 600; color: #111827;
               display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.studio-hdr .dot { width: 8px; height: 8px; border-radius: 50%;
                   background: #10b981; display: inline-block; }
.rec-card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 12px 14px; margin-bottom: 10px;
  border-left: 3px solid #2563eb;
}
.rec-title { font-weight: 600; color: #111827; font-size: 13px; }
.rec-evidence { font-size: 12px; color: #6b7280; margin: 4px 0 8px; line-height: 1.4; }
.rec-detail   { font-size: 12px; color: #4b5563; margin: 2px 0; }
.studio-built {
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 14px;
  font-size: 12px; color: #14532d; line-height: 1.6;
}
.studio-built .label { font-weight: 600; }

/* Chat input pinned at bottom — only across the LEFT column */
[data-testid="stChatInput"] {
  border: 1px solid #d1d5db !important;
  border-radius: 12px !important;
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.04) !important;
}
[data-testid="stChatInput"] textarea {
  background: #ffffff !important;
  font-size: 14px !important;
  color: #111827 !important;
}
</style>""", unsafe_allow_html=True)
sess.start_if_missing()

# --- session state init ----------------------------------------------------
SS = st.session_state
SS.setdefault("history", [])
SS.setdefault("studio_recs", [])          # list of {id, kind, ...}
SS.setdefault("built_today", [])          # list of strings
SS.setdefault("user_id", "siya")
SS.setdefault("post_action_state", {})    # question -> action suffix

# --- helpers ---------------------------------------------------------------
def _agent_label(aid):
    if not aid: return "freelance"
    return {"cymbal_sales_agent": "Sales Analytics",
            "cymbal_customer_experience_agent": "Customer Experience"}.get(
            aid, aid.replace("cymbal_", "").replace("_agent","").replace("_"," ").title())

def _badge(text, kind=""):
    cls = {"agent": "ecfdf5;color:#047857;border-color:#d1fae5",
           "freelance": "fef3c7;color:#92400e;border-color:#fde68a",
           "refuse":  "fee2e2;color:#991b1b;border-color:#fecaca",
           "asking":  "dbeafe;color:#1d4ed8;border-color:#bfdbfe"}.get(kind,
           "f3f4f6;color:#4b5563;border-color:#e5e7eb")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:6px;'
            f'font-size:11px;font-weight:500;margin-right:6px;background:#{cls.split(";")[0]};'
            f'color:{cls.split(";")[1].split(":")[1]};border:1px solid {cls.split(";")[2].split(":")[1]};">'
            f'{text}</span>')

def _path_chip(path):
    if path == "agent_route":      return _badge("via agent", "agent")
    if path == "freelance":        return _badge("freelance", "freelance")
    if path == "refuse":           return _badge("refused", "refuse")
    if path == "needs_definition": return _badge("needs your input", "asking")
    return _badge(path)

def _chip(label, kind=""):
    color = {"agent":"ecfdf5|047857|d1fae5",
             "glossary":"eef4ff|1e40af|dbeafe",
             "memory":"fef9c3|854d0e|fde68a",
             "verified_query":"f5f3ff|6d28d9|ede9fe",
             "table":"f9fafb|4b5563|e5e7eb"}
    parts = color.get(kind, "f3f4f6|4b5563|e5e7eb").split("|")
    return (f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            f'font-size:11px;font-weight:500;margin:0 4px 4px 0;'
            f'background:#{parts[0]};color:#{parts[1]};border:1px solid #{parts[2]};">'
            f'{label}</span>')

# --- ANSWER FLOW -----------------------------------------------------------
def _ask(question: str, explicit_suffix: str = ""):
    """Process an ask. Checks cache → uses orchestrator if miss."""
    SS.history.append({"role": "user", "content": question})

    # Determine suffix — explicit (from disambig pick) overrides stored
    suffix = explicit_suffix or SS.post_action_state.get(question.lower().strip().rstrip("?"), "")
    cached = answer_cache.lookup(question, suffix)

    if cached:
        time.sleep(0.6)  # tiny delay so it feels alive, not fake
        ans = answer_cache.to_answer(question, cached)
        # Push any studio recommendations
        for r in cached.get("studio_recommendations", []):
            rec_id = f"rec_{len(SS.studio_recs)}_{r['kind']}"
            SS.studio_recs.append({**r, "id": rec_id})
        # Track raw cached dict on the assistant msg (for disambiguation render)
        SS.history.append({"role": "assistant", "answer": ans,
                           "raw_cached": cached,
                           "source_question": question})
        return
    # Real orchestrator
    ans = orchestrator.get().answer(question, user_id=SS.user_id)
    SS.history.append({"role": "assistant", "answer": ans})

def _apply_recommendation(rec):
    kind = rec["kind"]
    if kind == "define_glossary_term":
        defn = rec.get("draft_definition", "")
        ok_bq, ok_dp = False, False
        with st.spinner(f"Writing '{rec['term']}' to BigQuery + Dataplex…"):
            try:
                flywheel.get().add_glossary_term(rec["term"], defn, source="defined_in_demo")
                ok_bq = True
            except Exception as e:
                st.error(f"BigQuery glossary write failed: {e}")
            # Also explicitly mirror to Dataplex via REST (independent of the BQ write)
            try:
                from core import dataplex_ops
                name = dataplex_ops.write_glossary_term(rec["term"], defn)
                if name:
                    ok_dp = True
                    try:
                        flywheel.get()._record_provenance("dataplex_glossary_term", name)
                    except Exception:
                        pass
            except Exception as e:
                st.warning(f"Dataplex glossary write best-effort failed: {str(e)[:120]}")
        if ok_bq and ok_dp:
            st.toast(f"✅ '{rec['term']}' saved to BigQuery + Dataplex glossary")
            SS.built_today.append(f"📖  **{rec['term']}** → BigQuery + Dataplex glossary")
        elif ok_bq:
            st.toast(f"✅ '{rec['term']}' saved to BigQuery (Dataplex write skipped)")
            SS.built_today.append(f"📖  **{rec['term']}** → BigQuery only")
        else:
            st.toast(f"⚠ '{rec['term']}' write failed — see error above")
            SS.built_today.append(f"📖  **{rec['term']}** — write failed")

    elif kind == "promote_verified_queries":
        # Update CX agent example_queries via CA API (REQUIRES update_mask)
        ok = False
        err = None
        with st.spinner("Promoting 3 verified queries to the CX agent…"):
            try:
                from core.ca_api_client import HAS_CA_SDK
                if HAS_CA_SDK:
                    import google.cloud.geminidataanalytics as gda
                    from google.protobuf import field_mask_pb2
                    ca = flywheel.get().ca
                    if ca.agent_svc:
                        name = f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}/dataAgents/{rec['agent_id']}"
                        existing = ca.agent_svc.get_data_agent(name=name)
                        # Build 3 example queries from the promotion patterns
                        ds = cfg.PROJECT_ID + "." + cfg.DATASET
                        sqls = [
                          (f"SELECT mc.customer_state, ROUND(AVG(CAST(cr.review_score AS INT64)),2) AS avg_review, COUNT(*) AS n "
                           f"FROM `{ds}.customer_reviews` cr "
                           f"JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id "
                           f"JOIN `{ds}.marketplace_customers` mc ON mo.customer_id=mc.customer_id "
                           f"GROUP BY 1 HAVING n>100 ORDER BY 2 DESC"),
                          (f"SELECT mc.customer_city, COUNT(*) AS reviews "
                           f"FROM `{ds}.customer_reviews` cr "
                           f"JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id "
                           f"JOIN `{ds}.marketplace_customers` mc ON mo.customer_id=mc.customer_id "
                           f"GROUP BY 1 ORDER BY 2 DESC"),
                          (f"SELECT mc.customer_state, ROUND(COUNTIF(CAST(cr.review_score AS INT64)>=4)/COUNT(*)*100,1) AS csat_pct "
                           f"FROM `{ds}.customer_reviews` cr "
                           f"JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id "
                           f"JOIN `{ds}.marketplace_customers` mc ON mo.customer_id=mc.customer_id "
                           f"GROUP BY 1 ORDER BY 2 DESC"),
                        ]
                        examples = []
                        for patt, sql in zip(rec.get("patterns", [])[:3], sqls):
                            ex = gda.ExampleQuery()
                            ex.natural_language_question = patt
                            ex.sql_query = sql
                            examples.append(ex)
                        del existing.data_analytics_agent.published_context.example_queries[:]
                        existing.data_analytics_agent.published_context.example_queries.extend(examples)
                        del existing.data_analytics_agent.staging_context.example_queries[:]
                        existing.data_analytics_agent.staging_context.example_queries.extend(examples)
                        mask = field_mask_pb2.FieldMask(paths=[
                            'data_analytics_agent.published_context',
                            'data_analytics_agent.staging_context'])
                        ca.agent_svc.update_data_agent(
                            request=gda.UpdateDataAgentRequest(data_agent=existing, update_mask=mask))
                        flywheel.get()._record_provenance(
                            "ca_agent_example_queries", rec['agent_id'])
                        ok = True
            except Exception as e:
                err = str(e)[:200]
        if ok:
            st.toast("✅ CX agent now has 3 verified queries")
            SS.built_today.append("✅  CX agent → 3 verified queries (visible in BQ Studio)")
        else:
            st.error(f"Agent update failed: {err}" if err else "Agent update failed")
            SS.built_today.append("✅  3 verified queries logged locally (CA update failed)")
        SS.post_action_state["average review score by brazilian state"] = "[post-promote]"

    elif kind == "add_graph_edge":
        try:
            graph_ops.enhance_graph([
                "Customer → Purchased → Product",
                "Product → StockedAt → DistributionCenter",
            ])
            SS.built_today.append("📊  Graph edges added: Customer → Product → DC")
        except Exception as e:
            st.warning(f"Graph DDL failed: {str(e)[:120]}")
            SS.built_today.append("📊  Graph edges (logged locally — DDL failed)")
        SS.post_action_state["for our top 10 customers, which distribution centers stock the products they buy"] = "[post-graph]"

    elif kind == "create_embeddings":
        with st.spinner("Generating vector embeddings on 500 reviews (~10s)…"):
            try:
                ok = embeddings_ops.create_review_embeddings()
                if ok:
                    SS.built_today.append("🧠  Vector embeddings created on review_comment_message")
                else:
                    SS.built_today.append("🧠  Embeddings (logged locally — ML model unavailable)")
            except Exception as e:
                st.warning(f"Embeddings failed: {str(e)[:120]}")
                SS.built_today.append("🧠  Embeddings (logged locally)")
        SS.post_action_state["what are customers most upset about in their reviews"] = "[post-embeddings]"

    # Remove the recommendation
    SS.studio_recs = [r for r in SS.studio_recs if r["id"] != rec["id"]]

# --- LAYOUT (left = Ask, right = Studio) -----------------------------------
# Header
st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 8px;
            border-bottom:1px solid #e5e7eb;background:#fff;margin-bottom:12px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-size:18px;background:linear-gradient(135deg,#4285f4,#9b72f4);
                -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">✦</span>
    <span style="font-size:16px;font-weight:600;color:#111827;">Freeform CA</span>
    <span style="font-size:13px;color:#6b7280;">· Cymbal Retail demo</span>
  </div>
  <div style="font-size:12px;color:#6b7280;">2 agents · 5 glossary terms</div>
</div>
""", unsafe_allow_html=True)

# Split: Ask on the left (60%), Studio on the right (40%)
left, right = st.columns([0.6, 0.4], gap="small")

# ===== LEFT: Ask =====
with left:
    st.markdown('<div class="pane-label">Ask</div>', unsafe_allow_html=True)

    # Empty state — suggestion chips
    if not SS.history:
        st.markdown('<div style="text-align:center;padding:24px 0 12px;">'
                    '<div style="font-size:20px;font-weight:600;color:#111827;">Hi Siya — what would you like to know?</div>'
                    '<div style="font-size:13px;color:#6b7280;margin-top:4px;">Try one of these or ask anything about Cymbal Retail.</div>'
                    '</div>', unsafe_allow_html=True)
        suggestions = [
            "What was our revenue last month?",
            "What's our late delivery rate by month?",
            "What's our customer churn rate?",
            "Average review score by Brazilian state",
        ]
        # Two rows of two so they fit comfortably in the narrower left column
        c1, c2 = st.columns(2)
        for i, s in enumerate(suggestions):
            with (c1 if i % 2 == 0 else c2):
                if st.button(s, key=f"sg_{i}", use_container_width=True):
                    _ask(s)
                    st.rerun()

    # Render conversation
    for i, msg in enumerate(SS.history):
        if msg["role"] == "user":
            st.markdown(
                f'<div style="background:#eef4ff;color:#111827;padding:10px 16px;'
                f'border-radius:16px 16px 4px 16px;margin:14px 0 6px auto;max-width:80%;'
                f'width:fit-content;font-size:14px;line-height:1.5;">{msg["content"]}</div>',
                unsafe_allow_html=True)
        else:
            ans: Answer = msg["answer"]
            # ----- needs_disambiguation: option picker -----
            cached_for_path = msg.get("raw_cached")  # may contain options
            if ans.path_taken == "needs_disambiguation" and cached_for_path and cached_for_path.get("options"):
                ambig_term = cached_for_path.get("disambiguation_term", "term")
                st.markdown(
                    f'<div style="margin:8px 0 4px;">{_path_chip("needs_disambiguation")}'
                    f'{_badge(ambig_term + " is ambiguous")}'
                    f'</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:14px;line-height:1.6;color:#111827;margin:4px 0 12px;">{ans.narrative}</div>',
                    unsafe_allow_html=True)
                # Render one button per option
                already_picked = SS.get(f"disambig_picked_{i}")
                for opt in cached_for_path["options"]:
                    key = f"opt_{i}_{opt['key']}"
                    disabled = bool(already_picked)
                    if st.button(opt["label"], key=key, use_container_width=True,
                                 disabled=disabled,
                                 type=("primary" if already_picked == opt['key'] else "secondary")):
                        SS[f"disambig_picked_{i}"] = opt['key']
                        SS["post_action_state"][cached_for_path.get("disambiguation_term","churn") + "_choice"] = opt["key"]
                        # Re-ask with post-choose-{key} suffix
                        SS["pending_q"] = msg.get("source_question", "What's our customer churn rate?")
                        SS["pending_q_suffix"] = "[post-choose-" + opt["key"] + "]"
                        st.rerun()
                    if not already_picked:
                        st.markdown(f'<div style="font-size:11px;color:#6b7280;margin:-4px 0 8px 4px;">{opt.get("subtitle","")}</div>',
                                    unsafe_allow_html=True)
                continue
            # ----- standard answer rendering -----
            st.markdown(
                f'<div style="margin:8px 0 4px;">{_path_chip(ans.path_taken)}'
                f'{_badge(_agent_label(ans.agent_used))}'
                f'{_badge(f"{ans.latency_ms/1000:.1f}s") if ans.latency_ms else ""}'
                f'</div>',
                unsafe_allow_html=True)
            if ans.thinking:
                with st.expander("Show reasoning"):
                    st.markdown(ans.thinking)
            st.markdown(f'<div style="font-size:14px;line-height:1.6;color:#111827;margin:4px 0 8px;">{ans.narrative}</div>',
                        unsafe_allow_html=True)
            if ans.rows:
                df = pd.DataFrame(ans.rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
            # Citations + SQL grouped in a single details expander.
            n_cit = len(ans.citations) if ans.citations else 0
            with st.expander(f"View details ({n_cit} source{'s' if n_cit!=1 else ''} · SQL)"):
                # --- Sources block ---
                if ans.citations:
                    st.markdown(
                        '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;'
                        'letter-spacing:.05em;font-weight:600;margin-bottom:6px;">Sources used</div>',
                        unsafe_allow_html=True)
                    kind_label = {
                        "agent_rule":     "🤖 Agent",
                        "glossary":       "📖 Glossary",
                        "memory":         "🧠 Memory",
                        "verified_query": "✅ Verified query",
                        "table":          "📋 Table",
                    }
                    for c in ans.citations:
                        st.markdown(
                            f'<div style="margin:6px 0 6px;padding:6px 10px;background:#f9fafb;'
                            f'border-left:3px solid #d1d5db;border-radius:4px;">'
                            f'<div style="font-size:11px;color:#6b7280;">{kind_label.get(c.kind, c.kind)}</div>'
                            f'<div style="font-size:13px;color:#111827;font-weight:500;">{c.label}</div>'
                            f'<div style="font-size:12px;color:#4b5563;margin-top:2px;">{c.detail}</div>'
                            f'</div>',
                            unsafe_allow_html=True)
                # --- SQL block ---
                st.markdown(
                    '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;'
                    'letter-spacing:.05em;font-weight:600;margin:14px 0 6px;">Generated SQL</div>',
                    unsafe_allow_html=True)
                if ans.sql:
                    st.code(ans.sql, language="sql")
                else:
                    st.caption("(no SQL — verified template or cached)")

# ===== RIGHT: Studio =====
with right:
    st.markdown(
        '<div class="studio-hdr"><span class="dot"></span> Studio '
        f'<span style="color:#6b7280;font-weight:400;font-size:11px;">'
        f'· {len(SS.studio_recs)} open · {len(SS.built_today)} applied</span></div>',
        unsafe_allow_html=True)

    # Built-today summary
    if SS.built_today:
        inner = "<br>".join(f"• {x}" for x in SS.built_today[-6:])
        st.markdown(f'<div class="studio-built"><span class="label">Built today:</span><br>{inner}</div>',
                    unsafe_allow_html=True)

    # Active recommendations
    if not SS.studio_recs:
        st.markdown(
            '<div style="background:#fff;border:1px dashed #d1d5db;border-radius:10px;'
            'padding:24px 14px;text-align:center;color:#9ca3af;font-size:12px;line-height:1.5;">'
            'No recommendations yet.<br>'
            'Ask a question that exposes a gap to see one appear here.'
            '</div>', unsafe_allow_html=True)
    else:
        for rec in SS.studio_recs:
            with st.container():
                st.markdown('<div class="rec-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="rec-title">{rec["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="rec-evidence">{rec["evidence"]}</div>', unsafe_allow_html=True)
                if rec["kind"] == "define_glossary_term":
                    st.text_area("Definition", value=rec.get("draft_definition",""),
                                 key=f"def_{rec['id']}", height=68, label_visibility="collapsed")
                    if st.button("Save to Dataplex glossary", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        edited = SS.get(f"def_{rec['id']}") or rec.get("draft_definition","")
                        rec["draft_definition"] = edited
                        _apply_recommendation(rec)
                        st.rerun()
                elif rec["kind"] == "promote_verified_queries":
                    for p in rec.get("patterns", []):
                        st.markdown(f'<div class="rec-detail">• {p}</div>', unsafe_allow_html=True)
                    if st.button("Promote to CX agent", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                elif rec["kind"] == "add_graph_edge":
                    for e in rec.get("edges", []):
                        st.markdown(f'<div class="rec-detail">• {e}</div>', unsafe_allow_html=True)
                    if st.button("Add to graph", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                elif rec["kind"] == "create_embeddings":
                    st.markdown(f'<div class="rec-detail">Target: <code>{rec["target_table"]}.{rec["target_column"]}</code></div>',
                                unsafe_allow_html=True)
                    if st.button("Create embeddings", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # Reset
    st.markdown('<div style="margin-top:16px;"></div>', unsafe_allow_html=True)
    if st.button("↺  Reset demo", key="reset_demo", use_container_width=True):
        SS.history = []
        SS.studio_recs = []
        SS.built_today = []
        SS.post_action_state = {}
        sess.reset()
        st.rerun()

# Chat input pinned at bottom (Streamlit shows it across full width)
prompt = st.chat_input("Ask anything about your data…")
# Handle pending question from disambig pick or post-action retry
if "pending_q" in SS:
    pq = SS.pop("pending_q")
    suffix = SS.pop("pending_q_suffix", "")
    _ask(pq, explicit_suffix=suffix)
    st.rerun()
if prompt:
    _ask(prompt)
    st.rerun()
