# 更新任务信息

- 文档序号：109
- 分类：应用集成类 / TrekAgent / 更新任务信息
- 唯一编码：sfm.api.auto-agent.agent.auto.new.open.task.update
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/update
- 文档版本：1787280869792

## 接口概述

根据taskId更新指定任务的信息，支持修改任务名称、状态和已读状态。

taskId参数必填；name、status、readStatus可选，按需传入需要更新的字段。

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
| name | string | 否 | body | 任务名称 | 我的任务 |
| status | string | 否 | body | 任务状态 | RUNNING |
| readStatus | boolean | 否 | body | 最新状态是否已读 | true |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 是否成功 | true |
| data | object | 是 | body | 返回数据 | {"result":true} |
| data.result | boolean | 是 | body | 更新结果 | true |
| errorCode | string | 否 | body | 错误码 |  |
| errorMsg | string | 否 | body | 错误信息 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/update \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-d '{
    "taskId": "4bcaa882-9c54-4b78-9057-54db58591b5b",
    "name": "我的任务",
    "status": "RUNNING",
    "readStatus": true
}'
```


## 响应示例

#### 非流式输出

```json
{
	"success": true,
	"data": {
		"result": true
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

- apiCode：agent.auto.new.open.task.update
- groupCode：AUTO-AGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
