"""Business User view — clean chat over the data agents."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings; warnings.filterwarnings("ignore")
import pandas as pd
import streamlit as st

from styles import ASK_CSS
from core import orchestrator, flywheel
from core.output_contract import Answer

st.set_page_config(page_title="Ask", page_icon="💬", layout="wide", initial_sidebar_state="expanded")
st.markdown(ASK_CSS, unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []
if "user_id" not in st.session_state:
    st.session_state.user_id = "siya"
if "user_name" not in st.session_state:
    st.session_state.user_name = "Siya"

# --- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.markdown('<div style="font-size:18px;font-weight:600;color:#111827;padding:4px 0 16px;">💬 Ask</div>',
                unsafe_allow_html=True)
    if st.button("＋ New conversation", use_container_width=True, key="newchat"):
        st.session_state.history = []
        st.rerun()
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#6b7280;letter-spacing:.04em;text-transform:uppercase;padding:4px 0 8px;">Recent</div>',
                unsafe_allow_html=True)
    if st.session_state.history:
        for msg in [m for m in st.session_state.history if m["role"]=="user"][-6:]:
            st.markdown(
                f'<div style="font-size:13px;color:#374151;padding:5px 4px;text-overflow:ellipsis;'
                f'overflow:hidden;white-space:nowrap;">{msg["content"][:45]}</div>',
                unsafe_allow_html=True)
    st.markdown('<div style="height:32px"></div>', unsafe_allow_html=True)
    st.page_link("pages/2_⚙️_Studio.py", label="🛠  Open Studio", icon=None)

# --- helpers ---------------------------------------------------------------
def _agent_label(agent_id):
    if not agent_id: return "no agent"
    return {"cymbal_sales_agent": "Sales Analytics",
            "cymbal_cx_agent":    "Customer Experience"}.get(agent_id, agent_id)

def _path_badge(path: str) -> str:
    if path == "agent_route":      return '<span class="badge badge-agent">via agent</span>'
    if path == "freelance":        return '<span class="badge badge-freelance">freelance</span>'
    if path == "refuse":           return '<span class="badge badge-refuse">refused</span>'
    if path == "needs_definition": return '<span class="badge badge-asking">needs your input</span>'
    return f'<span class="badge">{path}</span>'

def _meta_line(ans: Answer) -> str:
    parts = []
    if ans.agent_used: parts.append(_agent_label(ans.agent_used))
    parts.append(f"{int(ans.confidence*100)}% confidence")
    if ans.latency_ms: parts.append(f"{ans.latency_ms/1000:.1f}s")
    return " · ".join(parts)

def _citation_chips(citations) -> str:
    color = {"agent_rule":"agent","glossary":"gloss","memory":"mem",
             "verified_query":"vq","table":"tbl"}
    seen, out = set(), []
    for c in citations:
        key = (c.kind, c.label)
        if key in seen: continue
        seen.add(key)
        out.append(f'<span class="chip chip-{color.get(c.kind,"")}">{c.label[:40]}</span>')
    return "".join(out)

# --- inline-definition flow --------------------------------------------
def _render_needs_definition(ans: Answer, msg_idx: int):
    st.markdown('<div class="assist-wrap">', unsafe_allow_html=True)
    st.markdown(f'{_path_badge(ans.path_taken)}', unsafe_allow_html=True)
    st.markdown(f'<div class="assist-narrative">{ans.narrative}</div>', unsafe_allow_html=True)
    term = ans.needs_definition or "this term"
    defn = st.text_area(
        f"Definition of {term}",
        key=f"def_{msg_idx}",
        placeholder=f"e.g. {term} is …",
        height=80,
        label_visibility="collapsed",
    )
    c1, c2 = st.columns([0.18, 0.82])
    with c1:
        if st.button("Save & answer", key=f"defsave_{msg_idx}", type="primary"):
            if defn.strip():
                flywheel.get().save_user_definition(term, defn.strip(),
                    st.session_state.user_id, ans.question)
                st.session_state["pending_q"] = ans.question
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- answer rendering --------------------------------------------------
def _render_answer(ans: Answer, msg_idx: int):
    if ans.path_taken == "needs_definition":
        _render_needs_definition(ans, msg_idx)
        return

    st.markdown('<div class="assist-wrap">', unsafe_allow_html=True)
    st.markdown(f'{_path_badge(ans.path_taken)}', unsafe_allow_html=True)

    if ans.thinking:
        with st.expander("Show reasoning"):
            st.write(ans.thinking)

    st.markdown(f'<div class="assist-narrative">{ans.narrative}</div>',
                unsafe_allow_html=True)

    if ans.rows:
        df = pd.DataFrame(ans.rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Promote banner (if user's personal definition was used)
    if ans.suggest_promote_key:
        cols = st.columns([0.74, 0.26])
        with cols[0]:
            st.markdown(
                '<div class="promote-banner">'
                'Your personal definition was used. Share it with your team so others get the same answer.'
                '</div>', unsafe_allow_html=True)
        with cols[1]:
            if st.button("Promote to team", key=f"prom_{msg_idx}", type="primary"):
                flywheel.get().request_memory_promotion(ans.suggest_promote_key,
                                                        st.session_state.user_id)
                st.toast("Sent for analyst review")

    # Meta line
    st.markdown(f'<div class="answer-meta">{_meta_line(ans)}</div>',
                unsafe_allow_html=True)

    # Actions
    qid = ans.verification_token
    a = st.columns([0.05, 0.05, 0.05, 0.85])
    with a[0]:
        if st.button("👍", key=f"up_{msg_idx}", help="Helpful"):
            flywheel.get().record_feedback(qid, "up", None, st.session_state.user_id)
            st.toast("Thanks")
    with a[1]:
        if st.button("👎", key=f"dn_{msg_idx}", help="Not helpful"):
            st.session_state[f"corr_open_{msg_idx}"] = True
    with a[2]:
        if st.button("⟳", key=f"rg_{msg_idx}", help="Regenerate"):
            st.session_state["pending_q"] = ans.question
            st.rerun()

    if st.session_state.get(f"corr_open_{msg_idx}"):
        corr = st.text_input(
            "What's wrong?",
            key=f"corr_{msg_idx}",
            placeholder="e.g., we use 60 days, not 90",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([0.15, 0.85])
        with c1:
            if st.button("Save", key=f"sv_{msg_idx}", type="primary"):
                if corr.strip():
                    flywheel.get().record_feedback(qid, "down", corr.strip(), st.session_state.user_id)
                    st.session_state[f"corr_open_{msg_idx}"] = False
                    st.toast("Saved to your memory")
                    st.rerun()

    # Citation chips
    if ans.citations:
        st.markdown(f'<div class="cite-summary">Sources: {_citation_chips(ans.citations)}</div>',
                    unsafe_allow_html=True)

    # Details expander (SQL + grouped citations)
    if ans.sql or ans.citations:
        with st.expander("View details (SQL, citations, raw payload)"):
            if ans.sql:
                st.markdown("**Generated SQL**")
                st.code(ans.sql, language="sql")
            if ans.citations:
                st.markdown("**Citations**")
                grouped = {}
                for c in ans.citations:
                    grouped.setdefault(c.kind, []).append(c)
                kind_label = {"agent_rule":"Agent rule",
                              "glossary":"Glossary",
                              "memory":"Memory",
                              "verified_query":"Verified query",
                              "table":"Table"}
                for kind, items in grouped.items():
                    for c in items:
                        st.markdown(f"- **{kind_label.get(kind, kind)} — {c.label}**: {c.detail}")

    st.markdown('</div>', unsafe_allow_html=True)

# --- empty state -----------------------------------------------------------
if not st.session_state.history:
    st.markdown(
        f'<div class="greeting">'
        f'  <h1>Hi {st.session_state.user_name}, what would you like to know?</h1>'
        f'  <p>Ask anything about Cymbal Retail — sales, customers, products, supply chain.</p>'
        f'</div>',
        unsafe_allow_html=True)

    suggestions = [
        "What was our revenue last month?",
        "How many active customers do we have?",
        "Top 10 products by revenue this quarter",
        "Show me damaged-product complaints",
    ]
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        with cols[i]:
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state["pending_q"] = s
                st.rerun()
else:
    for i, msg in enumerate(st.session_state.history):
        if msg["role"] == "user":
            st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            _render_answer(msg["answer"], i)

# --- input -----------------------------------------------------------------
prompt = st.chat_input("Ask anything about your data…")
if "pending_q" in st.session_state:
    prompt = st.session_state.pop("pending_q")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    st.markdown(f'<div class="user-msg">{prompt}</div>', unsafe_allow_html=True)
    status = st.status("Thinking…", expanded=False)
    with status:
        ans = orchestrator.get().answer(prompt, user_id=st.session_state.user_id)
    status.update(label="Done", state="complete", expanded=False)
    st.session_state.history.append({"role": "assistant", "answer": ans, "content": ans.narrative})
    st.rerun()
