# Laminar Client

![Laminar Logo](logo.webp)

## Overview

The Laminar Client is the primary user-facing component of the Laminar framework. It provides a unified interface for
registering, managing, and executing dispel4py stream-based workflows, either through a Command Line Interface (CLI) or
directly from Python code and Jupyter notebooks.

The client communicates with the Laminar Server to authenticate users, register workflows and Processing Elements (PEs),
submit executions, and monitor their progress. Through this interaction, the Laminar Client enables efficient and
scalable execution of data-intensive applications using dispel4py’s automatic parallelisation and dynamic execution
capabilities.

## Architecture at a Glance

The Laminar Client acts as the entry point into the Laminar ecosystem and integrates with the following components:

- Laminar Server: Handles authentication, request routing, and workflow management
- Laminar Execution Engine: Executes registered workflows
- dispel4py: Defines stream-based workflows and Processing Elements

Together, these components provide a flexible environment for developing and running scalable data processing pipelines.

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/StreamingFlow/dispel4py-client.git
cd dispel4py-client
```

### Python Environment

A Python 3.10 (or newer) environment is required. The recommended approach is to use Conda.

```bash
conda create --name laminar python=3.10
conda activate laminar
```

### Install the Laminar Client

Install the client and CLI tool locally:

```bash
pip install .
```

After installation, configure the target Laminar Server by editing the `config.ini` file and setting the server URL.

## Using the Laminar Client in Python

The `CLIENT_EXAMPLES` directory contains several example dispel4py workflows that already integrate Laminar client
functions. These examples demonstrate how to authenticate, register workflows, and trigger executions programmatically.

Available examples include:

- IsPrime.py  
  Generates a user-defined number of random values and outputs only the prime numbers.

- WordCount.py  
  Counts the frequency of each word in a user-provided text.

- SensorIoT.py  
  Simulates an IoT sensor data processing workflow. A detailed explanation is available in the dispel4py workflows
  repository.

- AstroPhysics.py  
  Implements an astrophysics workflow. Further documentation is available in the dispel4py workflows repository.

An interactive Jupyter notebook example is also provided:

- Laminar_Notebook_Sample.ipynb

Additional workflows that do not include client functions are also available in the `CLIENT_EXAMPLES` directory and can
be used with the CLI.

### Running Client-Based Examples

To execute a workflow that includes client functions:

```bash
cp CLIENT_EXAMPLES/<file> .
python <file>
```

Before running these examples, ensure that you have registered a user and logged in using the Laminar client functions,
as authentication is required to interact with the Laminar framework.

## Using the Laminar CLI

### Register a New User

Register a user account (required only once per user):

```bash
laminar --register
```

You will be prompted to provide a username and password. It is also possible to skip the login step by setting the
following enviroment variables:
- `LAMINAR_USERNAME`: Previously register laminar username
- `LAMINAR_PASSWORD`: Password of the account

### Launch the CLI

Start the interactive CLI session:

```bash
laminar
```

Alternatively, if running from the source directory:

```bash
python -m laminar
```

### Preparing Workflows for the CLI

For CLI-based testing, copy workflow or PE files that do not include client functions from the `CLIENT_EXAMPLES`
directory:

```bash
cp CLIENT_EXAMPLES/<file> .
laminar
```

### Registering Workflows and Processing Elements

Within the CLI session, workflows and PEs can be registered as follows:

```bash
(laminar) > register workflow wordcount_wf.py
(laminar) > register workflow sensor_wf.py
(laminar) > register pe isprimePE.py
```

Additional dispel4py workflows suitable for use with Laminar are available in the dispel4py workflows repository and can
be adapted as needed.

## Documentation

Comprehensive documentation, including installation guides, configuration instructions, and detailed CLI and client API
usage, is available in the project wiki:

https://github.com/StreamingFlow/dispel4py-client/wiki

The user manual provides step-by-step instructions for running workflows, managing Processing Elements, and integrating
Laminar into scripts and Jupyter notebooks.