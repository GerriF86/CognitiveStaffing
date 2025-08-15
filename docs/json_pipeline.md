# Vacalyzer JSON Pipeline (Schema-Driven)

**Goal:** Single source of truth via `core/schema.py` (Pydantic v2).

## 1) Ingestion
- File (PDF/DOCX/TXT) → `_read_file_to_text` (PyMuPDF, python-docx)
- URL → `_read_url_to_text` (requests + lxml/bs4)
- Combined raw text → `openai_utils.extract_structured_from_text`

## 2) Extraction
- **Function-Calling enforced** using `VacalyserJD.model_json_schema()`
- Fallback: `response_format={"type":"json_object"}`
- Fallback: repair parser (strip codefences, trim to balanced `{..}`, fix trailing commas)

## 3) Normalization
- `coerce_and_fill(raw)`:
  - applies `ALIASES`
  - fills defaults from `VacalyserJD()`
  - coerces newline-delimited strings → lists
  - returns validated `VacalyserJD`

## 4) UI Binding
- Flattened model → `st.session_state` (dot-keys)
- **Safe updates** via `__pending_updates__` + `__apply_pending_updates__`
  (applied **before** widget construction), avoids Streamlit post-instantiation errors.

## 5) Generation
- `generate_job_ad` / `generate_interview_guide` use conservative LLM profiles
- Summary step: SEO/bias checks can be added; boolean query is built from title+skills.

## 6) Export
- `VacalyserJD.model_dump()` → JSON
- Future: DOCX/PDF export; RAG vector-store integration.

