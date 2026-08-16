# syntax=docker/dockerfile:1.7

FROM --platform=linux/amd64 python:3.13.13-slim-bookworm@sha256:f576b530293e74140ea91d262232648d5c4f45640a95ec447757701bfcacf034 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_VERSION=0.11.14

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /workspace/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
RUN uv sync --frozen --no-dev

FROM --platform=linux/amd64 python:3.13.13-slim-bookworm@sha256:f576b530293e74140ea91d262232648d5c4f45640a95ec447757701bfcacf034 AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --gid 10001 interview-guide \
    && useradd --uid 10001 --gid interview-guide --create-home interview-guide

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /workspace/backend/src ./src
COPY --from=builder /workspace/backend/resources ./resources
COPY --from=builder /workspace/backend/alembic ./alembic
COPY --from=builder /workspace/backend/alembic.ini ./alembic.ini

USER interview-guide
EXPOSE 8080

CMD ["uvicorn", "interview_guide.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
