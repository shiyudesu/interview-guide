# 发起agent调用

- 文档序号：115
- 分类：应用集成类 / 高码智能体 / 发起agent调用
- 唯一编码：sfm.api.highcodeagent.agent.highcode.process
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/highcode/process
- 文档版本：1787280869863

## 接口概述

您可以通过接口在已有会话的基础上对agent进行提问，可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

先进入菜单[主页->点击头像->APP_KEY]创建APP_KEY;然后调用'创建session'接口获取返回值 uniqueCode

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |
| x-sfm-security-business | string | 否 | Header | 智能体编码 | e36a0ab1-b673-49d0-9534-1480a147c691 |
| x-sfm-security-business-version | string | 否 | Header | 智能体版本编码 | 1706863858334 |
| x-session-id | string | 是 | Header | 会话ID | bd962db7-b1c8-4466-a2cc-41b9b67cd94b |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| user_id | string | 是 | body | 用户ID | test-user |
| session_id | string | 是 | body | 会话ID | bd962db7-b1c8-4466-a2cc-41b9b67cd94b |
| input | array | 是 | body | 输入消息数组 | [{"role":"user","content":[{"type":"text","text":"帮我订一张明天从上海去苏黎世的机票"}]}] |
| input.role | string | 是 | body | 角色 | user |
| input.type | string | 是 | body | 类型 | message |
| input.content | array | 是 | body | 内容数组 | [{"type":"text","text":"帮我订一张明天从上海去苏黎世的机票"}] |
| input.content.type | string | 是 | body | 内容类型 | text |
| input.content.text | string | 是 | body | 文本内容 | 你是谁 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| sequence_number | integer | 是 | body | 序列号 | 106 |
| object | string | 是 | body | 类型标识 | message 消息 <br> content 内容 <br> response 响应 |
| role | string | 否 | body | 角色 | assistant 助手 <br> tool 工具 <br> response 响应 |
| type | string | 否 | body | 类型 | data 数据 <br> text 文本 <br> message 消息 |
| status | string | 是 | body | 状态 | created 已创建 <br> in_progress 处理中 <br> completed 完成 <br> canceled 取消 <br> failed 失败 <br> rejected 拒绝 <br> unknown 未知 <br> queued 队列中 <br> incomplete 未完成 |
| error | object | 是 | body | 错误信息 | {"code":"AGENT_UNKNOWN_ERROR","message":"Unknown agent error: TypeError: query_func() got an unexpected keyword argument 'response'"} |
| created_at | long | 是 | body | 创建时间 | 1778641393 |
| completed_at | long | 是 | body | 完成时间 | 1778641450 |
| output | array | 否 | body | 输出 | [] |
| msg_id | string | 否 | body | 当前message的id | - |
| index | Integer | 否 | body | 当前message的index | 1 |
| success | Boolean | 是 | body | 非流式-业务是否成功 | true |
| data | object | 否 | body | 非流式-业务响应 | {} |
| data.message | object | 否 | body | 非流式-输出文本响应 | {} |
| data.message.created_at | long | 是 | body | 创建时间 | 1778641393 |
| data.message.completed_at | long | 是 | body | 完成时间 | 1779264309 |
| data.message.status | string | 否 | body | 状态 | completed 完成 <br> canceled 取消 <br> failed 失败 <br> rejected 拒绝 <br> unknown 未知 <br> queued 队列中 <br> incomplete 未完成 |
| data.message.content | List<Object> | 是 | body | 输出内容 |  |
| data.message.content.type | String | 是 | body | 输出内容类型 | reasoning <br> plugin_call <br> plugin_call_output etc |
| data.message.content.object | String | 是 | body | 输出内容类型 | message |
| data.message.content.text | String | 是 | body | 输出内容 | The result of adding 5 and 2 is **7**.\n\nThe calculation was successful (return code 0), and the sum is correctly computed as 7. |
| error | object | 否 | body | 非流式-业务错误 | {"code":"AGENT_UNKNOWN_ERROR","message":"Unknown agent error: TypeError: query_func() got an unexpected keyword argument 'response'"} |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/highcode/process \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-session-id: ${sessionId}' \
-d '{
    "user_id":"test-user",
    "session_id":"${sessionId}",
    "input":[{"role":"user","content":[{"type":"text","text":"帮我订一张明天从上海去苏黎世的机票"}]}
]}'
```


## 响应示例

#### 流式输出

```bash
data: {"sequence_number": 106,"object": "response","status": "completed","id": "msg_aeee66dd","output": [{"sequence_number": 49,"object": "response","status": "completed","id": "msg_08b954e0","type": "reasoning","role": "assistant", "content": [{"object": "content","status": "completed","type": "text","index": 0,"text": "智能体回答内容增量"}] }]}

data: {"sequence_number": 31,"object": "response","status": "in_progress","error": null, "type": "text","index": 0,"delta": true,"text": "   - Offer assistance"}

data: {"object": "response","error": {"message": "错误信息内容", "code": "CODE-1" }}


```

#### 非流式输出

```json
{"sequence_number":62,"object":"response","status":"completed","error":null,"id":"response_6dbe7725-b28d-43dc-848b-72911155505e","created_at":1781269937,"completed_at":1781271668,"output":[{"sequence_number":60,"object":"message","status":"completed","error":null,"id":"msg_5c2c5800-d148-49b0-9c6a-3a91cc844229","type":"reasoning","role":"assistant","content":[{"sequence_number":59,"object":"content","status":"completed","error":null,"type":"text","index":0,"delta":null,"msg_id":"msg_5c2c5800-d148-49b0-9c6a-3a91cc844229","text":"Thinking Process:\n\n1.  **Analyze User Input:** The user said \"你好\" (Hello).\n2.  **Identify Intent:** The user is initiating a conversation.\n3.  **Determine Response:** I should greet the user back, introduce myself as Friday (based on the system prompt), and ask how I can help them.\n4.  **Draft Response (Internal Monologue):** \"你好！我是Friday。有什么我可以帮你的吗？\" (Hello! I'm Friday. How can I help you?)\n5.  **Final Polish:** Keep it friendly and concise.\n\nResponse: \"你好！我是Friday，很高兴为你服务。请问有什么我可以帮你的吗？\" (Hello! I am Friday, happy to serve you. Is there anything I can help you with?)"}],"code":null,"message":null,"usage":null,"metadata":null},{"sequence_number":61,"object":"message","status":"completed","error":null,"id":"msg_30b49c15-b0a0-4372-b515-331c019fdaf7","type":"message","role":"assistant","content":[{"sequence_number":null,"object":"content","status":null,"error":null,"type":"text","index":0,"delta":null,"msg_id":"msg_30b49c15-b0a0-4372-b515-331c019fdaf7","text":"你好！我是Friday，很高兴为你服务。请问今天有什么我可以帮你的吗？"},{"sequence_number":null,"object":"content","status":null,"error":null,"type":"text","index":1,"delta":null,"msg_id":"msg_30b49c15-b0a0-4372-b515-331c019fdaf7","text":""}],"code":null,"message":null,"usage":null,"metadata":null}],"usage":null,"session_id":"aaf41568-4000-46e4-872c-10cb6e4813f4","host":"10.244.86.196"}
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

- apiCode：agent.highcode.process
- groupCode：HighCodeAGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
