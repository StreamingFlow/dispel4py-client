import shlex
import argparse

from laminar.screen_printer import print_text, print_status, print_error
from laminar.argument_parser import CustomArgumentParser, type_checker


class UpdateDescriptionCommand:

    def __init__(self, client):
        self.client = client

    def help(self):
        print_text("""
        Updates the description of a workflow or a PE by Id. 

        Usage: update_description <pe | workflow> <workflow_id> <new_description>
        """)

    def update_description(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("object", choices=["pe", "workflow"], help="Object to update")
        parser.add_argument("id", type=type_checker)
        parser.add_argument("new_description", type=str)
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            update_target = args["object"]
            feedback = (
                self.client.update_Workflow_Description(args["id"],
                                                        args["new_description"]) if update_target == "workflow" else
                self.client.update_PE_Description(args["id"], args["new_description"])
            )
            print_status(feedback)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "update_workflow_description"))
        except Exception as e:
            print_error(f"An error occurred: {e}")
