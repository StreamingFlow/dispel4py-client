"""Terminal commands for new runs and previously stored trace profiles."""
import ast
import json
from pathlib import Path
import shlex

from laminar.argument_parser import CustomArgumentParser, type_checker
from laminar.screen_printer import print_error
from laminar.trace import format_report


class TraceRunCommand:
    def __init__(self, client):
        self.client = client

    def parser(self):
        p = CustomArgumentParser(prog="trace_run", exit_on_error=False, add_help=False)
        p.add_argument("identifier", type=type_checker)
        p.add_argument("--mapping", "-m", required=True, choices=["simple","multi","mpi"])
        p.add_argument("--processes", "-n", type=int)
        p.add_argument("--engine", default="default")
        inputs = p.add_mutually_exclusive_group()
        inputs.add_argument("--input", "-i")
        inputs.add_argument("--input-file", help="Local JSON input file")
        p.add_argument("--rawinput", action="store_true")
        p.add_argument("--inputs-by-pe", action="store_true")
        p.add_argument("--resource", "-r", action="append")
        p.add_argument("--sampling-interval", type=float, default=.01)
        p.add_argument("--timeout", type=int, default=3600)
        p.add_argument("--graph-figures", action="store_true")
        p.add_argument("--output", help="Download raw trace ZIP to this path")
        p.add_argument("--json", action="store_true")
        return p

    def run(self, arg):
        try:
            a = self.parser().parse_args(shlex.split(arg))
            if a.input_file:
                if a.rawinput:
                    raise ValueError("--rawinput applies to --input, not --input-file")
                data = json.loads(Path(a.input_file).read_text())
            elif a.input is None or a.rawinput:
                data = a.input
            else:
                try:
                    data = json.loads(a.input)
                except json.JSONDecodeError:
                    data = ast.literal_eval(a.input)
            if not a.json:
                print("Running monitored workflow; the report appears when execution completes...")
            result = self.client.trace_run(a.identifier, mapping=a.mapping, num_processes=a.processes,
                    engine_id=a.engine, wf_inputs=data, inputs_by_pe=a.inputs_by_pe, resources=a.resource,
                    memory_sampling_interval=a.sampling_interval, timeout=a.timeout, graph_figures=a.graph_figures)
            print(json.dumps(result, indent=2) if a.json else format_report(result))
            if a.output:
                self.client.download_trace(result["profileId"], a.output, run_id=result["runId"])
                if not a.json:
                    print(f"Trace files saved to {a.output}")
        except Exception as exc:
            print_error(str(exc))

    def help(self):
        print(self.parser().format_help())
        print("Examples:\n  trace_run 42 --mapping simple -i 100\n"
              "  trace_run sensor_wf --mapping multi -n 16 -i 100 --output trace.zip\n"
              "  trace_run 42 --mapping mpi -n 8 --engine hpc --input-file inputs.json\n"
              "A completed run replaces this workflow/mapping/process-count/engine profile.\n"
              "Inputs/resources are metadata, not part of that replacement key.\n"
              "Resources arrive under their basenames; use those names inside the workflow.")


class TraceShowCommand:
    def __init__(self, client):
        self.client = client

    def parser(self):
        p = CustomArgumentParser(prog="trace_show", exit_on_error=False, add_help=False)
        p.add_argument("identifier", type=type_checker)
        p.add_argument("--mapping", choices=["simple","multi","mpi"])
        p.add_argument("--processes", "-n", type=int)
        p.add_argument("--engine")
        p.add_argument("--json", action="store_true")
        p.add_argument("--download-directory")
        return p

    def run(self,arg):
        try:
            a = self.parser().parse_args(shlex.split(arg))
            traces = self.client.get_traces(a.identifier, mapping=a.mapping,
                                          num_processes=a.processes, engine_id=a.engine)
            if a.json:
                print(json.dumps(traces,indent=2))
            elif not traces:
                print("No completed traces match these filters.")
            else:
                print("\n\n".join(format_report(t) for t in traces))
            if a.download_directory:
                for trace in traces:
                    self.client.download_trace(trace["profileId"], Path(a.download_directory) / f"trace-{trace['profileId']}.zip", run_id=trace["runId"])
        except Exception as exc:
            print_error(str(exc))

    def help(self):
        print(self.parser().format_help())
        print("Reads stored traces without executing the workflow. Omit filters to see all configurations.")
