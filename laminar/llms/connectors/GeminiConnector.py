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

    def ask(self,
            prompt: str = None,
            system_queries: list[str] = None) -> dict:
        print_warning(f"Using {self.default_model} from Gemini for description generation...")
        response = self.client.models.generate_content(
            model=self.default_model,
            config=types.GenerateContentConfig(
                system_instruction="\n".join(system_queries)
            ),
            contents=prompt,
        )

        response = json.loads(response.text)
        response["model"] = self.default_model
        response["provider"] = "Gemini"
        return response
