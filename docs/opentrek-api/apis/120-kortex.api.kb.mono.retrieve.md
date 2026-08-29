# 知识库检索

- 文档序号：120
- 分类：应用集成类 / 知识库检索 / 知识库检索
- 唯一编码：sfm.api.kortex.kortex.api.kb.mono.retrieve
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/mono/retrieve
- 文档版本：1787280869932

## 接口概述

知识库通用检索能力,包括文档知识库、自定义知识库、图文知识库

按照知识库的kbSubmodels.kbIndexes 字段用户可实现针对特定字段的通用检索能力。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| kbIndexCode | String | 是 | Body | 知识库索引code,见知识库详情返回结构 kbSubmodels[0].kbIndexes[0].kbIndexCode  | tttbnz21diense89 |
| kbIndexRetrieveFieldName | String | 是 | Body | 检索字段 | 见知识库详情返回结构kbSubmodels部分; <br> 文档知识库固定传递 chunk_representation; <br> 图文知识库可传递 image_path 或者 text; <br> 自定义知识库库 见知识库详情响应体中的 kbSubmodels[0].kbIndexes 中Retrieve类型字段;<br> |
| query | String | 是 | Body | 查询内容 | 字符串 |
| filters | JSONObject | 否 | Body | 查询内容 | 扩展过滤项, 例如图文知识库,支持针对特定文档进行检索, 例如 {"file_code": ["8a58578fce264cd3a648162ea94d2686"]}  |
| score | Double | 是 | Body | 最小分值 | 0.01 |
| limit | Integer | 是 | Body | 返回条目 | 10 |
| advancedRules | Object | 否 | Body | 高级规则配置，支持复杂的AND/OR逻辑组合过滤条件 | {"operator":"AND","conditions":[{"type":"simple","simpleRule":{"fileName":"plan_code","ruleTypeEnum":"EQ","fileValue":"YCJ2024100"}},{"type":"nested","advancedRules":{"operator":"AND","conditions":[{"type":"simple","simpleRule":{"fileName":"plan_name","ruleTypeEnum":"LIKE","fileValue":"江南区"}},{"type":"simple","simpleRule":{"fileName":"area_name","ruleTypeEnum":"IN","fileValueList":["江北区","江南区"]}}]}}]} |
| advancedRules.operator | String | 是 |  | 逻辑操作符，可选值: AND(与), OR(或) | AND |
| advancedRules.conditions | Array | 是 |  | 条件列表，每个条件可以是简单条件(type=simple)或嵌套条件(type=nested) | [{"type":"simple",...},{"type":"nested",...}] |
| advancedRules.conditions.type | String | 是 |  | 条件类型，可选值: simple(简单条件), nested(嵌套条件) | simple |
| advancedRules.conditions.simpleRule | Object | 否 |  | 简单规则定义(type=simple时必填) | {"fileName":"plan_code","ruleTypeEnum":"EQ","fileValue":"YWC34520000"} |
| advancedRules.conditions.simpleRule.fileName | String | 是 |  | 匹配的字段名 | plan_code |
| advancedRules.conditions.simpleRule.ruleTypeEnum | String | 是 |  | 规则类型，可选值: EQ(等于), IN(包含), IS_NOT_NULL(非空), LIKE(模糊匹配) | EQ |
| advancedRules.conditions.simpleRule.fileValue | Object | 否 |  | 单个匹配值，ruleTypeEnum为EQ/LIKE时使用 | YCJ2024520000 |
| advancedRules.conditions.simpleRule.fileValueList | Array | 否 |  | 多个匹配值列表，ruleTypeEnum为IN时使用 | ["江南区","江北区"] |
| advancedRules.conditions.advancedRules | Object | 否 |  | 嵌套的高级检索规则(type=nested时必填)，支持递归嵌套 | {"operator":"AND","conditions":[{"type":"simple",...},{"type":"simple",...}]} |
| advancedRules.conditions.advancedRules.operator | String | 是 |  | 嵌套逻辑操作符，可选值: AND, OR | AND |
| advancedRules.conditions.advancedRules.conditions | Array | 是 |  | 嵌套条件列表 | [...] |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | List<Object> | 是 | Body | 返回数据,按照预先定义的kbSubmodels结构返回 | [] |
| data.score | String | 是 | Body | 得分 | true |
| data.sys_source_ids | String | 是 | Body | 数据附加信息 | true |
| data.sys_data_id | String | 是 | Body | 数据唯一ID; | true |
| data.sys_create_time | String | 是 | Body | 创建时间 | true |
| data.**** | String | 是 | Body | 动态的自定义召回字段;例如图文知识库召回的file_code、image_path、text; 文档知识库召回的 file_code、chunk_bboxs、show_content、chunk_upload_type、chunk_content 、chunk_sort_number、start_page |  |
| metrics | Object | 否 | Body | 性能指标 | {} |
| metrics.kbCode | String |  |  | 知识库编码 | xxx |
| metrics.totalTime | Long |  |  | 检索总耗时(ms) | 150 |
| metrics.chunksCount | Integer |  |  | 返回的chunk数量 | 10 |
| metrics.retrievalDetails | List<Object> |  |  | 详细检索指标 | [{"kbIndexCode":"yyy","engineType":"builtin_vector","embeddingTime":50,"vectorRecallTime":80,"retrievedChunksCount":10}] |
| metrics.retrievalDetails.kbIndexCode | String |  |  | 索引编码 | ozqn95a5936ycwkl |
| metrics.retrievalDetails.engineType | String |  |  | 引擎类型 | builtin_vector |
| metrics.retrievalDetails.embeddingTime | Long |  |  | 向量嵌入耗时(ms) | 50 |
| metrics.retrievalDetails.vectorRecallTime | Long |  |  | 向量召回耗时(ms) | 80 |
| metrics.retrievalDetails.textQueryTime | Long |  |  | 全文检索耗时(ms) | 60 |
| metrics.retrievalDetails.retrievedChunksCount | Integer |  |  | 该引擎实际召回的chunk数量 | 10 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/mono/retrieve \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbIndexCode":"qdqsajkhjn6xpn7z",
     "kbIndexRetrieveFieldName":"text",
     "query":"草莓",
      "score":0.01,
     "limit":10
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":[{"score":0.529308557510376,"file_code":"adaf2a92995b4e439f68ebe3222de9a1","sys_source_ids":"{\"kb_submodel\": \"true\", \"kb_submodel.sys_data_id\": \"82aab26d-b1ff-40da-a3fc-bbadb5b3b439\"}","image_path":"apsara/kortex/kb/visual/file/wjtir7knghhr/SglptjTkqA35r12MoUOVxE91rWSEonTg/8f1af9cbaa9d9aee17a0c0bd944ef662.jpeg","sys_data_id":"82aab26d-b1ff-40da-a3fc-bbadb5b3b439","text":"这是一张草莓的特写照片，草莓表面有水珠，背景是绿色的叶子。","sys_create_time":"2025-07-04T13:28:58.122+00:00"}],"ext":"metrics":"{\'chunksCount\':3,\'retrievalDetails\:[{\'embeddingTime\:161,\'engineType\:\'builtin_vector\',\'kbCode\':\'ozqn95a5936y\',\'kbIndexCode\':\'ozqn95a5936ycwkl\',\'retrievedChunksCount\':3,\'vectorRecallTime\':40}],\'totalTime\':234}","errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.mono.retrieve
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
