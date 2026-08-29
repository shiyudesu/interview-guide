# 创建工作空间

- 文档序号：007
- 分类：平台功能类 / 系统管理 / 空间管理 / 创建工作空间
- 唯一编码：sfm.api.system-openapi.system.api.v1.workspace.create
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/system/api/v1/workspace/create
- 文档版本：1787280870046

## 接口概述

创建工作空间

创建工作空间。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| name | String | 是 | Body | 空间名称 | 测试空间 |
| description | String | 是 | Body | 空间描述 | 测试空间 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | String |  | Body | 空间编码 | true |
| errorCode | String |  | Body | 错误码 |  |
| errorMsg | String |  | Body | 错误信息 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/system/api/v1/workspace/create' \
-H 'Content-Type: application/json'  \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{
  "name": "",
  "description": ""
}'
```


## 响应示例

#### 返回数据

```json
{
    "errorMessages": [],
    "success": true,
    "data": "087a76c2-6684-4bb9-ad8a-d5aa77d0b136",
    "errorCode": null,
    "errorMsg": null,
    "extraData": null,
    "traceId": null,
    "env": null,
    "other": null,
    "failure": false,
    "firstErrorMessage": null
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

- apiCode：system.api.v1.workspace.create
- groupCode：SYSTEM-OPENAPI
- catalogCode：WORKSPACE
- serviceRegion：ctl
