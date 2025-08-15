import streamlit as st
import pandas as pd
import altair as alt

def render_salary_dashboard(jd: dict):
    comp = jd.get("compensation", {})
    if not comp or not comp.get("salary_provided"):
        st.info("No salary data provided.")
        return
    df = pd.DataFrame([{
        "min": comp.get("salary_min", 0.0),
        "max": comp.get("salary_max", 0.0),
        "currency": comp.get("salary_currency", "EUR"),
        "period": comp.get("salary_period", "year"),
    }])
    st.write("**Salary Range**")
    chart = alt.Chart(df).mark_bar().encode(
        x="min", x2="max", y=alt.value(20),
        tooltip=["min","max","currency","period"]
    )
    st.altair_chart(chart, use_container_width=True)
