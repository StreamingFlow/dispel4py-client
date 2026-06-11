from typing import Any
import openai
import os
import re
import json

from openai.types.chat import ChatCompletionSystemMessageParam as systemChat, ChatCompletionUserMessageParam as userChat

from laminar.screen_printer import print_warning, print_text, print_error, print_status


def safe_json_loads(s: str, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


class OpenAIConnector:

    def __init__(self):
        self.key = os.environ["OPENAI_API_KEY"] if "OPENAI_API_KEY" in os.environ else None
        if self.key is None:
            raise RuntimeError("OpenAI API key not set")

        self.client = openai.OpenAI(api_key=self.key)
        self.default_model = "gpt-4o"

    def ask(self, model: str = None,
            prompt: str = None,
            system_queries: list[str] | None = None) -> dict:

        if model is None:
            model = self.default_model

        messages: list[userChat | systemChat] = [
            systemChat(role="system", content="return only JSON. DO NOT EXPLAIN.")
        ]

        if system_queries:
            for q in system_queries:
                messages.append(systemChat(role="system", content=q))

        messages.append(userChat(role="user", content=f"USER_REQUEST: {prompt}".strip()))

        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0 if "nano" not in model else None,
        )

        txt = resp.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()

        try:
            result = json.loads(txt)
        except Exception as e:
            print_error(f"WARNING: failed to parse JSON: {e}")
            print_text(txt)
            raise e

        result["model"] = model
        result["provider"] = "OpenAI"

        return result
