from __future__ import annotations
import os, json, re, base64, requests
from typing import Any, Dict, Optional, List
from bs4 import BeautifulSoup
from openai import OpenAI
from core.schema import VacalyserJD, vacalyser_json_schema

# -------- OpenAI client ----------
_client_singleton: Optional[OpenAI] = None
def client() -> OpenAI:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = OpenAI()
    return _client_singleton

# -------- Robust JSON repair -----
def _strip_code_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?", "", s, flags=re.I).strip()
    s = re.sub(r"```$", "", s).strip()
    return s

def _repair_json(blob: str) -> Dict[str, Any]:
    s = _strip_code_fences(blob)
    l, r = s.find("{"), s.rfind("}")
    if l != -1 and r != -1 and r > l:
        s = s[l:r+1]
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)

# -------- LLM profiles ----------
def stable_seed(*parts: str, base: int = 20240823) -> int:
    import zlib
    return (base ^ zlib.crc32(("||".join(parts)).encode("utf-8"))) & 0x7FFFFFFF

LLM_PROFILES = {
    "extract":      {"model": os.getenv("OPENAI_MODEL", "gpt-4o"),     "temperature": 0.0,  "max_tokens": 1500},
    "company_info": {"model": "gpt-4o-mini", "temperature": 0.15, "max_tokens": 700},
    "reask_q":      {"model": "gpt-4o-mini", "temperature": 0.2,  "max_tokens": 180},
    "reask_sugg":   {"model": "gpt-4o-mini", "temperature": 0.3,  "max_tokens": 220},
    "skills":       {"model": "gpt-4o-mini", "temperature": 0.3,  "max_tokens": 260},
    "benefits":     {"model": "gpt-4o-mini", "temperature": 0.3,  "max_tokens": 260},
    "job_ad":       {"model": "gpt-4o",     "temperature": 0.55, "max_tokens": 1200},
    "interview":    {"model": "gpt-4o",     "temperature": 0.5,  "max_tokens": 1100},
    "refine":       {"model": "gpt-4o",     "temperature": 0.5,  "max_tokens": 900},
    "boolean":      {"model": "gpt-4o-mini","temperature": 0.1,  "max_tokens": 180},
}

# -------- Extraction with function-calling + fallbacks ----------
def extract_structured_from_text(raw_text: str, lang: str = "en") -> Dict[str, Any]:
    prof = LLM_PROFILES["extract"]
    mdl = prof["model"]
    sys = ("You are a strict extraction engine. "
           "Return ONLY structured data as function arguments matching the given JSON schema.")
    user = f"Extract all vacancy fields from the following text. Language hint: {lang}\n\n{raw_text}"
    tools = [{
        "type": "function",
        "function": {
            "name": "vacalyser_extract",
            "description": "Return all fields for VacalyserJD",
            "parameters": vacalyser_json_schema()
        }
    }]
    # 1) Function-calling enforced
    try:
        r = client().chat.completions.create(
            model=mdl, temperature=0, seed=stable_seed("extract", str(len(raw_text))),
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            tools=tools, tool_choice={"type": "function", "function": {"name": "vacalyser_extract"}},
            max_tokens=prof["max_tokens"],
        )
        msg = r.choices[0].message
        if getattr(msg, "tool_calls", None):
            return json.loads(msg.tool_calls[0].function.arguments)
        if getattr(msg, "function_call", None):
            return json.loads(msg.function_call.arguments)
    except Exception as e:
        last = f"[function_call] {e}"
    # 2) JSON mode
    try:
        r2 = client().chat.completions.create(
            model=mdl, temperature=0, seed=stable_seed("extract-json", str(len(raw_text))),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys + " Respond ONLY with a JSON object."},
                {"role": "user", "content": user},
            ],
            max_tokens=prof["max_tokens"]
        )
        return _repair_json(r2.choices[0].message.content or "{}")
    except Exception as e2:
        last = f"{last} | [json_mode] {e2}"
    # 3) Repair parser on plain text
    try:
        r3 = client().chat.completions.create(
            model=mdl, temperature=0, seed=stable_seed("extract-repair", str(len(raw_text))),
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": user}],
            max_tokens=prof["max_tokens"]
        )
        return _repair_json(r3.choices[0].message.content or "{}")
    except Exception as e3:
        raise RuntimeError(f"Could not parse AI response as JSON. Details: {last} | [repair] {e3}")

# -------- Company info agent ----------
def _fetch_url_text(url: str) -> str:
    try:
        res = requests.get(url, timeout=12)
        res.raise_for_status()
        html = res.text
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        return " ".join(soup.get_text(" ").split())
    except Exception:
        return ""

def extract_company_info(website_url: str, lang: str = "en") -> Dict[str, Any]:
    text = _fetch_url_text(website_url) or ""
    if not text:
        return {}
    prof = LLM_PROFILES["company_info"]
    mdl = prof["model"]
    system = ("Extract company facts. Return a strict JSON with "
              "{name, website, hq_location, city, country, mission, culture}. "
              "Do not invent; leave empty if not found.")
    user = f"WEBSITE TEXT:\n{text[:10000]}\n\nURL: {website_url}\nLanguage: {lang}"
    # Prefer JSON-mode
    try:
        r = client().chat.completions.create(
            model=mdl, temperature=prof["temperature"], seed=stable_seed("company", website_url),
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=prof["max_tokens"]
        )
        return _repair_json(r.choices[0].message.content or "{}")
    except Exception:
        # fallback: plain + repair
        r2 = client().chat.completions.create(
            model=mdl, temperature=prof["temperature"], seed=stable_seed("company2", website_url),
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=prof["max_tokens"]
        )
        return _repair_json(r2.choices[0].message.content or "{}")

# -------- Generators ----------
def generate_job_ad(data: Dict[str, Any], tone: str = "neutral", lang: str = "en") -> str:
    prof = LLM_PROFILES["job_ad"]; mdl = prof["model"]
    jd = VacalyserJD.model_validate(data)
    # compact details list:
    details = []
    c = jd.company; p = jd.position; loc = jd.location
    emp = jd.employment; comp = jd.compensation
    if c.name: details.append(f"Company: {c.name}")
    if p.job_title: details.append(f"Role: {p.job_title}")
    if loc.primary_city: details.append(f"Location: {loc.primary_city}, {loc.country or ''}".strip(", "))
    if p.role_summary: details.append(f"Summary: {p.role_summary}")
    if emp.work_policy:
        wp = emp.work_policy + (f" ({emp.remote_policy})" if emp.remote_policy else "")
        details.append(f"Work Policy: {wp}")
    if emp.travel_required:
        details.append(f"Travel: {jd.employment.travel_details or 'Yes'}")
    if comp.salary_provided and (comp.salary_min or comp.salary_max):
        details.append(f"Salary: {comp.salary_min:.0f}-{comp.salary_max:.0f} {comp.salary_currency} / {comp.salary_period}")
    if comp.benefits:
        details.append("Benefits: " + ", ".join(comp.benefits[:12]))
    if jd.requirements.hard_skills:
        details.append("Hard Skills: " + ", ".join(jd.requirements.hard_skills[:15]))
    if jd.requirements.soft_skills:
        details.append("Soft Skills: " + ", ".join(jd.requirements.soft_skills[:10]))
    if jd.responsibilities.items:
        details.append("Key Responsibilities: " + "; ".join(jd.responsibilities.items[:10]))

    system = ("You are a professional HR copywriter. Write a modern, bias-aware job ad in Markdown. "
              "Use concise sections: About, Responsibilities (bullets), Requirements (bullets), Benefits, How to Apply. "
              "Avoid discriminatory language.")
    user = f"Tone: {tone}\nLanguage: {lang}\nDetails:\n- " + "\n- ".join(details)
    r = client().chat.completions.create(
        model=mdl, temperature=prof["temperature"],
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        max_tokens=prof["max_tokens"]
    )
    return r.choices[0].message.content or ""

def generate_interview_guide(data: Dict[str, Any], lang: str = "en") -> str:
    prof = LLM_PROFILES["interview"]; mdl = prof["model"]
    jd = VacalyserJD.model_validate(data)
    hs = ", ".join(jd.requirements.hard_skills[:10]) or "—"
    ss = ", ".join(jd.requirements.soft_skills[:8]) or "—"
    resp = "; ".join(jd.responsibilities.items[:8]) or "—"
    system = "You are an expert interviewer. Produce a structured interview guide in Markdown."
    user = f"Language: {lang}\nJob Title: {jd.position.job_title}\nResponsibilities: {resp}\nHard Skills: {hs}\nSoft Skills: {ss}\nReturn sections with questions and evaluation criteria."
    r = client().chat.completions.create(
        model=mdl, temperature=prof["temperature"],
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        max_tokens=prof["max_tokens"]
    )
    return r.choices[0].message.content or ""

def refine_document(original: str, instructions: str, lang: str = "en") -> str:
    prof = LLM_PROFILES["refine"]; mdl = prof["model"]
    system = "Revise the given document according to the instructions. Keep Markdown. Do not add unrelated content."
    user = f"Language: {lang}\n=== ORIGINAL START ===\n{original}\n=== ORIGINAL END ===\nInstructions:\n{instructions}"
    r = client().chat.completions.create(
        model=mdl, temperature=prof["temperature"],
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        max_tokens=prof["max_tokens"]
    )
    return r.choices[0].message.content or ""

def build_boolean_query(data: Dict[str, Any]) -> str:
    jd = VacalyserJD.model_validate(data)
    title = f'"{jd.position.job_title}"' if jd.position.job_title else ""
    skills = [*jd.requirements.hard_skills, *jd.requirements.tools_and_technologies]
    skills_q = " AND ".join(f'("{s}")' for s in skills[:6])
    where = jd.location.primary_city or jd.company.hq_location
    parts = [p for p in [title, skills_q, where] if p]
    return " AND ".join(parts)
