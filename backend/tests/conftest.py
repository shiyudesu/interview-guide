from __future__ import annotations

import os

os.environ.setdefault(
    "APP_AI_CONFIG_ENCRYPTION_KEY",
    "backend-test-encryption-key",
)
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("APP_INFRASTRUCTURE_STARTUP_ENABLED", "false")
