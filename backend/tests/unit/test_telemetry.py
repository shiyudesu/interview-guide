from __future__ import annotations

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from interview_guide.common.config.settings import Settings
from interview_guide.common.telemetry import configure_tracing


def test_tracing_is_not_instrumented_without_exporter(
    monkeypatch: object,
) -> None:
    calls: list[FastAPI] = []
    monkeypatch.setattr(
        FastAPIInstrumentor,
        "instrument_app",
        lambda app: calls.append(app),
    )
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-encryption-key",
        APP_INFRASTRUCTURE_STARTUP_ENABLED=False,
        OTEL_ENABLED=True,
        OTEL_EXPORTER_OTLP_ENDPOINT=None,
    )

    configure_tracing(FastAPI(), settings)

    assert calls == []
