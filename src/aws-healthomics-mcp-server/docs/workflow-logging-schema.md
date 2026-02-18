# Workflow Logging Schema (v1)

## Purpose

Define a machine-consumable JSON event schema for workflow/task telemetry emitted to CloudWatch.
This enables MCP tools to compute meaningful progress, summarize state, and diagnose failures
without requiring users to understand CloudWatch internals.

This schema is optimized for:
- MCP server parsing and aggregation
- LLM consumption
- WDL/Snakemake/engine-agnostic workflow telemetry

## Scope

- Applies to application-emitted workflow telemetry events.
- Does not replace native HealthOmics lifecycle events.
- Intended for task/workflow scripts and wrappers writing JSON log lines.

## Versioning

- `schema_version` is required.
- Initial version: `1.0`.
- Backward-incompatible changes require a new major version.

## Canonical Event Envelope

Each log line should be one JSON object with these top-level fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | yes | Schema version (for example `1.0`) |
| `event_time` | string (RFC3339 UTC) | yes | Event timestamp |
| `event_id` | string | yes | Unique event identifier |
| `event_type` | string | yes | Event kind (see taxonomy doc) |
| `severity` | string enum | yes | `DEBUG` \| `INFO` \| `WARN` \| `ERROR` |
| `workflow_id` | string | yes | HealthOmics workflow ID |
| `run_id` | string | yes | HealthOmics run ID |
| `task_id` | string or null | no | HealthOmics task ID (null for run-level events) |
| `task_name` | string or null | no | Logical task name |
| `attempt` | integer | no | Retry attempt number (1-based) |
| `stage` | string | no | Phase within task/run (for example `import`, `align`, `index`) |
| `message` | string | yes | Human-readable summary |
| `duration_ms` | integer or null | no | Duration for completed operation |
| `correlation_id` | string | no | Cross-event correlation key |
| `progress` | object or null | no | Structured progress payload |
| `error` | object or null | no | Structured error payload |
| `labels` | object<string,string> | no | Low-cardinality tags |

## Structured Sub-objects

### `progress` object

| Field | Type | Required | Description |
|---|---|---|---|
| `percent` | number (0-100) | no | Deterministic completion estimate |
| `completed_units` | integer | no | Completed work units |
| `total_units` | integer | no | Total work units |
| `unit` | string | no | Unit label (`records`, `bases`, `chunks`) |
| `eta_seconds` | integer | no | Estimated remaining time |

At least one of `percent` or (`completed_units` + `total_units`) should be present for
progress-bearing events.

### `error` object

| Field | Type | Required | Description |
|---|---|---|---|
| `code` | string | no | Stable error code |
| `category` | string | no | Broad class (`INPUT`, `PERMISSION`, `RESOURCE`, `ENGINE`) |
| `retryable` | boolean | no | Indicates safe retry |
| `details` | object | no | Extra structured details |

## Minimal Required Fields by Event Class

- Run-level events: `workflow_id`, `run_id`, `event_type`, `severity`, `message`
- Task-level events: all above + `task_id`, `task_name`
- Retry events: task-level + `attempt`
- Progress events: corresponding level + `progress`
- Error/failure events: corresponding level + `error` (recommended)

## Example Events

### RUN_STARTED

```json
{
  "schema_version": "1.0",
  "event_time": "2026-02-18T19:17:14Z",
  "event_id": "evt-0001",
  "event_type": "RUN_STARTED",
  "severity": "INFO",
  "workflow_id": "3677759",
  "run_id": "3978063",
  "task_id": null,
  "task_name": null,
  "stage": "orchestration",
  "message": "Run entered RUNNING state",
  "correlation_id": "run-3978063"
}
```

### TASK_PROGRESS (WDL-style indexing)

```json
{
  "schema_version": "1.0",
  "event_time": "2026-02-18T19:35:37Z",
  "event_id": "evt-0327",
  "event_type": "TASK_PROGRESS",
  "severity": "INFO",
  "workflow_id": "3677759",
  "run_id": "3978063",
  "task_id": "3367394",
  "task_name": "IndexReference",
  "attempt": 1,
  "stage": "bwa_index",
  "message": "BWT iteration progress",
  "progress": {
    "completed_units": 1299999996,
    "total_units": 8786896236,
    "unit": "bases"
  },
  "correlation_id": "run-3978063-task-3367394"
}
```

### TASK_FAILED

```json
{
  "schema_version": "1.0",
  "event_time": "2026-02-18T20:03:20Z",
  "event_id": "evt-1041",
  "event_type": "TASK_FAILED",
  "severity": "ERROR",
  "workflow_id": "3677759",
  "run_id": "3978063",
  "task_id": "3367394",
  "task_name": "IndexReference",
  "attempt": 2,
  "stage": "bwa_index",
  "message": "Task failed with non-zero exit code",
  "duration_ms": 164320,
  "error": {
    "code": "EXIT_NON_ZERO",
    "category": "ENGINE",
    "retryable": false,
    "details": {
      "exit_code": 137
    }
  },
  "correlation_id": "run-3978063-task-3367394"
}
```

## Client Interpretation Guidance

- Treat HealthOmics run/task state as authoritative lifecycle truth.
- Treat structured workflow telemetry as progress/detail enrichment.
- Ignore unknown fields for forward compatibility.
- Prefer structured `progress` over regex parsing unstructured messages.

## Relationship to MCP tools

When this schema is present in task logs:
- `GetAHORunProgress` can compute higher-confidence progress.
- `GetAHORunSummary` can produce cleaner, machine-grounded highlights.
- `TailAHORunTaskLogs` can surface structured signals with less ambiguity.
