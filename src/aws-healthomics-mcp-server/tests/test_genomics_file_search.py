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

"""Regression tests for genomics file search wrappers."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from awslabs.aws_healthomics_mcp_server.tools.genomics_file_search import search_genomics_files


@pytest.mark.asyncio
async def test_search_genomics_files_normalizes_fieldinfo_defaults(mock_context):
    """Direct calls should not fail when defaults are FieldInfo objects."""
    fake_response = SimpleNamespace(
        results=[],
        total_found=0,
        search_duration_ms=1,
        storage_systems_searched=['s3'],
        enhanced_response=None,
    )
    mock_orchestrator = SimpleNamespace(search=AsyncMock(return_value=fake_response))

    with patch(
        'awslabs.aws_healthomics_mcp_server.tools.genomics_file_search.'
        'GenomicsSearchOrchestrator.from_environment',
        return_value=mock_orchestrator,
    ):
        result = await search_genomics_files(mock_context, file_type='fasta')

    assert result['total_found'] == 0
    request = mock_orchestrator.search.call_args.args[0]
    assert request.search_terms == []
    assert request.adhoc_s3_buckets is None


def test_lambda_wrapper_exposes_and_passes_adhoc_s3_buckets():
    """Lambda SearchGenomicsFiles wrapper should expose and pass adhoc bucket arg."""
    lambda_handler_path = (
        Path(__file__).resolve().parent.parent
        / 'awslabs'
        / 'aws_healthomics_mcp_server'
        / 'lambda_handler.py'
    )
    module = ast.parse(lambda_handler_path.read_text(encoding='utf-8'))

    search_fn = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'SearchGenomicsFiles'
    )
    arg_names = [arg.arg for arg in search_fn.args.args]
    assert 'adhoc_s3_buckets' in arg_names

    call_nodes = [
        node
        for node in ast.walk(search_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'search_genomics_files'
    ]
    assert call_nodes, 'Expected SearchGenomicsFiles wrapper to call search_genomics_files'
    call_keywords = {kw.arg for kw in call_nodes[0].keywords}
    assert 'adhoc_s3_buckets' in call_keywords
