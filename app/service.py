from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Optional

import yaml

from .document_processing.excel_parser import parse_excel
from .document_processing.pdf_parser import parse_pdf
from .llm.openai_client import OpenAIChatClient
from .utils.config import settings
from .utils.storage import StorageManager


logger = logging.getLogger(__name__)


class ContractAgentService:
    def __init__(self) -> None:
        self.storage = StorageManager(settings.data_storage_path, settings.artefact_storage_path)
        logger.info("Storage ready data=%s artefacts=%s", settings.data_storage_path, settings.artefact_storage_path)
        self.llm_client = OpenAIChatClient(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model,
            request_timeout=settings.request_timeout,
        )

    def process_documents(
        self,
        *,
        pdf_path: Path,
        excel_path: Path,
        run_id: Optional[str] = None,
    ) -> Dict[str, str]:
        run_identifier = run_id or self.storage.create_run_id()

        pdf_payload = parse_pdf(pdf_path)
        excel_payload = parse_excel(excel_path)

        logger.debug("PDF payload sample: %s", str(list(pdf_payload.keys()))[:200])
        logger.debug("Excel sheets: %s", list(excel_payload.get("sheets", {}).keys()))

        contract_yaml_text = yaml.safe_dump(pdf_payload, sort_keys=False, allow_unicode=False)
        invoice_yaml_text = yaml.safe_dump(excel_payload, sort_keys=False, allow_unicode=False)

        contract_yaml_path = self.storage.save_yaml(run_identifier, "contract_raw", pdf_payload)
        invoice_yaml_path = self.storage.save_yaml(run_identifier, "invoice_raw", excel_payload)

        logger.info("Persisted raw YAML for run %s", run_identifier)

        return {
            "run_id": run_identifier,
            "contract_yaml": contract_yaml_text,
            "invoice_yaml": invoice_yaml_text,
            "contract_yaml_path": str(contract_yaml_path),
            "invoice_yaml_path": str(invoice_yaml_path),
        }

    # ----------------------- LLM helpers -----------------------

    def clean_contract_yaml(self, run_id: str, contract_yaml: str) -> Dict[str, str]:
        prompt = (
            "You are preparing contract data for automated reasoning.\n"
            "Clean the YAML below by removing irrelevant fields, grouping related clauses, and ensuring consistent keys.\n"
            "Return well-formatted YAML with top-level keys: metadata, obligations, pricing, service_levels, termination, other_clauses."
        )
        cleaned = self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You transform noisy contract extracts into clean YAML."},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nOriginal YAML:\n```yaml\n{contract_yaml}\n```",
                },
            ],
            temperature=0.1,
            max_completion_tokens=1400,
        )
        path = self.storage.save_text(run_id, "contract_clean", cleaned, suffix=".yaml")
        return {"content": cleaned, "path": str(path)}

    def clean_invoice_yaml(self, run_id: str, invoice_yaml: str) -> Dict[str, str]:
        prompt = (
            "You are preparing invoice data for compliance checks.\n"
            "From the YAML below extract a list named line_items where each item captures: sheet, line_number, terminal, movement_type, container_number, size, type, operator, quantity, amount, currency, description.\n"
            "Infer reasonable defaults when fields are missing. Return YAML with keys: summary, line_items, notes."
        )
        cleaned = self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You normalise invoice spreadsheets into comparable YAML."},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nOriginal YAML:\n```yaml\n{invoice_yaml}\n```",
                },
            ],
            temperature=0.15,
            max_completion_tokens=1600,
        )
        path = self.storage.save_text(run_id, "invoice_clean", cleaned, suffix=".yaml")
        return {"content": cleaned, "path": str(path)}

    def generate_compliance_report(
        self,
        run_id: str,
        *,
        contract_yaml: str,
        invoice_yaml: str,
        extra_instructions: Optional[str] = None,
    ) -> Dict[str, str]:
        base_prompt = (
            "You are GPT-5 running within SAP. Produce a contract vs invoice compliance assessment.\n"
            "Use the cleaned contract YAML and invoice line_items to determine status for each row.\n"
            "Return markdown with sections: Compliance Overview, Line Item Review (table with Sheet, Line, Invoice Details, Contract Alignment, Status, Confidence), Risks & Follow-up, Suggested Next Actions."
        )
        if extra_instructions and extra_instructions.strip():
            base_prompt = f"{base_prompt}\n\nAdditional reviewer instructions:\n{extra_instructions.strip()}"

        response = self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You are a senior SAP contract compliance reviewer."},
                {
                    "role": "user",
                    "content": (
                        f"{base_prompt}\n\nClean contract YAML:\n```yaml\n{contract_yaml}\n```\n"
                        f"Clean invoice YAML:\n```yaml\n{invoice_yaml}\n```"
                    ),
                },
            ],
            temperature=0.15,
            max_completion_tokens=1800,
        )
        path = self.storage.save_markdown(run_id, "compliance_report", response)
        return {"content": response, "path": str(path)}

    def generate_contract_review(self, run_id: str, contract_yaml: str) -> Dict[str, str]:
        prompt = (
            "Summarise the contract's critical obligations, pricing mechanics, service levels, and termination clauses."
            " Highlight potential risk areas and recommended controls in markdown."
        )
        response = self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You prepare executive contract briefings."},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nClean contract YAML:\n```yaml\n{contract_yaml}\n```",
                },
            ],
            temperature=0.2,
            max_completion_tokens=1200,
        )
        path = self.storage.save_markdown(run_id, "contract_review", response)
        return {"content": response, "path": str(path)}

    def generate_translation(self, run_id: str, contract_yaml: str) -> Dict[str, str]:
        prompt = (
            "Provide a Spanish translation of the key contract obligations and pricing terms."
            " Present the result in markdown with sections mirrored to the source structure."
        )
        response = self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You translate contract summaries accurately while preserving terminology."},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nClean contract YAML:\n```yaml\n{contract_yaml}\n```",
                },
            ],
            temperature=0.1,
            max_completion_tokens=1200,
        )
        path = self.storage.save_markdown(run_id, "contract_translation_es", response)
        return {"content": response, "path": str(path)}


def get_service() -> ContractAgentService:
    return ContractAgentService()
