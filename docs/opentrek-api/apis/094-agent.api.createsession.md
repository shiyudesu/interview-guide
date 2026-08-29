# 创建session

- 文档序号：094
- 分类：应用集成类 / 智能体 / 创建session
- 唯一编码：sfm.api.agent.agent.api.createsession
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/createSession
- 文档版本：1787280869659

## 接口概述

您可以通过接口创建一个全新的agent会话，可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

先进入菜单[主页->点击头像->APP_KEY]创建APP_KEY;然后进入 智能体页面,完成智能体配置,获取智能体编码和版本编码或者配置输出版本

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| agentCode | string | 是 | body | 智能体编码 | e36a0ab1-b673-49d0-9534-1480a147c691 |
| agentVersion | string | 否 | body | 智能体版本 | 1706863858334 |
| memoryUserId | string | 否 | body | 记忆体-用户记忆分区里, 用于区分用户的标识, 与平台用户ID无关, 仅用于记忆体-用户记忆分区里隔离每个用户标识的记忆, 只在该智能体使用记忆体时生效, 传递时会按该字段生成隔离的记忆, 不传递时本会话不会生成用户记忆, 适用于客户需要根据自己的用户系统生成用户记忆的场景 | 6572d7dd5f914240a1bacacede483499 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 是否成功 | true |
| data | object | 是 | body | 返回数据 | {"uniqueCode":"4bcaa882-9c54-4b78-9057-54db58591b5b"} |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/createSession \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-d '{
    "agentCode": "",
    "agentVersion": ""
}'
```


## 响应示例

#### 非流式输出

```json
{
	"success": true,
	"data": {
		"uniqueCode": "4bcaa882-9c54-4b78-9057-54db58591b5b"
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

- apiCode：agent.api.createsession
- groupCode：AGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
