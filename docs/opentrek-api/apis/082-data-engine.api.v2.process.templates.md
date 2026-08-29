# 获取加工模版列表

- 文档序号：082
- 分类：平台功能类 / 数据中心 / 数据加工 / 获取加工模版列表
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.process.templates
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/templates
- 文档版本：1787280870589

## 接口概述

获取加工模版列表[ListProcessTemplates]

获取加工模版列表，支持根据关键字、模版类型、分页参数进行筛选。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| keyword | String | 否 | Query | 搜索关键字 | 数据清洗 |
| type | String | 否 | Query | 模版类型 | pipeline |
| pageNumber | Integer | 否 | Query | 列表的页码 | 1 |
| pageSize | Integer | 否 | Query | 每页行数 | 20 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| templates | List<Object> | 是 | body | 模版列表 | [{"id": 128, "code": "text_clean", "name": "数据清洗", "description": "数据清洗干干净净", "type": "pipeline", "icon": "", "tags": ["text", "LLM"], "version": "v1.0.0", "ownerId": "1631044****3440", "ownerName": "admin", "tenantCode": "sfmboost", "workspaceCode": "default_workspace", "createdAt": "2021-01-30T12:51:33.028Z", "updatedAt": "2021-01-30T12:51:33.028Z"}] |
| templates.id | Integer | 是 | body | 模版ID | 128 |
| templates.code | String | 是 | body | 模版Code | text_clean |
| templates.name | String | 是 | body | 模版名称 | 数据清洗 |
| templates.description | String | 是 | body | 模版描述 | 数据清洗干干净净 |
| templates.type | String | 是 | body | 模版类型 | pipeline |
| templates.icon | String | 否 | body | 模版图标 |  |
| templates.tags | List<String> | 否 | body | 模版标签 | ["text", "LLM"] |
| templates.version | String | 否 | body | 模版版本 | v1.0.0 |
| templates.ownerId | String | 是 | body | 模版所有者ID | 1631044****3440 |
| templates.ownerName | String | 是 | body | 模版所有者用户名 | admin |
| templates.tenantCode | String | 是 | body | 租户Code | sfmboost |
| templates.workspaceCode | String | 是 | body | 工作组Code | default_workspace |
| templates.createdAt | String | 是 | body | 创建时间 | 2021-01-30T12:51:33.028Z |
| templates.updatedAt | String | 是 | body | 更新时间 | 2021-01-30T12:51:33.028Z |
| pageSize | Integer | 是 | body | 每页行数 | 20 |
| totalCount | Integer | 是 | body | 总数量 | 79 |
| pageNumber | Integer | 是 | body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/templates?keyword=${keyword}&type=${type}&pageNumber=${pageNumber}&pageSize=${pageSize} \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "templates": [
    {
      "id": 128,
      "code": "text_clean",
      "name": "数据清洗",
      "description": "数据清洗干干净净",
      "type": "pipeline",
      "icon": "",
      "tags": ["text", "LLM"],
      "version": "v1.0.0",
      "ownerId": "1631044****3440",
      "ownerName": "admin",
      "tenantCode": "sfmboost",
      "workspaceCode": "default_workspace",
      "createdAt": "2021-01-30T12:51:33.028Z",
      "updatedAt": "2021-01-30T12:51:33.028Z"
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

- apiCode：data-engine.api.v2.process.templates
- groupCode：DATAPROCESS
- catalogCode：OPERATORS
- serviceRegion：ctl
