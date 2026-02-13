# Deployment Guide for AWS HealthOmics MCP Server

[← Back to main README](README.md)

This guide covers how to deploy workflow definitions to AWS HealthOmics using the
`aws-healthomics-mcp-server` tools.

## What "deployment" means here

For this server, deployment typically means:

1. Package a WDL/CWL/Nextflow workflow definition.
2. Create or version a HealthOmics workflow in AWS.
3. Start a run and validate outputs in S3.

## Prerequisites

1. AWS account with HealthOmics enabled in your target region.
2. AWS credentials configured (`AWS_PROFILE` or IAM role).
3. An IAM role ARN for HealthOmics run execution (`role_arn` in `StartAHORun`).
4. S3 buckets for workflow assets and run outputs.
5. MCP server configured in your MCP client.

## Required permissions

At minimum, grant the identity running the MCP server:

- `omics:CreateWorkflow`
- `omics:CreateWorkflowVersion`
- `omics:GetWorkflow`
- `omics:ListWorkflows`
- `omics:StartRun`
- `omics:GetRun`
- `omics:ListRuns`
- `omics:ListRunTasks`
- `omics:GetRunTask`
- `logs:DescribeLogGroups`
- `logs:DescribeLogStreams`
- `logs:GetLogEvents`
- `iam:PassRole` (for the execution role used by runs)

If using S3-hosted definitions and outputs, include relevant S3 permissions for the
definition and output buckets.

## Step 1: Validate and package workflow definitions

Use linting before deployment:

- `LintAHOWorkflowDefinition` for single-file workflows
- `LintAHOWorkflowBundle` for multi-file workflows with imports

Then package local files with:

- `PackageAHOWorkflow`

This returns a base64 ZIP that can be passed directly to workflow creation tools.

## Step 2: Create the workflow in AWS HealthOmics

Choose one method:

1. Base64 ZIP method:
   Use `CreateAHOWorkflow` with `definition_zip_base64`.
2. S3 method:
   Upload ZIP to S3 and use `CreateAHOWorkflow` with `definition_uri` (`s3://...`).

Notes:

- Provide only one of `definition_zip_base64` or `definition_uri`.
- Keep the S3 definition bucket in a compatible region for HealthOmics.

## Step 3: Version existing workflows

For updates, use:

- `CreateAHOWorkflowVersion`

Avoid replacing existing workflow definitions in place. Versioning makes rollout and
rollback safer.

## Step 4: Run the deployed workflow

Start execution with:

- `StartAHORun`

Required fields include:

- `workflow_id`
- `role_arn`
- `name`
- `output_uri` (S3 destination for run results)

Track execution with:

- `ListAHORuns`
- `GetAHORun`
- `ListAHORunTasks`
- `GetAHORunTask`

## Step 5: Validate results and troubleshoot

Use:

- `GetAHORunLogs`
- `GetAHORunEngineLogs`
- `GetAHORunManifestLogs`
- `GetAHOTaskLogs`
- `DiagnoseAHORunFailure`
- `AnalyzeAHORunPerformance`

Recommended sequence:

1. `GetAHORun` for top-level status.
2. `DiagnoseAHORunFailure` for root-cause summary.
3. Task and engine logs for detailed debugging.
4. Performance analysis for resource/cost tuning.

## Example deployment flow

1. Lint WDL/CWL files.
2. Package bundle with `PackageAHOWorkflow`.
3. Create workflow with `CreateAHOWorkflow`.
4. Start run with `StartAHORun`.
5. Monitor until `COMPLETED`.
6. Review outputs in `output_uri` S3 prefix.

## Common deployment failures

1. `AccessDenied` on workflow/run creation:
   Missing `omics:*` permissions or `iam:PassRole`.
2. Role pass failure:
   Execution role trust/policies are incomplete.
3. S3 definition URI errors:
   Bad path, missing object, or missing S3 permissions.
4. Input/output URI issues:
   Invalid S3 path format or missing bucket policy access.
5. Region mismatch:
   HealthOmics region and referenced resources are incompatible.

