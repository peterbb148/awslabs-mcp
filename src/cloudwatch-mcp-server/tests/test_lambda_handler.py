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

"""Tests for CloudWatch Lambda handler endpoints and MCP surface."""

import json

from awslabs.cloudwatch_mcp_server.lambda_handler import lambda_handler


def test_oauth_well_known_endpoint_returns_metadata(monkeypatch):
    """The OAuth well-known endpoint should return authorization server metadata."""
    monkeypatch.setenv('OAUTH_CLIENT_ID', 'test-client-id')

    event = {
        'rawPath': '/.well-known/oauth-authorization-server',
        'requestContext': {
            'domainName': 'abc123.execute-api.eu-west-1.amazonaws.com',
            'stage': 'stable',
        },
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['issuer'].startswith('https://')
    assert body['registration_endpoint'] == (
        'https://abc123.execute-api.eu-west-1.amazonaws.com/stable/register'
    )


def test_dynamic_client_registration_returns_preregistered_client(monkeypatch):
    """The /register endpoint should return pre-registered client metadata."""
    monkeypatch.setenv('OAUTH_CLIENT_ID', 'client-123')

    event = {
        'rawPath': '/register',
        'requestContext': {'http': {'method': 'POST'}},
        'body': json.dumps({'client_name': 'ChatGPT CloudWatch', 'redirect_uris': ['https://a.b/c']}),
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['client_id'] == 'client-123'
    assert body['client_name'] == 'ChatGPT CloudWatch'
    assert body['redirect_uris'] == ['https://a.b/c']


def test_tools_list_includes_cloudwatch_tools():
    """tools/list should expose registered CloudWatch tools through JSON-RPC."""
    event = {
        'httpMethod': 'POST',
        'headers': {'content-type': 'application/json'},
        'body': json.dumps(
            {
                'jsonrpc': '2.0',
                'id': 'req-1',
                'method': 'tools/list',
                'params': {},
            }
        ),
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    tool_names = {tool['name'] for tool in payload['result']['tools']}

    assert 'describeLogGroups' in tool_names
    assert 'getMetricData' in tool_names
    assert 'getActiveAlarms' in tool_names
