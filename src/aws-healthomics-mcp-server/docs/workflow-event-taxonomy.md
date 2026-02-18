# Workflow Event Taxonomy (v1)

## Purpose

Define canonical lifecycle event names and semantics for workflow telemetry, independent of
engine/provider-specific wording. This taxonomy is intended to pair with:

- `docs/workflow-logging-schema.md`
- HealthOmics run/task lifecycle APIs

## Event Families

### Run-level events

- `RUN_QUEUED`
  - Run accepted and waiting to start.
- `RUN_STARTED`
  - Run entered active execution.
- `RUN_PROGRESS`
  - Optional run-level aggregate progress update.
- `RUN_COMPLETED`
  - Run finished successfully.
- `RUN_FAILED`
  - Run finished with failure.
- `RUN_CANCELLED`
  - Run cancelled by user/system.

### Task-level events

- `TASK_QUEUED`
  - Task admitted and pending scheduling.
- `TASK_STARTED`
  - Task execution started.
- `TASK_PROGRESS`
  - Task emitted measurable progress.
- `TASK_RETRY`
  - Task retry initiated with incremented `attempt`.
- `TASK_COMPLETED`
  - Task completed successfully.
- `TASK_FAILED`
  - Task failed for current/terminal attempt.

### Data/IO events (optional but recommended)

- `INPUT_IMPORT_STARTED`
- `INPUT_IMPORT_COMPLETED`
- `OUTPUT_EXPORT_STARTED`
- `OUTPUT_EXPORT_COMPLETED`

### Diagnostics events (optional)

- `HEARTBEAT`
  - Periodic alive signal for long-running tasks.
- `RESOURCE_USAGE`
  - Structured resource metrics snapshot.
- `CHECKPOINT_WRITTEN`
  - Durable checkpoint emitted.

## Semantics and Constraints

- Events are append-only facts; do not mutate prior event meaning.
- `*_COMPLETED` and `*_FAILED` are terminal for a given scope and attempt.
- `TASK_RETRY` must carry incremented `attempt` and reference prior failure.
- `TASK_PROGRESS` should include structured `progress` object whenever possible.
- Event timestamps should be UTC RFC3339.

## Mapping from Common HealthOmics/Engine Signals

This table maps frequently observed operational signals to taxonomy events.

| Source signal (example) | Canonical event |
|---|---|
| `CREATING_RUN` | `RUN_QUEUED` |
| `RUNNING_WORKFLOW` | `RUN_STARTED` |
| `RUN_COMPLETED` | `RUN_COMPLETED` |
| `RUN_CANCELLED` | `RUN_CANCELLED` |
| `STARTING_TASK` / `RUNNING_TASK` | `TASK_STARTED` |
| `TASK_COMPLETED` | `TASK_COMPLETED` |
| task shell output with measurable units | `TASK_PROGRESS` |
| task non-zero exit + retry trigger | `TASK_FAILED` then `TASK_RETRY` |
| `IMPORTING_FILES` | `INPUT_IMPORT_STARTED` |
| `IMPORT_COMPLETED` | `INPUT_IMPORT_COMPLETED` |
| `EXPORTING_RESULTS` | `OUTPUT_EXPORT_STARTED` |
| `EXPORT_COMPLETED` | `OUTPUT_EXPORT_COMPLETED` |

## Retry Model

- `attempt` is 1-based and required for task-level retry-aware events.
- A retry sequence is:
  1. `TASK_FAILED` (`attempt=n`)
  2. `TASK_RETRY` (`attempt=n+1`)
  3. `TASK_STARTED` (`attempt=n+1`)

## LLM/MCP Consumption Rules

- Prefer canonical event types over parsing free-text messages.
- Use run/task terminal events to determine completion, not heuristics.
- Use structured `progress` payload to calculate confidence and percent.
- If taxonomy signals are absent, degrade to coarse lifecycle mode.

## Example Sequence

1. `RUN_QUEUED`
2. `RUN_STARTED`
3. `TASK_STARTED` (`task=IndexReference`, `attempt=1`)
4. `TASK_PROGRESS` (`completed_units=1.3e9`, `total_units=8.7e9`)
5. `TASK_COMPLETED`
6. `RUN_COMPLETED`
