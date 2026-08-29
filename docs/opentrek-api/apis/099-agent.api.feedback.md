# 调用结果反馈

- 文档序号：099
- 分类：应用集成类 / 智能体 / 调用结果反馈
- 唯一编码：sfm.api.agent.agent.api.feedback
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/feedback
- 文档版本：1787280869705

## 接口概述

您可以针对Agent单次执行的结果进行反馈, 也可以针对本次执行的某个任务进行反馈



## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| sessionId | string | 是 | Body | 会话ID |  |
| requestId | string | 是 | Body | 请求ID |  |
| taskId | string | 是 | Body | 任务ID |  |
| uniqueCode | string | 否 | Body | 唯一ID, 更新反馈信息时传入 |  |
| subject | string | 是 | Body | 反馈对象 | REQUEST-针对单次run的结果输出进行反馈, TASK-针对本次run中执行的某个任务进行反馈 |
| provider | object | 是 | Body | 反馈者 |  |
| provider.source | string | 是 | Body | 反馈者来源 | USER-用户, AUTO_EVALUATION-评测中心 |
| provider.extendInfo | object | 否 | Body | 反馈者扩展信息 |  |
| vote | string | 是 | Body | 反馈结果 | LIKE-点赞, DISLIKE-点踩, NEUTRAL-中立 |
| extCommentsInfo | object | 否 | Body | 反馈结果扩展信息 |  |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 是否成功 |  |
| data | object | 是 | body | 反馈信息 |  |
| data.sessionId | string | 是 | Body | 会话ID |  |
| data.requestId | string | 是 | Body | 请求ID |  |
| data.taskId | string | 是 | Body | 任务ID |  |
| data.uniqueCode | string | 是 | Body | 唯一ID |  |
| data.subject | string | 是 | Body | 反馈对象 | REQUEST-针对单次run的结果输出进行反馈, TASK-针对本次run中执行的某个任务进行反馈 |
| data.provider | object | 是 | Body | 反馈者 |  |
| data.provider.source | string | 是 | Body | 反馈者来源 | USER-用户, AUTO_EVALUATION-评测中心 |
| data.provider.extendInfo | object | 否 | Body | 反馈者扩展信息 |  |
| data.vote | string | 是 | Body | 反馈结果 | LIKE-点赞, DISLIKE-点踩, NEUTRAL-中立 |
| data.extCommentsInfo | object | 否 | Body | 反馈结果扩展信息 |  |
| errorCode | string | 是 | body | 错误码 |  |
| errorMsg | string | 是 | body | 错误码 |  |


## 请求示例

#### curl命令示例

```bash
curl --location --request POST 'http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/feedback' \
--header 'Authorization: Bearer YOUR_APP_KEY' \
--header 'Content-Type: application/json' \
-d '{
    "sessionId": "87302f04-7617-41e4-b4c9-9028c3341dcg",
    "requestId": "e359512f-ba3a-46a7-b412-882d7e9f8b32",
    "taskId": "61e60082-690c-4548-a7ef-28d1ff6bb0f9",
    "subject": "TASK",
    "provider": {
        "source": "USER",
        "extendInfo": {}
    },
    "vote": "LIKE",
    "extCommentsInfo": {
        "comment": "123"
    }
}'
```


## 响应示例

#### 输出

```json
{
  "errorMessages": [],
  "success": true,
  "data": {
    "tenant": null,
    "sessionId": "87302f04-7617-41e4-b4c9-9028c3341dcg",
    "requestId": "e359512f-ba3a-46a7-b412-882d7e9f8b32",
    "taskId": "61e60082-690c-4548-a7ef-28d1ff6bb0f9",
    "subject": "TASK",
    "uniqueCode": "b8f5ea27-50f7-4147-88d1-9d02ccbf0061",
    "provider": {
      "source": "USER",
      "extendInfo": {}
    },
    "vote": "LIKE",
    "extCommentsInfo": {
      "comment": "123"
    }
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

- apiCode：agent.api.feedback
- groupCode：AGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
