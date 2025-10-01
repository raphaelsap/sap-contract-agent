from __future__ import annotations

from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph


class ContractAgentState(TypedDict, total=False):
    contract_summary: str
    invoice_summary: str
    comment_md: str


def build_workflow(client: Any):
    graph = StateGraph(ContractAgentState)

    def comment_node(state: ContractAgentState) -> Dict[str, str]:
        contract_summary = state.get("contract_summary", "")
        invoice_summary = state.get("invoice_summary", "")
        user_prompt = (
            "You are an SAP contract compliance analyst.\n"
            "Determine whether each invoice line item is consistent with the contract clauses.\n"
            "For every line item you must state one of: Compliant, Non-compliant, Needs review.\n"
            "Reference the contract clause numbers or text snippets that justify your decision.\n"
            "Return markdown with sections: Compliance Overview, Line Item Review, Risks & Follow-up.\n"
            "Each charge_items entry includes a 'category' flag (either 'charge' or 'possible_charge'); treat 'possible_charge' rows cautiously and mark them Needs review unless supported by the contract.\n"
            "Under Line Item Review, render a markdown table with columns: Sheet, Line, Invoice Details, Contract Alignment, Status, Confidence.\n"
            "If exact matches are unavailable, infer the most plausible contract condition and indicate it explicitly.\n"
            "If information is missing to decide, mark Status as 'Needs review' but still offer your best professional judgment.\n"
            "Contract summary:\n```yaml\n"
            f"{contract_summary}\n"
            "```\n"
        )
        if invoice_summary:
            user_prompt += "".join([
                "Invoice summary (with charge_items for billable rows and metadata_preview for contextual lines):\n```yaml\n",
                invoice_summary,
                "\n```\n",
                "Focus exclusively on charge_items when making compliance decisions. Use metadata_preview only when it clarifies context.\n",
                "If a contract clause cannot be found, hypothesize a reasonable clause based on similar terms in the contract summary.\n",
            ])
        response = client.chat_completion(
            [
                {"role": "system", "content": "You operate within SAP BTP AI Core as a meticulous contract compliance analyst who produces concise, structured reviews."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.15,
            max_tokens=1500,
        )
        return {"comment_md": response}

    graph.add_node("comment", comment_node)
    graph.set_entry_point("comment")
    graph.add_edge("comment", END)

    return graph.compile()
