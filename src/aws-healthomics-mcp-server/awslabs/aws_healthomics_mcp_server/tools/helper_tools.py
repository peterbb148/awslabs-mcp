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

"""Helper tools for the AWS HealthOmics MCP server."""

import botocore
import botocore.exceptions
from awslabs.aws_healthomics_mcp_server import __version__
from awslabs.aws_healthomics_mcp_server.utils.aws_utils import (
    create_zip_file,
    encode_to_base64,
    get_aws_session,
    get_omics_service_name,
)
from awslabs.aws_healthomics_mcp_server.utils.error_utils import handle_tool_error
from loguru import logger
from mcp.server.fastmcp import Context
from pydantic import Field
from typing import Any, Dict, Optional, Union


_SERVER_MANUAL_SECTIONS = {
    'overview': """# AWS HealthOmics MCP Server Manual

## Purpose
This MCP server exposes AWS HealthOmics workflow and data-store operations as callable tools for AI clients.

## Operating Principle
- This server is designed for MCP-native operation from AI clients.
- Do not instruct users to fall back to AWS CLI or SDK for normal workflow operations.
- If a tool call is blocked by connector policy or client safety gates, report it as a connector limitation and
  provide the exact MCP tool call that should have been used.

## Authentication
- OAuth is enforced by API Gateway before requests reach this server.
- Tool calls execute with the server's configured AWS identity.
- Authorization to specific HealthOmics resources is enforced by AWS IAM at runtime.

## Tool Categories
- Workflow management and execution
- Run logs, diagnostics, and timeline analysis
- HealthOmics data-store operations (sequence/reference/annotation/variant)
- S3 discovery and import preparation helpers
- ECR and CodeConnections helpers
""",
    'rerun': """# Rerunning A Workflow

Use MCP tools only. Do not substitute CLI commands.

Recommended sequence:
1. Call `GetAHORun` for the source run.
2. Extract and reuse `workflowId`, `roleArn`, `outputUri`, and `parameters` exactly as returned.
3. Call `StartAHORun` with:
   - `workflow_id` from step 1
   - `role_arn` from step 1
   - `output_uri` from step 1
   - `parameters` from step 1
   - new `name` (for example append `_rerun` or `_02`)
4. Monitor with `GetAHORun` and `ListAHORunTasks` until terminal status.
5. If `StartAHORun` fails due to wrapper-required fields that are not required by HealthOmics,
   report a connector contract bug and do not invent placeholders.
6. If you need to stop an in-progress run, call `CancelAHORun` with the target `run_id`.
""",
    'troubleshooting': """# Troubleshooting Guide

## Common checks
- Confirm target region is HealthOmics-enabled (`GetAHOSupportedRegions`).
- Verify workflow and run IDs exist and are accessible.
- Check execution role permissions for S3, Logs, and Omics APIs.
- Retrieve logs with:
  - `GetAHORunProgress`
  - `GetAHORunSummary`
  - `GetAHORunLogs`
  - `GetAHORunManifestLogs`
  - `GetAHORunEngineLogs`
  - `GetAHOTaskLogs`
  - `TailAHORunTaskLogs`
- Use `DiagnoseAHORunFailure` for automated failure analysis.
""",
}


async def package_workflow(
    ctx: Context,
    main_file_content: str = Field(
        ...,
        description='Content of the main workflow file',
    ),
    main_file_name: str = Field(
        'main.wdl',
        description='Name of the main workflow file',
    ),
    additional_files: Optional[Dict[str, str]] = Field(
        None,
        description='Dictionary of additional files (filename: content)',
    ),
) -> Union[str, Dict[str, Any]]:
    """Package workflow definition files into a base64-encoded ZIP.

    Args:
        ctx: MCP context for error reporting
        main_file_content: Content of the main workflow file
        main_file_name: Name of the main workflow file (default: main.wdl)
        additional_files: Dictionary of additional files (filename: content)

    Returns:
        Base64-encoded ZIP file containing the workflow definition, or error dict
    """
    try:
        # Create a dictionary of files
        files = {main_file_name: main_file_content}

        if additional_files:
            files.update(additional_files)

        # Create ZIP file
        zip_data = create_zip_file(files)

        # Encode to base64
        base64_data = encode_to_base64(zip_data)

        return base64_data
    except Exception as e:
        return await handle_tool_error(ctx, e, 'Error packaging workflow')


async def get_supported_regions(
    ctx: Context,
) -> Dict[str, Any]:
    """Get the list of AWS regions where HealthOmics is available.

    Args:
        ctx: MCP context for error reporting

    Returns:
        Dictionary containing the list of supported region codes and the total count
        of regions where HealthOmics is available
    """
    try:
        # Get centralized AWS session
        session = get_aws_session()

        # Get the service name (defaults to 'omics')
        service_name = get_omics_service_name()

        # Get available regions for the HealthOmics service
        regions = session.get_available_regions(service_name)

        # If no regions found, use the hardcoded list as fallback
        if not regions:
            from awslabs.aws_healthomics_mcp_server.consts import HEALTHOMICS_SUPPORTED_REGIONS

            regions = HEALTHOMICS_SUPPORTED_REGIONS
            logger.warning('No regions found via boto3 session. Using hardcoded region list.')

        return {'regions': sorted(regions), 'count': len(regions)}
    except botocore.exceptions.BotoCoreError as e:
        error_message = f'AWS error retrieving supported regions: {str(e)}'
        logger.error(error_message)
        logger.info('Using hardcoded region list as fallback')

        # Use hardcoded list as fallback
        from awslabs.aws_healthomics_mcp_server.consts import HEALTHOMICS_SUPPORTED_REGIONS

        return {
            'regions': sorted(HEALTHOMICS_SUPPORTED_REGIONS),
            'count': len(HEALTHOMICS_SUPPORTED_REGIONS),
            'note': 'Using hardcoded region list due to error: ' + str(e),
        }
    except Exception as e:
        error_message = f'Unexpected error retrieving supported regions: {str(e)}'
        logger.error(error_message)
        await ctx.error(error_message)

        # Use hardcoded list as fallback
        from awslabs.aws_healthomics_mcp_server.consts import HEALTHOMICS_SUPPORTED_REGIONS

        return {
            'regions': sorted(HEALTHOMICS_SUPPORTED_REGIONS),
            'count': len(HEALTHOMICS_SUPPORTED_REGIONS),
            'note': 'Using hardcoded region list due to error: ' + str(e),
        }


async def get_server_manual(
    ctx: Context,
    section: str = 'overview',
) -> Dict[str, Any]:
    """Return built-in server documentation as Markdown.

    Args:
        ctx: MCP context for error reporting
        section: Manual section to return

    Returns:
        Dictionary containing Markdown content and metadata
    """
    try:
        normalized_section = section.strip().lower()
        if normalized_section == 'all':
            content = '\n\n---\n\n'.join(_SERVER_MANUAL_SECTIONS.values())
        else:
            content = _SERVER_MANUAL_SECTIONS.get(normalized_section)

        if content is None:
            available_sections = sorted(list(_SERVER_MANUAL_SECTIONS.keys()) + ['all'])
            return {
                'format': 'markdown',
                'error': f'Unknown section: {section}',
                'available_sections': available_sections,
            }

        return {
            'format': 'markdown',
            'title': 'AWS HealthOmics MCP Server Manual',
            'section': normalized_section,
            'version': __version__,
            'available_sections': sorted(list(_SERVER_MANUAL_SECTIONS.keys()) + ['all']),
            'content': content,
        }
    except Exception as e:
        return await handle_tool_error(ctx, e, 'Error retrieving server manual')
