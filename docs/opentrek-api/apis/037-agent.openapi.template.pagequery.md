# 查询智能体模版列表

- 文档序号：037
- 分类：平台功能类 / 智能体管理 / 智能体模版 / 查询智能体模版列表
- 唯一编码：sfm.api.openapi-agent.agent.openapi.template.pagequery
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/template/pageQuery
- 文档版本：1787280870288

## 接口概述

查询智能体模版列表

查询智能体模版列表。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| current | Integer | 是 | Body | 当前页数 | 1 |
| pageSize | Integer | 是 | Body | 每页条数 | 10 |
| name | String | 是 | Body | 模版名称模糊搜索 | 对话助手 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的模版总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的模版列表 |  |
| data.list.itemCode | String | 是 | Body | 模版编码 | 3b7628cc51544996908b6ea55ae07bc1 |
| data.list.itemName | String | 是 | Body | 模版名称 | 对话助手 |
| data.list.agentDesc | String | 是 | Body | 智能体描述 | DB 随表召回 |
| data.list.marketCode | String | 是 | Body | 模版类型，system=平台模版，common=自定义模版 | system |
| data.list.showDetail | Object | 是 | Body | 模版详情 |  |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/template/pageQuery' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"current": 1,"pageSize": 10,"name": "对话助手"}'
```


## 响应示例

#### 返回数据

```json
{
  "errorMessages": [],
  "success": true,
  "data": {
    "extInfos": {},
    "total": 1,
    "list": [
      {
        "marketCode": "common",
        "marketName": "自定义模版",
        "itemCode": "79d39852ceb148b9a0afe674a2e6d38d",
        "itemName": "whatsapp",
        "itemLabels": [
          "whatsapp"
        ],
        "itemType": "agentTemplate",
        "targetCode": "22bb7850-78b2-4ce7-b29d-682460f6a6ed",
        "targetName": "工具",
        "targetVersion": "1740037093657",
        "status": "online",
        "statusDesc": "已上架",
        "operatorId": null,
        "operatorName": null,
        "showDetail": {
          "usage": {
            "attachment": {},
            "configDesc": "whatsapp",
            "limitDesc": "whatsapp"
          },
          "icon": "AGENT_ICON_6",
          "abilityDependence": {},
          "description": "whatsapp",
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
            "interfaceDesc": "whatsapp",
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
          "type": "custom"
        },
        "config": {
          "toolDTOList": [],
          "agentCode": "22bb7850-78b2-4ce7-b29d-682460f6a6ed",
          "showConfig": "{\"edges\":[{\"id\":\"edge_cJ0uKN3zQB8yzAC4\",\"source\":\"node_C2qw-nUs7pkE8wbY\",\"target\":\"node_qKWAQMiRMjv5oyHa\",\"type\":\"link\"},{\"id\":\"edge_1i2eCp10VfIiw02O\",\"source\":\"node_qKWAQMiRMjv5oyHa\",\"target\":\"node_wTAJLIClOaIY4RP9\",\"type\":\"link\"},{\"id\":\"edge_A-tovC1DG_pKP1yd\",\"source\":\"node_wTAJLIClOaIY4RP9\",\"target\":\"node_t2f1AWNrVO2A6M8R\",\"type\":\"link\"},{\"id\":\"edge_s5nCSGi9FSVmx8FZ\",\"index\":1,\"source\":\"node_t2f1AWNrVO2A6M8R\",\"sourceHandle\":\"handle_9BYE3aCV\",\"target\":\"node_YC9Fee2I5E5FpkVO\",\"type\":\"link\"},{\"id\":\"edge_WKdn0owgbH8zo4Sr\",\"index\":0,\"source\":\"node_t2f1AWNrVO2A6M8R\",\"sourceHandle\":\"handle_0H7pMGRY\",\"target\":\"node_dIWgAFfb1bEkAp2J\",\"type\":\"link\"},{\"id\":\"edge_5h-urQDZmD6H5k3K\",\"source\":\"node_YC9Fee2I5E5FpkVO\",\"target\":\"node_wTAJLIClOaIY4RP9\",\"type\":\"link\"}],\"nodes\":[{\"data\":{\"config\":{},\"inMappings\":[{\"desc\":\"用户输入\",\"editable\":true,\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"text\",\"name\":\"text\",\"valueType\":\"STRING\"}],\"desc\":\"message\",\"name\":\"message\",\"valueType\":\"OBJECT\"}],\"desc\":\"OpenAPI\",\"name\":\"OPEN_API\"},\"name\":\"input\",\"necessary\":false,\"refType\":\"REF\",\"subMappings\":[],\"valueType\":\"STRING\"}],\"label\":\"开始\",\"name\":\"开始\",\"outMappings\":[{\"desc\":\"用户输入\",\"editable\":true,\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"text\",\"name\":\"text\",\"valueType\":\"STRING\"}],\"desc\":\"message\",\"name\":\"message\",\"valueType\":\"OBJECT\"}],\"desc\":\"OpenAPI\",\"name\":\"OPEN_API\"},\"name\":\"input\",\"necessary\":false,\"refType\":\"REF\",\"subMappings\":[],\"valueType\":\"STRING\"}],\"type\":\"startEvent\"},\"dragging\":false,\"height\":233,\"id\":\"node_C2qw-nUs7pkE8wbY\",\"name\":\"开始\",\"position\":{\"x\":-1139.8600266263104,\"y\":-284.33519556213093},\"positionAbsolute\":{\"x\":-1139.8600266263104,\"y\":-284.33519556213093},\"selected\":false,\"type\":\"startEvent\",\"width\":960},{\"data\":{\"config\":{\"projectCode\":\"1a7c834e-b8d5-4432-84c7-1d4cd7015ec7\",\"projectName\":\"hx空间\",\"prompt\":\"template\",\"stop\":[]},\"inMappings\":[{\"desc\":\"\",\"editable\":true,\"mappingTree\":{\"value\":\"oneUi_planning\",\"valueType\":\"STRING\"},\"name\":\"templateId\",\"necessary\":true,\"refType\":\"CONSTANT\",\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"\",\"editable\":true,\"mappingTree\":{\"value\":\"oneUi任务规划助手，具备生成式UI能力，通过技能解决用户问题\",\"valueType\":\"STRING\"},\"name\":\"role\",\"necessary\":true,\"refType\":\"CONSTANT\",\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"\",\"editable\":true,\"mappingTree\":{\"value\":\"无\",\"valueType\":\"STRING\"},\"name\":\"constraint\",\"necessary\":true,\"refType\":\"CONSTANT\",\"subMappings\":[],\"valueType\":\"STRING\"}],\"label\":\"任务规划\",\"name\":\"任务规划\",\"outMappings\":[{\"desc\":\"返回内容\",\"editable\":false,\"name\":\"content\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"SSTRING\"},{\"desc\":\"是否成功\",\"editable\":false,\"name\":\"success\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"错误码\",\"editable\":false,\"name\":\"errorCode\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"错误信息\",\"editable\":false,\"name\":\"errorMessage\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"STRING\"}],\"type\":\"LLM\"},\"dragging\":false,\"height\":1083,\"id\":\"node_qKWAQMiRMjv5oyHa\",\"name\":\"任务规划\",\"position\":{\"x\":43.518891372418125,\"y\":-461.99835700333324},\"positionAbsolute\":{\"x\":43.518891372418125,\"y\":-461.99835700333324},\"selected\":false,\"type\":\"LLM\",\"width\":960},{\"data\":{\"config\":{},\"inMappings\":[{\"desc\":\"组合任务输入\",\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"要获取的值\",\"name\":\"object\",\"valueMapping\":{\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"返回内容\",\"hasChildren\":false,\"name\":\"content\",\"valueType\":\"SSTRING\"}],\"desc\":\"观察任务\",\"hasChildren\":true,\"name\":\"node_YC9Fee2I5E5FpkVO\",\"valueType\":\"OBJECT\"}],\"desc\":\"节点\",\"hasChildren\":true,\"name\":\"NODE\"},\"refType\":\"REF\",\"valueType\":\"SSTRING\"}},{\"desc\":\"默认值\",\"name\":\"defaultValue\",\"valueMapping\":{\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"返回内容\",\"hasChildren\":false,\"name\":\"content\",\"valueType\":\"SSTRING\"}],\"desc\":\"任务规划\",\"hasChildren\":true,\"name\":\"node_qKWAQMiRMjv5oyHa\",\"valueType\":\"OBJECT\"}],\"desc\":\"节点\",\"hasChildren\":true,\"name\":\"NODE\"},\"refType\":\"REF\",\"valueType\":\"SSTRING\"}}],\"name\":\"params\"},{\"name\":\"returnType\"}],\"desc\":\"尝试获取参数，否则用指定的默认值\",\"name\":\"default(object, defaultValue)\"},\"name\":\"combinationParams\",\"necessary\":true,\"refType\":\"FUNCTION\",\"subMappings\":[{\"desc\":\"任务列表索引\",\"mappingTree\":{},\"name\":\"listIndex\",\"necessary\":false,\"sourceDisabled\":true,\"subMappings\":[],\"valueType\":\"NUMBER\"},{\"desc\":\"任务名称\",\"mappingTree\":{},\"name\":\"taskName\",\"necessary\":true,\"sourceDisabled\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"任务参数\",\"mappingTree\":{},\"name\":\"params\",\"necessary\":true,\"sourceDisabled\":true,\"subMappings\":[],\"valueType\":\"OBJECT\"}]}],\"label\":\"组合任务\",\"name\":\"组合任务\",\"outMappings\":[{\"desc\":\"组合任务结果列表\",\"name\":\"combinationTaskResult\",\"necessary\":false,\"subMappings\":[{\"desc\":\"节点内批次索引\",\"name\":\"listIndex\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"NUMBER\"},{\"desc\":\"任务名称\",\"name\":\"taskName\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"是否流式\",\"name\":\"isStream\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"BOOL\"},{\"desc\":\"是否成功\",\"name\":\"success\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"BOOL\"},{\"desc\":\"错误信息\",\"name\":\"errorMessage\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"错误码\",\"name\":\"errorCode\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"输出内容\",\"name\":\"content\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"扩展内容\",\"name\":\"extContent\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"系统日志\",\"name\":\"sysLog\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"AI理解\",\"name\":\"thought\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"任务ID\",\"name\":\"taskId\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"元数据\",\"name\":\"metadata\",\"necessary\":false,\"skipReference\":true,\"subMappings\":[],\"valueType\":\"OBJECT\"}],\"valueType\":\"LIST_OBJECT\"},{\"desc\":\"是否最终答案\",\"name\":\"isFinalAnswer\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"BOOL\"},{\"desc\":\"最终答案内容\",\"name\":\"content\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"SSTRING\"}],\"type\":\"COMBINATION_TASKS_TOOL\"},\"dragging\":false,\"height\":1144,\"id\":\"node_wTAJLIClOaIY4RP9\",\"name\":\"组合任务\",\"position\":{\"x\":1376.8877132330133,\"y\":-472.2533589715337},\"positionAbsolute\":{\"x\":1376.8877132330133,\"y\":-472.2533589715337},\"selected\":true,\"type\":\"COMBINATION_TASKS_TOOL\",\"width\":960},{\"data\":{\"config\":{\"rules\":[{\"lineId\":\"handle_0H7pMGRY\",\"ruleMode\":\"RULE\",\"ruleUnion\":{\"andRules\":[],\"orRules\":[{\"leftMapping\":{\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"是否最终答案\",\"hasChildren\":false,\"name\":\"isFinalAnswer\",\"valueType\":\"BOOL\"}],\"desc\":\"组合任务\",\"hasChildren\":true,\"name\":\"node_wTAJLIClOaIY4RP9\",\"valueType\":\"OBJECT\"}],\"desc\":\"节点\",\"hasChildren\":true,\"name\":\"NODE\"},\"refType\":\"REF\",\"valueType\":\"BOOL\"},\"rightMapping\":{\"mappingTree\":{\"value\":\"true\"},\"refType\":\"CONSTANT\"},\"type\":\"EQ\"}],\"source\":{}}},{\"isDefault\":true,\"lineId\":\"handle_9BYE3aCV\",\"ruleMode\":\"RULE\"}]},\"inMappings\":[],\"label\":\"选择器\",\"name\":\"选择器\",\"outMappings\":[],\"type\":\"exclusiveGateway\"},\"dragging\":false,\"height\":321,\"id\":\"node_t2f1AWNrVO2A6M8R\",\"name\":\"选择器\",\"position\":{\"x\":2429.428745682999,\"y\":-119.57165030607675},\"positionAbsolute\":{\"x\":2429.428745682999,\"y\":-119.57165030607675},\"selected\":false,\"type\":\"exclusiveGateway\",\"width\":680},{\"data\":{\"config\":{\"projectCode\":\"1a7c834e-b8d5-4432-84c7-1d4cd7015ec7\",\"projectName\":\"hx空间\",\"prompt\":\"template\",\"stop\":[]},\"inMappings\":[{\"desc\":\"用户输入\",\"editable\":true,\"mappingTree\":{\"value\":\"oneUi_observation\",\"valueType\":\"STRING\"},\"name\":\"templateId\",\"necessary\":true,\"refType\":\"CONSTANT\",\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"\",\"editable\":true,\"mappingTree\":{\"value\":\"oneUi任务规划助手，具备生成式UI能力，通过技能解决用户问题\",\"valueType\":\"STRING\"},\"name\":\"role\",\"necessary\":true,\"refType\":\"CONSTANT\",\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"\",\"editable\":true,\"mappingTree\":{\"value\":\"无\"},\"name\":\"constraint\",\"necessary\":true,\"refType\":\"CONSTANT\",\"subMappings\":[]}],\"label\":\"观察任务\",\"name\":\"观察任务\",\"outMappings\":[{\"desc\":\"返回内容\",\"editable\":false,\"name\":\"content\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"SSTRING\"},{\"desc\":\"是否成功\",\"editable\":false,\"name\":\"success\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"错误码\",\"editable\":false,\"name\":\"errorCode\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"STRING\"},{\"desc\":\"错误信息\",\"editable\":false,\"name\":\"errorMessage\",\"necessary\":false,\"subMappings\":[],\"valueType\":\"STRING\"}],\"type\":\"LLM\"},\"dragging\":false,\"height\":1083,\"id\":\"node_YC9Fee2I5E5FpkVO\",\"name\":\"观察任务\",\"position\":{\"x\":3507.854141018389,\"y\":727.6448771554283},\"positionAbsolute\":{\"x\":3507.854141018389,\"y\":727.6448771554283},\"selected\":false,\"type\":\"LLM\",\"width\":960},{\"data\":{\"config\":{\"contentMappings\":[{\"desc\":\"输出文本\",\"editable\":true,\"mappingTree\":{\"children\":[{\"children\":[{\"desc\":\"最终答案内容\",\"hasChildren\":false,\"name\":\"content\",\"valueType\":\"SSTRING\"}],\"desc\":\"组合任务\",\"hasChildren\":true,\"name\":\"node_wTAJLIClOaIY4RP9\",\"valueType\":\"OBJECT\"}],\"desc\":\"节点\",\"hasChildren\":true,\"name\":\"NODE\"},\"name\":\"cmd\",\"necessary\":false,\"refType\":\"REF\",\"sourceDisabled\":false,\"subMappings\":[],\"valueType\":\"SSTRING\"}],\"metaDataMappings\":[]},\"inMappings\":[],\"label\":\"结果渲染任务\",\"name\":\"结果渲染任务\",\"outMappings\":[],\"type\":\"endEvent\"},\"dragging\":false,\"height\":438,\"id\":\"node_dIWgAFfb1bEkAp2J\",\"name\":\"结果渲染任务\",\"position\":{\"x\":3790.7866647994265,\"y\":-620.5441767902761},\"positionAbsolute\":{\"x\":3790.7866647994265,\"y\":-620.5441767902761},\"selected\":false,\"type\":\"endEvent\",\"width\":680}]}",
          "versionFlowType": "default",
          "agentName": "lxj智能体查看",
          "versionName": "工具",
          "versionCode": "1740037093657"
        },
        "feature": null,
        "operateControl": null
      }
    ],
    "pageSize": 10,
    "current": 1,
    "totalPages": 1
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

- apiCode：agent.openapi.template.pagequery
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-TEMPLATE
- serviceRegion：ctl
