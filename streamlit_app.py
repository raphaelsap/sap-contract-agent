from __future__ import annotations

from typing import Any, Dict
import logging
import time

import streamlit as st

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
    st.set_page_config(page_title="SAP Contract Invoice Reviewer", layout="centered")
    st.image("https://www.sap.com/dam/application/shared/logos/sap-logo-svg.svg", width=100)
    st.title("SAP Contract & Invoice Reviewer Agent")
    st.caption("LLM assisted analysis")

    st.markdown(
        "Upload the executed contract PDF and the corresponding invoice spreadsheet. "
        "This assistant normalises the data, uses GPT-5 via OpenAI to compare each invoice line against the contract, "
        "highlights potential risks, and provides a Spanish translation of the core obligations."
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
            prompt_override = st.text_area(
                "Optional reviewer instructions",
                value=st.session_state.get("prompt_override", ""),
                placeholder="e.g. Pay special attention to demurrage charges for terminal MICT.",
                help="Temporarily extend the GPT-5 reviewer prompt for this run only.",
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
                st.session_state["prompt_override"] = prompt_override.strip()
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

                status.write("Cleaning contract YAML…")
                contract_clean = service.clean_contract_yaml(run_id, result["contract_yaml"])

                status.write("Cleaning invoice YAML…")
                invoice_clean = service.clean_invoice_yaml(run_id, result["invoice_yaml"])

                status.write("Running GPT-5 compliance analysis…")
                compliance = service.generate_compliance_report(
                    run_id,
                    contract_yaml=contract_clean["content"],
                    invoice_yaml=invoice_clean["content"],
                    extra_instructions=st.session_state.get("prompt_override"),
                )

                status.write("Reviewing contract obligations…")
                contract_review = service.generate_contract_review(run_id, contract_clean["content"])

                status.write("Translating contract summary…")
                translation = service.generate_translation(run_id, contract_clean["content"])

                processing_seconds = time.time() - st.session_state.get("processing_started", time.time())
                st.session_state["result_bundle"] = {
                    "run_id": run_id,
                    "result": result,
                    "contract_clean": contract_clean,
                    "invoice_clean": invoice_clean,
                    "compliance": compliance,
                    "contract_review": contract_review,
                    "translation": translation,
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
        contract_clean = bundle.get("contract_clean", {})
        invoice_clean = bundle.get("invoice_clean", {})
        compliance = bundle.get("compliance", {})
        contract_review = bundle.get("contract_review", {})
        translation = bundle.get("translation", {})
        processing_seconds = bundle.get("processing_seconds", 0.0)

        st.success(f"Review complete for run {run_id} in {format_duration(processing_seconds)}.")

        st.subheader("Compliance overview")
        st.markdown(compliance.get("content", "No output."))

        if st.session_state.get("prompt_override"):
            with st.expander("Custom reviewer instructions"):
                st.markdown(st.session_state["prompt_override"])

        with st.expander("Cleaned contract YAML"):
            st.code(contract_clean.get("content", ""), language="yaml")
            if contract_clean.get("path"):
                st.caption(f"Stored at {contract_clean['path']}")

        with st.expander("Cleaned invoice YAML"):
            st.code(invoice_clean.get("content", ""), language="yaml")
            if invoice_clean.get("path"):
                st.caption(f"Stored at {invoice_clean['path']}")

        with st.expander("Contract risk review"):
            st.markdown(contract_review.get("content", ""))
            if contract_review.get("path"):
                st.caption(f"Stored at {contract_review['path']}")

        with st.expander("Contract summary translation (Spanish)"):
            st.markdown(translation.get("content", ""))
            if translation.get("path"):
                st.caption(f"Stored at {translation['path']}")

        with st.expander("Raw artefacts"):
            st.code(result.get("contract_yaml", ""), language="yaml")
            if result.get("contract_yaml_path"):
                st.caption(f"Raw contract YAML stored at {result['contract_yaml_path']}")
            st.code(result.get("invoice_yaml", ""), language="yaml")
            if result.get("invoice_yaml_path"):
                st.caption(f"Raw invoice YAML stored at {result['invoice_yaml_path']}")

        time_saved = max(0.0, 7200 - processing_seconds)
        st.info(
            f"GPT-5 processing time: {format_duration(processing_seconds)}. "
            f"Estimated manual effort saved: {format_duration(time_saved)}."
        )

        if st.button("Review another contract"):
            reset_session()
            st.rerun()
        return


if __name__ == "__main__":
    main()
