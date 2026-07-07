"""HTTP client for the Laminar registry / execution server.
"""

import json
from typing import Union

import numpy as np
import pandas as pd
import requests as req

from laminar.aroma.similar import compare_similar, setup_features
from laminar.client.dto import (
    AuthenticationData,
    ExecutionData,
    PERegistrationData,
    SearchData,
    WorkflowRegistrationData,
)
from laminar.client.web.utils import (
    LaminarError,
    ServerConnectionError,
    cosine_similarity,
    format_ast_pe_results,
    format_ast_workflow_results,
    g_vars,
    get_objects,
    load_payload,
    parse_np_array_str,
    print_warning,
)
from laminar.conversion import ConvertPy
from laminar.global_variables import URL_SEARCH_PE, URL_SEARCH_WORKFLOW, AROMA_WORKING_DIR, HTTP_TIMEOUT
from laminar.llms.encoder import LaminarCodeEncoder
from laminar.screen_printer import print_text


def _api_error(payload: str | dict | None) -> Union[str, None]:
    """Return the error message if ``payload`` is an ApiError dict, else None."""
    if isinstance(payload, dict) and "ApiError" in payload:
        err = payload["ApiError"]
        return err.get("message") or err.get("debugMessage") or "Unknown API error"
    return None


class WebClient:
    def __init__(self):
        self.encoder = None
        self.user_login_id = None

    def verifyLogin(self):
        if not self.user_login_id:
            raise PermissionError("Current session is not logged in!")

    def getLogin(self):
        return self.user_login_id

    def _getEncoder(self, ensure_models: bool = True) -> LaminarCodeEncoder:
        if self.encoder is None:
            self.encoder = LaminarCodeEncoder(ensure_models=ensure_models)
        return self.encoder

    @staticmethod
    def _request(method: str, url: str, **kwargs):
        """Perform an HTTP request, translating connection failures into a
        :class:`ServerConnectionError` instead of leaving the client to guess."""
        kwargs.setdefault("timeout", HTTP_TIMEOUT)
        try:
            return req.request(method, url, **kwargs)
        except req.RequestException as e:
            raise ServerConnectionError(
                f"Unable to connect to Laminar server at {url}: {e}"
            ) from e

    @classmethod
    def _requestJson(cls, method: str, url: str, **kwargs):
        """Like :meth:`_request` but parse the JSON body (or return None)."""
        response = cls._request(method, url, **kwargs)
        try:
            return response.json()
        except ValueError:
            return None

    def registerUser(self, user_data: AuthenticationData):
        payload = self._requestJson(
            "POST", g_vars.URL_REGISTER_USER,
            data=json.dumps(user_data.to_dict()), headers=g_vars.headers,
        )

        if _api_error(payload):
            return False
        self.user_login_id = payload["userName"]

        return True

    def login(self, user_data: AuthenticationData):
        payload = self._requestJson(
            "POST", g_vars.URL_LOGIN_USER,
            data=json.dumps(user_data.to_dict()), headers=g_vars.headers,
        )

        if _api_error(payload):
            return False

        self.user_login_id = payload["userName"]
        return True

    def registerPE(self, pe_payload: PERegistrationData):
        self.verifyLogin()
        response = self._request(
            "POST", g_vars.URL_REGISTER_PE.format(self.user_login_id),
            data=json.dumps(pe_payload.to_dict()), headers=g_vars.headers,
        )
        if not response.ok:
            return None

        payload = response.json()

        if _api_error(payload):
            return None

        pe_id = int(payload["peId"])
        self._indexForSearch(URL_SEARCH_PE, pe_id, pe_payload.pe_name,
                             pe_payload.description, pe_payload.tags)
        return pe_id

    def registerWorkflow(self, workflow_payload: WorkflowRegistrationData):
        self.verifyLogin()
        payload = self._requestJson(
            "POST", g_vars.URL_REGISTER_WORKFLOW.format(self.user_login_id),
            data=json.dumps(workflow_payload.to_dict()), headers=g_vars.headers,
        )

        if _api_error(payload):
            return None

        workflow_id = payload["workflowId"]
        self._indexForSearch(URL_SEARCH_WORKFLOW, int(workflow_id),
                             workflow_payload.workflow_name,
                             workflow_payload.description, workflow_payload.tags)
        self._linkPEsToWorkflow(workflow_id, workflow_payload.workflow_pes)

        return payload["workflowId"]

    def _indexForSearch(self, base_url, obj_id, name, description, tags):
        """Register an object with the full-text-search index (best effort)."""
        tag_str = ",".join(tags) if tags else ""
        response = self._request("POST", base_url, json={
            "id": obj_id,
            "name": name,
            "description": description,
            "tags": tag_str,
            "keywords": tag_str,
        })
        if response.status_code != 200:
            print_warning(f"Error occurred while indexing {name}: {response.text}")

    def _linkPEsToWorkflow(self, workflow_id, workflow_pes):
        """Ensure every PE in the workflow exists and is linked to it."""
        encoder = self._getEncoder()
        for pe_obj in workflow_pes:
            get_pe_url = g_vars.URL_GET_PE_NAME.format(self.user_login_id) + pe_obj.name
            pe_res = self._requestJson("GET", get_pe_url) or {}

            if _api_error(pe_res):
                print_text(pe_res)
                pe_id = self.registerPE(PERegistrationData(
                    pe=pe_obj, encoder=encoder,
                    description=f"Auto-registered PE {pe_obj.name}",
                ))
            else:
                pe_id = pe_res["peId"]

            self._request(
                "PUT",
                g_vars.URL_LINK_PE_TO_WORKFLOW.format(
                    self.user_login_id, workflow_id, pe_id
                ),
            )

    def run(self, execution_payload: ExecutionData, verbose: bool = True):
        """Execute a workflow, streaming server-sent events.

        Returns the final result (or the list of partial results if the server
        streamed them), or ``None`` if the execution failed.
        """
        self.verifyLogin()
        headers = {**g_vars.headers, "Accept": "text/event-stream"}
        response = self._request(
            "POST", g_vars.URL_EXECUTE.format(self.user_login_id),
            data=json.dumps(execution_payload.to_dict()), headers=headers, stream=True,
        )
        if not response.ok:
            print(f"Error connecting to server: [{response.status_code}] {response.reason}")
            return None

        parts = []
        try:
            for raw_line in response.iter_lines():
                line = raw_line.decode("utf-8") if raw_line else ""
                if not line.startswith("data:"):
                    continue
                data = json.loads(line[5:])

                if "response" in data:
                    if verbose:
                        print(str(data["response"]), end="")
                elif "result" in data:
                    return parts if parts else data["result"]
                elif "part-result" in data:
                    parts.append(data["part-result"])
                elif "resources" in data:
                    self._uploadResources(data["resources"])
                elif "error" in data:
                    print("Error: " + str(data["error"]))
        except Exception as e:  # noqa: BLE001
            print("Error: " + str(e))
            return None

        return parts if parts else None

    def _uploadResources(self, resources):
        """Upload the resource files the server requested."""
        print("Requested resources: " + str(resources))
        if not resources:
            return

        open_files = [open(path, "rb") for path in resources]
        try:
            file_response = self._request(
                "PUT",
                g_vars.URL_RESOURCE.format(self.user_login_id),
                files=[("files", f) for f in open_files],
            )
            print(f"File response: {file_response.status_code} {file_response.reason}")
        finally:
            for f in open_files:
                f.close()

    def getPE(self, pe: Union[int, str]):
        self.verifyLogin()
        url = self._peUrl(g_vars.URL_GET_PE_NAME, g_vars.URL_GET_PE_ID, pe)
        payload = self._requestJson("GET", url)

        if _api_error(payload):
            return None

        return [
            load_payload(payload["peCode"]),
            payload["sourceCode"],
            payload["peName"],
            payload["peId"],
            payload["description"],
        ]

    def getWorkflow(self, workflow: Union[int, str]):
        self.verifyLogin()
        url = self._workflowUrl(
            g_vars.URL_GET_WORKFLOW_NAME, g_vars.URL_GET_WORKFLOW_ID, workflow
        )
        payload = self._requestJson("GET", url)

        if _api_error(payload):
            return None

        return [
            load_payload(payload["workflowCode"]),
            payload["moduleSourceCode"],
            payload["workflowName"],
            payload["workflowId"],
            payload["description"],
        ]

    def getPEsByWorkflow(self, workflow: Union[int, str]):
        self.verifyLogin()
        url = self._workflowUrl(
            g_vars.URL_GET_PE_BY_WORKFLOW_NAME, g_vars.URL_GET_PE_BY_WORKFLOW_ID, workflow
        )
        results = self._requestJson("GET", url) or []

        objects = []
        for index, result in enumerate(results, start=1):
            desc = result["description"] or "-"
            print(f"Result {index}: \nID: {result['peId']}\nPE Name: {result['peName']}\n"
                  f"Description: {desc}\n")
            objects.append(load_payload(result["peCode"]))
        return objects

    def getWorkflows(self):
        """Retrieve all workflows from the registry."""
        self.verifyLogin()
        url = g_vars.URL_WORKFLOW_ALL.format(self.user_login_id)
        response = self._request("GET", url)
        if not response.ok:
            return None
        return response.json() if response.text else []

    def getRegistry(self, extended: bool = False):
        self.verifyLogin()
        url = g_vars.URL_REGISTRY_ALL.format(self.user_login_id)
        results = self._requestJson("GET", url) or []
        return get_objects(results, extended)

    def getIds(self):
        self.verifyLogin()
        url = g_vars.URL_REGISTRY_ALL.format(self.user_login_id)
        results = self._requestJson("GET", url) or []

        workflow_ids, pe_ids = [], []
        for result in results:
            if "workflowName" in result:
                workflow_ids.append(result["workflowId"])
            else:
                pe_ids.append(result["peId"])
        return workflow_ids, pe_ids

    def removePE(self, pe: Union[int, str]):
        self.verifyLogin()
        url = self._peUrl(g_vars.URL_REMOVE_PE_NAME, g_vars.URL_REMOVE_PE_ID, pe)
        self._deleteFromSearchIndex(URL_SEARCH_PE, pe, "PE")
        return self._delete(url, pe, "PE")

    def removeWorkflow(self, workflow: Union[int, str]):
        self.verifyLogin()
        url = self._workflowUrl(
            g_vars.URL_REMOVE_WORKFLOW_NAME, g_vars.URL_REMOVE_WORKFLOW_ID, workflow
        )
        self._deleteFromSearchIndex(URL_SEARCH_WORKFLOW, workflow, "Workflow")
        return self._delete(url, workflow, "Workflow")

    def _deleteFromSearchIndex(self, base_url, obj_id, label):
        response = self._request(
            "DELETE", base_url.format(self.user_login_id) + "?id=" + str(obj_id)
        )
        if response.status_code != 200:
            print_warning(f"Error occurred while deleting {label}: {obj_id} : {response.text}")

    def _delete(self, url, obj_id, label):
        return self._requestJson("DELETE", url)

    def updateWorkflowDescription(self, workflow, new_description):
        return self._updateDescription(
            g_vars.URL_UPDATE_WORKFLOW_DESC_ID, workflow, new_description, "workflow"
        )

    def updatePEDescription(self, pe, new_description):
        return self._updateDescription(
            g_vars.URL_UPDATE_PE_DESC_ID, pe, new_description, "pe"
        )

    def _updateDescription(self, url_template, obj_id, new_description, label):
        self.verifyLogin()
        # BUGFIX: the encoder has no ``encode`` method; use ``embed_text`` which
        # already returns a numpy array.
        new_embedding = np.array_str(self._getEncoder().embed_text(new_description))
        url = url_template.format(self.user_login_id, obj_id)
        response = self._request(
            "PUT", url,
            json={"description": new_description, "descEmbedding": new_embedding},
            headers=g_vars.headers,
        )
        if response.status_code == 200:
            return f"Successfully updated the description of {label} ID: {obj_id}"
        raise LaminarError(f"Failed to update {label} description: {response.text}")

    def search(self, search_payload: SearchData):
        """Literal (keyword) search."""
        self.verifyLogin()
        search_dict = search_payload.to_dict()
        url = g_vars.URL_SEARCH.format(
            self.user_login_id, search_dict["search"], search_dict["searchType"]
        )
        response = self._request("GET", url)
        if not response.ok:
            return None

        if not response.text:
            return []

        return get_objects(response.json())[0]

    def searchSimilarity(self, search_payload: SearchData, query_type, embedding_type):
        """Semantic / code-recommendation search.

        ``embedding_type``:
          * ``"llm"`` -> local cosine similarity over transformer embeddings.
          * ``"spt"`` -> Aroma AST structural-similarity search.
        """
        self.verifyLogin()
        search_dict = search_payload.to_dict()
        search_type = search_dict["searchType"]

        if search_type == "workflow" and query_type == "text":
            url = g_vars.URL_WORKFLOW_ALL.format(self.user_login_id)
        else:
            url = g_vars.URL_PE_ALL.format(self.user_login_id)
        items = self._requestJson("GET", url) or []

        if embedding_type == "llm":
            return self._searchLLM(items, search_dict["search"], query_type, search_type)
        return self._searchAST(items, search_dict["search"], search_type)

    def _searchLLM(self, items, query, query_type, search_type):
        encoder = self._getEncoder()
        is_code = query_type == "code"
        query_vec = encoder.embed_code(query) if is_code else encoder.embed_text(query)
        stored_key = "codeEmbedding" if is_code else "descEmbedding"
        text_key = "sourceCode" if is_code else "description"

        scored = []
        for item in items:
            vec = parse_np_array_str(item.get(stored_key, ""))
            if vec.size != query_vec.size:
                text = item.get(text_key) or ""
                vec = encoder.embed_code(text) if is_code else encoder.embed_text(text)
            scored.append((cosine_similarity(query_vec, vec), item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:5]

        is_workflow = search_type == "workflow"
        code_key = "workflowCode" if is_workflow else "peCode"
        name_key = "workflowName" if is_workflow else "peName"
        id_key = "workflowId" if is_workflow else "peId"

        table = [{
            "ID": item.get(id_key),
            "Name": item.get(name_key),
            "score": round(score, 4),
            "description": item.get("description"),
        } for score, item in top]
        if table:
            print_text(table, tab=True)

        return [load_payload(item[code_key]) for _, item in top if item.get(code_key)]

    def _searchAST(self, items, query, search_type):
        ast_embeddings = []
        for pe in items:
            functions = json.loads(pe["astEmbedding"])
            for func in functions:
                func["peId"] = pe["peId"]
                func["peName"] = pe["peName"]
            ast_embeddings += functions

        converted = ConvertPy.ConvertPyToAST(query, False)
        setup_features([ast_embeddings], AROMA_WORKING_DIR)

        similar_pes = []
        for result in converted.result:
            similar_pes += compare_similar(ast_embeddings, [result], AROMA_WORKING_DIR)

        if search_type == "pe":
            return self._astPEResult(similar_pes, items)
        return self._astWorkflowResults(similar_pes)

    @staticmethod
    def _astPEResult(similar_pes, items):
        formatted = format_ast_pe_results(similar_pes, items)
        df = pd.DataFrame(formatted).sort_values(by="score", ascending=False).head(5)
        print(df[["peId", "peName", "description", "score", "simlarFunc"]])
        return [load_payload(code) for code in df["peCode"]]

    def _astWorkflowResults(self, similar_pes):
        url = g_vars.URL_GET_WORKFLOW_BY_PE.format(self.user_login_id)

        positions = {}  # workflow_id -> row index
        discovered = []  # [id, name, desc, code, index, occurrences]
        for pe in similar_pes:
            rows = self._requestJson("GET", url + str(pe[0])) or []
            for row in rows:
                wf_id = row[0]
                if wf_id not in positions:
                    positions[wf_id] = len(discovered)
                    discovered.append([row[0], row[1], row[2], row[3], len(discovered), 1])
                else:
                    discovered[positions[wf_id]][5] += 1

        formatted = format_ast_workflow_results(discovered)
        df = pd.DataFrame(formatted).sort_values(by="occurrences", ascending=False).head(5)
        print(df[["workflowId", "workflowName", "description", "occurrences"]])
        return [load_payload(code) for code in df["workflowCode"]]

    def lexicalScores(self, kind: str, query: str, limit: int = 50) -> dict:
        q = self._prepareFtsQuery(query)
        if not q:
            return {}

        scores = {}
        if kind in ("pe", "either"):
            self._collectFtsScores(URL_SEARCH_PE, "pe", q, limit, scores)
        if kind in ("workflow", "either"):
            # BUGFIX: previously stored under the "pe" namespace.
            self._collectFtsScores(URL_SEARCH_WORKFLOW, "workflow", q, limit, scores)
        return scores

    def _collectFtsScores(self, base_url, namespace, q, limit, scores):
        url = base_url.format(self.user_login_id) + f"?q={q}&limit={limit}"
        rows = self._requestJson("GET", url) or []
        for row in rows:
            score = float(row["score"]) if row.get("score") else 0.0
            scores[(namespace, int(row["id"]))] = 1.0 / (1.0 + score) if score else 0.0

    @staticmethod
    def _prepareFtsQuery(q: str) -> str:
        """Convert a free-form string into a simplified ``OR``-joined FTS query.

        Lowercases the input, keeps alphanumeric/underscore tokens longer than
        two characters, limits to the first 12 tokens.
        """
        import re
        tokens = [t for t in re.findall(r"[a-zA-Z0-9_]+", (q or "").lower()) if len(t) > 2]
        return " OR ".join(tokens[:12]) if tokens else ""

    def _peUrl(self, name_template, id_template, pe):
        if isinstance(pe, str):
            return name_template.format(self.user_login_id) + pe
        if isinstance(pe, int):
            return id_template.format(self.user_login_id) + str(pe)
        raise TypeError(f"Invalid type for pe: {type(pe)}")

    def _workflowUrl(self, name_template, id_template, workflow):
        if isinstance(workflow, str):
            return name_template.format(self.user_login_id) + workflow
        if isinstance(workflow, int):
            return id_template.format(self.user_login_id) + str(workflow)
        raise TypeError(f"Invalid type for workflow: {type(workflow)}")
