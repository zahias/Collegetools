import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile, os, tempfile
from typing import Dict, List, Tuple

st.set_page_config(page_title="Advising Data Extractor", page_icon="🧭", layout="wide")

SHEET_NAME = "Current Semester Advising"
START_ROW_IDX = 7   # 0-based: row 8 in Excel
COURSE_COL = 0
STATUS_COL = 7

def read_advising_table_from_file(path: str) -> pd.DataFrame:
    """
    Reads the advising table starting at row index 7 (Excel row 8),
    taking column 0 as Course Code and column 7 as Status.
    Returns a DataFrame with columns: ['Course', 'Status'] (NaNs dropped).
    """
    try:
        df = pd.read_excel(path, sheet_name=SHEET_NAME, header=None)
    except Exception:
        return pd.DataFrame(columns=["Course", "Status"])

    # Slice from START_ROW_IDX onwards, take only needed columns
    if df.shape[1] <= max(COURSE_COL, STATUS_COL):
        return pd.DataFrame(columns=["Course", "Status"])

    sub = df.iloc[START_ROW_IDX:, [COURSE_COL, STATUS_COL]].copy()
    sub.columns = ["Course", "Status"]

    # Keep only non-empty courses
    sub["Course"] = sub["Course"].astype(str).str.strip()
    sub = sub[sub["Course"].notna() & (sub["Course"] != "")]

    # Normalize status (we only care about "Yes", "Optional", else treat as Not Advised if empty)
    sub["Status"] = sub["Status"].astype(str)
    sub.loc[sub["Status"].str.strip().eq("") | sub["Status"].str.lower().isin(["nan", "none"]), "Status"] = ""
    return sub

def collect_from_zip(uploaded_zip) -> List[Tuple[str, pd.DataFrame]]:
    """Return list of (student_label, advising_df) for each Excel file in the zip."""
    out = []
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(uploaded_zip, "r") as zf:
            zf.extractall(td)
        for root, _, files in os.walk(td):
            for f in files:
                if f.endswith((".xlsx", ".xls")):
                    p = os.path.join(root, f)
                    df = read_advising_table_from_file(p)
                    label = os.path.splitext(os.path.basename(f))[0]  # use filename as student label
                    out.append((label, df))
    return out

def collect_from_filelist(files) -> List[Tuple[str, pd.DataFrame]]:
    """Same as above but for multiple uploaded files (not zipped)."""
    out = []
    for f in files:
        try:
            # save to temp to allow pandas openpyxl to read
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(f.read())
                tmp.flush()
                df = read_advising_table_from_file(tmp.name)
            label = os.path.splitext(f.name)[0]
            out.append((label, df))
        except Exception:
            out.append((f.name, pd.DataFrame(columns=["Course", "Status"])))
    return out

def make_advising_summary(student_tables: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """
    Task 1:
    For each course across all files, count 'Yes', 'Optional', 'Not Advised' (empty).
    """
    rows = []
    for _, df in student_tables:
        if df.empty:
            continue
        # For each course within a student, derive a single status value.
        # Priority: "Yes" > "Optional" > "" (Not Advised). If duplicates, keep the strongest.
        df_local = df.copy()
        df_local["Course"] = df_local["Course"].str.upper().str.strip()
        df_local["StatusNorm"] = df_local["Status"].str.strip().str.title()
        df_local["StatusNorm"] = df_local["StatusNorm"].where(df_local["StatusNorm"].isin(["Yes", "Optional"]), "")
        # Keep strongest per course for this student
        rank = {"Yes": 2, "Optional": 1, "": 0}
        df_best = (df_local
                   .assign(_r=df_local["StatusNorm"].map(rank))
                   .sort_values(["Course", "_r"], ascending=[True, False])
                   .drop_duplicates(subset=["Course"], keep="first")
                   .drop(columns="_r"))
        rows.append(df_best[["Course", "StatusNorm"]])
    if not rows:
        return pd.DataFrame(columns=["Course Code", "Yes Count", "Optional Count", "Not Advised Count"])

    all_df = pd.concat(rows, ignore_index=True)

    # Build counts per course
    yes = (all_df["StatusNorm"] == "Yes").groupby(all_df["Course"]).sum()
    opt = (all_df["StatusNorm"] == "Optional").groupby(all_df["Course"]).sum()
    # "Not Advised" = total students who had that course row but not advised;
    # BUT spec says empty cells/NaN indicate not advised. To count per student:
    # We need the number of students who had the course in their sheet (any row for that course),
    # minus those marked Yes or Optional.
    total_per_course = all_df.groupby("Course").size()
    not_adv = total_per_course - yes - opt

    summary = pd.DataFrame({
        "Course Code": total_per_course.index,
        "Yes Count": yes.values.astype(int),
        "Optional Count": opt.values.astype(int),
        "Not Advised Count": not_adv.values.astype(int)
    }).sort_values("Course Code").reset_index(drop=True)

    return summary

def make_conflict_free_groups(student_tables: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """
    Task 2:
    For each student, take courses with Status == "Yes".
    Group unique sets (order-insensitive) and list associated students.
    """
    from collections import defaultdict

    groups = defaultdict(list)  # key=frozenset(courses), val=list of students

    for student, df in student_tables:
        if df.empty:
            continue
        df_local = df.copy()
        df_local["Course"] = df_local["Course"].astype(str).str.upper().str.strip()
        yes_courses = sorted(df_local.loc[df_local["Status"].astype(str).str.strip().str.lower() == "yes", "Course"].unique())
        key = frozenset(yes_courses)
        groups[key].append(student)

    if not groups:
        return pd.DataFrame(columns=["Students"])

    # Build a rectangular table: Students | Course 1 | Course 2 | ...
    max_len = max((len(k) for k in groups.keys()), default=0)
    cols = ["Students"] + [f"Course {i}" for i in range(1, max_len + 1)]

    rows = []
    for course_set, students in groups.items():
        course_list = sorted(list(course_set))
        row = {
            "Students": ", ".join(sorted(students))
        }
        for i, crs in enumerate(course_list, start=1):
            row[f"Course {i}"] = crs
        rows.append(row)

    # Normalize missing columns with empty strings
    for r in rows:
        for c in cols:
            r.setdefault(c, "")
    df_out = pd.DataFrame(rows, columns=cols).sort_values("Students").reset_index(drop=True)
    return df_out

# --------------------- UI ---------------------
st.title("🧭 Advising Data Extractor")
st.markdown("""
Upload either **a .zip** containing many Excel files (one per student), **or** upload multiple Excel files directly.

**Source of truth per file:**  
Sheet **"Current Semester Advising"**, starting **row 8 (index 7)**  
- **Column 0** = Course Code  
- **Column 7** = Advising Status (`"Yes"`, `"Optional"`, or empty for *Not Advised*)  
""")

c_zip, c_files = st.columns(2)
zip_up = c_zip.file_uploader("Upload a .zip of advising sheets", type=["zip"])
files_up = c_files.file_uploader("Or upload multiple Excel files", type=["xlsx", "xls"], accept_multiple_files=True)

if st.button("Run Extraction", type="primary"):
    with st.spinner("Reading and aggregating…"):
        tables = []
        if zip_up:
            tables.extend(collect_from_zip(zip_up))
        if files_up:
            tables.extend(collect_from_filelist(files_up))

        # Filter out completely unreadable files
        tables = [(s, df) for (s, df) in tables if isinstance(df, pd.DataFrame)]

        # ----- Task 1: Advising Summary -----
        summary_df = make_advising_summary(tables)

        # ----- Task 2: Conflict-Free Course Groups -----
        groups_df = make_conflict_free_groups(tables)

    # ---------- Display & Downloads ----------
    st.subheader("Task 1 — Advising Summary")
    if summary_df.empty:
        st.info("No courses found in the uploaded files.")
    else:
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        out1 = BytesIO()
        summary_df.to_excel(out1, engine="openpyxl", index=False, sheet_name="Advising_Summary")
        st.download_button("📥 Download Advising Summary (Excel)", out1.getvalue(),
                           file_name="advising_summary.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.subheader("Task 2 — Conflict-Free Course Groups")
    if groups_df.empty:
        st.info("No 'Yes' groupings detected.")
    else:
        st.dataframe(groups_df, use_container_width=True, hide_index=True)
        out2 = BytesIO()
        groups_df.to_excel(out2, engine="openpyxl", index=False, sheet_name="Course_Groups")
        st.download_button("📥 Download Course Groups (Excel)", out2.getvalue(),
                           file_name="advising_course_groups.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with st.expander("Notes & Assumptions"):
    st.markdown("""
- If a student sheet repeats a course multiple times with different statuses, the extractor keeps the **strongest** status for counting:
  **Yes > Optional > Not Advised**.
- Student label in the output uses the **file name** (without extension).  
- Summary counts **per course** reflect the number of students who had that course row in their sheet and how many were labeled **Yes**, **Optional**, or left empty (**Not Advised**).
""")
