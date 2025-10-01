from __future__ import annotations

import streamlit as st
from pathlib import Path
from typing import Any

from app.service import get_service
from app.utils.storage import StorageManager

service = get_service()


def _persist_upload(storage: StorageManager, run_id: str, uploaded_file: Any) -> Path:
    content = uploaded_file.getvalue()
    filename = uploaded_file.name or "uploaded_file"
    return storage.save_raw_file(run_id, filename, content)


def main() -> None:
    st.set_page_config(page_title="SAP Contract Agent", layout="wide")
    st.title("SAP Contract Agent")
    st.caption("Process contract PDFs and invoice spreadsheets, compare them, and get next-step guidance.")

    if "runs" not in st.session_state:
        st.session_state["runs"] = []

    with st.sidebar:
        st.header("Stored Runs")
        runs = service.storage.list_run_directories()
        if not runs:
            st.write("No runs yet.")
        else:
            for run_id, paths in runs.items():
                st.write(f"{run_id}")
                st.caption(f"Data: {paths['data']}\nArtefacts: {paths['artefacts']}")

    with st.form("upload_form"):
        st.subheader("Upload documents")
        pdf_file = st.file_uploader("Contract PDF", type=["pdf"], accept_multiple_files=False)
        invoice_file = st.file_uploader("Invoice spreadsheet", type=["xlsx", "xls"], accept_multiple_files=False)
        submit = st.form_submit_button("Process")

    if submit:
        if pdf_file is None or invoice_file is None:
            st.error("Please upload both a contract PDF and an invoice spreadsheet.")
            return

        run_id = service.storage.create_run_id()

        with st.status("Processing documents", expanded=True) as status:
            status.write("Saving uploads...")
            contract_path = _persist_upload(service.storage, run_id, pdf_file)
            invoice_path = _persist_upload(service.storage, run_id, invoice_file)

            status.write("Extracting structured YAML...")
            try:
                result = service.process_documents(pdf_path=contract_path, excel_path=invoice_path, run_id=run_id)
            except Exception as exc:
                status.update(label="Processing failed", state="error")
                st.error(f"Failed to process documents: {exc}")
                return

            status.write("Running LLM comparison and action planning...")
            try:
                analysis = service.run_analysis(result["contract_yaml"], result["invoice_yaml"], run_id)
            except Exception as exc:
                status.update(label="LLM analysis failed", state="error")
                st.error(f"Failed to run analysis: {exc}")
                return

            status.update(label="Processing complete", state="complete")

        st.success(f"Run {run_id} finished.")

        tabs = st.tabs(["Contract YAML", "Invoice YAML", "Comparison", "Next Actions"])
        with tabs[0]:
            st.code(result["contract_yaml"], language="yaml")
            st.caption(f"Stored at {result['contract_yaml_path']}")
        with tabs[1]:
            st.code(result["invoice_yaml"], language="yaml")
            st.caption(f"Stored at {result['invoice_yaml_path']}")
        with tabs[2]:
            st.markdown(analysis["comparison_md"])
            st.caption(f"Stored at {analysis['comparison_path']}")
        with tabs[3]:
            st.markdown(analysis["recommendation_md"])
            st.caption(f"Stored at {analysis['recommendation_path']}")

        st.session_state["runs"].append(run_id)


if __name__ == "__main__":
    main()
