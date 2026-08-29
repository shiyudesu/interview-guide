# 数据表知识库资源查询-专家知识

- 文档序号：127
- 分类：应用集成类 / 知识库检索 / 数据表知识库资源查询-专家知识
- 唯一编码：sfm.api.kortex.dext.api.dp.refres.flexext.list
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/flexExt/list
- 文档版本：1787280869976

## 接口概述

通过API查询指定知识库下绑定的专家知识信息。您可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

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
| dpCode | String | 是 | body | 知识库code | 82168c22b87d494cb9b5e813e215ae9b |
| current | Integer | 是 | body | 当前页数 | 1 |
| pageSize | Integer | 是 | body | 分页大小, 不能超过1000 | 10 |
| scopeOfAllTables | Boolean | 否 | body | 是否整库过滤项: null -> 不限制; true -> 整库级别; false -> 非整库级别 | true |
| tableCodes | String[] | 否 | body | 过滤项: 表级知识和列级知识所在的tableCodes |  |
| columnCodes | String[] | 否 | body | 过滤项: 列级知识所在的columnCodes |  |
| categories | String[] | 否 | body | 过滤项: 知识分组 |  |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 接口是否调用成功 | true |
| data | JSONObject | 是 | body | 数据节点 |  |
| data.total | Integer | 是 | body | 总条目数 | 100 |
| data.list | JSONArray | 是 | body | 检索返回数据列表 | true |
| data.list.code | String | 是 | body | 知识code | 2688caccbe93fdd26b66195ebf7c1f2d |
| data.list.name | String | 是 | body | 知识名称 | 本院 |
| data.list.content | String | 是 | body | 知识内容 | 本院指的是用户所属的院区 |
| data.list.refRes | JSONObject | 否 | body | 该条知识绑定的资源 |  |
| data.list.refRes.schema | JSONObject | 是 | body | 绑定资源 - 表 |  |
| data.list.refRes.schema.allTables | Boolean | 是 | body | 是否是整库级别, 为true时, 标明为全库级别 |  |
| data.list.refRes.schema.tableCodes | String[] | 是 | body | tables下所有表级知识和列级知识所在的tableCodes |  |
| data.list.refRes.schema.columnCodes | String[] | 是 | body | tables下所有列级知识所在的columnCodes |  |
| data.list.refRes.schema.tables | JSONObject | 是 | body | 绑定的表级和列级适用范围, 与domain=table时, resources.schema.tables一致 |  |


## 请求示例

#### 示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/flexExt/list \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: test' \
-H 'Content-Type: application/json' \
-d '{
    "current":1,
    "pageSize":10,
    "dpCode":"094107a115f64f5c8770aa1c3a0d0c3c",
    "scopeOfAllTables":true,
    "tableCodes":["08dc4cbfef7c477e8ab9f50417678fd4"],
    "columnCodes":["e5e66de1d72a48bab699a599dcf78040"],
    "categories":["计算口径"]
}'
```


## 响应示例

#### 示例

```json
{
    "success": true,
    "data": {
        "total": 1,
        "list": [
            {
                "code": "263a188399a24bb282c7325b40d4a231",
                "name": "本院",
                "content": "本院指的是用户所属的院区",
                "datasourceCode": "5ca9ab2356b8419094983535587e5d03",
                "tags": null,
                "refRes": {
                    "schema": {
                        "allTables": false,
                        "tables": [
                            {
                                "tableCode": "08dc4cbfef7c477e8ab9f50417678fd4",
                                "tableName": "院区字典表",
                                "allColumns": false,
                                "columns": [
                                    {
                                        "columnCode": "e5e66de1d72a48bab699a599dcf78040",
                                        "columnName": "院区名称"
                                    }
                                ]
                            }
                        ],
                        "tableCodes": [
                            "08dc4cbfef7c477e8ab9f50417678fd4"
                        ],
                        "columnCodes": [
                            "e5e66de1d72a48bab699a599dcf78040"
                        ]
                    }
                }
            }
        ],
        "pageSize": 10,
        "current": 1
    },
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

- apiCode：dext.api.dp.refres.flexext.list
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
