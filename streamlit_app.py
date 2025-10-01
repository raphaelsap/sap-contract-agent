from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st
import yaml

from app.service import get_service
from app.utils.storage import StorageManager

service = get_service()

CUSTOM_CSS = """
<style>
:root {
    --primary-bg: #f4f7fb;
    --card-bg: #ffffffcc;
    --accent: #0a6ed1;
}
[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, var(--primary-bg) 0%, #dde6f5 100%);
}
main .block-container {
    padding-top: 3rem;
    padding-bottom: 3rem;
}
.headline {
    background: var(--card-bg);
    border-radius: 18px;
    padding: 1.5rem 2rem;
    box-shadow: 0 16px 40px rgb(10 110 209 / 8%);
}
.headline h1 {
    font-size: 2.2rem;
    margin-bottom: 0.2rem;
}
.headline p {
    margin: 0;
    color: #3a506b;
    font-size: 1rem;
}
.status-card {
    background: var(--card-bg);
    padding: 1.2rem 1.5rem;
    border-radius: 16px;
    box-shadow: 0 12px 32px rgb(12 68 204 / 10%);
}
.status-card h3 {
    margin: 0;
    font-size: 1rem;
    color: #4d5f7a;
    text-transform: uppercase;
    letter-spacing: .08em;
}
.status-card p {
    margin: .6rem 0 0;
    font-size: 1.6rem;
    font-weight: 600;
    color: #0a3d62;
}
.stTabs [role="tablist"] > div {
    font-weight: 600;
    padding: .75rem 1.2rem;
}
.preview-quote {
    border-left: 4px solid var(--accent);
    padding: .6rem 1rem;
    margin-bottom: .6rem;
    background: #f7fbff;
    border-radius: 8px;
    color: #19324d;
}
.sidebar-box {
    background: #0a3d62;
    border-radius: 18px;
    padding: 1.2rem;
    color: #fff;
}
.sidebar-box h3 {
    margin-top: 0;
    font-size: 1.1rem;
}
.sidebar-run {
    padding: .8rem 1rem;
    border-radius: 12px;
    background: rgba(255,255,255,.08);
    margin-bottom: .6rem;
}
.sidebar-run span {
    display: block;
    font-size: .82rem;
    opacity: .8;
}
</style>
"""


def apply_custom_style() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _persist_upload(storage: StorageManager, run_id: str, uploaded_file: Any) -> Path:
    content = uploaded_file.getvalue()
    filename = uploaded_file.name or "uploaded_file"
    return storage.save_raw_file(run_id, filename, content)


def render_header() -> None:
    st.markdown(
        """
        <div class="headline">
            <h1>SAP Contract Agent</h1>
            <p>Upload contract PDFs and invoice spreadsheets to extract structure, compare terms, and surface recommended follow-ups.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_run_history() -> None:
    with st.sidebar:
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.markdown("<h3>Recent Runs</h3>", unsafe_allow_html=True)
        runs = service.storage.list_run_directories()
        st.metric(label="Total Runs", value=len(runs))
        if not runs:
            st.markdown("<span>No processed runs yet — upload documents to get started.</span>", unsafe_allow_html=True)
        else:
            for run_id, paths in sorted(runs.items(), reverse=True):
                st.markdown(
                    f"<div class='sidebar-run'><strong>{run_id}</strong><span>Data: {paths['data']}</span><span>Artefacts: {paths['artefacts']}</span></div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


def render_results(run_id: str, result: Dict[str, str], analysis: Dict[str, str]) -> None:
    contract_payload = yaml.safe_load(result["contract_yaml"]) or {}
    invoice_payload = yaml.safe_load(result["invoice_yaml"]) or {}
    element_count = contract_payload.get("element_count", 0)
    sheets = invoice_payload.get("sheets", {})
    sheet_count = len(sheets)
    row_count = sum(sheet.get("row_count", 0) for sheet in sheets.values())

    st.divider()
    st.markdown(f"### Run {run_id}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div class='status-card'><h3>Contract Segments</h3><p>" + str(element_count) + "</p></div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='status-card'><h3>Invoice Sheets</h3><p>" + str(sheet_count) + "</p></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='status-card'><h3>Total Line Items</h3><p>" + str(row_count) + "</p></div>", unsafe_allow_html=True)

    preview_texts = []
    for element in contract_payload.get("elements", []):
        text = (element or {}).get("text", "").strip()
        if text:
            preview_texts.append(text)
        if len(preview_texts) == 3:
            break

    if preview_texts:
        st.markdown("#### Contract Glimpse")
        for snippet in preview_texts:
            st.markdown(f"<div class='preview-quote'>{snippet}</div>", unsafe_allow_html=True)

    tabs = st.tabs(["Contract YAML", "Invoice YAML", "Comparison", "Next Actions"])

    with tabs[0]:
        st.download_button(
            label="Download contract YAML",
            data=result["contract_yaml"],
            file_name=f"{run_id}_contract.yaml",
            mime="text/yaml",
        )
        st.code(result["contract_yaml"], language="yaml")
        st.caption(f"Stored at {result['contract_yaml_path']}")

    with tabs[1]:
        st.download_button(
            label="Download invoice YAML",
            data=result["invoice_yaml"],
            file_name=f"{run_id}_invoice.yaml",
            mime="text/yaml",
        )
        st.code(result["invoice_yaml"], language="yaml")
        st.caption(f"Stored at {result['invoice_yaml_path']}")

    with tabs[2]:
        st.download_button(
            label="Download comparison report",
            data=analysis["comparison_md"],
            file_name=f"{run_id}_comparison.md",
            mime="text/markdown",
        )
        st.markdown(analysis["comparison_md"])
        st.caption(f"Stored at {analysis['comparison_path']}")

    with tabs[3]:
        st.download_button(
            label="Download recommendations",
            data=analysis["recommendation_md"],
            file_name=f"{run_id}_recommendations.md",
            mime="text/markdown",
        )
        st.markdown(analysis["recommendation_md"])
        st.caption(f"Stored at {analysis['recommendation_path']}")


def main() -> None:
    st.set_page_config(page_title="SAP Contract Agent", layout="wide")
    apply_custom_style()
    render_header()
    render_run_history()

    with st.form("upload_form"):
        st.subheader("Upload documents")
        col_a, col_b = st.columns(2)
        with col_a:
            pdf_file = st.file_uploader(
                "Contract PDF",
                type=["pdf"],
                accept_multiple_files=False,
                help="Upload the contract document to process with OCR.",
            )
        with col_b:
            invoice_file = st.file_uploader(
                "Invoice spreadsheet",
                type=["xlsx", "xls"],
                accept_multiple_files=False,
                help="Upload the matching invoice in Excel format.",
            )
        submit = st.form_submit_button("Process", use_container_width=True)

    if submit:
        if pdf_file is None or invoice_file is None:
            st.error("Please upload both a contract PDF and an invoice spreadsheet.")
            return

        run_id = service.storage.create_run_id()

        with st.status("Processing documents", expanded=True) as status:
            status.write("Saving uploads...")
            st.toast("Uploads received", icon="📁")
            contract_path = _persist_upload(service.storage, run_id, pdf_file)
            invoice_path = _persist_upload(service.storage, run_id, invoice_file)

            status.write("Extracting structured YAML...")
            st.toast("Running unstructured + pandas extraction", icon="🧠")
            try:
                result = service.process_documents(pdf_path=contract_path, excel_path=invoice_path, run_id=run_id)
            except Exception as exc:
                status.update(label="Processing failed", state="error")
                st.error(f"Failed to process documents: {exc}")
                return

            status.write("Running LLM comparison and action planning...")
            st.toast("Calling SAP AI Core for comparison", icon="🤖")
            try:
                analysis = service.run_analysis(result["contract_yaml"], result["invoice_yaml"], run_id)
            except Exception as exc:
                status.update(label="LLM analysis failed", state="error")
                st.error(f"Failed to run analysis: {exc}")
                return

            status.update(label="Processing complete", state="complete")
            st.toast("Analysis complete", icon="✅")

        st.success(f"Run {run_id} finished.")
        render_results(run_id, result, analysis)


if __name__ == "__main__":
    main()
