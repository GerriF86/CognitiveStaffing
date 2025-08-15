from __future__ import annotations
from typing import List

def suggest_additional_skills(job_title: str, existing: List[str]) -> List[str]:
    bank = {
        "data": ["Python", "SQL", "Pandas", "Airflow", "Spark"],
        "software": ["Java", "Python", "Git", "Docker", "Kubernetes", "AWS"],
        "product": ["Roadmapping", "Stakeholder Management", "Analytics", "A/B Testing"],
    }
    jt = job_title.lower()
    pool = bank["software"] if "engineer" in jt else bank["data"] if "data" in jt else bank["product"]
    return [s for s in pool if s not in existing][:5]
