# 获取数据集预览数据

- 文档序号：075
- 分类：平台功能类 / 数据中心 / 数据管理 / 获取数据集预览数据
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.viewer
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/viewer
- 文档版本：1787280870539

## 接口概述

获取数据集预览数据[ListDatasetViewerData]

获取数据集预览数据。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Path传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| code | String | 是 | Url | 数据集Code | mmlu_no_train |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| subset | String | 否 | Query | 子集Code | default |
| split | String | 否 | Query | 切片Code | train |
| pageNumber | Integer | 否 | Query | 列表的页码 | 1 |
| pageSize | Integer | 否 | Query | 分页查询时设置的每页行数 | 100 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.schema | List<Object> | 是 | Body | 字段信息 |  |
| data.schema.columnName | String | 是 | Body | 字段名称 | pdf_url |
| data.schema.columnType | String | 是 | Body | 字段类型 | string |
| data.schema.columnPhysicalType | String | 是 | Body | 字段物理类型 | varchar |
| data.data | List<Object> | 是 | Body | 数据内容 | [["oss://xxx/tenant/dataset/xxx/tmp/xxx.pdf", {"path": "tmp/xxx.pdf", "bytes": null}, 19849], ...] |
| data.status | String | 是 | Body | 视图构建状态：BUILDING，BUILD_FAILED，BUILT | BUILD_FAILED |
| data.message | String | 是 | Body | 错误信息 | .... |
| data.pageSize | Integer | 是 | Body | 每页行数 | 100 |
| data.totalCount | Integer | 是 | Body | 总行数 | 12389 |
| data.pageNumber | Integer | 是 | Body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/${code}/viewer?subset=${subset}&split=${split}&pageNumber=${pageNumber}&pageSize=${pageSize}' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Content-Type: application/json'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "schema": [
      {
        "columnName": "pdf_url",
        "columnType": "string",
        "columnPhysicalType": "varchar"
      },
      {
        "columnName": "file",
        "columnType": "Doc",
        "columnPhysicalType": "struct(bytes blob, path varchar)"
      },
      {
        "columnName": "size",
        "columnType": "int64",
        "columnPhysicalType": "int64"
      }
    ],
    "data": [
      [
        "oss://xxx/tenant/dataset/xxx/tmp/xxx.pdf",
        {
          "path": "tmp/xxx.pdf",
          "bytes": null
        },
        19849
      ]
    ],
    "status": "BUILD_FAILED",
    "message": "...",
    "pageSize": 100,
    "totalCount": 12389,
    "pageNumber": 1
  }
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

- apiCode：data-engine.api.v2.datasets.Code.viewer
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
