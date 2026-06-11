import importlib.util
import time
import sys
import shlex
import argparse
import inspect

from dispel4py.base import GenericPE, IterativePE, ProducerPE, ConsumerPE
from dispel4py.workflow_graph import WorkflowGraph

from laminar.client.d4pyclient import d4pClient
from laminar.llms.LLMConnector import LLMConnector
from laminar.screen_printer import print_status, print_warning, print_error
from laminar.argument_parser import CustomArgumentParser

from laminar.llms.queries_templates import REGISTER_PE_CONTEXT_QUERIES, REGISTER_WORKFLOW_CONTEXT_QUERIES

PE_BASE_TYPES = (GenericPE, IterativePE, ProducerPE, ConsumerPE)


class RegisterCommand:

    def __init__(self, client: d4pClient, llmConnector: LLMConnector = None, loaded_modules={}):
        self.client = client
        self.module_counter = 0  # Initialize a counter for module names
        self.loaded_modules = loaded_modules
        self.AiConnector = llmConnector or LLMConnector()

    def _load_module(self, filepath):
        """Import the file at `filepath` under a unique name and track it."""
        unique_module_name = f"module_name_{int(time.time())}_{self.module_counter}"
        self.module_counter += 1

        spec = importlib.util.spec_from_file_location(unique_module_name, filepath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[unique_module_name] = mod  # Ensure module is in sys.modules
        spec.loader.exec_module(mod)
        self.loaded_modules[unique_module_name] = mod  # Store the loaded module

        return mod, unique_module_name

    @staticmethod
    def _is_pe_class(attr):
        return (isinstance(attr, type)
                and issubclass(attr, PE_BASE_TYPES)
                and attr not in PE_BASE_TYPES)

    def _discover_components(self, mod):
        """Return ({pe_name: pe_class}, {workflow_name: WorkflowGraph})."""
        pes, workflows = {}, {}
        for var in dir(mod):
            attr = getattr(mod, var)
            if self._is_pe_class(attr):
                pes[var] = attr
            elif isinstance(attr, WorkflowGraph):
                workflows[var] = attr
        return pes, workflows

    @staticmethod
    def _report_result(r):
        if r is None:
            print_warning("(Exists)")
        else:
            print_status(f"(ID {r})")

    @staticmethod
    def _cleanup_module(mod):
        """Drop references to instantiated PEs / workflows on the module."""
        for var in dir(mod):
            attr = getattr(mod, var)
            if isinstance(attr, (GenericPE, WorkflowGraph)):
                setattr(mod, var, None)

    def _register_single_pe(self, key, pe_class, model, provider):
        print_status(f"? {key} - {pe_class.__name__}")
        docstring = self.AiConnector.describe(
            component_name=key, kind="pe",
            code=inspect.getsource(pe_class),
            model=model, provider=provider,
            context_queries=REGISTER_PE_CONTEXT_QUERIES,
        )
        pe_instance = pe_class()
        r = self.client.register_PE(
            pe_instance,
            description=docstring["description"],
            input_description=docstring["inputs"],
            output_description=docstring["outputs"],
            llm_model=docstring["model"],
            llm_provider=docstring["provider"],
            tags=docstring["tags"],
        )
        self._report_result(r)

    def _register_single_workflow(self, key, workflow, mod, module_name, model, provider):
        source_code = f"entry {key}()\n"
        for pe in workflow.get_contained_objects():
            source_code += inspect.getsource(pe.__class__)

        print_status(f"? {key} - {type(workflow).__name__}")
        docstring = self.AiConnector.describe(
            component_name=key, kind="workflow",
            code=source_code,
            model=model, provider=provider,
            context_queries=REGISTER_WORKFLOW_CONTEXT_QUERIES,
        )
        r = self.client.register_Workflow(
            workflow=workflow, workflow_name=key,
            description=docstring["description"],
            module=mod, module_name=module_name,
            input_description=docstring["inputs"],
            output_description=docstring["outputs"],
            llm_model=docstring["model"],
            llm_provider=docstring["provider"],
            tags=docstring["tags"],
        )
        self._report_result(r)

    def _register_pe(self, filepath, provider: str = None, model: str = None):
        provider = provider or "openai"
        print_status(
            f"Registering PE from {filepath} using {provider} for LLM description generation.")

        try:
            mod, _ = self._load_module(filepath)
            pes, _ = self._discover_components(mod)

            if not pes:
                print_warning("Could not find any PEs")
                return

            for key, pe_class in pes.items():
                try:
                    self._register_single_pe(key, pe_class, model, provider)
                except Exception as e:
                    print_error(f"An error occurred during PE registration: {e}")

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}")
        except SyntaxError:
            print_error("Target file has invalid python syntax")
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def _register_workflow(self, filepath, provider: str = None, model: str = None):
        provider = provider or "openai"
        print_status(
            f"Registering workflow from {filepath} using {provider} for LLM description generation.")

        try:
            mod, unique_module_name = self._load_module(filepath)
            pes, workflows = self._discover_components(mod)

            if not pes and not workflows:
                print_warning("Could not find any PEs or Workflows")
                return

            for key, pe_class in pes.items():
                try:
                    self._register_single_pe(key, pe_class, model, provider)
                except Exception as e:
                    print_error(f"An error occurred during PE registration: {e}")

            for key, workflow in workflows.items():
                self._register_single_workflow(
                    key, workflow, mod, unique_module_name, model, provider)

            self._cleanup_module(mod)

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}")
        except SyntaxError:
            print_error("Target file has invalid python syntax")
        except Exception as e:
            print_error(f"An error occurred: {e}: {type(e).__name__}")

    def help(self):
        print_status("""
        Registers a new object within the Laminar registry.
        Remember to include all the imports necessary for those PEs within the file.

        Usage: register <type> <filepath>

        type          The category of object to register.
                            - 'workflow': Register a workflow, as well as all the 
                                          PEs that comprises the workflow within Laminar.,
                            - 'pe': Register a single PE.

        --provider   The LLM provider to use for description generation. Defaults to OpenAI.

        --model      The model to use for description generation. Defaults to gpt-4o.
        """)

    def register(self, args):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("type", choices=["workflow", "pe"])
        parser.add_argument("filepath")
        parser.add_argument("--provider", help="The LLM provider to use for description generation", required=False,
                            default=None)
        parser.add_argument("--model", help="The model to use for description generation", required=False, default=None)

        try:
            args = vars(parser.parse_args(shlex.split(args)))
            if args["type"] == "workflow":
                self._register_workflow(args["filepath"], model=args["model"], provider=args["provider"])
            else:
                self._register_pe(args["filepath"], model=args["model"], provider=args["provider"])
        except argparse.ArgumentError as e:
            print_error(e.message.replace("register_", ""))
