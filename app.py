import streamlit as st

st.set_page_config(
    page_title="PU PBHL Department Tools",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",  # <- forces sidebar open
)

st.title("🎓 PU PBHL Department Academic Data Tools")
st.markdown("""
Welcome! Choose a tool from the sidebar:

1. **📊 Grade Data Transformer** – turn wide, messy grade spreadsheets into a tidy dataset.
2. **🎓 Internship Data Consolidator** – read many student files and consolidate completed internship hours.
3. **🧭 Advising Data Extractor** – summarize advising statuses and discover unique *non-conflicting* course groups across students.
""")

# --- Always show a manual nav in the sidebar ---
st.sidebar.header("Navigate")
try:
    # Works on modern Streamlit (st.page_link)
    st.sidebar.page_link("app.py", label="🏠 Home")
    st.sidebar.page_link("pages/01_📊_Grade_Data_Transformer.py", label="📊 Grade Data Transformer")
    st.sidebar.page_link("pages/02_🎓_Internship_Data_Consolidator.py", label="🎓 Internship Data Consolidator")
    st.sidebar.page_link("pages/03_🧭_Advising_Data_Extractor.py", label="🧭 Advising Data Extractor")
except Exception:
    # Fallback for older Streamlit versions
    st.sidebar.write("Use the built-in page switcher (☰ at top-left).")
    st.sidebar.write("Pages are in the `/pages` folder.")
