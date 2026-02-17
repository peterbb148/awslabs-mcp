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

- `StartAHORun` with stringified `parameters` now succeeds through deployed Lambda path.
- Validation run created and cancelled during test:
  - Run ID: `7936295`
  - Final status: `CANCELLED`

## Current deployment reference

- Lambda function: `mcp-healthomics-server` (eu-west-1)
- Image tag deployed during latest validation:
  - `138681986447.dkr.ecr.eu-west-1.amazonaws.com/awslabs/aws-healthomics-mcp-server:omics-full-fix-20260217-2002`

## Resume workflow

1. Merge PR #12.
2. Build/push amd64 image from merged code.
3. Update Lambda image and run smoke tests from `DEPLOYMENT.md`.
4. For next bugfix branch, branch from latest custom baseline tag (or create a new baseline tag after merge).
