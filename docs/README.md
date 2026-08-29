# 文档导航

本目录保存项目级配置、运维、部署和架构说明。根目录 README 只负责项目介绍、首次启动和导航；
组件开发命令分别由 `backend/README.md`、`frontend/README.md` 和 `tools/README.md` 维护。

## 按任务查找

| 任务 | 文档 |
| --- | --- |
| 第一次启动项目 | [根目录 README](../README.md#快速启动) |
| 查环境变量、账号、Provider、存储或模型配置 | [配置说明](CONFIGURATION.md) |
| 排查启动、端口、证书、任务、Provider、数据库或 Redis | [运行与排障](OPERATIONS.md) |
| 在服务器安装、主动更新或回滚 GHCR 镜像 | [GHCR 主动拉取部署](DEPLOYMENT.md) |
| 理解文字、知识库和语音面试的统一 Turn 模型 | [统一自适应面试](ADAPTIVE_INTERVIEW.md) |
| 理解账号隔离、BYOK、安全和迁移边界 | [多租户账号与 BYOK](MULTI_TENANT_BYOK.md) |
| 将项目迁移到学校 OpenTrek 并在校园 Linux 主机部署 | [OpenTrek 迁移与校园部署计划](plans/OPENTREK_MIGRATION_PLAN.md) |
| 维护普通面试参考资料及来源追踪 | [普通面试参考资料来源](REFERENCE_SOURCES.md) |
| 开发后端 | [后端开发](../backend/README.md) |
| 开发前端 | [前端开发](../frontend/README.md) |
| 使用清单、诊断和验收工具 | [仓库工具](../tools/README.md) |

## 内容边界

为避免同一行为在多处复制，文档按以下边界维护：

- `README.md`：项目定位、最短启动路径、部署方式选择和文档入口。
- `CONFIGURATION.md`：环境变量和运行时配置的唯一说明。
- `OPERATIONS.md`：源码/Compose 运行步骤和故障处理，不重复完整变量清单。
- `DEPLOYMENT.md`：无源码服务器的 GHCR 安装、更新、HTTPS 和回滚流程。
- 架构文档：记录稳定设计、协议和安全边界，不保存易过期的操作命令或测试数量。
- 组件 README：只描述对应目录的开发、测试和代码结构。

新增内容时优先链接到现有专题章节。只有读者不打开链接就无法完成当前步骤时，才在入口文档保留
一条必要命令或一段必要说明。

## 维护检查

```bash
python3 tools/scripts/check_docs.py --root .
```

该检查覆盖 Markdown 本地链接、行尾空格和文档中的环境变量名称。文档变更在 CI 中只触发轻量
文档策略、工具测试和统一 gate；具体选择规则见 [仓库工具](../tools/README.md#ci-变更选择)。
