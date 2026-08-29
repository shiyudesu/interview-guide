# 获取数据集详情

- 文档序号：067
- 分类：平台功能类 / 数据中心 / 数据管理 / 获取数据集详情
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.get
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}
- 文档版本：1787280870495

## 接口概述

获取数据集详情[GetDataset]

获取数据集详情。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.code | String | 是 | Body | 数据集Code | mmlu_no_train |
| data.name | String | 是 | Body | 数据集名称 | 张三测试数据集 |
| data.description | String | 是 | Body | 数据集描述 |  |
| data.originalFilesSize | Integer | 是 | Body | 原始资源文件大小，单位bytes | 118019 |
| data.parquetFilesSize | Integer | 是 | Body | 数据集大小，单位bytes | 118019 |
| data.rowCount | Integer | 是 | Body | 数据行数 | 36 |
| data.downloadCount | Integer | 是 | Body | 下载次数 | 9 |
| data.tags | List<Object> | 是 | Body | 标签列表 |  |
| data.tags.id | Integer | 是 | Body | 标签ID | 123 |
| data.tags.name | String | 是 | Body | 标签名称 | size_scale |
| data.tags.value | String | 是 | Body | 标签值 | 1w-10w |
| data.subsets | List<Object> | 是 | Body | 子集列表 |  |
| data.subsets.code | String | 是 | Body | 子集Code | default |
| data.subsets.name | String | 是 | Body | 子集名称 | default |
| data.subsets.parquetFilesSize | Integer | 是 | Body | 子集数据大小，单位bytes | 0 |
| data.subsets.rowCount | Integer | 是 | Body | 子集数据行数 | 19 |
| data.subsets.features | List<Object> | 是 | Body | 字段列表 |  |
| data.subsets.features.columnName | String | 是 | Body | 字段名称 | __idx |
| data.subsets.features.columnType | String | 是 | Body | 字段类型 | string |
| data.subsets.features.columnPhysicalType | String | 是 | Body | 字段物理类型 | varchar |
| data.subsets.features.columnComment | String | 是 | Body | 字段描述 | 数据项唯一标识 |
| data.subsets.splits | List<Object> | 是 | Body | 切片列表 |  |
| data.subsets.splits.code | String | 是 | Body | 切片Code | train |
| data.subsets.splits.subset | String | 是 | Body | 所属子集 | default |
| data.subsets.splits.name | String | 是 | Body | 切片名称 | train |
| data.subsets.splits.parquetFilesSize | Integer | 是 | Body | 切片数据大小，单位bytes | 0 |
| data.subsets.splits.rowCount | Integer | 是 | Body | 切片数据行数 | 19 |
| data.subsets.splits.dataFiles | List<String> |  | Body | 数据文件列表 | ["car.jpg", "dog.jpg", "cat.jpg"] |
| data.subsets.splits.producer | String |  | Body | 数据来源标记：KN_DATASET、KN_PROCESS、KN_LABEL、UNKNOWN | KN_DATASET |
| data.ownerId | String | 是 | Body | 数据集所有者ID | 1631044****3440 |
| data.ownerName | String | 是 | Body | 数据集所有者用户名 | admin |
| data.tenantCode | String | 是 | Body | 租户Code | sfmboost |
| data.workspaceCode | String | 是 | Body | 工作组Code | default_workspace |
| data.createdAt | String | 是 | Body | 创建时间 | 2021-01-30T12:51:33.028Z |
| data.updatedAt | String | 是 | Body | 更新时间 | 2021-01-30T12:51:33.028Z |
| data.repoPath | String | 是 | Body | 数据集仓库地址 | sfm/dataset/baseline/mmlu_no_train/main |
| data.parquetPath | String | 是 | Body | 数据视图地址 | sfm/dataset/baseline/mmlu_no_train/parquet |
| data.summaryModified | String | 是 | Body | 数据集摘要修改时间 | 2021-01-30T12:51:33.028Z |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/${code} \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "code": "mmlu_no_train",
  "name": "张三测试数据集",
  "description": "",
  "parquetFilesSize": 118019,
  "rowCount": 36,
  "downloadCount": 9,
  "tags": [
    {
      "id": 123,
      "name": "size_scale",
      "value": "1w-10w"
    }
  ],
  "subsets": [
    {
      "code": "default",
      "name": "default",
      "parquetFilesSize": 0,
      "rowCount": 19,
      "features": [
        {
          "columnName": "__idx",
          "columnType": "string",
          "columnPhysicalType": "varchar",
          "columnComment": ""
        },
        {
          "columnName": "__content",
          "columnType": "string",
          "columnPhysicalType": "varchar",
          "columnComment": ""
        }
      ],
      "splits": [
        {
          "code": "train",
          "subset": "default",
          "name": "train",
          "parquetFilesSize": 0,
          "rowCount": 19
        }
      ]
    }
  ],
  "ownerId": "1631044****3440",
  "ownerName": "admin",
  "tenantCode": "sfmboost",
  "workspaceCode": "default_workspace",
  "createdAt": "2021-01-30T12:51:33.028Z",
  "updatedAt": "2021-01-30T12:51:33.028Z",
  "repoPath": "sfm/dataset/baseline/mmlu_no_train/main",
  "parquetPath": "sfm/dataset/baseline/mmlu_no_train/parquet"
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

- apiCode：data-engine.api.v2.datasets.Code.get
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
