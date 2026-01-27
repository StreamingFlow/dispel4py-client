import argparse
import shlex
import ast

from laminar.global_variables import Process
from laminar.screen_printer import print_error, print_warning, print_text
from laminar.argument_parser import CustomArgumentParser, type_checker


class RunCommand:

    def __init__(self, client):
        self.client = client

    def _run(self,
             resources=None,
             workflow_id: int = -1,
             input_data=None,
             rawinput: bool = False,
             multi: bool = False,
             dynamic: bool = False,
             verbose: bool = False):

        if resources is None:
            resources = []

        try:
            input_val = input_data if rawinput or input_data is None else ast.literal_eval(input_data)

            run_type = Process.MULTI if multi else Process.DYNAMIC if dynamic else Process.SIMPLE

            feedback = self.client.run(workflow_id, input=input_val, verbose=verbose, resources=resources,
                                       process=run_type)
            if feedback is not False:
                print_text(feedback)
            else:
                print_error(f"No workflow is registered with ID {workflow_id}")
        except:
            input_val = input_data if rawinput or input_data is None else ast.literal_eval(input_data)

            run_type = Process.MULTI if multi else Process.DYNAMIC if dynamic else Process.SIMPLE
            feedback = self.client.run(workflow_id, input=input_val, verbose=verbose, resources=resources,
                                       process=run_type)

            if feedback is not False:
                print_text(feedback)
            else:
                print_warning(f"No workflow is registered with name {workflow_id}")


    def run(self, arg):
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
            self._run(workflow_id=args["identifier"], input_data=args["input"], rawinput=args["rawinput"],
                      verbose=args["verbose"], multi=args["multi"], dynamic=args["dynamic"], resources=args["resource"])
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
           --multi                  Run the workflow in parallel using multiprocessing
           --dynamic                Run the workflow in parallel using Redis

       Examples:
           run my_workflow -i '[{"input" : "1,2,3"}]' 
           run my_workflow -i 100 --dynamic -v
           run 123 --input "[{"input" : "1,2,3"}]" --multi --verbose
           run my_workflow --dynamic --resource file1.txt --resource file2.txt
               """)


