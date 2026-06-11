import json

from laminar.llms.connectors.GeminiConnector import GeminiConnector
from laminar.llms.connectors.OpenAIConnector import OpenAIConnector
from laminar.llms.connectors.OpenWebUI import OpenWebUIConnector
from laminar.llms import prompts
from laminar.workflow_checker import is_valid_workflow_code
from laminar.screen_printer import print_warning, print_error


def safe_json_loads(s: str, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


# Provider name -> connector factory.
_CONNECTOR_FACTORIES = {
    "openai": OpenAIConnector,
    "gemini": GeminiConnector,
    "openwebui": OpenWebUIConnector,
}


class LLMConnector:

    def __init__(self):
        self.connectors = {}
        for name, factory in _CONNECTOR_FACTORIES.items():
            try:
                self.connectors[name] = factory()
            except RuntimeError:
                print_warning(f"Warn: unable to connect to {name}.")
        if not self.connectors:
            raise RuntimeError("No LLM connectors available.")

    def _ask(self, provider: str, prompt: str, system_queries: list = None) -> dict:
        if provider not in self.connectors:
            raise RuntimeError(f"Unknown provider {provider}")
        return self.connectors[provider].ask(
            prompt=prompt, system_queries=system_queries
        )

    def describe(self, component_name: str, kind: str, code: str,
                 provider: str = "openai", context_queries: list[str] = None) -> dict:
        if kind not in ("pe", "workflow"):
            raise RuntimeError(f"Unknown kind {kind}")
        prompt = prompts.describe_prompt(component_name, kind, code)
        return self._ask(provider, prompt, system_queries=context_queries)

    def rerank(self, provider: str = "openai", query: str = None,
               candidates: list = None, top_k: int = 3) -> dict:
        compact = [self._compact_candidate(c) for c in (candidates or [])]
        prompt = prompts.rerank_prompt(query, compact, top_k)
        return self._ask(provider, prompt,
                         system_queries=["Return JSON only. Do NOT explain."])

    def propose_workflow_composition(self, provider: str = "openai", query: str | None = None,
                                     pe_candidates: list | None = None, max_fixes: int = 2) -> dict:
        pe_compact = [self._compact_pe(c) for c in (pe_candidates or [])]
        original_request = prompts.compose_prompt(query, pe_compact)

        def collect_issues(prop: dict) -> list:
            """Merge static-validation issues with LLM-reported quality issues."""
            found = []
            ok, static_issues = is_valid_workflow_code(prop.get("workflow_code", ""))
            if not ok:
                found.extend(static_issues)
            review = self._ask(provider, prompts.evaluate_prompt(query, proposal))
            if isinstance(review, dict):
                found.extend(review.get("issues") or [])
            return found

        proposal = self._ask(provider, original_request)

        issues = []
        for attempt in range(max_fixes + 1):
            issues = collect_issues(proposal)
            if not issues:
                return proposal
            if attempt == max_fixes:
                break

            print_warning(f"Warn: possible wrong code generated. Found {len(issues)} issue(s):")
            for issue in issues:
                print_warning(f"\t • {issue}")

            print_warning(f"Trying to fix it... (retry {attempt + 1}/{max_fixes})\n")

            proposal = self._ask(provider, prompts.fix_prompt(issues, original_request, proposal))

        print_error(f"There were {len(issues)} issue(s) the LLM could not resolve after {max_fixes} fix attempt(s).",
                    _traceback=False)
        for issue in issues:
            print_error(f"\t • {issue}", _traceback=False)
        print_error("Please review the generated code manually.\n", _traceback=False)

        return proposal

    def propose_new_component(self, provider: str = "openai", query: str | None = None) -> dict:
        return self._ask(provider, prompts.new_component_prompt(query))

    def classify(self, provider: str = "openai", query: str | None = None) -> dict:
        return self._ask(provider, prompts.classify_prompt(query), system_queries=[])

    @staticmethod
    def _compact_pe(c: dict) -> dict:
        return {
            "id": c["id"],
            "name": c["name"],
            "description": c.get("description") or "",
            "tags": safe_json_loads(c.get("tags_json"), []),
            "io": safe_json_loads(c.get("io_json"), {}),
        }

    @staticmethod
    def _compact_candidate(c: dict) -> dict:
        code_excerpt = "\n".join((c.get("code") or "").strip().splitlines()[:35])
        return {
            "type": c["type"],
            "id": c["id"],
            "name": c["name"],
            "score": float(c["score"]),
            "signals": {"emb": c["emb"], "lex": c["lex"], "tag": c["tag"], "struct": c["struct"]},
            "tags": safe_json_loads(c.get("tags_json"), []),
            "workflow_pe_list": safe_json_loads(c.get("pe_list_json"), []) if c["type"] == "workflow" else None,
            "description": c.get("description") or "",
            "code_excerpt": code_excerpt,
        }
