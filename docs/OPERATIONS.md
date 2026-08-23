# 运行与排障

## 启动和检查

推荐使用一键启动脚本。脚本会检查 Docker、Compose 和 Docker daemon；Windows、macOS、
Ubuntu、Debian 和 WSL 缺少 Docker 时，可以在确认后自动安装。脚本还会自动创建 `.env`，并在
失败时输出关键日志：

```bash
./scripts/start.sh
```

Windows 可双击根目录的 `start.cmd`，或在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

跳过安装确认可使用 Bash 的 `--yes` 或 PowerShell 的 `-Yes`。自动安装可能触发 UAC、请求
sudo 密码或要求完成 Docker Desktop 的首次许可提示；脚本不会关闭安全确认，也不会删除数据卷。

手工启动命令：

```bash
docker compose up -d --build --wait
docker compose ps -a
```

关闭服务时使用配套脚本，默认保留所有数据卷：

```bash
./scripts/stop.sh
```

Windows 可双击 `stop.cmd`，或运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

关闭脚本不会自动安装或启动 Docker：Docker daemon 已关闭时，本地容器本身已不可用，脚本会
直接成功退出。需要彻底清空数据时仍必须手工执行 `docker compose down -v`，避免误触删除。

正常情况下：

- `migrate` 执行成功后退出
- `app`、`postgres`、`redis`、`minio` 为 healthy
- `worker`、`scheduler`、`frontend` 为 running

## 端口占用

启动脚本会在构建前检查端口，并在 Compose 仍因端口竞争失败时再次解析错误。提示会直接列出
占用进程和建议修改项，例如：

```env
FRONTEND_PORT=5174
SERVER_PORT=18080
POSTGRES_PORT=15432
REDIS_PORT=16379
APP_STORAGE_PORT=19000
APP_STORAGE_CONSOLE_PORT=19001
```

只修改宿主机映射变量即可，不要修改容器内部端口。修改 `FRONTEND_PORT` 后，访问地址也要带上
新端口，例如 <http://localhost:5174>。

## Docker Hub 镜像拉取失败

首次启动需要从 Docker Hub 拉取 PostgreSQL/pgvector、Redis、MinIO、Python、Node 和 Nginx
等镜像。出现以下错误通常是 Docker daemon 无法解析或连接 Docker Hub，而不是 Compose 服务
本身启动失败：

```text
lookup registry-1.docker.io: no such host
failed to fetch anonymous token
failed to resolve source metadata
dial tcp ...:443: i/o timeout
TLS handshake timeout
```

先用一个小镜像验证 daemon 的拉取链路：

```bash
docker pull docker.io/library/redis:7.4.2-alpine
```

浏览器或当前 shell 能访问 Docker Hub，不代表 Docker daemon 已经使用同一个代理。Docker
Desktop 应在 `Settings > Resources > Proxies` 中配置代理并重启；不要用容器内 DNS 设置修复
daemon 的镜像拉取。Linux Docker Engine 可以按 Docker 官方
[daemon 代理说明](https://docs.docker.com/engine/daemon/proxy/)为 systemd 服务配置代理，例如
新建 `/etc/systemd/system/docker.service.d/http-proxy.conf`：

```ini
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:3128"
Environment="HTTPS_PROXY=http://proxy.example.com:3128"
Environment="NO_PROXY=localhost,127.0.0.1"
```

然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
sudo systemctl show --property=Environment docker
```

另一种方式是按 Docker 官方
[registry mirror 说明](https://docs.docker.com/docker-hub/image-library/mirror/)配置自建或可信的
Docker Hub 缓存。修改 `/etc/docker/daemon.json` 时必须合并已有配置，不要直接覆盖：

```json
{
  "registry-mirrors": ["https://mirror.example.com"]
}
```

如果已有支持 Docker Hub 路径布局的可信 pull-through cache，也可以只对本项目覆盖镜像来源，
无需改 daemon：

```env
INTERVIEW_GUIDE_DOCKERHUB_REGISTRY=mirror.example.com
```

该值不要包含 `https://`。修改后可先确认所有外部镜像都已切换，再启动：

```bash
docker compose config --images
docker compose up -d --build --wait
```

启动脚本会识别常见的 Docker Hub/DNS/超时错误并显示以上入口，但不会自动修改 DNS、代理或
Docker daemon，也不会默认使用来源不明的公共镜像站。

健康检查：

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/info
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

Worker 启动时会创建四组 Redis consumer group，并 reclaim 空闲超过 5 分钟的 Pending 消息。
失败消息最多重试 3 次，之后写入失败状态再 ACK。

## Provider API Key 无法解密

典型错误：

```text
cryptography.exceptions.InvalidTag
解密 Provider API Key 失败，请检查加密主密钥或 provider_key 卷
```

先确认自动密钥卷和文件仍然存在：

```bash
docker volume ls | grep provider_key
docker compose exec app ls -l /var/lib/interview-guide/provider-encryption.key
```

如果不是通过 Compose 运行，并使用了可选环境变量覆盖，再检查当前 shell 是否注入了不同的值：

```bash
env | grep '^APP_AI_CONFIG_ENCRYPTION_KEY='
```

必须恢复最初用于加密 Provider 的 `provider_key` 卷或外部主密钥。两者都无法恢复时，只能删除
对应 Provider 配置并重新录入 API Key。备份 PostgreSQL 数据时应同时备份 `provider_key` 卷。

## Provider 连接失败

1. 在设置页确认 Base URL、聊天模型和 API Key。
2. 使用设置页的连接测试。
3. 确认 Base URL 是 OpenAI 兼容根路径；测试会依次尝试
   `/chat/completions` 和必要时的 `/v1/chat/completions`。
4. Embedding 需要单独填写真实模型名和 1024 维。

设置页会依次尝试 `/models` 和必要时的 `/v1/models`，结果缓存 5 分钟。列表过期或厂商刚刚
开放模型时，点击“刷新列表”绕过缓存。若页面提示厂商未返回列表：

1. 检查 API Key 是否具有列出模型的权限。
2. 检查 Base URL 是否已经包含正确的版本路径。
3. 查看提示中的 HTTP 状态和厂商响应摘要。
4. 对未实现模型列表接口的 Provider，按厂商文档手工填写模型 ID，再执行连接测试。

模型出现在列表中不代表一定有调用权限、余额或地区可用性，最终仍以连接测试和厂商控制台为准。

## 端口被占用

检查端口：

```bash
ss -ltnp | grep -E ':(5173|5432|6379|8080|9000|9001)\b'
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

可以在 `.env` 中修改宿主机映射端口：

```env
SERVER_PORT=18080
FRONTEND_PORT=5174
POSTGRES_PORT=15432
REDIS_PORT=16379
APP_STORAGE_PORT=19000
APP_STORAGE_CONSOLE_PORT=19001
```

容器内部端口不变。

生产前端通过 Docker DNS 动态解析 `app`，后端容器重建后不需要重启前端。前端健康检查会经由
Nginx 请求 `/health`；若前端显示正常但 API 返回 502，检查 `frontend` 和 `app` 是否在
同一 Compose 网络，并运行 `docker compose logs frontend app`。

## 数据库初始化

Migrate 会把空数据库直接创建为当前 schema。执行 `docker compose up -d --build --wait` 后，
使用 `docker compose logs migrate` 确认 Alembic 成功到达 head。

面试缓存使用 `interview:create:*`、`interview:turn:*` 和 `voice:interview:*`。不要手工删除
`interview:evaluate:stream`，以免破坏 Pending、reclaim 和 ACK 状态。

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
| 前端运行代码 | 前端 lint、单元测试、无真实后端 Playwright、构建、生产 Compose 集成、`CI gate` |
| 模型诊断代理 | Model Proxy 测试、`CI gate` |
| Compose、Docker、锁文件或工作流 | 全量 CI |

工作流文件和变更分类脚本本身的修改始终强制全量运行。需要手动完整验收时，在 GitHub
Actions 中运行 `CI` 的 `workflow_dispatch`。仓库还会每天定时执行一次全量 CI。

前端 Job 会启动 Vite 并执行不依赖真实后端的 Playwright 用例；生产 Compose 集成只执行
`@real-backend` 用例。浏览器失败时会上传 `frontend-browser-tests`，其中包含 Playwright 报告、
截图、视频和 trace。仓库 API 清单同时比较 REST 路径和 HTTP 方法，任何 frontend-only 调用都会
使仓库工具测试失败。
