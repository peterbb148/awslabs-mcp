# Logging Operations Policy

## Purpose

Define operational logging policy for HealthOmics workflow telemetry in CloudWatch:
- retention tiers
- sensitive data redaction
- correlation strategy
- reusable CloudWatch Logs Insights query patterns

This policy complements:
- `docs/workflow-logging-schema.md`
- `docs/workflow-event-taxonomy.md`
- `docs/healthomics-cloudwatch-boundary.md`

## Scope

- Applies to application-emitted workflow/task telemetry and operational summaries.
- Applies to logs processed by MCP monitoring tools.
- Does not authorize logging of PHI/raw biological payloads.

## Retention Policy

Use separate retention tiers by log value and sensitivity.

| Tier | Typical content | Retention | Notes |
|---|---|---|---|
| `debug-verbose` | high-volume step/debug events | 7-14 days | Short-lived; disable by default in production |
| `ops-standard` | run/task lifecycle, progress, retries | 30-90 days | Default operational window |
| `summary-error` | failures, terminal summaries, key diagnostics | 180-365 days | Supports long investigations and audit trails |

Policy recommendations:
- keep default production telemetry at `ops-standard`
- forward terminal failure summaries to `summary-error`
- avoid storing raw payloads in any tier

## Sensitive Data and Redaction Policy

### Never log

- PHI or direct identifiers (names, emails, DOB, patient IDs)
- genomic sequence payload content (FASTA/FASTQ/BAM body)
- access tokens, OAuth codes, API keys, AWS secret material
- full S3 pre-signed URLs or credentials in query strings

### Allowed with care

- resource identifiers (`run_id`, `task_id`, workflow IDs)
- bucket names and sanitized object prefixes
- file sizes, durations, and aggregate counters

### Redaction rules

- replace sensitive values with stable placeholders:
  - `<REDACTED_TOKEN>`
  - `<REDACTED_ID>`
  - `<REDACTED_SEQUENCE_PATH>`
- preserve structure while redacting value content
- hash only when deterministic matching is required (`sha256:<digest>`)

## Correlation-ID Strategy

Correlation is required across run/task/system logs.

### Required fields

- `correlation_id` (schema field)
- `run_id`
- `task_id` for task events
- `event_id` unique per event

### Canonical formats

- run scope: `run-{run_id}`
- task scope: `run-{run_id}-task-{task_id}`
- retry scope: `run-{run_id}-task-{task_id}-attempt-{attempt}`

### Propagation guidance

- initialize run-level `correlation_id` when run starts
- derive task correlation deterministically from run/task IDs
- preserve correlation IDs in all retry and terminal events

## Field Conventions for Operations

For machine-friendly operations and Insights queries:

- `event_time`: RFC3339 UTC
- `severity`: `DEBUG|INFO|WARN|ERROR`
- `event_type`: taxonomy enum from `workflow-event-taxonomy.md`
- `duration_ms`: integer milliseconds
- `labels`: low-cardinality key/value tags only

## CloudWatch Logs Insights Query Patterns

Use these as saved query templates.

Note: replace `<RUN_ID>`, `<TASK_ID>`, and `<N>` as needed.

### 1) Active run troubleshooting

```sql
fields @timestamp, @message
| filter @message like /"run_id":"<RUN_ID>"/
| sort @timestamp desc
| limit 200
```

### 2) Stalled task detection

Detect tasks with start/progress but no terminal event in the window.

```sql
fields @timestamp, event_type, task_id, task_name, run_id
| filter run_id = "<RUN_ID>"
| filter event_type in ["TASK_STARTED","TASK_PROGRESS","TASK_COMPLETED","TASK_FAILED"]
| stats
    latest(@timestamp) as last_seen,
    count_if(event_type="TASK_PROGRESS") as progress_events,
    count_if(event_type in ["TASK_COMPLETED","TASK_FAILED"]) as terminal_events
  by task_id, task_name
| filter terminal_events = 0
| sort last_seen asc
```

### 3) Failure root-cause extraction

```sql
fields @timestamp, severity, event_type, task_id, task_name, error.code, error.category, message
| filter run_id = "<RUN_ID>"
| filter severity = "ERROR" or event_type in ["TASK_FAILED","RUN_FAILED"]
| sort @timestamp desc
| limit 100
```

### 4) Run summary extraction

```sql
fields @timestamp, event_type, severity, task_id, task_name, duration_ms, progress.percent
| filter run_id = "<RUN_ID>"
| stats
    min(@timestamp) as first_event,
    max(@timestamp) as last_event,
    count_if(event_type="TASK_COMPLETED") as tasks_completed,
    count_if(event_type="TASK_FAILED") as tasks_failed,
    latest(progress.percent) as latest_percent
  by run_id
```

### 5) Retry hotspot identification (lookback window)

```sql
fields @timestamp, run_id, task_name, task_id, attempt, event_type
| filter event_type = "TASK_RETRY"
| stats count() as retries, max(attempt) as max_attempt by run_id, task_name, task_id
| sort retries desc
| limit 50
```

## Operational Guardrails

- production defaults should emit structured lifecycle/progress/error events only
- unstructured stdout/stderr is useful but non-authoritative
- treat schema/taxonomy drift as a quality incident and fix at workflow source
- monitoring tools must degrade gracefully when detailed telemetry is absent

## Compliance Note

This document provides engineering policy guidance, not legal/compliance advice.
Workloads handling regulated data must align with organization-specific security,
privacy, and retention requirements.
