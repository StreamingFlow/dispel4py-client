import argparse
import configparser
import importlib.util
import inspect
import os
import os.path
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from os import getcwd
from pathlib import Path

import cloudpickle
from dispel4py.base import GenericPE, IterativePE, ProducerPE, ConsumerPE
from dispel4py.workflow_graph import WorkflowGraph
from rich import box
from rich.table import Table

from laminar.argument_parser import CustomArgumentParser
from laminar.client.d4pyclient import d4pClient
from laminar.llms.LLMConnector import LLMConnector
from laminar.llms.queries_templates import (
    REGISTER_PE_CONTEXT_QUERIES,
    REGISTER_WORKFLOW_CONTEXT_QUERIES,
    NAME_WORKFLOW_CONTEXT_QUERY,
)
from laminar.screen_printer import console, print_status, print_warning, print_error

PE_BASE_TYPES = (GenericPE, IterativePE, ProducerPE, ConsumerPE)


def _pip_install(package: str) -> bool:
    def _detect_uv():
        """Return (use_uv: bool, reason: str)."""
        if os.environ.get("UV"):
            return True

        cfg = Path(sys.prefix) / "pyvenv.cfg"
        if cfg.is_file():
            parser = configparser.ConfigParser()
            try:
                parser.read_string("[v]\n" + cfg.read_text())
                if parser.has_option("v", "uv"):
                    return True
            except configparser.Error:
                pass

        here = Path(os.getcwd()).resolve()
        for d in (here, *here.parents):
            if (d / "uv.lock").is_file():
                return True
            pyproject = d / "pyproject.toml"
            if pyproject.is_file() and "[tool.uv]" in pyproject.read_text(errors="ignore"):
                return True

        return False

    use_uv = _detect_uv()
    command = ["uv", "pip", "install", package] if use_uv and shutil.which("uv") else [sys.executable, "-m", "pip",
                                                                                       "install", package]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True, )
    except subprocess.CalledProcessError as e:
        print_error(f"pip failed to install '{package}':\n{e.stderr.strip()}")
        return False
    importlib.invalidate_caches()  # let the running interpreter see the new package
    return True


class RegisterCommand:
    _PLACEHOLDER_CANDIDATES = (1, "placeholder", 1.0, True, [], {}, None)
    _ANNOTATION_DEFAULTS = {
        int: 1, float: 1.0, str: "placeholder", bool: True,
        list: [], dict: {}, tuple: (),
    }

    def __init__(self, client: d4pClient, llmConnector: LLMConnector | None = None, loaded_modules={}):
        self.client = client
        self.module_counter = 0  # Initialize a counter for module names
        self.loaded_modules = loaded_modules
        self.connector = llmConnector or LLMConnector()
        self._seen_workflow_names = set()
        self._stats = Counter()  # registered / skipped / failed, per run
        self._results = []  # buffered outcome rows for the current flow

    @staticmethod
    def _section(title: str, filepath=None, provider: str = None):
        """Render the run header as a compact table.

        A ``console.rule`` draws a fixed full-width line that overflows a narrow
        Textual widget; a table is measured and wrapped to the available width.
        """
        header = Table(
            title=f"[bold cyan]{title}[/bold cyan]", title_justify="left",
            box=box.SIMPLE, show_header=False, pad_edge=False, expand=False,
        )
        header.add_column(style="bold", no_wrap=True)
        header.add_column(overflow="fold")  # long paths wrap instead of overflow
        if filepath is not None:
            header.add_row("File", str(filepath))
        if provider is not None:
            header.add_row("Provider", provider)
        console.print(header)

    def _report_result(self, r, object_type: str = "PE", object_name: str = None):
        if r is None:
            self._stats["skipped"] += 1
            self._results.append(
                ("[yellow]•[/yellow]", object_type, object_name,
                 "[yellow]already registered[/yellow]")
            )
        else:
            self._stats["registered"] += 1
            self._results.append(
                ("[green]✓[/green]", object_type, object_name, f"[green]ID {r}[/green]")
            )

    def _report_failure(self, object_type: str, object_name: str, error: Exception):
        self._stats["failed"] += 1
        self._results.append(
            ("[red]✗[/red]", object_type, object_name,
             f"[red]{type(error).__name__}: {error}[/red]")
        )

    def _render_results(self):
        """Flush the buffered outcomes for the current flow as a table."""
        if not self._results:
            return
        table = Table(box=box.SIMPLE_HEAD, expand=False, pad_edge=False)
        table.add_column(" ", justify="center", no_wrap=True)
        table.add_column("Type", style="cyan", no_wrap=True)
        table.add_column("Name", overflow="fold")
        table.add_column("Result", overflow="fold")
        for status, object_type, name, result in self._results:
            table.add_row(status, object_type, name, result)
        console.print(table)
        self._results.clear()

    def _print_summary(self):
        registered = self._stats["registered"]
        skipped = self._stats["skipped"]
        failed = self._stats["failed"]
        if registered + skipped + failed == 0:
            return
        console.print(
            "[bold]Summary:[/bold] "
            f"[green]{registered} registered[/green] · "
            f"[yellow]{skipped} skipped[/yellow] · "
            f"[red]{failed} failed[/red]"
        )

    @staticmethod
    def _required_params(pe_class):
        try:
            sig = inspect.signature(pe_class)  # already excludes `self`
        except (ValueError, TypeError):
            return None
        required = []
        for p in sig.parameters.values():
            if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if p.default is inspect.Parameter.empty:
                required.append(p)
        return required

    def _instantiate_pe(self, pe_class):
        try:
            return pe_class()
        except TypeError:
            pass

        required = self._required_params(pe_class)
        if not required:
            return pe_class()

        last_err = None
        for candidate in self._PLACEHOLDER_CANDIDATES:
            args, kwargs = [], {}
            for p in required:
                value = (self._ANNOTATION_DEFAULTS.get(p.annotation, candidate)
                         if p.annotation is not inspect.Parameter.empty else candidate)
                if p.kind == inspect.Parameter.KEYWORD_ONLY:
                    kwargs[p.name] = value
                else:
                    args.append(value)
            try:
                return pe_class(*args, **kwargs)
            except Exception as e:
                last_err = e
        raise last_err

    def _load_module(self, filepath):
        unique_module_name = f"module_name_{int(time.time())}_{self.module_counter}"
        self.module_counter += 1

        spec = importlib.util.spec_from_file_location(unique_module_name, filepath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[unique_module_name] = mod

        # Allow sibling imports (`from domain import ...`, `from whiten import ...`).
        pkg_dir = str(Path(filepath).resolve().parent)
        added = pkg_dir not in sys.path
        if added:
            sys.path.insert(0, pkg_dir)
        try:
            spec.loader.exec_module(mod)
        finally:
            if added:
                try:
                    sys.path.remove(pkg_dir)
                except ValueError:
                    pass

        self.loaded_modules[unique_module_name] = mod
        cloudpickle.register_pickle_by_value(mod)
        return mod, unique_module_name

    @staticmethod
    def _is_pe_class(attr):
        return (isinstance(attr, type)
                and issubclass(attr, PE_BASE_TYPES)
                and attr not in PE_BASE_TYPES)

    def _discover_components(self, mod):
        """Return ({pe_name: pe_class}, {workflow_name: WorkflowGraph})."""
        pes, workflows = {}, {}
        for var in dir(mod):
            attr = getattr(mod, var)
            if self._is_pe_class(attr):
                pes[var] = attr
            elif isinstance(attr, WorkflowGraph):
                workflows[var] = attr
        return pes, workflows

    @staticmethod
    def _cleanup_module(mod):
        """Drop references to instantiated PEs / workflows on the module."""
        try:
            cloudpickle.unregister_pickle_by_value(mod)
        except (ValueError, KeyError):
            pass
        for var in dir(mod):
            attr = getattr(mod, var)
            if isinstance(attr, (GenericPE, WorkflowGraph)):
                setattr(mod, var, None)

    @staticmethod
    def _sanitize_workflow_name(raw):
        text = str(raw or "").strip()
        if not text:
            return ""
        # Take the first non-empty line and strip quoting / markdown fences.
        text = text.splitlines()[0].strip().strip("`'\"")
        text = re.sub(r"\s+", "_", text)  # spaces -> underscores
        text = re.sub(r"[^0-9A-Za-z_]", "", text)  # drop non-identifier chars
        if text and text[0].isdigit():  # identifiers can't start with a digit
            text = f"wf_{text}"
        return text

    def _deduplicate_name(self, name):
        """Ensure `name` is unique among names generated in this command."""
        candidate, suffix = name, 2
        while candidate in self._seen_workflow_names:
            candidate = f"{name}_{suffix}"
            suffix += 1
        self._seen_workflow_names.add(candidate)
        return candidate

    def _generate_workflow_name(self, source_code, fallback):
        name = ""
        try:
            raw = self.connector.propose_name(source_code=source_code, system_queries=NAME_WORKFLOW_CONTEXT_QUERY)
            name = self._sanitize_workflow_name(raw)
        except Exception as e:
            print_warning(f"Could not generate a workflow name via the LLM: {type(e).__name__}: {e}")

        if not name:
            name = self._sanitize_workflow_name(fallback) or "workflow"

        return self._deduplicate_name(name)

    def _register_single_pe(self, key, pe_class, provider):
        docstring = self.connector.describe(
            component_name=key, kind="pe",
            code=inspect.getsource(pe_class),
            provider=provider,
            context_queries=REGISTER_PE_CONTEXT_QUERIES,
        )
        pe_instance = self._instantiate_pe(pe_class)
        r = self.client.register_PE(
            pe_instance,
            description=docstring["description"],
            input_description=docstring["inputs"],
            output_description=docstring["outputs"],
            llm_model=docstring["model"],
            llm_provider=docstring["provider"],
            tags=docstring["tags"],
        )
        self._report_result(r, type(pe_instance).__bases__[0].__name__, key)

    def _register_single_workflow(self, key, workflow, mod, module_name, provider):
        pe_sources = "".join(
            inspect.getsource(pe.__class__)
            for pe in workflow.get_contained_objects()
        )

        workflow_name = self._generate_workflow_name(pe_sources, fallback=key)
        source_code = f"entry {workflow_name}()\n{pe_sources}"

        docstring = self.connector.describe(
            component_name=workflow_name, kind="workflow",
            code=source_code,
            provider=provider,
            context_queries=REGISTER_WORKFLOW_CONTEXT_QUERIES,
        )
        r = self.client.register_Workflow(
            workflow=workflow, workflow_name=workflow_name,
            description=docstring["description"],
            module=mod, module_name=module_name,
            input_description=docstring["inputs"],
            output_description=docstring["outputs"],
            llm_model=docstring["model"],
            llm_provider=docstring["provider"],
            tags=docstring["tags"],
        )
        self._report_result(r, type(workflow).__name__, workflow_name)

    def _register_pe(self, filepath, provider: str | None = None):
        provider = provider or "openai"
        self._results.clear()
        self._section("Register PE", filepath, provider)

        try:
            mod, _ = self._load_module(filepath)
            pes, _ = self._discover_components(mod)

            if not pes:
                print_warning("No PEs found in this file.")
                return

            print_status(f"Found {len(pes)} PE(s) to register.")
            for key, pe_class in pes.items():
                try:
                    self._register_single_pe(key, pe_class, provider)
                except Exception as e:
                    self._report_failure("PE", key, e)

            self._render_results()

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}", _traceback=False)
        except SyntaxError:
            print_error(f"{filepath} contains invalid Python syntax.", _traceback=False)
        except Exception as e:
            print_error(f"An unexpected error occurred: {type(e).__name__}: {e}")

    def _register_workflow(self, filepath, provider: str | None = None):
        provider = provider or "openai"
        self._results.clear()
        self._section("Register Workflow", filepath, provider)

        current_working_dir = getcwd()
        os.chdir(Path(filepath).parent)

        try:
            mod, unique_module_name = self._load_module(filepath)
            pes, workflows = self._discover_components(mod)

            if not pes and not workflows:
                print_warning("No PEs or workflows found in this file.")
                os.chdir(current_working_dir)
                return

            print_status(f"Found {len(pes)} PE(s) and {len(workflows)} workflow(s) to register.")

            for key, pe_class in pes.items():
                try:
                    self._register_single_pe(key, pe_class, provider)
                except Exception as e:
                    self._report_failure("PE", key, e)

            for key, workflow in workflows.items():
                try:
                    self._register_single_workflow(
                        key, workflow, mod, unique_module_name, provider)
                except Exception as e:
                    self._report_failure("workflow", key, e)

            self._render_results()
            self._cleanup_module(mod)

        except ModuleNotFoundError as e:
            if e.name:
                print_status(f"Installing missing dependency '{e.name}'…")
                if _pip_install(e.name):
                    return self._register_workflow(filepath, provider)
            print_warning(
                f"Skipping {filepath}: requires '{e.name}', which could not be installed automatically."
            )

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}", _traceback=False)
        except SyntaxError:
            print_error(f"{filepath} contains invalid Python syntax.", _traceback=False)
        except Exception as e:
            print_error(f"An unexpected error occurred: {type(e).__name__}: {e}")
        finally:
            os.chdir(current_working_dir)

    def _register_directory(self, path):
        self._section("Register Directory", path)

        if not os.path.exists(path):
            print_error(f"Directory '{path}' does not exist.", _traceback=False)
            return

        if not os.path.isdir(path):
            print_error(f"'{path}' is not a directory.", _traceback=False)
            return

        files = [str(p.absolute()) for p in Path(path).rglob("*.py") if p.is_file()]
        if not files:
            print_warning("No Python files found to register.")
            return

        print_status(f"Scanning {len(files)} Python file(s)…")
        for file in files:
            try:
                self._register_workflow(file)
            except Exception as e:
                print_warning(f"Could not register '{file}': {type(e).__name__}: {e}")

    def help(self):
        console.print(
            "[bold]register[/bold] — add objects to the Laminar registry\n\n"
            "Include every import the PEs need inside the target file.\n\n"
            "[bold]Usage:[/bold] register <type> <filepath> [--provider PROVIDER]\n\n"
            "[bold]type[/bold]\n"
            "  [cyan]workflow[/cyan]   Register a workflow and all of its PEs.\n"
            "  [cyan]pe[/cyan]         Register a single PE.\n"
            "  [cyan]directory[/cyan]  Recursively register every valid Dispel4py file in a directory.\n\n"
            "[bold]--provider[/bold]  LLM provider used for description generation (default: openai)."
        )

    def register(self, args):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("type", choices=["workflow", "pe", "directory"])
        parser.add_argument("filepath")
        parser.add_argument("--provider", help="The LLM provider to use for description generation", required=False,
                            default=None)

        try:
            args = vars(parser.parse_args(shlex.split(args)))
            self._seen_workflow_names.clear()
            self._stats.clear()

            if args["type"] == "workflow":
                self._register_workflow(args["filepath"], provider=args["provider"])
            elif args["type"] == "directory":
                self._register_directory(args["filepath"])
            else:
                self._register_pe(args["filepath"], provider=args["provider"])

            self._print_summary()
        except argparse.ArgumentError as e:
            print_error(e.message.replace("register_", ""), _traceback=False)
