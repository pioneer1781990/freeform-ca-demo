"""Analyst view — BQ Studio styled flywheel dashboard."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings; warnings.filterwarnings("ignore")
import streamlit as st
import pandas as pd

from styles import BQ_STUDIO_CSS
from core import substrate, flywheel, session as sess
import config as cfg

st.set_page_config(page_title="Studio", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")
st.markdown(BQ_STUDIO_CSS, unsafe_allow_html=True)
sess.start_if_missing()

s  = substrate.get()
fw = flywheel.get()

# --- Top bar (BQ-style) ---------------------------------------------------
st.markdown(f"""
<div class="bq-top">
  <span class="logo">Google Cloud</span>
  <span class="project-pill">📦 {cfg.PROJECT_ID}</span>
  <span class="search-bar">🔍&nbsp;&nbsp;Search (/) for resources, docs, products and more</span>
  <span style="font-size:18px;color:#1a73e8;">✦</span>
</div>
""", unsafe_allow_html=True)

# --- Sidebar (Explorer-style) ---------------------------------------------
with st.sidebar:
    st.markdown('<div style="font-weight:500;color:#202124;margin:0 0 8px;">Studio</div>', unsafe_allow_html=True)
    st.markdown('<div class="explorer-rail-icon">📊</div>', unsafe_allow_html=True)

    st.text_input("Search BigQuery resources", key="exp_search", label_visibility="collapsed",
                  placeholder="🔎 Search BigQuery resources")
    with st.expander(f"📁 {cfg.PROJECT_ID}", expanded=True):
        with st.expander(f"📁 {cfg.DATASET}", expanded=True):
            st.caption("Models (1)")
            st.markdown('• gemini_model')
            st.caption("Tables")
            for t in s.agent_ready_tables()[:12]:
                st.markdown(f'• {t}')
            with st.expander("non-agent-ready", expanded=False):
                for t in s.non_agent_ready_tables():
                    st.markdown(f'• {t}')

# --- Page header ----------------------------------------------------------
st.markdown('<div class="bq-page-title">Cymbal Retail — Agent Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="bq-page-sub">Manage data agents, curate the glossary, and act on flywheel recommendations. '
            'Built with <span style="color:#1a73e8;">✦ Gemini</span></div>', unsafe_allow_html=True)

tab_recs, tab_agents, tab_glossary, tab_memory, tab_feed = st.tabs(
    ["📋 Recommendations", "🤖 Agents", "📖 Glossary", "🧠 Memory", "📜 Query feed"])

# --- RECOMMENDATIONS ------------------------------------------------------
with tab_recs:
    # Session activity summary at top
    q_count = fw.session_question_count()
    cols = st.columns([0.6, 0.2, 0.2])
    with cols[0]:
        st.markdown(f"<div class='bq-section-title'>Live signals from this session "
                    f"&nbsp;·&nbsp;<span style='color:#5f6368;font-weight:400;'>{q_count} questions asked</span></div>",
                    unsafe_allow_html=True)
    with cols[1]:
        if st.button("🔁 Check for signals", use_container_width=True):
            st.session_state["show_recs"] = True
    with cols[2]:
        if st.button("Reset session", use_container_width=True):
            sess.reset(); st.session_state["show_recs"] = False; st.rerun()

    if not st.session_state.get("show_recs"):
        st.markdown('<div style="margin-top:24px;padding:36px;text-align:center;'
                    'border:1px dashed #dadce0;border-radius:12px;color:#5f6368;">'
                    '<div style="font-size:14px;">No recommendations yet.</div>'
                    '<div style="font-size:13px;margin-top:6px;">'
                    'Ask a few questions on the <b>Ask</b> page, then click <b>Check for signals</b> '
                    'to surface what the flywheel found.</div></div>',
                    unsafe_allow_html=True)
    else:
        col1, col2 = st.columns([0.55, 0.45])
        with col1:
            st.markdown('<div class="bq-section-title">🤖 Recommended new agents</div>', unsafe_allow_html=True)
            proposals = fw.agent_proposals(only_session=True, min_count=3)
            if not proposals:
                st.info("No new agent clusters detected this session.")
            for p in proposals[:3]:
                with st.container(border=True):
                    st.markdown(f"**{p['name']} Agent**")
                    st.caption(p['evidence'])
                    st.markdown(f"Tables in scope: `{', '.join(p['tables_in_scope'])}`")
                    with st.expander("Suggested system instruction", expanded=False):
                        st.write(p['system_instruction'])
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Review & publish", key=f"pub_{p['suggested_id']}", type="primary"):
                            with st.spinner(f"Publishing {p['name']} Agent to CA API..."):
                                ok = fw.publish_agent(
                                    agent_id=p['suggested_id'], name=p['name'],
                                    description=p['description'],
                                    tables_in_scope=p['tables_in_scope'],
                                    glossary_terms=p['glossary_terms'],
                                    system_instruction=p['system_instruction'],
                                )
                            st.success(f"Published ({'CA API ok' if ok else 'CA failed — registered as draft'})")
                            st.rerun()
                    with cc2:
                        st.button("Dismiss", key=f"dis_{p['suggested_id']}")

            st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="bq-section-title">📊 Recommended graph edges</div>', unsafe_allow_html=True)
            ge_props = fw.graph_edge_proposals()
            if not ge_props:
                st.caption("No graph edge proposals based on current activity.")
            for ge in ge_props[:3]:
                with st.container(border=True):
                    st.markdown(f"**{ge['left']} ↔ {ge['right']}**")
                    st.caption(f"Joined together in {ge['co_count']} queries")
                    st.button("Add to graph", key=f"ge_{ge['suggested_edge']}", type="primary")

        with col2:
            st.markdown('<div class="bq-section-title">📝 Prep recommendations</div>', unsafe_allow_html=True)
            desc_recs = fw.description_prep_recs()
            gl_recs   = fw.glossary_prep_recs()
            if not desc_recs and not gl_recs:
                st.caption("No prep recommendations based on current activity.")
            for r in desc_recs[:4]:
                with st.container(border=True):
                    st.markdown(f"⚠️ **Add descriptions: `{r['target_table']}`**")
                    st.caption(r['detail'])
                    if st.button("Generate & apply", key=f"desc_{r['target_table']}", type="primary"):
                        st.info("Would call Gemini to draft descriptions then ALTER TABLE")
            for r in gl_recs[:3]:
                with st.container(border=True):
                    st.markdown(f"📖 **Define glossary term: `{r['term']}`**")
                    st.caption(r['detail'])
                    if st.button("Define term", key=f"gl_{r['term']}", type="primary"):
                        st.session_state["define_term"] = r['term']

# --- AGENTS -----------------------------------------------------------------
with tab_agents:
    st.markdown('<div class="bq-section-title">Agent catalogue</div>', unsafe_allow_html=True)
    agents = s.agents()
    if agents.empty:
        st.info("No agents published yet.")
    else:
        # Dedupe by agent_id (newest)
        agents = agents.sort_values('created_at', ascending=False).drop_duplicates('agent_id', keep='first')
        published = agents[agents['status'] == 'published']
        cols = st.columns(min(3, max(1, len(published))))
        AVATAR = ["av-teal","av-orange","av-blue","av-purple","av-pink","av-yellow"]
        for i, (_, a) in enumerate(published.iterrows()):
            with cols[i % len(cols)]:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'<span class="bq-avatar {AVATAR[i % len(AVATAR)]}">{a["name"][0]}</span>'
                        f'<div><div style="font-weight:500;">{a["name"]}</div>'
                        f'<div style="font-size:11px;color:#5f6368;">{a["agent_id"]}</div></div></div>',
                        unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:13px;color:#5f6368;margin-top:8px;'>{a.get('description','')}</div>",
                                unsafe_allow_html=True)
                    tbls = list(a['tables_in_scope']) if a['tables_in_scope'] is not None else []
                    st.caption(f"Tables: {', '.join(tbls)}")
                    gts = list(a['glossary_terms']) if a['glossary_terms'] is not None else []
                    st.caption(f"Glossary: {', '.join(gts) if gts else '(none)'}")

# --- GLOSSARY ---------------------------------------------------------------
with tab_glossary:
    st.markdown('<div class="bq-section-title">Business glossary</div>', unsafe_allow_html=True)
    g = s.glossary()
    if g.empty:
        st.info("Glossary is empty. Add a term below or accept a 'Define term' prep recommendation.")
    else:
        for _, term in g.iterrows():
            with st.container(border=True):
                cols = st.columns([0.3, 0.5, 0.2])
                with cols[0]:
                    st.markdown(f"**{term['term']}**")
                    st.caption(f"source: {term.get('source','')}")
                with cols[1]:
                    st.markdown(term['definition'])
                with cols[2]:
                    if term.get('linked_table'):
                        st.caption(f"`{term['linked_table']}`")

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

# --- MEMORY -----------------------------------------------------------------
with tab_memory:
    st.markdown('<div class="bq-section-title">Memory promotion queue</div>', unsafe_allow_html=True)
    pr = fw.list_promotion_requests()
    if pr.empty:
        st.info("No promotion requests yet. Business users can submit them from the Ask page.")
    else:
        for _, r in pr.iterrows():
            with st.container(border=True):
                st.markdown(f"**Key:** `{r['key']}`")
                st.caption(f"{int(r['distinct_users'])} distinct users · {int(r['request_count'])} requests")
                st.markdown(f"> {r['sample_value']}")
                cols = st.columns([0.4, 0.3, 0.3])
                with cols[0]:
                    new_term = st.text_input("Glossary term", value=r['key'].replace("_"," ").title(), key=f"t_{r['key']}")
                with cols[1]:
                    if st.button("Approve & promote", key=f"ap_{r['key']}", type="primary"):
                        fw.promote_memory_to_semantic(r['key'], new_term, str(r['sample_value']))
                        st.success("Promoted to semantic glossary")
                        st.rerun()
                with cols[2]:
                    st.button("Reject", key=f"rj_{r['key']}")

    st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="bq-section-title">All user memory (by key)</div>', unsafe_allow_html=True)
    m = s.memory()
    if not m.empty:
        agg = (m.groupby('key')
                 .agg(users=('user_id', 'nunique'), entries=('id','count'),
                      sample=('value','first'))
                 .sort_values('users', ascending=False)
                 .reset_index())
        st.dataframe(agg, use_container_width=True, hide_index=True)

# --- QUERY FEED -------------------------------------------------------------
with tab_feed:
    st.markdown('<div class="bq-section-title">Recent business-user questions</div>', unsafe_allow_html=True)
    log = s.query_log(50)
    if log.empty:
        st.info("No queries yet.")
    else:
        display = log[['created_at','user_id','question_text','path_taken','confidence_score','agent_used','success']]
        st.dataframe(display, use_container_width=True, hide_index=True)

# --- Status bar -------------------------------------------------------------
st.markdown(f'<div class="bq-status">Project: {cfg.PROJECT_ID} · Location: {cfg.BQ_LOCATION} · Dataset: {cfg.DATASET} · Bytes processed: {len(s.query_log(50))*4} KB · Cache hit: 87%</div>', unsafe_allow_html=True)
