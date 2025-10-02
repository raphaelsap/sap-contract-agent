from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .document_processing.excel_parser import parse_excel
from .document_processing.pdf_parser import parse_pdf
from .llm.openai_client import OpenAIChatClient
from .utils.config import settings
from .utils.storage import StorageManager

logger = logging.getLogger(__name__)


class ContractAgentService:
    def _parse_document(self, path: Path, *, label: str) -> Dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix in {'.pdf'}:
            payload = parse_pdf(path)
        elif suffix in {'.xlsx', '.xls'}:
            payload = parse_excel(path)
        else:
            raise ValueError(f"Unsupported {label} file type: {suffix or 'unknown'}")
        if not payload:
            payload = {'notice': f'{label} document returned empty payload'}
        payload.setdefault('source_file', path.name)
        payload.setdefault('document_type', suffix.lstrip('.'))
        return payload

    def __init__(self) -> None:
        self.storage = StorageManager(settings.data_storage_path, settings.artefact_storage_path)
        self.llm_client = OpenAIChatClient(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model,
            request_timeout=settings.request_timeout,
        )
        logger.info("Storage initialised data=%s artefacts=%s", settings.data_storage_path, settings.artefact_storage_path)

    # ---------------------------- ingestion ----------------------------

    def process_documents(
        self,
        *,
        contract_path: Path,
        invoice_path: Path,
        run_id: Optional[str] = None,
    ) -> Dict[str, str]:
        run_identifier = run_id or self.storage.create_run_id()

        contract_payload = self._parse_document(contract_path, label="contract")
        invoice_payload = self._parse_document(invoice_path, label="invoice")

        contract_yaml_text = yaml.safe_dump(contract_payload, sort_keys=False, allow_unicode=False)
        invoice_yaml_text = yaml.safe_dump(invoice_payload, sort_keys=False, allow_unicode=False)

        self._assert_yaml_not_empty("contract", contract_yaml_text)
        self._assert_yaml_not_empty("invoice", invoice_yaml_text)

        contract_yaml_path = self.storage.save_yaml(run_identifier, "contract_raw", contract_payload)
        invoice_yaml_path = self.storage.save_yaml(run_identifier, "invoice_raw", invoice_payload)

        logger.info("Parsed documents saved for run %s", run_identifier)

        return {
            "run_id": run_identifier,
            "contract_yaml": contract_yaml_text,
            "invoice_yaml": invoice_yaml_text,
            "contract_yaml_path": str(contract_yaml_path),
            "invoice_yaml_path": str(invoice_yaml_path),
        }

    # ---------------------------- LLM calls ----------------------------

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
            "Contract YAML may contain either PDF page text under `elements` or structured spreadsheet data under `sheets`.\n"
            "Invoice YAML follows the same pattern. Infer line items and monetary values even when only raw text is available.\n"
            "Return markdown with sections: Compliance Overview, Line Item Review (table with Sheet, Line, Invoice Details, Contract Alignment, Status, Confidence), Risks & Follow-up, Suggested Next Actions.\n"
            "If information is sparse, provide best-effort analysis rather than returning empty sections."
        )
        if extra_instructions and extra_instructions.strip():
            base_prompt = f"{base_prompt}\n\nAdditional reviewer instructions:\n{extra_instructions.strip()}"

        response = self._chat_with_fallback(
            messages=[
                {"role": "system", "content": "You are a senior SAP contract compliance reviewer."},
                {
                    "role": "user",
                    "content": (
                        f"{base_prompt}\n\nContract YAML:\n```yaml\n{contract_yaml}\n```\n"
                        f"Invoice YAML:\n```yaml\n{invoice_yaml}\n```"
                    ),
                },
            ],
            max_completion_tokens=1800,
            insist_message="Your previous draft was empty or unclear. Produce a detailed analysis with tables, bullets, and actionable follow-up suggestions.",
        )
        path = self.storage.save_markdown(run_id, "compliance_report", response)
        return {"content": response, "path": str(path)}

    def generate_contract_review(
        self,
        run_id: str,
        *,
        contract_yaml: str,
        extra_instructions: Optional[str] = None,
    ) -> Dict[str, str]:
        prompt = (
            "Summarise the contract's critical obligations, pricing mechanics, service levels, and termination clauses.\n"
            "Contract YAML may expose `elements` (for PDFs) or `sheets` (for spreadsheets); use whichever data is available.\n"
            "Highlight potential risk areas and recommended controls in markdown with bullet points."
        )
        if extra_instructions and extra_instructions.strip():
            prompt = f"{prompt}\n\nAdditional reviewer guidance:\n{extra_instructions.strip()}"

        response = self._chat_with_fallback(
            messages=[
                {"role": "system", "content": "You prepare executive contract briefings."},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nContract YAML:\n```yaml\n{contract_yaml}\n```",
                },
            ],
            max_completion_tokens=1200,
            insist_message="Provide at least five concrete observations covering obligations, pricing, service levels, risks, and recommended controls.",
        )
        path = self.storage.save_markdown(run_id, "contract_review", response)
        return {"content": response, "path": str(path)}

    # ---------------------------- helpers ----------------------------

    def _assert_yaml_not_empty(self, label: str, yaml_text: str) -> None:
        try:
            data = yaml.safe_load(yaml_text) if yaml_text and yaml_text.strip() else None
        except yaml.YAMLError:
            logger.warning("Unable to parse %s YAML for validation", label)
            return
        if not data:
            raise ValueError(
                f"The {label} data appears empty after parsing. Please upload a richer {label} document or verify the file contents."
            )

    def _chat_with_fallback(
        self,
        *,
        messages: List[Dict[str, str]],
        max_completion_tokens: int,
        insist_message: str,
    ) -> str:
        attempt_messages = list(messages)
        for attempt in range(2):
            response = self.llm_client.chat_completion(
                attempt_messages,
                max_completion_tokens=max_completion_tokens,
            )
            if self._looks_meaningful(response):
                return response
            attempt_messages = attempt_messages + [
                {"role": "system", "content": insist_message}
            ]
        return response

    @staticmethod
    def _looks_meaningful(text: str) -> bool:
        if not text:
            return False
        simplified = text.strip().lower()
        if simplified in {"", "{}", "[]", "null", "none"}:
            return False
        alnum_count = sum(ch.isalnum() for ch in simplified)
        return alnum_count >= 30


def get_service() -> ContractAgentService:
    return ContractAgentService()
