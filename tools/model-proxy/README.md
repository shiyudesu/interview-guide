# Model recording proxy

This proxy forwards HTTP and WebSocket traffic without retrying or changing
successful upstream responses. It records request/response timing, headers, JSON,
stream bytes, and WebSocket messages as JSON Lines. API keys, authorization headers,
cookies, and large audio fields are replaced with hashes.

Use only synthetic diagnostic samples; recorded prompts and ordinary JSON fields are
intentionally preserved for exact provider request inspection.

```bash
cd tools/model-proxy
uv sync --frozen
MODEL_PROXY_ENABLE_FAULTS=true \
MODEL_PROXY_RECORD_PATH=../../.artifacts/model-proxy.jsonl \
uv run interview-guide-model-proxy
```

HTTP provider base URL example:

```text
http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode
```

ASR/TTS WebSocket URL example:

```text
ws://127.0.0.1:18090/ws/wss/dashscope.aliyuncs.com/api-ws/v1/realtime
```

Faults are disabled by default. When explicitly enabled, configure the next request:

```bash
curl -X POST http://127.0.0.1:18090/__control/fault \
  -H 'Content-Type: application/json' \
  -d '{"mode":"status","status":429,"count":1}'
```
