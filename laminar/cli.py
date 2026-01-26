import argparse
import ast
import cmd
import importlib.util
import shlex
import sys
import time
import pwinput

from dispel4py.workflow_graph import WorkflowGraph
from dispel4py.base import *
from laminar.screen_printer import *
from laminar.argument_parser import CustomArgumentParser
from laminar.client.d4pyclient import d4pClient
from laminar.global_variables import Process


def type_checker(value):
    if value.isdigit():
        return int(value)
    return value


class LaminarCLI(cmd.Cmd):

    def __init__(self):
        clear_terminal()
        super().__init__()
        self.prompt = "\033[1m(laminar) > \033[0m"
        self.intro = """
        \033[36m
          _                    _                             ____ _     ___ 
         | |    __ _ _ __ ___ (_)_ __   __ _ _ __           / ___| |   |_ _|
         | |   / _` | '_ ` _ \\| | '_ \\ / _` | '__|  _____  | |   | |    | | 
         | |__| (_| | | | | | | | | | | (_| | |    |_____| | |___| |___ | | 
         |_____\\__,_|_| |_| |_|_|_| |_|\\__,_|_|             \\____|_____|___|
        \033[0m

        \033[1m                 Welcome to the Laminar CLI!\033[0m
        """

        self.loaded_modules = {}  # Initialize the loaded_modules dictionary
        self.module_counter = 0  # Initialize a counter for module names
        self.client = d4pClient()

        if self.client.get_login() is not None:
            print_status(f"Logged in as {self.client.get_login()}")
        else:
            while self.client.get_login() is None:
                username = input("Username: ")
                password = pwinput.pwinput("Password: ")
                self.client.login(username, password)
                if self.client.get_login() is None:
                    print_error("Invalid login")
            clear_terminal()

        self.load_modules_on_startup()

    def cmdloop(self, intro=None):
        try:
            super().cmdloop(intro)
        except KeyboardInterrupt:
            print_warning("\nExiting Laminar CLI.")

    def load_modules_on_startup(self):
        # Load modules from the registry
        workflows = self.client.get_Workflows()
        for workflow in workflows:
            module_source_code = workflow['moduleSourceCode']
            if module_source_code:
                if workflow['moduleName']:
                    module_name = workflow['moduleName']
                else:
                    module_name = "tmp"
                spec = importlib.util.spec_from_loader(module_name, loader=None)
                mod = importlib.util.module_from_spec(spec)
                exec(module_source_code, mod.__dict__)
                sys.modules[module_name] = mod
                self.loaded_modules[module_name] = mod

    def do_literal_search(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe", "both"], default="both")
        parser.add_argument("search_term")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = self.client.search_Registry_Literal(args["search_term"], args["search_type"])
            print_text(feedback[0], tab=True)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "literal_search"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_literal_search(self):
        print_text("""
        Searches the registry for workflows and processing elements matching the search term in the name or description.
        
        Arguments:
          search_type   Type of items to search for. Choices are:
                        - 'workflow': Search only for workflows
                        - 'pe': Search only for processing elements (PEs)
                        - 'both': Search for both workflows and PEs (default)
          search_term   The term to search for in the registry.
          
        Usage:
          literal_search [workflow|pe|both] [string]
        
        Examples:
          literal_search workflow some_term
          literal_search pe some_term
          literal_search both some_term
          
        """)

    def do_semantic_search(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe"], default="pe")
        parser.add_argument("search_term")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = self.client.search_Registry_Semantic(args["search_term"], args["search_type"])
            print_text(feedback)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "semantic_search"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_semantic_search(self):
        print_text("""
        Searches the registry for workflows and processing elements matching semantically the search term.
        
        Arguments:
          search_type   Type of items to search for. Choices are:
                        - 'workflow': Search only for workflows
                        - 'pe': Search only for processing elements (PEs)
                        
          search_term   The term to search for in the registry.      
                    
        Usage:
          semantic_search [workflow|pe] [search_term]
        
        Examples:
          semantic_search workflow some_term 
          semantic_search pe some_term 
        """)

    def do_code_recommendation(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe"], default="pe")
        parser.add_argument("code_snippet")
        parser.add_argument("--embedding_type", choices=["llm", "spt"], default="spt")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = self.client.code_Recommendation(args["code_snippet"], args["search_type"],
                                                       args["embedding_type"])
            print_text(feedback)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "code_recommendation"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_code_recommendation(self):
        print_text("""
        Provides code recommdations from registered workflows and processing elements matching the code snippet.

        Arguments:
          search_type   Type of items to search for. Choices are:
                        - 'workflow': Search only for workflows
                        - 'pe': Search only for processing elements (PEs)
          code_snippet   The code_snippet to get recommendations from the registry.

        Options:
          --embedding_type  The type of embedding to use. Choices are:
                        - 'spt': Perform a search based on SPT features
                        - 'llm': Perform a search based on LLM-generated embeddings

        Note: code recommdations for workflows only possible with 'spt' embedding_type 

        Usage:
          semantic_search [workflow|pe] [code_snippet] [--embedding_type llm|spt]

        Examples:
          code_recommendation pe code_snippet --embedding_type spt
          code_recommendation workfkow code_snippet --embedding_type spt
          code_recommendation pe code_snippett --embedding_type llm
        """)

    def do_run(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier", type=type_checker)
        parser.add_argument("--rawinput", action="store_true")
        parser.add_argument("-v", "--verbose", action="store_true")
        parser.add_argument("-i", "--input", dest="input", required=False)
        parser.add_argument("-r", "--resource", action="append", required=False)
        parser.add_argument("--multi", action="store_true")
        parser.add_argument("--dynamic", action="store_true")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            if not isinstance(args["resource"], list):
                args["resource"] = []
            try:
                id = int(args["identifier"])
                inputVal = args["input"] if args["rawinput"] or args["input"] is None else ast.literal_eval(
                    args["input"])
                runType = Process.MULTI if args["multi"] else Process.DYNAMIC if args["dynamic"] else Process.SIMPLE

                feedback = self.client.run(id, input=inputVal, verbose=args["verbose"], resources=args["resource"],
                                           process=runType)
                if feedback is not False:
                    print_text(feedback)
                else:
                    print_error(f"No workflow is registered with ID {id}")
            except:
                inputVal = args["input"] if args["rawinput"] or args["input"] is None else ast.literal_eval(
                    args["input"])
                runType = Process.MULTI if args["multi"] else Process.DYNAMIC if args["dynamic"] else Process.SIMPLE
                feedback = self.client.run(args["identifier"], input=inputVal, verbose=args["verbose"],
                                           resources=args["resource"], process=runType)

                print_text(feedback) if feedback is not False else print_warning(
                    f"No workflow is registered with name {args['identifier']}")


        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "run"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_run(self):
        print_text("""
        Runs a workflow in the registry based on the provided name or ID.

        Usage:
            run identifier [options]

        Options:
            identifier               Name or ID of the workflow to run
            --rawinput               Treat input as a raw string instead of evaluating it
            -v, --verbose            Enable verbose output
            -i, --input <data>       Input data for the workflow
            -r, --resource <resource> Specify resources required by the workflow (can be used multiple times)
            --multi                  Run the workflow in parallel using multiprocessing
            --dynamic                Run the workflow in parallel using Redis

        Examples:
            run my_workflow -i '[{"input" : "1,2,3"}]' 
            run my_workflow -i 100 --dynamic -v
            run 123 --input "[{"input" : "1,2,3"}]" --multi --verbose
            run my_workflow --dynamic --resource file1.txt --resource file2.txt
        """)

    def do_register_workflow(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("filepath")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            try:
                unique_module_name = f"module_name_{int(time.time())}_{self.module_counter}"
                self.module_counter += 1

                spec = importlib.util.spec_from_file_location(unique_module_name, args["filepath"])
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
                if len(pes) > 0:
                    print_status("Found PEs")
                for key in pes:
                    print_status(f"• {key} - {type(pes[key]).__name__}")
                    docstring = pes[key].__doc__
                    pe_class = pes[key]
                    pe_instance = pe_class()
                    r = self.client.register_PE(pe_instance, docstring)
                    if r is None:
                        print_warning("(Exists)")
                    else:
                        print_status(f"(ID {r})")
                if len(workflows) > 0:
                    print_status("Found workflows")
                for key in workflows:
                    print_status(f"• {key} - {type(workflows[key]).__name__}")
                    docstring = workflows[key].__doc__
                    if "A graph representing the workflow and related methods" in docstring:
                        docstring = None
                    r = self.client.register_Workflow(workflows[key], key, docstring, mod, unique_module_name)
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
                print_error(f"Could not find file at {args['filepath']}")
            except SyntaxError:
                print_error(f"Target file has invalid python syntax")
            except Exception as e:
                print_error(f"An error occurred: {e}")
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "register_workflow"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_register_workflow(self):
        print_status("""
        Registers all workflows and PEs instantiated within a given file input.
        Remember to include all the imports necessary for those PEs within the file.
        
        Usage: register_workflow [file.py]
        """)

    def do_register_pe(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("filepath")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            unique_module_name = f"module_name_{int(time.time())}_{self.module_counter}"
            self.module_counter += 1

            spec = importlib.util.spec_from_file_location(unique_module_name, args["filepath"])
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
                print_status(f"• {key} - {pes[key].__name__}", end=" ")
                pe_instance = pes[key]()
                docstring = pes[key].__doc__
                pe_class = pes[key]
                pe_instance = pe_class()

                try:
                    r = self.client.register_PE(pe_instance, docstring)
                    if r is None:
                        print_warning("(Exists)")
                    else:
                        print_status(f"(ID {r})")
                except Exception as e:
                    print_error(f"An error occurred during PE registration: {e}")
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "register_pe"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_register_pe(self):
        print_text("""
        Registers all PEs instantiated within a given file input.
        Remember to include all the imports necessary for those PEs within the file.
         
        Usage: register_pe [file.py]
        """)

    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        print_text("Exits the Laminar CLI")

    def do_list(self, arg):
        try:
            description, registry = self.client.get_Registry()
            if description:
                print_text(description, tab=True)
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_list(self):
        print_text("Lists all registered PEs and workflows")

    def do_remove_pe(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("pe_identifier", nargs='?', type=type_checker)
        parser.add_argument("--all", action="store_true", help="Remove all processing elements")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            if args["all"]:
                confirmation = input("Are you sure you want to remove all processing elements? [Y/N]: ")
                if confirmation.lower() == 'y':
                    type_remove = "pe"
                    response = self.client.remove_All(type=type_remove)
                    if response is None:
                        print_error("No response from server.")
                    elif 'ApiError' in response:
                        print_error(f"Error: {response['ApiError']['message']}")
                    else:
                        print_text(response)
                else:
                    print_warning("Operation cancelled by user.")
            else:
                if args["pe_identifier"] is None:
                    print_error("Error: Missing processing element identifier. Use --all to remove all processing elements.")
                    return
                try:
                    response = self.client.remove_PE(args["pe_identifier"])
                    if 'ApiError' in response:
                        print_error(f"Error: {response['ApiError']['message']}.")
                    else:
                        print_status("Processing Element removed successfully")
                except Exception as e:
                    print_error(f"An error occurred while removing the PE: {e}")
                    if "NoneType" in str(e):
                        print_error(
                            "Problably you are trying to remove a workflow instead of a processing element. Use remove_workflow <id> instead. Or the PE <id> does not exit.")
                    else:
                        print_error(
                            "Probably the processing element is being used by a workflow. Try to remove the workflow first.")

        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "remove_pe"))
        except TypeError:
            # Specific catch for the 'NoneType' error that shouldn't be printed
            pass
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_remove_pe(self):
        print_text("""
        Removes a processing element by its name or ID, or removes all processing elements if --all is specified.
        
        Usage: remove_pe [pe_identifier] [--all]
        """)

    def do_remove_workflow(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("workflow_identifier", nargs='?', type=type_checker)
        parser.add_argument("--all", action="store_true", help="Remove all workflows")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            if args["all"]:
                confirmation = input("Are you sure you want to remove all workflows? [Y/N]: ")
                if confirmation.lower() == 'y':
                    type_remove = "workflow"
                    response = self.client.remove_All(type_remove)
                    if response is None:
                        print_error("No response from server.")
                    elif 'ApiError' in response:
                        print_error(f"Error: {response['ApiError']['message']}")
                    else:
                        print_status(response)

                else:
                    print_warning("Operation cancelled by user.")
            else:
                if args["workflow_identifier"] is None:
                    print_error("Error: Missing workflow identifier. Use --all to remove all workflows.")
                    return

                response = self.client.remove_Workflow(args["workflow_identifier"])
                if 'ApiError' in response:
                    print_error(f"Error: {response['ApiError']['message']}")
                else:
                    print_status("Workflow removed successfully")
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "remove_workflow"))
        except TypeError:
            # Specific catch for the 'NoneType' error that shouldn't be printed
            pass
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_remove_workflow(self):
        print_text("""
        Removes a workflow by its name or ID, or removes all workflows if --all is specified.
        
        Usage: remove_workflow [workflow_identifier] [--all]
        """)

    def do_describe(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier", type=type_checker)
        parser.add_argument("--source_code", "-sc", action="store_true",
                            help="Include the source code in the description")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            data = self.client.get_PE(args["identifier"]) or self.client.get_Workflow(args["identifier"])
            if data:
                obj = data[0]
                sc = data[1]
                self.client.describe(obj, sc, include_source_code=args["source_code"])
            else:
                print_warning(f"No description found for '{args['identifier']}'")
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "describe"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_describe(self):
        print_text("""
        It provides the information on PEs or workflow by its name 
        
        Usage: describe [identifier] [--source_code | -sc]
        """)

    def do_update_workflow_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("workflow_id", type=type_checker)
        parser.add_argument("new_description", type=str)
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = self.client.update_Workflow_Description(args["workflow_id"], args["new_description"])
            print_status(feedback)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "update_workflow_description"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_update_workflow_description(self):
        print_text("""
        Updates the description of a workflow by Id. 
        
        Usage: update_workflow_description [workflow_id] [new_description]
        """)

    def do_update_pe_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("pe_id", type=type_checker)
        parser.add_argument("new_description", type=str)
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = self.client.update_PE_Description(args["pe_id"], args["new_description"])
            print_status(feedback)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "update_pe_description"))
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help_update_pe_description(self):
        print_text("""
        Updates the description of a PE by Id 
        
        Usage: update_pe_description [pe_id] [new_description]
        """)

    def do_remove_all(self, arg):
        confirmation = input("Are you sure you want to remove all workflows and processing elements? [Y/N]: ")
        if confirmation.lower() == 'y':
            try:
                response = self.client.remove_All()
                if response is None:
                    print_error("No response from server.")
                elif 'ApiError' in response:
                    print_error(f"Error: {response['ApiError']['message']}")
                else:
                    print_error(response)
            except Exception as e:
                print_error(f"An error occurred: {e}")
        else:
            print_warning("Operation cancelled by user.")

    def help_remove_all(self):
        print_text("""
        Removes all workflows and Pocessing Elements registered by the user 
        
        Usage: remove_all
        """)
