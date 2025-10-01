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


def reset_session() -> None:
    keys = list(st.session_state.keys())
    for key in keys:
        del st.session_state[key]
    st.session_state["run_state"] = "ready"


def main() -> None:
    st.set_page_config(page_title="SAP Contract Invoice Reviewer Agent", layout="centered")
    st.title("SAP BTP Agent")
    st.title("Contract-Invoice Reviewer 🕵️📑")

    st.markdown(
        "Upload the executed contract PDF and the corresponding invoice spreadsheet. "
        "A SAP BTP AI Core-powered agent will check each invoice line item against the contract clauses and summarise the compliance results."
    )

    if "run_state" not in st.session_state:
        st.session_state["run_state"] = "ready"

    state = st.session_state["run_state"]

    if state == "ready":
        with st.form("upload_form"):
            pdf_file = st.file_uploader("Contract PDF", type=["pdf"], help="Provide the signed contract in PDF format.")
            invoice_file = st.file_uploader(
                "Invoice spreadsheet",
                type=["xlsx", "xls"],
                help="Provide the invoice with the line items to review.",
            )
            submitted = st.form_submit_button("Start review")

        if submitted:
            if pdf_file is None or invoice_file is None:
                st.warning("Please upload both the contract PDF and the invoice spreadsheet before starting the review.")
            else:
                st.session_state["pdf_bytes"] = pdf_file.getvalue()
                st.session_state["pdf_name"] = pdf_file.name or "contract.pdf"
                st.session_state["invoice_bytes"] = invoice_file.getvalue()
                st.session_state["invoice_name"] = invoice_file.name or "invoice.xlsx"
                st.session_state["processing_started"] = time.time()
                st.session_state["run_state"] = "processing"
                st.rerun()
        return

    if state == "processing":
        with st.status("Review in progress", expanded=True) as status:
            try:
                status.write("Saving uploaded documents…")
                run_id = service.storage.create_run_id()
                contract_path = service.storage.save_raw_file(
                    run_id,
                    st.session_state.get("pdf_name", f"contract_{run_id}.pdf"),
                    st.session_state.get("pdf_bytes", b""),
                )
                invoice_path = service.storage.save_raw_file(
                    run_id,
                    st.session_state.get("invoice_name", f"invoice_{run_id}.xlsx"),
                    st.session_state.get("invoice_bytes", b""),
                )

                status.write("Extracting contract clauses and invoice line items…")
                result = service.process_documents(
                    pdf_path=contract_path,
                    excel_path=invoice_path,
                    run_id=run_id,
                )

                status.write("Running compliance analysis with SAP BTP AI Core…")
                analysis = service.run_analysis(
                    contract_summary_yaml=result["contract_summary_yaml"],
                    invoice_summary_yaml=result["invoice_summary_yaml"],
                    run_id=run_id,
                )

                processing_seconds = time.time() - st.session_state.get("processing_started", time.time())
                st.session_state["result_bundle"] = {
                    "run_id": run_id,
                    "result": result,
                    "analysis": analysis,
                    "processing_seconds": processing_seconds,
                }
                st.session_state["run_state"] = "done"
                status.update(label="Review complete", state="complete")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Review failed")
                st.session_state["error_message"] = str(exc)
                st.session_state["run_state"] = "error"
                status.update(label="Review failed", state="error")
            finally:
                st.session_state.pop("pdf_bytes", None)
                st.session_state.pop("pdf_name", None)
                st.session_state.pop("invoice_bytes", None)
                st.session_state.pop("invoice_name", None)
        st.rerun()
        return

    if state == "error":
        st.error(f"The review failed: {st.session_state.get('error_message', 'Unknown error')}")
        if st.button("Try again"):
            reset_session()
            st.rerun()
        return

    if state == "done":
        bundle: Dict[str, Any] = st.session_state.get("result_bundle", {})
        run_id = bundle.get("run_id")
        result = bundle.get("result", {})
        analysis = bundle.get("analysis", {})
        processing_seconds = bundle.get("processing_seconds", 0.0)

        st.success(f"Review complete for run {run_id} in {format_duration(processing_seconds)}.")

        st.subheader("Compliance overview")
        st.markdown(analysis.get("comment_md", "No output."))

        with st.expander("Contract summary (YAML)"):
            st.code(result.get("contract_summary_yaml", ""), language="yaml")
            st.caption(f"Stored at {result.get('contract_summary_path')}")

        with st.expander("Invoice summary with line items (YAML)"):
            st.code(result.get("invoice_summary_yaml", ""), language="yaml")
            st.caption(f"Stored at {result.get('invoice_summary_path')}")

        with st.expander("Full raw outputs"):
            st.code(result.get("contract_yaml", ""), language="yaml")
            st.code(result.get("invoice_yaml", ""), language="yaml")
            st.code(analysis.get("comment_md", ""), language="markdown")

        time_saved = max(0.0, 7200 - processing_seconds)
        st.info(
            f"SAP BTP AI Core processing time: {format_duration(processing_seconds)}. "
            f"Estimated manual effort saved: {format_duration(time_saved)}."
        )

        if st.button("Review another contract"):
            reset_session()
            st.rerun()
        return


if __name__ == "__main__":
    main()
