import os
import json
from google import genai
from google.genai import types

from laminar.screen_printer import print_warning


class GeminiConnector():
    def __init__(self, system_queries: list[str] = None):
        self.system_queries = system_queries
        self.key = os.environ["GEMINI_API_KEY"] if "GEMINI_API_KEY" in os.environ else None
        if self.key is None:
            raise RuntimeError("Gemini API key not set")

        self.client = genai.Client(api_key=self.key)
        self.default_model = "gemini-3-flash-preview"

    def describe(self, query: str, model: str = None, context_queries: list[str] = None) -> dict[
        str, str | dict[str, str]]:
        if model is None:
            model = self.default_model
        print_warning(f"Using {model} for description generation.")
        response = self.client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction="\n".join(context_queries)
            ),
            contents=query,
        )

        response = json.loads(response.text)
        response["description"] = f"(({model}@Gemini))-> " + response["description"]

        return response
