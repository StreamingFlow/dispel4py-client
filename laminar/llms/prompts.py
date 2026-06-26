import json

from laminar.llms.queries_templates import (
    REQUEST_NEW_WORKFLOW_CONTEXT_QUERIES,
    REQUEST_DESCRIPTION_CONTEXT_QUERIES,
    EVALUATE_QUALITY_REQUESTED_WORKFLOW_CONTEXT_QUERIES,
    PE_AUTHORING_RULES,
    NAME_WORKFLOW_QUERY
)


def _bullets(items: list) -> str:
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


def compose_prompt(query: str | None, pe_compact: list) -> str:
    return (
        f"HARD REQUIREMENTS:\n{_bullets(REQUEST_NEW_WORKFLOW_CONTEXT_QUERIES)}\n"
        f"USER QUERY:\n{query}\n"
        f"AVAILABLE PES:\n{json.dumps(pe_compact, ensure_ascii=False)}"
    ).strip()


def evaluate_prompt(query: str | None, proposal: dict) -> str:
    return (
        f"EVALUATION INSTRUCTIONS:\n{_bullets(EVALUATE_QUALITY_REQUESTED_WORKFLOW_CONTEXT_QUERIES)}\n"
        f"USER QUERY:\n{query}\n"
        f"PROPOSED WORKFLOW (JSON):\n{json.dumps(proposal, ensure_ascii=False)}"
    ).strip()


def fix_prompt(issues: list, original_request: str, proposal: dict) -> str:
    return (
        "Your dispel4py workflow proposal has issues that must be fixed.\n\n"
        f"ISSUES TO FIX:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"ORIGINAL REQUEST:\n{original_request}\n\n"
        "Return the corrected proposal in the same JSON format as before:\n"
        f"{json.dumps(proposal, ensure_ascii=False)}"
        f"Remember the HARD RULES: \n {_bullets(REQUEST_NEW_WORKFLOW_CONTEXT_QUERIES)}"
    )


def new_component_prompt(query: str | None) -> str:
    schema = '{"type":"pe"|"workflow","name":"...","description":"...","code":"..."}'
    return (
        f"User request:\n{query}\n\n"
        "No good match exists.\n\n"
        "Propose ONE new component (PE or workflow).\n"
        f"Return JSON: {schema}\n"
        f"HARD RULES: {_bullets(PE_AUTHORING_RULES)}"
    )


def classify_prompt(query: str | None) -> str:
    schema = '{"kind":"pe"|"workflow"|"either","input_type":"text"|"code"}'
    return (
        "Classify the user's intent for searching a small dispel4py library.\n\n"
        f"Return JSON:\n{schema}\n\n"
        f"User input:\n{query}"
    )


def give_name_prompt(source_code: str) -> str:
    return NAME_WORKFLOW_QUERY.format(code=source_code)