from __future__ import annotations

from typing import Dict, TypedDict

from langgraph.graph import END, StateGraph

from .aicore_client import SAPAICoreClient


class ContractAgentState(TypedDict, total=False):
    contract_yaml: str
    invoice_yaml: str
    comparison_md: str
    recommendation_md: str


def build_workflow(client: SAPAICoreClient) -> StateGraph:
    graph = StateGraph(ContractAgentState)

    def compare_node(state: ContractAgentState) -> Dict[str, str]:
        contract_yaml = state["contract_yaml"]
        invoice_yaml = state["invoice_yaml"]
        user_prompt = (
            "You are validating if invoiced line items align with the contract terms.\n"
            "Summarize alignment and highlight discrepancies.\n"
            "Return only markdown with sections: Summary, Alignments, Discrepancies.\n"
            "Contract YAML:\n```yaml\n"
            f"{contract_yaml}\n"
            "```\nInvoice YAML:\n```yaml\n"
            f"{invoice_yaml}\n"
            "```"
        )
        response = client.chat_completion(
            [
                {"role": "system", "content": "You compare contracts and invoices."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        return {"comparison_md": response}

    def suggestion_node(state: ContractAgentState) -> Dict[str, str]:
        comparison = state.get("comparison_md", "")
        user_prompt = (
            "Based on the comparison summary, propose concrete next actions.\n"
            "Return markdown with sections: Immediate Actions, Follow-Up Considerations.\n"
            "Comparison summary:\n"
            f"{comparison}"
        )
        response = client.chat_completion(
            [
                {
                    "role": "system",
                    "content": "You suggest practical next steps for contract invoice reviews.",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        return {"recommendation_md": response}

    graph.add_node("compare", compare_node)
    graph.add_node("suggest", suggestion_node)
    graph.set_entry_point("compare")
    graph.add_edge("compare", "suggest")
    graph.add_edge("suggest", END)

    return graph.compile()
