from laminar.llms.connectors.GeminiConnector import GeminiConnector
from laminar.llms.connectors.OpenAIConnector import OpenAIConnector
from laminar.llms.connectors.OpenWebUI import OpenWebUIConnector
from laminar.screen_printer import print_warning, print_error
import json
from laminar.workflow_checker import is_valid_workflow_code
from laminar.llms.queries_templates import request_workflow_context_queries, request_description_queries


def safe_json_loads(s: str, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


class LLMConnector:

    def __init__(self):

        self.connectors = {}

        try:
            self.connectors["openai"] = OpenAIConnector()
        except RuntimeError:
            print_warning("Warn: unable to connect to OpenAI.")

        try:
            self.connectors["gemini"] = GeminiConnector()
        except RuntimeError:
            print_warning("Warn: unable to connect to Gemini.")

        try:
            self.connectors["openwebui"] = OpenWebUIConnector()
        except RuntimeError:
            print_warning("Warn: unable to connect to OpenWebUI.")

        if len(self.connectors) == 0:
            raise RuntimeError("No LLM connectors available.")

    def describe(self, component_name: str, kind: str, code: str, model: str = None, provider: str = "openai",
                 context_queries: list[str] = None) -> dict[str, str | list[str]]:

        if provider not in self.connectors.keys():
            raise RuntimeError(f"Unknown model {provider}")

        if kind not in ["pe", "workflow"]:
            raise RuntimeError(f"Unknown kind {kind}")

        description_query = (f"You are documenting dispel4py components for semantic search and retrieval."
                             f"\nComponent name: {component_name}\nComponent type: {kind}\n\
                             nWrite a short, structured description that:\n{'\n-'.join(request_description_queries)}"
                             f"\n\nCODE:\n{str(code)}")

        return self.connectors[provider].ask(model=model,
                                             prompt=description_query,
                                             system_queries=context_queries)

    def rerank(self, provider: str = "openai", model: str = None, query: str = None, candidates: list = None,
               top_k: int = 3) -> dict:

        compact = []
        for c in candidates:
            code_snip = (c.get("code") or "").strip().splitlines()
            code_snip = "\n".join(code_snip[:35])

            compact.append({
                "type": c["type"],
                "id": c["id"],
                "name": c["name"],
                "score": float(c["score"]),
                "signals": {"emb": c["emb"], "lex": c["lex"], "tag": c["tag"], "struct": c["struct"]},
                "tags": safe_json_loads(c.get("tags_json"), []),
                "workflow_pe_list": safe_json_loads(c.get("pe_list_json"), []) if c["type"] == "workflow" else None,
                "description": c.get("description") or "",
                "code_excerpt": code_snip
            })

        prompt = f"""
                   User query:
                   {query}

                   Rerank and pick the best {top_k} results.
                   Use metadata and signals as hints, but prefer correctness.

                   Return JSON:
                   {{"results":[{{"type": "pe"|"workflow", "id": 0, "name":"...", "score": 0.0, "why":"...", "what_it_does":"..."}}]}}

                   CANDIDATES:
                   {json.dumps(compact, ensure_ascii=False)}
                   """.strip()

        return self.connectors[provider].ask(model, prompt, ["Return JSON only. Do NOT explain."])

    def propose_workflow_composition(self, provider: str = "openai", model: str = None, query: str = None,
                                     pe_candidates: list = None, max_fixes: int = 2) -> dict:

        pe_compact = []
        for c in pe_candidates:
            pe_compact.append({
                "id": c["id"],
                "name": c["name"],
                "description": c.get("description") or "",
                "tags": safe_json_loads(c.get("tags_json"), []),
                "io": safe_json_loads(c.get("io_json"), {})
            })

        formatted_query = (f"HARD REQUIREMENTS:\n{'\n-'.join(request_workflow_context_queries)}\n"
                           f"USER QUERY: \n{query}\n"
                           f"AVAILABLE PES:\n{json.dumps(pe_compact, ensure_ascii=False)}").strip()

        proposal = self.connectors[provider].ask(model=model, prompt=formatted_query)
        issues = []
        for i in range(max_fixes + 1):
            ok, issues = is_valid_workflow_code(proposal.get("workflow_code", ""))
            if ok:
                return proposal
            print_warning(
                f"Warn: possible wrong code generated. Found {len(issues)} isssue(s). Trying to fix it...(retry {i + 1}/{max_fixes + 1})")
            fix_prompt = f"""
            Your workflow proposal has issues which must be fixed:
            Issues:
            {json.dumps(issues, ensure_ascii=False)}
            
            Original query:
            {formatted_query}
    
            Correct this original proposal accordingly:
            {json.dumps(proposal, ensure_ascii=False)}
            """.strip()
            proposal = self.connectors[provider].ask(model=model, prompt=formatted_query)

        if len(issues) > 0:
            print_error(
                "There were some issues that the LLM was not able to solve. Please review manually the generated code")
        return proposal

    def propose_new_component(self, provider: str = "openai", model: str = None, query: str = None) -> dict:
        prompt = f"""
            User request:
            {query}

            No good match exists.

            Propose ONE new component (PE or workflow).
            Return JSON: {{"type":"pe"|"workflow","name":"...","description":"...","code":"..."}}
            Rules:
            - If workflow: provide WorkflowGraph code.
            - If pe: provide a dispel4py PE class.
            """.strip()

        return self.connectors[provider].ask(model, prompt, [])

    def classify(self, provider: str = "openai", model: str = "gpt-4o", query: str = None) -> dict:
        prompt = f"""
            Classify the user's intent for searching a small dispel4py library.
    
            Return JSON:
            {{"kind": "pe" | "workflow" | "either", "input_type": "text" | "code" }}
    
            User input:
            {query}
            """.strip()

        return self.connectors[provider].ask(model, prompt, [])
