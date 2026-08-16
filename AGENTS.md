# AI 面试平台 Agent 工作规则

## 项目状态

本仓库正在把后端从 Java/Spring 迁移到 Python/FastAPI。

- `docs/MIGRATION_PLAN.md` 是完整迁移要求，开始迁移任务前必须先读相关章节。
- `app/` 是当前 Java 实现，也是迁移期间的新旧行为对照。
- `backend/` 是目标 Python 后端。
- `frontend/` 继续使用现有 React 代码，迁移不能要求前端改变业务接口。
- Java、Gradle、Flyway 和 JVM 文件只能在迁移计划中的全部检查通过后删除。
- 迁移任务只替换技术实现，不能顺手修复、重构或重新设计现有业务行为。

发现 Java 代码、前端调用和文档不一致时，先保存实际运行结果并记录问题，不能自行选择一个
“更合理”的结果。

## 不能改变的行为

Python 实现必须保持：

- REST 路径、HTTP 方法、参数、请求体、multipart 字段和响应头。
- 响应字段、默认值、null、数组顺序、时间格式、错误码和错误文案。
- 普通业务错误继续使用 HTTP 200；文件、SSE 和 WebSocket 按当前特殊行为处理。
- PostgreSQL 表、字段、类型、默认值、约束、索引、扩展和事务结果。
- Redis key、TTL、Stream、消息字段、重试、Pending、reclaim 和 ACK 顺序。
- requestId 幂等锁、结果缓存和数据库唯一索引。
- Prompt、Skill、Provider、模型参数、Tool、JSON Schema、重试和回退顺序。
- SSE 分帧、WebSocket 消息、ASR、TTS、暂停、恢复、超时和断开行为。
- 文件类型判断、文本提取、清洗、hash、对象 key、下载头和 PDF 可见内容。

所有“一致”“完成”“通过”都必须有可执行的检查方法，不能只凭人工感觉判断。

## 已确定的目标方案

### Python 后端

- Python 3.13.13。
- uv 0.11.14。
- uv、`pyproject.toml` 和提交到仓库的 `uv.lock`。
- FastAPI、Uvicorn 和 Pydantic v2。
- SQLAlchemy 2.0 AsyncEngine 和 psycopg 3 async。
- Alembic。
- LangGraph、langchain-openai 和项目统一 LLM Adapter。
- redis-py asyncio。
- APScheduler。
- boto3。
- prometheus-client 和 OpenTelemetry。
- pytest、pytest-asyncio、pytest-mock、Ruff 和 mypy。

### 文件和语音

- PDF 正文：pdfminer.six。
- pypdf 只用于加密状态和页面信息，不作为第二套正文解析 fallback。
- DOCX：python-docx。
- DOC：LibreOffice headless。
- 镜像固定 libmagic 5.44-3 和 LibreOffice 7.4.7-1+deb12u14。
- TXT/Markdown：显式编码处理和现有清洗规则。
- PDF 导出：ReportLab 和现有中文字体。
- ASR/TTS：项目直接封装 DashScope WebSocket 协议。
- 不使用 JVM 文档解析器。
- 不使用 antiword。
- 不依赖 DashScope SDK 的隐式重试。

### 前端

- React 18、TypeScript、Vite 和 Tailwind CSS 4。
- Node 24。
- 使用 `frontend/package.json` 声明的 pnpm 10.26.2。

## Python 运行方式

同一 Python 镜像启动四类程序：

1. **Migrate**
   - 只执行 Alembic 数据库升级。
   - 成功后其他程序才能启动。

2. **API**
   - 提供 REST、SSE 和 WebSocket。
   - 迁移完成初期只运行一个 Uvicorn worker。
   - 不得在语音状态仍保存在进程内时擅自开启多 worker。

3. **Worker**
   - 处理五类 Redis Stream。
   - 每类 Stream 内保持顺序消费。
   - 五类 Stream 可以同时运行。

4. **Scheduler**
   - 只处理数据库中的过期和恢复任务。
   - 只运行一个实例。
   - WebSocket 连接内计时继续由 API 负责。

boto3、ReportLab、libmagic 和文档解析等阻塞操作不能直接运行在 FastAPI 事件循环中。使用
有数量限制的线程池或受控子进程，并支持应用关闭时停止接收新任务。

## 目录结构

```text
app/                    当前 Java 行为参考
backend/                目标 Python 后端
frontend/               现有 React 前端
docs/MIGRATION_PLAN.md  完整迁移要求
migration/              新旧对比脚本、清单、样本和报告
docker-compose.dev.yml  本地 PostgreSQL、Redis 和 RustFS
.github/workflows/      CI
.githooks/              本地 Git hooks
```

目标 Python 代码放在 `backend/src/interview_guide/`：

- `common/`：统一响应、错误、配置、数据库、Redis、AI、评估和日志。
- `infrastructure/`：文档、PDF、对象存储和映射。
- `modules/`：业务模块，每个模块包含 API、Service 和 Repository。
- `main.py`：FastAPI 应用。
- `worker.py`：Redis Stream 消费入口。
- `scheduler.py`：定时任务入口。
- `backend/resources/`：Prompt、Skill、脚本、字体和静态资源。

## 开发命令

本地依赖：

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
```

当前 Java 基线：

```bash
./gradlew :app:compileJava
./gradlew :app:test --no-daemon
./gradlew :app:bootRun
```

迁移阶段 0 清单：

```bash
./migration/scripts/generate-manifests.sh
./migration/scripts/check-manifests.sh
./migration/scripts/sync-flyway-schema.py
./migration/scripts/sync-java-resources.py
./migration/scripts/start-comparison-env.sh
./migration/scripts/start-model-proxy.sh
./migration/scripts/capture-runtime-state.sh
./migration/scripts/run-comparison.sh
./migration/scripts/run-schema-comparison.sh
./migration/scripts/run-interview-schedule-comparison.sh
./migration/scripts/run-interview-skill-comparison.sh
./migration/scripts/run-failure-cases.sh
./migration/scripts/stop-model-proxy.sh
./migration/scripts/stop-comparison-env.sh
```

模型代理：

```bash
cd migration/model-proxy
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run interview-guide-model-proxy
```

Python 工程创建后：

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run uvicorn interview_guide.main:app --host 0.0.0.0 --port 8080
docker build -f Dockerfile -t interview-guide-python ..
```

前端：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
pnpm run build
```

只有明确需要清空本地数据时才执行：

```bash
docker compose -f docker-compose.dev.yml down -v
```

## 迁移工作顺序

每个模块都按以下顺序执行：

1. 整理 Java 当前行为。
2. 增加固定请求、响应、数据、SSE、WebSocket 或文件样本。
3. 在 `backend/` 实现 Python 版本。
4. 运行 Python 单元测试和真实基础设施集成测试。
5. 在隔离环境中分别运行 Java 和 Python。
6. 自动比较接口、数据库、Redis、S3、Prompt 和实时消息。
7. 使用现有前端执行真实流程。
8. 保存差异报告后再开始下一个模块。

Java 和 Python 对比环境必须使用不同端口、数据库、Redis 实例和 S3 bucket，不能让两套
后端消费同一条 Stream 或修改同一份数据。

模块顺序以 `docs/MIGRATION_PLAN.md` 为准。

## 真实模型规则

- 任何用于证明迁移完成、AI 兼容、语音流程、端到端功能或性能的数据，都必须调用真实模型。
- LLM、Embedding、ASR 和 TTS 不得偷偷替换为固定字符串、随机结果或本地假服务。
- Java 和 Python 使用同一个真实 Provider、模型和参数。
- 通过记录代理保存发给真实 Provider 的请求、响应、耗时和错误，但代理不得修改正常结果。
- 发给模型的请求需要逐项比较；真实模型生成的自然语言可能波动，响应应比较 JSON Schema、
  字段类型、数量、范围、回退和数据库保存结果。
- 普通单元测试可以使用明确命名的 stub/fake，前提是测试目标不需要模型参与。
- 使用 stub/fake 的测试必须在名称和报告中明确标记，不能算作真实模型验收。
- 超时、断线、429 和 5xx 可以通过代理制造，但报告必须明确写明这是故障测试。
- 真实模型测试必须保存 Provider、模型、参数、调用时间和费用，密钥必须脱敏。

## Python 代码规则

- FastAPI 路由只负责参数、校验、调用 Service 和返回结果。
- Service 负责编排业务。
- Repository 负责数据库读写。
- API 使用 Pydantic Model，数据库使用 SQLAlchemy Model，不能直接返回 ORM 对象。
- API 输出 camelCase，并明确控制 null、字段顺序、Unicode、时间和数字。
- 使用项目 `BusinessException` 和 `ErrorCode`。
- 不得让 Pydantic 自动增加 Java 当前没有启用的严格校验。
- 使用明确类型，Ruff 和 mypy 不能依赖大范围忽略。
- 不使用 bare `except`。
- 不静默吞掉新的异常。
- 不返回伪装成成功的意外错误。
- 不循环逐条访问数据库，优先批量查询和批量写入。
- 基础设施客户端通过依赖注入提供，不能在业务方法中临时创建。
- 不得因为 Python 写法更方便而改变事务提交、消息发送或错误返回顺序。

一般情况下，LLM、S3、文档解析和外部 HTTP 不放在数据库事务内。但迁移前必须先保存 Java
当前中途失败后的结果；如果调整事务位置，外部可见结果仍要与 Java 一致。

## 数据库规则

- Flyway SQL 和实际 PostgreSQL 结构是迁移依据，不能只参考 Entity。
- 使用 `hstore`、`uuid-ossp` 和 `vector` extension。
- 主键保持 `BIGINT GENERATED BY DEFAULT AS IDENTITY`。
- `vector_store.embedding` 保持 `vector(1024)`。
- `vector_store.metadata` 保持 JSON。
- HNSW 保持 `vector_cosine_ops`。
- 业务 JSON 字符串字段继续使用 TEXT，不能统一改为 JSONB。
- 时间继续使用无时区 `TIMESTAMP(6)`。
- 状态继续使用 VARCHAR 和现有 CHECK，不能自动改为 PostgreSQL enum。
- 保留现有 constraint、index 名称、冗余索引、缺失外键和 unique index。
- 数据库比较必须读取 PostgreSQL 实际结构，不能只比较 SQLAlchemy Model。
- 保留 `SELECT ... FOR UPDATE`、题库替换、向量 promote 和现有 after-commit 行为。

## Redis 和定时任务规则

- 原样复用 `rate_limit_single.lua`。
- 保留限流 key 中当前 Java 类名和方法名，不能换成 Python 函数名。
- 保留 GLOBAL、IP、User、窗口、permit、TTL 和错误码 8001。
- Redis Stream 直接使用 `XGROUP CREATE`、`XREADGROUP`、`XAUTOCLAIM`、`XADD` 和 `XACK`。
- 保留五组 Stream、Group、字段、批量、BLOCK、Pending、reclaim、重试和 ACK 顺序。
- 不使用 Celery、RQ、简单 pub/sub 或内存队列替换 Redis Stream。
- 消息格式错误或实体已经删除时，按 Java 当前行为 ACK 并丢弃。
- requestId 锁、等待时间、持有时间、结果缓存和数据库唯一索引必须保持一致。
- Scheduler 只能单实例运行。
- 面试日程、题目恢复和语音恢复的周期及阈值按迁移计划执行。

## AI 和 LangGraph 规则

- 所有聊天和 Embedding 客户端通过 `LlmProviderRegistry` 获取。
- 所有模型调用必须经过统一 LLM Adapter。
- Provider 数据库为空时从静态配置初始化一次，之后数据库配置是唯一来源。
- Provider 修改后，API、Worker 和 Scheduler 必须清理本地缓存并使用新配置。
- 保留四类客户端：普通 Tool、plain、语音流式 Tool 和 Embedding。
- 关闭 SDK、LangChain 和 LangGraph 的自动重试。
- 如果 Java 底层实际存在重试，在 Adapter 中明确实现相同次数。
- Prompt 和 Skill 文件保持原内容，使用兼容 StringTemplate 的渲染器。
- 保留 PromptSanitizer、随机分隔符、SafeGuard、Tool 和 JSON 修复顺序。
- LangGraph 只用于迁移计划列出的多步骤、分支或回退流程。
- 简单模型调用不能包装成无意义的单节点图。
- 统一评估必须按批次依次调用模型，不能改成并行。
- 面试出题必须保留当前不对称失败回退。
- ASR、TTS、WebSocket 生命周期和音频传输不能放入 LangGraph。

## 文件和存储规则

- 保留简历 10MB、知识库 50MB 和 multipart 50MB 限制。
- 使用 libmagic 判断类型；判断发生 I/O 错误时回退上传 Content-Type。
- 保留 Markdown 扩展名特例、RTF 支持和简历 MIME 子字符串匹配。
- 文档 5MiB 字符上限发生在清洗前，超出后整体失败，不能截断。
- 字符上限按 Java UTF-16 code unit 兼容计算。
- 不增加 OCR。
- 不提取嵌入文件和 PDF inline image。
- 保留文本清洗、SHA-256、日期目录、八位 UUID、安全文件名和拼音规则。
- boto3 使用 path-style。
- 保留 S3 超时、自动建 bucket、Content-Type 和当前 `HEAD` 异常处理。
- PDF 比较文字、页数、字体、布局、截图和响应头，不要求二进制完全相同。

## RAG、SSE 和语音规则

- 普通知识库 SSE 不保存聊天消息。
- RAG Chat 正常完成或报错时保存；客户端取消时不保存部分内容。
- SSE 需要比较原始分帧、换行、错误、完成和取消。
- WebSocket 使用文本 JSON 和 Base64 音频，不改为二进制帧。
- 保留消息大小、发送时间和发送缓冲限制。
- 语音模块必须最后迁移，并先补齐当前禁用测试。
- ASR ready、重连、音频追加重试、TTS 超时和并发按迁移计划中的具体数字实现。
- `audio_chunk.isLast` 保持 false。
- 至少一条音频成功后才发送 `audio_complete`。
- AI 处理期间和结束后 800ms 的音频丢弃按服务端状态判断。
- 4 分 30 秒 warning、5 分钟暂停、关闭后完成和暂停后关闭行为保持一致。
- API 初始只能单 worker，避免重复连接和进程内语音状态被分散。

## 测试和完成条件

- 每个迁移行为都要覆盖正常、错误、重试、重复、超时、取消和程序崩溃。
- 集成测试使用真实 PostgreSQL/pgvector、Redis 和 RustFS/MinIO。
- Python 改动运行 Ruff、mypy 和 pytest。
- 前端改动运行相关测试、Playwright 和 `pnpm run build`。
- 新旧对比必须能发现接口字段、数据库索引、Redis 状态和消息顺序差异。
- 性能测试调用真实 Provider，Java 和 Python 使用同一模型并至少重复五次。
- Java 只能在 REST、数据库、Redis、AI、文件、SSE、WebSocket、前端和性能全部达到迁移计划
  的明确标准后删除。
- 删除 Java 前必须实际演练一次恢复 Java 版本。

## Git 和 CI

- 默认分支是 `main`。
- Commit subject 使用 Conventional Commits：
  `type(optional-scope): summary`。
- 使用 `git config core.hooksPath .githooks` 启用本地 hooks。
- 当前 CI 在 `app/` 存在时运行 Java 基线，在 `backend/pyproject.toml` 存在后运行 Python
  检查，并始终运行前端和 hook 检查。
- 真实模型 CI 只能在有受保护密钥的 main 分支或手动任务中运行。
- Fork PR 不能获得密钥，也不能被标记为完整迁移检查通过。
- 迁移命令、Compose、CI 或最终技术方案变化时，同时更新 README、AGENTS.md 和迁移计划。

## 禁止事项

- 不得在迁移中顺手修复现有功能问题。
- 不得删除 Java 行为参考。
- 不得用假模型冒充真实模型结果。
- 不得直接返回 ORM Entity。
- 不得在业务代码中自行创建 LLM、Redis、S3 或数据库客户端。
- 不得依赖框架默认重试、默认 JSON 或默认校验来猜测兼容行为。
- 不得把 Redis Stream 换成其他任务队列。
- 不得在语音进程内状态尚未迁移时启用多 API worker。
- 不得提交 API Key、Token、数据库密码或真实用户文件。
- 不得使用 `latest` 容器镜像。
