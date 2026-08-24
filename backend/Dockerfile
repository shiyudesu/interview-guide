ARG INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=docker.io

FROM ${INTERVIEW_GUIDE_DOCKERHUB_REGISTRY}/library/python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f AS builder

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

FROM ${INTERVIEW_GUIDE_DOCKERHUB_REGISTRY}/library/python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
      libmagic1=1:5.44-3 \
      libreoffice-core=4:7.4.7-1+deb12u14 \
      libreoffice-writer=4:7.4.7-1+deb12u14 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 interview-guide \
    && useradd --uid 10001 --gid interview-guide --create-home interview-guide \
    && install -d --owner=interview-guide --group=interview-guide /var/lib/interview-guide

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /workspace/backend/src ./src
COPY --from=builder /workspace/backend/resources ./resources
COPY --from=builder /workspace/backend/alembic ./alembic
COPY --from=builder /workspace/backend/alembic.ini ./alembic.ini

USER interview-guide
EXPOSE 8080

CMD ["uvicorn", "interview_guide.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--ws-max-size", "2097152"]
