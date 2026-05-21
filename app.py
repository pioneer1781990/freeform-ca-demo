"""Single-page demo, v2 architecture.

Philosophy split (new):
- ASK (left): pure business-user surface. Asks question, sees answer + sources +
  reasoning. NO action buttons (no 'add to graph', no 'create embeddings').
  If an answer has unmet recommendations, the answer area shows a soft
  notification: "I've notified the analyst about X." That's it.
- STUDIO (right): analyst surface. Loads with initial recommendations derived
  from live INFORMATION_SCHEMA-style signals. As users ask questions, more
  recommendations appear. Analyst applies them with one click.

User switching:
- Top of Ask shows a persona avatar + dropdown to switch between Siya / Alex /
  Morgan. Switching clears Ask history but PRESERVES applied_enrichments so
  later asks by the new user inherit the prior enrichments and answer
  instantly with citation to the source user.
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

# Optional modules built by parallel agents — gracefully degrade if missing
try:
    from core import live_signals as _live_signals
    HAS_LIVE_SIGNALS = True
except Exception:
    HAS_LIVE_SIGNALS = False
try:
    from core import user_switcher as _user_switcher
    HAS_USER_SWITCHER = True
except Exception:
    HAS_USER_SWITCHER = False

# Default personas (used if user_switcher module isn't available yet)
DEFAULT_PERSONAS = [
    {"id": "siya",   "name": "Siya",   "role": "Sales analyst",       "avatar_color": "#3b82f6"},
    {"id": "alex",   "name": "Alex",   "role": "CX manager",          "avatar_color": "#10b981"},
    {"id": "morgan", "name": "Morgan", "role": "Supply chain lead",   "avatar_color": "#f59e0b"},
]
PERSONAS = (_user_switcher.PERSONAS if HAS_USER_SWITCHER else DEFAULT_PERSONAS)

st.set_page_config(page_title="Freeform CA Demo", page_icon="✦", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(BASE_CSS, unsafe_allow_html=True)
st.markdown("""<style>
.main .block-container { max-width: 1400px; padding-top: 0.5rem; }
div[data-testid="stHorizontalBlock"] > div:first-child  { border-right: 1px solid #ececec; padding-right: 16px; }
div[data-testid="stHorizontalBlock"] > div:nth-child(2) { padding-left: 20px; }

.pane-label  { font-size: 11px; color: #6b7280; text-transform: uppercase;
               letter-spacing: .06em; margin-bottom: 8px; font-weight: 600; }
.studio-hdr  { font-size: 14px; font-weight: 600; color: #111827;
               display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.studio-hdr .dot { width: 8px; height: 8px; border-radius: 50%;
                   background: #10b981; display: inline-block; }
.section-divider { font-size: 11px; color: #9ca3af; text-transform: uppercase;
                   letter-spacing: .06em; font-weight: 600; margin: 18px 0 8px; }

.rec-card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 12px 14px; margin-bottom: 10px;
  border-left: 3px solid #2563eb;
}
.rec-card.from-signal { border-left-color: #9ca3af; }
.rec-title { font-weight: 600; color: #111827; font-size: 13px; }
.rec-evidence { font-size: 12px; color: #6b7280; margin: 4px 0 8px; line-height: 1.4; }
.rec-detail   { font-size: 12px; color: #4b5563; margin: 2px 0; }

.signal-card {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 10px 12px; margin-bottom: 8px;
}
.signal-title { font-size: 12px; color: #6b7280; text-transform: uppercase;
                letter-spacing: .05em; margin-bottom: 6px; font-weight: 600; }
.signal-row { font-size: 12px; color: #111827; padding: 3px 0; }
.signal-row .num { color: #4b5563; }

.studio-built {
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 14px;
  font-size: 12px; color: #14532d; line-height: 1.6;
}
.studio-built .label { font-weight: 600; }

.persona-pill {
  display: inline-flex; align-items: center; gap: 8px;
  background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 999px;
  padding: 4px 10px 4px 4px; font-size: 12px; color: #4b5563;
}
.persona-pill .avatar {
  width: 22px; height: 22px; border-radius: 50%;
  display: inline-grid; place-items: center;
  font-size: 11px; font-weight: 600; color: white;
}

.analyst-ping {
  background: #eef4ff; border: 1px solid #bfdbfe; border-radius: 8px;
  padding: 8px 12px; margin: 10px 0 0; font-size: 12px; color: #1e3a8a;
}

[data-testid="stChatInput"] {
  border: 1px solid #d1d5db !important;
  border-radius: 12px !important;
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.04) !important;
}
[data-testid="stChatInput"] textarea {
  background: #ffffff !important; font-size: 14px !important; color: #111827 !important;
}
</style>""", unsafe_allow_html=True)
sess.start_if_missing()

# --- session state init ----------------------------------------------------
SS = st.session_state
SS.setdefault("history", [])
SS.setdefault("studio_recs", [])
SS.setdefault("built_today", [])
SS.setdefault("user_id", "siya")
SS.setdefault("post_action_state", {})
SS.setdefault("applied_enrichments", set())   # 'churn_defined','cx_verified_queries','graph_extended','embeddings_created'
SS.setdefault("initial_recs_loaded", False)
SS.setdefault("studio_signals", None)         # cache of live signals so we don't refetch per rerun

# --- helpers ---------------------------------------------------------------
def _persona(uid):
    for p in PERSONAS:
        if p["id"] == uid: return p
    return PERSONAS[0]

def _agent_label(aid):
    if not aid: return "freelance"
    return {"cymbal_sales_agent": "Sales Analytics",
            "cymbal_customer_experience_agent": "Customer Experience",
            "cymbal_customer_experience_agent_12ba": "Customer Experience"}.get(
            aid, aid.replace("cymbal_", "").replace("_agent","").replace("_"," ").title())

def _badge(text, kind=""):
    cls = {"agent":     "ecfdf5|047857|d1fae5",
           "freelance": "fef3c7|92400e|fde68a",
           "refuse":    "fee2e2|991b1b|fecaca",
           "asking":    "dbeafe|1d4ed8|bfdbfe",
           "inherited": "f5f3ff|6d28d9|ede9fe"}.get(kind, "f3f4f6|4b5563|e5e7eb")
    parts = cls.split("|")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:6px;'
            f'font-size:11px;font-weight:500;margin-right:6px;background:#{parts[0]};'
            f'color:#{parts[1]};border:1px solid #{parts[2]};">{text}</span>')

def _path_chip(path):
    if path == "agent_route":      return _badge("via agent", "agent")
    if path == "freelance":        return _badge("freelance", "freelance")
    if path == "refuse":           return _badge("refused", "refuse")
    if path == "needs_definition": return _badge("needs your input", "asking")
    if path == "needs_disambiguation": return _badge("needs your input", "asking")
    if path == "inherited":        return _badge("inherited", "inherited")
    return _badge(path)

# --- core flow -------------------------------------------------------------
def _ask(question: str, explicit_suffix: str = ""):
    SS.history.append({"role": "user", "content": question, "user_id": SS.user_id})

    # 1) Check for inheritance — non-original user + matching applied enrichment
    inherited_suffix = ""
    if HAS_USER_SWITCHER and SS.user_id != "siya" and SS.applied_enrichments:
        inherited_suffix = _user_switcher.inherited_suffix(
            SS.user_id, question, SS.applied_enrichments)

    suffix = explicit_suffix or inherited_suffix or SS.post_action_state.get(
        question.lower().strip().rstrip("?"), "")

    cached = answer_cache.lookup(question, suffix)
    if cached:
        time.sleep(0.4)
        ans = answer_cache.to_answer(question, cached)
        # Pin path to 'inherited' if we matched an inherit variant
        if inherited_suffix and "[inherited-by-" in suffix:
            ans.path_taken = "inherited"
        for r in cached.get("studio_recommendations", []):
            rec_id = f"rec_{len(SS.studio_recs)}_{r['kind']}_{int(time.time()*1000)%10000}"
            SS.studio_recs.append({**r, "id": rec_id, "source": "user_question"})
        SS.history.append({"role": "assistant", "answer": ans,
                           "raw_cached": cached, "source_question": question,
                           "user_id": SS.user_id})
        return
    ans = orchestrator.get().answer(question, user_id=SS.user_id)
    SS.history.append({"role": "assistant", "answer": ans, "user_id": SS.user_id})


def _load_initial_recs():
    """One-shot load of live-signal-derived recommendations into Studio."""
    if SS.initial_recs_loaded: return
    SS.initial_recs_loaded = True
    if not HAS_LIVE_SIGNALS: return
    try:
        for r in _live_signals.initial_recommendations():
            rec_id = f"rec_initial_{len(SS.studio_recs)}_{r['kind']}"
            SS.studio_recs.append({**r, "id": rec_id, "source": "live_signal"})
    except Exception as e:
        print(f"[init recs] {e}")


def _refresh_signals(force: bool = False):
    if SS.studio_signals is not None and not force: return
    if not HAS_LIVE_SIGNALS:
        SS.studio_signals = {"tables": [], "pairs": [], "terms": [], "failed": []}
        return
    try:
        SS.studio_signals = {
            "tables": _live_signals.top_tables_by_usage(),
            "pairs":  _live_signals.top_table_pairs(),
            "terms":  _live_signals.undefined_term_refusals(),
            "failed": _live_signals.recent_failed_queries(),
        }
    except Exception as e:
        print(f"[signals] {e}")
        SS.studio_signals = {"tables": [], "pairs": [], "terms": [], "failed": []}

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
            try:
                from core import dataplex_ops
                name = dataplex_ops.write_glossary_term(rec["term"], defn)
                if name:
                    ok_dp = True
                    try: flywheel.get()._record_provenance("dataplex_glossary_term", name)
                    except Exception: pass
            except Exception as e:
                st.warning(f"Dataplex glossary write best-effort failed: {str(e)[:120]}")
        if ok_bq and ok_dp:
            st.toast(f"✅ '{rec['term']}' saved to BigQuery + Dataplex glossary")
            SS.built_today.append(f"📖  **{rec['term']}** → BigQuery + Dataplex glossary")
        elif ok_bq:
            st.toast(f"✅ '{rec['term']}' saved to BigQuery (Dataplex skipped)")
            SS.built_today.append(f"📖  **{rec['term']}** → BigQuery only")
        else:
            st.toast(f"⚠ '{rec['term']}' write failed — see error above")
        SS.applied_enrichments.add("churn_defined")

    elif kind == "promote_verified_queries":
        ok, err = False, None
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
                        ds = cfg.PROJECT_ID + "." + cfg.DATASET
                        sqls = [
                          (f"SELECT mc.customer_state, ROUND(AVG(CAST(cr.review_score AS INT64)),2) AS avg_review, COUNT(*) AS n "
                           f"FROM `{ds}.customer_reviews` cr JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id "
                           f"JOIN `{ds}.marketplace_customers` mc ON mo.customer_id=mc.customer_id GROUP BY 1 HAVING n>100 ORDER BY 2 DESC"),
                          (f"SELECT mc.customer_city, COUNT(*) AS reviews "
                           f"FROM `{ds}.customer_reviews` cr JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id "
                           f"JOIN `{ds}.marketplace_customers` mc ON mo.customer_id=mc.customer_id GROUP BY 1 ORDER BY 2 DESC"),
                          (f"SELECT mc.customer_state, ROUND(COUNTIF(CAST(cr.review_score AS INT64)>=4)/COUNT(*)*100,1) AS csat_pct "
                           f"FROM `{ds}.customer_reviews` cr JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id "
                           f"JOIN `{ds}.marketplace_customers` mc ON mo.customer_id=mc.customer_id GROUP BY 1 ORDER BY 2 DESC"),
                        ]
                        examples = []
                        for patt, sql in zip(rec.get("patterns", [])[:3], sqls):
                            ex = gda.ExampleQuery(); ex.natural_language_question = patt; ex.sql_query = sql
                            examples.append(ex)
                        del existing.data_analytics_agent.published_context.example_queries[:]
                        existing.data_analytics_agent.published_context.example_queries.extend(examples)
                        del existing.data_analytics_agent.staging_context.example_queries[:]
                        existing.data_analytics_agent.staging_context.example_queries.extend(examples)
                        mask = field_mask_pb2.FieldMask(paths=['data_analytics_agent.published_context','data_analytics_agent.staging_context'])
                        ca.agent_svc.update_data_agent(request=gda.UpdateDataAgentRequest(data_agent=existing, update_mask=mask))
                        flywheel.get()._record_provenance("ca_agent_example_queries", rec['agent_id'])
                        ok = True
            except Exception as e:
                err = str(e)[:200]
        if ok:
            st.toast("✅ CX agent now has 3 verified queries")
            SS.built_today.append("✅  CX agent → 3 verified queries (visible in BQ Studio)")
        else:
            st.error(f"Agent update failed: {err}" if err else "Agent update failed")
        SS.applied_enrichments.add("cx_verified_queries")

    elif kind == "add_graph_edge":
        with st.spinner("Adding DC edges to BQ Property Graph…"):
            try:
                graph_ops.enhance_graph(["Customer → Purchased → Product",
                                         "Product → StockedAt → DistributionCenter"])
                SS.built_today.append("📊  Graph extended: Customer → Product → DC")
                st.toast("✅ Graph extended with DistributionCenter edges")
            except Exception as e:
                st.error(f"Graph DDL failed: {str(e)[:200]}")
        SS.applied_enrichments.add("graph_extended")

    elif kind == "create_embeddings":
        with st.spinner("Generating vector embeddings on 500 reviews (~10s)…"):
            try:
                ok = embeddings_ops.create_review_embeddings()
                if ok:
                    SS.built_today.append("🧠  Vector embeddings created on review_comment_message")
                    st.toast("✅ Embeddings + vector index built")
            except Exception as e:
                st.error(f"Embeddings failed: {str(e)[:200]}")
        SS.applied_enrichments.add("embeddings_created")

    elif kind == "add_description":
        st.toast("✅ Description draft generated (analyst to review)")
        SS.built_today.append(f"📝  Description draft → `{rec.get('target_table','?')}`")

    SS.studio_recs = [r for r in SS.studio_recs if r["id"] != rec["id"]]

# --- LAYOUT ---------------------------------------------------------------
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

_load_initial_recs()
_refresh_signals()

left, right = st.columns([0.6, 0.4], gap="small")

# ===== LEFT: Ask =====
with left:
    # Persona switcher (Beat A)
    cur = _persona(SS.user_id)
    pc1, pc2 = st.columns([0.7, 0.3])
    with pc1:
        st.markdown(
            f'<div class="persona-pill">'
            f'<span class="avatar" style="background:{cur["avatar_color"]};">{cur["name"][0]}</span>'
            f'<span><b>{cur["name"]}</b> · {cur["role"]}</span>'
            f'</div>', unsafe_allow_html=True)
    with pc2:
        names = [p["name"] for p in PERSONAS]
        cur_idx = names.index(cur["name"])
        new_idx = st.selectbox("Switch user", options=range(len(names)),
                               format_func=lambda i: f"Switch to {names[i]}",
                               index=cur_idx, label_visibility="collapsed")
        new_id = PERSONAS[new_idx]["id"]
        if new_id != SS.user_id:
            SS.user_id = new_id
            SS.history = []  # fresh chat for new user
            st.rerun()

    st.markdown('<div class="pane-label" style="margin-top:14px;">Ask</div>', unsafe_allow_html=True)

    if not SS.history:
        st.markdown('<div style="text-align:center;padding:18px 0 8px;">'
                    f'<div style="font-size:20px;font-weight:600;color:#111827;">Hi {cur["name"]} — what would you like to know?</div>'
                    '<div style="font-size:13px;color:#6b7280;margin-top:4px;">Try one of these or type a question below.</div>'
                    '</div>', unsafe_allow_html=True)
        suggestions = [
            "What was our revenue last month?",
            "What's our late delivery rate by month?",
            "What's our customer churn rate?",
            "Average review score by Brazilian state",
        ]
        c1, c2 = st.columns(2)
        for i, s in enumerate(suggestions):
            with (c1 if i % 2 == 0 else c2):
                if st.button(s, key=f"sg_{i}", use_container_width=True):
                    SS["pending_q"] = s
                    st.rerun()

    for i, msg in enumerate(SS.history):
        if msg["role"] == "user":
            st.markdown(
                f'<div style="background:#eef4ff;color:#111827;padding:10px 16px;'
                f'border-radius:16px 16px 4px 16px;margin:14px 0 6px auto;max-width:80%;'
                f'width:fit-content;font-size:14px;line-height:1.5;">{msg["content"]}</div>',
                unsafe_allow_html=True)
        else:
            ans: Answer = msg["answer"]
            cached_for_path = msg.get("raw_cached")

            # ---- needs_disambiguation: business user picks an option ----
            if ans.path_taken == "needs_disambiguation" and cached_for_path and cached_for_path.get("options"):
                ambig_term = cached_for_path.get("disambiguation_term", "term")
                st.markdown(
                    f'<div style="margin:8px 0 4px;">{_path_chip("needs_disambiguation")}'
                    f'{_badge(ambig_term + " is ambiguous")}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:14px;line-height:1.6;color:#111827;margin:4px 0 12px;">{ans.narrative}</div>',
                    unsafe_allow_html=True)
                already_picked = SS.get(f"disambig_picked_{i}")
                for opt in cached_for_path["options"]:
                    key = f"opt_{i}_{opt['key']}"
                    disabled = bool(already_picked)
                    if st.button(opt["label"], key=key, use_container_width=True,
                                 disabled=disabled,
                                 type=("primary" if already_picked == opt['key'] else "secondary")):
                        SS[f"disambig_picked_{i}"] = opt['key']
                        SS["pending_q"] = msg.get("source_question", "What's our customer churn rate?")
                        SS["pending_q_suffix"] = "[post-choose-" + opt["key"] + "]"
                        st.rerun()
                    if not already_picked:
                        st.markdown(f'<div style="font-size:11px;color:#6b7280;margin:-4px 0 8px 4px;">{opt.get("subtitle","")}</div>',
                                    unsafe_allow_html=True)
                continue

            # ---- standard / inherited / agent / freelance answer ----
            st.markdown(
                f'<div style="margin:8px 0 4px;">{_path_chip(ans.path_taken)}'
                f'{_badge(_agent_label(ans.agent_used))}'
                f'{_badge(f"{ans.latency_ms/1000:.1f}s") if ans.latency_ms else ""}'
                f'</div>', unsafe_allow_html=True)
            if ans.thinking:
                with st.expander("Show reasoning"):
                    st.markdown(ans.thinking)
            st.markdown(f'<div style="font-size:14px;line-height:1.6;color:#111827;margin:4px 0 8px;">{ans.narrative}</div>',
                        unsafe_allow_html=True)
            if ans.rows:
                df = pd.DataFrame(ans.rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

            # *** Soft "sent to analyst" notification (no actionable buttons) ***
            if cached_for_path and cached_for_path.get("studio_recommendations"):
                rec_titles = [r["title"] for r in cached_for_path["studio_recommendations"]]
                titles_str = "; ".join(rec_titles)
                st.markdown(
                    f'<div class="analyst-ping">💡 I\'ve sent <b>{len(rec_titles)}</b> recommendation'
                    f'{"s" if len(rec_titles)>1 else ""} to the analyst: <i>{titles_str}</i></div>',
                    unsafe_allow_html=True)

            n_cit = len(ans.citations) if ans.citations else 0
            with st.expander(f"View details ({n_cit} source{'s' if n_cit!=1 else ''} · SQL)"):
                if ans.citations:
                    st.markdown(
                        '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;'
                        'letter-spacing:.05em;font-weight:600;margin-bottom:6px;">Sources used</div>',
                        unsafe_allow_html=True)
                    kind_label = {"agent_rule":"🤖 Agent","glossary":"📖 Glossary",
                                  "memory":"🧠 Memory","verified_query":"✅ Verified query","table":"📋 Table"}
                    for c in ans.citations:
                        st.markdown(
                            f'<div style="margin:6px 0;padding:6px 10px;background:#f9fafb;'
                            f'border-left:3px solid #d1d5db;border-radius:4px;">'
                            f'<div style="font-size:11px;color:#6b7280;">{kind_label.get(c.kind, c.kind)}</div>'
                            f'<div style="font-size:13px;color:#111827;font-weight:500;">{c.label}</div>'
                            f'<div style="font-size:12px;color:#4b5563;margin-top:2px;">{c.detail}</div>'
                            f'</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;'
                    'letter-spacing:.05em;font-weight:600;margin:14px 0 6px;">Generated SQL</div>',
                    unsafe_allow_html=True)
                if ans.sql:
                    st.code(ans.sql, language="sql")
                else:
                    st.caption("(no SQL — verified template, cached or inherited result)")

# ===== RIGHT: Studio =====
with right:
    st.markdown(
        '<div class="studio-hdr"><span class="dot"></span> Studio '
        f'<span style="color:#6b7280;font-weight:400;font-size:11px;">'
        f'· {len(SS.studio_recs)} open · {len(SS.built_today)} applied</span></div>',
        unsafe_allow_html=True)

    # Built today (top)
    if SS.built_today:
        inner = "<br>".join(f"• {x}" for x in SS.built_today[-6:])
        st.markdown(f'<div class="studio-built"><span class="label">Built today:</span><br>{inner}</div>',
                    unsafe_allow_html=True)

    # Live signals panel
    sig = SS.studio_signals or {}
    if any(sig.get(k) for k in ("tables","pairs","terms","failed")):
        st.markdown('<div class="section-divider">Live signals from query history</div>', unsafe_allow_html=True)
        # Top tables
        if sig.get("tables"):
            rows_html = "".join(
                f'<div class="signal-row">• <b>{r["table"]}</b> <span class="num">{r["query_count"]} queries · {r["unique_users"]} users</span></div>'
                for r in sig["tables"][:5])
            st.markdown(f'<div class="signal-card"><div class="signal-title">Top tables (last 14d)</div>{rows_html}</div>',
                        unsafe_allow_html=True)
        # Pairs
        if sig.get("pairs"):
            rows_html = "".join(
                f'<div class="signal-row">• <b>{r["left"]} ↔ {r["right"]}</b> <span class="num">{r["co_count"]} co-queries</span></div>'
                for r in sig["pairs"][:5])
            st.markdown(f'<div class="signal-card"><div class="signal-title">Frequently joined together</div>{rows_html}</div>',
                        unsafe_allow_html=True)
        # Undefined terms
        if sig.get("terms"):
            rows_html = "".join(
                f'<div class="signal-row">• <b>{r["term"]}</b> <span class="num">{r["refusals"]} refusals</span></div>'
                for r in sig["terms"][:5])
            st.markdown(f'<div class="signal-card"><div class="signal-title">Undefined terms causing refusals</div>{rows_html}</div>',
                        unsafe_allow_html=True)

    # Recommendations
    st.markdown('<div class="section-divider">Recommendations</div>', unsafe_allow_html=True)
    if not SS.studio_recs:
        st.markdown(
            '<div style="background:#fff;border:1px dashed #d1d5db;border-radius:10px;'
            'padding:24px 14px;text-align:center;color:#9ca3af;font-size:12px;line-height:1.5;">'
            'No recommendations right now.<br>'
            'They\'ll appear as live signals build up or business users ask questions that expose gaps.'
            '</div>', unsafe_allow_html=True)
    else:
        for rec in SS.studio_recs:
            with st.container():
                from_signal = (rec.get("source") == "live_signal")
                card_cls = "rec-card from-signal" if from_signal else "rec-card"
                st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
                source_tag = '<span style="font-size:10px;color:#9ca3af;margin-right:6px;">FROM LIVE SIGNAL</span>' if from_signal else ''
                st.markdown(f'<div class="rec-title">{source_tag}{rec["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="rec-evidence">{rec.get("evidence","")}</div>', unsafe_allow_html=True)

                kind = rec["kind"]
                if kind == "define_glossary_term":
                    st.text_area("Definition", value=rec.get("draft_definition",""),
                                 key=f"def_{rec['id']}", height=68, label_visibility="collapsed")
                    if st.button("Save to Dataplex glossary", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        edited = SS.get(f"def_{rec['id']}") or rec.get("draft_definition","")
                        rec["draft_definition"] = edited
                        _apply_recommendation(rec)
                        st.rerun()
                elif kind == "promote_verified_queries":
                    for p in rec.get("patterns", []):
                        st.markdown(f'<div class="rec-detail">• {p}</div>', unsafe_allow_html=True)
                    if st.button("Promote to CX agent", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                elif kind == "add_graph_edge":
                    for e in rec.get("edges", []):
                        st.markdown(f'<div class="rec-detail">• {e}</div>', unsafe_allow_html=True)
                    if st.button("Add to graph", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                elif kind == "create_embeddings":
                    st.markdown(f'<div class="rec-detail">Target: <code>{rec.get("target_table","?")}.{rec.get("target_column","?")}</code></div>',
                                unsafe_allow_html=True)
                    if st.button("Create embeddings", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                elif kind == "add_description":
                    st.markdown(f'<div class="rec-detail">Target: <code>{rec.get("target_table","?")}</code></div>',
                                unsafe_allow_html=True)
                    if st.button("Generate description draft", key=f"act_{rec['id']}", type="primary",
                                 use_container_width=True):
                        _apply_recommendation(rec)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-top:16px;"></div>', unsafe_allow_html=True)
    if st.button("↺  Reset demo", key="reset_demo", use_container_width=True):
        SS.history = []
        SS.studio_recs = []
        SS.built_today = []
        SS.post_action_state = {}
        SS.applied_enrichments = set()
        SS.initial_recs_loaded = False
        SS.studio_signals = None
        sess.reset()
        st.rerun()

# Chat input pinned at bottom
prompt = st.chat_input("Ask anything about your data…")
if "pending_q" in SS:
    pq = SS.pop("pending_q"); suffix = SS.pop("pending_q_suffix","")
    _ask(pq, explicit_suffix=suffix)
    st.rerun()
if prompt:
    _ask(prompt)
    st.rerun()
