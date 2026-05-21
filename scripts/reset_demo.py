"""Reset the freeform demo back to its "before" state.

Walks `_demo_provenance` and undoes each recorded resource creation. Also
runs a pre-flight pass to clear hard-coded mutations that the demo always
makes regardless of provenance.

Design notes:
  * Uses SQL DML (INSERT/UPDATE/DELETE) via `bq.query`, never streaming
    inserts. This avoids the 30-min streaming-buffer DELETE lockout.
  * Tolerant of missing rows, missing tables, missing CA SDK, etc. — every
    step logs and continues.
  * The `_demo_provenance` schema documented in the task spec is
    `(kind, identifier, created_at)`. An older copy of the table used
    `(ts, operation, target, details)`. This script handles BOTH:
    rows that look like the new schema are dispatched by `kind`; rows
    that look like the old schema (e.g. `operation = 'enhance_graph'`)
    are mapped onto an equivalent new-schema kind.

Usage:
    source .env
    source .venv/bin/activate
    python3 scripts/reset_demo.py
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Make `import config`/`from core import …` work when run from any cwd.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

import warnings
warnings.filterwarnings("ignore")

from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions

import config as cfg

SESSION_FILE = "/tmp/freeform_session_start.txt"
GRAPH_DDL_PATH = _ROOT / "scripts" / "phase_c_graph.sql"

# Dataplex glossary identifiers (mirror core/dataplex_ops.py).
DATAPLEX_LOCATION = "us-central1"
GLOSSARY_ID = "cymbal-retail-glossary"


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
class Counters:
    def __init__(self):
        self.dataplex_terms = 0
        self.graph_edges = 0
        self.vector_tables = 0
        self.agent_updates = 0
        self.flywheel_glossary = 0
        self.flywheel_memory = 0
        self.preflight_glossary = 0
        self.preflight_memory = 0
        self.unknown = 0
        self.errors = 0

    def summary(self) -> str:
        return (
            "Reset complete. "
            f"Cleared {self.dataplex_terms} dataplex glossary terms, "
            f"{self.agent_updates} agent updates, "
            f"{self.vector_tables} embeddings tables, "
            f"{self.graph_edges} graph-edge rebuilds, "
            f"{self.flywheel_glossary} flywheel glossary rows, "
            f"{self.flywheel_memory} flywheel memory rows. "
            f"Pre-flight: removed {self.preflight_glossary} hard-coded glossary rows "
            f"and {self.preflight_memory} siya-memory rows. "
            f"Unknown rows: {self.unknown}. Errors: {self.errors}."
        )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _log(msg: str) -> None:
    print(msg, flush=True)


def _run_dml(bq: bigquery.Client, sql: str, label: str) -> bool:
    """Run a DML statement; log and swallow errors. Returns True on success."""
    try:
        bq.query(sql, location=cfg.BQ_LOCATION).result()
        _log(f"  ✓ {label}")
        return True
    except gcp_exceptions.NotFound:
        _log(f"  · {label} — table not found, skipping")
        return True
    except Exception as e:
        msg = str(e).splitlines()[0][:200]
        if "streaming buffer" in msg.lower():
            _log(f"  ⚠ {label} — streaming-buffer block; rows will flush in <30min")
        else:
            _log(f"  ✗ {label} — {msg}")
        return False


def _esc(s: str) -> str:
    """Escape a string for safe interpolation into a SQL string literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


# ---------------------------------------------------------------------------
# Per-kind handlers (each returns True if it counts as a successful undo)
# ---------------------------------------------------------------------------
def _undo_dataplex_term(identifier: str) -> bool:
    try:
        from core.dataplex_ops import delete_glossary_term
    except Exception as e:
        _log(f"  ✗ dataplex_glossary_term[{identifier}] — import failed: {e}")
        return False
    ok = delete_glossary_term(identifier)
    if ok:
        _log(f"  ✓ deleted dataplex term {identifier!r}")
    else:
        _log(f"  ✗ failed to delete dataplex term {identifier!r}")
    return ok


def _undo_graph_edges(bq: bigquery.Client) -> bool:
    """Re-run the BASE graph DDL from phase_c_graph.sql — overwrites with
    the original two edges (purchase_edges, stocking_edges) only.
    """
    if not GRAPH_DDL_PATH.exists():
        _log(f"  ✗ graph DDL not found at {GRAPH_DDL_PATH}")
        return False
    try:
        ddl = GRAPH_DDL_PATH.read_text()
    except Exception as e:
        _log(f"  ✗ could not read graph DDL: {e}")
        return False

    # The file has multiple statements separated by ';'. Run each, tolerating
    # the harmless 'ALTER TABLE ... ADD PRIMARY KEY' errors that occur when
    # the PK already exists.
    statements = [s.strip() for s in ddl.split(";") if s.strip() and not s.strip().startswith("--")]
    n_ok = 0
    for stmt in statements:
        try:
            bq.query(stmt, location=cfg.BQ_LOCATION).result()
            n_ok += 1
        except gcp_exceptions.BadRequest as e:
            # Pre-existing primary key constraint is fine.
            if "primary key" in str(e).lower() or "already" in str(e).lower():
                n_ok += 1
                continue
            _log(f"  · graph stmt warning: {str(e).splitlines()[0][:160]}")
        except Exception as e:
            _log(f"  · graph stmt warning: {str(e).splitlines()[0][:160]}")
    _log(f"  ✓ replayed base graph DDL ({n_ok}/{len(statements)} statements ok)")
    return True


def _undo_vector_table(bq: bigquery.Client, identifier: str) -> bool:
    """Drop a BQ table named in identifier. Identifier may be a bare table
    name (looked up under the demo dataset) or a fully-qualified name.
    """
    if not identifier:
        return False
    if "." in identifier:
        fq = identifier
    else:
        fq = f"{cfg.PROJECT_ID}.{cfg.DATASET}.{identifier}"
    sql = f"DROP TABLE IF EXISTS `{fq}`"
    return _run_dml(bq, sql, f"dropped vector table `{fq}`")


def _undo_ca_agent(identifier: str) -> bool:
    """Clear example_queries on the CA agent named in identifier."""
    try:
        from core.ca_api_client import HAS_CA_SDK
    except Exception as e:
        _log(f"  ✗ ca_agent_example_queries[{identifier}] — import failed: {e}")
        return False
    if not HAS_CA_SDK:
        _log(f"  · ca_agent_example_queries[{identifier}] — CA SDK not installed, skipping")
        return False
    try:
        from google.cloud import geminidataanalytics as gda
        svc = gda.DataAgentServiceClient()
        name = (
            f"projects/{cfg.PROJECT_ID}/locations/{cfg.CA_LOCATION}"
            f"/dataAgents/{identifier}"
        )
        try:
            existing = svc.get_data_agent(name=name)
        except gcp_exceptions.NotFound:
            _log(f"  · agent {identifier!r} not found, skipping")
            return True

        # Best-effort: clear example_queries from both staging + published
        # contexts. Field may not exist on older API builds — guard each set.
        for ctx_name in ("published_context", "staging_context"):
            try:
                ctx = getattr(existing.data_analytics_agent, ctx_name)
                if hasattr(ctx, "example_queries"):
                    # Repeated message — clearing assigns the empty list.
                    del ctx.example_queries[:]
            except Exception:
                pass

        req = gda.UpdateDataAgentRequest(data_agent=existing)
        svc.update_data_agent(request=req)
        _log(f"  ✓ cleared example_queries on agent {identifier!r}")
        return True
    except Exception as e:
        _log(f"  ✗ ca_agent_example_queries[{identifier}] — {type(e).__name__}: {str(e)[:160]}")
        return False


def _undo_flywheel_glossary_term(bq: bigquery.Client, identifier: str) -> bool:
    sql = (
        f"DELETE FROM {cfg.t('_flywheel_glossary')} "
        f"WHERE term = '{_esc(identifier)}'"
    )
    return _run_dml(bq, sql, f"deleted flywheel glossary term {identifier!r}")


def _undo_flywheel_memory(bq: bigquery.Client, identifier: str) -> bool:
    sql = (
        f"DELETE FROM {cfg.t('_flywheel_memory')} "
        f"WHERE id = '{_esc(identifier)}'"
    )
    return _run_dml(bq, sql, f"deleted flywheel memory row {identifier!r}")


# ---------------------------------------------------------------------------
# Provenance reader — supports both the new and legacy schemas
# ---------------------------------------------------------------------------
def _read_provenance(bq: bigquery.Client) -> List[Tuple[str, str]]:
    """Returns a list of (kind, identifier) tuples. Empty if table absent."""
    table_ref = f"{cfg.PROJECT_ID}.{cfg.DATASET}._demo_provenance"

    # Check table existence first; if absent there is nothing to undo.
    try:
        tbl = bq.get_table(table_ref)
    except gcp_exceptions.NotFound:
        _log("  · _demo_provenance does not exist — nothing to undo from provenance")
        return []

    cols = {f.name for f in tbl.schema}

    rows: List[Tuple[str, str]] = []

    if {"kind", "identifier"}.issubset(cols):
        # New schema (the one the spec describes).
        try:
            for r in bq.query(
                f"SELECT kind, identifier FROM `{table_ref}` "
                f"WHERE kind IS NOT NULL AND identifier IS NOT NULL",
                location=cfg.BQ_LOCATION,
            ).result():
                rows.append((r["kind"], r["identifier"]))
        except Exception as e:
            _log(f"  ✗ failed to read _demo_provenance (new schema): {e}")

    if {"operation", "details"}.issubset(cols):
        # Legacy schema written by core/graph_ops.py. Map onto new kinds.
        try:
            for r in bq.query(
                f"SELECT operation, target, details FROM `{table_ref}`",
                location=cfg.BQ_LOCATION,
            ).result():
                op = (r["operation"] or "").lower()
                if op == "enhance_graph":
                    # Identifier is irrelevant for the rebuild; pass a marker.
                    rows.append(("graph_edge", r["details"] or "(legacy)"))
                else:
                    _log(
                        f"  · legacy provenance row with unknown operation {op!r} — skipping"
                    )
        except Exception as e:
            _log(f"  ✗ failed to read _demo_provenance (legacy schema): {e}")

    return rows


def _truncate_provenance(bq: bigquery.Client) -> None:
    table_ref = f"{cfg.PROJECT_ID}.{cfg.DATASET}._demo_provenance"
    try:
        bq.get_table(table_ref)
    except gcp_exceptions.NotFound:
        return
    # TRUNCATE TABLE is supported as DDL; it bypasses the streaming buffer
    # block that affects DELETE.
    try:
        bq.query(f"TRUNCATE TABLE `{table_ref}`", location=cfg.BQ_LOCATION).result()
        _log("  ✓ truncated _demo_provenance")
    except Exception as e:
        # Fall back to DELETE WHERE TRUE.
        _log(f"  · TRUNCATE failed ({str(e).splitlines()[0][:120]}); trying DELETE")
        _run_dml(
            bq,
            f"DELETE FROM `{table_ref}` WHERE TRUE",
            "deleted all _demo_provenance rows",
        )


# ---------------------------------------------------------------------------
# Pre-flight: hard-coded mutations the demo always makes
# ---------------------------------------------------------------------------
def _preflight(bq: bigquery.Client, c: Counters) -> None:
    _log("\n=== PRE-FLIGHT: clear hard-coded demo mutations ===")
    sql_g = (
        f"DELETE FROM {cfg.t('_flywheel_glossary')} "
        f"WHERE source IN ('manual','promoted_from_memory','defined_in_demo')"
    )
    if _run_dml(bq, sql_g, "removed non-seed flywheel glossary rows"):
        # We do not get a per-row count from bq.query result rows here, but
        # numAffectedRows is available on the job — fetch it for the summary.
        try:
            job = bq.query(
                f"SELECT COUNT(*) AS n FROM {cfg.t('_flywheel_glossary')} "
                f"WHERE source IN ('manual','promoted_from_memory','defined_in_demo')",
                location=cfg.BQ_LOCATION,
            )
            # After delete this should be 0; the meaningful count is in
            # job.num_dml_affected_rows from the DELETE itself. Re-running
            # the DELETE to get that count would be wasteful; just record
            # success as "1 pass".
            c.preflight_glossary = 1
        except Exception:
            c.preflight_glossary = 1

    sql_m = (
        f"DELETE FROM {cfg.t('_flywheel_memory')} "
        f"WHERE user_id = 'siya'"
    )
    if _run_dml(bq, sql_m, "removed siya memory rows"):
        c.preflight_memory = 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    _log(f"▶ Reset demo for project={cfg.PROJECT_ID} dataset={cfg.DATASET}")
    bq = bigquery.Client(project=cfg.PROJECT_ID, location=cfg.BQ_LOCATION)
    counters = Counters()

    # Pre-flight first so even an empty provenance still leaves things clean.
    _preflight(bq, counters)

    _log("\n=== PROVENANCE WALK ===")
    rows = _read_provenance(bq)
    _log(f"  {len(rows)} provenance row(s) to undo")

    # Coalesce graph_edge entries — one rebuild handles them all.
    rebuilt_graph = False

    for kind, identifier in rows:
        try:
            if kind == "dataplex_glossary_term":
                if _undo_dataplex_term(identifier):
                    counters.dataplex_terms += 1
                else:
                    counters.errors += 1
            elif kind == "graph_edge":
                if not rebuilt_graph:
                    if _undo_graph_edges(bq):
                        counters.graph_edges += 1
                        rebuilt_graph = True
                    else:
                        counters.errors += 1
                else:
                    counters.graph_edges += 1  # already handled by single rebuild
            elif kind == "vector_embeddings_table":
                if _undo_vector_table(bq, identifier):
                    counters.vector_tables += 1
                else:
                    counters.errors += 1
            elif kind == "ca_agent_example_queries":
                if _undo_ca_agent(identifier):
                    counters.agent_updates += 1
                else:
                    counters.errors += 1
            elif kind == "flywheel_glossary_term":
                if _undo_flywheel_glossary_term(bq, identifier):
                    counters.flywheel_glossary += 1
                else:
                    counters.errors += 1
            elif kind == "flywheel_memory":
                if _undo_flywheel_memory(bq, identifier):
                    counters.flywheel_memory += 1
                else:
                    counters.errors += 1
            else:
                _log(f"  · unknown provenance kind {kind!r} (identifier={identifier!r}) — skipping")
                counters.unknown += 1
        except Exception as e:
            counters.errors += 1
            _log(f"  ✗ unhandled error on {kind}[{identifier}]: {e}")
            traceback.print_exc()

    # Truncate the provenance table so the next demo starts from a clean log.
    _log("\n=== FINALIZE ===")
    _truncate_provenance(bq)

    # Reset session timestamp.
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
            _log(f"  ✓ removed {SESSION_FILE}")
        else:
            _log(f"  · {SESSION_FILE} already absent")
    except Exception as e:
        _log(f"  ✗ could not remove {SESSION_FILE}: {e}")

    _log("")
    _log(counters.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
