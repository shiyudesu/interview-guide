# 生成Skill MD

- 文档序号：036
- 分类：平台功能类 / 智能体管理 / SKILL HUB / 生成Skill MD
- 唯一编码：sfm.api.openapi-agent.agent.api.skill.generateskillmd
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/api/skill/generateSkillMD
- 文档版本：1787280870271

## 接口概述

根据参数自动生成Skill的Markdown描述文档

根据参数自动生成Skill的Markdown描述文档。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| skillType | String | 是 | Body | Skill类型 | TOOL |
| skillRefs | List<Object> | 否 | Body | 关联的Agent/Tool列表 | [] |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | String | 是 | Body | 生成的Skill MD内容 | # My Skill<br>... |
| errorCode | String | 是 | Body | 错误码 |  |
| errorMsg | String | 是 | Body | 错误描述 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/api/skill/generateSkillMD' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"skillAlias": "my-skill","skillType": "FILE","enableLlm": true}'
```


## 响应示例

#### 返回数据

```json
{"errorMessages":[],"success":true,"data":"---\r\nname:   \r\ndescription: \"Execute platform API tools via ibp-agent. Includes: (1) 支持开发者将夸克搜索能力无缝集成至大模型应用中，实现网页内容检索、实时资讯获取等功能。. \r\nUse when the user needs to call standardized platform APIs for CRUD operations, data queries, or system integrations.\"\r\n---\r\n\r\n# Platform API Tool\r\n\r\nExecute platform API tools through ibp-agent's standardized API gateway.\r\n\r\n## Tool Structure\r\n\r\nAn API Skill contains 1 tool definitions:\r\n\r\n**Tool 1:**\n```json\n{\n\t\"desc\":\"支持开发者将夸克搜索能力无缝集成至大模型应用中，实现网页内容检索、实时资讯获取等功能。\",\n\t\"toolParam\":[\n\t\t{\n\t\t\t\"fieldCode\":\"query\",\n\t\t\t\"fieldType\":\"STRING\",\n\t\t\t\"required\":true,\n\t\t\t\"fieldDesc\":\"用户搜索信息\",\n\t\t\t\"fieldDemo\":\"\"\n\t\t},\n\t\t{\n\t\t\t\"fieldCode\":\"whiteSites\",\n\t\t\t\"fieldType\":\"LIST_STRING\",\n\t\t\t\"required\":false,\n\t\t\t\"fieldDesc\":\"白名单站点列表\",\n\t\t\t\"fieldDemo\":\"baidu.com\"\n\t\t},\n\t\t{\n\t\t\t\"fieldCode\":\"startPublishedDate\",\n\t\t\t\"fieldType\":\"STRING\",\n\t\t\t\"required\":false,\n\t\t\t\"fieldDesc\":\"发布时间\",\n\t\t\t\"fieldDemo\":\"2025-07-01\"\n\t\t}\n\t]\n}\n```\n\n\r\n\r\n## Usage\r\n\r\nCall the `executePlatformApiTool` with toolCode, toolVersion, and toolParam:\r\n\r\n```json\n[\n\t{\n\t\t\"toolParam\":\"{\\\"query\\\":{},\\\"whiteSites\\\":{},\\\"startPublishedDate\\\":{}}\"\n\t}\n]\n```\n\r\n\r\n## toolParam Schema\r\n\r\nThe toolParam is built from the tool's `toolParam` field definition:\r\n\r\n**Example fields:**\n\n### Tool: 10001baseline\n- `query` (string, required, non-leaf): 用户搜索信息\n- `whiteSites` (list_string, optional, non-leaf): 白名单站点列表 - baidu.com\n- `startPublishedDate` (string, optional, non-leaf): 发布时间 - \"2025-07-01\"\n\r\n\r\n**Rules:**\r\n- toolParam is a JSON string (escape quotes with \\\")\r\n- **fieldCode**: Parameter name, use as JSON key\r\n- **fieldType**: Value type - string, number, boolean, object, array\r\n- **required**: Must include if true, optional if false\r\n- **leaf**: true means basic type (direct value), false means object (has children)\r\n- **parentFieldCode**: Identifies parent for nested fields (e.g., \"product\" for product.name)\r\n- **fieldDesc**: Parameter description, helps understand purpose\r\n- **fieldDemo**: Example value for reference\r\n- **refValue**: Default value - use when model cannot extract suitable value from user input\r\n- **children**: Nested field definitions for object types (leaf=false)\r\n- For optional fields without user input, use `refValue` as default\r\n- If `refValue` exists and model cannot extract suitable value from user input, use it\r\n- Follow `fieldType` for value type (string, number, boolean, object, array)\r\n- For nested objects (leaf=false), build nested JSON structure and escape as string\r\n- Use `parentFieldCode` to identify the parent-child relationship\r\n\r\n## Notes\r\n\r\n- **toolCode**: The unique tool code from Tool Structure (code field)\r\n- **toolVersion**: The tool version from Tool Structure (version field)\r\n- **toolParam**: Must be a valid JSON string (escape quotes with \\\")\r\n- Include all `required=true` fields from toolParam schema\r\n- **refValue usage**: When model cannot extract suitable value from user input, use refValue as default\r\n- Response time is typically fast (milliseconds)\r\n- API tools are stateless\r\n- Timeout: 120 seconds\r\n","errorCode":null,"errorMsg":null,"extraData":null,"traceId":null,"env":null,"other":null,"errorMessage":null,"firstErrorMessage":null,"failure":false}
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

- apiCode：agent.api.skill.generateskillmd
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-SKILL
- serviceRegion：ctl
