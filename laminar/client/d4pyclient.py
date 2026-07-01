import logging
import os
import re
from typing import Union
from typing_extensions import Literal, get_args

from dispel4py.workflow_graph import WorkflowGraph

import laminar.global_variables as g_vars
from laminar.client.dto import (
    AuthenticationData,
    ExecutionData,
    PERegistrationData,
    SearchData,
    WorkflowRegistrationData,
)
from laminar.client.web.client import WebClient
from laminar.llms.encoder import LaminarCodeEncoder
from laminar.screen_printer import print_status, print_text, print_code

logger = logging.getLogger(__name__)

_TYPES = Literal["pe", "workflow", "both"]
_QUERY_TYPES = Literal["text", "code"]
_E_TYPES = Literal["llm", "spt"]

_VALID_COMBINATIONS = {"text": ["llm"], "code": ["llm", "spt"]}


class d4pClient:
    """Class to interact with the Laminar registry and execution services."""

    def __init__(self):
        self.webclient = WebClient()
        self.encoder = None

        user_name = os.getenv("LAMINAR_USERNAME")
        user_password = os.getenv("LAMINAR_PASSWORD")
        if user_name is not None and user_password is not None:
            self.login(user_name, user_password)

    def _get_encoder(self, ensure_models: bool = True) -> LaminarCodeEncoder:
        if self.encoder is None:
            self.encoder = LaminarCodeEncoder(ensure_models=ensure_models)
        return self.encoder

    @staticmethod
    def _validate_search_type(search_type: str):
        options = get_args(_TYPES)
        assert search_type in options, f"'{search_type}' is not in {options}"

    def register(self, user_name: str, user_password: str):
        """Register a user with the Registry service."""
        data = AuthenticationData(user_name=user_name, user_password=user_password)
        return self.webclient.register_user(data)

    def login(self, user_name: str, user_password: str):
        """Log a user in to use the Registry service."""
        data = AuthenticationData(user_name=user_name, user_password=user_password)
        return self.webclient.login_user(data)

    def get_login(self):
        """Return the current username, or ``None`` if nobody is logged in."""
        return g_vars.CLIENT_AUTH_ID if g_vars.CLIENT_AUTH_ID != "None" else None

    def register_PE(self, pe: g_vars.PE_TYPES, description: str = None,
                    input_description: str = None, output_description: str = None,
                    llm_provider: str = None, llm_model: str = None,
                    tags: list[str] = None):
        """Register a PE with the client service."""
        data = PERegistrationData(
            pe=pe, description=description, inputDescription=input_description,
            outputDescription=output_description, llmModel=llm_model,
            llmProvider=llm_provider, encoder=self._get_encoder(), tags=tags,
        )
        return self.webclient.register_PE(data)

    def register_Workflow(self, workflow: WorkflowGraph, workflow_name: str,
                          description: str = None, module=None, module_name=None,
                          input_description: str = None, output_description: str = None,
                          llm_provider: str = None, llm_model: str = None,
                          tags: list[str] = None):
        """Register a Workflow with the client service."""
        print_status(f"Registering workflow: {workflow_name}")
        data = WorkflowRegistrationData(
            workflow=workflow, workflow_name=workflow_name, entry_point=workflow_name,
            description=description, module=module, module_name=module_name,
            inputDescription=input_description, outputDescription=output_description,
            llmModel=llm_model, llmProvider=llm_provider,
            encoder=self._get_encoder(), tags=tags,
        )
        return self.webclient.register_Workflow(data)

    def run(self, workflow: Union[str, int, WorkflowGraph], input=None,
            process: g_vars.Process = g_vars.Process.SIMPLE,
            resources: list[str] = None, verbose: bool = True):
        """Execute a Workflow with the client service.

        ``workflow`` may be a registry name (str), a registry ID (int) or a
        :class:`WorkflowGraph` to run directly.
        """
        workflow_id = workflow if isinstance(workflow, int) else None
        workflow_name = workflow if isinstance(workflow, str) else None
        workflow_code = workflow if isinstance(workflow, WorkflowGraph) else None

        data = ExecutionData(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_code=workflow_code,
            input=input,
            resources=resources or [],
            process=process,
        )
        return self.webclient.run(data, verbose)

    def run_multiprocess(self, workflow: Union[str, int, WorkflowGraph], input=None,
                         resources: list[str] = None, verbose: bool = True):
        """Alternative for ``client.run(process=Process.MULTI)``."""
        return self.run(workflow, input, g_vars.Process.MULTI, resources, verbose)

    def run_dynamic(self, workflow: Union[str, int, WorkflowGraph], input=None,
                    resources: list[str] = None, verbose: bool = True):
        """Alternative for ``client.run(process=Process.DYNAMIC)``."""
        return self.run(workflow, input, g_vars.Process.DYNAMIC, resources, verbose)

    def get_PE(self, pe: Union[str, int], describe: bool = False):
        """Retrieve a PE from the registry."""
        data = self.webclient.get_PE(pe)
        if data and describe:
            self.describe(data[0], None, False)
        return data

    def get_Workflow(self, workflow: Union[str, int], describe: bool = False):
        """Retrieve a Workflow from the registry."""
        data = self.webclient.get_Workflow(workflow)
        if data and describe:
            # BUGFIX: describe the returned object, not the lookup key.
            self.describe(data[0], None, False)
        return data

    def get_PEs_By_Workflow(self, workflow: Union[str, int]):
        """Retrieve the PEs contained in a Workflow."""
        return self.webclient.get_PEs_By_Workflow(workflow)

    def get_Workflows(self):
        """Retrieve all Workflows."""
        return self.webclient.get_Workflows()

    def get_Registry(self, extended: bool = False):
        """Retrieve the full Registry."""
        return self.webclient.get_Registry(extended)

    def describe(self, obj: any, sc, include_source_code: bool = False):
        """Describe a PE or Workflow object.

        Parameters
        ----------
        obj : WorkflowGraph or PE
            Object to describe.
        sc : str
            Source code to show when ``include_source_code`` is True.
        include_source_code : bool
            Whether to print the source code (default: False).
        """
        if isinstance(obj, WorkflowGraph):
            self._describe_workflow(obj, sc, include_source_code)
        elif isinstance(obj, g_vars.PE_TYPES):
            self._describe_pe(obj, sc, include_source_code)
        else:
            raise TypeError("Requires an object of type WorkflowGraph or PE")

    @staticmethod
    def _pe_step_number(identifier: str):
        match = re.search(r"(\d+)$", identifier)
        return int(match.group(1)) if match else None

    def _describe_workflow(self, obj, sc, include_source_code):
        rows = [{
            "Step #": self._pe_step_number(o.id),
            "Name": o.name,
            "# Process": o.numprocesses,
            "Inputs": o.inputconnections,
            "Outputs": o.outputconnections,
        } for o in obj.get_contained_objects()]
        rows.sort(key=lambda x: (x["Step #"] is None, x["Step #"]))

        print_text(rows, tab=True)
        if include_source_code:
            print_status("\n Workflow Source Code:\n")
            print_code(sc)

    def _describe_pe(self, obj, sc, include_source_code):
        bases = type(obj).__bases__
        pe_state = {
            "Name": getattr(obj, "name", None),
            "PE Type": bases[0].__name__ if bases else "No name available",
        }
        for item, amount in obj.__dict__.items():
            if item not in ("wrapper", "pickleIgnore", "id", "name"):
                pe_state[item] = amount

        print_text([pe_state], tab=True)
        if include_source_code:
            print_status("\n PE Source Code:\n")
            print_code(sc)

    def search_Registry_Semantic(self, search: str, search_type: _TYPES = "pe"):
        """Semantic (text-embedding) search of the registry."""
        self._validate_search_type(search_type)
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Semantic searched for '{search}'")
        return self.webclient.search_similarity(data, query_type="text", embedding_type="llm")

    def code_Recommendation(self, search: str, search_type: _TYPES = "pe",
                            embedding_type: _E_TYPES = "spt"):
        """Code-similarity search of the registry."""
        if search_type == "workflow" and embedding_type == "llm":
            raise ValueError(
                f"Invalid combination: search_type '{search_type}' is only "
                f"compatible with embedding_type 'spt'."
            )
        self._validate_search_type(search_type)
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Code searched for '{search}'")
        return self.webclient.search_similarity(data, query_type="code",
                                                embedding_type=embedding_type)

    def search_Registry_Literal(self, search: str, search_type: _TYPES = "both"):
        """Literal (keyword) search of the registry."""
        self._validate_search_type(search_type)
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Literal searched for '{search}'")
        return self.webclient.search(data)

    def lexical_scores(self, kind: str, query: str, limit: int = 50) -> dict:
        """Return full-text-search scores keyed by ``(kind, id)``."""
        return self.webclient.lexical_scores(kind, query, limit)

    def update_Workflow_Description(self, workflow: Union[str, int], new_description):
        return self.webclient.update_workflow_description(workflow, new_description)

    def update_PE_Description(self, pe: Union[str, int], new_description):
        return self.webclient.update_pe_description(pe, new_description)

    def remove_PE(self, pe: Union[str, int]):
        """Remove a PE from the Registry."""
        return self.webclient.remove_PE(pe)

    def remove_Workflow(self, workflow: Union[str, int]):
        """Remove a Workflow from the Registry."""
        return self.webclient.remove_Workflow(workflow)

    def remove_All(self, type: str = "all"):
        """Remove all Workflows and/or PEs from the Registry.

        ``type`` is one of ``"all"``, ``"workflow"`` or ``"pe"``.
        """
        if type not in ("all", "workflow", "pe"):
            raise ValueError(f"Invalid type '{type}'; expected 'all', 'workflow' or 'pe'.")

        try:
            if type in ("all", "workflow"):
                workflow_ids, _ = self.webclient.get_ids()
                self._remove_each(workflow_ids, self.remove_Workflow, "workflow")
                if type == "workflow":
                    return "Finished removing Workflows"

            if type in ("all", "pe"):
                _, pe_ids = self.webclient.get_ids()
                self._remove_each(pe_ids, self.remove_PE, "PE")
                if type == "pe":
                    return "Finished removing PEs"

            return "Finished removing Workflows and PEs"
        except Exception as e:  # noqa: BLE001
            # BUGFIX: use the module logger; d4pClient has no ``self.logger``.
            logger.error(f"Error occurred while removing all workflows and/or PEs: {e}")
            return {"ApiError": {"message": str(e)}}

    @staticmethod
    def _remove_each(ids, remover, label):
        for obj_id in ids:
            try:
                remover(obj_id)
                print(f"Removed {label} {obj_id}")
            except Exception:  # noqa: BLE001
                print(f"The {label} {obj_id} couldn't be removed "
                      f"(it may be in use by another workflow).")