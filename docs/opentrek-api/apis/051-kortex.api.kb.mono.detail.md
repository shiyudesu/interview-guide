# 知识库详情查询

- 文档序号：051
- 分类：平台功能类 / 知识库管理 / 知识库详情查询
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.mono.detail
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/mono/detail
- 文档版本：1787280870389

## 接口概述

获取知识库的数据模型定义等详情数据

查看知识库详情中的数据模型定义,用于后续检索或者写入场景传参,模板创建的数据模型结构固定,自定义场景由用户自行定义。问答知识库(kbType=204)的数据模型包含question和answer字段；术语知识库(kbType=205)的数据模型包含term和definition字段。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| code | String | 是 | Body | 知识库唯一编码 | rkiviej5rkm2 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.code | String | 是 | Body | 知识库唯一编码 | tzf5wnyvkfdg |
| data.name | String | 是 | Body | 知识库名称 | 央久验证 |
| data.description | String | 是 | Body | 知识库描述 | 年报文档 |
| data.kbType | Integer | 是 | Body | 知识库类型 | 100,"自定义知识库",<br>    201,"文档知识库",<br>    202,"BI知识库",<br>   203,"图文知识库",<br>    204,"问答知识库",<br>   205,"术语知识库" |
| data.kbProperties | Object | 是 | Body | 知识库扩展属性,见 知识库创建 接口相关同名字段释义 |  |
| data.kbProperties.null |  |  |  |  |  |
| data.kbSubmodels | List<Object> | 是 | Body | 知识库数据模型,见 知识库创建 接口相关同名字段释义 |  |
| data.kbSubmodels.kbSubmodelName | String | 是 | Body | 自定义 标准知识库名称 |  |
| data.kbSubmodels.kbSubmodelCode | String | 是 | Body | 自定义 标准知识库数据模型唯一编码 |  |
| data.kbSubmodels.kbSubmodelFields | List<Object> | 是 | Body | 自定义 标准知识库 包含的属性信息 |  |
| data.kbSubmodels.kbSubmodelFields.fieldName | String | 是 | Body | 字段名称, 数据库字段命名语法, 驼峰场景以下划线衔接  | matter_name |
| data.kbSubmodels.kbSubmodelFields.fieldComment | String | 是 | Body | 字段释义 | 事项名称 |
| data.kbSubmodels.kbSubmodelFields.fieldType | String | 是 | Body | 字段类型 varchar\|varchar_64\|varchar_256\|varchar_1024\|integer | varchar_1024 |
| data.kbSubmodels.kbSubmodelFields.fieldIndexExt | String | 是 | Body | 索引相关扩展描述 | filter |
| data.kbSubmodels.kbSubmodelFields.kbSubmodelCode | String | 是 | Body | 归属数据模型 编码 |  |
| data.kbSubmodels.kbSubmodelFields.kbCode | String | 是 | Body | 归属知识库 编码 |  |
| data.kbSubmodels.kbIndexes | List<Object> | 是 | Body | 自定义 标准知识库 包含的索引信息 |  |
| data.kbSubmodels.kbIndexes.kbIndexCode | String | 是 | Body | 索引存储 唯一编码 |  |
| data.kbSubmodels.kbIndexes.kbSubmodelCode | String | 是 | Body | 归属数据模型 编码 |  |
| data.kbSubmodels.kbIndexes.kbCode | String | 是 | Body | 归属知识库 编码 |  |
| data.kbSubmodels.kbIndexes.kbIndexEngineType | String | 是 | Body | 索引类型 builtin_vector:向量索引引擎; builtin_es:全文索引引擎  | builtin_vector |
| data.kbSubmodels.kbIndexes.kbIndexName | String | 是 | Body | 索引定义名称 | 事项名称匹配 |
| data.kbSubmodels.kbIndexes.kbIndexFields | List<Object> | 是 | Body | 索引字段定义 |  |
| data.kbSubmodels.kbIndexes.kbIndexFields.fieldName | String | 是 | Body | 字段名称, 数据库字段命名语法, 驼峰场景以下划线衔接  | matter_name |
| data.kbSubmodels.kbIndexes.kbIndexFields.fieldIndexType | String | 是 | Body | 字段索引 类型 resource用于召回; retrieve用于检索 | resource |
| data.kbSubmodels.kbIndexes.kbIndexProperties | Object | 是 | Body | 文本向量化模型数据封装 |  |
| data.kbSubmodels.kbIndexes.kbIndexProperties.model | Object | 是 | Body | 文本向量化模型配置, 结构同上述 textModel, 必须选择 modelType=EMBEDDING 的模型配置 |  |
| data.kbSubmodels.kbIndexes.kbIndexProperties.indexType | String | 是 | Body | 索引 类型 vector\|es | vector |
| data.refRes | String | 是 | Body | 知识库引用资源 |  |
| data.disableFlag | Integer | 是 | Body | 是否启用 | 1 |
| data.createTime | String | 是 | Body | 创建时间 | 2025-07-16T15:00:24.192928 |
| data.createUser | String | 是 | Body | 知识库创建者 | dke |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/mono/detail \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "code":"rkiviej5rkm2"
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"code":"z7pn9wbtkpy0","name":"自定义知识库","description":"测试自定义知识库创建","kbType":100,"kbProperties":null,"kbSubmodels":[{"kbSubmodelCode":"z7pn9wbtkpy0x6l8","kbSubmodelName":"标准知识库","kbSubmodelFields":[{"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","fieldName":"matter_code","fieldType":"varchar_256","fieldComment":"事项编码","fieldDefaultValue":null,"fieldIndexExt":null},{"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","fieldName":"matter_name","fieldType":"varchar_256","fieldComment":"事项名称","fieldDefaultValue":null,"fieldIndexExt":null}],"kbIndexes":[{"kbCode":"z7pn9wbtkpy0","kbSubmodelCode":"z7pn9wbtkpy0x6l8","kbIndexCode":"z7pn9wbtkpy0w83n","kbIndexName":"事项名称匹配","kbIndexEngineType":"builtin_vector","kbIndexProperties":{"indexType":"vector","dimensionSize":1536,"model":{"abilities":[],"modelName":"新版文本向量","path":"/api/batch_predict_embeddings","modelSource":"system","modelExtParams":[],"customModelMappings":[],"modelCode":"rsv-e9modnqp","invokeUrl":"http://ai-gateway-svc:8090/v1/router/call/rsv-e9modnqp","modelConfigMode":"normal","modelType":"EMBEDDING","source":"system"}},"kbIndexFields":[{"fieldName":"matter_code","fieldIndexType":"resource"},{"fieldName":"matter_name","fieldIndexType":"retrieve"}]}]}],"refRes":null,"disableFlag":0,"createTime":"2025-07-22T22:59:48.073965","updateTime":"2025-07-22T22:59:48.073969","createUser":"gaochai"},"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.mono.detail
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
