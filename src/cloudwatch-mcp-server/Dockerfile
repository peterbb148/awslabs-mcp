# Lambda container image for the CloudWatch MCP server.
FROM public.ecr.aws/lambda/python:3.13

WORKDIR ${LAMBDA_TASK_ROOT}

# Install the package and runtime dependencies.
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY awslabs ./awslabs

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Lambda runtime handler entrypoint.
CMD ["awslabs.cloudwatch_mcp_server.lambda_handler.lambda_handler"]
