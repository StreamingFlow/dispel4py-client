import openai
import os
import re
import json

from laminar.screen_printer import print_warning, print_text


def safe_json_loads(s: str, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


SINK_HINTS = ["write", "sink", "jsonl", "csv", "parquet", "output"]
COMMON_PORTS = {"input", "output", "row", "rows"}


def contains_sink_step(code: str) -> bool:
    c = (code or "").lower()
    return any(h in c for h in SINK_HINTS)


def extract_connect_ports(code: str):
    ports = []
    for m in re.finditer(r"graph\.connect\(\s*([a-zA-Z_]\w*)\s*,\s*'([^']+)'\s*,\s*([a-zA-Z_]\w*)\s*,\s*'([^']+)'\s*\)",
                         code):
        ports.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    for m in re.finditer(r'graph\.connect\(\s*([a-zA-Z_]\w*)\s*,\s*"([^"]+)"\s*,\s*([a-zA-Z_]\w*)\s*,\s*"([^"]+)"\s*\)',
                         code):
        ports.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    return ports


def has_suspicious_ports(code: str) -> bool:
    for _, outp, _, inp in extract_connect_ports(code):
        if outp not in COMMON_PORTS:
            return True
        if inp not in COMMON_PORTS:
            return True
    return False


def is_valid_workflow_code_v4(code: str):
    issues = []
    if not code or ("WorkflowGraph" not in code) or ("graph.connect" not in code):
        issues.append("Missing WorkflowGraph or graph.connect")
    if not contains_sink_step(code):
        issues.append("Missing sink/write step (workflow should write results)")
    if has_suspicious_ports(code):
        issues.append("Uses non-standard ports (likely invented). Prefer 'output'->'input'")
    return (len(issues) == 0), issues


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

        print_warning(f"Using {model} from OpenAI for description generation...")
        messages = [{"role": "system", "content": query} for query in context_queries]
        messages.append({"role": "user", "content": query})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0 if "nano" not in model else None,
        )

        txt = response.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
        response = json.loads(txt)
        response["model"] = model
        response["provider"] = "OpenAI"
        return response

    def rerank(self, model: str, query: str, candidates: list, top_k: int = 3, context_queries: list[str] = None):
        compact = []
        for c in candidates:
            code_snip = (c.get("code") or "").strip().splitlines()
            code_snip = "\n".join(code_snip[:35])

            compact.append({
                "type": c["type"],
                "id": c["id"],
                "name": c["name"],
                "score": float(c["score"]),
                "signals": {"emb": c["emb"], "lex": c["lex"], "tag": c["tag"], "struct": c["struct"]},
                "tags": safe_json_loads(c.get("tags_json"), []),
                "workflow_pe_list": safe_json_loads(c.get("pe_list_json"), []) if c["type"] == "workflow" else None,
                "description": c.get("description") or "",
                "code_excerpt": code_snip
            })

        prompt = f"""
                        User query:
                        {query}

                        Rerank and pick the best {top_k} results.
                        Use metadata and signals as hints, but prefer correctness.

                        Return JSON:
                        {{
                          "results": [
                            {{
                              "type": "pe"|"workflow",
                              "id": 0,
                              "name": "...",
                              "score": 0.0,
                              "why": "...",
                              "what_it_does": "..."
                            }}
                          ]
                        }}

                        CANDIDATES:
                        {json.dumps(compact, ensure_ascii=False)}
                        """.strip()

        messages = [{"role": "system", "content": query} for query in context_queries]
        messages.append({"role": "user", "content": prompt})

        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0
        )
        txt = resp.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
        return json.loads(txt)

    def propose_workflow_composition(self, model: str = "gpt-4o", query: str = None, pe_candidates: list = None,
                                     max_fixes: int = 2) -> dict:
        pe_compact = []
        for c in pe_candidates[:12]:
            pe_compact.append({
                "id": c["id"],
                "name": c["name"],
                "description": c.get("description") or "",
                "tags": safe_json_loads(c.get("tags_json"), []),
                "io": safe_json_loads(c.get("io_json"), {})
            })

        def call(prompt: str) -> dict:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": "Return JSON only. Do not explain."},
                          {"role": "user", "content": prompt}],
                temperature=0.0
            )
            txt = resp.choices[0].message.content.strip()
            txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
            return json.loads(txt)

        base_prompt = f"""
        User request:
        {query}

        You MUST propose a COMPLETE dispel4py WORKFLOW.

        Hard requirements:
        - Output valid Python code using WorkflowGraph.
        - Must include: graph = WorkflowGraph()
        - Must include at least one: graph.connect(...)
        - Must include a sink/write PE (e.g., WriteJSONL) that is connected.
        - Use standard ports: connect(..., "output", ..., "input") whenever possible.
        - Prefer composing from existing PEs listed below.

        Return JSON:
        {{
          "type": "workflow",
          "name": "...",
          "description": "...",
          "workflow_code": "...",
          "uses_pes": ["PE1","PE2",...],
          "new_pe": null OR {{
              "name": "...",
              "description": "...",
              "code": "..."
          }}
        }}

        Available PEs:
        {json.dumps(pe_compact, ensure_ascii=False)}
        """.strip()

        proposal = call(base_prompt)

        for _ in range(max_fixes + 1):
            ok, issues = is_valid_workflow_code_v4(proposal.get("workflow_code", ""))
            if ok:
                return proposal

            fix_prompt = f"""
        Your workflow proposal has issues:

        Issues:
        {json.dumps(issues, ensure_ascii=False)}

        Please return a corrected JSON proposal in the SAME format.
        - Ensure there is a sink/write step connected.
        - Use only standard ports: "output" to "input".
        - Avoid inventing ports like "filtered_row" or "file_path" unless absolutely necessary and defined.

        Original proposal:
        {json.dumps(proposal, ensure_ascii=False)}
        """.strip()

            proposal = call(fix_prompt)

        return proposal

    def classify(self, model: str = "gpt-4o", query: str = None) -> dict:
        prompt = f"""
    Classify the user's intent for searching a small dispel4py library.

    Return JSON:
    {{
      "kind": "pe" | "workflow" | "either",
      "input_type": "text" | "code"
    }}

    User input:
    {query}
    """.strip()

        resp = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return JSON only. Do not explain."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        txt = resp.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
        return json.loads(txt)

    def propose(self, model: str = "gpt-4o", query: str = None):
        prompt = f"""
                                User request:
                                {query}

                                No good match exists.

                                Propose ONE new component (PE or workflow).
                                Return JSON: {{"type":"pe"|"workflow","name":"...","description":"...","code":"..."}}
                                Rules:
                                - If workflow: provide WorkflowGraph code.
                                - If pe: provide a dispel4py PE class.
                                """.strip()

        resp = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Return JSON only. Do not explain."},
                      {"role": "user", "content": prompt}],
            temperature=0.0
        )
        txt = resp.choices[0].message.content.strip()
        txt = re.sub(r"^```json|```$", "", txt, flags=re.I).strip()
        return json.loads(txt)
