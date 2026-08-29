# 获取算子列表

- 文档序号：081
- 分类：平台功能类 / 数据中心 / 数据加工 / 获取算子列表
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.operators
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/operators
- 文档版本：1787280870583

## 接口概述

获取算子列表[ListOperators]

获取算子列表，支持根据关键字、算子类型进行筛选。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| keyword | String | 否 | Query | 搜索关键字 | text |
| type | String | 否 | Query | 算子类型 | Mapper |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| operators | List<Object> | 是 | body | 算子列表 |  |
| operators.id | Integer | 是 | body | 算子ID | 1203 |
| operators.name | String | 是 | body | 算子名称 | 文本增强 |
| operators.code | String | 是 | body | 算子Code | opentrek_text_enhancement_mapper |
| operators.description | String | 是 | body | 算子描述 | 用来增强文本 |
| operators.type | String | 是 | body | 算子类型 | Mapper |
| operators.modalities | List<String> | 是 | body | 支持的数据类型 | ["text"] |
| operators.devices | List<String> | 是 | body | 支持的设备类型 | ["CPU", "GPU"] |
| operators.tags | List<String> | 是 | body | 标签 | ["LLM"] |
| operators.updateFeatures | List<Object> | 是 | body | 算子变更字段 | [{"columnName": "problem", "columnType": "string", "columnPhysicalType": "varchar", "columnComment": "用户提问"}, {"columnName": "param:solution", "columnType": "string", "columnPhysicalType": "varchar", "columnComment": "LLM回答"}] |
| operators.updateFeatures.columnName | String | 是 | body | 字段名称 | problem |
| operators.updateFeatures.columnType | String | 是 | body | 字段类型 | String |
| operators.updateFeatures.columnPhysicalType | String | 是 | body | 字段物理类型 | varchar |
| operators.updateFeatures.columnComment | String | 是 | body | 字段描述 | 用户提问 |
| operators.params | List<Object> | 是 | body | 参数信息 | [{"type": "literal", "required": true, "key": "model", "defaultValue": "qwen-max", "desc": "Model to use for data generation.", "options": ["qwen-max", "qwen-vl"]}] |
| operators.params.type | String | 是 | body | 参数类型 | literal |
| operators.params.required | Boolean | 是 | body | 是否必填 | true |
| operators.params.key | String | 是 | body | 参数Key | model |
| operators.params.defaultValue | String | 是 | body | 默认值 | qwen-max |
| operators.params.desc | String | 是 | body | 参数描述 | Model to use for data generation. |
| operators.params.options | List<String> | 是 | body | 可选值 | ["qwen-max", "qwen-vl"] |
| operators.components | List<Object> | 是 | body | 前端组件配置 | [{"type": "Select", "required": true, "label": "模型名称", "key": "model", "desc": "对于当前表单项的简单描述", "defaultValue": "qwen-max", "options": [{"label": "通义千问", "value": "qwen-max", "desc": "通义千问是一个专门响应人类指令的大模型，是一个灵活多变的全能型选手，能够写邮件、周报、提纲，创作诗歌、小说、剧本、coding、制表、甚至角色扮演。"}, {"label": "通义千问VL", "value": "qwen-vl", "desc": "通义千问VL（qwen-vl）是阿里云研发的大规模视觉语言模型，可以以图像、文本、检测框作为输入，并以文本和检测框作为输出，支持中文多模态对话及多图对话。"}], "extra": {"min": 0, "max": 10, "step": 1, "mode": "multiple"}}] |
| operators.components.type | String | 是 | body | 组件类型 | Select |
| operators.components.required | Boolean | 是 | body | 是否必填 | true |
| operators.components.label | String | 是 | body | 组件标签 | 模型名称 |
| operators.components.key | String | 是 | body | 参数Key | model |
| operators.components.desc | String | 是 | body | 组件描述 | 对于当前表单项的简单描述 |
| operators.components.defaultValue | String | 是 | body | 默认值 | qwen-max |
| operators.components.options | List<Object> | 是 | body | 选项列表 | [{"label": "通义千问", "value": "qwen-max", "desc": "通义千问是一个专门响应人类指令的大模型，是一个灵活多变的全能型选手，能够写邮件、周报、提纲，创作诗歌、小说、剧本、coding、制表、甚至角色扮演。"}, {"label": "通义千问VL", "value": "qwen-vl", "desc": "通义千问VL（qwen-vl）是阿里云研发的大规模视觉语言模型，可以以图像、文本、检测框作为输入，并以文本和检测框作为输出，支持中文多模态对话及多图对话。"}] |
| operators.components.options.label | String | 是 | body | 选项标签 | 通义千问 |
| operators.components.options.value | String | 是 | body | 选项值 | qwen-max |
| operators.components.options.desc | String | 是 | body | 选项描述 | 通义千问是一个专门响应人类指令的大模型，是一个灵活多变的全能型选手，能够写邮件、周报、提纲，创作诗歌、小说、剧本、coding、制表、甚至角色扮演。 |
| operators.components.extra | Object | 是 | body | 扩展配置 | {"min": 0, "max": 10, "step": 1, "mode": "multiple"} |
| operators.components.extra.min | Integer | 是 | body | 最小值 | 0 |
| operators.components.extra.max | Integer | 是 | body | 最大值 | 10 |
| operators.components.extra.step | Integer | 是 | body | 步长 | 1 |
| operators.components.extra.mode | String | 是 | body | 模式 | multiple |
| pageSize | Integer | 是 | body | 每页行数 | 20 |
| totalCount | Integer | 是 | body | 总数量 | 79 |
| pageNumber | Integer | 是 | body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' http://10.128.203.200:30226/gatectl/data-engine/api/v2/operators?keyword=${keyword}&type=${type} \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "operators": [
    {
      "id": 1203,
      "name": "文本增强",
      "code": "opentrek_text_enhancement_mapper",
      "description": "用来增强文本",
      "type": "Mapper",
      "modalities": ["text"],
      "devices": ["CPU", "GPU"],
      "tags": ["LLM"],
      "updateFeatures": [
        {
          "columnName": "problem",
          "columnType": "string",
          "columnPhysicalType": "varchar",
          "columnComment": "用户提问"
        },
        {
          "columnName": "param:solution",
          "columnType": "string",
          "columnPhysicalType": "varchar",
          "columnComment": "LLM回答"
        }
      ],
      "params": [
        {
          "type": "literal",
          "required": true,
          "key": "model",
          "defaultValue": "qwen-max",
          "desc": "Model to use for data generation.",
          "options": ["qwen-max", "qwen-vl"]
        }
      ],
      "components": [
        {
          "type": "Select",
          "required": true,
          "label": "模型名称",
          "key": "model",
          "desc": "对于当前表单项的简单描述",
          "defaultValue": "qwen-max",
          "options": [
            {
              "label": "通义千问",
              "value": "qwen-max",
              "desc": "通义千问是一个专门响应人类指令的大模型，是一个灵活多变的全能型选手，能够写邮件、周报、提纲，创作诗歌、小说、剧本、coding、制表、甚至角色扮演。"
            },
            {
              "label": "通义千问VL",
              "value": "qwen-vl",
              "desc": "通义千问VL（qwen-vl）是阿里云研发的大规模视觉语言模型，可以以图像、文本、检测框作为输入，并以文本和检测框作为输出，支持中文多模态对话及多图对话。"
            }
          ],
          "extra": {
            "min": 0,
            "max": 10,
            "step": 1,
            "mode": "multiple"
          }
        }
      ]
    }
  ],
  "pageSize": 20,
  "totalCount": 79,
  "pageNumber": 1
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

- apiCode：data-engine.api.v2.operators
- groupCode：DATAPROCESS
- catalogCode：OPERATORS
- serviceRegion：ctl
