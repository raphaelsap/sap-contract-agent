from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import re
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
    clauses: list[Dict[str, Any]] = []
    for idx, element in enumerate(elements, start=1):
        item = element or {}
        text_value = (item.get("text") or "").strip()
        if text_value:
            clauses.append({
                "index": idx,
                "type": item.get("type"),
                "text": text_value[:1200],
                "metadata": {
                    "page_number": item.get("metadata", {}).get("page_number"),
                    "section": item.get("type"),
                },
            })
        if len(clauses) >= 40:
            break
    return {
        "source_file": payload.get("source_file"),
        "segment_count": payload.get("element_count", 0),
        "clauses": clauses,
    }




def _invoice_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    sheets = payload.get("sheets", {})
    sheet_overview: list[Dict[str, Any]] = []
    charge_items: list[Dict[str, Any]] = []
    metadata_items: list[Dict[str, Any]] = []

    amount_keywords = {"amount", "qty", "quantity", "total", "price", "fee", "charge", "rate", "cost", "value", "tax", "duty"}
    currency_symbols = {"$", "€", "£"}

    def clean_cell(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ""
            normalized = stripped.replace(',', '')
            for symbol in currency_symbols:
                normalized = normalized.replace(symbol, '')
            try:
                numeric = float(normalized)
                return int(numeric) if numeric.is_integer() else numeric
            except ValueError:
                return stripped
        return value

    def normalize_fields(row: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in row.items():
            cleaned = clean_cell(value)
            if cleaned in ("", None):
                continue
            key_name = str(key).strip() if key else "column"
            normalized[key_name] = cleaned
        return normalized

    def is_numeric(value: Any) -> bool:
        return isinstance(value, (int, float))

    def classify_row(row: Dict[str, Any]) -> str:
        normalized = normalize_fields(row)
        if not normalized:
            return "empty"
        numeric_values = [v for v in normalized.values() if is_numeric(v)]
        keyword_in_keys = any(
            any(keyword in key_lower for keyword in amount_keywords)
            for key_lower in (str(key).lower() for key in normalized.keys())
        )
        keyword_in_values = any(
            any(keyword in value_lower for keyword in amount_keywords)
            for value_lower in (str(value).lower() for value in normalized.values())
        )
        has_currency_symbol = any(
            any(symbol in str(value) for symbol in currency_symbols) for value in normalized.values()
        )

        if not numeric_values:
            return "metadata"
        if has_currency_symbol or keyword_in_keys or keyword_in_values or len(numeric_values) >= 2:
            return "charge"
        return "possible_charge"

    for name, data in sheets.items():
        rows = data.get("rows") or []
        sheet_overview.append({"sheet": name, "row_count": len(rows), "columns": data.get("columns", [])})
        for idx, row in enumerate(rows, start=1):
            category = classify_row(row)
            normalized_fields = normalize_fields(row)
            entry: Dict[str, Any] = {
                "sheet": name,
                "line_number": idx,
                "category": category,
                "fields": normalized_fields,
            }
            if normalized_fields:
                entry["compact"] = "; ".join(f"{key}: {value}" for key, value in normalized_fields.items())[:400]
            if category in {"charge", "possible_charge"}:
                entry["numeric_fields"] = {k: v for k, v in normalized_fields.items() if is_numeric(v)}
                charge_items.append(entry)
            elif category == "metadata":
                metadata_items.append({
                    "sheet": name,
                    "line_number": idx,
                    "text": entry.get("compact", ""),
                })

    max_charge_items = 160
    max_metadata_preview = 40
    charge_breakdown = {
        "charge": sum(1 for item in charge_items if item["category"] == "charge"),
        "possible_charge": sum(1 for item in charge_items if item["category"] == "possible_charge"),
    }

    return {
        "source_file": payload.get("source_file"),
        "sheet_count": len(sheets),
        "total_line_items": len(charge_items) + len(metadata_items),
        "charge_item_count": len(charge_items),
        "metadata_item_count": len(metadata_items),
        "charge_category_breakdown": charge_breakdown,
        "sheet_overview": sheet_overview,
        "charge_items": charge_items[:max_charge_items],
        "metadata_preview": metadata_items[:max_metadata_preview],
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
            api_version=settings.sap_aicore_api_version,
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
        logger.info("Invoking SAP BTP AI Core workflow for run %s", run_id)
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
