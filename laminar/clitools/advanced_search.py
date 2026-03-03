import base64
import json
import argparse
import numpy as np
import os

from laminar.argument_parser import CustomArgumentParser
from laminar.cli import print_text, print_error
from laminar.client.d4pyclient import d4pClient
from laminar.llms.LLMConnector import LLMConnector
from laminar.llms.encoder import LaminarCodeEncoder
from laminar.screen_printer import print_code, print_warning, print_status
from laminar.clitools.register import RegisterCommand


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None or a.size == 0 or b.size == 0:
        return -1.0
    # embeddings already normalized in CELL 3
    return float(np.dot(a, b))


def hybrid_weights(input_type: str):
    # return (desc_weight, code_weight)
    if input_type == "mixed":
        return 0.5, 0.5
    if input_type == "code":
        return 0.2, 0.8
    return 1.0, 0.0


def tag_boost(query: str, tags_json: str, max_boost: float = 0.06) -> float:
    if not tags_json:
        return 0.0

    if not isinstance(tags_json, list):
        try:
            tags = set(json.loads(tags_json))
        except Exception as e:
            print_error(f"WARNING: failed to parse tags: {e}")
            return 0.0
    else:
        tags = set(tags_json)

    q = (query or "").lower()
    hits = 0
    for t in tags:
        t2 = str(t).lower().replace("_", " ")
        if t2 and t2 in q:
            hits += 1

    return min(max_boost, 0.02 * hits)


def _safe_json_loads(s: str, default):
    if isinstance(s, list):
        return s

    try:
        return json.loads(s) if s else default
    except Exception as e:
        print_error(f"WARNING: failed to load JSON: {e}")
        print_text(f"Input: {s}")
        return default


class AdvancedSearchCommand:

    def __init__(self, client: d4pClient, encoder: LaminarCodeEncoder = None, llm_connector: LLMConnector = None,
                 registerInterface: RegisterCommand = None):
        self.client = client
        self.encoder = encoder or LaminarCodeEncoder()
        self.connector = llm_connector or LLMConnector()
        self.registerInterface = registerInterface or RegisterCommand(self.client, llmConnector=self.connector)

        self._CAP_HINTS = {
            "csv": ["csv", "readcsv"],
            "filter": ["filter", "filtering", "threshold", "quality"],
            "fft": ["fft", "frequency", "spectrum"],
            "window": ["window", "hann", "hamming"],
            "bandpass": ["bandpass", "signal processing"],
            "detrend": ["detrend", "signal processing"],
            "write": ["write", "jsonl", "export", "output"]
        }

    def _extract_requested_caps(self, query: str) -> set:
        q = (query or "").lower()
        req = set()

        for k in self._CAP_HINTS.keys():
            if k in q:
                req.add(k)
        if "cross" in q and "correlation" in q:
            req.add("cross_correlation")
        return req

    def _workflow_structure_score(self, query: str, pe_list_json: str, pe_tags_by_name: dict) -> float:
        req = self._extract_requested_caps(query)
        if not req:
            return 0.0
        pe_list = _safe_json_loads(pe_list_json, [])
        if not pe_list:
            return 0.0

        tags_union = set()
        for pe_name in pe_list:
            tags_union |= set(pe_tags_by_name.get(pe_name, []))

        matched = 0
        for cap in req:
            if cap == "cross_correlation":
                if ("correlation" in tags_union) or ("signal processing" in tags_union):
                    matched += 1
                continue
            hints = self._CAP_HINTS.get(cap, [])
            if any(h in tags_union for h in hints):
                matched += 1

        return matched / max(1, len(req))

    def _retrieve(self,
                  query: str,
                  *,
                  kind: str,
                  input_type: str,
                  top_n: int = 30):
        w_desc, w_code = hybrid_weights(input_type)
        q_text, q_code = self.encoder.embed_query(query, input_type)
        lex = self.client.lexical_scores(kind, query, limit=120)

        # tags for structure
        pe_tags_by_name = {}

        registry, _ = self.client.get_Registry(extended=True)

        pe_rows = [itm for itm in registry if itm["Type"] == "PE"]
        wf_rows = [itm for itm in registry if itm["Type"] == "WF"]

        for pe in pe_rows:
            name = pe["peName"]
            pe_tags_by_name[name] = pe['tags'] if isinstance(pe['tags'], list) else []

        # weights
        W_EMB = 0.60
        W_LEX = 0.25
        W_TAG = 0.10
        W_STR = 0.05

        candidates = []

        if kind in ("pe", "either"):

            for pe in pe_rows:

                pe_id = pe["peId"]
                name = pe["peName"]
                code = pe["peCode"]
                desc = pe["description"]
                tags_json = pe["tags"]

                s_desc = cosine(q_text, self.encoder.embed_text(desc)) if (
                        q_text is not None and desc is not None) else -1.0
                s_code = cosine(q_code, self.encoder.embed_code(code)) if (
                        q_code is not None and code is not None) else -1.0

                emb = 0.0
                wsum = 0.0
                if w_desc > 0 and s_desc >= 0:
                    emb += w_desc * s_desc
                    wsum += w_desc
                if w_code > 0 and s_code >= 0:
                    emb += w_code * s_code
                    wsum += w_code
                emb = emb / wsum if wsum > 0 else max(s_desc, s_code)

                lex_s = lex.get(("pe", int(pe_id)), 0.0)
                tag_s = tag_boost(query, tags_json) / 0.06  # ~0..1

                final = W_EMB * emb + W_LEX * lex_s + W_TAG * tag_s

                candidates.append({
                    "type": "pe", "id": int(pe_id), "name": name,
                    "score": float(final),
                    "emb": float(emb), "lex": float(lex_s), "tag": float(tag_s), "struct": 0.0,
                    "sim_desc": float(s_desc), "sim_code": float(s_code),
                    "description": desc, "code": code,
                    "tags_json": tags_json
                })

        if kind in ("workflow", "either"):
            for workflow in wf_rows:
                wid = workflow["workflowId"]
                name = workflow["workflowName"]
                code = workflow["workflowCode"]
                desc = workflow["description"]
                dblob = workflow["descEmbedding"]
                tags_json = workflow["tags"]
                pe_list_json = workflow["tags"]
                edges_json = None

                s_desc = cosine(q_text, self.encoder.embed_text(desc)) if (
                        q_text is not None and dblob is not None) else -1.0
                s_code = cosine(q_code, self.encoder.embed_code(code)) if (
                        q_code is not None and code is not None) else -1.0

                emb = 0.0
                wsum = 0.0
                if w_desc > 0 and s_desc >= 0:
                    emb += w_desc * s_desc;
                    wsum += w_desc
                if w_code > 0 and s_code >= 0:
                    emb += w_code * s_code;
                    wsum += w_code
                emb = emb / wsum if wsum > 0 else max(s_desc, s_code)

                lex_s = lex.get(("workflow", int(wid)), 0.0)
                tag_s = tag_boost(query, tags_json) / 0.06
                struct_s = self._workflow_structure_score(query, pe_list_json, pe_tags_by_name)

                final = W_EMB * emb + W_LEX * lex_s + W_TAG * tag_s + W_STR * struct_s

                candidates.append({
                    "type": "workflow", "id": int(wid), "name": name,
                    "score": float(final),
                    "emb": float(emb), "lex": float(lex_s), "tag": float(tag_s), "struct": float(struct_s),
                    "sim_desc": float(s_desc), "sim_code": float(s_code),
                    "description": desc, "code": code,
                    "tags_json": tags_json, "pe_list_json": pe_list_json, "edges_json": edges_json
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_n], {"w_desc": w_desc, "w_code": w_code, "input_type": input_type}

    def _detect_inputs(self,
                       query: str,
                       *,
                       kind: str = "auto",
                       input_type: str = "auto") -> tuple[str, str]:
        try:
            clf = self.connector.classify("openai", "gpt-4o", query)
            kind = clf.get("kind", kind)
            input_type = clf.get("input_type", input_type)
        except Exception as e:
            print_warning(f"WARNING: failed to classify user intent with GPT. Using heuristic approach: {e}")
            pass  # go to default mode with not GPT query if errors occurs
        finally:
            return kind, input_type

    def help(self):
        print_text("""
        Perform a semantic search in the Laminar library. Proposes PEs and Workflows if it cannot find a match.
        """)

    def _search(self, query: str, *, kind: str = "auto", input_type: str = "auto", shortlist_n: int = 30,
                top_k: int = 3):
        kind, input_type = self._detect_inputs(query, kind=kind, input_type=input_type)

        shortlist, _mode = self._retrieve(query, kind=kind, input_type=input_type, top_n=shortlist_n)

        if not shortlist:
            print_warning("No candidates found (check embeddings/FTS).")
            return None

        best = shortlist[0]
        second = shortlist[1]["score"] if len(shortlist) > 1 else -1.0
        gap = best["score"] - second if second >= 0 else 1.0

        # IMPORTANT: uncertainty based on embedding similarity, not compressed final score
        uncertain = (best["emb"] < 0.55) or (best["emb"] < 0.65 and gap < 0.04)

        print_warning("Top results uncertainty: {}:\n".format(best["emb"]))

        if uncertain:
            if kind == "workflow":
                pe_only, _ = self._retrieve(query, kind="pe", input_type=input_type, top_n=40)
                proposal = self.connector.propose_workflow_composition("openai", "gpt-4o", query, pe_only, max_fixes=2)

                print_warning("Could not find a strong match in the database. Generating a new workflow:\n")
                print_status(f"{proposal.get('name')} - {proposal.get('description')}:\n")
                print_code(proposal.get("workflow_code"))

                if proposal.get("new_pe"):
                    print_warning("\nNew PEs are required for this workflow:")

                    for pe in proposal["new_pe"]:
                        name = pe["name"]
                        desc = pe["description"]
                        print_text(f"{name} : {desc}")
                        # print_code(pe["code"])

                register_workflow_choice = input(
                    "Would you like to register / save the workflow? [(R)egister/(S)tore/(N)one]: ") or "N"

                if "R" in register_workflow_choice.upper():
                    with open("workflow.py", "w") as f:
                        f.write(proposal["workflow_code"])

                    self.registerInterface.register("workflow workflow.py")

                    os.remove("workflow.py")

                if "S" in register_workflow_choice.upper():
                    filepath = input(
                        "Please input file path and filename to store the workflow code: ") or f"{proposal['name']}.py"
                    with open(filepath, "w") as f:
                        f.write(proposal["workflow_code"])

                    print_status(f"Stored workflow code to {filepath}")

                return None

            # PE/either: do NOT propose if we already have a clear top result
            # (If emb is decent, just rerank and show it)
            # Only propose if best emb is truly low
            if best["emb"] < 0.40:
                proposal = self.connector.propose_new_component(provider="openai", model="gpt-4o", query=query)

                print_warning("Could not find a strong match in the database. Generating a new PE:\n")
                print_status(f"{proposal.get('name')} - {proposal.get('description')}\n")
                print_code(proposal.get("code"))

                register_pe_choice = input(
                    "Would you like to register / save the proposed PE? [(R)egister/(S)tore/(N)one]: ") or "N"

                if "R" in register_pe_choice.upper():
                    with open("pe.py", "w") as f:
                        f.write(proposal["code"])

                    self.registerInterface.register("pe pe.py")

                    os.remove("pe.py")

                if "S" in register_pe_choice.upper():
                    filepath = input(
                        "Please input file path and filename to store the PE code: ") or f"{proposal['name']}.py"
                    with open(filepath, "w") as f:
                        f.write(proposal["code"])

                    print_status(f"Stored PE code to {filepath}")
                return None

        # GPT rerank if not proposing
        reranked = self.connector.rerank(provider="openai", model="gpt-4o", query=query, candidates=shortlist[:12],
                                         top_k=top_k)

        print_status("Top results (GPT reranked):\n")
        results = reranked.get("results", [])
        print_text(results, tab=True)

        # Suggested candidate
        suggested = shortlist[0]
        if results:
            top = results[0]
            for c in shortlist:
                if c["type"] == top["type"] and c["id"] == int(top["id"]):
                    suggested = c
                    break

        suggested["tags"] = _safe_json_loads(suggested.get("tags_json"), [])
        print_status("Suggested candidate:\n")
        print_text([{
            "id": suggested["id"],
            "name": suggested["name"],
            "score": suggested["score"],
            "description": suggested["description"],
            "tags": suggested["tags"],
        }], tab=True)

        workflow_id = suggested.get("id")
        wf = self.client.get_Workflow(workflow_id)
        print_status("\nWorkflow code:")
        print_code(wf[1])

        return None

    def search_library(self, arg):

        # TODO: better cli interface

        kind = input("Kind (pe or workflow. Default: workflow): ") or "workflow"
        input_type = input("Input type (auto): ") or "auto"
        query = input("Query: ")

        self._search(query=query, input_type=input_type, kind=kind, top_k=3)
