import json
import re
import ollama

from laminar.screen_printer import print_warning


class OllamaConnector:

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.client = ollama.Client(host=self.host)
        self.default_model = "llama3"

    def describe(self, query: str, model: str = None, context_queries: list[str] = None) -> dict[
        str, str | dict[str, str]]:

        if model is None:
            model = self.default_model

        print_warning(f"Using {model} from Ollama ({self.host}) for description generation...")

        messages = []

        if context_queries:
            for ctx in context_queries:
                messages.append({"role": "system", "content": ctx})

        messages.append({"role": "user", "content": query})

        response = self.client.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.0
            }
        )

        txt = response["message"]["content"].strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()

        parsed = json.loads(txt)
        parsed["model"] = model
        parsed["provider"] = "Ollama"
        parsed["host"] = self.host

        return parsed

    def rerank(self, query: str, candidates: list, top_k: int = 3, context_queries: list[str] = None):
        raise NotImplementedError

    def propose_workflow_composition(self, model: str = "gpt-4o", query: str = None, pe_candidates: list = None,
                                 max_fixes: int = 2) -> dict:
        raise NotImplementedError

    def classify(self, model: str = "gpt-4o", query: str = None) -> dict:
        return NotImplementedError

    def propose(self, model: str = "gpt-4o", query: str = None):
        raise NotImplementedError