ARG INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=docker.io

FROM ${INTERVIEW_GUIDE_DOCKERHUB_REGISTRY}/library/python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_VERSION=0.11.14

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

ENV UV_HTTP_TIMEOUT=600

WORKDIR /workspace/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,id=interview-guide-uv,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
RUN --mount=type=cache,id=interview-guide-uv,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
    && site_packages=/opt/venv/lib/python3.13/site-packages \
    && mkdir -p \
      /opt/venv-layers/a-f \
      /opt/venv-layers/g-l \
      /opt/venv-layers/m-r \
      /opt/venv-layers/s-z \
      /opt/venv-layers/other \
    && for entry in "$site_packages"/* "$site_packages"/.[!.]* "$site_packages"/..?*; do \
      [ -e "$entry" ] || continue; \
      name="${entry##*/}"; \
      case "$name" in \
        [a-fA-F]*) chunk=a-f ;; \
        [g-lG-L]*) chunk=g-l ;; \
        [m-rM-R]*) chunk=m-r ;; \
        [s-zS-Z]*) chunk=s-z ;; \
        *) chunk=other ;; \
      esac; \
      mv "$entry" "/opt/venv-layers/$chunk/"; \
    done

FROM ${INTERVIEW_GUIDE_DOCKERHUB_REGISTRY}/library/python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Keep the headless office runtime in several bounded layers. Besides avoiding
# GUI dependencies, this prevents one very large blob from making constrained
# registry connections restart the whole system-package download.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      libmagic1=1:5.44-3 \
      libreoffice-common=4:7.4.7-1+deb12u14 \
    && rm -rf \
      /usr/lib/libreoffice/share/autocorr \
      /usr/lib/libreoffice/share/basic \
      /usr/lib/libreoffice/share/emojiconfig \
      /usr/lib/libreoffice/share/gallery \
      /usr/lib/libreoffice/share/template \
      /usr/lib/libreoffice/share/tipoftheday \
      /usr/lib/libreoffice/share/wizards \
      /usr/share/libreoffice/share/config \
      /var/lib/apt/lists/* \
    && find /usr/share/doc -type f ! -name copyright -delete \
    && find /usr/share/doc -type l ! -name copyright -delete \
    && find /usr/share/doc -depth -type d -empty -delete
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      libreoffice-core-nogui=4:7.4.7-1+deb12u14 \
    && rm -rf /var/lib/apt/lists/* \
    && find /usr/share/doc -type f ! -name copyright -delete \
    && find /usr/share/doc -type l ! -name copyright -delete \
    && find /usr/share/doc -depth -type d -empty -delete
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      libreoffice-writer-nogui=4:7.4.7-1+deb12u14 \
    && rm -rf /var/lib/apt/lists/* \
    && find /usr/share/doc -type f ! -name copyright -delete \
    && find /usr/share/doc -type l ! -name copyright -delete \
    && find /usr/share/doc -depth -type d -empty -delete

RUN groupadd --gid 10001 interview-guide \
    && useradd --uid 10001 --gid interview-guide --create-home interview-guide \
    && install -d --owner=interview-guide --group=interview-guide /var/lib/interview-guide

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/venv-layers/a-f/ /opt/venv/lib/python3.13/site-packages/
COPY --from=builder /opt/venv-layers/g-l/ /opt/venv/lib/python3.13/site-packages/
COPY --from=builder /opt/venv-layers/m-r/ /opt/venv/lib/python3.13/site-packages/
COPY --from=builder /opt/venv-layers/s-z/ /opt/venv/lib/python3.13/site-packages/
COPY --from=builder /opt/venv-layers/other/ /opt/venv/lib/python3.13/site-packages/
COPY --from=builder /workspace/backend/src ./src
COPY --from=builder /workspace/backend/resources ./resources
COPY --from=builder /workspace/backend/alembic ./alembic
COPY --from=builder /workspace/backend/alembic.ini ./alembic.ini

USER interview-guide
EXPOSE 8080

CMD ["uvicorn", "interview_guide.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--ws-max-size", "2097152"]
