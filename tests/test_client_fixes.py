"""Offline regression checks. Model inference is mocked at its dependency boundary."""
import ast
import importlib
import io
import sys
from types import ModuleType
from unittest.mock import Mock

import numpy as np
import pytest
from rich.console import Console

from laminar import screen_printer
from laminar.generation_validation import inspect_generated


@pytest.fixture
def client_classes(monkeypatch):
    encoder = ModuleType("laminar.llms.encoder")
    encoder.LaminarCodeEncoder = Mock
    monkeypatch.setitem(sys.modules, encoder.__name__, encoder)
    from laminar.client.web.client import WebClient
    from laminar.client.d4pyclient import d4pClient
    import laminar.global_variables as g
    monkeypatch.setattr(g, "CLIENT_AUTH_ID", "rosa")
    return WebClient, d4pClient


def test_printer_empty_and_python_objects(monkeypatch):
    from dispel4py.base import IterativePE
    buf = io.StringIO()
    monkeypatch.setattr(screen_printer, "console", Console(file=buf, width=100))
    screen_printer.print_text([], tab=True)
    screen_printer.print_text([IterativePE()], tab=True)
    screen_printer.print_text([IterativePE()])
    assert "No results found" in buf.getvalue()


def test_semantic_returns_pe_objects_and_prints_metadata_once(client_classes, monkeypatch):
    from dispel4py.base import IterativePE
    from laminar.client.web.utils import get_payload
    from laminar.clitools.search import SearchCommand
    web = client_classes[0]()
    web.encoder = Mock()
    web.encoder.embed_text.return_value = np.array([1.0, 0.0])
    web._request_json = Mock(return_value=[dict(peId=9, peName="Average", description="average",
        descEmbedding="[1 0]", peCode=get_payload(IterativePE()))])
    client = client_classes[1].__new__(client_classes[1]); client.webclient = web
    printer = Mock()
    monkeypatch.setattr("laminar.client.web.client.print_text", printer)
    SearchCommand(client).search('semantic pe "calculate the average"')
    printer.assert_called_once()
    assert printer.call_args.args[0][0]["ID"] == 9
    result = client.search_Registry_Semantic("average", "pe")
    assert isinstance(result[0], IterativePE)


def test_empty_structural_matches_do_not_sort_missing_columns(client_classes, monkeypatch):
    web = client_classes[0]()
    printer = Mock(); monkeypatch.setattr("laminar.client.web.client.print_text", printer)
    assert web._ast_pe_results([], []) == []
    assert web._ast_workflow_results([]) == []
    assert web._search_ast([], "def f(x): return x", "pe") == []
    assert printer.call_count == 3


def test_run_is_never_retried_after_failure(client_classes):
    from laminar.clitools.run import RunCommand
    client = Mock(); client.run.side_effect = RuntimeError("broken connection")
    RunCommand(client).run('47 --input \'[{"input":"aAa"}]\'')
    client.run.assert_called_once()


def test_run_json_and_process_count_reach_payload(client_classes):
    from laminar.clitools.run import RunCommand
    client = client_classes[1].__new__(client_classes[1]); client.webclient = Mock()
    RunCommand(client).run('47 --multi -n 3 --input \'[{"input": true}]\'')
    data = client.webclient.run.call_args.args[0].to_dict()
    from laminar.client.web.utils import load_payload
    assert data["numProcesses"] == 3 and data["process"] == 2
    assert load_payload(data["inputCode"]) == [{"input": True}]


@pytest.mark.parametrize("args", ["47 -n 4", "47 --multi -n 0", "47 --multi --dynamic"])
def test_invalid_run_does_not_execute(client_classes, args):
    from laminar.clitools.run import RunCommand
    client = Mock(); RunCommand(client).run(args)
    client.run.assert_not_called()


def test_stream_returns_all_worker_outputs(client_classes):
    from laminar.client.dto.requests import ExecutionData
    web = client_classes[0](); response = Mock(ok=True)
    response.iter_lines.return_value = [b'data:{"part-result":{"peId":"sink","port":"output","data":1}}',
        b'data:{"part-result":{"peId":"sink","port":"output","data":2}}', b'data:{"result":[]}']
    web._request = Mock(return_value=response)
    data = ExecutionData(workflow_id=47, workflow_name=None, workflow_code=None,
                         input=1, process=2, resources=[], num_processes=3)
    assert [part["data"] for part in web.run(data)] == [1, 2]
    web._request.assert_called_once()


SOURCE = '''from dispel4py.base import IterativePE
class Encode(IterativePE):
    def _process(self, value):
        return {"text": value, "runs": []}
'''


def test_generated_framework_hook_and_reuse_contract():
    assert inspect_generated(SOURCE)[0] == []
    issues, _ = inspect_generated(SOURCE.replace("_process", "process"))
    assert "implement _process" in issues[0]
    candidates = [{"name": "Encode", "source_code": SOURCE}]
    assert inspect_generated(SOURCE, candidates, ["Encode"])[0] == []
    issues, _ = inspect_generated(SOURCE.replace('"runs"', '"groups"'), candidates, ["Encode"])
    assert "differs from its registered source" in issues[0]


def test_placeholder_is_explicit_not_a_syntax_error():
    source = SOURCE.replace('return {"text": value, "runs": []}', 'raise NotImplementedError("implement me")')
    issues, placeholders = inspect_generated(source)
    assert issues == [] and placeholders == ["Encode._process"]


def test_generation_prompt_contains_actual_registered_source(monkeypatch):
    for module, cls in [("GeminiConnector", "GeminiConnector"),
                        ("OpenAIConnector", "OpenAIConnector"), ("OpenWebUI", "OpenWebUIConnector")]:
        stub = ModuleType("laminar.llms.connectors." + module)
        setattr(stub, cls, Mock); monkeypatch.setitem(sys.modules, stub.__name__, stub)
    from laminar.llms.LLMConnector import LLMConnector
    from laminar.llms.prompts import compose_prompt
    candidate = LLMConnector._compact_pe(dict(id=44, name="Encode", code=SOURCE, tags_json=["encoding"]))
    assert candidate["source_code"] == SOURCE
    prompt = compose_prompt("reuse Encode", [candidate])
    assert 'def _process' in prompt
    assert candidate["tags"] == ["encoding"]
