import openai
from laminar.llms.core import LLMConnector
import os
import re
import json


class OpenAIConnector(LLMConnector):

    def __init__(self, model: str, system_queries: list[str] = None):
        super().__init__()
        self.key = os.environ["OPENAI_API_KEY"] if "OPENAI_API_KEY" in os.environ else None
        if self.key is None:
            raise RuntimeError("OpenAI API key not set")

        self.client = openai.OpenAI(api_key=self.key)
        self.model = model
        self.system_queries = system_queries

    def describe(self, component_name: str, kind: str, code: str) -> dict[str, str | dict[str, str]]:
        if kind not in ["pe", "workflow"]:
            raise RuntimeError(f"Unknown kind {kind}")

        messages = [{"role": "system", "content": query} for query in self.system_queries]
        messages.append(
            {"role": "user",
             "content": super()._get_description_prompt(component_name=component_name, component_type=kind, code=code)})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.0
        )

        txt = response.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
        return json.loads(txt)
