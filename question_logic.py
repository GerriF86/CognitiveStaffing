from __future__ import annotations
from typing import List, Dict, Any
from core.schema import CRITICAL_FIELDS

def missing_fields(state: Dict[str, Any], keys: List[str]) -> List[str]:
    out = []
    for k in keys:
        v = state.get(k, "")
        if (isinstance(v, list) and not v) or (not isinstance(v, list) and not v):
            if k in CRITICAL_FIELDS:
                out.append(k)
    return out

def generate_followup_questions(state: Dict[str, Any], keys: List[str], lang: str = "en") -> List[Dict[str, str]]:
    miss = missing_fields(state, keys)
    qs = []
    for k in miss:
        if lang == "de":
            label = f"Bitte Wert für **{k}** angeben."
        else:
            label = f"Please provide a value for **{k}**."
        qs.append({"field": k, "question": label})
    return qs
