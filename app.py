"""Entry point. Streamlit auto-discovers pages/ — this file redirects to Ask by default."""
import streamlit as st

st.set_page_config(
    page_title="Freeform CA — Cymbal Retail",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.switch_page("pages/1_💬_Ask.py")
