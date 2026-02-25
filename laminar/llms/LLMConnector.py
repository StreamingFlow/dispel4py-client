from laminar.llms.connectors.GeminiConnector import GeminiConnector
from laminar.llms.connectors.OpenAIConnector import OpenAIConnector
from laminar.llms.connectors.OpenWebUI import OpenWebUIConnector
from laminar.screen_printer import print_warning


class LLMConnector:

    def _get_description_prompt(self, component_name, component_type, code):
        return self.DESCRIPTION_PROMPT.format(component_name, component_type, code)

    def __init__(self):
        self.DESCRIPTION_PROMPT = """
You are documenting dispel4py components for semantic search and retrieval.

Component name: {}
Component type: {}

Write a short, structured description that:
- Explicitly states whether this is a Processing Element (PE) or a workflow.
- Clearly describes its role in a data-processing pipeline.
- Mentions expected inputs and outputs.
- Uses consistent technical vocabulary (e.g. filtering, transformation, signal processing, orchestration).
- Mentions important parameters or configuration options if obvious from the code.

The description should be suitable for:
- semantic similarity search
- explaining results to users

CODE:
{}
        """

        self.RERANK_PROMPT = """
        Return JSON only. Do not explain.
        """

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

        description_query = self._get_description_prompt(component_name, kind, str(code))

        return self.connectors[provider].describe(query=description_query,
                                                  model=model,
                                                  context_queries=context_queries)

    def rerank(self, provider: str = "openai", model: str = None, query: str = None, candidates: list = None,
               top_k: int = 3) -> dict:
        return self.connectors[provider].rerank(model, query, candidates, top_k, self.RERANK_PROMPT)

    def propose_workflow_composition(self, provider: str = "openai", model: str = None, query: str = None,
                                     pe_candidates: list = None, max_fixes: int = 2) -> dict:

        return self.connectors[provider].propose_workflow_composition(model, query, pe_candidates, max_fixes)

    def propose_new_component(self, provider: str = "openai", model: str = None, query: str = None) -> dict:
        return self.connectors[provider].propose(model, query)

    def classify(self, provider: str = "openai", model: str = "gpt-4o", query: str = None) -> dict:
        return self.connectors[provider].classify(model, query)
