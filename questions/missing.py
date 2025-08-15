from __future__ import annotations
from typing import List, Dict
from core.schema import CRITICAL_FIELDS

def list_missing_critical(state: Dict[str, object]) -> List[str]:
    out = []
    for k in CRITICAL_FIELDS:
        v = state.get(k, "")
        if isinstance(v, list):
            if not v:
                out.append(k)
        else:
            if not v:
                out.append(k)
    return out
