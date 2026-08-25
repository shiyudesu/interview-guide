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

内置 Provider 只有百炼：

| Provider | Base URL | 默认聊天模型 | 默认向量模型 |
| --- | --- | --- | --- |
| 百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-max` | `qwen3.7-text-embedding` |

初始 API Key 为空，请在前端设置页录入。Kimi、DeepSeek、GLM、LM Studio 和其他 OpenAI
兼容服务均通过“新增 Provider”添加，不再由环境变量初始化。

设置页会自动调用 Provider 的 OpenAI 兼容模型列表接口。后端先请求
`{baseUrl}/models`；当 Base URL 没有版本后缀时，还会尝试 `{baseUrl}/v1/models`。
拉取结果写入 `llm:provider:models:*`，TTL 为 5 分钟；设置页的“刷新列表”会跳过缓存重新请求。

编辑已有 Provider 时使用数据库中加密保存的 API Key。新建 Provider 时，填写 Base URL 和
API Key 后即可自动拉取。API Key 只发送给本系统后端，不会由浏览器直接请求厂商接口。

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
```

- Session 保存在 Redis，浏览器只保存 `HttpOnly + Secure + SameSite=Lax` Cookie。
- 登录响应和 `/api/auth/me` 返回 CSRF Token；所有已登录状态变更请求必须发送
  `X-CSRF-Token`，并通过同源 Origin 校验。
- 密码使用 Argon2id 哈希，哈希操作进入受限线程池。
- 登录同时按客户端 IP 和不可逆邮箱摘要限流，日志和 Redis key 不保存邮箱明文。
- `APP_AUTH_ENABLED` 对已有未配置部署默认保持关闭，避免自动更新后无管理员可登录；新安装模板会
  显式设为 `true`。
- `APP_AUTH_REGISTRATION_ENABLED` 在业务资源和 Provider 完成多租户隔离前必须保持 `false`。
- `.env.http` 明确设置 `APP_AUTH_ENABLED=false`，临时公网 HTTP 不承载正式账号或 BYOK。

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
