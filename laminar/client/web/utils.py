"""Shared helpers for the Laminar web client.

This module intentionally keeps *no* network logic: it only contains
serialization helpers, small formatting utilities and the exception types
used across the ``laminar.client.web`` package.
"""

import codecs
import os
import re
import subprocess
import tempfile

import cloudpickle as pickle
import numpy as np

import laminar.global_variables as g_vars
from laminar.screen_printer import print_warning

__all__ = [
    "LaminarError",
    "NotAuthenticatedError",
    "ServerConnectionError",
    "verify_login",
    "get_payload",
    "load_payload",
    "parse_np_array_str",
    "cosine_similarity",
    "create_import_string",
    "serialize_directory",
    "get_objects",
    "format_ast_pe_results",
    "format_ast_workflow_results",
    "g_vars",
    "print_warning",
]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class LaminarError(Exception):
    """Base class for all Laminar client errors."""


class NotAuthenticatedError(LaminarError):
    """Raised when an operation requires a logged-in user but none is set."""


class ServerConnectionError(LaminarError):
    """Raised when the Laminar server cannot be reached."""


def verify_login(logger=None):
    """Ensure a user is logged in.

    Historically this called ``exit()``, which kills the interpreter (and any
    hosting Jupyter kernel).  It now raises :class:`NotAuthenticatedError`
    instead so callers can handle it gracefully.  The ``logger`` argument is
    accepted for backwards compatibility and ignored.
    """
    if getattr(g_vars, "CLIENT_AUTH_ID", "None") == "None":
        raise NotAuthenticatedError(
            "You must be logged in to perform this operation."
        )


# --------------------------------------------------------------------------- #
# (De)serialization
# --------------------------------------------------------------------------- #
def get_payload(obj) -> str:
    """Pickle ``obj`` and encode it as a base64 string (server wire format)."""
    return codecs.encode(pickle.dumps(obj), "base64").decode()


def load_payload(payload: str):
    """Inverse of :func:`get_payload`: decode a base64 string back to an object."""
    return pickle.loads(codecs.decode(payload.encode(), "base64"))


def parse_np_array_str(s: str) -> np.ndarray:
    """Parse a string produced by :func:`numpy.array_str` back into an array.

    ``np.array_str`` output looks like ``"[ 0.1  0.2 -0.3 ]"`` and may span
    multiple lines, so we simply extract every float-looking token.
    """
    if not s:
        return np.zeros((0,), dtype=np.float32)
    tokens = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    return np.asarray([float(t) for t in tokens], dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors; 0.0 for empty/degenerate input."""
    if a is None or b is None or a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


# --------------------------------------------------------------------------- #
# Source-code helpers
# --------------------------------------------------------------------------- #
def create_import_string(pe_source_code: str) -> str:
    """Return a comma-separated list of top-level imports found in the source."""
    if not pe_source_code or pe_source_code == "Source code not available":
        return "No imports available"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(pe_source_code)
            tmp_path = tmp.name

        try:
            output = subprocess.check_output(["findimports", "-n", tmp_path], text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # findimports missing or failed: don't blow up registration.
            return "No imports available"

        lines = output.splitlines()[1:]  # first line is the filename header
        imports = [line.strip().split(".", 1)[0] for line in lines if line.strip()]
        return ",".join(imports)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def serialize_directory(path) -> str:
    """Recursively serialize a directory into a base64 pickled payload."""
    if path is None:
        return get_payload(None)

    data = {}
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            with open(item_path, "r") as f:
                data[item] = {
                    "type": "file",
                    "size": os.path.getsize(item_path),
                    "content": f.read(),
                }
        elif os.path.isdir(item_path):
            data[item] = {
                "type": "directory",
                "contents": serialize_directory(item_path),
            }
    return get_payload(data)


# --------------------------------------------------------------------------- #
# Result formatting
# --------------------------------------------------------------------------- #
def _describe_common(result: dict, desc: str) -> dict:
    """Fields shared by the PE and workflow summary rows."""
    return {
        "Description": desc,
        "LLM provider / model": "{} / {}".format(
            result.get("lldDescriptionProvider"), result.get("lldDescriptionModel")
        ),
        "Inputs": result.get("inputsDescription"),
        "Outputs": result.get("outputsDescription"),
        "Tags": result.get("tags"),
    }


def get_objects(results, extended: bool = False):
    """Split registry ``results`` into (description rows, unpickled objects)."""
    descriptions = []
    objects = []

    for result in results:
        desc = result.get("description") or "-"
        is_workflow = "workflowName" in result

        if extended:
            result["Type"] = "WF" if is_workflow else "PE"
            descriptions.append(result)
        elif is_workflow:
            row = {"ID": result["workflowId"], "Type": "WF", "Name": result["entryPoint"]}
            row.update(_describe_common(result, desc))
            descriptions.append(row)
        else:
            row = {"ID": result["peId"], "Type": "PE", "Name": result["peName"]}
            row.update(_describe_common(result, desc))
            row["Imports"] = result.get("peImports")
            descriptions.append(row)

        code_key = "workflowCode" if is_workflow else "peCode"
        label = result.get("workflowName") if is_workflow else result.get("peId")
        try:
            objects.append(load_payload(result[code_key]))
        except Exception as e:  # noqa: BLE001 - report and continue
            print_warning(f"An exception occurred while fetching {label} : {e}")

    return descriptions, objects


def format_ast_pe_results(similar_pes, response):
    """Turn raw AST-similarity tuples into dict rows joined with PE metadata."""
    by_id = {item["peId"]: item for item in response}
    formatted = []
    for pe_id, pe_name, score, pruned_score, similar_func, *_ in similar_pes:
        details = by_id.get(pe_id, {})
        formatted.append({
            "peId": pe_id,
            "peName": pe_name,
            "score": score,
            "pruned_score": pruned_score,
            "description": details.get("description"),
            "peCode": details.get("peCode"),
            "simlarFunc": similar_func.split("\n")[0],
        })
    return formatted


def format_ast_workflow_results(similar_workflows):
    """Turn raw AST-similarity workflow tuples into dict rows."""
    formatted = []
    for wf_id, wf_name, description, workflow_code, _position, occurrences in similar_workflows:
        formatted.append({
            "workflowId": wf_id,
            "workflowName": wf_name,
            "description": description,
            "workflowCode": workflow_code,
            "occurrences": occurrences,
        })
    return formatted
