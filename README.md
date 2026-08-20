# InterviewGuide

InterviewGuide 是一个自托管 AI 面试平台，覆盖简历分析、文字和语音模拟面试、面试日程、
知识库 RAG、知识库出题及多模型 Provider 管理。

后端为 Python/FastAPI，生产环境只运行 Python 服务和基础设施组件。

## 功能

- 上传 PDF、DOC、DOCX 简历，生成结构化分析和 PDF 报告
- 按岗位 Skill 或 JD 生成文字面试，异步评估并保存报告
- 内置 Java、Python、Go、前端、数据工程、DevOps/SRE、系统设计、算法、测试和 AI Agent 等面试方向
- 使用可追溯的多来源题目目录维护普通面试参考资料，生产链路不依赖外部题库
- 实时 ASR/TTS 语音面试，支持暂停、恢复和会后评估
- 管理面试日程，支持自然语言解析和状态流转
- 上传知识库文件，完成清洗、切片、向量化和 RAG 对话
- 从知识库生成题目并发起专项面试
- 在设置页管理聊天、Embedding、ASR 和 TTS 配置

## 技术栈

| 部分 | 实现 |
| --- | --- |
| 后端 | Python 3.13.13、FastAPI、Uvicorn、Pydantic v2 |
| 数据库 | PostgreSQL 16、pgvector、SQLAlchemy 2、psycopg 3、Alembic |
| 异步任务 | Redis 7、Redis Stream、APScheduler |
| AI | LangGraph、langchain-openai、统一 LLM Adapter |
| 文件 | S3 兼容存储、pdfminer.six、python-docx、LibreOffice、ReportLab |
| 前端 | React 18、TypeScript、Vite 5、Tailwind CSS 4 |
| 工具链 | uv 0.11.14、Node.js 24、pnpm 10.26.2 |

## 快速启动

启动脚本会检查 Docker CLI、Docker Compose v2 和 Docker daemon。缺少 Docker 时，它会先
询问一次，确认后在 Windows、macOS、Ubuntu、Debian 或 WSL 上自动安装官方组件；过程中可能
弹出 UAC 或请求 sudo 密码。

Windows 可以直接双击仓库根目录的 `start.cmd`。

Linux、macOS 或 WSL：

```bash
./scripts/start.sh
```

脚本会自动创建 `.env`、校验 Compose、构建并等待所有服务就绪；失败时会输出容器状态和关键
日志。启动前还会检查 5173、8080、5432、6379、9000、9001 等映射端口；如有占用，会指出
占用进程，并给出应修改的 `.env` 变量和建议端口。成功后会打开前端。服务器或不希望自动打开
浏览器时使用：

```bash
./scripts/start.sh --no-open
```

用于无人值守环境、希望自动同意安装提示时：

```bash
./scripts/start.sh --yes --no-open
```

AI 配置无需写入 `.env`。首次启动会自动生成 Provider 加密主密钥，并只创建一个不带 API Key
的百炼 Provider；启动后在设置页录入百炼 API Key 即可。`.env` 主要用于端口和基础设施配置。

对外部署前还要修改 PostgreSQL 和对象存储的默认密码。

需要手工启动时，等价命令为：

```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose ps
```

默认地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | <http://localhost:5173> |
| API | <http://localhost:8080> |
| Swagger UI | <http://localhost:8080/docs> |
| OpenAPI | <http://localhost:8080/openapi.json> |
| MinIO Console | <http://localhost:9001> |

查看日志：

```bash
docker compose logs -f app worker scheduler
docker compose logs migrate
```

停止服务并保留所有数据：

- Windows：双击根目录的 `stop.cmd`
- Linux、macOS、WSL：

```bash
./scripts/stop.sh
```

手工执行的等价命令是 `docker compose down --remove-orphans`。

`docker compose down -v` 会删除 PostgreSQL、Redis 和对象存储数据，只能在确认不再需要本地
数据时使用。

## 运行架构

生产 Compose 使用同一个 Python 镜像启动四类进程：

1. `interview-guide-migrate` 执行 `alembic upgrade head`。
2. `interview-guide-api` 提供 REST、SSE 和 WebSocket，固定为单 Uvicorn worker。
3. `interview-guide-worker` 消费四组 Redis Stream：简历分析、知识库向量化、知识库出题和
   统一面试评估。
4. `interview-guide-scheduler` 处理日程过期、题目生成恢复和语音会话恢复。

API、Worker 和 Scheduler 会等 Migrate 成功后再启动。前端由 Nginx 提供静态文件，并把
`/api/` 和 `/ws/` 转发到 API。

## 本地开发

先启动 PostgreSQL、Redis 和 RustFS：

```bash
docker compose -f docker-compose.dev.yml up -d --wait
```

启动后端：

```bash
cd backend
uv sync --frozen
uv run --frozen interview-guide-migrate
uv run --frozen interview-guide-api
```

Worker 和 Scheduler 需要分别在新终端中运行：

```bash
cd backend
uv run --frozen interview-guide-worker
```

```bash
cd backend
uv run --frozen interview-guide-scheduler
```

启动前端：

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

Vite 默认监听 <http://localhost:5173>，并把 `/api` 转发到
`VITE_API_PROXY_TARGET`，默认值为 `http://localhost:8080`。

REST API 成功时直接返回业务 JSON；无响应体操作返回 HTTP 204。错误使用标准 4xx/5xx
状态码，响应体为 `{"code": 业务错误码, "detail": "错误说明"}`。

## Provider 和模型

系统只内置百炼 Provider，也可以在设置页添加任意 OpenAI 兼容 Provider。百炼种子只在
Provider 表为空时写入，且不包含 API Key；系统启动后，数据库和设置页中的配置是实际数据源。

当前默认模型：

```text
聊天       qwen3.7-max
Embedding  qwen3.7-text-embedding（1024 维）
ASR        qwen3-asr-flash-realtime
TTS        qwen3-tts-flash-realtime
```

设置页会通过 Provider 的 OpenAI 兼容 `GET /models` 接口自动拉取聊天和 Embedding 模型，
结果在 Redis 中缓存 5 分钟，也可以手工强制刷新。厂商不支持模型列表接口或请求失败时，页面会
明确显示原因并保留当前配置和手工输入；向量维度仍需按厂商文档确认。
详细配置见 [配置说明](docs/CONFIGURATION.md)。

## 检查命令

后端：

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

前端：

```bash
cd frontend
pnpm run test:interview-history
pnpm run test:question-generation
pnpm run test:interview-capacity
pnpm run test:interview-entry
pnpm run test:e2e
pnpm run build
```

仓库清单和模型代理：

```bash
./tools/scripts/check-manifests.sh
cd tools/model-proxy
uv sync --frozen
uv run python -m unittest discover -s tests -v
```

普通面试参考资料来源校验：

```bash
python3 tools/scripts/reference_sources.py --root . validate
```

## 目录

```text
backend/                FastAPI 后端、Alembic、资源和测试
frontend/               React 前端、Playwright 和 Nginx 配置
tools/                  仓库清单、参考资料采集、模型诊断代理、生产模型验收
docs/                   配置、运维和架构说明
docker-compose.yml      完整生产拓扑
docker-compose.dev.yml  本地基础设施
```

## 文档

- [配置说明](docs/CONFIGURATION.md)
- [运行与排障](docs/OPERATIONS.md)
- [统一自适应面试](docs/ADAPTIVE_INTERVIEW.md)
- [后端开发](backend/README.md)
- [前端开发](frontend/README.md)
- [仓库工具](tools/README.md)
- [普通面试参考资料来源](docs/REFERENCE_SOURCES.md)

## CI

- `CI` 先按变更路径分类。文档提交只运行轻量策略和链接检查；后端、前端、模型代理与生产
  Compose 集成仅在对应代码或部署文件变化时运行。
- 完整运行包含后端 lint/mypy/pytest、前端测试和构建、模型代理、隔离的
  PostgreSQL/Redis/S3 集成测试、生产 Compose 及前端真实后端 E2E。
- `CI gate` 汇总必需 Job，允许未命中的检查安全跳过。
- 每日定时和手动触发始终执行全量 CI。
- `Real model production checks`：使用 `real-model` 环境中的受保护 Secret
  `REAL_MODEL_API_KEY` 调用真实 LLM、Embedding、ASR 和 TTS。

CI 还会检查生产镜像保持 Python-only。
