import streamlit as st

st.set_page_config(
    page_title="PU PBHL Department Tools",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 PU PBHL Department Academic Data Tools")

st.markdown("""
Welcome! Choose a tool from the sidebar:

1. **📊 Grade Data Transformer** – turn wide, messy grade spreadsheets into a tidy dataset.
2. **🎓 Internship Data Consolidator** – read many student files and consolidate completed internship hours.
3. **🧭 Advising Data Extractor** – summarize advising statuses and discover unique *non-conflicting* course groups across students.
""")
