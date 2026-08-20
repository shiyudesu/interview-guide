# InterviewGuide 后端

后端使用 Python 3.13.13、FastAPI、SQLAlchemy、Redis Stream 和 Alembic。API、Worker、
Scheduler 与 Migrate 共用同一代码和镜像。

## 安装

启动完整应用优先在仓库根目录运行 `./scripts/start.sh`；以下步骤用于只开发 Python 后端。

从仓库根目录创建 `.env`：

```bash
cp .env.example .env
```

启动本地基础设施：

```bash
docker compose -f docker-compose.dev.yml up -d --wait
```

安装锁定依赖：

```bash
cd backend
uv sync --frozen
```

## 进程

```bash
uv run --frozen interview-guide-migrate
uv run --frozen interview-guide-api
uv run --frozen interview-guide-worker
uv run --frozen interview-guide-scheduler
```

四个命令应分开运行。Migrate 必须先成功；异步分析、向量化和面试评估依赖 Worker，
恢复和过期任务依赖 Scheduler。

| 入口 | 作用 |
| --- | --- |
| `interview-guide-migrate` | 执行 Alembic 到最新版本 |
| `interview-guide-api` | REST、SSE、WebSocket、OpenAPI 和 Swagger UI |
| `interview-guide-worker` | 消费四组 Redis Stream |
| `interview-guide-scheduler` | 日程过期及失败任务恢复 |

## 代码结构

```text
src/interview_guide/
├── common/          配置、数据库、Redis、AI、错误和运行时
├── infrastructure/ 文件解析、对象存储和 PDF 导出
├── modules/         业务模块
├── main.py          API 入口
├── migrate.py       Alembic 入口
├── worker.py        Redis Stream Worker
└── scheduler.py     APScheduler

alembic/             数据库版本
resources/           Prompt、Skill、字体和 Lua 脚本
tests/               单元、契约和真实基础设施集成测试
```

路由只处理参数、校验、Service 调用和响应。Service 负责编排，Repository 负责数据库读写。
API 返回 Pydantic Model，不直接暴露 SQLAlchemy ORM。

主要列表接口支持可选 `limit`（最大 200）和 `offset`；省略时保持原有完整数组响应。简历、
文字面试、语音面试和知识库列表还支持重复的 `ids` 或 `sessionIds` 参数，供前端轮询时只刷新
活动记录。OpenAPI 明确登记成功状态、响应 Model 和标准 `code + detail` 错误结构。

## 检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

只运行单元测试：

```bash
uv run pytest -m "not integration"
```

集成测试需要真实 PostgreSQL、Redis 和 S3 兼容存储：

```bash
export POSTGRES_PASSWORD=password
export TEST_POSTGRES_URL="postgresql+psycopg://postgres:${POSTGRES_PASSWORD}@127.0.0.1:5432/interview_guide"
export TEST_REDIS_URL=redis://127.0.0.1:6379/0
export TEST_S3_ENDPOINT=http://127.0.0.1:9000
export TEST_S3_ACCESS_KEY=minioadmin
export TEST_S3_SECRET_KEY=minioadmin
export TEST_S3_BUCKET=interview-guide-integration
uv run pytest -m integration
```

不要把集成测试指向保存业务数据的数据库；测试会创建并清理夹具。

## 数据库升级

Alembic 是唯一升级入口：

```bash
uv run --frozen interview-guide-migrate
```

生产环境不要直接执行 SQL 文件，也不要让 API 在启动时修改 schema。

## 关键约束

- API 固定单 Uvicorn worker。
- SQLAlchemy 连接池默认 `pool_size=10`、`max_overflow=0`。
- Embedding 维度固定为 1024。
- Provider API Key 使用 AES-GCM 加密，Compose 主密钥自动生成到共享 `provider_key` 卷；
  直接运行 Python 后端时可用 `APP_AI_CONFIG_ENCRYPTION_KEY` 覆盖本地密钥文件。
- Provider 模型发现使用 OpenAI 兼容 `/models` 接口，Redis 缓存 TTL 为 5 分钟；不支持该
  接口时返回明确警告并保留当前配置。
- 阻塞文件操作进入受限线程池。
- REST 成功响应直接返回业务 JSON，无响应体操作使用 HTTP 204。
- REST 错误使用标准 4xx/5xx 和 `code + detail` 响应；SSE、WebSocket 保持各自状态语义。

完整环境变量见 [配置说明](../docs/CONFIGURATION.md)，部署和排障见
[运行与排障](../docs/OPERATIONS.md)。
