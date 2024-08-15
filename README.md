![Laminar Logo](logo.webp)

# Introduction

The Laminar Client is the primary interface for interacting with the Laminar framework, allowing users to manage and execute [dispel4py](https://github.com/StreamingFlow/d4py) workflows seamlessly. This component acts as the entry point for users, providing both a Command Line Interface (CLI) and direct client functions that can be used within Python scripts or Jupyter notebooks.

By leveraging the Laminar Client, users can register dispel4py workflows and Processing Elements (PEs), initiate and monitor workflow executions, and interact with other core components of the Laminar framework, such as the [Laminar Server](https://github.com/StreamingFlow/dispel4py-server) and [Laminar Execution Engine](https://github.com/StreamingFlow/dispel4py-execution). The client communicates with the Laminar Server to route requests and handle operations on behalf of the user, ensuring that workflows are executed efficiently and accurately.

Whether you are using the CLI for quick interactions or embedding client functions into your scripts for more complex tasks, the Laminar Client is designed to provide a flexible and user-friendly experience, making it an essential tool for working with the Laminar framework.


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

