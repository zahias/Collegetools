import streamlit as st
import pandas as pd
import re
from io import BytesIO
from typing import Optional, Tuple, List

# ======================= Parsing helpers (transform mode) =======================
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

def _find_col_exact(df: pd.DataFrame, candidates_norm: List[str]) -> Optional[str]:
    norm_map = {col: _norm_col_name(str(col)) for col in df.columns}
    for col, n in norm_map.items():
        if n in candidates_norm:
            return col
    return None

def _find_cols_fuzzy(df: pd.DataFrame, roots: List[str]) -> List[str]:
    norm_map = {col: _norm_col_name(str(col)) for col in df.columns}
    cols = []
    for col, n in norm_map.items():
        if any(root in n for root in roots):
            cols.append(col)
    return cols

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

# ---- Program detectors (hardened) ----
def _strip_np(txt: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', txt.upper())

def _is_pbhl(v: str) -> bool:
    if not isinstance(v, str):
        return False
    up = v.upper()
    up_np = _strip_np(v)
    # Matches PBHL, any PUBHEA*, PUBLIC HEALTH (with spaces/punct), and common variants
    return (
        "PBHL" in up_np or
        "PUBHEA" in up_np or
        "PUBLICHEALTH" in up_np or
        ("PUBLIC" in up and "HEALTH" in up)
    )

def _is_spth(v: str) -> bool:
    if not isinstance(v, str):
        return False
    up_np = _strip_np(v)
    tokens = ["SPTH", "SPETHE", "SPET", "SPEECH", "SPEECHTHERAPY", "SPEECHPATHOLOGY", "SLP"]
    return any(tok in up_np for tok in tokens)

def _is_nurs(v: str) -> bool:
    if not isinstance(v, str):
        return False
    up_np = _strip_np(v)
    return ("NURS" in up_np) or ("NURSING" in up_np)

def _is_majorless(v: str) -> bool:
    if not isinstance(v, str):
        return False
    up_np = _strip_np(v)
    # Main code requested: MAJRLS. Add a few safe synonyms.
    return ("MAJRLS" in up_np) or ("MAJORLESS" in up_np) or ("UNDECLARED" in up_np)

def _aggregate_program_string(row: pd.Series, program_cols: List[str]) -> str:
    parts = []
    for c in program_cols:
        val = row.get(c, None)
        if pd.isna(val):
            continue
        s = str(val).strip()
        if s and s.lower() != "nan":
            parts.append(s)
    return " | ".join(parts)

def _detect_id_column(df: pd.DataFrame) -> Optional[str]:
    id_candidates_exact = {"id", "studentid", "sid", "student_id", "studentnumber", "studentno"}
    col = _find_col_exact(df, list(id_candidates_exact))
    if col:
        return col
    # Fallback: fuzzy
    norm_map = {col: _norm_col_name(str(col)) for col in df.columns}
    for col, n in norm_map.items():
        if ("studentid" in n) or ("studentnumber" in n) or n == "id":
            return col
    return None

def _find_program_columns(df: pd.DataFrame) -> List[str]:
    # exact matches
    program_candidates_exact = {"major", "program", "degree", "maj", "track", "curriculum", "department"}
    cols = []
    exact = _find_col_exact(df, list(program_candidates_exact))
    if exact:
        cols.append(exact)
    # fuzzy matches (handles 'Curriculum Name', 'Major Plan', etc.)
    fuzzy_roots = ["major", "maj", "program", "prog", "degree", "track", "curriculum", "curr", "department", "dept"]
    more = _find_cols_fuzzy(df, fuzzy_roots)
    for c in more:
        if c not in cols:
            cols.append(c)
    return cols

def _split_programs(df_like: pd.DataFrame):
    """
    Split any dataframe (tidy or original) into:
      PBHL, SPTH Old (<=2021), SPTH New (>=2022), NURS, MAJRLS
    Returns: (pbhl_df, spth_old_df, spth_new_df, nurs_df, majorless_df, id_col, program_cols_list)
    """
    if df_like.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None, []

    id_col = _detect_id_column(df_like)
    program_cols = _find_program_columns(df_like)

    if not program_cols:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), id_col, []

    df = df_like.copy()
    df["__PROGRAM_AGG__"] = df.apply(lambda r: _aggregate_program_string(r, program_cols), axis=1)

    df["__PBHL__"] = df["__PROGRAM_AGG__"].apply(_is_pbhl)
    df["__SPTH__"] = df["__PROGRAM_AGG__"].apply(_is_spth)
    df["__NURS__"] = df["__PROGRAM_AGG__"].apply(_is_nurs)
    df["__MAJRLS__"] = df["__PROGRAM_AGG__"].apply(_is_majorless)

    base_drop = ["__PROGRAM_AGG__","__PBHL__","__SPTH__","__NURS__","__MAJRLS__"]

    pbhl_df = df[df["__PBHL__"]].drop(columns=base_drop, errors="ignore")
    nurs_df = df[df["__NURS__"]].drop(columns=base_drop, errors="ignore")
    majorless_df = df[df["__MAJRLS__"]].drop(columns=base_drop, errors="ignore")

    spth_old_df = pd.DataFrame()
    spth_new_df = pd.DataFrame()

    if id_col is not None:
        df["__ID_YEAR__"] = df[id_col].apply(_year_from_id)
        spth_old_df = df[(df["__SPTH__"]) & (df["__ID_YEAR__"].notna()) & (df["__ID_YEAR__"] <= 2021)] \
                        .drop(columns=base_drop + ["__ID_YEAR__"], errors="ignore")
        spth_new_df = df[(df["__SPTH__"]) & (df["__ID_YEAR__"].notna()) & (df["__ID_YEAR__"] >= 2022)] \
                        .drop(columns=base_drop + ["__ID_YEAR__"], errors="ignore")

    return pbhl_df, spth_old_df, spth_new_df, nurs_df, majorless_df, id_col, program_cols

# ======================= UI =======================
def run():
    st.subheader("📊 Grade Data Transformer")

    mode = st.radio(
        "Choose output mode",
        ["Transform to tidy then split", "Split original (no transformation)"],
        index=0,
        key="gt_mode",
        help="Pick 'Split original' to keep all original columns and only filter by program/ID."
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
        id_like = [c for c in tidy_df.columns if _norm_col_name(str(c)) in {"id","studentid","sid","student_id","studentnumber","studentno"}]
        with c3: st.metric("Unique Students", tidy_df[id_like[0]].nunique() if id_like else tidy_df.iloc[:,0].nunique())

        st.markdown("**Tidy Preview**")
        st.dataframe(tidy_df.head(20), use_container_width=True)

        # full cleaned
        full_out = BytesIO()
        tidy_df.to_excel(full_out, engine="openpyxl", sheet_name="Cleaned_Data", index=False)
        st.download_button("📥 Download Cleaned Excel (All Records)",
                           full_out.getvalue(),
                           file_name="cleaned_student_data.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        pbhl_df, spth_old_df, spth_new_df, nurs_df, majorless_df, id_col, program_cols = _split_programs(tidy_df)
    else:
        st.markdown("**Split original (no transformation)**")
        with st.spinner("Filtering…"):
            pbhl_df, spth_old_df, spth_new_df, nurs_df, majorless_df, id_col, program_cols = _split_programs(raw_df)

    # Diagnostics to confirm detection
    with st.expander("Detection diagnostics"):
        st.write("**Program columns used:**", program_cols if program_cols else "None")
        st.write("**ID column used:**", id_col if id_col else "None")
        if program_cols:
            norm = raw_df[program_cols].astype(str).apply(lambda s: s.str.upper().str.strip())
            sample = pd.Series(norm.apply(lambda r: " | ".join([x for x in r if x and x.lower() != 'nan']), axis=1)).value_counts().head(25)
            st.write("**Top program-like values (first 25):**")
            st.write(sample)

    if not program_cols:
        st.warning("Couldn't find a program column. Expected one of: MAJOR / CURRICULUM / PROGRAM / DEGREE / TRACK / DEPARTMENT (fuzzy variants like 'Curriculum Name' also work).")
        return

    if id_col is None:
        st.info("ID column not detected — PBHL / NURS / MAJRLS will work; SPTH Old/New need ID to infer year (≤2021 vs ≥2022).")

    st.markdown("---")
    st.markdown("### 🎯 Program-Specific Downloads")

    colA, colB, colC, colD, colE = st.columns(5)

    with colA:
        st.caption("PBHL")
        if pbhl_df.empty:
            st.info("No PBHL records found.")
        else:
            out = BytesIO(); pbhl_df.to_excel(out, engine="openpyxl", index=False, sheet_name="PBHL")
            st.download_button("📥 PBHL Excel", out.getvalue(),
                               file_name="PBHL.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with colB:
        st.caption("SPTH (Old) — IDs ≤ 2021")
        if spth_old_df.empty:
            st.info("No SPTH (Old) records found.")
        else:
            out = BytesIO(); spth_old_df.to_excel(out, engine="openpyxl", index=False, sheet_name="SPTH_Old")
            st.download_button("📥 SPTH Old Excel", out.getvalue(),
                               file_name="SPTH_old.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with colC:
        st.caption("SPTH (New) — IDs ≥ 2022")
        if spth_new_df.empty:
            st.info("No SPTH (New) records found.")
        else:
            out = BytesIO(); spth_new_df.to_excel(out, engine="openpyxl", index=False, sheet_name="SPTH_New")
            st.download_button("📥 SPTH New Excel", out.getvalue(),
                               file_name="SPTH_new.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with colD:
        st.caption("NURS (Nursing)")
        if nurs_df.empty:
            st.info("No NURS records found.")
        else:
            out = BytesIO(); nurs_df.to_excel(out, engine="openpyxl", index=False, sheet_name="NURS")
            st.download_button("📥 NURS Excel", out.getvalue(),
                               file_name="NURS.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with colE:
        st.caption("MAJRLS (Majorless)")
        if majorless_df.empty:
            st.info("No MAJRLS records found.")
        else:
            out = BytesIO(); majorless_df.to_excel(out, engine="openpyxl", index=False, sheet_name="MAJRLS")
            st.download_button("📥 MAJRLS Excel", out.getvalue(),
                               file_name="MAJRLS.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("Detection rules"):
        st.write("- **Program columns**: any of `MAJOR`, `CURRICULUM`, `PROGRAM`, `DEGREE`, `TRACK`, `DEPARTMENT` (fuzzy variants like 'Curriculum Name' also work).")
        st.write("- **PBHL**: matches `PBHL`, any `PUBHEA*`, or `PUBLIC HEALTH` (spacing/punct ignored).")
        st.write("- **SPTH**: matches `SPTH`, `SPETHE`, `SPET`, `SPEECH*`, `SLP` (spacing/punct ignored).")
        st.write("- **NURS**: matches `NURS` or `NURSING` (spacing/punct ignored).")
        st.write("- **MAJRLS**: matches `MAJRLS`, `MAJORLESS`, or `UNDECLARED`.")
        st.write("- **SPTH Old/New**: by the first 4 digits found in **ID** (`≤ 2021` → Old, `≥ 2022` → New).")
