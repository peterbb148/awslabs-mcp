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

### MCP-native guidance endpoint

Use `GetAHOServerManual` to retrieve runtime guidance as Markdown directly from the MCP server.
This is the canonical guidance surface for clients and should be preferred over external fallback
instructions.

## Example deployment flow

1. Lint WDL/CWL files.
2. Package bundle with `PackageAHOWorkflow`.
3. Create workflow with `CreateAHOWorkflow`.
4. Start run with `StartAHORun`.
5. Monitor until `COMPLETED`.
6. Review outputs in `output_uri` S3 prefix.

## Lambda container requirements (API Gateway deployment)

When deploying this MCP server behind API Gateway using containerized Lambda:

1. Build from a Lambda runtime base image (`public.ecr.aws/lambda/python:*`), not SAM build images.
2. Ensure image entrypoint remains Lambda default (`/lambda-entrypoint.sh`).
3. Set Lambda handler command to:
   `awslabs.aws_healthomics_mcp_server.lambda_handler.lambda_handler`
4. Ensure `awslabs.mcp_lambda_handler` is installed in the image.

If the image is built with a CLI-style `ENTRYPOINT`, Lambda will fail before request handling.

## Post-deploy smoke tests

After updating the image and Lambda function:

1. Check function config:
   `aws lambda get-function-configuration --function-name mcp-healthomics-server --region eu-west-1`
2. Confirm `ImageConfigResponse.ImageConfig.Command` points to the handler above.
3. Run a direct invoke with a `tools/call` payload for `StartAHORun`.
4. Verify Lambda response is JSON-RPC (not `Runtime.InvalidEntrypoint`).
5. Verify `StartAHORun` with `parameters` as JSON string creates a run (or returns a service-level error, not local validation failure).

Additional HealthOmics search smoke checks:

6. Run `tools/list` and verify:
   - `SearchGenomicsFiles.inputSchema.properties.search_terms.type == "array"`
   - `ListAHOReferences.inputSchema.required` includes `reference_store_id`
   - `ListAHOReferences` does **not** expose `ctx`
7. Run `tools/call` with `ListAHOReferences` and confirm it returns real reference data
   (not a coroutine object and no `FieldInfo` validation errors).

## Build and deploy checklist (required)

Use this exact sequence for containerized Lambda updates:

1. Build and push `amd64` image:
   `docker buildx build --platform linux/amd64 -t <ECR_URI>:<TAG> --push src/aws-healthomics-mcp-server`
2. Update Lambda:
   `aws lambda update-function-code --function-name mcp-healthomics-server --region eu-west-1 --image-uri <ECR_URI>:<TAG>`
3. Wait for completion:
   `aws lambda wait function-updated --function-name mcp-healthomics-server --region eu-west-1`
4. Verify handler command:
   `aws lambda get-function-configuration --function-name mcp-healthomics-server --region eu-west-1 --query 'ImageConfigResponse.ImageConfig.Command'`
5. Run smoke invoke using MCP `tools/call` payload and confirm:
   - No `Runtime.InvalidEntrypoint`
   - No `Runtime.ImportModuleError`
   - Tool response is valid JSON-RPC

## Live API Gateway and OAuth configuration snapshot

The following configuration was reverse-engineered from the live AWS deployment on
February 13, 2026.

### API Gateway (HTTP API v2)

- Region: `eu-west-1`
- API name: `mcp-healthomics-api`
- API ID: `osgs2j07zf`
- API endpoint: `https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com`
- Stage: `stable` (`AutoDeploy=true`)
- CORS:
  - `AllowOrigins=["*"]`
  - `AllowMethods=["GET","POST","OPTIONS"]`
- Integration:
  - Type: `AWS_PROXY` (Lambda proxy, payload format `2.0`)
  - Integration method: `POST`
  - Timeout: `30000` ms
  - Target Lambda:
    `arn:aws:lambda:eu-west-1:138681986447:function:mcp-healthomics-server`
- Stage throttling:
  - Burst limit: `500`
  - Rate limit: `1000`
- Stage access logs:
  - Log group:
    `arn:aws:logs:eu-west-1:138681986447:log-group:/aws/apigateway/mcp-healthomics`
  - Detailed metrics: enabled
- Custom domain mappings: none configured at capture time

### API Gateway route authorization model

JWT-protected routes:

- `ANY /`
- `ANY /{proxy+}`

Public (no auth) routes:

- `GET /.well-known/openid-configuration`
- `GET /.well-known/oauth-authorization-server`
- `GET /.well-known/{proxy+}`
- `POST /register`
- `ANY /callback`
- `ANY /logout`

### JWT authorizer

- Authorizer name: `cognito_jwt`
- Authorizer type: `JWT`
- Identity source: `$request.header.Authorization`
- Issuer:
  `https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_FejeFJmNE`
- Audience (app client ID): `6r52ekr37jn84nlusjgn6j7f8m`

### Cognito app client used by API authorizer

- User pool ID: `eu-west-1_FejeFJmNE`
- Client name: `carlsberg-healthomics-users-app-client`
- Client ID: `6r52ekr37jn84nlusjgn6j7f8m`
- Allowed OAuth flow: `code` (authorization code)
- Allowed OAuth scopes: `openid`, `profile`, `email`
- Supported identity providers: `AzureAD`
- Callback URLs:
  - `https://chatgpt.com/connector_platform_oauth_redirect`
  - `https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com/stable/callback`
- Logout URL:
  - `https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com/stable/logout`

## Common deployment failures

1. `AccessDenied` on workflow/run creation:
   Missing `omics:*` permissions or `iam:PassRole`.
2. `Runtime.InvalidEntrypoint` on Lambda invoke:
   Container image was built with non-Lambda entrypoint or missing handler module.
3. Role pass failure:
   Execution role trust/policies are incomplete.
4. S3 definition URI errors:
   Bad path, missing object, or missing S3 permissions.
5. Input/output URI issues:
   Invalid S3 path format or missing bucket policy access.
6. Region mismatch:
   HealthOmics region and referenced resources are incompatible.
7. `SearchGenomicsFiles` contract mismatch:
   If `search_terms` is shown as `string` in `tools/list`, redeploy the latest image.
8. `ListAHOReferences` fails with `ctx`/coroutine/`FieldInfo` errors:
   Indicates an outdated Lambda MCP handler image; redeploy latest handler fixes.
9. `SearchGenomicsFiles` fails immediately with "No S3 bucket paths configured":
   Set `GENOMICS_SEARCH_S3_BUCKETS` (for example `s3://crl-sandbox-data-bucket/`).
10. `SearchGenomicsFiles` returns
   "There is no current event loop in thread 'MainThread'":
   Use a build that includes the Python 3.13 async-bridge fix in
   `lambda_handler._run_async` (`asyncio.run(...)`).
11. `StartAHORun` appears in client schema as all-string/all-required:
   This is a connector-side schema drift condition. Use a build that includes
   server-side placeholder normalization and retry-without-optional-fields behavior
   (latest compatibility image tags in `WORK_CONTINUITY.md`).
12. Client cannot stop runs from MCP:
   `CancelAHORun` is not exposed yet in current toolset. Track implementation in:
   https://github.com/peterbb148/awslabs-mcp/issues/16
