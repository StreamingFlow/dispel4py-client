import json

from laminar.llms.queries_templates import (
    REQUEST_NEW_WORKFLOW_CONTEXT_QUERIES,
    REQUEST_DESCRIPTION_CONTEXT_QUERIES,
    EVALUATE_QUALITY_REQUESTED_WORKFLOW_CONTEXT_QUERIES,
)


def _bullets(items: list) -> str:
    """One clean bullet per requirement; strips the stray indentation that
    triple-quoted template entries carry."""
    return "\n".join(f"- {str(item).strip()}" for item in items)


def describe_prompt(component_name: str, kind: str, code: str) -> str:
    return (
        "You are documenting dispel4py components for semantic search and retrieval.\n"
        f"Component name: {component_name}\n"
        f"Component type: {kind}\n\n"
        "Write a short, structured description that:\n"
        f"{_bullets(REQUEST_DESCRIPTION_CONTEXT_QUERIES)}\n\n"
        f"CODE:\n{code}"
    )


def rerank_prompt(query: str, compact_candidates: list, top_k: int) -> str:
    schema = ('{"results":[{"type":"pe"|"workflow","id":0,"name":"...",'
              '"score":0.0,"why":"...","what_it_does":"..."}]}')
    return (
        f"User query:\n{query}\n\n"
        f"Rerank and pick the best {top_k} results.\n"
        "Use metadata and signals as hints, but prefer correctness.\n\n"
        f"Return JSON:\n{schema}\n\n"
        f"CANDIDATES:\n{json.dumps(compact_candidates, ensure_ascii=False)}"
    )


def compose_prompt(query: str, pe_compact: list) -> str:
    return (
        f"HARD REQUIREMENTS:\n{_bullets(REQUEST_NEW_WORKFLOW_CONTEXT_QUERIES)}\n"
        f"USER QUERY:\n{query}\n"
        f"AVAILABLE PES:\n{json.dumps(pe_compact, ensure_ascii=False)}"
    ).strip()


def evaluate_prompt(query: str, proposal: dict) -> str:
    return (
        f"EVALUATION INSTRUCTIONS:\n{_bullets(EVALUATE_QUALITY_REQUESTED_WORKFLOW_CONTEXT_QUERIES)}\n"
        f"USER QUERY:\n{query}\n"
        f"PROPOSED WORKFLOW (JSON):\n{json.dumps(proposal, ensure_ascii=False)}"
    ).strip()


def fix_prompt(issues: list, original_request: str, proposal: dict) -> str:
    return (
        "Your dispel4py workflow proposal has issues that must be fixed.\n\n"
        f"ISSUES TO FIX:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"ORIGINAL REQUEST (requirements, user query, available PEs):\n{original_request}\n\n"
        "Keep the skeleton intact: do NOT implement business logic and do NOT remove "
        "any raise NotImplementedError(...) placeholder or the unreachable "
        "write/return statements. Only fix the reported issues.\n\n"
        "Return the corrected proposal in the same JSON format as before:\n"
        f"{json.dumps(proposal, ensure_ascii=False)}"
    )


def new_component_prompt(query: str) -> str:
    schema = '{"type":"pe"|"workflow","name":"...","description":"...","code":"..."}'
    return (
        f"User request:\n{query}\n\n"
        "No good match exists.\n\n"
        "Propose ONE new component (PE or workflow).\n"
        f"Return JSON: {schema}\n"
        "Rules:\n"
        "- If workflow: provide WorkflowGraph code.\n"
        "- If pe: provide a dispel4py PE class."
    )


def classify_prompt(query: str) -> str:
    schema = '{"kind":"pe"|"workflow"|"either","input_type":"text"|"code"}'
    return (
        "Classify the user's intent for searching a small dispel4py library.\n\n"
        f"Return JSON:\n{schema}\n\n"
        f"User input:\n{query}"
    )