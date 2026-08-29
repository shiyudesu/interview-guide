# 知识库创建

- 文档序号：046
- 分类：平台功能类 / 知识库管理 / 知识库创建
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.create
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/create
- 文档版本：1787280870360

## 接口概述

创建知识库

创建知识库。支持创建的知识库类型包括：100(自定义知识库)、201(文档知识库)、202(BI知识库)、203(图文知识库)、204(问答知识库)、205(术语知识库)。问答知识库数据模型包含question和answer两个字段；术语知识库数据模型包含term和definition两个字段。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| name | String | 是 | Body | 知识库名称 | 测试 |
| description | String | 是 | Body | 知识库描述 | 测试 |
| kbType | Integer | 是 | Body | 知识库类型 | 100,"自定义知识库",<br>    201,"文档知识库",<br>    202,"BI知识库",<br>   203,"图文知识库",<br>    204,"问答知识库",<br>   205,"术语知识库" |
| kbProperties | Object | 是 | Body | 泛化属性(不同知识库类型,要求必传的信息不同, 自定义知识库可不传) |  |
| kbProperties.processStrategy | Object | 是 | Body | 文档知识库(策略详细配置) |  |
| kbProperties.processStrategy.chunkStrategyMethod | String | 是 | Body | 分段策略, 默认传递 default  | default |
| kbProperties.processStrategy.processStrategyMethod | String | 是 | Body | 解析策略方式 (simple 基础解析[只提取文档中文字]; deep 深度解析[增加图片、表格、公式等解析能力] ) | deep |
| kbProperties.processStrategy.processDeepConfigs | List<Object> | 是 | Body | 解析策略方式 (simple 基础解析[只提取文档中文字]; deep 深度解析[增加图片、表格、公式等解析能力] ) |  |
| kbProperties.processStrategy.processDeepConfigs.key | String | 是 | Body | 深度解析可开启解析配置类型 image_ocr:图片OCR; table_parse:表格解析; equation_parse:公式解析; if_figure_enhance:图片理解 |  |
| kbProperties.processStrategy.processDeepConfigs.enable | String | 是 | Boolean | 是否开启 | true |
| kbProperties.textModel | Object | 是 | Body | 文档知识库、问答知识库、术语知识库(文本向量化模型); <br> 模型相关参数可以通过先在平台手动创建后,调用知识库详情接口获取响应,解析对应模型参数结构后作为默认参数使用,模型参数必须有效可用,且一旦创建后涉及向量的生成,无法更改 |  |
| kbProperties.textModel.modelType | String | 是 | Body | 模型类型,该场景智能传递“EMBEDDING”类型的模型数据 |  |
| kbProperties.textModel.invokeUrl | String | 是 | Body | 模型调用内部服务地址 |  |
| kbProperties.textModel.path | String | 是 | Body | 模型调用相对路径地址 |  |
| kbProperties.textModel.modelConfigMode | String | 是 | Body | 模型配置类型,可默认传递 normal | normal |
| kbProperties.textModel.modelSource | String | 是 | Body | 模型来源,可默认传递 system | system |
| kbProperties.textModel.modelCode | String | 是 | Body | 模型编码 |  |
| kbProperties.textModel.modelName | String | 是 | Body | 模型名称 |  |
| kbProperties.visualProcess | Boolean | 是 | Body | 图文知识库(是否开启智能解析) |  |
| kbProperties.visualProcessModel | Object | 是 | Body | 图文知识库(多模态问答模型),结构同上述 textModel, 必须选择 modelType=vlm 的模型配置;<br> <br> 模型相关参数可以通过先在平台手动创建后,调用知识库详情接口获取响应,解析对应模型参数结构后作为默认参数使用,模型参数必须有效可用 |  |
| kbProperties.visualDescPrompt | String | 是 | Body | 图文知识库(多模态问答Prompt,用于识别并描述图片内容) | 请用简短的语句描述该图，不要带入情感和发散。 |
| kbProperties.visualIndexModel | Object | 是 | Body | 图文知识库(多模态向量化模型),结构同上述 textModel, 必须选择 modelType=MM_EMBEDDING 的模型配置; <br> 模型相关参数可以通过先在平台手动创建后,调用知识库详情接口获取响应,解析对应模型参数结构后作为默认参数使用,模型参数必须有效可用,且一旦创建后涉及向量的生成,无法更改 |  |
| kbProperties.indexTrigger | String | 是 | Body | 图文知识库(向量化机制,默认传递 upload) | upload |
| kbSubmodels | List<Object> | 是 | Body | 自定义知识库 必传 数据模型定义 |  |
| kbSubmodels.kbSubmodelName | Boolean | 是 | Body | 自定义 标准知识库名称 |  |
| kbSubmodels.kbSubmodelFields | List<Object> | 是 | Body | 自定义 标准知识库 包含的属性信息 |  |
| kbSubmodels.kbSubmodelFields.fieldName | String | 是 | Body | 字段名称, 数据库字段命名语法, 驼峰场景以下划线衔接  | matter_name |
| kbSubmodels.kbSubmodelFields.fieldComment | String | 是 | Body | 字段释义 | 事项名称 |
| kbSubmodels.kbSubmodelFields.fieldType | String | 是 | Body | 字段类型 varchar\|varchar_64\|varchar_256\|varchar_1024\|integer | varchar_1024 |
| kbSubmodels.kbIndexes | List<Object> | 是 | Body | 自定义 标准知识库 包含的索引信息 |  |
| kbSubmodels.kbIndexes.kbIndexEngineType | String | 是 | Body | 索引类型 builtin_vector:向量索引引擎; builtin_es:全文索引引擎  | builtin_vector |
| kbSubmodels.kbIndexes.kbIndexName | String | 是 | Body | 索引定义名称 | 事项名称匹配 |
| kbSubmodels.kbIndexes.kbIndexFields | List<Object> | 是 | Body | 索引字段定义 |  |
| kbSubmodels.kbIndexes.kbIndexFields.fieldName | String | 是 | Body | 字段名称, 数据库字段命名语法, 驼峰场景以下划线衔接  | matter_name |
| kbSubmodels.kbIndexes.kbIndexFields.fieldComment | String | 是 | Body | 字段释义 | 事项名称 |
| kbSubmodels.kbIndexes.kbIndexFields.fieldType | String | 是 | Body | 字段类型 varchar\|varchar_64\|varchar_256\|varchar_1024\|integer | varchar_1024 |
| kbSubmodels.kbIndexes.kbIndexFields.fieldIndexType | String | 是 | Body | 字段索引 类型 resource用于召回; retrieve用于检索 | resource |
| kbSubmodels.kbIndexes.kbIndexProperties | Object | 是 | Body | 文本向量化模型数据封装 |  |
| kbSubmodels.kbIndexes.kbIndexProperties.model | Object | 是 | Body | 文本向量化模型配置, 结构同上述 textModel, 必须选择 modelType=EMBEDDING 的模型配置 |  |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.stats | Object | 是 | Body | 创建详情 |  |
| data.kbCode | String | 是 | Body | 知识库唯一编码 | y4fu5k9w5yl2 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例[自定义知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/create \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "name":"自定义知识库",
    "description":"测试自定义知识库创建",
    "kbType":"100",
    "kbSubmodels":[{"kbSubmodelName":"标准知识库","kbSubmodelFields":[{"fieldName":"matter_code","fieldComment":"事项编码","fieldType":"varchar_256"},{"fieldName":"matter_name","fieldComment":"事项名称","fieldType":"varchar_256"}],"kbIndexes":[{"kbIndexEngineType":"builtin_vector","kbIndexName":"事项名称匹配","kbIndexFields":[{"fieldName":"matter_code","fieldComment":"事项编码","fieldType":"varchar_256","fieldIndexType":"resource"},{"fieldName":"matter_name","fieldComment":"事项名称","fieldType":"varchar_256","fieldIndexType":"retrieve"}],"kbIndexProperties":{"model":{"modelConfigMode":"normal","modelCode":"rsv-e9modnqp","modelName":"新版文本向量","abilities":[],"modelExtParams":[],"modelType":"EMBEDDING","modelSource":"system","source":"system","customModelMappings":[],"invokeUrl":"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp","path":"/api/batch_predict_embeddings"}}}]}]
}'
```

#### curl命令示例[文档知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/create \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "name":"百炼文档",
    "description":"百炼知识库",
    "kbType":"201",
    "kbProperties":{
        "textModel":{"modelConfigMode":"normal","modelCode":"rsv-e9modnqp","modelVersion":"OPENTREK_MODEL_DEFAULT_VERSION","modelName":"新版文本向量","path":"/api/batch_predict_embeddings","invokeUrl":"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp","modelType":"EMBEDDING","modelSource":"system"},"processStrategy":{"processDeepConfigs":[{"key":"image_ocr","enable":true},{"key":"table_parse","enable":true},{"key":"equation_parse","enable":true}],"chunkCustomConfigs":{},"chunkStrategyMethod":"default","processStrategyMethod":"deep"}
   }
}'
```

#### curl命令示例[问答知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/create \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "name":"问答知识库",
    "description":"测试问答知识库创建",
    "kbType":"204",
    "kbProperties":{
        "textModel":{"modelConfigMode":"normal","modelCode":"rsv-e9modnqp","modelVersion":"OPENTREK_MODEL_DEFAULT_VERSION","modelName":"新版文本向量","path":"/api/batch_predict_embeddings","invokeUrl":"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp","modelType":"EMBEDDING","modelSource":"system"}
    }
}'
```

#### curl命令示例[术语知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/create \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "name":"术语知识库",
    "description":"测试术语知识库创建",
    "kbType":"205",
    "kbProperties":{
        "textModel":{"modelConfigMode":"normal","modelCode":"rsv-e9modnqp","modelVersion":"OPENTREK_MODEL_DEFAULT_VERSION","modelName":"新版文本向量","path":"/api/batch_predict_embeddings","invokeUrl":"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp","modelType":"EMBEDDING","modelSource":"system"}
    }
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"stats":{"metaAffects":{"kbIndex":{"deletes":0,"inserts":1},"kb":{"inserts":1},"kbSubmodelField":{"deletes":0,"inserts":2},"kbSubmodel":{"deletes":0,"inserts":1},"kbIndexField":{"deletes":0,"inserts":2}},"ddlStats_smod":{"deletes":{},"fieldInserts":{},"inserts":{"z7pn9wbtkpy0x6l8":{"kbSubmodelEntity":{"id":458,"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","kbSubmodelName":"标准知识库","projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.086900569","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.086903719","updateUser":"gaochai"},"kbSubmodelFieldEntities":[{"id":3041,"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","fieldName":"matter_code","fieldType":"varchar_256","fieldComment":"事项编码","fieldDefaultValue":null,"fieldIndexExt":null,"projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.099405932","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.099409152","updateUser":"gaochai"},{"id":3042,"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","fieldName":"matter_name","fieldType":"varchar_256","fieldComment":"事项名称","fieldDefaultValue":null,"fieldIndexExt":null,"projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.099419083","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.099420433","updateUser":"gaochai"}]}}},"ddlStats_kbidx":{"deletes":{},"fieldInserts":{},"inserts":{"z7pn9wbtkpy0w83n":{"kbIndexEntity":{"id":721,"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","kbIndexCode":"z7pn9wbtkpy0w83n","kbIndexName":"事项名称匹配","kbIndexEngineType":"builtin_vector","kbIndexProperties":"{\"indexType\":\"vector\",\"dimensionSize\":1536,\"model\":{\"modelConfigMode\":\"normal\",\"modelCode\":\"rsv-e9modnqp\",\"modelName\":\"新版文本向量\",\"abilities\":[],\"modelExtParams\":[],\"modelType\":\"EMBEDDING\",\"modelSource\":\"system\",\"source\":\"system\",\"customModelMappings\":[],\"invokeUrl\":\"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp\",\"path\":\"/api/batch_predict_embeddings\"}}","projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.11207465","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.11207763","updateUser":"gaochai"},"kbIndexFieldEntities":[{"id":2305,"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","kbIndexCode":"z7pn9wbtkpy0w83n","fieldName":"matter_code","fieldType":null,"fieldIndexType":"resource","fieldIndexDefinition":"{\"indexType\":\"vector\",\"dimensionSize\":1536,\"model\":{\"modelConfigMode\":\"normal\",\"modelCode\":\"rsv-e9modnqp\",\"modelName\":\"新版文本向量\",\"abilities\":[],\"modelExtParams\":[],\"modelType\":\"EMBEDDING\",\"modelSource\":\"system\",\"source\":\"system\",\"customModelMappings\":[],\"invokeUrl\":\"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp\",\"path\":\"/api/batch_predict_embeddings\"}}","projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.124616445","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.124620155","updateUser":"gaochai"},{"id":2306,"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","kbIndexCode":"z7pn9wbtkpy0w83n","fieldName":"matter_name","fieldType":null,"fieldIndexType":"retrieve","fieldIndexDefinition":"{\"indexType\":\"vector\",\"dimensionSize\":1536,\"vectorFieldName\":\"sys_emb_matter_name\",\"model\":{\"modelConfigMode\":\"normal\",\"modelCode\":\"rsv-e9modnqp\",\"modelName\":\"新版文本向量\",\"abilities\":[],\"modelExtParams\":[],\"modelType\":\"EMBEDDING\",\"modelSource\":\"system\",\"source\":\"system\",\"customModelMappings\":[],\"invokeUrl\":\"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp\",\"path\":\"/api/batch_predict_embeddings\"}}","projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.124630415","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.124631745","updateUser":"gaochai"}]}}}},"kbCode":"z7pn9wbtkpy0"},"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.create
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
