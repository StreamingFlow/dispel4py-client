from laminar.search.deep_learn_search import *
from typing import Union
import requests as req
import cloudpickle as pickle
import json
import logging
import numpy as np
from laminar.conversion import ConvertPy
from dispel4py.workflow_graph import WorkflowGraph

from laminar.aroma.similar import setup_features, compare_similar
from laminar.client.web.authentication_data import AuthenticationData
from laminar.client.web.execution_data import ExecutionData
from laminar.client.web.pe_registration_data import PERegistrationData
from laminar.client.web.search_data import SearchData
from laminar.client.web.workflow_registration_data import WorkflowRegistrationData
from laminar.client.web.utils import *

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(message)s', level=logging.FATAL)


class WebClient:
    def __init__(self):
        pass

    def register_User(self, user_data: AuthenticationData):
        data = json.dumps(user_data.to_dict())
        response = req.post(g_vars.URL_REGISTER_USER, data=data, headers=g_vars.headers)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            logger.info("Successfully registered user: " + response["userName"])
            return response["userName"]

    def login_User(self, user_data: AuthenticationData):
        data = json.dumps(user_data.to_dict())
        response = req.post(g_vars.URL_LOGIN_USER, data=data, headers=g_vars.headers)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            g_vars.CLIENT_AUTH_ID = response["userName"]
            logger.info("Successfully logged in: " + response["userName"])
            return response["userName"]

    def register_PE(self, pe_payload: PERegistrationData):
        verify_login(logger)
        data = json.dumps(pe_payload.to_dict())
        response = req.post(g_vars.URL_REGISTER_PE.format(g_vars.CLIENT_AUTH_ID), data=data,
                            headers=g_vars.headers)
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
        verify_login(logger)
        workflow_dict = workflow_payload.to_dict()
        data = json.dumps(workflow_dict)
        response = req.post(g_vars.URL_REGISTER_WORKFLOW.format(g_vars.CLIENT_AUTH_ID), data=data,
                            headers=g_vars.headers)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            workflow_id = response['workflowId']
            for pe_obj in workflow_payload.workflow_pes:
                get_pe_url = g_vars.URL_GET_PE_NAME.format(g_vars.CLIENT_AUTH_ID) + pe_obj.name
                pe_res = req.get(url=get_pe_url)
                pe_res = json.loads(pe_res.text)
                if 'ApiError' in pe_res.keys():
                    data = PERegistrationData(pe=pe_obj)
                    pe_id = WebClient.register_PE(self, data)
                    req.put(url=g_vars.URL_LINK_PE_TO_WORKFLOW.format(g_vars.CLIENT_AUTH_ID,
                                                                      workflow_id, pe_id))
                else:
                    req.put(url=g_vars.URL_LINK_PE_TO_WORKFLOW.format(g_vars.CLIENT_AUTH_ID,
                                                                      workflow_id, pe_res["peId"]))
            logger.info(
                "Successfully registered Workflow: " + response["entryPoint"] + " ID:" + str(response["workflowId"]))
            return response["workflowId"]

    def run(self, execution_payload: ExecutionData, verbose=True):
        verify_login(logger)
        data = json.dumps(execution_payload.to_dict())
        customHeaders = g_vars.headers.copy()
        customHeaders['Accept'] = "text/event-stream"
        response = req.post(url=g_vars.URL_EXECUTE.format(g_vars.CLIENT_AUTH_ID), data=data,
                            headers=customHeaders, stream=True)
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
                            url = g_vars.URL_RESOURCE.format(g_vars.CLIENT_AUTH_ID)
                            file_response = req.put(
                                url=g_vars.URL_RESOURCE.format(g_vars.CLIENT_AUTH_ID),
                                files=multipart_files)
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
        verify_login(logger)
        if isinstance(pe, str):
            url = g_vars.URL_GET_PE_NAME.format(g_vars.CLIENT_AUTH_ID) + pe
        elif isinstance(pe, int):
            url = g_vars.URL_GET_PE_ID.format(g_vars.CLIENT_AUTH_ID) + str(pe)
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
            sourceCode = response["sourceCode"]
            unpickled_result = pickle.loads(codecs.decode(peCode.encode(), "base64"))
            return [unpickled_result, sourceCode]

    def get_Workflow(self, workflow: Union[int, str]):
        verify_login(logger)
        if isinstance(workflow, str):
            url = g_vars.URL_GET_WORKFLOW_NAME.format(g_vars.CLIENT_AUTH_ID) + workflow
        elif isinstance(workflow, int):
            url = g_vars.URL_GET_WORKFLOW_ID.format(g_vars.CLIENT_AUTH_ID) + str(workflow)
        response = req.get(url=url)
        response = json.loads(response.text)
        if 'ApiError' in response.keys():
            logger.error(response['ApiError']['message'])
            return None
        else:
            logger.info("Successfully retrieved Workflow " + response["entryPoint"])
            workflowCode = response["workflowCode"]
            moduleSourceCode = response["moduleSourceCode"]
            unpickled_result: WorkflowGraph = pickle.loads(codecs.decode(workflowCode.encode(), "base64"))
            return [unpickled_result, moduleSourceCode]

    def get_PEs_By_Workflow(self, workflow: Union[int, str]):
        verify_login(logger)
        if isinstance(workflow, str):
            url = g_vars.URL_GET_PE_BY_WORKFLOW_NAME.format(g_vars.CLIENT_AUTH_ID) + workflow
        if isinstance(workflow, int):
            url = g_vars.URL_GET_PE_BY_WORKFLOW_ID.format(g_vars.CLIENT_AUTH_ID) + str(workflow)
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
        verify_login(logger)
        if isinstance(pe, str):
            url = g_vars.URL_REMOVE_PE_NAME.format(g_vars.CLIENT_AUTH_ID) + pe
        elif isinstance(pe, int):
            url = g_vars.URL_REMOVE_PE_ID.format(g_vars.CLIENT_AUTH_ID) + str(pe)
        response = req.delete(url=url)
        response = json.loads(response.text)
        if response == 1:
            logger.info("Successfully removed PE: " + str(pe))
        else:
            logger.error(response['ApiError']['message'])

    def remove_Workflow(self, workflow: Union[int, str]):
        verify_login(logger)
        if isinstance(workflow, str):
            url = g_vars.URL_REMOVE_WORKFLOW_NAME.format(g_vars.CLIENT_AUTH_ID) + workflow
        elif isinstance(workflow, int):
            url = g_vars.URL_REMOVE_WORKFLOW_ID.format(g_vars.CLIENT_AUTH_ID) + str(workflow)
        response = req.delete(url=url)
        response = json.loads(response.text)
        if response == 1:
            logger.info("Successfully removed Workflow: " + str(workflow))
        else:
            logger.error(response['ApiError']['message'])

    def search(self, search_payload: SearchData):
        verify_login(logger)
        search_dict = search_payload.to_dict()
        url = g_vars.URL_SEARCH.format(g_vars.CLIENT_AUTH_ID, search_dict['search'],
                                       search_dict['searchType'])
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
        verify_login(logger)
        url = g_vars.URL_WORKFLOW_ALL.format(g_vars.CLIENT_AUTH_ID)
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
            url = g_vars.URL_WORKFLOW_ALL.format(g_vars.CLIENT_AUTH_ID)
        else:
            url = g_vars.URL_PE_ALL.format(g_vars.CLIENT_AUTH_ID)
        response = req.get(url=url)
        response = json.loads(response.text)

        if embedding_type == "llm":
            return similarity_search(search_dict['search'], response, query_type, search_dict["searchType"],
                                     embedding_type)
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
            setup_features([astEmbeddings], "../../Aroma")

            similarPEs = []
            for converted in convertToAST.result:
                similarPEs += compare_similar(astEmbeddings, [converted], "../../Aroma")

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
                obj_list = top_5_similar_docs["peCode"].apply(
                    lambda x: pickle.loads(codecs.decode(x.encode(), "base64"))).tolist()
                return obj_list


            else:

                ## this for embedding_type == "spt and search_dict["searchType"] == "workflow"

                url = g_vars.URL_GET_WORKFLOW_BY_PE.format(g_vars.CLIENT_AUTH_ID)

                objectList = []
                index = 0
                # recall that dictionaries are order post python 3.7
                discoveredWorkflows = []
                workflowPositions = {}  # used to find the index by workflow

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
                # discoveredWorkflows = sorted(discoveredWorkflows, key=lambda x: (-x[5], x[4]))

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
                obj_list = top_5_similar_workflows["workflowCode"].apply(
                    lambda x: pickle.loads(codecs.decode(x.encode(), "base64"))).tolist()
                return obj_list

    def get_Registry(self):
        verify_login(logger)
        url = g_vars.URL_REGISTRY_ALL.format(g_vars.CLIENT_AUTH_ID)
        response = req.get(url=url)
        response = json.loads(response.text)
        return get_objects(response)

    def update_workflow_description(self, workflow, new_description):
        verify_login(logger)
        new_embedding = np.array_str(encode(new_description, 1).cpu().numpy())
        url = g_vars.URL_UPDATE_WORKFLOW_DESC_ID.format(g_vars.CLIENT_AUTH_ID, workflow)
        response = req.put(url=url, json={"description": new_description, "descEmbedding": new_embedding},
                           headers=g_vars.headers)
        if response.status_code == 200:
            response = "Successfully updated the description of workflow ID: " + str(workflow)
            return response
        else:
            raise Exception(f"Failed to update workflow description: {response.text}")

    def update_pe_description(self, pe, new_description):
        verify_login(logger)
        new_embedding = np.array_str(encode(new_description, 1).cpu().numpy())
        url = g_vars.URL_UPDATE_PE_DESC_ID.format(g_vars.CLIENT_AUTH_ID, pe)
        response = req.put(url=url, json={"description": new_description, "descEmbedding": new_embedding},
                           headers=g_vars.headers)
        if response.status_code == 200:
            response = "Successfully updated the description of pe ID: " + str(pe)
            return response
        else:
            raise Exception(f"Failed to update pe description: {response.text}")

    def get_ids(self):
        verify_login(logger)
        url = g_vars.URL_REGISTRY_ALL.format(g_vars.CLIENT_AUTH_ID)
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
