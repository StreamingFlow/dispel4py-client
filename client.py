from web_client import *
from globals import *
from dispel4py.base import *
from dispel4py.workflow_graph import WorkflowGraph
from dispel4py.visualisation import display
from typing_extensions import Literal, get_args
from web_client import WebClient
from typing import Union
import os

_TYPES = Literal["pe", "workflow", "both"]
_QUERY_TYPES = Literal["text", "code"]
_E_TYPES = Literal["llm", "ast"]

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
        return globals.CLIENT_AUTH_ID if globals.CLIENT_AUTH_ID != "None" else None

    def register_PE(self, pe: PE_TYPES, description: str = None):
        """Register a PE with the client service"""
        data = PERegistrationData(pe=pe, description=description)
        return WebClient.register_PE(self, data)

    def register_Workflow(self, workflow: WorkflowGraph, workflow_name: str, description: str = None, module= None, module_name = None):
        """Register a Workflow with the client service"""
        data = WorkflowRegistrationData(workflow=workflow, entry_point=workflow_name, description=description, module=module, module_name = module_name)
        return WebClient.register_Workflow(self, data)

    def run(self, workflow: Union[str, int, WorkflowGraph], input=None, process=Process.SIMPLE, resources: list[str] = [], verbose=True):
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

    def run_multiprocess(self, workflow: Union[str, int, WorkflowGraph], input=None, resources: list[str] = [], verbose=True):
        """Alternative for client.run(process=Process.MULTI)"""
        return self.run(workflow, input, Process.MULTI, resources, verbose)

    def run_dynamic(self, workflow: Union[str, int, WorkflowGraph], input=None, resources: list[str] = [], verbose=True):
        """Alternative for client.run(process=Process.DYNAMIC)"""
        return self.run(workflow, input, Process.DYNAMIC, resources, verbose)

    def get_PE(self, pe: Union[str, int], describe: bool = False):
        """Retrieve PE from registry"""
        pe_obj = WebClient.get_PE(self, pe)
        if describe and pe_obj:
            WebClient.describe(pe_obj)
        return pe_obj

    def get_Workflow(self, workflow: Union[str, int], describe: bool = False):
        """Retrieve Workflow from registry"""
        workflow_obj = WebClient.get_Workflow(self, workflow)
        if describe and workflow_obj:
            WebClient.describe(self, workflow)
        return workflow_obj

    def describe(self, obj: any):
        """Describe PE or Workflow object

        Parameters
        ----------
        obj: WorkflowGraph or PE
        Object to describe
        """

        if isinstance(obj, WorkflowGraph):
            workflow_pes = [o.name for o in obj.get_contained_objects()]
            print("PEs in Workflow:", workflow_pes)
            descr = obj.__doc__ if obj.__doc__ else "No description available."
            print(descr)

        elif isinstance(obj, PE_TYPES):
            print("PE name:", getattr(obj, "name"))

            for item, amount in obj.__dict__.items():
                if item in ["wrapper", "pickleIgnore", "id", "name"]:
                    continue

                print("{}: {} ".format(item, amount))

        else:
            assert isinstance(obj, type), "Requires an object of type WorkflowGraph or PE"


    def search_Registry(self, search: str, search_type: _TYPES = "pe", query_type: _QUERY_TYPES = "text", embedding_type: _E_TYPES = "llm" ):
        """Semantic Search registry for workflow"""
        options = get_args(_TYPES)
        assert search_type in options, f"'{search_type}' is not in {options}"
        data = SearchData(search=search, search_type=search_type)
        logger.info(f"Semantic Searched for '{search}'")
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

    def update_workflow_description(self, workflow: Union[str, int], new_description):
        return WebClient.update_workflow_description(self, workflow, new_description)

    def update_pe_description(self, pe: Union[str, int], new_description):
        return WebClient.update_pe_description(self, pe, new_description)

    def remove_all(self, type: str = "all"):
        """Remove all Workflows and PEs from Registry"""
        try:
            if type == "all" or type == "workflow":
                # Remove all WFs
                (workflow_ids, pe_ids) = WebClient.get_ids(self)
                if len(workflow_ids)>0:
                    for workflow_id in workflow_ids:
                        try:
                            self.remove_Workflow(workflow_id)
                            print("Removed wf %s" %workflow_id)
                        except:
                            print("The workflow %s couldnt be removed" %workflow_id)
                if type == "workflow":
                    return "Finished removing Workflows"
            if type == "all" or type == "pe":    
                # Remove all PEs
                (workflow_ids, pe_ids) = WebClient.get_ids(self)
                if len(pe_ids) > 0:
                    for pe_id in pe_ids:
                        try:
                            self.remove_PE(pe_id)
                            print("Removed PE %s" %pe_id)
                        except:
                            print("The PE %s couldnt be removed. Problably it is been used by another workflow." %pe_id)
                if type == "pe":
                    return "Finished removing PEs"
                else:
                    return "Finished removing  Workflows and PEs"
        except Exception as e:
            self.logger.error(f"Error occurred while removing all workflows and/or PEs: {e}")
            return {"ApiError": {"message": str(e)}}
