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

脚本会自动创建 `.env`、生成 PostgreSQL 和对象存储随机密码、校验 Compose、构建并等待所有
服务就绪；失败时会输出容器状态和关键日志。生产 Compose 只有前端映射到宿主机，因此启动前
只检查 `FRONTEND_PORT`；如有占用，会指出占用进程并给出建议端口。遇到 Docker Hub DNS、超时或代理错误时，
脚本会单独提示 Docker daemon 的代理/镜像配置；已有可信 Docker Hub 缓存时，也可以在 `.env`
设置 `INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=mirror.example.com`，值中不要包含 `https://`。成功后会
打开前端。服务器或不希望自动打开浏览器时使用：

```bash
./scripts/start.sh --no-open
```

用于无人值守环境、希望自动同意安装提示时：

```bash
./scripts/start.sh --yes --no-open
```

AI 配置无需写入 `.env`。首次启动会自动生成 Provider 加密主密钥，并只创建一个不带 API Key
的百炼 Provider；启动后在设置页录入百炼 API Key 即可。数据库和对象存储密码不会使用仓库
内置默认值。

需要手工启动时，等价命令为：

```bash
cp .env.example .env
# 先填写 POSTGRES_PASSWORD 和 APP_STORAGE_SECRET_KEY
docker compose up -d --build --wait
docker compose ps
```

默认地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | <http://localhost:5173> |
| API | 前端同源路径 `/api/` |
| Swagger UI | <http://localhost:5173/docs> |
| OpenAPI | <http://localhost:5173/openapi.json> |

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

## 服务器 GHCR 主动拉取部署

服务器部署不需要克隆仓库。`main` 分支 CI 成功后，GitHub Actions 会发布 backend、frontend 和
deployment bundle 三个 GHCR 多架构镜像；服务器的 systemd timer 每 5 分钟主动检查部署通道，
并按不可变的 `sha-<commit>` tag 完成迁移和更新。

服务器只保存 `.env`、纯镜像 Compose、更新脚本和版本状态，不需要 Git、Node.js、Python、pnpm
或 uv。首次安装、private GHCR 登录、NAT 配置、日志和回滚命令见
[GHCR 主动拉取部署](docs/DEPLOYMENT.md)。

## 临时 HTTP 验收部署

NAT 服务器没有可用的 80/443，或宿主机已有多个服务时，可以启动隔离的 HTTP 验收实例：

```bash
./scripts/start-http.sh
```

脚本首次运行会创建权限为 `600` 的 `.env.http`，为 PostgreSQL 和 MinIO 生成随机密码，并使用
独立的 Compose 项目和数据卷。默认只有一个宿主机端口：

| 用途 | 宿主机地址 |
| --- | --- |
| 唯一公网入口 | `0.0.0.0:18073` |

API、PostgreSQL、Redis 和 MinIO 只存在于 Compose 网络，不发布任何宿主机端口。

只需配置一条 NAT TCP 映射，例如“公网 `28080` → 服务器 `18073`”，然后访问
`http://公网IP或域名:28080`。公网端口不必与 `FRONTEND_PORT` 相同。端口冲突时编辑
`.env.http`，不要修改容器内部端口。

```bash
./scripts/stop-http.sh
```

停止脚本保留 HTTP 验收实例的数据卷。该模式是临时、明文的验收入口，不代替服务器所在地要求的
备案或安全合规；非本机 HTTP 页面也无法获得浏览器麦克风权限，因此公网语音录制验收仍需 HTTPS。
详细说明见 [运行与排障](docs/OPERATIONS.md#临时-http-验收部署)。

## 运行架构

生产 Compose 使用同一个 Python 镜像启动四类进程：

1. `interview-guide-migrate` 执行 `alembic upgrade head`。
2. `interview-guide-api` 提供 REST、SSE 和 WebSocket，固定为单 Uvicorn worker。
3. `interview-guide-worker` 消费四组 Redis Stream：简历分析、知识库向量化、知识库出题和
   统一面试评估。
4. `interview-guide-scheduler` 处理日程过期、题目生成恢复和语音会话恢复。

API、Worker 和 Scheduler 会等 Migrate 成功后再启动。前端由 Nginx 提供静态文件，并把
`/api/`、`/ws/`、`/docs` 和 `/openapi.json` 转发到 API。镜像使用多架构 manifest digest，
Docker 会按宿主机自动选择 `linux/amd64` 或 `linux/arm64`，Compose 不再强制模拟 amd64。

## 本地开发

如果尚未通过一键启动脚本生成 `.env`，先复制 `.env.example`，并为
`POSTGRES_PASSWORD`、`APP_STORAGE_SECRET_KEY` 填写随机值。开发 Compose 和直接运行的 Python
后端必须读取同一组凭据。

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

Vite 默认监听 <http://localhost:5173>，并把 `/api` 和 `/ws` 转发到
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
pnpm run lint
pnpm run test:unit
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
  PostgreSQL/Redis/S3 集成测试、前端无真实后端依赖的 Playwright、生产 Compose 及前端真实
  后端 E2E。
- API 仓库清单按 REST 路径和 HTTP 方法核对前后端调用；出现前端调用但后端无对应接口时 CI
  直接失败。
- `CI gate` 汇总必需 Job，允许未命中的检查安全跳过。
- 每日定时和手动触发始终执行全量 CI。
- `Real model production checks`：使用 `real-model` 环境中的受保护 Secret
  `REAL_MODEL_API_KEY` 调用真实 LLM、Embedding、ASR 和 TTS。

CI 还会检查生产镜像保持 Python-only。
