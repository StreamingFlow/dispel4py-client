from laminar.client.d4pyclient import d4pClient
from laminar.llms.LLMConnector import LLMConnector
from laminar.screen_printer import print_warning, print_status, print_text, print_error


class ExplainCommand:

    def __init__(self, client: d4pClient):
        self.client = client
        self.connector = LLMConnector()

    def explain(self, identifier, provider, model):

        data = self.client.get_Workflow(identifier) or self.client.get_PE(identifier)

        if data:
            source_code = data[1]
            object_kind = "workflow" if "Workflow" in str(data[0].__class__.__name__) else "pe"
            object_name = data[2]

            description = self.connector.describe(component_name=object_name, kind=object_kind, code=source_code,
                                                  model=model,
                                                  provider=provider,
                                                  context_queries=[
                                                      "Return JSON only. Do not explain.",
                                                      """Return JSON only, describing the code, the inputs and the outputs:
                                                           {{
                                                               'description': '...',
                                                               'inputs':  {'<input_name>':'description', ...},
                                                               'outputs': {'<output_name>':'description', ...}
                                                           }}""",
                                                      "If a workflow is given the input and outputs are the ones coming from the user and not from the PEs",
                                                      "If no input or no outputs are present, say that no input or output are present",
                                                  ])

            print_status("Description: \n{}".format(description["description"]))
            print_status("\nInputs:")
            if isinstance(description["inputs"], str):
                print_warning("\t" + description["inputs"])
            else:
                for field in description["inputs"].keys():
                    print_text("\t{}: {}".format(field, description["inputs"][field]))
            print_status("\nOutputs:")
            if isinstance(description["outputs"], str):
                print_warning("\t" + description["outputs"])
            else:
                for field in description["outputs"].keys():
                    print_text("\t{}: {}".format(field, description["outputs"][field]))
        else:
            print_error(f"No object found with ID: '{identifier}'")

    def help(self):
        print_text("""
              Use LLMs to explain a workflow or a PE from the registered items. 
              Requires only the ID od the targeted component to be explained.
              
        Usage:
            explain <identifier> --model --provider
            
        --provider   The LLM provider to use for description generation. Defaults to OpenAI.
        
        --model      The model to use for description generation. Defaults to gpt-4o.
              """)
