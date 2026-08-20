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
        self.interview_turn_duration = Histogram(
            "interview_turn_decision_duration_seconds",
            "Adaptive interview turn decision duration",
            ("channel",),
            registry=self.registry,
        )
        self.interview_turn_decisions = Counter(
            "interview_turn_decisions_total",
            "Adaptive interview turn decisions",
            ("channel", "action"),
            registry=self.registry,
        )
        self.interview_turn_fallbacks = Counter(
            "interview_turn_fallback_total",
            "Adaptive interview deterministic fallbacks",
            ("channel", "reason"),
            registry=self.registry,
        )
        self.interview_follow_ups = Counter(
            "interview_follow_ups_total",
            "Dynamic interview follow-up questions",
            ("channel",),
            registry=self.registry,
        )
        self.interview_duplicate_requests = Counter(
            "interview_turn_duplicate_requests_total",
            "Duplicate adaptive interview requests",
            ("channel",),
            registry=self.registry,
        )
        self.interview_turn_tokens = Counter(
            "interview_turn_tokens_total",
            "Adaptive interview decision model tokens",
            ("channel", "type"),
            registry=self.registry,
        )

    @property
    def metric_names(self) -> list[str]:
        return [
            "app.http.request.duration",
            "app.http.requests",
            "interview.turn.decision.duration",
            "interview.turn.decisions",
            "interview.turn.duplicate.requests",
            "interview.turn.fallback",
            "interview.turn.tokens",
            "interview.follow.ups",
        ]

    def render_prometheus(self) -> bytes:
        return generate_latest(self.registry)
