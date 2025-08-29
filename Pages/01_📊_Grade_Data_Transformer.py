import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Grade Data Transformer", page_icon="📊", layout="wide")

# -------- Parsing helpers (same behavior as your current app) --------
from typing import Optional, Tuple

def parse_course_semester_grade_from_column(column_name: str) -> Optional[Tuple[str, str, str, str]]:
    pattern = r'^([A-Z]+\d+)-([A-Za-z]+)(\d{4})-([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    match = re.match(pattern, column_name.strip())
    if match:
        return match.groups()

    pattern2 = r'^([A-Z]+\d+)[-_]([A-Za-z]+)[-_](\d{4})[-_]([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    match2 = re.match(pattern2, column_name.strip())
    if match2:
        return match2.groups()
    return None

def parse_course_semester_grade_from_value(value: str) -> Optional[Tuple[str, str, str, str]]:
    if pd.isna(value) or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None

    pattern1 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+-\d{4})/([A-F][+-]?|[A-Z][+-]?|P\*?|R)$'
    match1 = re.match(pattern1, value.upper())
    if match1:
        course, semester_year, grade = match1.groups()
        if '-' in semester_year:
            semester, year = semester_year.split('-', 1)
            return course, semester, year, grade

    pattern2 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+)/(\d{4})/([A-F][+-]?|[A-Z][+-]?|P\*?|R)$'
    match2 = re.match(pattern2, value.upper())
    if match2:
        course, semester, year, grade = match2.groups()
        return course, semester, year, grade

    pattern3 = r'^([A-Z]+\d+[A-Z]*)/([A-Z]+-\d{4})/?$'
    match3 = re.match(pattern3, value.upper())
    if match3:
        course, semester_year = match3.groups()
        if '-' in semester_year:
            semester, year = semester_year.split('-', 1)
            return course, semester, year, "INCOMPLETE"
    return None

def identify_grade_columns(df: pd.DataFrame) -> list:
    grade_columns = []
    for col in df.columns:
        if parse_course_semester_grade_from_column(str(col)) is not None:
            grade_columns.append(col)
    if not grade_columns:
        for col in df.columns:
            if str(col).upper().startswith('COURSE'):
                sample_values = df[col].dropna().head(5)
                for val in sample_values:
                    if parse_course_semester_grade_from_value(str(val)) is not None:
                        grade_columns.append(col)
                        break
    return grade_columns

def transform_grades_to_tidy(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy().dropna(axis=1, how='all')
    grade_columns = identify_grade_columns(df_copy)
    id_columns = [c for c in df_copy.columns if c not in grade_columns]

    if not grade_columns:
        st.warning("No grade columns detected. Check your format.")
        return pd.DataFrame()

    melted = pd.melt(
        df_copy,
        id_vars=id_columns,
        value_vars=grade_columns,
        var_name='Course_Semester_Grade',
        value_name='Grade'
    )
    melted = melted.dropna(subset=['Grade'])
    melted = melted[melted['Grade'].astype(str).str.strip() != '']

    parsed_rows = []
    for _, row in melted.iterrows():
        parsed = parse_course_semester_grade_from_column(str(row['Course_Semester_Grade']))
        if not parsed:
            parsed = parse_course_semester_grade_from_value(str(row['Grade']))
        if parsed:
            course, semester, year, grade = parsed
            new_row = {c: row[c] for c in id_columns}
            new_row['Course'] = course
            new_row['Semester'] = semester.title()
            new_row['Year'] = int(year)
            new_row['Grade'] = grade
            parsed_rows.append(new_row)

    if not parsed_rows:
        return pd.DataFrame()

    tidy = pd.DataFrame(parsed_rows)
    ordered = [*id_columns, 'Course', 'Semester', 'Year', 'Grade']
    tidy = tidy[ordered]
    return tidy

# -------- UI --------
st.title("📊 Grade Data Transformer")
st.markdown("Transform wide-format grade sheets into tidy data for analysis.")

uploaded_file = st.file_uploader("Upload an Excel file (.xlsx/.xls)", type=["xlsx", "xls"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"Loaded: {df.shape[0]} rows × {df.shape[1]}
