# AI 面试平台 Agent 工作规则

## 项目状态

生产后端为 Python/FastAPI。旧后端迁移已经完成，旧实现、回滚镜像和对比证据已经删除。
兼容行为由后端测试、仓库清单、生产 Compose 集成和受保护真实模型工作流验证。

目录：

```text
backend/                Python 后端
frontend/               React 前端
tools/                  仓库清单、模型诊断和生产验收工具
docs/                   配置、运维和迁移完成记录
docker-compose.yml      生产 Compose
docker-compose.dev.yml  本地基础设施
```

## 不能改变的行为

- 保持 REST 路径、HTTP 方法、参数、请求体、multipart 字段和响应头。
- 保持响应字段、默认值、null、数组顺序、时间格式、错误码和错误文案。
- 普通业务错误继续使用 HTTP 200；文件、SSE 和 WebSocket 保持特殊状态行为。
- 保持 PostgreSQL 表、字段、约束、索引、事务结果和 `vector(1024)`。
- 保持 Redis key、TTL、Stream 字段、Pending、reclaim、重试和 ACK 顺序。
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
- 使用 `BusinessException` 和 `ErrorCode`。
- 不使用 bare `except`，不静默吞异常，不伪装成功。
- 基础设施客户端通过依赖注入提供。
- 阻塞操作必须进入受限线程池或受控子进程。
- Ruff、mypy 和 pytest 必须通过。

## 数据库、Redis 和 AI

- Alembic 是唯一数据库升级入口。
- SQLAlchemy 连接池默认 10 个常驻连接、0 overflow。
- Redis Stream 使用 XGROUP、XREADGROUP、XAUTOCLAIM、XADD 和 XACK。
- 五组 Stream 每组内部顺序消费，失败时先重投或写失败状态，再 ACK。
- 所有模型客户端由 `LlmProviderRegistry` 和统一 LLM Adapter 提供。
- 关闭 SDK、LangChain 和 LangGraph 隐式重试。
- Provider 配置以数据库为准，修改后通过 Redis 版本通知清理进程缓存。
- 当前模型默认值：
  - `qwen3.7-max`
  - `qwen3.7-text-embedding`，1024 维
  - `qwen3-asr-flash-realtime`
  - `qwen3-tts-flash-realtime`

## 运行方式

同一镜像启动：

1. Migrate：Alembic，成功后其他服务才能启动。
2. API：单 Uvicorn worker。
3. Worker：处理五组 Redis Stream。
4. Scheduler：单实例恢复和过期任务。

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
