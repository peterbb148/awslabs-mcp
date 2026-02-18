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

"""Schema contract tests for vendored MCP Lambda handler."""

import json
from typing import List, Optional

from awslabs.mcp_lambda_handler import MCPLambdaHandler
from pydantic import Field


def test_optional_list_is_exposed_as_array_and_not_required():
    """Optional list params should be represented as arrays in tool schema."""
    handler = MCPLambdaHandler('test-server')

    @handler.tool()
    def search_genomics_files(search_terms: Optional[List[str]] = None) -> dict:
        return {}

    schema = handler.tools['searchGenomicsFiles']['inputSchema']
    prop = schema['properties']['search_terms']

    assert prop['type'] == 'array'
    assert prop['items']['type'] == 'string'
    assert 'search_terms' not in schema['required']


def test_ctx_is_hidden_from_schema_and_async_tool_is_awaited():
    """FastMCP ctx should not be in schema and async tools should execute fully."""
    handler = MCPLambdaHandler('test-server')

    class Context:
        pass

    @handler.tool()
    async def list_aho_references(
        ctx: Context,
        reference_store_id: str = Field(..., description='Reference store ID'),
        next_token: Optional[str] = Field(None, description='Pagination token'),
    ) -> dict:
        return {'referenceStoreId': reference_store_id, 'nextToken': next_token, 'ok': True}

    schema = handler.tools['listAhoReferences']['inputSchema']
    assert 'ctx' not in schema['properties']
    assert 'ctx' not in schema['required']
    assert 'reference_store_id' in schema['required']
    assert 'next_token' not in schema['required']

    event = {
        'httpMethod': 'POST',
        'headers': {'content-type': 'application/json'},
        'body': json.dumps(
            {
                'jsonrpc': '2.0',
                'id': 'call-1',
                'method': 'tools/call',
                'params': {
                    'name': 'listAhoReferences',
                    'arguments': {'reference_store_id': '7661842487'},
                },
            }
        ),
    }

    response = handler.handle_request(event, context=None)
    payload = json.loads(response['body'])
    result_text = payload['result']['content'][0]['text']

    assert 'coroutine object' not in result_text
    assert "'referenceStoreId': '7661842487'" in result_text
    assert "'nextToken': None" in result_text


def test_readonly_hint_annotations_for_read_and_write_tools():
    """Tool schemas should expose readOnlyHint for MCP client action gating."""
    handler = MCPLambdaHandler('test-server')

    @handler.tool()
    def list_aho_workflows(max_results: int = 10) -> dict:
        return {'max_results': max_results}

    @handler.tool()
    def start_aho_run(workflow_id: str) -> dict:
        return {'workflow_id': workflow_id}

    @handler.tool()
    def cancel_aho_run(run_id: str) -> dict:
        return {'run_id': run_id}

    @handler.tool()
    def tail_aho_run_task_logs(run_id: str) -> dict:
        return {'run_id': run_id}

    list_schema = handler.tools['listAhoWorkflows']
    start_schema = handler.tools['startAhoRun']
    cancel_schema = handler.tools['cancelAhoRun']
    tail_schema = handler.tools['tailAhoRunTaskLogs']

    assert list_schema['annotations']['readOnlyHint'] is True
    assert start_schema['annotations']['readOnlyHint'] is False
    assert cancel_schema['annotations']['readOnlyHint'] is False
    assert tail_schema['annotations']['readOnlyHint'] is True
