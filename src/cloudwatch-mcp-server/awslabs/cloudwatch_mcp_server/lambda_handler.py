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

"""AWS Lambda handler for the CloudWatch MCP Server."""

import json
import os
from typing import Any, Dict, Optional

from awslabs.cloudwatch_mcp_server import MCP_SERVER_VERSION
from awslabs.cloudwatch_mcp_server.cloudwatch_alarms.tools import CloudWatchAlarmsTools
from awslabs.cloudwatch_mcp_server.cloudwatch_logs.tools import CloudWatchLogsTools
from awslabs.cloudwatch_mcp_server.cloudwatch_metrics.tools import CloudWatchMetricsTools
from awslabs.mcp_lambda_handler import MCPLambdaHandler
from loguru import logger


def get_oauth_config() -> Dict[str, str]:
    """Get OAuth configuration from environment variables."""
    return {
        'issuer': os.environ.get(
            'OAUTH_ISSUER',
            'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_FejeFJmNE',
        ),
        'authorization_endpoint': os.environ.get(
            'OAUTH_AUTHORIZATION_ENDPOINT',
            'https://carlsberg-healthomics-auth.auth.eu-west-1.amazoncognito.com/oauth2/authorize',
        ),
        'token_endpoint': os.environ.get(
            'OAUTH_TOKEN_ENDPOINT',
            'https://carlsberg-healthomics-auth.auth.eu-west-1.amazoncognito.com/oauth2/token',
        ),
        'client_id': os.environ.get('OAUTH_CLIENT_ID', '6r52ekr37jn84nlusjgn6j7f8m'),
        'base_url': os.environ.get(
            'MCP_SERVER_BASE_URL',
            'https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com/stable',
        ),
    }


def get_oauth_metadata(base_url: str = '') -> Dict[str, Any]:
    """Get OAuth 2.0 Authorization Server Metadata."""
    config = get_oauth_config()
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

    if effective_base_url:
        metadata['registration_endpoint'] = f'{effective_base_url}/register'

    return metadata


def get_base_url(event: Dict[str, Any]) -> str:
    """Extract base URL from API Gateway event."""
    request_context = event.get('requestContext', {})

    if 'domainName' in request_context:
        domain = request_context['domainName']
        stage = request_context.get('stage', '')
        if stage and stage != '$default':
            return f'https://{domain}/{stage}'
        return f'https://{domain}'

    headers = event.get('headers', {})
    host = headers.get('Host') or headers.get('host', '')
    if host:
        return f'https://{host}'

    return ''


def handle_oauth_discovery(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Serve OAuth/OIDC discovery documents on public endpoints."""
    path = event.get('path', '') or event.get('rawPath', '')
    base_url = get_base_url(event)

    if path.endswith('/.well-known/oauth-authorization-server') or path == (
        '/.well-known/oauth-authorization-server'
    ):
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=3600',
            },
            'body': json.dumps(get_oauth_metadata(base_url)),
        }

    if path.endswith('/.well-known/openid-configuration') or path == (
        '/.well-known/openid-configuration'
    ):
        metadata = get_oauth_metadata(base_url)
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


def handle_dynamic_client_registration(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle RFC 7591 Dynamic Client Registration requests."""
    path = event.get('path', '') or event.get('rawPath', '')
    method = event.get('httpMethod', '') or event.get('requestContext', {}).get('http', {}).get(
        'method', ''
    )

    if (path.endswith('/register') or path == '/register') and method == 'POST':
        body = event.get('body', '{}')
        if event.get('isBase64Encoded'):
            import base64

            body = base64.b64decode(body).decode('utf-8')

        try:
            registration_request = json.loads(body) if body else {}
        except json.JSONDecodeError:
            registration_request = {}

        config = get_oauth_config()
        client_response = {
            'client_id': config['client_id'],
            'client_name': registration_request.get('client_name', 'ChatGPT MCP Client'),
            'redirect_uris': registration_request.get('redirect_uris', []),
            'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'],
            'token_endpoint_auth_method': 'none',
            'client_id_issued_at': 0,
            'client_secret_expires_at': 0,
        }
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


mcp = MCPLambdaHandler(
    name='awslabs.cloudwatch-mcp-server',
    version=MCP_SERVER_VERSION,
)


logs_tools = CloudWatchLogsTools()
metrics_tools = CloudWatchMetricsTools()
alarms_tools = CloudWatchAlarmsTools()


def _register_lambda_tool(tool_name: str, tool_fn: Any) -> None:
    """Register tool function under a stable MCP name."""
    target_fn = tool_fn.__func__ if hasattr(tool_fn, '__func__') else tool_fn
    original_name = target_fn.__name__
    target_fn.__name__ = tool_name
    try:
        mcp.tool()(tool_fn)
    finally:
        target_fn.__name__ = original_name


_register_lambda_tool('describeLogGroups', logs_tools.describe_log_groups)
_register_lambda_tool('analyzeLogGroup', logs_tools.analyze_log_group)
_register_lambda_tool('executeLogInsightsQuery', logs_tools.execute_log_insights_query)
_register_lambda_tool('getLogsInsightQueryResults', logs_tools.get_logs_insight_query_results)
_register_lambda_tool('cancelLogsInsightQuery', logs_tools.cancel_logs_insight_query)

_register_lambda_tool('getMetricData', metrics_tools.get_metric_data)
_register_lambda_tool('getMetricMetadata', metrics_tools.get_metric_metadata)
_register_lambda_tool('getRecommendedMetricAlarms', metrics_tools.get_recommended_metric_alarms)

_register_lambda_tool('getActiveAlarms', alarms_tools.get_active_alarms)
_register_lambda_tool('getAlarmHistory', alarms_tools.get_alarm_history)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entrypoint for CloudWatch MCP Server."""
    logger.info('CloudWatch MCP Lambda handler invoked')

    oauth_response = handle_oauth_discovery(event)
    if oauth_response:
        return oauth_response

    dcr_response = handle_dynamic_client_registration(event)
    if dcr_response:
        return dcr_response

    return mcp.handle_request(event, context)
