from dispel4py.base import *
import configparser
from enum import Enum

config = configparser.ConfigParser()
config.read('config.ini')

CLIENT_AUTH_ID: str = "None"

class Process(Enum):
    SIMPLE = 1
    MULTI = 2
    DYNAMIC = 3

try:
  BASE_URL: str = config['CONFIGURATION']['SERVER_URL']
  if len(BASE_URL) < 1:
    raise "No base URL error"
except:
  print("ERROR: Server URL not configured - check your configuration file")
  exit(1)

BASE_URL_REGISTER: str = BASE_URL + "/registry/{}"

URL_REGISTRY_ALL: str = BASE_URL_REGISTER + "/all"

URL_REGISTER_PE: str = BASE_URL_REGISTER + "/pe/add"

URL_GET_PE_NAME: str = BASE_URL_REGISTER  + "/pe/name/"

URL_GET_PE_ID: str = BASE_URL_REGISTER + "/pe/id/"

URL_REMOVE_PE_NAME: str = BASE_URL_REGISTER + "/pe/remove/name/"

URL_REMOVE_PE_ID: str = BASE_URL_REGISTER + "/pe/remove/id/"

URL_PE_ALL: str = BASE_URL_REGISTER + "/pe/all"

URL_WORKFLOW_ALL: str = BASE_URL_REGISTER + "/workflow/all"

URL_REGISTER_WORKFLOW: str = BASE_URL_REGISTER + "/workflow/add"

URL_GET_WORKFLOW_NAME: str = BASE_URL_REGISTER + "/workflow/name/"

URL_GET_WORKFLOW_ID: str = BASE_URL_REGISTER + "/workflow/id/"

URL_GET_PE_BY_WORKFLOW_NAME: str = BASE_URL_REGISTER + "/workflow/pes/name/"

URL_GET_PE_BY_WORKFLOW_ID: str = BASE_URL_REGISTER + "/workflow/pes/id/"

URL_REMOVE_WORKFLOW_NAME: str = BASE_URL_REGISTER + "/workflow/remove/name/"

URL_REMOVE_WORKFLOW_ID: str = BASE_URL_REGISTER + "/workflow/remove/id/"

URL_LINK_PE_TO_WORKFLOW: str = BASE_URL_REGISTER + "/workflow/{}/pe/{}"

URL_GET_WORKFLOW_BY_PE: str = BASE_URL_REGISTER + "/workflow/byPeID/"

URL_EXECUTE: str = BASE_URL + "/execution/{}/run"

URL_RESOURCE: str = BASE_URL + "/execution/{}/resource"

URL_REGISTER_USER: str = BASE_URL + "/auth/register"

URL_LOGIN_USER: str =  BASE_URL + "/auth/login"

URL_SEARCH: str = BASE_URL_REGISTER + "/search/{}/type/{}"

URL_UPDATE_WORKFLOW_DESC_ID: str = BASE_URL_REGISTER + "/workflow/update/{}/description"

URL_UPDATE_PE_DESC_ID: str = BASE_URL_REGISTER + "/pe/update/{}/description"

PE_TYPES = (BasePE,IterativePE,ProducerPE,ConsumerPE,SimpleFunctionPE,CompositePE,GenericPE)

headers = {
            'Content-Type':'application/json', 
            'Accept':'application/json'
          }

