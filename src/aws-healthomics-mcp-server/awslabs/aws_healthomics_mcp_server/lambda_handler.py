# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AWS Lambda handler for the AWS HealthOmics MCP Server.

This module provides a Lambda-compatible HTTP handler for the MCP server,
enabling deployment to AWS Lambda with API Gateway integration.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Union

from awslabs.mcp_lambda_handler import MCPLambdaHandler
from loguru import logger

# Import version info
from awslabs.aws_healthomics_mcp_server import __version__
from awslabs.aws_healthomics_mcp_server.tools.annotation_store_tools import (
    get_aho_annotation_import_job,
    get_aho_annotation_store,
    list_aho_annotation_stores,
    search_aho_annotations,
    start_aho_annotation_import_job,
)
from awslabs.aws_healthomics_mcp_server.tools.codeconnections import (
    create_codeconnection,
    get_codeconnection,
    list_codeconnections,
)
from awslabs.aws_healthomics_mcp_server.tools.data_import_tools import (
    discover_aho_genomic_files,
    get_aho_s3_file_metadata,
    list_aho_s3_bucket_contents,
    prepare_aho_import_sources,
    validate_aho_s3_uri_format,
)
from awslabs.aws_healthomics_mcp_server.tools.ecr_tools import (
    check_container_availability,
    clone_container_to_ecr,
    create_container_registry_map,
    create_pull_through_cache_for_healthomics,
    grant_healthomics_repository_access,
    list_ecr_repositories,
    list_pull_through_cache_rules,
    validate_healthomics_ecr_config,
)
from awslabs.aws_healthomics_mcp_server.tools.reference_store_tools import (
    get_aho_reference,
    get_aho_reference_import_job,
    get_aho_reference_store,
    list_aho_reference_stores,
    list_aho_references,
    start_aho_reference_import_job,
)
from awslabs.aws_healthomics_mcp_server.tools.run_timeline import generate_run_timeline
from awslabs.aws_healthomics_mcp_server.tools.sequence_store_tools import (
    get_aho_read_set,
    get_aho_read_set_import_job,
    list_aho_read_set_import_jobs,
    list_aho_read_sets,
    list_aho_sequence_stores,
    start_aho_read_set_import_job,
)
from awslabs.aws_healthomics_mcp_server.tools.variant_store_tools import (
    count_aho_variants,
    get_aho_variant_import_job,
    get_aho_variant_store,
    list_aho_variant_stores,
    search_aho_variants,
    start_aho_variant_import_job,
)


# ============================================================================
# OAuth Discovery Configuration
# ============================================================================

def get_oauth_config() -> Dict[str, str]:
    """Get OAuth configuration from environment variables.

    Environment variables:
        OAUTH_ISSUER: The OAuth issuer URL (e.g., Cognito User Pool URL)
        OAUTH_AUTHORIZATION_ENDPOINT: The authorization endpoint URL
        OAUTH_TOKEN_ENDPOINT: The token endpoint URL
        OAUTH_CLIENT_ID: The OAuth client ID for pre-registered clients
        MCP_SERVER_BASE_URL: The base URL of this MCP server (for registration endpoint)

    Returns:
        Dictionary with OAuth configuration
    """
    return {
        'issuer': os.environ.get(
            'OAUTH_ISSUER',
            'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_FejeFJmNE'
        ),
        'authorization_endpoint': os.environ.get(
            'OAUTH_AUTHORIZATION_ENDPOINT',
            'https://carlsberg-healthomics-auth.auth.eu-west-1.amazoncognito.com/oauth2/authorize'
        ),
        'token_endpoint': os.environ.get(
            'OAUTH_TOKEN_ENDPOINT',
            'https://carlsberg-healthomics-auth.auth.eu-west-1.amazoncognito.com/oauth2/token'
        ),
        'client_id': os.environ.get(
            'OAUTH_CLIENT_ID',
            '6r52ekr37jn84nlusjgn6j7f8m'
        ),
        'base_url': os.environ.get(
            'MCP_SERVER_BASE_URL',
            'https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com/stable'
        ),
    }


def get_oauth_metadata(base_url: str = '') -> Dict[str, Any]:
    """Get OAuth 2.0 Authorization Server Metadata.

    Args:
        base_url: Base URL of this server for registration endpoint (optional override)

    Returns:
        OAuth 2.0 Authorization Server Metadata document (RFC 8414)
    """
    config = get_oauth_config()

    # Use provided base_url or fall back to config
    effective_base_url = base_url or config['base_url']

    metadata = {
        'issuer': config['issuer'],
        'authorization_endpoint': config['authorization_endpoint'],
        'token_endpoint': config['token_endpoint'],
        'response_types_supported': ['code'],
        'grant_types_supported': ['authorization_code', 'refresh_token'],
        'code_challenge_methods_supported': ['S256'],
        'token_endpoint_auth_methods_supported': ['none', 'client_secret_post'],
        'scopes_supported': ['openid', 'email', 'profile'],
    }

    # Add registration endpoint for RFC 7591 Dynamic Client Registration
    if effective_base_url:
        metadata['registration_endpoint'] = f'{effective_base_url}/register'

    return metadata


def handle_dynamic_client_registration(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle RFC 7591 Dynamic Client Registration requests.

    Since Cognito doesn't support DCR natively, we return a pre-registered
    client configuration. This allows ChatGPT and other clients to "register"
    and receive the existing client credentials.

    Args:
        event: Lambda event object

    Returns:
        HTTP response if this is a registration request, None otherwise
    """
    path = event.get('path', '') or event.get('rawPath', '')
    method = event.get('httpMethod', '') or event.get('requestContext', {}).get('http', {}).get('method', '')

    # Handle POST /register for dynamic client registration
    if (path.endswith('/register') or path == '/register') and method == 'POST':
        logger.info('Handling dynamic client registration request')

        # Parse the registration request body
        body = event.get('body', '{}')
        if event.get('isBase64Encoded'):
            import base64
            body = base64.b64decode(body).decode('utf-8')

        try:
            registration_request = json.loads(body) if body else {}
        except json.JSONDecodeError:
            registration_request = {}

        config = get_oauth_config()

        # Return pre-registered client credentials
        # This simulates DCR by returning existing Cognito app client
        client_response = {
            'client_id': config['client_id'],
            'client_name': registration_request.get('client_name', 'ChatGPT MCP Client'),
            'redirect_uris': registration_request.get('redirect_uris', []),
            'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'],
            'token_endpoint_auth_method': 'none',
            # RFC 7591 requires these fields
            'client_id_issued_at': 0,  # Unknown, pre-registered
            'client_secret_expires_at': 0,  # Never expires
        }

        logger.info(f'Returning pre-registered client: {config["client_id"]}')

        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-store',
            },
            'body': json.dumps(client_response),
        }

    return None


def get_base_url(event: Dict[str, Any]) -> str:
    """Extract base URL from the Lambda event.

    Args:
        event: Lambda event object

    Returns:
        Base URL string (e.g., https://api.example.com/stage)
    """
    # Try to get from requestContext (API Gateway v2)
    request_context = event.get('requestContext', {})

    # API Gateway HTTP API (v2)
    if 'domainName' in request_context:
        domain = request_context['domainName']
        stage = request_context.get('stage', '')
        if stage and stage != '$default':
            return f'https://{domain}/{stage}'
        return f'https://{domain}'

    # API Gateway REST API (v1)
    if 'domain_name' in request_context:
        domain = request_context['domain_name']
        stage = request_context.get('stage', '')
        if stage:
            return f'https://{domain}/{stage}'
        return f'https://{domain}'

    # Fallback to headers
    headers = event.get('headers', {})
    host = headers.get('Host') or headers.get('host', '')
    if host:
        return f'https://{host}'

    return ''


def handle_oauth_discovery(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle OAuth discovery requests.

    Args:
        event: Lambda event object

    Returns:
        HTTP response if this is an OAuth discovery request, None otherwise
    """
    # Get the path from the event
    path = event.get('path', '') or event.get('rawPath', '')
    base_url = get_base_url(event)

    # Check for OAuth discovery endpoints
    if path.endswith('/.well-known/oauth-authorization-server') or \
       path == '/.well-known/oauth-authorization-server':
        logger.info('Serving OAuth authorization server metadata')
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=3600',
            },
            'body': json.dumps(get_oauth_metadata(base_url)),
        }

    # Also support OpenID Connect discovery
    if path.endswith('/.well-known/openid-configuration') or \
       path == '/.well-known/openid-configuration':
        logger.info('Serving OpenID Connect discovery document')
        metadata = get_oauth_metadata(base_url)
        # Add OIDC-specific fields
        metadata['id_token_signing_alg_values_supported'] = ['RS256']
        metadata['subject_types_supported'] = ['public']
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=3600',
            },
            'body': json.dumps(metadata),
        }

    return None


# Create the MCP Lambda handler instance (stateless)
mcp = MCPLambdaHandler(
    name='awslabs.aws-healthomics-mcp-server',
    version=__version__,
)

def _register_lambda_tool(tool_name: str, tool_fn: Any) -> None:
    """Register async tool functions with custom names for MCPLambdaHandler."""
    tool_fn.__name__ = tool_name
    mcp.tool()(tool_fn)


# Register Lambda tools that are present in server.py but not wrapped below.
_register_lambda_tool('GenerateAHORunTimeline', generate_run_timeline)

# CodeConnections
_register_lambda_tool('ListCodeConnections', list_codeconnections)
_register_lambda_tool('CreateCodeConnection', create_codeconnection)
_register_lambda_tool('GetCodeConnection', get_codeconnection)

# ECR container tools
_register_lambda_tool('ListECRRepositories', list_ecr_repositories)
_register_lambda_tool('CheckContainerAvailability', check_container_availability)
_register_lambda_tool('CloneContainerToECR', clone_container_to_ecr)
_register_lambda_tool('GrantHealthOmicsRepositoryAccess', grant_healthomics_repository_access)
_register_lambda_tool('ListPullThroughCacheRules', list_pull_through_cache_rules)
_register_lambda_tool(
    'CreatePullThroughCacheForHealthOmics', create_pull_through_cache_for_healthomics
)
_register_lambda_tool('CreateContainerRegistryMap', create_container_registry_map)
_register_lambda_tool('ValidateHealthOmicsECRConfig', validate_healthomics_ecr_config)

# Sequence store tools
_register_lambda_tool('ListAHOSequenceStores', list_aho_sequence_stores)
_register_lambda_tool('ListAHOReadSets', list_aho_read_sets)
_register_lambda_tool('GetAHOReadSet', get_aho_read_set)
_register_lambda_tool('StartAHOReadSetImportJob', start_aho_read_set_import_job)
_register_lambda_tool('GetAHOReadSetImportJob', get_aho_read_set_import_job)
_register_lambda_tool('ListAHOReadSetImportJobs', list_aho_read_set_import_jobs)

# Variant store tools
_register_lambda_tool('ListAHOVariantStores', list_aho_variant_stores)
_register_lambda_tool('GetAHOVariantStore', get_aho_variant_store)
_register_lambda_tool('SearchAHOVariants', search_aho_variants)
_register_lambda_tool('CountAHOVariants', count_aho_variants)
_register_lambda_tool('StartAHOVariantImportJob', start_aho_variant_import_job)
_register_lambda_tool('GetAHOVariantImportJob', get_aho_variant_import_job)

# Reference store tools
_register_lambda_tool('ListAHOReferenceStores', list_aho_reference_stores)
_register_lambda_tool('GetAHOReferenceStore', get_aho_reference_store)
_register_lambda_tool('ListAHOReferences', list_aho_references)
_register_lambda_tool('GetAHOReference', get_aho_reference)
_register_lambda_tool('StartAHOReferenceImportJob', start_aho_reference_import_job)
_register_lambda_tool('GetAHOReferenceImportJob', get_aho_reference_import_job)

# Annotation store tools
_register_lambda_tool('ListAHOAnnotationStores', list_aho_annotation_stores)
_register_lambda_tool('GetAHOAnnotationStore', get_aho_annotation_store)
_register_lambda_tool('SearchAHOAnnotations', search_aho_annotations)
_register_lambda_tool('StartAHOAnnotationImportJob', start_aho_annotation_import_job)
_register_lambda_tool('GetAHOAnnotationImportJob', get_aho_annotation_import_job)

# Data import and S3 tools
_register_lambda_tool('DiscoverAHOGenomicFiles', discover_aho_genomic_files)
_register_lambda_tool('ValidateAHOS3URIFormat', validate_aho_s3_uri_format)
_register_lambda_tool('ListAHOS3BucketContents', list_aho_s3_bucket_contents)
_register_lambda_tool('GetAHOS3FileMetadata', get_aho_s3_file_metadata)
_register_lambda_tool('PrepareAHOImportSources', prepare_aho_import_sources)


# Helper to run async functions synchronously
def _run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ============================================================================
# Workflow Management Tools
# ============================================================================


@mcp.tool()
def ListAHOWorkflows(
    max_results: int = 10,
    next_token: Optional[str] = None,
) -> Dict[str, Any]:
    """List available HealthOmics workflows.

    Args:
        max_results: Maximum number of results to return (default: 10)
        next_token: Token for pagination

    Returns:
        Dictionary containing workflow information and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_management import list_workflows

    async def _call():
        # Create a mock context that logs errors instead of using ctx.error()
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await list_workflows(MockContext(), max_results=max_results, next_token=next_token)

    return _run_async(_call())


@mcp.tool()
def CreateAHOWorkflow(
    name: str,
    definition_zip_base64: Optional[str] = None,
    description: Optional[str] = None,
    parameter_template: Optional[Dict[str, Any]] = None,
    container_registry_map: Optional[Dict[str, Any]] = None,
    container_registry_map_uri: Optional[str] = None,
    definition_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new HealthOmics workflow.

    Args:
        name: Name of the workflow
        definition_zip_base64: Base64-encoded workflow definition ZIP file
        description: Optional description of the workflow
        parameter_template: Optional parameter template for the workflow
        container_registry_map: Optional container registry map
        container_registry_map_uri: Optional S3 URI for container registry mappings
        definition_uri: S3 URI of the workflow definition ZIP file

    Returns:
        Dictionary containing the created workflow information
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_management import create_workflow

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await create_workflow(
            MockContext(),
            name=name,
            definition_zip_base64=definition_zip_base64,
            description=description,
            parameter_template=parameter_template,
            container_registry_map=container_registry_map,
            container_registry_map_uri=container_registry_map_uri,
            definition_uri=definition_uri,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHOWorkflow(
    workflow_id: str,
    export_definition: bool = False,
) -> Dict[str, Any]:
    """Get details about a specific workflow.

    Args:
        workflow_id: ID of the workflow to retrieve
        export_definition: Whether to include a presigned URL for downloading the workflow definition

    Returns:
        Dictionary containing workflow details
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_management import get_workflow

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_workflow(
            MockContext(), workflow_id=workflow_id, export_definition=export_definition
        )

    return _run_async(_call())


@mcp.tool()
def CreateAHOWorkflowVersion(
    workflow_id: str,
    version_name: str,
    definition_zip_base64: Optional[str] = None,
    description: Optional[str] = None,
    parameter_template: Optional[Dict[str, Any]] = None,
    storage_type: Optional[str] = 'DYNAMIC',
    storage_capacity: Optional[int] = None,
    container_registry_map: Optional[Dict[str, Any]] = None,
    container_registry_map_uri: Optional[str] = None,
    definition_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new version of an existing workflow.

    Args:
        workflow_id: ID of the workflow
        version_name: Name for the new version
        definition_zip_base64: Base64-encoded workflow definition ZIP file
        description: Optional description of the workflow version
        parameter_template: Optional parameter template for the workflow
        storage_type: Storage type (STATIC or DYNAMIC)
        storage_capacity: Storage capacity in GB (required for STATIC)
        container_registry_map: Optional container registry map
        container_registry_map_uri: Optional S3 URI for container registry mappings
        definition_uri: S3 URI of the workflow definition ZIP file

    Returns:
        Dictionary containing the created workflow version information
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_management import (
        create_workflow_version,
    )

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await create_workflow_version(
            MockContext(),
            workflow_id=workflow_id,
            version_name=version_name,
            definition_zip_base64=definition_zip_base64,
            description=description,
            parameter_template=parameter_template,
            storage_type=storage_type,
            storage_capacity=storage_capacity,
            container_registry_map=container_registry_map,
            container_registry_map_uri=container_registry_map_uri,
            definition_uri=definition_uri,
        )

    return _run_async(_call())


@mcp.tool()
def ListAHOWorkflowVersions(
    workflow_id: str,
    max_results: int = 10,
    next_token: Optional[str] = None,
) -> Dict[str, Any]:
    """List versions of a workflow.

    Args:
        workflow_id: ID of the workflow
        max_results: Maximum number of results to return (default: 10)
        next_token: Token for pagination

    Returns:
        Dictionary containing workflow version information and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_management import list_workflow_versions

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await list_workflow_versions(
            MockContext(), workflow_id=workflow_id, max_results=max_results, next_token=next_token
        )

    return _run_async(_call())


# ============================================================================
# Workflow Execution Tools
# ============================================================================


@mcp.tool()
def StartAHORun(
    workflow_id: str,
    role_arn: str,
    name: str,
    output_uri: str,
    parameters: Optional[Dict[str, Any]] = None,
    workflow_version_name: Optional[str] = None,
    storage_type: str = 'DYNAMIC',
    storage_capacity: Optional[int] = None,
    cache_id: Optional[str] = None,
    cache_behavior: Optional[str] = None,
) -> Dict[str, Any]:
    """Start a workflow run.

    Args:
        workflow_id: ID of the workflow to run
        role_arn: ARN of the IAM role to use for the run
        name: Name for the run
        output_uri: S3 URI for the run outputs
        parameters: Parameters for the workflow
        workflow_version_name: Optional version name to run
        storage_type: Storage type (STATIC or DYNAMIC)
        storage_capacity: Storage capacity in GB (required for STATIC)
        cache_id: Optional ID of a run cache to use
        cache_behavior: Optional cache behavior (CACHE_ALWAYS or CACHE_ON_FAILURE)

    Returns:
        Dictionary containing the run information
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_execution import start_run

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await start_run(
            MockContext(),
            workflow_id=workflow_id,
            role_arn=role_arn,
            name=name,
            output_uri=output_uri,
            parameters=parameters,
            workflow_version_name=workflow_version_name,
            storage_type=storage_type,
            storage_capacity=storage_capacity,
            cache_id=cache_id,
            cache_behavior=cache_behavior,
        )

    return _run_async(_call())


@mcp.tool()
def ListAHORuns(
    max_results: int = 10,
    next_token: Optional[str] = None,
    status: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
) -> Dict[str, Any]:
    """List workflow runs.

    Args:
        max_results: Maximum number of results to return (default: 10)
        next_token: Token for pagination
        status: Filter by run status
        created_after: Filter for runs created after this timestamp (ISO format)
        created_before: Filter for runs created before this timestamp (ISO format)

    Returns:
        Dictionary containing run information and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_execution import list_runs

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await list_runs(
            MockContext(),
            max_results=max_results,
            next_token=next_token,
            status=status,
            created_after=created_after,
            created_before=created_before,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHORun(run_id: str) -> Dict[str, Any]:
    """Get details about a specific run.

    Args:
        run_id: ID of the run to retrieve

    Returns:
        Dictionary containing run details
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_execution import get_run

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_run(MockContext(), run_id=run_id)

    return _run_async(_call())


@mcp.tool()
def ListAHORunTasks(
    run_id: str,
    max_results: int = 10,
    next_token: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """List tasks for a specific run.

    Args:
        run_id: ID of the run
        max_results: Maximum number of results to return (default: 10)
        next_token: Token for pagination
        status: Filter by task status

    Returns:
        Dictionary containing task information and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_execution import list_run_tasks

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await list_run_tasks(
            MockContext(),
            run_id=run_id,
            max_results=max_results,
            next_token=next_token,
            status=status,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHORunTask(run_id: str, task_id: str) -> Dict[str, Any]:
    """Get details about a specific task.

    Args:
        run_id: ID of the run
        task_id: ID of the task

    Returns:
        Dictionary containing task details
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_execution import get_run_task

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_run_task(MockContext(), run_id=run_id, task_id=task_id)

    return _run_async(_call())


# ============================================================================
# Workflow Analysis Tools
# ============================================================================


@mcp.tool()
def GetAHORunLogs(
    run_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    next_token: Optional[str] = None,
    start_from_head: bool = True,
) -> Dict[str, Any]:
    """Retrieve high-level run logs showing workflow execution events.

    Args:
        run_id: ID of the run
        start_time: Optional start time for log retrieval (ISO format)
        end_time: Optional end time for log retrieval (ISO format)
        limit: Maximum number of log events to return (default: 100)
        next_token: Token for pagination
        start_from_head: Whether to start from the beginning (True) or end (False)

    Returns:
        Dictionary containing log events and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_analysis import get_run_logs

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_run_logs(
            MockContext(),
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            next_token=next_token,
            start_from_head=start_from_head,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHORunManifestLogs(
    run_id: str,
    run_uuid: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    next_token: Optional[str] = None,
    start_from_head: bool = True,
) -> Dict[str, Any]:
    """Retrieve run manifest logs with workflow summary.

    Args:
        run_id: ID of the run
        run_uuid: Optional UUID of the run
        start_time: Optional start time for log retrieval (ISO format)
        end_time: Optional end time for log retrieval (ISO format)
        limit: Maximum number of log events to return (default: 100)
        next_token: Token for pagination
        start_from_head: Whether to start from the beginning (True) or end (False)

    Returns:
        Dictionary containing log events and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_analysis import get_run_manifest_logs

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_run_manifest_logs(
            MockContext(),
            run_id=run_id,
            run_uuid=run_uuid,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            next_token=next_token,
            start_from_head=start_from_head,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHORunEngineLogs(
    run_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    next_token: Optional[str] = None,
    start_from_head: bool = True,
) -> Dict[str, Any]:
    """Retrieve engine logs containing STDOUT and STDERR from the workflow engine process.

    Args:
        run_id: ID of the run
        start_time: Optional start time for log retrieval (ISO format)
        end_time: Optional end time for log retrieval (ISO format)
        limit: Maximum number of log events to return (default: 100)
        next_token: Token for pagination
        start_from_head: Whether to start from the beginning (True) or end (False)

    Returns:
        Dictionary containing log events and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_analysis import get_run_engine_logs

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_run_engine_logs(
            MockContext(),
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            next_token=next_token,
            start_from_head=start_from_head,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHOTaskLogs(
    run_id: str,
    task_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    next_token: Optional[str] = None,
    start_from_head: bool = True,
) -> Dict[str, Any]:
    """Retrieve logs for a specific workflow task.

    Args:
        run_id: ID of the run
        task_id: ID of the specific task
        start_time: Optional start time for log retrieval (ISO format)
        end_time: Optional end time for log retrieval (ISO format)
        limit: Maximum number of log events to return (default: 100)
        next_token: Token for pagination
        start_from_head: Whether to start from the beginning (True) or end (False)

    Returns:
        Dictionary containing log events and next token if available
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_analysis import get_task_logs

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_task_logs(
            MockContext(),
            run_id=run_id,
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            next_token=next_token,
            start_from_head=start_from_head,
        )

    return _run_async(_call())


@mcp.tool()
def AnalyzeAHORunPerformance(run_ids: Union[List[str], str]) -> str:
    """Analyze workflow run performance and provide optimization recommendations.

    Args:
        run_ids: List of run IDs to analyze (can be JSON array or comma-separated string)

    Returns:
        Formatted analysis report with optimization recommendations
    """
    from awslabs.aws_healthomics_mcp_server.tools.run_analysis import analyze_run_performance

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await analyze_run_performance(MockContext(), run_ids=run_ids)

    return _run_async(_call())


# ============================================================================
# Troubleshooting Tools
# ============================================================================


@mcp.tool()
def DiagnoseAHORunFailure(run_id: str) -> Dict[str, Any]:
    """Diagnose a failed workflow run.

    Args:
        run_id: ID of the failed run

    Returns:
        Dictionary containing comprehensive diagnostic information
    """
    from awslabs.aws_healthomics_mcp_server.tools.troubleshooting import diagnose_run_failure

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await diagnose_run_failure(MockContext(), run_id=run_id)

    return _run_async(_call())


# ============================================================================
# Workflow Linting Tools
# ============================================================================


@mcp.tool()
def LintAHOWorkflowDefinition(
    workflow_content: str,
    workflow_format: str,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Lint WDL or CWL workflow definitions.

    Args:
        workflow_content: The workflow definition content to lint
        workflow_format: The workflow format ('wdl' or 'cwl')
        filename: Optional filename for context

    Returns:
        Dictionary containing lint results
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_linting import lint_workflow_definition

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await lint_workflow_definition(
            MockContext(),
            workflow_content=workflow_content,
            workflow_format=workflow_format,
            filename=filename,
        )

    return _run_async(_call())


@mcp.tool()
def LintAHOWorkflowBundle(
    workflow_files: Dict[str, str],
    workflow_format: str,
    main_workflow_file: str,
) -> Dict[str, Any]:
    """Lint multi-file WDL or CWL workflow bundles.

    Args:
        workflow_files: Dictionary mapping file paths to their content
        workflow_format: The workflow format ('wdl' or 'cwl')
        main_workflow_file: Path to the main workflow file within the bundle

    Returns:
        Dictionary containing lint results
    """
    from awslabs.aws_healthomics_mcp_server.tools.workflow_linting import lint_workflow_bundle

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await lint_workflow_bundle(
            MockContext(),
            workflow_files=workflow_files,
            workflow_format=workflow_format,
            main_workflow_file=main_workflow_file,
        )

    return _run_async(_call())


# ============================================================================
# Genomics File Search Tools
# ============================================================================


@mcp.tool()
def SearchGenomicsFiles(
    file_type: Optional[str] = None,
    search_terms: Optional[List[str]] = None,
    max_results: int = 100,
    include_associated_files: bool = True,
    offset: int = 0,
    continuation_token: Optional[str] = None,
    enable_storage_pagination: bool = False,
    pagination_buffer_size: int = 500,
    adhoc_s3_buckets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search for genomics files across S3 buckets and HealthOmics stores.

    Args:
        file_type: Optional file type filter (e.g., 'fastq', 'bam', 'vcf')
        search_terms: List of search terms to match against file paths and tags
        max_results: Maximum number of results to return (default: 100)
        include_associated_files: Whether to include associated files in results
        offset: Number of results to skip for pagination
        continuation_token: Continuation token from previous search
        enable_storage_pagination: Enable storage-level pagination for large datasets
        pagination_buffer_size: Buffer size for storage-level pagination
        adhoc_s3_buckets: Optional list of additional S3 bucket paths to search

    Returns:
        Dictionary containing search results and metadata
    """
    from awslabs.aws_healthomics_mcp_server.tools.genomics_file_search import search_genomics_files

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await search_genomics_files(
            MockContext(),
            file_type=file_type,
            search_terms=search_terms or [],
            max_results=max_results,
            include_associated_files=include_associated_files,
            offset=offset,
            continuation_token=continuation_token,
            enable_storage_pagination=enable_storage_pagination,
            pagination_buffer_size=pagination_buffer_size,
            adhoc_s3_buckets=adhoc_s3_buckets,
        )

    return _run_async(_call())


@mcp.tool()
def GetSupportedFileTypes() -> Dict[str, Any]:
    """Get information about supported genomics file types.

    Returns:
        Dictionary containing supported file types and their descriptions
    """
    from awslabs.aws_healthomics_mcp_server.tools.genomics_file_search import (
        get_supported_file_types,
    )

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_supported_file_types(MockContext())

    return _run_async(_call())


# ============================================================================
# Helper Tools
# ============================================================================


@mcp.tool()
def PackageAHOWorkflow(
    main_file_content: str,
    main_file_name: str = 'main.wdl',
    additional_files: Optional[Dict[str, str]] = None,
) -> str:
    """Package workflow definition files into a base64-encoded ZIP.

    Args:
        main_file_content: Content of the main workflow file
        main_file_name: Name of the main workflow file (default: main.wdl)
        additional_files: Dictionary of additional files (filename: content)

    Returns:
        Base64-encoded ZIP file containing the workflow definition
    """
    from awslabs.aws_healthomics_mcp_server.tools.helper_tools import package_workflow

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await package_workflow(
            MockContext(),
            main_file_content=main_file_content,
            main_file_name=main_file_name,
            additional_files=additional_files,
        )

    return _run_async(_call())


@mcp.tool()
def GetAHOSupportedRegions() -> Dict[str, Any]:
    """Get the list of AWS regions where HealthOmics is available.

    Returns:
        Dictionary containing the list of supported region codes
    """
    from awslabs.aws_healthomics_mcp_server.tools.helper_tools import get_supported_regions

    async def _call():
        class MockContext:
            async def error(self, msg):
                logger.error(msg)

        return await get_supported_regions(MockContext())

    return _run_async(_call())


# ============================================================================
# Lambda Handler Entry Point
# ============================================================================


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler function.

    Args:
        event: Lambda event object (API Gateway HTTP event)
        context: Lambda context object

    Returns:
        HTTP response dictionary with statusCode, body, and headers
    """
    logger.info('AWS HealthOmics MCP Lambda handler invoked')

    # Check for OAuth discovery requests first (these don't require auth)
    oauth_response = handle_oauth_discovery(event)
    if oauth_response:
        return oauth_response

    # Check for dynamic client registration requests (RFC 7591)
    dcr_response = handle_dynamic_client_registration(event)
    if dcr_response:
        return dcr_response

    # Handle MCP requests
    return mcp.handle_request(event, context)
