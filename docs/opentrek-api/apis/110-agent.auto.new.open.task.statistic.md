# 统计任务状态

- 文档序号：110
- 分类：应用集成类 / TrekAgent / 统计任务状态
- 唯一编码：sfm.api.auto-agent.agent.auto.new.open.task.statistic
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/statistic
- 文档版本：1787280869822

## 接口概述

统计任务状态信息，包括各状态任务数量、未读数量及近7天/30天失败率。

solutionCode、digitalCode参数可选，用于筛选特定方案或业务下的任务统计。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| solutionCode | string | 否 | body | 方案编码 | solution-abc123 |
| digitalCode | string | 否 | body | 数字人编码 | digital-001 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 是否成功 | true |
| data | object | 是 | body | 统计数据 | {} |
| data.reasoningQuantity | integer | 是 | body | 推理中任务数 | 5 |
| data.completedQuantity | integer | 是 | body | 已完成任务数 | 20 |
| data.failedQuantity | integer | 是 | body | 失败任务数 | 2 |
| data.cancelQuantity | integer | 是 | body | 已取消任务数 | 1 |
| data.intentionClarificationQuantity | integer | 是 | body | 意图澄清任务数 | 3 |
| data.unreadReasoningQuantity | integer | 是 | body | 未读推理中任务数 | 2 |
| data.unreadCompletedQuantity | integer | 是 | body | 未读已完成任务数 | 5 |
| data.unreadFailedQuantity | integer | 是 | body | 未读失败任务数 | 1 |
| data.unreadIntentionClarificationQuantity | integer | 是 | body | 未读意图澄清任务数 | 0 |
| data.recentSevenDaysTotalCount | integer | 是 | body | 近7天总任务数 | 50 |
| data.recentSevenDaysFailedCount | integer | 是 | body | 近7天失败任务数 | 3 |
| data.recentSevenDaysFailureRate | number | 是 | body | 近7天失败率 | 0.06 |
| data.recentThirtyDaysTotalCount | integer | 是 | body | 近30天总任务数 | 200 |
| data.recentThirtyDaysFailedCount | integer | 是 | body | 近30天失败任务数 | 10 |
| data.recentThirtyDaysFailureRate | number | 是 | body | 近30天失败率 | 0.05 |
| errorCode | string | 否 | body | 错误码 |  |
| errorMsg | string | 否 | body | 错误信息 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/statistic \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-d '{
    "solutionCode": "solution-abc123",
    "digitalCode": "digital-001"
}'
```


## 响应示例

#### 非流式输出

```json
{
	"success": true,
	"data": {
		"reasoningQuantity": 5,
		"completedQuantity": 20,
		"failedQuantity": 2,
		"cancelQuantity": 1,
		"intentionClarificationQuantity": 3,
		"unreadReasoningQuantity": 2,
		"unreadCompletedQuantity": 5,
		"unreadFailedQuantity": 1,
		"unreadIntentionClarificationQuantity": 0,
		"recentSevenDaysTotalCount": 50,
		"recentSevenDaysFailedCount": 3,
		"recentSevenDaysFailureRate": 0.06,
		"recentThirtyDaysTotalCount": 200,
		"recentThirtyDaysFailedCount": 10,
		"recentThirtyDaysFailureRate": 0.05
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

- apiCode：agent.auto.new.open.task.statistic
- groupCode：AUTO-AGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
