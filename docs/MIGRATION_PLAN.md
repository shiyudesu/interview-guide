# Java/Spring AI 到 Python/LangGraph 技术栈迁移实施计划

## 1. 问题与目标

当前后端基于 Java 25、Spring Boot 4.1、Spring AI 2.0、Spring Data JPA、Redisson、
Apache Tika、iText 和 DashScope Java SDK。后端约有 197 个 Java 文件，覆盖简历、
文字面试、语音面试、知识库、RAG、面试日程、多 Provider 配置、Redis Stream
异步任务、pgvector、S3 文件存储、SSE 和 WebSocket。

本次迁移的唯一目标是替换技术栈：

- Java/Spring Boot/Spring AI 替换为 Python/FastAPI/LangGraph。
- PostgreSQL、pgvector、Redis、Redis Stream、S3/RustFS、React 前端继续保留。
- 最终运行环境彻底移除 Java/JVM，包括 Flyway 和 Apache Tika Java 运行时。
- 当前没有需要保留的开发数据，允许重建 PostgreSQL、Redis 和对象存储。
- 开发阶段直接逐模块替换，不建设生产双栈路由、灰度发布和长期 Java 回滚链路。

### P0 不变量

除实现技术外，以下内容必须完全一致：

- 用户功能、业务规则和页面交互。
- REST 路径、HTTP 方法、参数、响应字段、默认值、错误码和错误文案。
- PostgreSQL 表结构、字段类型、约束、索引和状态机。
- Redis key、TTL、Stream、消息字段、重试、ACK 和限流语义。
- Prompt、Skill、模型参数、Provider 选择、结构化输出和降级策略。
- SSE 分帧、WebSocket 消息协议、时序、超时、暂停和恢复行为。
- 文件格式、上传限制、哈希去重、对象存储 key、下载响应和 PDF 内容。

迁移过程中发现的现存问题只能登记，不能在迁移任务中顺手修复。需要修复时必须在
迁移完成后以独立需求处理。

## 2. 已确认的迁移边界

- 实施方式：开发阶段直接逐模块替换。
- 数据处理：允许清空并重建开发数据库、Redis 和 RustFS/MinIO 数据。
- Java 边界：最终不保留任何 JVM 运行时。
- LangGraph 边界：
  - 多步骤、并行、分支和降级流程使用 LangGraph。
  - 单次模型调用通过统一 Python LLM Adapter 完成，不创建无意义的单节点图。
  - 所有 AI 调用均不再依赖 Spring AI。
- 前端：原则上不修改业务代码；只有测试或环境配置确有必要时才能调整。

## 3. 目标技术栈

| 当前技术 | 目标技术 |
| --- | --- |
| Java 25 | Python 3.13 |
| Gradle | uv + pyproject.toml |
| Spring Boot WebMVC | FastAPI + Uvicorn |
| Jackson / Bean Validation | Pydantic v2 |
| Spring Data JPA | SQLAlchemy 2.0 + psycopg 3 |
| Flyway | Alembic，历史结构重建为等价初始迁移 |
| Spring AI | LangGraph + langchain-openai + 自定义 LLM Adapter |
| Reactor Flux | async generator + StreamingResponse |
| Spring WebSocket | FastAPI/Starlette WebSocket |
| Redisson | redis-py asyncio |
| Spring Scheduler | APScheduler 独立单实例进程 |
| AWS S3 SDK | boto3 |
| Apache Tika | python-magic + pdfminer.six/pypdf + python-docx + antiword/LibreOffice |
| iText 8 | ReportLab，继续使用现有中文字体 |
| DashScope Java SDK | DashScope Python SDK或原始 WebSocket 协议 |
| Micrometer | prometheus-client + OpenTelemetry |
| JUnit/Mockito/AssertJ | pytest + pytest-asyncio + pytest-mock |

## 4. 目标工程结构

迁移期间新增 `backend/`，保留 `app/` 作为只读行为参考。全部验收通过后删除 Java
`app/`，Docker Compose 中的服务名仍保持 `app`，避免前端和部署调用变化。

```text
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/
├── src/interview_guide/
│   ├── main.py
│   ├── common/
│   │   ├── api/
│   │   ├── ai/
│   │   ├── config/
│   │   ├── db/
│   │   ├── errors/
│   │   ├── evaluation/
│   │   ├── redis/
│   │   └── result/
│   ├── infrastructure/
│   │   ├── document/
│   │   ├── export/
│   │   ├── storage/
│   │   └── mapping/
│   ├── modules/
│   │   ├── interview/
│   │   ├── interview_schedule/
│   │   ├── knowledge_base/
│   │   ├── llm_provider/
│   │   ├── resume/
│   │   └── voice_interview/
│   ├── worker.py
│   └── scheduler.py
├── resources/
│   ├── prompts/
│   ├── skills/
│   ├── scripts/
│   ├── fonts/
│   └── voice-interview-opening.yml
└── tests/
```

API、Worker 和 Scheduler 使用同一代码库、不同启动命令：

- API：REST、SSE、WebSocket。
- Worker：Redis Stream 消费。
- Scheduler：日程过期、题目生成恢复和语音评估恢复。

## 5. 实施阶段

### 阶段 A：冻结现有行为

目标是在删除 Java 前获得可自动比较的行为基线。

实施内容：

1. 从所有 Controller、前端 API 和 TypeScript 类型生成接口契约矩阵。
2. 固化统一响应：
   - 成功 `{code: 200, message: "success", data: ...}`。
   - 普通业务异常继续使用 HTTP 200。
   - 文件、SSE 和 WebSocket 保持当前例外行为。
3. 为每个接口保存典型请求、响应、错误、空值、默认值和时间格式样本。
4. 保存 SSE event block 和换行转义样本。
5. 保存语音 WebSocket 从连接、开场、ASR、提交、LLM、TTS 到断线的完整 trace。
6. 保存所有 Prompt 的渲染快照、JSON Schema 和模型请求参数。
7. 保存文档解析、文本清洗、分块、对象 key 和 PDF 黄金样本。
8. 将 36 个现有 Java 测试文件按行为映射到 Python 测试清单。
9. 登记但不修复当前兼容行为：
   - 前端调用但后端不存在的 `/api/resumes/statistics`。
   - 语音创建请求中的 `roleType` 当前被忽略。
   - WebSocket URL 当前硬编码 localhost。
   - `audio_chunk.isLast` 当前始终为 false。
   - 部分接口当前未启用完整校验。
   - 简历 AI 失败返回零分结果而非任务失败。

完成门禁：

- 每个外部接口均有契约用例。
- 每个 AI 用例均有固定模型响应的回归样本。
- 每个异步状态机均有正常、重试、最终失败和重复执行样本。

### 阶段 B：建立 Python 基础骨架

实施内容：

1. 使用 uv 管理 Python 版本和锁文件。
2. 配置 Ruff、mypy、pytest 和覆盖率。
3. 创建 FastAPI 应用，端口保持 8080。
4. 实现与 Spring 相同的兼容入口：
   - `/swagger-ui.html`
   - `/v3/api-docs`
   - `/actuator/health`
   - `/actuator/info`
   - `/actuator/metrics`
   - `/actuator/prometheus`
5. 实现 `Result`、`BusinessException`、`ErrorCode` 和全局异常处理。
6. Pydantic 输出使用 camelCase，保留 null、数组顺序和无时区时间格式。
7. 复刻 CORS origin、method、credentials 和 multipart 50MB 限制。
8. 建立配置模型，继续支持当前环境变量和 `application.yml` 中的同名配置。
9. 配置结构化日志、请求关联 ID、Prometheus 和 OpenTelemetry。

完成门禁：

- 前端 Axios 无须修改即可访问健康检查和模拟接口。
- 统一响应、异常、OpenAPI 路径和 CORS 契约测试通过。

### 阶段 C：重建等价数据库结构

因为允许重建开发数据，使用 Alembic 创建新的初始 migration，但必须逐字段复刻现有
Flyway 最终状态。

实施内容：

1. 建立所有 SQLAlchemy Model。
2. 保留：
   - 原表名和列名。
   - `BIGINT IDENTITY`。
   - `VARCHAR` 状态字段和 CHECK 约束。
   - JSON 字符串使用 `TEXT`，不改为 JSONB。
   - `TIMESTAMP(6)` 无时区。
   - 当前 FK 和缺失 FK。
   - 当前唯一约束和索引，包括冗余索引。
3. 使用 Alembic raw SQL 创建：
   - `vector` 和 `uuid-ossp` extension。
   - `vector_store.embedding vector(1024)`。
   - HNSW `vector_cosine_ops` 索引。
4. 显式实现原 Entity `@PrePersist/@PreUpdate` 默认值。
5. 实现 Repository 和事务 helper：
   - LLM、S3、文档解析、外部 HTTP 不进入数据库事务。
   - 保留 `SELECT ... FOR UPDATE`。
   - 保留题库替换、向量 promote 和 after-commit 投递边界。
6. 编写 schema diff，比较 PostgreSQL catalog，而不是只比较 ORM Model。

完成门禁：

- 新旧空数据库的表、列、类型、默认值、约束和索引差异为零。
- 所有状态机和唯一键测试通过。

### 阶段 D：迁移 Redis、异步任务和限流

实施内容：

1. 原样复用 `rate_limit_single.lua`。
2. 保留限流 key namespace、GLOBAL/IP/User 维度、窗口、permit 和错误码 8001。
3. 使用 redis-py 实现 Stream 模板：
   - `XREADGROUP`
   - `XAUTOCLAIM`
   - `XADD MAXLEN ~ 1000`
   - `XACK`
4. 保留五组 Stream 名称、Group 和消息字段。
5. 保留批量 10、BLOCK 1 秒、Pending idle 5 分钟、claim 10。
6. 保留 retryCount 0 到 3，因此最多执行四次。
7. 保留“重投后 ACK”的 at-least-once 语义，不替换为 Celery。
8. 缓存改为明确 JSON codec；因为允许清空数据，不实现 Redisson 二进制兼容层。
9. 保留：
   - 文字会话缓存 24 小时。
   - 语音会话缓存 1 小时。
   - requestId 创建幂等结果 1 天。
10. Scheduler 单实例执行当前恢复和过期逻辑。

完成门禁：

- Redis 集成测试覆盖重复消费、崩溃窗口、reclaim、重试和最终失败。
- 同样的故障序列产生相同数据库状态。

### 阶段 E：迁移文件、解析、存储和 PDF

实施内容：

1. 文件校验保持简历 10MB、知识库 50MB 和当前 MIME 白名单。
2. 使用 libmagic 检测实际 MIME，不能只信任上传头。
3. 解析链：
   - PDF：pdfminer.six/pypdf，复刻位置排序。
   - DOCX：python-docx。
   - DOC：antiword 或 LibreOffice headless，不引入 JVM。
   - TXT/Markdown：按当前编码和清洗规则处理。
4. 保持无 OCR、不提取嵌入文件、不提取 PDF inline image。
5. 复刻正文 5Mi 字符上限和超长失败行为。
6. 逐条移植文本清洗正则和换行规则。
7. 使用 boto3 path-style 访问 RustFS/MinIO。
8. 保持 SHA-256、日期目录、8 位 UUID、安全文件名、拼音规则和 URL 拼接。
9. 使用 ReportLab 和现有朱雀仿宋字体重建 PDF。
10. 保留 Unicode `So/Cs` 删除、字段顺序、下载 Content-Type 和 RFC 5987 文件名。

完成门禁：

- 黄金文档的清洗文本、哈希、对象 key 与 Java 基线一致。
- PDF 用户可见内容、顺序、字体、分页和响应头一致；不要求二进制字节相同。

### 阶段 F：迁移 Provider 和统一 LLM Adapter

实施内容：

1. 实现 Python `LlmProviderRegistry`：
   - 数据库配置优先，静态配置 fallback。
   - 聊天和 Embedding 默认 Provider 独立。
   - base URL 自动补 `/v1`。
   - 连接 10 秒、读取 300 秒。
   - temperature 缺省 0.2。
2. 保留 plain、voice、embedding 三类客户端的能力差异。
3. 使用 AES-GCM 复刻 API Key 加密、nonce、Base64 和 key 派生。
4. 保留 Provider 增删改查、掩码、默认切换、reload 和连通性测试。
5. 禁用 SDK、LangChain 和 LangGraph 的隐式自动 retry。
6. 实现结构化输出兼容层：
   - 同样的 JSON Schema。
   - 默认最多两次。
   - 第二次注入上次错误和严格 JSON 指令。
   - 同样的错误截断、指标和最终 BusinessException。
7. Prompt 内容不转换为新模板；继续保存原文件，编写兼容渲染器并使用快照测试确保
   渲染文本逐字符一致。
8. Skill 文件、reference 文件和 display 元数据原样复用。
9. 将 SkillsTool 映射为 LangChain Tool，但保持 tool history 和 memory 当前关闭状态。

完成门禁：

- 固定 Mock Provider 下，请求路径、headers、model、temperature、messages、tools、
  JSON Schema 和调用次数一致。

### 阶段 G：实现 LangGraph 工作流

#### G1. 面试出题图

节点：

```text
resolve_skill
→ allocate_question_counts
→ [generate_resume_questions || generate_direction_questions]
→ apply_existing_fallbacks
→ merge_and_cap
```

必须保留单分支失败、双分支失败和静态 fallback 的当前顺序。

#### G2. 统一评估图

节点：

```text
prepare_qa
→ fan_out_batches(batch_size=8)
→ replace_failed_batches_with_zero
→ summarize
→ summary_fallback
→ calculate_local_overall_score
```

最终总分继续由本地逐题平均计算，不能采用模型返回的 overallScore。

#### G3. 知识库题目生成图

节点：

```text
validate_task
→ multi_query_retrieve
→ build_context
→ structured_generate
→ validate_and_dedupe
→ revalidate_task
→ transactional_replace
```

提交前必须重新检查 taskId。

#### G4. RAG 图

节点：

```text
normalize
→ rewrite
→ retrieve_rewritten
→ retrieve_original_fallback
→ answer_or_no_hit
→ stream_and_persist
```

#### G5. 语音单轮图

节点：

```text
load_session
→ optional_context_compression
→ build_prompt
→ stream_llm_and_tools
→ normalize_and_truncate
→ persist_turn
```

ASR、TTS、WebSocket 生命周期和音频块不放入 LangGraph。

#### 简单 LLM 调用

以下调用直接使用统一 Adapter：

- 简历分析。
- JD 解析。
- 面试邀约规则失败后的 AI 解析。
- RAG 查询改写节点内部调用。
- 语音上下文摘要节点内部调用。
- Provider 连通性测试。
- Embedding。

完成门禁：

- 每个图的节点顺序、并行、分支、异常和降级均有状态转换测试。
- LangGraph 不新增当前不存在的业务重试和持久化副作用。

### 阶段 H：按风险顺序迁移业务模块

每个模块均执行“实现 → 单元测试 → 集成测试 → Java/Python 契约对比 → 前端验证”，
通过后才能迁移下一个模块。

#### H1. 面试日程

- CRUD、状态更新、时间格式和定时过期。
- 规则解析优先、LLM fallback。
- PATCH 和 PUT 状态更新均保留。

#### H2. Skill 与 LLM Provider

- Skill 列表、详情和 JD 解析。
- Provider、默认模型、Embedding、ASR/TTS 配置。
- 配置文件路径、掩码和连通性测试。

#### H3. 简历

- 上传、重复检测、解析、S3、Stream 分析。
- 状态机和重新分析。
- 列表、详情、删除和 PDF。
- 保留上传响应的多种联合结构。

#### H4. 知识库基础与向量化

- 上传、重复检测、分类、搜索、统计和下载。
- 分块和 Embedding 每批最多 10。
- 临时 metadata、旧向量删除和 promote 事务。
- 保持维度 1024、COSINE 和 TopK/score 配置。

#### H5. RAG Chat

- 单次同步查询。
- 单次 SSE 查询。
- 会话创建、列表、详情、标题、置顶、知识库关联和删除。
- 用户消息预写、AI 占位、流完成和中断后的内容持久化。

#### H6. 文字面试

- requestId 幂等创建。
- Skill/JD/简历出题。
- 当前题、答案暂存、答案提交、完成和异步评估。
- 历史、未完成、详情、报告和 PDF。

#### H7. 知识库题库及专项面试

- 题目生成状态机和恢复。
- 题目 CRUD、状态、筛选和分类。
- 容量校验、ACTIVE 题抽取、追问硬约束。
- 复用文字面试和统一评估。

#### H8. 语音面试

- REST 会话、列表、暂停、恢复、结束、删除和评估。
- `/ws/voice-interview/{sessionId}`。
- 文本 JSON + Base64 音频，不改成二进制帧。
- welcome、asr_ready、asr_reconnecting、audio_complete 和 timeout action。
- ASR partial/final、手动 submit、AI 流式 text、完整或分句音频。
- AI 说话期间和结束后 800ms 丢弃音频。
- 4 分 30 秒 warning、5 分钟自动暂停。
- WebSocket close 时 IN_PROGRESS 自动完成并触发评估。
- pause 后关闭不自动完成，resume 后不重复开场。
- ASR 重连两次、TTS 连接/合成超时、并发 3 和完整文本兜底。

完成门禁：

- React 前端无需业务改动即可覆盖全部页面流程。
- 所有异步轮询状态和恢复行为一致。

### 阶段 I：全量兼容性验证

测试层次：

1. Python 单元测试。
2. PostgreSQL/pgvector、Redis、RustFS/MinIO 集成测试。
3. API 契约测试。
4. Java/Python golden-master 对比。
5. 前端现有 Node 测试、构建和 Playwright E2E。
6. LLM Mock、超时、无效 JSON、Provider 切换和 Embedding 维度测试。
7. Redis 崩溃、消费者崩溃、重复消息和恢复测试。
8. SSE 慢客户端和中断测试。
9. WebSocket 重连、暂停、超时、ASR/TTS 失败和顺序测试。
10. 性能基线，确保 API p95、错误率和语音首包延迟没有明显退化。

最终兼容矩阵必须达到：

- REST 路由、请求和响应差异为零。
- 数据库 schema 差异为零。
- Redis Stream 和状态机差异为零。
- Prompt 渲染和固定模型请求差异为零。
- SSE/WebSocket 协议差异为零。
- 前端全部测试和构建通过。

## 6. CI、容器与开发命令迁移

1. 新建纯 Python 多阶段 Dockerfile，不安装 JDK/JRE。
2. Compose 保持 `app:8080` 服务和现有环境变量。
3. 增加 Worker 和 Scheduler 服务，使用同一 Python 镜像。
4. 删除 Flyway；API/部署启动前执行 `alembic upgrade head`。
5. CI 后端步骤改为：
   - 安装 Python 3.13 和 uv。
   - `uv sync --frozen`。
   - Ruff。
   - mypy。
   - pytest。
   - PostgreSQL schema diff 和集成测试。
6. 前端 CI 命令保持不变。
7. 更新 README、AGENTS.md 和开发命令，但不改变功能说明。

## 7. Java 清理

仅在所有门禁通过后执行：

1. 删除 Java `app/src/main/java`、Java tests 和 Gradle 配置。
2. 删除 Spring Boot、Spring AI、Redisson、Tika、iText 和 DashScope Java 依赖。
3. 删除 Java Docker 镜像和 CI Java setup。
4. 删除 Flyway runtime 和历史脚本；保留 schema 对照文档或归档引用。
5. 检查最终镜像和 Compose，不允许包含 JDK、JRE、Java 命令或 JVM 服务。
6. 确认仓库只剩 Python 后端和现有 React 前端。

## 8. 关键风险与控制

### 文档解析差异

纯 Python/非 JVM 解析器可能改变 PDF/DOC 的文本顺序。必须以真实样本文本快照作为门禁，
不以“能够解析”为验收标准。

### Prompt 和结构化输出差异

LangChain 默认消息构造、Schema 和 retry 可能与 Spring AI 不同。所有调用必须经过统一
Adapter，禁止业务 Service 直接创建 ChatOpenAI。

### LangGraph 重复副作用

图恢复或节点重试可能重复保存消息、写向量或发送 TTS。迁移初期不启用额外持久
checkpointer；现有 DB 状态和 taskId 继续作为幂等来源。

### Redis Stream 语义漂移

不得用 Celery、RQ 或简单 pub/sub 替换 Redis Stream。需要直接实现并测试当前
at-least-once、reclaim、重投和 ACK 顺序。

### FastAPI 默认 HTTP 语义

FastAPI 默认使用 4xx/5xx，与当前 HTTP 200 + 业务码不同。必须通过全局异常层和验证异常
处理器显式覆盖。

### 数据库 ORM 默认差异

SQLAlchemy 不得自动把 enum、JSON、timezone 或 cascade 调整为更“现代”的设计；以当前
PostgreSQL schema 为唯一标准。

## 9. 完成定义

迁移完成必须同时满足：

1. React 前端不感知后端技术变化。
2. 所有现有功能和业务分支可用。
3. 所有 API、数据、异步、AI、SSE 和 WebSocket 契约测试通过。
4. PostgreSQL schema 与当前最终 Flyway schema 等价。
5. Prompt、Skill、模型参数、重试和降级一致。
6. 开发环境可通过新的 Python 命令和 Docker Compose 启动。
7. 最终应用、容器、CI 和运行环境不存在 Java/JVM。
8. 所有行为变化均为零；任何功能改进均留到迁移完成后的独立任务。

## 10. 执行 Todos

1. 冻结并自动化现有行为契约。
2. 建立 Python 工程、基础 API 和质量工具。
3. 使用 Alembic 重建等价 PostgreSQL/pgvector schema。
4. 迁移 Redis、限流、Stream、缓存和 Scheduler。
5. 迁移文件解析、S3 和 PDF。
6. 实现 Provider Registry、LLM Adapter 和结构化输出。
7. 实现五个 LangGraph 工作流。
8. 迁移面试日程、Skill 和 Provider 模块。
9. 迁移简历模块。
10. 迁移知识库、向量化和 RAG Chat。
11. 迁移文字面试和知识库专项面试。
12. 迁移语音面试。
13. 完成全量契约、故障和前端 E2E 验证。
14. 更新 CI、Docker、文档和开发命令。
15. 删除 Java、Gradle、Flyway 和全部 JVM 运行时。

## 11. 说明

当前未发现本项目正在运行的 Compose 服务，也未发现当前 Compose 对应的
`postgres_data`、`redis_data`、`rustfs_data` 数据卷，因此本计划按允许重建开发数据执行。
若实施前出现需要保留的数据，应暂停 schema 初始化和 Java 清理，先增加一次数据兼容检查。
