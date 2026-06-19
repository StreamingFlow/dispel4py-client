import os
import json
import requests

from laminar.screen_printer import print_warning, print_text, print_error


class OpenWebUIConnector:

    def _get_available_models(self) -> dict:
        url = f"{self.base_url}/api/models"
        response = requests.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
        response.raise_for_status()
        return response.json()["data"][0]["id"]

    def __init__(
            self,
            system_queries: list[str] = None,
            base_url: str = None
    ):
        self.system_queries = system_queries or []
        self.base_url = base_url or os.environ.get("OPENWEBUI_BASE_URL", None)
        self.api_key = os.environ.get("OPENWEBUI_API_KEY", None)

        if not self.api_key or not self.base_url:
            raise RuntimeError("OPENWEBUI_API_KEY or OPENWEBUI_BASE_URL not set")

        self.default_model = self._get_available_models()
        self.endpoint = f"{self.base_url}/api/chat/completions"

    def ask(self,
            prompt: str | None = None,
            system_queries: list[str] = None) -> dict[
        str, str | dict[str, str]]:

        if system_queries is None:
            system_queries = []

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            "model": self.default_model,
            "messages": [{"role": "system", "content": f"{q}"} for q in self.system_queries] + [
                {"role": "system", "content": f"{q}"} for q in system_queries] + [
                            {"role": "user", "content": prompt, }]
        }

        try:
            response = requests.post(self.base_url + "/api/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]

            parsed = json.loads(content)
            parsed["model"] = self.default_model
            parsed["provider"] = "OpenWebUI"

            return parsed
        except requests.exceptions.RequestException as e:

            if e.response is not None:
                print_error(f"Return code: {e.response.status_code}: {e.response.text}")

            raise e
