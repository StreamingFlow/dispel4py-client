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


class d4pClient:
    """Class to interact with registry 
    and server services"""

    def __init__(self):
        user_name = os.getenv('LAMINAR_USERNAME')
        user_password = os.getenv('LAMINAR_PASSWORD')
        if user_name is not None and user_password is not None:
            self.login(user_name, user_password)

    def register(self, user_name: str, user_password: str):
        """ Register a user with the Registry service 

        Parameters
        ----------
        user_name:str
            Username
        user_password: str
            User password

        Return 
        ------
        user_name: str
            Username
        """

        data = AuthenticationData(
            user_name=user_name,
            user_password=user_password
        )

        return WebClient.register_User(self, data)

    def login(self, user_name: str, user_password: str):
        """Login user to use Register service 

        Parameters
        ----------
        user_name:str
            Username
        user_password: str
            User password

        Return 
        ------
        user_name: str
            Username
        """

        data = AuthenticationData(
            user_name=user_name,
            user_password=user_password
        )

        return WebClient.login_User(self, data)

    def get_login(self):
        """Returns the username of the current user, or None if no user is logged in

        Return
        ------
        user_name: str | None
            Username
        """

        return globals.CLIENT_AUTH_ID if globals.CLIENT_AUTH_ID != "None" else None

    def register_PE(self, pe: PE_TYPES, description: str = None):
        """Register a PE with the client service
        
        Parameters
        ----------
        pe: dispel4py Processing Element
           PE object 
        description: str
            Description of PE

        Return 
        -------
        id: int
            ID for registered PE
        """

        data = PERegistrationData(
            pe=pe,
            description=description
        )

        return WebClient.register_PE(self, data)

    def register_Workflow(self, workflow: WorkflowGraph, workflow_name: str, description: str = None):
        """Register a Workflow with the client service 

        Parameters 
        ----------
        workflow: dispel4py WorkflowGraph
                Workflow object
        workflow_name: str 
                Entrypoint of workflow 
        description: str 
                Description of workflow 
        Return 
        -------
        id: int
                ID for registered workflow 
        """

        data = WorkflowRegistrationData(
            workflow=workflow,
            entry_point=workflow_name,
            description=description
        )

        return WebClient.register_Workflow(self, data)

    def run(self, workflow: Union[str, int, WorkflowGraph], input=None, process=Process.SIMPLE, resources: list[str] = [],
            verbose=True):
        """Execute a Workflow with the client service 

        Parameters 
        ----------
        workflow: int/str/WorkflowGraph
                Workflow to execute 
        input: any 
                Input to execute
        process: Process (Simple/Multi/Dynamic) 
                Execution method
        resources: list[str] 
                The paths of any files or directories necessary for workflow execution 
        verbose: bool
                Whether or not to print the outputs produced by the program
        Return 
        -------
        result: str
                Output from executing workflow 

        """

        workflow_id = None
        workflow_name = None
        workflow_code = None

        if isinstance(workflow, str):  # Name
            workflow_name = workflow
        elif isinstance(workflow, int):  # ID
            workflow_id = workflow
        elif isinstance(workflow, WorkflowGraph):  # Graph
            workflow_code = workflow

        if input is None:
            # todo do something
            None

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
        """
            Alternative for client.run(process=Process.MULTI)
        """
        return self.run(workflow, input, Process.MULTI, resources, verbose)

    def run_dynamic(self, workflow: Union[str, int, WorkflowGraph], input=None, resources: list[str] = [],
                    verbose=True):
        """
            Alternative for client.run(process=Process.DYNAMIC)
        """
        return self.run(workflow, input, Process.DYNAMIC, resources, verbose)

    def get_PE(self, pe: Union[str, int], describe: bool = False):
        """Retrieve PE from resgistry 

        Parameters 
        ----------
        pe: str/int
            Name or ID of PE to retrieve
        describe: bool 
            True - provides description of PE   
        Return 
        -------
        PE: Class 
            PE Class
        """

        pe_obj = WebClient.get_PE(self, pe)

        if describe and pe_obj:
            WebClient.describe(pe_obj)

        return pe_obj

    def get_Workflow(self, workflow: Union[str, int], describe: bool = False):
        """Retrieve Workflow from resgistry 

        Parameters 
        ----------
        workflow: str/int
            Name or ID of Workflow to retrieve
        describe: bool 
            True - provides description of Workflow  

        Return 
        -------
        Workflow: WorkflowGraph 
            Workflow Class
        """
        workflow_obj = WebClient.get_Workflow(self, workflow)

        if describe and workflow_obj:
            WebClient.describe(self, workflow)

        return workflow_obj

    def search_Registry(self, search: str, search_type: _TYPES = "both", query_type: _QUERY_TYPES = "text"):
        """Search registry for workflow 
        
        Parameters
        ----------
        search: str
           Search string 
        includePE: "both"/"pe"/"workflow" 
            "both" - Searches registry for both workflow or PE 
            "pe" - Only searches for PE 
            "workflow" - Only searches for workflow
        Return 
        -------
        results: list 
            List of Workflow and/or PE objects  
        """

        options = get_args(_TYPES)
        assert search_type in options, f"'{search_type}' is not in {options}"

        data = SearchData(
            search=search,
            search_type=search_type,
        )

        logger.info("Searched for \"" + search + "\"")

        # Performing search similarity for PEs
        if search_type == "pe":
            return WebClient.search_similarity(self, data, query_type)
        else:
            return WebClient.search(self, data)

    def update_description(self, identifier: Union[str, int], new_description: str):
        """Update the description of a PE or Workflow

        Parameters
        ----------
        identifier: str/int
            Name or ID of the PE or Workflow to update
        new_description: str
            New description to set

        Return
        ------
        bool
            True if update was successful, False otherwise
        """
        if isinstance(identifier, str):
            if identifier in self.get_Registry():
                for item in self.get_Registry():
                    if item.name == identifier:
                        item.description = new_description
                        print(f"Updated description for {item.__class__.__name__.lower()} '{identifier}': {new_description}")
                        return True
        elif isinstance(identifier, int):
            registry = self.get_Registry()
            if registry and identifier <= len(registry):
                registry[identifier - 1].description = new_description
                print(f"Updated description for {registry[identifier - 1].__class__.__name__.lower()} with ID {identifier}: {new_description}")
                return True
        return False

    def describe(self, obj: any):
        """Describe PE or Workflow object

        Parameters
        ----------
        obj: WorkflowGraph or PE
            Object to describe
        """

        if isinstance(obj, WorkflowGraph):
            workflow_pes = [o.name for o in obj.get_contained_objects()]
            print("Workflow Name:", obj.name)
            print("Description:", getattr(obj, "description", "No description available."))
            print("PEs in Workflow:", workflow_pes)

        elif isinstance(obj, PE_TYPES):
            print("PE name:", getattr(obj, "name"))

            for item, amount in obj.__dict__.items():
                if item in ["wrapper", "pickleIgnore", "id", "name"]:
                    continue

                print("{}: {} ".format(item, amount))

        else:
            assert isinstance(obj, type), "Requires an object of type WorkflowGraph or PE"

    def remove_PE(self, pe: Union[str, int]):
        """Remove PE from Registry
        
            Parameters
            ----------
            pe: str/int
                PE Name or ID to remove 
        """
        WebClient.remove_PE(self, pe)

    def remove_Workflow(self, workflow: Union[str, int]):
        """Remove Workflow from Registry  
        
            Parameters
            ----------
            workflow: str/int
                Workflow Name or ID to remove 
        """
        WebClient.remove_Workflow(self, workflow)

    def get_PEs_By_Workflow(self, workflow: Union[str, int]):
        """Retrieve PEs in Workflow 

        Parameters 
        ----------
        workflow: str/int
            Name or ID of Workflow to retrieve
         
        Return 
        -------
        pes: list 
            List of PEs
        """

        return WebClient.get_PEs_By_Workflow(self, workflow)

    def get_Registry(self):
        """Retrieve Registry 

        Return 
        -------
        registry: list 
            List of PEs/Workflows
        """

        return WebClient.get_Registry(self)

