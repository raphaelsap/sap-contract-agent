from __future__ import annotations

from typing import Any, Dict
import logging
import time

import streamlit as st
import yaml

from app.service import get_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamlit_app")
service = get_service()


CUSTOM_CSS = """
<style>
:root {
    --sap-night: #050913;
    --sap-deep: #081427;
    --sap-card: rgba(12, 28, 52, 0.92);
    --sap-border: rgba(55, 178, 255, 0.35);
    --sap-blue: #0a6ed1;
    --sap-cyan: #37b2ff;
    --sap-text: #ecf4ff;
    --sap-muted: #8ea6c8;
}
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 20% 20%, rgba(10, 110, 209, 0.15), transparent 55%),
                linear-gradient(160deg, var(--sap-night) 0%, var(--sap-deep) 65%, #050913 100%);
    color: var(--sap-text);
}
main .block-container {
    padding-top: 3.5rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}
body, p, label, span, div, button {
    color: var(--sap-text) !important;
    font-family: "72", "Segoe UI", sans-serif;
}
a { color: var(--sap-cyan); }
.headline {
    background: var(--sap-card);
    border: 1px solid var(--sap-border);
    border-radius: 22px;
    padding: 1.8rem 2.4rem;
    box-shadow: 0 24px 60px rgba(5, 15, 35, 0.45);
    position: relative;
    overflow: hidden;
}
.headline::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(55, 178, 255, 0.15), transparent 55%);
    pointer-events: none;
}
.agent-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    background: rgba(55, 178, 255, 0.12);
    border: 1px solid rgba(55, 178, 255, 0.35);
    color: var(--sap-cyan);
    padding: 0.35rem 0.9rem;
    border-radius: 999px;
    font-size: 0.78rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}
.headline h1 {
    font-size: 2.2rem;
    margin: 0 0 0.6rem 0;
}
.headline p {
    margin: 0;
    color: var(--sap-muted);
    font-size: 1rem;
}
.agent-activity {
    margin-top: 1.4rem;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.8rem;
}
.agent-activity-item {
    background: rgba(10, 110, 209, 0.08);
    border: 1px solid rgba(55, 178, 255, 0.18);
    border-radius: 14px;
    padding: 0.85rem 1rem;
    font-size: 0.92rem;
}
.agent-activity-item span {
    display: block;
    color: var(--sap-muted);
    font-size: 0.78rem;
    margin-top: 0.35rem;
}
.sidebar-box {
    background: rgba(8, 18, 40, 0.9);
    border: 1px solid var(--sap-border);
    border-radius: 20px;
    padding: 1.4rem 1.2rem;
    margin-top: 1.2rem;
    box-shadow: 0 16px 40px rgba(4, 12, 28, 0.4);
}
.sidebar-box h3 {
    margin: 0 0 1rem 0;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.86rem;
    color: var(--sap-muted);
}
.sidebar-run {
    padding: 0.9rem 1rem;
    border-radius: 14px;
    background: rgba(12, 41, 78, 0.7);
    border: 1px solid rgba(55, 178, 255, 0.18);
    margin-bottom: 0.65rem;
}
.sidebar-run strong {
    font-size: 0.92rem;
}
.sidebar-run span {
    display: block;
    font-size: 0.78rem;
    color: var(--sap-muted);
}
.status-card {
    background: var(--sap-card);
    border: 1px solid rgba(55, 178, 255, 0.2);
    padding: 1.2rem 1.5rem;
    border-radius: 18px;
    box-shadow: 0 16px 40px rgba(2, 9, 24, 0.4);
    width: 100%;
}
.status-card h3 {
    margin: 0;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--sap-muted);
}
.status-card p {
    margin: 0.65rem 0 0;
    font-size: 1.8rem;
    font-weight: 600;
    color: var(--sap-cyan);
}
.status-card span {
    display: block;
    font-size: 0.78rem;
    color: var(--sap-muted);
}
.preview-quote {
    border-left: 3px solid var(--sap-blue);
    padding: 0.7rem 1rem;
    margin-bottom: 0.7rem;
    background: rgba(12, 28, 52, 0.85);
    border-radius: 12px;
    color: var(--sap-text);
}
.stTabs [role="tablist"] {
    border-bottom: 1px solid rgba(55, 178, 255, 0.25);
}
.stTabs [role="tab"] {
    border-radius: 0;
    padding: 0.9rem 1.3rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--sap-muted);
}
.stTabs [role="tab"][aria-selected="true"] {
    border-bottom: 2px solid var(--sap-cyan);
    color: var(--sap-text);
}
[data-testid="stFileUploaderDropzone"] {
    background: rgba(12, 41, 78, 0.6);
    border: 1px dashed rgba(55, 178, 255, 0.45);
}
[data-testid="stToastContainer"] div {
    background: rgba(8, 18, 40, 0.92) !important;
    border: 1px solid rgba(55, 178, 255, 0.25) !important;
}
.stButton button {
    background: var(--sap-blue);
    color: white;
    border-radius: 12px;
    border: none;
    padding: 0.6rem 1.2rem;
    font-weight: 600;
}
.stButton button:hover {
    background: #0b86ff;
}
</style>
"""


def apply_custom_style() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header() -> None:
    st.markdown(
        """
        <div class="headline">
            <img src="https://www.sap.com/dam/application/shared/logos/sap-logo-svg.svg" alt="SAP" width="96" style="margin-bottom: 1rem;" />
            <div class="agent-chip">🛰️ SAP BTP Contract Agent</div>
            <h1>Continuous Contract & Invoice Alignment</h1>
            <p>Your SAP BTP agent ingests contracts, reads invoices, and reports back with guided actions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="agent-activity">
            <div class="agent-activity-item">🔍 Extraction Pipeline<span>OCR with unstructured.io + structured parsing</span></div>
            <div class="agent-activity-item">🤖 Reasoning Engine<span>LangGraph workflow on SAP Generative AI Core</span></div>
            <div class="agent-activity-item">🗂️ Evidence Vault<span>Versioned YAML + markdown artefacts for every run</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )




def format_duration(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{sec}s")
    return " ".join(parts)

def render_results(run_id: str, result: Dict[str, str], analysis: Dict[str, str], processing_seconds: float) -> None:
    contract_payload = yaml.safe_load(result["contract_yaml"]) or {}
    invoice_payload = yaml.safe_load(result["invoice_yaml"]) or {}
    contract_summary = yaml.safe_load(result["contract_summary_yaml"]) or {}
    invoice_summary = yaml.safe_load(result["invoice_summary_yaml"]) or {}

    element_count = contract_payload.get("element_count", 0)
    sheets = invoice_payload.get("sheets", {})
    sheet_count = len(sheets)
    row_count = sum(sheet.get("row_count", 0) for sheet in sheets.values())

    st.divider()
    st.markdown(f"### Mission Report · {run_id}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            "<div class='status-card'><h3>Contract Segments</h3>"
            f"<p>{element_count}</p><span>Structured blocks identified</span></div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            "<div class='status-card'><h3>Invoice Sheets</h3>"
            f"<p>{sheet_count}</p><span>Workbook tabs processed</span></div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            "<div class='status-card'><h3>Line Items</h3>"
            f"<p>{row_count}</p><span>Rows normalised for comparison</span></div>",
            unsafe_allow_html=True,
        )

    preview_texts = contract_summary.get("preview_text", [])
    if preview_texts:
        st.markdown("#### Contract Signal Preview")
        for snippet in preview_texts:
            st.markdown(f"<div class='preview-quote'>{snippet}</div>", unsafe_allow_html=True)

    tabs = st.tabs(["Contract Summary", "Invoice Summary", "Agent Comment"])

    with tabs[0]:
        st.download_button(
            label="Download contract summary",
            data=result["contract_summary_yaml"],
            file_name=f"{run_id}_contract_summary.yaml",
            mime="text/yaml",
        )
        st.download_button(
            label="Download full contract YAML",
            data=result["contract_yaml"],
            file_name=f"{run_id}_contract.yaml",
            mime="text/yaml",
        )
        st.code(result["contract_summary_yaml"], language="yaml")
        st.caption(
            f"Summary stored at {result['contract_summary_path']} — full YAML stored at {result['contract_yaml_path']}"
        )

    with tabs[1]:
        st.download_button(
            label="Download invoice summary",
            data=result["invoice_summary_yaml"],
            file_name=f"{run_id}_invoice_summary.yaml",
            mime="text/yaml",
        )
        st.download_button(
            label="Download full invoice YAML",
            data=result["invoice_yaml"],
            file_name=f"{run_id}_invoice.yaml",
            mime="text/yaml",
        )
        st.code(result["invoice_summary_yaml"], language="yaml")
        st.caption(
            f"Summary stored at {result['invoice_summary_path']} — full YAML stored at {result['invoice_yaml_path']}"
        )

    with tabs[2]:
        st.download_button(
            label="Download agent comment",
            data=analysis.get("comment_md", ""),
            file_name=f"{run_id}_comment.md",
            mime="text/markdown",
        )
        st.markdown(analysis.get("comment_md", ""))
        st.caption(f"Stored at {analysis['comment_path']}")

    st.divider()
    time_saved = max(0, 7200 - processing_seconds)
    st.markdown("#### Time Saved")
    st.markdown(
        f"Your SAP agent just handled this review in **{format_duration(processing_seconds)}**. "
        f"That preserves **{format_duration(time_saved)}** from a standard two-hour manual reconciliation."
    )



def main() -> None:
    st.set_page_config(page_title="SAP BTP Contract Agent", layout="wide")
    apply_custom_style()
    render_header()

    extraction_container = st.container()

    with st.form("upload_form"):
        st.subheader("Deploy a new analysis mission")
        col_a, col_b = st.columns(2)
        with col_a:
            pdf_file = st.file_uploader(
                "Contract PDF",
                type=["pdf"],
                accept_multiple_files=False,
                help="Upload the contract the agent should read (PDF).",
            )
        with col_b:
            invoice_file = st.file_uploader(
                "Invoice spreadsheet",
                type=["xlsx", "xls"],
                accept_multiple_files=False,
                help="Upload the invoice the agent should reconcile (Excel).",
            )
        submit = st.form_submit_button("Launch analysis", use_container_width=True)

    if submit:
        if pdf_file is None or invoice_file is None:
            st.error("Please upload both a contract PDF and an invoice spreadsheet.")
            return

        run_id = service.storage.create_run_id()

        start_ts = time.time()
        extraction_container.empty()
        with st.status("Agent pipeline active", expanded=True) as status:
            status.write("Initializing artefact vault...")
            st.toast("Agent secured uploads", icon="🧷")
            contract_name = pdf_file.name or f"contract_{run_id}.pdf"
            invoice_name = invoice_file.name or f"invoice_{run_id}.xlsx"
            contract_path = service.storage.save_raw_file(run_id, contract_name, pdf_file.getvalue())
            invoice_path = service.storage.save_raw_file(run_id, invoice_name, invoice_file.getvalue())
            logger.info("Saved uploads for run %s at %s and %s", run_id, contract_path, invoice_path)

            status.write("Performing OCR and structuring contract...")
            st.toast("Running unstructured pipeline", icon="🛰️")
            try:
                result = service.process_documents(pdf_path=contract_path, excel_path=invoice_path, run_id=run_id)
            except Exception as exc:
                logger.exception("Document processing failed for run %s", run_id)
                status.update(label="Processing failed", state="error")
                st.error(f"Failed to process documents: {exc}")
                st.info("If the message mentions Poppler or Tesseract, install those utilities and restart the agent.")
                return

            status.write("Displaying extracted YAML artifacts...")
            with extraction_container.container():
                st.markdown("### Live Extraction Output")
                contract_col, invoice_col = st.columns(2)
                with contract_col:
                    st.markdown("##### Contract Summary")
                    st.code(result["contract_summary_yaml"], language="yaml")
                with invoice_col:
                    st.markdown("##### Invoice Summary")
                    st.code(result["invoice_summary_yaml"], language="yaml")

            status.write("Comparing contract vs invoice with SAP GenAI...")
            st.toast("Consulting SAP BTP AI Core", icon="🤖")
            try:
                analysis = service.run_analysis(
                    contract_summary_yaml=result["contract_summary_yaml"],
                    invoice_summary_yaml=result["invoice_summary_yaml"],
                    run_id=run_id,
                )
            except Exception as exc:
                logger.exception("LLM analysis failed for run %s", run_id)
                status.update(label="LLM analysis failed", state="error")
                st.error(f"Failed to run analysis: {exc}")
                return

            status.update(label="Agent mission complete", state="complete")
            st.toast("Mission complete", icon="✅")

        processing_seconds = time.time() - start_ts
        st.success(f"Run {run_id} finished in {format_duration(processing_seconds)}.")
        render_results(run_id, result, analysis, processing_seconds)


if __name__ == "__main__":
    main()
