import openai
import os
import re
import json

from laminar.screen_printer import print_warning


class OpenAIConnector():

    def __init__(self):
        self.key = os.environ["OPENAI_API_KEY"] if "OPENAI_API_KEY" in os.environ else None
        if self.key is None:
            raise RuntimeError("OpenAI API key not set")

        self.client = openai.OpenAI(api_key=self.key)
        self.default_model = "gpt-4o"

    def describe(self, query: str, model: str, context_queries: list[str] = None) -> dict[str, str | dict[str, str]]:
        if model is None:
            model = self.default_model

        print_warning(f"Using {model} for description generation.")
        messages = [{"role": "system", "content": query} for query in context_queries]
        messages.append({"role": "user", "content": query})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0
        )

        txt = response.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
        return json.loads(txt)
