import inspect
import json
import numpy as np

from laminar.client.web.utils import get_payload
from laminar.llms.encoder import LaminarCodeEncoder


class WorkflowRegistrationData:
    def __init__(self, *, workflow: any, workflow_name: str = None, workflow_code: str = None, workflow_pes=None,
                 entry_point: str = None, description: str = None, module=None, module_name=None,
                 inputDescription: str = None, outputDescription: str = None, llmProvider: str = None,
                 llmModel: str = None, tags: list[str] = None ,encoder: LaminarCodeEncoder):
        if workflow is not None:
            workflow_code = get_payload(workflow)

        if not description:
            raise RuntimeError("No description provided")

        workflow_pes = workflow.get_contained_objects()
        workflow_source_code = "class " + entry_point + "():\n"

        self.llmProvider = llmProvider
        self.llmModel = llmModel
        self.inputDescription = inputDescription
        self.outputDescription = outputDescription

        for pe in workflow_pes:
            try:
                pe_code = inspect.getsource(pe.__class__)
            except:
                pe_code = inspect.getsource(pe._process)
            pe_code = pe_code.split("\n", 2)[2]
            workflow_source_code = workflow_source_code + pe_code
            workflow_source_code = workflow_source_code + "\n"

        self.description = description
        self.workflow_name = workflow_name
        self.workflow_code = workflow_code
        self.entry_point = entry_point
        self.workflow_pes = workflow_pes
        self.desc_embedding = np.array_str(encoder.embed_text(self.description))
        self.tags = tags

        if module:
            self.module_source_code = inspect.getsource(module)
        else:
            self.module_source_code = ""

        if module_name:
            self.module_name = module_name
        else:
            self.module_name = ""

    def to_dict(self):
        return {
            "workflowName": self.workflow_name,
            "workflowCode": self.workflow_code,
            "entryPoint": self.entry_point,
            "description": self.description,
            "descEmbedding": self.desc_embedding,
            "moduleSourceCode": self.module_source_code,
            "moduleName": self.module_name,
            "lldDescriptionProvider": self.llmProvider,
            "lldDescriptionModel": self.llmModel,
            "inputsDescription": self.inputDescription,
            "outputsDescription": self.outputDescription,
            "tags": self.tags
        }

    def __str__(self):
        return "WorkflowRegistrationData(" + json.dumps(self.to_dict(), indent=4) + ")"
