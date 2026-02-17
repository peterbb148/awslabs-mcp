# Work Continuity Notes

Last updated: 2026-02-17

## Current source-control state

- Upstream sync baseline in fork: `main` at commit `bc2d6b0c`
- Custom baseline tag for Healthomics fork layer:
  - `healthomics-custom-baseline-2026-02-17`
- Active bugfix branch:
  - `codex/issue-11-searchgenomics-fieldinfo`
- Active PR:
  - https://github.com/peterbb148/awslabs-mcp/pull/12
- Active issue:
  - https://github.com/peterbb148/awslabs-mcp/issues/11

## What is documented where

- Fork strategy and layering rules:
  - `src/aws-healthomics-mcp-server/CUSTOM_DELTA.md`
- Deployment/runtime contract and smoke tests:
  - `src/aws-healthomics-mcp-server/DEPLOYMENT.md`

## Verified runtime behavior (latest validation)

- `StartAHORun` with stringified `parameters` succeeds through deployed Lambda path.
- `SearchGenomicsFiles` contract is consistent in `tools/list`:
  - `search_terms` is `array[string]` (not `string`)
- `ListAHOReferences` now works via Lambda MCP path:
  - `reference_store_id` is correctly required
  - `ctx` is not exposed
  - async tool execution returns real results (no coroutine text)
  - no `FieldInfo` passthrough errors for optional params like `next_token`
- Verified reference enumeration from store `7661842487`:
  - Found 1 active reference (`hop_pseudomolecules_v1.1_p1_p2_special_organelles.fasta`)
- `SearchGenomicsFiles` with `search_terms=["hop"]` returned:
  - 1 S3 hit in `s3://crl-sandbox-data-bucket/Genomes/References/...`
  - 1 HealthOmics reference-store hit for the same genome
- Python 3.13 event-loop regression fix applied:
  - `lambda_handler._run_async` now uses `asyncio.run(...)`
  - resolves `There is no current event loop in thread 'MainThread'`

## Current deployment reference

- Lambda function: `mcp-healthomics-server` (eu-west-1)
- Image tag deployed during latest validation:
  - `138681986447.dkr.ecr.eu-west-1.amazonaws.com/awslabs/aws-healthomics-mcp-server:omics-issue11-20260217-204504`
- Required env var currently set:
  - `GENOMICS_SEARCH_S3_BUCKETS=s3://crl-sandbox-data-bucket/`

## Resume workflow

1. Push latest branch commit(s) to PR #12.
2. Merge PR #12.
3. Rebuild/push amd64 image from merged `main`.
4. Update Lambda image and rerun smoke tests from `DEPLOYMENT.md`.
