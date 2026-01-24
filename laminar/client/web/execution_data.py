import inspect
import json
from dispel4py.workflow_graph import WorkflowGraph

from laminar.client.web.utils import create_import_string, get_payload


class ExecutionData:
    def __init__(self, *, workflow_id: int, workflow_name: str, workflow_code: WorkflowGraph, input: any, process: int, resources: list[str]):
        imports = ""
        if workflow_code is not None:
            for pe in workflow_code.get_contained_objects():
                pe_class = pe.__class__
                try:
                    pe_source_code = inspect.getsource(pe_class)
                    imports = imports + "," + create_import_string(pe_source_code)
                    #print(pe_source_code)
                except OSError as e:
                    pass
                    #print(f"Error getting source for {pe_class.__name__}: {e}")
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.input = get_payload(input)
        self.workflow_code = get_payload(workflow_code)
        self.resources = resources
        self.imports = imports
        self.process = process.value

    def to_dict(self):
        return {
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "workflowCode": self.workflow_code,
            "inputCode": self.input,
            "resources": self.resources,
            "imports": self.imports,
            "process": self.process
        }

    def __str__(self):
        return "ExecutionData(" + json.dumps(self.to_dict(), indent=4) + ")"
