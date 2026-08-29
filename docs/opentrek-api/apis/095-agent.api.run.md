# 发起agent调用

- 文档序号：095
- 分类：应用集成类 / 智能体 / 发起agent调用
- 唯一编码：sfm.api.agent.agent.api.run
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/run
- 文档版本：1787280869673

## 接口概述

您可以通过接口在已有会话的基础上对agent进行提问，可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

先进入菜单[主页->点击头像->APP_KEY]创建APP_KEY;然后调用'创建session'接口获取返回值 uniqueCode

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| sessionId | String | 是 | body | sessionId | bd962db7-b1c8-4466-a2cc-41b9b67cd94b 创建session接口的返回值uniqueCode |
| stream | Boolean | 是 | body | 是否流式 | true |
| delta | Boolean | 是 | true | 当stream=true,控制是否不追加新文本 | true 默认每次输出新内容,不包含前序输出的文本 |
| trace | Boolean | 否 | true | 当trace=true,控制是否返回trace记录 | false 默认不返回trace记录 |
| message | object | 是 | body | 请求消息体 | {"text":"帮我订一张明天从上海去苏黎世的机票","metadata":{}, "attachments":[{"url":"","name":""}]} |
| message.text | string | 是 | body | 对话输入 | 帮我订一张明天从上海去苏黎世的机票 |
| message.metadata | Map | 否 | body | 扩展信息 | {} |
| message.attachments | List<Object> | 否 | body | 附件信息 | [] |
| message.attachments.url | string | 是 | body | 附件地址 | {} |
| message.attachments.name | string | 否 | body | 附件名称 | {} |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| object | string | 是 | body | 数据类型 | message.delta 输出文本块 <br> thought.delta 思考过程块   <br>  error 错误信息 |
| role | string | 是 | body | 角色 | assistant |
| content | object | 是 | body | 数据内容 | object=message.delta场景 : {"type":"text","text":{"value":"智能体回答内容增量"}}<br>object=thought.delta场景 : {"type":"text","data":"思考内容增量"}<br> object=error场景 {"errorMsg": "错误信息内容"} <br> |
| metadata | object | 否 | body | 扩展字段 | {"key":"value"} |
| end | Boolean | 是 | body | 流式(object=message.delta)场景 标记文本输出是否结束 | false\|true |
| sessionId | string | 是 | body | 当前会话ID | - |
| requestId | string | 是 | body | 当前运行的请求ID | - |
| id | object | 是 | body | 流式消息的业务唯一ID | 思考内容唯一ID\|最终答案信息的唯一ID; <br> 思考内容支持在问答结束前输出多个,业务侧有多流输出的场景,可以进一步根据自定义的id前缀来区分呈现 |
| success | Boolean | 是 | body | 非流式-业务是否成功 | true |
| data | object | 否 | body | 非流式-业务响应 | {} |
| data.message | object | 否 | body | 非流式-输出文本响应 | {} |
| data.message.role | string | 是 | body | 角色 | assistant |
| data.message.metadata | object | 否 | body | 扩展字段 | {"key":"value"} |
| data.message.content | List<Object> | 是 | body | 输出内容 |  |
| data.message.content.type | String | 是 | body | 输出内容类型 | text\|image |
| data.message.content.text | JSONObject | 是 | body | type=text 场景的输出结构 | {} |
| data.message.content.text.value | String | 是 | body | 输出文本 | 你好！有什么我能帮助你的吗？ |
| data.message.content.image | JSONObject | 是 | body | type=image 场景的输出结构 | {} |
| data.message.content.image.url | String | 是 | body | 输出图片的地址 |  |
| data.thoughts | object | 否 | body | 非流式-输出思考响应 | {} |
| data.thoughts.role | string | 是 | body | 角色 | assistant |
| data.thoughts.content | object | 是 | body | 输出内容 |  |
| data.thoughts.content.data | String | 是 | body | 输出文本 |  |
| data.thoughts.content.type | String | 是 | body | 输出内容类型,目前是常量 text | text |
| errorCode | Boolean | 否 | body | 非流式-业务错误码 | true |
| errorMsg | Boolean | 否 | body | 非流式-业务错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/run \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-d '{
    "stream":true,
    "delta":true,
    "sessionId": "7af650e7-ed57-498d-8081-fe1dea5361fa",
    "message":{
        "text":"帮我订一张明天从上海去苏黎世的机票",
        "metadata":{},
        "attachments":[]
    }
}'
```


## 响应示例

#### 流式输出

```bash
data: {"object": "message.delta","end":false,"role": "assistant","sessionId":"de454297-c547-440f-ae55-057a83a2d121","content": [{"type":"text","text": {"value": "智能体回答内容增量"}}],"metadata": {"key": "value"}}

data: {"object": "thought.delta","role": "assistant","sessionId":"de454297-c547-440f-ae55-057a83a2d121","content": {"type":"text","data":"思考内容增量"}}

data: {"object": "error","role": "assistant","sessionId":"de454297-c547-440f-ae55-057a83a2d121","content": {"errorMsg": "错误信息内容"}}

data:{"content":{"data":"您好","type":"text"},"id":"323ef0f2f57e445fbec343f62441c608","object":"thought.delta"}
data:{"content":{"data":"！","type":"text"},"id":"323ef0f2f57e445fbec343f62441c608","object":"thought.delta"}
data:{"content":{"data":"请问","type":"text"},"id":"323ef0f2f57e445fbec343f62441c608","object":"thought.delta"}
data:{"content":{"data":"有什么可以帮助您的？","type":"text"},"id":"323ef0f2f57e445fbec343f62441c608","object":"thought.delta"}
data:{"content":{"data":"","type":"text"},"id":"323ef0f2f57e445fbec343f62441c608","object":"thought.delta"}
data:{"content":[{"text":{"value":"您好"},"type":"text"}],"end":false,"gmtCreate":"2024-09-19 11:52:56.012","id":"9b0a21677f4a4512935c0e96977f292b","metadata":{},"requestId":"6d511a54-d95f-419c-9d34-02e86ea050e4","role":"assistant","sessionId":"7af650e7-ed57-498d-8081-fe1dea5361fa","useage":{"uiTaskId":"23ce3bf3-5248-4293-8326-bdb7f452a092"},"object":"message.delta"}
data:{"content":[{"text":{"value":"！"},"type":"text"}],"end":false,"gmtCreate":"2024-09-19 11:52:56.012","id":"9b0a21677f4a4512935c0e96977f292b","metadata":{},"requestId":"6d511a54-d95f-419c-9d34-02e86ea050e4","role":"assistant","sessionId":"7af650e7-ed57-498d-8081-fe1dea5361fa","useage":{"uiTaskId":"23ce3bf3-5248-4293-8326-bdb7f452a092"},"object":"message.delta"}
data:{"content":[{"text":{"value":"请问"},"type":"text"}],"end":false,"gmtCreate":"2024-09-19 11:52:56.012","id":"9b0a21677f4a4512935c0e96977f292b","metadata":{},"requestId":"6d511a54-d95f-419c-9d34-02e86ea050e4","role":"assistant","sessionId":"7af650e7-ed57-498d-8081-fe1dea5361fa","useage":{"uiTaskId":"23ce3bf3-5248-4293-8326-bdb7f452a092"},"object":"message.delta"}
data:{"content":[{"text":{"value":"有什么可以帮助您的？"},"type":"text"}],"end":false,"gmtCreate":"2024-09-19 11:52:56.012","id":"9b0a21677f4a4512935c0e96977f292b","metadata":{},"requestId":"6d511a54-d95f-419c-9d34-02e86ea050e4","role":"assistant","sessionId":"7af650e7-ed57-498d-8081-fe1dea5361fa","useage":{"uiTaskId":"23ce3bf3-5248-4293-8326-bdb7f452a092"},"object":"message.delta"}
data:{"content":[{"text":{"value":""},"type":"text"}],"end":true,"gmtCreate":"2024-09-19 11:52:56.012","id":"9b0a21677f4a4512935c0e96977f292b","metadata":{},"requestId":"6d511a54-d95f-419c-9d34-02e86ea050e4","role":"assistant","sessionId":"7af650e7-ed57-498d-8081-fe1dea5361fa","useage":{"uiTaskId":"23ce3bf3-5248-4293-8326-bdb7f452a092"},"object":"message.delta"}
```

#### 非流式输出

```json
{
	"success": true,
	"data": {
		"message": {
			"role": "assistant",
			"content": [{
				"type": "text",
				"text": {
					"value": "你好！有什么我能帮助你的吗？"
				}
			},{
				"type": "image",
				"image": {
					"url": ""
				}
			}],
			"metadata": null
		},
		"thoughts": [{
				"role": "assistant",
				"content": {
					"type": "text",
					"data": ""
				}
			}
		],
		"error": null
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

- apiCode：agent.api.run
- groupCode：AGENT
- catalogCode：DEFAULT
- serviceRegion：tenant
