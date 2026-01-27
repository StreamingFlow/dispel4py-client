import shlex

from laminar.argument_parser import CustomArgumentParser, type_checker
from laminar.screen_printer import print_text, print_error, print_warning, print_status


class RemoveCommand:
    def __init__(self, client):
        self.client = client

    def _remove_pe(self, pe_id, remove_all=False):
        if remove_all:
            response = self.client.remove_All(type="pe")
            if response is None:
                print_error("No response from server.")
            elif 'ApiError' in response:
                print_error(f"Error: {response['ApiError']['message']}")
            else:
                print_text(response)
        else:
            try:
                response = self.client.remove_PE(pe_id)
                if isinstance(response, dict) and 'ApiError' in response:
                    print_error(f"Error: {response['ApiError']['message']}.")
                else:
                    print_status("Processing Element removed successfully")
            except Exception as e:
                print_error(f"An error occurred while removing the PE: {e}")
                if "NoneType" in str(e):
                    print_error(
                        "Probably you are trying to remove a workflow instead of a processing element. "
                        "Use remove workflow <id> instead. Or the PE <id> does not exit.")
                else:
                    print_error("Probably the processing element is being used by a workflow. "
                                "Try to remove the workflow first.")

    def _remove_workflow(self, workflow_id, remove_all=False):
        if remove_all:
            response = self.client.remove_All(type="workflow")
            if response is None:
                print_error("No response from server.")
            elif 'ApiError' in response:
                print_error(f"Error: {response['ApiError']['message']}")
            else:
                print_status(response)

        else:
            response = self.client.remove_Workflow(workflow_id)
            if isinstance(response, dict) and 'ApiError' in response:
                print_error(f"Error: {response['ApiError']['message']}")
            else:
                print_status("Workflow removed successfully")

    def help(self):
        print_status("""
        Remove a registered object from Laminar.
        
        Syntax: 
            remove <object> <id>
            
        Arguments:
            type       The type of object to remove.
                        - 'workflow': Removes a workflow with given ID.
                        - 'pe': Remove a PE with a given ID.
                        - 'all': Remove all registered Workflows and PEs

            id         The ID of the object to remove. Either an integer or 'all' to remove all.
        """)

    def remove(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("type", help="Type of object to remove", choices=["workflow", "pe", "all"])
        parser.add_argument("id", type=type_checker, default=-1, nargs='?')
        try:
            args = vars(parser.parse_args(shlex.split(arg)))

            remove_all = args["id"] == "all" or args["type"] == "all"

            if remove_all:
                confirmation = input(
                    f"Are you sure you want to remove all {args["type"] if "all" not in args["type"] else "objects"}? [Y/N]: ")
                if confirmation.lower() != 'y':
                    print_warning("Operation cancelled by user.")
                    return
            elif args["id"] == -1:
                print_warning("No valid object ID was provided")
                return

            if "pe" in args["type"]:
                self._remove_pe(pe_id=args["id"], remove_all=remove_all)
            elif "workflow" in args["type"]:
                self._remove_workflow(workflow_id=args["id"], remove_all=remove_all)
            else:
                self._remove_workflow(workflow_id=-1, remove_all=True)
                self._remove_pe(pe_id=-1, remove_all=True)
        except Exception as e:
            print_error(e)
