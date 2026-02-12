import argparse
import cmd
import importlib.util
import shlex
import sys
import pwinput

from laminar.llms.LLMConnector import LLMConnector
from laminar.llms.OpenAIConnector import OpenAIConnector

from laminar.screen_printer import *
from laminar.argument_parser import CustomArgumentParser, type_checker
from laminar.client.d4pyclient import d4pClient
from laminar.clitools.search import SearchCommand
from laminar.clitools.register import RegisterCommand
from laminar.clitools.remove import RemoveCommand
from laminar.clitools.run import RunCommand
from laminar.clitools.update_description import UpdateDescriptionCommand
from laminar.clitools.explain import ExplainCommand


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
        self.search_command = SearchCommand(self.client)
        self.register_command = RegisterCommand(self.client, self.loaded_modules)
        self.remove_command = RemoveCommand(self.client)
        self.run_command = RunCommand(self.client)
        self.update_description_command = UpdateDescriptionCommand(self.client)
        self.explain_command = ExplainCommand(self.client)

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

    def do_search(self, arg):
        self.search_command.search(arg)

    def help_search(self):
        self.search_command.help()

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
        Provides code recommendation from registered workflows and processing elements matching the code snippet.

        Arguments:
          search_type   Type of items to search for. Choices are:
                        - 'workflow': Search only for workflows
                        - 'pe': Search only for processing elements (PEs)
          code_snippet   The code_snippet to get recommendations from the registry.

        Options:
          --embedding_type  The type of embedding to use. Choices are:
                        - 'spt': Perform a search based on SPT features
                        - 'llm': Perform a search based on LLM-generated embeddings

        Note: code recommendations for workflows only possible with 'spt' embedding_type 

        Usage:
          semantic_search [workflow|pe] [code_snippet] [--embedding_type llm|spt]

        Examples:
          code_recommendation pe code_snippet --embedding_type spt
          code_recommendation workflow code_snippet --embedding_type spt
          code_recommendation pe code_snippet --embedding_type llm
        """)

    def do_run(self, arg):
        self.run_command.run(arg)

    def help_run(self):
        self.run_command.help()

    def do_register(self, arg):
        self.register_command.register(arg)

    def help_register(self):
        self.register_command.help()

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

    def help_remove(self):
        self.remove_command.help()

    def do_remove(self, arg):
        self.remove_command.remove(arg)

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

    def do_explain(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier", type=type_checker)
        parser.add_argument("--provider", help="The LLM provider to use for explanation", required=False,
                            default="openai")
        parser.add_argument("--model", help="The model to use for explanation", required=False, default=None)

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            self.explain_command.explain(identifier=args["identifier"], provider=args["provider"], model=args["model"])
        except Exception as e:
            print_error(e)

    def help_explain(self):
        self.explain_command.help()

    def do_update_description(self, arg):
        self.update_description_command.update_description(arg)

    def help_update_description(self):
        self.update_description_command.help()
