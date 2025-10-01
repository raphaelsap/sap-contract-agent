from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import logging
import yaml

from .document_processing.excel_parser import parse_excel
from .document_processing.pdf_parser import parse_pdf
from .llm.aicore_client import SAPAICoreClient
from .llm.workflow import build_workflow
from .utils.config import settings
from .utils.storage import StorageManager


logger = logging.getLogger(__name__)


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
    ) -> Dict[str, Dict[str, str]]:
        run_identifier = run_id or self.storage.create_run_id()

        pdf_payload = parse_pdf(pdf_path)
        excel_payload = parse_excel(excel_path)

        logger.debug("PDF payload sample: %%s", str(list(pdf_payload.keys()))[:200])
        logger.debug("Excel sheets: %%s", list(excel_payload.get("sheets", {}).keys()))

        pdf_yaml_text = yaml.safe_dump(pdf_payload, sort_keys=False, allow_unicode=False)
        excel_yaml_text = yaml.safe_dump(excel_payload, sort_keys=False, allow_unicode=False)

        pdf_yaml_path = self.storage.save_yaml(run_identifier, "contract", pdf_payload)
        excel_yaml_path = self.storage.save_yaml(run_identifier, "invoice", excel_payload)

        logger.info("Persisted structured outputs for run %%s", run_identifier)

        return {
            "run_id": run_identifier,
            "contract_yaml": pdf_yaml_text,
            "invoice_yaml": excel_yaml_text,
            "contract_yaml_path": str(pdf_yaml_path),
            "invoice_yaml_path": str(excel_yaml_path),
        }

    def run_analysis(self, contract_yaml: str, invoice_yaml: str, run_id: str) -> Dict[str, str]:
        logger.info("Invoking workflow for run %%s", run_id)
        state = self.workflow.invoke({
            "contract_yaml": contract_yaml,
            "invoice_yaml": invoice_yaml,
        })

        logger.debug("Workflow response keys: %%s", list(state.keys()))

        comparison_md = state.get("comparison_md", "")
        recommendation_md = state.get("recommendation_md", "")

        comparison_path = self.storage.save_markdown(run_id, "comparison", comparison_md)
        recommendation_path = self.storage.save_markdown(run_id, "recommendations", recommendation_md)

        return {
            "comparison_md": comparison_md,
            "recommendation_md": recommendation_md,
            "comparison_path": str(comparison_path),
            "recommendation_path": str(recommendation_path),
        }


def get_service() -> ContractAgentService:
    return ContractAgentService()
