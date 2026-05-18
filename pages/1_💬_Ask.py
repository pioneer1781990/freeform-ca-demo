"""Business User view — Gemini Enterprise styled chat over the data agents."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings; warnings.filterwarnings("ignore")
import pandas as pd
import streamlit as st

from styles import GEMINI_CSS
from core import orchestrator, flywheel, substrate
from core.output_contract import Answer

st.set_page_config(page_title="Ask", page_icon="✦", layout="wide", initial_sidebar_state="expanded")
st.markdown(GEMINI_CSS, unsafe_allow_html=True)

# --- session state init ---------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "user_id" not in st.session_state:
    st.session_state.user_id = "siya"
if "user_name" not in st.session_state:
    st.session_state.user_name = "Siya"

# --- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding:4px 8px 16px;">'
        '<span style="font-size:22px;background:linear-gradient(135deg,#4285f4,#9b72f4);'
        '-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">✦</span>'
        '<span style="font-weight:500;font-size:15px;color:#1f1f1f;">Gemini Enterprise</span>'
        '</div>', unsafe_allow_html=True)
    if st.button("＋  New", use_container_width=True, key="newchat"):
        st.session_state.history = []
        st.rerun()
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item">🔍 &nbsp;Search</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item">⭐ &nbsp;Starred</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item">✨ &nbsp;Agents</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:24px;border-top:1px solid #e8eaed;margin:12px -16px 12px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-section">RECENT TASKS</div>', unsafe_allow_html=True)
    if st.session_state.history:
        for msg in [m for m in st.session_state.history if m["role"]=="user"][-6:]:
            st.markdown(
                f'<div class="recent-item">{msg["content"][:42]}</div>',
                unsafe_allow_html=True)

    st.markdown('<div style="height:32px"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:linear-gradient(135deg,#e8f0fe 0%,#f3e8ff 50%,#fce4ec 100%);
                border-radius:12px;padding:14px;font-size:13px;color:#1f1f1f;">
      <div style="font-weight:500;margin-bottom:8px;">Tips to get started</div>
      <div style="padding:3px 0;">• Get answers from your data ›</div>
      <div style="padding:3px 0;">• Try a predefined prompt ›</div>
      <div style="padding:3px 0;">• Try an agent ›</div>
      <div style="padding:3px 0;">• Personalize your experience ›</div>
    </div>
    """, unsafe_allow_html=True)

# --- helpers ---------------------------------------------------------------
def _path_badge(path: str) -> str:
    if path == "agent_route": return '<span class="badge badge-agent">via agent</span>'
    if path == "freelance":   return '<span class="badge badge-freelance">freelance</span>'
    return '<span class="badge badge-refuse">refused</span>'

def _agent_label(agent_id):
    if not agent_id: return "no agent"
    return {"cymbal_sales_agent": "Sales Analytics",
            "cymbal_cx_agent":    "Customer Experience"}.get(agent_id, agent_id)

def _render_context_block(ans: Answer):
    """Details expander — only opens if user wants to inspect. Compact rows."""
    if not ans.citations: return
    by_kind: dict = {}
    for c in ans.citations:
        by_kind.setdefault(c.kind, []).append(c)
    with st.expander(f"View details ({len(ans.citations)} sources, SQL, raw payload)", expanded=False):
        # SQL
        if ans.sql:
            st.markdown('<div class="ctx-kind">SQL</div>', unsafe_allow_html=True)
            st.code(ans.sql, language="sql")
        # Citations grouped
        order = ["agent_rule", "glossary", "memory", "verified_query", "table"]
        kind_label = {"agent_rule":"Agent rules",
                      "glossary":"Glossary terms applied",
                      "memory":"Your memory",
                      "verified_query":"Verified query template",
                      "table":"Tables queried"}
        for kind in order:
            items = by_kind.get(kind)
            if not items: continue
            html = f'<div class="ctx-kind">{kind_label[kind]}</div>'
            for c in items:
                html += f'<div class="ctx-row"><span class="ctx-label">{c.label}</span><span class="ctx-detail">{c.detail}</span></div>'
            st.markdown(html, unsafe_allow_html=True)
            for c in items:
                if kind == "memory" and c.extra.get("convergence_count"):
                    st.markdown(f'<div class="convergence">👉 {c.extra["convergence_count"]} people share this correction</div>', unsafe_allow_html=True)

def _render_answer(ans: Answer, msg_idx: int):
    """Clean Gemini-style assistant message.
    Layout: sparkle avatar + narrative (top), then data, then a single slim
    footer row with: meta · 👍 👎 ⟳ · context · SQL."""

    # --- needs_definition: minimal, conversational ---
    if ans.path_taken == "needs_definition":
        st.markdown(
            f'<div class="assist-row">'
            f'  <div class="assist-sparkle">✦</div>'
            f'  <div class="assist-body assist-narrative">{ans.narrative}</div>'
            f'</div>', unsafe_allow_html=True)
        term = ans.needs_definition or "this term"
        defn = st.text_input(
            f"Define {term}",
            key=f"def_{msg_idx}",
            placeholder=f"{term} = …",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([0.15, 0.85])
        with c1:
            if st.button("Save & answer", key=f"defsave_{msg_idx}", type="primary"):
                if defn.strip():
                    flywheel.get().save_user_definition(term, defn.strip(),
                        st.session_state.user_id, ans.question)
                    st.session_state["pending_q"] = ans.question
                    st.rerun()
        return

    # --- assistant row: sparkle + narrative as a single flowing block ---
    # Thinking shows ABOVE the narrative as a slim accordion (Gemini-style)
    sparkle_col, body_col = st.columns([0.04, 0.96])
    with body_col:
        if ans.thinking:
            with st.expander("Show thinking", expanded=False):
                st.write(ans.thinking)

        st.markdown(
            f'<div class="assist-row">'
            f'  <div class="assist-sparkle">✦</div>'
            f'  <div class="assist-body assist-narrative">{ans.narrative}</div>'
            f'</div>', unsafe_allow_html=True)

        # Results table flows under narrative
        if ans.rows:
            df = pd.DataFrame(ans.rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Slim promotion banner (single line, not boxed)
        if ans.suggest_promote_key:
            cols = st.columns([0.78, 0.22])
            with cols[0]:
                st.markdown(
                    '<div class="promote-banner">'
                    '<span class="promote-dot">●</span> Your personal definition was used. '
                    'Share it with your team so others get the same answer.'
                    '</div>', unsafe_allow_html=True)
            with cols[1]:
                if st.button("Promote to team", key=f"prom_{msg_idx}", type="primary"):
                    flywheel.get().request_memory_promotion(ans.suggest_promote_key,
                                                            st.session_state.user_id)
                    st.toast("Sent for analyst review")

        # --- Slim footer: meta + actions in ONE row ---
        meta_html = _meta_line(ans)
        st.markdown(f'<div class="answer-meta">{meta_html}</div>', unsafe_allow_html=True)

        qid = ans.verification_token
        action_cols = st.columns([0.05, 0.05, 0.05, 0.85])
        with action_cols[0]:
            if st.button("👍", key=f"up_{msg_idx}", help="Helpful"):
                flywheel.get().record_feedback(qid, "up", None, st.session_state.user_id)
                st.toast("Thanks")
        with action_cols[1]:
            if st.button("👎", key=f"dn_{msg_idx}", help="Not helpful"):
                st.session_state[f"correction_open_{msg_idx}"] = True
        with action_cols[2]:
            if st.button("⟳", key=f"rg_{msg_idx}", help="Regenerate"):
                st.toast("Regenerate coming soon")

        if st.session_state.get(f"correction_open_{msg_idx}"):
            corr = st.text_input(
                "Tell me what's wrong",
                key=f"corr_{msg_idx}",
                placeholder="e.g. active customer should use 60 days, not 90",
                label_visibility="collapsed",
            )
            sc1, sc2 = st.columns([0.15, 0.85])
            with sc1:
                if st.button("Save", key=f"sv_{msg_idx}", type="primary"):
                    if corr.strip():
                        flywheel.get().record_feedback(qid, "down", corr.strip(), st.session_state.user_id)
                        st.session_state[f"correction_open_{msg_idx}"] = False
                        st.toast("Saved to your memory")
                        st.rerun()

        # Inline citation summary + the deeper context expander
        if ans.citations:
            chips = _citation_chips(ans.citations)
            st.markdown(f'<div class="cite-summary">Sources: {chips}</div>', unsafe_allow_html=True)
        _render_context_block(ans)

def _meta_line(ans: Answer) -> str:
    path_text = {"agent_route":"via agent","freelance":"freelance","refuse":"refused"}.get(ans.path_taken,"")
    agent = _agent_label(ans.agent_used) if ans.agent_used else None
    parts = [path_text]
    if agent and agent != "no agent": parts.append(agent)
    parts.append(f"{int(ans.confidence*100)}% confidence")
    if ans.latency_ms: parts.append(f"{ans.latency_ms/1000:.1f}s")
    return " · ".join(parts)

def _citation_chips(citations) -> str:
    kind_color = {"agent_rule":"agent","glossary":"gloss","memory":"mem",
                  "verified_query":"vq","table":"tbl"}
    seen = set(); out = []
    for c in citations:
        cls = kind_color.get(c.kind, "chip")
        key = (c.kind, c.label)
        if key in seen: continue
        seen.add(key)
        label = c.label[:40]
        out.append(f'<span class="chip chip-{cls}">{label}</span>')
    return "".join(out)

# --- empty state -----------------------------------------------------------
if not st.session_state.history:
    st.markdown(
        f'<div class="greeting-hero">'
        f'  <h1>Hello, {st.session_state.user_name}</h1>'
        f'  <p>Gemini for Cymbal Retail</p>'
        f'</div>',
        unsafe_allow_html=True)

    suggestions = [
        "What was our revenue last month?",
        "How many active customers do we have?",
        "Top 10 products by revenue this quarter",
        "Which products are at stockout risk?",
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

prompt = st.chat_input("Ask anything, search your data, @mention or /tools")
if "pending_q" in st.session_state:
    prompt = st.session_state.pop("pending_q")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    st.markdown(f'<div class="user-msg">{prompt}</div>', unsafe_allow_html=True)
    # Slim, non-intrusive status that auto-collapses on completion
    status = st.status("✦ Thinking…", expanded=False)
    with status:
        ans = orchestrator.get().answer(prompt, user_id=st.session_state.user_id)
    status.update(label="✦ Done", state="complete", expanded=False)
    st.session_state.history.append({"role": "assistant", "answer": ans, "content": ans.narrative})
    st.rerun()
