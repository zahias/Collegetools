# features/internship_consolidator.py
# VERSION: 2025-11-13T12:30Z — in-memory zip/xlsx, filename-as-student, no ID reads

import re
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

VERSION = "Internship Data Consolidator — 2025-11-13 12:30Z"

# Ignore macOS junk inside ZIPs
JUNK_DIR_PREFIXES = ("__MACOSX/",)
JUNK_FILE_PREFIXES = ("._",)

# Accept multiple header wordings for the "completed" column
COMPLETED_TERMS = [
    "completed",
    "completed hours",
    "hours completed",
    "# completed",
    "hrs completed",
    "completed (hrs)",
]

# ---------- helpers ----------
def _is_excel_name(name: str) -> bool:
    n = name.lower()
    return n.endswith(".xlsx") or n.endswith(".xls")

def _is_junk_member(name: str) -> bool:
    if name.endswith("/"):
        return True
    for p in JUNK_DIR_PREFIXES:
        if name.startswith(p):
            return True
    base = name.split("/")[-1]
    return any(base.startswith(pref) for pref in JUNK_FILE_PREFIXES)

def _stem(name: str) -> str:
    base = name.split("/")[-1]
    return base.rsplit(".", 1)[0] if "." in base else base

def _norm(x) -> str:
    return re.sub(r"\s+", " ", str(x).strip().lower())

# ---------- table detection ----------
def _find_header_positions(df: pd.DataFrame) -> Optional[Tuple[int, int, int]]:
    """
    Find a header row that has:
      - a column containing both 'internship' and 'code'
      - a column containing any of COMPLETED_TERMS
    Return (header_row_idx, code_col_idx, completed_col_idx)
    """
    for i in range(len(df)):
        row = df.iloc[i]
        cells = [_norm(v) for v in row.tolist()]
        code_idx = None
        comp_idx = None
        for j, val in enumerate(cells):
            if "internship" in val and "code" in val:
                code_idx = j
                break
        if code_idx is None:
            continue
        for j, val in enumerate(cells):
            if any(term in val for term in COMPLETED_TERMS):
                comp_idx = j
                break
        if code_idx is not None and comp_idx is not None:
            return i, code_idx, comp_idx
    return None

def extract_internship_data_from_excel_bytes(xbytes: bytes, logs: List[str]) -> Optional[Dict[str, int]]:
    """
    Read an Excel (bytes) and extract {internship_code: completed_int}.
    Scans all sheets and auto-detects the table by headers.
    """
    try:
        xls = pd.ExcelFile(BytesIO(xbytes))
    except Exception as e:
        logs.append(f"  !! Failed to open Excel: {e}")
        return None

    for sh in xls.sheet_names:
        try:
            df = pd.read_excel(BytesIO(xbytes), sheet_name=sh, header=None)
        except Exception as e:
            logs.append(f"  !! Sheet read error [{sh}]: {e}")
            continue

        if df.empty:
            continue

        found = _find_header_positions(df)
        if not found:
            continue

        header_row, code_col, comp_col = found
        logs.append(f"  > Found header in sheet '{sh}' at row {header_row}, code_col={code_col}, completed_col={comp_col}")

        out: Dict[str, int] = {}
        for r in range(header_row + 1, len(df)):
            row = df.iloc[r]
            if code_col >= len(row) or comp_col >= len(row):
                break

            code_val = row.iloc[code_col]
            comp_val = row.iloc[comp_col]

            # end of table if code blank
            if pd.isna(code_val) or str(code_val).strip() == "":
                break

            code = str(code_val).strip()

            # completed: blank -> 0; non-numeric -> stop table (likely a new section)
            completed = 0
            if pd.notna(comp_val) and str(comp_val).strip() != "":
                try:
                    completed = int(float(str(comp_val).strip()))
                except Exception:
                    break

            out[code] = completed

        if out:
            return out

    logs.append("  .. No internship table found in any sheet")
    return None

# ---------- uploads ----------
def collect_excel_streams(uploads, logs: List[str]) -> List[Tuple[str, bytes]]:
    """
    Accepts a mixed list of UploadedFile items (.zip/.xlsx/.xls).
    Returns a list of (student_name_from_filename, excel_bytes).
    """
    results: List[Tuple[str, bytes]] = []

    for up in uploads:
        name = up.name
        low = name.lower()

        # Direct Excel
        if _is_excel_name(low):
            student = _stem(name)
            data = bytes(up.getbuffer())
            logs.append(f"* Excel: {name} → Student='{student}'")
            results.append((student, data))
            continue

        # ZIP (in-memory)
        if low.endswith(".zip"):
            logs.append(f"* ZIP: {name}")
            try:
                import zipfile
                zf = zipfile.ZipFile(BytesIO(up.getbuffer()))
            except Exception as e:
                logs.append(f"  !! Bad ZIP: {e}")
                continue

            for member in zf.namelist():
                if _is_junk_member(member):
                    logs.append(f"    - skip junk: {member}")
                    continue
                if not _is_excel_name(member):
                    logs.append(f"    - skip (not excel): {member}")
                    continue
                try:
                    data = zf.read(member)
                    student = _stem(member)
                    logs.append(f"    + add Excel: {member} → Student='{student}'")
                    results.append((student, data))
                except Exception as e:
                    logs.append(f"    !! read error: {member} — {e}")
            continue

        # Unknown file
        logs.append(f"* Ignored (not zip/xlsx/xls): {name}")

    # crude dedupe to avoid duplicate resource-fork copies with same name/size
    seen = set()
    dedup: List[Tuple[str, bytes]] = []
    for student, data in results:
        key = (student, len(data))
        if key in seen:
            continue
        seen.add(key)
        dedup.append((student, data))
    return dedup

# ---------- consolidate ----------
def consolidate(streams: List[Tuple[str, bytes]], logs: List[str]) -> Tuple[pd.DataFrame, List[str], List[str]]:
    rows: List[Dict] = []
    ok, bad = [], []

    for student, xbytes in streams:
        logs.append(f"- Processing '{student}'")
        mapping = extract_internship_data_from_excel_bytes(xbytes, logs)
        if not mapping:
            bad.append(student)
            continue
        rows.append({"Student": student, **mapping})
        ok.append(student)

    if not rows:
        return pd.DataFrame(), ok, bad

    df = pd.DataFrame(rows).fillna(0)
    # keep Student first, sort other columns for stable order
    first = ["Student"]
    other = sorted([c for c in df.columns if c not in first], key=str.lower)
    df = df[first + other]
    return df, ok, bad

# ---------- streamlit UI ----------
def run():
    st.subheader("🎓 Internship Data Consolidator")
    st.caption(VERSION)
    st.caption("• Upload **.zip** and/or **.xlsx/.xls**. The **file name** becomes the student name. No IDs are read from inside sheets.")

    verbose = st.toggle("Verbose logs", value=True)

    uploads = st.file_uploader(
        "Upload ZIP and/or Excel files",
        type=["zip", "xlsx", "xls"],
        accept_multiple_files=True
    )
    if not uploads:
        st.info("Add one or more files to begin.")
        return

    if st.button("Process", type="primary"):
        logs: List[str] = []
        streams = collect_excel_streams(uploads, logs)
        if not streams:
            st.error("No Excel files were found in the uploaded items.")
            if verbose and logs:
                with st.expander("Logs"):
                    for line in logs:
                        st.write(line)
            return

        df, ok, bad = consolidate(streams, logs)

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Excel streams", len(streams))
        with c2: st.metric("Processed", len(ok))
        with c3: st.metric("Errors", len(bad))

        if verbose and logs:
            with st.expander("Logs"):
                for line in logs:
                    st.write(line)

        if bad:
            st.warning("Files without a detectable internship table:")
            st.write(", ".join(bad))

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
