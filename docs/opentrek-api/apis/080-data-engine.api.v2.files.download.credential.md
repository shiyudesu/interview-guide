# 获取文件下载授权凭证

- 文档序号：080
- 分类：平台功能类 / 数据中心 / 数据管理 / 获取文件下载授权凭证
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.files.download.credential
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/files/download/credential
- 文档版本：1787280870567

## 接口概述

获取文件下载授权凭证[GetFileDownloadCredential]

获取文件下载授权凭证。安全要求，使用服务端生成STS临时访问凭证由前端下载。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| datasetCode | String | 是 | Query | 数据集Code | mmlu |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.type | String | 是 | Body | 存储类型 | oss |
| data.endpoint | String | 是 | Body | 访问端点 | https://oss-cn-hangzhou.aliyuncs.com |
| data.internalEndpoint | String | 是 | Body | 内部访问地址 | xxx |
| data.externalEndpoint | String | 是 | Body | 外部访问地址 | xxx |
| data.bucket | String | 是 | Body | 存储桶名称 | kn-tenant-xxx |
| data.region | String | 是 | Body | 区域 | xxx |
| data.accessKeyId | String | 是 | Body | 访问密钥ID | xxx |
| data.accessKeySecret | String | 是 | Body | 访问密钥 | xxx |
| data.stsToken | String | 是 | Body | 安全令牌 | xxx |
| data.expiration | Integer | 是 | Body | 有效期(秒) | 3600 |
| data.expireTime | String | 是 | Body | 过期时间 | 2024-10-08T11:53:23.000Z |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/data-engine/api/v2/files/download/credential?datasetCode=${datasetCode}' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "type": "oss",
    "endpoint": "https://oss-cn-hangzhou.aliyuncs.com",
  "internalEndpoint": "xxx",
    "externalEndpoint": "xxx",
    "bucket": "kn-tenant-xxx",
    "region": "xxx",
    "accessKeyId": "xxx",
    "accessKeySecret": "xxx",
    "stsToken": "xxx",
    "expiration": 3600,
    "expireTime": "2024-10-08T11:53:23.000Z"
  }
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

- apiCode：data-engine.api.v2.files.download.credential
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
