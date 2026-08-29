# 文件元数据批量标注

- 文档序号：118
- 分类：应用集成类 / 知识库检索 / 文件元数据批量标注
- 唯一编码：sfm.api.kortex.kortex.api.kb.metadata.annotatefilemetadata
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/metadata/annotateFileMetadata
- 文档版本：1787280869918

## 接口概述

为指定知识库下的文件批量标注用户元数据，支持文档知识库和图文知识库

仅支持文档知识库(kb_doc)和图文知识库(kb_visual)类型。metadata 为元数据键值对，key 对应元数据定义的 name，value 为标注值。接口会校验元数据是否在当前知识库可见范围内、值类型是否匹配、候选值是否合法；写入时为增量合并，同名 key 会覆盖原值。单个文件最多支持 32 个元数据标注。

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
| kbCode | String | 是 | Body | 知识库编码 | ozqn95a5936ycwkl |
| fileCodes | List<Object> | 是 | Body | 目标文件编码列表 | ["adaf2a92995b4e439f68ebe3222de9a1", "bfe2b1a3888c4f529e79cdfa4330f8b2"] |
| metadata | Object | 否 | Body | 元数据键值对 | {"region":"华东","file_type":"pdf","publish_time":"2025-01-01 00:00:00","score":95} |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 否 | Body | 返回数据，成功时为空 | null |
| errorCode | String | 是 | Body | 错误码 | KB_METADATA_UNSUPPORTED_TYPE |
| errorMsg | String | 是 | Body | 错误描述 | Unsupported knowledge base type for metadata annotation: 3 |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/metadata/annotateFileMetadata \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode": "ozqn95a5936ycwkl",
    "fileCodes": [
        "adaf2a92995b4e439f68ebe3222de9a1",
        "bfe2b1a3888c4f529e79cdfa4330f8b2"
    ],
    "metadata": {
        "region": "华东",
        "file_type": "pdf",
        "publish_time": "2025-01-01 00:00:00",
        "score": 95
    }
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
| 404 | GATEWAY ROUTE URL NOT FOUND! | 无效的目标服务地址 |
| 401 | GATEWAY LIMIT ! | 服务链接已达上限,请稍后再试 |
| 500 | TARGET_SERVICE_ERROR_CONNECTION_REFUSE_EXCEPTION | 目标服务拒绝连接 |
| 500 | TARGET_SERVICE_ERROR_NO_RESPONSE_EXCEPTION | 目标服务无响应 |



## 原始文档标识

- apiCode：kortex.api.kb.metadata.annotatefilemetadata
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
