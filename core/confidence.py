"""Heuristic confidence score (0..1) for an answer."""
from typing import Dict, List

def score(*,
          path_taken: str,
          tables_used: List[str],
          glossary_terms_used: int,
          glossary_gaps: int,
          description_coverage: float,   # 0..1 over tables_used
          verified_query_match: bool,
          memory_used: int,
          had_error: bool) -> float:
    if had_error or path_taken == "refuse":
        return 0.0
    base = 0.95 if path_taken == "agent_route" else 0.55
    if path_taken == "agent_route":
        base += 0.0 if verified_query_match else -0.05
    else:
        base += 0.10 * min(glossary_terms_used, 2)    # up to +0.20
        base -= 0.10 * min(glossary_gaps, 3)          # up to -0.30
        base += 0.10 if verified_query_match else 0.0
        base += 0.10 * min(memory_used, 2)            # up to +0.20
        base += 0.15 * description_coverage           # up to +0.15
    return max(0.0, min(0.99, round(base, 2)))
