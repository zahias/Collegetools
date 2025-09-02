import streamlit as st
import pandas as pd
import re
from io import BytesIO
from typing import Optional, Tuple, List

# ======================= Parsing helpers (existing behavior) =======================
def parse_course_semester_grade_from_column(column_name: str) -> Optional[Tuple[str, str, str, str]]:
    pattern = r'^([A-Z]+\d+)-([A-Za-z]+)(\d{4})-([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    m = re.match(pattern, column_name.strip())
    if m:
        return m.groups()
    pattern2 = r'^([A-Z]+\d+)[-_]([A-Za-z]+)[-_](\d{4})[-_]([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    m2 = re.match(pattern2, column_name.strip())
    return m2.groups() if m2 else None

def parse_course_semester_grade_from_value(value: str) -> Optional[Tuple[str, str, str, str]]:
    if pd.isna(value) or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    p1 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+-\d{4})/([A-F][+-]?|[A-Z][+-]?|P\*?|R)$'
    m1 = re.match(p1, v.upper())
    if m1:
        course, sem_year, grade = m1.groups()
        if '-' in sem_year:
            semester, year = sem_year.split('-', 1)
            return course, semester, year, grade
    p2 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+)/(\d{4})/([A-F][+-]?|[A-Z][+-]?|P\*?|R)$'
    m2 = re.match(p2, v.upper())
    if m2:
        return m2.groups()
    p3 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+-\d{4})/?$'
    m3 = re.match(p3, v.upper())
    if m3:
        course, sem_year = m3.groups()
        if '-' in sem_year:
            semester, year = sem_year.split('-', 1)
            return course, semester, year, "INCOMPLETE"
    return None

def identify_grade_columns(df: pd.DataFrame) -> list:
    grade_cols = [c for c in df.columns if parse_course_semester_grade_from_column(str(c))]
    if grade_cols:
        return grade_cols
    for c in df.columns:
        if str(c).upper().startswith('COURSE'):
            sample = df[c].dropna().head(5)
            if any(parse_course_semester_grade_from_value(str(v)) for v in sample):
                grade_cols.append(c)
    return grade_cols

def transform_grades_to_tidy(df: pd.DataFrame) -> pd.DataFrame:
    dfc = df.copy().dropna(axis=1, how='all')
    grade_cols = identify_grade_columns(dfc)
    id_cols = [c for c in dfc.columns if c not in grade_cols]
    if not grade_cols:
        st.warning("No grade columns detected. Check your format.")
        return pd.DataFrame()

    melted = pd.melt(
        dfc, id_vars=id_cols, value_vars=grade_cols,
        var_name='Course_Semester_Grade', value_name='Grade'
    )
    melted = melted.dropna(subset=['Grade'])
    melted = melted[melted['Grade'].astype(str).str.strip() != '']

    parsed_rows = []
    for _, row in melted.iterrows():
        parsed = parse_course_semester_grade_from_column(str(row['Course_Semester_Grade'])) \
                 or parse_course_semester_grade_from_value(str(row['Grade']))
        if parsed:
            course, semester, year, grade = parsed
            new_row = {c: row[c] for c in id_cols}
            new_row.update({
                'Course': course,
                'Semester': semester.title(),
                'Year': int(year),
                'Grade': grade
            })
            parsed_rows.append(new_row)

    if not parsed_rows:
        return pd.DataFrame()

    tidy = pd.DataFrame(parsed_rows)
    return tidy[[*id_cols, 'Course', 'Semester', 'Year', 'Grade']]

# ======================= Split helpers (used by both modes) =======================
def _norm_col_name(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.strip().lower())

def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    norm_map = {col: _norm_col_name(str(col)) for col in df.columns}
    cand_norm = set(candidates)
    for col, n in norm_map.items():
        if n in cand_norm:
            return col
    return None

def _year_from_id(val) -> Optional[int]:
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    m = re.match(r'^(\d{4})', s) or re.search(r'(\d{4})', s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def _is_pbhl(major_val: str) -> bool:
    if not isinstance(major_val, str):
        return False
    m = major_val.strip().upper()
    # PBHL family, PUBHEA, or text "PUBLIC HEALTH"
    return m.startswith("PBHL") or m == "PUBHEA" or ("PUBLIC" in m and "HEALTH" in m)

def _is_spth(major_val: str) -> bool:
    if not isinstance(major_val, str):
        return False
    m = major_val.strip().upper().replace(" ", "")
    # Includes your data's label "SPETHE" and common variants
    tokens = ["SPTH", "SPETHE", "SPET", "SPEECH", "SPEECHTHERAPY", "SPEECHPATHOLOGY", "SLP"]
    return any(tok in m for tok in tokens)

def _split_three(df_like: pd.DataFrame):
    """
    Split any dataframe (tidy or original) into PBHL / SPTH Old / SPTH New.
    Returns (pbhl_df, spth_old_df, spth_new_df, id_col, major_col).
    """
    if df_like.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None, None

    id_candidates = {"id", "studentid", "sid", "student_id", "studentnumber", "studentno"}
    major_candidates = {"major", "program", "degree", "maj", "track"}

    id_col = _find_col(df_like, list(id_candidates))
    major_col = _find_col(df_like, list(major_candidates))

    if id_col is None or major_col is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), id_col, major_col

    df = df_like.copy()
    df["_MAJOR_OK_PBHL"] = df[major_col].apply(_is_pbhl)
    df["_MAJOR_OK_SPTH"] = df[major_col].apply(_is_spth)
    df["_ID_YEAR"] = df[id_col].apply(_year_from_id)

    pbhl_df = df[df["_MAJOR_OK_PBHL"]].drop(columns=["_MAJOR_OK_PBHL","_MAJOR_OK_SPTH","_ID_YEAR"])
    spth_old_df = df[(df["_MAJOR_OK_SPTH"]) & (df["_ID_YEAR"].notna()) & (df["_ID_YEAR"] <= 2021)] \
                    .drop(columns=["_MAJOR_OK_PBHL","_MAJOR_OK_SPTH","_ID_YEAR"])
    spth_new_df = df[(df["_MAJOR_OK_SPTH"]) & (df["_ID_YEAR"].notna()) & (df["_ID_YEAR"] >= 2022)] \
                    .drop(columns=["_MAJOR_OK_PBHL","_MAJOR_OK_SPTH","_ID_YEAR"])

    return pbhl_df, spth_old_df, spth_new_df, id_col, major_col

# ======================= UI =======================
def run():
    st.subheader("📊 Grade Data Transformer")

    mode = st.radio(
        "Choose output mode",
        ["Transform to tidy then split", "Split original (no transformation)"],
        index=0,
        help="If you pick 'Split original', the app will filter the uploaded sheet as-is into PBHL / SPTH Old / SPTH New, without melting."
    )

    up = st.file_uploader("Upload an Excel file (.xlsx/.xls)", type=["xlsx","xls"])
    if not up:
        return

    try:
        raw_df = pd.read_excel(up)
    except Exception as e:
        st.error(f"Could not read Excel file: {e}")
        return

    st.success(f"Loaded: {raw_df.shape[0]} rows × {raw_df.shape[1]} cols")
    st.markdown("**Original Preview**")
    st.dataframe(raw_df.head(10), use_container_width=True)

    # ---------------- Mode A: Transform to tidy, then split (existing) ----------------
    if mode == "Transform to tidy then split":
        st.markdown("**Transform**")
        with st.spinner("Transforming…"):
            tidy_df = transform_grades_to_tidy(raw_df)

        if tidy_df.empty:
            st.error("No valid rows parsed. Check formatting.")
            return

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Original Rows", raw_df.shape[0])
        with c2: st.metric("Transformed Rows", tidy_df.shape[0])
        # Unique students = try to use detected ID column; else first column
        id_like_cols = [c for c in tidy_df.columns if _norm_col_name(str(c)) in {"id","studentid","sid","student_id","studentnumber","studentno"}]
        with c3: st.metric("Unique Students", tidy_df[id_like_cols[0]].nunique() if id_like_cols else tidy_df.iloc[:,0].nunique())

        st.markdown("**Tidy Preview**")
        st.dataframe(tidy_df.head(20), use_container_width=True)

        # full cleaned
        full_out = BytesIO()
        tidy_df.to_excel(full_out, engine="openpyxl", sheet_name="Cleaned_Data", index=False)
        st.download_button("📥 Download Cleaned Excel (All Records)",
                           full_out.getvalue(),
                           file_name="cleaned_student_data.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # split into 3
        pbhl_df, spth_old_df, spth_new_df, id_col, major_col = _split_three(tidy_df)
        if id_col is None or major_col is None:
            st.warning("Could not detect ID and/or MAJOR columns — skipping PBHL/SPTH split downloads. "
                       "Please ensure columns like 'ID' and 'MAJOR' exist (case-insensitive).")
            return

        st.markdown("---")
        st.markdown("### 🎯 Program-Specific Downloads (from tidy data)")

        colA, colB, colC = st.columns(3)
        with colA:
            st.caption("PBHL only")
            if pbhl_df.empty:
                st.info("No PBHL records found.")
            else:
                out = BytesIO(); pbhl_df.to_excel(out, engine="openpyxl", index=False, sheet_name="PBHL")
                st.download_button("📥 Download PBHL Excel", out.getvalue(),
                                   file_name="cleaned_PBHL.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with colB:
            st.caption("SPTH (Old) — IDs starting 2021 and below")
            if spth_old_df.empty:
                st.info("No SPTH (Old) records found.")
            else:
                out = BytesIO(); spth_old_df.to_excel(out, engine="openpyxl", index=False, sheet_name="SPTH_Old")
                st.download_button("📥 Download SPTH Old Excel", out.getvalue(),
                                   file_name="cleaned_SPTH_old.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with colC:
            st.caption("SPTH (New) — IDs starting 2022 and above")
            if spth_new_df.empty:
                st.info("No SPTH (New) records found.")
            else:
                out = BytesIO(); spth_new_df.to_excel(out, engine="openpyxl", index=False, sheet_name="SPTH_New")
                st.download_button("📥 Download SPTH New Excel", out.getvalue(),
                                   file_name="cleaned_SPTH_new.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ---------------- Mode B: Split original (no transformation) ----------------
    else:
        st.markdown("**Split original (no transformation)**")
        with st.spinner("Filtering…"):
            pbhl_raw, spth_old_raw, spth_new_raw, id_col, major_col = _split_three(raw_df)

        if id_col is None or major_col is None:
            st.warning("Could not detect ID and/or MAJOR columns. "
                       "Please ensure your original sheet has columns like 'ID' and 'MAJOR' (case-insensitive).")
            return

        # quick stats
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Rows (original)", raw_df.shape[0])
        with c2: st.metric("PBHL rows", len(pbhl_raw))
        with c3: st.metric("SPTH Old rows", len(spth_old_raw))
        with c4: st.metric("SPTH New rows", len(spth_new_raw))

        st.markdown("---")
        st.markdown("### 🎯 Program-Specific Downloads (original data, untransformed)")

        colA, colB, colC = st.columns(3)
        with colA:
            st.caption("PBHL only (original columns)")
            if pbhl_raw.empty:
                st.info("No PBHL records found.")
            else:
                out = BytesIO(); pbhl_raw.to_excel(out, engine="openpyxl", index=False, sheet_name="PBHL_raw")
                st.download_button("📥 Download PBHL (original)", out.getvalue(),
                                   file_name="original_PBHL.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with colB:
            st.caption("SPTH (Old) — IDs ≤ 2021 (original columns)")
            if spth_old_raw.empty:
                st.info("No SPTH (Old) records found.")
            else:
                out = BytesIO(); spth_old_raw.to_excel(out, engine="openpyxl", index=False, sheet_name="SPTH_Old_raw")
                st.download_button("📥 Download SPTH Old (original)", out.getvalue(),
                                   file_name="original_SPTH_old.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with colC:
            st.caption("SPTH (New) — IDs ≥ 2022 (original columns)")
            if spth_new_raw.empty:
                st.info("No SPTH (New) records found.")
            else:
                out = BytesIO(); spth_new_raw.to_excel(out, engine="openpyxl", index=False, sheet_name="SPTH_New_raw")
                st.download_button("📥 Download SPTH New (original)", out.getvalue(),
                                   file_name="original_SPTH_new.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("Format details"):
        st.write("- **Transform mode:** Accepts either column-name pattern `Course-SemesterYear-Grade` "
                 "or value pattern like `COURSE/SEM-YEAR/GRADE` inside `COURSE*` columns.")
        st.write("- **Split rules:**")
        st.write("  - **PBHL**: MAJOR starts with `PBHL`, equals `PUBHEA`, or contains `PUBLIC` + `HEALTH`.")
        st.write("  - **SPTH**: MAJOR contains one of `SPTH`, `SPETHE`, `SPET`, `SPEECH*`, `SLP`.")
        st.write("  - **Old vs New**: determined by the first 4 digits in the **ID** value; "
                 "`≤ 2021` → Old, `≥ 2022` → New.")
