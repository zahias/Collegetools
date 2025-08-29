import streamlit as st

st.set_page_config(
    page_title="PU PBHL Department Tools",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎓 PU PBHL Department Academic Data Tools")
st.markdown("""
Use the sidebar to switch between tools:
- **Grade Data Transformer** – tidy wide grade sheets
- **Internship Data Consolidator** – compile internship hours across student files
- **Advising Data Extractor** – summarize advising statuses + list unique 'Yes' course groups
""")

# Sidebar navigation
st.sidebar.header("Navigate")
page = st.sidebar.radio(
    "Go to:",
    ["📊 Grade Data Transformer", "🎓 Internship Data Consolidator", "🧭 Advising Data Extractor"],
    index=0,
)

# Lazy imports so cold starts are faster
if page.startswith("📊"):
    from features.grade_transformer import run as run_grade
    run_grade()
elif page.startswith("🎓"):
    from features.internship_consolidator import run as run_intern
    run_intern()
else:
    from features.advising_extractor import run as run_adv
    run_adv()
