import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile, os, tempfile
from typing import Dict, List, Optional, Tuple

def extract_internship_data(path: str) -> Optional[Dict[str, int]]:
    try:
        xls = pd.ExcelFile(path)
        out = {}
        for sh in xls.sheet_names:
            try:
                df = pd.read_excel(path, sheet_name=sh, header=None)
                for i in range(len(df)):
                    row = df.iloc[i]
                    if (len(row) >= 4 and
                        pd.notna(row.iloc[0]) and pd.notna(row.iloc[2]) and
                        str(row.iloc[0]).strip().lower() == "internship code" and
                        str(row.iloc[2]).strip().lower() == "completed"):
                        for j in range(i+1, len(df)):
                            r = df.iloc[j]
                            if len(r) >= 4 and pd.notna(r.iloc[0]) and pd.notna(r.iloc[2]):
                                code = str(r.iloc[0]).strip()
                                try:
                                    comp = int(float(r.iloc[2]))
                                except Exception:
                                    continue
                                if code: out[code] = comp
                            else:
                                break
                        if out: return out
            except Exception:
                continue
        return out if out else None
    except Exception:
        return None

def process_zip(up_zip) -> Tuple[pd.DataFrame, List[str], List[str]]:
    processed, errors, all_rows = [], [], []
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(up_zip, "r") as zf:
            zf.extractall(td)
        excel_files = []
        for root,_,files in os.walk(td):
            for f in files:
                if f.endswith((".xlsx",".xls")):
                    excel_files.append(os.path.join(root,f))
        if not excel_files:
            return pd.DataFrame(), [], ["No Excel files found in the zip."]
        for path in excel_files:
            file_name = os.path.basename(path)
            student_display = os.path.splitext(file_name)[0]
            data = extract_internship_data(path)
            if not data:
                errors.append(f"{file_name}: internship table not found")
                continue
            row = {"Student Name": student_display, **data}
            all_rows.append(row)
            processed.append(file_name)

    if not all_rows:
        return pd.DataFrame(), processed, errors

    df = pd.DataFrame(all_rows).fillna(0)
    preferred = ["Student Name"]
    cols = preferred + [c for c in df.columns if c not in preferred]
    return df[cols], processed, errors

def run():
    st.subheader("🎓 Internship Data Consolidator")
    up = st.file_uploader("Upload a .zip of Excel files (one student per file)", type=["zip"])

    if up and st.button("Process", type="primary"):
        with st.spinner("Reading files…"):
            df, ok, bad = process_zip(up)
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Processed", len(ok))
        with c2: st.metric("Errors", len(bad))
        with c3: st.metric("Students", 0 if df.empty else len(df))
        if bad:
            st.markdown("**Errors**")
            for e in bad: st.error(e)
        if not df.empty:
            st.markdown("**Consolidated Preview**")
            st.dataframe(df, use_container_width=True, hide_index=True)
            out = BytesIO(); df.to_excel(out, engine="openpyxl", index=False, sheet_name="Consolidated_Report")
            st.download_button("📥 Download Excel", out.getvalue(),
                               file_name="consolidated_internship_report.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
