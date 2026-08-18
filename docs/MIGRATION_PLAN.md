# Java/Spring AI 到 Python/FastAPI/LangGraph 迁移实施计划

## 1. 迁移目标

当前后端使用 Java 25、Spring Boot 4.1、Spring AI 2.0、Spring Data JPA、
Redisson、Apache Tika、iText 和 DashScope Java SDK。

本次迁移只更换后端技术实现：

- Java 25 替换为 Python 3.13.13。
- Spring Boot WebMVC 替换为 FastAPI 和 Uvicorn。
- Spring Data JPA 替换为 SQLAlchemy 2.0 和 psycopg 3。
- Flyway 替换为 Alembic。
- Spring AI 替换为 LangGraph、langchain-openai 和项目统一 LLM Adapter。
- Redisson 替换为 redis-py asyncio。
- Apache Tika、iText 和 DashScope Java SDK 替换为不需要 JVM 的实现。

以下部分继续保留：

- PostgreSQL 和 pgvector。
- Redis、Redis Stream 和 Lua 限流脚本。
- RustFS/S3 兼容对象存储。
- React 前端。
- 现有 REST、SSE 和 WebSocket 对外协议。

最终运行环境中不能再包含 JDK、JRE、Java 命令、Gradle、Flyway 或其他 JVM 服务。

## 2. 迁移期间不能改变的内容

### 2.1 功能和接口

迁移前后必须保持一致：

- 页面功能、操作流程和业务规则。
- REST 路径、HTTP 方法、查询参数、路径参数和请求体字段。
- multipart 字段名、文件名、Content-Type 和上传大小限制。
- 响应字段、默认值、null、空数组、字段顺序和时间格式。
- HTTP 状态码、业务错误码和错误文案。
- SSE 的 event、data、换行、转义、结束和报错方式。
- WebSocket 消息类型、字段、发送顺序、超时、暂停、恢复和断开行为。

普通业务异常继续使用 HTTP 200 和统一 `Result`。文件下载、SSE、WebSocket 以及当前确实
返回 HTTP 4xx/5xx 的情况，按 Java 实际结果保留。

### 2.2 数据和异步处理

迁移前后必须保持一致：

- PostgreSQL 表、列、类型、默认值、约束、索引、扩展和状态变化。
- 数据库事务开始和提交的位置，以及程序中途失败后的可见数据状态。
- Redis key、TTL、缓存内容、Stream、Group、消息字段、重试次数和 ACK 顺序。
- requestId 幂等锁、数据库唯一索引和结果缓存。
- 定时任务的执行周期、首次延迟、重复执行方式和恢复条件。
- pgvector 维度 `1024` 和 COSINE 距离。

### 2.3 AI、文件和实时语音

迁移前后必须保持一致：

- Prompt、Skill、reference 文件和渲染结果。
- Provider 选择、模型、base URL、temperature、超时和重试次数。
- Tool、结构化输出 JSON Schema、JSON 修复和失败后的回退顺序。
- 文档类型判断、文本提取、清洗、字符上限和错误结果。
- 文件哈希、重复检测、对象存储 key、下载响应头和 PDF 可见内容。
- ASR、TTS、LLM、Base64 音频、字幕和控制消息的顺序。

### 2.4 不在迁移中顺手修复问题

发现现有问题时：

1. 写入本计划的“已知问题”部分。
2. 用测试保存当前结果。
3. Python 先保持相同结果。
4. 如果需要修复，迁移完成后再单独立项。

迁移任务不能以“Python 默认更合理”为理由改变当前行为。

## 3. 当前项目情况

本计划编写时，仓库包含：

- 197 个生产 Java 文件。
- 36 个 Java 测试文件，但其中部分语音测试被禁用或只是占位。
- 9 个 Controller。
- 14 个 Entity。
- 5 组 Redis Stream 任务。
- 17 个 StringTemplate Prompt。
- 10 个 Skill 目录和共享 reference 文件。
- React 18、TypeScript、Vite 和 pnpm 前端。

以上数字只用于说明当前规模。迁移开始后必须通过脚本重新生成实际清单，不能长期依赖这里
的手工统计。

### 3.1 当前实现的主要来源

迁移时按以下顺序确认现有行为：

1. 实际请求和响应样本。
2. Java Controller、Service、Repository 和配置代码。
3. Flyway SQL。
4. Redis Lua、Stream 常量和缓存实现。
5. 前端 API 调用和 TypeScript 类型。
6. Java 测试。
7. README 等说明文档。

如果文档与代码不一致，以实际运行结果和代码为准，并记录差异。

### 3.2 已确认的现有问题

以下问题必须先保留，不能在迁移中静默修复：

- 前端调用 `/api/resumes/statistics`，但后端没有对应接口。
- 简历健康接口使用 `Map.of`，`data.status` 和 `data.service` 的 JSON 字段顺序可能随 JVM 实例变化。
- 语音创建请求中的 `roleType` 当前被忽略。
- 语音 WebSocket URL 在部分前端代码中回退到 localhost。
- `audio_chunk.isLast` 当前始终为 false。
- 部分 Controller 没有启用 `@Valid`，请求对象上的校验注解实际不生效。
- 多个 Bean Validation 字段同时失败时，Java 返回的错误文案顺序可能随 JVM 实例变化。
- 部分请求使用原始 Map 和强制类型转换，错误输入可能落入通用 500 处理。
- 简历 AI 失败时返回零分结果，而不是把任务标记为失败。
- RAG Chat 客户端中途断开时，当前不会保存已经生成的部分内容。
- RAG 慢客户端当前没有明确的缓冲上限。
- 同一 RAG 会话并发发送可能出现消息顺序竞争。
- RAG 会话关联知识库使用 `HashSet`，ID、名称和详情数组在不同请求中的顺序可能变化。
- 语音 WebSocket 连接开始时没有先完整校验会话状态，再启动 ASR。
- 语音配置中的连接数量限制当前没有真正使用。
- 同一 sessionId 建立第二条语音连接时，当前进程内状态可能互相覆盖。
- 部分语音配置项写在 `application.yml` 中，但没有对应代码读取，当前实际无效。
- 部分语音单元测试和集成测试被禁用。
- 当前 Nginx 配置代理 `/api`，但没有完整覆盖 `/ws`。
- README、前端 Dockerfile 和 CI 使用的 Node 版本不一致。
- `.env.example` 与开发 Compose 的默认 PostgreSQL 密码不一致。

这些问题要进入固定测试样本或风险清单。任何行为修改都需要独立任务。

## 4. 已确定的目标技术方案

### 4.1 技术栈

| 当前实现 | Python 实现 |
| --- | --- |
| Java 25 | Python 3.13.13 |
| Gradle | uv + `pyproject.toml` + `uv.lock` |
| Spring Boot WebMVC | FastAPI + Uvicorn |
| Jackson | Pydantic v2 + 项目兼容转换代码 |
| Bean Validation | Pydantic 校验 + 每个接口的兼容处理 |
| Spring Data JPA | SQLAlchemy 2.0 AsyncEngine |
| PostgreSQL Driver | psycopg 3 async |
| Flyway | Alembic |
| Spring AI | LangGraph + langchain-openai + 统一 LLM Adapter |
| Reactor Flux | async generator + `StreamingResponse` |
| Spring WebSocket | FastAPI/Starlette WebSocket |
| Redisson | redis-py asyncio |
| Spring Scheduler | APScheduler 独立进程 |
| AWS S3 SDK | boto3 |
| Apache Tika PDF | pdfminer.six |
| Apache Tika DOCX | python-docx |
| Apache Tika DOC | LibreOffice headless |
| Apache Tika TXT/Markdown | 显式编码处理和现有清洗规则 |
| iText 8 | ReportLab |
| DashScope Java SDK | 项目封装 DashScope WebSocket 协议 |
| Micrometer | prometheus-client + OpenTelemetry |
| JUnit/Mockito/AssertJ | pytest + pytest-asyncio + pytest-mock |

### 4.2 已确定的运行方式

使用同一 Python 镜像启动四类程序：

1. **Migrate**
   - 只执行 `alembic upgrade head`。
   - 执行成功后 API、Worker 和 Scheduler 才能启动。
   - 多个应用进程不得同时执行数据库升级。

2. **API**
   - 提供 REST、SSE 和 WebSocket。
   - 迁移完成初期固定一个 Uvicorn worker。
   - 原因是语音连接和部分计时状态保存在进程内。
   - 多 worker 和横向扩容属于迁移后的独立改造。

3. **Worker**
   - 处理五类 Redis Stream。
   - 每类 Stream 内保持顺序处理。
   - 五类 Stream 可以同时运行。
   - 迁移期间固定 Worker 副本数，不能在未比较行为前提高并发。

4. **Scheduler**
   - 只执行数据库中的过期和恢复任务。
   - 只运行一个实例。
   - WebSocket 连接活动计时仍放在 API 进程，不能错误移动到 Scheduler。

### 4.3 异步和阻塞操作

- FastAPI 路由、SQLAlchemy、Redis 和外部 HTTP 使用异步接口。
- boto3、ReportLab、libmagic 和部分文档解析是阻塞操作，不能直接堵塞事件循环。
- S3 和 PDF 生成放入有数量限制的线程池。
- LibreOffice 通过受控子进程执行，并限制并发、执行时间、临时目录和输出大小。
- 文档解析需要单独的并发限制，避免大文件耗尽 API 线程。
- 所有后台任务在应用关闭时必须停止接收新任务，并在规定时间内完成或明确取消。

默认并发值必须写入配置，并通过压力测试确认后才能修改。

### 4.4 依赖和镜像版本

- Python 固定为 3.13.13，uv 固定为 0.11.14。
- Python 镜像中的 libmagic 固定为 5.44-3，LibreOffice 固定为 7.4.7-1+deb12u14。
- Python 小版本、uv、Python 包、Node、pnpm 和系统包全部固定版本。
- 前端统一使用 Node 24 和 `packageManager` 中声明的 pnpm 10.26.2。
- 容器基础镜像必须固定标签和 digest。
- 不允许在生产 Compose 中使用 `latest`。
- `uv.lock` 必须提交。
- CI 使用 `uv sync --frozen`。
- 生成 Python 依赖清单和容器软件清单，随发布结果保存。

## 5. 目标工程结构

迁移期间新增 `backend/`，保留 `app/` 作为 Java 行为参考。

```text
backend/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── alembic/
├── src/interview_guide/
│   ├── main.py
│   ├── worker.py
│   ├── scheduler.py
│   ├── common/
│   │   ├── api/
│   │   ├── ai/
│   │   ├── config/
│   │   ├── db/
│   │   ├── errors/
│   │   ├── evaluation/
│   │   ├── logging/
│   │   ├── redis/
│   │   └── result/
│   ├── infrastructure/
│   │   ├── document/
│   │   ├── export/
│   │   ├── storage/
│   │   └── mapping/
│   └── modules/
│       ├── interview/
│       ├── interview_schedule/
│       ├── knowledge_base/
│       ├── llm_provider/
│       ├── resume/
│       └── voice_interview/
├── resources/
│   ├── prompts/
│   ├── skills/
│   ├── scripts/
│   ├── fonts/
│   └── voice-interview-opening.yml
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── performance/

migration/
├── manifests/       接口、数据库、Redis、配置和资源清单
├── samples/         固定请求、响应、文件、SSE 和 WebSocket 样本
├── model-proxy/     转发真实模型请求、记录请求响应并支持故障测试
├── scripts/         启动、比较、故障测试和清理脚本
└── reports/         本地生成的差异报告，不提交大文件
```

全部检查通过后才能删除 Java `app/`。Docker Compose 中对外服务名继续使用 `app`，端口继续
使用 `8080`。

## 6. 迁移开始前必须整理的清单

### 6.1 接口清单

为每个 REST、SSE 和 WebSocket 接口记录：

- Java Controller 和方法。
- 前端调用位置。
- HTTP 方法和路径。
- 请求头、查询参数、路径参数、请求体和 multipart 字段。
- 正常响应。
- 业务错误。
- 缺少字段、null、空字符串、错误类型、超长值和非法枚举的结果。
- HTTP 状态、Content-Type、Content-Disposition 和其他响应头。
- 是否写数据库、Redis、S3 或发送 Stream。

接口清单必须由脚本扫描 Controller 后再人工检查，避免只靠手写。

### 6.2 校验和错误清单

FastAPI/Pydantic 默认行为不能直接代替 Spring 当前行为。

每个接口至少比较：

- 字段不存在。
- 字段为 null。
- 字符串为空或只有空格。
- 数字使用字符串传入。
- 小数传给整数。
- 数字溢出。
- 日期格式错误。
- 枚举大小写错误。
- JSON 语法错误。
- 多余字段。
- 缺少 query、path 或 multipart 参数。
- 上传不支持的 Content-Type。
- HTTP 方法错误。

需要保存：

- HTTP 状态。
- 原始响应体。
- 业务 code 和 message。
- 多个字段同时错误时的错误顺序。

当前没有启用 `@Valid` 的接口，Python 也不能因为使用 Pydantic 而自动增加更严格的校验。

### 6.3 数据库清单

从最终 Flyway SQL 和 PostgreSQL catalog 生成：

- extension。
- table。
- column。
- 数据类型和长度。
- null。
- 默认值表达式。
- identity 类型。
- sequence 和 owner。
- primary key。
- foreign key 和删除规则。
- check。
- unique constraint。
- unique index。
- 普通索引。
- 索引方法、opclass 和参数。
- comment。

必须明确：

- 使用 `hstore`、`uuid-ossp` 和 `vector` extension。
- 主键是 `BIGINT GENERATED BY DEFAULT AS IDENTITY`。
- `vector_store.embedding` 是 `vector(1024)`。
- `vector_store.metadata` 是 JSON。
- HNSW 使用 `vector_cosine_ops`。
- JSON 字符串业务字段继续使用 TEXT，不能统一改为 JSONB。
- 时间字段继续使用无时区 `TIMESTAMP(6)`。
- 状态继续使用 VARCHAR 和现有 CHECK，不自动改为 PostgreSQL enum。
- `request_id` 的唯一性按现有 unique index 复刻。
- 需要保留现有冗余索引和缺失的外键。

### 6.4 Redis 和定时任务清单

记录：

- 每个 key 的完整格式。
- key 中使用的类名、方法名、用户、IP 和业务 ID。
- value 格式。
- TTL 和刷新 TTL 的时机。
- Stream、Group、Consumer、消息字段和字段类型。
- `XGROUP CREATE` 的起始 ID。
- `XREADGROUP` 数量和 BLOCK 时间。
- Pending idle 时间和 `XAUTOCLAIM` 数量。
- 重试字段、重投、ACK 和最终失败顺序。
- 定时任务是按固定频率执行、上一次结束后延迟执行，还是首次等待后执行。
- 时区和允许同时运行的任务数量。

当前 requestId 幂等创建还必须记录：

- 锁 key `interview:create:{requestId}`。
- 结果 key `interview:create:result:{requestId}`。
- requestId 规则 `[A-Za-z0-9_-]{8,64}`。
- 等待锁 185 秒。
- 锁持有 600 秒。
- 结果缓存 1 天。
- 数据库唯一索引作为最后保护。

### 6.5 配置清单

每个配置项记录：

- 配置名和环境变量名。
- 类型。
- 默认值。
- 是否敏感。
- API、Worker、Scheduler 中谁会使用。
- 启动时读取还是运行时可修改。
- Java 代码是否真的读取。
- Python 对应位置。
- 修改后是否需要重启。

当前写在 YAML 但没有代码读取的语音配置，在 Python 中也必须保持无效，除非另开任务。

Provider 配置需要单独记录：

- 静态配置只在数据库为空时初始化。
- 初始化后数据库是唯一配置来源。
- API 修改 Provider 后，在事务提交完成后发送 Redis 配置变更通知。
- API、Worker 和 Scheduler 收到通知后清理本地客户端缓存。
- 每次任务开始时检查配置版本，防止进程错过通知后长期使用旧配置。

### 6.6 固定测试样本

必须保存：

- 每个接口的典型请求和响应。
- 每个业务错误和错误文案。
- 所有 Prompt 渲染结果。
- 发送给模型的 headers、path、model、temperature、messages、tools 和 JSON Schema。
- SSE 原始字节。
- WebSocket 完整消息记录。
- 数据库执行前后状态。
- Redis key、TTL、Stream 和 Pending 状态。
- S3 对象 key、metadata 和响应头。
- PDF、DOC、DOCX、RTF、TXT、Markdown、加密、损坏和超大文件。
- PDF 抽取文本和页面截图。

测试中固定：

- 当前时间。
- 时区。
- UUID。
- 随机数。
- AES-GCM nonce。
- 数据库初始 sequence。
- 使用的真实 Provider、模型名称、temperature 和其他模型参数。
- 音频发送时间。
- 故障发生位置。

Prompt 中随机生成的八位 UUID 分隔符必须通过测试注入固定值，不能用“比较时忽略整段
Prompt”的方式绕过。

### 6.7 真实模型使用规则

- 任何用于证明迁移完成、接口兼容、AI 效果、语音流程或性能的数据，都必须调用真实模型。
- LLM、Embedding、ASR 和 TTS 都不能在最终验收时偷偷替换为固定字符串、随机生成器或本地
  假服务。
- 可以在普通单元测试中使用明确命名的 stub/fake，测试不需要模型参与的分支和业务计算。
- 使用 stub/fake 的测试必须在测试名和报告中明确标记，并且不能算作真实模型验收结果。
- Java 和 Python 都通过同一个转发代理调用真实 Provider。代理只负责记录请求、响应、耗时
  和错误，不得修改正常模型结果。
- 需要测试超时、断线、429 或 5xx 时，代理可以主动制造网络故障，但报告必须明确标记这是
  故障测试，不得把它描述成真实模型返回。
- 每次真实模型测试保存 Provider、模型版本、请求参数、调用时间、requestId、响应和费用
  统计，敏感密钥必须脱敏。
- 真实模型输出存在波动，因此逐字符比较的是发给模型的请求；模型响应比较 JSON Schema、
  字段、类型、数量、分数范围、业务回退和保存结果，不强制比较自然语言文本逐字相同。

## 7. Java/Python 新旧对比环境

### 7.1 环境隔离

Java 和 Python 同时运行时：

- Java 使用测试端口 `18080`。
- Python 使用测试端口 `28080`。
- 使用两个独立 PostgreSQL 数据库。
- 使用两个独立 Redis 实例，保证 key 名不需要添加额外前缀。
- 使用两个独立 S3 bucket。
- Java 和 Python 通过同一个记录代理调用同一个真实 Provider 和真实模型。
- 使用同一份初始化数据和同一组请求。

不能让两套后端消费同一个 Stream、修改同一张表或写同一个 bucket。

### 7.2 对比内容

每次对比生成：

- REST 请求和响应差异。
- SSE 原始内容差异。
- WebSocket 消息顺序和字段差异。
- PostgreSQL schema 差异。
- 请求执行后的数据库数据差异。
- Redis key、value、TTL、Stream、Pending 和 ACK 差异。
- S3 对象 key、hash、metadata 和下载头差异。
- Prompt 和模型请求差异。
- 真实模型响应的结构、字段、数量、分数范围、回退结果和数据库保存结果。
- PDF 抽取文本、页数和页面截图差异。

### 7.3 允许替换的动态值

默认不允许忽略字段。确实无法固定时，只能对提前列出的字段做替换：

- 端口。
- 环境隔离使用的数据库名和 bucket 名。
- 明确标记为动态的 trace ID。

业务 ID、时间、UUID、对象 key、nonce 和消息顺序应优先通过测试注入固定下来，不应直接
忽略。

### 7.4 执行命令

迁移过程中需要实现以下命令：

```bash
./migration/scripts/start-comparison-env.sh
./migration/scripts/seed-comparison-data.sh
./migration/scripts/run-comparison.sh
./migration/scripts/run-failure-cases.sh
./migration/scripts/stop-comparison-env.sh
```

`run-comparison.sh` 必须使用非零退出码表示存在不允许的差异，并生成 JSON 和 HTML 报告。

## 8. Python 基础运行规则

### 8.1 API 和统一响应

实现与 Spring 相同的兼容入口：

- `/swagger-ui.html`
- `/v3/api-docs`
- `/actuator/health`
- `/actuator/info`
- `/actuator/metrics`
- `/actuator/prometheus`

不仅路径一致，返回字段、Content-Type、HTTP 状态和依赖异常时的结果也要比较。

统一响应继续使用：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

实现 Python 版：

- `Result`。
- `BusinessException`。
- `ErrorCode`。
- 全局异常处理。
- 请求校验异常转换。

### 8.2 JSON、时间和数字

需要单独实现兼容转换：

- API 字段输出 camelCase。
- 保留 null。
- 保留数组顺序。
- Long ID 输出 JSON number。
- 普通时间继续输出无时区字符串。
- `interviewTime` 保持秒级格式。
- 其他时间字段按 Java 当前是否带微秒分别保存。
- WebSocket 时间戳继续使用 epoch millisecond。
- `plannedDuration` 和 `actualDuration` 保持当前不同单位。
- 评分中的平均值、整数截断和未回答题目按零分处理保持一致。
- TEXT 中保存的 JSON 使用固定字段顺序、Unicode 处理和紧凑分隔符。
- 嵌套 JSON 字符串不能自动改成 JSON 对象。

Python 的 Unicode 字符数与 Java UTF-16 code unit 不完全相同。涉及字符上限时必须用兼容
方法计算。

### 8.3 配置加载

- 继续支持现有环境变量名。
- 本地 `.env` 只用于开发，不提交密钥。
- 配置通过 Pydantic Settings 集中读取。
- Service 中不能直接散落读取环境变量。
- 对无效配置、缺少配置和格式错误返回明确启动错误。
- API Key、数据库密码和 S3 密钥不能写日志。
- Provider API Key 加密必须复刻 AES-GCM、nonce、Base64、字符编码和 key 派生。

### 8.4 日志和监控

- 每个 HTTP 请求生成 requestId。
- requestId 写入 Stream 消息，并在 Worker 日志中继续使用。
- WebSocket 每条连接使用稳定 connectionId。
- 结构化日志记录模块、操作、业务 ID、耗时和结果。
- 关闭 Uvicorn 重复 access log；普通 HTTP 完成日志使用 DEBUG，慢请求或 4xx 使用 INFO，
  5xx 使用 WARNING，requestId 和 Prometheus 指标仍覆盖每个请求。
- OpenTelemetry 仅在启用且配置 `OTEL_EXPORTER_OTLP_ENDPOINT` 时挂载 instrumentation；
  未配置 exporter 时不得创建无法导出的 span。
- 不记录完整 API Key、Authorization、简历正文、Prompt 私密内容和 Base64 音频。
- 指标保留当前接口，并增加 API、Worker、Scheduler、LLM、Embedding、ASR、TTS、S3、
  文档解析和 Stream 指标。
- 指标标签不能直接使用 sessionId、requestId 或文件名，避免标签数量无限增长。

## 9. PostgreSQL 和事务迁移

SQLAlchemy 连接池默认固定为 10 个常驻连接、0 overflow，与 Java Hikari 默认并发上限一致；
允许通过 `APP_DATABASE_POOL_SIZE` 和 `APP_DATABASE_MAX_OVERFLOW` 显式覆盖。
连接借用不启用 SQLAlchemy `pool_pre_ping`，避免每次借用增加隐藏 SQL 和隐式重连；真实断线
按当前操作失败并进入已有恢复流程。

### 9.1 Alembic 初始版本

因为开发数据允许清空，创建一个等价的 Alembic 初始版本，不逐条移植旧 Flyway 历史。

初始版本必须：

- 创建全部 extension。
- 创建全部表、约束和索引。
- 使用原表名和列名。
- 使用原默认值表达式。
- 使用相同 identity 方式。
- 创建 pgvector HNSW 索引。
- 保留索引和约束名称。
- 保留数据库中实际存在的 seed 数据。

### 9.2 数据库结构比较

不能只比较 SQLAlchemy Model。

对两个空数据库查询 PostgreSQL 自带的结构信息，比较：

- extension。
- table、column 和顺序。
- 类型、长度、precision 和 scale。
- null 和 default。
- identity 和 sequence。
- primary key、foreign key、check 和 unique。
- index name、method、column、expression、opclass 和参数。
- comment。

任何未列入允许差异的项目都必须使测试失败。

### 9.3 事务和失败后的状态

为每个包含多个系统的操作画出实际顺序，例如：

```text
parse file
→ upload S3
→ insert database
→ send Redis Stream
```

每两个步骤之间模拟程序崩溃，记录：

- 数据库是否已经提交。
- S3 对象是否存在。
- Redis 消息是否已经发送。
- 重试后是否重复。
- 是否需要清理。
- 用户查询到什么状态。

重点覆盖：

- 简历上传和分析。
- 知识库上传和向量化。
- 题目生成。
- 文字面试创建和完成。
- 语音会话创建、完成和评估。
- RAG 消息保存。
- Provider 修改。

一般情况下，LLM、S3、文档解析和外部 HTTP 不能放在数据库事务内。但如果 Java 当前失败
顺序与此不同，必须先用测试保存实际结果，再决定 Python 如何在不改变外部结果的前提下
缩短事务。

继续保留：

- `SELECT ... FOR UPDATE`。
- 题库替换事务。
- 向量 promote 事务。
- 已经存在的 after-commit 发送行为。
- 当前确实会吞掉并继续执行的特定失败结果，但必须在代码和测试中明确标记。

## 10. Redis、异步任务和定时任务迁移

### 10.1 限流

- 原样复用 `rate_limit_single.lua`。
- 保留 GLOBAL、IP、User 三种维度。
- 保留 permit、窗口和错误码 8001。
- 保留 forwarded IP 的取值顺序。
- 保留 `:value`、`:permits` 等实际 key。
- 保留当前 key 中 Java 类名和方法名，不能自动换成 Python 函数名。
- 保留当前 TTL 为窗口两倍的行为。
- 保留可重复限流注解对应的多条规则执行顺序。

### 10.2 Redis Stream

使用 redis-py asyncio 直接实现：

- `XGROUP CREATE`
- `XREADGROUP`
- `XAUTOCLAIM`
- `XADD MAXLEN ~ 1000`
- `XACK`

保持：

- 五组 Stream、Group 和字段。
- 每批 10 条。
- BLOCK 1 秒。
- Pending idle 5 分钟。
- 每次 claim 10 条。
- `retryCount` 从 0 到 3，因此最多执行四次。
- 重投成功后才 ACK 原消息。
- 消息格式错误时 ACK 并丢弃。
- 实体已经删除时 ACK 并丢弃。
- 重投本身失败时保留原 Pending 状态。
- 消费者崩溃后使用相同 cursor 规则继续 reclaim。

不能使用 Celery、RQ、简单 pub/sub 或内存队列代替 Stream。

### 10.3 缓存

- 文字面试会话 TTL 24 小时。
- 语音会话 TTL 1 小时。
- requestId 创建结果 TTL 1 天。
- 保留当前 key namespace。
- 保留 `questionsJson` 等嵌套 JSON 字符串。
- 保留读改写导致 TTL 刷新的时机。
- 保留不同映射缓存当前不同的 TTL 刷新方式。
- 迁移时允许清空 Redisson 二进制缓存，因此 Python 使用明确 JSON 编码，不实现 Redisson
  二进制兼容。

### 10.4 定时任务

迁移以下数据库定时任务：

- 面试日程过期。
- 知识库题目生成恢复。
- 语音会话和评估恢复。

当前时间规则必须按下表保存并在 Python 中复刻：

| 任务 | 当前执行方式 | 当前时间条件 |
| --- | --- | --- |
| 面试日程过期 | 每小时检查一次 | 使用服务器本地时间 |
| 知识库题目恢复 | 上一次执行结束 60 秒后再次执行，首次等待 60 秒 | Pending 超过 2 分钟；Processing 超过 20 分钟 |
| 语音会话和评估恢复 | 每 60 秒检查一次 | 会话超过 2 小时；Pending 超过 3 分钟；Processing 超过 30 分钟 |

APScheduler 必须明确：

- 错过执行时间后是否补跑。
- 多次错过时是否合并成一次。
- 同一任务最多同时运行一个实例。
- 进程重启后第一次何时执行。

语音 4 分 30 秒提示、5 分钟暂停等连接内计时继续放在 API 进程。当前检查周期造成的时间
偏差必须用测试记录，不能假设提示会精确发生在某一毫秒。

## 11. 文件、对象存储和 PDF 迁移

### 11.1 文件校验

保持：

- 简历最大 10MB。
- 知识库最大 50MB。
- multipart 总限制 50MB。
- 当前扩展名和 MIME 白名单。

文件类型判断必须复刻当前特殊情况：

- 先用 libmagic 判断实际类型。
- 类型判断发生 I/O 错误时，回退到上传请求头的 Content-Type。
- 知识库允许 `.md`、`.markdown`、`.mdown` 的扩展名特例。
- 知识库当前接受 RTF。
- 简历当前存在 MIME 子字符串匹配行为。
- 请求头和实际文件类型不一致时，结果按固定样本比较。

### 11.2 文档解析

- PDF 正文使用 pdfminer.six，按位置排序。
- pypdf 只检查加密状态和页面信息。
- DOCX 使用 python-docx。
- DOC 通过 LibreOffice headless 转换后解析。
- TXT/Markdown 使用固定编码识别顺序。
- 不增加 OCR。
- 不提取嵌入文件。
- 不提取 PDF inline image。

当前 5MiB 是解析阶段清洗前的字符上限，超出时整体失败，不是截断。Python 需要按照 Java
UTF-16 code unit 方式计算边界。

逐条移植文本清洗：

- Unicode 类别删除。
- 空白和换行规则。
- 标点处理。
- 最大长度。
- 空文档结果。

### 11.3 S3/RustFS

- 使用 boto3 path-style。
- 保留 bucket 自动创建。
- 保留 SHA-256。
- 保留日期目录。
- 保留八位 UUID。
- 保留安全文件名和中文转拼音规则。
- 保留对象 URL 拼接。
- 上传时保存的 Content-Type 继续使用当前上传请求头值。
- 保留调用总超时 60 秒和单次尝试 20 秒。
- S3 `HEAD` 的任意异常当前都按对象不存在处理。
- 删除前 `HEAD` 异常时当前会跳过删除。
- Python 自动重试次数必须通过网络层测试与 Java 实际行为一致。

### 11.4 PDF

使用 ReportLab 和现有中文字体。

比较：

- 可见文字和顺序。
- 页数。
- 字体和字号。
- 粗体和斜体。
- 颜色。
- 页边距。
- 表格宽度和换行。
- 分页位置。
- Unicode `So/Cs` 删除位置。
- Content-Type。
- RFC 5987 文件名。

验收同时使用：

- PDF 抽取文本比较。
- 页面截图比较。
- 人工查看复杂样本。

不要求 PDF 二进制字节完全一致。

## 12. Provider、Prompt 和统一 LLM Adapter

### 12.1 Provider

Python `LlmProviderRegistry` 保持：

- 数据库为空时，从静态配置初始化一次。
- 初始化完成后，数据库是唯一配置来源。
- 聊天和 Embedding 默认 Provider 分开。
- base URL 自动补 `/v1`。
- 普通连接超时 10 秒。
- 普通读取超时 300 秒。
- temperature 缺省 0.2。
- Provider 连通性测试使用当前独立的 5 秒连接、10 秒读取限制。
- Provider 增删改查、掩码、默认切换、reload 和测试接口不变。

当前实际存在四类客户端配置，Python 也要分别保留：

1. 带 Tool 的普通聊天客户端。
2. 不带普通业务 Tool 的 plain 客户端。
3. 语音流式 Tool 客户端。
4. Embedding 客户端。

SafeGuard、Tool、memory 和 advisor 的启用情况按实际请求样本复制，不能按方法名称推测。

### 12.2 API Key 加密

复刻：

- AES-GCM。
- nonce 长度。
- Base64 格式。
- 字符编码。
- key 派生。
- 加密失败和解密失败的错误结果。
- API 返回时的掩码。

生产环境修改加密 key 前必须有明确迁移方法，否则已有 Provider 密钥无法解密。

### 12.3 自动重试

- Python SDK 和 HTTP 客户端的自动重试全部关闭。
- 通过模拟 408、409、429、5xx、连接断开和读取超时，记录 Java 实际请求次数。
- 如果 Java 底层 SDK 确实发生重试，在项目 Adapter 中明确实现相同次数和等待，不依赖库默认。
- 业务 Service 不得自行复制重试代码。

### 12.4 结构化输出

统一组件必须保留：

- attempts 最小为 1。
- 错误截断长度配置最小为 20。
- 每次调用都追加防注入说明。
- 是否启用 repair prompt。
- 上一次错误如何加入第二次请求。
- 是否启用 JSON Schema 校验。
- 只有关闭 Schema 校验时才执行的本地未转义引号修复。
- 错误截断。
- 指标。
- 最终 `BusinessException`。

所有分支都需要测试，不只测试“第二次成功”。

### 12.5 Prompt 和 Skill

- Prompt 内容不转换为新的模板语法。
- 继续保存原 `.st` 文件。
- 实现兼容 StringTemplate 的渲染器。
- 渲染结果逐字符比较。
- 随机分隔符在测试中固定。
- 保留 PromptSanitizer 正则。
- 保留 SafeGuard 词表和固定回复。
- 保留 Skill 排序。
- 保留 category 冲突时 first-wins。
- 保留路径校验和 fallback 顺序。
- 保留每个 reference 3,000 字符、生成 12,000 字符、评估 6,000 字符限制。

## 13. LangGraph 使用范围

LangGraph 只用于多步骤、分支、并行或回退流程。简单模型调用直接使用统一 Adapter。

### 13.1 面试出题

```text
resolve_skill
→ allocate_question_counts
→ start_resume_and_direction_generation
→ apply_current_asymmetric_fallback
→ merge_and_cap
```

必须保留当前不对称回退：

- 简历分支失败时，取消方向分支，并重新按方向生成全部题目。
- 方向分支失败时，只返回已经生成的简历题目。
- 当前分支没有额外业务超时，Python 不能自行增加后改变结果。

### 13.2 统一评估

当前批次必须顺序执行，不能并行：

```text
prepare_qa
→ evaluate_next_batch_sequentially
→ replace_failed_batch_with_zero
→ repeat_until_finished
→ summarize
→ summary_fallback
→ calculate_local_overall_score
```

保持：

- batch size 最小为 1。
- 默认每批 8 条。
- 失败批次用零分结果替代。
- 最终总分由本地逐题平均。
- 未回答题目按当前规则进入平均。
- Java `(int)` 截断方式。
- 分类统计顺序按当前实际输出样本。

### 13.3 知识库题目生成

```text
validate_task
→ multi_query_retrieve
→ build_context
→ structured_generate
→ validate_and_dedupe
→ revalidate_task
→ transactional_replace
```

写入前必须再次检查 taskId 和任务状态。

### 13.4 RAG

普通查询和 RAG Chat 分开实现。

普通查询：

```text
normalize
→ rewrite
→ retrieve_rewritten
→ retrieve_original_fallback
→ answer_or_no_hit
→ stream
```

RAG Chat：

```text
validate_session
→ persist_user_message
→ create_assistant_placeholder
→ run_rag_stream
→ persist_on_complete_or_error
```

保持当前行为：

- 普通 SSE 不保存聊天消息。
- RAG Chat 正常完成时保存完整内容。
- 报错时按当前回调保存。
- 客户端取消时不保存部分内容。
- 当前慢客户端缓冲和并发顺序问题先记录，不在迁移中悄悄改变外部结果。

### 13.5 语音单轮

```text
load_session
→ optional_context_compression
→ build_prompt
→ stream_llm_and_tools
→ normalize_and_truncate
→ persist_turn
```

ASR、TTS、WebSocket 生命周期、连接计时和音频块不放入 LangGraph。

### 13.6 简单调用

以下调用直接使用统一 Adapter：

- 简历分析。
- JD 解析。
- 面试邀约规则失败后的 AI 解析。
- RAG 查询改写节点内部调用。
- 语音上下文摘要节点内部调用。
- Provider 连通性测试。
- Embedding。

## 14. RAG、SSE 和 WebSocket

### 14.1 SSE

保存原始字节样本，覆盖：

- 正常多段输出。
- 多行 data。
- 换行和转义。
- 无命中。
- 业务错误以数据形式返回。
- 外部模型超时。
- 客户端取消。
- 慢客户端。
- 服务端生成完成但客户端尚未读完。

FastAPI 必须设置与 Java 一致的：

- Content-Type。
- charset。
- Cache-Control。
- Connection。
- 代理缓冲相关响应头。
- 完成时的最后分帧。

### 14.2 RAG 并发

固定测试：

- 同一会话同时发送两个请求。
- 两个请求同时读取当前最大 message order。
- 一个请求完成、另一个失败。
- 删除会话时仍有流式响应。

先保存 Java 当前结果。Python 不得因数据库锁或新排序方式改变正常场景的消息顺序。

### 14.3 WebSocket 基础限制

保持当前限制：

- WebSocket 容器消息上限 2MiB。
- 处理器单条输入上限 256KiB。
- 发送时间上限 10 秒。
- 发送缓冲区 512KiB。
- 当前发送失败会被记录后吞掉，不会继续向调用方抛出。
- 文本 JSON 加 Base64 音频。
- 不改为二进制帧。

连接建立、重复 sessionId、超大消息、发送超时和断开后的清理都要有测试。

## 15. 语音面试迁移

语音模块最后迁移，并先补齐禁用测试。

### 15.1 连接和会话

保持：

- `/ws/voice-interview/{sessionId}`。
- welcome。
- asr_ready。
- asr_reconnecting。
- audio_complete。
- timeout action。
- partial/final 字幕。
- 手动 submit。
- AI 流式 text。
- Base64 音频。

当前连接开始前没有完整校验会话并限制资源，配置中的连接数量限制也没有真正使用。这些属于
已知风险。迁移中先保存当前正常行为，不得一边迁移一边增加新鉴权或连接拒绝规则。

固定测试：

- sessionId 不存在。
- session 已完成。
- 同一 sessionId 两个连接。
- 连接建立后立即断开。
- ASR 尚未 ready 时发送音频。
- AI/TTS 处理中断开。
- pause 后断开。
- resume 后重连。

### 15.2 ASR

保持当前实际流程：

- ASR ready 每 10 秒检查一次。
- 初始失败后最多重启两次。
- ready 前音频等待约 1.2 秒后仍不可用则丢弃。
- append 失败时重启 ASR。
- 同一音频块最多进行 15 次、每次 80ms 的追加重试。
- ASR `onClose` 当前不会自行重连。
- partial 和 final 的字段及顺序。
- 手动 submit 才触发本轮回答。

不能只写“ASR 重试两次”。

### 15.3 TTS

保持：

- 连接超时可配置，最小 1 秒。
- SDK 等待语音合成完成的当前上限 30 秒。
- 外层单句超时最小 5 秒，默认 8 秒。
- 每个会话最多并发 3 条 TTS。
- 输出实际为 PCM 24kHz。
- `audio_chunk.isLast` 始终为 false。
- 至少一条音频成功后才发送 `audio_complete`。
- 完整文本 TTS fallback。

消息中报告的 format 和 sampleRate 与实际字节不一致时，也要先保存当前结果。

### 15.4 AI 说话期间的音频处理

- 从服务端开始执行 LLM/TTS 到流程结束期间丢弃用户音频。
- 流程结束后继续丢弃 800ms。
- 这个时间以服务端流程为准，不以浏览器实际播放结束为准。
- 开场白音频当前不一定设置同一 speaking 标志。

需要覆盖用户在开场白、AI 文本生成、TTS 合成、音频播放和 800ms 窗口内说话的情况。

### 15.5 超时和暂停

- 4 分 30 秒发送 warning。
- 5 分钟自动暂停。
- 当前检查任务按固定周期运行，因此允许值来自 Java 实际样本，不能假设毫秒级精确。
- IN_PROGRESS WebSocket 关闭时自动完成并触发评估。
- PAUSED 关闭时不自动完成。
- resume 后不重复开场。

### 15.6 取消和后台任务

当前 LLM 流没有独立超时，文本发送默认存在 180ms 和 12 字符节流。断开连接时，父流程
中断后部分 TTS 子任务可能继续运行。

迁移时必须测试：

- 断开发生在 LLM 流中。
- 断开发生在多个 TTS 子任务中。
- 发送缓冲区满。
- TTS 子任务超时。
- API 进程关闭。

如果要改进子任务取消，需要迁移完成后单独处理。

## 16. 业务模块迁移顺序

每个模块都执行：

```text
整理 Java 行为
→ 增加固定测试样本
→ 实现 Python
→ Python 单元测试
→ PostgreSQL/Redis/S3 集成测试
→ Java/Python 自动比较
→ 前端真实流程测试
→ 保存报告
```

### 16.1 面试日程

- CRUD。
- 时间解析和输出。
- 状态更新。
- PATCH 和 PUT。
- 规则解析优先。
- LLM fallback。
- 定时过期。

### 16.2 Skill 和 LLM Provider

- Skill 列表和详情。
- JD 解析。
- Provider CRUD。
- 默认聊天和 Embedding Provider。
- ASR/TTS 配置。
- API Key 加密和掩码。
- reload、跨进程更新和连通性测试。

### 16.3 简历

- `/api/resumes/health`。
- 上传、MIME、解析和重复检测。
- S3。
- Stream 分析。
- 状态机和重新分析。
- 列表、详情和删除。
- PDF。
- 上传响应的多种结构。
- AI 失败时零分结果。

### 16.4 知识库基础和向量化

- 上传、重复检测、分类、搜索、统计和下载。
- 文档清洗和分块。
- Embedding 每批最多 10 条。
- 临时 metadata。
- 旧向量删除。
- promote 事务。
- 维度 1024、COSINE、TopK 和 score。

### 16.5 RAG Chat

- 单次同步查询。
- 单次 SSE 查询。
- 常规无密钥比较只覆盖参数校验、缺失知识库、无模型分支和原始 SSE 分帧，不得将 fake
  结果标记为真实模型验收。
- 受保护真实模型任务记录 query rewrite、1024 维 Embedding、同步回答和 SSE 请求，
  并确认普通查询不写入 RAG 聊天消息。
- 会话创建、列表、详情、标题、置顶、知识库关联和删除。
- 用户消息预写。
- AI 占位消息。
- 正常完成、报错和取消。
- 慢客户端和并发发送。

### 16.6 文字面试

- requestId 幂等创建。
- Skill、JD 和简历出题。
- 当前题。
- 答案暂存。
- 答案提交。
- 完成和异步评估。
- 历史、未完成、详情、报告和 PDF。
- 常规无密钥比较使用明确标记的固定模型 stub，固定比较 CRUD、幂等、错误、数据库、Redis
  Stream 和 PDF 可见文本，不得将该结果标记为真实模型验收。
- 受保护真实模型任务必须记录出题、顺序分批评估和二次汇总请求，校验本地总分、保存结果、
  Provider、模型、参数、耗时、Token 和费用。

### 16.7 知识库题库和专项面试

- 题目生成状态机和恢复。
- 题目 CRUD、状态、筛选和分类。
- 容量校验。
- ACTIVE 题抽取。
- 追问数量硬约束。
- 文字面试和统一评估复用。
- 固定任务 ID、随机选择、API/数据库/Redis Stream 的 Java/Python 比较通过
  `run-knowledge-base-interview-comparison.sh` 执行；普通测试使用明确命名的 fake，
  受保护工作流使用真实 Embedding 和 LLM 并保存请求、耗时、Token 与费用记录。

### 16.8 语音面试

- REST 会话。
- 列表、暂停、恢复、结束、删除和评估。
- WebSocket 完整流程。
- ASR、TTS、LLM 和连接计时。
- 断开、恢复和失败状态。

## 17. 每个阶段必须使用的写法

每个阶段都要写清：

1. **开始条件**
   - 前一阶段哪些结果已经通过。

2. **修改内容**
   - 哪些目录、模块和配置会变化。

3. **必须保持的行为**
   - 对应清单编号和固定样本。

4. **执行命令**
   - 本地和 CI 使用的准确命令。

5. **通过标准**
   - 哪些测试必须通过。
   - 允许的差异是什么。
   - 性能允许变化多少。

6. **保存结果**
   - JSON、HTML、日志、截图和性能报告位置。

7. **失败恢复**
   - 回到哪个 Git 提交。
   - 使用哪套 Compose。
   - 是否需要清空测试数据库、Redis 和 bucket。

## 18. 实施阶段

### 阶段 0：纠正现状并固定决定

实施内容：

- 生成接口、数据库、Redis、配置、Prompt、Skill 和测试清单。
- 修正文档中与 Java 不一致的描述。
- 固定本计划中的技术方案。
- 为已知问题创建编号。
- 统一 Python、Node、pnpm、容器和系统包版本。

通过标准：

- 清单能够关联到具体代码和前端调用。
- 没有未决定的“或”方案。
- 所有已知问题都有固定样本或明确的补样任务。

### 阶段 1：建立新旧对比和 CI

实施内容：

- 建立 Java/Python 隔离环境。
- 建立真实模型转发和记录代理。
- 固定时间、UUID、随机数和 nonce。
- 生成 REST、SSE、WebSocket、数据库、Redis、S3 和 PDF 差异报告。
- CI 从这一阶段开始运行比较。
- 补齐前端当前没有进入 CI 的测试。
- Playwright 对真实 Python 后端执行，不只使用浏览器内 mock。
- 真实模型测试只在有受保护密钥的 main 分支或手动任务中运行。
- Fork PR 只能运行不需要密钥的测试，不能因此被标记为“完整迁移检查通过”。

通过标准：

- Java 对 Java 自比较时差异为零。
- 故意修改一个响应字段时比较脚本必须失败。
- 故意修改一个数据库索引时结构比较必须失败。
- Java 和 Python 都有调用真实 LLM、Embedding、ASR 和 TTS 的记录。
- CI 保存差异报告。

### 阶段 2：建立 Python 基础项目

实施内容：

- uv、pyproject、锁文件。
- FastAPI、Uvicorn 和生命周期。
- Result、异常和校验兼容。
- JSON、时间和数字兼容。
- 配置、日志、指标和 trace。
- Migrate、API、Worker 和 Scheduler 启动入口。
- Python 多阶段 Dockerfile。

通过标准：

- 健康检查、OpenAPI、CORS、multipart 和统一响应通过新旧比较。
- API 能优雅停止。
- 阻塞操作不会堵塞事件循环测试通过。
- 镜像中没有 Java。

### 阶段 3：迁移 PostgreSQL、Redis、文件和存储

实施内容：

- SQLAlchemy Model。
- Alembic 初始版本。
- PostgreSQL catalog 比较。
- Redis Stream、缓存、幂等和限流。
- Scheduler 数据库任务。
- 文件判断、解析、清洗、S3 和 PDF。

通过标准：

- 空数据库结构差异为零。
- 状态机、锁和唯一索引测试通过。
- Redis 重复消费、崩溃、reclaim 和最终失败测试通过。
- 所有固定文件样本通过。
- PDF 文字、页数、截图和响应头通过。

### 阶段 4：迁移 Provider 和 AI 公共能力

实施内容：

- Provider 初始化和数据库配置。
- 跨进程配置更新。
- 四类客户端。
- API Key 加密。
- Prompt 和 Skill。
- 结构化输出。
- 统一评估。
- LangGraph 公共流程。

通过标准：

- 调用同一个真实 Provider 时，Java 和 Python 发出的完整请求差异为零。
- 真实模型响应都满足相同 JSON Schema、字段约束和业务保存结果。
- 所有结构化输出分支通过。
- 顺序批处理和回退顺序一致。
- Provider 修改后 API 和 Worker 都使用新配置。

### 阶段 5：按模块逐个迁移

按第 16 节顺序迁移。

每完成一个模块：

- Java 模块继续保留。
- Python 模块完成接口、数据和异步比较。
- 前端真实流程通过。
- 保存模块报告。
- 不允许用“后面统一补测试”结束模块。

### 阶段 6：集中测试语音、流式和故障

实施内容：

- SSE 慢客户端和取消。
- RAG 并发。
- WebSocket 重连和重复连接。
- ASR/TTS/LLM 失败。
- Redis、数据库、S3 和进程崩溃。
- API、Worker 和 Scheduler 优雅停止。
- 前端 Playwright 全流程。

通过标准：

- 消息字段和顺序符合固定样本。
- 没有新增重复数据库记录和重复音频。
- 已知现有问题仍按登记结果表现。
- 所有故障后的数据库、Redis 和 S3 状态符合记录。

### 阶段 7：性能测试

性能测试必须调用真实 Provider，不能用假模型制造更好看的延迟。

为了区分应用性能和模型本身波动：

- Java 和 Python 使用同一个 Provider、模型和参数。
- 尽量在同一时间段交替执行。
- 每组场景至少重复 5 次，使用中位数比较。
- 同时记录应用内部耗时和 Provider 网络耗时。
- 报告真实调用次数、Token、音频时长和费用。
- 单独运行不调用模型的基础接口测试，但不能用它替代 AI 接口性能结果。

受保护的 `real-model.yml` 先通过
`./migration/scripts/run-performance-acceptance.sh` 交替运行至少五次 Java/Python
Provider 连通性请求，保存请求一致性、应用延迟、Provider 网络延迟、Token 和版本化价格估算。
这个报告只覆盖单并发 REST 真实模型场景，不能替代下列其余性能场景。
真实 Provider 延迟会在相邻 Java/Python 请求间波动，因此该场景以
`端到端耗时 - 同请求 Provider 网络耗时` 得到的应用开销执行阈值判断；端到端与 Provider
p95/p99 仍完整保存，但不将模型网络波动误判为应用回归。
手动 `performance.yml` 通过 `./migration/scripts/run-rest-performance-comparison.sh`
对固定、无模型的 Skill 详情接口执行 1、10、50 并发，检查 REST p95、p99、吞吐、错误率和
响应一致性；该结果只用于
区分应用基础开销，不能替代真实 Provider 场景。脚本在压测期间按完整进程树采样 RSS，保存
baseline、peak 和末段稳定中位数，并检查 Python 稳定内存不超过 Java 的 120%。

测试场景：

- REST 1、10、50 并发。
- SSE 1、10、20 个客户端，包括慢客户端。
- WebSocket 1、5、10 个并发会话。
- Worker 正常消息、重复消息和 Pending reclaim。
- 10MB 简历、50MB 知识库文件和 PDF 生成。

通过标准：

- REST p95 不超过 Java 基线的 110%，且绝对增加不超过 100ms。
- REST p99 不超过 Java 基线的 115%。
- 吞吐不低于 Java 基线的 90%。
- SSE 首包 p95 不超过 Java 基线的 110%，且绝对增加不超过 100ms。
- 语音文本首包 p95 不超过 Java 基线的 110%，且绝对增加不超过 150ms。
- 语音音频首包 p95 不超过 Java 基线的 110%，且绝对增加不超过 200ms。
- 稳定运行时内存不超过 Java 基线的 120%。
- 消息顺序错误、重复 ACK、丢失完成消息均为 0。
- 错误率不能高于 Java 基线。

如果 Java 基线本身不稳定，先重复测试并记录中位数和波动范围，不能直接放宽 Python 标准。

### 阶段 8：正式切换和 Java 清理

当前实施状态：

- 已创建并推送 `pre-python-switch` tag。
- 已归档 Java 运行镜像、脱敏配置和新旧对比报告。
- 已从空 comparison volumes 演练 Java 恢复。
- 已在真实 Flyway schema 上连续运行两次 Python Migrate：首次只写入 Alembic baseline，
  第二次无 DDL，随后 schema 比较零差异。
- 生产 Compose 已改为先运行 Migrate，再启动同一 Python 镜像的 API、Worker 和 Scheduler；
  服务名 `app` 和对外端口 `8080` 保持不变。
- 最终受保护真实模型验收固定使用本地生产配置：
  `qwen3.7-max`、`qwen3.7-text-embedding`（1024 维）、
  `qwen3-asr-flash-realtime` 和 `qwen3-tts-flash-realtime`。

正式切换前：

- 保存 `pre-python-switch` Git tag。
- 保存 Java 镜像、配置备份和新旧对比报告。
- 实际演练一次恢复 Java 版本。
- 确认 Python 数据库升级程序只运行一次。
- 确认 API、Worker 和 Scheduler 健康。
- 运行前端冒烟测试。

正式切换：

- Compose 服务名继续使用 `app`。
- 对外端口继续使用 `8080`。
- Worker 和 Scheduler 使用同一 Python 镜像。
- 先执行 Migrate，再启动其他程序。

连续两次完整 CI 和一次本地 Compose 全流程通过后，才允许：

- 删除 Java 生产代码和测试。
- 删除 Gradle。
- 删除 Flyway。
- 删除 Spring Boot、Spring AI、Redisson、Tika、iText 和 DashScope Java 依赖。
- 删除 Java Dockerfile 和 CI Java setup。
- 删除 JVM 运行说明。

删除后再次检查：

```bash
git grep -nEi 'java|jdk|jre|gradle|flyway|spring-ai|spring boot' \
  -- Dockerfile* docker-compose*.yml .github backend README.md
docker compose config
docker history <python-image>
```

保留：

- 固定测试样本。
- Java 最终行为报告。
- 数据库结构报告。
- 新旧差异报告。
- 恢复演练记录。

## 19. 测试命令

当前 Java 基线：

```bash
./gradlew :app:compileJava
./gradlew :app:test --no-daemon
```

阶段 0 清单：

```bash
./migration/scripts/generate-manifests.sh
./migration/scripts/check-manifests.sh
./migration/scripts/sync-flyway-schema.py
./migration/scripts/sync-java-resources.py
./migration/scripts/start-comparison-env.sh
./migration/scripts/start-model-proxy.sh
./migration/scripts/record-java-baseline.sh
./migration/scripts/capture-runtime-state.sh
./migration/scripts/run-comparison.sh
./migration/scripts/run-schema-comparison.sh
./migration/scripts/run-interview-schedule-comparison.sh
./migration/scripts/run-interview-skill-comparison.sh
./migration/scripts/run-llm-provider-comparison.sh
./migration/scripts/run-resume-foundation-comparison.sh
./migration/scripts/run-resume-upload-comparison.sh
./migration/scripts/run-voice-rest-comparison.sh
./migration/scripts/run-voice-websocket-comparison.sh
./migration/scripts/run-voice-evaluation-comparison.sh
./migration/scripts/run-knowledge-base-comparison.sh
./migration/scripts/run-rag-chat-comparison.sh
./migration/scripts/run-interview-comparison.sh
./migration/scripts/run-knowledge-base-interview-comparison.sh
./migration/scripts/run-rest-performance-comparison.sh
./migration/scripts/run-performance-acceptance.sh
./migration/scripts/run-failure-cases.sh
./migration/scripts/stop-model-proxy.sh
./migration/scripts/stop-comparison-env.sh
```

模型记录代理：

```bash
cd migration/model-proxy
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run interview-guide-model-proxy
```

Python：

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
docker build -f Dockerfile -t interview-guide-python ..
```

前端：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run test:interview-history
pnpm run test:question-generation
pnpm run test:interview-capacity
pnpm run test:interview-entry
pnpm run test:e2e
pnpm run build
```

基础设施：

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml down
```

新旧比较：

```bash
./migration/scripts/run-comparison.sh
./migration/scripts/run-failure-cases.sh
```

## 20. 完成标准

迁移完成必须同时满足：

1. React 前端不感知后端技术变化。
2. 所有现有页面流程可用。
3. REST 请求、响应、错误和响应头符合固定样本。
4. PostgreSQL 结构差异为零。
5. 数据库事务失败后的状态符合固定样本。
6. Redis key、TTL、Stream、Pending、重试和 ACK 符合固定样本。
7. Prompt、Skill、模型参数、Tool、Schema、重试和回退一致。
8. SSE 和 WebSocket 字段、分帧、顺序、取消和超时一致。
9. 文档文本、hash、对象 key、下载头和 PDF 可见结果一致。
10. 前端测试、Playwright 和构建通过。
11. 性能达到“阶段 7：性能测试”的标准。
12. Python Compose 可以从空环境完成数据库升级并启动。
13. 正式应用镜像、Compose、CI 和运行环境不存在 JVM。
14. Java 恢复演练和 Python 正式切换记录已经保存。
15. 所有行为变化都已被拒绝或通过独立需求批准，迁移任务本身没有夹带功能改造。

## 21. 执行清单

1. 生成当前接口、数据库、Redis、配置、资源和测试清单。
2. 补齐固定请求、响应、文件、SSE 和 WebSocket 样本。
3. 建立 Java/Python 隔离对比环境。
4. 将新旧比较接入 CI。
5. 建立 Python 项目和四类启动入口。
6. 实现统一响应、异常、校验、JSON、配置和日志。
7. 使用 Alembic 重建 PostgreSQL 结构。
8. 迁移 Redis、幂等、限流、Stream、缓存和 Scheduler。
9. 迁移文件判断、解析、S3 和 PDF。
10. 迁移 Provider、Prompt、Skill、结构化输出和统一评估。
11. 实现规定的 LangGraph 流程。
12. 按顺序迁移八个业务模块。
13. 完成流式、语音、故障和性能测试。
14. 更新 Docker、Compose、CI、README 和 AGENTS.md。
15. 演练 Java 恢复。
16. 正式切换 Python。
17. 删除 Java、Gradle、Flyway 和全部 JVM 运行时。
