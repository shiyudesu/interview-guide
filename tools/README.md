# 仓库工具

`tools/` 保存仍在 CI 和生产验收中使用的工具，不包含迁移历史产物。

```text
manifests/      API、配置、数据库、Redis、资源和测试清单
model-proxy/    Provider HTTP/WebSocket 诊断代理
reference_sources/ 普通面试参考资料来源、分类词表和来源追踪
scripts/        清单生成与真实模型验收脚本
tests/          工具测试
```

CI 辅助脚本：

- `scripts/detect_ci_changes.py`：按改动路径选择后端、前端、模型代理和生产集成 Job。
- `scripts/check_docs.py`：检查 Markdown 链接、行尾空格和文档环境变量。

## 仓库清单

重新生成：

```bash
./tools/scripts/generate-manifests.sh
```

验证提交内容与当前源码一致：

```bash
./tools/scripts/check-manifests.sh
python3 tools/scripts/check-docs.py --root .
python3 -m unittest discover -s tools/tests -p 'test_*.py' -v
```

检查脚本会在临时目录重新生成清单并逐文件比较。工具单元测试通过
`python3 -m unittest discover -s tools/tests -p 'test_*.py' -v` 单独运行。修改路由、配置、
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

## 普通面试参考资料

外部题库只通过离线工具用于发现问题方向，不进入生产请求链路。工具支持面试鸭搜索、
GitHub Markdown 和结构化 JSON 题库。校验来源目录：

```bash
python3 tools/scripts/reference_sources.py --root . validate
```

采集少量面试鸭候选题进行检查：

```bash
python3 tools/scripts/reference_sources.py --root . collect \
  --source mianshiya \
  --skill java-backend \
  --query-limit 2 \
  --output .artifacts/reference-sample.jsonl
```

完整的来源许可、采集和整理规则见
[普通面试参考资料来源](../docs/REFERENCE_SOURCES.md)。
