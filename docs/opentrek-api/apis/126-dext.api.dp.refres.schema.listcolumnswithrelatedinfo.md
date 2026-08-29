# 数据表知识库资源查询-字段

- 文档序号：126
- 分类：应用集成类 / 知识库检索 / 数据表知识库资源查询-字段
- 唯一编码：sfm.api.kortex.dext.api.dp.refres.schema.listcolumnswithrelatedinfo
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/schema/listColumnsWithRelatedInfo
- 文档版本：1787280869970

## 接口概述

通过API查询指定知识库下指定表的字段详细信息。您可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

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
| tableCode | String | 是 | body | 表code | 6174366442861c023cba74c26321cd8a |
| current | Integer | 是 | body | 当前页数 | 1 |
| pageSize | Integer | 是 | body | 分页大小, 不能超过1000 | 10 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 接口是否调用成功 | true |
| data | JSONObject | 是 | body | 数据节点 |  |
| data.total | Integer | 是 | body | 总条目数 | 100 |
| data.list | JSONArray | 是 | body | 检索返回数据列表 | true |
| data.list.dpCode | String | 是 | body | 知识库id | 2688caccbe93fdd26b66195ebf7c1f2d |
| data.list.tableCode | String | 是 | body | 表code | ca2cbfb7928d59547a3a28a044467b15 |
| data.list.columnCode | String | 是 | body | 字段code | ca2cbfb7928d59547a3a28a044467b15 |
| data.list.columnName | String | 是 | body | 原始字段名 | col_student_name |
| data.list.columnCommentExt | String | 是 | body | 字段注释, 优先取页面手工修正的注释, 否则取源数据库中对应的注释 | 学生姓名 |
| data.list.tags | JSONObject | 是 | body | 知识库中维护的扩展配置, 格式为key: value | {"随表召回":"是"} |
| data.list.refDims.dims[*] | JSONArray | 否 | body | 相关维度, 为一个深层jsonpath路径 |  |
| data.list.refDims.dims[*].code | String | 是 | body | 维度表code |  |
| data.list.refDims.dims[*].name | String | 是 | body | 维度表名称 |  |
| data.list.refDims.dims[*].refDimType | Integer | 是 | body | 相关维度 |  |


## 请求示例

#### 示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/schema/listColumnsWithRelatedInfo \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: test' \
-H 'Content-Type: application/json' \
-d '{
    "dpCode":"094107a115f64f5c8770aa1c3a0d0c3c",
    "tableCode":"08dc4cbfef7c477e8ab9f50417678fd4"
}'
```


## 响应示例

#### 示例

```json
{
    "success": true,
    "data": {
        "total": 20,
        "list": [
            {
                "dpCode": "094107a115f64f5c8770aa1c3a0d0c3c",
                "tableCode": "08dc4cbfef7c477e8ab9f50417678fd4",
                "columnCode": "e5e66de1d72a48bab699a599dcf78040",
                "columnName": "student_name",
                "columnCommentExt": "学生姓名",
                "tags": {
                    "随表召回": "是"
                },
                "includeValue": 0,
                "refDims": {
                    "dims": [
                        {
                            "code": "0d57e22c692a4c83a4de24fb1bb064b9",
                            "name": "学生名单表",
                            "refDimType": 1
                        }
                    ]
                }
            },
            {
                "dpCode": "094107a115f64f5c8770aa1c3a0d0c3c",
                "tableCode": "08dc4cbfef7c477e8ab9f50417678fd4",
                "columnCode": "e911596b0c8648378b41c22fcdabe7e8",
                "columnName": "score",
                "columnCommentExt": "考试成绩",
                "tags": null,
                "includeValue": 0,
                "refDims": null
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

- apiCode：dext.api.dp.refres.schema.listcolumnswithrelatedinfo
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
