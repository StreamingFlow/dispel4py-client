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

Start by registering a new user. You will be prompted to enter a username and password. This step only needs to be completed once for each user.
```
python register.py
```

Launch the CLI application. You will be prompted to enter your username and password. If you haven’t registered yet, please complete the registration step above first. More information about the CLI is available [here](https://github.com/StreamingFlow/dispel4py-client/wiki#cli-options-laminarpy).
```
python laminar.py
```

## How to use the laminar Client Functions

You can also interact with the Laminar framework by using the laminar client functions directly in your Python scripts or Jupyter notebooks. More information about cliente functions is available [here](https://github.com/StreamingFlow/dispel4py-client/wiki#using-client-functions-in-notebooks-and-scripts-clientpy).

## User Manual

For detailed instructions on installation, configuration, and usage, please refer to the comprehensive **User Manual** available in the [wiki](https://github.com/StreamingFlow/dispel4py-client/wiki) of this repository. The manual covers everything you need to get started with the Laminar framework, including step-by-step guides for installing components, running workflows, and managing Processing Elements (PEs). It also provides in-depth explanations of the Command Line Interface (CLI) as well as the client functions to be used in scripts or jupyter notebooks.

