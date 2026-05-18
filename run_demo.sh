#!/usr/bin/env bash
# Start the Streamlit demo app. Run AFTER setup_gcp.sh and load_data.sh.
# Idempotent — re-running is safe.

set -euo pipefail
: "${PROJECT_ID:?source .env first}"
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY not set in .env}"

echo "▶ Activating venv"
source .venv/bin/activate

echo "▶ Pre-creating the Sales Analytics agent + seeding sales glossary (if not already done)"
python3 scripts/precreate_sales_agent.py 2>&1 | tail -5

echo "▶ Resetting demo session timestamp (so recommendations are 'fresh')"
rm -f /tmp/freeform_session_start.txt

echo "▶ Killing any old Streamlit on :8501"
pkill -9 -f "streamlit run" 2>/dev/null || true
sleep 1

echo "▶ Starting Streamlit headless on :8501 (log: /tmp/streamlit.log)"
nohup streamlit run app.py \
  --server.headless true --server.port 8501 \
  --browser.gatherUsageStats false \
  --theme.base light \
  > /tmp/streamlit.log 2>&1 &

sleep 4
if curl -sS -o /dev/null -w "%{http_code}" http://localhost:8501/ | grep -q 200; then
  echo ""
  echo "════════════════════════════════════════════════════════════"
  echo "  ✓ Freeform CA demo is live"
  echo "  Ask     →  http://localhost:8501/"
  echo "  Studio  →  http://localhost:8501/Studio"
  echo "════════════════════════════════════════════════════════════"
  echo ""
  echo "  Logs:   tail -f /tmp/streamlit.log"
  echo "  Stop:   pkill -9 -f 'streamlit run'"
else
  echo "✗ Streamlit failed to start. Check /tmp/streamlit.log"
  tail -20 /tmp/streamlit.log
  exit 1
fi
