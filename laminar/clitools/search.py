import shlex
import argparse
from laminar.argument_parser import CustomArgumentParser
from laminar.cli import print_text, print_error


class SearchCommand:

    def __init__(self, client):
        self.client = client

    def help(self):
        print_text("""
            Search the registry for Workflows or Processing Elements (PEs).
            Supports both literal keyword matching and AI-driven semantic search.

            Syntax:
              search <mode> <type> <query>

            Arguments:
              mode          Search method to use:
                            - 'literal': Matches the exact string in name or description.
                            - 'semantic': Matches the conceptual meaning of the query.

              type          The category of items to retrieve:
                            - 'workflow': Search only for workflows.
                            - 'pe': Search only for processing elements.

              query         The search term or phrase.

            Examples:
              search literal workflow some_term
              search semantic pe some_term
              search literal pe some_term
            """)

    def search(self, arg):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("type", choices=["literal", "semantic"], default="both")
        parser.add_argument("object", choices=["workflow", "pe", "both"], default="pe")
        parser.add_argument("search_term")

        try:
            args = vars(parser.parse_args(shlex.split(arg)))

            feedback = (
                self.client.search_Registry_Literal(args["search_term"], args["object"]) if args["type"] == "literal"
                else self.client.search_Registry_Semantic(args["search_term"], args["object"])
            )
            
            print_text(feedback, tab=True)

        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "semantic_search"))
        except Exception as e:
            print_error(f"An error occurred: {e}")
