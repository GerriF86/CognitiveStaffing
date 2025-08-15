from __future__ import annotations
from typing import Dict, Any, List
from core.schema import VacalyserJD, flatten_model

def make_job_ad_prompt(data: Dict[str, Any], tone: str, lang: str) -> str:
    jd = VacalyserJD.model_validate(data)
    # auto-build bullet list from schema fields (selected)
    bullets: List[str] = []
    if jd.company.name: bullets.append(f"Company: {jd.company.name}")
    if jd.position.job_title: bullets.append(f"Role: {jd.position.job_title}")
    if jd.position.role_summary: bullets.append(f"Summary: {jd.position.role_summary}")
    if jd.responsibilities.items: bullets.append("Responsibilities: " + "; ".join(jd.responsibilities.items[:10]))
    if jd.requirements.hard_skills: bullets.append("Hard Skills: " + ", ".join(jd.requirements.hard_skills[:12]))
    if jd.requirements.soft_skills: bullets.append("Soft Skills: " + ", ".join(jd.requirements.soft_skills[:8]))
    if jd.compensation.benefits: bullets.append("Benefits: " + ", ".join(jd.compensation.benefits[:10]))
    wp = jd.employment.work_policy + (f" ({jd.employment.remote_policy})" if jd.employment.remote_policy else "")
    if wp.strip(): bullets.append(f"Work Policy: {wp}")
    if jd.employment.travel_required: bullets.append(f"Travel: {jd.employment.travel_details or 'Yes'}")
    if jd.compensation.salary_provided and (jd.compensation.salary_min or jd.compensation.salary_max):
        bullets.append(f"Salary: {jd.compensation.salary_min:.0f}-{jd.compensation.salary_max:.0f} {jd.compensation.salary_currency}/{jd.compensation.salary_period}")
    if jd.company.mission: bullets.append(f"Mission: {jd.company.mission}")
    if jd.company.culture: bullets.append(f"Culture: {jd.company.culture}")

    prompt = f"""You are an HR copywriter.
Language: {lang}
Tone: {tone}
Create a modern, inclusive job ad in Markdown.
Use sections: About, Responsibilities, Requirements, Benefits, How to apply.
Details:
- """ + "\n- ".join(bullets)
    return prompt

def make_interview_prompt(data: Dict[str, Any], lang: str) -> str:
    jd = VacalyserJD.model_validate(data)
    hs = ", ".join(jd.requirements.hard_skills[:10]) or "—"
    ss = ", ".join(jd.requirements.soft_skills[:8]) or "—"
    resp = "; ".join(jd.responsibilities.items[:8]) or "—"
    return f"""Create an interview guide.
Language: {lang}
Job Title: {jd.position.job_title}
Responsibilities: {resp}
Hard Skills: {hs}
Soft Skills: {ss}
Return a Markdown document with sections and evaluation criteria."""
