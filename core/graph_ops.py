"""Property graph enhancement operations.

Idempotently re-creates `cymbal_retail_graph` with the requested edges
(plus all existing edges) and records what was added in `_demo_provenance`.
"""
from __future__ import annotations

from typing import List, Dict, Optional
from datetime import datetime, timezone

from google.cloud import bigquery

import config as cfg


# ---------------------------------------------------------------------------
# Edge registry — each entry knows how to build itself into the graph DDL.
# ---------------------------------------------------------------------------
# An "edge spec" produces:
#   - optional view DDL (CREATE OR REPLACE VIEW ...) executed before the graph
#   - an EDGE TABLES clause fragment for the property graph
#
# Node table fragments are emitted once, unconditionally, to match the
# original phase_c_graph.sql definition.

_NODE_TABLES_SQL = f"""    {cfg.t('users')} AS Customer
      KEY (id)
      LABEL Customer
      PROPERTIES (id, first_name, last_name, age, gender, country, city, traffic_source),
    {cfg.t('products')} AS Product
      KEY (id)
      LABEL Product
      PROPERTIES (id, name, brand, category, department, retail_price, cost),
    {cfg.t('distribution_centers')} AS DC
      KEY (id)
      LABEL DistributionCenter
      PROPERTIES (id, name, latitude, longitude)"""


def _purchased_edge() -> Dict[str, Optional[str]]:
    view_sql = f"""
    CREATE OR REPLACE VIEW {cfg.t('purchase_edges')} AS
    SELECT DISTINCT user_id AS customer_id, product_id
    FROM {cfg.t('order_items')}
    WHERE status NOT IN ('Cancelled')
    """
    edge_frag = f"""    {cfg.t('purchase_edges')} AS Purchased
      KEY (customer_id, product_id)
      SOURCE KEY (customer_id) REFERENCES Customer (id)
      DESTINATION KEY (product_id) REFERENCES Product (id)
      LABEL Purchased"""
    return {"view_sql": view_sql, "edge_frag": edge_frag}


def _stocked_at_edge() -> Dict[str, Optional[str]]:
    view_sql = f"""
    CREATE OR REPLACE VIEW {cfg.t('stocking_edges')} AS
    SELECT DISTINCT
      product_id,
      product_distribution_center_id AS dc_id
    FROM {cfg.t('inventory_items')}
    WHERE product_distribution_center_id IS NOT NULL
    """
    edge_frag = f"""    {cfg.t('stocking_edges')} AS StockedAt
      KEY (product_id, dc_id)
      SOURCE KEY (product_id) REFERENCES Product (id)
      DESTINATION KEY (dc_id) REFERENCES DC (id)
      LABEL StockedAt"""
    return {"view_sql": view_sql, "edge_frag": edge_frag}


# Canonical key -> builder
_EDGE_BUILDERS = {
    "Customer → Purchased → Product": _purchased_edge,
    "Product → StockedAt → DistributionCenter": _stocked_at_edge,
}


def _normalize(spec: str) -> str:
    """Accept both unicode arrow and ASCII -> in edge specs."""
    return spec.replace("->", "→").replace("  ", " ").strip()


def _ensure_provenance_table(bq: bigquery.Client) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS {cfg.t('_demo_provenance')} (
      ts TIMESTAMP,
      operation STRING,
      target STRING,
      details STRING
    )
    """
    bq.query(sql).result()


def _record_provenance(bq: bigquery.Client, edges: List[str]) -> None:
    _ensure_provenance_table(bq)
    rows = [
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "operation": "enhance_graph",
            "target": "cymbal_retail_graph",
            "details": edge,
        }
        for edge in edges
    ]
    table_ref = f"{cfg.PROJECT_ID}.{cfg.DATASET}._demo_provenance"
    errors = bq.insert_rows_json(table_ref, rows)
    if errors:
        # Streaming inserts may fail on a freshly created table; fall back to DML.
        values_sql = ",\n".join(
            f"(CURRENT_TIMESTAMP(), 'enhance_graph', 'cymbal_retail_graph', "
            f"{repr(edge)})"
            for edge in edges
        )
        bq.query(
            f"INSERT INTO {cfg.t('_demo_provenance')} (ts, operation, target, details) "
            f"VALUES {values_sql}"
        ).result()


def enhance_graph(edges_to_add: List[str]) -> bool:
    """Re-create the property graph with the requested edges merged in.

    Idempotent: edges already present in the live graph are simply re-declared
    via CREATE OR REPLACE. Unknown edge specs raise ValueError.

    Args:
        edges_to_add: list of canonical edge strings, e.g.
            ["Customer → Purchased → Product",
             "Product → StockedAt → DistributionCenter"]

    Returns:
        True on success.
    """
    bq = bigquery.Client(project=cfg.PROJECT_ID, location=cfg.BQ_LOCATION)

    # Always include the canonical set of edges that already exist in the live
    # graph, plus any requested additions. Deduplicate by canonical key.
    canonical_existing = [
        "Customer → Purchased → Product",
        "Product → StockedAt → DistributionCenter",
    ]
    requested = [_normalize(s) for s in (edges_to_add or [])]
    final_edges: List[str] = []
    for e in canonical_existing + requested:
        if e not in final_edges:
            final_edges.append(e)

    # Validate and build fragments.
    view_sqls: List[str] = []
    edge_frags: List[str] = []
    for spec in final_edges:
        builder = _EDGE_BUILDERS.get(spec)
        if builder is None:
            raise ValueError(
                f"Unsupported edge spec: {spec!r}. "
                f"Supported: {list(_EDGE_BUILDERS)}"
            )
        parts = builder()
        if parts.get("view_sql"):
            view_sqls.append(parts["view_sql"])
        edge_frags.append(parts["edge_frag"])

    # 1) (Re)create supporting views.
    for vsql in view_sqls:
        bq.query(vsql).result()

    # 2) Re-create the property graph with all edges.
    graph_sql = (
        f"CREATE OR REPLACE PROPERTY GRAPH "
        f"{cfg.t('cymbal_retail_graph')}\n"
        f"  NODE TABLES (\n{_NODE_TABLES_SQL}\n  )\n"
        f"  EDGE TABLES (\n"
        + ",\n".join(edge_frags)
        + "\n  )"
    )
    bq.query(graph_sql).result()

    # 3) Record provenance (best-effort; do not fail the operation if logging
    #    has a transient issue).
    try:
        _record_provenance(bq, requested or canonical_existing)
    except Exception:
        pass

    return True
