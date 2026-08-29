# 查询账号授权信息

- 文档序号：006
- 分类：平台功能类 / 系统管理 / 用户授权 / 查询账号授权信息
- 唯一编码：sfm.api.system-openapi.system.api.v1.permUserAuth.pageUserAuthDetail
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/system/api/v1/permUserAuth/pageUserAuthDetail
- 文档版本：1787280870032

## 接口概述

查询账号授权信息

查询账号授权信息。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| uid | String | 是 | Body | 用户Account ID | 0c1457b0829c4481bfb4f9d8e9a4e974 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 用户权限信息 | true |
| data.list | List<Object> | 是 | Body | 授权列表 |  |
| data.list.statusCode | String | 是 | Body | 授权状态编码 | EFFECTIVE |
| data.list.status | String | 是 | Body | 授权状态 | 正常 |
| data.list.authObjectId | String | 是 | Body | 用户Account ID | 0c1457b0829c4481bfb4f9d8e9a4e974 |
| data.list.authObject | String | 是 | Body | 用户昵称 | opentrek大模型 |
| data.list.authSubjectCode | String | 是 | Body | 用户角色编码 | OPENTREK_SAFE_MANAGER |
| data.list.authSubjectId | String | 是 | Body | 用户角色ID | OPENTREK_SAFE_MANAGER |
| data.list.authSubjectType | String | 是 | Body | 授权类型 | ROLE |
| data.list.status | String | 是 | Body | status | ACTIVE |
| data.list.authPerson | String | 是 | Body | 授权人 | opentrek |
| data.list.expireDate | String | 是 | Body | 过期时间 | 2026-05-01T15:59:59.000+00:00 |
| data.list.reason | String | 否 | Body | 授权原因 | 2026-05-01T15:59:59.000+00:00 |
| errorCode | String |  | Body | 错误码 |  |
| errorMsg | String |  | Body | 错误信息 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/system/api/v1/permUserAuth/pageUserAuthDetail' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{
    "uid": ""
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
                "id": "218225",
                "authType": "INDIRECT",
                "status": "正常",
                "statusCode": "EFFECTIVE",
                "riskLevel": "低",
                "systemName": "",
                "authObject": "opentrek",
                "authObjectId": "0c1457b0829c4481bfb4f9d8e9a4e974",
                "authSubject": "安全保密管理员",
                "authSubjectCode": "OPENTREK_SAFE_MANAGER",
                "authSubjectId": "99000001686",
                "authSubjectType": "ROLE",
                "authPerson": "test01",
                "permissionNum": "0",
                "authedTime": "2025-08-28T03:46:46.772+00:00",
                "expireDate": "2026-05-01T15:59:59.000+00:00",
                "modelId": null,
                "modelType": "PK",
                "dataPermissionDTOList": null,
                "description": "OPENTREK_SAFE_MANAGER",
                "reason": "测试",
                "sourceAuthSubjectId": "",
                "sourceAuthSubjectType": "",
                "sourceAuthSubjectName": null,
                "sourceAuthSubjectCode": null,
                "opEnable": true,
                "disableDesc": "请联系授权人员或系统管理员"
            }
        ],
        "pageSize": 1000,
        "current": 1,
        "totalPages": 1
    },
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

- apiCode：system.api.v1.permUserAuth.pageUserAuthDetail
- groupCode：SYSTEM-OPENAPI
- catalogCode：USERAUTH
- serviceRegion：ctl
