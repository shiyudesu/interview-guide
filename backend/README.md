# Python backend

The Python backend is being built under the compatibility requirements in
`../docs/MIGRATION_PLAN.md`. Java remains the behavior reference until every
comparison stage passes.

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run interview-guide-api
```

Runtime entry points:

- `interview-guide-migrate`: Alembic upgrade only.
- `interview-guide-api`: FastAPI/Uvicorn, fixed to one worker.
- `interview-guide-worker`: Redis Stream worker process.
- `interview-guide-scheduler`: single APScheduler process.
