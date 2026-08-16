# AI Interview Platform Agent Guide

## Project State

This repository is migrating its backend from Java/Spring to Python/FastAPI. The
complete migration contract and phase gates are defined in
`docs/MIGRATION_PLAN.md`; treat that document as the source of truth.

- `app/` is the current Java implementation and the behavior reference during
  migration.
- `backend/` is the target Python backend. Create and migrate code there.
- `frontend/` remains the React application and should not require business
  changes for the backend migration.
- Do not remove Java, Gradle, Flyway, or JVM-related files until every final
  gate in `docs/MIGRATION_PLAN.md` passes.
- Migration tasks replace implementation only. Record existing defects
  separately instead of fixing or redesigning behavior while porting it.

## Compatibility Is the Primary Requirement

The Python implementation must preserve all externally observable behavior:

- REST paths, methods, request parameters, response fields, defaults, error
  codes, error messages, null handling, ordering, and date-time formats.
- HTTP 200 responses for ordinary business errors, except for existing file,
  SSE, and WebSocket behavior.
- PostgreSQL tables, column types, constraints, indexes, state machines, and
  transaction boundaries.
- Redis keys, TTLs, Streams, message fields, retry counts, reclaim/ACK order,
  idempotency, and rate-limit semantics.
- Prompt text, Skill resources, provider selection, model parameters,
  structured output, retries, and fallback order.
- SSE framing and WebSocket message types, ordering, timeouts, pause/resume,
  ASR, and TTS behavior.
- File validation, parsing output, hashes, object keys, download headers, and
  visible PDF content.

Use contract tests and golden-master fixtures to prove equivalence. Do not rely
on a new implementation merely appearing reasonable.

## Target Stack

- Python 3.13, uv, FastAPI, Uvicorn, Pydantic v2.
- SQLAlchemy 2.0, psycopg 3, Alembic, PostgreSQL, pgvector.
- LangGraph, langchain-openai, and a project-owned LLM adapter.
- redis-py asyncio with direct Redis Stream consumer-group operations.
- APScheduler in a separate single-instance scheduler process.
- boto3 for RustFS/S3-compatible storage.
- python-magic, pdfminer.six/pypdf, python-docx, and antiword or LibreOffice for
  document parsing; no JVM-based parser.
- ReportLab for PDF generation.
- pytest, pytest-asyncio, pytest-mock, Ruff, and mypy.
- React 18, TypeScript, Vite, Tailwind CSS 4, and pnpm in `frontend/`.

PostgreSQL/pgvector, Redis, Redis Stream, RustFS/S3, API port `8080`, and the
React frontend remain part of the architecture.

## Repository Layout

```text
app/                    Current Java behavior reference
backend/                Target Python API, worker, scheduler, and tests
frontend/               Existing React frontend
docs/MIGRATION_PLAN.md  Migration phases, invariants, and completion gates
docker-compose.dev.yml  Local PostgreSQL, Redis, and RustFS dependencies
.github/workflows/      Repository CI
.githooks/              Optional local Git hooks
```

The target Python package is `backend/src/interview_guide/`:

- `common/`: API response, errors, config, database, Redis, AI, and evaluation.
- `infrastructure/`: document parsing, export, storage, and mapping.
- `modules/`: business modules, each owning its API/service/repository layers.
- `main.py`: FastAPI application.
- `worker.py`: Redis Stream consumers.
- `scheduler.py`: scheduled recovery and expiration jobs.
- `backend/resources/`: prompts, Skills, scripts, fonts, and static resources.

## Development Commands

Start local dependencies:

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
```

Current Java baseline:

```bash
./gradlew :app:compileJava
./gradlew :app:test --no-daemon
./gradlew :app:bootRun
```

Python backend, after `backend/pyproject.toml` is introduced:

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run uvicorn interview_guide.main:app --host 0.0.0.0 --port 8080
```

Frontend:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
pnpm run build
```

Stop local dependencies with
`docker compose -f docker-compose.dev.yml down`. Use `down -v` only when
intentionally discarding local development data.

## Migration Workflow

1. Freeze the current Java behavior with contract fixtures before porting a
   module.
2. Implement the equivalent Python module under `backend/`.
3. Add unit, integration, and Java/Python comparison tests.
4. Verify the existing frontend flow without changing its business behavior.
5. Keep the Java reference until the relevant module and final migration gates
   pass.

Migrate modules in the risk order defined in `docs/MIGRATION_PLAN.md`. Preserve
the `app` Compose service name even after its implementation becomes Python.

## Python Architecture and Style

- Keep FastAPI routes thin: parse/validate, delegate, and translate the result.
- Put business orchestration in services and persistence in repositories.
- Use Pydantic models for API boundaries and SQLAlchemy models for persistence;
  never return ORM entities directly.
- Emit camelCase API fields and preserve the current null and time behavior.
- Raise project `BusinessException` values backed by `ErrorCode`; translate
  validation and business failures through the global exception layer.
- Keep transactions short. Never perform LLM, S3, document parsing, or external
  HTTP calls inside a database transaction.
- Use explicit type annotations. Pass Ruff formatting/linting and mypy without
  broad ignores or unsafe casts.
- Do not use bare `except`, silently swallow failures, or return success-shaped
  fallbacks for unexpected errors.
- Avoid per-row database calls; use batch queries and writes.
- Use dependency injection through FastAPI dependencies or explicit
  constructors; do not create infrastructure clients inside business methods.

## AI, LangGraph, and Async Rules

- Obtain all model and embedding clients through the Python
  `LlmProviderRegistry`.
- Route every single model call through the shared LLM adapter.
- Use LangGraph only for multi-step, branching, parallel, or fallback workflows
  listed in the migration plan; do not wrap simple calls in one-node graphs.
- Disable hidden SDK, LangChain, and LangGraph retries. Implement only the
  existing retry and fallback behavior.
- Keep prompts and Skill/reference files byte-for-byte compatible and cover the
  renderer with snapshots.
- Do not place WebSocket lifecycle, ASR, TTS, or audio chunk transport inside
  LangGraph.
- Implement Redis Streams directly with consumer groups, reclaim, retry,
  republish, and ACK order matching the Java baseline. Do not replace them with
  Celery, RQ, pub/sub, or an in-memory queue.
- Before async work, verify the referenced entity still exists. ACK and discard
  messages for entities that were intentionally deleted.

## Data, Files, and Configuration

- Treat the current PostgreSQL catalog as authoritative; do not modernize enum,
  JSON, timezone, cascade, constraint, or index choices during migration.
- Keep pgvector dimension `1024` and cosine distance semantics.
- Manage schema changes with Alembic in Python. Compare actual PostgreSQL
  catalogs, not only ORM declarations.
- Preserve current file size limits, MIME allowlists, text cleaning, SHA-256
  deduplication, object key generation, and response headers.
- Configuration belongs in typed settings loaded from environment variables and
  supported config files. Do not scatter environment reads through services.
- Store API keys, database passwords, and other secrets only in local `.env` or
  secret stores. Never commit credentials or log unmasked secrets.

## Frontend Rules

- Keep API clients in `frontend/src/api/` and reuse its shared Axios instance.
- Keep shared interfaces in `frontend/src/types/`, pages in
  `frontend/src/pages/`, reusable UI in `frontend/src/components/`, and route
  constants in `frontend/src/constants/routes.ts`.
- Reuse the existing design language and `lucide-react` icons.
- Backend migration must not trigger unrelated UI redesign or API reshaping.

## Testing and Completion

- Add or update tests for every migrated behavior, including failure,
  retry/reclaim, idempotency, timeout, and interrupted-stream cases.
- Run the smallest relevant checks while iterating, then the full checks for the
  touched backend or frontend before completion.
- Changes to shared backend infrastructure require the complete backend test
  suite for the implementation being changed.
- Frontend changes require `pnpm run build` and the relevant package scripts.
- Java removal is allowed only after REST, schema, Redis, prompt/model, SSE,
  WebSocket, frontend, and performance compatibility gates all pass.

## Git and CI

- The default branch is `main`.
- Commit subjects follow Conventional Commits:
  `type(optional-scope): summary`. The summary language is unrestricted.
- Enable local hooks with `git config core.hooksPath .githooks`.
- `.github/workflows/ci.yml` runs the Java baseline while `app/` exists, runs
  Python checks once `backend/pyproject.toml` exists, and always validates the
  frontend and repository hooks.
- Update CI, Compose, README, and this file when migration commands become
  executable or Java is finally removed.
