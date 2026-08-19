# 运行与排障

## 启动和检查

```bash
docker compose up -d --build --wait
docker compose ps -a
```

正常情况下：

- `migrate` 执行成功后退出
- `app`、`postgres`、`redis`、`minio` 为 healthy
- `worker`、`scheduler`、`frontend` 为 running

健康检查：

```bash
curl http://127.0.0.1:8080/actuator/health
curl http://127.0.0.1:8080/actuator/info
```

日志：

```bash
docker compose logs migrate
docker compose logs -f app
docker compose logs -f worker
docker compose logs -f scheduler
```

## 更新部署

```bash
git pull --ff-only
docker compose up -d --build --wait
docker compose ps
```

Compose 会先执行 Alembic，再重建依赖同一 Python 镜像的 API、Worker 和 Scheduler。

## 服务职责

| 服务 | 说明 |
| --- | --- |
| `migrate` | Alembic 数据库升级 |
| `app` | REST、SSE、WebSocket |
| `worker` | 简历分析、向量化、题目生成和面试评估 |
| `scheduler` | 日程过期及失败任务恢复 |
| `frontend` | Nginx 静态页面和反向代理 |
| `postgres` | PostgreSQL + pgvector |
| `redis` | Stream、缓存、锁和限流 |
| `minio` | 文件和报告对象存储 |

## 报告或任务一直处理中

先确认 Worker 正在运行：

```bash
docker compose ps worker
docker compose logs --tail=200 worker
```

只启动 API 时，以下任务不会完成：

- 简历分析
- 知识库向量化
- 知识库题目生成
- 文字面试报告评估
- 语音面试报告评估

Worker 启动时会创建五组 Redis consumer group，并 reclaim 空闲超过 5 分钟的 Pending 消息。
失败消息最多重试 3 次，之后写入失败状态再 ACK。

## Provider API Key 无法解密

典型错误：

```text
cryptography.exceptions.InvalidTag
解密 Provider API Key 失败，请检查 APP_AI_CONFIG_ENCRYPTION_KEY
```

检查当前 shell 是否覆盖了 `.env`：

```bash
env | grep '^APP_AI_CONFIG_ENCRYPTION_KEY='
```

如果 shell 中是旧值，先清除再启动：

```bash
unset APP_AI_CONFIG_ENCRYPTION_KEY
docker compose up -d --force-recreate app worker scheduler
```

必须恢复最初用于加密 Provider 的密钥。没有原密钥时，只能删除对应 Provider 配置并重新录入
API Key。

## Provider 连接失败

1. 在设置页确认 Base URL、聊天模型和 API Key。
2. 使用设置页的连接测试。
3. 确认 Base URL 是 OpenAI 兼容根路径；测试会依次尝试
   `/chat/completions` 和必要时的 `/v1/chat/completions`。
4. Embedding 需要单独填写真实模型名和 1024 维。

系统不会自动发现可用模型。模型是否存在、权限和地区可用性以厂商控制台为准。

## 端口被占用

检查端口：

```bash
ss -ltnp | grep -E ':(80|5432|6379|8080|9000|9001)\b'
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

可以在 `.env` 中修改宿主机映射端口：

```env
SERVER_PORT=18080
FRONTEND_PORT=8088
POSTGRES_PORT=15432
REDIS_PORT=16379
APP_STORAGE_PORT=19000
APP_STORAGE_CONSOLE_PORT=19001
```

容器内部端口不变。

## PostgreSQL 密码不一致

PostgreSQL 只在首次创建 volume 时使用 `POSTGRES_PASSWORD`。修改 `.env` 不会改变已有角色
密码。

保留数据时，在数据库内修改密码；只有确定可以丢弃本地数据时才执行：

```bash
docker compose down -v
docker compose up -d --build --wait
```

## 对象存储问题

检查 MinIO：

```bash
docker compose ps minio createbuckets
docker compose logs minio createbuckets
```

生产 Compose 会创建 `APP_STORAGE_BUCKET` 并设置公开读取。上传失败时确认 endpoint、access key、
secret key 和 bucket 名在所有后端进程中一致。

## 查看 Redis Stream

```bash
docker compose exec redis redis-cli XINFO GROUPS resume:analyze:stream
docker compose exec redis redis-cli XPENDING resume:analyze:stream analyze-group
```

其他 Stream：

```text
knowledgebase:vectorize:stream
knowledgebase:question-gen:stream
interview:evaluate:stream
voice:evaluate:stream
```

不要直接删除生产 Stream key。删除 key 会同时删除 consumer group，必须重启 Worker 才会重建。

## 停止和清理

停止但保留数据：

```bash
docker compose down
```

删除全部本地数据：

```bash
docker compose down -v
```

第二条命令不可恢复本地 PostgreSQL、Redis 和对象存储内容。

## CI 变更选择

`CI` 会先运行 `tools/scripts/detect_ci_changes.py`，再按路径选择检查：

| 改动 | 运行内容 |
| --- | --- |
| 仅 Markdown 文档 | 文档、提交规范、工具测试、`CI gate` |
| 后端单元测试 | 后端检查、仓库清单、`CI gate` |
| 后端运行代码或集成测试 | 后端检查、生产 Compose 集成、`CI gate` |
| 前端运行代码 | 前端测试和构建、生产 Compose 集成、`CI gate` |
| 模型诊断代理 | Model Proxy 测试、`CI gate` |
| Compose、Docker、锁文件或工作流 | 全量 CI |

工作流文件和变更分类脚本本身的修改始终强制全量运行。需要手动完整验收时，在 GitHub
Actions 中运行 `CI` 的 `workflow_dispatch`。仓库还会每天定时执行一次全量 CI。
