from __future__ import annotations

from typing import Dict, TypedDict

from langgraph.graph import END, StateGraph

from .aicore_client import SAPAICoreClient


class ContractAgentState(TypedDict, total=False):
    contract_summary: str
    invoice_summary: str
    comment_md: str


def build_workflow(client: SAPAICoreClient):
    graph = StateGraph(ContractAgentState)

    def comment_node(state: ContractAgentState) -> Dict[str, str]:
        contract_summary = state.get("contract_summary", "")
        invoice_summary = state.get("invoice_summary", "")
        user_prompt = (
            "You are an SAP contract reviewer.\n"
            "Given the YAML summaries below, draft a concise professional comment highlighting key obligations,"
            " potential risks, and items worth attention.\n"
            "Return markdown with sections: Key Points, Observations, Recommendations.\n"
            "If invoice details are provided, reference them only when relevant.\n"
            "Contract summary:\n```yaml\n"
            f"{contract_summary}\n"
            "```\n"
        )
        if invoice_summary:
            user_prompt += "Invoice summary:\n```yaml\n" + invoice_summary + "\n```\n"
        response = client.chat_completion(
            [
                {"role": "system", "content": "You are a diligent SAP contract analyst."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        return {"comment_md": response}

    graph.add_node("comment", comment_node)
    graph.set_entry_point("comment")
    graph.add_edge("comment", END)

    return graph.compile()
