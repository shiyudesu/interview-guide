# 查询智能体模版详情

- 文档序号：038
- 分类：平台功能类 / 智能体管理 / 智能体模版 / 查询智能体模版详情
- 唯一编码：sfm.api.openapi-agent.agent.openapi.template.getone
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/template/getOne
- 文档版本：1787280870295

## 接口概述

查询智能体模版详情

查询智能体模版详情。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| itemCode | String | 是 | Body | 模版编码 | 3b7628cc51544996908b6ea55ae07bc1 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.itemCode | String | 是 | Body | 模版编码 | 3b7628cc51544996908b6ea55ae07bc1 |
| data.itemName | String | 是 | Body | 模版名称 | 对话助手 |
| data.agentDesc | String | 是 | Body | 智能体描述 | DB 随表召回 |
| data.marketCode | String | 是 | Body | 模版类型，system=平台模版，common=自定义模版 | system |
| data.showDetail | Object | 是 | Body | 模版详情 |  |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/template/getOne' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"itemCode": "3b7628cc51544996908b6ea55ae07bc1"}'
```


## 响应示例

#### 返回数据

```json
{
  "errorMessages": [],
  "success": true,
  "data": {
    "marketCode": "system",
    "marketName": "自定义模版",
    "itemCode": "3b7628cc51544996808b6ea55ae07bc1",
    "itemName": "AutoBot对话助手",
    "itemLabels": [
      "系统内置"
    ],
    "itemType": "agentTemplate",
    "targetCode": "851d5b0b-8393-497c-b909-1d3209efee74",
    "targetName": "v1.0",
    "targetVersion": "1731573095677",
    "status": "online",
    "statusDesc": "已上架",
    "operatorId": null,
    "operatorName": null,
    "showDetail": {
      "skills": [
        "支持接入用户已有业务api",
        "支持OneRag插件联动用户业务数据",
        "支持接入其他智能体实例"
      ],
      "usage": {
        "attachment": {},
        "configDesc": "无",
        "limitDesc": "无"
      },
      "description": "综合问答能力",
      "interfaceInfo": {
        "inputParams": [
          {
            "example": "bd962db7-b1c8-4466-a2cc-41b9b67cd94b 创建session接口的返回值uniqueCode",
            "label": "sessionId",
            "name": "sessionId",
            "necessary": true,
            "type": "STRING"
          },
          {
            "example": "true",
            "label": "是否流式",
            "name": "stream",
            "necessary": true,
            "type": "BOOL"
          },
          {
            "example": "true 默认每次输出新内容,不包含前序输出的文本",
            "label": "当stream=true,控制是否不追加新文本",
            "name": "delta",
            "necessary": true,
            "type": "BOOL"
          },
          {
            "example": "false 默认不返回trace记录",
            "label": "当trace=true,控制是否返回trace记录",
            "name": "trace",
            "necessary": false,
            "type": "BOOL"
          },
          {
            "children": [
              {
                "example": "帮我订一张明天从上海去苏黎世的机票",
                "label": "对话输入",
                "name": "text",
                "necessary": true,
                "type": "STRING"
              },
              {
                "example": "{}",
                "label": "扩展信息",
                "name": "metadata",
                "necessary": false,
                "type": "OBJECT"
              },
              {
                "children": [
                  {
                    "example": "{}",
                    "label": "附件地址",
                    "name": "url",
                    "necessary": true,
                    "type": "STRING"
                  },
                  {
                    "example": "{}",
                    "label": "附件名称",
                    "name": "name",
                    "necessary": false,
                    "type": "STRING"
                  }
                ],
                "example": "[]",
                "label": "附件信息",
                "name": "attachments",
                "necessary": false,
                "type": "LIST<Object>"
              }
            ],
            "example": "{\"text\":\"帮我订一张明天从上海去苏黎世的机票\",\"metadata\":{}, \"attachments\":[{\"url\":\"\",\"name\":\"\"}]}",
            "label": "请求消息体",
            "name": "message",
            "necessary": true,
            "type": "OBJECT"
          }
        ],
        "interfaceDesc": "无",
        "outputParams": [
          {
            "example": "message.delta 输出文本块 \n thought.delta 思考过程块   \n  error 错误信息",
            "label": "数据类型",
            "name": "object",
            "necessary": true,
            "type": "STRING"
          },
          {
            "example": "assistant",
            "label": "角色",
            "name": "role",
            "necessary": true,
            "type": "STRING"
          },
          {
            "example": "object=message.delta场景 : {\"type\":\"text\",\"text\":{\"value\":\"智能体回答内容增量\"}}\nobject=thought.delta场景 : {\"type\":\"text\",\"data\":\"思考内容增量\"}\n object=error场景 {\"errorMsg\": \"错误信息内容\"} \n",
            "label": "数据内容",
            "name": "content",
            "necessary": true,
            "type": "OBJECT"
          },
          {
            "example": "{\"key\":\"value\"}",
            "label": "扩展字段",
            "name": "metadata",
            "necessary": false,
            "type": "OBJECT"
          },
          {
            "example": "false|true",
            "label": "流式(object=message.delta)场景 标记文本输出是否结束",
            "name": "end",
            "necessary": true,
            "type": "BOOL"
          },
          {
            "example": "-",
            "label": "当前会话ID",
            "name": "sessionId",
            "necessary": true,
            "type": "STRING"
          },
          {
            "example": "-",
            "label": "当前运行的请求ID",
            "name": "requestId",
            "necessary": true,
            "type": "STRING"
          },
          {
            "example": "true",
            "label": "非流式-业务是否成功",
            "name": "success",
            "necessary": true,
            "type": "BOOL"
          },
          {
            "children": [
              {
                "children": [
                  {
                    "example": "assistant",
                    "label": "角色",
                    "name": "role",
                    "necessary": true,
                    "type": "STRING"
                  },
                  {
                    "example": "{\"key\":\"value\"}",
                    "label": "扩展字段",
                    "name": "metadata",
                    "necessary": false,
                    "type": "OBJECT"
                  },
                  {
                    "children": [
                      {
                        "example": "text|image",
                        "label": "输出内容类型",
                        "name": "type",
                        "necessary": true,
                        "type": "STRING"
                      },
                      {
                        "children": [
                          {
                            "example": "你好！有什么我能帮助你的吗？",
                            "label": "输出文本",
                            "name": "value",
                            "necessary": true,
                            "type": "STRING"
                          }
                        ],
                        "example": "{}",
                        "label": "type=text 场景的输出结构",
                        "name": "text",
                        "necessary": true,
                        "type": "OBJECT"
                      },
                      {
                        "children": [
                          {
                            "example": "",
                            "label": "输出图片的地址",
                            "name": "url",
                            "necessary": true,
                            "type": "STRING"
                          }
                        ],
                        "example": "{}",
                        "label": "type=image 场景的输出结构",
                        "name": "image",
                        "necessary": true,
                        "type": "OBJECT"
                      }
                    ],
                    "example": "",
                    "label": "输出内容",
                    "name": "content",
                    "necessary": true,
                    "type": "LIST<Object>"
                  }
                ],
                "example": "{}",
                "label": "非流式-输出文本响应",
                "name": "message",
                "necessary": false,
                "type": "OBJECT"
              },
              {
                "children": [
                  {
                    "example": "assistant",
                    "label": "角色",
                    "name": "role",
                    "necessary": true,
                    "type": "STRING"
                  },
                  {
                    "children": [
                      {
                        "example": "",
                        "label": "输出文本",
                        "name": "data",
                        "necessary": true,
                        "type": "STRING"
                      },
                      {
                        "example": "text",
                        "label": "输出内容类型,目前是常量 text",
                        "name": "type",
                        "necessary": true,
                        "type": "STRING"
                      }
                    ],
                    "example": "",
                    "label": "输出内容",
                    "name": "content",
                    "necessary": true,
                    "type": "OBJECT"
                  }
                ],
                "example": "{}",
                "label": "非流式-输出思考响应",
                "name": "thoughts",
                "necessary": false,
                "type": "OBJECT"
              }
            ],
            "example": "{}",
            "label": "非流式-业务响应",
            "name": "data",
            "necessary": false,
            "type": "OBJECT"
          },
          {
            "example": "true",
            "label": "非流式-业务错误码",
            "name": "errorCode",
            "necessary": false,
            "type": "BOOL"
          },
          {
            "example": "true",
            "label": "非流式-业务错误描述",
            "name": "errorMsg",
            "necessary": false,
            "type": "BOOL"
          }
        ]
      },
      "type": "platform"
    },
    "config": null,
    "feature": {
      "templateType": "AutoBot"
    },
    "operateControl": null
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

- apiCode：agent.openapi.template.getone
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-TEMPLATE
- serviceRegion：ctl
