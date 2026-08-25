# 多租户账号与 BYOK 实施计划

## 文档状态

- 状态：设计草案，尚未实现。
- 目标：将当前单租户、自托管系统升级为用户使用自己 API Key 的多租户平台。
- 当前安全前提：生产环境尚未录入或暴露 Provider API Key，因此不需要执行历史 Key 轮换。
- 上线门禁：在双用户隔离、Provider 隔离、异步任务归属和文件访问测试全部通过前，生产环境不得
  开放用户注册。

当前实施状态：安全前置修复、账号/Session/CSRF、管理员 CLI、`legacy-owner` 回填，以及简历、
日程、面试、知识库、题库、RAG、语音 REST/SSE/WebSocket/下载的 Repository 级所有权校验已经
实现；用户级 Provider、文件 hash/对象 key 和异步任务 Provider 归属仍在后续阶段，注册继续关闭。

本文描述目标行为、数据迁移和交付顺序，不代表仓库当前已经具备账号或多租户能力。实施过程中
必须使用 Alembic 更新数据库，并在相同变更中同步更新 `AGENTS.md`、README、配置、运维、部署和
API 清单。

## 背景与问题

当前系统以单个全局用户运行：

- FastAPI 业务路由没有统一认证和授权依赖。
- Provider、默认聊天模型、默认 Embedding 模型以及 ASR/TTS 配置都是全局配置。
- `LlmProviderRegistry` 会把所有已启用 Provider 的 API Key 解密后放入全局进程内存字典。
- 简历、面试日程、面试会话、知识库和 RAG 会话没有统一的用户所有权。
- 语音会话虽然存在 `user_id`，创建时仍使用固定值 `default`。
- 简历和知识库按照全局 `file_hash` 去重，重复上传会直接复用已有记录。
- API、SSE、WebSocket 和文件下载均未形成统一的资源级授权边界。

这套行为适合受信任网络内的单用户自托管，不适合开放注册的公网平台。增加登录页面本身不能解决
跨用户读写、后台任务选错 Key、文件重复命中和 Provider 配置串用问题。

## 已确认的产品决策

### 用户自带 Key

平台采用 BYOK（Bring Your Own Key）模式：

- 每个用户独立配置 OpenAI 兼容 Provider、API Key、模型和语音参数。
- 用户没有可用 Key 时，依赖模型的功能必须明确失败并提示前往设置页配置。
- 生产请求不得静默回退到管理员、平台或其他用户的 Provider。
- 平台可以保留不含 Key 的 Provider 模板，例如百炼默认 Base URL 和推荐模型。
- 管理员可以管理用户状态和平台模板，但管理 API 不返回用户 API Key 明文。

### 兼容现有业务协议

多租户改造继续保持以下外部协议：

- 现有 REST 路径、HTTP 方法、请求参数、请求体、multipart 字段和下载响应头保持不变。
- `POST /api/interview/sessions/{sessionId}/turns` 继续使用
  `requestId + questionId + answer`。
- 成功响应继续直接返回业务 JSON；无响应体操作继续使用 HTTP 204。
- 错误继续使用标准 4xx/5xx，响应体为 `code + detail`。
- SSE 分帧、WebSocket JSON/Base64 音频、语音生命周期和面试 Turn 状态机保持不变。
- Redis Stream 名称、字段、消费组、Pending、XAUTOCLAIM、重试和 ACK 顺序保持不变。
- `vector(1024)`、Prompt、Skill、Tool、JSON Schema、显式重试和回退顺序保持不变。

现有业务接口的语义由“全局资源”变为“当前登录用户的资源”。例如：

- `GET /api/resumes` 只列出当前用户的简历。
- `GET /api/llm-provider/list` 只列出当前用户的 Provider。
- `GET /api/interview/sessions/{sessionId}` 只能读取当前用户的会话。
- 用户无法通过猜测 ID 读取、修改、下载或删除其他用户的数据。

### 必须调整的内部约束

当前 `AGENTS.md` 中“保持现有 PostgreSQL 表、字段、约束和索引”是当前单租户行为的保护规则。
真正的多租户需要一次明确、受 Alembic 管理的架构升级，至少包括用户所有权、用户级 Provider 和
用户级文件唯一约束。因此实施该计划时必须先批准并记录以下受控例外：

- 为聚合根增加 `user_id`、外键和查询索引。
- 将全局 `file_hash` 唯一约束调整为 `(user_id, file_hash)`。
- 将全局 Provider ID 调整为用户作用域别名。
- 将全局默认 Provider 和语音设置调整为每用户配置。
- 将只按 requestId 或资源 ID 构造的缓存、锁和限流标识调整为用户作用域，但保持业务幂等结果、
  TTL 和原有时序。
- 新文件的对象 key 加入用户命名空间；原有文件 key 通过迁移保持可读。

这些变化完成后，迁移后的多租户约束应成为新的不可变行为，重新写入 `AGENTS.md`。

## 安全前置修复

账号系统开发开始前，先消除 Provider 模型发现链路中的 Key 外带和 SSRF 风险。

当前模型发现请求允许同时提供已有 `providerId` 和新的 `baseUrl`。未显式提供 `apiKey` 时，服务
会解密已有 Provider 的 Key，再把它作为 Bearer Token 发送到请求中的 Base URL。多租户目标行为
必须改为两种互斥模式：

1. 已保存 Provider 模式：只接收 `providerId`，Base URL 和 Key 都从该用户的同一条 Provider
   记录读取。
2. 新 Provider 预览模式：调用者同时显式提供 `baseUrl` 和 `apiKey`，不得回退读取任何已保存
   Key。

出站 Provider 请求还必须执行以下校验：

- 默认仅允许 HTTPS。
- 禁止 URL 中包含用户名、密码和 fragment。
- 禁止回环、链路本地、私有、保留、组播和云元数据地址。
- DNS 解析得到任一禁止地址时拒绝请求，同时校验 IPv4 和 IPv6。
- 保持关闭重定向，避免通过 30x 跳转绕过目标校验。
- 连接前重新校验解析结果，避免只在字符串层面判断域名。
- 自托管环境需要访问可信内网 Provider 时，只能由部署者配置明确的主机或网段 allowlist，普通
  用户不能自行放宽策略。
- Provider 测试、模型发现和实际模型请求共用同一出站策略。

所有 `/api/llm-provider/**` 接口在实现用户级 Provider 后都要求登录；在此之前，生产入口应通过
外部访问控制或 Nginx 临时限制这些接口。

## HTTPS 传输前提

多租户账号、用户密码、Session、简历和 BYOK Key 只允许通过 HTTPS 传输。正式部署使用已经备案
并解析到服务器的域名，由 Caddy 作为唯一公网入口：

```text
公网 80/443
  -> Caddy（Let's Encrypt 自动签发、续期、80 跳转 443）
  -> frontend Nginx
  -> FastAPI
```

- 正式部署启用 Compose `https` profile，前端原始 HTTP 端口只绑定回环地址。
- Session Cookie 必须保持 `Secure`，不能为了兼容公网 HTTP 而降级。
- WebSocket 使用同源 `wss://`，SSE 和文件上传继续使用同源 HTTPS。
- 部署更新必须从应用网络内验证 `https://域名/health` 的证书和反向代理链路。
- `scripts/start-http.sh` 只保留给隔离验收，注册、登录和 Provider Key 录入不得在该模式开放。
- 在 HTTPS、邮箱验证、限流和双用户隔离门禁全部通过前，生产注册开关保持关闭。

## 目标架构

```text
Browser
  │ Secure HttpOnly session cookie + CSRF header
  ▼
FastAPI authentication dependency
  │
  ├─ Actor(userId, role, sessionId)
  │
  ├─ Route: 参数、Pydantic 校验、Service 调用、返回
  │
  ├─ Service: 业务编排并显式传递 Actor/UserScope
  │
  └─ Repository: 每次资源读写同时约束 resource id + user id
        │
        ├─ PostgreSQL: 用户、资源所有权、用户 Provider、用户设置
        ├─ Redis: Session、CSRF、限流、现有缓存和 Stream
        └─ S3: users/{userId}/... 对象命名空间

Worker / Scheduler
  │
  ├─ 从现有 Stream 或恢复查询得到资源 ID
  ├─ 从 PostgreSQL 解析资源所有者
  ├─ 读取该用户在任务创建时选定的 Provider
  └─ 仅在调用边界解密该用户的 Key
```

认证负责确认“是谁”，Repository 和 Service 的资源级授权负责确认“能操作什么”。前端路由保护只
用于用户体验，不作为授权边界。

## 账号与会话

### 用户模型

建议新增 `users`：

| 字段 | 说明 |
| --- | --- |
| `id` | UUID 主键，不使用自增 ID 作为对外用户标识 |
| `email` | 标准化邮箱，大小写无关唯一 |
| `display_name` | 可选展示名称 |
| `kind` | `HUMAN` 或仅用于迁移/内部任务的 `SYSTEM` |
| `role` | `USER` 或 `ADMIN` |
| `status` | `PENDING`、`ACTIVE`、`DISABLED` |
| `email_verified_at` | 邮箱验证时间，可空 |
| `created_at` / `updated_at` | UTC 时间 |

密码凭据单独保存在 `user_password_credentials`：

| 字段 | 说明 |
| --- | --- |
| `user_id` | 用户 UUID，主键和外键 |
| `password_hash` | Argon2id 哈希，不保存可逆密码 |
| `password_changed_at` | 密码变更和批量撤销 Session 使用 |
| `created_at` / `updated_at` | UTC 时间 |

`SYSTEM` 用户没有密码凭据，也不能创建 Session。初期只实现本地邮箱密码登录，但内部认证接口
不应把密码登录写死到业务 Service 中，为以后增加 OIDC 保留边界。

### Session

浏览器使用 Redis 服务端 Session，不把长期 JWT 放入 Local Storage：

- 登录成功后生成至少 256 bit 随机 Session Token。
- 浏览器只保存原始 Token；Redis key 使用 Token 的 SHA-256，日志不记录原始 Token。
- Cookie 名称固定，设置 `HttpOnly`、`Secure`、`SameSite=Lax` 和 `Path=/`。
- Session 保存 `userId`、角色、CSRF secret、创建时间、最后访问时间和绝对过期时间。
- 默认采用空闲 TTL 与绝对 TTL 双限制；续期不能突破绝对过期时间。
- 退出、密码修改、用户禁用和管理员撤销操作必须使相关 Session 失效。
- 登录接口同时按 IP 和标准化账号限流，错误信息不区分账号不存在与密码错误。

状态变更 REST 请求必须验证 CSRF Token 和同源 `Origin`。SSE 为只读 GET 时依赖 Session 和资源
授权；WebSocket 在握手阶段验证 Session、Origin 和资源所有权。

### 新增认证接口

建议新增：

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
POST /api/auth/password/change
POST /api/auth/sessions/revoke
```

开放注册前还需要邮箱验证和密码找回接口。第一阶段生产环境的注册开关默认：

```text
registrationEnabled=false
```

具体环境变量名在实现配置项时确定，并在同一变更中登记到 `.env.example` 和
`docs/CONFIGURATION.md`，计划文档不提前声明尚不存在的环境变量。

初始管理员通过镜像内的一次性 CLI 创建，命令从 TTY 读取密码，不在 shell 参数、Compose、`.env`
或日志中传递明文密码。启动脚本不得自动创建弱口令管理员。

## 授权策略

### 默认拒绝

应用采用默认拒绝：除明确列入公开清单的接口外，所有 API、SSE 和 WebSocket 都要求有效 Session。

公开接口建议仅包括：

```text
GET  /health
GET  /info
POST /api/auth/register    # 仅配置允许时
POST /api/auth/login
```

生产环境的 `/metrics` 只允许容器网络或监控网络访问。`/docs` 和 `/openapi.json` 默认仅管理员可见，
也可以由生产配置完全关闭。

### 状态码

- 未登录或 Session 失效：HTTP 401，响应体仍为 `code + detail`。
- 已登录但缺少管理员角色：HTTP 403。
- 访问不属于当前用户的资源：HTTP 404，避免泄露资源是否存在。
- CSRF、Origin 或 Session 校验失败不得伪装成成功。

### 代码边界

新增不可为空的请求上下文：

```python
@dataclass(frozen=True)
class Actor:
    user_id: UUID
    role: UserRole
    session_id: str
```

- FastAPI Dependency 解析 Session 并构造 `Actor`。
- Route 只接收 Actor、参数和请求体，然后调用 Service。
- Service 显式接收 Actor 或 `UserScope`，不能读取全局“当前用户”。
- Repository 查询必须把 `user_id` 写入 SQL 条件，不能先按 ID 读取后再由前端过滤。
- Worker 使用独立的内部任务上下文，不伪造管理员 Actor，也不能绕过所有权解析直接选择全局 Key。

## 多租户数据模型

### 聚合根所有权

为以下聚合根增加 `user_id UUID NOT NULL REFERENCES users(id)`：

| 聚合根 | 子资源如何继承所有权 |
| --- | --- |
| `interview_schedule` | 日程自身 |
| `resumes` | `resume_analyses` 和关联面试通过 `resume_id` |
| `interview_sessions` | 问题、Turn、决策和评估通过会话外键 |
| `knowledge_bases` | 题目、切片和向量查询通过知识库 ID |
| `rag_chat_sessions` | 消息和会话知识库关联通过 RAG 会话 |
| `voice_interview_sessions` | 消息通过语音会话；同时校验核心面试会话属于相同用户 |

根资源至少增加以下索引：

```text
(user_id, created_at)
(user_id, id)
```

列表接口常用状态或排序字段应追加到用户前缀索引中，避免所有用户数据增长后出现全表扫描。子资源
通常不重复保存 `user_id`，但所有查询必须通过根资源 join 或已验证的根资源主键进入。

跨聚合引用必须保证所有者一致：

- 面试使用的 `resume_id` 和 `knowledge_base_id` 必须属于面试会话用户。
- RAG 会话关联的全部知识库必须属于 RAG 会话用户。
- 语音会话和核心面试会话必须属于同一用户。
- 知识库题目、重新向量化和专项面试入口必须先验证知识库所有权。
- `vector_store` 当前通过 metadata 关联知识库，向量查询必须先获得当前用户可访问的知识库 ID
  allowlist，并把它作为数据库过滤条件，禁止无租户条件的全局向量检索。

### Provider

建议新增 `user_llm_providers`，而不是直接把现有全局 Provider 主键继续作为用户可见 ID：

| 字段 | 说明 |
| --- | --- |
| `id` | 内部 UUID 主键 |
| `user_id` | Provider 所有者 |
| `alias` | 用户可见字符串 ID，例如 `dashscope` |
| `base_url` | 经过标准化和出站策略校验的地址 |
| `api_key_ciphertext` / `api_key_nonce` | AES-GCM 密文和随机 nonce |
| `encryption_version` | 加密格式和主密钥轮换版本 |
| `model` | 聊天模型 |
| `embedding_model` | Embedding 模型，可空 |
| `embedding_dimensions` | 保持 1024 维业务约束 |
| `supports_embedding` | 是否作为 Embedding Provider |
| `temperature` | 可选温度 |
| `enabled` | 是否可用 |
| `created_at` / `updated_at` | UTC 时间 |

约束：

```text
UNIQUE(user_id, alias)
```

现有接口中的 `providerId` 继续使用 alias。所有读取、更新、测试、删除和模型发现都以
`(actor.user_id, alias)` 定位记录，因此不同用户可以同时拥有名为 `dashscope` 的 Provider。

### 用户默认模型和语音设置

新增 `user_ai_settings`，每个用户一行：

- 默认聊天 Provider 内部 UUID。
- 默认 Embedding Provider 内部 UUID。
- 创建和更新时间。

新增 `user_voice_settings`，每个用户一行：

- ASR Provider 和现有 ASR 参数。
- TTS Provider 和现有 TTS 参数。
- 创建和更新时间。

设置引用的 Provider 必须属于相同用户。数据库外键保证记录存在，Service 负责保证所有者一致、
Provider 已启用以及 Embedding 能力符合要求。

新用户只获得不含 Key 的百炼模板提示，不自动创建可调用的 Provider，也不继承管理员设置。

### Provider 加密

Compose 继续使用共享 `provider_key` Volume 中的主密钥，但用户 Key 使用带上下文的 AES-GCM：

```text
AAD = encryptionVersion + userId + providerInternalId
```

要求：

- 每次保存使用新的 96 bit nonce。
- 密文、nonce 和版本保存在 PostgreSQL，主密钥只在受保护 Volume 或外部密钥系统中。
- API 响应只返回 `hasApiKey` 和固定掩码，不返回可用于恢复的片段。
- 不把明文 Key 写入 Redis、Stream、任务表、日志、异常或审计详情。
- 不在应用启动时解密全部用户 Key。
- 初始实现只缓存非敏感 Provider 元数据；每次模型调用前按需解密，调用结束后不保留跨请求引用。
- 后续主密钥轮换通过 `encryption_version` 分批重新加密，不能直接替换 Volume 后启动。

### 全局 Provider Registry 的替代

当前全局 `LlmProviderRegistry` 改造为用户级 Resolver：

```text
get_chat(user_id, provider_alias=None)
get_embedding(user_id, provider_alias=None)
get_voice(user_id, provider_alias)
```

Resolver 的职责：

1. 根据用户设置解析默认 alias 或显式 alias。
2. 使用 `(user_id, alias)` 查询 Provider。
3. 验证 enabled、模型能力和所有权。
4. 在调用边界解密 Key，返回统一 `ProviderConfig`。
5. 配置变更后只失效该用户或该 Provider 的缓存。

Redis 版本通知应使用内部 Provider UUID 或用户版本，不再因一个用户修改配置而全量加载所有用户
Provider。不得把用户 ID、邮箱或 Key 放入 Pub/Sub 消息正文；发送不可逆内部标识即可。

模型列表缓存使用内部 Provider UUID、配置版本和刷新标识构造，不再把 API Key 本身或其可关联
摘要作为缓存身份的一部分。

## 文件、去重和对象存储

### 用户级去重

当前简历和知识库的 `file_hash` 是全局唯一，并在重复时返回已有资源。多用户环境必须改为：

```text
UNIQUE(user_id, file_hash)
```

同一用户重复上传相同文件时继续保持当前去重体验。不同用户上传相同字节时必须创建彼此独立的
业务记录，不能返回另一用户的文件名、分析、分类、题目、存储 key 或访问计数。

跨用户共享底层对象或分析结果不纳入第一版，因为它会引入引用计数、删除语义、内容侧信道和数据
保留策略。第一版优先保证隔离正确性。

### 对象 key

新对象使用：

```text
users/{userId}/resumes/{generatedObjectName}
users/{userId}/knowledgebases/{generatedObjectName}
```

- 用户文件只能通过已授权 API 下载。
- S3 Bucket 保持私有，不依赖不可猜测 URL 作为访问控制。
- 下载前先按 `(user_id, resource_id)` 查询资源，再读取对象。
- 删除资源时只能删除数据库中属于该用户记录引用的对象 key。
- 旧对象 key 不在迁移时批量移动；旧记录继续引用原 key，新的所有权检查负责保护访问。

## 异步任务和调度

### 所有者解析

保持当前四组 Redis Stream、字段和处理顺序。Worker 收到资源 ID 后执行：

```text
resource id
  -> 查询根资源及 user_id
  -> 查询任务创建时选择的 Provider alias
  -> 按 user_id + alias 解析用户 Provider
  -> 调用模型
  -> 按现有事务、重试和 ACK 顺序保存结果
```

不得从 Stream 中携带明文 Key。已有 Stream 字段不足以固定 Provider 的任务，应在 XADD 前把任务
Provider 选择保存在 PostgreSQL 的资源或任务上下文中，Stream 继续只携带现有资源/任务标识。

### 任务 Provider 固定规则

- 面试创建时已选定 `llm_provider`，Worker 结合会话 `user_id` 解析用户 Provider。
- Turn 决策和面试评估使用会话所属用户及会话保存的 Provider。
- 简历分析在入队前保存分析任务使用的 Provider alias 和模型快照。
- 知识库向量化在入队前保存 Embedding Provider alias、模型和 1024 维配置快照。
- 知识库出题在任务创建事务中保存聊天 Provider alias 和模型快照。
- ASR/TTS 由语音会话所属用户的语音设置解析，并在会话开始时固定本次会话使用的配置。

用户在任务排队后修改默认 Provider，不改变已经创建任务的选择。用户删除仍被未完成任务引用的
Provider 时返回业务错误，或先显式取消相关任务；不得自动切换到其他 Provider。

### Scheduler

Scheduler 恢复任务时通过根资源重新获得 `user_id` 和已保存 Provider 选择。恢复、租约、重试、
失败状态和 ACK 顺序保持现有行为。用户被禁用后：

- 不再创建新的模型任务。
- 未开始任务标记为明确失败或暂停，不能改用平台 Key。
- 已经开始的单次 Provider 请求可以完成，但结果仍只能写回原用户资源。

## Redis、幂等和限流

### Session 和认证 Key

新增认证专用 Redis 命名空间，不复用业务缓存：

```text
auth:session:{tokenHash}
auth:user-sessions:{userId}
auth:login:ip:{ipHash}
auth:login:account:{accountHash}
```

具体 TTL 在实现时写入 `docs/CONFIGURATION.md`，并由测试锁定。

### 业务缓存和锁

多租户后，任何可能由用户控制或在不同用户间重复的标识都要包含用户作用域。例如创建幂等、
Provider 模型缓存、限流和临时上传状态使用不可逆用户 ID 或内部 UUID 作为组成部分。

保持以下业务语义：

- 同一用户、同一会话、同一 requestId、相同载荷返回原结果。
- 同一用户、同一会话、同一 requestId、不同载荷返回业务错误。
- 不同用户使用相同 requestId 不得互相命中锁、结果或唯一约束。
- 原有 TTL、Pending、reclaim、重试次数和 ACK 时序不因用户作用域改变。

### 限流

至少覆盖：

- 登录：IP + 标准化账号。
- 注册和邮件发送：IP + 邮箱。
- Provider 测试和模型发现：用户 + IP。
- 文件上传：用户 + IP，并限制并发和每日总量。
- AI 请求：用户 + Provider + 业务 scope。
- WebSocket：用户并发连接数和单会话消息速率。

用户使用自己的 API Key 不代表平台没有滥用成本；文件解析、LibreOffice、数据库、Redis、对象
存储、向量化和网络连接仍然消耗平台资源。

## 前端计划

### 认证状态

前端新增统一 Auth Provider：

1. 首次加载调用 `/api/auth/me`。
2. 未登录时跳转登录页，并保存原目标路径。
3. 登录成功后回到原目标路径。
4. 全局请求拦截器附加 CSRF Header。
5. 收到 401 时清理本地用户状态并跳转登录，不保存 Session Token。
6. 403、404 和业务错误继续展示后端 `detail`。

浏览器同源 Cookie 自动携带 Session；不得把 Session Token 或 API Key 写入 Local Storage、
Session Storage、URL、前端日志或错误上报。

### 页面

新增：

- 登录页。
- 注册页；注册关闭时显示明确提示。
- 当前账号与退出入口。
- 密码修改和 Session 撤销页。
- 用户级 Provider 与默认模型设置。
- 未配置 Key 时的阻断式引导。

现有设置页不再管理全局 Provider。每个用户只能看到自己的 Provider，编辑已有 Provider 时继续以
空 API Key 表示“保持原 Key 不变”。

### WebSocket 和 SSE

- WebSocket 使用同源 Secure Cookie，在 `accept` 前完成认证、Origin 和语音会话所有权验证。
- SSE 请求使用当前 Session；开始流式响应前完成知识库/RAG 会话所有权验证。
- Session 被撤销或用户禁用时，新连接立即拒绝；现有 WebSocket 通过连接注册表收到关闭通知。

## 数据迁移

### 迁移原则

- Alembic 是唯一 schema 升级入口。
- 迁移不得删除现有用户文件、面试、简历、知识库、Provider 配置或数据卷。
- 所有新列先允许回填，再收紧非空和唯一约束。
- 迁移脚本不读取或输出 Provider Key 明文。
- 大表索引和约束变更必须评估锁表时间。
- 在开放注册前完成至少一次生产备份和恢复演练。

### 存量所有者

为了让无人值守 Migrate 可以完成，第一阶段迁移创建一个不可登录、状态为 `DISABLED` 的
`legacy-owner` 内部账户，并把所有现有资源和全局 Provider 配置归属该账户。它没有密码、Session
或注册入口。

部署者随后运行一次性 CLI：

```text
interview-guide-create-admin
interview-guide-claim-legacy-data
```

第一条命令通过 TTY 创建管理员，第二条命令在事务中把 `legacy-owner` 的全部资源、Provider 和
设置转移给指定管理员。转移完成并验证计数后，`legacy-owner` 保持禁用以保留审计关系，不作为
正常用户显示。

### Provider 迁移

1. 创建用户级 Provider 和用户设置表。
2. 把现有全局 Provider 复制到 `legacy-owner`，保留 alias、Base URL、模型和现有密文。
3. 旧密文第一次被管理员使用或保存时，解密后按带 AAD 的新格式重新加密。
4. 全部进程切换到用户级 Resolver 后，旧全局表进入只读兼容期。
5. 在后续独立迁移中确认无读取者后再移除旧表；不得在同一次高风险发布中立即删除。

当前尚未录入 Key，因此生产迁移预期不需要处理有效密文，但迁移代码仍必须覆盖已有 Key 的自托管
实例，不能假设所有部署都为空。

### 文件 hash 迁移

1. 给简历和知识库增加 `user_id` 并回填 `legacy-owner`。
2. 增加 `(user_id, file_hash)` 唯一约束。
3. 删除旧的全局 `file_hash` 唯一约束。
4. Repository 同时按用户和 hash 查询。
5. 保留原始 SHA-256 算法、文件识别、清洗和内容语义。

### 分阶段兼容

建议使用扩展—迁移—收紧顺序：

1. Expand：新增表、可空列和兼容读取。
2. Backfill：创建 `legacy-owner` 并回填全部现有记录。
3. Switch：API、Worker、Scheduler 和前端切换到用户作用域。
4. Constrain：增加非空、外键、联合唯一约束和最终索引。
5. Cleanup：在后续版本删除旧全局 Provider 读取路径和过渡代码。

## 部署和回滚

### 发布顺序

1. 保持外部访问控制或维护模式，注册关闭。
2. 备份 PostgreSQL、对象存储和 `provider_key` Volume。
3. 发布包含 Expand/Backfill 迁移的兼容版本。
4. 创建管理员并认领存量数据。
5. 运行双用户隔离和生产 Compose 验收。
6. 发布 Constrain 迁移和完整用户级 Provider Resolver。
7. 验证 Caddy/Let's Encrypt HTTPS、邮件、限流和监控后再开放注册。

### 安全回滚下限

一旦开放注册并产生多个用户数据，不能回滚到不识别用户所有权的旧镜像，否则旧 API 会把不同
用户的数据重新视为全局数据。部署系统必须记录“最低安全 revision”：

- 注册开放前，可以在外部访问控制保持启用时回滚到兼容版本。
- 注册开放后，回滚脚本拒绝部署低于多租户安全基线的 backend/frontend bundle。
- schema 迁移失败时停止 API、Worker 和 Scheduler，不用旧镜像带病启动。
- 不使用 `down -v` 或删除数据卷作为回滚方式。

该限制需要同步更新 GHCR deployment bundle、服务器主动更新和回滚脚本。

## 测试计划

### 认证

- 正确登录、错误密码、禁用用户、未验证用户和注册关闭。
- Session 空闲过期、绝对过期、退出、密码修改和管理员撤销。
- Secure/HttpOnly/SameSite Cookie 属性。
- CSRF 缺失、错误 Token、跨站 Origin 和重复提交。
- 登录、注册、邮件和密码尝试限流。

### 双用户资源隔离

为用户 A 和用户 B 创建数据，逐一验证：

- 列表只返回自己的资源。
- 使用另一用户的数字 ID、UUID 或 sessionId 读取时返回 404。
- 更新、删除、下载、重新分析、重新向量化和导出均不能跨用户。
- RAG 会话不能关联另一用户的知识库。
- 知识库面试不能使用另一用户的题目或知识库。
- 语音会话、WebSocket 重连、消息历史和评估不能跨用户。
- 相同 requestId 在不同用户间不共享锁或结果。

### Provider 和 Key

- 两个用户都能创建 alias 为 `dashscope` 的 Provider。
- 用户 A 的每种模型调用只携带 A 的 Key，用户 B 同理。
- 管理员 API、列表、错误和日志都看不到明文 Key。
- 用户没有 Key 时明确失败，不回退到其他 Provider。
- 修改默认 Provider 只影响当前用户和之后创建的任务。
- 排队任务使用创建时固定的 Provider，不因后来修改默认值而改变。
- 删除被未完成任务引用的 Provider 被拒绝。
- 模型发现不能把保存的 Key 发送到请求覆盖的 Base URL。
- SSRF 测试覆盖回环、私网、链路本地、IPv6、DNS 多地址和重定向。

### 文件和存储

- 同一用户上传相同文件继续命中用户内去重。
- 不同用户上传相同文件得到独立资源，不返回对方分析或对象 key。
- 下载必须经过用户所有权检查。
- 删除一个用户的文件不影响另一用户的同内容文件。
- 旧对象 key 在迁移后仍可由所有者下载。

### Worker 和 Scheduler

- 四组 Stream 使用真实 Redis 验证 XGROUP、XREADGROUP、XAUTOCLAIM、XADD 和 XACK。
- 每组内部顺序、Pending、重试次数和失败后 ACK 顺序保持不变。
- Worker 通过根资源解析正确用户和 Provider。
- 用户禁用、Provider 删除、Key 无效和模型失败产生明确失败状态。
- Scheduler 恢复遗漏任务时不会切换用户或 Provider。

### 前端和真实模型

- Vitest 覆盖 Auth 状态、401、CSRF、Provider 用户作用域和无 Key 引导。
- Playwright 使用两个账号覆盖登录、退出、路由保护和跨用户 404。
- 生产 Compose `@real-backend` 用例覆盖真实 PostgreSQL、Redis、S3 和 Nginx Cookie 转发。
- `real-model.yml` 在受保护环境中使用测试用户自己的真实 Key，不能使用 fake 冒充。
- Windows Chrome 验证 Secure Context 下的语音 Cookie、WebSocket 和麦克风生命周期。

## 可观测性与审计

新增不含敏感值的安全事件和指标：

- 登录成功/失败、注册、退出、密码修改、Session 撤销。
- Provider 创建、更新、Key 替换、删除、测试和模型发现。
- 管理员禁用/启用用户。
- 授权拒绝、CSRF 拒绝、SSRF 拒绝和限流。
- 按业务 scope 统计模型调用成功、失败、耗时和 Provider 类型。

日志使用内部 user UUID 或不可逆短标识，不记录邮箱、Session Token、CSRF Token、API Key、简历
正文、面试回答和文件内容。审计详情记录操作类型、对象内部 ID、结果和 requestId，不记录密文。

## 分阶段交付

### 阶段 0：安全前置

交付：

- 修复模型发现保存 Key 与自定义 Base URL 混用。
- 增加统一 Provider 出站策略和 SSRF 测试。
- 注册保持关闭，Provider 接口在过渡期受外部访问控制保护。

门禁：任何保存 Key 都不能发送到用户覆盖地址。

### 阶段 1：认证骨架和兼容迁移

交付：

- `users`、Redis Session、登录/退出/当前用户、CSRF 和初始管理员 CLI。
- `legacy-owner` 回填迁移。
- FastAPI 默认认证依赖和公开路径清单。
- 前端登录页和 401 处理。

门禁：注册关闭时，只有管理员能进入现有系统，健康检查继续可用。

### 阶段 2：业务数据隔离

交付：

- 所有聚合根增加用户所有权。
- Repository、Service、REST、SSE、WebSocket 和下载全部按用户授权。
- 文件 hash 联合唯一约束和用户对象命名空间。

门禁：完整双用户资源越权矩阵通过。

### 阶段 3：用户级 BYOK

交付：

- 用户 Provider、默认模型和语音设置表。
- 带 AAD 的 Key 加密格式。
- 用户级 Provider Resolver 和精确缓存失效。
- 设置页改为用户作用域。

门禁：两个用户同名 Provider 使用各自 Key，且无平台 Key 回退。

### 阶段 4：Worker、Scheduler 和语音

交付：

- 四组 Stream 消费者通过资源所有者解析 Provider。
- 任务创建时固定 Provider 选择。
- Scheduler 恢复、ASR/TTS 和 WebSocket 使用正确用户设置。

门禁：真实 Redis 集成测试证明重试、Pending、reclaim 和 ACK 顺序未改变。

### 阶段 5：开放注册准备

交付：

- 邮箱验证、密码找回、注册/上传/AI/WS 限流。
- 安全审计、指标、告警和数据保留说明。
- GHCR 部署安全回滚下限。
- README、AGENTS、CONFIGURATION、OPERATIONS、DEPLOYMENT 和用户界面说明更新。

门禁：CI、生产 Compose、Playwright、真实模型工作流、备份恢复和安全回滚演练全部通过。

完成门禁后才将生产注册开关切换为 `true`。

## 完成定义

只有同时满足以下条件，才能认为多租户 BYOK 已完成：

- 未登录用户无法调用任何业务或 Provider 接口。
- 任意资源操作都验证当前用户所有权，跨用户请求稳定返回 404。
- 每个用户独立配置并使用自己的聊天、Embedding、ASR 和 TTS Key。
- 平台不存在管理员 Key 或其他用户 Key 的隐式回退。
- API Key 不出现在响应明文、日志、Redis、Stream、URL、前端存储或审计详情中。
- 文件去重、对象访问、RAG、面试、语音、Worker 和 Scheduler 都按用户隔离。
- 现有面试协议、Stream 顺序、模型行为、PDF 内容和错误响应格式保持兼容。
- 存量数据完整归属管理员，备份恢复和部署回滚策略经过验证。
- 注册开放前的全部测试门禁已经由 CI 和生产 Compose 验收锁定。
