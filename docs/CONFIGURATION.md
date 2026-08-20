# 配置说明

## 配置文件

本地和 Compose 默认读取仓库根目录的 `.env`：

```bash
cp .env.example .env
```

`.env` 不应提交。生产环境也可以直接注入同名环境变量。

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
POSTGRES_PASSWORD=password
APP_DATABASE_POOL_SIZE=10
APP_DATABASE_MAX_OVERFLOW=0

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

APP_STORAGE_ENDPOINT=http://localhost:9000
APP_STORAGE_ACCESS_KEY=minioadmin
APP_STORAGE_SECRET_KEY=minioadmin
APP_STORAGE_BUCKET=interview-guide
APP_STORAGE_REGION=us-east-1
```

完整生产 Compose 使用 MinIO；`docker-compose.dev.yml` 使用 RustFS。两者都提供 S3 兼容
接口，默认 API 端口 9000、控制台端口 9001。

示例密码只适合本地开发。对外部署前必须修改 PostgreSQL 和对象存储凭据。

已有 PostgreSQL volume 不会因修改 `.env` 自动更新数据库用户密码。若密码发生变化，需要
在数据库中同步修改角色密码，或明确删除本地 volume 后重建。

## API 和前端

```env
SERVER_PORT=8080
FRONTEND_PORT=5173
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
LOG_LEVEL=INFO
TZ=Asia/Shanghai
```

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
