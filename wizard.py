from __future__ import annotations
import streamlit as st
from typing import Dict, Any, List, Optional
from core.schema import VacalyserJD, FIELDS_BY_SECTION, CRITICAL_FIELDS, flatten_model, coerce_and_fill
from openai_utils import extract_structured_from_text, extract_company_info, generate_job_ad, generate_interview_guide, build_boolean_query

# -------------------------
# INIT & PENDING-UPDATE SAFE-APPLIER (pre-widget)
# -------------------------
def _init_state():
    st.session_state.setdefault("lang", "en")
    st.session_state.setdefault("current_section", 0)
    st.session_state.setdefault("extraction_complete", False)
    st.session_state.setdefault("__apply_pending_updates__", False)

    if st.session_state.pop("__apply_pending_updates__", False):
        pending: Dict[str, Any] = st.session_state.pop("__pending_updates__", {})
        for k, v in pending.items():
            st.session_state[k] = v

# -------------------------
# UTIL: TEXT EXTRACTION (simple, inline to avoid extra module)
# -------------------------
def _read_file_to_text(uploaded) -> str:
    if not uploaded: return ""
    name = uploaded.name.lower()
    if name.endswith(".txt"):
        return uploaded.read().decode("utf-8", "ignore")
    if name.endswith(".docx"):
        from docx import Document
        d = Document(uploaded)
        return "\n".join(p.text for p in d.paragraphs)
    if name.endswith(".pdf"):
        import fitz
        doc = fitz.open(stream=uploaded.read(), filetype="pdf")
        text = []
        for pg in doc:
            text.append(pg.get_text() or "")
        return "\n".join(text)
    return ""

def _read_url_to_text(url: str) -> str:
    if not url: return ""
    try:
        import requests
        from bs4 import BeautifulSoup
        res = requests.get(url, timeout=12)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")
        for t in soup(["script", "style", "noscript"]): t.extract()
        return " ".join(soup.get_text(" ").split())
    except Exception:
        return ""

# -------------------------
# FOLLOW-UP (very light): report missing criticals for current section
# -------------------------
def _missing_for_section(sec: int) -> List[str]:
    keys = FIELDS_BY_SECTION.get(sec, [])
    missing = []
    for k in keys:
        v = st.session_state.get(k, "")
        if isinstance(v, list):
            if not v: missing.append(k)
        else:
            if not v and k in CRITICAL_FIELDS:
                missing.append(k)
    return missing

# -------------------------
# RENDERERS
# -------------------------
def _header(title_en: str, title_de: str):
    st.markdown(f"### {title_de if st.session_state['lang']=='de' else title_en}")

def _kv_overview(keys: List[str]):
    cols = st.columns(2)
    for i, k in enumerate(keys):
        v = st.session_state.get(k, "")
        if v:
            with cols[i % 2]:
                if isinstance(v, list):
                    st.write(f"**{k}**")
                    st.write(", ".join(v))
                else:
                    st.write(f"**{k}**: {v}")

def _text(key: str, label: str):
    st.text_input(label, key=key)

def _textarea(key: str, label: str, height=120):
    st.text_area(label, height=height, key=key)

def _checkbox(key: str, label: str):
    st.checkbox(label, key=key)

def _number(key: str, label: str, min_value=0, step=1):
    st.number_input(label, key=key, min_value=min_value, step=step)

def _select(key: str, label: str, options: List[str]):
    st.selectbox(label, options=options, key=key)

def editable_list(key: str, label: str, add_label="Add"):
    st.write(f"**{label}**")
    new = st.text_input(f"New {label}", key=f"__i__{key}")
    if st.button(add_label, key=f"__b__{key}"):
        items = list(st.session_state.get(key, []))
        if new and new.strip():
            items.append(new.strip())
            # Pending update to avoid post-instantiation write:
            st.session_state["__pending_updates__"] = {key: items}
            st.session_state["__apply_pending_updates__"] = True
            st.rerun()
    # show current
    cur = st.session_state.get(key, [])
    if cur:
        st.caption(", ".join(cur))

# -------------------------
# SECTIONS
# -------------------------
def render_welcome():
    st.markdown("# 🔎 Start Your Analysis with Vacalyzer")
    st.write("Avoid expensive information loss. Upload a job ad, paste a URL or type a job title. We’ll extract everything we can and ask only what’s missing.")

    col1, col2 = st.columns([2,1])
    with col1:
        st.text_input("Job Title", key="position.job_title")
        st.text_input("Job Ad URL (optional)", key="__url__")
    with col2:
        uploaded = st.file_uploader("Upload Job Ad (PDF, DOCX, TXT)", type=["pdf","docx","txt"], key="__file__")

    if uploaded:
        st.success("✅ File uploaded.")
    if st.button("🚀 Start Discovery"):
        raw = ""
        raw += _read_file_to_text(uploaded)
        raw += "\n" + _read_url_to_text(st.session_state.get("__url__", ""))
        if not raw.strip():
            st.error("Please provide a file or URL or job title text.")
            st.stop()
        try:
            extracted = extract_structured_from_text(raw, lang=st.session_state["lang"])
            jd = coerce_and_fill(extracted)
            # move to session-state BEFORE widgets of next page
            st.session_state["__pending_updates__"] = flatten_model(jd)
            st.session_state["__apply_pending_updates__"] = True
            st.session_state["extraction_complete"] = True
            st.session_state["current_section"] = 1
            st.rerun()
        except Exception as e:
            st.error(f"❌ Could not parse AI response as JSON. {e}")
    st.stop()

def render_company():
    _header("🏢 Company Information", "🏢 Firmeninformationen")
    keys = FIELDS_BY_SECTION[1]
    _kv_overview(keys)
    _text("company.name", "Company Name")
    _select("company.industry", "Industry", ["", "Information Technology", "Finance", "Manufacturing", "Healthcare", "Retail"])
    _text("company.hq_location", "Headquarters Location")
    _select("company.size", "Company Size", ["", "1-10","11-50","51-200","201-500","501-1000","1001-5000","5001+"])
    _text("location.primary_city", "City")
    _text("location.country", "Country")
    _text("company.website", "Company Website")
    if st.button("🔄 Fetch Company Info from Website"):
        url = st.session_state.get("company.website", "")
        info = extract_company_info(url, st.session_state["lang"]) if url else {}
        pend = {}
        mapping = {
            "company.name": info.get("name", ""),
            "company.website": info.get("website", url),
            "company.hq_location": info.get("hq_location",""),
            "location.primary_city": info.get("city",""),
            "location.country": info.get("country",""),
            "company.mission": info.get("mission",""),
            "company.culture": info.get("culture",""),
        }
        for dest, val in mapping.items():
            if val:
                pend[dest] = val
        st.session_state["__pending_updates__"] = pend
        st.session_state["__apply_pending_updates__"] = True
        st.success("✅ Company information updated")
        st.rerun()
    _textarea("company.mission", "Company Mission")
    _textarea("company.culture", "Company Culture")

def render_role():
    _header("👤 Role Description", "👤 Rollenbeschreibung")
    _text("position.job_title", "Job Title")
    _textarea("position.role_summary", "Role Summary / Objective")
    _text("position.department", "Department")
    _text("position.team_structure", "Team Structure")
    _text("position.reporting_line", "Reporting Line")
    _select("position.seniority_level", "Seniority", ["", "Junior", "Mid", "Senior", "Lead", "Head"])

def render_responsibilities():
    _header("🧭 Responsibilities", "🧭 Verantwortlichkeiten")
    editable_list("responsibilities.items", "Key Responsibilities", add_label="Add Responsibility")

def render_requirements():
    _header("🧩 Requirements", "🧩 Anforderungen")
    editable_list("requirements.hard_skills", "Hard Skills")
    editable_list("requirements.soft_skills", "Soft Skills")
    editable_list("requirements.tools_and_technologies", "Tools & Technologies")
    editable_list("requirements.languages_required", "Languages")
    editable_list("requirements.certifications", "Certifications")

def render_compensation():
    _header("💼 Employment & Compensation", "💼 Anstellung & Vergütung")
    _select("employment.job_type", "Employment Type", ["", "Full-time","Part-time","Contract","Working student","Internship"])
    _select("employment.work_policy", "Work Policy", ["", "Onsite","Hybrid","Remote"])
    _checkbox("employment.travel_required", "Travel required")
    _text("employment.remote_policy", "Remote Work Policy")
    _text("employment.travel_details", "Travel Requirements")
    _checkbox("compensation.salary_provided", "Salary information provided")
    if st.session_state.get("compensation.salary_provided", False):
        _number("compensation.salary_min", "Salary Min", 0, 1000)
        _number("compensation.salary_max", "Salary Max", 0, 1000)
        _select("compensation.salary_currency", "Currency", ["EUR","USD","GBP","CHF"])
        _select("compensation.salary_period", "Period", ["year","month","hour"])
    editable_list("compensation.benefits", "Benefits/Perks")
    _textarea("compensation.healthcare_plan", "Healthcare Plan")
    _textarea("compensation.pension_plan", "Pension Plan")
    _checkbox("compensation.variable_pay", "Variable Pay")
    _checkbox("compensation.equity_offered", "Equity Offered")

def render_process():
    _header("🧪 Hiring Process", "🧪 Einstellungsprozess")
    _number("process.interview_stages", "Interview Stages", 0, 1)
    _textarea("process.process_notes", "Process Notes", height=160)

def render_summary():
    _header("📦 Summary & Outputs", "📦 Zusammenfassung & Ergebnisse")
    jd = VacalyserJD.model_validate({k: v for k, v in st.session_state.items() if isinstance(k, str) and "." in k})
    colA, colB = st.columns(2)
    with colA:
        st.write("**Company:**", jd.company.name or "—")
        st.write("**Role:**", jd.position.job_title or "—")
        st.write("**Location:**", (jd.location.primary_city + (", " + jd.location.country if jd.location.country else "")) or "—")
    with colB:
        st.write("**Work Policy:**", jd.employment.work_policy or "—")
        st.write("**Salary:**", f"{jd.compensation.salary_min:.0f}-{jd.compensation.salary_max:.0f} {jd.compensation.salary_currency}/{jd.compensation.salary_period}" if jd.compensation.salary_provided else "—")
        st.write("**Benefits:**", ", ".join(jd.compensation.benefits[:10]) or "—")
    st.divider()

    with st.expander("📑 JSON Preview", expanded=False):
        st.json(jd.model_dump(), expanded=False)

    col1, col2, col3 = st.columns(3)
    with col1:
        tone = st.selectbox("Tone", ["neutral","formal","creative","inclusive"], index=0, key="__tone__")
    with col2:
        model_choice = st.selectbox("Model", ["gpt-4o","gpt-4.1","gpt-4o-mini"], index=0, key="__model__")
    with col3:
        lang = st.selectbox("Language", ["en","de"], index=0, key="__out_lang__")

    if st.button("🎯 Generate Job Ad"):
        txt = generate_job_ad(jd.model_dump(), tone=tone, lang=lang)
        st.session_state["__jobad__"] = txt
    if st.button("🎤 Generate Interview Guide"):
        ig = generate_interview_guide(jd.model_dump(), lang=lang)
        st.session_state["__interview__"] = ig

    if st.session_state.get("__jobad__"):
        st.subheader("Job Ad (Markdown)")
        st.markdown(st.session_state["__jobad__"])
    if st.session_state.get("__interview__"):
        st.subheader("Interview Guide (Markdown)")
        st.markdown(st.session_state["__interview__"])

    st.divider()
    st.write("**Boolean Search:**")
    st.code(build_boolean_query(jd.model_dump()))

# -------------------------
# NAVIGATION
# -------------------------
SECTIONS = {
    0: ("Welcome", render_welcome),
    1: ("Company", render_company),
    2: ("Role", render_role),
    3: ("Responsibilities", render_responsibilities),
    4: ("Requirements", render_requirements),
    5: ("Compensation", render_compensation),
    6: ("Process", render_process),
    7: ("Summary", render_summary),
}

def nav_controls():
    sec = st.session_state["current_section"]
    if sec == 0:  # welcome has own stop
        return
    cols = st.columns([1,1,6])
    with cols[0]:
        if st.button("⬅ Previous") and sec > 1:
            st.session_state["current_section"] = sec - 1
            st.rerun()
    with cols[1]:
        if sec < 7:
            missing = _missing_for_section(sec)
            if missing:
                st.warning("Please fill critical fields: " + ", ".join(missing))
            else:
                if st.button("Next ➡"):
                    st.session_state["current_section"] = sec + 1
                    st.rerun()

def run_wizard():
    _init_state()
    sec = st.session_state["current_section"]
    title, renderer = SECTIONS.get(sec, SECTIONS[0])
    renderer()
    # each renderer calls st.stop except summary/others
    nav_controls()
