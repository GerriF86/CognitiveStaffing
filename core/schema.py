from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

# -------------------------
# SCHEMA (Single Source of Truth)
# -------------------------

class Company(BaseModel):
    name: str = ""
    industry: str = ""
    hq_location: str = ""
    size: str = ""          # e.g., "1-10", "11-50", ...
    website: str = ""
    mission: str = ""
    culture: str = ""

class Location(BaseModel):
    primary_city: str = ""
    country: str = ""

class Position(BaseModel):
    job_title: str = ""
    role_summary: str = ""
    department: str = ""
    team_structure: str = ""
    reporting_line: str = ""
    seniority_level: str = ""  # e.g., "Junior/Mid/Senior/Lead"

class Responsibilities(BaseModel):
    items: List[str] = Field(default_factory=list)

class Requirements(BaseModel):
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    tools_and_technologies: List[str] = Field(default_factory=list)
    languages_required: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)

class Employment(BaseModel):
    job_type: str = ""       # Full-time/Part-time/Contract/...
    work_policy: str = ""    # Onsite/Hybrid/Remote
    travel_required: bool = False
    # UI helper fields (not persisted as-is; merged into text):
    remote_policy: str = ""  # e.g., "2 days WFH"
    travel_details: str = ""

class Compensation(BaseModel):
    salary_provided: bool = False
    salary_min: float = 0.0
    salary_max: float = 0.0
    salary_currency: str = "EUR"
    salary_period: str = "year"   # year | month | hour
    benefits: List[str] = Field(default_factory=list)
    healthcare_plan: str = ""
    pension_plan: str = ""
    variable_pay: bool = False
    equity_offered: bool = False

class Process(BaseModel):
    interview_stages: int = 0
    process_notes: str = ""

class VacalyserJD(BaseModel):
    company: Company = Field(default_factory=Company)
    location: Location = Field(default_factory=Location)
    position: Position = Field(default_factory=Position)
    responsibilities: Responsibilities = Field(default_factory=Responsibilities)
    requirements: Requirements = Field(default_factory=Requirements)
    employment: Employment = Field(default_factory=Employment)
    compensation: Compensation = Field(default_factory=Compensation)
    process: Process = Field(default_factory=Process)

# -------------------------
# SECTION FIELD MAP
# -------------------------
FIELDS_BY_SECTION: Dict[int, List[str]] = {
    1: ["company.name", "company.industry", "company.hq_location", "company.size",
        "company.website", "location.primary_city", "location.country", "company.mission", "company.culture"],
    2: ["position.job_title", "position.role_summary", "position.department",
        "position.team_structure", "position.reporting_line", "position.seniority_level"],
    3: ["responsibilities.items"],
    4: ["requirements.hard_skills", "requirements.soft_skills",
        "requirements.tools_and_technologies", "requirements.languages_required",
        "requirements.certifications"],
    5: ["employment.job_type", "employment.work_policy", "employment.travel_required",
        "employment.remote_policy", "employment.travel_details",
        "compensation.salary_provided", "compensation.salary_min", "compensation.salary_max",
        "compensation.salary_currency", "compensation.salary_period",
        "compensation.benefits", "compensation.healthcare_plan",
        "compensation.pension_plan", "compensation.variable_pay", "compensation.equity_offered"],
    6: ["process.interview_stages", "process.process_notes"],
    # 7 summary
}

CRITICAL_FIELDS: List[str] = [
    "company.name", "position.job_title", "location.primary_city",
    "requirements.hard_skills", "responsibilities.items",
]

# -------------------------
# Helpers: dot get/set + flatten/unflatten
# -------------------------
def _split_key(k: str) -> List[str]:
    return k.split(".")

def dot_get(obj: Any, path: str, default=None):
    cur = obj
    for part in _split_key(path):
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            cur = getattr(cur, part, default)
        if cur is default:
            break
    return cur

def dot_set(d: Dict[str, Any], path: str, value: Any):
    parts = _split_key(path)
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def flatten_model(m: BaseModel) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    def _rec(prefix: str, v: Any):
        if isinstance(v, BaseModel):
            for k, vv in v.model_dump().items():
                _rec(f"{prefix}.{k}" if prefix else k, vv)
        elif isinstance(v, dict):
            for k, vv in v.items():
                _rec(f"{prefix}.{k}" if prefix else k, vv)
        else:
            out[prefix] = v
    _rec("", m)
    return out

def unflatten_to_model(d: Dict[str, Any]) -> VacalyserJD:
    nested: Dict[str, Any] = {}
    for k, v in d.items():
        dot_set(nested, k, v)
    return VacalyserJD.model_validate(nested)

# -------------------------
# Aliases (legacy -> canonical)
# -------------------------
ALIASES: Dict[str, str] = {
    "company_name": "company.name",
    "company_website": "company.website",
    "city": "location.primary_city",
    "country": "location.country",
    "job_title": "position.job_title",
    "role_summary": "position.role_summary",
    "tasks": "responsibilities.items",
    "contract_type": "employment.job_type",
    "remote_policy": "employment.remote_policy",
    "travel_required": "employment.travel_required",
}

def apply_aliases(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    for src, dst in ALIASES.items():
        if src in out and dst not in out:
            out[dst] = out[src]
    return out

def coerce_and_fill(raw: Dict[str, Any]) -> VacalyserJD:
    raw = apply_aliases(raw or {})
    # fill missing with defaults
    base = VacalyserJD()
    flat = flatten_model(base)
    flat.update({k: raw[k] for k in raw if k in flat})
    # lists: coerce strings -> [strings] by line breaks
    for k, v in list(flat.items()):
        if isinstance(dot_get(base, k), list) and isinstance(v, str):
            flat[k] = [x.strip() for x in v.splitlines() if x.strip()]
    return unflatten_to_model(flat)

# convenience for OpenAI function schema
def vacalyser_json_schema() -> Dict[str, Any]:
    schema = VacalyserJD.model_json_schema()
    if isinstance(schema, dict) and schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)
    return schema
