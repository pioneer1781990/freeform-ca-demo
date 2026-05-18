"""Structured response envelope. Same shape returned to every caller."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import json, hashlib, time

@dataclass
class Citation:
    kind: str         # 'glossary' | 'memory' | 'table' | 'verified_query' | 'agent_rule'
    label: str
    detail: str
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Answer:
    question: str
    path_taken: str                       # 'agent_route' | 'freelance' | 'refuse' | 'needs_definition'
    narrative: str
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    columns: Optional[List[str]] = None
    confidence: float = 0.0
    agent_used: Optional[str] = None
    citations: List[Citation] = field(default_factory=list)
    tables_used: List[str] = field(default_factory=list)
    error: Optional[str] = None
    thinking: Optional[str] = None
    latency_ms: int = 0
    verification_token: str = ""
    # For inline-definition flow (Change 1):
    needs_definition: Optional[str] = None    # term that needs definition
    suggest_promote_key: Optional[str] = None # if memory was just used and is promotable

    def __post_init__(self):
        if not self.verification_token:
            h = hashlib.sha256((self.question + (self.sql or '') + str(time.time())).encode()).hexdigest()[:16]
            self.verification_token = f"vt_{h}"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)
