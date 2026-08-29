# 文档知识库批量检索

- 文档序号：123
- 分类：应用集成类 / 知识库检索 / 文档知识库批量检索
- 唯一编码：sfm.api.kortex.kortex.api.kb.doc.combination.retrieve
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/doc/combination/retrieve
- 文档版本：1787280869951

## 接口概述

支持同时检索多个文档知识库，每个知识库可配置不同的检索参数，最大支持10个知识库同时检索。

批量检索接口支持多文档知识库同时检索，返回每个知识库的独立结果，适用于需要同时从多个文档知识库获取数据的场景。

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
| combinationParams | List<Object> | 是 | Body | 检索参数列表 | [{"kbCode":"xxx","query":"测试","score":0.01,"limit":10}] |
| combinationParams.kbCode | String | 是 |  | 知识库编码 | tttbnz21dien |
| combinationParams.query | String | 是 |  | 查询内容 | 测试查询 |
| combinationParams.score | Double | 是 |  | 最小分值 | 0.01 |
| combinationParams.limit | Integer | 是 |  | 返回条目 | 10 |
| combinationParams.mapBatchKey | String | 否 |  | 批量检索时的结果映射KEY，用于区分不同请求的结果 | kb1 |
| combinationParams.kbIndexEngineType | String | 否 |  | 索引引擎类型，可选值: builtin_vector(向量索引引擎), builtin_es(全文索引引擎) | builtin_vector |
| combinationParams.filters | Object | 否 | Body | 过滤条件 | 扩展过滤项, {"fileCodes": ["d110d4f793e347bdb8aaf840b3e3d27a","8a58578fce264cd3a648162ea94d2686"]}  |
| combinationParams.chunkConfig | Object | 否 |  | Chunk扩展配置 | {"chunkBefore": 2, "chunkAfter": 2, "withNeighborChunks": true} |
| combinationParams.chunkConfig.chunkBefore | Integer | 否 |  | 返回前N个相邻chunk数量，最大不超过5 | 2 |
| combinationParams.chunkConfig.chunkAfter | Integer | 否 |  | 返回后N个相邻chunk数量，最大不超过5 | 2 |
| combinationParams.chunkConfig.withNeighborChunks | Boolean | 否 |  | 是否返回相邻chunk内容列表 | true |
| combinationParams.fusionType | String | 否 |  | 融合检索类型，可选值: lws(线性加权), rrf(互惠排名融合)。为空时表示不使用融合检索 | lws |
| combinationParams.fusionConfig | Object | 否 |  | 融合检索配置，只有fusionType不为空时才需要设置 | {"textScore": 0.5, "vectorScore": 0.5, "topKText": 20, "topKVec": 20, "topN": 10, "keywordWeight": 0.5, "rankDiscount": 60} |
| combinationParams.fusionConfig.topKText | Integer | 否 |  | 全文检索返回条数，默认使用limit | 20 |
| combinationParams.fusionConfig.topKVec | Integer | 否 |  | 向量检索返回条数，默认使用limit | 20 |
| combinationParams.fusionConfig.topN | Integer | 否 |  | 融合检索后返回条数，默认使用limit | 10 |
| combinationParams.fusionConfig.textScore | Double | 否 |  | 全文检索分数阈值，融合检索时使用，默认0.5 | 0.5 |
| combinationParams.fusionConfig.vectorScore | Double | 否 |  | 向量检索分数阈值，融合检索时使用，默认0.5 | 0.5 |
| combinationParams.fusionConfig.keywordWeight | Float | 否 |  | 关键词权重(LWS融合时使用)，越大越偏向于全文检索-BM25，默认0.5 | 0.5 |
| combinationParams.fusionConfig.rankDiscount | Integer | 否 |  | RRF名次衰减系数(RRF融合时使用)，越大越不看重头部排名，默认60 | 60 |
| combinationParams.needFileInfo | Boolean | 否 |  | 是否需要返回文件信息 | true |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  |  | 是否成功 | true |
| data | List<Object> | 是 | Body | 批量检索结果列表 | [] |
| data.mapBatchKey | String |  |  | 结果映射KEY（对应请求中的mapBatchKey） | kb1 |
| data.kbCode | String |  |  | 知识库编码 | xxx |
| data.result | List<KbdocRetrieveItem> |  |  | 检索结果列表 | [{"sys_data_id":"xxx","file_code":"yyy","chunk_content":"内容","score":0.85}] |
| data.result.score | String |  |  | 检索结果的相关性得分，根据检索类型不同含义不同，单引擎检索保持原始语义，融合检索经归一化处理用于统一评分标准。1）单引擎检索：保持原始引擎的语义，向量检索为余弦相似度(0-1)，全文检索为BM25相关性得分；2）LWS融合：线性加权融合得分，经归一化处理；3）RRF融合：基于排名的互惠排名融合得分。 | 0.5 |
| data.result.sys_data_id | String |  |  | 数据唯一ID; | 59cc2523-8445-4f3a-91f7-5e311f5530b2 |
| data.result.file_name | String |  |  | 文件名称(当needFileInfo为true时返回) | document.pdf |
| data.result.file_url | String |  |  | 文件URL(当needFileInfo为true时返回 带有STS临时认证信息的地址) | https://example.com/files/document.pdf |
| data.result.file_type | String |  |  | 文件类型(当needFileInfo为true时返回) | pdf |
| data.result.sys_create_time | String |  |  | 数据创建时间; | 2023-04-01T12:34:56Z |
| data.result.file_code | String |  |  | 文件编码(当needFileInfo为true时返回) | 123456 |
| data.result.chunk_upload_type | Integer | 是 | Body | 上传类型 | 1 |
| data.result.chunk_content | String | 是 | Body | chunk内容 - 召回后送入LLM的prompt文本 |  |
| data.result.show_content | String | 是 | Body | chunk内容 - 带有bbox和objects占位符的文本形式 |  |
| data.result.chunk_bboxs | List<Object> | 是 | Body | bbox坐标信息 |  |
| data.result.chunk_bboxs.text_bbox | List<Double> | 是 | Body | 坐标 | [<br>					0.3115,<br>					0.0683,<br>					0.0285,<br>					0.372<br>				] |
| data.result.chunk_bboxs.text_type | String | 是 | Body | 文本类型 | docTitle |
| data.result.chunk_bboxs.text_content | String | 是 | Body | 文本内容 | 汇丰香港账户使用指南<br> |
| data.result.chunk_bboxs.page | Integer | 是 | Body | 页数 | 1 |
| data.result.start_page | Integer | 是 | Body | chunk序号 | 1 |
| data.result.chunk_sort_number | Integer | 是 | Body | 页码 | 0 |
| data.result.beforeChunks | List<KbdocChunkNeighbor> |  |  | 前N个相邻chunks(当chunkBefore>0时返回) | [{"sysDataId":"xxx","fileCode":"yyy","chunkContent":"内容"}] |
| data.result.afterChunks | List<KbdocChunkNeighbor> |  |  | 后N个相邻chunks(当chunkAfter>0时返回) | [{"sysDataId":"xxx","fileCode":"yyy","chunkContent":"内容"}] |
| data.result.neighborChunkContents | List<String> |  |  | 相邻chunk内容列表(当withNeighborChunks为true时返回) | ["前chunk内容","检索chunk内容","后chunk内容"] |
| data.metrics | Object |  |  | 性能指标 | {} |
| data.metrics.kbCode | String |  |  | 知识库编码 | xxx |
| data.metrics.totalTime | Long |  |  | 检索总耗时(ms) | 150 |
| data.metrics.chunksCount | Integer |  |  | 返回的chunk数量 | 10 |
| data.metrics.fusionType | String |  |  | 融合方法类型 | lws |
| data.metrics.rrfTime | Long |  |  | RRF融合耗时(ms)，仅RRF融合时有值 | 20 |
| data.metrics.lwsTime | Long |  |  | LWS融合耗时(ms)，仅LWS融合时有值 | 15 |
| data.metrics.fillTime | Long |  |  | 附加信息填充耗时(ms) | 30 |
| data.metrics.retrievalDetails | List<Object> |  |  | 详细检索指标 | [] |
| data.metrics.retrievalDetails.kbIndexCode | String |  |  | 索引编码 | ozqn95a5936ycwkl |
| data.metrics.retrievalDetails.engineType | String |  |  | 引擎类型 | builtin_vector |
| data.metrics.retrievalDetails.embeddingTime | Long |  |  | 向量嵌入耗时(ms) | 50 |
| data.metrics.retrievalDetails.vectorRecallTime | Long |  |  | 向量召回耗时(ms) | 80 |
| data.metrics.retrievalDetails.textQueryTime | Long |  |  | 全文检索耗时(ms) | 60 |
| data.metrics.retrievalDetails.retrievedChunksCount | Integer |  |  | 该引擎实际召回的chunk数量 | 10 |
| data.success | Boolean |  |  | 是否检索成功 | true |
| data.errorMessage | String |  |  | 错误信息(检索失败时返回) | 知识库不存在 |
| errorCode | String |  |  | 错误码 |  |
| errorMsg | String |  |  | 错误描述 |  |


## 请求示例

#### 批量检索2个文档知识库示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/doc/combination/retrieve \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "combinationParams":[
        {
            "kbCode":"kbcode1",
            "query":"测试查询1",
            "score":0.01,
            "limit":5,
            "mapBatchKey":"kb1"
        },
        {
            "kbCode":"kbcode2",
            "query":"测试查询2",
            "score":0.01,
            "limit":5,
            "mapBatchKey":"kb2",
            "fusionType":"lws",
            "topKText":20,
            "topKVec":20,
            "topN":5
        }
    ]
}'
```


## 响应示例

#### 批量检索返回示例

```json
{"success":true,"data":[{"mapBatchKey":"ozqn95a5936y","kbCode":"ozqn95a5936y","result":[{"sys_data_id":"59cc2523-8445-4f3a-91f7-5e311f5530b2","file_code":"89549201e6e24b0f83a328863701b593","chunk_content":"xxxxxxxxxxxx","score":0.5},{"sys_data_id":"ab4a788d-889e-4916-bc53-d09ae943c12d","file_code":"89549201e6e24b0f83a328863701b593","chunk_content":"xxxxxxxxxxxx","score":0.5},{"sys_data_id":"fe422a14-cecf-4fe8-a8ec-1ae9c8760a21","file_code":"89549201e6e24b0f83a328863701b593","chunk_content":"xxxxxxxxxxxx","score":0}],"metrics":{"kbCode":"ozqn95a5936y","totalTime":220,"chunksCount":3,"fusionType":"LWS","rrfTime":null,"lwsTime":0,"fillTime":0,"retrievalDetails":[{"kbIndexCode":"ozqn95a5936ysvdl","engineType":"builtin_es","embeddingTime":null,"vectorRecallTime":null,"textQueryTime":21,"retrievedChunksCount":1},{"kbIndexCode":"ozqn95a5936ycwkl","engineType":"builtin_vector","embeddingTime":153,"vectorRecallTime":35,"textQueryTime":null,"retrievedChunksCount":2}]},"success":true,"errorMessage":null}],"errorCode":null,"errorMsg":null,"traceId":null,"env":null,"ext":null}
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

- apiCode：kortex.api.kb.doc.combination.retrieve
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
