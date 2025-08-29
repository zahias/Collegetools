import streamlit as st
import pandas as pd
from io import BytesIO
import os, tempfile
from typing import List, Tuple

# --------- Config per program/plan ---------
SHEET_NAME = "Current Semester Advising"
START_ROW_IDX = 7   # Excel row 8 (0-based)

PROGRAMS = {
    "PBHL": {"course_col": 0, "status_col": 7},
    # Both SPTH Old & New (based on provided samples) keep Course Code in column 1 and Status in column 7
    "SPTH_OLD": {"course_col": 1, "status_col": 7},
    "SPTH_NEW": {"course_col": 1, "status_col": 7},
}

def _normalize_status(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if not s:
        return ""
    s_lower = s.lower()
    if s_lower == "yes":
        return "Yes"
    if s_lower == "optional":
        return "Optional"
    # anything else (including "nan", "none") treated as empty -> Not Advised
    return ""

def _course_key(raw: str) -> str:
    """Uppercase + remove spaces to make ACCT201 and ACCT 201 group together."""
    if not isinstance(raw, str):
        return ""
    return "".join(raw.upper().split())

def read_advising_table_from_file(path: str, program_key: str) -> pd.DataFrame:
    """Extract [Course, CourseKey, Status] from the configured columns of the advising sheet."""
    cfg = PROGRAMS[program_key]
    try:
        df = pd.read_excel(path, sheet_name=SHEET_NAME, header=None)
    except Exception:
        return pd.DataFrame(columns=["Course", "CourseKey", "Status"])

    c_idx = cfg["course_col"]
    s_idx = cfg["status_col"]
    if df.shape[1] <= max(c_idx, s_idx):
        return pd.DataFrame(columns=["Course", "CourseKey", "Status"])

    sub = df.iloc[START_ROW_IDX:, [c_idx, s_idx]].copy()
    sub.columns = ["Course", "Status"]

    # Drop obvious header repeats like "Course Code" and empties
    sub["Course"] = sub["Course"].astype(str).str.strip()
    sub = sub[(sub["Course"] != "") & (~sub["Course"].str.fullmatch(r"(?i)course code"))]

    # Normalize the status into Yes/Optional/""
    sub["Status"] = sub["Status"].astype(str).apply(_normalize_status)

    # Add a normalized course key for grouping
    sub["CourseKey"] = sub["Course"].apply(_course_key)

    # Keep only rows with a non-empty CourseKey
    sub = sub[sub["CourseKey"] != ""]

    return sub[["Course", "CourseKey", "Status"]]

def collect_from_filelist(files, program_key: str) -> List[Tuple[str, pd.DataFrame]]:
    """Return [(student_label, df)] for multiple uploaded Excel files."""
    out = []
    for f in files:
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(f.read()); tmp.flush()
                df = read_advising_table_from_file(tmp.name, program_key)
            label = os.path.splitext(f.name)[0]
            out.append((label, df))
        except Exception:
            out.append((f.name, pd.DataFrame(columns=["Course","CourseKey","Status"])))
    return out

def make_advising_summary(student_tables: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Task 1: counts per CourseKey for Yes / Optional / Not Advised."""
    rows = []
    for _, df in student_tables:
        if df.empty: 
            continue
        d = df.copy()
        # For duplicated courses within a single student sheet, keep strongest status: Yes > Optional > ""
        rank = {"Yes": 2, "Optional": 1, "": 0}
        d = (d.assign(_r=d["Status"].map(rank))
               .sort_values(["CourseKey","_r"], ascending=[True, False])
               .drop_duplicates(subset=["CourseKey"], keep="first")
               .drop(columns="_r"))
        rows.append(d[["CourseKey","Status"]])

    if not rows:
        return pd.DataFrame(columns=["Course Code","Yes Count","Optional Count","Not Advised Count"])

    all_df = pd.concat(rows, ignore_index=True)
    yes = (all_df["Status"] == "Yes").groupby(all_df["CourseKey"]).sum()
    opt = (all_df["Status"] == "Optional").groupby(all_df["CourseKey"]).sum()
    total = all_df.groupby("CourseKey").size()
    not_adv = total - yes - opt

    out = pd.DataFrame({
        "Course Code": total.index,
        "Yes Count": yes.reindex(total.index, fill_value=0).astype(int).values,
        "Optional Count": opt.reindex(total.index, fill_value=0).astype(int).values,
        "Not Advised Count": not_adv.astype(int).values,
    }).sort_values("Course Code").reset_index(drop=True)
    return out

def make_conflict_free_groups(student_tables: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Task 2: build unique sets of 'Yes' courses per student using CourseKey."""
    from collections import defaultdict
    groups = defaultdict(list)
    for student, df in student_tables:
        if df.empty:
            continue
        yes_courses = sorted(df.loc[df["Status"] == "Yes", "CourseKey"].unique())
        key = frozenset(yes_courses)
        groups[key].append(student)

    if not groups:
        return pd.DataFrame(columns=["Students"])

    max_len = max((len(k) for k in groups.keys()), default=0)
    cols = ["Students"] + [f"Course {i}" for i in range(1, max_len+1)]
    rows = []
    for course_set, students in groups.items():
        course_list = sorted(list(course_set))
        row = {"Students": ", ".join(sorted(students))}
        for i, crs in enumerate(course_list, start=1):
            row[f"Course {i}"] = crs
        rows.append(row)

    for r in rows:
        for c in cols:
            r.setdefault(c, "")

    return pd.DataFrame(rows, columns=cols).sort_values("Students").reset_index(drop=True)

def run():
    st.subheader("🧭 Advising Data Extractor")

    # Program & plan selection
    program = st.selectbox("Program", ["PBHL", "SPTH"], index=0)
    plan = None
    program_key = "PBHL"
    if program == "SPTH":
        plan = st.selectbox("SPTH Plan", ["Old", "New"], index=0, help="Choose based on the student's degree plan template.")
        program_key = "SPTH_OLD" if plan == "Old" else "SPTH_NEW"
    else:
        program_key = "PBHL"

    st.write("""
Upload **multiple Excel files** (one per student).  
Source of truth per file → Sheet **"Current Semester Advising"**, starting **row 8**.
- **PBHL:** Course Code in **column 0**, Status in **column 7**  
- **SPTH (Old/New):** Course Code in **column 1**, Status in **column 7**
""")

    files_up = st.file_uploader("Upload advising sheets (.xlsx/.xls)", type=["xlsx","xls"], accept_multiple_files=True)

    if st.button("Run Extraction", type="primary"):
        if not files_up:
            st.warning("Please upload one or more Excel files.")
            return

        with st.spinner("Reading and aggregating…"):
            tables = collect_from_filelist(files_up, program_key)
            tables = [(s, df) for (s, df) in tables if isinstance(df, pd.DataFrame)]

            summary_df = make_advising_summary(tables)
            groups_df = make_conflict_free_groups(tables)

        st.markdown("### Task 1 — Advising Summary")
        if summary_df.empty:
            st.info("No courses found in the uploaded files.")
        else:
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            out1 = BytesIO(); summary_df.to_excel(out1, engine="openpyxl", index=False, sheet_name="Advising_Summary")
            st.download_button("📥 Download Advising Summary (Excel)", out1.getvalue(),
                               file_name="advising_summary.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("### Task 2 — Conflict-Free Course Groups")
        if groups_df.empty:
            st.info("No 'Yes' groupings detected.")
        else:
            st.dataframe(groups_df, use_container_width=True, hide_index=True)
            out2 = BytesIO(); groups_df.to_excel(out2, engine="openpyxl", index=False, sheet_name="Course_Groups")
            st.download_button("📥 Download Course Groups (Excel)", out2.getvalue(),
                               file_name="advising_course_groups.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("Notes & Assumptions"):
        st.markdown("""
- If the same course appears multiple times in a student's sheet with different statuses, the strongest is kept:
  **Yes > Optional > Not Advised**.
- Courses are grouped by a normalized key (uppercase, spaces removed) so `ARAB 201` and `ARAB201` are the same.
- Student labels in Task 2 use the **file name**. If you want to pull a real name/ID from a specific cell, tell me which cell.
""")
