from __future__ import annotations
from typing import Dict, Any
from llm.prompts import make_job_ad_prompt, make_interview_prompt
from openai_utils import client, LLM_PROFILES

def job_ad_from_schema(data: Dict[str, Any], tone: str, lang: str) -> str:
    prompt = make_job_ad_prompt(data, tone, lang)
    prof = LLM_PROFILES["job_ad"]
    r = client().chat.completions.create(
        model=prof["model"], temperature=prof["temperature"],
        messages=[{"role": "system", "content": "You are a professional HR copywriter."},
                  {"role": "user", "content": prompt}],
        max_tokens=prof["max_tokens"]
    )
    return r.choices[0].message.content or ""

def interview_from_schema(data: Dict[str, Any], lang: str) -> str:
    prompt = make_interview_prompt(data, lang)
    prof = LLM_PROFILES["interview"]
    r = client().chat.completions.create(
        model=prof["model"], temperature=prof["temperature"],
        messages=[{"role": "system", "content": "You are an expert interviewer."},
                  {"role": "user", "content": prompt}],
        max_tokens=prof["max_tokens"]
    )
    return r.choices[0].message.content or ""
