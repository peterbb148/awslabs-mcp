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

"""Tests for OAuth discovery path handling in the HealthOmics Lambda handler."""

import json

from awslabs.aws_healthomics_mcp_server.lambda_handler import (
    _extract_mount_prefix,
    get_base_url,
    handle_oauth_discovery,
)


def test_extract_mount_prefix_strips_mcp_subpath() -> None:
    """Discovery under /mcp should still resolve to the stage root."""
    path = '/stable/mcp/.well-known/openid-configuration'

    assert _extract_mount_prefix(path) == '/stable'


def test_get_base_url_prefers_explicit_env(monkeypatch) -> None:
    """Explicit MCP server base URL should override request reconstruction."""
    monkeypatch.setenv(
        'MCP_SERVER_BASE_URL',
        'https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com/stable',
    )
    event = {
        'requestContext': {'domainName': 'example.execute-api.eu-west-1.amazonaws.com', 'stage': 'stable'},
        'headers': {'host': 'example.execute-api.eu-west-1.amazonaws.com'},
    }

    base_url = get_base_url(event, '/stable/mcp/.well-known/openid-configuration')

    assert base_url == 'https://osgs2j07zf.execute-api.eu-west-1.amazonaws.com/stable'


def test_get_base_url_does_not_duplicate_stage_for_mcp_discovery(monkeypatch) -> None:
    """Base URL reconstruction should not append the API stage twice."""
    monkeypatch.delenv('MCP_SERVER_BASE_URL', raising=False)
    event = {
        'requestContext': {'domainName': 'example.execute-api.eu-west-1.amazonaws.com', 'stage': 'stable'},
        'headers': {
            'host': 'example.execute-api.eu-west-1.amazonaws.com',
            'x-forwarded-proto': 'https',
        },
    }

    base_url = get_base_url(event, '/stable/mcp/.well-known/openid-configuration')

    assert base_url == 'https://example.execute-api.eu-west-1.amazonaws.com/stable'


def test_handle_oauth_discovery_emits_stage_root_registration_endpoint(monkeypatch) -> None:
    """OpenID metadata should advertise the stage-root register endpoint."""
    monkeypatch.delenv('MCP_SERVER_BASE_URL', raising=False)
    event = {
        'rawPath': '/stable/mcp/.well-known/openid-configuration',
        'requestContext': {'domainName': 'example.execute-api.eu-west-1.amazonaws.com', 'stage': 'stable'},
        'headers': {
            'host': 'example.execute-api.eu-west-1.amazonaws.com',
            'x-forwarded-proto': 'https',
        },
    }

    response = handle_oauth_discovery(event)
    assert response is not None

    payload = json.loads(response['body'])

    assert payload['registration_endpoint'] == (
        'https://example.execute-api.eu-west-1.amazonaws.com/stable/register'
    )


def test_handle_oauth_discovery_supports_mcp_relative_path(monkeypatch) -> None:
    """Requests whose raw path omits the stage should still emit the stage-root register endpoint."""
    monkeypatch.delenv('MCP_SERVER_BASE_URL', raising=False)
    event = {
        'rawPath': '/mcp/.well-known/openid-configuration',
        'requestContext': {'domainName': 'example.execute-api.eu-west-1.amazonaws.com', 'stage': 'stable'},
        'headers': {
            'host': 'example.execute-api.eu-west-1.amazonaws.com',
            'x-forwarded-proto': 'https',
        },
    }

    response = handle_oauth_discovery(event)
    assert response is not None

    payload = json.loads(response['body'])

    assert payload['registration_endpoint'] == (
        'https://example.execute-api.eu-west-1.amazonaws.com/stable/register'
    )
