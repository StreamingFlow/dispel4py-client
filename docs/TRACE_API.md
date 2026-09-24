# Stored trace API and database queries

The server retains the existing Laminar user/workflow access checks. Examples below assume the corresponding user owns or can access the referenced registry workflow. The existing authentication model is unchanged.

## HTTP API

| Method | Path | Result |
|---|---|---|
| POST | `/execution/{user}/trace_run` | Execute once, atomically replace the matching completed profile, return summary |
| GET | `/execution/{user}/traces?workflowId=47` | Completed configurations for workflow 47 |
| GET | `/execution/{user}/traces?workflowName=NAME&mapping=multi&numProcesses=3&engineId=default` | Filtered profiles |
| GET | `/execution/{user}/traces/{profileId}` | One report |
| GET | `/execution/{user}/traces/{profileId}/iterations?offset=0&limit=1000&runId=RUN` | Paginated processing-call measurements |
| GET | `/execution/{user}/traces/{profileId}/artifacts?runId=RUN` | Raw artifact ZIP |

`run_traces` is a CLI/Python alias; the HTTP route remains `trace_run`. Identify a workflow with exactly one of `workflowId` or `workflowName`. For POST, provide `mapping`, `numProcesses`, `engineId`, `inputCode` (base64 cloudpickle), `inputsByPe`, `memorySamplingInterval`, `timeoutSeconds`, `graphFigures`, and optional `resourceFiles` containing `name` and `contentBase64`. The client supplies defaults and serialization; prefer its API.

The response contains `profileId`, `workflowId`, `mapping`, `numProcesses`, `engineId`, `runId`, timestamps, `wallSeconds`, `metadata`, `perPe`, `instances`, and replacement status (`inProgress`, `lastError`). Individual calls and ZIP bytes are retrieved separately. Raw metric field names follow the dispel4py monitoring schema v2, preserved in `metrics_json` for future queries.

An active execution of the same configuration returns HTTP 409. An unsuccessful engine run returns a failure without replacing completed evidence. A download/page with a stale `runId` returns 409; read the latest report before retrying. Page sizes are 1–10,000. Process budgets are 1–256; simple requires 1. Resource bytes are capped at 64 MiB by default; large workloads should use data already accessible on the engine. The engine rejects oversized artifacts/trace responses rather than saving a partial profile.

## SQL examples (administrator access)

Find one configuration:

```sql
SELECT id, workflow_id, mapping, num_processes, engine_id,
       run_id, started_at, completed_at, wall_seconds
FROM trace_profile
WHERE workflow_id = 47 AND mapping = 'multi'
  AND num_processes = 3 AND engine_id = 'default'
  AND completed_at IS NOT NULL;
```

Rank its PEs by accumulated processing time:

```sql
SELECT m.pe_id, m.total_count, m.total_seconds,
       m.cpu_seconds, m.rss_max_bytes
FROM trace_profile p
JOIN trace_pe m ON m.profile_id = p.id
WHERE p.workflow_id = 47 AND p.mapping = 'multi'
  AND p.num_processes = 3 AND p.engine_id = 'default'
ORDER BY m.total_seconds DESC;
```

Compare engine elapsed times across stored configurations:

```sql
SELECT mapping, num_processes, engine_id, wall_seconds, run_id
FROM trace_profile
WHERE workflow_id = 47 AND completed_at IS NOT NULL
ORDER BY engine_id, mapping, num_processes;
```

Inputs/sampling settings must be checked in `metadata_json` before interpreting this comparison. SQL does not itself enforce the per-user checks applied by the REST service.

The migration is `dispel4py-server/src/main/resources/db/trace_schema.sql`. Primary and foreign keys cascade from registry workflow to profile and its four dependent tables. Storage uses one profile per exact configuration, not a success-history table. Replacement deletes and inserts child rows in one transaction. Lease tokens prevent concurrent/stale writers from replacing the wrong run.
