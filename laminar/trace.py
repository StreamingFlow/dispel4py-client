"""Monitoring client and terminal report; independent of the ML stack."""
import base64
import json
import math
from pathlib import Path
import re
from urllib.parse import quote

import cloudpickle


def validate(mapping, num_processes, sampling_interval, timeout):
    if mapping not in {"simple", "multi", "mpi"}:
        raise ValueError("mapping must be simple, multi or mpi")
    if num_processes is None and mapping == "simple":
        num_processes = 1
    if type(num_processes) is not int or not 1 <= num_processes <= 256:
        raise ValueError("Specify -n / num_processes between 1 and 256 for multi/mpi")
    if mapping == "simple" and num_processes != 1:
        raise ValueError("simple always uses one process; use -n 1")
    if not math.isfinite(sampling_interval) or not 0 <= sampling_interval <= 60:
        raise ValueError("memory_sampling_interval must be between 0 and 60 seconds")
    if type(timeout) is not int or not 1 <= timeout <= 86400:
        raise ValueError("timeout must be an integer between 1 and 86400 seconds")
    return num_processes


def workflow_ref(workflow):
    if type(workflow) is int and workflow > 0:
        return {"workflowId": workflow}
    if isinstance(workflow, str) and workflow.strip():
        return {"workflowName": workflow}
    raise ValueError("Use the name or ID of a registered workflow")


def endpoint(web):
    from laminar import global_variables as g
    web.verifyLogin()
    return g.BASE_URL.rstrip("/") + "/execution/" + quote(str(web.user_login_id), safe="")


def checked_json(response):
    if not response.ok:
        raise RuntimeError(f"Trace request failed (HTTP {response.status_code}): {response.text[:5000]}")
    return response.json()


def trace_run(web, workflow, *, mapping, num_processes=None, engine_id="default", wf_inputs=None,
              inputs_by_pe=False, resources=None, memory_sampling_interval=0.01,
              timeout=3600, graph_figures=False):
    n = validate(mapping, num_processes, memory_sampling_interval, timeout)
    payload = dict(workflow_ref(workflow), mapping=mapping, numProcesses=n, engineId=engine_id,
                   inputCode=base64.b64encode(cloudpickle.dumps(wf_inputs)).decode(),
                   inputsByPe=inputs_by_pe, memorySamplingInterval=memory_sampling_interval,
                   timeoutSeconds=timeout, graphFigures=graph_figures, resourceFiles=[])
    names, total = set(), 0
    for resource in resources or []:
        path = Path(resource)
        # Basenames are stable on a remote engine; reject collisions explicitly.
        if path.name in names:
            raise ValueError(f"Duplicate resource basename: {path.name}")
        names.add(path.name)
        total += path.stat().st_size
        if total > 64 * 1024 * 1024:
            raise ValueError("Resources exceed the 64 MiB transfer limit")
        payload["resourceFiles"].append({"name": path.name,
              "contentBase64": base64.b64encode(path.read_bytes()).decode()})
    # Never retry POST automatically: it executes a workflow.
    return checked_json(web._request("POST", endpoint(web) + "/trace_run", json=payload,
                                    timeout=(10, timeout + 120)))


def get_traces(web, workflow, *, mapping=None, num_processes=None, engine_id=None):
    params = workflow_ref(workflow)
    params.update({k:v for k,v in {"mapping":mapping,"numProcesses":num_processes,"engineId":engine_id}.items() if v is not None})
    return checked_json(web._request("GET",endpoint(web)+"/traces",params=params))


def download_trace(web, profile_id, path, *, run_id=None):
    if type(profile_id) is not int or profile_id <= 0:
        raise ValueError("Invalid profile ID")
    response = web._request("GET",endpoint(web)+f"/traces/{profile_id}/artifacts",
                            params={"runId":run_id} if run_id else {},timeout=(10,120))
    if not response.ok:
        checked_json(response)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def get_iterations(web, profile_id, *, offset=0, limit=1000, run_id=None):
    return checked_json(web._request("GET",endpoint(web)+f"/traces/{int(profile_id)}/iterations",
                                    params={"offset":offset,"limit":limit,"runId":run_id}))


def clean(value):
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value))


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    if 0 < abs(value) < 10 ** -digits:
        return f"{value:.2e}"
    return f"{value:.{digits}f}"


def format_report(trace, top=5):
    """Rank observations, not causal bottlenecks; never sum RSS or CPU % values."""
    pes, instances = trace.get("perPe", []), trace.get("instances", [])
    lines = [f"Trace #{trace.get('profileId', '?')} | workflow {trace.get('workflowId', '?')}",
             f"{trace['mapping']} | processes: {trace['numProcesses']} | engine: {clean(trace['engineId'])}",
             f"Run: {clean(trace.get('runId', '?'))}",
             f"Engine elapsed: {fmt(trace.get('wallSeconds'))} s (startup + execution + monitoring export)"]
    if trace.get("inProgress"):
        lines.append("A replacement is running; these are the last completed results.")
    if trace.get("lastError"):
        lines.append("The latest attempt failed; these are the last completed results.")
    if not pes:
        return "\n".join(lines + ["No PE measurements available."])
    total = sum(p.get("total_secs") or 0 for p in pes)
    lines += ["", "PEs ranked by accumulated processing-call time:",
              f"{'PE':30} {'Calls':>7} {'Time s':>10} {'CPU s':>9} {'RSS MiB':>9}"]
    for p in sorted(pes,key=lambda r:r.get("total_secs") or 0,reverse=True)[:top]:
        rss = p.get("rss_max_bytes")
        lines.append(f"{clean(p['pe_id'])[:30]:30} {p.get('total_count',0):>7} "
                     f"{fmt(p.get('total_secs')):>10} {fmt(p.get('total_cpu_secs')):>9} "
                     f"{fmt(rss / 1048576 if rss is not None else None,1):>9}")
    slow = max(pes,key=lambda p:p.get("total_secs") or 0)
    if total:
        share = 100 * (slow.get("total_secs") or 0) / total
        lines += ["", f"Most accumulated time: {clean(slow['pe_id'])} ({share:.1f}% of PE-call time).",
                  f"  Typical call: {fmt(slow.get('p50_secs'))} s; p95: {fmt(slow.get('p95_secs'))} s."]
        percent = slow.get("cpu_percent")
        if percent is not None:
            lines.append(f"  Local process CPU during these calls: {percent:.1f}% of one logical CPU.")
        if percent is not None and percent < 20 and (slow.get("total_secs") or 0) >= 0.1:
            lines.append("  Low local CPU during these calls suggests waiting or external work;")
            lines.append("  inspect I/O/API latency before assuming more CPUs will help.")
    for key, label, scale, unit in [("total_cpu_secs","Most CPU time",1,"s"),
                                    ("rss_max_bytes","Highest observed hosting-process RSS",1048576,"MiB")]:
        measured = [p for p in pes if p.get(key) is not None]
        if measured:
            p = max(measured,key=lambda r:r[key])
            lines.append(f"{label}: {clean(p['pe_id'])} ({p[key]/scale:.3f} {unit}).")
        else:
            lines.append(f"{label}: unavailable.")
    if instances:
        active = [p for p in instances if (p.get("total_count") or 0) > 0]
        idle = len(instances) - len(active)
        lines += ["", f"Runtime PE instances: {len(instances)}; idle: {idle}."]
        if active:
            slow_instance = max(active,key=lambda p:p.get("total_secs") or 0)
            lines.append(f"Most accumulated instance time: {clean(slow_instance['instance_id'])} "
                         f"({fmt(slow_instance.get('total_secs'))} s).")
        for key, label, scale, unit in [("total_cpu_secs", "Most instance CPU", 1, "s"),
                                      ("rss_max_bytes", "Highest instance hosting-process RSS",1048576,"MiB")]:
            measured = [p for p in active if p.get(key) is not None]
            if measured:
                p = max(measured,key=lambda r:r[key])
                lines.append(f"{label}: {clean(p['instance_id'])} ({p[key]/scale:.3f} {unit}).")
        if idle:
            idle_names = [clean(p["instance_id"]) for p in instances if not p.get("total_count")]
            lines.append("Idle instances: " + ", ".join(idle_names[:top]) + (" ..." if idle > top else ""))
            lines.append("Some allocated instances processed no calls; review input volume and routing.")
        process_ids = {pid for p in instances for pid in (p.get('process_ids') or '').split(';') if pid}
        lines.append(f"Observed hosting processes: {len(process_ids)} (PE instances can share a process).")
    if total < 0.05:
        lines += ["", "Very short workload: timing and CPU rankings can be dominated by instrumentation.",
                  "Use a larger representative input before making performance decisions."]
    errors = sum(p.get("rss_sample_errors") or 0 for p in pes)
    if errors:
        lines.append(f"RSS sampling errors: {errors}; memory observations may be incomplete.")
    lines += ["", "How to read this:",
              "- PE-call times overlap in parallel runs; their sum is not workflow elapsed time.",
              "- CPU is local process CPU during successful calls, including its threads.",
              "- RSS is observed hosting-process memory, not memory owned by a PE.",
              "  Never sum PE/instance RSS; brief peaks may be missed between samples.",
              "- Remote LLM/server CPU, GPU memory, queue waits and setup are not PE metrics.",
              "- PE metrics cover processing calls; separate setup/finalization work is excluded.",
              "- Compare configurations using the same workflow, inputs and sampling settings."]
    return "\n".join(lines)
