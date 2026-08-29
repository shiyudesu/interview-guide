# 查询单个任务详情

- 文档序号：107
- 分类：应用集成类 / TrekAgent / 查询单个任务详情
- 唯一编码：sfm.api.auto-agent.agent.auto.new.open.task.desc
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/desc
- 文档版本：1787280869779

## 接口概述

根据taskId查询单个任务的详细信息，包括任务状态、标题、描述、耗时等。

taskId参数必填。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| taskId | string | 是 | body | 任务ID | 4bcaa882-9c54-4b78-9057-54db58591b5b |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 是否成功 | true |
| data | object | 是 | body | 任务详情 | {"taskId":"xxx","sessionId":"xxx","status":"RUNNING","name":"任务标题","desc":"任务描述"} |
| data.taskId | string | 是 | body | 任务ID | 4bcaa882-9c54-4b78-9057-54db58591b5b |
| data.sessionId | string | 是 | body | Agent会话ID | de454297-c547-440f-ae55-057a83a2d121 |
| data.status | string | 是 | body | 任务状态 | RUNNING |
| data.name | string | 否 | body | 任务标题 | 任务标题 |
| data.desc | string | 否 | body | 任务描述 | 任务描述 |
| data.createDate | string | 否 | body | 创建时间 | 2024-01-01 00:00:00 |
| data.readStatus | boolean | 否 | body | 最新状态是否已读 | true |
| data.spendSeconds | integer | 否 | body | 耗时（秒） | 12 |
| data.solutionCode | string | 否 | body | 解决方案编码 |  |
| data.contextUsage | object | 否 | body | 上下文使用情况 | {} |
| errorCode | string | 否 | body | 错误码 |  |
| errorMsg | string | 否 | body | 错误信息 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/desc \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-d '{
    "taskId": "4bcaa882-9c54-4b78-9057-54db58591b5b"
}'
```


## 响应示例

#### 非流式输出

```json
{
	"success": true,
	"data": {
		"taskId": "4bcaa882-9c54-4b78-9057-54db58591b5b",
		"sessionId": "de454297-c547-440f-ae55-057a83a2d121",
		"status": "RUNNING",
		"name": "任务标题",
		"desc": "任务描述",
		"createDate": "2024-01-01 00:00:00",
		"readStatus": true,
		"spendSeconds": 12,
		"solutionCode": "",
		"contextUsage": {}
	},
	"errorCode": null,
	"errorMsg": null
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
| 404 | GATEWAY ROUTE URL NOT FOUND! | 无效的目标服务地址 |
| 401 | GATEWAY LIMIT ! | 服务链接已达上限,请稍后再试 |
| 500 | TARGET_SERVICE_ERROR_CONNECTION_REFUSE_EXCEPTION | 目标服务拒绝连接 |
| 500 | TARGET_SERVICE_ERROR_NO_RESPONSE_EXCEPTION | 目标服务无响应 |



## 原始文档标识

- apiCode：agent.auto.new.open.task.desc
- groupCode：AUTO-AGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
