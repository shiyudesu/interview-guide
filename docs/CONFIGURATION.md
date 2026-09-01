# 配置说明

## 配置文件

本地和 Compose 默认读取仓库根目录的 `.env`：

```bash
cp .env.example .env
```

`.env` 不应提交。`scripts/start.sh` 和 Windows 启动脚本会为留空的基础设施密码生成随机值；
手工运行 Compose 时必须先填写这些值。生产环境也可以直接注入同名环境变量。

无源码服务器部署读取 `/opt/interview-guide/.env`，模板位于 `deploy/.env.example`。除业务配置外，
它还包含：

```env
INTERVIEW_GUIDE_IMAGE_REGISTRY=ghcr.io
INTERVIEW_GUIDE_IMAGE_NAMESPACE=shiyudesu
INTERVIEW_GUIDE_IMAGE_TAG=main
INTERVIEW_GUIDE_UPDATE_CHANNEL=main
INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=docker.io
COMPOSE_PROJECT_NAME=interview-guide
```

主动更新时 `INTERVIEW_GUIDE_IMAGE_TAG` 会由已验证的 `sha-<commit>` 临时覆盖；当前和上一成功版本
记录在部署目录的 `state/` 中。完整流程见 [GHCR 主动拉取部署](DEPLOYMENT.md)。

NAT 高端口的临时 HTTP 验收实例使用单独的 `.env.http`：

```bash
./scripts/start-http.sh
```

脚本只在文件不存在时根据 `.env.http.example` 创建 `.env.http`，不会覆盖已有配置，并会为留空的
`POSTGRES_PASSWORD` 和 `APP_STORAGE_SECRET_KEY` 生成随机值。`.env.http` 已加入 `.gitignore`，
应继续作为服务器本地配置保存。

Compose 的宿主机绑定通过以下变量控制：

```env
FRONTEND_BIND_ADDRESS=127.0.0.1
DEV_INFRASTRUCTURE_BIND_ADDRESS=127.0.0.1
```

基础 Compose 的前端 HTTP 端口默认绑定 `127.0.0.1`。正式部署不把该端口暴露公网，而是启用
Caddy HTTPS profile，由 Caddy 发布 80/443。API、PostgreSQL、Redis 和 MinIO 不发布宿主机
端口。本地开发 Compose 的三组基础设施端口默认也只绑定回环地址。Compose 使用项目作用域自动
生成容器名和数据卷名，不再声明全局固定容器名。

正式 HTTPS 配置：

```env
COMPOSE_PROFILES=https
PUBLIC_DOMAIN=interview.example.com
ACME_EMAIL=admin@example.com
TLS_BIND_ADDRESS=0.0.0.0
TLS_HTTP_PORT=80
TLS_HTTPS_PORT=443
FRONTEND_BIND_ADDRESS=127.0.0.1
```

- `PUBLIC_DOMAIN` 只填写已备案并解析到服务器的域名，不包含协议、端口或路径。
- `ACME_EMAIL` 用于 Let's Encrypt 账号和证书通知。
- 公网 TCP 80 和 TCP 443 必须转发到对应宿主机端口。
- Caddy 的证书、ACME 账号和续期状态保存在 `caddy_data`、`caddy_config` Volume。
- 服务器已有共享宿主机 Caddy 时，部署安装器使用 `--external-caddy`。它会设置
  `EXTERNAL_CADDY=true`、清空 `COMPOSE_PROFILES`，让前端只监听 `127.0.0.1:18073`；宿主机
  Caddy 负责自动证书和反向代理，部署更新通过本机 443 继续验证真实 HTTPS。
  该模式不要求安装器提供 `--email`，因为宿主机 Caddy 已经独立管理 ACME 联系信息。
- `FRONTEND_PORT` 在 HTTPS 模式下只作为服务器本机诊断入口，不应建立公网转发。
- 生产环境不允许把 `TLS_HTTP_PORT` 改成无法由公网 80 到达的端口，也不允许把
  `TLS_HTTPS_PORT` 改成无法由公网 443 到达的端口；使用 NAT 时可以保持公网端口为 80/443，
  再转发到这里配置的宿主机端口。

## Docker Hub 镜像来源

Compose、后端 Dockerfile 和前端 Dockerfile 默认从 `docker.io` 拉取镜像。Docker Hub 在当前
网络不可达，且已经有可信的 Docker Hub pull-through cache 时，可以设置：

```env
INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=mirror.example.com
```

该值只填写 registry 主机名和可选路径，例如 `mirror.example.com/dockerhub`，不要包含
`http://` 或 `https://`。生产 Compose、本地开发 Compose、Python、Node 和 Nginx 基础镜像会
统一使用该来源；未设置时仍使用官方 `docker.io`。项目不会自动选择或写入第三方公共镜像站，
也不会修改宿主机 DNS、Docker daemon 或 Docker Desktop 设置。

所有生产和开发镜像使用多架构 manifest digest，而不是 amd64 单架构 digest。当前完整栈支持
`linux/amd64` 和 `linux/arm64`，Docker 会选择本机架构，不需要 `platform: linux/amd64`。

如果使用的是普通 HTTP/HTTPS 代理，应配置 Docker daemon 或 Docker Desktop，而不是把代理
地址填入该变量。具体排障方式见 [运行与排障](OPERATIONS.md#docker-hub-镜像拉取失败)。

## 零配置启动

AI Provider 不需要任何环境变量即可启动。首次运行时：

- 系统只创建百炼 Provider，默认模型为 `qwen3.7-max` 和
  `qwen3.7-text-embedding`，API Key 为空。
- API、Worker 和 Scheduler 会在共享的 `provider_key` Docker Volume 中自动生成并复用
  `/var/lib/interview-guide/provider-encryption.key`。
- 在前端设置页录入百炼 API Key 后，密钥使用该主密钥进行 AES-GCM 加密并保存到 PostgreSQL。

本地直接运行 Python 后端时，默认密钥文件位于
`~/.local/share/interview-guide/provider-encryption.key`。

直接运行 Python 后端且需要由外部密钥系统管理主密钥时，可以在首次录入 Provider Key 之前
设置可选覆盖：

```env
APP_AI_CONFIG_ENCRYPTION_KEY=replace_with_a_stable_random_secret
```

Compose 不读取该变量，始终使用独立 `provider_key` 卷，避免旧 `.env` 中的历史配置意外覆盖
自动密钥。直接运行后端时，设置该变量后不会创建或读取自动密钥文件。

主密钥或 `provider_key` 卷在首次保存 Provider 后不能随意更换，否则会报：

```text
解密 Provider API Key 失败，请检查加密主密钥或 provider_key 卷
```

恢复方式只有三种：恢复原 `provider_key` 卷、使用原环境变量主密钥重新启动，或清空无法解密的
Provider 配置后重新录入 API Key。应用不会静默忽略错误，也不会把解密失败伪装成空密钥。

可以生成一个随机值：

```bash
openssl rand -hex 32
```

## Provider 配置

### Provider 出站安全策略

Provider 测试、模型发现、聊天、Embedding 和语音配置默认只允许 HTTPS/WSS，且域名解析结果必须
全部是可公开路由地址。回环、私网、链路本地、保留、组播和云元数据地址默认拒绝；连接建立前会
重新解析并校验地址，HTTP SDK 环境代理也不会绕过该策略。

部署者确实需要连接可信内网 OpenAI 兼容服务时，必须同时登记主机和允许访问的 CIDR：

```env
APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS=lmstudio.internal
APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS=192.168.10.0/24
```

- 主机 allowlist 允许该主机使用 HTTP/WS，但不会单独放开任意私网地址。
- 网络 allowlist 决定实际允许连接的非公网 IP 段。
- 两项均由部署配置控制，设置页用户不能修改。
- 不要加入 `127.0.0.0/8`、`169.254.0.0/16` 或云元数据地址。
- 修改已有 Provider Base URL 或语音 WebSocket URL 时必须同时填写新 API Key，防止把已保存 Key
  发送到新地址。

每个用户的内置 Provider 只有百炼：

| Provider | Base URL | 默认聊天模型 | 默认向量模型 |
| --- | --- | --- | --- |
| 百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-max` | `qwen3.7-text-embedding` |

初始 API Key 为空，请在前端设置页录入。Kimi、DeepSeek、GLM、LM Studio 和其他 OpenAI
兼容服务均通过“新增 Provider”添加，不再由环境变量初始化。Provider 使用内部 UUID 作为数据库
主键，以 `(user_id, alias)` 唯一，因此不同用户可以拥有同名 Provider。

设置页会自动调用 Provider 的 OpenAI 兼容模型列表接口。后端先请求
`{baseUrl}/models`；当 Base URL 没有版本后缀时，还会尝试 `{baseUrl}/v1/models`。
拉取结果写入 `llm:provider:models:*`，TTL 为 5 分钟；设置页的“刷新列表”会跳过缓存重新请求。

编辑已有 Provider 时使用当前用户数据库中加密保存的 API Key。新建 Provider 时，填写 Base URL
和 API Key 后即可自动拉取。API Key 只发送给本系统后端，不会由浏览器直接请求厂商接口，也不会
回退到平台或其他用户配置。

并非所有 OpenAI 兼容 Provider 都实现模型列表接口。请求失败时，接口会明确返回警告并仅展示
当前已配置模型；模型输入框始终允许手工填写。模型列表只能说明账号可见的模型 ID，不能替代
权限、地区、余额和实际调用测试。

每个 Provider 保存一组当前模型配置：

- `model`：聊天模型
- `embeddingModel`：向量模型，可为空
- `embeddingDimensions`：向量维度，本项目固定使用 1024
- `supportsEmbedding`：是否允许作为默认 Embedding Provider
- `temperature`：可选

`qwen3.7-text-embedding` 是有效的 Embedding 模型。不要把聊天模型名填到
`embeddingModel`。

## OpenTrek 校园赛模式

OpenTrek 校园赛实例使用根目录 `.env.campus`，模板为 `.env.campus.example`。该文件包含比赛专用
OpenTrek 应用密钥，已被 Git 忽略，必须保持 `0600` 权限；不要把它复制到聊天、Issue、CI 日志或提交中。
校园实例与普通实例使用不同的 Compose 项目名和数据卷。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_COMPETITION_MODE` | `false` | 开启校园赛只读产品模式；校园模板固定为 `true` |
| `APP_OPENTREK_ENABLED` | `false` | 启用 OpenTrek 能力路由；比赛模式要求为 `true` |
| `APP_OPENTREK_RUNTIME_BASE_URL` | `http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway` | Agent/Kortex 运行时网关，只允许主机 `10.128.203.200` |
| `APP_OPENTREK_APP_KEY` | 空 | 比赛工作空间专用应用密钥，仅由后端读取 |
| `APP_OPENTREK_WORKSPACE_CODE` | 空 | 应用密钥所属工作空间编码 |
| `APP_OPENTREK_GENERAL_AGENT_CODE` | 空 | 简历分析、日程解析 Agent |
| `APP_OPENTREK_GENERAL_AGENT_VERSION` | 空 | General Agent 已发布版本 |
| `APP_OPENTREK_INTERVIEWER_AGENT_CODE` | 空 | JD、出题和动态追问 Agent |
| `APP_OPENTREK_INTERVIEWER_AGENT_VERSION` | 空 | Interviewer Agent 已发布版本 |
| `APP_OPENTREK_EVALUATOR_AGENT_CODE` | 空 | 评估和知识库出题 Agent |
| `APP_OPENTREK_EVALUATOR_AGENT_VERSION` | 空 | Evaluator Agent 已发布版本 |
| `APP_OPENTREK_RAG_AGENT_CODE` | 空 | Kortex 问答 Agent |
| `APP_OPENTREK_RAG_AGENT_VERSION` | 空 | RAG Agent 已发布版本 |
| `APP_OPENTREK_KB_MAPPINGS_JSON` | `[]` | 本地文件 SHA-256 到只读 Kortex `kbCode` 的映射 |
| `APP_OPENTREK_CONNECT_TIMEOUT_SECONDS` | `10` | OpenTrek TCP/连接池超时 |
| `APP_OPENTREK_READ_TIMEOUT_SECONDS` | `300` | Agent 和 Kortex 响应超时 |
| `APP_OPENTREK_KB_BATCH_SIZE` | `10` | Kortex combination retrieve 单批数量，最大 10 |
| `APP_OPENTREK_AGENT_LOCK_FILE` | 空 | 跨进程 Agent 调用门禁文件；校园模板位于共享 `provider_key` 卷 |
| `APP_OPENTREK_AGENT_MIN_INTERVAL_SECONDS` | `0` | 相邻 Agent 执行的最小间隔；校园模板为 1 秒 |

校园模板还设置 `INTERVIEW_GUIDE_BUILD_NETWORK=host`，仅让受信任源码的 Docker 构建步骤复用 Linux
宿主机网络，以降低学校代理或弱网络下 Python/npm 包下载失败率；普通和 CI 构建默认仍使用隔离的
`default` build network。该变量只影响镜像构建，不改变运行中容器的网络或公开端口。

校园模板将 `APP_INTERVIEW_TURN_DECISION_TIMEOUT_SECONDS` 提高到 `120`，并把
`APP_INTERVIEW_TURN_LEASE_SECONDS` 配套设为 `150`。OpenTrek 校内 Agent 的复杂结构化响应明显
慢于普通 OpenAI 兼容接口；租约必须长于决策超时，仍保持 Turn 只调用模型一次和原有确定性回退。
校园模板同时设置 `APP_AI_RAG_REWRITE_ENABLED=false`：Kortex 已直接处理原始问题，省去一次额外
Agent 调用；比赛模式也不向 RAG Agent 传递 OpenAI Tool 描述，因为检索已由受控 Kortex Facade
完成。标准模式继续使用原有查询改写和 Tool 顺序。

当前 OpenTrek Agent 对题库生成有两项实测限制：单次请求只能稳定生成 1 道题，且嵌套固定追问会
返回无规划结果。比赛模式因此逐题顺序调用并聚合结果，预生成题库的 `followUpCount` 固定为 0；
知识库面试过程中仍由统一 Turn 模型按回答动态追问。标准模式继续一次批量生成并支持固定追问。

当前工作空间在不同 Agent 或进程连续执行时还需要冷却。校园 Compose 将门禁文件放在所有后端
进程共享的 `provider_key` 卷中，以 `flock` 串行化 Agent 生命周期，并在释放前记录完成时间；下一
次执行至少间隔 1 秒。门禁不作用于 Kortex 检索，不占用数据库连接，也不新增 Redis key。直接在
主机运行 Python 且门禁路径不可写时会明确记录警告并退回进程内互斥。

映射格式为：

```dotenv
APP_OPENTREK_KB_MAPPINGS_JSON='[{"fileHash":"64位小写SHA-256","kbCode":"Kortex编码"}]'
```

General、Interviewer、Evaluator 和 RAG 四类能力固定路由到各自 Agent，前端请求中的
`llmProvider` 字段仍保留但不会改变实际出口。Interviewer/Evaluator 请求按 OpenTrek 的
`message.metadata.skillList` 协议在主问题生成和评估时绑定当前面试方向对应的已发布 Skill；13 个
岗位方向均已配置。Turn 决策继续使用仓库内已审核的 Skill reference 上下文，不向平台重复加载
Skill，避免当前 OpenTrek 在短决策任务上进入长时间规划。
平台不可用时明确失败，不回退用户
Provider 或其他生成模型；Turn 仍保留原有确定性动作回退。

校园模板还显式设置：

```dotenv
APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS=10.128.203.200
APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS=10.128.203.200/32
```

这是对固定校内平台的部署者级放行，不会放宽普通用户的 Provider 出站策略。OpenTrek Client 仍
禁用重定向、环境代理和隐式重试，并在连接前执行 DNS/IP 校验。

比赛模式强制开启账号认证、关闭自助注册，并在服务端禁止知识库上传、删除、分类修改、重新向量化
和语音接口；前端同时隐藏对应入口、Provider 设置和模型选择。普通 `.env` 未开启比赛模式时，现有
BYOK、知识库和语音行为保持不变。

平台资源通过 `interview-guide-provision-opentrek` 幂等配置。命令会创建应用密钥、四个 Agent、
发布版本、打包并扫描 13 个 Skill，以及创建文档 Kortex 知识库。当前校内平台创建文档知识库时，
除 `text-embedding-v4` 外还要求文档解析 `visualModel`；命令自动发现 `qwen-vl-plus`，并为文本
Embedding 选择 1024 维。管理 Cookie 与应用密钥分开使用，应用密钥立即原子写入
`.env.campus`，不会输出到终端。

Provisioning 当前目标版本为 `competition-v12`，General、Interviewer、Evaluator、RAG 均使用
`glm-5.1`。真实 Agent 规划探针中 `glm-5.1` 和 `kimi-k2.6` 均为 5/5 成功；用户指定的
`deepseek-v4-pro` 在多组思考、token 和温度配置下仍随机返回“无规划任务结果”，最好仅 2/3，正式
配置为 1/5，因此 provisioning 明确拒绝将其发布到当前 OpenTrek Agent 模板。目标工作空间必须
唯一发现目标模型后才能创建并发布新版本。Provisioning 的
`--agent-model` 仅用于诊断时显式覆盖全部能力，正常部署使用上述映射。非流式 OpenTrek 响应开启
`delta` 后可能把多个累计 JSON
快照串联在一个文本字段中，Client 会严格解析连续 JSON 并只保留最后一个完整快照。

## 账号与 Session

正式 Compose 通过以下配置启用账号底座，注册默认关闭：

```env
APP_AUTH_ENABLED=true
APP_AUTH_REGISTRATION_ENABLED=false
APP_AUTH_COOKIE_SECURE=true
APP_AUTH_SESSION_IDLE_SECONDS=86400
APP_AUTH_SESSION_ABSOLUTE_SECONDS=604800
APP_AUTH_LOGIN_IP_LIMIT_PER_MINUTE=20
APP_AUTH_LOGIN_ACCOUNT_LIMIT_PER_MINUTE=8
APP_AUTH_REGISTRATION_IP_LIMIT_PER_HOUR=5
APP_AUTH_EMAIL_VERIFICATION_REQUIRED=true
APP_AUTH_PUBLIC_URL=https://interview.example.com
APP_AUTH_EMAIL_VERIFICATION_SECONDS=86400
APP_AUTH_PASSWORD_RESET_SECONDS=3600
APP_AUTH_EMAIL_REQUEST_LIMIT_PER_HOUR=5
APP_AUTH_SMTP_HOST=smtp.example.com
APP_AUTH_SMTP_PORT=587
APP_AUTH_SMTP_USERNAME=
APP_AUTH_SMTP_PASSWORD=
APP_AUTH_SMTP_STARTTLS=true
APP_AUTH_SMTP_SSL=false
APP_AUTH_SMTP_FROM_EMAIL=noreply@example.com
APP_AUTH_SMTP_TIMEOUT_SECONDS=10
```

- Session 保存在 Redis，浏览器只保存 `HttpOnly + Secure + SameSite=Lax` Cookie。
- 登录响应和 `/api/auth/me` 返回 CSRF Token；所有已登录状态变更请求必须发送
  `X-CSRF-Token`，并通过同源 Origin 校验。
- 密码使用 Argon2id 哈希，哈希操作进入受限线程池。
- 登录同时按客户端 IP 和不可逆邮箱摘要限流，日志和 Redis key 不保存邮箱明文。
- 注册用户先以 `PENDING` 状态创建，验证邮件 Token 只以 SHA-256 摘要保存在 Redis，默认 24 小时
  过期且只能使用一次；验证成功后才切换为 `ACTIVE`。
- 密码找回请求对存在和不存在的邮箱返回相同 204；重置 Token 默认 1 小时过期，成功后撤销该用户
  的全部 Session。邮件 Token、SMTP 密码和邮件正文不会写入应用日志。
- `APP_AUTH_SMTP_STARTTLS` 与 `APP_AUTH_SMTP_SSL` 只能启用一个。使用 465 端口时通常选择 SSL 并
  关闭 STARTTLS；使用 587 端口时通常使用 STARTTLS。
- 一旦把 `APP_AUTH_REGISTRATION_ENABLED` 改为 `true`，配置校验会强制要求认证、Secure Cookie、
  邮箱验证、HTTPS 的 `APP_AUTH_PUBLIC_URL`、SMTP 主机和发件邮箱全部有效，否则服务拒绝启动。
- `APP_AUTH_ENABLED` 对已有未配置部署默认保持关闭，避免自动更新后无管理员可登录；新安装模板会
  显式设为 `true`。
- `APP_AUTH_REGISTRATION_ENABLED` 默认保持 `false`；只有生产 HTTPS、SMTP 和双用户门禁全部通过后
  才能由部署者显式改为 `true`。
- `.env.http` 明确设置 `APP_AUTH_ENABLED=false`，临时公网 HTTP 不承载正式账号或 BYOK。

## 多租户文件和异步任务

- 简历和知识库只在同一用户内按 SHA-256 去重，数据库唯一约束为 `(user_id, file_hash)`。
- 新对象 key 使用 `users/{userId}/resumes/...` 和 `users/{userId}/knowledgebases/...`。
- S3 Bucket 保持私有，原文件和报告必须通过完成所有权校验的 API 下载。
- 旧对象不会在迁移时批量移动，数据库中已有 key 继续由原所有者通过 API 读取。
- 简历分析、知识库向量化、知识库出题和面试评估在任务创建时保存 Provider alias；Worker 根据
  资源所有者创建用户作用域 Provider Resolver，不读取平台或 legacy Key。
- Redis Stream 字段、Pending、XAUTOCLAIM、重试和 ACK 顺序保持不变，明文 API Key 不进入
  Stream、任务表或日志。

当前固定模型默认值和可配置语音默认值：

```env
APP_AI_EMBEDDING_DIMENSIONS=1024
APP_VOICE_ASR_MODEL=qwen3-asr-flash-realtime
APP_VOICE_TTS_MODEL=qwen3-tts-flash-realtime
```

## 语音配置

ASR 和 TTS 可在设置页选择已配置的 Provider，并修改模型、WebSocket URL、音色和采样参数。
配置保存在 PostgreSQL 的 `voice_model_config` 表中，API Key 复用 Provider 表中的 AES-GCM
密文，不会写入本地 JSON 文件。环境变量只用于首次初始化默认值。

常用变量：

```env
APP_VOICE_ASR_MODEL=qwen3-asr-flash-realtime
APP_VOICE_ASR_SAMPLE_RATE=16000
APP_VOICE_ASR_SILENCE_MS=2000
APP_VOICE_TTS_MODEL=qwen3-tts-flash-realtime
APP_VOICE_TTS_VOICE=Cherry
APP_VOICE_TTS_SAMPLE_RATE=24000
```

## PostgreSQL、Redis 和对象存储

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=interview_guide
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
APP_DATABASE_POOL_SIZE=10
APP_DATABASE_MAX_OVERFLOW=0

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

APP_STORAGE_ENDPOINT=http://localhost:9000
APP_STORAGE_ACCESS_KEY=interview-guide
APP_STORAGE_SECRET_KEY=
APP_STORAGE_BUCKET=interview-guide
APP_STORAGE_REGION=us-east-1
```

完整生产 Compose 使用 MinIO；`docker-compose.dev.yml` 使用 RustFS。两者都提供 S3 兼容
接口，默认 API 端口 9000、控制台端口 9001。

一键启动脚本会为留空密码生成随机值。手工运行生产 Compose 前必须显式填写两项密码；生产
Compose 对空值直接报错，不再回退到仓库内置弱密码。`docker-compose.dev.yml` 仍允许使用本地
开发默认值，但端口只绑定 `127.0.0.1`。

已有 PostgreSQL volume 不会因修改 `.env` 自动更新数据库用户密码。若密码发生变化，需要
在数据库中同步修改角色密码，或明确删除本地 volume 后重建。

## API 和前端

前端启动时先读取公开的 `GET /api/auth/config`。正式账号模式下随后调用 `/api/auth/me` 恢复
Session；未登录会跳转 `/login` 并在成功后返回原目标页面。浏览器只保存后端设置的 HttpOnly
Session Cookie，CSRF Token 仅保存在页面内存中并自动附加到 POST、PUT、PATCH 和 DELETE 请求，
不会写入 Local Storage、Session Storage 或 URL。收到 HTTP 401 后前端会清理内存登录态。

`/account` 提供密码修改和撤销全部 Session；两项操作成功后当前设备也会退出。`/verify-email`、
`/forgot-password` 和 `/reset-password` 分别承接邮箱验证与密码找回。注册关闭时 `/register` 只
显示管理员创建账号提示，不能提交注册表单。临时 HTTP 验收配置关闭认证时，前端根据
`/api/auth/config` 进入兼容的本地单用户界面，不显示可用的正式退出操作。

```env
SERVER_PORT=8080
FRONTEND_PORT=5173
FRONTEND_BIND_ADDRESS=127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
LOG_LEVEL=INFO
TZ=Asia/Shanghai
```

前端生产 Nginx 将 `/api/`、`/ws/`、`/docs` 和 `/openapi.json` 转发到同一 Compose 网络内的 API。通过同一个 HTTP 域名、
IP 和端口访问时属于同源请求，因此 NAT 的公网地址不需要写进 `CORS_ALLOWED_ORIGINS`。只有将
浏览器前端和 API 拆成不同 origin 时，才需要加入实际的外部 origin。

前端开发变量应放在 `frontend/.env.local`，也可以在命令前临时导出：

```env
VITE_API_PROXY_TARGET=http://localhost:8080
VITE_API_BASE_URL=
```

API 文档位于 `/docs`，OpenAPI 位于 `/openapi.json`，健康检查位于 `/health`。REST 成功响应
直接返回业务 JSON；错误使用标准 HTTP 状态码和 `code + detail` JSON。

## RAG 和面试

```env
APP_AI_RAG_REWRITE_ENABLED=true
APP_AI_RAG_SHORT_QUERY_LENGTH=4
APP_AI_RAG_TOPK_SHORT=20
APP_AI_RAG_TOPK_MEDIUM=12
APP_AI_RAG_TOPK_LONG=8
APP_AI_RAG_MIN_SCORE_SHORT=0.18
APP_AI_RAG_MIN_SCORE_DEFAULT=0.28
APP_AI_RAG_HISTORY_ENABLED=true
APP_AI_RAG_HISTORY_MAX_MESSAGES=10
APP_INTERVIEW_FOLLOW_UP_COUNT=1
APP_INTERVIEW_TURN_CONFIDENCE_THRESHOLD=0.65
APP_INTERVIEW_TURN_DECISION_TIMEOUT_SECONDS=20
APP_INTERVIEW_TURN_LEASE_SECONDS=30
APP_INTERVIEW_TURN_CONTEXT_MAX_CHARS=12000
APP_INTERVIEW_TURN_RECENT_COUNT=6
APP_VOICE_TURN_MIN_REMAINING_SECONDS=30
```

`APP_INTERVIEW_FOLLOW_UP_COUNT` 表示普通文字和语音面试每道主问题允许的动态追问上限。
会话创建时只生成主问题，追问在回答提交后动态决定。知识库专项面试使用创建请求中的
`followUpCount` 作为每道主问题的上限。

普通面试生成主问题后，会按题目 `type` 或分类名称匹配当前 Skill reference，并将最多 3000
个 Unicode 字符保存为题目 `source_context` 快照。动态追问和最终评估读取该快照，不会在面试
过程中访问外部题库；已经创建的会话不会因 reference 文件更新而改变。

Embedding 维度与 PostgreSQL `vector(1024)` 必须一致，不要只改环境变量而不修改 schema 和
相关测试。

## OpenTelemetry

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=interview-guide-api
OTEL_EXPORTER_OTLP_ENDPOINT=
```

未配置 OTLP endpoint 时不会向外部 Collector 发送数据。真实模型验收会显式关闭
OpenTelemetry。
