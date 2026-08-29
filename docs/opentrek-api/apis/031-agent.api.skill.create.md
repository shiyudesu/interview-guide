# 创建Skill

- 文档序号：031
- 分类：平台功能类 / 智能体管理 / SKILL HUB / 创建Skill
- 唯一编码：sfm.api.openapi-agent.agent.api.skill.create
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/api/skill/create
- 文档版本：1787280870243

## 接口概述

创建一个新的Skill

创建一个新的Skill，支持ZIP/Tool/Workflow等模式。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| skillAlias | String | 是 | Body | Skill别名 | my-skill |
| skillType | String | 是 | Body | Skill类型，FILE/TOOL/WORKFLOW | FILE |
| zipUrl | String | 否 | Body | ZIP文件下载URL |  |
| skillMd | String | 否 | Body | Skill MD内容 |  |
| scanReport | Object | 否 | Body | 扫描报告 | {} |
| skillRefs | List<Object> | 否 | Body | 关联的Agent/Tool列表 | [] |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 创建的Skill数据 | {} |
| data.skillCode | String | 是 | Body | Skill唯一标识 | sk-abc123 |
| data.skillAlias | String | 是 | Body | Skill别名 | my-skill |
| data.skillType | String | 是 | Body | Skill类型 | FILE |
| data.version | String | 是 | Body | Skill版本 | 1716800000000 |
| data.workspaceCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.gmtCreate | String | 是 | Body | 创建时间 | 2025-08-29T11:43:54.722+00:00 |
| errorCode | String | 是 | Body | 错误码 |  |
| errorMsg | String | 是 | Body | 错误描述 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/api/skill/create' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"skillAlias": "my-skill","skillType": "FILE","zipUrl": "http://xxx.com/xxx.zip"}'
```


## 响应示例

#### 返回数据

```json
{"errorMessages":[],"success":true,"data":{"id":118,"skillCode":"6a4b68c2-0774-4a40-a77e-bfe1e5673d36","skillVersion":"1780906143961","skillAlias":"my-scan-skill","name":"skill-vetter","description":"Security-first skill vetting for AI agents. Use before installing any skill from ClawdHub, GitHub, or other sources. Checks for red flags, permission scope, and suspicious patterns.","skillType":"FILE","zipUrl":null,"skillRefs":null,"skillMd":"---\nname: skill-vetter\nversion: 1.0.0\ndescription: Security-first skill vetting for AI agents. Use before installing any skill from ClawdHub, GitHub, or other sources. Checks for red flags, permission scope, and suspicious patterns.\n---\n\n# Skill Vetter \uD83D\uDD12\n\nSecurity-first vetting protocol for AI agent skills. **Never install a skill without vetting it first.**\n\n## When to Use\n\n- Before installing any skill from ClawdHub\n- Before running skills from GitHub repos\n- When evaluating skills shared by other agents\n- Anytime you're asked to install unknown code\n\n## Vetting Protocol\n\n### Step 1: Source Check\n\n```\nQuestions to answer:\n- [ ] Where did this skill come from?\n- [ ] Is the author known/reputable?\n- [ ] How many downloads/stars does it have?\n- [ ] When was it last updated?\n- [ ] Are there reviews from other agents?\n```\n\n### Step 2: Code Review (MANDATORY)\n\nRead ALL files in the skill. Check for these **RED FLAGS**:\n\n```\n\uD83D\uDEA8 REJECT IMMEDIATELY IF YOU SEE:\n─────────────────────────────────────────\n• curl/wget to unknown URLs\n• Sends data to external servers\n• Requests credentials/tokens/API keys\n• Reads ~/.ssh, ~/.aws, ~/.config without clear reason\n• Accesses MEMORY.md, USER.md, SOUL.md, IDENTITY.md\n• Uses base64 decode on anything\n• Uses eval() or exec() with external input\n• Modifies system files outside workspace\n• Installs packages without listing them\n• Network calls to IPs instead of domains\n• Obfuscated code (compressed, encoded, minified)\n• Requests elevated/sudo permissions\n• Accesses browser cookies/sessions\n• Touches credential files\n─────────────────────────────────────────\n```\n\n### Step 3: Permission Scope\n\n```\nEvaluate:\n- [ ] What files does it need to read?\n- [ ] What files does it need to write?\n- [ ] What commands does it run?\n- [ ] Does it need network access? To where?\n- [ ] Is the scope minimal for its stated purpose?\n```\n\n### Step 4: Risk Classification\n\n| Risk Level | Examples | Action |\n|------------|----------|--------|\n| \uD83D\uDFE2 LOW | Notes, weather, formatting | Basic review, install OK |\n| \uD83D\uDFE1 MEDIUM | File ops, browser, APIs | Full code review required |\n| \uD83D\uDD34 HIGH | Credentials, trading, system | Human approval required |\n| ⛔ EXTREME | Security configs, root access | Do NOT install |\n\n## Output Format\n\nAfter vetting, produce this report:\n\n```\nSKILL VETTING REPORT\n═══════════════════════════════════════\nSkill: [name]\nSource: [ClawdHub / GitHub / other]\nAuthor: [username]\nVersion: [version]\n───────────────────────────────────────\nMETRICS:\n• Downloads/Stars: [count]\n• Last Updated: [date]\n• Files Reviewed: [count]\n───────────────────────────────────────\nRED FLAGS: [None / List them]\n\nPERMISSIONS NEEDED:\n• Files: [list or \"None\"]\n• Network: [list or \"None\"]  \n• Commands: [list or \"None\"]\n───────────────────────────────────────\nRISK LEVEL: [\uD83D\uDFE2 LOW / \uD83D\uDFE1 MEDIUM / \uD83D\uDD34 HIGH / ⛔ EXTREME]\n\nVERDICT: [✅ SAFE TO INSTALL / ⚠️ INSTALL WITH CAUTION / ❌ DO NOT INSTALL]\n\nNOTES: [Any observations]\n═══════════════════════════════════════\n```\n\n## Quick Vet Commands\n\nFor GitHub-hosted skills:\n```bash\n# Check repo stats\ncurl -s \"https://api.github.com/repos/OWNER/REPO\" | jq '{stars: .stargazers_count, forks: .forks_count, updated: .updated_at}'\n\n# List skill files\ncurl -s \"https://api.github.com/repos/OWNER/REPO/contents/skills/SKILL_NAME\" | jq '.[].name'\n\n# Fetch and review SKILL.md\ncurl -s \"https://raw.githubusercontent.com/OWNER/REPO/main/skills/SKILL_NAME/SKILL.md\"\n```\n\n## Trust Hierarchy\n\n1. **Official OpenClaw skills** → Lower scrutiny (still review)\n2. **High-star repos (1000+)** → Moderate scrutiny\n3. **Known authors** → Moderate scrutiny\n4. **New/unknown sources** → Maximum scrutiny\n5. **Skills requesting credentials** → Human approval always\n\n## Remember\n\n- No skill is worth compromising security\n- When in doubt, don't install\n- Ask your human for high-risk decisions\n- Document what you vet for future reference\n\n---\n\n*Paranoia is a feature.* \uD83D\uDD12\uD83E\uDD80\n","scanReport":{"filePath":"http://sfm-lite-0518.oss-cn-hangzhou.aliyuncs.com/agent/skill-files/14ccb74d-c0a0-4959-b7e2-72d8bc3df83e/skill-vetter.zip?REDACTED_PRESIGNED_QUERY","securityStatus":true,"insecurityReasons":[]},"status":"PUBLISHED","masterFlag":true,"labels":null,"feature":null,"shareWorkspaces":null,"workspaceCode":"7a92789c-3882-43f5-be70-87c84b7fbede","tenant":"baseline","gmtCreate":"2026-06-08T08:09:03.962+00:00","gmtModified":"2026-06-08T08:09:03.962+00:00","creator":{"id":null,"gmtCreate":null,"gmtModified":null,"tenant":null,"uniqueCode":"7551a976815b413bb859074c9b0677d7","source":null,"outerId":null,"name":"opentrek"},"modifier":{"id":null,"gmtCreate":null,"gmtModified":null,"tenant":null,"uniqueCode":"7551a976815b413bb859074c9b0677d7","source":null,"outerId":null,"name":"opentrek"},"skillCategory":"workspace","installStatus":null,"exampleQuestions":null,"newVersionFlag":null},"errorCode":null,"errorMsg":null,"extraData":null,"traceId":null,"env":null,"other":null,"errorMessage":null,"firstErrorMessage":null,"failure":false}
```


## 状态码说明

#### 网关异常状态码说明

| HTTP 状态码 | 错误描述 | 错误释义 |
| --- | --- | --- |
| 401 | GATEWAY APP_KEY MISSING! | 网关必填参数缺失 |
| 401 | GATEWAY APP_KEY WRONG! | 鉴权失败,无效 APP_KEY |
| 401 | GATEWAY APP_KEY ALREADY EXPIRED! | 鉴权失败,APP_KEY 已过期 |
| 401 | GATEWAY ROLE NOT MATCH! | 鉴权失败,当前 APP_KEY 归属用户对应的角色不匹配 |
| 401 | GATEWAY ROLE HAS EXPIRED! | 鉴权失败,当前 APP_KEY 归属用户对应的角色已过期 |
| 403 | GATEWAY APP_PATH NOT FOUND! | 无效的服务调用路径 |
| 403 | GATEWAY APP_PATH NOT REGISTER! | 当前服务调用路径未注册 |
| 429 | GATEWAY LIMIT ! | 服务触发限流,请稍后再试 |
| 429 | GATEWAY LIMIT CURRENT CALL TYPE ! | 服务触发限流,请稍后再试 |
| 403 | GATEWAY HEADER PARAMETER MISSING! | 业务所需必填参数缺失 |
| 403 | GATEWAY PARAMETER WORKSPACE NO MATCH! | 传递的工作空间编码与APP_KEY归属用户关联的工作空间编码不匹配 |
| 401 | GATEWAY AUTH_TYPE WRONG! | 鉴权失败,不支持的鉴权方式 |
| 401 | GATEWAY AUTH_USER NOT MATCH WRONG! | 鉴权失败,AK用户信息不匹配 |
| 401 | GATEWAY AUTH_USER_ROLE WRONG! | 鉴权失败,用户角色不匹配 |



## 原始文档标识

- apiCode：agent.api.skill.create
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-SKILL
- serviceRegion：ctl
