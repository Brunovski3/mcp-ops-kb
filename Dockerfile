FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPS_KB_RUNBOOKS_DIR=/app/runbooks

COPY pyproject.toml README.md ./
COPY src ./src
COPY runbooks ./runbooks

RUN pip install --no-cache-dir .

ENTRYPOINT ["mcp-ops-kb"]
