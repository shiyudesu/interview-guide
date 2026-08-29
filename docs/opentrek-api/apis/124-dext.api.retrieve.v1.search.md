# 数据表知识库检索服务

- 文档序号：124
- 分类：应用集成类 / 知识库检索 / 数据表知识库检索服务
- 唯一编码：sfm.api.kortex.dext.api.retrieve.v1.search
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/retrieve/v1/search
- 文档版本：1787280869958

## 接口概述

根据查询文本在已构建好索引的知识库-数据表中进行向量或文本的检索。您可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

先进入菜单[主页->点击头像->APP_KEY]创建APP_KEY;然后访问菜单[主页->点击头像->空间管理],获取目标空间编码;空间管理菜单看不到的请联系租户管理员或目标空间管理员.

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| Content-Type | String | 是 | header | Content-Type | application/json |
| x-sfm-workspacecode | String | 是 | header | 工作空间编码 | 87f52c24f9bb47b1ac1e8716c392da65 |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| dataPortfolioCode | String | 是 | body | 知识库code | 82168c22b87d494cb9b5e813e215ae9b |
| domainName | String | 是 | body | 知识库下domain名称, 取值范围:  table(表列信息), value(值), knowledge(知识), biSample(样例库/ICL), dimension(维度) | table |
| query | String | 是 | body | 查询的文本内容 | 西湖区 |
| returnNum | Integer | 是 | body | 返回数量, 最大不能超过100 | 10 |
| score | Double | 是 | body | 分数过滤阈值 |  |
| storeEngine | String | 是 | body | 索引类型, 包括: vector(向量), text(文本) | vector |
| domainFilters | JSONObject | 否 | body | 特定domain下可以支持的搜索filter参数, 不同domain支持的搜索范围不同, 具体支持范围见示例 | domain - knowledge, storeEngine - vector<br>{<br>    "domainFilters":{<br>        "scopeOfAllTables":false,<br>        "category":"术语解释",<br>        "tableCodes":["e5e66de1d72a48bab699a599dcf78040"],<br>        "columnCodes":["e5e66de1d72a48bab699a599dcf78040"]<br>    }<br>}<br>domainFilters参数解释:<br>scopeOfAllTables: false - 限定为非全库, true - 限定为全库<br>category: 知识分组<br>tableCodes: 表code, 来自知识库-表接口, 为这条知识相关表, 相关字段所在的表<br>columnCodes: 字段code, 来自知识库-字段接口, 为这条知识相关的表<br><br>domain - value, storeEngine - text<br>{<br>    "domainFilters":{<br>        "tableCodes":["66024e2bf01541da93e3bd04cdf946a5"],<br>        "columnCodes":["758f112ee7a84f4684dd5a893ddf1430"]<br>    }<br>}<br>domainFilters参数解释:<br>tableCodes: 表code, 来自知识库-表接口, 为这个值所在的表<br>columnCodes: 字段code, 来自知识库-字段接口, 为这个值所在的字段<br><br>domain - dimension, storeEngine - text<br>{<br>    "domainFilters":{<br>        "dimDsCodes":["3c2e30a6873b4717890e0adf3c70781c"]<br>    }<br>}<br>domainFilters参数解释:<br>dimDsCodes: 维度表code, 来自字段接口出参, refDims |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 接口是否调用成功 | true |
| data | Object | 是 | body | 数据节点 |  |
| data.items | JSONArray | 是 | body | 检索返回数据列表 | true |
| data.items.score | Double | 是 | body | 排序得分的浮点数，值越大相似性越高 | 0.334 |
| data.items.content | String | 是 | body | 召回的文本内容 | XX工厂第二车间 |
| data.items.resources | JSONObject | 是 | body | 召回的文本内容所在的结构化数据, 对于不同的domain结构不同, 见示例 | table(表列信息)<br>{<br>    "resources": {<br>        "schema": {<br>            "tables": [<br>                {<br>                    "table": {<br>                        "columns": [<br>                            {<br>                                "columnComment": "团队名称",<br>                                "columnCode": "083b4109b21a4c58b555e6885a320667",<br>                                "columnName": "team_name"<br>                            }<br>                        ],<br>                        "tableCode": "2dda169434a342f6b6233940e69c883a",<br>                        "tableName": "llm_dev_inventory"<br>                    }<br>                }<br>            ]<br>        }<br>    }<br>}<br>参数解释:<br>tableCode: 表code<br>tableName: 原始表名<br>columnCode: 字段code<br>columnName: 原始字段名<br>columnComment: 字段注释, 优先取页面手工修正的注释, 否则取源数据库中对应的注释<br><br>value(值)<br>{<br>    "resources": {<br>        "value": {<br>            "columnCode": "eb19cfa9308b467c8fda8bc3ef84380c",<br>            "value": {<br>                "value": "张三"<br>            },<br>            "tableName": "llm_dev_input_inventory",<br>            "columnName": "alias"<br>        }<br>    }<br>}<br>参数解释:<br>columnCode: 字段code<br>value: 源库中实际的value<br>tableName: 原始表名<br>columnName: 原始字段名<br><br>knowledge(知识)<br>{<br>    "resources": {<br>        "knowledge": {<br>            "code": "ec231f17cfbc40e08afef23c066c2d37",<br>            "name": "张三团队",<br>            "refRes": {<br>                "schema": {<br>                    "columnCodes": [],<br>                    "tables": [],<br>                    "allTables": true,<br>                    "tableCodes": []<br>                }<br>            },<br>            "content": "研发组，主管为张三"<br>        }<br>    }<br>}<br>参数解释:<br>code: 该条知识的系统code<br>name: 知识名称<br>content: 知识内容<br>refRes: 该条知识绑定的资源, 参考知识库资源查询 - 专家知识部分refRes节点解释<br><br>biSample(样例库/ICL)<br>{<br>    "resources": {<br>        "biSample": {<br>            "code": "9fa48139fc6043889856a06332e64e01",<br>            "query": "上周兵力大盘情况?",<br>            "sql": "select project_name , sum(actual_input) from llm_dev_inventory where week_start >= DATE_SUB(CURRENT_DATE, INTERVAL 7 day) group by project_name"<br>        }<br>    }<br>}<br>参数解释:<br>code: 该条样例的系统code<br>query: 样例库-query, 如'查询最高的分数'<br>sql: 样例库-sql, 如'select max(score) from exam;'<br><br>dimension(维度)<br>{<br>    "resources": {<br>        "dimension": {<br>            "dimDsCode": "9fa48139fc6043889856a06332e64e01",<br>            "key": "1",<br>            "value": "男性"<br>        }<br>    }<br>}<br>参数解释:<br>dimDsCode: 知识库维度表对应的code<br>key: 对应的维度键, 如'1'<br>value: 对应的维度值, 如'男性' |


## 请求示例

#### 示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/retrieve/v1/search \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: test' \
-H 'Content-Type: application/json' \
-d '{
    "dataPortfolioCode":"543eec8256cf40418d18c009ad9b319b",
    "domainName":"dimension",
    "query":"公司",
    "returnNum":10,
    "score":0.52,
    "domainFilters":{
        "dimDsCodes":["3c2e30a6873b4717890e0adf3c70781c"]
    },
    "storeEngine":"text"
}'
```


## 响应示例

#### 示例

```json
{
    "success": true,
    "data": [
        {
            "score": 1.0809742,
            "indexCode": "94bff03a24df40138044a5da0e601cff",
            "dataPortfolioCode": "543eec8256cf40418d18c009ad9b319b",
            "domainName": "dimension",
            "content": "华润置地有限公司",
            "contentIndex": 0,
            "sysTag": null,
            "resources": {
                "dimension": {
                    "dimDsName": "3c2e30a6873b4717890e0adf3c70781c",
                    "dimDsCode": "3c2e30a6873b4717890e0adf3c70781c",
                    "value": "华润置地有限公司",
                    "key": "华润置地有限公司"
                }
            },
            "tag": null,
            "version": null
        },
        {
            "score": 1.0809742,
            "indexCode": "e4d32d35aca84ee18d940a5d411b5453",
            "dataPortfolioCode": "543eec8256cf40418d18c009ad9b319b",
            "domainName": "dimension",
            "content": "碧桂园控股有限公司",
            "contentIndex": 0,
            "sysTag": null,
            "resources": {
                "dimension": {
                    "dimDsName": "3c2e30a6873b4717890e0adf3c70781c",
                    "dimDsCode": "3c2e30a6873b4717890e0adf3c70781c",
                    "value": "碧桂园控股有限公司",
                    "key": "碧桂园控股有限公司"
                }
            },
            "tag": null,
            "version": null
        }
    ],
    "errorCode": null,
    "errorMsg": null,
    "traceId": null,
    "env": null,
    "ext": null
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
| 404 | GATEWAY ROUTE URL NOT FOUND! | 无效的目标服务地址 |
| 401 | GATEWAY LIMIT ! | 服务链接已达上限,请稍后再试 |
| 500 | TARGET_SERVICE_ERROR_CONNECTION_REFUSE_EXCEPTION | 目标服务拒绝连接 |
| 500 | TARGET_SERVICE_ERROR_NO_RESPONSE_EXCEPTION | 目标服务无响应 |



## 原始文档标识

- apiCode：dext.api.retrieve.v1.search
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
