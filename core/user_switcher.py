"""User persona switcher for the freeform demo.

Demonstrates inheritance of enrichments across users: when Siya defines a
glossary term (or promotes verified queries, extends the graph, builds
embeddings) and the analyst approves it, the next user (Alex, Morgan) asking
the same question gets the post-enrichment answer instantly — without
re-doing any of the work.

The orchestrator should call `inherited_suffix(...)` to derive a cache-key
suffix (e.g. "[inherited-by-alex-from-churn-defined]") that maps onto the
inheritance variants in `core/answer_cache.py`.
"""
from typing import Dict, List, Set


PERSONAS: List[Dict[str, str]] = [
    {"id": "siya",   "name": "Siya",   "role": "Sales analyst",      "avatar_color": "#3b82f6"},
    {"id": "alex",   "name": "Alex",   "role": "CX manager",         "avatar_color": "#10b981"},
    {"id": "morgan", "name": "Morgan", "role": "Supply chain lead",  "avatar_color": "#f59e0b"},
]


# Siya is the "original demo user" — she's the one who performs the
# enrichments (defines churn, promotes verified queries, etc.). Any other
# user asking the same question after an enrichment was applied should get
# the inherited answer.
_ORIGINAL_USER_ID = "siya"


# Map each enrichment marker to the substring(s) we look for in the
# normalized question. A question can only be "inherited" if it actually
# matches the question that originally triggered the enrichment.
_ENRICHMENT_QUESTION_MARKERS: Dict[str, List[str]] = {
    "churn_defined":        ["churn rate", "customer churn"],
    "cx_verified_queries":  ["review score", "brazilian state"],
    "graph_extended":       ["distribution centers", "top 10 customers"],
    "embeddings_created":   ["upset", "reviews"],
}


def get_persona(user_id: str) -> Dict[str, str]:
    """Return the persona dict for `user_id`. Defaults to Siya if unknown."""
    for p in PERSONAS:
        if p["id"] == user_id:
            return p
    return PERSONAS[0]


def _question_matches(base_question: str, markers: List[str]) -> bool:
    q = " ".join(base_question.lower().strip().split())
    return any(m in q for m in markers)


def inherited_suffix(user_id: str, base_question: str, applied_enrichments: Set[str]) -> str:
    """Return an inheritance suffix if this user/question/state combo should
    hit an inherited cache variant; otherwise return "".

    The suffix looks like `"[inherited-by-alex-from-churn-defined]"` and is
    designed to be appended to the normalized question when looking up
    `answer_cache.lookup(question, suffix=...)`.
    """
    if user_id == _ORIGINAL_USER_ID:
        return ""
    if not applied_enrichments:
        return ""

    for enrichment, markers in _ENRICHMENT_QUESTION_MARKERS.items():
        if enrichment in applied_enrichments and _question_matches(base_question, markers):
            # Replace underscores with dashes for a cleaner suffix label.
            enrichment_label = enrichment.replace("_", "-")
            return f"[inherited-by-{user_id}-from-{enrichment_label}]"

    return ""
