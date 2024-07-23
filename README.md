![Laminar Logo](logo.webp)
# Laminar Client Instructions 

The following instructions will allow you to run the client application to run dispel4py workflows 

##  Clone the Repository 
```
git clone https://github.com/StreamingFlow/dispel4py-client.git
```
Then enter directory by 
```
cd dispel4py-client
```

## Enviroment 

In order to run the application you need to create a new Python 3.10 enviroment 
```
--note conda must be installed beforehand, go to https://conda.io/projects/conda/en/stable/user-guide/install/linux.html
conda create --name laminar python=3.10
conda activate laminar
```

## Install client modules
```
pip install -r requirements_client.txt
```
Enter target server URL into config.ini

## Run test client 
```
cp CLIENT_EXAMPLES\<file> .
python <file>
```

## How to use the laminar CLI

Run the CLI application
```
python laminar.py
```

### Register workflows and PEs
Within the CLI register all workflows and PEs instantiated within a file using
```
(laminar) register <filename>
```
The name will be based off of the variable name used within the file and the description will be taken from the docstring

### Search the registry
Within the CLI you can search for stored workflows and PEs using
```
(laminar) search [workflow|pe|both] <search term> [--query_type text|code]

```

### Run workflows
Within the CLI you can run workflows registered to the registry with
```
(laminar) run <workflow name or id> 
```
Optional flags
- -i <input> for providing the workflow with input
- -r <resource> for providing a resource to send with the request
- --rawinput parses input as a string rather than a python object
- --verbose prints program output
There are a couple of optional flags including `-i <input>` which provides the workflow with input and `--rawinput` which parses the input as a raw string rather than attempting to parse it as a python object



