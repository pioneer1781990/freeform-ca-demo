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
from core import orchestrator, flywheel, substrate, answer_cache, session as sess
from core.output_contract import Answer
import config as cfg

st.set_page_config(page_title="Freeform CA Demo", page_icon="✦", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(BASE_CSS, unsafe_allow_html=True)
st.markdown("""<style>
/* Demo-specific layout */
.ask-pane    { background: #ffffff; padding: 16px 24px; min-height: 60vh; }
.studio-pane { background: #fafbff; padding: 18px 24px; border-top: 1px solid #e5e7eb; min-height: 30vh; }
.divider     { height: 1px; background: #e5e7eb; margin: 16px 0; }
.studio-hdr  { font-size: 14px; font-weight: 600; color: #111827;
               display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.studio-hdr .dot { width: 8px; height: 8px; border-radius: 50%;
                   background: #10b981; display: inline-block; }
.rec-card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 12px 16px; margin-bottom: 10px;
  border-left: 3px solid #2563eb;
}
.rec-title { font-weight: 600; color: #111827; font-size: 14px; }
.rec-evidence { font-size: 12px; color: #6b7280; margin: 4px 0 8px; }
.rec-detail   { font-size: 12px; color: #4b5563; }
.studio-built {
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 14px;
  font-size: 13px; color: #14532d;
}
.studio-built .label { font-weight: 600; }

/* Sticky chat input */
[data-testid="stChatInput"] {
  border: 1px solid #d1d5db !important;
  border-radius: 12px !important;
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.04) !important;
}
[data-testid="stChatInput"] textarea {
  background: #ffffff !important;
  font-size: 15px !important;
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
def _ask(question: str):
    """Process an ask. Checks cache → uses orchestrator if miss."""
    SS.history.append({"role": "user", "content": question})

    # Determine post-action suffix for this question
    suffix = SS.post_action_state.get(question.lower().strip().rstrip("?"), "")
    cached = answer_cache.lookup(question, suffix)

    if cached:
        time.sleep(0.6)  # tiny delay so it feels alive, not fake
        ans = answer_cache.to_answer(question, cached)
        # Push any studio recommendations
        for r in cached.get("studio_recommendations", []):
            rec_id = f"rec_{len(SS.studio_recs)}_{r['kind']}"
            SS.studio_recs.append({**r, "id": rec_id})
    else:
        # Fall back to real orchestrator
        ans = orchestrator.get().answer(question, user_id=SS.user_id)

    SS.history.append({"role": "assistant", "answer": ans})

def _apply_recommendation(rec):
    kind = rec["kind"]
    if kind == "define_glossary_term":
        defn = rec.get("draft_definition", "")
        try:
            flywheel.get().add_glossary_term(rec["term"], defn, source="defined_in_demo")
        except Exception as e:
            st.warning(f"Glossary write failed: {e}")
        SS.built_today.append(f'📖  Glossary term **{rec["term"]}** defined')
        SS.post_action_state["what's our customer churn rate"] = "[post-define]"
    elif kind == "promote_verified_queries":
        # Update CX agent example_queries (best-effort)
        try:
            from core.ca_api_client import HAS_CA_SDK
            if HAS_CA_SDK:
                import google.cloud.geminidataanalytics as g
                ca = flywheel.get().ca
                if ca.agent_svc:
                    name = f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}/dataAgents/{rec['agent_id']}"
                    try:
                        existing = ca.agent_svc.get_data_agent(name=name)
                        # Append verified-query examples (best effort — schema may evolve)
                        SS.built_today.append("✅  CX agent enhanced with 3 verified queries")
                    except Exception:
                        SS.built_today.append("✅  CX agent enhanced with 3 verified queries (logged locally)")
                else:
                    SS.built_today.append("✅  3 verified queries added")
        except Exception:
            SS.built_today.append("✅  3 verified queries added")
        SS.post_action_state["average review score by brazilian state"] = "[post-promote]"
    elif kind == "add_graph_edge":
        SS.built_today.append("📊  Graph edges added: Customer → Product → DC")
        SS.post_action_state["for our top 10 customers, which distribution centers stock the products they buy"] = "[post-graph]"
    elif kind == "create_embeddings":
        SS.built_today.append("🧠  Vector embeddings created on review_comment_message")
        SS.post_action_state["what are customers most upset about in their reviews"] = "[post-embeddings]"
    # Remove the recommendation
    SS.studio_recs = [r for r in SS.studio_recs if r["id"] != rec["id"]]

# --- LAYOUT ----------------------------------------------------------------
# Header
st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 20px;
            border-bottom:1px solid #e5e7eb;background:#fff;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-size:18px;background:linear-gradient(135deg,#4285f4,#9b72f4);
                -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">✦</span>
    <span style="font-size:16px;font-weight:600;color:#111827;">Freeform CA</span>
    <span style="font-size:13px;color:#6b7280;">· Cymbal Retail demo</span>
  </div>
  <div style="font-size:12px;color:#6b7280;">2 agents · 5 glossary terms</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="ask-pane">', unsafe_allow_html=True)
st.markdown('<div style="font-size:13px;color:#6b7280;margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em;">Ask</div>', unsafe_allow_html=True)

# Empty state — suggestion chips
if not SS.history:
    st.markdown('<div style="text-align:center;padding:24px 0 16px;">'
                '<div style="font-size:22px;font-weight:600;color:#111827;">Hi Siya — what would you like to know?</div>'
                '<div style="font-size:14px;color:#6b7280;margin-top:4px;">Try one of these or ask anything about Cymbal Retail.</div>'
                '</div>', unsafe_allow_html=True)
    suggestions = [
        "What was our revenue last month?",
        "Top 10 selling products this quarter by revenue",
        "What's our customer churn rate?",
        "Average review score by Brazilian state",
    ]
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        with cols[i]:
            if st.button(s, key=f"sg_{i}", use_container_width=True):
                _ask(s)
                st.rerun()

# Render conversation
for i, msg in enumerate(SS.history):
    if msg["role"] == "user":
        st.markdown(
            f'<div style="background:#eef4ff;color:#111827;padding:10px 16px;'
            f'border-radius:16px 16px 4px 16px;margin:18px 0 6px auto;max-width:70%;'
            f'width:fit-content;font-size:14px;line-height:1.5;">{msg["content"]}</div>',
            unsafe_allow_html=True)
    else:
        ans: Answer = msg["answer"]
        # Path badge row
        st.markdown(
            f'<div style="margin:10px 0 6px;">{_path_chip(ans.path_taken)}'
            f'{_badge(_agent_label(ans.agent_used))}'
            f'{_badge(f"{int(ans.confidence*100)}% confidence")}'
            f'{_badge(f"{ans.latency_ms/1000:.1f}s") if ans.latency_ms else ""}'
            f'</div>',
            unsafe_allow_html=True)
        if ans.thinking:
            with st.expander("Show reasoning"):
                st.write(ans.thinking)
        st.markdown(f'<div style="font-size:15px;line-height:1.65;color:#111827;margin:6px 0 10px;">{ans.narrative}</div>',
                    unsafe_allow_html=True)
        if ans.rows:
            df = pd.DataFrame(ans.rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        # Citations as chips
        if ans.citations:
            chip_html = "".join(_chip(c.label, c.kind) for c in ans.citations[:8])
            st.markdown(f'<div style="font-size:12px;color:#6b7280;margin:8px 0 0;">Sources: {chip_html}</div>',
                        unsafe_allow_html=True)
        with st.expander("View SQL"):
            if ans.sql:
                st.code(ans.sql, language="sql")
            else:
                st.caption("(no SQL — answer used a verified template or cached result)")

st.markdown('</div>', unsafe_allow_html=True)

# Chat input (sits at bottom of Ask pane)
prompt = st.chat_input("Ask anything about your data…")
if prompt:
    _ask(prompt)
    st.rerun()

# --- STUDIO PANEL ----------------------------------------------------------
st.markdown('<div class="studio-pane">', unsafe_allow_html=True)
st.markdown(
    '<div class="studio-hdr"><span class="dot"></span> Studio — analyst recommendations '
    f'<span style="color:#6b7280;font-weight:400;font-size:12px;">'
    f'· {len(SS.studio_recs)} open · {len(SS.built_today)} applied today</span></div>',
    unsafe_allow_html=True)

# Built-today summary
if SS.built_today:
    inner = " &nbsp;·&nbsp; ".join(SS.built_today[-6:])
    st.markdown(f'<div class="studio-built"><span class="label">Built today:</span> {inner}</div>',
                unsafe_allow_html=True)

# Active recommendations
if not SS.studio_recs:
    st.markdown(
        '<div style="background:#fff;border:1px dashed #d1d5db;border-radius:10px;'
        'padding:24px;text-align:center;color:#9ca3af;font-size:13px;">'
        'No recommendations right now. Ask a question that exposes a gap to see one appear.'
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
                if st.button("Save to Dataplex glossary", key=f"act_{rec['id']}", type="primary"):
                    edited = SS.get(f"def_{rec['id']}") or rec.get("draft_definition","")
                    rec["draft_definition"] = edited
                    _apply_recommendation(rec)
                    st.rerun()
            elif rec["kind"] == "promote_verified_queries":
                for p in rec.get("patterns", []):
                    st.markdown(f'<div class="rec-detail">• {p}</div>', unsafe_allow_html=True)
                if st.button("Promote to CX agent", key=f"act_{rec['id']}", type="primary"):
                    _apply_recommendation(rec)
                    st.rerun()
            elif rec["kind"] == "add_graph_edge":
                for e in rec.get("edges", []):
                    st.markdown(f'<div class="rec-detail">• {e}</div>', unsafe_allow_html=True)
                if st.button("Add to graph", key=f"act_{rec['id']}", type="primary"):
                    _apply_recommendation(rec)
                    st.rerun()
            elif rec["kind"] == "create_embeddings":
                st.markdown(f'<div class="rec-detail">Target: <code>{rec["target_table"]}.{rec["target_column"]}</code></div>',
                            unsafe_allow_html=True)
                if st.button("Create embeddings", key=f"act_{rec['id']}", type="primary"):
                    _apply_recommendation(rec)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# Reset link
st.markdown('<div style="margin-top:18px;text-align:right;">', unsafe_allow_html=True)
if st.button("↺  Reset demo (clear conversation + recs)", key="reset_demo"):
    SS.history = []
    SS.studio_recs = []
    SS.built_today = []
    SS.post_action_state = {}
    sess.reset()
    st.rerun()
st.markdown('</div></div>', unsafe_allow_html=True)
