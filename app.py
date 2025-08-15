import streamlit as st
from wizard import run_wizard
from components.salary_dashboard import render_salary_dashboard
from pathlib import Path

st.set_page_config(
    page_title="Vacalyzer — Cognitive Staffing",
    page_icon="🧠",
    layout="wide",
)

# --- Sidebar Navigation (Streamlit 1.48+: simple manual nav) ---
PAGES = {
    "Home": "home",
    "Advantages": "advantages",
    "Tech Overview": "tech",
}
with st.sidebar:
    page = st.radio("Navigation", list(PAGES.keys()), index=0)

# --- Shared top bar actions (optional minimal) ---
with st.sidebar.expander("⚙️ Settings", expanded=False):
    lang = st.selectbox("Language", ["en", "de"], index=0, key="lang")
    st.caption("Model can also be selected in Summary step.")

# --- Route ---
if PAGES[page] == "home":
    run_wizard()
elif PAGES[page] == "advantages":
    st.title("✨ Advantages")
    st.markdown("""
- Faster discovery with schema-driven prompts  
- Auto follow-ups for missing critical fields  
- Company mission & culture extraction from URL  
- SEO & bias scan for generated job ads  
- Download as JSON/DOCX/MD  
""")
elif PAGES[page] == "tech":
    st.title("🛠️ Tech Overview")
    st.markdown("""
**Stack:** Streamlit, Pydantic v2, OpenAI Python SDK v1, PyMuPDF, python-docx, readability-lxml, BeautifulSoup4.  
**Design:** Schema-first; LLM profiles per feature; safe SessionState updates; Function-Calling → JSON Mode → Repair-Parse fallback.  
**Next:** Vector-Store/RAG; persistent DB; multi-user auth; advanced analytics dashboards.
""")
