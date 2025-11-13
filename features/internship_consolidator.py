# internship_consolidator.py
import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile, os, tempfile
from typing import Dict, List, Optional, Tuple, Iterable

# -------------------------------
# Low-level extractor
# -------------------------------
def extract_internship_data_from_path(path: str) -> Optional[Dict[str, int]]:
    """
    Scan all sheets to locate a table whose header row contains:
      col0 == "Internship Code"  AND  col2 == "Completed"
    Then read subsequent rows until a blank/short row, returning {code: completed_int}.
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

        nrows = len(df)
        for i in range(nrows):
            try:
                row = df.iloc[i]
            except Exception:
                continue

            # Guard on row length & header match (case-insensitive)
            if (
                len(row) >= 3
                and pd.notna(row.iloc[0])
                and pd.notna(row.iloc[2])
                and str(row.iloc[0]).strip().lower() == "internship code"
                and str(row.iloc[2]).strip().lower() == "completed"
            ):
                out: Dict[str, int] = {}
                # Read downward until broken table
                for j in range(i + 1, nrows):
                    r = df.iloc[j]
                    if len(r) < 3:
                        break
                    code_val = r.iloc[0]
                    comp_val = r.iloc[2]
                    if pd.isna(code_val) or pd.isna(comp_val):
                        break
                    code = str(code_val).strip()
                    if not code:
                        break
                    try:
                        completed = int(float(comp_val))
                    except Exception:
                        # Not a number -> stop or skip; we choose stop to avoid sliding into another section
                        break
                    out[code] = completed
                if out:
                    return out
    return None


# -------------------------------
# Utilities to gather files
# -------------------------------
def _excel_paths_from_zip(uploaded_zip) -> List[str]:
    paths: List[str] = []
    td = tempfile.TemporaryDirectory()
    try:
        with zipfile.ZipFile(uploaded_zip, "r") as zf:
            zf.extractall(td.name)
        for root, _, files in os.walk(td.name):
            for f in files:
                if f.lower().endswith((".xlsx", ".xls")):
                    paths.append(os.path.join(root, f))
    except Exception:
        pass
    return paths


def _names_and_paths_from_uploaded_files(files: Iterable) -> List[Tuple[str, str]]:
    """
    Save Streamlit UploadedFiles to temp paths and return [(display_name, path)].
    display_name is file name without extension.
    """
    out: List[Tuple[str, str]] = []
    if not files:
        return out
    td = tempfile.TemporaryDirectory()
    base = td.name
    for up in files:
        try:
            fname = os.path.basename(up.name)
            # write to disk
            buf = up.read()
            path = os.path.join(base, fname)
            with open(path, "wb") as fp:
                fp.write(buf)
            display = os.path.splitext(fname)[0]
            out.append((display, path))
        except Exception:
            continue
    return out


# -------------------------------
# Core processors
# -------------------------------
def process_paths(named_paths: List[Tuple[str, str]]) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    named_paths: list of (student_display_name, file_path)
    Returns:
      df: consolidated table
      processed: list of file names processed OK
      errors: list of error messages
    """
    rows: List[Dict] = []
    processed: List[str] = []
    errors: List[str] = []

    for display_name, path in named_paths:
        file_name = os.path.basename(path)
        data = extract_internship_data_from_path(path)
        if not data:
            errors.append(f"{file_name}: internship table not found")
            continue
        row = {"Student": display_name, **data}
        rows.append(row)
        processed.append(file_name)

    if not rows:
        return pd.DataFrame(), processed, errors

    df = pd.DataFrame(rows).fillna(0)
    # Ensure Student is first column, sort the rest alphabetically for stable order
    first = ["Student"]
    other = sorted([c for c in df.columns if c not in first], key=str.lower)
    df = df[first + other]
    return df, processed, errors


# -------------------------------
# Streamlit UI
# -------------------------------
def run():
    st.subheader("🎓 Internship Data Consolidator")
    st.caption("• Each student must be **one Excel file**. The student's file name is used as the student identifier.")

    mode = st.radio(
        "Choose upload method",
        ["Upload a ZIP of many Excel files", "Upload multiple Excel files directly"],
        horizontal=True,
    )

    named_paths: List[Tuple[str, str]] = []

    if mode == "Upload a ZIP of many Excel files":
        up_zip = st.file_uploader("Upload .zip", type=["zip"])
        if up_zip and st.button("Process ZIP", type="primary"):
            with st.spinner("Unpacking and reading files…"):
                paths = _excel_paths_from_zip(up_zip)
                if not paths:
                    st.error("No Excel files found in the ZIP.")
                    return
                named_paths = [(os.path.splitext(os.path.basename(p))[0], p) for p in paths]

            with st.spinner("Extracting internship data…"):
                df, ok, bad = process_paths(named_paths)
            _render_results(df, ok, bad)

    else:
        up_files = st.file_uploader("Upload Excel files", type=["xlsx", "xls"], accept_multiple_files=True)
        if up_files and st.button("Process Files", type="primary"):
            with st.spinner("Saving files…"):
                named_paths = _names_and_paths_from_uploaded_files(up_files)
                if not named_paths:
                    st.error("No readable Excel files were uploaded.")
                    return

            with st.spinner("Extracting internship data…"):
                df, ok, bad = process_paths(named_paths)
            _render_results(df, ok, bad)


def _render_results(df: pd.DataFrame, ok: List[str], bad: List[str]) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Processed", len(ok))
    with c2:
        st.metric("Errors", len(bad))
    with c3:
        st.metric("Students", 0 if df.empty else len(df))

    if bad:
        st.markdown("**Errors**")
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
