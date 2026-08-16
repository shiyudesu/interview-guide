from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


class ApplicationMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.http_requests = Counter(
            "app_http_requests_total",
            "HTTP requests handled by the API",
            ("method", "pathTemplate", "status"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "app_http_request_duration_seconds",
            "HTTP request duration",
            ("method", "pathTemplate"),
            registry=self.registry,
        )

    @property
    def metric_names(self) -> list[str]:
        return [
            "app.http.request.duration",
            "app.http.requests",
        ]

    def render_prometheus(self) -> bytes:
        return generate_latest(self.registry)
