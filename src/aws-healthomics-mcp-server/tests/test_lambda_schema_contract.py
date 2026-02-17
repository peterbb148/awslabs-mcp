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

from typing import List, Optional

from awslabs.mcp_lambda_handler import MCPLambdaHandler


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
