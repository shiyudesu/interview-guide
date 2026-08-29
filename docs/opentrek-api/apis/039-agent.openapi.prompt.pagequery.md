# 查询提示词模版列表

- 文档序号：039
- 分类：平台功能类 / 智能体管理 / 提示词模版 / 查询提示词模版列表
- 唯一编码：sfm.api.openapi-agent.agent.openapi.prompt.pagequery
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/prompt/pageQuery
- 文档版本：1787280870309

## 接口概述

查询提示词模版列表

查询提示词模版列表。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| type | String | 是 | Body | 提示词模版类型，custom: 我的提示词，platform: 平台提示词 | custom |
| name | String | 是 | Body | 提示词名称，模糊搜索 | 测试名称 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的提示词模版总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的提示词模版列表 |  |
| data.list.id | Integer | 是 | Body | 提示词模版唯一编码 | 57 |
| data.list.name | String | 是 | Body | 提示词模版名称 | md格式转txt |
| data.list.type | Integer | 是 | Body | 提示词模版类型，custom: 我的提示词，system: 平台提示词 | custom: 我的提示词，system: 平台提示词 |
| data.list.labels | String | 是 | Body | 分类标签 | ["职场效率"] |
| data.list.projectCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.list.frame | String | 是 | Body | 提示词框架类型，Custom\|CRISPE\|Few-shot | Custom |
| data.list.prompt | String | 是 | Body | 提示词模版内容，结构化json格式 | {"prompt":"将此md内容转换为txt格式，只输出txt格式内容\n```markdown\n{{mdContent}}\n```"} |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/prompt/pageQuery' \
-H 'Content-Type: application/json'  \
-H 'x-sfm-workspacecode: baseline'  \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{
    "current":1,
    "pageSize":10,
    "type":"custom",
    "label":"职场效率",
    "name":"转txt"
}'
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
        "id": 5,
        "projectCode": "fmthktsjdb",
        "name": "神阳自定义",
        "frame": "Custom",
        "prompt": "{\"prompt\":\"你是一个{{学科}}教授，根据自己的专业知识回答用户问题。\"}",
        "promptTemp": "你是一个{{学科}}教授，根据自己的专业知识回答用户问题。",
        "debugModel": "rsv-ik4zut8s",
        "debugModelVersion": "OPENTREK_MODEL_DEFAULT_VERSION",
        "debugArgs": "{\"学科\":\"计算机\"}",
        "debugStatus": "success",
        "debugResult": "当然，我会尽力帮助你解答关于计算机科学的问题。请问你对哪方面感兴趣？例如编程语言、数据结构、算法、操作系统、网络、数据库等。",
        "creatorId": null,
        "creator": null,
        "modified": null,
        "lastModified": null,
        "gmtCreate": "2025-07-21T07:00:33.013+00:00",
        "gmtModified": "2025-09-05T02:24:45.976+00:00",
        "isDel": false,
        "type": "custom",
        "labels": [
          "营销文案",
          "职场效率"
        ],
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

- apiCode：agent.openapi.prompt.pagequery
- groupCode：OPENAPI-AGENT
- catalogCode：PROMPT
- serviceRegion：ctl
