# 写入记忆分区内容

- 文档序号：021
- 分类：平台功能类 / 智能体管理 / 智能体 / 写入记忆分区内容
- 唯一编码：sfm.api.openapi-agent.agent.openapi.memory.longterm.partition.add
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/memory/longTerm/partition/add
- 文档版本：1787280870155

## 接口概述

写入记忆分区内容

写入记忆分区内容。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| partitionCode | String | 是 | Body | 分区编码 | 1111 |
| storageKey | String | 是 | Body | 键值对-KEY | key |
| storageValue | String | 是 | Body | 键值对-VALUE | value |
| storageContent | String | 是 | Body | 文本 | value |
| memoryUserId | String | 是 | Body | 记忆用户ID | value |
| status | Integer | 是 | Body | 状态 0:正常 1:删除 2:禁用 | value |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.memoryCode | String | 是 | Body | 记忆编码 | a9c81580-8e93-42e1-b331-5cc6506c0093 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/memory/longTerm/partition/add' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"partitionCode": "1111","storageKey": "key","storageValue": "value","storageContent": "value","memoryUserId": "value","status": 0}'
```


## 响应示例

#### 返回数据

```json
{
  "errorMessages": [],
  "success": false,
  "data": null,
  "errorCode": "-1",
  "errorMsg": "记忆分区不存在",
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

- apiCode：agent.openapi.memory.longterm.partition.add
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-OPERATE
- serviceRegion：ctl
