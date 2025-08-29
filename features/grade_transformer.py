import streamlit as st
import pandas as pd
import re
from io import BytesIO
from typing import Optional, Tuple

def parse_course_semester_grade_from_column(column_name: str) -> Optional[Tuple[str, str, str, str]]:
    pattern = r'^([A-Z]+\d+)-([A-Za-z]+)(\d{4})-([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    m = re.match(pattern, column_name.strip())
    if m: return m.groups()
    pattern2 = r'^([A-Z]+\d+)[-_]([A-Za-z]+)[-_](\d{4})[-_]([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    m2 = re.match(pattern2, column_name.strip())
    return m2.groups() if m2 else None

def parse_course_semester_grade_from_value(value: str) -> Optional[Tuple[str, str, str, str]]:
    if pd.isna(value) or not isinstance(value, str): return None
    v = value.strip()
    if not v: return None
    p1 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+-\d{4})/([A-F][+-]?|[A-Z][+-]?|P\*?|R)$'
    m1 = re.match(p1, v.upper())
    if m1:
        course, sem_year, grade = m1.groups()
        if '-' in sem_year:
            semester, year = sem_year.split('-', 1)
            return course, semester, year, grade
    p2 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+)/(\d{4})/([A-F][+-]?|[A-Z][+-]?|P\*?|R)$'
    m2 = re.match(p2, v.upper())
    if m2: return m2.groups()
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
    if grade_cols: return grade_cols
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
    melted = pd.melt(dfc, id_vars=id_cols, value_vars=grade_cols,
                     var_name='Course_Semester_Grade', value_name='Grade')
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

def run():
    st.subheader("📊 Grade Data Transformer")
    st.write("Transform wide-format grade sheets into tidy data for analysis.")
    up = st.file_uploader("Upload an Excel file (.xlsx/.xls)", type=["xlsx","xls"])
    if up:
        try:
            df = pd.read_excel(up)
            st.success(f"Loaded: {df.shape[0]} rows × {df.shape[1]} cols")
            st.markdown("**Original Preview**")
            st.dataframe(df.head(10), use_container_width=True)
            st.markdown("**Transform**")
            with st.spinner("Transforming…"):
                tidy_df = transform_grades_to_tidy(df)
            if tidy_df.empty:
                st.error("No valid rows parsed. Check formatting.")
            else:
                c1,c2,c3 = st.columns(3)
                with c1: st.metric("Original Rows", df.shape[0])
                with c2: st.metric("Transformed Rows", tidy_df.shape[0])
                with c3: st.metric("Unique Students", tidy_df.iloc[:,0].nunique())
                st.markdown("**Tidy Preview**")
                st.dataframe(tidy_df.head(20), use_container_width=True)
                out = BytesIO(); tidy_df.to_excel(out, engine="openpyxl", sheet_name="Cleaned_Data", index=False)
                st.download_button("📥 Download Cleaned Excel", out.getvalue(),
                                   file_name="cleaned_student_data.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"Error: {e}")
    with st.expander("Format details"):
        st.write("- **Format 1 (column names):** `Course-SemesterYear-Grade` e.g., `MATH101-Fall2024-A`")
        st.write("- **Format 2 (cell values):** `COURSE/SEM-YEAR/GRADE` e.g., `SPTH201/FALL-2016/F`")
