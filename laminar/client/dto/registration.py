"""Registration data payloads.
"""

import inspect
import json

import numpy as np

from laminar.aroma.similar import setup_features
from laminar.client.dto.base import SerializableDTO
from laminar.client.web.utils import create_import_string, get_payload
from laminar.conversion import ConvertPy
from laminar.llms.encoder import LaminarCodeEncoder

AROMA_WORKING_DIR = "../../Aroma"
SOURCE_UNAVAILABLE = "Source code not available"


def _safe_getsource(obj) -> str:
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        return SOURCE_UNAVAILABLE


def _dedent(code: str) -> str:
    """Left-align a block of code to the minimum indentation of its lines."""
    lines = code.splitlines()
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    if not indents:
        return code
    min_indent = min(indents)
    return "\n".join(line[min_indent:] for line in lines)


class PERegistrationData(SerializableDTO):
    def __init__(self, *, pe: type, pe_name: str = None, pe_code: any = None,
                 description: str = None, inputDescription: str = None,
                 outputDescription: str = None, llmProvider: str = None,
                 llmModel: str = None, tags: list[str] = None,
                 encoder: LaminarCodeEncoder):
        if not description:
            raise RuntimeError("PE description not provided")

        pe_class = pe.__class__
        pe_source_code = _safe_getsource(pe_class)
        pe_process_source_code = _safe_getsource(pe._process)

        self.llmProvider = llmProvider
        self.llmModel = llmModel
        self.inputDescription = inputDescription
        self.outputDescription = outputDescription
        self.pe_name = pe_class.__name__
        self.pe_code = get_payload(pe)
        self.description = description
        self.pe_source_code = pe_source_code
        self.pe_imports = create_import_string(pe_source_code)
        self.code_embedding = np.array_str(encoder.embed_code(pe_process_source_code))
        self.desc_embedding = np.array_str(encoder.embed_text(self.description))
        self.tags = tags
        self.astEmbedding = self._build_ast_embedding(pe_source_code, pe_process_source_code)

    @staticmethod
    def _build_ast_embedding(pe_source_code: str, pe_process_source_code: str) -> str:
        code = pe_source_code if pe_source_code != SOURCE_UNAVAILABLE else pe_process_source_code
        if code != SOURCE_UNAVAILABLE:
            code = _dedent(code)
        converted = ConvertPy.ConvertPyToAST(code, False)
        featurised = setup_features([converted.result], AROMA_WORKING_DIR)
        return json.dumps(featurised)

    def to_dict(self) -> dict:
        return {
            "peName": self.pe_name,
            "peCode": self.pe_code,
            "sourceCode": self.pe_source_code,
            "description": self.description,
            "peImports": self.pe_imports,
            "codeEmbedding": self.code_embedding,
            "descEmbedding": self.desc_embedding,
            "astEmbedding": self.astEmbedding,
            "lldDescriptionProvider": self.llmProvider,
            "lldDescriptionModel": self.llmModel,
            "inputsDescription": self.inputDescription,
            "outputsDescription": self.outputDescription,
            "tags": self.tags,
        }


class WorkflowRegistrationData(SerializableDTO):
    def __init__(self, *, workflow: any, workflow_name: str = None,
                 workflow_code: str = None, workflow_pes=None, entry_point: str = None,
                 description: str = None, module=None, module_name=None,
                 inputDescription: str = None, outputDescription: str = None,
                 llmProvider: str = None, llmModel: str = None,
                 tags: list[str] = None, encoder: LaminarCodeEncoder):
        if not description:
            raise RuntimeError("No description provided")

        self.workflow_name = workflow_name
        self.workflow_code = get_payload(workflow) if workflow is not None else workflow_code
        self.entry_point = entry_point
        self.description = description
        self.workflow_pes = workflow.get_contained_objects()
        self.inputDescription = inputDescription
        self.outputDescription = outputDescription
        self.llmProvider = llmProvider
        self.llmModel = llmModel
        self.tags = tags
        self.desc_embedding = np.array_str(encoder.embed_text(self.description))

        self.module_source_code = inspect.getsource(module) if module else ""
        self.module_name = module_name or ""

    def to_dict(self) -> dict:
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
            "tags": self.tags,
        }
