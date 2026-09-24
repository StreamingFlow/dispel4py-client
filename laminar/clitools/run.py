import argparse
import shlex
import ast
import json

from laminar.client.d4pyclient import d4pClient
from laminar.global_variables import Process
from laminar.screen_printer import print_error, print_warning, print_text
from laminar.argument_parser import CustomArgumentParser, type_checker


class RunCommand:

    def __init__(self, client: d4pClient):
        self.client = client

    def _run(self, resources=None, workflow_id=-1, input_data=None, rawinput=False,
             multi=False, dynamic=False, verbose=False, num_processes=None):
        if num_processes is not None and (not multi or not 1 <= num_processes <= 256):
            raise ValueError("Use -n between 1 and 256 with --multi")
        input_val = input_data
        if input_data is not None and not rawinput:
            try:
                input_val = json.loads(input_data)
            except json.JSONDecodeError:
                input_val = ast.literal_eval(input_data)
        run_type = Process.MULTI if multi else Process.DYNAMIC if dynamic else Process.SIMPLE
        # Never retry execution on parsing, network, or display exceptions.
        feedback = self.client.run(workflow_id, input=input_val, verbose=verbose,
                                   resources=resources or [], process=run_type,
                                   num_processes=num_processes)
        if feedback is False:
            print_warning(f"No workflow is registered as {workflow_id}")
        else:
            print_text(feedback)

    def run(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier", type=type_checker)
        parser.add_argument("--rawinput", action="store_true")
        parser.add_argument("-v", "--verbose", action="store_true")
        parser.add_argument("-i", "--input", dest="input", required=False)
        parser.add_argument("-r", "--resource", action="append", required=False)
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument("--multi", action="store_true")
        modes.add_argument("--dynamic", action="store_true")
        parser.add_argument("-n", "--processes", type=int)

        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            self._run(workflow_id=args["identifier"], input_data=args["input"], rawinput=args["rawinput"],
                      verbose=args["verbose"], multi=args["multi"], dynamic=args["dynamic"], resources=args["resource"],
                      num_processes=args["processes"])
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def help(self):
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
           -n, --processes N        Multiprocessing process budget (requires --multi)
           --multi                  Run the workflow in parallel using multiprocessing
           --dynamic                Run the workflow in parallel using Redis

       Examples:
           run my_workflow -i '[{"input" : "1,2,3"}]' 
           run my_workflow -i 100 --dynamic -v
           run 123 --input "[{"input" : "1,2,3"}]" --multi --verbose
           run my_workflow --dynamic --resource file1.txt --resource file2.txt
               """)


