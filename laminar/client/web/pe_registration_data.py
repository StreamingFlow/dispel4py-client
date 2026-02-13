import inspect
import json
import numpy as np
from laminar.conversion import ConvertPy

from laminar.aroma.similar import setup_features
from laminar.client.web.utils import get_payload, create_import_string
from laminar.llms.encoder import LaminarCodeEncoder


class PERegistrationData:
    def __init__(self, *, pe: type, pe_name: str = None, pe_code: any = None, description: str = None,
                 inputDescription: str = None, outputDescription: str = None, llmProvider: str = None,
                 llmModel: str = None, encoder: LaminarCodeEncoder):
        pe_class = pe.__class__

        if not description:
            raise RuntimeError("PE description not provided")

        try:
            pe_source_code = inspect.getsource(pe_class)
        except OSError as e:
            pe_source_code = "Source code not available"
            # print(f"An error occurred: could not find class definition for {pe_class}. Error: {str(e)}")
            # print("Debugging info: Is the class defined dynamically or imported from elsewhere?")
        except TypeError as e:
            pe_source_code = "Source code not available"
            # print(f"An error occurred: {str(e)}")
            # print("Debugging info: The class might be a built-in or a C extension.")

        if pe is not None:
            pe_name = pe_class.__name__
        try:
            pe_process_source_code = inspect.getsource(pe._process)
        except OSError:
            pe_process_source_code = "Source code not available"

        self.llmProvider = llmProvider
        self.llmModel = llmModel
        self.inputDescription = inputDescription
        self.outputDescription = outputDescription
        self.pe_name = pe_name
        self.pe_code = get_payload(pe)
        self.description = description
        self.pe_source_code = pe_source_code
        self.pe_imports = create_import_string(pe_source_code)
        self.code_embedding = np.array_str(encoder.encode(pe_process_source_code, 2).cpu().numpy())
        self.desc_embedding = np.array_str(encoder.encode(self.description, 1).cpu().numpy())
        # convert to json style file for AST similarity

        # Ensure valid Python code is passed to AST parser
        code_to_use = pe_source_code if pe_source_code != "Source code not available" else pe_process_source_code
        if code_to_use != "Source code not available":

            # Ensure code starts at the correct indentation level
            lines = code_to_use.splitlines()
            min_indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
            adjusted_lines = [line[min_indent:] for line in lines]
            adjusted_code = "\n".join(adjusted_lines)
            convertToAST = ConvertPy.ConvertPyToAST(adjusted_code, False)
        else:
            convertToAST = ConvertPy.ConvertPyToAST(code_to_use, False)

        # featurisation allows for storing the relevant features for the similarity analysis
        featurisedAST = setup_features([convertToAST.result], "../../Aroma")
        self.astEmbedding = str(json.dumps(featurisedAST))

    def to_dict(self):
        return {
            "peName": self.pe_name,
            "peCode": self.pe_code,
            "sourceCode": self.pe_source_code,
            "description": self.description,
            "peImports": self.pe_imports,
            "codeEmbedding": self.code_embedding,
            "descEmbedding": self.desc_embedding,
            "astEmbedding": self.astEmbedding,
            "lldDescriptionProvider": self.llmProvider,
            "lldDescriptionModel" : self.llmModel,
            "inputsDescription": self.inputDescription,
            "outputsDescription": self.outputDescription,
        }

    def __str__(self):
        return "PERegistrationData(" + json.dumps(self.to_dict(), indent=4) + ")"
