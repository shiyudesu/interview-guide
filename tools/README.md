# 仓库工具

`tools/` 保存仍在 CI 和生产验收中使用的工具，不包含迁移历史产物。

```text
manifests/      API、配置、数据库、Redis、资源和测试清单
model-proxy/    Provider HTTP/WebSocket 诊断代理
scripts/        清单生成与真实模型验收脚本
tests/          工具测试
```

## 仓库清单

重新生成：

```bash
./tools/scripts/generate-manifests.sh
```

验证提交内容与当前源码一致：

```bash
./tools/scripts/check-manifests.sh
```

检查脚本会运行工具单元测试、在临时目录重新生成清单，并逐文件比较。修改路由、配置、
Alembic、Redis 常量、资源或测试后需要更新清单。

## 模型诊断代理

代理会转发 HTTP 和 WebSocket 请求，并把脱敏后的请求、响应、计时和流式消息写为 JSONL。
它不会修改成功响应，也不会自动重试。

```bash
cd tools/model-proxy
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run interview-guide-model-proxy
```

详细用法见 [model-proxy/README.md](model-proxy/README.md)。

## 真实模型验收

`scripts/production_model_acceptance.py` 由受保护的 GitHub Actions 环境调用，检查：

- 连续 5 次真实聊天请求
- 1024 维 Embedding
- ASR WebSocket ready
- TTS 返回 PCM

结果写入被忽略的 `.artifacts/real-model-production.json`，不会记录 API Key。
