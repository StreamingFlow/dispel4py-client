import json
import re
import ollama

from laminar.screen_printer import print_warning


class OllamaConnector:

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.client = ollama.Client(host=self.host)
        self.default_model = "llama3"

    def ask(self,
            prompt: str = None,
            system_queries: list[str] = None) -> dict[
        str, str | dict[str, str]]:

        print_warning(f"Using {self.default_model} from Ollama ({self.host}) for description generation...")

        messages = []

        if system_queries:
            for ctx in system_queries:
                messages.append({"role": "system", "content": ctx})

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat(
            model=self.default_model,
            messages=messages,
            options={
                "temperature": 0.0
            }
        )

        txt = response["message"]["content"].strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()

        parsed = json.loads(txt)
        parsed["model"] = self.default_model
        parsed["provider"] = "Ollama"
        parsed["host"] = self.host

        return parsed
