# InterviewGuide

InterviewGuide 是一个自托管 AI 面试平台，覆盖简历分析、文字和语音模拟面试、面试日程、
知识库 RAG、知识库出题以及用户级模型 Provider 管理。

生产后端使用 Python/FastAPI，前端使用 React；PostgreSQL/pgvector、Redis Stream 和 S3 兼容
对象存储负责持久化、异步任务与文件。

## 功能

- 上传 PDF、DOC、DOCX 简历，生成结构化分析和 PDF 报告
- 按岗位 Skill 或 JD 生成文字面试，异步评估并保存报告
- 支持 Java、Python、Go、前端、数据工程、DevOps/SRE、系统设计、算法、测试和 AI Agent 等方向
- 实时 ASR/TTS 语音面试，支持暂停、恢复和会后评估
- 管理面试日程，支持自然语言解析和状态流转
- 上传知识库文件，完成清洗、切片、向量化、RAG 对话和专项面试
- 每个账号独立管理 OpenAI 兼容 Provider、API Key、默认模型和语音配置

## 快速启动

推荐使用仓库脚本启动完整 Compose。脚本会检查 Docker 和 Compose，在用户确认后安装缺少的官方
组件，创建缺失的 `.env`，生成基础设施随机密码，并等待服务就绪；不会覆盖已有 `.env` 或删除
数据卷。

Windows 直接双击 `start.cmd`。Linux、macOS 或 WSL 运行：

```bash
./scripts/start.sh
```

服务器或不需要自动打开浏览器时：

```bash
./scripts/start.sh --no-open
```

默认入口：

| 用途 | 地址 |
| --- | --- |
| 前端 | <http://localhost:5173> |
| API | 前端同源路径 `/api/` |
| Swagger UI | <http://localhost:5173/docs> |
| OpenAPI | <http://localhost:5173/openapi.json> |

认证默认开启且自助注册关闭。首次启动后先创建管理员，密码会从终端安全读取：

```bash
docker compose run --rm app interview-guide-create-admin --email admin@example.com
```

登录后在设置页为默认的百炼 Provider 录入自己的 API Key；Provider 配置不需要写入 `.env`。
正式开放注册前必须完成真实 HTTPS、SMTP 和双用户隔离验收。

停止服务并保留数据：

- Windows：双击 `stop.cmd`
- Linux、macOS、WSL：运行 `./scripts/stop.sh`

手工 Compose 命令、端口冲突、镜像拉取和服务日志见
[运行与排障](docs/OPERATIONS.md)。

## 部署方式

| 场景 | 入口 | 说明 |
| --- | --- | --- |
| 本地使用或源码构建 | `scripts/start.sh` | 只发布前端入口，其他服务保留在 Compose 网络内 |
| OpenTrek 校园赛 | `scripts/start-campus.sh` | 独立数据卷、只读知识库和文字面试，校园网 HTTP |
| 正式服务器 | [GHCR 主动拉取部署](docs/DEPLOYMENT.md) | 使用备案域名和 HTTPS，服务器无需克隆仓库 |
| NAT 高端口临时验收 | `scripts/start-http.sh` | 使用独立配置和数据卷，仅用于短期明文验收 |

校园赛拉取新代码后，如需把仓库内完整资料同步到全部尚未生成题目的评委影子知识库，显式运行
`./scripts/sync-campus-kb.sh --yes`；普通 `git pull` 不会隐式修改 `.env.campus` 或数据卷。

临时 HTTP 模式不能替代正式 HTTPS，也无法在非本机页面完成浏览器麦克风录音。详细边界和停止命令
见 [临时 HTTP 验收部署](docs/OPERATIONS.md#临时-http-验收部署)。

## 本地开发

先准备根目录 `.env`，再启动开发基础设施：

```bash
cp .env.example .env
# 填写 POSTGRES_PASSWORD 和 APP_STORAGE_SECRET_KEY
docker compose -f docker-compose.dev.yml up -d --wait
```

随后按开发范围进入对应说明：

- [后端开发](backend/README.md)：uv、Alembic、API、Worker、Scheduler、Ruff、mypy 和 pytest
- [前端开发](frontend/README.md)：pnpm、Vite、Vitest、Playwright、lint 和构建
- [仓库工具](tools/README.md)：仓库清单、文档检查、模型诊断和真实模型验收

完整环境变量只在 [配置说明](docs/CONFIGURATION.md) 维护，避免 README 与实际配置漂移。

## 运行架构

生产 Compose 使用同一个 Python 镜像启动四类后端进程：

| 进程 | 职责 |
| --- | --- |
| `migrate` | 通过 Alembic 升级数据库，成功后其他后端进程才能启动 |
| `app` | 提供 REST、SSE、WebSocket、OpenAPI 和健康检查 |
| `worker` | 顺序消费四组 Redis Stream，处理分析、向量化、出题和面试评估 |
| `scheduler` | 处理日程过期、遗漏任务和语音会话恢复 |

前端 Nginx 提供静态文件并将 `/api/`、`/ws/`、`/docs` 和 `/openapi.json` 同源代理到 API；正式
公网部署由 Caddy 作为唯一 80/443 入口终止 TLS。

## 仓库目录

```text
backend/                FastAPI 后端、Alembic、资源和测试
frontend/               React 前端、Playwright 和 Nginx 配置
tools/                  仓库清单、参考资料、模型诊断和生产验收工具
scripts/                跨平台启动、停止和辅助脚本
docs/                   配置、运维、部署和架构文档
deploy/                 GHCR 部署包、主动更新、systemd 和回滚脚本
docker-compose.yml      生产 Compose
docker-compose.dev.yml  本地基础设施
docker-compose.test.yml 集成测试回环端口覆盖
```

## 文档

从 [文档导航](docs/README.md) 按任务查找说明。主要入口：

- [配置说明](docs/CONFIGURATION.md)
- [运行与排障](docs/OPERATIONS.md)
- [GHCR 主动拉取部署](docs/DEPLOYMENT.md)
- [统一自适应面试](docs/ADAPTIVE_INTERVIEW.md)
- [多租户账号与 BYOK](docs/MULTI_TENANT_BYOK.md)
- [OpenTrek 迁移与校园部署计划](docs/plans/OPENTREK_MIGRATION_PLAN.md)
- [OpenTrek 校园赛配置](docs/CONFIGURATION.md#opentrek-校园赛模式)
- [OpenTrek 校园赛运维](docs/OPERATIONS.md#opentrek-校园赛部署)
- [普通面试参考资料来源](docs/REFERENCE_SOURCES.md)

文档、代码或部署行为变更后，可运行：

```bash
python3 tools/scripts/check_docs.py --root .
./tools/scripts/check-manifests.sh
```
