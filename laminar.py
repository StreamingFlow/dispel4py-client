# Laminar CLI

import cmd
import sys
import argparse
import shlex
import ast
from typing import IO
import pwinput
import importlib.util

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # gets the libraries to write less garbage to the terminal
from client import d4pClient, Process
from dispel4py.base import GenericPE, WorkflowGraph

client = d4pClient()


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

    def do_search(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe", "both"], default="both")
        parser.add_argument("search_term")
        parser.add_argument("--query_type", choices=["text", "code"], default="text")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = client.search_Registry(args["search_term"], args["search_type"], args["query_type"])
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "search"))

    def help_search(self):
        print("Searches the registry for workflows and processing elements matching the search term")
        print("Usage: search [workflow|pe|both] [string] [--query_type text|code]")

    def do_run(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier")
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

    def help_run(self):
        print("Runs a workflow in the registry based on the provided name or ID")

    def do_register(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("filepath")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            try:
                spec = importlib.util.spec_from_file_location("__main__", args["filepath"])
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                pes = {}
                workflows = {}
                for var in dir(mod):
                    attr = getattr(mod, var)
                    if isinstance(attr, GenericPE):
                        pes.update({var: attr})
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
                    r = client.register_PE(pes[key], docstring)
                    if r is None:
                        print("(Exists)")
                    else:
                        print(f"(ID {r})")
                if len(workflows) > 0:
                    print("Found workflows")
                for key in workflows:
                    print(f"• {key} - {type(workflows[key]).__name__}", end=" ")
                    docstring = workflows[key].__doc__
                    r = client.register_Workflow(workflows[key], key, docstring)
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
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "register"))

    def help_register(self):
        print("Registers all workflows and PEs instantiated within a given file input")

    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        print("Exits the Laminar CLI")

    def do_list(self, arg):
        registry = client.get_Registry()
        if registry:
            for item in registry:
                print(item)

    def help_list(self):
        print("Lists all registered PEs and workflows")

    def do_remove_pe(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("pe_identifier")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            client.remove_PE(args["pe_identifier"])
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "remove_pe"))

    def help_remove_pe(self):
        print("Removes a PE by its name or ID")
        print("Usage: remove_pe [pe_identifier]")

    def do_remove_workflow(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("workflow_identifier")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            client.remove_Workflow(args["workflow_identifier"])
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "remove_workflow"))

    def help_remove_workflow(self):
        print("Removes a workflow by its name or ID")
        print("Usage: remove_workflow [workflow_identifier]")

    def do_get_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            obj = client.get_PE(args["identifier"])
            if obj is None:
                obj = client.get_Workflow(args["identifier"])
            client.describe(obj)
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "get_description"))

    def help_get_description(self):
        print("Gets the description of a PE or workflow by its name or ID")
        print("Usage: get_description [identifier]")

    def do_update_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier")
        parser.add_argument("description", nargs='+')
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            description = ' '.join(args["description"])
            success = client.update_description(args["identifier"], description)
            if success:
                print(f"Updated description for '{args['identifier']}': {description}")
            else:
                print(f"Failed to update description for '{args['identifier']}'")
        except argparse.ArgumentError as e:
            print(e.message.replace("laminar.py", "update_description"))

    def help_update_description(self):
        print("Updates the description of a PE or workflow by its name or ID")
        print("Usage: update_description [identifier] [description]")


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

