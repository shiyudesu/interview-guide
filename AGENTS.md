# AI 面试平台 Agent 工作规则

## 项目状态

生产后端为 Python/FastAPI。当前行为由后端测试、仓库清单、生产 Compose 集成和受保护
真实模型工作流验证。

多租户账号和用户自带 API Key 已按 `docs/MULTI_TENANT_BYOK.md` 完成仓库实现。当前具备
Provider 出站防护、账号/Session/CSRF、管理员 CLI、`legacy-owner` 兼容迁移，以及简历、日程、
面试、知识库、题库、RAG 和语音的 Repository 级所有权校验、用户级 Provider、默认模型/语音
配置及 AAD Key 加密、用户级文件去重与对象 key，以及异步任务 Provider 归属。前端已具备登录、
注册关闭提示、受保护路由、CSRF、401 失效处理、邮箱验证、密码找回、账号安全和退出入口。
自助注册仍默认关闭；部署者必须配置真实 SMTP 和正式 HTTPS 公网地址，并完成目标服务器现场
验证后再显式开放。仓库级双用户、浏览器和隔离生产 Compose 门禁已经通过。
`APP_AUTH_REGISTRATION_ENABLED` 必须保持关闭，直到计划中的全部双用户隔离门禁通过。

OpenTrek 校园赛接入已按 `docs/plans/OPENTREK_MIGRATION_PLAN.md` 实现：比赛模式固定路由四类
Agent，通过运行时 `skillList` 选择当前方向对应的 13 个岗位 Skill 之一，知识库使用只读 Kortex
哈希映射且失败不回退
pgvector；平台资源由受保护的 provisioning CLI 配置。校园源码部署使用 `.env.campus`、独立
`interview-guide-campus` Compose 项目和 `scripts/start-campus.sh`，仅公开前端 HTTP 入口并关闭
语音及知识库写操作。目标 Linux 主机、两台真实校园设备和重启持久化仍属于现场验收门禁，未取得
对应环境时不得宣称这些门禁已经通过。

目录：

```text
backend/                Python 后端
frontend/               React 前端
tools/                  仓库清单、模型诊断和生产验收工具
scripts/                跨平台一键启动和仓库辅助脚本
docs/                   配置、运维和架构说明
deploy/                 GHCR 纯镜像清单、主动拉取、systemd 和回滚脚本
docker-compose.yml      生产 Compose
docker-compose.dev.yml  本地基础设施
docker-compose.test.yml CI/集成测试回环端口覆盖
.env.http.example       NAT 高端口临时 HTTP 验收配置模板
.env.campus.example     OpenTrek 校园赛隔离实例配置模板
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
- 所有模型客户端由用户作用域 `ScopedProviderRegistry` 和统一 LLM Adapter 提供；Worker 必须先
  根据资源所有者取得用户作用域，不能使用全局或 legacy Provider 回退。
- 普通面试外部题库只允许通过 `tools/scripts/reference_sources.py` 离线采集，生产请求链路不得
  调用外部题库；运行时只读取已审核并提交的 Skill reference。
- 外部来源必须登记在 `tools/reference_sources/catalog.json`，新增或修改 reference 时同步更新
  `provenance.json`；无明确许可的内容只能用于方向发现，不能复制题解。
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
启动脚本必须在构建前检查实际发布的宿主机端口，并在 Compose 绑定失败时给出对应 `.env` 变量、
建议端口和占用进程；不得要求用户修改容器内部端口。生产 Compose 只能发布前端入口，API、
PostgreSQL、Redis 和对象存储不得映射宿主机端口；集成测试只能通过 `docker-compose.test.yml`
临时绑定到 `127.0.0.1`。
Docker Hub 镜像必须统一支持 `INTERVIEW_GUIDE_DOCKERHUB_REGISTRY` 来源覆盖；默认仍使用
`docker.io`，启动脚本只提供 DNS、代理和可信 mirror 的诊断，不得自动修改 daemon 或写入
来源不明的公共镜像站。
关闭服务优先使用 `scripts/stop.sh` 或 `stop.cmd`，只能执行非破坏性的 Compose down 并保留
数据卷；不得在一键关闭入口中提供或隐式调用 `down -v`。
NAT 高端口临时验收使用 `scripts/start-http.sh` 和 `scripts/stop-http.sh`；必须使用单独的
`.env.http`、Compose 项目名和数据卷，只公开前端入口，其他服务不得发布宿主机端口。该模式
不能宣称绕过备案或替代 HTTPS，公网 HTTP 下必须明确提示麦克风不可用。

OpenTrek 校园赛使用 `scripts/start-campus.sh` 和 `scripts/stop-campus.sh`；必须使用单独的
`.env.campus`、Compose 项目名和数据卷，只公开前端入口。启动前必须通过
`interview-guide-provision-opentrek` 配置 OpenTrek应用密钥、四个已发布 Agent 版本、13 个扫描通过的 Skill
和完成向量化的 Kortex 文档知识库。`.env.campus`、OpenTrek Cookie 和账号凭据不得提交。该模式
只支持 Ubuntu/Debian x86_64 校园主机，HTTP 风险和麦克风不可用必须明确提示。

Compose 和 Dockerfile 不得固定 `linux/amd64` 或声明全局 `container_name`。所有固定 digest 必须
指向同时包含 `linux/amd64`、`linux/arm64` 的 manifest list；启动脚本应拒绝完整栈不支持的其他
架构。生产基础设施密码必须由启动脚本生成或由部署者显式提供，不能回退到仓库内置弱密码。

服务器正式分发使用 `.github/workflows/publish-ghcr.yml` 和 `deploy/`。只有 `CI` 对当前 `main`
commit 成功后才能推进 GHCR `main` 部署通道；backend、frontend 必须先发布同一 revision 的
不可变 `sha-<commit>` 多架构镜像，deployment bundle 最后发布。服务器必须主动拉取，GitHub
Actions 不持有服务器 SSH Key；更新过程必须校验镜像 revision、先执行 Alembic、等待健康检查、
记录当前及上一成功 tag，并保留数据卷。部署包变化也必须通过 GHCR 通道下发，服务器不得依赖
完整 Git 仓库。

生产后端镜像必须保留 `.doc`、`.rtf` 的 LibreOffice 转换能力，但使用 nogui 包，并将大型系统
依赖和 Python site-packages 拆分成有界 layer，避免弱网络因单个超大 blob 无法完成拉取。

同一镜像启动：

1. Migrate：Alembic，成功后其他服务才能启动。
2. API：单 Uvicorn worker。
3. Worker：处理四组 Redis Stream。
4. Scheduler：单实例恢复和过期任务。

正式公网部署必须使用备案域名和 HTTPS。Caddy 作为唯一公网入口发布 80/443，通过 Let's Encrypt
自动签发和续期证书，80 仅用于 ACME 和跳转 HTTPS；证书状态必须保存在独立数据卷。前端 Nginx
不直接暴露公网，必须通过 Docker DNS 动态解析 `app`，健康检查经由反向代理访问 `/health`，
后端容器重建不能要求同时重启前端。`scripts/start-http.sh` 仍只用于隔离的临时明文验收。
服务器已有宿主机 Caddy 时，正式部署包必须支持 `--external-caddy`：不启动 Compose gateway，
前端只绑定 `127.0.0.1:18073`，宿主机 Caddy 自动签证书并反向代理；主动更新仍需通过本机 443
验证真实域名证书和 `/health`。

```bash
docker compose up -d --build --wait
docker compose ps
docker compose logs migrate app worker scheduler frontend gateway
```

## 测试

- 单元测试可以使用明确命名的 fake/stub。
- 真实模型验收必须使用受保护 Key，不能用 fake 冒充。
- 集成测试使用真实 PostgreSQL/pgvector、Redis 和 S3 兼容存储。
- 集成测试不能指向保存业务数据的数据库或 bucket。
- 前端改动运行 `pnpm run lint`、`pnpm run test:unit`、相关 Playwright 和
  `pnpm run build`。
- 浏览器验证使用 Windows Chrome：
  `/mnt/c/Program Files/Google/Chrome/Application/chrome.exe`。

## Git 和 CI

- 默认分支 `main`。
- Commit subject 使用 Conventional Commits。
- 不提交 API Key、Token、数据库密码或用户文件。
- `ci.yml` 必须验证生产 Compose 和 Python-only 镜像。
- CI 使用 `tools/scripts/detect_ci_changes.py` 选择必要 Job；工作流或分类脚本变化必须全量运行。
- 前端 CI 必须运行不依赖真实后端的 Playwright；生产 Compose 集成运行标记为
  `@real-backend` 的浏览器用例。
- API 清单必须按 REST 路径和 HTTP 方法匹配，不能保留未明确修复的 frontend-only 调用。
- 文档提交只运行轻量文档检查和统一 `CI gate`，不能启动完整 Compose。
- `real-model.yml` 只在受保护环境中运行。
- 修改运行命令、Compose、CI 或技术方案时同步更新 README、AGENTS 和相关文档。
- 环境变量和 Provider 行为以 `docs/CONFIGURATION.md` 为准，部署排障以
  `docs/OPERATIONS.md` 为准。
