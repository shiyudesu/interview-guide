# 获取加工任务详情

- 文档序号：090
- 分类：平台功能类 / 数据中心 / 数据加工 / 获取加工任务详情
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.process.tasks.Taskid.get
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}
- 文档版本：1787280870629

## 接口概述

获取加工任务详情[GetProcessTask]

根据任务ID获取加工任务的详细信息。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Path传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| taskId | Integer | 是 | url | 任务ID | 123 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| id | Integer | 是 | body | 任务ID | 123 |
| name | String | 是 | body | 任务名称 | 自定义蒙牛文本清洗任务 |
| description | String | 是 | body | 任务描述 | 清洗干干净净的蒙牛任务 |
| editState | String | 是 | body | 任务编辑状态 | draft |
| type | String | 是 | body | 任务类型 | pipeline |
| dkeJobId | Integer | 是 | body | DKE作业ID | 231 |
| tplId | Integer | 是 | body | 模版ID | 12 |
| tplName | String | 是 | body | 模版名称 | 数据清洗 |
| tplCode | String | 是 | body | 模版Code | text_clean |
| tplVersion | String | 是 | body | 模版版本 | v1.0.0 |
| operatorIds | List<Object> | 是 | body | 使用算子ID列表 | [12, 13, 14] |
| operators | List<Object> | 是 | body | 算子详情 | [] |
| config | Object | 是 | body | 任务配置 | {} |
| creatorId | String | 是 | body | 创建者ID | 1631044****3440 |
| creatorName | String | 是 | body | 创建者用户名 | admin |
| tenantCode | String | 是 | body | 租户Code | sfmboost |
| workspaceCode | String | 是 | body | 工作组Code | default_workspace |
| createdAt | String | 是 | body | 创建时间 | 2021-01-30T12:51:33.028Z |
| updatedAt | String | 是 | body | 更新时间 | 2021-01-30T12:51:33.028Z |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/${taskId} \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "id": 123,
  "name": "自定义蒙牛文本清洗任务",
  "description": "清洗干干净净的蒙牛任务",
  "editState": "draft",
  "type": "pipeline",
  "dkeJobId": 231,
  "tplId": 12,
  "tplName": "数据清洗",
  "tplCode": "text_clean",
  "tplVersion": "v1.0.0",
  "operatorIds": [12, 13, 14],
  "operators": [],
  "config": {},
  "creatorId": "1631044****3440",
  "creatorName": "admin",
  "tenantCode": "sfmboost",
  "workspaceCode": "default_workspace",
  "createdAt": "2021-01-30T12:51:33.028Z",
  "updatedAt": "2021-01-30T12:51:33.028Z"
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

- apiCode：data-engine.api.v2.process.tasks.Taskid.get
- groupCode：DATAPROCESS
- catalogCode：OPERATORS
- serviceRegion：ctl
