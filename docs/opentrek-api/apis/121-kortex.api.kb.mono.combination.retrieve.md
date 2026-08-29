# 知识库批量检索

- 文档序号：121
- 分类：应用集成类 / 知识库检索 / 知识库批量检索
- 唯一编码：sfm.api.kortex.kortex.api.kb.mono.combination.retrieve
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/mono/combination/retrieve
- 文档版本：1787280869939

## 接口概述

支持同时检索多个知识库，每个知识库可配置不同的检索参数，最大支持10个知识库同时检索。

批量检索接口支持多知识库同时检索，返回每个知识库的独立结果和性能指标。适用于需要同时从多个知识库获取数据的场景。

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
| combinationParams | List<object> | 是 | Body | 检索参数列表 | [{"kbIndexCode":"xxx","kbIndexRetrieveFieldName":"name","query":"测试","score":0.01,"limit":10}] |
| combinationParams.kbIndexCode | String | 是 |  | 知识库索引code | tttbnz21dien |
| combinationParams.kbIndexRetrieveFieldName | String | 是 |  | 检索字段 | name |
| combinationParams.query | String | 是 |  | 查询内容 | 测试查询 |
| combinationParams.score | Double | 是 |  | 最小分值 | 0.01 |
| combinationParams.limit | Integer | 是 |  | 返回条目 | 10 |
| combinationParams.filters | Object | 否 | Body | 查询内容 | 扩展过滤项, 例如图文知识库,支持针对特定文档进行检索, 例如 {"file_code": ["8a58578fce264cd3a648162ea94d2686"]}  |
| combinationParams.mapBatchKey | String | 否 |  | 批量检索时的结果映射KEY，用于区分不同请求的结果 | kb1 |
| combinationParams.advancedRules | Object | 否 | Body | 高级规则配置，支持复杂的AND/OR逻辑组合过滤条件 | {"operator":"AND","conditions":[{"type":"simple","simpleRule":{"fileName":"plan_code","ruleTypeEnum":"EQ","fileValue":"YCJ2024100"}},{"type":"nested","advancedRules":{"operator":"AND","conditions":[{"type":"simple","simpleRule":{"fileName":"plan_name","ruleTypeEnum":"LIKE","fileValue":"江南区"}},{"type":"simple","simpleRule":{"fileName":"area_name","ruleTypeEnum":"IN","fileValueList":["江北区","江南区"]}}]}}]} |
| combinationParams.advancedRules.operator | String | 是 |  | 逻辑操作符，可选值: AND(与), OR(或) | AND |
| combinationParams.advancedRules.conditions | Array | 是 |  | 条件列表，每个条件可以是简单条件(type=simple)或嵌套条件(type=nested) | [{"type":"simple",...},{"type":"nested",...}] |
| combinationParams.advancedRules.conditions.type | String | 是 |  | 条件类型，可选值: simple(简单条件), nested(嵌套条件) | simple |
| combinationParams.advancedRules.conditions.simpleRule | Object | 否 |  | 简单规则定义(type=simple时必填) | {"fileName":"plan_code","ruleTypeEnum":"EQ","fileValue":"YWC34520000"} |
| combinationParams.advancedRules.conditions.simpleRule.fileName | String | 是 |  | 匹配的字段名 | plan_code |
| combinationParams.advancedRules.conditions.simpleRule.ruleTypeEnum | String | 是 |  | 规则类型，可选值: EQ(等于), IN(包含), IS_NOT_NULL(非空), LIKE(模糊匹配) | EQ |
| combinationParams.advancedRules.conditions.simpleRule.fileValue | Object | 否 |  | 单个匹配值，ruleTypeEnum为EQ/LIKE时使用 | YCJ2024520000 |
| combinationParams.advancedRules.conditions.simpleRule.fileValueList | Array | 否 |  | 多个匹配值列表，ruleTypeEnum为IN时使用 | ["江南区","江北区"] |
| combinationParams.advancedRules.conditions.advancedRules | Object | 否 |  | 嵌套的高级检索规则(type=nested时必填)，支持递归嵌套 | {"operator":"AND","conditions":[{"type":"simple",...},{"type":"simple",...}]} |
| combinationParams.advancedRules.conditions.advancedRules.operator | String | 是 |  | 嵌套逻辑操作符，可选值: AND, OR | AND |
| combinationParams.advancedRules.conditions.advancedRules.conditions | Array | 是 |  | 嵌套条件列表 | [...] |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  |  | 是否成功 | true |
| data | List<Object> | 是 | Body | 批量检索结果列表 | [] |
| data.mapBatchKey | String | 否 |  | 结果映射KEY（对应请求中的mapBatchKey） | kb1 |
| data.kbCode | String | 是 |  | 知识库编码 | xxx |
| data.kbIndexEngineType | String | 是 |  | 索引引擎类型 | builtin_vector |
| data.kbIndexCode | String | 是 |  | 索引编码 | yyy |
| data.result | List<Map<String,Object>> | 是 |  | 检索结果列表 | [{"score":0.85,"file_code":"xxx"}] |
| data.metrics | Object | 否 |  | 性能指标 | {} |
| data.metrics.kbCode | String |  |  | 知识库编码 | xxx |
| data.metrics.totalTime | Long |  |  | 检索总耗时(ms) | 150 |
| data.metrics.chunksCount | Integer |  |  | 返回的chunk数量 | 10 |
| data.metrics.retrievalDetails | List<Object> |  |  | 详细检索指标 | [] |
| data.metrics.retrievalDetails.kbIndexCode | String |  |  | 索引编码 | ozqn95a5936ycwkl |
| data.metrics.retrievalDetails.engineType | String |  |  | 引擎类型 | builtin_vector |
| data.metrics.retrievalDetails.embeddingTime | Long |  |  | 向量嵌入耗时(ms) | 50 |
| data.metrics.retrievalDetails.vectorRecallTime | Long |  |  | 向量召回耗时(ms) | 80 |
| data.metrics.retrievalDetails.textQueryTime | Long |  |  | 全文检索耗时(ms) | 60 |
| data.metrics.retrievalDetails.retrievedChunksCount | Integer |  |  | 该引擎实际召回的chunk数量 | 10 |
| errorCode | String |  |  | 错误码 |  |
| errorMsg | String |  |  | 错误描述 |  |


## 请求示例

#### 批量检索知识库示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/mono/combination/retrieve \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "combinationParams":[
        {
            "kbCode":"kbcode1",
            "kbIndexRetrieveFieldName":"name",
            "query":"测试查询1",
            "score":0.01,
            "limit":5,
            "mapBatchKey":"kb1",
            "kbIndexEngineType":"builtin_vector"
        },
        {
            "kbCode":"kbcode2",
            "kbIndexRetrieveFieldName":"text",
            "query":"测试查询2",
            "score":0.01,
            "limit":5,
            "mapBatchKey":"kb2",
            "kbIndexEngineType":"builtin_es"
        }
    ]
}'
```


## 响应示例

#### 批量检索返回示例

```json
{"success":true,"data":[{"mapBatchKey":"kb1","kbCode":"o4jgjrg0997v","kbIndexEngineType":"builtin_vector","kbIndexCode":"o4jgjrg0997vr4rd","result":[{"score":1,"sys_source_ids":"{\'kb_submodel\': \'true\', \'source_builtin_smod\': \'true\', \'kb_submodel.sys_data_id\': \'a8c07518-0f8f-4ff4-b5f4-a91781241cac\'}","name":"小明","sys_data_id":"a8c07518-0f8f-4ff4-b5f4-a91781241cac","describe":"学生","age":12,"sys_create_time":"2026-03-13T07:16:57.661+00:00"},{"score":0.4903782308101654,"sys_source_ids":"{\'kb_submodel\': \'true\', \'source_builtin_smod\': \'true\', \'kb_submodel.sys_data_id\': \'5a8d1e92-ec8f-4316-aa8b-7be48379733e\'}","name":"小刚","sys_data_id":"5a8d1e92-ec8f-4316-aa8b-7be48379733e","describe":"工人","age":25,"sys_create_time":"2026-03-13T07:17:12.418+00:00"}],"metrics":{"kbCode":"o4jgjrg0997v","totalTime":412,"chunksCount":2,"retrievalDetails":[{"kbIndexCode":"o4jgjrg0997vr4rd","engineType":"builtin_vector","embeddingTime":279,"vectorRecallTime":94,"textQueryTime":null,"retrievedChunksCount":2}]}}],"errorCode":null,"errorMsg":null,"traceId":null,"env":null,"ext":null}
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

- apiCode：kortex.api.kb.mono.combination.retrieve
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
