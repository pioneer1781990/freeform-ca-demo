"""Minimal, clean CSS for the demo. Light mode. No platform mimicry."""

# Shared base — used on both pages.
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], div, p, span, button, input, textarea {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

:root { color-scheme: light !important; }

/* Hide Streamlit chrome */
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }
#MainMenu { visibility: hidden !important; }

.stApp { background: #fafafa; }

/* Tighten main content */
.main .block-container {
  background: #ffffff;
  padding-top: 2rem;
  padding-bottom: 6rem;
  max-width: 880px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background: #f7f7f8 !important;
  border-right: 1px solid #ececec;
}
section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* Primary button — soft blue */
.stButton > button[kind="primary"] {
  background: #2563eb !important;
  border: 1px solid #2563eb !important;
  color: white !important;
  border-radius: 8px !important;
  font-weight: 500 !important;
  padding: 8px 16px !important;
  font-size: 14px !important;
  box-shadow: none !important;
}
.stButton > button[kind="primary"]:hover {
  background: #1d4ed8 !important; border-color: #1d4ed8 !important;
}

/* Secondary buttons */
.stButton > button {
  background: #ffffff !important;
  border: 1px solid #e5e7eb !important;
  color: #111827 !important;
  border-radius: 8px !important;
  font-weight: 400 !important;
  padding: 8px 14px !important;
  font-size: 14px !important;
  box-shadow: none !important;
  min-height: 36px !important;
}
.stButton > button:hover {
  background: #f9fafb !important;
  border-color: #d1d5db !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  background: #ffffff !important;
  color: #111827 !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 8px !important;
  font-size: 14px !important;
}

/* Dataframes — clean light */
[data-testid="stDataFrame"], [data-testid="stDataFrame"] * {
  background: #ffffff !important; color: #111827 !important;
}
[data-testid="stDataFrame"] {
  border: 1px solid #e5e7eb !important; border-radius: 8px !important;
  overflow: hidden;
}
[data-testid="stDataFrame"] thead tr,
[data-testid="stDataFrame"] thead th {
  background: #f9fafb !important; color: #6b7280 !important;
  font-weight: 500 !important; font-size: 12px !important;
  text-transform: uppercase; letter-spacing: .03em;
}
[data-testid="stDataFrame"] tbody tr:nth-child(even) { background: #fafafa !important; }

/* Code */
pre, code, [data-testid="stCodeBlock"] {
  background: #f9fafb !important; color: #111827 !important;
  border: 1px solid #e5e7eb !important; border-radius: 8px !important;
  font-family: 'SF Mono', Menlo, Monaco, Consolas, monospace !important;
}
[data-testid="stCodeBlock"] * { color: #111827 !important; }

/* Expanders */
[data-testid="stExpander"] {
  background: #ffffff !important;
  border: 1px solid #ececec !important; border-radius: 8px !important;
  margin-top: 4px;
}
[data-testid="stExpander"] * { color: #111827 !important; }
[data-testid="stExpander"] summary {
  padding: 10px 14px !important; font-size: 13px !important; color: #4b5563 !important;
}

/* Status widget */
[data-testid="stStatusWidget"], [data-testid="stStatus"] {
  background: #f5f7fb !important;
  border: 1px solid #e0e7f3 !important;
  border-radius: 8px !important;
  color: #1e3a8a !important;
}
[data-testid="stStatusWidget"] *, [data-testid="stStatus"] * {
  color: #1e3a8a !important;
}

/* Tabs */
[data-baseweb="tab-list"] {
  border-bottom: 1px solid #e5e7eb !important;
  gap: 8px !important;
}
[data-baseweb="tab"] {
  color: #6b7280 !important;
  padding: 10px 16px !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}
[data-baseweb="tab"][aria-selected="true"] {
  color: #2563eb !important;
}
</style>
"""

# Ask-page specific.
ASK_CSS = BASE_CSS + """
<style>
/* Chat input — light, rounded */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] {
  background: #ffffff !important;
  border-top: 1px solid #ececec !important;
}
[data-testid="stChatInput"] {
  background: #ffffff !important;
  border: 1px solid #d1d5db !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
[data-testid="stChatInput"] textarea {
  background: #ffffff !important;
  font-size: 15px !important;
  color: #111827 !important;
}

/* User message — right-aligned soft pill */
.user-msg {
  background: #eef4ff; color: #111827;
  padding: 10px 16px; border-radius: 16px 16px 4px 16px;
  margin: 20px 0 8px auto; max-width: 70%; width: fit-content;
  font-size: 14px; line-height: 1.55;
}

/* Assistant message wrapper */
.assist-wrap {
  margin: 16px 0 6px;
}
.assist-narrative {
  color: #111827; font-size: 15px; line-height: 1.65;
  margin-bottom: 8px;
}
.assist-narrative p { margin: 0 0 12px 0; }
.assist-narrative strong { font-weight: 600; }

/* Meta line under answer */
.answer-meta {
  font-size: 12px; color: #9ca3af;
  margin: 14px 0 6px;
}

/* Citation chips */
.cite-summary {
  font-size: 12px; color: #6b7280;
  margin: 6px 0 0;
  line-height: 1.9;
}
.cite-summary .chip {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 500; margin: 0 4px 4px 0;
  border: 1px solid #e5e7eb; background: #f9fafb; color: #374151;
}
.cite-summary .chip-agent { background: #ecfdf5; color: #047857; border-color: #d1fae5; }
.cite-summary .chip-gloss { background: #eef4ff; color: #1e40af; border-color: #dbeafe; }
.cite-summary .chip-mem   { background: #fef9c3; color: #854d0e; border-color: #fde68a; }
.cite-summary .chip-vq    { background: #f5f3ff; color: #6d28d9; border-color: #ede9fe; }
.cite-summary .chip-tbl   { background: #f9fafb; color: #4b5563; border-color: #e5e7eb; }

/* Promote banner */
.promote-banner {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px; color: #78350f;
  margin: 10px 0 0;
}

/* Greeting */
.greeting {
  text-align: center;
  margin: 64px 0 28px;
}
.greeting h1 {
  font-size: 36px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 8px;
}
.greeting p {
  color: #6b7280;
  font-size: 16px;
  margin: 0;
}

/* Suggestion chips */
.main .stButton > button {
  border-radius: 999px !important;
  padding: 9px 18px !important;
  font-size: 13px !important;
}

/* Path badge */
.badge {
  display: inline-block; padding: 2px 9px; border-radius: 6px;
  font-size: 11px; font-weight: 500; margin-right: 6px;
  background: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb;
}
.badge-agent    { background: #ecfdf5; color: #047857; border-color: #d1fae5; }
.badge-freelance{ background: #fef3c7; color: #92400e; border-color: #fde68a; }
.badge-refuse   { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
.badge-asking   { background: #dbeafe; color: #1d4ed8; border-color: #bfdbfe; }
</style>
"""

# Studio-page specific.
STUDIO_CSS = BASE_CSS + """
<style>
.main .block-container { max-width: 1100px; }

.studio-title {
  font-size: 26px; font-weight: 600; color: #111827;
  margin: 0 0 4px;
}
.studio-sub {
  font-size: 14px; color: #6b7280;
  margin: 0 0 32px;
}

.section-title {
  font-size: 15px; font-weight: 600; color: #111827;
  margin: 4px 0 12px;
}

.metric-row {
  display: flex; gap: 24px;
  margin: 0 0 24px;
}
.metric-card {
  flex: 1;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px 18px;
}
.metric-label {
  font-size: 12px; color: #6b7280;
  text-transform: uppercase; letter-spacing: .04em;
  margin: 0 0 6px;
}
.metric-value {
  font-size: 26px; font-weight: 600; color: #111827;
}

.empty-state {
  background: #ffffff;
  border: 1px dashed #d1d5db;
  border-radius: 12px;
  padding: 36px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

/* Agent avatar */
.agent-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: inline-grid; place-items: center;
  font-size: 14px; font-weight: 600; color: white;
  margin-right: 10px;
}
.av-blue   { background: #3b82f6; }
.av-green  { background: #10b981; }
.av-purple { background: #8b5cf6; }
.av-orange { background: #f59e0b; }
.av-pink   { background: #ec4899; }

/* Glossary / memory cards */
.kv-row {
  padding: 10px 0; border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
}
.kv-row:last-child { border-bottom: none; }
.kv-key { font-weight: 500; color: #111827; }
.kv-val { color: #4b5563; font-size: 13px; margin-top: 4px; }
</style>
"""
