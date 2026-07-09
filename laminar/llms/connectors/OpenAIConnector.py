import openai
import os
import re
import json

from openai.types.chat import ChatCompletionSystemMessageParam as systemChat, ChatCompletionUserMessageParam as userChat

from laminar.screen_printer import print_text, print_error


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
        self.default_model = "gpt-5.4-mini"

    def ask(self,
            prompt: str | None = None,
            system_queries: list[str] | None = None) -> dict:

        messages: list[userChat | systemChat] = [
            systemChat(role="system", content="return only JSON. DO NOT EXPLAIN.")
        ]

        if system_queries:
            for q in system_queries:
                messages.append(systemChat(role="system", content=q))

        messages.append(userChat(role="user", content=f"USER_REQUEST: {prompt}".strip()))

        resp = self.client.chat.completions.create(
            model=self.default_model,
            messages=messages,
            temperature=0.0 if "nano" not in self.default_model else None,
        )

        txt = resp.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()

        try:
            result = json.loads(txt)
        except Exception as e:
            print_error(f"WARNING: failed to parse JSON: {e}")
            print_text(txt)
            raise e

        result["model"] = self.default_model
        result["provider"] = "OpenAI"

        return result
