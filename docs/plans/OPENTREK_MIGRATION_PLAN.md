# OpenTrek 迁移与 Linux 校园网部署计划

## 1. 目标与已确定决策

本计划用于将 InterviewGuide 接入学校自行部署的 OpenTrek，并在一台校园网内的
Ubuntu/Debian x86_64 Linux 主机上提供比赛访问。

实施记录（2026-08-29）：仓库实现、四类能力路由、比赛模式、校园脚本、资源 provisioning、
13 个 Skill、Kortex 建库/上传/真实召回、四个 Agent 非流式调用和 RAG 流式调用已经在真实
OpenTrek 工作空间验证。当前已发布资源版本为 `competition-v9`；General、Interviewer、RAG 使用
`qwen3.6-plus`，Evaluator 使用 `qwen3.6-flash`，均关闭思考并限制 4096 输出。后续升级为
`competition-v12`，四类 Agent 统一切换到真实规划探针 5/5 成功的 `glm-5.1`。曾按需求验证
`deepseek-v4-pro`，但多组参数下仍随机返回“无规划任务结果”，最好仅 2/3、正式配置为 1/5，不能
用于比赛运行时。必须先在目标工作空间唯一发现模型，再使用管理 Cookie 创建、配置和发布新版本。
目标比赛 Linux
主机 IP/SSH、
两台真实校园网设备并发访问及主机重启持久化尚未提供，因此这些现场门禁仍保持未通过；本记录不
把本地 WSL/Compose 验证等同于目标服务器验收。

当前已经确定：

- Linux 主机具备 SSH 和 sudo 权限。
- 评委通过校园网访问 Linux 主机，不依赖公网。
- 暂时只有校园网 IP 和 HTTP，不使用校内 HTTPS。
- InterviewGuide 保留本地账号体系，为评委准备独立账号。
- OpenTrek 使用一套比赛专用账号、工作空间和 OpenTrek应用密钥。
- 第一阶段迁移简历分析、JD 解析、文字面试、动态追问、评估和知识库能力。
- 暂不展示语音面试。
- 不允许评委现场上传新的知识库文件。
- 比赛知识库提前上传到 OpenTrek Kortex 并完成解析和向量化。
- OpenTrek 调用失败时不回退其他生成模型。
- OpenTrek 平台中的比赛 Agent、Skill、知识库和 OpenTrek应用密钥 由开发代理自动配置。

本次迁移不改变现有 REST、SSE 和 WebSocket 对外协议，不改变 PostgreSQL 表、字段、约束、
索引，不改变现有 Redis key、Stream、Pending、reclaim、重试和 ACK 顺序。

## 2. 目标架构

~~~text
校园网内的评委浏览器
          |
          | HTTP
          v
Linux 主机 :18073
  |
  +-- Frontend Nginx / React
  |
  +-- FastAPI
       |
       +-- PostgreSQL
       +-- Redis Stream
       +-- MinIO
       +-- Worker / Scheduler
       |
       +-- OpenTrek Client
              |
              +-- General Agent
              +-- Interviewer Agent
              +-- Evaluator Agent
              +-- RAG Agent
              +-- Kortex 预置知识库
~~~

浏览器只访问 InterviewGuide。OpenTrek OpenTrek应用密钥 只保存在 Linux 后端环境中，不发送给浏览器。
OpenTrek 管理页面的 30226 端口用于配置资源；运行时主要调用 80 端口下的 Agent 和 Kortex 网关。

## 3. OpenTrek 平台资源

### 3.1 Agent

创建并发布四个比赛专用 Agent。OpenTrek 的 Agent 名称上限为 20 个字符，因此资源名称统一使用
`ig-comp-` 前缀（General、Interviewer、Evaluator、RAG 当前分别使用 `general`、`intv-v2`、
`eval-v2`、`rag` 后缀）。Interviewer/Evaluator 的早期资源在平台不可逆版本切换后对部分结构化
任务持续返回无规划结果，因此保留旧资源作审计并切换到新的干净资源：

| Agent | 职责 |
| --- | --- |
| General | 简历分析、日程文本解析 |
| Interviewer | JD 解析、问题生成、动态追问 |
| Evaluator | 面试评估、知识库题库生成 |
| RAG | 知识库普通问答和流式问答 |

Agent 使用任务执行型系统提示词。InterviewGuide 继续传入当前仓库中的 system prompt、
user prompt 和 JSON Schema，平台 Agent 不自行改写输出协议。

### 3.2 Skill

将 backend/resources/skills 下的 13 个岗位 Skill 分别打包，保留：

- SKILL.md
- skill.meta.yml
- 当前 Skill 自身引用的 reference 文件
- _shared/references 中实际使用的共享参考文件

Skill ZIP 必须先经过 OpenTrek 扫描。扫描不通过时停止上传，不绕过安全结果。当前平台管理接口会
忽略 Skill 保存请求中的静态 Agent 关联，因此运行时按平台 UI 的实际协议，通过
`message.metadata.skillList` 将当前面试方向对应岗位 Skill 的 `name` 传给 Interviewer 和
Evaluator 的出题/评估调用；JD 通用解析和无岗位上下文的调用不盲目加载全部 13 个 Skill。Turn
决策已由当前 Prompt 载入审核后的 Skill reference，不重复启用平台 Skill，以保持单次低延迟决策。

### 3.3 预置知识库

比赛知识库在 OpenTrek 管理页面中提前创建为文档知识库：

1. 选择平台内可用的 EMBEDDING 模型；当前平台的文档知识库还要求 `visualModel`，需同时选择可用
   VLM，即使基础解析策略不启用图片增强。
2. 上传比赛资料。
3. 等待文件转存、解析和向量化完成。
4. 使用文档知识库检索接口进行真实召回。
5. 记录 kbCode。

比赛期间不开放知识库上传，只允许查询、RAG 问答、知识库出题和知识库专项面试。

## 4. 后端实施方案

### 4.1 OpenTrek Client

新增统一 OpenTrek Client，负责：

- createSession
- 非流式 run
- 流式 run
- clearSession
- deleteSession
- SSE 分帧与 message.delta 合并
- thought.delta、error 和结束事件处理
- 超时、取消、限流和权限错误映射

每次业务调用创建临时 OpenTrek Session，调用结束后删除。第一阶段不启用 OpenTrek 长期记忆，
不传 memoryUserId，避免多个评委之间出现平台记忆串扰。

客户端必须：

- 禁止 HTTP 重定向。
- 禁止使用环境代理。
- 不启用 SDK 或传输层隐式重试。
- 只允许连接部署配置中的 10.128.203.200。
- 不记录 OpenTrek应用密钥、完整简历、完整回答或平台临时凭据。
- 校园工作空间的 Agent 执行通过共享卷文件锁跨 API/Worker 进程串行化，并保持 1 秒最小间隔；
  Kortex 检索不走该门禁，且不改变任何 Redis key。

### 4.2 能力路由

增加能力级 Agent Registry：

| InterviewGuide 能力 | OpenTrek Agent |
| --- | --- |
| 简历分析 | General |
| 日程解析 | General |
| JD 解析 | Interviewer |
| 主问题生成 | Interviewer |
| 动态追问决策 | Interviewer |
| 面试评估 | Evaluator |
| 知识库题库生成 | Evaluator |
| 知识库回答 | RAG |

比赛模式下，用户请求中的 llmProvider 不改变实际生成模型出口。Provider 选择界面在前端隐藏，
但现有请求字段、响应字段和数据库字段保持不变。

### 4.3 Prompt、Schema、重试与回退

- 继续使用现有 PromptRepository、PromptSanitizer 和反注入边界。
- 继续使用现有 Pydantic 输出类型和 StructuredOutputInvoker。
- 普通结构化调用仍最多尝试两次，第二次使用当前 JSON 修复提示。
- Turn 决策仍只允许一次模型调用。
- Redis 后台任务继续按当前最多三次重投和失败状态处理。
- 不回退本地或其他外部生成模型。
- Turn 模型不可用时继续使用当前确定性 NEXT_MAIN 或 COMPLETE 回退，并记录 FALLBACK。

当前平台的 Agent 对知识库题库和普通面试出题 Prompt 单次生成多题、或在题目中嵌套固定追问时会
返回“无规划任务结果”。OpenTrek 模式保持相同 Prompt 模板和 JSON Schema，压缩 Schema 的传输
表示，并且每次只生成 1 题后顺序聚合；固定追问数设为 0，面试阶段继续由 Turn 模型动态追问。
标准 Provider 的批量生成和固定追问行为不变。

知识库专项面试的会话仍保留兼容用的 `skill_id=knowledge-base`，但它不是 OpenTrek 已发布岗位
Skill，评估调用不得把它写入 `message.metadata.skillList`。Evaluator 继续使用完整反注入边界，
同时关闭重复 Schema 并使用紧凑 Schema 传输，避免较长知识库评估 Prompt 触发“无规划任务结果”。

### 4.4 预置 Kortex 知识库映射

不增加数据库字段。新增运维命令 interview-guide-seed-opentrek-kb：

1. 为指定 InterviewGuide 用户保存预置资料的本地下载副本。
2. 在现有 knowledge_bases 表中创建该用户自己的影子记录。
3. 将 vector_status 标记为 COMPLETED，不投递本地向量化任务。
4. 输出文件 SHA-256。
5. 将文件哈希与 Kortex kbCode 写入 APP_OPENTREK_KB_MAPPINGS_JSON。

每个评委账号拥有独立的本地知识库记录，但可以映射到同一个只读 Kortex 知识库。

知识库查询和题库生成统一经过 Retrieval Facade：

- 命中文件哈希映射时调用 Kortex。
- 单次最多向 Kortex 提交 10 个知识库，超过时分批调用。
- 沿用现有 top-k、最低分数、去重、上下文截断和问题生成限制。
- Kortex 调用失败时返回明确错误，不使用本地 pgvector 结果伪装成功。

### 4.5 比赛账号

新增 interview-guide-create-user CLI，用于交互式创建已验证的普通 USER 账号。自助注册保持关闭。

部署时至少创建：

- 一个演示管理员账号。
- 两个普通评委账号。
- 若预计同时试用人数更多，按人数增加普通账号。

密码必须为比赛专用一次性密码，不得复用个人、学校或生产系统密码。

## 5. 前端比赛模式

增加 APP_COMPETITION_MODE 配置。启用后：

- 隐藏语音面试入口。
- 隐藏 Provider 设置与模型选择。
- 隐藏知识库上传、删除和重新向量化入口。
- 隐藏注册入口。
- 保留登录、退出、简历、文字面试、历史报告、RAG 和知识库专项面试。
- 显示“OpenTrek 校园赛版”标识和平台不可用时的明确错误。

原有前端 API 路径、multipart 字段、SSE 分帧和响应解析保持不变。

## 6. Linux 校园网部署

新增：

- .env.campus.example
- scripts/start-campus.sh
- scripts/stop-campus.sh

校园实例使用独立 Compose 项目名 interview-guide-campus 和独立数据卷。启动脚本必须非破坏性，
不得覆盖已有 .env.campus，不得删除现有数据卷。

核心配置：

~~~dotenv
APP_COMPETITION_MODE=true
APP_AUTH_ENABLED=true
APP_AUTH_REGISTRATION_ENABLED=false
APP_AUTH_COOKIE_SECURE=false

FRONTEND_BIND_ADDRESS=0.0.0.0
FRONTEND_PORT=18073
COMPOSE_PROFILES=

APP_OPENTREK_ENABLED=true
APP_OPENTREK_RUNTIME_BASE_URL=http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway
APP_OPENTREK_APP_KEY=
APP_OPENTREK_WORKSPACE_CODE=

APP_OPENTREK_GENERAL_AGENT_CODE=
APP_OPENTREK_GENERAL_AGENT_VERSION=
APP_OPENTREK_INTERVIEWER_AGENT_CODE=
APP_OPENTREK_INTERVIEWER_AGENT_VERSION=
APP_OPENTREK_EVALUATOR_AGENT_CODE=
APP_OPENTREK_EVALUATOR_AGENT_VERSION=
APP_OPENTREK_RAG_AGENT_CODE=
APP_OPENTREK_RAG_AGENT_VERSION=

APP_OPENTREK_KB_MAPPINGS_JSON=[]

APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS=10.128.203.200
APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS=10.128.203.200/32
~~~

启动脚本负责：

- 检查 Docker Engine、Compose v2 和 x86_64 架构。
- 在用户确认后安装 Docker 官方组件。
- 检查宿主机 18073 端口占用。
- 生成 PostgreSQL 和 MinIO 随机密码。
- 列出 Linux 主机的非回环 IPv4。
- 从宿主机检查 OpenTrek 30226 和 80 端口。
- 启动后从 app 和 worker 容器再次检查 OpenTrek。
- 只发布前端端口。
- 输出评委访问地址和 HTTP 明文风险。

stop-campus.sh 只执行非破坏性 Compose down 并保留数据卷。

## 7. 测试和验收

### 7.1 自动测试

- OpenTrek URL、Header、Session 生命周期和敏感信息脱敏。
- SSE 拆包、粘包、delta 合并、流中断与取消。
- 401、403、429、5xx、超时和非法 JSON。
- 普通结构化重试与 Turn 单次调用。
- Kortex 哈希映射、分批检索、去重和失败不回退。
- 比赛模式入口隐藏与知识库写操作禁用。
- 标准模式现有行为不变。
- 两个账号的简历、面试、知识库和会话隔离。

普通 CI 使用明确命名的 Stub OpenTrek，不用 fake 冒充真实平台验收。

### 7.2 真实平台验收

- Linux 宿主机、app 容器和 worker 容器均能连接 OpenTrek。
- 简历分析成功并符合现有 AnalysisOutput。
- JD 解析和问题生成成功。
- 动态追问返回符合 TurnDecisionOutput。
- 异步面试评估成功。
- Kortex 普通检索、流式问答和知识库题库生成成功。
- 错误 OpenTrek应用密钥、平台不可达和限流时明确失败，不调用其他生成模型。

### 7.3 校园网验收

- 使用至少两台真实校园网设备访问 Linux 主机。
- 两个评委账号同时登录，互相看不到对方的数据。
- 完成“简历分析 → 创建文字面试 → 回答 → 动态追问 → 完成 → 查看报告”。
- 完成“选择预置知识库 → RAG 问答 → 生成题库 → 知识库面试”。
- 重启 Linux 和 Docker 后数据、账号和配置仍然存在。

## 8. 用户前置任务清单

### 8.1 当前仍未完成的硬前置

- [ ] 提供比赛关于“必须使用 OpenTrek”的官方原文或截图。
- [ ] 提供最终比赛日期和期望的代码冻结日期。
- [ ] 提供 Linux 主机校园网 IP。
- [ ] 提供 Linux 主机 SSH 用户名和安全登录方式；不要把 SSH 密码或私钥写进仓库或聊天。
- [ ] 在 Linux 主机执行下面的环境诊断并保存输出。
- [ ] 从另一台真实校园网设备验证能够访问 Linux 主机的临时 18073 端口。
- [ ] 告知预计同时试用的评委人数。
- [ ] 提供至少一份虚构简历和一份目标岗位 JD。
- [ ] 提供允许上传到学校平台的知识库资料。
- [ ] 确认 Linux 主机比赛期间持续供电、不休眠、不自动更新重启。

环境诊断：

~~~bash
cat /etc/os-release
uname -m
nproc
free -h
df -h /
ip -4 addr show scope global
ip route get 10.128.203.200
docker --version
docker compose version
sudo ss -ltnp
sudo ufw status
~~~

OpenTrek 网络诊断：

~~~bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  http://10.128.203.200:30226/agent/index.html

curl -sS -o /dev/null -w '%{http_code}\n' \
  http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/createSession
~~~

第一条预期返回 200；第二条在没有 OpenTrek应用密钥 时预期返回 401 或 403。

校园互访测试：

~~~bash
test_dir="$(mktemp -d)"
cd "$test_dir"
python3 -m http.server 18073 --bind 0.0.0.0
~~~

从另一台校园网设备访问 http://Linux校园网IP:18073。测试完成后按 Ctrl+C 停止。

### 8.2 用户不需要提前完成的工作

以下工作将在开发和部署阶段完成：

- 创建 OpenTrek 比赛专用 OpenTrek应用密钥。
- 创建和发布四个 Agent。
- 打包、扫描和上传 13 个 Skill。
- 创建 Kortex 知识库并上传预置资料。
- 开发 OpenTrek Client、SSE 解析和错误映射。
- 开发能力路由、比赛模式和知识库映射。
- 创建评委账号和预置知识库影子记录。
- 编写校园启动、停止和诊断脚本。
- 执行单元、集成、真实平台和浏览器验收。
- 更新配置、运维、README、AGENTS 和比赛策划文档。

## 9. 风险与退出条件

- 若校园网设备无法访问 Linux 主机，必须先由学校网络管理员开放端口或调整 VLAN；开发完成不能
  弥补现场网络不可达。
- 若 Linux 容器无法访问 OpenTrek，必须处理宿主机路由、防火墙或校园网访问控制。
- 若账号无创建 Agent、Skill、知识库或 OpenTrek应用密钥 权限，必须由平台管理员补权。
- 若知识库资料无明确使用许可，不上传 OpenTrek。
- HTTP 模式不上传真实简历，不使用真实个人密码；比赛结束后删除评委账号和比赛数据。
- 任一核心真实 OpenTrek 门禁未通过，不宣称迁移完成。
