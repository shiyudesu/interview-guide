# InterviewGuide

智能 AI 面试平台，包含简历分析、文字/语音模拟面试、面试日程、知识库 RAG、知识库题库面试和多模型配置。

## 技术栈

- Python 3.13.13、FastAPI、Uvicorn、Pydantic v2
- SQLAlchemy 2.0 AsyncEngine、psycopg 3、Alembic、PostgreSQL 16 + pgvector
- redis-py asyncio、Redis Stream、APScheduler
- LangGraph、langchain-openai、统一 LLM Adapter
- pdfminer.six、python-docx、LibreOffice、ReportLab、boto3
- React 18、TypeScript、Vite、Tailwind CSS 4
- uv 0.11.14、Node 24、pnpm 10.26.2

## 快速启动

复制并编辑环境变量：

```bash
cp .env.example .env
```

必须长期保持 `APP_AI_CONFIG_ENCRYPTION_KEY` 不变。默认模型：

```env
AI_MODEL=qwen3.7-max
AI_EMBEDDING_MODEL=qwen3.7-text-embedding
APP_AI_CONFIG_ENCRYPTION_KEY=replace_with_a_stable_random_secret
```

如使用 DashScope，再配置：

```env
AI_BAILIAN_API_KEY=your_key
```

完整部署：

```bash
docker compose up -d --build --wait
docker compose ps
```

访问：

- 前端：<http://localhost>
- API：<http://localhost:8080>
- Swagger：<http://localhost:8080/swagger-ui.html>
- MinIO：<http://localhost:9001>

查看日志：

```bash
docker compose logs -f app worker scheduler
docker compose logs migrate
```

停止服务：

```bash
docker compose down
```

仅在明确需要删除所有本地数据时使用：

```bash
docker compose down -v
```

## 本地开发

启动依赖：

```bash
docker compose -f docker-compose.dev.yml up -d
```

后端：

```bash
cd backend
uv sync --frozen
uv run --frozen interview-guide-migrate
uv run --frozen interview-guide-api
```

另开终端启动异步进程：

```bash
cd backend
uv run --frozen interview-guide-worker
```

```bash
cd backend
uv run --frozen interview-guide-scheduler
```

前端：

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

## 检查命令

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

```bash
cd frontend
pnpm run build
pnpm run test:e2e
```

## 运行架构

同一 Python 镜像启动四类程序：

1. `interview-guide-migrate`：只执行 Alembic 升级。
2. `interview-guide-api`：提供 REST、SSE 和 WebSocket，保持单 Uvicorn worker。
3. `interview-guide-worker`：并行运行五类 Redis Stream 的顺序消费者。
4. `interview-guide-scheduler`：单实例处理过期与恢复任务。

Compose 会等待 Migrate 成功后再启动 API、Worker 和 Scheduler。

## Provider

内置 DashScope、Kimi、DeepSeek、GLM 和 LM Studio，也可添加任意 OpenAI 兼容 Provider。

- 默认聊天模型：`qwen3.7-max`
- 默认向量模型：`qwen3.7-text-embedding`，1024 维
- 默认 ASR：`qwen3-asr-flash-realtime`
- 默认 TTS：`qwen3-tts-flash-realtime`

Provider API Key 加密保存在 PostgreSQL。API、Worker 和 Scheduler 必须使用相同的
`APP_AI_CONFIG_ENCRYPTION_KEY`。

## 数据和对象存储

- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`
- MinIO API：`localhost:9000`
- MinIO Console：`localhost:9001`

上传限制：简历 10MB、知识库 50MB、multipart 50MB。

## 自动化

- `ci.yml`：Python、真实基础设施集成、生产 Compose、前端和镜像无 JVM 检查。
- `real-model.yml`：受保护环境中的 LLM、Embedding、ASR 和 TTS 生产冒烟。
- `tools/`：仓库清单检查、模型诊断代理和生产模型验收工具。

Java 回滚标签、镜像和迁移期间的对比证据已在最终收尾时删除。
