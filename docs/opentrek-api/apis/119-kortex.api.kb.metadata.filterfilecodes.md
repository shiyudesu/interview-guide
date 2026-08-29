# 文件元数据过滤查询

- 文档序号：119
- 分类：应用集成类 / 知识库检索 / 文件元数据过滤查询
- 唯一编码：sfm.api.kortex.kortex.api.kb.metadata.filterfilecodes
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/metadata/filterFileCodes
- 文档版本：1787280869925

## 接口概述

根据文件元数据过滤条件查询匹配的 fileCode 列表，支持文档知识库和图文知识库

仅支持文档知识库(kb_doc)和图文知识库(kb_visual)类型。通过元数据条件组构建AND/OR逻辑组合，精确筛选符合元数据标注要求的文件。

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
| operator | String | 是 | Body | 条件组间逻辑操作符 | AND |
| conditions | List<Object> | 是 | Body | 条件组列表 | [{"innerOperator":"AND","rules":[{"metadataName":"region","ruleType":"EQ","value":"华东"}]}] |
| conditions.innerOperator | String | 是 |  | 条件组内逻辑操作符，可选值: AND(与), OR(或) | AND |
| conditions.rules | Array | 是 |  | 过滤规则列表 | [{"metadataName":"file_type","ruleType":"IN","valueList":["pdf","doc"]}] |
| conditions.rules.metadataName | String | 是 |  | 元数据key，对应元数据定义的metadataCode | region |
| conditions.rules.metadataType | String | 是 |  | 元数据类型，用于GT/GTE/LT/LTE的类型转换 | string |
| conditions.rules.ruleType | String | 是 |  | 运算符类型，可选值: EQ(等于), NE(不等于), IN(包含), NOT_IN(不包含), IS_NULL(为空), IS_NOT_NULL(非空), LIKE(模糊匹配), GT(大于), GTE(大于等于), LT(小于), LTE(小于等于), LEN_EQ(长度等于), LEN_NE(长度不等于), LEN_GT(长度大于), LEN_GTE(长度大于等于), LEN_LT(长度小于), LEN_LTE(长度小于等于) | EQ |
| conditions.rules.value | Object | 否 |  | 匹配值（单值），ruleType为EQ/NE/GT/GTE/LT/LTE/LIKE/LEN_xxx时使用 | 华东 |
| conditions.rules.valueList | Array | 否 |  | 匹配值列表，ruleType为IN/NOT_IN时使用 | ["pdf","doc"] |
| conditions.rules.valueSource | String | 否 |  | 值来源，可选值: constant(常量), reference(引用), function(函数) | constant |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | List<String> | 是 | Body | 返回数据，匹配的fileCode列表（已排序） | ["adaf2a92995b4e439f68ebe3222de9a1", "bfe2b1a3888c4f529e79cdfa4330f8b2"] |
| errorCode | String | 是 | Body | 错误码 | KB_METADATA_UNSUPPORTED_TYPE |
| errorMsg | String | 是 | Body | 错误描述 | Unsupported knowledge base type for metadata fileCode filtering: 3 |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/metadata/filterFileCodes \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode": "ozqn95a5936ycwkl",
    "operator": "AND",
    "conditions": [
        {
            "innerOperator": "AND",
            "rules": [
                {
                    "metadataName": "region",
                    "ruleType": "EQ",
                    "value": "华东"
                },
                {
                    "metadataName": "file_type",
                    "ruleType": "IN",
                    "valueList": ["pdf", "doc"]
                }
            ]
        }
    ]
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":["adaf2a92995b4e439f68ebe3222de9a1","bfe2b1a3888c4f529e79cdfa4330f8b2"],"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.metadata.filterfilecodes
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
