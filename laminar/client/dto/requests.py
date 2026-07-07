"""Lightweight request payloads.

These DTOs describe simple requests (authentication, search, execution) and
deliberately avoid importing the ML/AST stack, so operations like login or
search stay fast to import.
"""

import inspect
from enum import Enum

from dispel4py.workflow_graph import WorkflowGraph

from laminar.client.dto.base import SerializableDTO
from laminar.client.web.utils import create_import_string, get_payload


class AuthenticationData(SerializableDTO):
    def __init__(self, *, user_name: str, user_password: str):
        self.user_name = user_name
        self.user_password = user_password

    def to_dict(self) -> dict:
        return {
            "userName": self.user_name,
            "password": self.user_password,
        }


class SearchData(SerializableDTO):
    def __init__(self, *, search: str, search_type: str):
        self.search = search
        self.search_type = search_type

    def to_dict(self) -> dict:
        return {
            "search": self.search,
            "searchType": self.search_type,
        }


class ExecutionData(SerializableDTO):
    def __init__(self, *, workflow_id: int | None, workflow_name: str | None,
                 workflow_code: WorkflowGraph | None, input: any, process, resources: list[str]):
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.input = get_payload(input)
        self.workflow_code = get_payload(workflow_code)
        self.resources = resources
        self.imports = self._collect_imports(workflow_code)
        # Accept either a Process enum member or a raw int.
        self.process = process.value if isinstance(process, Enum) else int(process)

    @staticmethod
    def _collect_imports(workflow_code: WorkflowGraph | None) -> str:
        if workflow_code is None:
            return ""
        parts = []
        for pe in workflow_code.get_contained_objects():
            try:
                source = inspect.getsource(pe.__class__)
            except (OSError, TypeError):
                continue
            parts.append(create_import_string(source))
        return ("," + ",".join(parts)) if parts else ""

    def to_dict(self) -> dict:
        return {
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "workflowCode": self.workflow_code,
            "inputCode": self.input,
            "resources": self.resources,
            "imports": self.imports,
            "process": self.process,
        }
