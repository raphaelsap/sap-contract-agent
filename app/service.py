from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import logging
import yaml

from .document_processing.excel_parser import parse_excel
from .document_processing.pdf_parser import parse_pdf
from .llm.aicore_client import SAPAICoreClient
from .llm.workflow import build_workflow
from .utils.config import settings
from .utils.storage import StorageManager


logger = logging.getLogger(__name__)


def _contract_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    elements = payload.get("elements", [])
    preview: list[str] = []
    for element in elements:
        text = (element or {}).get("text", "").strip()
        if text:
            preview.append(text)
        if len(preview) == 5:
            break
    return {
        "source_file": payload.get("source_file"),
        "segment_count": payload.get("element_count", 0),
        "preview_text": preview,
    }


def _invoice_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    sheets = payload.get("sheets", {})
    summary_sheets = []
    for name, data in sheets.items():
        sheet_summary = {
            "sheet": name,
            "row_count": data.get("row_count", 0),
            "columns": (data.get("columns") or [])[:8],
            "sample_row": (data.get("rows") or [{}])[0],
        }
        summary_sheets.append(sheet_summary)
        if len(summary_sheets) == 5:
            break
    return {
        "source_file": payload.get("source_file"),
        "sheet_count": len(sheets),
        "summaries": summary_sheets,
    }


class ContractAgentService:
    def __init__(self) -> None:
        self.storage = StorageManager(settings.data_storage_path, settings.artefact_storage_path)
        logger.info("Storage ready data=%s artefacts=%s", settings.data_storage_path, settings.artefact_storage_path)
        self.llm_client = SAPAICoreClient(
            client_id=settings.sap_aicore_client_id,
            client_secret=settings.sap_aicore_client_secret,
            auth_url=settings.sap_aicore_auth_url,
            api_base=settings.sap_aicore_api_base,
            deployment_id=settings.sap_aicore_deployment_id,
            resource_group=settings.sap_aicore_resource_group,
            scope=settings.sap_aicore_scope,
            chat_completions_path=settings.chat_completions_path,
            request_timeout=settings.request_timeout,
        )
        self.workflow = build_workflow(self.llm_client)

    def process_documents(
        self,
        *,
        pdf_path: Path,
        excel_path: Path,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_identifier = run_id or self.storage.create_run_id()

        pdf_payload = parse_pdf(pdf_path)
        excel_payload = parse_excel(excel_path)

        logger.debug("PDF payload sample: %s", str(list(pdf_payload.keys()))[:200])
        logger.debug("Excel sheets: %s", list(excel_payload.get("sheets", {}).keys()))

        contract_summary = _contract_summary(pdf_payload)
        invoice_summary = _invoice_summary(excel_payload)

        pdf_yaml_text = yaml.safe_dump(pdf_payload, sort_keys=False, allow_unicode=False)
        excel_yaml_text = yaml.safe_dump(excel_payload, sort_keys=False, allow_unicode=False)
        contract_summary_yaml = yaml.safe_dump(contract_summary, sort_keys=False, allow_unicode=False)
        invoice_summary_yaml = yaml.safe_dump(invoice_summary, sort_keys=False, allow_unicode=False)

        pdf_yaml_path = self.storage.save_yaml(run_identifier, "contract", pdf_payload)
        excel_yaml_path = self.storage.save_yaml(run_identifier, "invoice", excel_payload)
        contract_summary_path = self.storage.save_yaml(run_identifier, "contract_summary", contract_summary)
        invoice_summary_path = self.storage.save_yaml(run_identifier, "invoice_summary", invoice_summary)

        logger.info("Persisted structured outputs for run %s", run_identifier)

        return {
            "run_id": run_identifier,
            "contract_yaml": pdf_yaml_text,
            "invoice_yaml": excel_yaml_text,
            "contract_summary_yaml": contract_summary_yaml,
            "invoice_summary_yaml": invoice_summary_yaml,
            "contract_yaml_path": str(pdf_yaml_path),
            "invoice_yaml_path": str(excel_yaml_path),
            "contract_summary_path": str(contract_summary_path),
            "invoice_summary_path": str(invoice_summary_path),
        }

    def run_analysis(
        self,
        *,
        contract_summary_yaml: str,
        invoice_summary_yaml: Optional[str],
        run_id: str,
    ) -> Dict[str, str]:
        logger.info("Invoking workflow for run %s", run_id)
        state = self.workflow.invoke({
            "contract_summary": contract_summary_yaml,
            "invoice_summary": invoice_summary_yaml or "",
        })

        logger.debug("Workflow response keys: %s", list(state.keys()))

        comment_md = state.get("comment_md", "")
        comment_path = self.storage.save_markdown(run_id, "comment", comment_md)

        return {
            "comment_md": comment_md,
            "comment_path": str(comment_path),
        }


def get_service() -> ContractAgentService:
    return ContractAgentService()
