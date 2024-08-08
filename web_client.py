# web_client.py

from dispel4py.workflow_graph import WorkflowGraph
from deep_learn_search import *
from typing import Union
from globals import *
import globals
import requests as req
import cloudpickle as pickle
import codecs
import json
import logging
import subprocess
from enum import Enum
import os
import numpy as np
import inspect
import importlib.util
import ConvertPy
from Aroma.similar import setup_features, compare_similar

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(message)s', level=logging.FATAL)

def verify_login():
    if globals.CLIENT_AUTH_ID == "None":
        logger.info("You must be logged-in to perform this operation.")
        exit()

def create_import_string(pe_source_code: str):
    if pe_source_code == "Source code not available":
        return "No imports available"
    
    # write source code to file
    text_file = open("imports.py", "w")
    text_file.write(pe_source_code)
    text_file.close()

    # call find imports on file
    output = subprocess.check_output("findimports -n imports.py", shell=True).decode()
    pe_imports = output.splitlines()
    del pe_imports[0]
    pe_imports = [s.strip().split('.', 1)[0] for s in pe_imports]
    pe_imports = ','.join(pe_imports)
    return pe_imports

def serialize_directory(path):
    if path is None:
        return get_payload(None)
    data = {}
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            with open(item_path, 'r') as f:
                file_contents = f.read()
            data[item] = {
                "type": "file",
                "size": os.path.getsize(item_path),
                "content": file_contents
            }
        elif os.path.isdir(item_path):
            data[item] = {
                "type": "directory",
                "contents": serialize_directory(item_path)
            }
    return get_payload(data)

def get_payload(code: any):
    pickled = codecs.encode(pickle.dumps(code), "base64").decode()
    return pickled

def get_objects(results):
    objectList = []
    print("\nREGISTRY\n")
    for index, result in enumerate(results, start=1):
        desc = result['description']
        if desc is None:
            desc = "-"
        if 'workflowName' in result.keys():
            workflow = f"Result {index}: ID: {result['workflowId']}\nWorkflow Name: {result['entryPoint']}\nDescription: {desc}\n"
            obj = pickle.loads(codecs.decode(result['workflowCode'].encode(), "base64"))
            print(workflow)
        else:
            pe_name = result['peName']
            pe = f"Result {index}: ID: {result['peId']}\nPE Name: {pe_name}\nDescription: {desc}\n"
            obj = pickle.loads(codecs.decode(result['peCode'].encode(), "base64"))
            print(pe)
        objectList.append(obj)
    return objectList

def format_ast_pe_results(similarPEs, response):
        formatted_pes = []
        for pe in similarPEs:
            peId = pe[0]
            peName = pe[1]
            score = pe[2]
            pruned_score = pe[3]
            similar_func = pe[4].split("\n")[0]
            pe_details = next(item for item in response if item["peId"] == peId)
            description = pe_details.get('description', None)
            peCode = pe_details.get('peCode', None)
            formatted_pes.append({
                "peId": peId,
                "peName": peName,
                "score": score,
                "pruned_score": pruned_score,
                "description": description,
                "peCode": peCode,
                "simlarFunc": similar_func
            })
        return formatted_pes

def format_ast_workflow_results(similarWorkflows):
    formatted_workflows = []
    formatted_workflows = []
    for wf in similarWorkflows:
        wfId = wf[0]
        wfName = wf[1]
        description = wf[2]
        workflowCode = wf[3]
        occurrences = wf[5]

        formatted_workflows.append({
            "workflowId": wfId,
            "workflowName": wfName,
            "description": description,
            "workflowCode": workflowCode,
            "occurrences": occurrences
        })
    return formatted_workflows




class AuthenticationData:
    def __init__(self, *, user_name: str, user_password: str):
        self.user_name = user_name
        self.user_password = user_password

    def to_dict(self):
        return {
            "userName": self.user_name,
            "password": self.user_password
        }

    def __str__(self):
        return "AuthenticationData(" + json.dumps(self.to_dict(), indent=4) + ")"

class Process(Enum):
    SIMPLE = 1
    MULTI = 2
    DYNAMIC = 3

class PERegistrationData:
    def __init__(self, *, pe: type, pe_name: str = None, pe_code: any = None, description: str = None):
        pe_class = pe.__class__

        try:
            pe_source_code = inspect.getsource(pe_class)
        except OSError as e:
            pe_source_code = "Source code not available"
            #print(f"An error occurred: could not find class definition for {pe_class}. Error: {str(e)}")
            #print("Debugging info: Is the class defined dynamically or imported from elsewhere?")
        except TypeError as e:
            pe_source_code = "Source code not available"
            #print(f"An error occurred: {str(e)}")
            #print("Debugging info: The class might be a built-in or a C extension.")

        if pe is not None:
            pe_name = pe_class.__name__
        try:
            pe_process_source_code = inspect.getsource(pe._process)
        except OSError:
            pe_process_source_code = "Source code not available"

        self.pe_name = pe_name
        self.pe_code = get_payload(pe)
        if description:
            self.description = description
        else:
            if pe_source_code != "Source code not available":
                self.description = generate_summary(pe_source_code).replace(" class ", " pe ")
            else:
                self.description = generate_summary(pe_process_source_code)
        self.pe_source_code = pe_source_code
        self.pe_imports = create_import_string(pe_source_code)
        self.code_embedding = np.array_str(encode(pe_process_source_code, 2).cpu().numpy())
        self.desc_embedding = np.array_str(encode(self.description, 1).cpu().numpy())
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
        featurisedAST = setup_features([convertToAST.result], "./Aroma")
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
            "astEmbedding": self.astEmbedding
        }

    def __str__(self):
        return "PERegistrationData(" + json.dumps(self.to_dict(), indent=4) + ")"


class WorkflowRegistrationData:
    def __init__(self, *, workflow: any, workflow_name: str = None, workflow_code: str = None, workflow_pes=None, entry_point: str = None, description: str = None, module=None, module_name=None):
        if workflow is not None:
            workflow_name = workflow.__class__.__name__
            workflow_code = get_payload(workflow)
        workflow_pes = workflow.get_contained_objects()
        workflow_source_code = "class " + entry_point + "():\n"

        for pe in workflow_pes:
            #try:
            #    pe_code = inspect.getsource(pe.__class__)
            #except:
            #    pe_code = inspect.getsource(pe._process)
            pe_code = inspect.getsource(pe._process)
            pe_code = pe_code.split("\n", 2)[2]
            workflow_source_code = workflow_source_code + pe_code
            workflow_source_code = workflow_source_code + "\n"
        if description:
            self.description = description
        else:
            summary = generate_summary(workflow_source_code)
            self.description = summary.replace(" class ", " workflow ")

        self.workflow_name = workflow_name
        self.workflow_code = workflow_code
        self.entry_point = entry_point
        self.workflow_pes = workflow_pes
        self.desc_embedding = np.array_str(encode(self.description, 1).cpu().numpy())

        if module:
            self.module_source_code = inspect.getsource(module)
        else:
            self.module_source_code = ""

        if module_name:
            self.module_name = module_name
        else:
            self.module_name = ""

    def to_dict(self):
        return {
            "workflowName": self.workflow_name,
            "workflowCode": self.workflow_code,
            "entryPoint": self.entry_point,
            "description": self.description,
            "descEmbedding": self.desc_embedding,
            "moduleSourceCode": self.module_source_code,
            "moduleName": self.module_name
        }

    def __str__(self):
        return "WorkflowRegistrationData(" + json.dumps(self.to_dict(), indent=4) + ")"

class ExecutionData:
    def __init__(self, *, workflow_id: int, workflow_name: str, workflow_code: WorkflowGraph, input: any, process: int, resources: list[str]):
        imports = ""
        if workflow_code is not None:
            for pe in workflow_code.get_contained_objects():
                pe_class = pe.__class__
                try:
                    pe_source_code = inspect.getsource(pe_class)
                    imports = imports + "," + create_import_string(pe_source_code)
                    #print(pe_source_code)
                except OSError as e:
                    pass
                    #print(f"Error getting source for {pe_class.__name__}: {e}")
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.input = get_payload(input)
        self.workflow_code = get_payload(workflow_code)
        self.resources = resources
        self.imports = imports
        self.process = process.value

    def to_dict(self):
        return {
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "workflowCode": self.workflow_code,
            "inputCode": self.input,
            "resources": self.resources,
            "imports": self.imports,
            "process": self.process
        }

    def __str__(self):
        return "ExecutionData(" + json.dumps(self.to_dict(), indent=4) + ")"

class SearchData:
    def __init__(self, *, search: str, search_type: bool):
        self.search = search
        self.search_type = search_type

    def to_dict(self):
        return {
            "search": self.search,
            "searchType": self.search_type,
        }

    def __str__(self):
        return "SearchData(" + json.dumps(self.to_dict(), indent=4) + ")"

class WebClient:
    def __init__(self):
        pass

    def register_User(self, user_data: AuthenticationData):
        data = json.dumps(user_data.to_dict())
        response = req.post(URL_REGISTER_USER, data=data, headers=headers)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            logger.info("Successfully registered user: " + response["userName"])
            return response["userName"]

    def login_User(self, user_data: AuthenticationData):
        data = json.dumps(user_data.to_dict())
        response = req.post(URL_LOGIN_USER, data=data, headers=headers)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            globals.CLIENT_AUTH_ID = response["userName"]
            logger.info("Successfully logged in: " + response["userName"])
            return response["userName"]

    def register_PE(self, pe_payload: PERegistrationData):
        verify_login()
        data = json.dumps(pe_payload.to_dict())
        response = req.post(URL_REGISTER_PE.format(globals.CLIENT_AUTH_ID), data=data, headers=headers)
        if response.ok:
            response = json.loads(response.text)
            if 'ApiError' in response.keys():
                logger.error(response['ApiError']['debugMessage'])
                return None
            else:
                pe_id = response["peId"]
                logger.info("Successfully registered PE " + response["peName"] + " with ID " + str(pe_id))
                return int(pe_id)
        else:
            logging.error(f"Failed to register PE {pe_payload.pe_name}")

    def register_Workflow(self, workflow_payload: WorkflowRegistrationData):
        verify_login()
        workflow_dict = workflow_payload.to_dict()
        data = json.dumps(workflow_dict)
        response = req.post(URL_REGISTER_WORKFLOW.format(globals.CLIENT_AUTH_ID), data=data, headers=headers)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            workflow_id = response['workflowId']
            for pe_obj in workflow_payload.workflow_pes:
                get_pe_url = URL_GET_PE_NAME.format(globals.CLIENT_AUTH_ID) + pe_obj.name
                pe_res = req.get(url=get_pe_url)
                pe_res = json.loads(pe_res.text)
                if 'ApiError' in pe_res.keys():
                    data = PERegistrationData(pe=pe_obj)
                    pe_id = WebClient.register_PE(self, data)
                    req.put(url=URL_LINK_PE_TO_WORKFLOW.format(globals.CLIENT_AUTH_ID, workflow_id, pe_id))
                else:
                    req.put(url=URL_LINK_PE_TO_WORKFLOW.format(globals.CLIENT_AUTH_ID, workflow_id, pe_res["peId"]))
            logger.info("Successfully registered Workflow: " + response["entryPoint"] + " ID:" + str(response["workflowId"]))
            return response["workflowId"]

    def run(self, execution_payload: ExecutionData, verbose=True):
        verify_login()
        data = json.dumps(execution_payload.to_dict())
        customHeaders = headers.copy()
        customHeaders['Accept'] = "text/event-stream"
        response = req.post(url=URL_EXECUTE.format(globals.CLIENT_AUTH_ID), data=data, headers=customHeaders, stream=True)
        if not response.ok:
            print(f"Error connecting to server: [{response.status_code}] {response.reason}")
            return False
        try:   
            parts = []
            for line in response.iter_lines():
                line = line.decode('utf-8')
                if line:
                    if line[:5] == "data:":
                        data = json.loads(line[5:])
                        if "response" in data.keys() and verbose:
                            print(str(data["response"]), end="")
                        elif "result" in data.keys():
                            if len(parts) > 0:
                                return parts
                            return data["result"]
                        elif "part-result" in data.keys():
                            parts.append(data["part-result"])
                        elif "resources" in data.keys():
                            resources: list[str] = data["resources"]
                            print("Requested resources: " + str(resources))
                            if len(resources) == 0:
                                continue
                            multipart_files: list = []
                            for resource in resources:
                                multipart_files.append(("files", open(resource, 'rb')))
                            url = URL_RESOURCE.format(globals.CLIENT_AUTH_ID)
                            file_response = req.put(url=URL_RESOURCE.format(globals.CLIENT_AUTH_ID), files=multipart_files)
                            print(f"File response: {file_response.status_code} {file_response.reason}")
                            for _, file in multipart_files:
                                file.close()
                        elif "error" in data.keys():
                            print(str("Error: " + str(data["error"])))
        except Exception as e:
            print("Error: " + str(e))
            return True
        return {}

    def get_PE(self, pe: Union[int, str]):
        verify_login()
        if isinstance(pe, str):
            url = URL_GET_PE_NAME.format(globals.CLIENT_AUTH_ID) + pe
        elif isinstance(pe, int):
            url = URL_GET_PE_ID.format(globals.CLIENT_AUTH_ID) + str(pe)
        else:
            assert 'invalid type'
        response = req.get(url=url)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            logger.info("Successfully retrieved PE " + response["peName"])
            peCode = response["peCode"]
            unpickled_result = pickle.loads(codecs.decode(peCode.encode(), "base64"))
            return unpickled_result

    def get_Workflow(self, workflow: Union[int, str]):
        verify_login()
        if isinstance(workflow, str):
            url = URL_GET_WORKFLOW_NAME.format(globals.CLIENT_AUTH_ID) + workflow
        elif isinstance(workflow, int):
            url = URL_GET_WORKFLOW_ID.format(globals.CLIENT_AUTH_ID) + str(workflow)
        response = req.get(url=url)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            logger.info("Successfully retrieved Workflow " + response["entryPoint"])
            workflowCode = response["workflowCode"]
            unpickled_result: WorkflowGraph = pickle.loads(codecs.decode(workflowCode.encode(), "base64"))
            return unpickled_result

    def get_PEs_By_Workflow(self, workflow: Union[int, str]):
        verify_login()
        if isinstance(workflow, str):
            url = URL_GET_PE_BY_WORKFLOW_NAME.format(globals.CLIENT_AUTH_ID) + workflow
        if isinstance(workflow, int):
            url = URL_GET_PE_BY_WORKFLOW_ID.format(globals.CLIENT_AUTH_ID) + str(workflow)
        response = req.get(url=url)
        response = json.loads(response.text)
        objectList = []
        for index, response in enumerate(response, start=1):
            pe_name = response['peName']
            pe_desc = response['description']
            if pe_desc is None:
                pe_desc = "-"
            pe = f"Result {index}: \nID: {response['peId']}\nPE Name: {pe_name}\nDescription: {pe_desc}\n"
            obj = pickle.loads(codecs.decode(response['peCode'].encode(), "base64"))
            print(pe)
            objectList.append(obj)
        return objectList

    def remove_PE(self, pe: Union[int, str]):
        verify_login()
        if isinstance(pe, str):
            url = URL_REMOVE_PE_NAME.format(globals.CLIENT_AUTH_ID) + pe
        elif isinstance(pe, int):
            url = URL_REMOVE_PE_ID.format(globals.CLIENT_AUTH_ID) + str(pe)
        response = req.delete(url=url)
        response = json.loads(response.text)
        if response == 1:
            logger.info("Successfully removed PE: " + str(pe))
        else:
            logger.error(response['ApiError']['message'])

    def remove_Workflow(self, workflow: Union[int, str]):
        verify_login()
        if isinstance(workflow, str):
            url = URL_REMOVE_WORKFLOW_NAME.format(globals.CLIENT_AUTH_ID) + workflow
        elif isinstance(workflow, int):
            url = URL_REMOVE_WORKFLOW_ID.format(globals.CLIENT_AUTH_ID) + str(workflow)
        response = req.delete(url=url)
        response = json.loads(response.text)
        if response == 1:
            logger.info("Successfully removed Workflow: " + str(workflow))
        else:
            logger.error(response['ApiError']['message'])

    def search(self, search_payload: SearchData):
        verify_login()
        search_dict = search_payload.to_dict()
        url = URL_SEARCH.format(globals.CLIENT_AUTH_ID, search_dict['search'], search_dict['searchType'])
        response = req.get(url=url)
        if response.ok:
            if response.text:
                response = json.loads(response.text)
                return get_objects(response)
            else:
                return []
        logger.error(response.reason)
        return None

    def get_Workflows(self):
        """Retrieve all workflows from the registry"""
        verify_login()
        url = URL_WORKFLOW_ALL.format(globals.CLIENT_AUTH_ID)
        response = req.get(url=url)
        if response.ok:
            if response.text:
                response = json.loads(response.text)
                return response
            else:
                return []
        logger.error(response.reason)
        return None


    def search_similarity(self, search_payload: SearchData, query_type, embedding_type):
        search_dict = search_payload.to_dict()
        
        if search_dict["searchType"] == "workflow" and query_type == "text":
            url = URL_WORKFLOW_ALL.format(globals.CLIENT_AUTH_ID)
        else:
            url = URL_PE_ALL.format(globals.CLIENT_AUTH_ID)
        response = req.get(url=url)
        response = json.loads(response.text)


        if embedding_type == "llm":
            return similarity_search(search_dict['search'], response, query_type, search_dict["searchType"], embedding_type)
        else:
            ## this for embedding_type == "spt" 
            astEmbeddings = []
            # puts all of the pe embeddings into a list
            for pe in response:
                # concat instead of appending
                jsonData = None
                jsonData = json.loads(pe['astEmbedding'])
                # adds the pe name and id to each function
                for func in jsonData:
                    func['peId'] = pe['peId']
                    func['peName'] = pe['peName']
                astEmbeddings += jsonData

            convertToAST = ConvertPy.ConvertPyToAST(search_payload.search, False)
            setup_features([astEmbeddings], "./Aroma")

            similarPEs = []
            for converted in convertToAST.result:
                similarPEs += compare_similar(astEmbeddings, [converted], "./Aroma")

            if search_dict["searchType"] == "pe":
                
                formatted_pes = format_ast_pe_results(similarPEs, response)

                # Convert to DataFrame
                formatted_pes_df = pd.DataFrame(formatted_pes)

                # Sort the DataFrame based on the score
                sorted_df = formatted_pes_df.sort_values(by="score", ascending=False)

                # Retrieve the top 5 most similar documents
                top_5_similar_docs = sorted_df.head(5)

                selected_columns = ['peId', 'peName', 'description', 'score', 'simlarFunc']
                print(top_5_similar_docs[selected_columns])

                # Retrieve code column
                obj_list = top_5_similar_docs["peCode"].apply(lambda x: pickle.loads(codecs.decode(x.encode(), "base64"))).tolist()
                return obj_list
                
                
            else: 
                
                ## this for embedding_type == "spt and search_dict["searchType"] == "workflow"
                
                url = URL_GET_WORKFLOW_BY_PE.format(globals.CLIENT_AUTH_ID)


                objectList = []
                index = 0
                # recall that dictionaries are order post python 3.7
                discoveredWorkflows = []
                workflowPositions = {} # used to find the index by workflow
        
                for pe in similarPEs:
                    
                  
                    response = req.get(url=url + str(pe[0]))
                    response = json.loads(response.text)

                  
                    for result in response:
                        if not result[0] in workflowPositions:
                            workflowPositions[result[0]] = index
                            discoveredWorkflows.append([result[0], result[1], result[2], result[3], index, 1])
                            index += 1
                        else:
                            discoveredWorkflows[workflowPositions[result[0]]][5] += 1

                 # sort by number of occurrences, break ties by position
                #discoveredWorkflows = sorted(discoveredWorkflows, key=lambda x: (-x[5], x[4]))
            
                formatted_workflows = format_ast_workflow_results(discoveredWorkflows)
                # Convert to DataFrame
                formatted_workflows_df = pd.DataFrame(formatted_workflows)

                # Sort the DataFrame based on the score
                sorted_workflows_df = formatted_workflows_df.sort_values(by="occurrences", ascending=False)

                # Retrieve the top 5 most similar documents
                top_5_similar_workflows = sorted_workflows_df.head(5)

                selected_columns = ['workflowId', 'workflowName', 'description', 'occurrences']
                print(top_5_similar_workflows[selected_columns])

                # Retrieve code column
                obj_list = top_5_similar_workflows["workflowCode"].apply(lambda x: pickle.loads(codecs.decode(x.encode(), "base64"))).tolist()
                return obj_list           

        
    

    def get_Registry(self):
        verify_login()
        url = URL_REGISTRY_ALL.format(globals.CLIENT_AUTH_ID)
        response = req.get(url=url)
        response = json.loads(response.text)
        return get_objects(response)

    def update_workflow_description(self, workflow, new_description):
        verify_login()
        new_embedding = np.array_str(encode(new_description, 1).cpu().numpy())
        url = URL_UPDATE_WORKFLOW_DESC_ID.format(globals.CLIENT_AUTH_ID, workflow)
        response = req.put(url=url, json={"description": new_description, "descEmbedding": new_embedding}, headers=headers)
        if response.status_code == 200:
            response = "Successfully updated the description of workflow ID: " + str(workflow)
            return response
        else:
            raise Exception(f"Failed to update workflow description: {response.text}")

    def update_pe_description(self, pe, new_description):
        verify_login()
        new_embedding = np.array_str(encode(new_description, 1).cpu().numpy())
        url = URL_UPDATE_PE_DESC_ID.format(globals.CLIENT_AUTH_ID, pe)
        response = req.put(url=url, json={"description": new_description, "descEmbedding": new_embedding}, headers=headers)
        if response.status_code == 200:
            response = "Successfully updated the description of pe ID: " + str(pe)
            return response
        else:
            raise Exception(f"Failed to update pe description: {response.text}")

    def get_ids(self):
        verify_login()
        url = URL_REGISTRY_ALL.format(globals.CLIENT_AUTH_ID)
        response = req.get(url=url)
        results = json.loads(response.text)
        workflow_list = []
        pe_list = []
        if len(results) > 0:
            for index, result in enumerate(results, start=1):
                if 'workflowName' in result.keys():
                    workflow_list.append(result['workflowId'])
                else:
                    pe_list.append(result['peId'])

        return (workflow_list, pe_list)
