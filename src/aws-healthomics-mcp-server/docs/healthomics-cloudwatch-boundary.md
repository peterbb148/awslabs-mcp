# Healthomics-CloudWatch Boundary

## Decision

Use a workflow-native interface in `aws-healthomics-mcp-server` and keep CloudWatch details hidden
from normal users.

Use `cloudwatch-mcp-server` for advanced/operator log-native operations.

## Why

- HealthOmics APIs provide coarse lifecycle and task state.
- Detailed execution progress is often only visible in CloudWatch task/engine logs.
- Users should not need to know CloudWatch log group/stream names to monitor workflows.
- Separation keeps IAM scope tighter and avoids coupling deployment of both servers.

## Responsibilities

### aws-healthomics-mcp-server

- Primary user-facing workflow interface.
- Run/task lifecycle operations.
- Server-side orchestration of HealthOmics metadata and CloudWatch-derived detail where required.
- Stable workflow-centric contracts (`run_id`, `task_id`) without exposing CloudWatch identifiers.

### cloudwatch-mcp-server

- Advanced log retrieval and log analytics.
- Generic log exploration and ad-hoc querying.
- Operator-focused debugging workflows.

## User Experience Rules

- Standard monitoring tools must accept workflow-native inputs only.
- The server must internally resolve any log destinations.
- If detailed logs are missing, tools must degrade to coarse HealthOmics status and state this clearly.

## Implementation sequence

1. Define and approve this boundary.
2. Define structured workflow event schema and taxonomy.
3. Implement task-log tailing and run-summary aggregation using internal orchestration.
4. Add hybrid progress reporting with explicit confidence/fallback modes.

