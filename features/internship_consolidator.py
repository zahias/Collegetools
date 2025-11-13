# internship_consolidator.py
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
# Helpers: file collection
# -------------------------------
JUNK_PREFIXES = ("._",)  # macOS resource-fork files
JUNK_DIRS = ("__MACOSX",)  # macOS zip dir

def _is_excel_path(p: str) -> bool:
    pl = p.lower()
    if any(part in pl for part in JUNK_DIRS):
        return False
    base = os.path.basename(p)
    if base.startswith(JUNK_PREFIXES):
        return False
    return pl.endswith(".xlsx") or pl.endswith(".xls")

def _save_uploaded_file(tmpdir: str, up_file) -> str:
    fname = os.path.basename(up_file.name)
    path = os.path.join(tmpdir, fname)
    with open(path, "wb") as fp:
        fp.write(up_file.getbuffer())
    return path

def _extract_excel_paths_from_zip(zip_path: str, into_dir: str) -> List[str]:
    excel_paths: List[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(into_dir)
        for root, _, files in os.walk(into_dir):
            # skip junk dirs
            if any(j in root for j in JUNK_DIRS):
                continue
            for f in files:
                full = os.path.join(root, f)
                if _is_excel_path(full):
                    excel_paths.append(full)
    except Exception:
        pass
    return excel_paths

def _collect_all_excel_paths(uploaded_files: Iterable) -> List[Tuple[str, str]]:
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
        except Exception:
            continue

    # Walk saved files
    for p in saved_paths:
        pl = p.lower()
        if pl.endswith(".zip"):
            zdir = os.path.join(base, f"unzipped_{os.path.splitext(os.path.basename(p))[0]}")
            os.makedirs(zdir, exist_ok=True)
            for ep in _extract_excel_paths_from_zip(p, zdir):
                if _is_excel_path(ep):
                    display = pathlib.Path(ep).stem
                    results.append((display, ep))
        elif _is_excel_path(p):
            display = pathlib.Path(p).stem
            results.append((display, p))
        else:
            # ignore other types
            pass

    # remove dup paths just in case
    seen = set()
    dedup: List[Tuple[str, str]] = []
    for name, path in results:
        if path not in seen:
            seen.add(path)
            dedup.append((name, path))
    return dedup


# -------------------------------
# Core extractor
# -------------------------------
def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _find_header_positions(df: pd.DataFrame) -> Optional[Tuple[int, int, int]]:
    """
    Scan for a header row containing something like:
      - a column with 'internship code' (loosely matched)
      - a column with 'completed' (loosely matched)
    Returns (header_row_idx, code_col_idx, completed_col_idx)
    """
    nrows, ncols = df.shape
    for i in range(nrows):
        row = df.iloc[i]
        # build normalized strings for cells in this row
        norm_cells = [_norm(x) for x in row.tolist()]
        # find likely indices
        code_idx = None
        comp_idx = None
        for idx, val in enumerate(norm_cells):
            if "internship" in val and "code" in val:
                code_idx = idx if code_idx is None else code_idx
            if "completed" in val:
                comp_idx = idx if comp_idx is None else comp_idx
        if code_idx is not None and comp_idx is not None:
            return i, code_idx, comp_idx
    return None

def extract_internship_data_from_path(path: str) -> Optional[Dict[str, int]]:
    """
    Reads all sheets, finds the internships table by locating a header row
    (one cell ~ 'Internship Code' and another ~ 'Completed'), then collects
    rows beneath until the table ends. Returns {code: completed_int}.
    """
    try:
        xls = pd.ExcelFile(path)
    except Exception:
        return None

    for sh in xls.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sh, header=None)
        except Exception:
            continue

        if df.empty:
            continue

        found = _find_header_positions(df)
        if not found:
            continue

        header_row, code_col, comp_col = found
        out: Dict[str, int] = {}

        # parse table beneath header
        for r in range(header_row + 1, len(df)):
            row = df.iloc[r]
            # require both code + completed to be present
            if code_col >= len(row) or comp_col >= len(row):
                break
            code_val = row.iloc[code_col]
            comp_val = row.iloc[comp_col]

            # stop at first empty/broken row (end of table)
            if pd.isna(code_val) or str(code_val).strip() == "":
                break
            if pd.isna(comp_val) or str(comp_val).strip() == "":
                # If completed missing, treat as 0 and keep moving
                completed = 0
            else:
                try:
                    completed = int(float(str(comp_val).strip()))
                except Exception:
                    # if not a number -> assume table ended
                    break

            code = str(code_val).strip()
            if code:
                out[code] = completed

        if out:
            return out

    return None


# -------------------------------
# Consolidation
# -------------------------------
def process_paths(named_paths: List[Tuple[str, str]]) -> Tuple[pd.DataFrame, List[str], List[str]]:
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
        try:
            data = extract_internship_data_from_path(path)
        except Exception as e:
            data = None

        if not data:
            errors.append(f"{file_name}: internship table not found")
            continue

        row = {"Student": display_name, **data}
        rows.append(row)
        processed.append(file_name)

    if not rows:
        return pd.DataFrame(), processed, errors

    df = pd.DataFrame(rows).fillna(0)

    # Ensure Student first; sort internship columns alphabetically for stable order
    first = ["Student"]
    other = sorted([c for c in df.columns if c not in first], key=str.lower)
    df = df[first + other]
    return df, processed, errors


# -------------------------------
# Streamlit UI
# -------------------------------
def run():
    st.subheader("🎓 Internship Data Consolidator")
    st.caption("• Upload **.zip** and/or **.xlsx/.xls**. Each student's **file name** (without extension) is used as the student identifier.")

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
            named_paths = _collect_all_excel_paths(uploads)

        if not named_paths:
            st.error("No Excel files were found in the uploaded items.")
            return

        st.success(f"Found {len(named_paths)} student file(s).")

        with st.spinner("Extracting internship data…"):
            df, ok, bad = process_paths(named_paths)

        _render_results(df, ok, bad)


def _render_results(df: pd.DataFrame, ok: List[str], bad: List[str]) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Processed files", len(ok))
    with c2:
        st.metric("Errors", len(bad))
    with c3:
        st.metric("Students", 0 if df.empty else len(df))

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
