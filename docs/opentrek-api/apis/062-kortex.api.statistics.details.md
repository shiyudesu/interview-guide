# 文档知识库资源用量-明细数据接口

- 文档序号：062
- 分类：平台功能类 / 知识库管理 / 文档知识库资源用量-明细数据接口
- 唯一编码：sfm.api.ctl-kortex.kortex.api.statistics.details
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/statistics/details
- 文档版本：1787280870455

## 接口概述

获取明细数据列表。[明细数据接口]

获取下方表格的数据，支持分页。根据指定的筛选条件，返回数据集/知识库的汇总信息列表。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| pageNumber | Integer | 是 | Query | 当前页码，从1开始。 | 1 |
| pageSize | Integer | 是 | Query | 每页显示的条目数。 | 10 |
| dataType | String | 否 | Query | 201 目前仅支持 文档知识库 可不传 | 1 |
| startTime | String | 否 | Query | 统计时间点，格式：YYYY-MM-DD。该场景与 endTime 保持一致 | 2025-01-20 |
| endTime | String | 否 | Query | 统计时间点，格式：YYYY-MM-DD。该场景与 startTime 保持一致, 结束时间未传则默认是今天 | 2025-01-26 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| errorCode | Integer | 是 | body | 错误码 | 200 |
| errorMsg | String | 是 | body | 错误信息 | success |
| success | Boolean | 是 | body | 是否成功 | true |
| data | Object | 是 | body | 分页数据对象 | {} |
| data.pageNumber | Integer | 是 | body | 当前页码 | 1 |
| data.pageSize | Integer | 是 | body | 每页显示的条目数 | 10 |
| data.totalCount | Integer | 是 | body | 总条目数 | 35 |
| data.columns | List<Object> | 是 | body | 列定义元数据 | [{"label": "数据类型", "value": "dataType"}] |
| data.columns.label | String | 是 | body | 列的显示名称 | 数据类型 |
| data.columns.value | String | 是 | body | 列的字段Key | dataType |
| data.list | List<Object> | 是 | body | 当前页的数据列表 | [{...}] |
| data.list.kbName | String | 是 | body | 知识库名称 | 海冲测试数据集 |
| data.list.fileCount | Integer | 是 | body | 原始文件数 | 15 |
| data.list.fileSize | Integer | 是 | body | 原始文件大小(Bytes) | 214748364800 |
| data.list.tokenCount | Integer | 是 | body | Token总数 | 100000 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/kortex/api/statistics/details?pageNumber=${pageNumber}&pageSize=${pageSize}' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "columns": [
      {
        "label": "知识库名称",
        "value": "kbName"
      },
      {
        "label": "原始文件数",
        "value": "fileCount"
      },
      {
        "label": "原始文件大小",
        "value": "fileSize"
      },
      {
        "label": "Token总数",
        "value": "tokenCount"
      }
    ],
    "pageNumber": 1,
    "pageSize": 10,
    "totalCount": 1,
    "list": [
      {
        "projectCode": "05bb2bad-689b-4518-9a50-53953c65d59a",
        "date": null,
        "fileCount": 1,
        "fileSize": 3532962,
        "fileOtherSizes": null,
        "tokenCount": 121036,
        "kbName": "高柴验证",
        "kbCode": "v8ocqajdnb16"
      }
    ]
  },
  "errorCode": null,
  "errorMsg": null
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



## 原始文档标识

- apiCode：kortex.api.statistics.details
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
