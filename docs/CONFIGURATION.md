# 配置说明

## 配置文件

本地和 Compose 默认读取仓库根目录的 `.env`：

```bash
cp .env.example .env
```

`.env` 不应提交。生产环境也可以直接注入同名环境变量。

## 必填项

### Provider 加密密钥

```env
APP_AI_CONFIG_ENCRYPTION_KEY=replace_with_a_stable_random_secret
```

该值用于 AES-GCM 加密 PostgreSQL 中保存的 Provider API Key。API、Worker 和 Scheduler
必须使用同一个值。

首次保存 Provider 后不要轮换这个值。更换后，启动会报：

```text
解密 Provider API Key 失败，请检查 APP_AI_CONFIG_ENCRYPTION_KEY
```

恢复方式只有两种：使用原密钥重新启动，或清空无法解密的 Provider 配置后重新录入 API Key。
应用不会静默忽略错误，也不会把解密失败伪装成空密钥。

可以生成一个随机值：

```bash
openssl rand -hex 32
```

### 默认 DashScope Key

```env
AI_BAILIAN_API_KEY=your_dashscope_api_key
```

默认 LLM、Embedding、ASR 和 TTS 都使用 DashScope。若改用其他聊天 Provider，应用仍可启动，
但默认语音模型需要可用的 DashScope Key。

## Provider 配置

Provider 初始种子来自环境变量：

| Provider | Key | 默认聊天模型 |
| --- | --- | --- |
| DashScope | `AI_BAILIAN_API_KEY` | `qwen3.7-max` |
| Kimi | `PROVIDER_KIMI_API_KEY` | `PROVIDER_KIMI_MODEL` |
| DeepSeek | `PROVIDER_DEEPSEEK_API_KEY` | `PROVIDER_DEEPSEEK_MODEL` |
| GLM | `PROVIDER_GLM_API_KEY` | `PROVIDER_GLM_MODEL` |
| LM Studio | `PROVIDER_LMSTUDIO_API_KEY` | `qwen2.5-7b-instruct` |

这些种子只在 `llm_provider_config` 表为空时写入。数据库初始化后，修改 `.env` 不会覆盖已经
保存的 Provider；请在前端设置页编辑并测试连接。

系统不会自动拉取厂商模型列表。每个 Provider 保存一组当前模型配置：

- `model`：聊天模型
- `embeddingModel`：向量模型，可为空
- `embeddingDimensions`：向量维度，本项目固定使用 1024
- `supportsEmbedding`：是否允许作为默认 Embedding Provider
- `temperature`：可选

`qwen3.7-text-embedding` 是有效的 Embedding 模型。不要把聊天模型名填到
`embeddingModel`。

当前默认值：

```env
AI_MODEL=qwen3.7-max
AI_EMBEDDING_MODEL=qwen3.7-text-embedding
APP_AI_EMBEDDING_DIMENSIONS=1024
APP_VOICE_INTERVIEW_QWEN_ASR_MODEL=qwen3-asr-flash-realtime
APP_VOICE_INTERVIEW_QWEN_TTS_MODEL=qwen3-tts-flash-realtime
```

## 语音配置

ASR 和 TTS 可在设置页修改。默认值来自环境变量，运行时修改会写入
`APP_VOICE_CONFIG_PATH` 指向的 JSON 文件。

生产 Compose 没有为该文件单独挂载 volume，因此重建容器后会重新使用环境变量。需要长期
保持自定义语音配置时，应把模型、音色、采样率等写入部署环境变量。

该 JSON 文件包含语音 API Key 明文，不要提交、上传或使用宽松文件权限共享。

常用变量：

```env
APP_VOICE_INTERVIEW_QWEN_ASR_MODEL=qwen3-asr-flash-realtime
APP_VOICE_INTERVIEW_QWEN_ASR_SAMPLE_RATE=16000
APP_VOICE_ASR_SILENCE_MS=2000
APP_VOICE_INTERVIEW_QWEN_TTS_MODEL=qwen3-tts-flash-realtime
APP_VOICE_INTERVIEW_QWEN_TTS_VOICE=Cherry
APP_VOICE_INTERVIEW_QWEN_TTS_SAMPLE_RATE=24000
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
FRONTEND_PORT=80
CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:5173
LOG_LEVEL=INFO
TZ=Asia/Shanghai
```

前端开发变量应放在 `frontend/.env.local`，也可以在命令前临时导出：

```env
VITE_API_PROXY_TARGET=http://localhost:8080
VITE_API_BASE_URL=
```

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
APP_INTERVIEW_EVALUATION_BATCH_SIZE=8
```

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
