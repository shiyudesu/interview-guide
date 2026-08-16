from __future__ import annotations

import os
from pathlib import Path

from aiohttp import web

from model_proxy.app import ProxyConfig, create_app


def main() -> None:
    config = ProxyConfig(
        allowed_hosts=frozenset(
            host.strip().lower()
            for host in os.getenv(
                "MODEL_PROXY_ALLOWED_HOSTS",
                (
                    "dashscope.aliyuncs.com,api.moonshot.cn,"
                    "api.deepseek.com,open.bigmodel.cn,"
                    "localhost,127.0.0.1"
                ),
            ).split(",")
            if host.strip()
        ),
        control_token=os.getenv("MODEL_PROXY_CONTROL_TOKEN"),
        enable_faults=os.getenv("MODEL_PROXY_ENABLE_FAULTS", "false").lower()
        == "true",
        max_record_bytes=int(os.getenv("MODEL_PROXY_MAX_RECORD_BYTES", "1048576")),
        record_path=Path(
            os.getenv("MODEL_PROXY_RECORD_PATH", "migration/reports/model-proxy.jsonl")
        ),
        upstream_connect_timeout=float(
            os.getenv("MODEL_PROXY_CONNECT_TIMEOUT_SECONDS", "10")
        ),
    )
    web.run_app(
        create_app(config),
        host=os.getenv("MODEL_PROXY_HOST", "127.0.0.1"),
        port=int(os.getenv("MODEL_PROXY_PORT", "18090")),
        access_log=None,
    )


if __name__ == "__main__":
    main()
