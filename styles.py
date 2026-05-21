"""Minimal CSS. Style ONLY custom classes we define ourselves.
Never override font-family, font-weight, or display on Streamlit's own
component elements — that's what was breaking the expander icons.
"""

# Only style our own classes. Streamlit defaults handle the rest.
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Hide Streamlit clutter (safe — these are documented testids) */
header[data-testid="stHeader"] { display: none; }
[data-testid="stSidebarNav"] { display: none; }
#MainMenu { visibility: hidden; }
footer { display: none; }

/* Custom user-message bubble (right-aligned soft pill) */
.user-msg {
  font-family: 'Inter', -apple-system, sans-serif;
  background: #eef4ff; color: #111827;
  padding: 10px 16px; border-radius: 16px 16px 4px 16px;
  margin: 20px 0 8px auto; max-width: 70%; width: fit-content;
  font-size: 14px; line-height: 1.55;
}

/* Custom assistant narrative block */
.assist-narrative {
  font-family: 'Inter', -apple-system, sans-serif;
  color: #111827; font-size: 15px; line-height: 1.65;
  margin: 8px 0 8px;
}
.assist-narrative p { margin: 0 0 12px 0; }
.assist-narrative strong { font-weight: 600; }

/* Custom meta line under answer */
.answer-meta {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 12px; color: #9ca3af; margin: 14px 0 6px;
}

/* Custom citation chips */
.cite-summary {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 12px; color: #6b7280; margin: 6px 0 0; line-height: 1.9;
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
  font-family: 'Inter', -apple-system, sans-serif;
  background: #fffbeb; border: 1px solid #fde68a;
  border-radius: 8px; padding: 10px 14px;
  font-size: 13px; color: #78350f; margin: 10px 0 0;
}

/* Empty-state greeting */
.greeting {
  font-family: 'Inter', -apple-system, sans-serif;
  text-align: center; margin: 64px 0 28px;
}
.greeting h1 {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 36px; font-weight: 600; color: #111827; margin: 0 0 8px;
}
.greeting p {
  color: #6b7280; font-size: 16px; margin: 0;
}

/* Path badge */
.badge {
  font-family: 'Inter', -apple-system, sans-serif;
  display: inline-block; padding: 2px 9px; border-radius: 6px;
  font-size: 11px; font-weight: 500; margin-right: 6px;
  background: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb;
}
.badge-agent    { background: #ecfdf5; color: #047857; border-color: #d1fae5; }
.badge-freelance{ background: #fef3c7; color: #92400e; border-color: #fde68a; }
.badge-refuse   { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
.badge-asking   { background: #dbeafe; color: #1d4ed8; border-color: #bfdbfe; }

/* Studio-specific custom classes */
.studio-title {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 26px; font-weight: 600; color: #111827; margin: 0 0 4px;
}
.studio-sub {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 14px; color: #6b7280; margin: 0 0 32px;
}
.section-title {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 15px; font-weight: 600; color: #111827; margin: 4px 0 12px;
}

/* Metric cards */
.metric-row { display: flex; gap: 24px; margin: 0 0 24px; }
.metric-card {
  font-family: 'Inter', -apple-system, sans-serif;
  flex: 1; background: #ffffff; border: 1px solid #e5e7eb;
  border-radius: 10px; padding: 16px 18px;
}
.metric-label {
  font-size: 12px; color: #6b7280;
  text-transform: uppercase; letter-spacing: .04em; margin: 0 0 6px;
}
.metric-value { font-size: 26px; font-weight: 600; color: #111827; }

/* Empty state for Studio Recommendations */
.empty-state {
  font-family: 'Inter', -apple-system, sans-serif;
  background: #ffffff; border: 1px dashed #d1d5db;
  border-radius: 12px; padding: 36px;
  text-align: center; color: #6b7280; font-size: 14px;
}

/* Agent avatar (Studio Agents tab) */
.agent-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: inline-grid; place-items: center;
  font-size: 14px; font-weight: 600; color: white; margin-right: 10px;
  font-family: 'Inter', -apple-system, sans-serif;
}
.av-blue   { background: #3b82f6; }
.av-green  { background: #10b981; }
.av-purple { background: #8b5cf6; }
.av-orange { background: #f59e0b; }
.av-pink   { background: #ec4899; }

/* Glossary/memory key-value rows */
.kv-row {
  font-family: 'Inter', -apple-system, sans-serif;
  padding: 10px 0; border-bottom: 1px solid #f3f4f6; font-size: 14px;
}
.kv-row:last-child { border-bottom: none; }
.kv-key { font-weight: 500; color: #111827; }
.kv-val { color: #4b5563; font-size: 13px; margin-top: 4px; }
</style>
"""

ASK_CSS = BASE_CSS
STUDIO_CSS = BASE_CSS
