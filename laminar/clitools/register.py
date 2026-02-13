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

PE_CONTEXT_QUERIES = [
    "Return JSON only. Do not explain.",
    """Return JSON only, describing the code, the inputs and the outputs:
    {{
        'description': '...',
        'inputs':  '<input_name>:<description>\n...',
        'outputs': '<output_name>:<description>\n...',
    }}""",
    "The <input_name> and <output_name> arguments are placeholders for the channels used to communicate",
    "<description> is a placeholder for the description of the input or output",
    "If either no input or output is available, return null",
    "Ensure that the description contains all the information and is not verbose or repetitive"
]

WORKFLOW_CONTEXT_QUERIES = [
    "Return JSON only. Do not explain.",
    """Return JSON only, describing the code, the inputs and the outputs:
    {{
          'description': '...',
          'inputs':  '<input_name>:<description>\n...',
          'outputs': '<output_name>:<description>\n...',
    }}""",
    "The <input_name> and <output_name> arguments are placeholders for the workflow user inputs and workflow output",
    "<description> is a placeholder for the description of the input or output",
    "If either no input or output is available, return null",
    "Ensure that the description contains all the information and is not verbose or repetitive"
]


class RegisterCommand:

    def __init__(self, client: d4pClient, loaded_modules={}):
        self.client = client
        self.module_counter = 0  # Initialize a counter for module names
        self.loaded_modules = loaded_modules
        self.AiConnector = LLMConnector()

    def _register_pe(self, filepath, provider: str = None, model: str = None):

        if provider is None:
            provider = "openai"

        print_status(
            f"Registering PE from {filepath} using {provider} for LLM description generation.")

        try:
            unique_module_name = f"module_name_{int(time.time())}_{self.module_counter}"
            self.module_counter += 1

            spec = importlib.util.spec_from_file_location(unique_module_name, filepath)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[unique_module_name] = mod  # Ensure module is in sys.modules
            spec.loader.exec_module(mod)
            self.loaded_modules[unique_module_name] = mod  # Store the loaded module

            pes = {}
            for var in dir(mod):
                attr = getattr(mod, var)
                # Check if the attribute is a class and is a subclass of the PE types
                if isinstance(attr, type) and issubclass(attr, (GenericPE, IterativePE, ProducerPE,
                                                                ConsumerPE)) and attr not in (GenericPE, IterativePE,
                                                                                              ProducerPE, ConsumerPE):
                    pes[var] = attr
            if len(pes) == 0:
                print_warning("Could not find any PEs")
                return

            for key in pes:
                print_status(f"• {key} - {pes[key].__name__}")
                docstring = self.AiConnector.describe(component_name=key, kind="pe", code=inspect.getsource(pes[key]),
                                                      model=model,
                                                      provider=provider, context_queries=PE_CONTEXT_QUERIES)
                pe_class = pes[key]
                pe_instance = pe_class()

                try:
                    r = self.client.register_PE(pe_instance, description=docstring["description"],
                                                inputDescription=docstring["inputs"],
                                                outputDescription=docstring["outputs"], llmModel=docstring["model"],
                                                llmProvider=docstring["provider"])
                    if r is None:
                        print_warning("(Exists)")
                    else:
                        print_status(f"(ID {r})")
                except Exception as e:
                    print_error(f"An error occurred during PE registration: {e}")

        except Exception as e:
            print_error(f"An error occurred: {e}")

    def _register_workflow(self, filepath, provider: str = None, model: str = None):

        if provider is None:
            provider = "openai"

        print_status(
            f"Registering PE from {filepath} using {provider} for LLM description generation.")

        try:
            unique_module_name = f"module_name_{int(time.time())}_{self.module_counter}"
            self.module_counter += 1

            spec = importlib.util.spec_from_file_location(unique_module_name, filepath)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[unique_module_name] = mod  # Ensure module is in sys.modules
            spec.loader.exec_module(mod)
            self.loaded_modules[unique_module_name] = mod  # Store the loaded module

            pes = {}
            workflows = {}
            for var in dir(mod):
                attr = getattr(mod, var)
                if isinstance(attr, type) and issubclass(attr, (GenericPE, IterativePE, ProducerPE,
                                                                ConsumerPE)) and attr not in (GenericPE,
                                                                                              IterativePE,
                                                                                              ProducerPE,
                                                                                              ConsumerPE):
                    pes[var] = attr
                if isinstance(attr, WorkflowGraph):
                    workflows.update({var: attr})

            if len(pes) == 0 and len(workflows) == 0:
                print_warning("Could not find any PEs or Workflows")
                return

            for key in pes:
                print_status(f"• {key} - {type(pes[key]).__name__}")
                source_code = inspect.getsource(pes[key])
                docstring = self.AiConnector.describe(component_name=key, kind="pe", code=source_code,
                                                      model=model,
                                                      provider=provider, context_queries=PE_CONTEXT_QUERIES)
                pe_class = pes[key]
                pe_instance = pe_class()
                r = self.client.register_PE(pe_instance, description=docstring["description"],
                                            inputDescription=docstring["inputs"],
                                            outputDescription=docstring["outputs"], llmModel=docstring["model"],
                                            llmProvider=docstring["provider"])
                if r is None:
                    print_warning("(Exists)")
                else:
                    print_status(f"(ID {r})")

            for key in workflows:

                workflow = workflows[key]
                workflow_source_code = f"entry {key}()\n"
                for pe in workflow.get_contained_objects():
                    workflow_source_code += inspect.getsource(pe.__class__)

                print_status(f"• {key} - {type(workflows[key]).__name__}")
                docstring = self.AiConnector.describe(component_name=key,
                                                      kind="workflow",
                                                      code=workflow_source_code,
                                                      model=model,
                                                      provider=provider,
                                                      context_queries=WORKFLOW_CONTEXT_QUERIES)

                r = self.client.register_Workflow(workflow=workflows[key], workflow_name=key,
                                                  description=docstring["description"],
                                                  module=mod, module_name=unique_module_name,
                                                  inputDescription=docstring["inputs"],
                                                  outputDescription=docstring["outputs"], llmModel=docstring["model"],
                                                  llmProvider=docstring["provider"])
                if r is None:
                    print_warning("(Exists)")
                else:
                    print_status(f"(ID {r})")
            for var in dir(mod):
                attr = getattr(mod, var)
                if isinstance(attr, GenericPE):
                    setattr(mod, var, None)
                if isinstance(attr, WorkflowGraph):
                    setattr(mod, var, None)

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}")
        except SyntaxError:
            print_error(f"Target file has invalid python syntax")
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
