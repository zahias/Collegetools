import streamlit as st

st.set_page_config(
    page_title="PU PBHL Department Tools",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎓 PU PBHL Department Academic Data Tools")
st.markdown("""
Welcome! Choose a tool from the sidebar:

1. **Grade Data Transformer** – turn wide, messy grade spreadsheets into a tidy dataset.
2. **Internship Data Consolidator** – read many student files and consolidate completed internship hours.
3. **Advising Data Extractor** – summarize advising statuses and discover unique *non-conflicting* course groups across students.
""")

# Always render manual nav (works even if auto list doesn’t)
st.sidebar.header("Navigate")
try:
    st.sidebar.page_link("app.py", label="🏠 Home")
    st.sidebar.page_link("pages/01_Grade_Data_Transformer.py", label="📊 Grade Data Transformer")
    st.sidebar.page_link("pages/02_Internship_Data_Consolidator.py", label="🎓 Internship Data Consolidator")
    st.sidebar.page_link("pages/03_Advising_Data_Extractor.py", label="🧭 Advising Data Extractor")
except Exception:
    st.sidebar.info("If you don't see pages, ensure there's a `pages/` folder with .py files next to app.py.")
