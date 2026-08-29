# 数据表知识库资源查询-表

- 文档序号：125
- 分类：应用集成类 / 知识库检索 / 数据表知识库资源查询-表
- 唯一编码：sfm.api.kortex.dext.api.dp.refres.schema.listtableswithrelatedinfo
- 请求方法：POST
- 调用地址：http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/schema/listTablesWithRelatedInfo
- 文档版本：1787280869964

## 接口概述

通过API查询指定知识库下绑定的表的详细信息。您可以通过查看请求示例，点击 curl命令示例 右侧的调试按钮验证业务接口调用效果。

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

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | boolean | 是 | body | 接口是否调用成功 | true |
| data | JSONObject | 是 | body | 数据节点 |  |
| data.total | Integer | 是 | body | 总条目数 | 100 |
| data.list | JSONArray | 是 | body | 检索返回数据列表 | true |
| data.list.dpCode | String | 是 | body | 知识库id | 2688caccbe93fdd26b66195ebf7c1f2d |
| data.list.tableCode | String | 是 | body | 表code, 为数据库中全局唯一code | ca2cbfb7928d59547a3a28a044467b15 |
| data.list.tableName | String | 是 | body | 原始表名 | tbl_student |
| data.list.tableCommentExt | String | 是 | body | 表注释, 优先取页面手工修正的注释, 否则取源数据库中对应的注释 | 学生表 |


## 请求示例

#### 示例

```bash
curl -X 'POST' http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/schema/listTablesWithRelatedInfo \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: test' \
-H 'Content-Type: application/json' \
-d '{
    "dpCode": "543eec8256cf40418d18c009ad9b319b",
    "pageSize": 1000,
    "current": 1
}'
```


## 响应示例

#### 示例

```json
{
    "success": true,
    "data": {
        "total": 2,
        "list": [
            {
                "dpCode": "543eec8256cf40418d18c009ad9b319b",
                "tableCode": "66024e2bf01541da93e3bd04cdf946a5",
                "tableName": "dwd_mat_voucher",
                "tableCommentExt": "物料凭证"
            },
            {
                "dpCode": "543eec8256cf40418d18c009ad9b319b",
                "tableCode": "b3856941fbe0462b9b9e3dcb95d79886",
                "tableName": "zfsc_spzz_xs_qg_y",
                "tableCommentExt": "住房市场_商品住宅销售情况_月，来源国家统计局"
            }
        ],
        "pageSize": 1000,
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

- apiCode：dext.api.dp.refres.schema.listtableswithrelatedinfo
- groupCode：KORTEX
- catalogCode：DEFAULT
- serviceRegion：tenant
