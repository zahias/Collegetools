# internship_consolidator.py
# VERSION: 2025-11-13T11:00Z — filename-as-student, no ID reads, wider header matching, verbose logs

import os
import re
import zipfile
import tempfile
import pathlib
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Iterable

import pandas as pd
import streamlit as st

# -------------------------------
# Constants / UI
# -------------------------------
VERSION = "Internship Data Consolidator — 2025-11-13 11:00Z"

JUNK_PREFIXES = ("._",)       # macOS resource-fork files
JUNK_DIRS = ("__MACOSX",)     # macOS zip dir

# Header detection terms (lowercased)
CODE_TERMS = ["internship code", "code"]   # we’ll require something with both 'internship' and 'code' OR exactly 'code' next to “internship”
COMPLETED_TERMS = ["completed", "completed hours", "hours completed", "# completed", "hrs completed", "completed (hrs)"]

# -------------------------------
# Utility helpers
# -------------------------------
def _is_excel_path(p: str) -> bool:
    pl = p.lower()
    if any(dir_ in pl for dir_ in JUNK_DIRS):  # ignore junk dirs
        return False
    base = os.path.basename(p)
    if base.startswith(JUNK_PREFIXES):         # ignore junk files
        return False
    return pl.endswith(".xlsx") or pl.endswith(".xls")

def _save_uploaded_file(tmpdir: str, up_file) -> str:
    fname = os.path.basename(up_file.name)
    path = os.path.join(tmpdir, fname)
    with open(path, "wb") as fp:
        fp.write(up_file.getbuffer())
    return path

def _extract_excel_paths_from_zip(zip_path: str, into_dir: str, verbose: bool=False, logs: List[str]=None) -> List[str]:
    excel_paths: List[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(into_dir)
        for root, _, files in os.walk(into_dir):
            if any(j in root for j in JUNK_DIRS):
                continue
            for f in files:
                full = os.path.join(root, f)
                if _is_excel_path(full):
                    excel_paths.append(full)
                else:
                    if verbose and logs is not None:
                        logs.append(f"Skipped (not Excel): {full}")
    except Exception as e:
        if verbose and logs is not None:
            logs.append(f"Zip extract error for {zip_path}: {e}")
    return excel_paths

def _collect_all_excel_paths(uploaded_files: Iterable, verbose: bool=False, logs: List[str]=None) -> List[Tuple[str, str]]:
    """
    Accepts a mix of .zip, .xlsx, .xls from Streamlit.
    Returns list of (display_name_without_ext, absolute_excel_path).
    The display name is used as the Student value.
    """
    td = tempfile.TemporaryDirectory()
    base = td.name
    results: List[Tuple[str, str]] = []

    # Save everything first
    saved_paths: List[str] = []
    for up in uploaded_files:
        try:
            saved_paths.append(_save_uploaded_file(base, up))
        except Exception as e:
            if verbose and logs is not None:
                logs.append(f"Save error for {getattr(up, 'name', 'uploaded_file')}: {e}")

    # Walk saved files
    for p in saved_paths:
        pl = p.lower()
        if pl.endswith(".zip"):
            zdir = os.path.join(base, f"unzipped_{os.path.splitext(os.path.basename(p))[0]}")
            os.makedirs(zdir, exist_ok=True)
            for ep in _extract_excel_paths_from_zip(p, zdir, verbose=verbose, logs=logs):
                if _is_excel_path(ep):
                    display = pathlib.Path(ep).stem
                    results.append((display, ep))
        elif _is_excel_path(p):
            display = pathlib.Path(p).stem
            results.append((display, p))
        else:
            if verbose and logs is not None:
                logs.append(f"Ignored (not zip/xlsx/xls): {p}")

    # deduplicate
    seen = set()
    dedup: List[Tuple[str, str]] = []
    for name, path in results:
        if path not in seen:
            seen.add(path)
            dedup.append((name, path))
    return dedup

# -------------------------------
# Table extraction
# -------------------------------
def _norm(x) -> str:
    return re.sub(r"\s+", " ", str(x).strip().lower())

def _find_header_positions(df: pd.DataFrame) -> Optional[Tuple[int, int, int]]:
    """
    Find a header row that has:
      - a column that contains 'internship' and 'code' (or the exact text 'internship code')
      - a column that contains any of COMPLETED_TERMS
    Return (header_row_idx, code_col_idx, completed_col_idx)
    """
    nrows, ncols = df.shape
    for i in range(nrows):
        row = df.iloc[i]
        norm_cells = [_norm(x) for x in row.tolist()]
        code_idx = None
        comp_idx = None

        # locate "internship code"
        for idx, val in enumerate(norm_cells):
            if ("internship" in val and "code" in val) or val in CODE_TERMS:
                code_idx = idx
                break

        # locate "completed" variants
        if code_idx is not None:
            for idx, val in enumerate(norm_cells):
                if any(term in val for term in COMPLETED_TERMS):
                    comp_idx = idx
                    break

        if code_idx is not None and comp_idx is not None:
            return i, code_idx, comp_idx

    return None

def extract_internship_data_from_path(path: str, verbose: bool=False, logs: List[str]=None) -> Optional[Dict[str, int]]:
    """
    Reads all sheets, finds header row+columns, then collects rows until table ends.
    Returns {code: completed_int}.
    """
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        if verbose and logs is not None:
            logs.append(f"Cannot open Excel: {path} — {e}")
        return None

    for sh in xls.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sh, header=None)
        except Exception as e:
            if verbose and logs is not None:
                logs.append(f"Cannot read sheet '{sh}' in {path}: {e}")
            continue

        if df.empty:
            continue

        found = _find_header_positions(df)
        if not found:
            continue

        header_row, code_col, comp_col = found
        if verbose and logs is not None:
            logs.append(f"{os.path.basename(path)}[{sh}]: header at row {header_row}, code_col={code_col}, completed_col={comp_col}")

        out: Dict[str, int] = {}
        for r in range(header_row + 1, len(df)):
            row = df.iloc[r]
            if code_col >= len(row) or comp_col >= len(row):
                break

            code_val = row.iloc[code_col]
            comp_val = row.iloc[comp_col]

            # End of table if code empty
            if pd.isna(code_val) or str(code_val).strip() == "":
                break

            code = str(code_val).strip()
            if not code:
                break

            # Completed may be blank -> treat as 0 and continue
            completed = 0
            if pd.notna(comp_val) and str(comp_val).strip() != "":
                try:
                    completed = int(float(str(comp_val).strip()))
                except Exception:
                    # not numeric → assume table ended
                    break

            out[code] = completed

        if out:
            return out

    if verbose and logs is not None:
        logs.append(f"No internship table found in {os.path.basename(path)}")
    return None

# -------------------------------
# Consolidation
# -------------------------------
def process_paths(named_paths: List[Tuple[str, str]], verbose: bool=False, logs: List[str]=None) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    named_paths: list of (student_display_name, file_path)
    Returns:
      df: consolidated table (Student + internship codes)
      processed: list of file names processed OK
      errors: list of error messages
    """
    rows: List[Dict] = []
    processed: List[str] = []
    errors: List[str] = []

    for display_name, path in named_paths:
        file_name = os.path.basename(path)
        data = extract_internship_data_from_path(path, verbose=verbose, logs=logs)
        if not data:
            msg = f"{file_name}: internship table not found"
            errors.append(msg)
            if verbose and logs is not None:
                logs.append(msg)
            continue

        row = {"Student": display_name, **data}
        rows.append(row)
        processed.append(file_name)

    if not rows:
        return pd.DataFrame(), processed, errors

    df = pd.DataFrame(rows).fillna(0)

    # Ensure Student first; sort internship columns for stability
    first = ["Student"]
    other = sorted([c for c in df.columns if c not in first], key=str.lower)
    df = df[first + other]
    return df, processed, errors

# -------------------------------
# Streamlit UI
# -------------------------------
def run():
    st.subheader("🎓 Internship Data Consolidator")
    st.caption(VERSION)
    st.caption("• Upload **.zip** and/or **.xlsx/.xls**. Each student's **file name** (without extension) is used as the student identifier.")

    verbose = st.toggle("Verbose logs", value=False)
    logs: List[str] = []

    uploads = st.file_uploader(
        "Upload ZIP and/or Excel files",
        type=["zip", "xlsx", "xls"],
        accept_multiple_files=True
    )

    if not uploads:
        st.info("Add one or more files to begin.")
        return

    if st.button("Process", type="primary"):
        with st.spinner("Collecting files…"):
            named_paths = _collect_all_excel_paths(uploads, verbose=verbose, logs=logs)

        if not named_paths:
            st.error("No Excel files were found in the uploaded items.")
            if verbose and logs:
                with st.expander("Logs"):
                    for line in logs:
                        st.write(line)
            return

        st.success(f"Found {len(named_paths)} student file(s).")

        with st.spinner("Extracting internship data…"):
            df, ok, bad = process_paths(named_paths, verbose=verbose, logs=logs)

        _render_results(df, ok, bad, logs if verbose else None)

def _render_results(df: pd.DataFrame, ok: List[str], bad: List[str], logs: Optional[List[str]]=None) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Processed files", len(ok))
    with c2:
        st.metric("Errors", len(bad))
    with c3:
        st.metric("Students", 0 if df.empty else len(df))

    if logs:
        with st.expander("Logs"):
            for line in logs:
                st.write(line)

    if bad:
        st.markdown("**Issues found**")
        for e in bad:
            st.error(e)

    if not df.empty:
        st.markdown("**Consolidated Preview**")
        st.dataframe(df, use_container_width=True, hide_index=True)

        out = BytesIO()
        df.to_excel(out, engine="openpyxl", index=False, sheet_name="Consolidated_Report")
        st.download_button(
            "📥 Download Excel",
            out.getvalue(),
            file_name="consolidated_internship_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
