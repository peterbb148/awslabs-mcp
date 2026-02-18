# Work Continuity Notes

Last updated: 2026-02-18

## Current source-control state

- Branch: `codex/issue-14-readonly-tool-annotations`
- Local repo: `peterbb148/awslabs-mcp`
- Open PR from this branch: none at the moment (next step is to open/update PR after push)

## Active/related GitHub issues

- Read-only tool annotation regression:
  - https://github.com/peterbb148/awslabs-mcp/issues/14
- Start run schema/placeholder normalization:
  - https://github.com/peterbb148/awslabs-mcp/issues/15
- Add cancel-run MCP method:
  - https://github.com/peterbb148/awslabs-mcp/issues/16

## What changed in this session

1. Added MCP-callable server manual:
   - Tool: `GetAHOServerManual`
   - Returns Markdown from in-code templates (not filesystem reads)
   - Registered in both `server.py` and Lambda wrapper
2. Updated manual content to enforce MCP-native usage:
   - Explicitly avoids AWS CLI fallback guidance for normal operations
   - Adds MCP-only rerun sequence
3. Diagnosed connector schema drift for `StartAHORun`:
   - Some ChatGPT connector surfaces still report all-string required fields
4. Added compatibility handling in `start_run`:
   - Normalizes stale placeholder values (`"", "0", "null", "none"`)
   - Accepts stringified `parameters` JSON and converts to dict
   - Retries without optional `workflowVersionName/cacheId/cacheBehavior` when AWS reports
     missing workflow version or run cache (`ValidationException`/`ResourceNotFoundException`)
5. Created issue to add run cancellation tool:
   - `CancelAHORun` tracked in issue #16

## Latest deployment state

- Lambda function: `mcp-healthomics-server` (`eu-west-1`)
- Latest image deployed:
  - `138681986447.dkr.ecr.eu-west-1.amazonaws.com/awslabs/aws-healthomics-mcp-server:omics-issue14-start-run-compat-20260218-074546`
- Prior image tags deployed during verification:
  - `...:omics-issue14-docs-20260218-072416`
  - `...:omics-issue14-manual-20260218-073257`
  - `...:omics-issue14-start-run-compat-20260218-074350`

## Live runtime validations completed

- `tools/list` exposes `GetAHOServerManual` with read-only annotation.
- `GetAHOServerManual(section="all")` returns Markdown content.
- `ListAHOWorkflows` executes successfully through deployed Lambda path.
- `StartAHORun` works with minimal payload (no workflow version/cache required).
- `StartAHORun` also works with stale all-string connector payload shape after compatibility fix.

## Temporary validation runs started and canceled

- `4930296` (compat validation): canceled.
- `8587294` (stale-schema validation): canceled (was `STOPPING` on last check).
- User-requested run `9533660` canceled via CLI (was `STOPPING` on last check).

## Tests run during this session

- `uv run pytest tests/test_helper_tools.py -q` -> pass
- `uv run pytest tests/test_server.py -q` -> pass
- Targeted `workflow_execution` tests for `StartAHORun` compatibility and retries -> pass

## Resume workflow

1. Commit and push this branch.
2. Open/update PR against `main`.
3. Merge after review.
4. Implement issue #16 (`CancelAHORun`) on a new branch after this PR is merged.
