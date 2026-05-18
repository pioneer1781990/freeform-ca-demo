"""CSS for the Streamlit app. Two themes: Gemini-Enterprise (Ask) and BQ-Studio (Studio)."""

GEMINI_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans+Text:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
  font-family: 'Google Sans Text', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Hide default Streamlit chrome */
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }   /* hide auto page list */
.stApp > div:first-child > div:first-child > div:first-child { padding-top: 0 !important; }

/* Main app background */
.stApp { background: #ffffff; }
.main .block-container { background: #ffffff; padding-top: 1rem; max-width: 1100px; }

/* Bottom input bar — undo Streamlit dark wrapper */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] {
  background: #ffffff !important;
  border-top: 1px solid #e8eaed !important;
}
[data-testid="stChatInput"] {
  background: #ffffff !important;
  border: 1px solid #d2e3fc !important;
  border-radius: 24px !important;
  box-shadow: 0 1px 3px rgba(60,64,67,.08) !important;
}
[data-testid="stChatInputTextArea"], [data-testid="stChatInput"] textarea {
  background: #ffffff !important;
  font-family: 'Google Sans Text','Inter',sans-serif !important;
  font-size: 15px !important;
  color: #1f1f1f !important;
}

/* Sidebar — Gemini Enterprise style */
section[data-testid="stSidebar"] {
  background: #f4f7fb !important;
  border-right: 1px solid #e8eaed;
  padding-top: 16px;
}
section[data-testid="stSidebar"] .block-container { padding-top: 0.5rem; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
  font-weight: 500; color: #1f1f1f;
}
/* Sidebar "+ New" button to match Gemini soft blue */
section[data-testid="stSidebar"] .stButton > button {
  background: #e8f0fe !important;
  color: #1f1f1f !important;
  border: 1px solid #d2e3fc !important;
  border-radius: 24px !important;
  font-weight: 500 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  background: #d2e3fc !important;
}

/* Suggestion chips in main area — STYLE BUTTONS as pill chips */
.main .stButton > button {
  background: #ffffff !important;
  color: #1f1f1f !important;
  border: 1px solid #dadce0 !important;
  border-radius: 999px !important;
  padding: 10px 22px !important;
  font-size: 14px !important;
  font-weight: 400 !important;
  min-height: 0 !important;
  height: auto !important;
}
.main .stButton > button:hover {
  background: #f1f3f4 !important;
  border-color: #c5c8cc !important;
}

/* Centered greeting */
.greeting-hero {
  text-align: center;
  margin-top: 60px;
  margin-bottom: 32px;
}
.greeting-hero h1 {
  font-size: 48px;
  font-weight: 400;
  background: linear-gradient(120deg, #4285f4 0%, #9b72f4 50%, #d96570 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}
.greeting-hero p {
  color: #b0b6bd;
  font-size: 28px;
  font-weight: 300;
  margin: 8px 0 0 0;
}

/* Suggestion chips */
.suggest-row {
  display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;
  margin: 24px auto 0; max-width: 720px;
}
.suggest-chip {
  display: inline-block; padding: 10px 20px;
  border: 1px solid #dadce0; border-radius: 999px;
  font-size: 14px; color: #1f1f1f; background: #fff;
  cursor: pointer; user-select: none;
}
.suggest-chip:hover { background: #f1f3f4; border-color: #cdd1d6; }

/* Chat bubbles */
.user-msg {
  background: #e8f0fe; color: #1f1f1f;
  padding: 10px 16px; border-radius: 18px 18px 4px 18px;
  margin: 18px 0 6px auto; max-width: 70%; width: fit-content;
  font-size: 14px; line-height: 1.5;
}
.assist-row { display: flex; gap: 14px; align-items: flex-start; margin: 12px 0 4px; }
.assist-sparkle {
  flex: 0 0 28px; width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg,#4285f4,#9b72f4); color: white;
  display: grid; place-items: center; font-size: 14px; margin-top: 2px;
}
.assist-body { flex: 1 1 auto; color: #1f1f1f; font-size: 15px; line-height: 1.65; }
.assist-narrative { padding-right: 24px; }
.assist-narrative p { margin: 0 0 12px 0; }
.assist-narrative strong { font-weight: 600; color: #1f1f1f; }
.assist-narrative h1, .assist-narrative h2, .assist-narrative h3 {
  font-weight: 500; margin: 16px 0 8px; font-size: 16px;
}

/* Slim footer line under answer */
.answer-meta {
  font-size: 12px; color: #80868b;
  margin: 12px 0 6px 42px;
}

/* Inline citation chip row */
.cite-summary {
  font-size: 12px; color: #5f6368;
  margin: 8px 0 4px 42px;
  line-height: 1.9;
}
.cite-summary .chip {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 500; margin: 0 4px 0 0;
  border: 1px solid #e8eaed; background: #f8f9fa; color: #3c4043;
}
.cite-summary .chip-agent { background: #e6f4ea; color: #137333; border-color: #c8e6d0; }
.cite-summary .chip-gloss { background: #e8f0fe; color: #1967d2; border-color: #d2e3fc; }
.cite-summary .chip-mem   { background: #fef7e0; color: #b06000; border-color: #fcdd9c; }
.cite-summary .chip-vq    { background: #f3e8ff; color: #6f3ec1; border-color: #e0cffc; }
.cite-summary .chip-tbl   { background: #f8f9fa; color: #5f6368; border-color: #e8eaed; }

/* Slim promote banner — replaces big bordered card */
.promote-banner {
  background: linear-gradient(90deg,#fff8e1 0%, #fffaf0 100%);
  border: 1px solid #fde2a2;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px; color: #5f4300;
  margin: 12px 0 0 42px;
}
.promote-banner .promote-dot { color: #f9ab00; margin-right: 6px; }

/* Smaller action buttons (👍 👎 ⟳) */
.main .stButton > button[kind="secondary"]:has(div p:contains("👍")),
.main .stButton > button[kind="secondary"]:has(div p:contains("👎")),
.main .stButton > button[kind="secondary"]:has(div p:contains("⟳")) {
  padding: 4px 10px !important; min-height: 32px !important; min-width: 0 !important;
  font-size: 13px !important;
}

/* Tighter dataframes under narrative */
.assist-row + div [data-testid="stDataFrame"] {
  margin: 4px 0 0 42px !important;
  max-width: calc(100% - 42px);
}
.assist-body .badge {
  display: inline-block; font-size: 11px; color: #5f6368;
  padding: 2px 8px; border-radius: 8px; background: #f1f3f4;
  border: 1px solid #e8eaed; margin-right: 6px; vertical-align: middle;
}
.assist-body .badge-agent { background: #e6f4ea; color: #137333; border-color: #c8e6d0; }
.assist-body .badge-freelance { background: #fef7e0; color: #b06000; border-color: #fcdd9c; }
.assist-body .badge-refuse { background: #fce8e6; color: #c5221f; border-color: #fbcfcb; }
.assist-body .badge-asking { background: #e8f0fe; color: #1967d2; border-color: #d2e3fc; }

.thinking-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: #5f6368; cursor: pointer;
  padding: 6px 0; border: 0; background: transparent;
}

/* Citation chips inline in narrative */
.cite-chip {
  display: inline-block; padding: 1px 7px; border-radius: 8px;
  font-size: 11px; line-height: 1.4;
  background: #e8f0fe; color: #1967d2; margin: 0 2px;
  border: 1px solid #d2e3fc; vertical-align: middle;
}

/* Context card */
.ctx-card {
  border: 1px solid #e8eaed; border-radius: 12px; padding: 14px 16px;
  background: #fafbfc; margin-bottom: 10px;
}
.ctx-card-title { font-size: 13px; font-weight: 600; color: #1f1f1f; margin-bottom: 6px; }
.ctx-card-kind { font-size: 11px; color: #5f6368; text-transform: uppercase; letter-spacing: .04em; }
.ctx-card-detail { font-size: 14px; color: #3c4043; }
.ctx-card .convergence { font-size: 13px; color: #b06000; margin-top: 8px; }

/* Bottom input */
div[data-testid="stChatInput"] {
  border: 1px solid #d2e3fc !important;
  border-radius: 22px !important;
  box-shadow: 0 1px 3px rgba(60,64,67,.08);
}
div[data-testid="stChatInput"] textarea {
  font-family: 'Google Sans Text','Inter',sans-serif !important;
  font-size: 15px !important;
}

/* Tables */
[data-testid="stDataFrame"] {
  border: 1px solid #e8eaed; border-radius: 8px; overflow: hidden;
}

/* Primary buttons */
.stButton > button[kind="primary"] {
  background: #1a73e8 !important; border-color: #1a73e8 !important;
  border-radius: 999px !important;
  font-weight: 500 !important;
}
</style>
"""

BQ_STUDIO_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans+Text:wght@400;500;700&family=Roboto+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
  font-family: 'Google Sans Text', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: #202124;
}

header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }

.stApp { background: #ffffff; }

section[data-testid="stSidebar"] {
  background: #ffffff !important;
  border-right: 1px solid #dadce0;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
  font-weight: 500;
}

/* BQ Studio top bar */
.bq-top {
  background: #fff; border-bottom: 1px solid #dadce0;
  padding: 10px 16px; display: flex; align-items: center; gap: 12px;
  font-size: 14px;
}
.bq-top .logo { font-weight: 500; color: #5f6368; }
.bq-top .project-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border: 1px solid #dadce0; border-radius: 4px;
  background: #fff;
}
.bq-top .search-bar {
  flex: 1; max-width: 720px; margin: 0 auto;
  background: #f1f3f4; border-radius: 8px; padding: 8px 14px;
  color: #5f6368; font-size: 13px;
}

/* Page heading like agent catalogue */
.bq-page-title { font-size: 24px; font-weight: 500; color: #202124; margin: 12px 0 4px; }
.bq-page-sub   { font-size: 14px; color: #5f6368; margin-bottom: 24px; }
.bq-section-title { font-size: 15px; font-weight: 500; color: #202124; margin: 8px 0 12px; }

/* Force light mode on all interactive widgets in Studio */
[data-testid="stDataFrame"], [data-testid="stDataFrame"] * {
  background: #ffffff !important; color: #1f1f1f !important;
}
[data-testid="stDataFrame"] thead { background: #f1f3f4 !important; }
[data-testid="stExpander"] {
  border: 1px solid #e8eaed !important; background: #ffffff !important;
}
[data-testid="stExpander"] * { color: #1f1f1f !important; }

[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
  background: #ffffff !important; color: #1f1f1f !important;
  border: 1px solid #dadce0 !important;
}
[data-testid="stStatusWidget"], [data-testid="stStatus"] {
  background: #f8fafd !important; color: #1f1f1f !important;
}
[data-testid="stStatusWidget"] * { color: #1f1f1f !important; }

/* Tabs */
[data-baseweb="tab-list"] { border-bottom: 1px solid #dadce0 !important; }
[data-baseweb="tab"] { color: #5f6368 !important; }
[data-baseweb="tab"][aria-selected="true"] { color: #1a73e8 !important; }

/* Tab strip */
.bq-tabs {
  display: flex; gap: 4px; border-bottom: 1px solid #dadce0;
  margin-bottom: 16px;
}
.bq-tab {
  padding: 10px 18px; border: 1px solid #dadce0; border-bottom: 0;
  background: #f8f9fa; border-radius: 8px 8px 0 0;
  font-size: 13px; color: #5f6368; cursor: pointer;
}
.bq-tab.active { background: #fff; color: #1a73e8; font-weight: 500; }

/* Cards (recommendations / agents) */
.bq-card {
  border: 1px solid #dadce0; border-radius: 8px; padding: 16px;
  background: #fff; margin-bottom: 12px;
}
.bq-card-title { font-size: 14px; font-weight: 500; color: #202124; display: flex; align-items: center; gap: 8px; }
.bq-card-detail { font-size: 13px; color: #5f6368; margin-top: 6px; }

/* Card avatar circles (pastel) */
.bq-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: inline-grid; place-items: center;
  font-size: 14px; font-weight: 500; color: white;
  margin-right: 8px;
}
.av-teal { background: #94d9d3; color: #0d6e63; }
.av-orange { background: #f6c6a2; color: #a45c1d; }
.av-red { background: #f9c2bf; color: #b3261e; }
.av-yellow { background: #fde293; color: #936a14; }
.av-blue { background: #aecbfa; color: #1a4ba0; }
.av-purple { background: #cab5f5; color: #5d3fb5; }
.av-pink { background: #f9b3d4; color: #a33b6c; }

/* Status bar / breadcrumb */
.bq-status {
  font-size: 12px; color: #5f6368;
  border-top: 1px solid #e8eaed; padding: 8px 16px;
  background: #fafbfc; margin-top: 24px;
}

/* SQL code blocks */
pre, code, .stCode {
  font-family: 'Roboto Mono', monospace !important;
  font-size: 13px !important;
}

/* Buttons in BQ blue */
.stButton > button[kind="primary"] {
  background: #1a73e8 !important; border-color: #1a73e8 !important;
  border-radius: 4px !important;
  font-weight: 500 !important;
}
.stButton > button:not([kind="primary"]) {
  border-color: #dadce0 !important; color: #1a73e8 !important;
  border-radius: 4px !important;
}
</style>
"""
