# Laminar CLI

import cmd
import sys
import argparse
import shlex
import ast
from typing import IO
import pwinput
import importlib.util
import time  

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # gets the libraries to write less garbage to the terminal
from client import d4pClient, Process
from dispel4py.base import GenericPE, IterativePE, ProducerPE, ConsumerPE, WorkflowGraph

client = d4pClient()

def type_checker(value):
    if value.isdigit():
        return int(value)
    return value

class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, exit_on_error=True):
        super().__init__(exit_on_error=exit_on_error)

    def exit(self, status=0, message=None):
        if self.exit_on_error:
            sys.exit(status)
        else:
            raise argparse.ArgumentError(None, message=message)


class LaminarCLI(cmd.Cmd):
    def __init__(self):
        super().__init__()
        self.prompt = "(laminar) "
        self.intro = """Welcome to the Laminar CLI"""
        self.loaded_modules = {}  # Initialize the loaded_modules dictionary
        self.module_counter = 0  # Initialize a counter for module names
        self.load_modules_on_startup()


    def load_modules_on_startup(self):
    # Load modules from the registry
        workflows = client.get_Workflows()
        for workflow in workflows:
            module_source_code = workflow['moduleSourceCode']
            if module_source_code:
                if  workflow['moduleName']:
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
            feedback = client.search_Registry_Literal(args["search_term"], args["search_type"])
            print(feedback)
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "literal_search"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_literal_search(self):
        print("Searches the registry for workflows and processing elements matching the search term in the name or description.")
        print()
        print("Arguments:")
        print("  search_type   Type of items to search for. Choices are:")
        print("                - 'workflow': Search only for workflows")
        print("                - 'pe': Search only for processing elements (PEs)")
        print("                - 'both': Search for both workflows and PEs (default)")
        print("  search_term   The term to search for in the registry.")
        print()
        print("Usage:")
        print("  literal_search [workflow|pe] [string]")
        print()
        print("Examples:")
        print("  literal_search workflow some_term")
        print("  literal_search pe some_term")
        print("  literal_search both some_term")


    def do_semantic_search(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe"], default="pe")
        parser.add_argument("search_term")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = client.search_Registry_Semantic(args["search_term"], args["search_type"])
            print(feedback)
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "semantic_search"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_semantic_search(self):
        print("Searches the registry for workflows and processing elements matching semantically the search term.")
        print()
        print("Arguments:")
        print("  search_type   Type of items to search for. Choices are:")
        print("                - 'workflow': Search only for workflows")
        print("                - 'pe': Search only for processing elements (PEs)")
        print("  search_term   The term to search for in the registry.")
        print()
        print("Usage:")
        print("  semantic_search [workflow|pe] [search_term] ")
        print()
        print("Examples:")
        print("  semantic_search workflow some_term ")
        print("  semantic_search pe some_term ")


    def do_code_recommendation(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe"], default="pe")
        parser.add_argument("code_snippet")
        parser.add_argument("--embedding_type", choices=["llm", "ast"], default="ast")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = client.code_Recommendation(args["code_snippet"], args["search_type"], args["embedding_type"])
            print(feedback)
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "code_recommendation"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_code_recommendation(self):
        print("Provides code recommdations from registered workflows and processing elements matching the code snippet.")
        print()
        print("Arguments:")
        print("  search_type   Type of items to search for. Choices are:")
        print("                - 'workflow': Search only for workflows")
        print("                - 'pe': Search only for processing elements (PEs)")
        print("  code_snippet   The code_snippet to get recommendations from the registry.")
        print()
        print("Options:")
        print("  --embedding_type  The type of embedding to use. Choices are:")
        print("                - 'ast': Perform a search based on AST features (ast)")
        print("                - 'llm': Perform a search based on LLM-generated embeddings")
        print()
        print("Note: code recommdations for workflows only possible with 'ast' embedding_type ")
        print()
        print("Usage:")
        print("  semantic_search [workflow|pe] [code_snippet] [--embedding_type llm|ast]")
        print()
        print("Examples:")
        print("  code_recommendation pe code_snippet --embedding_type ast")
        print("  code_recommendation pe code_snippett --embedding_type llm")
        print("  code_recommendation workfkow code_snippet --embedding_type ast")

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
                inputVal = args["input"] if args["rawinput"] or args["input"] is None else ast.literal_eval(args["input"])
                runType = Process.SIMPLE
                if args["multi"]:
                    runType = Process.MULTI
                elif args["dynamic"]:
                    runType = Process.DYNAMIC
                feedback = client.run(id, input=inputVal, verbose=args["verbose"], resources=args["resource"], process=runType)
                if feedback is not False:
                    print(feedback)
                else:
                    print(f"No workflow is registered with ID {id}")
            except:
                inputVal = args["input"] if args["rawinput"] or args["input"] is None else ast.literal_eval(args["input"])
                runType = Process.SIMPLE
                if args["multi"]:
                    runType = Process.MULTI
                elif args["dynamic"]:
                    runType = Process.DYNAMIC
                feedback = client.run(args["identifier"], input=inputVal, verbose=args["verbose"], resources=args["resource"], process=runType)
                if feedback is not False:
                    print(feedback)
                else:
                    print(f"No workflow is registered with name {args['identifier']}")
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "run"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_run(self):
        print("Runs a workflow in the registry based on the provided name or ID")

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
                    if isinstance(attr, type) and issubclass(attr, (GenericPE, IterativePE, ProducerPE, ConsumerPE)) and attr not in (GenericPE, IterativePE, ProducerPE, ConsumerPE):
                        pes[var] = attr
                    if isinstance(attr, WorkflowGraph):
                        workflows.update({var: attr})

                if len(pes) == 0 and len(workflows) == 0:
                    print("Could not find any PEs or Workflows")
                    return
                if len(pes) > 0:
                    print("Found PEs")
                for key in pes:
                    print(f"• {key} - {type(pes[key]).__name__}", end=" ")
                    docstring = pes[key].__doc__
                    pe_class = pes[key]
                    pe_instance = pe_class()
                    r = client.register_PE(pe_instance, docstring)
                    if r is None:
                        print("(Exists)")
                    else:
                        print(f"(ID {r})")
                if len(workflows) > 0:
                    print("Found workflows")
                for key in workflows:
                    print(f"• {key} - {type(workflows[key]).__name__}", end=" ")
                    docstring = workflows[key].__doc__
                    if "A graph representing the workflow and related methods" in docstring:
                        docstring=None
                    r = client.register_Workflow(workflows[key], key, docstring, mod, unique_module_name)
                    if r is None:
                        print("(Exists)")
                    else:
                        print(f"(ID {r})")
                for var in dir(mod):
                    attr = getattr(mod, var)
                    if isinstance(attr, GenericPE):
                        setattr(mod, var, None)
                    if isinstance(attr, WorkflowGraph):
                        setattr(mod, var, None)

            except FileNotFoundError:
                print(f"Could not find file at {args['filepath']}")
            except SyntaxError:
                print(f"Target file has invalid python syntax")
            except Exception as e:
                print(f"An error occurred: {e}")
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "register_workflow"))
        except Exception as e:
            print(f"An error occurred: {e}")


    def help_register_workflow(self):
        print("Registers all workflows and PEs instantiated within a given file input.\n Remember to include all the imports necessary for those PEs within the file.")
        print("Usage: register_workflow [file.py]")


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
                if isinstance(attr, type) and issubclass(attr, (GenericPE, IterativePE, ProducerPE, ConsumerPE)) and attr not in (GenericPE, IterativePE, ProducerPE, ConsumerPE):
                    pes[var] = attr
            if len(pes) == 0:
                print("Could not find any PEs")
                return
        
            for key in pes:
                print(f"• {key} - {pes[key].__name__}", end=" ")
                pe_instance = pes[key]()
                docstring = pes[key].__doc__
                pe_class = pes[key]
                pe_instance = pe_class()
                   
                try:
                    r = client.register_PE(pe_instance, docstring)
                    if r is None:
                        print("(Exists)")
                    else:
                        print(f"(ID {r})")
                except Exception as e:
                    print(f"An error occurred during PE registration: {e}")
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "register_pe"))
        except Exception as e:
            print(f"An error occurred: {e}")
           


    def help_register_pe(self):
        print("Registers all PEs instantiated within a given file input.\n Remember to include all the imports necessary for those PEs within the file.")
        print("Usage: register_pe [file.py]")


    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        print("Exits the Laminar CLI")

    def do_list(self, arg):
        try:
            registry = client.get_Registry()
            if registry:
                for item in registry:
                    print(item)
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_list(self):
        print("Lists all registered PEs and workflows")


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
                    response = client.remove_All(type=type_remove)
                    if response is None:
                        print("No response from server.")
                    elif 'ApiError' in response:
                        print(f"Error: {response['ApiError']['message']}")
                    else:
                        print(response)
                else:
                    print("Operation cancelled by user.")
            else:
                if args["pe_identifier"] is None:
                    print("Error: Missing processing element identifier. Use --all to remove all processing elements.")
                    return
                try:
                    response = client.remove_PE(args["pe_identifier"])
                    if 'ApiError' in response:
                        print(f"Error: {response['ApiError']['message']}.")
                    else:
                        print("Processing Element removed successfully")
                except Exception as e:
                    print(f"An error occurred while removing the PE: {e}")
                    if "NoneType" in str(e):
                        print("Problably you are trying to remove a workflow instead of a processing element. Use remove_workflow <id> instead. Or the PE <id> does not exit.")
                    else:
                        print("Probably the processing element is being used by a workflow. Try to remove the workflow first.")

        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "remove_pe"))
        except TypeError:
            # Specific catch for the 'NoneType' error that shouldn't be printed
            pass
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_remove_pe(self):
        print("Removes a processing element by its name or ID, or removes all processing elements if --all is specified.")
        print("Usage: remove_pe [pe_identifier] [--all]")

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
                    response = client.remove_All(type_remove)
                    if response is None:
                        print("No response from server.")
                    elif 'ApiError' in response:
                        print(f"Error: {response['ApiError']['message']}")
                    else:
                        print(response)
     
                else:
                    print("Operation cancelled by user.")
            else:
                if args["workflow_identifier"] is None:
                    print("Error: Missing workflow identifier. Use --all to remove all workflows.")
                    return 

                response = client.remove_Workflow(args["workflow_identifier"])
                if 'ApiError' in response:
                    print(f"Error: {response['ApiError']['message']}")
                else:
                    print("Workflow removed successfully")
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "remove_workflow"))
        except TypeError:
            # Specific catch for the 'NoneType' error that shouldn't be printed
            pass
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_remove_workflow(self):
        print("Removes a workflow by its name or ID, or removes all workflows if --all is specified.")
        print("Usage: remove_workflow [workflow_identifier] [--all]")

    def do_describe(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier", type=type_checker)
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            obj = client.get_PE(args["identifier"]) or client.get_Workflow(args["identifier"])
            if obj:
                client.describe(obj)
            else:
                print(f"No description found for '{args['identifier']}'")
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "describe"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_describe(self):
        print("It provides the information on PEs or workflow by its name")
        print("Usage: describe [identifier]")


    def do_update_workflow_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("workflow_id", type=type_checker)
        parser.add_argument("new_description", type=str)
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = client.update_Workflow_Description(args["workflow_id"], args["new_description"])
            print(feedback)
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "update_workflow_description"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_update_workflow_description(self):
        print("Updates the description of a workflow by Id")
        print("Usage: update_workflow_description [workflow_id] [new_description]")

    def do_update_pe_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("pe_id", type=type_checker)
        parser.add_argument("new_description", type=str)
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = client.update_PE_Description(args["pe_id"], args["new_description"])
            print(feedback)
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "update_pe_description"))
        except Exception as e:
            print(f"An error occurred: {e}")

    def help_update_pe_description(self):
        print("Updates the description of a PE by Id")
        print("Usage: update_pe_description [pe_id] [new_description]")


    def do_remove_all(self, arg):
        confirmation = input("Are you sure you want to remove all workflows and processing elements? [Y/N]: ")
        if confirmation.lower() == 'y':
            try:
                response = client.remove_All()
                if response is None:
                    print("No response from server.")
                elif 'ApiError' in response:
                    print(f"Error: {response['ApiError']['message']}")
                else:
                    print(response)
            except Exception as e:
                print(f"An error occurred: {e}")
        else:
            print("Operation cancelled by user.")



    def help_remove_all(self):
        print("Removes all workflows and Pocessing Elements registered by the user")
        print("Usage: remove_all")


def parseArgs(arg: str):
    return arg.split()


def clear_terminal():
    if os.name == "nt":
        os.system('cls')
    else:
        os.system('clear')


clear_terminal()

# Start
if client.get_login() is not None:
    print(f"Logged in as {client.get_login()}")
else:
    while client.get_login() is None:
        username = input("Username: ")
        password = pwinput.pwinput("Password: ")
        client.login(username, password)
        if client.get_login() is None:
            print("Invalid login")

clear_terminal()

cli = LaminarCLI()
cli.cmdloop()

