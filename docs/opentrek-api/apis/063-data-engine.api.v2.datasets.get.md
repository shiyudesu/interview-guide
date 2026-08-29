# 获取数据集列表

- 文档序号：063
- 分类：平台功能类 / 数据中心 / 数据管理 / 获取数据集列表
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.get
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets
- 文档版本：1787280870473

## 接口概述

获取数据集列表[ListDatasets]

获取数据集列表。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| keyword | String | 否 | Query | 搜索关键字 | mmlu |
| tags | String | 否 | Query | 数据集标签KeyID | 1,2,3 |
| pageNumber | Integer | 否 | Query | 列表的页码 | 1 |
| pageSize | Integer | 否 | Query | 每页行数 | 20 |
| order | String | 否 | Query | 排序方式 | DESC |
| orderBy | String | 否 | Query | 排序字段 | createdAt |
| brief | Boolean | 否 | Query | 数据集简述 | false |
| ownerId | String | 否 | Query | 用户ID | xxx |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.datasets | List<Object> | 是 | Body | 数据集列表 |  |
| data.datasets.id | Integer | 是 | Body | 数据集ID | 128 |
| data.datasets.code | String | 是 | Body | 数据集Code | mmlu_no_train |
| data.datasets.name | String | 是 | Body | 数据集名称 | dataset001 |
| data.datasets.description | String | 是 | Body | 数据集描述 |  |
| data.datasets.parquetFilesSize | Integer | 是 | Body | 数据集大小 | 118019 |
| data.datasets.rowCount | Integer | 是 | Body | 数据行数 | 36 |
| data.datasets.downloadCount | Integer | 是 | Body | 下载次数 | 9 |
| data.datasets.tags | List<Object> | 是 | Body | 标签列表 |  |
| data.datasets.tags.id | Integer | 是 | Body | 标签ID | 7 |
| data.datasets.tags.name | String | 是 | Body | 标签名称 | 多标签分类 |
| data.datasets.tags.value | String | 是 | Body | 标签值 |  |
| data.datasets.ownerId | String | 是 | Body | 数据集所有者ID | 1631044****3440 |
| data.datasets.ownerName | String | 是 | Body | 数据集所有者用户名 | admin |
| data.datasets.tenantCode | String | 是 | Body | 租户Code | sfmboost |
| data.datasets.workspaceCode | String | 是 | Body | 工作组Code | default_workspace |
| data.datasets.createdAt | String | 是 | Body | 创建时间 | 2021-01-30T12:51:33.028Z |
| data.datasets.updatedAt | String | 是 | Body | 更新时间 | 2021-01-30T12:51:33.028Z |
| data.pageSize | Integer | 是 | Body | 每页行数 | 20 |
| data.totalCount | Integer | 是 | Body | 总数量 | 79 |
| data.pageNumber | Integer | 是 | Body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets?keyword=${keyword}&tags=${tags}&pageNumber=${pageNumber}&pageSize=${pageSize}&order=${order}&orderBy=${orderBy}&brief=${brief}&ownerId=${ownerId}' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "datasets": [
    {
      "id": 128,
      "code": "mmlu_no_train",
      "name": "dataset001",
      "description": "",
      "parquetFilesSize": 118019,
      "rowCount": 36,
      "downloadCount": 9,
      "tags": [
        {
          "id": 7,
          "name": "多标签分类",
          "value": ""
        },
        {
          "id": 202,
          "name": "法语",
          "value": "法语标签值"
        }
      ],
      "ownerId": "1631044****3440",
      "ownerName": "admin",
      "tenantCode": "sfmboost",
      "workspaceCode": "default_workspace",
      "createdAt": "2021-01-30T12:51:33.028Z",
      "updatedAt": "2021-01-30T12:51:33.028Z"
    }
  ],
  "pageSize": 20,
  "totalCount": 79,
  "pageNumber": 1
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

- apiCode：data-engine.api.v2.datasets.get
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
