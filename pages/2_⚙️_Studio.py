"""Analyst view — clean recommendation dashboard."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings; warnings.filterwarnings("ignore")
import streamlit as st
import pandas as pd

from styles import STUDIO_CSS
from core import substrate, flywheel, session as sess
import config as cfg

st.set_page_config(page_title="Studio", page_icon="🛠", layout="wide", initial_sidebar_state="expanded")
st.markdown(STUDIO_CSS, unsafe_allow_html=True)
sess.start_if_missing()

s  = substrate.get()
fw = flywheel.get()

# --- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.markdown('<div style="font-size:18px;font-weight:600;color:#111827;padding:4px 0 16px;">🛠 Studio</div>',
                unsafe_allow_html=True)
    st.page_link("pages/1_💬_Ask.py", label="💬  Back to Ask", icon=None)
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:12px;color:#6b7280;padding:4px 0;">Project</div>'
                f'<div style="font-size:13px;color:#111827;font-family:monospace;padding-bottom:8px;">{cfg.PROJECT_ID}</div>'
                f'<div style="font-size:12px;color:#6b7280;padding:4px 0;">Dataset</div>'
                f'<div style="font-size:13px;color:#111827;font-family:monospace;">{cfg.DATASET}</div>',
                unsafe_allow_html=True)

# --- header ----------------------------------------------------------------
st.markdown('<div class="studio-title">Analyst Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="studio-sub">Recommendations from observed usage. Govern agents, glossary, and memory.</div>',
            unsafe_allow_html=True)

# --- top metrics -----------------------------------------------------------
q_count = fw.session_question_count()
agents_df = s.agents()
n_agents = 0
if not agents_df.empty:
    n_agents = agents_df[agents_df['status']=='published']['agent_id'].nunique()
glossary_df = s.glossary()
n_terms = len(glossary_df)
memory_df = s.memory()
pending_promotions = 0
try:
    pr_df = fw.list_promotion_requests()
    pending_promotions = len(pr_df) if not pr_df.empty else 0
except Exception:
    pending_promotions = 0

st.markdown(f"""
<div class="metric-row">
  <div class="metric-card"><div class="metric-label">Questions this session</div><div class="metric-value">{q_count}</div></div>
  <div class="metric-card"><div class="metric-label">Published agents</div><div class="metric-value">{n_agents}</div></div>
  <div class="metric-card"><div class="metric-label">Glossary terms</div><div class="metric-value">{n_terms}</div></div>
  <div class="metric-card"><div class="metric-label">Promotion requests</div><div class="metric-value">{pending_promotions}</div></div>
</div>
""", unsafe_allow_html=True)

# --- tabs ------------------------------------------------------------------
tab_recs, tab_agents, tab_glossary, tab_memory, tab_feed = st.tabs(
    ["Recommendations", "Agents", "Glossary", "Memory", "Query feed"])

# --- RECOMMENDATIONS -------------------------------------------------------
with tab_recs:
    c1, c2 = st.columns([0.18, 0.18, ])
    with c1:
        if st.button("🔁 Check for signals", use_container_width=True, type="primary"):
            st.session_state["show_recs"] = True
    with c2:
        if st.button("Reset session", use_container_width=True):
            sess.reset()
            st.session_state["show_recs"] = False
            st.rerun()

    if not st.session_state.get("show_recs"):
        st.markdown(
            '<div class="empty-state">'
            'No recommendations yet. Ask a few questions on the <b>Ask</b> page first, '
            'then click <b>Check for signals</b> to see what the flywheel found.'
            '</div>', unsafe_allow_html=True)
    else:
        col1, col2 = st.columns([0.55, 0.45])

        with col1:
            st.markdown('<div class="section-title">Suggested new agents</div>', unsafe_allow_html=True)
            proposals = fw.agent_proposals(only_session=True, min_count=3)
            if not proposals:
                st.caption("No agent clusters detected this session.")
            for p in proposals[:3]:
                with st.container(border=True):
                    st.markdown(f"**{p['name']} Agent**")
                    st.caption(p['evidence'])
                    st.markdown(f"Tables in scope: `{', '.join(p['tables_in_scope'])}`")
                    with st.expander("Suggested system instruction"):
                        st.write(p['system_instruction'])
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Review & publish", key=f"pub_{p['suggested_id']}", type="primary"):
                            with st.spinner(f"Publishing {p['name']} Agent..."):
                                ok = fw.publish_agent(
                                    agent_id=p['suggested_id'], name=p['name'],
                                    description=p['description'],
                                    tables_in_scope=p['tables_in_scope'],
                                    glossary_terms=p['glossary_terms'],
                                    system_instruction=p['system_instruction'],
                                )
                            st.success("Published" if ok else "Saved locally (CA API failed)")
                            st.rerun()
                    with cc2:
                        st.button("Dismiss", key=f"dis_{p['suggested_id']}")

            st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Suggested graph edges</div>', unsafe_allow_html=True)
            ge_props = fw.graph_edge_proposals()
            if not ge_props:
                st.caption("No graph edge proposals yet.")
            for ge in ge_props[:3]:
                with st.container(border=True):
                    st.markdown(f"**{ge['left']} ↔ {ge['right']}**")
                    st.caption(f"Joined together in {ge['co_count']} queries")
                    st.button("Add to graph", key=f"ge_{ge['suggested_edge']}")

        with col2:
            st.markdown('<div class="section-title">Prep recommendations</div>', unsafe_allow_html=True)
            desc_recs = fw.description_prep_recs()
            gl_recs   = fw.glossary_prep_recs()
            if not desc_recs and not gl_recs:
                st.caption("No prep recommendations yet.")
            for r in desc_recs[:4]:
                with st.container(border=True):
                    st.markdown(f"⚠️ **`{r['target_table']}`** is missing descriptions")
                    st.caption(r['detail'])
                    st.button("Generate & apply", key=f"desc_{r['target_table']}")
            for r in gl_recs[:3]:
                with st.container(border=True):
                    st.markdown(f"📖 Define glossary term **`{r['term']}`**")
                    st.caption(r['detail'])
                    if st.button("Define", key=f"gl_{r['term']}"):
                        st.session_state["define_term"] = r['term']

# --- AGENTS ----------------------------------------------------------------
with tab_agents:
    st.markdown('<div class="section-title">Published agents</div>', unsafe_allow_html=True)
    agents = s.agents()
    if agents.empty:
        st.caption("No agents yet.")
    else:
        agents = (agents.sort_values('created_at', ascending=False)
                        .drop_duplicates('agent_id', keep='first'))
        published = agents[agents['status'] == 'published']
        AVATAR = ["av-blue","av-green","av-purple","av-orange","av-pink"]
        cols = st.columns(min(3, max(1, len(published))))
        for i, (_, a) in enumerate(published.iterrows()):
            with cols[i % len(cols)]:
                with st.container(border=True):
                    initial = a["name"][0].upper()
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;">'
                        f'<span class="agent-avatar {AVATAR[i % len(AVATAR)]}">{initial}</span>'
                        f'<div><div style="font-weight:600;color:#111827;">{a["name"]}</div>'
                        f'<div style="font-size:12px;color:#6b7280;font-family:monospace;">{a["agent_id"]}</div></div></div>',
                        unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:13px;color:#4b5563;margin-top:10px;'>{a.get('description','')}</div>",
                                unsafe_allow_html=True)
                    tbls = list(a['tables_in_scope']) if a['tables_in_scope'] is not None else []
                    st.caption(f"Tables: {', '.join(tbls)}")
                    gts = list(a['glossary_terms']) if a['glossary_terms'] is not None else []
                    if gts:
                        st.caption(f"Glossary: {', '.join(gts)}")

# --- GLOSSARY --------------------------------------------------------------
with tab_glossary:
    st.markdown('<div class="section-title">Business glossary</div>', unsafe_allow_html=True)
    g = s.glossary()
    if g.empty:
        st.caption("Glossary is empty.")
    else:
        for _, term in g.iterrows():
            st.markdown(
                f'<div class="kv-row">'
                f'<div class="kv-key">{term["term"]} <span style="font-size:11px;color:#9ca3af;font-weight:400;">· {term.get("source","")}</span></div>'
                f'<div class="kv-val">{term["definition"]}</div>'
                f'</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    with st.expander("➕ Add a new glossary term", expanded=bool(st.session_state.get('define_term'))):
        new_term = st.text_input("Term", value=st.session_state.get('define_term', ''))
        new_def  = st.text_area("Definition", height=80)
        if st.button("Add to glossary", type="primary"):
            if new_term.strip() and new_def.strip():
                fw.add_glossary_term(new_term.strip(), new_def.strip(), source="manual")
                st.success(f"Added: {new_term}")
                st.session_state.pop("define_term", None)
                st.rerun()

# --- MEMORY ----------------------------------------------------------------
with tab_memory:
    st.markdown('<div class="section-title">Promotion queue</div>', unsafe_allow_html=True)
    try:
        pr = fw.list_promotion_requests()
    except Exception as e:
        pr = pd.DataFrame()
        st.error(f"Could not load promotion requests: {e}")
    if pr.empty:
        st.caption("No promotion requests. Business users can submit them from the Ask page.")
    else:
        for _, r in pr.iterrows():
            with st.container(border=True):
                st.markdown(f"**Key:** `{r['key']}`")
                st.caption(f"{int(r['distinct_users'])} distinct users · {int(r['request_count'])} requests")
                st.markdown(f"> {r['sample_value']}")
                cols = st.columns([0.4, 0.25, 0.35])
                with cols[0]:
                    new_term = st.text_input("Glossary term", value=r['key'].replace("_"," ").title(), key=f"t_{r['key']}")
                with cols[1]:
                    if st.button("Approve", key=f"ap_{r['key']}", type="primary"):
                        fw.promote_memory_to_semantic(r['key'], new_term, str(r['sample_value']))
                        st.success("Promoted")
                        st.rerun()
                with cols[2]:
                    st.button("Reject", key=f"rj_{r['key']}")

    st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">All user memory (by key)</div>', unsafe_allow_html=True)
    m = s.memory()
    if not m.empty:
        agg = (m.groupby('key')
                 .agg(users=('user_id', 'nunique'), entries=('id','count'),
                      sample=('value','first'))
                 .sort_values('users', ascending=False)
                 .reset_index())
        st.dataframe(agg, use_container_width=True, hide_index=True)
    else:
        st.caption("No user memory yet.")

# --- QUERY FEED ------------------------------------------------------------
with tab_feed:
    st.markdown('<div class="section-title">Recent business-user questions</div>', unsafe_allow_html=True)
    log = s.query_log(50)
    if log.empty:
        st.caption("No queries yet.")
    else:
        display = log[['created_at','user_id','question_text','path_taken','confidence_score','agent_used','success']]
        st.dataframe(display, use_container_width=True, hide_index=True)
