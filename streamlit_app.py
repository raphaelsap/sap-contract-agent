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


def _looks_meaningful(text: str) -> bool:
    if not text:
        return False
    simplified = text.strip().lower()
    if simplified in {"", "{}", "[]", "null", "none"}:
        return False
    alnum_count = sum(ch.isalnum() for ch in simplified)
    return alnum_count >= 30


def reset_session() -> None:
    keys = list(st.session_state.keys())
    for key in keys:
        del st.session_state[key]
    st.session_state["run_state"] = "ready"


def main() -> None:
    st.set_page_config(page_title="SAP Contract Invoice Reviewer", layout="centered")
    svg_url = "https://www.sap.com/dam/application/shared/logos/sap-logo-svg.svg"

    st.markdown(
        f"""
        <style>
        .rounded-img {{
            border-radius: 0%;
            width: 100px;
            height: 100px;
            overflow: hidden;
            display: inline-block;
        }}
        .rounded-img img {{
            width: 100px;
            height: 100px;
            display: block;
        }}
        </style>
        <span class="rounded-img">
        <img src="{svg_url}" />
        </span>
        """,
        unsafe_allow_html=True
    )
    st.title("SAP BTP Agent - Contract & Invoice Reviewer")

    st.markdown(
        "Upload the executed contract PDF and the corresponding invoice spreadsheet. "
        "This assistant parses both documents, calls the SAP BTP AI Core to compare line items against contract clauses, and surfaces risks with actionable follow-up."
    )

    if "run_state" not in st.session_state:
        st.session_state["run_state"] = "ready"

    state = st.session_state["run_state"]

    if state == "ready":
        with st.form("upload_form"):
            contract_file = st.file_uploader("Contract document", type=["pdf", "xlsx", "xls"], help="Provide the contract in PDF or Excel format.")
            invoice_file = st.file_uploader(
                "Invoice document",
                type=["pdf", "xlsx", "xls"],
                help="Provide the invoice in PDF or Excel format.",
            )
            prompt_override = st.text_area(
                "Optional reviewer instructions",
                value=st.session_state.get("prompt_override", ""),
                placeholder="e.g. Pay special attention to demurrage charges for terminal MICT.",
                help="Temporarily extend the GPT-5 reviewer prompt for this run only.",
            )
            submitted = st.form_submit_button("Start review")

        if submitted:
            if contract_file is None or invoice_file is None:
                st.warning("Please upload both the contract and the invoice before starting the review.")
            else:
                st.session_state["contract_bytes"] = contract_file.getvalue()
                st.session_state["contract_name"] = contract_file.name or "contract.pdf"
                st.session_state["invoice_bytes"] = invoice_file.getvalue()
                st.session_state["invoice_name"] = invoice_file.name or "invoice.pdf"
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
                    st.session_state.get("contract_name", f"contract_{run_id}.pdf"),
                    st.session_state.get("contract_bytes", b""),
                )
                invoice_path = service.storage.save_raw_file(
                    run_id,
                    st.session_state.get("invoice_name", f"invoice_{run_id}.xlsx"),
                    st.session_state.get("invoice_bytes", b""),
                )

                status.write("Extracting contract clauses and invoice line items…")
                result = service.process_documents(
                    contract_path=contract_path,
                    invoice_path=invoice_path,
                    run_id=run_id,
                )

                status.write("Running GPT-5 compliance analysis…")
                compliance = service.generate_compliance_report(
                    run_id,
                    contract_yaml=result["contract_yaml"],
                    invoice_yaml=result["invoice_yaml"],
                    extra_instructions=st.session_state.get("prompt_override"),
                )

                status.write("Reviewing contract obligations…")
                contract_review = service.generate_contract_review(
                    run_id,
                    contract_yaml=result["contract_yaml"],
                    extra_instructions=st.session_state.get("prompt_override"),
                )

                processing_seconds = time.time() - st.session_state.get("processing_started", time.time())
                st.session_state["result_bundle"] = {
                    "run_id": run_id,
                    "result": result,
                    "compliance": compliance,
                    "contract_review": contract_review,
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
                st.session_state.pop("contract_bytes", None)
                st.session_state.pop("contract_name", None)
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
        compliance = bundle.get("compliance", {})
        contract_review = bundle.get("contract_review", {})
        processing_seconds = bundle.get("processing_seconds", 0.0)

        st.success(f"Review complete for run {run_id} in {format_duration(processing_seconds)}.")

        compliance_text = compliance.get("content", "")
        if not _looks_meaningful(compliance_text):
            st.warning("Compliance analysis looked empty. Re-running with stricter instructions…")
            compliance = service.generate_compliance_report(
                run_id,
                contract_yaml=result.get("contract_yaml", ""),
                invoice_yaml=result.get("invoice_yaml", ""),
                extra_instructions=(st.session_state.get("prompt_override") or "") + "\nEnsure the response contains a detailed table, bullet points, and explicit conclusions.",
            )
            compliance_text = compliance.get("content", "")
            bundle["compliance"] = compliance
            st.session_state["result_bundle"] = bundle

        st.subheader("Compliance overview")
        st.markdown(compliance_text or "No output.")

        if st.session_state.get("prompt_override"):
            with st.expander("Custom reviewer instructions"):
                st.markdown(st.session_state["prompt_override"])

        with st.expander("Contract YAML"):
            st.code(result.get("contract_yaml", ""), language="yaml")
            if result.get("contract_yaml_path"):
                st.caption(f"Stored at {result['contract_yaml_path']}")

        with st.expander("Invoice YAML"):
            st.code(result.get("invoice_yaml", ""), language="yaml")
            if result.get("invoice_yaml_path"):
                st.caption(f"Stored at {result['invoice_yaml_path']}")

        review_text = contract_review.get("content", "")
        if not _looks_meaningful(review_text):
            contract_review = service.generate_contract_review(
                run_id,
                contract_yaml=result.get("contract_yaml", ""),
                extra_instructions="Your previous summary was too light. Provide at least five concrete insights covering obligations, pricing, service levels, risks, and controls.",
            )
            review_text = contract_review.get("content", "")
            bundle["contract_review"] = contract_review
            st.session_state["result_bundle"] = bundle

        if _looks_meaningful(review_text):
            with st.expander("Contract risk review"):
                st.markdown(review_text)
                if contract_review.get("path"):
                    st.caption(f"Stored at {contract_review['path']}")

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
