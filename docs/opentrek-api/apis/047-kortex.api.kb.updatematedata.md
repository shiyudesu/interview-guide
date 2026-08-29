# 知识库元数据更新

- 文档序号：047
- 分类：平台功能类 / 知识库管理 / 知识库元数据更新
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.updatematedata
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/updateMateData
- 文档版本：1787280870367

## 接口概述

更新知识库元数据信息

更新知识库元数据信息（名称、描述等）。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| code | String | 是 | Body | 知识库唯一编码 | z7pn9wbtkpy0 |
| name | String | 否 | Body | 知识库名称 | 测试知识库 |
| description | String | 否 | Body | 知识库描述 | 这是一个测试知识库 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | null |
| errorCode | String | 是 | Body | 错误码 | null |
| errorMsg | String | 是 | Body | 错误描述 | null |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/updateMateData \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "code":"z7pn9wbtkpy0",
    "name":"测试知识库",
    "description":"这是一个测试知识库"
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":null,"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.updatematedata
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
