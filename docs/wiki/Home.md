# Laminar 3: installation, examples and monitoring

This guide accompanies the fixes and tracing update based on the source archive supplied on 22 September 2026. Commands marked **new** require that update on the client, server, execution engine and d4py. The public repositories and older installed packages may differ.

## Components

| Directory | Role |
|---|---|
| `dispel4py-client` | Terminal interface, registration, search, LLM composition and trace reports |
| `dispel4py-server` | Registry API, routing, MySQL storage and trace queries |
| `dispel4py-execution` | Runs workflows and collects trace artifacts |
| `d4py` | Workflow and PE implementations, simple/multi/MPI mappings and monitoring |

Keep these directories adjacent. The examples below use `~/Research/StreamFlow`, matching the tested Mac installation. Shell commands run in a normal terminal; Laminar commands run inside the `(laminar) >` prompt.

## Start the services

For the updated execution engine, build from the adjacent d4py source. The override adds the monitored engine image and MPI dependencies while retaining the existing Compose service and Redis configuration:

```bash
cd ~/Research/StreamFlow/dispel4py-execution
docker compose -f compose.yaml -f compose.trace.yaml up -d --build
docker compose -f compose.yaml -f compose.trace.yaml ps

cd ~/Research/StreamFlow/dispel4py-server
docker compose up -d --build
docker compose ps
```

Use both execution Compose files again when rebuilding. The original service name is spelled `execuction`; it is retained for compatibility. Docker Desktop must be running. Server and engine ports default to 8080 and 5000. The server uses the existing MySQL volume; this upgrade adds tables without clearing the registry.

For an existing client environment:

```bash
conda activate laminar
cd ~/Research/StreamFlow/dispel4py-client
python -m pip install .
laminar
```

The client requires Python 3.11–3.13 and the dependencies in `requirements_client.txt`. For a new environment, create it with `conda create -n laminar python=3.11`, activate it, and install the client as above. The existing model setup may download its models on first launch. Keep your existing LLM provider configuration.

The client reads `config.ini` from the working directory:

```ini
[CONFIGURATION]
SERVER_URL = http://127.0.0.1:8080
```

To register a new account, run `laminar --register` in the normal terminal. Existing users can run `laminar` and sign in. Close and reopen the CLI after reinstalling it.

### Restarting and logs

```bash
cd ~/Research/StreamFlow/dispel4py-server
docker compose logs --tail=100 server

cd ~/Research/StreamFlow/dispel4py-execution
docker compose -f compose.yaml -f compose.trace.yaml logs --tail=100 execuction
```

Ordinary restarts do not require deleting containers or volumes. `docker compose down` stops that project's services and retains its named database volume. **`docker compose down -v` in the server directory deletes the registry and stored traces**; use it only for an intentional disposable reset. Do not use a global Docker prune as an installation step.

## Terminal commands

```text
help
help run
help trace_run
help trace_show
list
advanced_search
```

`list` and `advanced_search` open full-screen tools. Ctrl+Q returns from those tools; Ctrl+Q in the main shell exits Laminar. Terminal font/window size is controlled by the terminal application, not the workflow.

| Task | Laminar 3 command |
|---|---|
| Register a PE file | `register pe FILE.py` |
| Register a workflow file | `register workflow FILE.py` |
| Find a workflow by keywords | `search literal workflow sensor` |
| Find a PE by meaning | `search semantic pe "calculate the average temperature"` |
| Show stored code | `describe IDENTIFIER --source_code` |
| Recommend similar code | `code_recommendation pe "def _process(self, data): return data" --embedding_type spt` |
| Execute sequentially | `run IDENTIFIER --input 100 --verbose` |
| Execute with a process budget — **new `-n`** | `run IDENTIFIER --multi -n 5 --input 100 --verbose` |
| Monitor an execution — **new** | `trace_run IDENTIFIER --mapping multi -n 5 --input 100` |
| Query stored measurements — **new** | `trace_show IDENTIFIER --mapping multi -n 5 --engine default` |

Use a registry name or the ID returned by registration. IDs below are examples from the test session; another registry assigns different IDs. Registration can skip an existing component. **“Already registered” does not update its stored implementation.** Inspect stored source when a local edit seems to have no effect. To test changed code without replacing an old registry entry, use distinct class/workflow names and check the new registration output.

## Worked examples

### Word count

```text
register workflow wordcount_wf.py
run 42 --input '[{"input": "apple banana apple orange banana apple"}]' --verbose
run 42 --input '[{"input": "red blue red"}, {"input": "blue green"}]' --verbose
run 42 --multi -n 3 --input '[{"input": "red blue red"}, {"input": "blue green"}]' --verbose
```

The first simple result is `apple: 3, banana: 2, orange: 1`. The second is `red: 2, blue: 2, green: 1`. A three-PE pipeline with three allocated workers avoids replicating the counting PE. With more workers, a stateful counter may emit partial counts; the engine returns those messages separately and does not invent an application-specific merge.

### Random primes

```text
register workflow isprime_wf.py
run 43 --input 100 --verbose
run 43 --multi -n 3 --input 100 --verbose
```

`100` requests 100 producer iterations; it is not a process count. Outputs vary because numbers are random. The updated local example explicitly rejects 1 as a prime. An already registered old workflow still contains its old predicate until you register an updated variant.

### Sensor data and resource files

```text
run sensor_temperature_anomaly_alerting --input '[{"input": "sensor_data_10.json"}]' --resource sensor_data_10.json --verbose
run sensor_temperature_anomaly_alerting --input '[{"input": "sensor_data_1000.json"}]' --resource sensor_data_1000.json --verbose
run sensor_temperature_anomaly_alerting --multi -n 5 --input '[{"input": "sensor_data_1000.json"}]' --resource sensor_data_1000.json --verbose
```

The 10-record file produced batch means approximately `20.3167943427` and `20.0474524883`. The tested stored workflow used a ConsumerPE sink that only printed, so `{}` was a valid simple return value. The local file had a different sink that emitted an output. Use `describe ... --source_code` to distinguish them.

Each replica of a stateful PE has its own running mean or batch buffer. Replicating anomaly detection or aggregation can change results relative to the simple mapping. Five workers for this five-PE chain avoids replication; a larger budget may replicate stages. Process budgets need not equal the number of workers actually assigned by dispel4py. Traces record the observed allocation.

### Run-length encoding

The corrected example registered as workflow 47, `run_length_encode_strings`:

```text
run 47 --input '[{"input": "aaabbccccaa"}, {"input": ""}, {"input": "aAa"}]' --verbose
run 47 --multi -n 3 --input '[{"input": "aaabbccccaa"}, {"input": ""}, {"input": "aAa"}]' --verbose
```

Expected encoded records:

```json
[
  {"text": "aaabbccccaa", "runs": [["a", 3], ["b", 2], ["c", 4], ["a", 2]]},
  {"text": "", "runs": []},
  {"text": "aAa", "runs": [["a", 1], ["A", 1], ["a", 1]]}
]
```

Simple execution returns a dictionary indexed by sink PE and output port; this collector emits the records as one batch. A message such as `SimplePE: Processed 1 iteration` describes the wrapper and does not imply that only one input record was processed. The updated ordinary multi engine returns a list of output messages, each containing `peId`, `port`, and `data`. Cross-worker ordering is not guaranteed.

## Search and LLM composition

Semantic search and code recommendations display registry metadata. Python callers continue to receive executable PE/workflow objects. Empty results now show a message instead of `KeyError: score`; the CLI no longer tries to display those objects again as dictionaries or JSON.

`--embedding_type llm` uses transformer embeddings; it does not ask a chat model to generate a PE. `spt` uses structural code similarity. Their scores use different scales and are not probabilities of correctness. A short snippet may have no structural match. The poor ranking observed for the short averaging query still needs a retrieval-quality evaluation; fixing display errors is not evidence that ranking is now ideal.

To search and potentially generate a component:

```text
advanced_search
```

The tool searches first. A weak match can trigger generation. A request beginning “Create” does not force generation. Follow the tool's refine/save prompts. Save the Python file, review it, implement any placeholders, then register and test it.

The update supplies actual registered source to the composer, checks that reused classes are unchanged, and instructs it to implement `_process`, not `process`. Pass-through adapters and collecting/output sinks must work. New business-logic PEs may intentionally be templates with `NotImplementedError`; the UI lists those methods. Unresolved static/reuse issues are displayed. Static checks do not prove runtime correctness, and no live paid LLM generation was used to validate this update.

## Monitoring with trace_run — new

`run_traces` is an alias for `trace_run`. Register the workflow first. Mapping is required; simple defaults to one process, while multi and MPI require `-n`.

```text
trace_run 47 --mapping simple --input '[{"input": "aaabbccccaa"}, {"input": ""}, {"input": "aAa"}]' --output rle-simple.zip
trace_run 47 --mapping multi -n 3 --input '[{"input": "aaabbccccaa"}, {"input": ""}, {"input": "aAa"}]' --output rle-multi-3.zip
trace_run 47 --mapping multi -n 5 --input '[{"input": "aaabbccccaa"}, {"input": ""}, {"input": "aAa"}]'
trace_run 47 --mapping mpi -n 3 --input '[{"input": "aaabbccccaa"}, {"input": ""}, {"input": "aAa"}]' --output rle-mpi-3.zip
```

MPI is launched on the execution engine; the Mac client does not need MPI. The supplied Docker recipe installs MPICH and mpi4py. MPI code and launcher argument checks are included; live MPI execution must be verified on the deployment because the development environment prohibits the required IPC sockets.

Trace a resource-backed workflow:

```text
trace_run sensor_temperature_anomaly_alerting --mapping multi -n 5 --input '[{"input": "sensor_data_1000.json"}]' --resource sensor_data_1000.json --output sensor-trace.zip
```

For tracing, resources arrive under their basenames. Use those names in workflow input; duplicate basenames are rejected. Workflow dependencies must already be installed on the selected engine. Each trace runs in a fresh directory, preventing earlier run files from contaminating its measurements.

| Option | Meaning |
|---|---|
| `--mapping simple\|multi\|mpi` | Required execution mapping |
| `-n N`, `--processes N` | Requested process budget; simple requires 1 |
| `--engine ID` | Configured execution engine, default `default` |
| `--input VALUE`, `-i VALUE` | JSON input, with Python literal fallback |
| `--rawinput` | Treat `--input` as an unparsed string |
| `--input-file FILE.json` | Read input JSON locally |
| `--inputs-by-pe` | Input is a dictionary keyed by source PE names/IDs, for multiple sources |
| `--resource FILE`, `-r FILE` | Upload an input resource; repeatable |
| `--sampling-interval SECONDS` | RSS sampling interval, default 0.01; 0 uses call-boundary observations |
| `--timeout SECONDS` | Execution limit, default 3600 |
| `--output FILE.zip` | Download raw trace artifacts after completion |
| `--graph-figures` | Also generate graph PNG files |
| `--json` | Return the report in JSON form |

The terminal report ranks PEs by accumulated processing-call time and identifies the largest observed CPU and RSS values, busy/idle instances, and local CPU versus elapsed time. It is computed directly from measurements; it does not require an LLM API call. Low local CPU can suggest waiting or external work, but is not proof of its cause.

### What is measured

- PE summaries, concrete PE-instance summaries, and individual processing calls.
- Processing-call elapsed time and local hosting-process CPU time, including its threads.
- Hosting-process RSS observed during calls. This is **not memory owned exclusively by a PE**. Never add RSS across PEs or instances as a workflow memory total.
- Abstract and concrete graphs, allocation, host/process identifiers, software/runtime metadata, source and input hashes, resource names/hashes, timestamps, and raw trace files.
- Engine elapsed time includes subprocess startup, execution and monitoring export; it excludes client/server transfer and database storage.

Parallel PE times overlap, so their sum differs from workflow elapsed time. Setup/finalization work, waits outside processing calls, remote service/LLM CPU and GPU memory are not attributed by these PE measurements. Sampling can miss short memory peaks. Tiny workflows such as the three-string example verify behavior but are too short for reliable performance decisions.

### Storage and replacement

The unique configuration is exactly **workflow ID + mapping + requested process count + engine ID**.

| Workflow | Mapping | Processes | Engine | Profile |
|---|---|---:|---|---|
| 47 | simple | 1 | default | A |
| 47 | multi | 3 | default | B |
| 47 | multi | 5 | default | C |
| 47 | mpi | 3 | default | D |
| 47 | multi | 3 | hpc | E |

Repeating configuration B replaces B's completed measurements and artifacts atomically, retaining its profile ID and assigning a new run ID. Other profiles remain unchanged. Inputs and sampling settings are recorded but are **not additional key fields**: changing them with the same key also replaces that profile. Compare performance using equivalent inputs and sampling settings.

A failed run retains the last successful results and records the error. Concurrent submissions for the same configuration are rejected while its execution lease is active. A stale execution cannot overwrite a newer one. Download/paging requests can include the run ID to detect intervening replacement.

Five additive MySQL tables are created after the existing registry schema initializes:

| Table | Contents |
|---|---|
| `trace_profile` | Unique configuration, latest run metadata, timestamps and execution lease |
| `trace_pe` | Aggregated metrics for each abstract PE |
| `trace_instance` | Metrics for each concrete PE instance/rank |
| `trace_iteration` | Individual processing-call measurements |
| `trace_artifact` | ZIP with raw CSV/JSON files, graph artifacts, logs, source and serialized inputs/workflow |

Input resource bytes are not duplicated in the trace ZIP; their hashes and names are recorded. Serialized workflow inputs are included. Deleting a workflow cascades to its trace data. There is no retained history of earlier successful runs for the same configuration.

### Query without rerunning

```text
trace_show 47
trace_show 47 --mapping multi -n 3 --engine default
trace_show 47 --mapping multi -n 3 --engine default --json
trace_show 47 --mapping multi -n 3 --download-directory saved_traces
```

Python API:

```python
trace = client.trace_run(47, mapping="multi", num_processes=3,
                         wf_inputs=[{"input": "aaabbccccaa"}])
profiles = client.get_traces(47, mapping="multi", num_processes=3, engine_id="default")
rows = client.get_trace_iterations(trace["profileId"], offset=0, limit=1000,
                                   run_id=trace["runId"])
client.download_trace(trace["profileId"], "trace.zip", run_id=trace["runId"])
```

These methods use the existing authenticated client. Iterations are paginated separately to keep ordinary reports small. Raw SQL examples and REST details are in `docs/TRACE_API.md` in the updated client repository.

### Additional execution engines

The server maps engine IDs to trusted configured URLs. If no explicit map is supplied, `default` uses the existing `laminar.execution.url`.

For example, add this server property with your actual addresses:

```properties
laminar.trace.engines={"default":"http://engine-one:5000","hpc":"http://engine-two:5000"}
```

For Docker, the equivalent environment variable is `LAMINAR_TRACE_ENGINES`. Set `LAMINAR_ENGINE_ID=default` on the first engine and `LAMINAR_ENGINE_ID=hpc` on the second. Engines verify their identity. Clients select an ID using `--engine`, not an arbitrary URL. Multi-host MPI additionally requires site-specific launcher configuration and a shared `LAMINAR_TRACE_WORK_DIR`; the supplied Compose example is a single-engine deployment.

## Validation scope

The accompanying `VALIDATION.md` records actual automated results and remaining deployment checks. Successful local tests do not establish MPI, Docker Desktop or MySQL compatibility on every host. Run the supplied smoke sequence after rebuilding your services. The wiki is provided as a file ready for publication; no live GitHub wiki was modified automatically.
