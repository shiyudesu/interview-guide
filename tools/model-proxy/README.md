# 模型诊断代理

该代理用于排查 OpenAI 兼容 HTTP 接口和实时语音 WebSocket。它原样转发上游流量，将
请求、响应、耗时和消息帧记录为 JSONL。

Authorization、Cookie、API Key 和大块音频会被脱敏或替换为哈希。普通 Prompt 和 JSON
字段会保留，因此只能使用合成测试数据，不能转发真实用户内容。

## 启动

```bash
cd tools/model-proxy
uv sync --frozen
MODEL_PROXY_RECORD_PATH=../../.artifacts/model-proxy.jsonl \
uv run interview-guide-model-proxy
```

默认监听 `127.0.0.1:18090`。默认允许 DashScope、Kimi、DeepSeek、GLM、localhost 和
127.0.0.1，可通过 `MODEL_PROXY_ALLOWED_HOSTS` 覆盖。

HTTP Provider Base URL 示例：

```text
http://127.0.0.1:18090/proxy/https/dashscope.aliyuncs.com/compatible-mode
```

ASR/TTS WebSocket 示例：

```text
ws://127.0.0.1:18090/ws/wss/dashscope.aliyuncs.com/api-ws/v1/realtime
```

## 故障注入

故障注入默认关闭。显式启用后，可以让后续请求返回指定状态码或延迟：

```bash
MODEL_PROXY_ENABLE_FAULTS=true \
MODEL_PROXY_RECORD_PATH=../../.artifacts/model-proxy.jsonl \
uv run interview-guide-model-proxy
```

```bash
curl -X POST http://127.0.0.1:18090/__control/fault \
  -H 'Content-Type: application/json' \
  -d '{"mode":"status","status":429,"count":1}'
```

设置 `MODEL_PROXY_CONTROL_TOKEN` 后，控制请求还必须携带
`X-Model-Proxy-Control-Token`。

## 测试

```bash
uv run python -m unittest discover -s tests -v
```

测试覆盖 HTTP 字节透传、WebSocket 转发、压缩响应记录、脱敏、允许列表和显式故障注入。
