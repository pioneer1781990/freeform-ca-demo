#!/usr/bin/env bash
# Reset the freeform demo back to its "before" state.
#
# Walks the `_demo_provenance` BQ table, undoes every resource recorded
# there, runs a pre-flight to clear hard-coded demo mutations, then
# truncates the provenance log and resets the session timestamp.
#
# Safe to re-run. Tolerant of missing tables, missing rows, missing CA SDK.
#
# Usage:
#   cd /path/to/freeform_demo
#   source .env          # exports PROJECT_ID, DATASET, BQ_LOCATION, etc.
#   ./scripts/reset_demo.sh

set -euo pipefail

# Resolve the demo root regardless of where this script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${DEMO_ROOT}"

# Best-effort: load .env if the caller did not already.
if [[ -z "${PROJECT_ID:-}" && -f ".env" ]]; then
  # shellcheck disable=SC1091
  set -a && source .env && set +a
fi

# Activate venv if one is present and not already active.
if [[ -z "${VIRTUAL_ENV:-}" && -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

: "${PROJECT_ID:?PROJECT_ID is not set — source .env first}"

exec python3 scripts/reset_demo.py "$@"
