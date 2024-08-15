![Laminar Logo](logo.webp)

# Introduction

The Laminar Client is the primary interface for interacting with the Laminar framework, allowing users to manage and execute [dispel4py](https://github.com/StreamingFlow/d4py) stream-based workflows seamlessly. This component acts as the entry point for users, providing both a Command Line Interface (CLI) and direct client functions that can be used within Python scripts or Jupyter notebooks. 

By leveraging the Laminar Client, users can register dispel4py workflows and Processing Elements (PEs), initiate and monitor workflow executions, and interact with other core components of the Laminar framework, such as the [Laminar Server](https://github.com/StreamingFlow/dispel4py-server) and [Laminar Execution Engine](https://github.com/StreamingFlow/dispel4py-execution). The client communicates with the Laminar Server to route requests and handle operations on behalf of the user, ensuring that workflows are executed efficiently and accurately. 

Laminar takes full advantage of dispel4py’s capabilities, including automatic parallelization of workflows and dynamic resource provisioning when running workflows in parallel or dynamically. These features ensure efficient and scalable execution of data-intensive applications.


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

## How to use the laminar Client Functions

In the [CLIENT_EXAMPLES](https://github.com/StreamingFlow/dispel4py-client/tree/main/CLIENT_EXAMPLES) directory, we provide four dispel4py workflows that already include client functions. You can use these examples to test the Laminar framework with the client functions. The available workflows are:

* [IsPrime.py](https://github.com/StreamingFlow/dispel4py-client/blob/main/CLIENT_EXAMPLES/IsPrime.py). The workflow generates as many random numbers as the number indicate by the user in the input, and prints out only the prime numbers.
* [WordCount.py](https://github.com/StreamingFlow/dispel4py-client/blob/main/CLIENT_EXAMPLES/WordCount.py). This workflow reads the input text provided by the user and returns the total count of each word found within it 
* [SensorIoT.py](https://github.com/StreamingFlow/dispel4py-client/blob/main/CLIENT_EXAMPLES/SensorIoT.py). You can find the explanation of this workflow [here](https://github.com/StreamingFlow/d4py_workflows/tree/main/others)
* [AstroPhysics.py](https://github.com/StreamingFlow/dispel4py-client/blob/main/CLIENT_EXAMPLES/AstroPhysics.py). You can find the explanation of this workflow [here](https://github.com/StreamingFlow/d4py_workflows/tree/main/internal_extinction)

Additionally, we offer a [Notebook](https://github.com/StreamingFlow/dispel4py-client/blob/main/Laminar_Notebook_Sample.ipynb) that you can use to test the framework in a more interactive environment.

For more examples, the [CLIENT_EXAMPLES](https://github.com/StreamingFlow/dispel4py-client/tree/main/CLIENT_EXAMPLES) directory also contains other workflows that don't include client functions. These can be used with the CLI.


If you're looking for more dispel4py workflows, additional examples are available [here](https://github.com/StreamingFlow/d4py_workflows). You could adapt these for running them with client functions.

To run a test any of the five workflows which include client functions, copy the desired file from the CLIENT_EXAMPLES directory and execute it with the following commands:

```
cp CLIENT_EXAMPLES\<file> .
python <file>
```

Before running these examples, ensure that you have registered a user and logged in using the appropriate client functions. This step is crucial for authenticating your requests with the Laminar framework.

## How to use the laminar CLI

### Register a New User:
Begin by registering a new user. You will be prompted to enter a username and password. This step only needs to be completed once for each user.
```
python register.py
```

### Launch the CLI Application:

After registration, launch the CLI application. You will be prompted to enter your username and password. If you haven't registered yet, please complete the registration step above first. For more detailed information about the CLI, you can refer to the documentation.
```
python laminar.py
```

### Prepare for Testing:

To start testing the CLI, we recommend copying the desired files (e.g. wordcount_wf.py, sensor_wf.py or isprimePE.py) from the CLIENT_EXAMPLES directory. Once copied, you can begin using the CLI:
```
cp CLIENT_EXAMPLES/<file> .
python laminar.py
```

Note that the PEs or workflows files to use in laminar are the ones that do not include the client functions.

### Register Workflows and PEs:

Once logged into Laminar, you can use the workflows or Processing Elements (PEs) from the CLIENT_EXAMPLES directory (without client functions) to register them. For example:
```
(laminar) register_workflow wordcount_wf.py
(laminar) register_workflow sensor_wf.py
(laminar) register_pe isprimePE.py
```

If you're looking for more dispel4py workflows, additional examples are available [here](https://github.com/StreamingFlow/d4py_workflows).

## User Manual

For detailed instructions on installation, configuration, and usage, please refer to the comprehensive **User Manual** available in the [wiki](https://github.com/StreamingFlow/dispel4py-client/wiki) of this repository. The manual covers everything you need to get started with the Laminar framework, including step-by-step guides for installing components, running workflows, and managing Processing Elements (PEs). It also provides in-depth explanations of the Command Line Interface (CLI) as well as the client functions to be used in scripts or jupyter notebooks.

