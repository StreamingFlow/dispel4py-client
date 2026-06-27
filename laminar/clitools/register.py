import importlib.util
import os.path
import time
import sys
import shlex
import argparse
import inspect
import re
import subprocess
import shutil
import os
import configparser
from os import getcwd
from pathlib import Path

from dispel4py.base import GenericPE, IterativePE, ProducerPE, ConsumerPE
from dispel4py.workflow_graph import WorkflowGraph

from laminar.client.d4pyclient import d4pClient
from laminar.llms.LLMConnector import LLMConnector
from laminar.screen_printer import print_status, print_warning, print_error
from laminar.argument_parser import CustomArgumentParser

from laminar.llms.queries_templates import (
    REGISTER_PE_CONTEXT_QUERIES,
    REGISTER_WORKFLOW_CONTEXT_QUERIES,
    NAME_WORKFLOW_QUERY,
    NAME_WORKFLOW_CONTEXT_QUERY,
)

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
    command = ["uv", "pip", "install", package] if use_uv and shutil.which("uv") else [sys.executable, "-m", "pip", "install", package]

    try:
        subprocess.run(command,check=True, capture_output=True, text=True,)
    except subprocess.CalledProcessError as e:
        print_error(f"pip failed to install '{package}':\n{e.stderr.strip()}", _traceback=False)
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
    def _report_result(r):
        if r is None:
            print_warning("(Exists)")
        else:
            print_status(f"(ID {r})")

    @staticmethod
    def _cleanup_module(mod):
        """Drop references to instantiated PEs / workflows on the module."""
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
        text = re.sub(r"\s+", "_", text)            # spaces -> underscores
        text = re.sub(r"[^0-9A-Za-z_]", "", text)   # drop non-identifier chars
        if text and text[0].isdigit():              # identifiers can't start with a digit
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
            raw = self.connector.propose_name(source_code=source_code, system_queries= NAME_WORKFLOW_CONTEXT_QUERY)
            name = self._sanitize_workflow_name(raw)
        except Exception as e:
            print_warning(f"Could not generate a workflow name via the LLM: {type(e).__name__}: {e}")

        if not name:
            name = self._sanitize_workflow_name(fallback) or "workflow"

        return self._deduplicate_name(name)

    def _register_single_pe(self, key, pe_class, provider):
        print_status(f"? {key} - {pe_class.__name__}")
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
        self._report_result(r)

    def _register_single_workflow(self, key, workflow, mod, module_name, provider):
        pe_sources = "".join(
            inspect.getsource(pe.__class__)
            for pe in workflow.get_contained_objects()
        )

        workflow_name = self._generate_workflow_name(pe_sources, fallback=key)
        source_code = f"entry {workflow_name}()\n{pe_sources}"

        print_status(f"? {workflow_name} - {type(workflow).__name__}")
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
        self._report_result(r)

    def _register_pe(self, filepath, provider: str | None = None):
        provider = provider or "openai"
        print_status(
            f"Registering PE from {filepath} using {provider} for LLM description generation.")

        try:
            mod, _ = self._load_module(filepath)
            pes, _ = self._discover_components(mod)

            if not pes:
                print_warning("Could not find any PEs")
                return

            for key, pe_class in pes.items():
                try:
                    self._register_single_pe(key, pe_class, provider)
                except Exception as e:
                    print_error(f"An error occurred during PE registration: {e}")

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}")
        except SyntaxError:
            print_error("Target file has invalid python syntax")
        except Exception as e:
            print_error(f"An error occurred: {e}")

    def _register_workflow(self, filepath, provider: str | None = None):
        provider = provider or "openai"
        print_status(
            f"Registering workflow from {filepath} using {provider} for LLM description generation.")

        current_working_dir = getcwd()
        os.chdir(Path(filepath).parent)

        try:
            mod, unique_module_name = self._load_module(filepath)
            pes, workflows = self._discover_components(mod)

            if not pes and not workflows:
                print_warning("Could not find any PEs or Workflows")
                os.chdir(current_working_dir)
                return

            for key, pe_class in pes.items():
                try:
                    self._register_single_pe(key, pe_class, provider)
                except Exception as e:
                    print_error(f"An error occurred during PE registration: {e}")

            for key, workflow in workflows.items():
                try:
                    self._register_single_workflow(
                        key, workflow, mod, unique_module_name, provider)
                except Exception as e:
                    print_error(f"An error occurred during workflow registration: {e}")

            self._cleanup_module(mod)

        except ModuleNotFoundError as e:
            if e.name and _pip_install(e.name):
                return self._register_workflow(filepath, provider)
            print_warning(f"Skipping {filepath}: requires '{e.name}', which can not installed automatically.")

        except FileNotFoundError:
            print_error(f"Could not find file at {filepath}")
        except SyntaxError:
            print_error("Target file has invalid python syntax")
        except Exception as e:
            print_error(f"An error occurred: {e}: {type(e).__name__}")
        finally:
            os.chdir(current_working_dir)

    def _register_directory(self, path):

        if not os.path.exists(path):
            print_warning(f"Error: directory {path} does not exist")
            return

        if not os.path.isdir(path):
            print_error(f"Error: directory {path} is not a directory")
            return

        files = [str(p.absolute()) for p in Path(path).rglob("*.py") if p.is_file()]
        print_status(f"Trying to register {len(files)} files")

        for file in files:
            try:
                self._register_workflow(file)
            except Exception as e:
                print_warning(f"File {file} could not be registered: {e}")

    def help(self):
        print_status("""
        Registers a new object within the Laminar registry.
        Remember to include all the imports necessary for those PEs within the file.

        Usage: register <type> <filepath>

        type          The category of object to register.
                            - 'workflow':   Register a workflow, as well as all the 
                                            PEs that comprises the workflow within Laminar.,
                            - 'pe':         Register a single PE.
                            - 'directory':  Register recursively all files within a directory 
                                            if they contain valid Dispel4py components.

        --provider   The LLM provider to use for description generation. Defaults to OpenAI.
        """)

    def register(self, args):
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("type", choices=["workflow", "pe", "directory"])
        parser.add_argument("filepath")
        parser.add_argument("--provider", help="The LLM provider to use for description generation", required=False,
                            default=None)

        try:
            args = vars(parser.parse_args(shlex.split(args)))
            self._seen_workflow_names.clear()

            if args["type"] == "workflow":
                self._register_workflow(args["filepath"], provider=args["provider"])
            elif args["type"] == "directory":
                self._register_directory(args["filepath"])
            else:
                self._register_pe(args["filepath"], provider=args["provider"])
        except argparse.ArgumentError as e:
            print_error(e.message.replace("register_", ""))