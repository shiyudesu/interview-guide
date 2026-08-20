# AI 面试平台 Agent 工作规则

## 项目状态

生产后端为 Python/FastAPI。当前行为由后端测试、仓库清单、生产 Compose 集成和受保护
真实模型工作流验证。

目录：

```text
backend/                Python 后端
frontend/               React 前端
tools/                  仓库清单、模型诊断和生产验收工具
scripts/                跨平台一键启动和仓库辅助脚本
docs/                   配置、运维和架构说明
docker-compose.yml      生产 Compose
docker-compose.dev.yml  本地基础设施
```

## 不能改变的行为

面试提交协议为 `POST /api/interview/sessions/{sessionId}/turns`，使用
`requestId + questionId + answer`。以下行为不可改变：

- 保持当前 REST 路径、HTTP 方法、参数、请求体、multipart 字段和响应头。
- 成功响应直接返回业务 JSON，无响应体操作使用 HTTP 204。
- 错误使用标准 4xx/5xx，响应体固定为 `code + detail`；SSE 和 WebSocket 保持各自协议。
- 保持当前 PostgreSQL 表、字段、约束、索引、事务结果和 `vector(1024)`。
- 保持当前 Redis key、TTL、Stream 字段、Pending、reclaim、重试和 ACK 顺序。
- 保持 requestId 幂等锁、结果缓存和数据库唯一索引。
- 保持 Prompt、Skill、Provider、Tool、JSON Schema、重试和回退顺序。
- 保持 SSE 分帧、WebSocket JSON/Base64 音频和语音生命周期。
- 保持文件识别、清洗、hash、对象 key、下载头和 PDF 可见内容。

## Python 规则

- Python 3.13.13，uv 0.11.14，提交 `uv.lock`。
- FastAPI 路由只负责参数、校验、Service 调用和返回。
- Service 负责编排；Repository 负责数据库读写。
- API 使用 Pydantic Model，数据库使用 SQLAlchemy Model，不直接返回 ORM。
- 输出 camelCase，明确控制 null、字段顺序、Unicode、时间和数字。
- 字符长度、截断和文本切片使用 Python Unicode 字符语义，不模拟 UTF-16 或 Java hash。
- 使用 `BusinessException` 和 `ErrorCode`。
- 不使用 bare `except`，不静默吞异常，不伪装成功。
- 基础设施客户端通过依赖注入提供。
- 阻塞操作必须进入受限线程池或受控子进程。
- Ruff、mypy 和 pytest 必须通过。

## 数据库、Redis 和 AI

- Alembic 是唯一数据库升级入口。
- SQLAlchemy 连接池默认 10 个常驻连接、0 overflow。
- Redis Stream 使用 XGROUP、XREADGROUP、XAUTOCLAIM、XADD 和 XACK。
- 四组 Stream 每组内部顺序消费，失败时先重投或写失败状态，再 ACK。
- 文字和语音面试统一写入 `interview:evaluate:stream`。
- 限流 key 使用业务 scope，不使用 Controller 或方法类名。
- 所有模型客户端由 `LlmProviderRegistry` 和统一 LLM Adapter 提供。
- 关闭 SDK、LangChain 和 LangGraph 隐式重试。
- Provider 配置以数据库为准，修改后通过 Redis 版本通知清理进程缓存。
- 内置 Provider 只有百炼，初始不带 API Key；其他 Provider 必须从设置页添加。
- Compose 的 Provider 加密主密钥自动生成到共享 `provider_key` 卷，不读取 `.env` 主密钥；
  直接运行 Python 后端时才允许环境变量作为可选外部覆盖。
- Provider 模型列表通过 OpenAI 兼容 `/models` 自动发现，缓存 5 分钟；远端失败时必须明确
  标记为当前配置兜底，不能伪装成远端发现成功。
- 当前模型默认值：
  - `qwen3.7-max`
  - `qwen3.7-text-embedding`，1024 维
  - `qwen3-asr-flash-realtime`
  - `qwen3-tts-flash-realtime`

## 运行方式

合作开发者优先使用 `scripts/start.sh` 或 Windows 根目录 `start.cmd`。启动脚本必须保持非破坏性，
不得覆盖已有 `.env` 或删除数据卷；只允许在用户确认或显式 `--yes`/`-Yes` 后安装 Docker 官方
组件，不得绕过 UAC、sudo 或 Docker Desktop 的许可提示。
启动脚本必须在构建前检查常用宿主机端口，并在 Compose 绑定失败时给出对应 `.env` 变量、建议
端口和占用进程；不得要求用户修改容器内部端口。
关闭服务优先使用 `scripts/stop.sh` 或 `stop.cmd`，只能执行非破坏性的 Compose down 并保留
数据卷；不得在一键关闭入口中提供或隐式调用 `down -v`。

同一镜像启动：

1. Migrate：Alembic，成功后其他服务才能启动。
2. API：单 Uvicorn worker。
3. Worker：处理四组 Redis Stream。
4. Scheduler：单实例恢复和过期任务。

生产前端 Nginx 必须通过 Docker DNS 动态解析 `app`，健康检查经由反向代理访问 `/health`，
后端容器重建不能要求同时重启前端。

```bash
docker compose up -d --build --wait
docker compose ps
docker compose logs migrate app worker scheduler
```

## 测试

- 单元测试可以使用明确命名的 fake/stub。
- 真实模型验收必须使用受保护 Key，不能用 fake 冒充。
- 集成测试使用真实 PostgreSQL/pgvector、Redis 和 S3 兼容存储。
- 集成测试不能指向保存业务数据的数据库或 bucket。
- 前端改动运行相关测试、Playwright 和 `pnpm run build`。
- 浏览器验证使用 Windows Chrome：
  `/mnt/c/Program Files/Google/Chrome/Application/chrome.exe`。

## Git 和 CI

- 默认分支 `main`。
- Commit subject 使用 Conventional Commits。
- 不提交 API Key、Token、数据库密码或用户文件。
- `ci.yml` 必须验证生产 Compose 和 Python-only 镜像。
- CI 使用 `tools/scripts/detect_ci_changes.py` 选择必要 Job；工作流或分类脚本变化必须全量运行。
- 文档提交只运行轻量文档检查和统一 `CI gate`，不能启动完整 Compose。
- `real-model.yml` 只在受保护环境中运行。
- 修改运行命令、Compose、CI 或技术方案时同步更新 README、AGENTS 和相关文档。
- 环境变量和 Provider 行为以 `docs/CONFIGURATION.md` 为准，部署排障以
  `docs/OPERATIONS.md` 为准。
