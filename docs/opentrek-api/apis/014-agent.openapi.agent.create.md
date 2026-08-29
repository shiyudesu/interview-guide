# 创建智能体

- 文档序号：014
- 分类：平台功能类 / 智能体管理 / 智能体 / 创建智能体
- 唯一编码：sfm.api.openapi-agent.agent.openapi.agent.create
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/agent/create
- 文档版本：1787280870103

## 接口概述

创建智能体

创建智能体。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| agentName | String | 是 | Body | 智能体名称 | Test_custom |
| agentDesc | String | 是 | Body | 智能体描述 | Test_custom_desc |
| templateCode | String | 否 | Body | 智能体业务模板(对应业务类型),默认是custom | 系统内置模<br> agentBot: 3b8628cc51544996908b6ea55ae07bc2<br> agentAutoX-agentBi:653fe21f9dad4ab6ac01e6d14455ac03  <br>agentAutoX-agentVideo: 6bbab5fbc0c34f5fba6ab028dffc9816  <br>agentAutoX-agentDoc: f3e52770a81a4b9388bbe74ba440be88  <br>agentTrekClaw: 3b8628cc51544996908b6ea55ae07111 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.agentCode | String | 是 | Body | 智能体唯一编码 | a9c81580-8e93-42e1-b331-5cc6506c0093 |
| data.agentName | String | 是 | Body | 智能体名称 | DB 随表召回 |
| data.agentDesc | String | 是 | Body | 智能体描述 | DB 随表召回 |
| data.workspaceCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.gmtCreate | String | 是 | Body | 创建时间 | 2025-08-29T11:43:54.722+00:00 |
| data.gmtModified | String | 是 | Body | 修改时间 | 2025-08-29T11:43:54.722+00:00 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/agent/create' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"agentName": "DB 随表召回","agentDesc": "DB 随表召回"}'
```


## 响应示例

#### 返回数据

```json
{
  "errorMessages": [],
  "success": true,
  "data": {
    "id": 189,
    "gmtCreate": "2025-11-11T12:00:00.308+00:00",
    "gmtModified": "2025-11-11T12:00:00.308+00:00",
    "tenant": "fmthktsjdb",
    "agentCode": "9456fd9d-1a55-43b0-b383-f1331e81e69d",
    "agentName": "testAgent",
    "agentDesc": "test",
    "icon": null,
    "label": null,
    "developer": {
      "id": null,
      "gmtCreate": null,
      "gmtModified": null,
      "tenant": null,
      "uniqueCode": "7b7d340c8ec04c9db0c8c072e3d5e690",
      "source": null,
      "outerId": null,
      "name": "daily_root"
    },
    "pd": {
      "id": null,
      "gmtCreate": null,
      "gmtModified": null,
      "tenant": null,
      "uniqueCode": "7b7d340c8ec04c9db0c8c072e3d5e690",
      "source": null,
      "outerId": null,
      "name": "daily_root"
    },
    "outputVersions": null,
    "workspaceCode": "fmthktsjdb",
    "agentApiLimitConfig": null
  },
  "errorCode": null,
  "errorMsg": null,
  "extraData": null,
  "traceId": null,
  "env": null,
  "other": null,
  "firstErrorMessage": null,
  "failure": false
}
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

- apiCode：agent.openapi.agent.create
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-OPERATE
- serviceRegion：ctl
