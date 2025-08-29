import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile, os, tempfile
from typing import List, Tuple

SHEET_NAME = "Current Semester Advising"
START_ROW_IDX = 7   # Excel row 8 (0-based index)
COURSE_COL = 0
STATUS_COL = 7

def read_advising_table_from_file(path: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(path, sheet_name=SHEET_NAME, header=None)
    except Exception:
        return pd.DataFrame(columns=["Course", "Status"])
    if df.shape[1] <= max(COURSE_COL, STATUS_COL):
        return pd.DataFrame(columns=["Course", "Status"])
    sub = df.iloc[START_ROW_IDX:, [COURSE_COL, STATUS_COL]].copy()
    sub.columns = ["Course", "Status"]
    sub["Course"] = sub["Course"].astype(str).str.strip()
    sub = sub[sub["Course"].notna() & (sub["Course"] != "")]
    sub["Status"] = sub["Status"].astype(str)
    sub.loc[sub["Status"].str.strip().eq("") | sub["Status"].str.lower().isin(["nan", "none"]), "Status"] = ""
    return sub

def collect_from_zip(uploaded_zip) -> List[Tuple[str, pd.DataFrame]]:
    out = []
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(uploaded_zip, "r") as zf: zf.extractall(td)
        for root,_,files in os.walk(td):
            for f in files:
                if f.endswith((".xlsx",".xls")):
                    p = os.path.join(root,f)
                    df = read_advising_table_from_file(p)
                    label = os.path.splitext(os.path.basename(f))[0]
                    out.append((label, df))
    return out

def collect_from_filelist(files) -> List[Tuple[str, pd.DataFrame]]:
    out = []
    for f in files:
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(f.read()); tmp.flush()
                df = read_advising_table_from_file(tmp.name)
            label = os.path.splitext(f.name)[0]
            out.append((label, df))
        except Exception:
            out.append((f.name, pd.DataFrame(columns=["Course","Status"])))
    return out

def make_advising_summary(student_tables: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    rows = []
    for _, df in student_tables:
        if df.empty: continue
        d = df.copy()
        d["Course"] = d["Course"].str.upper().str.strip()
        d["StatusNorm"] = d["Status"].str.strip().str.title()
        d["StatusNorm"] = d["StatusNorm"].where(d["StatusNorm"].isin(["Yes","Optional"]), "")
        rank = {"Yes":2, "Optional":1, "":0}
        d = (d.assign(_r=d["StatusNorm"].map(rank))
               .sort_values(["Course","_r"], ascending=[True, False])
               .drop_duplicates(subset=["Course"], keep="first")
               .drop(columns="_r"))
        rows.append(d[["Course","StatusNorm"]])

    if not rows:
        return pd.DataFrame(columns=["Course Code","Yes Count","Optional Count","Not Advised Count"])

    all_df = pd.concat(rows, ignore_index=True)
    yes = (all_df["StatusNorm"]=="Yes").groupby(all_df["Course"]).sum()
    opt = (all_df["StatusNorm"]=="Optional").groupby(all_df["Course"]).sum()
    total = all_df.groupby("Course").size()
    not_adv = total - yes - opt

    out = pd.DataFrame({
        "Course Code": total.index,
        "Yes Count": yes.values.astype(int),
        "Optional Count": opt.values.astype(int),
        "Not Advised Count": not_adv.values.astype(int),
    }).sort_values("Course Code").reset_index(drop=True)
    return out

def make_conflict_free_groups(student_tables: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    from collections import defaultdict
    groups = defaultdict(list)
    for student, df in student_tables:
        if df.empty: continue
        d = df.copy()
        d["Course"] = d["Course"].astype(str).str.upper().str.strip()
        yes_courses = sorted(d.loc[d["Status"].astype(str).str.strip().str.lower()=="yes","Course"].unique())
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
        for c in cols: r.setdefault(c, "")
    return pd.DataFrame(rows, columns=cols).sort_values("Students").reset_index(drop=True)

def run():
    st.subheader("🧭 Advising Data Extractor")
    st.write("""
Upload either **a .zip** (many Excel files, one per student) **or** upload multiple Excel files directly.

**Source of truth per file** — Sheet **"Current Semester Advising"**, starting **row 8**  
- **Column 0** = Course Code  
- **Column 7** = Advising Status (`"Yes"`, `"Optional"`, or empty for *Not Advised*)  
""")
    c1, c2 = st.columns(2)
    zip_up = c1.file_uploader("Upload a .zip of advising sheets", type=["zip"])
    files_up = c2.file_uploader("Or upload multiple Excel files", type=["xlsx","xls"], accept_multiple_files=True)

    if st.button("Run Extraction", type="primary"):
        with st.spinner("Reading and aggregating…"):
            tables = []
            if zip_up: tables.extend(collect_from_zip(zip_up))
            if files_up: tables.extend(collect_from_filelist(files_up))
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
- If a student sheet repeats a course with different statuses, the strongest is kept for counting:
  **Yes > Optional > Not Advised**.
- Student label for groups uses the **file name** (without extension). If you want a real name/ID from a cell, tell me the address.
- Summary counts per course = number of *students who had that course row* and how many were **Yes**, **Optional**, or **Not Advised**.
""")
