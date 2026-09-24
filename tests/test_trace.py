import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from laminar.trace import format_report, trace_run, get_traces, validate, workflow_ref


@pytest.mark.parametrize("mapping,n",[("simple",2),("multi",None),("mpi",0),("dynamic",2)])
def test_invalid_configuration(mapping,n):
    with pytest.raises(ValueError): validate(mapping,n,.01,60)


def test_zero_is_observed_and_none_is_missing():
    trace=dict(mapping="simple",numProcesses=1,engineId="default",wallSeconds=1,
        perPe=[dict(pe_id="PE",total_count=1,total_secs=1,total_cpu_secs=0,cpu_percent=0,rss_max_bytes=None)],instances=[])
    report=format_report(trace)
    assert "Most CPU time: PE (0.000 s)" in report
    assert "Highest observed hosting-process RSS: unavailable" in report
    assert "not workflow elapsed time" in report


def fake_web(monkeypatch):
    import laminar.global_variables as g
    monkeypatch.setattr(g, "BASE_URL", "http://server")
    web=Mock();web.user_login_id="rosa";web._request.return_value.ok=True
    web._request.return_value.json.return_value={"profileId":7}
    return web


def test_post_exactly_once_with_long_timeout(monkeypatch):
    web=fake_web(monkeypatch)
    assert trace_run(web,"sensor",mapping="multi",num_processes=16,timeout=600)=={"profileId":7}
    web._request.assert_called_once()
    args,kwargs=web._request.call_args
    assert args == ("POST","http://server/execution/rosa/trace_run")
    assert kwargs["timeout"]==(10,720)
    assert kwargs["json"]["workflowName"]=="sensor"
    assert kwargs["json"]["numProcesses"]==16


def test_post_failure_does_not_retry(monkeypatch):
    web=fake_web(monkeypatch);web._request.return_value.ok=False
    web._request.return_value.status_code=502;web._request.return_value.text="engine failed"
    with pytest.raises(RuntimeError,match="engine failed"):
        trace_run(web,4,mapping="simple")
    web._request.assert_called_once()


def test_query_has_all_key_fields(monkeypatch):
    web=fake_web(monkeypatch)
    get_traces(web,4,mapping="mpi",num_processes=8,engine_id="hpc")
    assert web._request.call_args.kwargs["params"]==dict(workflowId=4,mapping="mpi",numProcesses=8,engineId="hpc")


def test_resource_basename_collision(monkeypatch,tmp_path):
    web=fake_web(monkeypatch)
    for name in ["a","b"]:
        (tmp_path/name).mkdir();(tmp_path/name/"data.csv").write_text("x")
    with pytest.raises(ValueError,match="Duplicate"):
        trace_run(web,1,mapping="simple",resources=[tmp_path/"a/data.csv",tmp_path/"b/data.csv"])
    web._request.assert_not_called()


def test_workflow_requires_registered_identity():
    with pytest.raises(ValueError):workflow_ref(object())


def test_cli_passes_mapping_input_and_download_revision(capsys):
    from laminar.clitools.trace_run import TraceRunCommand
    client=Mock()
    client.trace_run.return_value=dict(profileId=7,runId="abc",mapping="multi",numProcesses=4,
                                      engineId="default",perPe=[],instances=[])
    TraceRunCommand(client).run('42 --mapping multi -n 4 --input \'[{"input": 3}]\' --output trace.zip')
    args,kwargs=client.trace_run.call_args
    assert args==(42,)
    assert kwargs["wf_inputs"]==[{"input":3}]
    assert kwargs["num_processes"]==4
    client.download_trace.assert_called_once_with(7,"trace.zip",run_id="abc")


def test_cli_bad_input_never_executes(capsys):
    from laminar.clitools.trace_run import TraceRunCommand
    client=Mock()
    TraceRunCommand(client).run('42 --mapping simple -i not_valid')
    client.trace_run.assert_not_called()
    assert "ERR" in capsys.readouterr().out
