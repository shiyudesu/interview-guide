# Python/FastAPI 切换完成记录

## 状态

旧后端到 Python/FastAPI 的切换已经完成。生产 Compose、CI、数据库升级、Worker、
Scheduler 和真实模型验收均使用 Python 实现。

切换期间使用的旧代码、构建工具、回滚镜像、标签、对比脚本和历史差异报告已经删除。
当前仓库不提供旧后端回滚路径。

## 最终架构

| 部分 | 当前实现 |
| --- | --- |
| API | Python 3.13.13、FastAPI、Uvicorn |
| 数据访问 | SQLAlchemy 2、psycopg 3 |
| 数据库升级 | Alembic |
| Redis | redis-py asyncio |
| AI | LangGraph、langchain-openai、统一 LLM Adapter |
| 文件与 PDF | pdfminer.six、python-docx、LibreOffice、ReportLab |

## 保持不变的外部行为

切换的约束是替换实现，不修改产品协议。当前测试继续保护以下行为：

- REST 路径、HTTP 方法、参数、multipart 字段和响应头
- 响应字段、默认值、null、数组顺序、时间格式、错误码和错误文案
- 普通业务错误使用 HTTP 200 包装响应
- SSE 分帧和 WebSocket JSON/Base64 音频协议
- PostgreSQL 表、约束、索引、事务结果和 `vector(1024)`
- Redis key、TTL、Stream、Pending reclaim、重试和 ACK 顺序
- requestId 幂等锁、结果缓存和数据库唯一索引
- Prompt、Skill、Provider、Tool、JSON Schema、重试和回退顺序
- 文件识别、清洗、hash、对象 key、下载头和 PDF 可见内容

## 数据库切换

Alembic 是当前唯一数据库升级入口：

```bash
cd backend
uv run --frozen interview-guide-migrate
```

切换验收时已在既有 PostgreSQL schema 上完成 baseline 和重复执行检查，并验证第二次执行
不产生额外 DDL。新环境直接升级到 Alembic head。

## 运行进程

同一 Python 镜像启动：

1. Migrate：升级数据库，成功后其他服务才能启动。
2. API：单 Uvicorn worker，提供 REST、SSE 和 WebSocket。
3. Worker：处理五组 Redis Stream。
4. Scheduler：单实例执行恢复和过期任务。

Compose 对外服务名仍为 `app`，默认端口仍为 8080。

## 最终模型验收

受保护工作流固定检查：

```text
LLM        qwen3.7-max
Embedding  qwen3.7-text-embedding（1024 维）
ASR        qwen3-asr-flash-realtime
TTS        qwen3-tts-flash-realtime
```

真实模型工作流不会用 fake 替代 Provider 调用。普通单元测试可以使用明确命名的 fake 或 stub。

## 当前维护方式

切换完成后，不再运行新旧后端对比。兼容性由以下检查持续维护：

- 后端单元、契约和真实基础设施集成测试
- 前端状态测试、Playwright 和生产构建
- `tools/manifests/` 仓库清单
- 生产 Compose 集成测试
- Python-only 镜像检查
- 受保护 LLM、Embedding、ASR 和 TTS 冒烟

当前命令见根目录 [README](../README.md)，配置见
[CONFIGURATION.md](CONFIGURATION.md)，部署和排障见 [OPERATIONS.md](OPERATIONS.md)。
