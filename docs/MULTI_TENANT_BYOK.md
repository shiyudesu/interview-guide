# 多租户账号与 BYOK

## 文档状态

多租户账号和用户自带 API Key（BYOK）的仓库实现已经完成。自助注册仍默认关闭，部署者必须在
目标服务器完成真实域名 HTTPS、证书续期、SMTP 到达率和双用户现场验收后再显式开放。

本文记录已经落地的架构决策、安全边界和迁移结果。环境变量以
[配置说明](CONFIGURATION.md) 为准，现场操作以 [运行与排障](OPERATIONS.md) 和
[GHCR 主动拉取部署](DEPLOYMENT.md) 为准；本文不复制易过期的变量清单、部署命令或测试数量。

## 目标和兼容边界

平台允许每个用户独立配置 OpenAI 兼容 Provider、API Key、聊天/Embedding 模型以及 ASR/TTS。
没有可用 Key 时，依赖模型的功能明确失败并引导用户前往设置页，不会回退到管理员、平台、
`legacy-owner` 或其他用户的 Provider。

多租户改造保持以下外部协议：

- REST 路径、HTTP 方法、参数、请求体、multipart 字段和下载响应头不变。
- `POST /api/interview/sessions/{sessionId}/turns` 继续使用
  `requestId + questionId + answer`。
- 成功响应直接返回业务 JSON；无响应体操作使用 HTTP 204。
- 错误使用标准 4xx/5xx 和 `code + detail`；SSE、WebSocket 保持各自协议。
- Redis Stream 名称、字段、消费组、Pending、reclaim、重试和 ACK 顺序不变。
- `vector(1024)`、Prompt、Skill、Tool、JSON Schema、显式重试和回退顺序不变。

业务接口的资源范围从全局改为当前登录用户。跨用户读取、修改、下载、关联或删除统一按资源不存在
处理，避免泄露目标是否存在。

## 认证和会话

- 用户、邮箱验证状态和密码摘要保存在 PostgreSQL；密码使用 Argon2id。
- Session 和一次性邮箱 Token 保存在 Redis，Session 同时受空闲和绝对过期时间限制。
- 浏览器只保存 `Secure + HttpOnly + SameSite=Lax` Session Cookie，不持久化 Session Token、
  CSRF Token 或 Provider API Key。
- 登录响应和 `/api/auth/me` 返回 CSRF Token；状态变更请求同时验证 Token 和同源 Origin。
- 退出、修改密码、用户禁用和管理员撤销会使相关 Session 失效。
- SSE 在开始流式响应前验证 Session 和资源；WebSocket 在接受连接前验证 Session、Origin 和
  资源所有权。

健康检查、认证配置、登录、注册、邮箱验证和密码重置入口按明确白名单公开，其余业务与 Provider
接口默认要求认证。管理员通过 CLI 创建，不通过公共注册接口绕过验证流程。

## 授权和数据所有权

授权由后端 Repository 查询强制执行，而不是依赖前端过滤。Service 显式传递当前用户作用域，
Repository 把 `user_id` 或已验证的根资源主键写入数据库条件。

用户所有权覆盖以下聚合：

- 简历、面试日程、文字/知识库/语音面试会话及其报告
- 知识库、文档、分块、题目和 RAG 会话
- Provider、用户默认模型和语音配置
- 文件下载、SSE、WebSocket、异步任务和恢复任务

子资源可以通过根资源继承所有权，但跨聚合引用必须属于同一用户。例如面试引用的简历或知识库、
RAG 会话引用的知识库、语音会话关联的核心面试会话都需要在写入前验证所有者一致。

## Provider 和出站安全

每个用户拥有独立的 Provider alias、默认聊天/Embedding Provider 和 ASR/TTS 配置。同名 alias
可以同时存在于不同用户，进程内缓存也按用户与 Provider 版本隔离。Provider 修改后通过 Redis
版本通知使 API、Worker 和 Scheduler 清理对应缓存。

API Key 使用 AES-GCM 加密，并把用户和 Provider 身份纳入 AAD，避免密文被移动到另一条记录后
仍可解密。Compose 主密钥保存在共享 `provider_key` 卷；备份 PostgreSQL 时必须同时备份该卷。

Provider 模型发现分为两种互斥模式：

1. 已保存 Provider：Base URL 和 Key 都从当前用户的同一条记录读取。
2. 新 Provider 预览：调用者同时提供 Base URL 和 Key，不读取任何已保存 Key。

Provider 测试、模型发现和实际模型请求共用出站策略：默认只允许 HTTPS，拒绝凭据 URL、重定向、
回环、私网、链路本地、保留地址和云元数据地址，并同时校验 DNS 返回的 IPv4/IPv6。可信内网
Provider 只能由部署者通过明确 allowlist 放行，普通用户不能自行放宽。

## 文件、去重和对象存储

文件 hash 的唯一范围是用户，而不是全局：同一用户重复上传相同内容继续复用自己的资源，不同用户
上传相同字节时得到相互隔离的记录和对象。新对象 key 包含用户命名空间，下载必须先通过资源所有权
检查；迁移前对象 key 保持可读。

对象存储 Bucket 保持私有。浏览器通过受保护的下载接口访问文件和报告，不根据对象 key 直接读取
Bucket。删除一个用户的资源不能影响另一用户的同内容文件。

## 异步任务、幂等和调度

四组 Redis Stream 的字段和消费时序保持兼容。Worker 收到资源 ID 后先从根资源解析所有者，再
取得该用户作用域的 Provider；缺失资源、禁用用户、不可用 Provider 或无效 Key 都写入明确失败
状态，不使用全局或 legacy Provider 兜底。

任务创建时固定 Provider 选择。用户后来修改默认 Provider 不会改变已经排队的任务；仍被未完成
任务引用的 Provider 不能直接删除。Scheduler 恢复任务时沿用资源所有者和已固定 Provider。

requestId 幂等锁、结果缓存和限流 key 包含用户或业务 scope，避免不同用户共享锁、结果或额度；
原有 TTL、数据库唯一约束结果和处理顺序保持不变。

## 迁移结果

Alembic 迁移创建不可登录且禁用的 `legacy-owner`，用于承接升级前无法推断真实用户的存量资源。
部署者创建首个管理员后，通过显式 CLI 把这些资源和兼容 Provider 认领给目标管理员。认领只更新
所有者，不删除业务数据；`legacy-owner` 继续保持禁用，不参与登录或 Provider 回退。

迁移同时完成用户所有权、用户级 Provider/默认设置、用户级文件唯一约束和新对象命名空间。注册
开放后不能回滚到忽略用户边界的旧版本；部署通道必须遵守多租户安全基线和向后兼容迁移要求。

## 前端边界

- 未登录访问受保护路由时跳转登录页，成功后返回原目标页面。
- HTTP 401 清理内存登录态；状态变更自动附加 CSRF Token。
- 设置页只展示当前用户的 Provider、默认模型和语音配置。
- 注册关闭时展示管理员创建账号提示，不提供可提交的注册表单。
- 账号页支持修改密码、撤销全部 Session 和退出。
- 邮箱验证和密码找回使用一次性 Token，前端不保存 Provider Key 或 Session Token。

## 开放注册门禁

仓库级双用户隔离、浏览器流程和隔离生产 Compose 门禁已经通过。正式把注册开关改为启用前，部署者
仍需在目标服务器完成：

1. 备案域名解析、真实 HTTPS、证书签发与续期验证。
2. Secure Cookie、同源代理、CSRF、SSE 和 WebSocket 的浏览器验证。
3. 真实 SMTP 的注册验证、密码重置、到达率和旧 Session 撤销验证。
4. 两个真实账号的资源、Provider、文件、异步任务和语音隔离复验。
5. PostgreSQL、对象存储和 `provider_key` 的备份恢复演练。

这些现场条件未满足时，`APP_AUTH_REGISTRATION_ENABLED` 必须保持关闭。具体配置和值只在
[配置说明](CONFIGURATION.md#账号与-session) 维护。

## 验证范围

持续验证覆盖认证和 Session、双用户资源隔离、同名 Provider 与 Key 隔离、用户级文件去重、
Worker/Scheduler 所有者解析、SSE/WebSocket、生产 Compose、前端浏览器流程和受保护真实模型
工作流。测试必须使用真实 PostgreSQL/pgvector、Redis 和 S3 兼容存储验证基础设施语义；真实
模型验收必须使用受保护 Key，不能用 fake 冒充。
