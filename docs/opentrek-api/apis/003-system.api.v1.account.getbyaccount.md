# 获取账号信息

- 文档序号：003
- 分类：平台功能类 / 系统管理 / 账号管理 / 获取账号信息
- 唯一编码：sfm.api.system-openapi.system.api.v1.account.getByAccount
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/system/api/v1/account/getByAccount
- 文档版本：1787280870004

## 接口概述

获取账号信息

获取账号信息。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| account | String | 是 | Query | 用户名 | opentrek |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 账号信息 | true |
| data.accountId | String | 是 | Body | accountId | 7551a976815b413bb859074c9b0677d7 |
| data.account | String | 是 | Body | account | opentrek |
| data.userNick | String | 是 | Body | userNick | opentrek大模型 |
| data.outUid | String | 是 | Body | outUid | 123456 |
| data.status | String | 是 | Body | status | ACTIVE |
| errorCode | String |  | Body | 错误码 |  |
| errorMsg | String |  | Body | 错误信息 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/system/api/v1/account/getByAccount?account=${account}' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY'
```


## 响应示例

#### 返回数据

```json
{
    "errorMessages": [],
    "success": true,
    "data": {
        "accountId": "7551a976815b413bb859074c9b0677d7",
        "accountType": "MANAGER",
        "accountTypeCode": "manager",
        "accountSource": "inner",
        "account": "opentrek",
        "userNick": "opentrek",
        "userAvatar": null,
        "status": "ACTIVE",
        "gmtCreate": "2022-08-09T16:00:00.000+00:00",
        "attributes": {
            "isTest": "false",
            "workspaceCode": "0d9082089cee4a7681bcd6bb3ed50580"
        },
        "userInfo": {
            "userId": "41a0af02574946d09ca4edab1f88c889",
            "userType": "PERSON",
            "personInfo": {
                "userId": "41a0af02574946d09ca4edab1f88c889",
                "userName": "opentrek",
                "idNo": "320602198309052017",
                "phone": "13599542031",
                "nation": "HA",
                "gender": "MALE",
                "idNoEnc": "3****************7",
                "phoneEnc": "135****2031",
                "userNameEnc": "*pentrek"
            },
            "organizationInfoList": []
        },
        "outUid": "7551a976815b413bb859074c9b0677d7",
        "orgIds": null,
        "accountLevel": null,
        "authlevel": null,
        "tenantCode": null
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

- apiCode：system.api.v1.account.getByAccount
- groupCode：SYSTEM-OPENAPI
- catalogCode：ACCOUNT
- serviceRegion：ctl
