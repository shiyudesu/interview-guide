# Python backend

Production FastAPI backend. Compatibility behavior is enforced by backend tests,
repository manifests, and protected real-model checks.

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
TEST_REDIS_URL=redis://127.0.0.1:6379/0 uv run pytest -m integration
uv run interview-guide-api
```

Runtime entry points:

- `interview-guide-migrate`: Alembic upgrade only.
- `interview-guide-api`: FastAPI/Uvicorn, fixed to one worker.
- `interview-guide-worker`: Redis Stream worker process.
- `interview-guide-scheduler`: single APScheduler process.
