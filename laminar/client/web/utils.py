import subprocess
import os
import pickle
import codecs

import laminar.global_variables as g_vars
from laminar.screen_printer import print_warning


def verify_login(logger):
    if g_vars.CLIENT_AUTH_ID == "None":
        print("You must be logged-in to perform this operation.")
        exit()


def create_import_string(pe_source_code: str):
    if pe_source_code == "Source code not available":
        return "No imports available"

    # write source code to file
    text_file = open("../../../imports.py", "w")
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
    object_description = []
    for index, result in enumerate(results, start=1):
        desc = result['description']
        if desc is None:
            desc = "-"
        if 'workflowName' in result.keys():
            object_description.append({
                "ID": result['workflowId'],
                "Type": "WF",
                "Name": result['entryPoint'],
                "Description": desc,
                "LLM provider / model": "{} / {}".format(result["lldDescriptionProvider"],
                                                         result["lldDescriptionModel"]),
                "Inputs": result['inputsDescription'],
                "Outputs": result['outputsDescription'],
            })
            try:
                obj = pickle.loads(codecs.decode(result['workflowCode'].encode(), "base64"))
                objectList.append(obj)
            except Exception as e:
                print_warning(F"An exception occurred while fetching {result['peName']} : {e}")
                pass
        else:
            object_description.append({
                "ID": result['peId'],
                "Type": "PE",
                "Name": result['peName'],
                "Description": desc,
                "LLM provider / model": "{} / {}".format(result["lldDescriptionProvider"],
                                                         result["lldDescriptionModel"]),
                "Inputs": result['inputsDescription'],
                "Outputs": result['outputsDescription'],
            })
            try:
                obj = pickle.loads(codecs.decode(result['peCode'].encode(), "base64"))
                objectList.append(obj)
            except Exception as e:
                print_warning(F"An exception occurred while fetching {result['peId']} : {e}")
                pass

    return object_description, objectList


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
