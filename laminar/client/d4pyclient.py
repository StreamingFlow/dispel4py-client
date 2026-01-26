from dispel4py.workflow_graph import WorkflowGraph
from typing_extensions import Literal, get_args
from typing import Union
import os

from laminar.client.web.client import *
import laminar.global_variables as g_vars

import laminar.screen_printer
from laminar.screen_printer import print_status, print_text, print_code

_TYPES = Literal["pe", "workflow", "both"]
_QUERY_TYPES = Literal["text", "code"]
_E_TYPES = Literal["llm", "spt"]

# valid semantic_search combinations
_valid_combinations = {"text": ["llm"], "code": ["llm", "spt"]}


class d4pClient:
    """Class to interact with registry and server services"""

    def __init__(self):
        user_name = os.getenv('LAMINAR_USERNAME')
        user_password = os.getenv('LAMINAR_PASSWORD')
        if user_name is not None and user_password is not None:
            self.login(user_name, user_password)

    def register(self, user_name: str, user_password: str):
        """ Register a user with the Registry service """
        data = AuthenticationData(user_name=user_name, user_password=user_password)
        return WebClient.register_User(self, data)

    def login(self, user_name: str, user_password: str):
        """Login user to use Register service"""
        data = AuthenticationData(user_name=user_name, user_password=user_password)
        return WebClient.login_User(self, data)

    def get_login(self):
        """Returns the username of the current user, or None if no user is logged in"""
        return g_vars.CLIENT_AUTH_ID if g_vars.CLIENT_AUTH_ID != "None" else None

    def register_PE(self, pe: g_vars.PE_TYPES, description: str = None):
        """Register a PE with the client service"""
        data = PERegistrationData(pe=pe, description=description)
        return WebClient.register_PE(self, data)

    def register_Workflow(self, workflow: WorkflowGraph, workflow_name: str, description: str = None, module=None,
                          module_name=None):
        """Register a Workflow with the client service"""
        data = WorkflowRegistrationData(workflow=workflow, entry_point=workflow_name, description=description,
                                        module=module, module_name=module_name)
        return WebClient.register_Workflow(self, data)

    def run(self, workflow: Union[str, int, WorkflowGraph], input=None, process=g_vars.Process,
            resources: list[str] = [], verbose=True):
        """Execute a Workflow with the client service"""
        workflow_id = None
        workflow_name = None
        workflow_code = None

        if isinstance(workflow, str):  # Name
            workflow_name = workflow
        elif isinstance(workflow, int):  # ID
            workflow_id = workflow
        elif isinstance(workflow, WorkflowGraph):  # Graph
            workflow_code = workflow

        data = ExecutionData(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_code=workflow_code,
            input=input,
            resources=resources,
            process=process
        )

        return WebClient.run(self, data, verbose)

    def run_multiprocess(self, workflow: Union[str, int, WorkflowGraph], input=None, resources: list[str] = [],
                         verbose=True):
        """Alternative for client.run(process=Process.MULTI)"""
        return self.run(workflow, input, g_vars.Process.MULTI, resources, verbose)

    def run_dynamic(self, workflow: Union[str, int, WorkflowGraph], input=None, resources: list[str] = [],
                    verbose=True):
        """Alternative for client.run(process=Process.DYNAMIC)"""
        return self.run(workflow, input, g_vars.Process.DYNAMIC, resources, verbose)

    def get_PE(self, pe: Union[str, int], describe: bool = False):
        """Retrieve PE from registry"""
        data = WebClient.get_PE(self, pe)
        if data:
            pe_obj = data[0]
            pe_sc = data[1]
            if describe and pe_obj:
                WebClient.describe(pe_obj)
        return data

    def get_Workflow(self, workflow: Union[str, int], describe: bool = False):
        """Retrieve Workflow from registry"""
        data = WebClient.get_Workflow(self, workflow)
        if data:
            workflow_obj = data[0]
            if describe and workflow_obj:
                WebClient.describe(self, workflow)
        return data

    def describe(self, obj: any, sc, include_source_code: bool = False):
        """Describe PE or Workflow object

        Parameters
        ----------
        obj: WorkflowGraph or PE
        Object to describe
        include_source_code: bool
        Whether to include the source code in the description (default: False)
        """

        def get_pe_id(s: str):
            import re
            match = re.search(r'(\d+)$', s)
            if match:
                digits = match.group(1)
                text = s[:match.start(1)]
                return int(digits)
            else:
                return None

        if isinstance(obj, WorkflowGraph):
            workflow_pes = [{
                "Step #": get_pe_id(o.id),
                "Name": o.name,
                "# Process": o.numprocesses,
                "Inputs": o.inputconnections,
                "Outputs": o.outputconnections,
            } for o in obj.get_contained_objects()]

            workflow_pes = sorted(workflow_pes, key=lambda x: x["Step #"])

            descr = obj.__doc__ if obj.__doc__ else "No description available."
            print_text(f"{descr}")
            print_text(workflow_pes, tab=True)

            if include_source_code:
                print_status("\n Workflow Source Code:\n")
                print_code(sc)

        elif isinstance(obj, g_vars.PE_TYPES):
            pe_state = {

                "Name": getattr(obj, "name"),
                "PE Type": type(obj).__bases__[0].__name__ if len(type(obj).__bases__) > 0 else "No name available",
            }

            for item, amount in obj.__dict__.items():
                if item in ["wrapper", "pickleIgnore", "id", "name"]:
                    continue
                pe_state[f"{item}"] = amount

            print_text([pe_state], tab=True)

            if include_source_code:
                print_status("\n PE Source Code:\n")
                print_code(sc)

        else:
            assert isinstance(obj, type), "Requires an object of type WorkflowGraph or PE"

    def search_Registry_Semantic(self, search: str, search_type: _TYPES = "pe"):
        """Semantic Search registry for workflows and pes"""

        query_type = "text"
        embedding_type = "llm"
        # Validate the search_type

        # Create the search data
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Semantic Searched for '{search}'")

        # Perform the search
        return WebClient.search_similarity(self, data, query_type, embedding_type)

    def code_Recommendation(self, search: str, search_type: _TYPES = "pe", embedding_type: _E_TYPES = "spt"):
        """Semantic Search registry for workflows and pes"""

        if search_type == "workflow" and embedding_type == "llm":
            raise ValueError(
                f"Invalid combination: search_type '{search_type}' is only compatible with embedding_type spt ")

        query_type = "code"
        # Validate the search_type
        options = get_args(_TYPES)
        assert search_type in options, f"'{search_type}' is not in {options}"

        # Create the search data
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Semantic Searched for '{search}'")

        # Perform the search
        return WebClient.search_similarity(self, data, query_type, embedding_type)

    def search_Registry_Literal(self, search: str, search_type: _TYPES = "both"):
        """Literal Search registry for workflow and pes"""
        options = get_args(_TYPES)
        assert search_type in options, f"'{search_type}' is not in {options}"
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Literal Searched for '{search}'")
        return WebClient.search(self, data)

    def remove_PE(self, pe: Union[str, int]):
        """Remove PE from Registry"""
        WebClient.remove_PE(self, pe)

    def remove_Workflow(self, workflow: Union[str, int]):
        """Remove Workflow from Registry"""
        WebClient.remove_Workflow(self, workflow)

    def get_PEs_By_Workflow(self, workflow: Union[str, int]):
        """Retrieve PEs in Workflow"""
        return WebClient.get_PEs_By_Workflow(self, workflow)

    def get_Workflows(self):
        """Retrieve all Workflow"""
        return WebClient.get_Workflows(self)

    def get_Registry(self):
        """Retrieve Registry"""
        return WebClient.get_Registry(self)

    def update_Workflow_Description(self, workflow: Union[str, int], new_description):
        return WebClient.update_workflow_description(self, workflow, new_description)

    def update_PE_Description(self, pe: Union[str, int], new_description):
        return WebClient.update_pe_description(self, pe, new_description)

    def remove_All(self, type: str = "all"):
        """Remove all Workflows and PEs from Registry"""
        try:
            if type == "all" or type == "workflow":
                # Remove all WFs
                (workflow_ids, pe_ids) = WebClient.get_ids(self)
                if len(workflow_ids) > 0:
                    for workflow_id in workflow_ids:
                        try:
                            self.remove_Workflow(workflow_id)
                            print("Removed wf %s" % workflow_id)
                        except:
                            print("The workflow %s couldnt be removed" % workflow_id)
                if type == "workflow":
                    return "Finished removing Workflows"
            if type == "all" or type == "pe":
                # Remove all PEs
                (workflow_ids, pe_ids) = WebClient.get_ids(self)
                if len(pe_ids) > 0:
                    for pe_id in pe_ids:
                        try:
                            self.remove_PE(pe_id)
                            print("Removed PE %s" % pe_id)
                        except:
                            print(
                                "The PE %s couldnt be removed. Problably it is been used by another workflow." % pe_id)
                if type == "pe":
                    return "Finished removing PEs"
                else:
                    return "Finished removing  Workflows and PEs"
        except Exception as e:
            self.logger.error(f"Error occurred while removing all workflows and/or PEs: {e}")
            return {"ApiError": {"message": str(e)}}
